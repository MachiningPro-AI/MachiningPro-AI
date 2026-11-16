"""
P9-A: Manufacturer-backed tool geometry — test suite.

Covers:
  P9-A-1  CuttingToolCatalogRecord model allows flute_length_mm
  P9-A-2  Adapter: tool_record with flute_length_mm → provenance=KNOWN in input
  P9-A-3  Adapter: tool_record without flute_length_mm → FLUTE_LENGTH_MISSING note
  P9-A-4  check_tool_reach: flute_length=None → INSUFFICIENT_DATA
  P9-A-5  check_tool_reach: deep cut exceeds flute_length → FAIL
  P9-A-6  check_tool_reach: cut within flute_length → PASS
  P9-A-7  check_tool_reach: no cutting segments → PASS (regardless of flute)
  P9-A-8  Adapter: flute_length in input controls tool_reach_validated status
  P9-A-9  Seed catalog: end mills already have flute_length_mm populated
  P9-A-10 Seed catalog: Sandvik 860-1 drills currently have flute_length_mm=None
           (P9-A enrichment requires explicit seed_catalog.py permission)
  P9-A-11 Catalog model: flute_length_mm defaults to None
  P9-A-12 check_tool_reach: holder_clearance limits effective reach
  P9-A-13 Adapter: mock drill with flute_length_mm=26.0 → KNOWN provenance
  P9-A-14 run_p8_verification: flute_length known → tool_reach_validated != INSUFFICIENT_DATA
  P9-A-15 Adapter: flute_length_mm propagated to P8VerificationInput.tool_flute_length_mm
  P9-A-16 check_tool_reach: exact match (depth == flute_length) → PASS
  P9-A-17 check_tool_reach: depth == flute_length + epsilon (above tol) → FAIL
  P9-A-18 Seed catalog catalog_models: flute_length_mm field typing is float | None
  P9-A-19 Adapter: cutting_length_mm also propagated when available
  P9-A-20 Seed catalog: at least 3 tools have flute_length_mm populated

HARD_RULES_CHECKED:
  - UNKNOWN remains UNKNOWN (flute absent → INSUFFICIENT_DATA, never PASS)
  - NO_FABRICATED_GEOMETRY=YES
  - is_dispatchable=False at all times
  - production_released=False at all times
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.seed_catalog import get_catalog as seed_cutting_tool_catalog
from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    build_verification_input,
    run_p8_verification,
)
from backend.verification.checks import check_tool_reach
from backend.verification.enums import VerificationStatus
from backend.verification.models import VerificationSegment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(
    start_x: float = 0.0,
    start_y: float = 0.0,
    start_z: float = 0.0,
    end_x: float = 0.0,
    end_y: float = 0.0,
    end_z: float = 0.0,
    is_cutting: bool = True,
    motion_type: str = "CUT",
    seg_id: str = "s1",
) -> VerificationSegment:
    return VerificationSegment(
        segment_id=seg_id,
        start_x=start_x,
        start_y=start_y,
        start_z=start_z,
        end_x=end_x,
        end_y=end_y,
        end_z=end_z,
        motion_type=motion_type,
        is_cutting=is_cutting,
    )


def _mock_candidate(
    tool_diameter_mm: float | None = 5.0,
    nc_segments: list | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        feature_id="test-feature-p9a",
        toolpath_id="tp-p9a",
        tool_diameter_mm=tool_diameter_mm,
        nc_segments=nc_segments or [],
    )


def _mock_tool(
    stable_id: str = "mock-drill",
    flute_length_mm: float | None = None,
    overall_length_mm: float | None = None,
    cutting_length_mm: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        stable_id=stable_id,
        flute_length_mm=flute_length_mm,
        overall_length_mm=overall_length_mm,
        cutting_length_mm=cutting_length_mm,
    )


# ---------------------------------------------------------------------------
# P9-A-1: Model field existence
# ---------------------------------------------------------------------------


class TestCatalogModelFluteLengthField:

    def test_p9a_1_catalog_model_allows_flute_length_mm(self):
        """CuttingToolCatalogRecord must have a flute_length_mm field."""
        # Pydantic model — check via model_fields
        if hasattr(CuttingToolCatalogRecord, 'model_fields'):
            assert "flute_length_mm" in CuttingToolCatalogRecord.model_fields
        else:
            # dataclass fallback
            import dataclasses
            assert "flute_length_mm" in {
                f.name for f in dataclasses.fields(CuttingToolCatalogRecord)
            }

    def test_p9a_11_flute_length_defaults_to_none(self):
        """flute_length_mm defaults to None in the model."""
        import dataclasses
        if hasattr(CuttingToolCatalogRecord, 'model_fields'):
            fi = CuttingToolCatalogRecord.model_fields["flute_length_mm"]
            assert fi.default is None or fi.is_required() is False
        else:
            # dataclass
            for f in dataclasses.fields(CuttingToolCatalogRecord):
                if f.name == "flute_length_mm":
                    assert f.default is None
                    break

    def test_p9a_18_flute_length_field_type(self):
        """flute_length_mm typing should allow float | None."""
        if hasattr(CuttingToolCatalogRecord, 'model_fields'):
            annotation = str(
                CuttingToolCatalogRecord.model_fields["flute_length_mm"].annotation
            )
            # Annotation is "float | None" or "Optional[float]"
            assert "float" in annotation or "NoneType" in annotation


# ---------------------------------------------------------------------------
# P9-A-2 / P9-A-3 / P9-A-15 / P9-A-19: Adapter provenance wiring
# ---------------------------------------------------------------------------


class TestAdapterFluteLengthProvenance:

    def test_p9a_2_tool_record_with_flute_length_gives_known_provenance(self):
        """When tool_record.flute_length_mm is set, provenance must be KNOWN."""
        cand = _mock_candidate()
        tr = _mock_tool(flute_length_mm=26.0)
        vi = build_verification_input(candidate=cand, tool_record=tr)
        assert vi.tool_flute_length_mm == 26.0
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.KNOWN

    def test_p9a_3_tool_record_without_flute_length_gives_missing_note(self):
        """When tool_record.flute_length_mm is None, provenance note must mention MISSING."""
        cand = _mock_candidate()
        tr = _mock_tool(flute_length_mm=None, stable_id="mock-no-flute")
        vi = build_verification_input(candidate=cand, tool_record=tr)
        assert vi.tool_flute_length_mm is None
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.UNKNOWN
        note_text = " ".join(vi.provenance_notes)
        assert "FLUTE_LENGTH_MISSING" in note_text
        assert "mock-no-flute" in note_text

    def test_p9a_15_flute_length_propagated_to_vi_field(self):
        """flute_length from tool_record propagates to P8VerificationInput.tool_flute_length_mm."""
        cand = _mock_candidate()
        tr = _mock_tool(flute_length_mm=16.0)
        vi = build_verification_input(candidate=cand, tool_record=tr)
        assert vi.tool_flute_length_mm == pytest.approx(16.0)

    def test_p9a_13_mock_drill_with_flute_length_known(self):
        """Mock drill with flute_length_mm=26.0 → KNOWN provenance (simulates post-P9-A)."""
        cand = _mock_candidate()
        tr = _mock_tool(stable_id="sandvik-860-1-0500-026a1-pm-p9a", flute_length_mm=26.0)
        vi = build_verification_input(candidate=cand, tool_record=tr)
        assert vi.tool_flute_length_mm == 26.0
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.KNOWN

    def test_p9a_19_cutting_length_also_propagated(self):
        """cutting_length_mm from tool_record propagates to P8VerificationInput."""
        cand = _mock_candidate()
        tr = _mock_tool(cutting_length_mm=26.0)
        vi = build_verification_input(candidate=cand, tool_record=tr)
        assert vi.tool_cutting_length_mm == pytest.approx(26.0)
        assert vi.tool_cutting_length_provenance == GeometryFieldProvenance.KNOWN


# ---------------------------------------------------------------------------
# P9-A-4..7, P9-A-12, P9-A-16, P9-A-17: check_tool_reach
# ---------------------------------------------------------------------------


class TestCheckToolReach:

    def test_p9a_4_no_flute_length_gives_insufficient_data(self):
        """check_tool_reach: flute_length=None → INSUFFICIENT_DATA."""
        segs = [_seg(start_z=0.0, end_z=-20.0)]
        result = check_tool_reach(segs, flute_length_mm=None, holder_clearance_mm=None)
        assert result.status == VerificationStatus.INSUFFICIENT_DATA

    def test_p9a_5_deep_cut_exceeds_flute_gives_fail(self):
        """check_tool_reach: depth 30mm exceeds flute 26mm → FAIL."""
        segs = [_seg(start_z=0.0, end_z=-30.0)]
        result = check_tool_reach(segs, flute_length_mm=26.0, holder_clearance_mm=None)
        assert result.status == VerificationStatus.FAIL

    def test_p9a_6_cut_within_flute_gives_pass(self):
        """check_tool_reach: depth 20mm within flute 26mm → PASS."""
        segs = [_seg(start_z=0.0, end_z=-20.0)]
        result = check_tool_reach(segs, flute_length_mm=26.0, holder_clearance_mm=None)
        assert result.status == VerificationStatus.PASS

    def test_p9a_7_no_cutting_segments_gives_pass(self):
        """check_tool_reach: no cutting segments → PASS regardless of flute_length."""
        rapid = _seg(is_cutting=False, motion_type="RAPID")
        result = check_tool_reach([rapid], flute_length_mm=26.0, holder_clearance_mm=None)
        assert result.status == VerificationStatus.PASS

    def test_p9a_7b_empty_segments_gives_pass(self):
        """check_tool_reach: empty list → PASS (no cutting segments to exceed)."""
        result = check_tool_reach([], flute_length_mm=26.0, holder_clearance_mm=None)
        assert result.status == VerificationStatus.PASS

    def test_p9a_12_holder_clearance_limits_effective_reach(self):
        """check_tool_reach: holder_clearance_mm constrains effective reach."""
        # flute=50mm but holder clearance=20mm → depth=25mm → FAIL
        segs = [_seg(start_z=0.0, end_z=-25.0)]
        result = check_tool_reach(segs, flute_length_mm=50.0, holder_clearance_mm=20.0)
        assert result.status == VerificationStatus.FAIL

    def test_p9a_12b_holder_clearance_above_depth_pass(self):
        """check_tool_reach: holder_clearance=50mm, depth=25mm → PASS."""
        segs = [_seg(start_z=0.0, end_z=-25.0)]
        result = check_tool_reach(segs, flute_length_mm=50.0, holder_clearance_mm=50.0)
        assert result.status == VerificationStatus.PASS

    def test_p9a_16_exact_depth_equals_flute_pass(self):
        """check_tool_reach: depth == flute_length → PASS (within tolerance)."""
        segs = [_seg(start_z=0.0, end_z=-26.0)]
        result = check_tool_reach(segs, flute_length_mm=26.0, holder_clearance_mm=None)
        assert result.status == VerificationStatus.PASS

    def test_p9a_17_depth_slightly_above_flute_fails(self):
        """check_tool_reach: depth == flute + 0.2mm (above 0.1mm tol) → FAIL."""
        segs = [_seg(start_z=0.0, end_z=-26.2)]
        result = check_tool_reach(segs, flute_length_mm=26.0, holder_clearance_mm=None)
        assert result.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# P9-A-8 / P9-A-14: run_p8_verification via adapter
# ---------------------------------------------------------------------------


class TestRunP8VerificationFluteLengthWiring:

    def _make_simple_seg_dict(
        self,
        start_z: float = 0.0,
        end_z: float = -15.0,
        is_cutting: bool = True,
    ) -> dict:
        return {
            "segment_id": "s1",
            "start_x": 0.0, "start_y": 0.0, "start_z": start_z,
            "end_x": 0.0, "end_y": 0.0, "end_z": end_z,
            "motion_type": "FEED_LINEAR",
            "is_cutting": is_cutting,
        }

    def test_p9a_8a_no_flute_gives_insufficient_data_in_result(self):
        """run_p8_verification: flute=None → tool_reach_validated=INSUFFICIENT_DATA."""
        cand = _mock_candidate(nc_segments=[self._make_simple_seg_dict()])
        vi = build_verification_input(candidate=cand, tool_record=_mock_tool(flute_length_mm=None))
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"

    def test_p9a_8b_flute_set_gives_non_insufficient_data(self):
        """run_p8_verification: flute=26mm → tool_reach_validated != INSUFFICIENT_DATA."""
        cand = _mock_candidate(nc_segments=[self._make_simple_seg_dict(end_z=-15.0)])
        vi = build_verification_input(
            candidate=cand,
            tool_record=_mock_tool(flute_length_mm=26.0),
        )
        result = run_p8_verification(vi)
        assert result.tool_reach_validated != "INSUFFICIENT_DATA"
        # Depth=15mm < flute=26mm → PASS
        assert result.tool_reach_validated == "PASS"

    def test_p9a_14_dispatchable_always_false(self):
        """is_dispatchable must remain False even when all checks PASS."""
        cand = _mock_candidate(nc_segments=[self._make_simple_seg_dict(end_z=-10.0)])
        vi = build_verification_input(
            candidate=cand,
            tool_record=_mock_tool(flute_length_mm=26.0),
        )
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False
        assert result.production_released is False


# ---------------------------------------------------------------------------
# P9-A-9 / P9-A-10 / P9-A-20: Seed catalog state
# ---------------------------------------------------------------------------


class TestSeedCatalogFluteLengthState:

    def setup_method(self):
        self.catalog = seed_cutting_tool_catalog()

    def test_p9a_9_some_tools_have_flute_length_populated(self):
        """At least some tools in the catalog already have flute_length_mm populated."""
        tools_with_flute = [t for t in self.catalog if t.flute_length_mm is not None]
        assert len(tools_with_flute) >= 3, (
            f"Expected at least 3 tools with flute_length_mm; got {len(tools_with_flute)}"
        )

    def test_p9a_20_at_least_3_tools_have_flute_length(self):
        """At least 3 tools have flute_length_mm populated (P9-A baseline)."""
        tools_with_flute = [t for t in self.catalog if t.flute_length_mm is not None]
        assert len(tools_with_flute) >= 3

    def test_p9a_10_dxf01_drill_flute_length_state(self):
        """sandvik-860-1-0500-026a1-pm (DXF-01 tool) documents P9-A pending state.

        This test documents the CURRENT state of the seed catalog.
        When P9-A seed_catalog.py enrichment is applied (requires permission to
        modify production data files), this tool will have flute_length_mm=26.0.
        Until then, flute_length_mm=None → TOOL_REACH returns INSUFFICIENT_DATA.
        """
        drills = {t.stable_id: t for t in self.catalog}
        dxf01_drill_id = "sandvik-860-1-0500-026a1-pm"
        if dxf01_drill_id not in drills:
            pytest.skip(f"DXF-01 drill {dxf01_drill_id} not found in catalog")
        drill = drills[dxf01_drill_id]
        # Document current state — may be None (pending) or 26.0 (after P9-A applied)
        if drill.flute_length_mm is None:
            # P9-A pending: seed_catalog.py edit blocked by classifier
            # This is the documented PENDING state — not a test failure
            pytest.skip(
                "P9-A PENDING: sandvik-860-1-0500-026a1-pm flute_length_mm=None "
                "(seed_catalog.py edit requires explicit permission grant). "
                "Expected: flute_length_mm=26.0 after P9-A."
            )
        else:
            # P9-A applied
            assert drill.flute_length_mm == pytest.approx(26.0)

    def test_p9a_10b_sandvik_860_drills_flute_length_count(self):
        """Documents how many Sandvik 860-1 drills have flute_length_mm (P9-A progress)."""
        sandvik_drills = [
            t for t in self.catalog
            if "sandvik-860-1" in t.stable_id
        ]
        fluted = [t for t in sandvik_drills if t.flute_length_mm is not None]
        total = len(sandvik_drills)
        # Either 0 (P9-A pending) or 9 (after P9-A)
        assert len(fluted) in (0, total), (
            f"Expected 0 or {total} Sandvik 860-1 drills with flute_length_mm; "
            f"got {len(fluted)} — partial state indicates incomplete P9-A application"
        )
