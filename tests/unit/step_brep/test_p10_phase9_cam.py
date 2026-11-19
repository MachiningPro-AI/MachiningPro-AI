"""
Phase 9 unit tests: multi-face shoulder boundary extraction, drill cycle
assessment, and Phase 9 E2E CAM.

Coverage:
  - Safety constants (all False/True invariants) — MUST 15, 20–24
  - MultiShoulderStatus enum values
  - _find_shared_edges: no edges, some edges, absent face
  - _classify_shoulder_boundary: VALID, OPEN_CHAIN, DISCONNECTED, NO_SHARED
  - ShoulderEdgeBoundary: boundary_ready semantics
  - assess_shoulder_cam: boundary/depth/tool/cam_ready logic
  - ShoulderCAMResult: aggregate counts
  - DrillCycleAssessment: geometric/parameterized separation (MUST 19)
  - assess_drill_cycle: internal vs external, axis check, catalog gap
  - DrillCycleResult: aggregate counts + unique diameters
  - Phase9E2E: aggregate struct, safety invariants
  - Negative cases: external cylinder not drilled, non-Z axis blocked
  - False-positive: shoulder toolpath_ready always False
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
from backend.step_brep.phase5_feature_detector import (
    CylinderOrientation,
    OrientedCylinderRecord,
    StepShoulderRecord,
)
from backend.step_brep.phase9_cam_e2e import (
    PHASE9_AUTO_APPROVAL,
    PHASE9_AUTO_CNC_DISPATCH,
    PHASE9_AUTOMATIC_ADAPTATION,
    PHASE9_IS_DISPATCHABLE,
    PHASE9_P9B_TOOLPATH_READY,
    PHASE9_PRODUCTION_RELEASED,
    PHASE9_REAL_MACHINE_WRITE,
    PHASE9_REVIEW_REQUIRED,
)
from backend.step_brep.phase9_drill_cam import (
    P9C_AUTO_CONFIRMATION,
    P9C_IS_DISPATCHABLE,
    P9C_PRODUCTION_RELEASED,
    DrillCycleResult,
    assess_drill_cycle,
)
from backend.step_brep.phase9_shoulder_cam import (
    P9B_AUTO_CONFIRMATION,
    P9B_IS_DISPATCHABLE,
    P9B_PRODUCTION_RELEASED,
    P9B_TOOLPATH_READY,
    MultiShoulderStatus,
    ShoulderCAMAssessment,
    ShoulderCAMResult,
    _classify_shoulder_boundary,
    _find_shared_edges,
    assess_shoulder_cam,
)

# ---------------------------------------------------------------------------
# Synthetic topology helpers
# ---------------------------------------------------------------------------


def _pt(x: float, y: float, z: float = 0.0) -> CanonicalPoint3D:
    return CanonicalPoint3D(x=Decimal(str(x)), y=Decimal(str(y)), z=Decimal(str(z)))


def _v(vid: str, x: float, y: float) -> CanonicalVertex:
    return CanonicalVertex(vertex_id=vid, point=_pt(x, y))


def _e(eid: str, sv: str, ev: str) -> CanonicalEdge:
    return CanonicalEdge(edge_id=eid, start_vertex_id=sv, end_vertex_id=ev,
                         curve_id=f"C-{eid}")


def _empty_topo() -> CanonicalTopology:
    return CanonicalTopology(topology_id="EMPTY", faces=(), loops=(), edges=(), vertices=())


def _make_two_face_topo(
    lower_tag: int = 1,
    wall_tag: int = 2,
    shared_edges: list[tuple[str, str, str]] | None = None,
) -> CanonicalTopology:
    """Two faces sharing some edges.

    shared_edges: list of (edge_id, start_vid, end_vid) for edges in BOTH faces.
    """
    if shared_edges is None:
        shared_edges = []

    # Build shared edge objects
    s_edges = [_e(eid, sv, ev) for eid, sv, ev in shared_edges]
    s_verts_seen: set[str] = set()
    for _, sv, ev in shared_edges:
        s_verts_seen.add(sv)
        s_verts_seen.add(ev)
    s_verts = [_v(vid, float(i), 0.0) for i, vid in enumerate(sorted(s_verts_seen))]

    # Lower face edges (private + shared)
    lower_priv = [_e("EL1", "VL1", "VL2"), _e("EL2", "VL2", "VL3"), _e("EL3", "VL3", "VL1")]
    lp_verts = [_v("VL1", 0, 0), _v("VL2", 10, 0), _v("VL3", 10, 10)]
    lower_eids = tuple(e.edge_id for e in lower_priv + s_edges)
    lower_loop = CanonicalLoop(loop_id=f"LOOP-L{lower_tag}", edge_ids=lower_eids,
                               loop_type=LoopType.OUTER)
    lower_face = CanonicalFace(face_id=f"F-{lower_tag}", surface_id=f"S-{lower_tag}",
                               boundary_loop_ids=(f"LOOP-L{lower_tag}",))

    # Wall face edges (private + shared)
    wall_priv = [_e("EW1", "VW1", "VW2"), _e("EW2", "VW2", "VW3"), _e("EW3", "VW3", "VW1")]
    w_verts = [_v("VW1", 20, 0), _v("VW2", 30, 0), _v("VW3", 30, 10)]
    wall_eids = tuple(e.edge_id for e in wall_priv + s_edges)
    wall_loop = CanonicalLoop(loop_id=f"LOOP-W{wall_tag}", edge_ids=wall_eids,
                              loop_type=LoopType.OUTER)
    wall_face = CanonicalFace(face_id=f"F-{wall_tag}", surface_id=f"S-{wall_tag}",
                              boundary_loop_ids=(f"LOOP-W{wall_tag}",))

    all_edges = lower_priv + wall_priv + s_edges
    all_verts = lp_verts + w_verts + s_verts
    all_loops = [lower_loop, wall_loop]
    all_faces = [lower_face, wall_face]

    return CanonicalTopology(
        topology_id="TWO_FACE",
        faces=tuple(all_faces),
        loops=tuple(all_loops),
        edges=tuple(all_edges),
        vertices=tuple(all_verts),
    )


def _make_step_record(
    bbox_min=(0.0, 0.0, 0.0),
    bbox_max=(50.0, 50.0, 25.0),
):
    """Make a minimal StepImportRecord with given bbox."""
    from unittest.mock import MagicMock
    rec = MagicMock()
    rec.source_path = "test.step"
    rec.bbox_min = tuple(bbox_min)
    rec.bbox_max = tuple(bbox_max)
    rec.faces = []
    return rec


def _make_wcs():
    """Make a valid SUGGESTED WCS."""
    from backend.step_brep.phase7_wcs_provider import suggest_wcs_top_center
    return suggest_wcs_top_center(_make_step_record())


def _make_cyl(
    face_tag: int = 5,
    diameter_mm: float = 8.0,
    orientation: CylinderOrientation = CylinderOrientation.INTERNAL_CYLINDER,
    axis_direction: str | None = "Z",
    depth_mm: float | None = 20.0,
    hole_class: str = "THROUGH_HOLE_CANDIDATE",
    bbox_min=(5.0, 5.0, 0.0),
    bbox_max=(13.0, 13.0, 20.0),
) -> OrientedCylinderRecord:
    return OrientedCylinderRecord(
        face_tag=face_tag,
        feature_status="CANDIDATE",
        hole_class=hole_class,
        cylinder_orientation=orientation,
        diameter_mm=diameter_mm,
        axis_direction=axis_direction,
        depth_mm=depth_mm,
        bbox_min=tuple(bbox_min),
        bbox_max=tuple(bbox_max),
        circular_boundary_count=1,
        orientation_evidence="SYNTHETIC_TEST_RECORD",
    )


def _make_shoulder(
    lower_tag: int = 1,
    wall_tag: int = 2,
    upper_tag: int = 3,
    step_height_mm: float | None = 5.0,
) -> StepShoulderRecord:
    return StepShoulderRecord(
        lower_face_tag=lower_tag,
        upper_face_tag=upper_tag,
        wall_face_tag=wall_tag,
        step_height_mm=step_height_mm,
        feature_status="CANDIDATE",
        evidence="SYNTHETIC_TEST_RECORD",
    )


# ===========================================================================
# TestPhase9SafetyConstants
# ===========================================================================

class TestPhase9SafetyConstants:
    def test_p9b_is_dispatchable_false(self):
        assert P9B_IS_DISPATCHABLE is False

    def test_p9b_production_released_false(self):
        assert P9B_PRODUCTION_RELEASED is False

    def test_p9b_toolpath_ready_false(self):
        assert P9B_TOOLPATH_READY is False

    def test_p9b_auto_confirmation_false(self):
        assert P9B_AUTO_CONFIRMATION is False

    def test_p9c_is_dispatchable_false(self):
        assert P9C_IS_DISPATCHABLE is False

    def test_p9c_production_released_false(self):
        assert P9C_PRODUCTION_RELEASED is False

    def test_p9c_auto_confirmation_false(self):
        assert P9C_AUTO_CONFIRMATION is False

    def test_phase9_is_dispatchable_false(self):
        assert PHASE9_IS_DISPATCHABLE is False

    def test_phase9_production_released_false(self):
        assert PHASE9_PRODUCTION_RELEASED is False

    def test_phase9_review_required_true(self):
        assert PHASE9_REVIEW_REQUIRED is True

    def test_phase9_real_machine_write_false(self):
        assert PHASE9_REAL_MACHINE_WRITE is False

    def test_phase9_auto_cnc_dispatch_false(self):
        assert PHASE9_AUTO_CNC_DISPATCH is False

    def test_phase9_auto_approval_false(self):
        assert PHASE9_AUTO_APPROVAL is False

    def test_phase9_automatic_adaptation_false(self):
        assert PHASE9_AUTOMATIC_ADAPTATION is False

    def test_phase9_p9b_toolpath_ready_reexport(self):
        assert PHASE9_P9B_TOOLPATH_READY is False


# ===========================================================================
# TestMultiShoulderStatus
# ===========================================================================

class TestMultiShoulderStatus:
    def test_valid_multi_face_shoulder_value(self):
        assert MultiShoulderStatus.VALID_MULTI_FACE_SHOULDER == "VALID_MULTI_FACE_SHOULDER"

    def test_open_chain_value(self):
        assert MultiShoulderStatus.OPEN_CHAIN == "OPEN_CHAIN"

    def test_disconnected_value(self):
        assert MultiShoulderStatus.DISCONNECTED == "DISCONNECTED"

    def test_branched_value(self):
        assert MultiShoulderStatus.BRANCHED == "BRANCHED"

    def test_ambiguous_value(self):
        assert MultiShoulderStatus.AMBIGUOUS == "AMBIGUOUS"

    def test_no_shared_edges_value(self):
        assert MultiShoulderStatus.NO_SHARED_EDGES == "NO_SHARED_EDGES"

    def test_self_intersecting_value(self):
        assert MultiShoulderStatus.SELF_INTERSECTING == "SELF_INTERSECTING"

    def test_all_values_distinct(self):
        vals = list(MultiShoulderStatus)
        assert len(vals) == len(set(str(v) for v in vals))


# ===========================================================================
# TestFindSharedEdges
# ===========================================================================

class TestFindSharedEdges:
    def test_no_shared_edges_returns_empty(self):
        topo = _make_two_face_topo(lower_tag=1, wall_tag=2, shared_edges=[])
        shared = _find_shared_edges(1, 2, topo)
        assert shared == ()

    def test_one_shared_edge(self):
        topo = _make_two_face_topo(
            lower_tag=1, wall_tag=2,
            shared_edges=[("ES1", "VA", "VB")],
        )
        shared = _find_shared_edges(1, 2, topo)
        assert "ES1" in shared

    def test_three_shared_edges_closed_rectangle(self):
        # Simulate a 4-edge shared boundary (closed rectangle between lower+wall)
        topo = _make_two_face_topo(
            lower_tag=1, wall_tag=2,
            shared_edges=[
                ("ES1", "VA", "VB"),
                ("ES2", "VB", "VC"),
                ("ES3", "VC", "VD"),
                ("ES4", "VD", "VA"),
            ],
        )
        shared = _find_shared_edges(1, 2, topo)
        assert set(shared) == {"ES1", "ES2", "ES3", "ES4"}

    def test_absent_lower_face_returns_empty(self):
        topo = _empty_topo()
        shared = _find_shared_edges(99, 100, topo)
        assert shared == ()

    def test_absent_wall_face_returns_empty(self):
        topo = _make_two_face_topo(lower_tag=1, wall_tag=2, shared_edges=[])
        shared = _find_shared_edges(1, 999, topo)
        assert shared == ()

    def test_shared_edges_are_sorted(self):
        topo = _make_two_face_topo(
            lower_tag=1, wall_tag=2,
            shared_edges=[("EC3", "VA", "VB"), ("EC1", "VC", "VD"), ("EC2", "VE", "VF")],
        )
        shared = _find_shared_edges(1, 2, topo)
        assert list(shared) == sorted(shared)


# ===========================================================================
# TestClassifyShoulderBoundary
# ===========================================================================

class TestClassifyShoulderBoundary:
    def test_empty_edges_returns_no_shared(self):
        result = _classify_shoulder_boundary((), _empty_topo())
        assert result == MultiShoulderStatus.NO_SHARED_EDGES

    def test_closed_loop_returns_valid(self):
        # 4-edge rectangle: v1-v2-v3-v4-v1
        v1 = _v("V1", 0, 0)
        v2 = _v("V2", 10, 0)
        v3 = _v("V3", 10, 10)
        v4 = _v("V4", 0, 10)
        edges = (
            _e("E1", "V1", "V2"),
            _e("E2", "V2", "V3"),
            _e("E3", "V3", "V4"),
            _e("E4", "V4", "V1"),
        )
        topo = CanonicalTopology(
            topology_id="RECT",
            faces=(),
            loops=(),
            edges=edges,
            vertices=(v1, v2, v3, v4),
        )
        result = _classify_shoulder_boundary(("E1", "E2", "E3", "E4"), topo)
        assert result == MultiShoulderStatus.VALID_MULTI_FACE_SHOULDER

    def test_open_chain_returns_open_chain(self):
        # 3-edge open chain
        edges = (
            _e("E1", "VA", "VB"),
            _e("E2", "VB", "VC"),
            _e("E3", "VC", "VD"),  # doesn't return to VA
        )
        topo = CanonicalTopology(
            topology_id="OPEN",
            faces=(),
            loops=(),
            edges=edges,
            vertices=(_v("VA", 0, 0), _v("VB", 1, 0), _v("VC", 2, 0), _v("VD", 3, 0)),
        )
        result = _classify_shoulder_boundary(("E1", "E2", "E3"), topo)
        assert result == MultiShoulderStatus.OPEN_CHAIN


# ===========================================================================
# TestAssessShoulderCAM
# ===========================================================================

class TestAssessShoulderCAM:
    def _closed_rect_topo_two_faces(self, lower_tag: int, wall_tag: int) -> CanonicalTopology:
        """Make topology where lower+wall share a 4-edge closed rectangle."""
        v1 = _v("V1", 0, 0)
        v2 = _v("V2", 10, 0)
        v3 = _v("V3", 10, 5)
        v4 = _v("V4", 0, 5)
        shared = [_e("ES1", "V1", "V2"), _e("ES2", "V2", "V3"),
                  _e("ES3", "V3", "V4"), _e("ES4", "V4", "V1")]
        priv_l = [_e("EL1", "VLA", "VLB"), _e("EL2", "VLB", "VLA")]
        priv_w = [_e("EW1", "VWA", "VWB"), _e("EW2", "VWB", "VWA")]

        lower_eids = tuple(e.edge_id for e in shared + priv_l)
        wall_eids = tuple(e.edge_id for e in shared + priv_w)
        lower_loop = CanonicalLoop(loop_id=f"LL{lower_tag}", edge_ids=lower_eids,
                                   loop_type=LoopType.OUTER)
        wall_loop = CanonicalLoop(loop_id=f"WL{wall_tag}", edge_ids=wall_eids,
                                  loop_type=LoopType.OUTER)
        lower_face = CanonicalFace(face_id=f"F-{lower_tag}", surface_id="SL",
                                   boundary_loop_ids=(f"LL{lower_tag}",))
        wall_face = CanonicalFace(face_id=f"F-{wall_tag}", surface_id="SW",
                                  boundary_loop_ids=(f"WL{wall_tag}",))
        all_edges = shared + priv_l + priv_w
        all_verts = [v1, v2, v3, v4,
                     _v("VLA", 15, 0), _v("VLB", 15, 5),
                     _v("VWA", 20, 0), _v("VWB", 20, 5)]
        return CanonicalTopology(
            topology_id="CLOSED_RECT",
            faces=(lower_face, wall_face),
            loops=(lower_loop, wall_loop),
            edges=tuple(all_edges),
            vertices=tuple(all_verts),
        )

    def test_boundary_ready_when_shared_closed_loop(self):
        topo = self._closed_rect_topo_two_faces(lower_tag=1, wall_tag=2)
        s = _make_shoulder(lower_tag=1, wall_tag=2, upper_tag=3, step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.boundary_ready is True

    def test_depth_ready_when_step_height_positive(self):
        topo = self._closed_rect_topo_two_faces(1, 2)
        s = _make_shoulder(step_height_mm=3.5)
        result = assess_shoulder_cam(s, topo)
        assert result.depth_ready is True

    def test_depth_not_ready_when_step_height_none(self):
        topo = _empty_topo()
        s = _make_shoulder(step_height_mm=None)
        result = assess_shoulder_cam(s, topo)
        assert result.depth_ready is False

    def test_tool_ready_always_false_phase9(self):
        """Shoulder mill selection is deferred in Phase 9."""
        topo = self._closed_rect_topo_two_faces(1, 2)
        s = _make_shoulder(step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.tool_ready is False

    def test_toolpath_ready_always_false(self):
        """FEATURE_CONFIRMED=NO always; toolpath_ready must be False."""
        topo = self._closed_rect_topo_two_faces(1, 2)
        s = _make_shoulder(step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.toolpath_ready is False

    def test_cam_ready_requires_boundary_and_depth(self):
        topo = self._closed_rect_topo_two_faces(1, 2)
        s = _make_shoulder(step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.cam_ready is True  # boundary + depth (tool deferred)

    def test_cam_not_ready_when_no_boundary(self):
        topo = _empty_topo()
        s = _make_shoulder(step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.cam_ready is False

    def test_cam_not_ready_when_depth_none(self):
        topo = self._closed_rect_topo_two_faces(1, 2)
        s = _make_shoulder(step_height_mm=None)
        result = assess_shoulder_cam(s, topo)
        assert result.cam_ready is False

    def test_is_dispatchable_always_false(self):
        topo = _empty_topo()
        s = _make_shoulder()
        result = assess_shoulder_cam(s, topo)
        assert result.is_dispatchable is False

    def test_production_released_always_false(self):
        topo = _empty_topo()
        s = _make_shoulder()
        result = assess_shoulder_cam(s, topo)
        assert result.production_released is False


# ===========================================================================
# TestShoulderCAMResult
# ===========================================================================

class TestShoulderCAMResult:
    def test_empty_result_counts(self):
        r = ShoulderCAMResult()
        assert r.total_count == 0
        assert r.boundary_valid_count == 0
        assert r.cam_ready_count == 0
        assert r.toolpath_count == 0

    def test_toolpath_count_always_zero(self):
        r = ShoulderCAMResult()
        r.assessments.append(
            ShoulderCAMAssessment(
                shoulder_id="S1",
                lower_face_tag=1,
                wall_face_tag=2,
                upper_face_tag=3,
                edge_boundary=None,
                depth_mm=5.0,
                boundary_ready=True,
                depth_ready=True,
                tool_ready=False,
                cam_ready=True,
                toolpath_ready=False,
            )
        )
        assert r.toolpath_count == 0

    def test_is_dispatchable_false(self):
        r = ShoulderCAMResult()
        assert r.is_dispatchable is False

    def test_production_released_false(self):
        r = ShoulderCAMResult()
        assert r.production_released is False


# ===========================================================================
# TestDrillCycleAssessment
# ===========================================================================

class TestDrillCycleAssessment:
    def test_external_cylinder_blocked(self):
        cyl = _make_cyl(orientation=CylinderOrientation.EXTERNAL_CYLINDER, diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is False
        assert "NOT_INTERNAL_CYLINDER" in result.blocker

    def test_ambiguous_cylinder_blocked(self):
        cyl = _make_cyl(orientation=CylinderOrientation.AMBIGUOUS_CYLINDER, diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is False

    def test_non_z_axis_blocked(self):
        cyl = _make_cyl(axis_direction="X", diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.is_axial is False
        assert result.geometric_toolpath_ready is False
        assert "IS_AXIAL=NO" in result.blocker

    def test_no_wcs_blocked(self):
        cyl = _make_cyl(diameter_mm=8.0)
        result = assess_drill_cycle(cyl, None)
        assert result.wcs_ready is False
        assert result.geometric_toolpath_ready is False

    def test_catalog_gap_no_match(self):
        """2.5mm not in catalog → TOOL_CATALOG_GAP=True (7mm+9mm+20mm added in Phase 10)."""
        cyl = _make_cyl(diameter_mm=2.5)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is True
        assert result.tool_id is None
        assert result.geometric_toolpath_ready is False
        assert "TOOL_CATALOG_GAP" in result.blocker

    def test_parameterized_cam_ready_always_false(self):
        """MUST 19: parameterized_cam_ready=False always (Vc/fn not in scope)."""
        cyl = _make_cyl(diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.parameterized_cam_ready is False

    def test_is_dispatchable_always_false(self):
        cyl = _make_cyl(diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.is_dispatchable is False

    def test_production_released_always_false(self):
        cyl = _make_cyl(diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.production_released is False

    def test_8mm_z_axis_has_tool_match(self):
        """8mm drill exists in catalog — should match."""
        cyl = _make_cyl(diameter_mm=8.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is False
        assert result.tool_id is not None
        assert result.tool_match_type in ("EXACT_MATCH", "COMPATIBLE_MATCH")

    def test_8mm_z_axis_geometric_tp_ready(self):
        """8mm Z-axis + WCS + depth → geometric_toolpath_ready=True."""
        cyl = _make_cyl(diameter_mm=8.0, axis_direction="Z", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is True

    def test_depth_none_blocks_toolpath(self):
        cyl = _make_cyl(diameter_mm=8.0, axis_direction="Z", depth_mm=None)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.depth_ready is False
        assert result.geometric_toolpath_ready is False

    def test_unmatched_diameter_recorded_as_gap(self):
        # Phase 10: 7mm+9mm+20mm all matched. Remaining genuine gaps: 2.5mm, 10mm, 11mm.
        for dia in [2.5, 10.0, 11.0]:
            cyl = _make_cyl(diameter_mm=dia)
            result = assess_drill_cycle(cyl, _make_wcs())
            assert result.tool_catalog_gap is True, f"Expected gap for {dia}mm"


# ===========================================================================
# TestDrillCycleResult
# ===========================================================================

class TestDrillCycleResult:
    def test_empty_result(self):
        r = DrillCycleResult()
        assert r.total_candidates == 0
        assert r.tool_matched_count == 0
        assert r.tool_catalog_gap_count == 0
        assert r.geometric_toolpath_ready_count == 0
        assert r.parameterized_cam_ready_count == 0
        assert r.toolpath_count == 0

    def test_parameterized_always_zero(self):
        r = DrillCycleResult()
        assert r.parameterized_cam_ready_count == 0

    def test_is_dispatchable_false(self):
        r = DrillCycleResult()
        assert r.is_dispatchable is False

    def test_unique_unmatched_diameters_sorted(self):
        # Phase 10: 7mm+9mm+20mm all matched. Using 10mm and 11mm (both NO_MATCH).
        r = DrillCycleResult()
        for dia in [10.0, 11.0, 11.0, 2.5]:
            cyl = _make_cyl(diameter_mm=dia)
            r.assessments.append(assess_drill_cycle(cyl, _make_wcs()))
        gaps = r.unique_unmatched_diameters_mm
        assert gaps == sorted(gaps)
        assert 10.0 in gaps and 11.0 in gaps and 2.5 in gaps
        assert gaps.count(11.0) == 1  # deduped


# ===========================================================================
# TestPhase9E2ESafetyInvariants
# ===========================================================================

class TestPhase9E2ESafetyInvariants:
    def _make_e2e_result(self):
        from backend.step_brep.phase8_cam_e2e import (
            Phase8E2EResult,
        )
        p8 = MagicMock(spec=Phase8E2EResult)
        p8.wcs_ready = True
        p8.pocket_toolpath_count = 0
        p8.slot_toolpath_count = 0
        p8.step_toolpath_count = 0
        p8.drill_toolpath_count = 0
        p8.total_toolpath_count = 0
        p8.arc_map_faces_used = ()
        p8.step_boundary_ready_count = 0

        rec = _make_step_record()
        with (
            patch("backend.step_brep.phase9_cam_e2e.run_phase8_e2e", return_value=p8),
            patch(
                "backend.step_brep.phase9_cam_e2e.detect_step_shoulder_candidates",
                return_value=[],
            ),
            patch("backend.step_brep.phase9_cam_e2e.detect_oriented_cylinders", return_value=[]),
        ):
            from backend.step_brep.phase9_cam_e2e import run_phase9_e2e
            return run_phase9_e2e(rec, _empty_topo(), None)

    def test_is_dispatchable_false(self):
        r = self._make_e2e_result()
        assert r.is_dispatchable is False

    def test_production_released_false(self):
        r = self._make_e2e_result()
        assert r.production_released is False

    def test_review_required_true(self):
        r = self._make_e2e_result()
        assert r.review_required is True

    def test_real_machine_write_false(self):
        r = self._make_e2e_result()
        assert r.real_machine_write is False

    def test_auto_cnc_dispatch_false(self):
        r = self._make_e2e_result()
        assert r.auto_cnc_dispatch is False

    def test_auto_approval_false(self):
        r = self._make_e2e_result()
        assert r.auto_approval is False

    def test_automatic_adaptation_false(self):
        r = self._make_e2e_result()
        assert r.automatic_adaptation is False

    def test_p9b_shoulder_toolpath_always_zero(self):
        r = self._make_e2e_result()
        assert r.p9b_shoulder_toolpath_count == 0

    def test_p9c_parameterized_cam_ready_always_zero(self):
        r = self._make_e2e_result()
        assert r.p9c_drill_parameterized_cam_ready == 0


# ===========================================================================
# TestPhase9FalsePositive (MUST 35/36)
# ===========================================================================

class TestPhase9FalsePositive:
    def test_shoulder_toolpath_never_generated_even_with_all_conditions(self):
        """Even with boundary+depth ready, shoulder toolpath_ready must be False."""
        helper = TestAssessShoulderCAM()
        topo = helper._closed_rect_topo_two_faces(1, 2)
        s = _make_shoulder(step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        # Even with boundary_ready=True, depth_ready=True, cam_ready=True:
        assert result.toolpath_ready is False
        assert result.is_dispatchable is False

    def test_external_cylinder_never_drilled(self):
        cyl = _make_cyl(orientation=CylinderOrientation.EXTERNAL_CYLINDER, diameter_mm=8.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.toolpath is None
        assert result.geometric_toolpath_ready is False

    def test_unmatched_diameter_never_fabricates_toolpath(self):
        """Catalog gap must never produce a toolpath via fabrication.
        Phase 10: 7mm+9mm+20mm all added; use 2.5mm (still a genuine gap)."""
        cyl = _make_cyl(diameter_mm=2.5, axis_direction="Z", depth_mm=16.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.tool_catalog_gap is True
        assert result.toolpath is None

    def test_non_z_axis_blocked_regardless_of_tool(self):
        """Non-Z axis hole must NOT generate toolpath even if tool exists."""
        cyl = _make_cyl(diameter_mm=8.0, axis_direction="X", depth_mm=20.0)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.geometric_toolpath_ready is False
        assert result.toolpath is None

    def test_shoulder_blocker_always_set(self):
        """Every ShoulderCAMAssessment must have a blocker string explaining the gate."""
        topo = _empty_topo()
        s = _make_shoulder(step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.blocker != ""


# ===========================================================================
# TestPhase9NegativeCases
# ===========================================================================

class TestPhase9NegativeCases:
    def test_no_topo_returns_empty_shoulder_result(self):
        from backend.step_brep.phase9_cam_e2e import _run_shoulder_cam
        rec = _make_step_record()
        result = _run_shoulder_cam(rec, None)
        assert result.total_count == 0

    def test_no_internal_cylinders_returns_empty_drill_result(self):
        from backend.step_brep.phase9_cam_e2e import _run_drill_cycle
        rec = _make_step_record()
        with patch("backend.step_brep.phase9_cam_e2e.detect_oriented_cylinders", return_value=[]):
            result = _run_drill_cycle(rec)
        assert result.total_candidates == 0

    def test_missing_depth_blocks_drill_toolpath(self):
        cyl = _make_cyl(diameter_mm=8.0, axis_direction="Z", depth_mm=None)
        result = assess_drill_cycle(cyl, _make_wcs())
        assert result.toolpath is None
        assert "DEPTH_READY=NO" in result.blocker

    def test_shoulder_no_shared_edges_reports_correctly(self):
        topo = _empty_topo()
        s = _make_shoulder(lower_tag=1, wall_tag=2, step_height_mm=5.0)
        result = assess_shoulder_cam(s, topo)
        assert result.boundary_ready is False
        assert result.edge_boundary is not None
        from backend.step_brep.phase9_shoulder_cam import MultiShoulderStatus
        assert result.edge_boundary.boundary_status == MultiShoulderStatus.NO_SHARED_EDGES
