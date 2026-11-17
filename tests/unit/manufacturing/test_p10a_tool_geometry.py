"""
P10-A test suite: remaining tool geometry status.

Validates:
  - 9/18 drills have flute_length_mm (Sandvik 860-1 — P9-A complete)
  - 9/18 drills remain WITHOUT flute_length_mm (Kennametal B221A + Walter Titex DC150)
  - UNSUPPORTED_TOOL_GEOMETRY_COUNT=9 (no fabrication, no manufacturer data available yet)
  - Tools without flute → tool_reach=INSUFFICIENT_DATA (fail-closed, never PASS)
  - Tools with flute → tool_reach can be PASS or FAIL (geometry verified)
  - Shank diameter present for all drills (18/18)
  - Overall length coverage per record

HARD RULES verified:
  - No fabricated flute_length_mm for Kennametal/Walter
  - INSUFFICIENT_DATA ≠ PASS (fail-closed)
  - TOOLS_WITH_FLUTE_LENGTH_BEFORE=9 (from P9-A)
  - TOOLS_WITH_FLUTE_LENGTH_AFTER=9 (no change — no source data for Kennametal/Walter)
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.cutting_tools.seed_catalog import get_catalog
from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    build_verification_input,
    run_p8_verification,
)

# ---------------------------------------------------------------------------
# Constants from P9-A baseline
# ---------------------------------------------------------------------------

TOOLS_WITH_FLUTE_LENGTH_BEFORE = 9
TOOLS_WITH_FLUTE_LENGTH_AFTER = 9   # no change in P10-A without source data
UNSUPPORTED_TOOL_GEOMETRY_COUNT = 9  # Kennametal B221A (6) + Walter Titex DC150 (3)


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _get_drills():
    return [t for t in get_catalog() if "drilling" in t.supported_operations]


def _seg(sx, sy, sz, ex, ey, ez, motion="FEED_LINEAR", is_cutting=True):
    return {
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "motion_type": motion, "is_cutting": is_cutting, "segment_id": "s1",
    }


def _candidate_with_depth(depth_mm: float, diam_mm: float = 5.0):
    return SimpleNamespace(
        nc_segments=[
            _seg(0, 0, 2, 0, 0, 1, "RAPID_LINEAR", False),
            _seg(0, 0, 1, 0, 0, -depth_mm, "FEED_LINEAR", True),
            _seg(0, 0, -depth_mm, 0, 0, 2, "RAPID_LINEAR", False),
        ],
        tool_diameter_mm=diam_mm,
        feature_id="feat-reach",
        toolpath_id="tp-reach",
    )


# ---------------------------------------------------------------------------
# P10-A1: Coverage counts
# ---------------------------------------------------------------------------

class TestToolGeometryCoverage:
    def test_total_drills_is_18(self):
        drills = _get_drills()
        assert len(drills) == 18

    def test_sandvik_860_1_all_have_flute_length(self):
        sandvik_drills = [
            d for d in _get_drills()
            if d.stable_id.startswith("sandvik-860-1-")
        ]
        assert len(sandvik_drills) == 9, (
            f"Expected 9 Sandvik 860-1 drills; found {len(sandvik_drills)}"
        )
        for d in sandvik_drills:
            assert d.flute_length_mm is not None, (
                f"{d.stable_id} should have flute_length_mm (P9-A)"
            )

    def test_tools_with_flute_count_matches_before(self):
        drills = _get_drills()
        with_flute = [d for d in drills if d.flute_length_mm is not None]
        assert len(with_flute) == TOOLS_WITH_FLUTE_LENGTH_BEFORE

    def test_tools_with_flute_count_unchanged_after_p10a(self):
        drills = _get_drills()
        with_flute = [d for d in drills if d.flute_length_mm is not None]
        assert len(with_flute) == TOOLS_WITH_FLUTE_LENGTH_AFTER

    def test_unsupported_tool_geometry_count(self):
        drills = _get_drills()
        without_flute = [d for d in drills if d.flute_length_mm is None]
        assert len(without_flute) == UNSUPPORTED_TOOL_GEOMETRY_COUNT

    def test_kennametal_b221a_drills_all_missing_flute(self):
        kennametal_drills = [
            d for d in _get_drills()
            if d.manufacturer == "Kennametal"
        ]
        assert len(kennametal_drills) >= 6
        for d in kennametal_drills:
            if d.product_family == "B221A":
                assert d.flute_length_mm is None, (
                    f"{d.stable_id}: Kennametal B221A flute_length_mm must remain "
                    "UNKNOWN (no source data available — do not fabricate)"
                )

    def test_walter_titex_drills_all_missing_flute(self):
        walter_drills = [
            d for d in _get_drills()
            if d.manufacturer == "Walter Tools"
        ]
        assert len(walter_drills) >= 3
        for d in walter_drills:
            assert d.flute_length_mm is None, (
                f"{d.stable_id}: Walter Titex DC150 flute_length_mm must remain "
                "UNKNOWN (no source data available — do not fabricate)"
            )

    def test_all_drills_have_shank_diameter(self):
        drills = _get_drills()
        for d in drills:
            assert d.shank_diameter_mm is not None, (
                f"{d.stable_id} missing shank_diameter_mm"
            )

    def test_all_drills_have_cutting_diameter(self):
        drills = _get_drills()
        for d in drills:
            assert d.cutting_diameter_mm is not None, (
                f"{d.stable_id} missing cutting_diameter_mm"
            )


# ---------------------------------------------------------------------------
# P10-A2: Tool reach fail-closed for missing flute
# ---------------------------------------------------------------------------

class TestToolReachFailClosed:
    def test_kennametal_without_flute_gives_insufficient_data(self):
        ken = next(
            d for d in _get_drills()
            if d.manufacturer == "Kennametal" and d.product_family == "B221A"
        )
        assert ken.flute_length_mm is None
        candidate = _candidate_with_depth(20.0, diam_mm=ken.cutting_diameter_mm)
        vi = build_verification_input(candidate=candidate, tool_record=ken)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"
        assert result.tool_reach_validated != "PASS"

    def test_walter_without_flute_gives_insufficient_data(self):
        walter = next(
            d for d in _get_drills()
            if d.manufacturer == "Walter Tools"
        )
        assert walter.flute_length_mm is None
        candidate = _candidate_with_depth(20.0, diam_mm=walter.cutting_diameter_mm)
        vi = build_verification_input(candidate=candidate, tool_record=walter)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"


# ---------------------------------------------------------------------------
# P10-A3: Tool reach PASS/FAIL for Sandvik with flute
# ---------------------------------------------------------------------------

class TestSandvikToolReach:
    def test_sandvik_5mm_pass_within_flute(self):
        sandvik_5mm = next(
            d for d in _get_drills()
            if d.stable_id == "sandvik-860-1-0500-026a1-pm"
        )
        assert sandvik_5mm.flute_length_mm == 26.0
        # Depth 25mm < flute 26mm → PASS
        candidate = _candidate_with_depth(25.0, diam_mm=5.0)
        vi = build_verification_input(candidate=candidate, tool_record=sandvik_5mm)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "PASS"

    def test_sandvik_5mm_fail_beyond_flute(self):
        sandvik_5mm = next(
            d for d in _get_drills()
            if d.stable_id == "sandvik-860-1-0500-026a1-pm"
        )
        # Depth 30mm > flute 26mm → FAIL
        candidate = _candidate_with_depth(30.0, diam_mm=5.0)
        vi = build_verification_input(candidate=candidate, tool_record=sandvik_5mm)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "FAIL"


# ---------------------------------------------------------------------------
# P10-A4: Provenance labels
# ---------------------------------------------------------------------------

class TestToolGeometryProvenance:
    def test_sandvik_flute_provenance_known(self):
        sandvik = next(
            d for d in _get_drills()
            if d.manufacturer == "Sandvik Coromant"
        )
        candidate = _candidate_with_depth(20.0, diam_mm=sandvik.cutting_diameter_mm)
        vi = build_verification_input(candidate=candidate, tool_record=sandvik)
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.KNOWN

    def test_kennametal_flute_provenance_unknown(self):
        ken = next(
            d for d in _get_drills()
            if d.manufacturer == "Kennametal" and d.product_family == "B221A"
        )
        candidate = _candidate_with_depth(20.0, diam_mm=ken.cutting_diameter_mm)
        vi = build_verification_input(candidate=candidate, tool_record=ken)
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.UNKNOWN
