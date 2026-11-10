"""Tests for /api/workflow/{id}/export/{format} endpoints — MUST 16.

Covers: authenticated export, unauthenticated rejection, missing workflow,
format validation, safe filenames, no path leakage, NC offline-candidate labels.
"""
import json
import os

os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "dev")
os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "dev")

import pytest
from fastapi.testclient import TestClient

ALL_FORMATS = ["plan.json", "plan.html", "stages.csv", "dfm.json", "nc-manifest.json"]


@pytest.fixture
def client():
    from backend.api.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/login", json={"username": "dev", "password": "dev"})
    if resp.status_code != 200:
        pytest.skip(f"Login failed: {resp.status_code}")
    return {"Authorization": f"Bearer {resp.json().get('token', '')}"}


@pytest.fixture
def workflow_id(client, auth_headers):
    resp = client.post(
        "/api/workflow",
        json={
            "part_reference": "EXPORT-TEST",
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


class TestExportAuthGate:
    @pytest.mark.parametrize("fmt", ALL_FORMATS)
    def test_unauthenticated_export_rejected(self, client, workflow_id, fmt):
        resp = client.get(f"/api/workflow/{workflow_id}/export/{fmt}")
        assert resp.status_code == 401

    @pytest.mark.parametrize("fmt", ALL_FORMATS)
    def test_bad_token_export_rejected(self, client, workflow_id, fmt):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/{fmt}",
            headers={"Authorization": "Bearer bad-token"},
        )
        assert resp.status_code == 401


class TestExportMissingWorkflow:
    @pytest.mark.parametrize("fmt", ALL_FORMATS)
    def test_missing_workflow_404(self, client, auth_headers, fmt):
        resp = client.get(
            f"/api/workflow/WF_nonexistent_xyz_abc/export/{fmt}",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestExportUnsupportedFormat:
    def test_unsupported_format_404(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/unsupported.format",
            headers=auth_headers,
        )
        assert resp.status_code == 404


class TestExportPlanJson:
    def test_returns_200(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.json",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_content_type_json(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.json",
            headers=auth_headers,
        )
        assert "application/json" in resp.headers["content-type"]

    def test_content_disposition_attachment(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.json",
            headers=auth_headers,
        )
        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd

    def test_safe_filename_no_path_chars(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.json",
            headers=auth_headers,
        )
        cd = resp.headers.get("content-disposition", "")
        assert "/" not in cd
        assert "\\" not in cd
        assert ".." not in cd

    def test_no_server_path_in_response(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.json",
            headers=auth_headers,
        )
        body = resp.text
        assert "C:\\" not in body
        assert "/home/" not in body
        assert "/data/" not in body or "MACHININGPRO" not in body


class TestExportPlanHtml:
    def test_returns_200(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.html",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_content_type_html(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.html",
            headers=auth_headers,
        )
        assert "text/html" in resp.headers["content-type"]

    def test_html_safety_warning(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.html",
            headers=auth_headers,
        )
        assert "PRODUCTION_APPROVED" in resp.text
        assert "Engineering Review Required" in resp.text

    def test_no_server_path_in_html(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/plan.html",
            headers=auth_headers,
        )
        assert "C:\\" not in resp.text
        assert "/home/" not in resp.text


class TestExportStagesCsv:
    def test_returns_200(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/stages.csv",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_content_type_csv(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/stages.csv",
            headers=auth_headers,
        )
        assert "text/csv" in resp.headers["content-type"]

    def test_csv_has_stage_header(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/stages.csv",
            headers=auth_headers,
        )
        assert "stage" in resp.text
        assert "status" in resp.text


class TestExportDfmJson:
    def test_returns_200(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/dfm.json",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_dfm_format_identifier(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/dfm.json",
            headers=auth_headers,
        )
        data = json.loads(resp.content)
        assert data["export_format"] == "MachiningPro-DFM-JSON"


class TestExportNcManifest:
    def test_returns_200(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/nc-manifest.json",
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_nc_offline_candidate_label(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/nc-manifest.json",
            headers=auth_headers,
        )
        data = json.loads(resp.content)
        assert data["safety"]["OFFLINE_CANDIDATE"] is True
        assert data["safety"]["NOT_MACHINE_APPROVED"] is True
        assert data["safety"]["NOT_DISPATCHED"] is True
        assert data["safety"]["NO_CNC_TRANSFER"] is True

    def test_nc_format_identifier(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/nc-manifest.json",
            headers=auth_headers,
        )
        data = json.loads(resp.content)
        assert data["export_format"] == "MachiningPro-NC-Manifest-JSON"

    def test_nc_no_send_to_cnc_in_response(self, client, auth_headers, workflow_id):
        resp = client.get(
            f"/api/workflow/{workflow_id}/export/nc-manifest.json",
            headers=auth_headers,
        )
        body = resp.text.lower()
        assert "send to cnc" not in body
        assert "dispatch_approved" not in body
