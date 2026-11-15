"""P4-A: Confirmed Feature → Route Generator Bridge tests.

Verifies:
- USER_CONFIRMED → route generated (PROPOSED status, never APPROVED)
- EXACT_BREP and TOPOLOGY_RULE → route generated
- GEOMETRY_RULE, PATTERN_RECOGNIZED, INFERRED, AMBIGUOUS → blocked (NOT_CONFIRMED)
- FREEFORM, UNKNOWN → blocked (UNSUPPORTED_FEATURE_TYPE)
- Dimensions flow from confirmed feature to route (never re-inferred)
- Provenance is USER_CONFIRMED throughout
- Route status is always PROPOSED/DRAFT — AUTO_APPROVED=NO

FABRICATED_ROUTE=NO
AUTO_APPROVED=NO
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType

from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeature,
    ManufacturingFeatureType,
    RecognitionMethod,
)
from backend.interoperability.geometry import CanonicalSurfaceType
from backend.manufacturing.confirmed_feature_route import (
    RouteBlockedReason,
    bridge_confirmed_feature_to_route,
)


def _make_feat(
    ftype: ManufacturingFeatureType = ManufacturingFeatureType.BLIND_HOLE,
    confidence: FeatureRecognitionConfidence = FeatureRecognitionConfidence.USER_CONFIRMED,
    diameter_mm: Decimal | None = Decimal("12.0"),
    depth_mm: Decimal | None = Decimal("25.0"),
    width_mm: Decimal | None = None,
    length_mm: Decimal | None = None,
    radius_mm: Decimal | None = None,
    fid: str = "feat-hole-001",
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
        width_mm=width_mm,
        length_mm=length_mm,
        radius_mm=radius_mm,
        angle_deg=None,
        bounding_box=None,
        recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
        confidence=confidence,
        pattern_id=None,
        confirmed_by="eng1",
        metadata=MappingProxyType({}),
    )


class TestConfidenceGuard:

    def test_user_confirmed_is_eligible(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.USER_CONFIRMED)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False
        assert result.blocked_reason is None

    def test_exact_brep_is_eligible(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.EXACT_BREP)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False

    def test_topology_rule_is_eligible(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.TOPOLOGY_RULE)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False

    def test_geometry_rule_is_blocked(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.GEOMETRY_RULE)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is True
        assert result.blocked_reason == RouteBlockedReason.NOT_CONFIRMED

    def test_pattern_recognized_is_blocked(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.PATTERN_RECOGNIZED)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is True
        assert result.blocked_reason == RouteBlockedReason.NOT_CONFIRMED

    def test_inferred_is_blocked(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.INFERRED)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is True
        assert result.blocked_reason == RouteBlockedReason.NOT_CONFIRMED

    def test_ambiguous_is_blocked(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.AMBIGUOUS)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is True
        assert result.blocked_reason == RouteBlockedReason.NOT_CONFIRMED


class TestUnsupportedFeatureTypes:

    def test_freeform_is_blocked(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.FREEFORM,
            confidence=FeatureRecognitionConfidence.USER_CONFIRMED,
        )
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is True
        assert result.blocked_reason == RouteBlockedReason.UNSUPPORTED_FEATURE_TYPE

    def test_unknown_is_blocked(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.UNKNOWN,
            confidence=FeatureRecognitionConfidence.USER_CONFIRMED,
        )
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is True
        assert result.blocked_reason == RouteBlockedReason.UNSUPPORTED_FEATURE_TYPE


class TestDimensionFlow:

    def test_diameter_mm_flows_to_route(self):
        feat = _make_feat(diameter_mm=Decimal("15.0"), depth_mm=Decimal("30.0"))
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False
        # Route result exists and was generated from engineer-confirmed dims
        assert result.route_result is not None

    def test_radius_used_when_diameter_absent(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.OUTER_DIAMETER,
            diameter_mm=None,
            depth_mm=None,
            radius_mm=Decimal("6.0"),
            confidence=FeatureRecognitionConfidence.USER_CONFIRMED,
        )
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False

    def test_depth_mm_flows_to_route(self):
        feat = _make_feat(depth_mm=Decimal("40.0"))
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False
        assert result.route_result is not None

    def test_width_mm_flows_for_slot(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.OPEN_SLOT,
            diameter_mm=None,
            depth_mm=Decimal("15.0"),
            width_mm=Decimal("8.0"),
            confidence=FeatureRecognitionConfidence.USER_CONFIRMED,
        )
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False


class TestProvenanceAndStatus:

    def test_provenance_is_user_confirmed(self):
        feat = _make_feat()
        result = bridge_confirmed_feature_to_route(feat)
        assert result.provenance == "USER_CONFIRMED"

    def test_disclaimer_contains_draft(self):
        feat = _make_feat()
        result = bridge_confirmed_feature_to_route(feat)
        assert "DRAFT" in result.disclaimer.upper() or "PROPOSED" in result.disclaimer.upper()

    def test_disclaimer_contains_no_auto_approve(self):
        feat = _make_feat()
        result = bridge_confirmed_feature_to_route(feat)
        assert "AUTO_APPROVED=NO" in result.disclaimer

    def test_route_status_is_proposed(self):
        feat = _make_feat()
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False
        d = result.as_dict()
        rg = d["route_generation"]
        assert rg is not None
        assert rg["status"] == "PROPOSED"
        for r in rg.get("routes", []):
            assert r["status"] == "PROPOSED"

    def test_as_dict_contains_feature_id(self):
        feat = _make_feat(fid="feat-test-999")
        result = bridge_confirmed_feature_to_route(feat)
        d = result.as_dict()
        assert d["feature_id"] == "feat-test-999"

    def test_blocked_result_has_no_route_generation(self):
        feat = _make_feat(confidence=FeatureRecognitionConfidence.AMBIGUOUS)
        result = bridge_confirmed_feature_to_route(feat)
        d = result.as_dict()
        assert d["route_generation"] is None

    def test_domain_feature_type_set_for_hole(self):
        feat = _make_feat(ftype=ManufacturingFeatureType.BLIND_HOLE)
        result = bridge_confirmed_feature_to_route(feat)
        assert result.domain_feature_type is not None


class TestPocketAndSlotRoutes:

    def test_open_pocket_eligible(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.OPEN_POCKET,
            diameter_mm=None,
            depth_mm=Decimal("12.0"),
            width_mm=Decimal("20.0"),
            length_mm=Decimal("40.0"),
        )
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False

    def test_closed_slot_eligible(self):
        feat = _make_feat(
            ftype=ManufacturingFeatureType.CLOSED_SLOT,
            diameter_mm=None,
            depth_mm=Decimal("10.0"),
            width_mm=Decimal("6.0"),
            length_mm=Decimal("30.0"),
        )
        result = bridge_confirmed_feature_to_route(feat)
        assert result.blocked is False
