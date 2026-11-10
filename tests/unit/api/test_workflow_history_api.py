"""Tests for GET /api/workflow/history — MUST 15.

Covers: empty history, multiple workflows, sort order, field content,
authentication gate, unknown workflow reload, objective/stage fields.
"""
import os

os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "dev")
os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "dev")

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.api.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/login", json={"username": "dev", "password": "dev"})
    if resp.status_code != 200:
        pytest.skip(f"Login failed: {resp.status_code}")
    token = resp.json().get("token", "")
    return {"Authorization": f"Bearer {token}"}


def _create_wf(client, auth_headers, part: str = "HIST-PART"):
    resp = client.post(
        "/api/workflow",
        json={
            "part_reference": part,
            "revision": "REV-A",
            "source_file_ref": None,
            "requested_mode": "ANALYSIS_ONLY",
            "objective": "BALANCED",
            "material_ref": None,
            "quantity": 1,
            "stock_ref": None,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    return resp.json()["workflow_id"]


class TestHistoryAuthGate:
    def test_history_requires_auth(self, client):
        resp = client.get("/api/workflow/history")
        assert resp.status_code == 401

    def test_history_rejects_bad_token(self, client):
        resp = client.get(
            "/api/workflow/history",
            headers={"Authorization": "Bearer invalid-token"},
        )
        assert resp.status_code == 401


class TestHistoryEmptyAndContent:
    def test_history_returns_list(self, client, auth_headers):
        resp = client.get("/api/workflow/history", headers=auth_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_history_fields_present(self, client, auth_headers):
        _create_wf(client, auth_headers, "FIELD-CHECK")
        resp = client.get("/api/workflow/history", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()
        assert len(items) >= 1
        item = items[0]
        for field in ("workflow_id", "part_reference", "status", "created_at", "updated_at"):
            assert field in item, f"Missing field: {field}"

    def test_history_objective_field_present(self, client, auth_headers):
        _create_wf(client, auth_headers, "OBJ-CHECK")
        resp = client.get("/api/workflow/history", headers=auth_headers)
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "objective" in item

    def test_history_current_stage_field_present(self, client, auth_headers):
        _create_wf(client, auth_headers, "STAGE-CHECK")
        resp = client.get("/api/workflow/history", headers=auth_headers)
        assert resp.status_code == 200
        item = resp.json()[0]
        assert "current_stage" in item

    def test_history_no_server_path_in_response(self, client, auth_headers):
        _create_wf(client, auth_headers, "PATH-CHECK")
        resp = client.get("/api/workflow/history", headers=auth_headers)
        payload = resp.text
        assert "C:\\" not in payload
        assert "/home/" not in payload
        assert "data/workflows.db" not in payload


class TestHistorySortAndLimit:
    def test_history_newest_first(self, client, auth_headers):
        id1 = _create_wf(client, auth_headers, "SORT-A")
        id2 = _create_wf(client, auth_headers, "SORT-B")
        resp = client.get("/api/workflow/history?limit=10", headers=auth_headers)
        assert resp.status_code == 200
        ids = [i["workflow_id"] for i in resp.json()]
        assert ids.index(id2) < ids.index(id1)

    def test_history_limit_respected(self, client, auth_headers):
        for i in range(5):
            _create_wf(client, auth_headers, f"LIM-{i}")
        resp = client.get("/api/workflow/history?limit=3", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) <= 3

    def test_history_multiple_workflows_all_present(self, client, auth_headers):
        ids = set()
        for i in range(3):
            ids.add(_create_wf(client, auth_headers, f"MULTI-{i}"))
        resp = client.get("/api/workflow/history?limit=100", headers=auth_headers)
        returned = {i["workflow_id"] for i in resp.json()}
        for wf_id in ids:
            assert wf_id in returned


class TestHistoryReloadRecovery:
    def test_workflow_retrievable_by_id(self, client, auth_headers):
        wf_id = _create_wf(client, auth_headers, "RELOAD-PART")
        resp = client.get(f"/api/workflow/{wf_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["workflow_id"] == wf_id
        assert data["part_reference"] == "RELOAD-PART"

    def test_unknown_workflow_404(self, client, auth_headers):
        resp = client.get("/api/workflow/WF_nonexistent_xyz", headers=auth_headers)
        assert resp.status_code == 404

    def test_history_item_matches_full_workflow(self, client, auth_headers):
        wf_id = _create_wf(client, auth_headers, "MATCH-PART")
        history_resp = client.get("/api/workflow/history?limit=50", headers=auth_headers)
        history_item = next(
            (i for i in history_resp.json() if i["workflow_id"] == wf_id), None
        )
        assert history_item is not None
        full_resp = client.get(f"/api/workflow/{wf_id}", headers=auth_headers)
        full = full_resp.json()
        assert history_item["workflow_id"] == full["workflow_id"]
        assert history_item["part_reference"] == full["part_reference"]
        assert history_item["status"] == full["status"]
