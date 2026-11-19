"""
Phase 8 unit tests: arc sampler, contour extractor, step shoulder boundary,
and Phase 8 E2E CAM assessment.

Coverage:
  - BoundaryTraversalStatus enum (MUST 5)
  - Undirected edge traversal: connected closed loop, open chain, disconnected,
    branched (MUST 7)
  - topology_adapter Fix 1: circular outer loop classification (MUST 10)
  - Arc sampler: 2-arc closed face detection (MUST 12)
  - Contour extractor: exact topology, arc_map fallback (MUST 10-15)
  - Step/shoulder boundary: boundary_ready, feature_not_confirmed (MUST 3-9)
  - Phase 8 E2E: pocket/slot/step/drill matrices (MUST 22-33)
  - Safety invariants: is_dispatchable=False, etc. (MUST 44)
  - Negative tests: disconnected, open chain, missing WCS, missing tool (MUST 41-42)
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.interoperability.topology import (
    CanonicalEdge,
    CanonicalFace,
    CanonicalLoop,
    CanonicalPoint3D,
    CanonicalTopology,
    CanonicalVertex,
    LoopType,
)
from backend.step_brep.phase8_arc_sampler import (
    ARC_APPROXIMATION_RESOLUTION,
    ARC_APPROXIMATION_TOLERANCE_MM,
    ARC_BOUNDARY_METHOD,
    ArcContourMap,
    build_arc_contour_map,
)
from backend.step_brep.phase8_cam_e2e import (
    PHASE8_AUTO_APPROVAL,
    PHASE8_AUTO_CNC_DISPATCH,
    PHASE8_AUTOMATIC_ADAPTATION,
    PHASE8_IS_DISPATCHABLE,
    PHASE8_PRODUCTION_RELEASED,
    PHASE8_REAL_MACHINE_WRITE,
    PHASE8_REVIEW_REQUIRED,
    ReadinessStatus,
    run_phase8_e2e,
)
from backend.step_brep.phase8_contour_extractor import (
    P8_AMBIGUOUS_CONTOUR_AUTO_USED,
    P8_DISCONNECTED_BOUNDARY_USED_FOR_CAM,
    P8_OPEN_LOOP_USED_FOR_CAM,
    BoundaryTraversalStatus,
    _classify_traversal,
    extract_face_contour_p8,
)
from backend.step_brep.phase8_step_shoulder_boundary import (
    STEP_IS_DISPATCHABLE,
    STEP_PRODUCTION_RELEASED,
    STEP_REVIEW_REQUIRED,
    extract_step_shoulder_boundary,
)

# ---------------------------------------------------------------------------
# Helpers — synthetic topology builder
# ---------------------------------------------------------------------------


def _pt(x: float, y: float, z: float = 0.0) -> CanonicalPoint3D:
    return CanonicalPoint3D(
        x=Decimal(str(x)), y=Decimal(str(y)), z=Decimal(str(z))
    )


def _v(vid: str, x: float, y: float, z: float = 0.0) -> CanonicalVertex:
    return CanonicalVertex(vertex_id=vid, point=_pt(x, y, z))


def _e(eid: str, sv: str, ev: str) -> CanonicalEdge:
    return CanonicalEdge(
        edge_id=eid, start_vertex_id=sv, end_vertex_id=ev,
        curve_id=f"C-{eid}",
    )


def _rect_topo(face_tag: int = 10, w: float = 10.0, h: float = 10.0) -> CanonicalTopology:
    """Synthetic 4-edge rectangular outer loop."""
    stag = f"{face_tag}"
    v1 = _v(f"V{stag}1", 0.0, 0.0)
    v2 = _v(f"V{stag}2", w, 0.0)
    v3 = _v(f"V{stag}3", w, h)
    v4 = _v(f"V{stag}4", 0.0, h)
    e1 = _e(f"E{stag}1", f"V{stag}1", f"V{stag}2")
    e2 = _e(f"E{stag}2", f"V{stag}2", f"V{stag}3")
    e3 = _e(f"E{stag}3", f"V{stag}3", f"V{stag}4")
    e4 = _e(f"E{stag}4", f"V{stag}4", f"V{stag}1")
    lp = CanonicalLoop(
        loop_id=f"LOOP-S{stag}-OUTER",
        edge_ids=(f"E{stag}1", f"E{stag}2", f"E{stag}3", f"E{stag}4"),
        loop_type=LoopType.OUTER,
    )
    face = CanonicalFace(
        face_id=f"F-{face_tag}",
        surface_id=f"SURF-{face_tag}",
        boundary_loop_ids=(f"LOOP-S{stag}-OUTER",),
    )
    return CanonicalTopology(
        topology_id=f"TEST-{face_tag}",
        faces=(face,),
        loops=(lp,),
        edges=(e1, e2, e3, e4),
        vertices=(v1, v2, v3, v4),
    )


def _empty_topo() -> CanonicalTopology:
    return CanonicalTopology(
        topology_id="EMPTY",
        faces=(),
        loops=(),
        edges=(),
        vertices=(),
    )


def _make_step_record(
    bbox_min=(0.0, 0.0, 0.0),
    bbox_max=(50.0, 50.0, 25.0),
) -> MagicMock:
    """Minimal StepImportRecord mock with the fields Phase 8 uses."""
    rec = MagicMock()
    rec.source_path = "/fake/test.step"
    rec.bbox_min = bbox_min
    rec.bbox_max = bbox_max
    rec.faces = []
    return rec


# ---------------------------------------------------------------------------
# Phase 8 safety constants
# ---------------------------------------------------------------------------


class TestPhase8SafetyConstants:
    def test_is_dispatchable_false(self):
        assert PHASE8_IS_DISPATCHABLE is False

    def test_production_released_false(self):
        assert PHASE8_PRODUCTION_RELEASED is False

    def test_review_required_true(self):
        assert PHASE8_REVIEW_REQUIRED is True

    def test_real_machine_write_false(self):
        assert PHASE8_REAL_MACHINE_WRITE is False

    def test_auto_cnc_dispatch_false(self):
        assert PHASE8_AUTO_CNC_DISPATCH is False

    def test_auto_approval_false(self):
        assert PHASE8_AUTO_APPROVAL is False

    def test_automatic_adaptation_false(self):
        assert PHASE8_AUTOMATIC_ADAPTATION is False

    def test_step_is_dispatchable_false(self):
        assert STEP_IS_DISPATCHABLE is False

    def test_step_production_released_false(self):
        assert STEP_PRODUCTION_RELEASED is False

    def test_step_review_required_true(self):
        assert STEP_REVIEW_REQUIRED is True

    def test_p8_ambiguous_contour_auto_used_false(self):
        assert P8_AMBIGUOUS_CONTOUR_AUTO_USED is False

    def test_p8_open_loop_used_for_cam_false(self):
        assert P8_OPEN_LOOP_USED_FOR_CAM is False

    def test_p8_disconnected_boundary_used_for_cam_false(self):
        assert P8_DISCONNECTED_BOUNDARY_USED_FOR_CAM is False


# ---------------------------------------------------------------------------
# BoundaryTraversalStatus enum (MUST 5)
# ---------------------------------------------------------------------------


class TestBoundaryTraversalStatus:
    def test_connected_closed_loop_value(self):
        assert BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP == "CONNECTED_CLOSED_LOOP"

    def test_connected_open_chain_value(self):
        assert BoundaryTraversalStatus.CONNECTED_OPEN_CHAIN == "CONNECTED_OPEN_CHAIN"

    def test_disconnected_value(self):
        assert BoundaryTraversalStatus.DISCONNECTED == "DISCONNECTED"

    def test_branched_value(self):
        assert BoundaryTraversalStatus.BRANCHED == "BRANCHED"

    def test_ambiguous_value(self):
        assert BoundaryTraversalStatus.AMBIGUOUS == "AMBIGUOUS"

    def test_all_five_statuses_exist(self):
        statuses = set(BoundaryTraversalStatus)
        assert len(statuses) == 5


# ---------------------------------------------------------------------------
# _classify_traversal (undirected graph walk)
# ---------------------------------------------------------------------------


class TestClassifyTraversal:
    def _emap(self, edges: list[tuple[str, str, str]]) -> dict[str, tuple[str, str]]:
        return {eid: (sv, ev) for eid, sv, ev in edges}

    def test_simple_triangle_closed(self):
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V2", "V3"), ("E3", "V3", "V1"),
        ])
        result = _classify_traversal(("E1", "E2", "E3"), emap)
        assert result == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP

    def test_rectangle_closed(self):
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V2", "V3"),
            ("E3", "V3", "V4"), ("E4", "V4", "V1"),
        ])
        result = _classify_traversal(("E1", "E2", "E3", "E4"), emap)
        assert result == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP

    def test_rectangle_unordered_edges_still_closed(self):
        """Edges in arbitrary order — undirected walk should still find closure."""
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V2", "V3"),
            ("E3", "V3", "V4"), ("E4", "V4", "V1"),
        ])
        result = _classify_traversal(("E3", "E1", "E4", "E2"), emap)
        assert result == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP

    def test_mismatched_start_vertices_undirected_ok(self):
        """EE face 19 pattern: V-25 appears as start of 2 edges (directed).
        Undirected graph: degree 2 at each vertex → closed loop."""
        # V1 is start of E1 (→V2) and also start of E4 (→V4) in directed representation
        # But undirected: V1 ↔ V2 (E1) and V1 ↔ V4 (E4) → degree 2 at V1
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V2", "V3"),
            ("E3", "V3", "V4"), ("E4", "V1", "V4"),  # V1 appears as start of E1 and E4
        ])
        result = _classify_traversal(("E1", "E2", "E3", "E4"), emap)
        assert result == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP

    def test_open_chain_line(self):
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V2", "V3"),
        ])
        result = _classify_traversal(("E1", "E2"), emap)
        # 2 edges, 3 vertices: degree 1 at V1, degree 2 at V2, degree 1 at V3
        # Open: V1 and V3 are endpoints
        assert result in (
            BoundaryTraversalStatus.CONNECTED_OPEN_CHAIN,
            BoundaryTraversalStatus.DISCONNECTED,
        )

    def test_disconnected_two_separate_edges(self):
        """Two edges sharing no vertices → DISCONNECTED."""
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V3", "V4"), ("E3", "V4", "V5"),
        ])
        result = _classify_traversal(("E1", "E2", "E3"), emap)
        assert result == BoundaryTraversalStatus.DISCONNECTED

    def test_branched_junction_vertex(self):
        """A vertex connected to 3 edges → BRANCHED."""
        emap = self._emap([
            ("E1", "V1", "V2"), ("E2", "V2", "V3"),
            ("E3", "V2", "V4"), ("E4", "V4", "V1"),  # V2 has degree 3
        ])
        result = _classify_traversal(("E1", "E2", "E3", "E4"), emap)
        assert result == BoundaryTraversalStatus.BRANCHED

    def test_empty_edge_ids_disconnected(self):
        assert _classify_traversal((), {}) == BoundaryTraversalStatus.DISCONNECTED

    def test_missing_edge_in_emap_disconnected(self):
        emap = self._emap([("E1", "V1", "V2")])
        result = _classify_traversal(("E1", "E_MISSING"), emap)
        assert result == BoundaryTraversalStatus.DISCONNECTED


# ---------------------------------------------------------------------------
# Arc sampler module constants
# ---------------------------------------------------------------------------


class TestArcSamplerConstants:
    def test_boundary_method_approximated(self):
        assert ARC_BOUNDARY_METHOD == "APPROXIMATED"

    def test_tolerance_positive(self):
        assert ARC_APPROXIMATION_TOLERANCE_MM > 0.0

    def test_resolution_at_least_8(self):
        assert ARC_APPROXIMATION_RESOLUTION >= 8


# ---------------------------------------------------------------------------
# Arc sampler: build_arc_contour_map (mocked gmsh)
# ---------------------------------------------------------------------------


class TestBuildArcContourMap:
    def _mock_gmsh_2arc_circle(self, cx=0.0, cy=0.0, r=10.0, z=5.0, stag=42):
        """Mock gmsh for a planar circular face with 2 arcs sharing 2 vertices."""
        with (
            patch("backend.step_brep.phase8_arc_sampler.gmsh") as mock_gmsh,
        ):
            # getEntities(2) → one surface
            mock_gmsh.model.getEntities.return_value = [(2, stag)]
            # getBoundingBox(2, stag) → flat Z face
            mock_gmsh.model.getBoundingBox.side_effect = lambda dim, tag: (
                (cx - r, cy - r, z, cx + r, cy + r, z) if dim == 2
                else (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
            )
            # getBoundary([(2, stag)]) → 2 curves
            mock_gmsh.model.getBoundary.side_effect = lambda ents, **kw: (
                [(1, 100), (1, 101)] if ents == [(2, stag)]
                else [(0, 10), (0, 11)]  # Both arcs share vertices 10 and 11
            )
            result = build_arc_contour_map()
        return result

    def test_2arc_planar_face_in_map(self):
        result = self._mock_gmsh_2arc_circle()
        assert 42 in result

    def test_2arc_circle_12_points(self):
        result = self._mock_gmsh_2arc_circle()
        assert len(result[42]) == ARC_APPROXIMATION_RESOLUTION

    def test_2arc_circle_points_on_circle(self):
        import math
        cx, cy, r, z = 0.0, 0.0, 10.0, 5.0
        result = self._mock_gmsh_2arc_circle(cx=cx, cy=cy, r=r, z=z)
        pts = result[42]
        for px, py, pz in pts:
            dist = math.sqrt((px - cx) ** 2 + (py - cy) ** 2)
            assert abs(dist - r) < 0.1  # within 0.1mm of radius
            assert abs(pz - z) < 1e-9

    def test_non_2arc_face_excluded(self):
        """A face with 3 boundary curves must NOT appear in the arc_map."""
        with patch("backend.step_brep.phase8_arc_sampler.gmsh") as mock_gmsh:
            mock_gmsh.model.getEntities.return_value = [(2, 99)]
            mock_gmsh.model.getBoundingBox.return_value = (-5, -5, 0, 5, 5, 0)
            # 3 boundary curves → not a 2-arc face
            mock_gmsh.model.getBoundary.side_effect = lambda ents, **kw: (
                [(1, 10), (1, 11), (1, 12)]
            )
            result = build_arc_contour_map()
        assert 99 not in result

    def test_non_planar_face_excluded(self):
        """A face with nonzero Z extent (not flat) → excluded from arc_map."""
        with patch("backend.step_brep.phase8_arc_sampler.gmsh") as mock_gmsh:
            mock_gmsh.model.getEntities.return_value = [(2, 55)]
            # Non-planar: z-extent = 10mm
            mock_gmsh.model.getBoundingBox.return_value = (-5, -5, 0, 5, 5, 10)
            mock_gmsh.model.getBoundary.side_effect = lambda ents, **kw: (
                [(1, 10), (1, 11)] if ents == [(2, 55)]
                else [(0, 1), (0, 2)]  # Both arcs share same 2 vertices
            )
            result = build_arc_contour_map()
        assert 55 not in result

    def test_empty_model_returns_empty_map(self):
        with patch("backend.step_brep.phase8_arc_sampler.gmsh") as mock_gmsh:
            mock_gmsh.model.getEntities.return_value = []
            result = build_arc_contour_map()
        assert result == {}


# ---------------------------------------------------------------------------
# Phase 8 contour extractor: extract_face_contour_p8
# ---------------------------------------------------------------------------


class TestExtractFaceContourP8:
    def test_simple_rect_topology_closed_loop(self):
        topo = _rect_topo(face_tag=10, w=10.0, h=10.0)
        p8c = extract_face_contour_p8(10, topo, None, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert p8c.traversal_status == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP
        assert p8c.contour.is_valid
        assert p8c.contour.area_mm2 > 0.0
        assert p8c.boundary_method == "EXACT"

    def test_rect_topology_no_arc_map_needed(self):
        topo = _rect_topo(face_tag=20, w=50.0, h=30.0)
        p8c = extract_face_contour_p8(20, topo, {}, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert p8c.traversal_status == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP
        assert abs(p8c.contour.area_mm2 - 1500.0) < 1.0

    def test_face_not_in_topo_arc_map_fallback(self):
        topo = _empty_topo()
        arc_map: ArcContourMap = {
            109: [(9.9, 0.0, 149.33), (0.0, 9.9, 149.33), (-9.9, 0.0, 149.33),
                  (0.0, -9.9, 149.33), (7.0, 7.0, 149.33), (-7.0, 7.0, 149.33),
                  (-7.0, -7.0, 149.33), (7.0, -7.0, 149.33),
                  (5.0, 5.0, 149.33), (-5.0, 5.0, 149.33), (-5.0, -5.0, 149.33),
                  (5.0, -5.0, 149.33)],
        }
        p8c = extract_face_contour_p8(109, topo, arc_map, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert p8c.traversal_status == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP
        assert p8c.contour.is_valid
        assert p8c.boundary_method == "APPROXIMATED"
        assert p8c.approximation_tolerance_mm is not None
        assert p8c.approximation_resolution == ARC_APPROXIMATION_RESOLUTION

    def test_face_not_in_topo_no_arc_map_returns_none(self):
        topo = _empty_topo()
        result = extract_face_contour_p8(999, topo, None, (0.0, 0.0, 1.0))
        assert result is None

    def test_face_not_in_topo_arc_map_missing_key_returns_none(self):
        topo = _empty_topo()
        result = extract_face_contour_p8(999, topo, {}, (0.0, 0.0, 1.0))
        assert result is None

    def test_disconnected_boundary_traversal_disconnected(self):
        """Face with OUTER loop but disconnected edges → DISCONNECTED, is_valid=False."""
        stag = "77"
        # Edges that share NO vertices with each other
        v1 = _v("Va", 0.0, 0.0)
        v2 = _v("Vb", 10.0, 0.0)
        v3 = _v("Vc", 20.0, 20.0)
        v4 = _v("Vd", 30.0, 20.0)
        v5 = _v("Ve", 40.0, 40.0)
        # E1: Va-Vb, E2: Vc-Vd, E3: Ve-Va (Ve not connected to Vd)
        e1 = _e("Ex1", "Va", "Vb")
        e2 = _e("Ex2", "Vc", "Vd")
        e3 = _e("Ex3", "Ve", "Va")
        lp = CanonicalLoop(
            loop_id=f"LOOP-S{stag}-OUTER",
            edge_ids=("Ex1", "Ex2", "Ex3"),
            loop_type=LoopType.OUTER,
        )
        face = CanonicalFace(
            face_id="F-77", surface_id="S-77",
            boundary_loop_ids=(f"LOOP-S{stag}-OUTER",),
        )
        topo = CanonicalTopology(
            topology_id="DISC",
            faces=(face,), loops=(lp,), edges=(e1, e2, e3), vertices=(v1, v2, v3, v4, v5),
        )
        p8c = extract_face_contour_p8(77, topo, None, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert p8c.traversal_status == BoundaryTraversalStatus.DISCONNECTED
        assert not p8c.contour.is_valid

    def test_p8_contour_has_traversal_status(self):
        topo = _rect_topo(face_tag=10)
        p8c = extract_face_contour_p8(10, topo)
        assert isinstance(p8c.traversal_status, BoundaryTraversalStatus)

    def test_p8_contour_boundary_method_exact_for_topology(self):
        topo = _rect_topo(face_tag=10)
        p8c = extract_face_contour_p8(10, topo)
        assert p8c.boundary_method == "EXACT"
        assert p8c.approximation_tolerance_mm is None
        assert p8c.approximation_resolution is None

    def test_p8_contour_boundary_method_approximated_for_arc_map(self):
        topo = _empty_topo()
        arc_map = {5: [(i, i, 0.0) for i in range(12)]}  # 12 points
        p8c = extract_face_contour_p8(5, topo, arc_map, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert p8c.boundary_method == "APPROXIMATED"
        assert p8c.approximation_tolerance_mm == ARC_APPROXIMATION_TOLERANCE_MM

    def test_no_outer_loop_no_contour(self):
        """Face with only INNER loops → no OUTER loop → returns None."""
        stag = "88"
        v1 = _v("Vi1", 0.0, 0.0)
        v2 = _v("Vi2", 1.0, 0.0)
        v3 = _v("Vi3", 1.0, 1.0)
        e1 = _e("Ei1", "Vi1", "Vi2")
        e2 = _e("Ei2", "Vi2", "Vi3")
        e3 = _e("Ei3", "Vi3", "Vi1")
        lp = CanonicalLoop(
            loop_id=f"LOOP-S{stag}-INNER",
            edge_ids=("Ei1", "Ei2", "Ei3"),
            loop_type=LoopType.INNER,
        )
        face = CanonicalFace(
            face_id="F-88", surface_id="S-88",
            boundary_loop_ids=(f"LOOP-S{stag}-INNER",),
        )
        topo = CanonicalTopology(
            topology_id="INNER_ONLY", faces=(face,), loops=(lp,),
            edges=(e1, e2, e3), vertices=(v1, v2, v3),
        )
        result = extract_face_contour_p8(88, topo)
        assert result is None


# ---------------------------------------------------------------------------
# Phase 8 step/shoulder boundary (MUST 3-9)
# ---------------------------------------------------------------------------


class TestStepShoulderBoundary:
    def _make_step_rec(self, face_tag=1):
        rec = MagicMock()
        rec.lower_face_tag = face_tag
        rec.upper_face_tag = face_tag + 1
        rec.wall_face_tag = face_tag + 2
        return rec

    def test_boundary_ready_for_valid_topology(self):
        """Step face with valid rectangular outer loop → boundary_ready=True."""
        topo = _rect_topo(face_tag=10)
        step_rec = self._make_step_rec(face_tag=10)
        result = extract_step_shoulder_boundary(step_rec, topo)
        assert result.boundary_ready is True

    def test_feature_confirmed_always_false(self):
        """CANDIDATE never auto-confirmed in Phase 8."""
        topo = _rect_topo(face_tag=10)
        step_rec = self._make_step_rec(face_tag=10)
        result = extract_step_shoulder_boundary(step_rec, topo)
        # Even with boundary_ready=True, blocker mentions no toolpath
        assert "FEATURE_CONFIRMED=NO" in result.blocker

    def test_boundary_not_ready_for_missing_face(self):
        topo = _empty_topo()
        step_rec = self._make_step_rec(face_tag=99)
        result = extract_step_shoulder_boundary(step_rec, topo)
        assert result.boundary_ready is False
        assert result.contour is None

    def test_boundary_not_ready_for_disconnected(self):
        """Step face with disconnected boundary → boundary_ready=False."""
        stag = "55"
        v1 = _v("Ss1", 0.0, 0.0)
        v2 = _v("Ss2", 5.0, 0.0)
        v3 = _v("Ss3", 10.0, 10.0)
        v4 = _v("Ss4", 15.0, 15.0)
        e1 = _e("Se1", "Ss1", "Ss2")
        e2 = _e("Se2", "Ss3", "Ss4")
        e3 = _e("Se3", "Ss4", "Ss1")
        lp = CanonicalLoop(
            loop_id=f"LOOP-S{stag}-OUTER",
            edge_ids=("Se1", "Se2", "Se3"),
            loop_type=LoopType.OUTER,
        )
        face = CanonicalFace(
            face_id="F-55", surface_id="S-55",
            boundary_loop_ids=(f"LOOP-S{stag}-OUTER",),
        )
        topo = CanonicalTopology(
            topology_id="DISC55", faces=(face,), loops=(lp,),
            edges=(e1, e2, e3), vertices=(v1, v2, v3, v4),
        )
        step_rec = self._make_step_rec(face_tag=55)
        result = extract_step_shoulder_boundary(step_rec, topo)
        assert result.boundary_ready is False
        assert result.traversal_status in (
            BoundaryTraversalStatus.DISCONNECTED,
            BoundaryTraversalStatus.BRANCHED,
        )

    def test_is_dispatchable_false_always(self):
        topo = _rect_topo(face_tag=10)
        step_rec = self._make_step_rec(face_tag=10)
        from backend.step_brep.phase8_step_shoulder_boundary import StepShoulderBoundaryResult
        res = StepShoulderBoundaryResult()
        res.step_boundaries.append(extract_step_shoulder_boundary(step_rec, topo))
        assert res.is_dispatchable is False

    def test_step_shoulder_boundary_step_id_format(self):
        topo = _rect_topo(face_tag=10)
        step_rec = self._make_step_rec(face_tag=10)
        result = extract_step_shoulder_boundary(step_rec, topo, step_index=3)
        assert result.step_id == "STEP-3-F10"


# ---------------------------------------------------------------------------
# Phase 8 E2E: run_phase8_e2e
# ---------------------------------------------------------------------------


class TestPhase8E2E:
    def _make_record(self, bbox_max=(50.0, 50.0, 25.0)):
        rec = MagicMock()
        rec.source_path = "/fake/test.step"
        rec.bbox_min = (0.0, 0.0, 0.0)
        rec.bbox_max = bbox_max
        rec.faces = []
        return rec

    def test_wcs_derived_from_bbox(self):
        rec = self._make_record()
        with (
            patch("backend.step_brep.phase8_cam_e2e.detect_pocket_candidates", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, _empty_topo())
        assert r.wcs is not None
        assert r.wcs_ready is True

    def test_safety_invariants_in_result(self):
        rec = self._make_record()
        with (
            patch("backend.step_brep.phase8_cam_e2e.detect_pocket_candidates", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, _empty_topo())
        assert r.is_dispatchable is False
        assert r.production_released is False
        assert r.review_required is True
        assert r.real_machine_write is False
        assert r.auto_cnc_dispatch is False
        assert r.auto_approval is False
        assert r.automatic_adaptation is False

    def test_zero_features_no_toolpaths(self):
        rec = self._make_record()
        with (
            patch("backend.step_brep.phase8_cam_e2e.detect_pocket_candidates", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, _empty_topo())
        assert r.total_toolpath_count == 0
        assert r.any_toolpath_generated is False

    def test_pocket_with_valid_topology_generates_toolpath(self):
        """Pocket with valid rectangular floor face, 16mm Sandvik → toolpath generated."""
        from backend.step_brep.phase5_feature_detector import PocketCandidateRecord
        pocket = MagicMock(spec=PocketCandidateRecord)
        pocket.floor_face_tag = 10
        pocket.width_mm = 45.0
        pocket.length_mm = 45.0
        pocket.depth_mm = 15.0

        rec = self._make_record(bbox_max=(90.0, 90.0, 20.0))
        topo = _rect_topo(face_tag=10, w=45.0, h=45.0)

        with (
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_pocket_candidates",
                return_value=[pocket],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, topo, None)
        assert r.pocket_toolpath_count >= 1
        assert r.pocket_results[0].is_dispatchable is False
        assert r.pocket_results[0].feature_confirmed == ReadinessStatus.NO

    def test_pocket_with_arc_map_generates_toolpath(self):
        """Pocket floor in arc_map (not in topology) → BOUNDARY_METHOD=APPROXIMATED."""
        from backend.step_brep.phase5_feature_detector import PocketCandidateRecord
        pocket = MagicMock(spec=PocketCandidateRecord)
        pocket.floor_face_tag = 109
        pocket.width_mm = 45.0
        pocket.length_mm = 45.0
        pocket.depth_mm = 15.0

        rec = self._make_record(bbox_max=(100.0, 100.0, 50.0))
        topo = _empty_topo()
        arc_pts = [(9.9 * __import__('math').cos(2 * __import__('math').pi * i / 12),
                    9.9 * __import__('math').sin(2 * __import__('math').pi * i / 12),
                    0.0) for i in range(12)]
        arc_map: ArcContourMap = {109: arc_pts}

        with (
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_pocket_candidates",
                return_value=[pocket],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, topo, arc_map)
        assert 109 in r.arc_map_faces_used
        # Boundary should be APPROXIMATED
        assert r.pocket_results[0].boundary_method == "APPROXIMATED"

    def test_disconnected_pocket_blocked(self):
        """Pocket floor with disconnected boundary → BOUNDARY_READY=NO."""
        from backend.step_brep.phase5_feature_detector import PocketCandidateRecord
        pocket = MagicMock(spec=PocketCandidateRecord)
        pocket.floor_face_tag = 77
        pocket.width_mm = 45.0
        pocket.length_mm = 45.0
        pocket.depth_mm = 15.0

        stag = "77"
        v1 = _v("Vd1", 0.0, 0.0)
        v2 = _v("Vd2", 5.0, 0.0)
        v3 = _v("Vd3", 15.0, 10.0)  # disconnected from V2
        v4 = _v("Vd4", 20.0, 10.0)
        e1 = _e("Ed1", "Vd1", "Vd2")
        e2 = _e("Ed2", "Vd3", "Vd4")
        e3 = _e("Ed3", "Vd4", "Vd1")
        lp = CanonicalLoop(
            loop_id=f"LOOP-S{stag}-OUTER",
            edge_ids=("Ed1", "Ed2", "Ed3"),
            loop_type=LoopType.OUTER,
        )
        face = CanonicalFace(
            face_id="F-77", surface_id="S-77",
            boundary_loop_ids=(f"LOOP-S{stag}-OUTER",),
        )
        topo = CanonicalTopology(
            topology_id="DISC77", faces=(face,), loops=(lp,),
            edges=(e1, e2, e3), vertices=(v1, v2, v3, v4),
        )
        rec = self._make_record()

        with (
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_pocket_candidates",
                return_value=[pocket],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, topo, None)
        assert r.pocket_results[0].boundary_ready == ReadinessStatus.NO
        assert r.pocket_results[0].toolpath_ready == ReadinessStatus.NO

    def test_step_shoulder_never_auto_confirmed(self):
        """Step/shoulder features always have feature_confirmed=NO and toolpath_ready=NO."""
        from backend.step_brep.phase5_feature_detector import StepShoulderRecord
        step = MagicMock(spec=StepShoulderRecord)
        step.lower_face_tag = 10
        step.upper_face_tag = 11
        step.wall_face_tag = 12
        topo = _rect_topo(face_tag=10)
        rec = self._make_record()

        with (
            patch("backend.step_brep.phase8_cam_e2e.detect_pocket_candidates", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[step],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, topo, None)

        assert r.step_results[0].feature_confirmed == ReadinessStatus.NO
        assert r.step_results[0].toolpath_ready == ReadinessStatus.NO
        assert r.step_results[0].is_dispatchable is False

    def test_step_boundary_ready_count_reported(self):
        """Step shoulder with valid boundary → step_boundary_ready_count ≥ 1."""
        from backend.step_brep.phase5_feature_detector import StepShoulderRecord
        step = MagicMock(spec=StepShoulderRecord)
        step.lower_face_tag = 10
        step.upper_face_tag = 11
        step.wall_face_tag = 12
        topo = _rect_topo(face_tag=10)
        rec = self._make_record()

        with (
            patch("backend.step_brep.phase8_cam_e2e.detect_pocket_candidates", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[step],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, topo, None)
        assert r.step_boundary_ready_count >= 1

    def test_arc_map_faces_used_empty_when_no_arc(self):
        rec = self._make_record()
        with (
            patch("backend.step_brep.phase8_cam_e2e.detect_pocket_candidates", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.detect_slot_candidates", return_value=[]),
            patch(
                "backend.step_brep.phase8_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase8_cam_e2e.detect_oriented_cylinders", return_value=[]),
            patch("backend.step_brep.phase8_cam_e2e.filter_internal_cylinders", return_value=[]),
        ):
            r = run_phase8_e2e(rec, _empty_topo(), None)
        assert r.arc_map_faces_used == ()


# ---------------------------------------------------------------------------
# Negative / false-positive tests (MUST 41-42)
# ---------------------------------------------------------------------------


class TestPhase8NegativeCases:
    def test_open_loop_not_used_for_cam(self):
        """CONNECTED_OPEN_CHAIN never generates a toolpath."""
        # Build a 3-edge open chain: V1-V2-V3-V4 (open, not closing back to V1)
        v1 = _v("N1", 0.0, 0.0)
        v2 = _v("N2", 10.0, 0.0)
        v3 = _v("N3", 10.0, 10.0)
        v4 = _v("N4", 20.0, 10.0)
        e1 = _e("NE1", "N1", "N2")
        e2 = _e("NE2", "N2", "N3")
        e3 = _e("NE3", "N3", "N4")
        lp = CanonicalLoop(
            loop_id="LOOP-OPEN",
            edge_ids=("NE1", "NE2", "NE3"),
            loop_type=LoopType.OUTER,
        )
        face = CanonicalFace(
            face_id="F-200", surface_id="S-200",
            boundary_loop_ids=("LOOP-OPEN",),
        )
        topo = CanonicalTopology(
            topology_id="OPEN",
            faces=(face,), loops=(lp,), edges=(e1, e2, e3), vertices=(v1, v2, v3, v4),
        )
        p8c = extract_face_contour_p8(200, topo, None, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert p8c.traversal_status in (
            BoundaryTraversalStatus.CONNECTED_OPEN_CHAIN,
            BoundaryTraversalStatus.DISCONNECTED,
        )
        assert not p8c.contour.is_valid

    def test_branched_loop_not_used_for_cam(self):
        """BRANCHED topology never generates a valid contour."""
        v1 = _v("B1", 0.0, 0.0)
        v2 = _v("B2", 10.0, 0.0)
        v3 = _v("B3", 10.0, 10.0)
        v4 = _v("B4", 0.0, 10.0)
        v5 = _v("B5", 20.0, 5.0)
        # V2 connects to V3, V4, and V5 → degree 3 (including E1 from V1)
        e1 = _e("BE1", "B1", "B2")
        e2 = _e("BE2", "B2", "B3")
        e3 = _e("BE3", "B3", "B4")
        e4 = _e("BE4", "B4", "B1")  # closes V4-V1
        e5 = _e("BE5", "B2", "B5")  # extra edge from V2 → branch
        lp = CanonicalLoop(
            loop_id="LOOP-BRANCH",
            edge_ids=("BE1", "BE2", "BE3", "BE4", "BE5"),
            loop_type=LoopType.OUTER,
        )
        face = CanonicalFace(
            face_id="F-201", surface_id="S-201",
            boundary_loop_ids=("LOOP-BRANCH",),
        )
        topo = CanonicalTopology(
            topology_id="BRANCHED",
            faces=(face,), loops=(lp,), edges=(e1, e2, e3, e4, e5),
            vertices=(v1, v2, v3, v4, v5),
        )
        p8c = extract_face_contour_p8(201, topo)
        assert p8c is not None
        assert p8c.traversal_status == BoundaryTraversalStatus.BRANCHED
        assert not p8c.contour.is_valid

    def test_zero_points_arc_map_no_valid_contour(self):
        """arc_map with fewer than 3 points → no valid contour."""
        topo = _empty_topo()
        arc_map: ArcContourMap = {5: [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]}  # only 2 points
        p8c = extract_face_contour_p8(5, topo, arc_map, (0.0, 0.0, 1.0))
        assert p8c is not None
        assert not p8c.contour.is_valid

    def test_circular_outer_loop_requires_topology_proof(self):
        """Circular face without OUTER loop in topology → no contour (not arc_map face)."""
        stag = "99"
        # Circular face: only circular loops classified as UNKNOWN (pre-fix)
        v1 = _v("CU1", 10.0, 0.0)
        v2 = _v("CU2", 0.0, 10.0)
        v3 = _v("CU3", -10.0, 0.0)
        e1 = _e("UC1", "CU1", "CU2")
        e2 = _e("UC2", "CU2", "CU3")
        e3 = _e("UC3", "CU3", "CU1")
        lp = CanonicalLoop(
            loop_id=f"LOOP-S{stag}-UNKNOWN",
            edge_ids=("UC1", "UC2", "UC3"),
            loop_type=LoopType.UNKNOWN,  # Unlassified — no OUTER
        )
        face = CanonicalFace(
            face_id="F-99", surface_id="S-99",
            boundary_loop_ids=(f"LOOP-S{stag}-UNKNOWN",),
        )
        topo = CanonicalTopology(
            topology_id="UNKNOWN",
            faces=(face,), loops=(lp,), edges=(e1, e2, e3), vertices=(v1, v2, v3),
        )
        result = extract_face_contour_p8(99, topo)
        # No OUTER loop → None
        assert result is None
