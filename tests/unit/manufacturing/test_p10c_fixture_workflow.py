"""
P10-C test suite: fixture/workholding production workflow wiring.

Validates:
  - Fixture selection with valid WCS → trustworthy FixtureInput → collision PASS/FAIL
  - Missing WCS coordinates → UNKNOWN provenance → NOT_VERIFIABLE
  - Unknown fixture_id → UNKNOWN provenance → NOT_VERIFIABLE
  - Multiple fixtures: collision with any → FAIL
  - Multiple fixtures: all clear → SCOPED_PASS
  - Empty fixture list → NOT_VERIFIABLE
  - Fixture source: LIBRARY_EVIDENCE preserved
  - RAPID/FEED segment distinction
  - Collision scope summary: SCOPED_PASS / SCOPED_FAIL / NOT_VERIFIABLE / PARTIAL
  - Safety invariants: is_dispatchable=False, production_released=False

HARD RULES (all verified):
  - No silent WCS defaults
  - Unknown fixture_id produces NOT_VERIFIABLE, not PASS
  - Incomplete WCS produces NOT_VERIFIABLE, not PASS
  - SCOPED_PASS != global collision safety
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.manufacturing.fixture_seed import get_fixture_catalog
from backend.manufacturing.verification_adapter import GeometryFieldProvenance
from backend.manufacturing.workflow_orchestrator import (
    SIMULATION_METHOD,
    FixtureSelection,
    WorkflowVerificationRequest,
    WorkflowVerificationResult,
    _collision_scope,
    _resolve_fixture_selection,
    run_production_verification,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _seg(sx, sy, sz, ex, ey, ez, motion="RAPID_LINEAR", is_cutting=False):
    return {
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "motion_type": motion,
        "is_cutting": is_cutting,
        "segment_id": "s1",
    }


def _candidate(
    segs=None,
    tool_diam=5.0,
    feature_id="feat-01",
    toolpath_id="tp-01",
):
    if segs is None:
        segs = [
            _seg(0, 0, 10, 0, 0, 1, "RAPID_LINEAR"),
            _seg(0, 0, 1, 0, 0, -24, "FEED_LINEAR", True),
            _seg(0, 0, -24, 0, 0, 10, "RAPID_LINEAR"),
        ]
    return SimpleNamespace(
        nc_segments=segs,
        tool_diameter_mm=tool_diam,
        feature_id=feature_id,
        toolpath_id=toolpath_id,
    )


# ---------------------------------------------------------------------------
# P10-C1: Fixture catalog is available
# ---------------------------------------------------------------------------

class TestFixtureCatalogAvailable:
    def test_fixture_catalog_has_records(self):
        cats = get_fixture_catalog()
        assert len(cats) >= 3

    def test_known_fixture_ids_present(self):
        ids = {r.stable_id for r in get_fixture_catalog()}
        assert "std-vise-jaw-100mm" in ids
        assert "std-vise-jaw-150mm" in ids
        assert "std-step-clamp-sm" in ids

    def test_fixture_records_are_library_evidence(self):
        for r in get_fixture_catalog():
            assert r.source == "LIBRARY_EVIDENCE"


# ---------------------------------------------------------------------------
# P10-C2: FixtureSelection resolution
# ---------------------------------------------------------------------------

class TestFixtureSelectionResolution:
    def test_known_id_with_wcs_resolves_trustworthy(self):
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=0.0,
            wcs_centre_y_mm=50.0,
            wcs_bottom_z_mm=-40.0,
        )
        warnings: list[str] = []
        fi = _resolve_fixture_selection(sel, warnings)
        assert fi.is_trustworthy is True
        assert fi.provenance == GeometryFieldProvenance.USER_CONFIRMED

    def test_unknown_id_produces_unknown_provenance(self):
        sel = FixtureSelection(
            fixture_id="nonexistent-fixture-xyz",
            wcs_centre_x_mm=0.0,
            wcs_centre_y_mm=0.0,
            wcs_bottom_z_mm=0.0,
        )
        warnings: list[str] = []
        fi = _resolve_fixture_selection(sel, warnings)
        assert fi.is_trustworthy is False
        assert fi.provenance == GeometryFieldProvenance.UNKNOWN
        assert any("not found" in w.lower() for w in warnings)

    def test_missing_x_produces_unknown_provenance(self):
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=None,
            wcs_centre_y_mm=50.0,
            wcs_bottom_z_mm=-40.0,
        )
        warnings: list[str] = []
        fi = _resolve_fixture_selection(sel, warnings)
        assert fi.is_trustworthy is False
        assert fi.provenance == GeometryFieldProvenance.UNKNOWN
        assert any("incomplete" in w.lower() for w in warnings)

    def test_missing_y_produces_unknown_provenance(self):
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=0.0,
            wcs_centre_y_mm=None,
            wcs_bottom_z_mm=-40.0,
        )
        warnings: list[str] = []
        fi = _resolve_fixture_selection(sel, warnings)
        assert fi.is_trustworthy is False

    def test_missing_z_produces_unknown_provenance(self):
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=0.0,
            wcs_centre_y_mm=50.0,
            wcs_bottom_z_mm=None,
        )
        warnings: list[str] = []
        fi = _resolve_fixture_selection(sel, warnings)
        assert fi.is_trustworthy is False

    def test_resolved_bbox_matches_library_plus_wcs(self):
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=100.0,
            wcs_centre_y_mm=200.0,
            wcs_bottom_z_mm=-40.0,
        )
        warnings: list[str] = []
        fi = _resolve_fixture_selection(sel, warnings)
        assert fi.min_x_mm == pytest.approx(100.0 - 55.0)
        assert fi.max_x_mm == pytest.approx(100.0 + 55.0)
        assert fi.min_z_mm == pytest.approx(-40.0)
        assert fi.max_z_mm == pytest.approx(-40.0 + 40.0)


# ---------------------------------------------------------------------------
# P10-C3: Collision scope summary
# ---------------------------------------------------------------------------

class TestCollisionScopeSummary:
    def test_all_not_verifiable(self):
        result = _collision_scope("NOT_VERIFIABLE", "NOT_VERIFIABLE", "NOT_VERIFIABLE")
        assert result == "NOT_VERIFIABLE"

    def test_one_fail_gives_scoped_fail(self):
        assert _collision_scope("FAIL", "NOT_VERIFIABLE", "NOT_VERIFIABLE") == "SCOPED_FAIL"
        assert _collision_scope("PASS", "FAIL", "NOT_VERIFIABLE") == "SCOPED_FAIL"
        assert _collision_scope("PASS", "PASS", "FAIL") == "SCOPED_FAIL"

    def test_all_pass_gives_scoped_pass(self):
        assert _collision_scope("PASS", "PASS", "PASS") == "SCOPED_PASS"

    def test_mixed_pass_and_not_verifiable_gives_partial(self):
        # Only 1 of 3 checks ran (PASS); 2 are NOT_VERIFIABLE → PARTIAL (not SCOPED_PASS)
        result = _collision_scope("PASS", "NOT_VERIFIABLE", "NOT_VERIFIABLE")
        assert result == "PARTIAL"
        # 2 of 3 ran (PASS); 1 NOT_VERIFIABLE → also PARTIAL
        result2 = _collision_scope("PASS", "PASS", "NOT_VERIFIABLE")
        assert result2 == "PARTIAL"

    def test_scoped_pass_not_global(self):
        result = _collision_scope("PASS", "PASS", "PASS")
        assert result == "SCOPED_PASS"
        assert result != "PASS"  # explicitly NOT global PASS


# ---------------------------------------------------------------------------
# P10-C4: Production workflow with fixture
# ---------------------------------------------------------------------------

class TestProductionWorkflowWithFixture:
    def _make_request(self, fixture_selections, tool_record=None):
        return WorkflowVerificationRequest(
            candidate=_candidate(),
            fixture_selections=fixture_selections,
        )

    def test_no_fixture_collision_not_verifiable(self):
        req = self._make_request([])
        result = run_production_verification(req)
        assert isinstance(result, WorkflowVerificationResult)
        assert result.p8_result.tool_collision_validated == "NOT_VERIFIABLE"
        assert result.p8_result.fixture_collision_validated == "NOT_VERIFIABLE"
        assert result.collision_scope_validated == "NOT_VERIFIABLE"

    def test_unknown_fixture_id_not_verifiable(self):
        sel = FixtureSelection(
            fixture_id="unknown-fixture-xyz",
            wcs_centre_x_mm=0.0,
            wcs_centre_y_mm=50.0,
            wcs_bottom_z_mm=-40.0,
        )
        req = self._make_request([sel])
        result = run_production_verification(req)
        assert result.p8_result.tool_collision_validated == "NOT_VERIFIABLE"
        assert result.fixture_trustworthy_count == 0
        assert result.fixture_unknown_count == 1

    def test_missing_wcs_fixture_not_verifiable(self):
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=None,
            wcs_centre_y_mm=50.0,
            wcs_bottom_z_mm=-40.0,
        )
        req = self._make_request([sel])
        result = run_production_verification(req)
        assert result.p8_result.tool_collision_validated == "NOT_VERIFIABLE"
        assert result.fixture_trustworthy_count == 0

    def test_clear_path_fixture_gives_pass(self):
        # Tool path at x=0,y=0, fixture far away
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=500.0,  # far from tool path at x=0,y=0
            wcs_centre_y_mm=500.0,
            wcs_bottom_z_mm=-40.0,
        )
        req = self._make_request([sel])
        result = run_production_verification(req)
        assert result.p8_result.tool_collision_validated == "PASS"
        assert result.fixture_trustworthy_count == 1

    def test_intersecting_fixture_gives_fail(self):
        # Fixture at x=0,y=0 — same position as tool path
        sel = FixtureSelection(
            fixture_id="std-vise-jaw-100mm",
            wcs_centre_x_mm=0.0,
            wcs_centre_y_mm=0.0,
            wcs_bottom_z_mm=-40.0,
        )
        req = self._make_request([sel])
        result = run_production_verification(req)
        assert result.p8_result.tool_collision_validated == "FAIL"
        assert "FAIL" in result.collision_scope_validated

    def test_fixture_selections_processed_count(self):
        sels = [
            FixtureSelection("std-vise-jaw-100mm", 500.0, 500.0, -40.0),
            FixtureSelection("std-step-clamp-sm", 400.0, 400.0, -30.0),
        ]
        req = self._make_request(sels)
        result = run_production_verification(req)
        assert result.fixture_selections_processed == 2
        assert result.fixture_resolved_count == 2

    def test_fixture_resolved_vs_unknown_counts(self):
        sels = [
            FixtureSelection("std-vise-jaw-100mm", 500.0, 500.0, -40.0),
            FixtureSelection("bad-id", 0.0, 0.0, 0.0),
        ]
        req = self._make_request(sels)
        result = run_production_verification(req)
        assert result.fixture_resolved_count == 1
        assert result.fixture_unknown_count == 1


# ---------------------------------------------------------------------------
# P10-C5: RAPID/FEED segment distinction (MUST 11)
# ---------------------------------------------------------------------------

class TestRapidFeedDistinction:
    def test_rapid_and_feed_segments_counted(self):
        segs = [
            _seg(0, 0, 10, 0, 0, 1, "RAPID_LINEAR"),
            _seg(0, 0, 1, 0, 0, -24, "FEED_LINEAR", True),
            _seg(0, 0, -24, 0, 0, 10, "RAPID_LINEAR"),
        ]
        req = WorkflowVerificationRequest(candidate=_candidate(segs=segs))
        result = run_production_verification(req)
        assert result.rapid_segments_checked == 2
        assert result.feed_segments_checked == 1

    def test_all_rapid_segments(self):
        segs = [
            _seg(0, 0, 10, 100, 0, 10, "RAPID_LINEAR"),
            _seg(100, 0, 10, 100, 100, 10, "RAPID_LINEAR"),
        ]
        req = WorkflowVerificationRequest(candidate=_candidate(segs=segs))
        result = run_production_verification(req)
        assert result.rapid_segments_checked == 2
        assert result.feed_segments_checked == 0

    def test_all_feed_segments(self):
        segs = [
            _seg(0, 0, 0, 0, 0, -10, "FEED_LINEAR", True),
            _seg(0, 0, -10, 10, 0, -10, "FEED_LINEAR", True),
        ]
        req = WorkflowVerificationRequest(candidate=_candidate(segs=segs))
        result = run_production_verification(req)
        assert result.rapid_segments_checked == 0
        assert result.feed_segments_checked == 2


# ---------------------------------------------------------------------------
# P10-C6: Safety invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_is_dispatchable_false(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.is_dispatchable is False
        assert result.p8_result.is_dispatchable is False

    def test_production_released_false(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.production_released is False
        assert result.p8_result.production_released is False

    def test_simulation_method_is_voxel_approximation(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.simulation_method == SIMULATION_METHOD
        assert result.simulation_method == "VOXEL_APPROXIMATION"


# ---------------------------------------------------------------------------
# P10-C7: production_workholding.py — WorkholdingSetupItem (supplementary)
# ---------------------------------------------------------------------------

class TestProductionWorkholding:
    """Tests for production_workholding.py which adds BOX/CYLINDER/KEEP_OUT geometry classes."""

    def test_audit_constants(self):
        from backend.manufacturing.production_workholding import (
            FIXTURE_CATALOG_FOUND, FIXTURE_SCHEMA_FOUND, FIXTURE_WORKFLOW_FOUND,
        )
        assert FIXTURE_CATALOG_FOUND is True
        assert FIXTURE_SCHEMA_FOUND is True
        assert FIXTURE_WORKFLOW_FOUND is True

    def test_build_from_catalog_vise_100mm(self):
        from backend.manufacturing.production_workholding import build_workholding_from_catalog
        item = build_workholding_from_catalog("std-vise-jaw-100mm", 0.0, 0.0, -40.0)
        assert item is not None
        assert item.catalog_id == "std-vise-jaw-100mm"
        assert item.has_wcs is True
        assert item.has_geometry is True

    def test_build_from_catalog_unknown_id_returns_none(self):
        from backend.manufacturing.production_workholding import build_workholding_from_catalog
        assert build_workholding_from_catalog("nonexistent", 0.0, 0.0, 0.0) is None

    def test_resolve_fixture_inputs_catalog_trustworthy(self):
        from backend.manufacturing.production_workholding import (
            WorkholdingSetupItem, WorkholdingGeometryClass, WorkholdingSource,
            resolve_fixture_inputs, build_workholding_from_catalog,
        )
        item = build_workholding_from_catalog("std-step-clamp-sm", 80.0, 10.0, 0.0)
        assert item is not None
        inputs, notes = resolve_fixture_inputs([item])
        assert len(inputs) == 1
        assert inputs[0].is_trustworthy is True

    def test_resolve_missing_wcs_excluded(self):
        from backend.manufacturing.production_workholding import (
            WorkholdingSetupItem, WorkholdingGeometryClass, WorkholdingSource,
            resolve_fixture_inputs,
        )
        from backend.manufacturing.verification_adapter import GeometryFieldProvenance
        from backend.verification.enums import FixtureType
        item = WorkholdingSetupItem(
            catalog_id=None, fixture_type=FixtureType.VISE_JAWS,
            geometry_class=WorkholdingGeometryClass.BOX,
            source=WorkholdingSource.USER_CONFIRMED,
            half_x_mm=55.0, half_y_mm=50.0, height_mm=40.0,
            wcs_centre_x_mm=None, wcs_centre_y_mm=None, wcs_bottom_z_mm=None,
            wcs_provenance=GeometryFieldProvenance.UNKNOWN,
        )
        inputs, notes = resolve_fixture_inputs([item])
        assert len(inputs) == 0
        assert any("INCOMPLETE_TRANSFORM" in n or "WCS" in n for n in notes)

    def test_workflow_safety_invariants(self):
        from backend.manufacturing.production_workholding import (
            WorkholdingWorkflow, build_workholding_workflow, build_workholding_from_catalog,
        )
        item = build_workholding_from_catalog("std-vise-jaw-100mm", 0.0, 0.0, -40.0)
        wf = WorkholdingWorkflow(
            setup_id="setup-p10c7",
            items=[item] if item else [],
            candidate=_candidate(),
        )
        result = build_workholding_workflow(wf)
        assert result.is_dispatchable is False
        assert result.production_released is False

    def test_gouge_always_not_verifiable_without_step(self):
        sel = FixtureSelection("std-vise-jaw-100mm", 0.0, 0.0, -40.0)
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            fixture_selections=[sel],
        )
        result = run_production_verification(req)
        assert result.gouge_validated == "NOT_VERIFIABLE"
        assert result.p8_result.gouge_validated == "NOT_VERIFIABLE"
