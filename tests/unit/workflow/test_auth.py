"""Auth guard tests: all workflow and upload endpoints must reject unauthenticated requests."""
import io
import os

os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "dev")
os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "dev")

import pytest
from fastapi.testclient import TestClient

VALID_DXF = b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n"


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


class TestWorkflowAuthGuard:
    """Every workflow endpoint returns 401 without a valid Bearer token."""

    def test_create_no_auth(self, client):
        resp = client.post("/api/workflow", json={"part_reference": "X", "quantity": 1})
        assert resp.status_code == 401

    def test_get_no_auth(self, client):
        resp = client.get("/api/workflow/fake-id")
        assert resp.status_code == 401

    def test_run_no_auth(self, client):
        resp = client.post("/api/workflow/fake-id/run")
        assert resp.status_code == 401

    def test_resume_no_auth(self, client):
        resp = client.post("/api/workflow/fake-id/resume")
        assert resp.status_code == 401

    def test_retry_no_auth(self, client):
        resp = client.post("/api/workflow/fake-id/retry", json={"stage": "01_CAD_IMPORT"})
        assert resp.status_code == 401

    def test_cancel_no_auth(self, client):
        resp = client.post("/api/workflow/fake-id/cancel")
        assert resp.status_code == 401

    def test_stages_no_auth(self, client):
        resp = client.get("/api/workflow/fake-id/stages")
        assert resp.status_code == 401

    def test_plan_no_auth(self, client):
        resp = client.get("/api/workflow/fake-id/plan")
        assert resp.status_code == 401

    def test_cad_upload_no_auth(self, client):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
        )
        assert resp.status_code == 401


class TestWorkflowBadToken:
    """Invalid tokens also return 401."""

    def test_bad_token_create(self, client):
        resp = client.post(
            "/api/workflow",
            json={"part_reference": "X", "quantity": 1},
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401

    def test_wrong_scheme(self, client):
        resp = client.post(
            "/api/workflow",
            json={"part_reference": "X", "quantity": 1},
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401

    def test_empty_bearer(self, client):
        resp = client.post(
            "/api/workflow",
            json={"part_reference": "X", "quantity": 1},
            headers={"Authorization": "Bearer "},
        )
        assert resp.status_code == 401


class TestWorkflowValidToken:
    """Valid tokens allow access."""

    def test_create_with_valid_token(self, client, auth_headers):
        resp = client.post(
            "/api/workflow",
            json={"part_reference": "AUTH_OK", "quantity": 1},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    def test_cad_upload_with_valid_token(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
