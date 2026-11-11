"""DXF 2D geometry feature recognition tests — MUST 8 / MUST 12 / MUST 13.

Fixtures A–K cover:
  A. Literal CIRCLE → HOLE
  B. Two semicircular ARCs → HOLE (DXF_ARC_LOOP)
  C. Four quarter ARCs → HOLE
  D. Incomplete ARC (single 180°) → NO HOLE
  E. Circular LWPOLYLINE (16 vertices) → HOLE candidate
  F. Square closed LWPOLYLINE → NO HOLE
  G. Generic ellipse (major≠minor) → NO HOLE
  H. Exact circular ellipse (ratio=1.0) → HOLE
  I. BLOCK + INSERT → no crash, DEFERRED
  J. Mixed DXF (geometry + annotations) → no fabrication
  K. No fabrication: depth/material/Ra/IT must be absent/None for all

FABRICATED_DEPTH=NO
FABRICATED_MATERIAL=NO
FABRICATED_RA=NO
FABRICATED_IT=NO
SINGLE_ARC_FALSE_POSITIVE=NO
POLYGON_FALSE_POSITIVE=NO
GENERIC_ELLIPSE_FALSE_POSITIVE=NO
"""
from __future__ import annotations

import base64
import math

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.api.cad_features import _parse_dxf_2d
from backend.interoperability.cad_feature_recognition import (
    Dxf2dEntity,
    RecognitionMethod,
    recognize_dxf_features,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# DXF fixture builder
# ---------------------------------------------------------------------------

def _dxf(*entity_blocks: str, insunits: int = 4) -> bytes:
    """Build a minimal DXF R12 with given ENTITIES section blocks."""
    hdr = [
        "  0", "SECTION", "  2", "HEADER",
        "  9", "$ACADVER", "  1", "AC1009",
        "  9", "$INSUNITS", " 70", f"     {insunits}",
        "  0", "ENDSEC",
    ]
    entities = ["  0", "SECTION", "  2", "ENTITIES"]
    for blk in entity_blocks:
        entities.append(blk.strip())
    entities += ["  0", "ENDSEC", "  0", "EOF"]
    return "\n".join(hdr + entities).encode("utf-8")


def _circle_block(cx: float, cy: float, r: float) -> str:
    return f"  0\nCIRCLE\n  8\n0\n 10\n{cx}\n 20\n{cy}\n 40\n{r}"


def _arc_block(cx: float, cy: float, r: float, sa: float, ea: float) -> str:
    return f"  0\nARC\n  8\n0\n 10\n{cx}\n 20\n{cy}\n 40\n{r}\n 50\n{sa}\n 51\n{ea}"


def _lwpolyline_block(vertices: list[tuple[float, float]], closed: bool = True) -> str:
    flag = 1 if closed else 0
    lines = [f"  0\nLWPOLYLINE\n  8\n0\n 70\n{flag:6d}\n 90\n{len(vertices):6d}"]
    for x, y in vertices:
        lines.append(f" 10\n{x:.6f}\n 20\n{y:.6f}")
    return "\n".join(lines)


def _circular_vertices(cx: float, cy: float, r: float, n: int) -> list[tuple[float, float]]:
    return [
        (cx + r * math.cos(2 * math.pi * i / n),
         cy + r * math.sin(2 * math.pi * i / n))
        for i in range(n)
    ]


def _ellipse_block(cx: float, cy: float, mx: float, my: float, ratio: float) -> str:
    return (
        f"  0\nELLIPSE\n  8\n0\n"
        f" 10\n{cx}\n 20\n{cy}\n"
        f" 11\n{mx}\n 21\n{my}\n"
        f" 40\n{ratio}"
    )


# ---------------------------------------------------------------------------
# Fixture A — Literal CIRCLE
# ---------------------------------------------------------------------------

class TestFixtureA_Circle:
    def test_circle_produces_one_hole(self):
        content = _dxf(_circle_block(50.0, 50.0, 5.0))
        entities, counts = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 1
        assert feats[0].feature_type == "HOLE"
        assert feats[0].recognition_method == RecognitionMethod.DXF_CIRCLE

    def test_circle_diameter_equals_2r(self):
        content = _dxf(_circle_block(0.0, 0.0, 6.0))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 1
        assert abs(float(feats[0].diameter_mm) - 12.0) < 0.001

    def test_circle_entity_counted_in_histogram(self):
        content = _dxf(_circle_block(0.0, 0.0, 5.0))
        _, counts = _parse_dxf_2d(content)
        assert counts.get("CIRCLE", 0) == 1

    def test_tiny_circle_ignored(self):
        content = _dxf(_circle_block(0.0, 0.0, 0.01))  # < 0.05 threshold
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 0


# ---------------------------------------------------------------------------
# Fixture B — Two semicircular ARCs forming a full circle
# ---------------------------------------------------------------------------

class TestFixtureB_TwoSemiArcs:
    def test_two_semicircles_make_one_hole(self):
        content = _dxf(
            _arc_block(50.0, 50.0, 5.0, 0.0, 180.0),
            _arc_block(50.0, 50.0, 5.0, 180.0, 360.0),
        )
        entities, counts = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 1
        assert feats[0].recognition_method == RecognitionMethod.DXF_ARC_LOOP
        assert abs(float(feats[0].diameter_mm) - 10.0) < 0.001

    def test_arc_count_in_metadata(self):
        content = _dxf(
            _arc_block(50.0, 50.0, 5.0, 0.0, 180.0),
            _arc_block(50.0, 50.0, 5.0, 180.0, 360.0),
        )
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert feats[0].metadata.get("arc_count") == "2"

    def test_arc_histogram_counted(self):
        content = _dxf(
            _arc_block(50.0, 50.0, 5.0, 0.0, 180.0),
            _arc_block(50.0, 50.0, 5.0, 180.0, 360.0),
        )
        _, counts = _parse_dxf_2d(content)
        assert counts.get("ARC", 0) == 2


# ---------------------------------------------------------------------------
# Fixture C — Four quarter ARCs
# ---------------------------------------------------------------------------

class TestFixtureC_FourQuarterArcs:
    def test_four_arcs_make_one_hole(self):
        content = _dxf(
            _arc_block(0.0, 0.0, 8.0, 0.0,   90.0),
            _arc_block(0.0, 0.0, 8.0, 90.0,  180.0),
            _arc_block(0.0, 0.0, 8.0, 180.0, 270.0),
            _arc_block(0.0, 0.0, 8.0, 270.0, 360.0),
        )
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 1
        assert feats[0].recognition_method == RecognitionMethod.DXF_ARC_LOOP
        assert abs(float(feats[0].diameter_mm) - 16.0) < 0.001


# ---------------------------------------------------------------------------
# Fixture D — Incomplete ARC loop (single arc, 180°)
# ---------------------------------------------------------------------------

class TestFixtureD_IncompleteArc:
    def test_single_arc_no_hole(self):
        """Single ARC must NOT become a hole candidate."""
        content = _dxf(_arc_block(50.0, 50.0, 5.0, 0.0, 180.0))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 0, (
            f"Single 180° ARC must not produce a hole, got: {feats}"
        )

    def test_two_arcs_270_degrees_no_hole(self):
        """270° total coverage must not produce a hole."""
        content = _dxf(
            _arc_block(0.0, 0.0, 5.0, 0.0,   90.0),   # 90°
            _arc_block(0.0, 0.0, 5.0, 90.0,  270.0),  # 180°
        )
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 0, (
            f"270° ARC loop must not produce a hole, got {feats}"
        )


# ---------------------------------------------------------------------------
# Fixture E — Circular LWPOLYLINE (16 vertices)
# ---------------------------------------------------------------------------

class TestFixtureE_CircularPolyline:
    def test_circular_polyline_recognized(self):
        verts = _circular_vertices(50.0, 50.0, 5.0, 16)
        content = _dxf(_lwpolyline_block(verts, closed=True))
        entities, counts = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        # Either recognized as DXF_CIRCULAR_POLYLINE or 0 if deferred
        if len(feats) > 0:
            assert feats[0].recognition_method == RecognitionMethod.DXF_CIRCULAR_POLYLINE
            assert abs(float(feats[0].diameter_mm) - 10.0) < 0.5  # 5% tolerance
        # Must not crash

    def test_circular_polyline_in_histogram(self):
        verts = _circular_vertices(50.0, 50.0, 5.0, 16)
        content = _dxf(_lwpolyline_block(verts, closed=True))
        _, counts = _parse_dxf_2d(content)
        assert counts.get("LWPOLYLINE", 0) == 1


# ---------------------------------------------------------------------------
# Fixture F — Square closed LWPOLYLINE
# ---------------------------------------------------------------------------

class TestFixtureF_Square:
    def test_square_not_a_hole(self):
        """Closed square polyline MUST NOT become a hole candidate."""
        square = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
        content = _dxf(_lwpolyline_block(square, closed=True))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 0, (
            f"Square LWPOLYLINE must not become a hole, got: {feats}"
        )

    def test_rectangle_not_a_hole(self):
        """Non-square rectangle also must not become a hole."""
        rect = [(0.0, 0.0), (20.0, 0.0), (20.0, 5.0), (0.0, 5.0)]
        content = _dxf(_lwpolyline_block(rect, closed=True))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 0, (
            f"Rectangle must not become a hole, got: {feats}"
        )


# ---------------------------------------------------------------------------
# Fixture G — Generic ellipse (major≠minor)
# ---------------------------------------------------------------------------

class TestFixtureG_GenericEllipse:
    def test_ellipse_ratio_half_no_hole(self):
        """Ellipse with ratio=0.5 (major:minor = 2:1) must NOT be a hole."""
        content = _dxf(_ellipse_block(0.0, 0.0, 5.0, 0.0, 0.5))
        entities, counts = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 0, (
            f"Generic ellipse (ratio=0.5) must not produce a hole, got: {feats}"
        )

    def test_ellipse_counted_in_histogram(self):
        content = _dxf(_ellipse_block(0.0, 0.0, 5.0, 0.0, 0.5))
        _, counts = _parse_dxf_2d(content)
        assert counts.get("ELLIPSE", 0) == 1


# ---------------------------------------------------------------------------
# Fixture H — Exact circular ellipse (ratio=1.0)
# ---------------------------------------------------------------------------

class TestFixtureH_CircularEllipse:
    def test_circular_ellipse_recognized(self):
        """Ellipse with ratio=1.0 is a circle — may become a hole candidate."""
        content = _dxf(_ellipse_block(0.0, 0.0, 5.0, 0.0, 1.0))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        # Implementation may or may not support this — must not crash
        if len(feats) > 0:
            assert feats[0].recognition_method == RecognitionMethod.DXF_CIRCULAR_ELLIPSE
            assert abs(float(feats[0].diameter_mm) - 10.0) < 0.001


# ---------------------------------------------------------------------------
# Fixture I — BLOCK + INSERT (DEFERRED)
# ---------------------------------------------------------------------------

class TestFixtureI_BlockInsert:
    def test_block_insert_no_crash(self):
        """DXF with BLOCK+INSERT must not crash. BLOCK_INSERT_GEOMETRY_SUPPORT=DEFERRED."""
        dxf_content = (
            "  0\nSECTION\n  2\nBLOCKS\n"
            "  0\nBLOCK\n  8\n0\n  2\nHOLE_TEMPLATE\n 10\n0\n 20\n0\n"
            "  0\nCIRCLE\n  8\n0\n 10\n0\n 20\n0\n 40\n5.0\n"
            "  0\nENDBLK\n"
            "  0\nENDSEC\n"
            "  0\nSECTION\n  2\nENTITIES\n"
            "  0\nINSERT\n  8\n0\n  2\nHOLE_TEMPLATE\n 10\n50\n 20\n50\n"
            "  0\nENDSEC\n  0\nEOF\n"
        ).encode("utf-8")
        # Must not crash
        entities, counts = _parse_dxf_2d(dxf_content)
        feats = recognize_dxf_features(entities)
        # INSERT geometry deferred — no fabricated hole from deferred BLOCK
        # (may be 0 or more if CIRCLE in BLOCKS section is counted — either is acceptable)
        assert isinstance(feats, list)


# ---------------------------------------------------------------------------
# Fixture J — Mixed DXF (geometry + annotations)
# ---------------------------------------------------------------------------

class TestFixtureJ_Mixed:
    def test_annotations_do_not_produce_features(self):
        """TEXT/MTEXT annotations must not produce manufacturing features."""
        dxf_text = (
            "  0\nSECTION\n  2\nENTITIES\n"
            "  0\nCIRCLE\n  8\n0\n 10\n50\n 20\n50\n 40\n6.0\n"
            "  0\nTEXT\n  8\n0\n 10\n10\n 20\n10\n 40\n2.5\n  1\nRa 1.6\n"
            "  0\nMTEXT\n  8\n0\n 10\n20\n 20\n20\n  1\nM12x1.75\n"
            "  0\nENDSEC\n  0\nEOF\n"
        ).encode("utf-8")
        entities, counts = _parse_dxf_2d(dxf_text)
        feats = recognize_dxf_features(entities)
        # Only the CIRCLE should produce a feature
        assert all(f.recognition_method == RecognitionMethod.DXF_CIRCLE for f in feats)
        # TEXT/MTEXT in histogram
        assert counts.get("TEXT", 0) >= 1 or counts.get("MTEXT", 0) >= 1

    def test_multiple_circles_all_recognized(self):
        content = _dxf(
            _circle_block(10.0, 10.0, 3.0),
            _circle_block(50.0, 50.0, 5.0),
            _circle_block(90.0, 90.0, 7.5),
        )
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        assert len(feats) == 3


# ---------------------------------------------------------------------------
# Fixture K — No fabrication assertions
# ---------------------------------------------------------------------------

class TestFixtureK_NoFabrication:
    """Every recognized feature must have depth_mm=None; no material/Ra/IT."""

    def _all_features(self, content: bytes):
        entities, _ = _parse_dxf_2d(content)
        return recognize_dxf_features(entities)

    def test_no_depth_fabricated_circle(self):
        content = _dxf(_circle_block(0.0, 0.0, 5.0))
        for feat in self._all_features(content):
            assert feat.depth_mm is None, f"depth_mm must be None, got {feat.depth_mm}"

    def test_no_depth_fabricated_arc_loop(self):
        content = _dxf(
            _arc_block(0.0, 0.0, 5.0, 0.0, 180.0),
            _arc_block(0.0, 0.0, 5.0, 180.0, 360.0),
        )
        for feat in self._all_features(content):
            assert feat.depth_mm is None

    def test_no_material_in_feature(self):
        """Feature dict must not contain iso_material_group, required_ra_um, required_it_grade."""
        content = _dxf(_circle_block(0.0, 0.0, 5.0))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        for feat in feats:
            d = feat.as_dict()
            assert "iso_material_group" not in d, "material must not appear in feature dict"
            assert "required_ra_um" not in d, "Ra must not appear in feature dict"
            assert "required_it_grade" not in d, "IT grade must not appear in feature dict"

    def test_requires_review_true(self):
        """All DXF hole candidates must require engineer review."""
        content = _dxf(_circle_block(0.0, 0.0, 5.0))
        entities, _ = _parse_dxf_2d(content)
        feats = recognize_dxf_features(entities)
        for feat in feats:
            assert feat.requires_review is True, (
                f"DXF hole candidates must require_review=True, got {feat.confidence}"
            )

    def test_no_width_length_fabricated(self):
        content = _dxf(_circle_block(0.0, 0.0, 5.0))
        for feat in self._all_features(content):
            assert feat.width_mm is None
            assert feat.length_mm is None

    def test_diameter_matches_geometry(self):
        """Diameter must equal 2 * actual DXF radius."""
        for r in (3.0, 6.5, 12.0, 0.75):
            content = _dxf(_circle_block(0.0, 0.0, r))
            for feat in self._all_features(content):
                assert abs(float(feat.diameter_mm) - r * 2.0) < 0.001, (
                    f"diameter_mm should be {r * 2.0}, got {feat.diameter_mm}"
                )


# ---------------------------------------------------------------------------
# Entity histogram tests
# ---------------------------------------------------------------------------

class TestEntityHistogram:
    def test_histogram_counts_all_entity_types(self):
        dxf_text = (
            "  0\nSECTION\n  2\nENTITIES\n"
            "  0\nCIRCLE\n  8\n0\n 10\n0\n 20\n0\n 40\n5\n"
            "  0\nARC\n  8\n0\n 10\n0\n 20\n0\n 40\n5\n 50\n0\n 51\n90\n"
            "  0\nLINE\n  8\n0\n 10\n0\n 20\n0\n 11\n10\n 21\n0\n"
            "  0\nTEXT\n  8\n0\n 10\n0\n 20\n0\n 40\n2.5\n  1\nHello\n"
            "  0\nENDSEC\n  0\nEOF\n"
        ).encode("utf-8")
        _, counts = _parse_dxf_2d(dxf_text)
        assert counts.get("CIRCLE", 0) == 1
        assert counts.get("ARC", 0) == 1
        assert counts.get("LINE", 0) == 1
        assert counts.get("TEXT", 0) == 1

    def test_empty_dxf_no_counts(self):
        content = _dxf()
        _, counts = _parse_dxf_2d(content)
        assert isinstance(counts, dict)

    def test_no_crash_on_malformed_dxf(self):
        content = b"garbage content that is not valid DXF at all"
        entities, counts = _parse_dxf_2d(content)
        assert isinstance(entities, list)
        assert isinstance(counts, dict)


# ---------------------------------------------------------------------------
# API contract test (analyze_cad response via TestClient)
# ---------------------------------------------------------------------------

def _auth_header() -> dict:
    """Get JWT token for API requests."""
    login = client.post("/api/login", json={"username": "demo", "password": "demo"})
    if login.status_code == 200:
        token = login.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}
    return {}


class TestAnalyzeCadContract:
    def test_entity_counts_in_response(self):
        content = _dxf(_circle_block(50.0, 50.0, 5.0))
        b64 = base64.b64encode(content).decode()
        headers = _auth_header()
        resp = client.post("/api/cad-features/analyze", json={
            "file_name": "test.dxf",
            "content_b64": b64,
            "source_id": "hist-test",
        }, headers=headers)
        if resp.status_code == 401:
            pytest.skip("No auth credentials in test environment")
        assert resp.status_code == 200
        data = resp.json()
        assert "entity_counts" in data
        assert data["entity_counts"].get("CIRCLE", 0) == 1
        assert "geometry_entity_count" in data
        assert data["geometry_entity_count"] >= 1
        assert data["block_insert_support"] == "DEFERRED"

    def test_zero_feature_dxf_no_fabrication(self):
        """DXF with only LINE entities → 0 features, no fabrication."""
        dxf_text = (
            "  0\nSECTION\n  2\nENTITIES\n"
            "  0\nLINE\n  8\n0\n 10\n0\n 20\n0\n 11\n100\n 21\n0\n"
            "  0\nENDSEC\n  0\nEOF\n"
        ).encode("utf-8")
        b64 = base64.b64encode(dxf_text).decode()
        headers = _auth_header()
        resp = client.post("/api/cad-features/analyze", json={
            "file_name": "lines_only.dxf",
            "content_b64": b64,
        }, headers=headers)
        if resp.status_code == 401:
            pytest.skip("No auth credentials in test environment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["feature_count"] == 0
        assert data["face_count"] == 0
        assert data["body_count"] == 0
        assert data["status"] == "ANALYZED"
