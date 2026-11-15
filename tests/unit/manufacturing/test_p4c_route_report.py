"""P4-C: Process Route Report generation tests.

Verifies:
- Report fields populated from confirmed feature + route + setup
- review_status=PENDING_REVIEW (never APPROVED)
- provenance=USER_CONFIRMED
- EN and TR disclaimers both present
- HTML output contains DRAFT/PENDING_REVIEW banner
- HTML output contains both disclaimers
- CAM gate result flows into report
- GD&T constraints serialized correctly
- Routes serialized with PROPOSED status

FABRICATED_REPORT_CONTENT=NO
AUTO_APPROVED=NO
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from types import MappingProxyType

import pytest

from backend.drawing_intelligence.gdt_process_constraints import (
    GdtCharacteristic,
    GdtConstraintType,
    GdtProcessConstraint,
    GdtProcessStatus,
)
from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeature,
    ManufacturingFeatureType,
    RecognitionMethod,
)
from backend.interoperability.geometry import CanonicalSurfaceType
from backend.manufacturing.cam_gate import check_cam_prerequisites
from backend.manufacturing.confirmed_feature_route import bridge_confirmed_feature_to_route
from backend.manufacturing.route_report import (
    generate_route_report,
    generate_route_report_html,
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
    fid: str = "feat-report-001",
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


def _make_gdt_constraint() -> GdtProcessConstraint:
    return GdtProcessConstraint(
        constraint_id="GPC-R01-POSITION",
        req_id="R01",
        characteristic=GdtCharacteristic.POSITION,
        constraint_type=GdtConstraintType.REVIEW_REQUIRED,
        constraint_note="Position tolerance 0.05 - REVIEW_REQUIRED",
        gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
        provenance="FILE_EVIDENCE",
        feature_ref=None,
    )


class TestReportFields:

    def test_feature_id_populated(self):
        feat = _make_feat(fid="feat-rpt-001")
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.feature_id == "feat-rpt-001"

    def test_feature_type_populated(self):
        feat = _make_feat(ftype=ManufacturingFeatureType.BLIND_HOLE)
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert "BLIND_HOLE" in report.feature_type

    def test_depth_mm_from_feature(self):
        feat = _make_feat(depth_mm=Decimal("33.0"))
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.depth_mm == pytest.approx(33.0)

    def test_diameter_mm_from_feature(self):
        feat = _make_feat(diameter_mm=Decimal("14.0"))
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.diameter_mm == pytest.approx(14.0)

    def test_material_grade_from_session(self):
        feat = _make_feat()
        sess = _make_full_session(material="316L")
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result, setup_session=sess)
        assert report.material_grade == "316L"

    def test_stock_shape_from_session(self):
        feat = _make_feat()
        sess = _make_full_session()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result, setup_session=sess)
        assert report.stock_shape is not None

    def test_setup_datum_a_from_session(self):
        feat = _make_feat()
        sess = _make_full_session()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result, setup_session=sess)
        assert report.setup_datum_a == "Bottom face"

    def test_n_setups_from_session(self):
        feat = _make_feat()
        sess = _make_full_session()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result, setup_session=sess)
        assert report.n_setups == 1

    def test_no_session_gives_unknown_material(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.material_grade is None


class TestReviewStatusAndProvenance:

    def test_review_status_is_pending(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.review_status == "PENDING_REVIEW"

    def test_review_status_never_approved(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert "APPROVED" not in report.review_status

    def test_provenance_is_user_confirmed(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.provenance == "USER_CONFIRMED"

    def test_report_id_starts_with_rpt(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert report.report_id.startswith("RPT-")

    def test_generated_at_is_iso_format(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        from datetime import datetime
        # Should parse without error
        datetime.fromisoformat(report.generated_at)


class TestDisclaimers:

    def test_en_disclaimer_present(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert len(report.disclaimer_en) > 20
        assert "AUTO_APPROVED=NO" in report.disclaimer_en

    def test_tr_disclaimer_present(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert len(report.disclaimer_tr) > 20
        assert "TASLAK" in report.disclaimer_tr

    def test_tr_disclaimer_contains_offline_equiv(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        assert "OFFLİNE" in report.disclaimer_tr or "OFFLINE" in report.disclaimer_tr


class TestGdtConstraints:

    def test_gdt_constraint_serialized(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        gdt = _make_gdt_constraint()
        report = generate_route_report(
            feat,
            route_bridge.route_result,
            gdt_constraints=(gdt,),
        )
        assert len(report.gdt_constraints) == 1
        item = report.gdt_constraints[0]
        assert item["constraint_id"] == "GPC-R01-POSITION"
        assert item["req_id"] == "R01"
        assert "REVIEW_REQUIRED" in item["gdnt_status"]

    def test_no_gdt_constraints_gives_empty_tuple(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result, gdt_constraints=())
        assert len(report.gdt_constraints) == 0


class TestCamStateInReport:

    def test_cam_ready_true_when_all_met(self):
        feat = _make_feat()
        sess = _make_full_session()
        cam_state = check_cam_prerequisites(feat, sess)
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(
            feat,
            route_bridge.route_result,
            setup_session=sess,
            cam_state=cam_state,
        )
        assert report.cam_ready is True
        assert report.cam_first_blocker is None

    def test_cam_ready_false_when_no_session(self):
        feat = _make_feat()
        cam_state = check_cam_prerequisites(feat, None)
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(
            feat,
            route_bridge.route_result,
            cam_state=cam_state,
        )
        assert report.cam_ready is False
        assert report.cam_first_blocker is not None


class TestRoutesInReport:

    def test_routes_have_proposed_status(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        for r in report.routes:
            if not r.get("rejected"):
                assert r["status"] == "PROPOSED"

    def test_no_route_result_gives_empty_routes(self):
        feat = _make_feat()
        report = generate_route_report(feat, None)
        assert report.routes == ()

    def test_as_dict_contains_routes(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        d = report.as_dict()
        assert "routes" in d
        assert isinstance(d["routes"], list)


class TestHtmlGeneration:

    def test_html_contains_pending_review_banner(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        html = generate_route_report_html(report)
        assert "PENDING_REVIEW" in html

    def test_html_contains_en_disclaimer(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        html = generate_route_report_html(report)
        assert "AUTO_APPROVED=NO" in html

    def test_html_contains_tr_disclaimer(self):
        feat = _make_feat()
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        html = generate_route_report_html(report)
        assert "TASLAK" in html

    def test_html_contains_feature_id(self):
        feat = _make_feat(fid="feat-html-001")
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        html = generate_route_report_html(report)
        assert "feat-html-001" in html

    def test_html_no_script_injection(self):
        feat = _make_feat(fid="feat-<script>alert(1)</script>")
        route_bridge = bridge_confirmed_feature_to_route(feat)
        report = generate_route_report(feat, route_bridge.route_result)
        html = generate_route_report_html(report)
        assert "<script>alert(1)</script>" not in html
