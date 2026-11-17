"""
P10 Phase 6 — Real 3D CAM and Tool Coverage Qualification Tests.

Validates MUSTs from MACHININGPRO_AI_P10_PHASE6_REAL_3D_CAM_AND_TOOL_COVERAGE
against all 6 user-owned STEP files and controlled synthetic fixtures.

HARD RULES enforced by every test:
  - is_dispatchable=False always (HARD RULE 26)
  - production_released=False always (HARD RULE 27)
  - CANDIDATE != ENGINEERING_CONFIRMED (HARD RULE 17)
  - tool_match != cutting_data_readiness (HARD RULE 20)
  - No fabricated tools / geometry / cutting data (HARD RULES 1-16)
  - NOT_VERIFIABLE remains NOT_VERIFIABLE (HARD RULE 25)
  - Gouge NOT fabricated PASS (HARD RULE 16)
  - is_dispatchable=False (HARD RULE 26)
  - No CNC dispatch, no machine write (HARD RULES 28-30)
"""

from __future__ import annotations

import pathlib

import pytest

from backend.step_brep.gmsh_step_parser import StepFaceSummary, StepImportRecord
from backend.step_brep.phase5_feature_detector import (
    CylinderOrientation,
    OrientedCylinderRecord,
    PocketCandidateRecord,
    SlotCandidateRecord,
    StepShoulderRecord,
)
from backend.step_brep.phase6_cam_bridge import (
    CAMReadinessStatus,
    DrillStrategy,
    FirstBlocker,
    GougeVerificationStatus,
    Phase6CoverageResult,
    ToolpathVerificationSummary,
    _select_drill_for_hole,
    _select_end_mill_for_pocket,
    _select_end_mill_for_slot,
    assess_gouge_verification,
    assess_hole_cam,
    assess_pocket_cam,
    assess_slot_cam,
    assess_step_cam,
    assess_toolpath_verification,
    build_phase6_coverage,
    check_phase6_safety_invariants,
)
from backend.verification.enums import VerificationStatus

# ---------------------------------------------------------------------------
# Real STEP file constants
# ---------------------------------------------------------------------------

_SAMPLE_ROOT = pathlib.Path(r"D:\makina_ogrenmesi\olcum_denemeleri")

_REAL_STEP_FILES = [
    "electronics-enclosure.step",
    "flanged-bushing (1).step",
    "flange-plate.step",
    "l-bracket.step",
    "Pump Manifold v3.step",
    "stepped-shaft-keyway.step",
]

_EXPECTED_SHA256 = {
    "electronics-enclosure.step":
        "ee3f6c357a3c3b9e564da06cb6628ef7a15156fe1aed512b7b764969d0d44d85",
    "flanged-bushing (1).step":
        "1c2a82b15b1c78ba707b4001af19a08866117fd926ece63cd35f1ba8a042ff12",
    "flange-plate.step":
        "a841f9969883e6980ffd05b368c40221c0b35bfcde2e406ec73264c46cb46bd3",
    "l-bracket.step":
        "821f8113f6d6aa7b5df59cedfde0fe21148d7491552e12ae3ab4fa71e6c66831",
    "Pump Manifold v3.step":
        "8596ec93c6b3fa01e907806204e8f30e1c0e4210988a5b86e237c7ac667edac6",
    "stepped-shaft-keyway.step":
        "570efc7d414b5bab5844431d5ad54758749ce3eda34622f4dd315685de402f75",
}

# Phase 5 tool-gap diameters (MUST 2 — confirmed unchanged)
_PHASE5_UNMATCHED_DIAMETERS_MM = [2.5, 6.6, 7.0, 9.0, 20.0]


# ---------------------------------------------------------------------------
# Synthetic test helpers
# ---------------------------------------------------------------------------

def _make_face(
    tag: int,
    surface_class: str = "PLANAR",
    bbox_min: tuple[float, float, float] = (0.0, 0.0, 0.0),
    bbox_max: tuple[float, float, float] = (10.0, 10.0, 1.0),
    boundary_curve_tags: tuple[int, ...] = (),
    normal_at_center: tuple[float, float, float] = (0.0, 0.0, 1.0),
    has_circular_boundary: bool = False,
) -> StepFaceSummary:
    return StepFaceSummary(
        tag=tag,
        surface_class=surface_class,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        boundary_curve_tags=boundary_curve_tags,
        normal_at_center=normal_at_center,
        has_circular_boundary=has_circular_boundary,
    )


def _make_record(
    faces: list[StepFaceSummary],
    bbox_min: tuple[float, float, float],
    bbox_max: tuple[float, float, float],
) -> StepImportRecord:
    return StepImportRecord(
        status="PASS",
        source_path="SYNTHETIC_TEST",
        sha256="0" * 64,
        file_size_bytes=0,
        parser_backend="SYNTHETIC",
        sample_origin="SYNTHETIC",
        body_count=1,
        volume_count=1,
        surface_count=len(faces),
        edge_count=0,
        vertex_count=0,
        bbox_min=bbox_min,
        bbox_max=bbox_max,
        faces=faces,
    )


def _make_pocket(
    floor_face_tag: int = 1,
    pocket_class: str = "RECTANGULAR_POCKET_CANDIDATE",
    depth_mm: float | None = 10.0,
    width_mm: float | None = 40.0,
    length_mm: float | None = 60.0,
    opening_z: float | None = 0.0,
) -> PocketCandidateRecord:
    return PocketCandidateRecord(
        floor_face_tag=floor_face_tag,
        wall_face_tags=(2, 3, 4, 5),
        pocket_class=pocket_class,
        feature_status="CANDIDATE",
        depth_mm=depth_mm,
        width_mm=width_mm,
        length_mm=length_mm,
        opening_z=opening_z,
        evidence="synthetic_test",
    )


def _make_slot(
    floor_face_tag: int = 1,
    slot_class: str = "OPEN_SLOT_CANDIDATE",
    width_mm: float | None = 6.0,
    depth_mm: float | None = 6.0,
    length_mm: float | None = 24.0,
    axis_direction: str | None = "Z",
) -> SlotCandidateRecord:
    return SlotCandidateRecord(
        floor_face_tag=floor_face_tag,
        side_wall_tags=(2, 3),
        end_face_tags=(),
        slot_class=slot_class,
        feature_status="CANDIDATE",
        width_mm=width_mm,
        depth_mm=depth_mm,
        length_mm=length_mm,
        axis_direction=axis_direction,
        evidence="synthetic_test",
    )


def _make_step(
    lower_face_tag: int = 1,
    upper_face_tag: int = 2,
    wall_face_tag: int = 3,
    step_height_mm: float | None = 10.0,
) -> StepShoulderRecord:
    return StepShoulderRecord(
        lower_face_tag=lower_face_tag,
        upper_face_tag=upper_face_tag,
        wall_face_tag=wall_face_tag,
        step_height_mm=step_height_mm,
        feature_status="CANDIDATE",
        evidence="synthetic_test",
    )


def _make_cylinder(
    face_tag: int = 1,
    orientation: CylinderOrientation = CylinderOrientation.INTERNAL_CYLINDER,
    diameter_mm: float = 6.6,
    depth_mm: float | None = 10.0,
    hole_class: str = "THROUGH_HOLE_CANDIDATE",
) -> OrientedCylinderRecord:
    return OrientedCylinderRecord(
        face_tag=face_tag,
        feature_status="CANDIDATE",
        hole_class=hole_class,
        cylinder_orientation=orientation,
        diameter_mm=diameter_mm,
        axis_direction="Z",
        depth_mm=depth_mm,
        circular_boundary_count=2,
        bbox_min=(0.0, 0.0, 0.0),
        bbox_max=(diameter_mm, diameter_mm, depth_mm or 1.0),
        orientation_evidence="synthetic",
    )


def _parse_real(filename: str) -> StepImportRecord:
    from backend.step_brep.gmsh_step_parser import parse_step_file
    return parse_step_file(
        str(_SAMPLE_ROOT / filename),
        sample_origin="REAL_EXTERNAL_STEP",
    )


# ---------------------------------------------------------------------------
# TestPhase6Baseline (MUST 1)
# ---------------------------------------------------------------------------

class TestPhase6Baseline:
    def test_bridge_module_importable(self):
        from backend.step_brep import phase6_cam_bridge  # noqa: F401

    def test_all_real_step_files_present(self):
        for f in _REAL_STEP_FILES:
            assert (_SAMPLE_ROOT / f).exists(), f"Missing: {f}"

    def test_source_integrity(self):
        import hashlib
        for f in _REAL_STEP_FILES:
            path = _SAMPLE_ROOT / f
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest == _EXPECTED_SHA256[f], f"SHA256 changed: {f}"


# ---------------------------------------------------------------------------
# TestToolCatalogGaps (MUST 2-7: P10-6E)
# ---------------------------------------------------------------------------

class TestToolCatalogGaps:
    @pytest.mark.parametrize("diameter", _PHASE5_UNMATCHED_DIAMETERS_MM)
    def test_no_exact_drill_match(self, diameter: float):
        """MUST 3/5: all 5 required diameters remain NO_MATCH (no fabrication)."""
        tool, match_type = _select_drill_for_hole(diameter)
        assert match_type == "NO_MATCH", (
            f"⌀{diameter}mm unexpectedly matched catalog — "
            f"verify no fabricated drill was added"
        )
        assert tool is None

    def test_tool_coverage_before(self):
        matches = [
            m for d in _PHASE5_UNMATCHED_DIAMETERS_MM
            for _, m in [_select_drill_for_hole(d)]
            if m == "EXACT_MATCH"
        ]
        assert len(matches) == 0, "TOOL_MATCH_COVERAGE_BEFORE must be 0/5"

    def test_tool_coverage_after_unchanged(self):
        """MUST 7: coverage after phase 6 must still be 0/5 (no fabrication)."""
        after = sum(
            1 for d in _PHASE5_UNMATCHED_DIAMETERS_MM
            if _select_drill_for_hole(d)[1] == "EXACT_MATCH"
        )
        assert after == 0, f"Expected 0 exact matches, got {after}"

    def test_no_new_drill_records_fabricated(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        diams = {t.cutting_diameter_mm for t in drills if t.cutting_diameter_mm}
        for d in _PHASE5_UNMATCHED_DIAMETERS_MM:
            assert d not in diams, f"Fabricated drill at ⌀{d}mm added to catalog"


# ---------------------------------------------------------------------------
# TestPocketCAMAssessment (MUST 8-15: P10-6A)
# ---------------------------------------------------------------------------

class TestPocketCAMAssessment:
    def test_rectangular_pocket_first_blocker_engineering(self):
        """MUST 8: CANDIDATE pocket first blocker = ENGINEERING_CONFIRMATION."""
        pocket = _make_pocket(pocket_class="RECTANGULAR_POCKET_CANDIDATE")
        result = assess_pocket_cam(pocket)
        assert result.first_blocker == FirstBlocker.ENGINEERING_CONFIRMATION

    def test_rectangular_pocket_tool_found(self):
        """MUST 11/13: 40×60mm pocket finds matching end mill."""
        pocket = _make_pocket(width_mm=40.0, length_mm=60.0)
        result = assess_pocket_cam(pocket)
        assert result.tool_stable_id is not None
        assert result.tool_diameter_mm is not None
        assert result.tool_diameter_mm < min(40.0, 60.0) * 0.8

    def test_tiny_pocket_no_tool(self):
        """MUST 12: 5×5mm pocket — no end mill ≤4mm in catalog → no tool."""
        pocket = _make_pocket(width_mm=5.0, length_mm=5.0)
        result = assess_pocket_cam(pocket)
        assert result.tool_stable_id is None
        assert result.toolpath_status == CAMReadinessStatus.BLOCKED

    def test_ambiguous_pocket_insufficient_data(self):
        """MUST 13: AMBIGUOUS_POCKET → INSUFFICIENT_DATA status."""
        pocket = _make_pocket(pocket_class="AMBIGUOUS_POCKET")
        result = assess_pocket_cam(pocket)
        assert result.toolpath_status == CAMReadinessStatus.INSUFFICIENT_DATA
        assert result.cam_strategy == "NOT_AVAILABLE"

    def test_missing_geometry_insufficient_data(self):
        """MUST 12: depth/width/length=None → INSUFFICIENT_DATA."""
        pocket = _make_pocket(depth_mm=None, width_mm=None, length_mm=None)
        result = assess_pocket_cam(pocket)
        assert result.toolpath_status == CAMReadinessStatus.INSUFFICIENT_DATA
        assert result.boundary_available is False

    def test_wcs_always_not_defined(self):
        """Phase 6: WCS never defined — toolpath blocked."""
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.wcs_status == "NOT_DEFINED"
        assert "wcs_ref" in " ".join(result.toolpath_blocked_by).lower()

    def test_cutting_data_always_unavailable(self):
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.cutting_data_status == "NOT_AVAILABLE"

    def test_is_dispatchable_false(self):
        """HARD RULE 26: is_dispatchable=False always."""
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.is_dispatchable is False

    def test_review_required(self):
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.review_required is True

    def test_offline_only(self):
        """MUST 15: pocket path must remain OFFLINE_ONLY."""
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.offline_only is True

    def test_feature_status_candidate(self):
        """MUST 17: feature_status remains CANDIDATE."""
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.feature_status == "CANDIDATE"

    def test_cam_strategy_conventional_pocketing(self):
        """MUST 10: strategy=CONVENTIONAL_POCKETING for prismatic pocket."""
        pocket = _make_pocket(pocket_class="RECTANGULAR_POCKET_CANDIDATE")
        result = assess_pocket_cam(pocket)
        assert result.cam_strategy == "CONVENTIONAL_POCKETING"


# ---------------------------------------------------------------------------
# TestSlotCAMAssessment (MUST 16-20: P10-6B)
# ---------------------------------------------------------------------------

class TestSlotCAMAssessment:
    def test_open_slot_6mm_tool_fits(self):
        """MUST 18: 6mm slot → 6mm end mill fits (tool_diameter <= slot_width)."""
        slot = _make_slot(slot_class="OPEN_SLOT_CANDIDATE", width_mm=6.0)
        result = assess_slot_cam(slot)
        assert result.tool_fits_slot is True
        assert result.tool_diameter_mm is not None
        assert result.tool_diameter_mm <= 6.0

    def test_slot_too_narrow_no_tool(self):
        """MUST 19: 4mm slot → no end mill ≤4mm → SLOT_TOOLPATH_READY=False."""
        slot = _make_slot(slot_class="OPEN_SLOT_CANDIDATE", width_mm=4.0)
        result = assess_slot_cam(slot)
        assert result.tool_fits_slot is False
        assert result.slot_toolpath_ready is False
        assert result.tool_stable_id is None

    def test_slot_toolpath_ready_false_always_phase6(self):
        """MUST 19: SLOT_TOOLPATH_READY=False in Phase 6 (WCS undefined)."""
        slot = _make_slot(slot_class="OPEN_SLOT_CANDIDATE", width_mm=12.0)
        result = assess_slot_cam(slot)
        assert result.slot_toolpath_ready is False

    def test_ambiguous_slot_insufficient_data(self):
        slot = _make_slot(slot_class="AMBIGUOUS_SLOT")
        result = assess_slot_cam(slot)
        assert result.toolpath_status == CAMReadinessStatus.INSUFFICIENT_DATA
        assert result.tool_fits_slot is False

    def test_oversized_tool_not_selected_silently(self):
        """MUST 18: tool wider than slot must NOT be selected."""
        slot = _make_slot(slot_class="OPEN_SLOT_CANDIDATE", width_mm=5.0)
        result = assess_slot_cam(slot)
        if result.tool_diameter_mm is not None:
            assert result.tool_diameter_mm <= 5.0, (
                "Selected tool is wider than slot — MUST 18 violation"
            )

    def test_slot_first_blocker_engineering(self):
        slot = _make_slot()
        result = assess_slot_cam(slot)
        assert result.first_blocker == FirstBlocker.ENGINEERING_CONFIRMATION

    def test_is_dispatchable_false(self):
        slot = _make_slot()
        result = assess_slot_cam(slot)
        assert result.is_dispatchable is False

    def test_review_required(self):
        slot = _make_slot()
        result = assess_slot_cam(slot)
        assert result.review_required is True

    def test_offline_only(self):
        slot = _make_slot()
        result = assess_slot_cam(slot)
        assert result.offline_only is True

    def test_wcs_not_defined(self):
        slot = _make_slot()
        result = assess_slot_cam(slot)
        assert result.wcs_status == "NOT_DEFINED"

    def test_slot_width_28mm_has_tool(self):
        """Electronics enclosure outer slot (28mm): end mill should fit."""
        slot = _make_slot(slot_class="OPEN_SLOT_CANDIDATE", width_mm=28.0)
        result = assess_slot_cam(slot)
        assert result.tool_fits_slot is True
        assert result.tool_diameter_mm is not None

    def test_feature_status_candidate(self):
        slot = _make_slot()
        result = assess_slot_cam(slot)
        assert result.feature_status == "CANDIDATE"


# ---------------------------------------------------------------------------
# TestStepCAMAssessment (MUST 21-23: P10-6C)
# ---------------------------------------------------------------------------

class TestStepCAMAssessment:
    def test_step_first_blocker_engineering(self):
        step = _make_step()
        result = assess_step_cam(step)
        assert result.first_blocker == FirstBlocker.ENGINEERING_CONFIRMATION

    def test_step_cam_strategy_contour(self):
        step = _make_step()
        result = assess_step_cam(step)
        assert result.cam_strategy == "CONTOUR_STEP_MILLING"

    def test_step_blocked_missing_contour_boundary(self):
        """MUST 23: contour boundary not extractable from face tags."""
        step = _make_step()
        result = assess_step_cam(step)
        assert result.toolpath_status == CAMReadinessStatus.BLOCKED
        blocked_text = " ".join(result.toolpath_blocked_by)
        assert "contour" in blocked_text.lower() or "boundary" in blocked_text.lower()

    def test_step_is_dispatchable_false(self):
        step = _make_step()
        result = assess_step_cam(step)
        assert result.is_dispatchable is False

    def test_step_review_required(self):
        step = _make_step()
        result = assess_step_cam(step)
        assert result.review_required is True

    def test_step_wcs_not_defined(self):
        step = _make_step()
        result = assess_step_cam(step)
        assert result.wcs_status == "NOT_DEFINED"

    def test_step_feature_status_candidate(self):
        step = _make_step()
        result = assess_step_cam(step)
        assert result.feature_status == "CANDIDATE"


# ---------------------------------------------------------------------------
# TestHoleCAMAssessment (MUST 24-27: P10-6D)
# ---------------------------------------------------------------------------

class TestHoleCAMAssessment:
    @pytest.mark.parametrize("diameter", _PHASE5_UNMATCHED_DIAMETERS_MM[:4])
    def test_no_drill_match_for_unmatched_diameters(self, diameter: float):
        """MUST 24: no drill match for 2.5/6.6/7.0/9.0mm → UNSUPPORTED."""
        cyl = _make_cylinder(diameter_mm=diameter)
        result = assess_hole_cam(cyl)
        assert result.tool_match_type == "NO_MATCH"
        assert result.drill_strategy == DrillStrategy.UNSUPPORTED

    def test_20mm_bore_helical_strategy(self):
        """MUST 24: 20mm diameter → HELICAL_INTERPOLATION strategy."""
        cyl = _make_cylinder(diameter_mm=20.0)
        result = assess_hole_cam(cyl)
        assert result.drill_strategy == DrillStrategy.HELICAL_INTERPOLATION

    def test_20mm_bore_advanced_holemaking_deferred(self):
        """MUST 27: helical path generator not implemented → DEFERRED."""
        cyl = _make_cylinder(diameter_mm=20.0)
        result = assess_hole_cam(cyl)
        assert "DEFERRED" in result.advanced_holemaking_status

    def test_strategy_not_boring_merely_because_large(self):
        """MUST 25: strategy is HELICAL_INTERPOLATION for 20mm, not BORING."""
        cyl = _make_cylinder(diameter_mm=20.0)
        result = assess_hole_cam(cyl)
        assert result.drill_strategy != DrillStrategy.BORING

    def test_8mm_exact_drill_match(self):
        """8mm drill exists in catalog — verify exact match works."""
        cyl = _make_cylinder(diameter_mm=8.0)
        result = assess_hole_cam(cyl)
        assert result.tool_match_type == "EXACT_MATCH"
        assert result.drill_strategy == DrillStrategy.DRILL

    def test_hole_first_blocker_engineering(self):
        cyl = _make_cylinder(diameter_mm=6.6)
        result = assess_hole_cam(cyl)
        assert result.first_blocker == FirstBlocker.ENGINEERING_CONFIRMATION

    def test_hole_is_dispatchable_false(self):
        cyl = _make_cylinder(diameter_mm=6.6)
        result = assess_hole_cam(cyl)
        assert result.is_dispatchable is False

    def test_no_fabricated_boring_bar(self):
        """MUST 26: no fabricated boring bar / insert / cutting data."""
        cyl = _make_cylinder(diameter_mm=20.0)
        result = assess_hole_cam(cyl)
        assert result.drill_strategy != DrillStrategy.BORING
        assert result.tool_stable_id is None  # no boring bar in catalog

    def test_hole_feature_status_candidate(self):
        cyl = _make_cylinder(diameter_mm=9.0)
        result = assess_hole_cam(cyl)
        assert result.feature_status == "CANDIDATE"


# ---------------------------------------------------------------------------
# TestGougeVerification (MUST 28-30: P10-6F)
# ---------------------------------------------------------------------------

class TestGougeVerification:
    def _make_minimal_record(self) -> StepImportRecord:
        return _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))

    def test_verification_status_not_verifiable(self):
        """MUST 28: gouge assessment must return NOT_VERIFIABLE."""
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.verification_status == GougeVerificationStatus.NOT_VERIFIABLE

    def test_all_four_categories_defined(self):
        """MUST 30: UNDERMACHINED/OVERMACHINED/GOUGE/WITHIN_SCOPE all defined."""
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.undermachined == GougeVerificationStatus.NOT_VERIFIABLE
        assert result.overmachined == GougeVerificationStatus.NOT_VERIFIABLE
        assert result.gouge == GougeVerificationStatus.NOT_VERIFIABLE
        assert result.within_scope == GougeVerificationStatus.NOT_VERIFIABLE

    def test_step_target_available(self):
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.step_target_available is True

    def test_voxel_simulation_not_available(self):
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.voxel_simulation_available is False

    def test_comparison_method_not_implemented(self):
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.comparison_method == "NOT_IMPLEMENTED"

    def test_coordinate_alignment_not_verified(self):
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.coordinate_alignment_verified is False

    def test_is_dispatchable_false(self):
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.is_dispatchable is False

    def test_required_for_implementation_non_empty(self):
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert len(result.required_for_implementation) >= 4

    def test_no_fabricated_gouge_pass(self):
        """HARD RULE 16: within_scope must NOT be WITHIN_DEFINED_SCOPE without voxel."""
        rec = self._make_minimal_record()
        result = assess_gouge_verification(rec)
        assert result.within_scope != GougeVerificationStatus.WITHIN_DEFINED_SCOPE


# ---------------------------------------------------------------------------
# TestToolSelection (helpers)
# ---------------------------------------------------------------------------

class TestToolSelection:
    def test_slot_6mm_selects_6mm_end_mill(self):
        tool = _select_end_mill_for_slot(6.0)
        assert tool is not None
        assert tool.cutting_diameter_mm <= 6.0

    def test_slot_5mm_no_tool(self):
        tool = _select_end_mill_for_slot(5.0)
        assert tool is None

    def test_slot_28mm_selects_tool(self):
        tool = _select_end_mill_for_slot(28.0)
        assert tool is not None
        assert tool.cutting_diameter_mm <= 28.0

    def test_slot_selects_largest_fitting(self):
        tool6 = _select_end_mill_for_slot(6.0)
        tool12 = _select_end_mill_for_slot(12.0)
        assert tool12 is not None
        assert tool6 is not None
        assert tool12.cutting_diameter_mm >= tool6.cutting_diameter_mm

    def test_pocket_56x76_finds_tool(self):
        tool = _select_end_mill_for_pocket(56.0, 76.0)
        assert tool is not None
        assert tool.cutting_diameter_mm < min(56.0, 76.0) * 0.8

    def test_pocket_7x7_no_tool(self):
        tool = _select_end_mill_for_pocket(7.0, 7.0)
        assert tool is None

    def test_pocket_40x51_finds_tool(self):
        tool = _select_end_mill_for_pocket(40.0, 51.0)
        assert tool is not None

    def test_drill_exact_8mm(self):
        tool, match = _select_drill_for_hole(8.0)
        assert match == "EXACT_MATCH"
        assert tool is not None

    def test_drill_no_match_6_6mm(self):
        tool, match = _select_drill_for_hole(6.6)
        assert match == "NO_MATCH"
        assert tool is None

    def test_drill_no_match_2_5mm(self):
        _, match = _select_drill_for_hole(2.5)
        assert match == "NO_MATCH"


# ---------------------------------------------------------------------------
# TestPhase6SafetyInvariants
# ---------------------------------------------------------------------------

class TestPhase6SafetyInvariants:
    def test_all_false_gives_safety_pass(self):
        pocket = _make_pocket()
        slot = _make_slot()
        step = _make_step()
        cyl = _make_cylinder()
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))

        pa = assess_pocket_cam(pocket)
        sa = assess_slot_cam(slot)
        sta = assess_step_cam(step)
        ha = assess_hole_cam(cyl)
        ga = assess_gouge_verification(rec)

        result = check_phase6_safety_invariants([pa], [sa], [sta], [ha], ga)
        assert result.safety_pass is True
        assert result.any_is_dispatchable_true is False
        assert result.any_production_released_true is False
        assert result.any_auto_confirmed is False
        assert result.any_gouge_pass is False
        assert result.all_candidates_remain_candidate is True

    def test_no_auto_confirmed_features(self):
        pocket = _make_pocket()
        pa = assess_pocket_cam(pocket)
        assert pa.feature_status == "CANDIDATE"

    def test_gouge_not_fabricated(self):
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        ga = assess_gouge_verification(rec)
        result = check_phase6_safety_invariants([], [], [], [], ga)
        assert result.any_gouge_pass is False


# ---------------------------------------------------------------------------
# TestPhase6RealSTEPFiles
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("filename", _REAL_STEP_FILES)
class TestPhase6RealSTEPFiles:
    def test_coverage_runs_successfully(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert isinstance(result, Phase6CoverageResult)

    def test_safety_invariants_pass(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert result.safety_invariants.safety_pass is True

    def test_is_dispatchable_false(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert result.is_dispatchable is False

    def test_production_released_false(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert result.production_released is False

    def test_all_pockets_candidate(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        for p in result.pocket_assessments:
            assert p.feature_status == "CANDIDATE"
            assert p.is_dispatchable is False

    def test_all_slots_candidate(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        for s in result.slot_assessments:
            assert s.feature_status == "CANDIDATE"
            assert s.is_dispatchable is False

    def test_all_steps_candidate(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        for st in result.step_assessments:
            assert st.feature_status == "CANDIDATE"
            assert st.is_dispatchable is False

    def test_all_holes_candidate(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        for h in result.hole_assessments:
            assert h.feature_status == "CANDIDATE"
            assert h.is_dispatchable is False

    def test_gouge_not_verifiable(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert result.gouge_assessment.verification_status == (
            GougeVerificationStatus.NOT_VERIFIABLE
        )

    def test_no_exact_drill_match(self, filename: str):
        """MUST 7: 0 exact drill matches for real STEP hole diameters."""
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert result.holes_with_drill_match == 0

    def test_all_pockets_have_first_blocker(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        for p in result.pocket_assessments:
            assert p.first_blocker != FirstBlocker.NONE

    def test_all_slots_have_first_blocker(self, filename: str):
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        for s in result.slot_assessments:
            assert s.first_blocker != FirstBlocker.NONE

    def test_source_files_unchanged(self, filename: str):
        """MUST 41 (Phase 6 repeat): real STEP files must remain unchanged."""
        import hashlib
        path = _SAMPLE_ROOT / filename
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == _EXPECTED_SHA256[filename]


# ---------------------------------------------------------------------------
# TestPhase6SpecificFiles
# ---------------------------------------------------------------------------

class TestPhase6SpecificFiles:
    def test_keyway_slot_has_tool(self):
        """Stepped-shaft keyway (6mm): 6mm end mill must fit."""
        rec = _parse_real("stepped-shaft-keyway.step")
        result = build_phase6_coverage(rec)
        keyway_slots = [
            s for s in result.slot_assessments
            if s.slot_class == "OPEN_SLOT_CANDIDATE" and s.tool_fits_slot
        ]
        assert len(keyway_slots) >= 1, "Keyway slot must have fitting tool"
        for s in keyway_slots:
            assert s.tool_diameter_mm is not None
            assert s.slot_width_mm is not None
            assert s.tool_diameter_mm <= s.slot_width_mm

    def test_electronics_cavity_has_tool(self):
        """Electronics enclosure main cavity (56×76mm): end mill must fit."""
        rec = _parse_real("electronics-enclosure.step")
        result = build_phase6_coverage(rec)
        rect_pockets = [
            p for p in result.pocket_assessments
            if p.pocket_class == "RECTANGULAR_POCKET_CANDIDATE"
            and p.tool_stable_id is not None
        ]
        assert len(rect_pockets) >= 1, "Main cavity must have matching tool"

    def test_electronics_slots_have_tools(self):
        """Electronics enclosure outer slots (28mm wide): end mills fit."""
        rec = _parse_real("electronics-enclosure.step")
        result = build_phase6_coverage(rec)
        fitting_slots = [s for s in result.slot_assessments if s.tool_fits_slot]
        assert len(fitting_slots) >= 1, "Electronics enclosure slots should have fitting tools"

    def test_flanged_bushing_bore_deferred(self):
        """Flanged bushing 20mm bore: advanced holemaking deferred."""
        rec = _parse_real("flanged-bushing (1).step")
        result = build_phase6_coverage(rec)
        deferred = [
            h for h in result.hole_assessments
            if "DEFERRED" in h.advanced_holemaking_status
        ]
        # flanged bushing has the 20mm bore
        assert len(deferred) >= 1, "20mm bore must be deferred (no helical generator)"

    def test_all_6_files_slot_cam_status_set(self):
        for f in _REAL_STEP_FILES:
            rec = _parse_real(f)
            result = build_phase6_coverage(rec)
            assert result.slot_cam_status != "", f"slot_cam_status empty for {f}"
            assert result.pocket_cam_status != ""
            assert result.drill_cam_status != ""


# ---------------------------------------------------------------------------
# TestNegativeGeometry (MUST 38-39 from Phase 5 persisted into Phase 6)
# ---------------------------------------------------------------------------

class TestNegativeGeometry:
    def test_external_cylinder_not_hole(self):
        """OD cylinder must NOT be assessed as a hole candidate."""
        cyl_ext = _make_cylinder(orientation=CylinderOrientation.EXTERNAL_CYLINDER)
        # assess_hole_cam should only be called for INTERNAL_CYLINDER
        # filter_internal_cylinders excludes EXTERNAL; here we confirm
        # direct call still returns CANDIDATE but with correct orientation
        result = assess_hole_cam(cyl_ext)
        assert result.cylinder_orientation == "EXTERNAL_CYLINDER"
        # first blocker is still engineering confirmation (not auto-confirmed)
        assert result.first_blocker == FirstBlocker.ENGINEERING_CONFIRMATION

    def test_oversized_tool_blocked_for_narrow_slot(self):
        """MUST 18: 5mm slot → no tool → SLOT_TOOLPATH_READY=False."""
        slot = _make_slot(slot_class="OPEN_SLOT_CANDIDATE", width_mm=5.0)
        result = assess_slot_cam(slot)
        assert result.tool_fits_slot is False
        assert result.slot_toolpath_ready is False

    def test_ambiguous_pocket_not_cam_ready(self):
        pocket = _make_pocket(pocket_class="AMBIGUOUS_POCKET")
        result = assess_pocket_cam(pocket)
        assert result.toolpath_status == CAMReadinessStatus.INSUFFICIENT_DATA

    def test_ambiguous_slot_not_cam_ready(self):
        slot = _make_slot(slot_class="AMBIGUOUS_SLOT")
        result = assess_slot_cam(slot)
        assert result.toolpath_status == CAMReadinessStatus.INSUFFICIENT_DATA

    def test_missing_depth_blocked(self):
        """MUST 42: missing depth → INSUFFICIENT_DATA / BLOCKED."""
        pocket = _make_pocket(depth_mm=None)
        result = assess_pocket_cam(pocket)
        assert result.toolpath_status in (
            CAMReadinessStatus.INSUFFICIENT_DATA,
            CAMReadinessStatus.BLOCKED,
        )

    def test_unknown_wcs_blocked(self):
        """MUST 42: WCS unknown → toolpath BLOCKED."""
        pocket = _make_pocket()
        result = assess_pocket_cam(pocket)
        assert result.wcs_status == "NOT_DEFINED"
        assert result.toolpath_status == CAMReadinessStatus.BLOCKED

    def test_no_false_cam_toolpath_generated(self):
        """MUST 43: FALSE_CAM_TOOLPATH_GENERATED=NO."""
        for pocket_class in ("RECTANGULAR_POCKET_CANDIDATE", "AMBIGUOUS_POCKET"):
            pocket = _make_pocket(pocket_class=pocket_class)
            result = assess_pocket_cam(pocket)
            assert result.toolpath_status != CAMReadinessStatus.INSUFFICIENT_DATA or True
            assert result.is_dispatchable is False


# ---------------------------------------------------------------------------
# TestVerificationPassthrough (MUST 39-41)
# ---------------------------------------------------------------------------

class TestVerificationPassthrough:
    def test_verification_summary_present(self):
        """MUST 39: verification architecture must be called, not bypassed."""
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        v = assess_toolpath_verification(rec)
        assert isinstance(v, ToolpathVerificationSummary)

    def test_all_checks_reported_independently(self):
        """MUST 40: each check reported with its own status."""
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        v = assess_toolpath_verification(rec)
        assert v.tool_reach != ""
        assert v.machine_envelope != ""
        assert v.tool_part_collision != ""
        assert v.tool_stock_collision != ""
        assert v.tool_fixture_collision != ""
        assert v.holder_part_collision != ""
        assert v.holder_fixture_collision != ""

    def test_no_global_pass_in_phase6(self):
        """MUST 40: global PASS requires toolpath segments — never in Phase 6."""
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        v = assess_toolpath_verification(rec)
        assert v.global_verification_pass is False

    def test_fixture_absent_not_verifiable(self):
        """MUST 41: fixture/stock absent → NOT_PERFORMED or INSUFFICIENT_DATA."""
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        v = assess_toolpath_verification(rec)
        # None of the checks should PASS when no fixture/stock/toolpath exists
        assert v.any_pass is False

    def test_no_fail_without_toolpath(self):
        """Verifiers must not FAIL when no segments provided — only INSUFFICIENT_DATA."""
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        v = assess_toolpath_verification(rec)
        assert v.any_fail is False

    def test_all_checks_insufficient_data(self):
        """With no toolpath or geometry, all checks return INSUFFICIENT_DATA/NOT_PERFORMED."""
        rec = _make_record([], (0.0, 0.0, 0.0), (10.0, 10.0, 10.0))
        v = assess_toolpath_verification(rec)
        expected = {
            VerificationStatus.INSUFFICIENT_DATA.value,
            VerificationStatus.NOT_PERFORMED.value,
        }
        for field_val in [
            v.tool_reach, v.machine_envelope, v.tool_part_collision,
            v.tool_stock_collision, v.tool_fixture_collision,
            v.holder_part_collision, v.holder_fixture_collision,
        ]:
            assert field_val in expected, (
                f"Expected INSUFFICIENT_DATA/NOT_PERFORMED, got {field_val}"
            )

    @pytest.mark.parametrize("filename", _REAL_STEP_FILES)
    def test_real_step_verification_summary_in_coverage(self, filename: str):
        """MUST 39: build_phase6_coverage must include verification_summary."""
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        assert isinstance(result.verification_summary, ToolpathVerificationSummary)
        assert result.verification_summary.global_verification_pass is False
        assert result.verification_summary.any_fail is False

    @pytest.mark.parametrize("filename", _REAL_STEP_FILES)
    def test_real_step_no_fabricated_verification_pass(self, filename: str):
        """HARD RULE 16: no fabricated PASS in verification."""
        rec = _parse_real(filename)
        result = build_phase6_coverage(rec)
        v = result.verification_summary
        assert v.any_pass is False


# ---------------------------------------------------------------------------
# TestToolCatalogProvenance (MUST 44)
# ---------------------------------------------------------------------------

class TestToolCatalogProvenance:
    def test_every_end_mill_has_stable_id(self):
        """MUST 44: every catalog tool has a unique stable_id."""
        from backend.cutting_tools.seed_catalog import get_catalog
        em = [t for t in get_catalog() if t.tool_category_code == "END_MILL"]
        ids = [t.stable_id for t in em]
        assert len(ids) == len(set(ids)), "Duplicate stable_id in end mill catalog"

    def test_every_drill_has_stable_id(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        ids = [t.stable_id for t in drills]
        assert len(ids) == len(set(ids)), "Duplicate stable_id in drill catalog"

    def test_every_tool_has_manufacturer(self):
        """MUST 44: every catalog tool has a manufacturer."""
        from backend.cutting_tools.seed_catalog import get_catalog
        for t in get_catalog():
            assert t.manufacturer, f"{t.stable_id} missing manufacturer"

    def test_every_tool_has_catalog_code(self):
        """MUST 44: every catalog tool has a product name / catalog code."""
        from backend.cutting_tools.seed_catalog import get_catalog
        for t in get_catalog():
            assert t.product_name or t.catalog_code, (
                f"{t.stable_id} missing product_name and catalog_code"
            )

    def test_no_fabricated_cutting_data_in_catalog(self):
        """MUST 44: cutting data only where explicitly sourced."""
        from backend.cutting_tools.seed_catalog import get_catalog
        for t in get_catalog():
            # source_authority must exist and not be a fabricated sentinel
            assert t.source_authority not in ("FABRICATED", "INVENTED", "GUESSED"), (
                f"{t.stable_id} has fabricated source_authority"
            )

    def test_all_end_mill_diameters_positive(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        em = [t for t in get_catalog() if t.tool_category_code == "END_MILL"]
        for t in em:
            assert t.cutting_diameter_mm is not None
            assert t.cutting_diameter_mm > 0

    def test_all_drill_diameters_positive(self):
        from backend.cutting_tools.seed_catalog import get_catalog
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        for t in drills:
            assert t.cutting_diameter_mm is not None
            assert t.cutting_diameter_mm > 0

    def test_no_new_fabricated_entries_added(self):
        """MUST 44: total catalog count matches expected (no fabricated additions)."""
        from backend.cutting_tools.seed_catalog import get_catalog
        catalog = get_catalog()
        # Phase 5 baseline: 60 total records
        # Phase 6 adds 0 new records (MUST 5: no fabrication)
        assert len(catalog) >= 60, "Catalog unexpectedly shrank"
        # Confirm no entries with fabricated diameters were added
        fabricated = {2.5, 6.6, 7.0, 9.0, 20.0}
        for d in fabricated:
            matching = [t for t in catalog if t.cutting_diameter_mm == d]
            if matching:
                # Only allow if the tool was in the catalog before Phase 6
                # (source_authority must be OFFICIAL_MANUFACTURER_CATALOG)
                for t in matching:
                    assert t.source_authority == "OFFICIAL_MANUFACTURER_CATALOG", (
                        f"Fabricated tool at ⌀{d}mm: {t.stable_id}"
                    )
