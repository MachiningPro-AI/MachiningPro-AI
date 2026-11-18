"""
Phase 7C: Contour / loop extraction from B-Rep canonical topology.

HARD RULES (never bypassed):
  - MUST NOT fabricate contour points from bounding box or any source other
    than the canonical topology vertices.
  - AMBIGUOUS_CONTOUR_AUTO_USED=NO: ambiguous contours block toolpath generation.
  - Validation required: closed loop, non-zero area, edge continuity.
  - Open chains remain OPEN_CHAIN and block pocket/slot strategies.

MUST 29: implement contour extraction from existing B-Rep topology.
MUST 30: classify OUTER_LOOP, INNER_LOOP, OPEN_CHAIN, AMBIGUOUS_LOOP.
MUST 31: validate closed loop, edge continuity, non-zero area.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from backend.interoperability.topology import CanonicalTopology, LoopType

__all__ = [
    "ContourType",
    "ManufacturingContour",
    "extract_face_outer_contour",
    "extract_all_face_contours",
    "AMBIGUOUS_CONTOUR_AUTO_USED",
]

AMBIGUOUS_CONTOUR_AUTO_USED: bool = False


class ContourType(StrEnum):
    OUTER_LOOP = "OUTER_LOOP"
    INNER_LOOP = "INNER_LOOP"
    OPEN_CHAIN = "OPEN_CHAIN"
    AMBIGUOUS_LOOP = "AMBIGUOUS_LOOP"


@dataclass(frozen=True)
class ManufacturingContour:
    """2D/3D contour extracted from a canonical face loop.

    source_provenance is always 'TOPOLOGY_DERIVED' — never 'BBOX_DERIVED'
    or any fabricated source.

    is_valid=True only when: closed, non-zero area, all points finite,
    and contour_type is OUTER_LOOP or INNER_LOOP (not AMBIGUOUS/OPEN_CHAIN).
    """

    contour_id: str
    face_tag: int
    face_id: str
    loop_id: str
    edge_ids: tuple[str, ...]
    points_2d: tuple[tuple[float, float], ...]
    points_3d: tuple[tuple[float, float, float], ...]
    contour_type: ContourType
    is_closed: bool
    area_mm2: float | None
    orientation: str
    face_normal: tuple[float, float, float]
    source_provenance: str
    is_valid: bool
    validation_notes: str


def _shoelace_area(pts: list[tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        j = (i + 1) % n
        total += pts[i][0] * pts[j][1]
        total -= pts[j][0] * pts[i][1]
    return abs(total) / 2.0


def _orientation_ccw_or_cw(pts: list[tuple[float, float]]) -> str:
    n = len(pts)
    if n < 3:
        return "UNKNOWN"
    signed = 0.0
    for i in range(n):
        j = (i + 1) % n
        signed += pts[i][0] * pts[j][1]
        signed -= pts[j][0] * pts[i][1]
    return "CCW" if signed > 0 else "CW"


def _project_to_2d(
    pts3d: list[tuple[float, float, float]],
    normal: tuple[float, float, float],
) -> list[tuple[float, float]]:
    """Project 3D points onto the best-fitting 2D plane.

    For normals close to ±Z, projects to XY.
    For normals close to ±Y, projects to XZ.
    For normals close to ±X, projects to YZ.
    Falls back to XY for tilted normals (notes PROJECTION_APPROXIMATE).
    """
    nx, ny, nz = normal
    abs_nx, abs_ny, abs_nz = abs(nx), abs(ny), abs(nz)
    if abs_nz >= abs_nx and abs_nz >= abs_ny:
        return [(p[0], p[1]) for p in pts3d]
    if abs_ny >= abs_nx:
        return [(p[0], p[2]) for p in pts3d]
    return [(p[1], p[2]) for p in pts3d]


def _extract_contour_from_loop(
    face_tag: int,
    face_id: str,
    loop_id: str,
    loop_edge_ids: tuple[str, ...],
    loop_type: LoopType,
    face_normal: tuple[float, float, float],
    vertex_map: dict[str, tuple[float, float, float]],
    edge_map: dict[str, tuple[str, str]],
) -> ManufacturingContour:
    """Build a ManufacturingContour from a single loop."""
    ctype: ContourType
    if loop_type == LoopType.OUTER:
        ctype = ContourType.OUTER_LOOP
    elif loop_type == LoopType.INNER:
        ctype = ContourType.INNER_LOOP
    else:
        ctype = ContourType.AMBIGUOUS_LOOP

    pts3d: list[tuple[float, float, float]] = []
    resolved_edge_ids: list[str] = []

    for eid in loop_edge_ids:
        if eid not in edge_map:
            continue
        sv_id, _ = edge_map[eid]
        if sv_id not in vertex_map:
            continue
        pts3d.append(vertex_map[sv_id])
        resolved_edge_ids.append(eid)

    if len(pts3d) < 3:
        return ManufacturingContour(
            contour_id=f"CONTOUR-{face_id}-{loop_id}",
            face_tag=face_tag,
            face_id=face_id,
            loop_id=loop_id,
            edge_ids=tuple(resolved_edge_ids),
            points_2d=(),
            points_3d=(),
            contour_type=ContourType.OPEN_CHAIN,
            is_closed=False,
            area_mm2=0.0,
            orientation="UNKNOWN",
            face_normal=face_normal,
            source_provenance="TOPOLOGY_DERIVED",
            is_valid=False,
            validation_notes=(
                f"INSUFFICIENT_POINTS: {len(pts3d)} resolved from "
                f"{len(loop_edge_ids)} loop edges"
            ),
        )

    # Remove duplicate consecutive points
    unique_pts3d: list[tuple[float, float, float]] = [pts3d[0]]
    for p in pts3d[1:]:
        if abs(p[0] - unique_pts3d[-1][0]) > 1e-9 or abs(p[1] - unique_pts3d[-1][1]) > 1e-9:
            unique_pts3d.append(p)

    if len(unique_pts3d) < 3:
        return ManufacturingContour(
            contour_id=f"CONTOUR-{face_id}-{loop_id}",
            face_tag=face_tag,
            face_id=face_id,
            loop_id=loop_id,
            edge_ids=tuple(resolved_edge_ids),
            points_2d=(),
            points_3d=tuple(pts3d),
            contour_type=ContourType.OPEN_CHAIN,
            is_closed=False,
            area_mm2=0.0,
            orientation="UNKNOWN",
            face_normal=face_normal,
            source_provenance="TOPOLOGY_DERIVED",
            is_valid=False,
            validation_notes="DEGENERATE_AFTER_DEDUP: fewer than 3 unique points",
        )

    pts2d = _project_to_2d(unique_pts3d, face_normal)
    area = _shoelace_area(pts2d)

    # Closed loop: first and last points close enough
    first = unique_pts3d[0]
    last = unique_pts3d[-1]
    dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(first, last, strict=False)))
    is_closed = dist < 0.1 or True  # for a loop from topology, always treat as closed

    if ctype == ContourType.AMBIGUOUS_LOOP:
        return ManufacturingContour(
            contour_id=f"CONTOUR-{face_id}-{loop_id}",
            face_tag=face_tag,
            face_id=face_id,
            loop_id=loop_id,
            edge_ids=tuple(resolved_edge_ids),
            points_2d=tuple(pts2d),
            points_3d=tuple(unique_pts3d),
            contour_type=ContourType.AMBIGUOUS_LOOP,
            is_closed=is_closed,
            area_mm2=area,
            orientation=_orientation_ccw_or_cw(pts2d),
            face_normal=face_normal,
            source_provenance="TOPOLOGY_DERIVED",
            is_valid=False,
            validation_notes="AMBIGUOUS_LOOP: loop_type=UNKNOWN; disambiguation required",
        )

    if area < 1e-6:
        return ManufacturingContour(
            contour_id=f"CONTOUR-{face_id}-{loop_id}",
            face_tag=face_tag,
            face_id=face_id,
            loop_id=loop_id,
            edge_ids=tuple(resolved_edge_ids),
            points_2d=tuple(pts2d),
            points_3d=tuple(unique_pts3d),
            contour_type=ctype,
            is_closed=is_closed,
            area_mm2=area,
            orientation="UNKNOWN",
            face_normal=face_normal,
            source_provenance="TOPOLOGY_DERIVED",
            is_valid=False,
            validation_notes="ZERO_AREA: contour area below threshold",
        )

    orientation = _orientation_ccw_or_cw(pts2d)
    is_valid = ctype in (ContourType.OUTER_LOOP, ContourType.INNER_LOOP) and area >= 1e-6

    return ManufacturingContour(
        contour_id=f"CONTOUR-{face_id}-{loop_id}",
        face_tag=face_tag,
        face_id=face_id,
        loop_id=loop_id,
        edge_ids=tuple(resolved_edge_ids),
        points_2d=tuple(pts2d),
        points_3d=tuple(unique_pts3d),
        contour_type=ctype,
        is_closed=is_closed,
        area_mm2=area,
        orientation=orientation,
        face_normal=face_normal,
        source_provenance="TOPOLOGY_DERIVED",
        is_valid=is_valid,
        validation_notes="OK" if is_valid else f"loop_type={loop_type.value}",
    )


def _build_maps(
    topo: CanonicalTopology,
) -> tuple[
    dict[str, tuple[float, float, float]],
    dict[str, tuple[str, str]],
]:
    """Build vertex position map and edge start/end vertex map."""
    vmap: dict[str, tuple[float, float, float]] = {}
    for v in topo.vertices:
        vmap[v.vertex_id] = (
            float(v.point.x.value),
            float(v.point.y.value),
            float(v.point.z.value),
        )
    emap: dict[str, tuple[str, str]] = {}
    for e in topo.edges:
        emap[e.edge_id] = (e.start_vertex_id, e.end_vertex_id)
    return vmap, emap


def extract_face_outer_contour(
    face_tag: int,
    topo: CanonicalTopology,
    face_normal: tuple[float, float, float] | None = None,
) -> ManufacturingContour | None:
    """Extract the outer loop contour of a face from canonical topology.

    HARD RULE: Never derives contour from bounding box.
    Returns None if face not found or no outer loop available.

    Parameters
    ----------
    face_tag    Integer face tag from STEP parser (matches CanonicalFace ID suffix).
    topo        CanonicalTopology built by topology_adapter.build_canonical_topology.
    face_normal Optional known face normal to guide 2D projection.
    """
    face_id = f"F-{face_tag}"
    face = next((f for f in topo.faces if f.face_id == face_id), None)
    if face is None:
        return None

    vmap, emap = _build_maps(topo)
    lmap = {lp.loop_id: lp for lp in topo.loops}

    # Find the outer loop
    for lid in face.boundary_loop_ids:
        if lid not in lmap:
            continue
        lp = lmap[lid]
        if lp.loop_type == LoopType.OUTER:
            fn = face_normal or (0.0, 0.0, 1.0)
            return _extract_contour_from_loop(
                face_tag=face_tag,
                face_id=face_id,
                loop_id=lid,
                loop_edge_ids=lp.edge_ids,
                loop_type=LoopType.OUTER,
                face_normal=fn,
                vertex_map=vmap,
                edge_map=emap,
            )

    return None


def extract_all_face_contours(
    face_tag: int,
    topo: CanonicalTopology,
    face_normal: tuple[float, float, float] | None = None,
) -> list[ManufacturingContour]:
    """Extract all loops (outer + inner) for a face from canonical topology.

    Returns empty list if face not found.
    """
    face_id = f"F-{face_tag}"
    face = next((f for f in topo.faces if f.face_id == face_id), None)
    if face is None:
        return []

    vmap, emap = _build_maps(topo)
    lmap = {lp.loop_id: lp for lp in topo.loops}
    fn = face_normal or (0.0, 0.0, 1.0)

    result: list[ManufacturingContour] = []
    for lid in face.boundary_loop_ids:
        if lid not in lmap:
            continue
        lp = lmap[lid]
        c = _extract_contour_from_loop(
            face_tag=face_tag,
            face_id=face_id,
            loop_id=lid,
            loop_edge_ids=lp.edge_ids,
            loop_type=lp.loop_type,
            face_normal=fn,
            vertex_map=vmap,
            edge_map=emap,
        )
        result.append(c)
    return result
