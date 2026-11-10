"""Tests for the CAD file upload endpoint."""
import io
import os

os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "dev")
os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "dev")

import pytest
from fastapi.testclient import TestClient

VALID_DXF = b"0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1015\n"
VALID_IGES = b" " * 72 + b"S" + b"S      1\n" + b" " * 10
VALID_STEP = b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('test'),'2;1');\nENDATA;"


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


class TestCadUploadAuth:
    def test_upload_requires_auth(self, client):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
        )
        assert resp.status_code == 401

    def test_upload_with_valid_auth(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["upload_status"] == "ACCEPTED"
        assert "file_ref" in data
        assert "file_id" in data


class TestCadUploadExtensions:
    def test_reject_txt_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("notes.txt", io.BytesIO(b"hello"), "text/plain")},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_reject_pdf_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("drawing.pdf", io.BytesIO(b"%PDF-1.4"), "application/pdf")},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_reject_exe_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("payload.exe", io.BytesIO(b"MZ\x90\x00"), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_accept_dxf_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_accept_stp_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.stp", io.BytesIO(VALID_STEP), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_accept_step_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.step", io.BytesIO(VALID_STEP), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200

    def test_accept_iges_extension(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.iges", io.BytesIO(VALID_IGES), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200


class TestCadUploadPathTraversal:
    def test_reject_dotdot_in_filename(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("../evil.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_reject_dotdot_backslash(self, client, auth_headers):
        """Windows-style ..\\traversal pattern is rejected (dotdot triggers check)."""
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("..\\evil.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestCadUploadFormatValidation:
    def test_dxf_wrong_content_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": (
                "part.dxf", io.BytesIO(b"This is not a DXF file"), "application/octet-stream"
            )},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_step_wrong_content_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": (
                "part.step", io.BytesIO(b"Not a STEP file at all"), "application/octet-stream"
            )},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    def test_empty_file_rejected(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(b""), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestCadUploadResponse:
    def test_response_no_absolute_path(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("mypart.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not data["file_ref"].startswith("/")
        assert "\\" not in data["file_ref"]
        assert ":" not in data["file_ref"]

    def test_response_fields_present(self, client, auth_headers):
        resp = client.post(
            "/api/cad-upload",
            files={"file": ("part.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        for field in ("file_id", "original_filename", "safe_name", "size_bytes", "format",
                       "upload_status", "file_ref"):
            assert field in data
        assert data["upload_status"] == "ACCEPTED"

    def test_content_addressed_same_content_same_ref(self, client, auth_headers):
        """Level-20: content-addressed storage — same content produces same artifact_id (dedup)."""
        def upload():
            return client.post(
                "/api/cad-upload",
                files={"file": ("same.dxf", io.BytesIO(VALID_DXF), "application/octet-stream")},
                headers=auth_headers,
            )
        r1 = upload()
        r2 = upload()
        assert r1.status_code == r2.status_code == 200
        # Same content → same artifact ID (content-addressed deduplication)
        assert r1.json()["file_ref"] == r2.json()["file_ref"]

    def test_different_content_different_ref(self, client, auth_headers):
        """Different file contents produce different artifact IDs."""
        content_a = b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n"
        content_b = b"0\nSECTION\n2\nHEADER\n9\n$EXTRA\n0\nENDSEC\n0\nEOF\n"
        r1 = client.post(
            "/api/cad-upload",
            files={"file": ("a.dxf", io.BytesIO(content_a), "application/octet-stream")},
            headers=auth_headers,
        )
        r2 = client.post(
            "/api/cad-upload",
            files={"file": ("b.dxf", io.BytesIO(content_b), "application/octet-stream")},
            headers=auth_headers,
        )
        assert r1.status_code == r2.status_code == 200
        assert r1.json()["file_ref"] != r2.json()["file_ref"]
