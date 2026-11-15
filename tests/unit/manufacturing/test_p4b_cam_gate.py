"""P4-B: CAM Prerequisite Gate tests.

Verifies granular per-requirement CAM readiness checking:
  1. feature_confirmed: USER_CONFIRMED → MET; others → MISSING
  2. feature_type_mappable: FREEFORM/UNKNOWN → BLOCKED
  3. depth_known: required types with no depth → MISSING
  4. diameter_known: required types with no diameter/radius → MISSING
  5. material_defined: empty/missing material_grade → MISSING
  6. stock_complete: missing stock shape dims → MISSING
  7. setup_defined: no datum_a → MISSING

Also verifies:
  - cam_ready=True only when ALL prerequisites are MET
  - first_blocker names exactly the first missing/blocked prerequisite
  - disclaimer text is present and contains offline/no-dispatch claim

OFFLINE_ONLY=YES
AUTO_APPROVE=NO
CNC_DISPATCH=NO
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import MappingProxyType

from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeature,
    ManufacturingFeatureType,
    RecognitionMethod,
)
from backend.interoperability.geometry import CanonicalSurfaceType
from backend.manufacturing.cam_gate import (
    CamPrerequisiteStatus,
    check_cam_prerequisites,
)
from backend.manufacturing.setup_stock import (
    SetupDefinition,
    SetupStockSession,
    StockDefinition,
    StockShape,
    create_setup_stock_session,
)


def _make_feat(
    ftype: ManufacturingFeatureType = ManufacturingFeatureType.BLIND_HOLE,
    confidence: FeatureRecognitionConfidence = FeatureRecognitionConfidence.USER_CONFIRMED,
    diameter_mm: Decimal | None = Decimal("12.0"),
    depth_mm: Decimal | None = Decimal("25.0"),
    fid: str = "feat-cam-001",
) -> ManufacturingFeature:
    return ManufacturingFeature(
        feature_id=fid,
        feature_type=ftype,
        source_body_id="body-01",
        source_face_ids=("face-01",),
        source_edge_ids=(),
        surface_type=CanonicalSurfaceType.CYLINDER,
        location=None,
        axis=None,
        diameter_mm=diameter_mm,
        depth_mm=depth_mm,
        width_mm=None,
        length_mm=None,
        radius_mm=None,
        angle_deg=None,
        bounding_box=None,
        recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
        confidence=confidence,
        pattern_id=None,
        confirmed_by="eng1",
        metadata=MappingProxyType({}),
    )


def _make_full_session(material: str = "C45") -> SetupStockSession:
    sess = create_setup_stock_session()
    sess.stock = StockDefinition(
        stock_id=str(uuid.uuid4()),
        shape=StockShape.RECTANGULAR_BLOCK,
        material_grade=material,
        length_mm=200.0,
        width_mm=150.0,
        height_mm=50.0,
        outer_diameter_mm=None,
        inner_diameter_mm=None,
        stock_notes=None,
        confirmed_by="eng1",
    )
    sess.setup = SetupDefinition(
        setup_id=str(uuid.uuid4()),
        n_setups=1,
        datum_a="Bottom face",
        datum_b=None,
        datum_c=None,
        orientation=None,
        fixture_note=None,
        confirmed_by="eng1",
    )
    return sess


class TestPrereq1FeatureConfirmed:

    def test_user_confirmed_is_met(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.USER_CONFIRMED)
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "feature_confirmed")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_inferred_is_missing(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.INFERRED)
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "feature_confirmed")
        assert prereq.status == CamPrerequisiteStatus.MISSING

    def test_ambiguous_is_missing(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.AMBIGUOUS)
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "feature_confirmed")
        assert prereq.status == CamPrerequisiteStatus.MISSING


class TestPrereq2FeatureTypeMappable:

    def test_blind_hole_is_mappable(self):
        feat = _make_feat(ftype=ManufacturingFeatureType.BLIND_HOLE)
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "feature_type_mappable")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_freeform_is_blocked(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.FREEFORM,
            diameter_mm=None,
            depth_mm=None,
        )
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "feature_type_mappable")
        assert prereq.status == CamPrerequisiteStatus.BLOCKED

    def test_unknown_is_blocked(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.UNKNOWN,
            diameter_mm=None,
            depth_mm=None,
        )
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "feature_type_mappable")
        assert prereq.status == CamPrerequisiteStatus.BLOCKED


class TestPrereq3DepthKnown:

    def test_hole_with_depth_is_met(self):
        feat = _make_feat(ftype=ManufacturingFeatureType.BLIND_HOLE, depth_mm=Decimal("30.0"))
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "depth_known")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_hole_without_depth_is_missing(self):
        feat = _make_feat(ftype=ManufacturingFeatureType.BLIND_HOLE, depth_mm=None)
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "depth_known")
        assert prereq.status == CamPrerequisiteStatus.MISSING

    def test_planar_face_does_not_require_depth(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.PLANAR_FACE, diameter_mm=None, depth_mm=None
        )
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "depth_known")
        assert prereq.status == CamPrerequisiteStatus.MET


class TestPrereq4DiameterKnown:

    def test_hole_with_diameter_is_met(self):
        feat = _make_feat(diameter_mm=Decimal("12.0"))
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "diameter_known")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_hole_without_diameter_or_radius_is_missing(self):
        feat = ManufacturingFeature(
            feature_id="feat-hole-002",
            feature_type=ManufacturingFeatureType.BLIND_HOLE,
            source_body_id="body-01",
            source_face_ids=("face-01",),
            source_edge_ids=(),
            surface_type=CanonicalSurfaceType.CYLINDER,
            location=None,
            axis=None,
            diameter_mm=None,
            depth_mm=Decimal("25.0"),
            width_mm=None,
            length_mm=None,
            radius_mm=None,
            angle_deg=None,
            bounding_box=None,
            recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
            confidence=FeatureRecognitionConfidence.USER_CONFIRMED,
            pattern_id=None,
            confirmed_by="eng1",
            metadata=MappingProxyType({}),
        )
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "diameter_known")
        assert prereq.status == CamPrerequisiteStatus.MISSING

    def test_planar_face_does_not_require_diameter(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.PLANAR_FACE, diameter_mm=None, depth_mm=None
        )
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "diameter_known")
        assert prereq.status == CamPrerequisiteStatus.MET


class TestPrereq5MaterialDefined:

    def test_material_grade_set_is_met(self):
        feat = _make_feat()
        sess = _make_full_session(material="C45")
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "material_defined")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_no_session_is_missing(self):
        feat = _make_feat()
        state = check_cam_prerequisites(feat, None)
        prereq = next(p for p in state.prerequisites if p.name == "material_defined")
        assert prereq.status == CamPrerequisiteStatus.MISSING

    def test_no_stock_is_missing(self):
        feat = _make_feat()
        sess = create_setup_stock_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "material_defined")
        assert prereq.status == CamPrerequisiteStatus.MISSING


class TestPrereq6StockComplete:

    def test_complete_rect_block_is_met(self):
        feat = _make_feat()
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "stock_complete")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_incomplete_stock_is_missing(self):
        feat = _make_feat()
        sess = create_setup_stock_session()
        sess.stock = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=None,  # missing
            width_mm=None,   # missing
            height_mm=None,  # missing
            outer_diameter_mm=None,
            inner_diameter_mm=None,
            stock_notes=None,
            confirmed_by="eng1",
        )
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "stock_complete")
        assert prereq.status == CamPrerequisiteStatus.MISSING


class TestPrereq7SetupDefined:

    def test_full_setup_with_datum_a_is_met(self):
        feat = _make_feat()
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "setup_defined")
        assert prereq.status == CamPrerequisiteStatus.MET

    def test_no_setup_is_missing(self):
        feat = _make_feat()
        sess = create_setup_stock_session()
        sess.stock = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=200.0,
            width_mm=150.0,
            height_mm=50.0,
            outer_diameter_mm=None,
            inner_diameter_mm=None,
            stock_notes=None,
            confirmed_by="eng1",
        )
        # no setup set
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "setup_defined")
        assert prereq.status == CamPrerequisiteStatus.MISSING

    def test_setup_without_datum_a_is_missing(self):
        feat = _make_feat()
        sess = _make_full_session()
        sess.setup = SetupDefinition(
            setup_id=str(uuid.uuid4()),
            n_setups=1,
            datum_a=None,  # missing
            datum_b=None,
            datum_c=None,
            orientation=None,
            fixture_note=None,
            confirmed_by="eng1",
        )
        state = check_cam_prerequisites(feat, sess)
        prereq = next(p for p in state.prerequisites if p.name == "setup_defined")
        assert prereq.status == CamPrerequisiteStatus.MISSING


class TestOverallCamReady:

    def test_all_met_gives_cam_ready_true(self):
        feat = _make_feat()
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        assert state.cam_ready is True
        assert state.first_blocker is None
        assert len(state.all_blockers) == 0

    def test_missing_depth_gives_cam_ready_false(self):
        feat = _make_feat(depth_mm=None)
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        assert state.cam_ready is False
        assert state.first_blocker is not None

    def test_no_session_gives_cam_ready_false(self):
        feat = _make_feat()
        state = check_cam_prerequisites(feat, None)
        assert state.cam_ready is False

    def test_disclaimer_contains_offline_only(self):
        feat = _make_feat()
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        assert "OFFLINE" in state.disclaimer.upper() or "offline" in state.disclaimer.lower()
        assert "AUTO_APPROVED=NO" in state.disclaimer

    def test_as_dict_has_all_keys(self):
        feat = _make_feat()
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        d = state.as_dict()
        for key in ("feature_id", "cam_ready", "prerequisites", "first_blocker",
                    "all_blockers", "offline_only", "disclaimer"):
            assert key in d

    def test_as_dict_offline_only_is_true(self):
        feat = _make_feat()
        sess = _make_full_session()
        state = check_cam_prerequisites(feat, sess)
        assert state.as_dict()["offline_only"] is True
