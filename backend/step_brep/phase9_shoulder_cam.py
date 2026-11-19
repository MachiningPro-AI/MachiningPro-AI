"""
Phase 9B: Multi-face shoulder boundary extraction and CAM assessment.

Extends Phase 8 step/shoulder work by extracting the SHOULDER EDGE
(shared between lower_face and wall_face) rather than the lower_face
outer perimeter.  This edge is the actual milling contour for a
shoulder/profile milling operation.

SAFETY RULES (MUST 11–15):
  - FEATURE_CONFIRMED=YES is required before any toolpath is generated.
  - Phase 9 never auto-confirms CANDIDATE features.
  - Multi-face shoulder tracing uses ONLY the canonical topology; no
    second topology graph, no proximity inference, no gap bridging.
  - TOOLPATH_READY=False always.

HARD INVARIANTS:
  IS_DISPATCHABLE=False
  PRODUCTION_RELEASED=False
  REVIEW_REQUIRED=True
  TOOLPATH_READY=False
  AUTO_CONFIRMATION=False
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.interoperability.topology import CanonicalTopology
from backend.step_brep.phase5_feature_detector import StepShoulderRecord
from backend.step_brep.phase8_contour_extractor import (
    BoundaryTraversalStatus,
    _classify_traversal,
)

__all__ = [
    "MultiShoulderStatus",
    "ShoulderEdgeBoundary",
    "ShoulderCAMAssessment",
    "ShoulderCAMResult",
    "assess_shoulder_cam",
    "P9B_IS_DISPATCHABLE",
    "P9B_PRODUCTION_RELEASED",
    "P9B_TOOLPATH_READY",
    "P9B_AUTO_CONFIRMATION",
]

P9B_IS_DISPATCHABLE: bool = False
P9B_PRODUCTION_RELEASED: bool = False
P9B_TOOLPATH_READY: bool = False
P9B_AUTO_CONFIRMATION: bool = False


class MultiShoulderStatus(StrEnum):
    """Multi-face shoulder boundary classification (MUST 12)."""

    VALID_MULTI_FACE_SHOULDER = "VALID_MULTI_FACE_SHOULDER"
    OPEN_CHAIN = "OPEN_CHAIN"
    DISCONNECTED = "DISCONNECTED"
    BRANCHED = "BRANCHED"
    SELF_INTERSECTING = "SELF_INTERSECTING"
    AMBIGUOUS = "AMBIGUOUS"
    NO_SHARED_EDGES = "NO_SHARED_EDGES"


@dataclass(frozen=True)
class ShoulderEdgeBoundary:
    """Extracted boundary from the shared edges of lower_face and wall_face.

    boundary_ready=True iff the shared edges form a VALID_MULTI_FACE_SHOULDER
    (connected closed loop, degree ≤ 2 at every vertex).
    """

    shoulder_id: str
    lower_face_tag: int
    wall_face_tag: int
    shared_edge_ids: tuple[str, ...]
    boundary_status: MultiShoulderStatus
    boundary_ready: bool


@dataclass(frozen=True)
class ShoulderCAMAssessment:
    """CAM readiness for a single step/shoulder feature via multi-face tracing.

    toolpath_ready is ALWAYS False — FEATURE_CONFIRMED=YES is required (MUST 15).
    cam_ready indicates all geometric pre-conditions are met but the CANDIDATE
    gate still blocks toolpath generation.

    is_dispatchable=False and production_released=False always.
    """

    shoulder_id: str
    lower_face_tag: int
    wall_face_tag: int
    upper_face_tag: int
    edge_boundary: ShoulderEdgeBoundary | None
    depth_mm: float | None
    # Readiness flags
    boundary_ready: bool
    depth_ready: bool
    tool_ready: bool   # NOT_IMPLEMENTED in Phase 9 (shoulder mill selection deferred)
    cam_ready: bool    # boundary_ready and depth_ready (tool_ready deferred)
    toolpath_ready: bool   # always False
    # Safety
    is_dispatchable: bool = field(default=P9B_IS_DISPATCHABLE)
    production_released: bool = field(default=P9B_PRODUCTION_RELEASED)
    blocker: str = ""


@dataclass
class ShoulderCAMResult:
    """Aggregate Phase 9B result for all step/shoulder features in a file."""

    assessments: list[ShoulderCAMAssessment] = field(default_factory=list)
    is_dispatchable: bool = P9B_IS_DISPATCHABLE
    production_released: bool = P9B_PRODUCTION_RELEASED

    @property
    def total_count(self) -> int:
        return len(self.assessments)

    @property
    def boundary_valid_count(self) -> int:
        return sum(
            1 for a in self.assessments
            if a.edge_boundary is not None
            and a.edge_boundary.boundary_status == MultiShoulderStatus.VALID_MULTI_FACE_SHOULDER
        )

    @property
    def depth_ready_count(self) -> int:
        return sum(1 for a in self.assessments if a.depth_ready)

    @property
    def cam_ready_count(self) -> int:
        return sum(1 for a in self.assessments if a.cam_ready)

    @property
    def toolpath_count(self) -> int:
        return 0   # always 0 in Phase 9


def _face_edge_ids(face_tag: int, topo: CanonicalTopology) -> set[str]:
    """Return all edge IDs referenced by any loop of the given face."""
    lmap = {lp.loop_id: lp for lp in topo.loops}
    face = next((f for f in topo.faces if f.face_id == f"F-{face_tag}"), None)
    if face is None:
        return set()
    eids: set[str] = set()
    for lid in face.boundary_loop_ids:
        lp = lmap.get(lid)
        if lp:
            eids.update(lp.edge_ids)
    return eids


def _find_shared_edges(
    lower_face_tag: int,
    wall_face_tag: int,
    topo: CanonicalTopology,
) -> tuple[str, ...]:
    """Return edge IDs shared between lower_face and wall_face.

    Uses set intersection on existing topology — no second graph (MUST 10).
    Cannot infer missing edges from proximity (MUST 13).
    """
    return tuple(sorted(
        _face_edge_ids(lower_face_tag, topo) & _face_edge_ids(wall_face_tag, topo)
    ))


def _classify_shoulder_boundary(
    shared_edge_ids: tuple[str, ...],
    topo: CanonicalTopology,
) -> MultiShoulderStatus:
    """Classify multi-face shoulder boundary from shared edges.

    Uses the Phase 8 undirected graph traversal.
    Maps BoundaryTraversalStatus → MultiShoulderStatus.
    """
    if not shared_edge_ids:
        return MultiShoulderStatus.NO_SHARED_EDGES

    emap = {e.edge_id: (e.start_vertex_id, e.end_vertex_id) for e in topo.edges}

    traversal = _classify_traversal(shared_edge_ids, emap)

    mapping = {
        BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP: (
            MultiShoulderStatus.VALID_MULTI_FACE_SHOULDER
        ),
        BoundaryTraversalStatus.CONNECTED_OPEN_CHAIN: MultiShoulderStatus.OPEN_CHAIN,
        BoundaryTraversalStatus.DISCONNECTED: MultiShoulderStatus.DISCONNECTED,
        BoundaryTraversalStatus.BRANCHED: MultiShoulderStatus.BRANCHED,
        BoundaryTraversalStatus.AMBIGUOUS: MultiShoulderStatus.AMBIGUOUS,
    }
    return mapping.get(traversal, MultiShoulderStatus.AMBIGUOUS)


def _extract_shoulder_edge_boundary(
    shoulder_id: str,
    lower_face_tag: int,
    wall_face_tag: int,
    topo: CanonicalTopology,
) -> ShoulderEdgeBoundary:
    """Extract and classify the shoulder edge boundary."""
    shared = _find_shared_edges(lower_face_tag, wall_face_tag, topo)
    status = _classify_shoulder_boundary(shared, topo)
    return ShoulderEdgeBoundary(
        shoulder_id=shoulder_id,
        lower_face_tag=lower_face_tag,
        wall_face_tag=wall_face_tag,
        shared_edge_ids=shared,
        boundary_status=status,
        boundary_ready=(status == MultiShoulderStatus.VALID_MULTI_FACE_SHOULDER),
    )


def assess_shoulder_cam(
    step_rec: StepShoulderRecord,
    topo: CanonicalTopology,
    idx: int = 0,
) -> ShoulderCAMAssessment:
    """Assess CAM readiness for a single step/shoulder feature via multi-face tracing.

    boundary_ready: shared edge forms a VALID_MULTI_FACE_SHOULDER.
    depth_ready: step_height_mm is not None and > 0.
    tool_ready: NOT_IMPLEMENTED in Phase 9 (shoulder mill selection deferred).
    cam_ready: boundary_ready and depth_ready (tool_ready deferred).
    toolpath_ready: ALWAYS False — FEATURE_CONFIRMED=YES required (MUST 15).
    """
    shoulder_id = f"P9B-SHOULDER-{idx}-L{step_rec.lower_face_tag}-W{step_rec.wall_face_tag}"

    edge_boundary = _extract_shoulder_edge_boundary(
        shoulder_id=shoulder_id,
        lower_face_tag=step_rec.lower_face_tag,
        wall_face_tag=step_rec.wall_face_tag,
        topo=topo,
    )

    boundary_ready = edge_boundary.boundary_ready
    depth_ready = (
        step_rec.step_height_mm is not None and step_rec.step_height_mm > 0.0
    )
    tool_ready = False  # NOT_IMPLEMENTED: shoulder mill selection not in Phase 9

    cam_ready = boundary_ready and depth_ready  # tool_ready deferred

    # Determine primary blocker
    if not boundary_ready:
        blocker = (
            f"BOUNDARY_READY=NO: shoulder_boundary_status="
            f"{edge_boundary.boundary_status.value}"
        )
    elif not depth_ready:
        blocker = "DEPTH_READY=NO: step_height_mm not available"
    else:
        # boundary + depth ready, tool deferred, feature never auto-confirmed
        blocker = (
            "TOOLPATH_READY=NO: FEATURE_CONFIRMED=NO (CANDIDATE never auto-confirmed)"
        )

    return ShoulderCAMAssessment(
        shoulder_id=shoulder_id,
        lower_face_tag=step_rec.lower_face_tag,
        wall_face_tag=step_rec.wall_face_tag,
        upper_face_tag=step_rec.upper_face_tag,
        edge_boundary=edge_boundary,
        depth_mm=step_rec.step_height_mm,
        boundary_ready=boundary_ready,
        depth_ready=depth_ready,
        tool_ready=tool_ready,
        cam_ready=cam_ready,
        toolpath_ready=False,  # always
        blocker=blocker,
    )
