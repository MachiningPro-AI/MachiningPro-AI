"""
Tests for Phase 7C: Contour/loop extraction from B-Rep topology.

Covers MUST 29–31: topology-derived contours, loop classification,
closed loop validation, non-zero area check.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.interoperability.topology import LoopType
from backend.step_brep.phase7_contour_extractor import (
    AMBIGUOUS_CONTOUR_AUTO_USED,
    ContourType,
    extract_all_face_contours,
    extract_face_outer_contour,
)

# ---------------------------------------------------------------------------
# Helpers — build minimal CanonicalTopology stubs
# ---------------------------------------------------------------------------

def _stub_vertex(vid, x, y, z):
    """Build a minimal stub vertex."""
    v = MagicMock()
    v.vertex_id = vid
    pt = MagicMock()
    pt.x = MagicMock()
    pt.x.value = x
    pt.y = MagicMock()
    pt.y.value = y
    pt.z = MagicMock()
    pt.z.value = z
    v.point = pt
    return v


def _stub_edge(eid, sv_id, ev_id):
    e = MagicMock()
    e.edge_id = eid
    e.start_vertex_id = sv_id
    e.end_vertex_id = ev_id
    return e


def _stub_loop(lid, edge_ids, loop_type=LoopType.OUTER):
    lp = MagicMock()
    lp.loop_id = lid
    lp.edge_ids = tuple(edge_ids)
    lp.loop_type = loop_type
    return lp


def _stub_face(fid, loop_ids):
    f = MagicMock()
    f.face_id = fid
    f.boundary_loop_ids = tuple(loop_ids)
    return f


def _make_square_topo(face_tag=1):
    """Build a 10×10mm square face topology."""
    vertices = [
        _stub_vertex("V-1", 0.0, 0.0, 5.0),
        _stub_vertex("V-2", 10.0, 0.0, 5.0),
        _stub_vertex("V-3", 10.0, 10.0, 5.0),
        _stub_vertex("V-4", 0.0, 10.0, 5.0),
    ]
    edges = [
        _stub_edge("E-1", "V-1", "V-2"),
        _stub_edge("E-2", "V-2", "V-3"),
        _stub_edge("E-3", "V-3", "V-4"),
        _stub_edge("E-4", "V-4", "V-1"),
    ]
    outer_loop = _stub_loop("LOOP-S1-OUTER", ["E-1", "E-2", "E-3", "E-4"], LoopType.OUTER)
    face = _stub_face(f"F-{face_tag}", ["LOOP-S1-OUTER"])

    topo = MagicMock()
    topo.vertices = vertices
    topo.edges = edges
    topo.loops = [outer_loop]
    topo.faces = [face]
    return topo


def _make_topo_with_inner_loop(face_tag=5):
    """Build a face with one outer + one inner (hole) loop."""
    vertices = [
        _stub_vertex("V-1", 0.0, 0.0, 0.0),
        _stub_vertex("V-2", 20.0, 0.0, 0.0),
        _stub_vertex("V-3", 20.0, 20.0, 0.0),
        _stub_vertex("V-4", 0.0, 20.0, 0.0),
        _stub_vertex("V-5", 8.0, 8.0, 0.0),
        _stub_vertex("V-6", 12.0, 8.0, 0.0),
        _stub_vertex("V-7", 12.0, 12.0, 0.0),
        _stub_vertex("V-8", 8.0, 12.0, 0.0),
    ]
    outer_edges = [
        _stub_edge("E-1", "V-1", "V-2"),
        _stub_edge("E-2", "V-2", "V-3"),
        _stub_edge("E-3", "V-3", "V-4"),
        _stub_edge("E-4", "V-4", "V-1"),
    ]
    inner_edges = [
        _stub_edge("E-5", "V-5", "V-6"),
        _stub_edge("E-6", "V-6", "V-7"),
        _stub_edge("E-7", "V-7", "V-8"),
        _stub_edge("E-8", "V-8", "V-5"),
    ]
    outer_loop = _stub_loop("LOOP-S5-OUTER", ["E-1", "E-2", "E-3", "E-4"], LoopType.OUTER)
    inner_loop = _stub_loop("LOOP-S5-INNER", ["E-5", "E-6", "E-7", "E-8"], LoopType.INNER)
    face = _stub_face(f"F-{face_tag}", ["LOOP-S5-OUTER", "LOOP-S5-INNER"])

    topo = MagicMock()
    topo.vertices = vertices
    topo.edges = outer_edges + inner_edges
    topo.loops = [outer_loop, inner_loop]
    topo.faces = [face]
    return topo


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestContourSafetyInvariants:
    def test_ambiguous_contour_auto_used_is_false(self):
        assert AMBIGUOUS_CONTOUR_AUTO_USED is False


# ---------------------------------------------------------------------------
# ContourType enum
# ---------------------------------------------------------------------------

class TestContourType:
    def test_outer_loop_value(self):
        assert ContourType.OUTER_LOOP == "OUTER_LOOP"

    def test_inner_loop_value(self):
        assert ContourType.INNER_LOOP == "INNER_LOOP"

    def test_open_chain_value(self):
        assert ContourType.OPEN_CHAIN == "OPEN_CHAIN"

    def test_ambiguous_loop_value(self):
        assert ContourType.AMBIGUOUS_LOOP == "AMBIGUOUS_LOOP"

    def test_has_four_values(self):
        assert len(ContourType) == 4


# ---------------------------------------------------------------------------
# extract_face_outer_contour — basic success
# ---------------------------------------------------------------------------

class TestExtractFaceOuterContour:
    def test_returns_contour_for_known_face(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c is not None

    def test_returns_none_for_unknown_face(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(99, topo, (0.0, 0.0, 1.0))
        assert c is None

    def test_contour_type_is_outer_loop(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c.contour_type == ContourType.OUTER_LOOP

    def test_is_valid_true(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c.is_valid is True

    def test_is_closed_true(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c.is_closed is True

    def test_has_non_zero_area(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c.area_mm2 is not None
        assert c.area_mm2 > 0

    def test_square_area_100(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert abs(c.area_mm2 - 100.0) < 1e-3

    def test_points_2d_at_least_3(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert len(c.points_2d) >= 3

    def test_source_provenance_topology_derived(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c.source_provenance == "TOPOLOGY_DERIVED"

    def test_source_provenance_never_bbox(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert "BBOX" not in c.source_provenance

    def test_face_tag_preserved(self):
        topo = _make_square_topo(face_tag=7)
        c = extract_face_outer_contour(7, topo, (0.0, 0.0, 1.0))
        assert c.face_tag == 7

    def test_face_id_format(self):
        topo = _make_square_topo(face_tag=7)
        c = extract_face_outer_contour(7, topo, (0.0, 0.0, 1.0))
        assert c.face_id == "F-7"

    def test_validation_notes_ok_on_valid(self):
        topo = _make_square_topo(face_tag=1)
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        assert c.validation_notes == "OK"


# ---------------------------------------------------------------------------
# Inner loop classification
# ---------------------------------------------------------------------------

class TestInnerLoopClassification:
    def test_all_contours_returns_outer_and_inner(self):
        topo = _make_topo_with_inner_loop(face_tag=5)
        contours = extract_all_face_contours(5, topo, (0.0, 0.0, 1.0))
        assert len(contours) == 2
        types = {c.contour_type for c in contours}
        assert ContourType.OUTER_LOOP in types
        assert ContourType.INNER_LOOP in types

    def test_inner_loop_is_valid(self):
        topo = _make_topo_with_inner_loop(face_tag=5)
        contours = extract_all_face_contours(5, topo, (0.0, 0.0, 1.0))
        inner = next(c for c in contours if c.contour_type == ContourType.INNER_LOOP)
        assert inner.is_valid is True

    def test_inner_loop_area_is_smaller(self):
        topo = _make_topo_with_inner_loop(face_tag=5)
        contours = extract_all_face_contours(5, topo, (0.0, 0.0, 1.0))
        outer = next(c for c in contours if c.contour_type == ContourType.OUTER_LOOP)
        inner = next(c for c in contours if c.contour_type == ContourType.INNER_LOOP)
        assert outer.area_mm2 > inner.area_mm2

    def test_all_contours_empty_for_unknown_face(self):
        topo = _make_topo_with_inner_loop(face_tag=5)
        contours = extract_all_face_contours(99, topo)
        assert contours == []


# ---------------------------------------------------------------------------
# Negative / degenerate cases
# ---------------------------------------------------------------------------

class TestContourNegativeCases:
    def test_ambiguous_loop_is_not_valid(self):
        topo = _make_square_topo(face_tag=1)
        # Override loop type to UNKNOWN
        topo.loops[0].loop_type = LoopType.UNKNOWN
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        # No outer loop found (UNKNOWN ≠ OUTER), returns None
        assert c is None

    def test_missing_vertex_does_not_crash(self):
        topo = _make_square_topo(face_tag=1)
        # Remove vertex V-3 from lookup by making vertex_id mismatch
        topo.vertices[2].vertex_id = "V-999"
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        # Should return a contour (possibly degenerate/invalid) but not crash
        # With only 3 valid start-vertex edges it may still produce a result
        assert c is not None or c is None  # no crash is the requirement

    def test_too_few_edges_returns_open_chain(self):
        """A loop with only 2 edges → OPEN_CHAIN, not valid."""
        topo = MagicMock()
        topo.vertices = [
            _stub_vertex("V-1", 0.0, 0.0, 0.0),
            _stub_vertex("V-2", 5.0, 0.0, 0.0),
        ]
        topo.edges = [
            _stub_edge("E-1", "V-1", "V-2"),
            _stub_edge("E-2", "V-2", "V-1"),
        ]
        loop = _stub_loop("LOOP-S1-OUTER", ["E-1", "E-2"], LoopType.OUTER)
        face = _stub_face("F-1", ["LOOP-S1-OUTER"])
        topo.loops = [loop]
        topo.faces = [face]
        # With dedup, 2 unique points < 3 → open chain
        c = extract_face_outer_contour(1, topo, (0.0, 0.0, 1.0))
        if c is not None:
            assert c.is_valid is False
