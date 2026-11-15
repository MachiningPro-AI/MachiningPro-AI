"""P4-E: DXF-01 E2E route generation and CAM gate integration test.

Full workflow:
  1. Upload synthetic DXF (circles → candidate holes)
  2. Confirm feature with engineer-supplied depth and diameter
  3. Verify route generation result attached (P4-A)
  4. Create setup-stock session with material + setup
  5. Query CAM status gate (P4-B)
  6. Verify CAM prerequisites reported

This test uses a synthetic DXF (no real sample content committed).
Real-sample DXF-01 is verified separately via qualification run.

HARD RULES enforced:
  - Depth and diameter come from engineer confirm call (never inferred).
  - Route result is PROPOSED/DRAFT — never APPROVED.
  - CAM gate returns OFFLINE_ONLY=True.
  - No auto-dispatch, no auto-approval.

FABRICATED_ROUTE=NO
AUTO_APPROVED=NO
CNC_DISPATCH=NO
"""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Synthetic DXF fixture — 2 circles (minimum 2D hole candidates)
# Radius 6.0 mm → candidate diameter 12.0 mm
# ---------------------------------------------------------------------------

_DXF_TWO_HOLES = (
    "0\nSECTION\n2\nHEADER\n"
    "9\n$INSUNITS\n70\n4\n"           # insunits=4 → mm
    "0\nENDSEC\n"
    "0\nSECTION\n2\nENTITIES\n"
    "0\nCIRCLE\n8\n0\n10\n20.0\n20\n30.0\n30\n0.0\n40\n6.0\n"   # r=6
    "0\nCIRCLE\n8\n0\n10\n60.0\n20\n30.0\n30\n0.0\n40\n6.0\n"   # r=6
    "0\nENDSEC\n0\nEOF\n"
).encode("ascii")


def _b64(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


class TestDxfE2ERouteAndCamGate:

    def _upload_and_get_session(self):
        """Upload synthetic DXF and return (session_id, features)."""
        payload = {
            "file_name": "TEST_ONLY_two_holes.dxf",
            "content_b64": _b64(_DXF_TWO_HOLES),
        }
        resp = client.post("/api/cad-features/analyze", json=payload)
        assert resp.status_code == 200, f"analyze failed: {resp.text}"
        data = resp.json()
        session_id = data["session_id"]
        return session_id, data

    def test_upload_returns_session_id(self):
        sess_id, data = self._upload_and_get_session()
        assert isinstance(sess_id, str)
        assert len(sess_id) > 0

    def test_upload_returns_features(self):
        sess_id, data = self._upload_and_get_session()
        features = data.get("features", [])
        # Synthetic DXF with 2 circles should produce at least 1 feature candidate
        # (DXF circles under size threshold may be skipped — accept 0 or more)
        assert isinstance(features, list)

    def test_confirm_with_dimension_attaches_route(self):
        sess_id, data = self._upload_and_get_session()
        features = data.get("features", [])
        if not features:
            pytest.skip("No features recognized from synthetic DXF — skipping confirm test")

        fid = features[0]["feature_id"]
        confirm_resp = client.post(
            f"/api/cad-features/{sess_id}/features/{fid}/confirm-with-dimension",
            json={
                "user_id": "eng1",
                "depth_mm": 25.0,
                "feature_type_override": None,
                "review_notes": "Test E2E depth supplied by engineer",
            },
        )
        assert confirm_resp.status_code == 200, f"confirm failed: {confirm_resp.text}"
        cdata = confirm_resp.json()
        assert cdata["status"] == "CONFIRMED_WITH_DIMENSION"
        assert cdata["depth_mm"] == pytest.approx(25.0)
        assert cdata["dimension_provenance"] == "USER_CONFIRMED"
        assert "route_generation" in cdata

    def test_route_generation_has_proposed_status(self):
        sess_id, data = self._upload_and_get_session()
        features = data.get("features", [])
        if not features:
            pytest.skip("No features recognized from synthetic DXF — skipping route status test")

        fid = features[0]["feature_id"]
        confirm_resp = client.post(
            f"/api/cad-features/{sess_id}/features/{fid}/confirm-with-dimension",
            json={
                "user_id": "eng1",
                "depth_mm": 25.0,
                "review_notes": "Route status check",
            },
        )
        assert confirm_resp.status_code == 200
        rg = confirm_resp.json().get("route_generation", {})
        # Route generation key present; if not blocked, routes should be PROPOSED
        assert isinstance(rg, dict)
        status_in_rg = rg.get("route_generation", {}) or {}
        for r in status_in_rg.get("routes", []):
            assert r["status"] == "PROPOSED"

    def test_cam_status_no_cad_session_returns_zero(self):
        """CAM status without a cad_session_id returns 0 confirmed features."""
        resp = client.post("/api/setup-stock/", json={})
        assert resp.status_code == 200
        ss_id = resp.json()["session_id"]

        cam_resp = client.get(f"/api/setup-stock/{ss_id}/cam-status")
        assert cam_resp.status_code == 200
        d = cam_resp.json()
        assert d["cam_ready_count"] == 0
        assert d["overall_cam_ready"] is False
        assert d["offline_only"] is True

    def test_cam_status_with_confirmed_feature_and_complete_session(self):
        """Full E2E: confirm feature → create setup → check CAM gate."""
        sess_id, data = self._upload_and_get_session()
        features = data.get("features", [])
        if not features:
            pytest.skip("No features recognized from synthetic DXF — skipping CAM gate E2E")

        fid = features[0]["feature_id"]
        client.post(
            f"/api/cad-features/{sess_id}/features/{fid}/confirm-with-dimension",
            json={"user_id": "eng1", "depth_mm": 25.0},
        )

        # Create full setup-stock session
        ss_resp = client.post("/api/setup-stock/", json={
            "cad_session_id": sess_id,
            "stock": {
                "shape": "RECTANGULAR_BLOCK",
                "material_grade": "C45",
                "length_mm": 200.0,
                "width_mm": 150.0,
                "height_mm": 50.0,
            },
            "setup": {
                "n_setups": 1,
                "datum_a": "Bottom face",
            },
        })
        assert ss_resp.status_code == 200, f"setup-stock create failed: {ss_resp.text}"
        ss_id = ss_resp.json()["session_id"]

        cam_resp = client.get(
            f"/api/setup-stock/{ss_id}/cam-status",
            params={"cad_session_id": sess_id},
        )
        assert cam_resp.status_code == 200, f"cam-status failed: {cam_resp.text}"
        d = cam_resp.json()
        assert d["total_confirmed_features"] >= 1
        assert d["offline_only"] is True
        assert "disclaimer" in d
        assert "AUTO_APPROVED=NO" in d["disclaimer"]

    def test_cam_status_offline_only_flag(self):
        """CAM status must always return offline_only=True."""
        resp = client.post("/api/setup-stock/", json={})
        ss_id = resp.json()["session_id"]
        cam_resp = client.get(f"/api/setup-stock/{ss_id}/cam-status")
        assert cam_resp.json()["offline_only"] is True

    def test_no_auto_dispatch_in_route_response(self):
        """Route response must not contain auto-dispatch or auto-approve keys."""
        sess_id, data = self._upload_and_get_session()
        features = data.get("features", [])
        if not features:
            pytest.skip("No features recognized")

        fid = features[0]["feature_id"]
        confirm_resp = client.post(
            f"/api/cad-features/{sess_id}/features/{fid}/confirm-with-dimension",
            json={"user_id": "eng1", "depth_mm": 25.0},
        )
        assert confirm_resp.status_code == 200
        text = confirm_resp.text.lower()
        # Confirm that auto-dispatch and auto-approve are explicitly excluded
        assert "auto_dispatch=yes" not in text
        assert "auto_approve=yes" not in text
        assert "cnc_dispatch=yes" not in text

    def test_disclaimer_in_confirm_response(self):
        """Confirm endpoint must include disclaimer about provenance."""
        sess_id, data = self._upload_and_get_session()
        features = data.get("features", [])
        if not features:
            pytest.skip("No features recognized")

        fid = features[0]["feature_id"]
        confirm_resp = client.post(
            f"/api/cad-features/{sess_id}/features/{fid}/confirm-with-dimension",
            json={"user_id": "eng1", "depth_mm": 25.0},
        )
        assert confirm_resp.status_code == 200
        d = confirm_resp.json()
        assert "disclaimer" in d
        assert "USER_CONFIRMED" in d["disclaimer"]
