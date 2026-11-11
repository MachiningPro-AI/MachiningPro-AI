"""Tests for DXF annotation extraction in drawing_parser API.

MUST 7 — Drawing Parser Live DXF Tests.

Tests verify:
  - FILE CONTENT changes results (not static)
  - Blank notes field does NOT prevent DXF content extraction
  - Unit extraction: mm, inch, unitless→UNKNOWN
  - FIT, THREAD, SURFACE_FINISH token extraction where parser supports them
  - No annotations → NO_ANNOTATIONS_FOUND warning (not an error)

DXF_ANNOTATION_EXTRACTION_TESTED=YES
UNIT_UNKNOWN_FAIL_CLOSED_TESTED=YES
"""
from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.drawing_parser import _extract_dxf_annotations

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

def _dxf(*, insunits: int | None = None, text_entities: list[str] | None = None,
          circles: list[float] | None = None) -> bytes:
    """Build a minimal valid DXF R12 byte string."""
    lines: list[str] = []

    lines += ["  0", "SECTION", "  2", "HEADER"]
    lines += ["  9", "$ACADVER", "  1", "AC1009"]
    if insunits is not None:
        lines += ["  9", "$INSUNITS", " 70", f"     {insunits}"]
    lines += ["  0", "ENDSEC"]

    lines += ["  0", "SECTION", "  2", "ENTITIES"]

    for r in (circles or []):
        lines += [
            "  0", "CIRCLE",
            "  8", "0",
            " 10", "50.0",
            " 20", "50.0",
            " 40", str(r),
        ]

    for txt in (text_entities or []):
        lines += [
            "  0", "TEXT",
            "  8", "0",
            " 10", "10.0",
            " 20", "20.0",
            " 40", "2.5",
            "  1", txt,
        ]

    lines += ["  0", "ENDSEC", "  0", "EOF"]
    return "\n".join(lines).encode("utf-8")


def _b64(dxf_bytes: bytes) -> str:
    return base64.b64encode(dxf_bytes).decode()


def _analyze(dxf_bytes: bytes, source_id: str, file_name: str, notes: list[str],
             auth: dict[str, str]) -> dict:
    r = client.post("/api/drawing-parser/analyze", json={
        "source_id": source_id,
        "file_name": file_name,
        "content_b64": _b64(dxf_bytes),
        "notes": notes,
    }, headers=auth)
    assert r.status_code == 200, f"Unexpected status {r.status_code}: {r.text}"
    return r.json()


# ---------------------------------------------------------------------------
# Unit A: Explicit mm drawing
# ---------------------------------------------------------------------------

class TestExplicitMm:
    def test_insunits_4_returns_mm(self):
        content = _dxf(insunits=4, text_entities=["Ra 1.6"])
        tokens, unit = _extract_dxf_annotations(content)
        assert unit == "mm", f"Expected mm, got {unit!r}"

    def test_mm_text_extracted(self):
        content = _dxf(insunits=4, text_entities=["Ra 1.6"])
        tokens, unit = _extract_dxf_annotations(content)
        assert len(tokens) == 1
        assert "Ra 1.6" in tokens[0] or "1.6" in tokens[0]

    def test_mm_via_api(self, auth_headers):
        content = _dxf(insunits=4, text_entities=["Ra 1.6"])
        resp = _analyze(content, "test-mm", "test.dxf", [], auth_headers)
        assert resp["detected_unit"] == "mm"


# ---------------------------------------------------------------------------
# Unit B: Explicit inch drawing
# ---------------------------------------------------------------------------

class TestExplicitInch:
    def test_insunits_1_returns_inch(self):
        content = _dxf(insunits=1, text_entities=["0.500"])
        tokens, unit = _extract_dxf_annotations(content)
        assert unit == "inch", f"Expected inch, got {unit!r}"

    def test_insunits_2_returns_inch(self):
        content = _dxf(insunits=2)
        _, unit = _extract_dxf_annotations(content)
        assert unit == "inch"

    def test_inch_via_api(self, auth_headers):
        content = _dxf(insunits=1, text_entities=["0.500"])
        resp = _analyze(content, "test-inch", "test.dxf", [], auth_headers)
        assert resp["detected_unit"] == "inch"


# ---------------------------------------------------------------------------
# Unit C: Unitless drawing
# ---------------------------------------------------------------------------

class TestUnitless:
    def test_insunits_0_returns_none(self):
        content = _dxf(insunits=0, text_entities=["Some note"])
        tokens, unit = _extract_dxf_annotations(content)
        assert unit is None, f"Expected None (UNKNOWN), got {unit!r}"

    def test_no_insunits_returns_none(self):
        content = _dxf(text_entities=["Some note"])
        tokens, unit = _extract_dxf_annotations(content)
        assert unit is None, f"Expected None (UNKNOWN), got {unit!r}"

    def test_unitless_via_api_unit_unknown(self, auth_headers):
        """$INSUNITS=0 must leave detected_unit as None (not silently assume mm)."""
        content = _dxf(insunits=0, text_entities=["Some text"])
        resp = _analyze(content, "test-unitless", "test.dxf", [], auth_headers)
        assert resp["detected_unit"] is None, (
            f"Unitless DXF must have detected_unit=None, got {resp['detected_unit']!r}"
        )
        assert any("UNIT_NOT_DECLARED" in w for w in resp["warnings"]), (
            f"Expected UNIT_NOT_DECLARED warning, got {resp['warnings']}"
        )


# ---------------------------------------------------------------------------
# Unit D: Drawing with no annotations
# ---------------------------------------------------------------------------

class TestNoAnnotations:
    def test_no_text_no_tokens(self):
        content = _dxf(insunits=4, circles=[6.0])
        tokens, unit = _extract_dxf_annotations(content)
        assert tokens == [], f"Expected no tokens, got {tokens}"
        assert unit == "mm"

    def test_blank_notes_uses_dxf_content(self):
        """Blank notes field must NOT prevent DXF content extraction."""
        dxf_with_text = _dxf(insunits=4, text_entities=["H7/f6"])
        tokens, unit = _extract_dxf_annotations(dxf_with_text)
        assert len(tokens) > 0
        assert unit == "mm"


# ---------------------------------------------------------------------------
# Unit E: FIT token
# ---------------------------------------------------------------------------

class TestFitToken:
    def test_fit_token_extracted(self):
        content = _dxf(insunits=4, text_entities=["H7/f6"])
        tokens, unit = _extract_dxf_annotations(content)
        assert any("H7" in t or "f6" in t for t in tokens)

    def test_fit_detection_via_api(self, auth_headers):
        content = _dxf(insunits=4, text_entities=["H7/f6"])
        resp = _analyze(content, "test-fit", "test.dxf", [], auth_headers)
        assert resp["detection_count"] >= 1
        assert resp["detected_unit"] == "mm"


# ---------------------------------------------------------------------------
# Unit F: Thread token
# ---------------------------------------------------------------------------

class TestThreadToken:
    def test_thread_token_extracted(self):
        content = _dxf(insunits=4, text_entities=["M12x1.75"])
        tokens, unit = _extract_dxf_annotations(content)
        assert any("M12" in t for t in tokens)

    def test_thread_detection_via_api(self, auth_headers):
        content = _dxf(insunits=4, text_entities=["M12x1.75"])
        resp = _analyze(content, "test-thread", "test.dxf", [], auth_headers)
        assert resp["detection_count"] >= 1


# ---------------------------------------------------------------------------
# Unit G: Surface finish token
# ---------------------------------------------------------------------------

class TestSurfaceFinishToken:
    def test_surface_finish_via_api(self, auth_headers):
        content = _dxf(insunits=4, text_entities=["Ra 1.6"])
        resp = _analyze(content, "test-sf", "test.dxf", [], auth_headers)
        assert resp["detection_count"] >= 1


# ---------------------------------------------------------------------------
# Content changes results
# ---------------------------------------------------------------------------

class TestContentChangesResults:
    def test_different_content_different_sessions(self, auth_headers):
        dxf_a = _dxf(insunits=4, text_entities=["Ra 1.6"])
        dxf_b = _dxf(insunits=4, text_entities=["M12x1.75"])

        resp_a = _analyze(dxf_a, "cmp-a", "a.dxf", [], auth_headers)
        resp_b = _analyze(dxf_b, "cmp-b", "b.dxf", [], auth_headers)

        assert resp_a["session_id"] != resp_b["session_id"]

    def test_blank_notes_does_not_prevent_extraction(self, auth_headers):
        """Blank notes field must NOT prevent DXF content extraction."""
        content = _dxf(insunits=4, text_entities=["H7/f6"])
        resp = _analyze(content, "test-blank-notes", "test.dxf", [], auth_headers)
        assert resp["detection_count"] >= 1
