"""
Phase 8: Extended contour extractor with boundary traversal classification.

Extends Phase 7 contour extraction with:
  - BoundaryTraversalStatus classification (MUST 5)
  - Arc-point map support for 2-arc closed faces (MUST 10-15)
  - Connectivity sorting for scrambled polygon edges (MUST 7)
  - BOUNDARY_METHOD tracking: EXACT vs APPROXIMATED (MUST 12)
  - Disconnected/branched boundary detection (MUST 41)

HARD RULES (MUST 6, MUST 13, MUST 14):
  - No geometric gap healing.
  - An arc must not be treated as a full circle.
  - Full-circle acceptance requires topological proof of closure.
  - NURBS/freeform boundaries: AMBIGUOUS unless connectivity proven.
  - Approximated boundaries: BOUNDARY_METHOD=APPROXIMATED, never exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.interoperability.topology import CanonicalTopology, LoopType
from backend.step_brep.phase7_contour_extractor import (
    ContourType,
    ManufacturingContour,
    _build_maps,
    _extract_contour_from_loop,
    _orientation_ccw_or_cw,
    _project_to_2d,
    _shoelace_area,
)
from backend.step_brep.phase8_arc_sampler import (
    ARC_APPROXIMATION_RESOLUTION,
    ARC_APPROXIMATION_TOLERANCE_MM,
    ARC_BOUNDARY_METHOD,
    ArcContourMap,
)

__all__ = [
    "BoundaryTraversalStatus",
    "Phase8Contour",
    "extract_face_contour_p8",
    "P8_AMBIGUOUS_CONTOUR_AUTO_USED",
    "P8_OPEN_LOOP_USED_FOR_CAM",
    "P8_DISCONNECTED_BOUNDARY_USED_FOR_CAM",
]

P8_AMBIGUOUS_CONTOUR_AUTO_USED: bool = False
P8_OPEN_LOOP_USED_FOR_CAM: bool = False
P8_DISCONNECTED_BOUNDARY_USED_FOR_CAM: bool = False


class BoundaryTraversalStatus(StrEnum):
    """Topological status of a proposed manufacturing loop (MUST 5)."""

    CONNECTED_CLOSED_LOOP = "CONNECTED_CLOSED_LOOP"
    CONNECTED_OPEN_CHAIN = "CONNECTED_OPEN_CHAIN"
    DISCONNECTED = "DISCONNECTED"
    BRANCHED = "BRANCHED"
    AMBIGUOUS = "AMBIGUOUS"


@dataclass(frozen=True)
class Phase8Contour:
    """Extended contour with Phase 8 traversal classification.

    boundary_method: 'EXACT' (from canonical topology) or 'APPROXIMATED'
    (from arc-bbox sampling).
    Only CONNECTED_CLOSED_LOOP with is_valid=True may become BOUNDARY_READY=YES.
    """

    contour: ManufacturingContour
    traversal_status: BoundaryTraversalStatus
    boundary_method: str
    approximation_tolerance_mm: float | None
    approximation_resolution: int | None


def _classify_traversal(
    edge_ids: tuple[str, ...],
    emap: dict[str, tuple[str, str]],
) -> BoundaryTraversalStatus:
    """Classify the traversal status of an edge set using undirected graph walk.

    Topology edges have stored start/end vertex IDs, but their orientation is
    not guaranteed to follow a consistent polygon winding.  This function builds
    an UNDIRECTED vertex adjacency graph and walks from any start vertex.

    Detects:
      - CONNECTED_CLOSED_LOOP: all edges traversed, ends back at start
      - CONNECTED_OPEN_CHAIN: all edges traversed, path is open
      - DISCONNECTED: at least one component is unreachable
      - BRANCHED: a vertex has degree > 2 (topology junction)
    """
    if not edge_ids:
        return BoundaryTraversalStatus.DISCONNECTED

    resolved = {eid: emap[eid] for eid in edge_ids if eid in emap}
    if len(resolved) < len(edge_ids):
        return BoundaryTraversalStatus.DISCONNECTED

    if len(resolved) < 2:
        return BoundaryTraversalStatus.CONNECTED_OPEN_CHAIN

    # Build UNDIRECTED adjacency: vertex → list of (neighbor_vertex, edge_id)
    adj: dict[str, list[tuple[str, str]]] = {}
    for eid, (sv, ev) in resolved.items():
        adj.setdefault(sv, []).append((ev, eid))
        adj.setdefault(ev, []).append((sv, eid))

    # Branching: any vertex with degree > 2
    for _v, neighbors in adj.items():
        if len(neighbors) > 2:
            return BoundaryTraversalStatus.BRANCHED

    # Walk from the first edge's start vertex
    start_v = resolved[edge_ids[0]][0]
    prev_v: str | None = None
    current_v = start_v
    visited_edges: set[str] = set()

    for _ in range(len(resolved)):
        candidates = [
            (nv, eid)
            for nv, eid in adj.get(current_v, [])
            if eid not in visited_edges
        ]
        if not candidates:
            break
        # Prefer the neighbor that is NOT where we came from
        forward = [(nv, eid) for nv, eid in candidates if nv != prev_v]
        nv, eid = (forward or candidates)[0]
        visited_edges.add(eid)
        prev_v = current_v
        current_v = nv
        if current_v == start_v:
            break  # closed loop found

    if len(visited_edges) < len(resolved):
        return BoundaryTraversalStatus.DISCONNECTED

    if current_v == start_v:
        return BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP
    return BoundaryTraversalStatus.CONNECTED_OPEN_CHAIN


def _sort_edges_by_connectivity(
    edge_ids: tuple[str, ...],
    emap: dict[str, tuple[str, str]],
) -> tuple[str, ...]:
    """Return edge_ids sorted into a connected undirected chain, if possible.

    Uses undirected adjacency to walk the polygon boundary.  Returns the
    original order unchanged if the chain cannot be completed (disconnected,
    branched, or too few edges).
    """
    resolved = {eid: emap[eid] for eid in edge_ids if eid in emap}
    if len(resolved) < 3:
        return edge_ids

    # Undirected adjacency: vertex → list of (neighbor, edge_id)
    adj: dict[str, list[tuple[str, str]]] = {}
    for eid, (sv, ev) in resolved.items():
        adj.setdefault(sv, []).append((ev, eid))
        adj.setdefault(ev, []).append((sv, eid))

    # Only attempt sort when every vertex has degree ≤ 2
    if any(len(nbrs) > 2 for nbrs in adj.values()):
        return edge_ids

    start_v = resolved[edge_ids[0]][0]
    ordered: list[str] = []
    prev_v: str | None = None
    current_v = start_v
    seen_edges: set[str] = set()

    for _ in range(len(resolved)):
        candidates = [
            (nv, eid)
            for nv, eid in adj.get(current_v, [])
            if eid not in seen_edges
        ]
        if not candidates:
            break
        forward = [(nv, eid) for nv, eid in candidates if nv != prev_v]
        nv, eid = (forward or candidates)[0]
        ordered.append(eid)
        seen_edges.add(eid)
        prev_v = current_v
        current_v = nv

    if len(ordered) == len(resolved):
        return tuple(ordered)
    return edge_ids  # fell short — return original


def _contour_from_arc_points(
    face_tag: int,
    pts3d: list[tuple[float, float, float]],
    face_normal: tuple[float, float, float],
) -> ManufacturingContour:
    """Build a ManufacturingContour from arc-sampled 3D points.

    BOUNDARY_METHOD: APPROXIMATED — not exact topology.
    """
    if len(pts3d) < 3:
        return ManufacturingContour(
            contour_id=f"CONTOUR-ARC-F{face_tag}",
            face_tag=face_tag,
            face_id=f"F-{face_tag}",
            loop_id=f"ARC-LOOP-F{face_tag}",
            edge_ids=(),
            points_2d=(),
            points_3d=(),
            contour_type=ContourType.OPEN_CHAIN,
            is_closed=False,
            area_mm2=0.0,
            orientation="UNKNOWN",
            face_normal=face_normal,
            source_provenance="ARC_BBOX_SAMPLED",
            is_valid=False,
            validation_notes="INSUFFICIENT_ARC_POINTS",
        )

    pts2d = _project_to_2d(pts3d, face_normal)
    area = _shoelace_area(pts2d)
    is_valid = area >= 1e-6

    return ManufacturingContour(
        contour_id=f"CONTOUR-ARC-F{face_tag}",
        face_tag=face_tag,
        face_id=f"F-{face_tag}",
        loop_id=f"ARC-LOOP-F{face_tag}",
        edge_ids=(),
        points_2d=tuple(pts2d),
        points_3d=tuple(pts3d),
        contour_type=ContourType.OUTER_LOOP,
        is_closed=True,
        area_mm2=area,
        orientation=_orientation_ccw_or_cw(pts2d),
        face_normal=face_normal,
        source_provenance="ARC_BBOX_SAMPLED",
        is_valid=is_valid,
        validation_notes="OK_APPROXIMATED" if is_valid else "ZERO_AREA_ARC",
    )


def extract_face_contour_p8(
    face_tag: int,
    topo: CanonicalTopology,
    arc_map: ArcContourMap | None = None,
    face_normal: tuple[float, float, float] | None = None,
) -> Phase8Contour | None:
    """Extract the outer-loop contour of a face using Phase 8 improvements.

    Tries in order:
      1. Canonical topology OUTER loop (exact).
      2. Arc-contour map (approximated, 2-arc closed faces).

    Returns None if no contour can be extracted.

    BOUNDARY_METHOD=EXACT for topology-derived contours.
    BOUNDARY_METHOD=APPROXIMATED for arc-sampled contours.

    For OUTER loops: attempts connectivity sorting to fix scrambled polygons.
    Reports BoundaryTraversalStatus for every result.
    """
    fn = face_normal or (0.0, 0.0, 1.0)
    vmap, emap = _build_maps(topo)
    lmap = {lp.loop_id: lp for lp in topo.loops}

    face_id = f"F-{face_tag}"
    face = next((f for f in topo.faces if f.face_id == face_id), None)

    if face is not None:
        for lid in face.boundary_loop_ids:
            if lid not in lmap:
                continue
            lp = lmap[lid]
            if lp.loop_type != LoopType.OUTER:
                continue

            # Attempt connectivity sort to fix scrambled polygon order
            sorted_eids = _sort_edges_by_connectivity(lp.edge_ids, emap)

            # Classify traversal status
            traversal = _classify_traversal(sorted_eids, emap)

            if traversal == BoundaryTraversalStatus.DISCONNECTED:
                # Return blocked contour so caller gets the DISCONNECTED info
                blocked = ManufacturingContour(
                    contour_id=f"CONTOUR-{face_id}-{lid}",
                    face_tag=face_tag,
                    face_id=face_id,
                    loop_id=lid,
                    edge_ids=sorted_eids,
                    points_2d=(),
                    points_3d=(),
                    contour_type=ContourType.OPEN_CHAIN,
                    is_closed=False,
                    area_mm2=0.0,
                    orientation="UNKNOWN",
                    face_normal=fn,
                    source_provenance="TOPOLOGY_DERIVED",
                    is_valid=False,
                    validation_notes="DISCONNECTED_BOUNDARY: edges do not form a connected chain",
                )
                return Phase8Contour(
                    contour=blocked,
                    traversal_status=traversal,
                    boundary_method="EXACT",
                    approximation_tolerance_mm=None,
                    approximation_resolution=None,
                )

            # Build a temporary loop with sorted edges for extraction
            from backend.interoperability.topology import CanonicalLoop
            try:
                sorted_loop = CanonicalLoop(
                    loop_id=lid,
                    edge_ids=sorted_eids,
                    loop_type=LoopType.OUTER,
                    source_entity_ref=lp.source_entity_ref,
                )
            except Exception:
                sorted_loop = lp  # fall back to original

            c = _extract_contour_from_loop(
                face_tag=face_tag,
                face_id=face_id,
                loop_id=lid,
                loop_edge_ids=sorted_loop.edge_ids,
                loop_type=LoopType.OUTER,
                face_normal=fn,
                vertex_map=vmap,
                edge_map=emap,
            )
            if traversal != BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP:
                # Was classified open/branched after sorting — downgrade validity
                c = ManufacturingContour(
                    contour_id=c.contour_id,
                    face_tag=c.face_tag,
                    face_id=c.face_id,
                    loop_id=c.loop_id,
                    edge_ids=c.edge_ids,
                    points_2d=c.points_2d,
                    points_3d=c.points_3d,
                    contour_type=ContourType.OPEN_CHAIN,
                    is_closed=False,
                    area_mm2=c.area_mm2,
                    orientation=c.orientation,
                    face_normal=c.face_normal,
                    source_provenance=c.source_provenance,
                    is_valid=False,
                    validation_notes=f"TRAVERSAL={traversal.value}",
                )
            return Phase8Contour(
                contour=c,
                traversal_status=traversal,
                boundary_method="EXACT",
                approximation_tolerance_mm=None,
                approximation_resolution=None,
            )

    # Face not in topology — try arc-contour map (MUST 12 APPROXIMATED path)
    if arc_map and face_tag in arc_map:
        pts3d = arc_map[face_tag]
        c = _contour_from_arc_points(face_tag, pts3d, fn)
        traversal = (
            BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP
            if c.is_valid
            else BoundaryTraversalStatus.DISCONNECTED
        )
        return Phase8Contour(
            contour=c,
            traversal_status=traversal,
            boundary_method=ARC_BOUNDARY_METHOD,
            approximation_tolerance_mm=ARC_APPROXIMATION_TOLERANCE_MM,
            approximation_resolution=ARC_APPROXIMATION_RESOLUTION,
        )

    return None
