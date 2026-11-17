"""
P10 Phase 5 — Real 3D Feature Coverage Qualification Tests.

Validates MUSTs from MACHININGPRO_AI_P10_PHASE5_REAL_3D_FEATURE_COVERAGE
against all 6 user-owned STEP files.

HARD RULES (enforced):
  - feature_status = "CANDIDATE" always (MUST 17)
  - is_dispatchable = False always (HARD RULE 27)
  - production_released = False always (HARD RULE 28)
  - OD_AS_BORE_FALSE_POSITIVE_COUNT = 0 for negative-geometry tests (MUST 7)
  - AMBIGUOUS remains AMBIGUOUS (HARD RULE 20)
  - NOT_VERIFIABLE remains NOT_VERIFIABLE (HARD RULE 21)
  - gouge_validated = NOT_VERIFIABLE (HARD RULE 11)
  - GOUGE_COMPARATOR_IMPLEMENTED = False (Phase 5 scope)
"""

from __future__ import annotations

import pathlib

import pytest

from backend.step_brep.feature_detector import detect_hole_candidates
from backend.step_brep.gmsh_step_parser import parse_step_file
from backend.step_brep.phase5_feature_detector import (
    GOUGE_COMPARATOR_IMPLEMENTED,
    CylinderOrientation,
    build_face_adjacency,
    build_gouge_comparator_result,
    classify_cylinder_orientation,
    compute_cylinder_params,
    detect_oriented_cylinders,
    detect_pocket_candidates,
    detect_slot_candidates,
    detect_step_shoulder_candidates,
    filter_internal_cylinders,
)

# ---------------------------------------------------------------------------
# Constants — real STEP files and baseline data from Phase 4 (2026-11-17)
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

# Phase 4 hole candidate counts (MUST 2 baseline)
_PHASE4_HOLE_COUNTS = {
    "electronics-enclosure.step": 8,
    "flanged-bushing (1).step": 5,
    "flange-plate.step": 5,
    "l-bracket.step": 4,
    "Pump Manifold v3.step": 0,
    "stepped-shaft-keyway.step": 3,
}
_PHASE4_TOTAL_HOLES = 25


# ===========================================================================
# MUST 2 — Feature baseline matches Phase 4 exactly
# ===========================================================================


class TestFeatureBaseline:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_phase4_hole_count_preserved(self, fname: str) -> None:
        """MUST 2: Phase 5 does not regress Phase 4 hole candidate counts."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        holes = detect_hole_candidates(r)
        assert len(holes) == _PHASE4_HOLE_COUNTS[fname], (
            f"{fname}: Phase 4 baseline broken — expected {_PHASE4_HOLE_COUNTS[fname]}, "
            f"got {len(holes)}"
        )

    def test_phase4_total_holes_25(self) -> None:
        """MUST 2: Total Phase 4 holes across all 6 files = 25."""
        total = 0
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
            total += len(detect_hole_candidates(r))
        assert total == _PHASE4_TOTAL_HOLES


# ===========================================================================
# MUST 3 — Feature provenance: source file hash unchanged
# ===========================================================================


class TestFeatureProvenance:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_source_hash_unchanged(self, fname: str) -> None:
        """MUST 3: Source files have not been modified (SHA256 stable)."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.sha256 == _EXPECTED_SHA256[fname], (
            f"{fname}: SHA256 changed — source file tampered"
        )


# ===========================================================================
# MUST 4 — compute_cylinder_params: improved axis detection
# ===========================================================================


class TestImprovedCylinderParams:
    """Validates Phase 5 bbox-equalness axis detection vs Phase 3 largest-extent."""

    def test_short_cylinder_axis_is_z(self) -> None:
        """MUST 4: Short cylinder (disk) → axis=Z, diameter from equal XY extents."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        # Simulate flanged-bushing flange OD face: bbox (45,45,5)
        face = StepFaceSummary(
            tag=5,
            surface_class="CYLINDRICAL",
            bbox_min=(-22.5, -22.5, 0.0),
            bbox_max=(22.5, 22.5, 5.0),
            boundary_curve_tags=[10, 11],
            normal_at_center=(1.0, 0.0, 0.0),
            has_circular_boundary=True,
        )
        axis, dia, depth = compute_cylinder_params(face)
        assert axis == "Z", f"Expected Z axis for disk-like cylinder, got {axis}"
        assert dia is not None and abs(dia - 45.0) < 0.5

    def test_tall_cylinder_axis_is_z(self) -> None:
        """MUST 4: Tall cylinder → axis=Z detected correctly."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        # stepped-shaft main OD: bbox (25,25,39)
        face = StepFaceSummary(
            tag=1,
            surface_class="CYLINDRICAL",
            bbox_min=(-12.5, -12.5, 0.0),
            bbox_max=(12.5, 12.5, 39.0),
            boundary_curve_tags=[1, 2],
            normal_at_center=(0.88, -0.48, 0.0),
            has_circular_boundary=True,
        )
        axis, dia, depth = compute_cylinder_params(face)
        assert axis == "Z"
        assert dia is not None and abs(dia - 25.0) < 0.5

    def test_x_axis_cylinder_detected(self) -> None:
        """MUST 4: X-axis through-hole in bracket → axis=X."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        # l-bracket vertical plate hole: bbox (5, 6.6, 6.6)
        face = StepFaceSummary(
            tag=12,
            surface_class="CYLINDRICAL",
            bbox_min=(0.0, 26.7, 29.7),
            bbox_max=(5.0, 33.3, 36.3),
            boundary_curve_tags=[20, 21],
            normal_at_center=(0.0, 0.88, -0.48),
            has_circular_boundary=True,
        )
        axis, dia, depth = compute_cylinder_params(face)
        assert axis == "X"
        assert dia is not None and 5.0 < dia < 8.0


# ===========================================================================
# MUST 5–8 — Cylinder orientation: INTERNAL / EXTERNAL / AMBIGUOUS
# ===========================================================================


class TestCylinderOrientation:
    def test_external_cylinder_large_diameter_ratio(self) -> None:
        """MUST 5: Large-diameter cylinder spanning full part → EXTERNAL."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        face = StepFaceSummary(
            tag=5,
            surface_class="CYLINDRICAL",
            bbox_min=(-22.5, -22.5, 0.0),
            bbox_max=(22.5, 22.5, 5.0),
            boundary_curve_tags=[10, 11],
            normal_at_center=(1.0, 0.0, 0.0),
            has_circular_boundary=True,
        )
        record = _make_minimal_record(
            faces=[face],
            bbox_min=(-22.5, -22.5, 0.0),
            bbox_max=(22.5, 22.5, 30.0),
        )
        orientation, _ = classify_cylinder_orientation(face, record)
        assert orientation == CylinderOrientation.EXTERNAL_CYLINDER

    def test_internal_cylinder_offset_small(self) -> None:
        """MUST 6: Small off-center cylinder → INTERNAL_CYLINDER."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        face = StepFaceSummary(
            tag=20,
            surface_class="CYLINDRICAL",
            bbox_min=(30.0, 20.0, -15.0),
            bbox_max=(37.0, 27.0, 15.0),
            boundary_curve_tags=[50, 51],
            normal_at_center=(0.88, -0.48, 0.0),
            has_circular_boundary=True,
        )
        record = _make_minimal_record(
            faces=[face],
            bbox_min=(-40.0, -30.0, -15.0),
            bbox_max=(40.0, 30.0, 15.0),
        )
        orientation, _ = classify_cylinder_orientation(face, record)
        assert orientation == CylinderOrientation.INTERNAL_CYLINDER

    def test_no_od_as_bore_false_positive(self) -> None:
        """MUST 7: OD_AS_BORE_FALSE_POSITIVE_COUNT=0 for stepped shaft main OD."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        # stepped-shaft main OD: Ø25mm shaft → must NOT be classified as INTERNAL
        face = StepFaceSummary(
            tag=1,
            surface_class="CYLINDRICAL",
            bbox_min=(-12.5, -12.5, 0.0),
            bbox_max=(12.5, 12.5, 39.0),
            boundary_curve_tags=[1, 2],
            normal_at_center=(0.88, -0.48, 0.0),
            has_circular_boundary=True,
        )
        record = _make_minimal_record(
            faces=[face],
            bbox_min=(-12.5, -12.5, 0.0),
            bbox_max=(12.5, 12.5, 120.0),
        )
        orientation, evidence = classify_cylinder_orientation(face, record)
        assert orientation != CylinderOrientation.INTERNAL_CYLINDER, (
            f"FALSE POSITIVE: OD classified as internal. Evidence: {evidence}"
        )

    def test_oriented_cylinders_are_all_candidate(self) -> None:
        """MUST 17: All oriented cylinder results have feature_status=CANDIDATE."""
        fname = "l-bracket.step"
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        cylinders = detect_oriented_cylinders(r)
        for c in cylinders:
            assert c.feature_status == "CANDIDATE"
            assert not c.is_dispatchable
            assert not c.production_released

    def test_filter_internal_excludes_external(self) -> None:
        """MUST 7: filter_internal_cylinders excludes EXTERNAL and AMBIGUOUS entries."""
        fname = "stepped-shaft-keyway.step"
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        cylinders = detect_oriented_cylinders(r)
        internal = filter_internal_cylinders(cylinders)
        for c in internal:
            assert c.cylinder_orientation == CylinderOrientation.INTERNAL_CYLINDER

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_no_negative_dispatchable_on_oriented_cylinders(self, fname: str) -> None:
        """MUST 8 / HARD RULE 27: is_dispatchable=False for all oriented cylinders."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for c in detect_oriented_cylinders(r):
            assert not c.is_dispatchable


# ===========================================================================
# MUST 9–10 — Hole through/blind via boundary count
# ===========================================================================


class TestHoleClassification:
    def test_through_hole_has_two_or_more_boundaries(self) -> None:
        """MUST 9: THROUGH_HOLE_CANDIDATE requires ≥2 boundary curves."""
        fname = "electronics-enclosure.step"
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        cylinders = detect_oriented_cylinders(r)
        through = [c for c in cylinders if c.hole_class == "THROUGH_HOLE_CANDIDATE"]
        for c in through:
            assert c.circular_boundary_count >= 2, (
                f"THROUGH_HOLE_CANDIDATE face={c.face_tag} has only "
                f"{c.circular_boundary_count} boundary curves"
            )

    def test_transition_ring_has_low_aspect(self) -> None:
        """MUST 10: TRANSITION_RING has depth/diameter < 0.3."""
        fname = "flanged-bushing (1).step"
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        cylinders = detect_oriented_cylinders(r)
        rings = [c for c in cylinders if c.hole_class == "TRANSITION_RING"]
        for c in rings:
            if c.depth_mm and c.diameter_mm:
                assert c.depth_mm / c.diameter_mm < 0.3


# ===========================================================================
# MUST 11–13 — Pocket candidate detection
# ===========================================================================


class TestPocketDetection:
    def test_electronics_enclosure_has_pocket_candidate(self) -> None:
        """MUST 11: Electronics enclosure inner cavity → at least 1 pocket candidate."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "electronics-enclosure.step"),
            sample_origin="USER_OWNED",
        )
        pockets = detect_pocket_candidates(r)
        assert len(pockets) >= 1, (
            "Electronics enclosure inner cavity not detected as pocket candidate"
        )

    def test_pocket_candidate_has_walls(self) -> None:
        """MUST 11: Pocket candidate has ≥2 adjacent wall faces."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "electronics-enclosure.step"),
            sample_origin="USER_OWNED",
        )
        for pocket in detect_pocket_candidates(r):
            assert len(pocket.wall_face_tags) >= 2, (
                f"Pocket floor={pocket.floor_face_tag} has only "
                f"{len(pocket.wall_face_tags)} wall faces"
            )

    def test_pocket_candidate_is_candidate(self) -> None:
        """MUST 12: Pocket feature_status=CANDIDATE always."""
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
            for pocket in detect_pocket_candidates(r):
                assert pocket.feature_status == "CANDIDATE"
                assert not pocket.is_dispatchable
                assert not pocket.production_released

    def test_pocket_not_from_single_planar_face(self) -> None:
        """MUST 12 / HARD RULE: Never infer pocket from single planar face alone."""
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
            for pocket in detect_pocket_candidates(r):
                assert len(pocket.wall_face_tags) >= 2, (
                    "Pocket with <2 walls: HARD RULE violation"
                )

    def test_pocket_depth_positive_and_from_bbox(self) -> None:
        """MUST 11: Pocket depth from bbox evidence, not fabricated."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "electronics-enclosure.step"),
            sample_origin="USER_OWNED",
        )
        for pocket in detect_pocket_candidates(r):
            if pocket.depth_mm is not None:
                assert pocket.depth_mm > 0, "Pocket depth must be positive"

    def test_no_pocket_from_external_top_face(self) -> None:
        """MUST 12: Top external face of part must NOT produce pocket candidate."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "l-bracket.step"),
            sample_origin="USER_OWNED",
        )
        pockets = detect_pocket_candidates(r)
        # l-bracket top face (Z=5) is at part top → must be excluded
        part_top_z = r.bbox_max[2] if r.bbox_max else None
        if part_top_z is not None:
            for pocket in pockets:
                opening = pocket.opening_z or 0.0
                assert abs(opening - part_top_z) < 1.0 or pocket.floor_face_tag != 1, (
                    "External top face incorrectly flagged as pocket floor"
                )


# ===========================================================================
# MUST 14–16 — Slot candidate detection
# ===========================================================================


class TestSlotDetection:
    def test_stepped_shaft_has_keyway_slot(self) -> None:
        """MUST 14: Stepped-shaft-keyway.step → at least 1 slot candidate (keyway)."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "stepped-shaft-keyway.step"),
            sample_origin="USER_OWNED",
        )
        slots = detect_slot_candidates(r)
        assert len(slots) >= 1, (
            "Keyway slot in stepped-shaft-keyway.step not detected"
        )

    def test_slot_has_two_parallel_walls(self) -> None:
        """MUST 14: Slot candidate requires exactly 2 parallel side walls."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "stepped-shaft-keyway.step"),
            sample_origin="USER_OWNED",
        )
        for slot in detect_slot_candidates(r):
            assert len(slot.side_wall_tags) == 2, (
                f"Slot floor={slot.floor_face_tag} has {len(slot.side_wall_tags)} "
                f"walls instead of 2"
            )

    def test_slot_width_positive(self) -> None:
        """MUST 15: Slot width from geometry, positive."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "stepped-shaft-keyway.step"),
            sample_origin="USER_OWNED",
        )
        for slot in detect_slot_candidates(r):
            if slot.width_mm is not None:
                assert slot.width_mm > 0, "Slot width must be positive"

    def test_slot_is_candidate(self) -> None:
        """MUST 16: Slot feature_status=CANDIDATE always."""
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
            for slot in detect_slot_candidates(r):
                assert slot.feature_status == "CANDIDATE"
                assert not slot.is_dispatchable
                assert not slot.production_released

    def test_slot_not_from_parallel_faces_alone(self) -> None:
        """MUST 13 / HARD RULE: Never infer slot from 2 parallel faces alone — floor required."""
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
            for slot in detect_slot_candidates(r):
                assert slot.floor_face_tag is not None, (
                    "Slot must have an explicit floor face"
                )


# ===========================================================================
# MUST 17 — Step / shoulder detection
# ===========================================================================


class TestStepShoulderDetection:
    def test_stepped_shaft_has_step_shoulder(self) -> None:
        """MUST 17: Stepped shaft → at least 1 step/shoulder candidate."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "stepped-shaft-keyway.step"),
            sample_origin="USER_OWNED",
        )
        steps = detect_step_shoulder_candidates(r)
        assert len(steps) >= 1, (
            "No step/shoulder candidates found in stepped-shaft-keyway.step"
        )

    def test_step_height_positive(self) -> None:
        """MUST 17: Step height from bbox evidence, positive."""
        r = parse_step_file(
            str(_SAMPLE_ROOT / "stepped-shaft-keyway.step"),
            sample_origin="USER_OWNED",
        )
        for step in detect_step_shoulder_candidates(r):
            if step.step_height_mm is not None:
                assert step.step_height_mm > 0

    def test_step_is_candidate(self) -> None:
        """MUST 17: Step feature_status=CANDIDATE always."""
        for fname in _REAL_STEP_FILES:
            r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
            for step in detect_step_shoulder_candidates(r):
                assert step.feature_status == "CANDIDATE"
                assert not step.is_dispatchable
                assert not step.production_released


# ===========================================================================
# MUST 26–30 — CAM strategy readiness
# ===========================================================================


class TestCamStrategyAssessment:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_no_auto_cam_confirmation(self, fname: str) -> None:
        """MUST 26: No feature auto-confirmed as CAM-ready."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for c in detect_oriented_cylinders(r):
            assert c.feature_status == "CANDIDATE", f"{fname}: feature auto-confirmed"
        for p in detect_pocket_candidates(r):
            assert p.feature_status == "CANDIDATE"
        for s in detect_slot_candidates(r):
            assert s.feature_status == "CANDIDATE"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_no_dispatchable_features(self, fname: str) -> None:
        """HARD RULE 27: is_dispatchable=False on all Phase 5 features."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        all_features: list = []
        all_features.extend(detect_oriented_cylinders(r))
        all_features.extend(detect_pocket_candidates(r))
        all_features.extend(detect_slot_candidates(r))
        all_features.extend(detect_step_shoulder_candidates(r))
        for f in all_features:
            assert not f.is_dispatchable, (
                f"{fname}: feature {f} has is_dispatchable=True — HARD RULE 27 violated"
            )


# ===========================================================================
# MUST 31–35 — Gouge comparator (NOT_IMPLEMENTED)
# ===========================================================================


class TestGougeComparator:
    def test_comparator_not_implemented(self) -> None:
        """MUST 31: GOUGE_COMPARATOR_IMPLEMENTED=False in Phase 5."""
        assert GOUGE_COMPARATOR_IMPLEMENTED is False

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_gouge_result_not_verifiable(self, fname: str) -> None:
        """MUST 32: gouge_validated=NOT_VERIFIABLE for all files."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        result = build_gouge_comparator_result(r)
        assert result.gouge_validated == "NOT_VERIFIABLE"
        assert result.comparator_implemented is False
        assert result.voxel_result_available is False

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_no_fabricated_gouge_pass(self, fname: str) -> None:
        """HARD RULE 11: result never 'PASS', 'GOUGE_CLEARED', or similar."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        result = build_gouge_comparator_result(r)
        assert "PASS" not in result.result.upper(), (
            f"{fname}: fabricated gouge PASS in result field"
        )
        assert result.result == "NOT_VERIFIABLE"


# ===========================================================================
# MUST 36–37 — Phase 4 vs Phase 5 comparison
# ===========================================================================


class TestPhase4VsPhase5Comparison:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_phase5_cylinder_count_ge_phase4_hole_count(self, fname: str) -> None:
        """MUST 36: Phase 5 oriented cylinders ≥ Phase 4 hole candidates.

        Phase 5 may find the same or more cylindrical faces (adds EXTERNAL/AMBIGUOUS).
        It must not regress Phase 4 internal cylinder detection.
        """
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        p4_holes = detect_hole_candidates(r)
        p5_cylinders = detect_oriented_cylinders(r)
        assert len(p5_cylinders) >= len(p4_holes), (
            f"{fname}: Phase 5 found fewer total cylinders ({len(p5_cylinders)}) "
            f"than Phase 4 holes ({len(p4_holes)})"
        )

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_phase5_adds_orientation_evidence(self, fname: str) -> None:
        """MUST 37: All Phase 5 oriented cylinders have orientation evidence."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for c in detect_oriented_cylinders(r):
            assert c.orientation_evidence, (
                f"{fname}: face={c.face_tag} has empty orientation_evidence"
            )
            assert c.cylinder_orientation in (
                CylinderOrientation.INTERNAL_CYLINDER,
                CylinderOrientation.EXTERNAL_CYLINDER,
                CylinderOrientation.AMBIGUOUS_CYLINDER,
            )


# ===========================================================================
# MUST 38–39 — False positive campaign (negative geometry tests)
# ===========================================================================


class TestNegativeGeometry:
    """Synthetic parts with no holes/pockets/slots must not produce INTERNAL detections."""

    def test_pure_rectangular_block_no_internal_cylinders(self) -> None:
        """MUST 38: Pure rectangular block has no INTERNAL cylinder candidates."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        # 6 purely planar faces, no cylindrical faces
        faces = [
            StepFaceSummary(
                tag=i,
                surface_class="PLANAR",
                bbox_min=(0.0, 0.0, 0.0),
                bbox_max=(100.0, 50.0, 25.0),
                boundary_curve_tags=[i * 4, i * 4 + 1, i * 4 + 2, i * 4 + 3],
                normal_at_center=(0.0, 0.0, 1.0),
                has_circular_boundary=False,
            )
            for i in range(1, 7)
        ]
        record = _make_minimal_record(
            faces=faces,
            bbox_min=(0.0, 0.0, 0.0),
            bbox_max=(100.0, 50.0, 25.0),
        )
        cylinders = detect_oriented_cylinders(record)
        internal = filter_internal_cylinders(cylinders)
        assert len(internal) == 0, (
            f"Rectangular block: {len(internal)} false INTERNAL cylinders detected"
        )

    def test_pure_rectangular_block_no_pockets(self) -> None:
        """MUST 38: Pure rectangular block has no pocket candidates."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        # Minimal solid block faces — only top and bottom, no internal faces
        # (All at extremes of bounding box → excluded by pocket detector)
        bbox_min = (0.0, 0.0, 0.0)
        bbox_max = (100.0, 50.0, 25.0)
        top_face = StepFaceSummary(
            tag=1,
            surface_class="PLANAR",
            bbox_min=(0.0, 0.0, 25.0),
            bbox_max=(100.0, 50.0, 25.0),
            boundary_curve_tags=[1, 2, 3, 4],
            normal_at_center=(0.0, 0.0, 1.0),
            has_circular_boundary=False,
        )
        bottom_face = StepFaceSummary(
            tag=2,
            surface_class="PLANAR",
            bbox_min=(0.0, 0.0, 0.0),
            bbox_max=(100.0, 50.0, 0.0),
            boundary_curve_tags=[5, 6, 7, 8],
            normal_at_center=(0.0, 0.0, -1.0),
            has_circular_boundary=False,
        )
        record = _make_minimal_record(
            faces=[top_face, bottom_face],
            bbox_min=bbox_min,
            bbox_max=bbox_max,
        )
        pockets = detect_pocket_candidates(record)
        assert len(pockets) == 0, (
            f"Rectangular block: {len(pockets)} false pocket candidates"
        )

    def test_external_od_cylinder_not_slot(self) -> None:
        """MUST 39: OD cylinder alone does NOT produce slot candidate."""
        from backend.step_brep.gmsh_step_parser import StepFaceSummary

        face = StepFaceSummary(
            tag=1,
            surface_class="CYLINDRICAL",
            bbox_min=(-12.5, -12.5, 0.0),
            bbox_max=(12.5, 12.5, 100.0),
            boundary_curve_tags=[1, 2],
            normal_at_center=(0.88, -0.48, 0.0),
            has_circular_boundary=True,
        )
        record = _make_minimal_record(
            faces=[face],
            bbox_min=(-12.5, -12.5, 0.0),
            bbox_max=(12.5, 12.5, 100.0),
        )
        slots = detect_slot_candidates(record)
        assert len(slots) == 0, (
            f"OD cylinder alone produced {len(slots)} false slot candidates"
        )


# ===========================================================================
# MUST 40 — Safety invariants
# ===========================================================================


class TestSafetyInvariants:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_all_features_candidate_status(self, fname: str) -> None:
        """MUST 40 / HARD RULE 17: All Phase 5 features have feature_status=CANDIDATE."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for c in detect_oriented_cylinders(r):
            assert c.feature_status == "CANDIDATE"
        for p in detect_pocket_candidates(r):
            assert p.feature_status == "CANDIDATE"
        for s in detect_slot_candidates(r):
            assert s.feature_status == "CANDIDATE"
        for sh in detect_step_shoulder_candidates(r):
            assert sh.feature_status == "CANDIDATE"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_production_released_always_false(self, fname: str) -> None:
        """HARD RULE 28: production_released=False for all features."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        for c in detect_oriented_cylinders(r):
            assert not c.production_released
        for p in detect_pocket_candidates(r):
            assert not p.production_released
        for s in detect_slot_candidates(r):
            assert not s.production_released
        for sh in detect_step_shoulder_candidates(r):
            assert not sh.is_dispatchable

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_cylinder_orientation_valid_enum(self, fname: str) -> None:
        """MUST 40: All cylinder orientation values are valid CylinderOrientation entries."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        valid = set(CylinderOrientation)
        for c in detect_oriented_cylinders(r):
            assert c.cylinder_orientation in valid


# ===========================================================================
# Face adjacency tests
# ===========================================================================


class TestFaceAdjacency:
    def test_adjacency_symmetric(self) -> None:
        """Face adjacency must be symmetric: if A adj B then B adj A."""
        fname = "l-bracket.step"
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        adj = build_face_adjacency(r.faces)
        for ftag, neighbors in adj.items():
            for ntag in neighbors:
                assert ftag in adj.get(ntag, frozenset()), (
                    f"Adjacency not symmetric: {ftag} → {ntag} but not {ntag} → {ftag}"
                )

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adjacency_no_self_loops(self, fname: str) -> None:
        """Face must not be adjacent to itself."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        adj = build_face_adjacency(r.faces)
        for ftag, neighbors in adj.items():
            assert ftag not in neighbors, f"Self-loop on face {ftag} in {fname}"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_adjacency_covers_all_faces(self, fname: str) -> None:
        """Every face appears in adjacency map."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        adj = build_face_adjacency(r.faces)
        for face in r.faces:
            assert face.tag in adj


# ===========================================================================
# MUST 42 — Full regression: Phase 4 tests still pass
# ===========================================================================


class TestRegressionP4:
    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_parse_still_passes(self, fname: str) -> None:
        """MUST 42: Phase 4 parse PASS still holds after Phase 5 changes."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        assert r.status == "PASS"

    @pytest.mark.parametrize("fname", _REAL_STEP_FILES)
    def test_hole_candidates_stable(self, fname: str) -> None:
        """MUST 42: Phase 4 detect_hole_candidates unchanged."""
        r = parse_step_file(str(_SAMPLE_ROOT / fname), sample_origin="USER_OWNED")
        holes = detect_hole_candidates(r)
        assert len(holes) == _PHASE4_HOLE_COUNTS[fname]


# ===========================================================================
# Helpers
# ===========================================================================


def _make_minimal_record(
    faces: list,
    bbox_min: tuple,
    bbox_max: tuple,
) -> object:
    """Create a minimal StepImportRecord for unit tests."""
    from backend.step_brep.gmsh_step_parser import StepImportRecord

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
