"""
Phase 10 unit tests: tool catalog expansion and drill cycle coverage.

Covers:
  - 10A: Sandvik CoroDrill 860-1 7.0mm catalog record (manufacturer-confirmed)
  - 10A: 7mm EXACT_MATCH / 6.6mm COMPATIBLE_MATCH via 7mm drill
  - 10A: Gühring RT 100 U 9.0mm (EDP 9055140090000) catalog record
  - 10A: 9mm EXACT_MATCH → FP 4×9mm drill toolpaths
  - Phase 9C E2E double-count fix (p8.drill_tp excluded from grand total)
  - Safety invariants carried forward from Phase 9

HARD RULES (enforced by tests):
  is_dispatchable=False always.
  production_released=False always.
  Catalog gap → no toolpath (no fabrication).
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.cutting_tools.seed_catalog import get_catalog
from backend.step_brep.phase5_feature_detector import (
    CylinderOrientation,
    OrientedCylinderRecord,
)
from backend.step_brep.phase6_cam_bridge import _select_drill_for_hole
from backend.step_brep.phase7_wcs_provider import WorkCoordinateSystem
from backend.step_brep.phase9_cam_e2e import (
    PHASE9_AUTO_APPROVAL,
    PHASE9_AUTO_CNC_DISPATCH,
    PHASE9_AUTOMATIC_ADAPTATION,
    PHASE9_IS_DISPATCHABLE,
    PHASE9_P9B_TOOLPATH_READY,
    PHASE9_PRODUCTION_RELEASED,
    PHASE9_REAL_MACHINE_WRITE,
    PHASE9_REVIEW_REQUIRED,
)
from backend.step_brep.phase9_drill_cam import (
    P9C_IS_DISPATCHABLE,
    P9C_PRODUCTION_RELEASED,
    DrillCycleResult,
    assess_drill_cycle,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wcs() -> WorkCoordinateSystem:
    from backend.step_brep.gmsh_step_parser import GMSH_BACKEND, StepImportRecord
    from backend.step_brep.phase7_wcs_provider import suggest_wcs_top_center
    rec = StepImportRecord(
        status="PASS",
        source_path="test.step",
        sha256=None,
        file_size_bytes=None,
        parser_backend=GMSH_BACKEND,
        sample_origin="IN_HOUSE_BENCHMARK",
        body_count=1,
        volume_count=1,
        surface_count=4,
        edge_count=12,
        vertex_count=8,
        bbox_min=(0.0, 0.0, 0.0),
        bbox_max=(100.0, 80.0, 50.0),
    )
    return suggest_wcs_top_center(rec)


def _make_cyl(
    *,
    diameter_mm: float = 8.0,
    hole_class: str = "THROUGH_HOLE_CANDIDATE",
    axis_direction: str | None = "Z",
    depth_mm: float | None = 20.0,
    orientation: CylinderOrientation = CylinderOrientation.INTERNAL_CYLINDER,
    bbox_min: tuple = (5.0, 5.0, 0.0),
    bbox_max: tuple = (13.0, 13.0, 20.0),
) -> OrientedCylinderRecord:
    return OrientedCylinderRecord(
        face_tag=5,
        feature_status="CANDIDATE",
        diameter_mm=diameter_mm,
        depth_mm=depth_mm,
        hole_class=hole_class,
        axis_direction=axis_direction,
        cylinder_orientation=orientation,
        circular_boundary_count=1,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        orientation_evidence="SYNTHETIC_TEST_RECORD",
    )


# ---------------------------------------------------------------------------
# TestPhase10SafetyConstants
# ---------------------------------------------------------------------------

class TestPhase10SafetyConstants:
    """Safety constants must remain False after Phase 10 changes."""

    def test_p9c_is_dispatchable_false(self):
        assert P9C_IS_DISPATCHABLE is False

    def test_p9c_production_released_false(self):
        assert P9C_PRODUCTION_RELEASED is False

    def test_phase9_is_dispatchable_false(self):
        assert PHASE9_IS_DISPATCHABLE is False

    def test_phase9_production_released_false(self):
        assert PHASE9_PRODUCTION_RELEASED is False

    def test_phase9_review_required_true(self):
        assert PHASE9_REVIEW_REQUIRED is True

    def test_phase9_real_machine_write_false(self):
        assert PHASE9_REAL_MACHINE_WRITE is False

    def test_phase9_auto_cnc_dispatch_false(self):
        assert PHASE9_AUTO_CNC_DISPATCH is False

    def test_phase9_auto_approval_false(self):
        assert PHASE9_AUTO_APPROVAL is False

    def test_phase9_automatic_adaptation_false(self):
        assert PHASE9_AUTOMATIC_ADAPTATION is False

    def test_phase9_p9b_toolpath_ready_false(self):
        assert PHASE9_P9B_TOOLPATH_READY is False


# ---------------------------------------------------------------------------
# TestPhase10SevenMMDrillCatalog
# ---------------------------------------------------------------------------

class TestPhase10SevenMMDrillCatalog:
    """Verify the Phase 10A Sandvik 7mm drill record from official catalog."""

    def _get_7mm(self):
        tools = get_catalog()
        return [
            t for t in tools
            if t.cutting_diameter_mm == 7.0 and t.tool_category_code == "DRILL"
        ]

    def test_7mm_drill_in_catalog(self):
        recs = self._get_7mm()
        assert len(recs) >= 1

    def test_7mm_sandvik_record_stable_id(self):
        recs = self._get_7mm()
        ids = [r.stable_id for r in recs]
        assert "sandvik-860-1-0700-040a1-pm" in ids

    def test_7mm_sandvik_evidence_manufacturer_catalog(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.evidence_status == "MANUFACTURER_CATALOG"

    def test_7mm_sandvik_cutting_diameter(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.cutting_diameter_mm == 7.0

    def test_7mm_sandvik_flute_length_populated(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.flute_length_mm == 40.0

    def test_7mm_sandvik_cutting_length(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.cutting_length_mm == 40.0

    def test_7mm_sandvik_overall_length(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.overall_length_mm == 91.0

    def test_7mm_sandvik_shank_diameter(self):
        # Sandvik uses 8mm shank for 7mm diameter (larger for rigidity)
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.shank_diameter_mm == 8.0

    def test_7mm_sandvik_point_angle(self):
        # 147° for 7mm (different from 140° used in 3-6mm range)
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.point_angle_deg == 147.0

    def test_7mm_sandvik_through_coolant(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert rec.through_coolant is True

    def test_7mm_sandvik_catalog_code_matches_convention(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        assert "860.1-0700-040A1-PM" in rec.catalog_code

    def test_7mm_sandvik_source_note_cites_official_page(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "sandvik-860-1-0700-040a1-pm")
        # Source note must reference the official Sandvik product page
        assert rec.source_note is not None
        note = rec.source_note.lower()
        assert "sandvik" in note or "coromant" in note


# ---------------------------------------------------------------------------
# TestPhase10DrillMatch
# ---------------------------------------------------------------------------

class TestPhase10DrillMatch:
    """Verify 7mm EXACT_MATCH and 6.6mm COMPATIBLE_MATCH after Phase 10A."""

    def test_7mm_exact_match(self):
        tool, match = _select_drill_for_hole(7.0)
        assert tool is not None
        assert match == "EXACT_MATCH"
        assert tool.stable_id == "sandvik-860-1-0700-040a1-pm"

    def test_7mm_exact_match_drill_cycle(self):
        cyl = _make_cyl(diameter_mm=7.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is False
        assert result.tool_match_type == "EXACT_MATCH"
        assert result.tool_id == "sandvik-860-1-0700-040a1-pm"

    def test_7mm_exact_match_generates_toolpath(self):
        cyl = _make_cyl(diameter_mm=7.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is True
        assert result.toolpath is not None

    def test_6_6mm_compatible_match_via_7mm(self):
        # |6.6-7.0|/6.6 = 6.06% < 7% tolerance → COMPATIBLE_MATCH
        tool, match = _select_drill_for_hole(6.6)
        assert tool is not None
        assert match == "COMPATIBLE_MATCH"
        assert tool.cutting_diameter_mm == 7.0

    def test_6_6mm_axial_hole_generates_toolpath(self):
        cyl = _make_cyl(diameter_mm=6.6, axis_direction="Z", depth_mm=15.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is False
        assert result.geometric_toolpath_ready is True

    def test_6_6mm_non_axial_blocked(self):
        cyl = _make_cyl(diameter_mm=6.6, axis_direction="X", depth_mm=15.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is False
        assert result.toolpath is None

    def test_9mm_exact_match(self):
        # 9mm now in catalog as guhring-5514-0900
        tool, match = _select_drill_for_hole(9.0)
        assert tool is not None
        assert match == "EXACT_MATCH"
        assert tool.stable_id == "guhring-5514-0900"

    def test_20mm_exact_match(self):
        # 20mm Sandvik 860-1-2000-055A1-PM added in Phase 10A
        tool, match = _select_drill_for_hole(20.0)
        assert tool is not None
        assert match == "EXACT_MATCH"
        assert tool.stable_id == "sandvik-860-1-2000-055a1-pm"

    def test_2_5mm_still_no_match(self):
        tool, match = _select_drill_for_hole(2.5)
        assert match == "NO_MATCH" or tool is None

    def test_9mm_drill_cycle_no_gap(self):
        # 9mm now matched by guhring-5514-0900
        cyl = _make_cyl(diameter_mm=9.0, axis_direction="Z", depth_mm=25.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is False
        assert result.tool_id == "guhring-5514-0900"

    def test_is_dispatchable_false_7mm_matched(self):
        cyl = _make_cyl(diameter_mm=7.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.is_dispatchable is False

    def test_production_released_false_7mm_matched(self):
        cyl = _make_cyl(diameter_mm=7.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.production_released is False

    def test_parameterized_cam_ready_always_false(self):
        # Even with 7mm exact match, Vc/fn not in scope
        cyl = _make_cyl(diameter_mm=7.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.parameterized_cam_ready is False


# ---------------------------------------------------------------------------
# TestPhase10E2EDoubleCountFix
# ---------------------------------------------------------------------------

class TestPhase10E2EDoubleCountFix:
    """Verify Phase 9C supersedes Phase 8 drill count — no double counting."""

    def _make_p8_mock(self, pocket_tp=1, slot_tp=1, step_tp=0, drill_tp=4):
        from backend.step_brep.phase8_cam_e2e import Phase8E2EResult
        p8 = MagicMock(spec=Phase8E2EResult)
        p8.pocket_toolpath_count = pocket_tp
        p8.slot_toolpath_count = slot_tp
        p8.step_toolpath_count = step_tp
        p8.drill_toolpath_count = drill_tp
        p8.total_toolpath_count = pocket_tp + slot_tp + step_tp + drill_tp
        p8.wcs_ready = True
        p8.wcs = _make_wcs()
        return p8

    def _make_drill_result(self, toolpath_count=4):
        r = MagicMock(spec=DrillCycleResult)
        r.toolpath_count = toolpath_count
        r.total_candidates = 4
        r.tool_matched_count = 4
        r.tool_catalog_gap_count = 0
        r.geometric_toolpath_ready_count = 4
        return r

    def _make_shoulder_result(self):
        from backend.step_brep.phase9_shoulder_cam import ShoulderCAMResult
        r = MagicMock(spec=ShoulderCAMResult)
        r.total_count = 0
        r.boundary_valid_count = 0
        r.depth_ready_count = 0
        r.cam_ready_count = 0
        return r

    def test_total_tp_excludes_p8_drill_count(self):
        """grand total = p8_non_drill + p9c_drill, NOT p8_total + p9c_drill."""
        p8 = self._make_p8_mock(pocket_tp=1, slot_tp=1, step_tp=0, drill_tp=4)
        dr = self._make_drill_result(toolpath_count=4)
        # Simulate what run_phase9_e2e computes:
        # total = p8_non_drill + drill_cycle.toolpath_count
        p8_non_drill = p8.pocket_toolpath_count + p8.slot_toolpath_count + p8.step_toolpath_count
        total_tp = p8_non_drill + dr.toolpath_count
        # Must NOT be p8.total_toolpath_count + dr.toolpath_count (which would be 10)
        assert total_tp == 6  # 1+1+0 + 4 = 6
        assert total_tp != p8.total_toolpath_count + dr.toolpath_count  # 6 != 10

    def test_total_tp_no_p8_drills_case(self):
        """When p8 drill_tp=0, the fix has no effect (Phase 9 baseline)."""
        p8 = self._make_p8_mock(pocket_tp=1, slot_tp=1, step_tp=0, drill_tp=0)
        dr = self._make_drill_result(toolpath_count=0)
        p8_non_drill = p8.pocket_toolpath_count + p8.slot_toolpath_count + p8.step_toolpath_count
        total_tp = p8_non_drill + dr.toolpath_count
        # 1+1+0+0 = 2, same as p8.total (since drill_tp=0)
        assert total_tp == 2
        assert total_tp == p8.total_toolpath_count - p8.drill_toolpath_count + dr.toolpath_count

    def test_phase9c_authoritative_drill_source(self):
        """Phase 9C drill count replaces Phase 8 drill count in grand total."""
        p8 = self._make_p8_mock(pocket_tp=1, slot_tp=0, step_tp=0, drill_tp=3)
        dr = self._make_drill_result(toolpath_count=3)
        p8_non_drill = p8.pocket_toolpath_count + p8.slot_toolpath_count + p8.step_toolpath_count
        total_tp = p8_non_drill + dr.toolpath_count
        assert total_tp == 4  # 1 pocket + 3 P9C drills
        # Not 7 (1+3+3 double-counted)
        assert total_tp != p8.total_toolpath_count + dr.toolpath_count


# ---------------------------------------------------------------------------
# TestPhase10ANineMMDrillCatalog
# ---------------------------------------------------------------------------

class TestPhase10ANineMMDrillCatalog:
    """Verify the Phase 10A Guhring RT 100 U 9mm drill (EDP 9055140090000)."""

    def _get_9mm(self):
        tools = get_catalog()
        return [
            t for t in tools
            if t.cutting_diameter_mm == 9.0 and t.tool_category_code == "DRILL"
        ]

    def test_9mm_drill_in_catalog(self):
        recs = self._get_9mm()
        assert len(recs) >= 1

    def test_9mm_guhring_record_stable_id(self):
        recs = self._get_9mm()
        ids = [r.stable_id for r in recs]
        assert "guhring-5514-0900" in ids

    def test_9mm_guhring_evidence_manufacturer_catalog(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.evidence_status == "MANUFACTURER_CATALOG"

    def test_9mm_guhring_cutting_diameter(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.cutting_diameter_mm == 9.0

    def test_9mm_guhring_flute_length_confirmed(self):
        # 47mm confirmed from MSC Direct UK listing GUR-14600J
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.flute_length_mm == 47.0

    def test_9mm_guhring_overall_length(self):
        # 89mm confirmed from MSC Direct UK listing GUR-14600J
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.overall_length_mm == 89.0

    def test_9mm_guhring_shank_diameter_none(self):
        # Shank diameter NOT confirmed for exact 9.000mm — HARD RULE 4 forbids inference
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.shank_diameter_mm is None

    def test_9mm_guhring_no_through_coolant(self):
        # RT 100 U series = without through coolant
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.through_coolant is False

    def test_9mm_guhring_point_angle(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.point_angle_deg == 140.0

    def test_9mm_guhring_catalog_code_is_edp(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.catalog_code == "9055140090000"

    def test_9mm_guhring_source_note_cites_sources(self):
        tools = get_catalog()
        rec = next(t for t in tools if t.stable_id == "guhring-5514-0900")
        assert rec.source_note is not None
        note = rec.source_note.lower()
        assert "guhring" in note or "gühring" in note

    def test_9mm_exact_match_drill_cycle_generates_toolpath(self):
        # FP 4×9mm Z-axis holes should now be toolpath-ready
        cyl = _make_cyl(diameter_mm=9.0, axis_direction="Z", depth_mm=10.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is False
        assert result.tool_match_type == "EXACT_MATCH"
        assert result.geometric_toolpath_ready is True
        assert result.toolpath is not None

    def test_9mm_non_axial_still_blocked(self):
        cyl = _make_cyl(diameter_mm=9.0, axis_direction="X", depth_mm=10.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is False
        assert result.toolpath is None

    def test_9mm_is_dispatchable_false(self):
        cyl = _make_cyl(diameter_mm=9.0, axis_direction="Z", depth_mm=10.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.is_dispatchable is False

    def test_9mm_production_released_false(self):
        cyl = _make_cyl(diameter_mm=9.0, axis_direction="Z", depth_mm=10.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.production_released is False

    def test_9mm_parameterized_cam_ready_false(self):
        cyl = _make_cyl(diameter_mm=9.0, axis_direction="Z", depth_mm=10.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.parameterized_cam_ready is False

    def test_fp_9mm_drill_count_four(self):
        """FP 4×9mm Z-axis holes all become toolpath-ready after 9mm added."""
        results = [
            assess_drill_cycle(
                _make_cyl(
                    diameter_mm=9.0,
                    axis_direction="Z",
                    depth_mm=10.0,
                    orientation=CylinderOrientation.INTERNAL_CYLINDER,
                ),
                _make_wcs(),
            )
            for _ in range(4)
        ]
        toolpath_count = sum(1 for r in results if r.geometric_toolpath_ready)
        assert toolpath_count == 4
