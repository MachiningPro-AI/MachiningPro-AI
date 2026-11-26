"""API-layer tests for Auto CAM endpoint.

MACHININGPRO_AI_AUTO_CAM_END_TO_END_01

Uses TestClient (sync httpx) with real auth login flow.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "admin")
os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "machiningpro")
os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "autocam-api-test-secret-32chars!!")


@pytest.fixture(scope="session")
def client():
    from backend.api.app import app
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def token(client):
    resp = client.post("/api/login", json={"username": "admin", "password": "machiningpro"})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="session")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


def _body(features=None, stock=None):
    return {
        "file_ref": "api_test.stp",
        "features": features if features is not None else [
            {
                "feature_id": "F1",
                "feature_type": "HOLE",
                "center_x": 10.0,
                "center_y": 20.0,
                "center_z_top": 30.0,
                "depth_mm": 15.0,
                "diameter_mm": 8.0,
            }
        ],
        "stock_bbox": stock or {
            "min_x": 0, "min_y": 0, "min_z": 0,
            "max_x": 100, "max_y": 100, "max_z": 30,
        },
        "material_grade": "42CrMo4",
        "is_dispatchable": False,
        "production_released": False,
    }


def test_run_requires_auth(client):
    resp = client.post("/api/autocam/run", json=_body())
    assert resp.status_code == 401


def test_run_returns_plan(client, auth):
    resp = client.post("/api/autocam/run", json=_body(), headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert "plan_id" in data
    assert len(data["plan_id"]) == 16


def test_run_safety_invariants(client, auth):
    resp = client.post("/api/autocam/run", json=_body(), headers=auth)
    assert resp.status_code == 200
    safety = resp.json()["safety"]
    assert safety["AUTO_CAM_CAN_DISPATCH_CNC"] is False
    assert safety["AUTO_CAM_CAN_RELEASE_PRODUCTION"] is False
    assert safety["AUTO_CAM_CAN_AUTO_APPROVE"] is False
    assert safety["REAL_MACHINE_WRITE_FOUND"] is False
    assert safety["DISPATCH_GATE"] == "ALWAYS_BLOCKED"


def test_run_20_stages(client, auth):
    resp = client.post("/api/autocam/run", json=_body(), headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()["stages"]) == 20


def test_get_plan(client, auth):
    create_resp = client.post("/api/autocam/run", json=_body(), headers=auth)
    assert create_resp.status_code == 200
    plan_id = create_resp.json()["plan_id"]
    get_resp = client.get(f"/api/autocam/{plan_id}", headers=auth)
    assert get_resp.status_code == 200
    assert get_resp.json()["plan_id"] == plan_id


def test_get_plan_not_found(client, auth):
    resp = client.get("/api/autocam/nonexistent_plan_id_x", headers=auth)
    assert resp.status_code == 404


def test_run_blocked_no_features(client, auth):
    body = _body(features=[])
    resp = client.post("/api/autocam/run", json=body, headers=auth)
    assert resp.status_code == 200
    assert resp.json()["plan_status"] == "BLOCKED"


def test_run_safety_violation_rejected(client, auth):
    body = _body()
    body["is_dispatchable"] = True  # Safety violation
    resp = client.post("/api/autocam/run", json=body, headers=auth)
    assert resp.status_code == 400
    assert resp.json()["detail"]["error_code"] == "SAFETY_INVARIANT_VIOLATION"


def test_run_multiple_features(client, auth):
    body = _body(features=[
        {"feature_id": "F1", "feature_type": "HOLE", "center_x": 10, "center_y": 10,
         "center_z_top": 30, "depth_mm": 10, "diameter_mm": 6},
        {"feature_id": "F2", "feature_type": "POCKET", "center_x": 50, "center_y": 50,
         "center_z_top": 30, "depth_mm": 8, "width_mm": 20, "length_mm": 30},
        {"feature_id": "F3", "feature_type": "SLOT", "center_x": 25, "center_y": 25,
         "center_z_top": 30, "depth_mm": 5, "width_mm": 8, "length_mm": 40},
    ])
    resp = client.post("/api/autocam/run", json=body, headers=auth)
    assert resp.status_code == 200
    assert len(resp.json()["operations"]) == 3


def test_s19_always_blocked_in_api(client, auth):
    resp = client.post("/api/autocam/run", json=_body(), headers=auth)
    assert resp.status_code == 200
    stages = resp.json()["stages"]
    s19 = next(s for s in stages if s["stage"] == "S19_DISPATCH_SAFETY_GATE")
    assert s19["status"] == "BLOCKED"
