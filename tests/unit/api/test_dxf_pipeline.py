"""End-to-end pipeline integration test: DXF → drawing parser → CAD features.

MUST 12 — End-to-End Pipeline Test.

FABRICATED_FEATURE=NO
FABRICATED_MATERIAL=NO
FABRICATED_TOLERANCE=NO
FABRICATED_RA=NO
FABRICATED_IT_GRADE=NO
"""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Auth fixture
# ---------------------------------------------------------------------------

@pytest.fixture()
def auth_headers() -> dict[str, str]:
    import os
    username = os.getenv("MACHININGPRO_DEV_USERNAME", "demo")
    password = os.getenv("MACHININGPRO_DEV_PASSWORD", "demo")
    r = client.post("/api/login", json={"username": username, "password": password})
    if r.status_code != 200:
        pytest.skip("Auth not configured — skipping API tests")
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# DXF fixture builder
# ---------------------------------------------------------------------------

def _dxf_with_circle(radius_mm: float, insunits: int = 4) -> bytes:
    """Minimal DXF with one CIRCLE entity and $INSUNITS."""
    lines = [
        "  0", "SECTION", "  2", "HEADER",
        "  9", "$ACADVER", "  1", "AC1009",
        "  9", "$INSUNITS", " 70", f"     {insunits}",
        "  0", "ENDSEC",
        "  0", "SECTION", "  2", "ENTITIES",
        "  0", "CIRCLE",
        "  8", "0",
        " 10", "50.0",
        " 20", "50.0",
        " 40", str(radius_mm),
        "  0", "ENDSEC",
        "  0", "EOF",
    ]
    return "\n".join(lines).encode("utf-8")


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode()


# ---------------------------------------------------------------------------
# Drawing parser pipeline
# ---------------------------------------------------------------------------

class TestDxfDrawingParserPipeline:
    def test_mm_dxf_unit_declared(self, auth_headers):
        content = _dxf_with_circle(6.0, insunits=4)
        r = client.post("/api/drawing-parser/analyze", json={
            "source_id": "pipe-mm",
            "file_name": "part.dxf",
            "content_b64": _b64(content),
        }, headers=auth_headers)
        assert r.status_code == 200
        resp = r.json()
        assert resp["detected_unit"] == "mm"

    def test_unitless_dxf_stays_unknown(self, auth_headers):
        content = _dxf_with_circle(6.0, insunits=0)
        r = client.post("/api/drawing-parser/analyze", json={
            "source_id": "pipe-unitless",
            "file_name": "part.dxf",
            "content_b64": _b64(content),
        }, headers=auth_headers)
        assert r.status_code == 200
        resp = r.json()
        assert resp["detected_unit"] is None

    def test_no_fabricated_annotations(self, auth_headers):
        """DXF with only a circle (no TEXT) must have 0 detections."""
        content = _dxf_with_circle(6.0, insunits=4)
        r = client.post("/api/drawing-parser/analyze", json={
            "source_id": "pipe-no-fab",
            "file_name": "part.dxf",
            "content_b64": _b64(content),
            "notes": [],
        }, headers=auth_headers)
        assert r.status_code == 200
        resp = r.json()
        assert resp["detection_count"] == 0, (
            f"Empty DXF (no TEXT/MTEXT) must have 0 detections, got {resp['detection_count']}"
        )


# ---------------------------------------------------------------------------
# CAD feature pipeline
# ---------------------------------------------------------------------------

class TestCadFeaturePipeline:
    def test_dxf_circle_recognized(self, auth_headers):
        """A DXF with a known circle should produce a hole candidate."""
        content = _dxf_with_circle(6.0, insunits=4)
        r = client.post("/api/cad-features/analyze", json={
            "file_name": "part.dxf",
            "content_b64": _b64(content),
        }, headers=auth_headers)
        assert r.status_code == 200
        resp = r.json()
        assert resp["session_id"]
        assert resp["feature_count"] >= 1, (
            f"Expected at least 1 recognized feature, got {resp['feature_count']}"
        )

    def test_dxf_circle_diameter_from_geometry(self, auth_headers):
        """Geometric diameter must come from the DXF entity, not be fabricated."""
        radius = 7.5  # diameter = 15.0
        content = _dxf_with_circle(radius, insunits=4)
        r = client.post("/api/cad-features/analyze", json={
            "file_name": "part.dxf",
            "content_b64": _b64(content),
        }, headers=auth_headers)
        assert r.status_code == 200
        session_id = r.json()["session_id"]

        r2 = client.get(f"/api/cad-features/{session_id}/features", headers=auth_headers)
        assert r2.status_code == 200
        features = r2.json()["features"]
        assert len(features) >= 1
        hole = features[0]
        assert hole["diameter_mm"] is not None, "diameter_mm must not be None for a recognized circle"
        assert abs(hole["diameter_mm"] - 15.0) < 1.0, (
            f"Expected diameter ~15.0 mm, got {hole['diameter_mm']} — must come from geometry"
        )

    def test_no_fabricated_material(self, auth_headers):
        """CAD feature recognition must not fabricate material group."""
        content = _dxf_with_circle(6.0, insunits=4)
        r = client.post("/api/cad-features/analyze", json={
            "file_name": "part.dxf",
            "content_b64": _b64(content),
        }, headers=auth_headers)
        assert r.status_code == 200
        session_id = r.json()["session_id"]
        r2 = client.get(f"/api/cad-features/{session_id}/features", headers=auth_headers)
        assert r2.status_code == 200
        for feat in r2.json()["features"]:
            assert "iso_material_group" not in feat or feat["iso_material_group"] is None

    def test_response_contract(self, auth_headers):
        """Verify analyze_cad returns all required contract fields."""
        content = _dxf_with_circle(6.0)
        r = client.post("/api/cad-features/analyze", json={
            "file_name": "part.dxf",
            "content_b64": _b64(content),
            "source_id": "contract-test",
        }, headers=auth_headers)
        assert r.status_code == 200
        resp = r.json()
        required = {"session_id", "source_id", "status", "face_count", "body_count",
                    "feature_count", "pattern_count", "warnings"}
        missing = required - set(resp.keys())
        assert not missing, f"Response missing fields: {missing}"
        assert resp["source_id"] == "contract-test"
        assert resp["status"] == "ANALYZED"
        assert isinstance(resp["body_count"], int)

    def test_no_fabricated_tolerance(self, auth_headers):
        """Feature must not have fabricated IT grade or Ra."""
        content = _dxf_with_circle(6.0)
        r = client.post("/api/cad-features/analyze", json={
            "file_name": "part.dxf",
            "content_b64": _b64(content),
        }, headers=auth_headers)
        assert r.status_code == 200
        session_id = r.json()["session_id"]
        r2 = client.get(f"/api/cad-features/{session_id}/features", headers=auth_headers)
        assert r2.status_code == 200
        for feat in r2.json()["features"]:
            assert "required_it_grade" not in feat, "IT grade must not be in CAD features"
            assert "required_ra_um" not in feat, "Ra must not be in CAD features"
