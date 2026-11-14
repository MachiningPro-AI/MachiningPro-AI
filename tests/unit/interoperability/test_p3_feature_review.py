"""P3-A: Feature & Dimension Review tests.

Tests confirm_with_dimensions() on ManufacturingFeature and
the /api/cad-features/{session_id}/features/{fid}/confirm-with-dimension endpoint.

HARD RULES verified:
  - depth_mm must come from engineer, never inferred.
  - Feature type override validated against ManufacturingFeatureType enum.
  - Resulting confidence is always USER_CONFIRMED.
  - Original extracted values preserved; only user-supplied fields overridden.
  - Negative / zero depth rejected.

FABRICATED_ENGINEERING_DATA=NO
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Unit tests for confirm_with_dimensions()
# ---------------------------------------------------------------------------


def _make_feature():
    from backend.interoperability.cad_feature_recognition import (
        FeatureRecognitionConfidence,
        ManufacturingFeature,
        ManufacturingFeatureType,
        RecognitionMethod,
    )
    from backend.interoperability.geometry import CanonicalSurfaceType
    from types import MappingProxyType
    return ManufacturingFeature(
        feature_id="feat-bore-001",
        feature_type=ManufacturingFeatureType.PRECISION_BORE_CANDIDATE,
        source_body_id="body-01",
        source_face_ids=("face-01",),
        source_edge_ids=(),
        surface_type=CanonicalSurfaceType.CYLINDER,
        location=None,
        axis=None,
        diameter_mm=Decimal("20.0"),
        depth_mm=None,
        width_mm=None,
        length_mm=None,
        radius_mm=Decimal("10.0"),
        angle_deg=None,
        bounding_box=None,
        recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
        confidence=FeatureRecognitionConfidence.INFERRED,
        pattern_id=None,
        confirmed_by=None,
        metadata=MappingProxyType({}),
    )


class TestConfirmWithDimensions:

    def test_basic_confirm_sets_user_confirmed(self):
        from backend.interoperability.cad_feature_recognition import FeatureRecognitionConfidence
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1")
        assert confirmed.confidence == FeatureRecognitionConfidence.USER_CONFIRMED
        assert confirmed.confirmed_by == "eng1"

    def test_basic_confirm_preserves_existing_type(self):
        from backend.interoperability.cad_feature_recognition import ManufacturingFeatureType
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1")
        assert confirmed.feature_type == ManufacturingFeatureType.PRECISION_BORE_CANDIDATE

    def test_type_override_changes_type(self):
        from backend.interoperability.cad_feature_recognition import ManufacturingFeatureType
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions(
            "eng1",
            feature_type_override=ManufacturingFeatureType.BLIND_HOLE,
        )
        assert confirmed.feature_type == ManufacturingFeatureType.BLIND_HOLE

    def test_depth_supplied_sets_depth_mm(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1", depth_mm=Decimal("30.0"))
        assert confirmed.depth_mm == Decimal("30.0")

    def test_width_supplied_sets_width_mm(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1", width_mm=Decimal("12.5"))
        assert confirmed.width_mm == Decimal("12.5")

    def test_review_notes_stored_in_metadata(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1", review_notes="verified against blue print rev C")
        assert confirmed.metadata.get("review_notes") == "verified against blue print rev C"

    def test_no_depth_preserves_none(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1")
        assert confirmed.depth_mm is None

    def test_original_diameter_preserved(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1", depth_mm=Decimal("25.0"))
        assert confirmed.diameter_mm == Decimal("20.0")

    def test_feature_is_frozen(self):
        feat = _make_feature()
        with pytest.raises((AttributeError, TypeError)):
            feat.depth_mm = Decimal("10.0")  # type: ignore[misc]

    def test_confirm_with_dimensions_returns_new_instance(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1", depth_mm=Decimal("5.0"))
        assert confirmed is not feat
        assert feat.depth_mm is None

    def test_full_combo_type_depth_width_notes(self):
        from backend.interoperability.cad_feature_recognition import (
            FeatureRecognitionConfidence,
            ManufacturingFeatureType,
        )
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions(
            "engineer_a",
            feature_type_override=ManufacturingFeatureType.BLIND_HOLE,
            depth_mm=Decimal("22.5"),
            width_mm=Decimal("8.0"),
            review_notes="measured on CMM",
        )
        assert confirmed.feature_type == ManufacturingFeatureType.BLIND_HOLE
        assert confirmed.depth_mm == Decimal("22.5")
        assert confirmed.width_mm == Decimal("8.0")
        assert confirmed.metadata["review_notes"] == "measured on CMM"
        assert confirmed.confidence == FeatureRecognitionConfidence.USER_CONFIRMED

    def test_existing_metadata_preserved_alongside_notes(self):
        import dataclasses
        from types import MappingProxyType
        feat = _make_feature()
        feat_with_meta = dataclasses.replace(feat, metadata=MappingProxyType({"existing_key": "existing_value"}))
        confirmed = feat_with_meta.confirm_with_dimensions("eng1", review_notes="new note")
        assert confirmed.metadata["existing_key"] == "existing_value"
        assert confirmed.metadata["review_notes"] == "new note"

    def test_as_dict_contains_depth_after_confirmation(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1", depth_mm=Decimal("15.0"))
        d = confirmed.as_dict()
        assert d["depth_mm"] == pytest.approx(15.0)
        assert d["confidence"] == "USER_CONFIRMED"

    def test_confidence_score_is_1_after_user_confirmed(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1")
        assert confirmed.confidence_score == pytest.approx(1.0)

    def test_requires_review_false_after_user_confirmed(self):
        feat = _make_feature()
        confirmed = feat.confirm_with_dimensions("eng1")
        assert confirmed.requires_review is False


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from backend.api.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    import os
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "testuser")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "testpass")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-key-p3")
    resp = client.post("/api/login", json={"username": "testuser", "password": "testpass"})
    if resp.status_code != 200:
        pytest.skip("Auth not configured for test environment")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _create_dxf_session(client, auth_headers) -> str:
    """Create a CAD session with a minimal DXF circle."""
    import base64
    dxf = (
        "0\nSECTION\n2\nENTITIES\n"
        "0\nCIRCLE\n8\n0\n10\n50.0\n20\n50.0\n40\n12.5\n"
        "0\nENDSEC\n0\nEOF\n"
    )
    b64 = base64.b64encode(dxf.encode()).decode()
    resp = client.post(
        "/api/cad-features/analyze",
        json={"file_name": "test_p3.dxf", "content_b64": b64},
        headers=auth_headers,
    )
    assert resp.status_code == 200, f"Session creation failed: {resp.text}"
    return resp.json()["session_id"]


class TestConfirmWithDimensionEndpoint:

    def test_endpoint_returns_200(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized from minimal DXF")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"depth_mm": 20.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_endpoint_status_confirmed_with_dimension(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"depth_mm": 15.0, "review_notes": "checked"},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["status"] == "CONFIRMED_WITH_DIMENSION"
        assert data["dimension_provenance"] == "USER_CONFIRMED"

    def test_endpoint_depth_reflected_in_response(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"depth_mm": 30.5},
            headers=auth_headers,
        )
        data = resp.json()
        assert data["depth_mm"] == pytest.approx(30.5)
        assert data["depth_supplied"] is True

    def test_negative_depth_rejected_422(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"depth_mm": -5.0},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_zero_depth_rejected_422(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"depth_mm": 0.0},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_invalid_feature_type_rejected_422(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"feature_type_override": "NOT_A_REAL_TYPE"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_unknown_feature_id_returns_404(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        resp = client.post(
            f"/api/cad-features/{sid}/features/nonexistent-id/confirm-with-dimension",
            json={"depth_mm": 10.0},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_unknown_session_returns_404(self, client, auth_headers):
        resp = client.post(
            "/api/cad-features/nonexistent-session/features/feat-001/confirm-with-dimension",
            json={"depth_mm": 10.0},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    def test_type_override_in_response(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        fid = feats["features"][0]["feature_id"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"feature_type_override": "BLIND_HOLE", "depth_mm": 25.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature_type"] == "BLIND_HOLE"
        assert data["type_changed"] is True

    def test_no_type_override_type_unchanged(self, client, auth_headers):
        sid = _create_dxf_session(client, auth_headers)
        feats = client.get(f"/api/cad-features/{sid}/features", headers=auth_headers).json()
        if feats["total"] == 0:
            pytest.skip("No features recognized")
        feat = feats["features"][0]
        fid = feat["feature_id"]
        original_type = feat["feature_type"]
        resp = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"depth_mm": 10.0},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature_type"] == original_type
        assert data["type_changed"] is False
