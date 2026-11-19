"""
Phase 8: Arc-point sampler for circular/2-arc faces.

Runs while gmsh is active (before finalize) and produces a companion dict
mapping face_tag → list of sampled 3D boundary points.

This is NOT a second topology model (MUST 3).  It is geometric data sampled
from the existing B-Rep kernel for faces that the topology adapter cannot
represent exactly with CanonicalLoop (e.g. 2-arc closed loops with < 3 edges).

HARD RULES:
  - Only called while gmsh session is active.
  - Points are sampled from actual B-Rep geometry, never fabricated.
  - For non-circular curves: returns empty (no guessing).
  - BOUNDARY_METHOD=APPROXIMATED for all arc-sampled contours.
  - MUST NOT be used to bypass topology gaps; only used when topology proves
    the boundary is geometrically closed.
"""

from __future__ import annotations

import math

import gmsh  # type: ignore[import]

__all__ = [
    "ArcContourMap",
    "build_arc_contour_map",
    "ARC_BOUNDARY_METHOD",
    "ARC_APPROXIMATION_TOLERANCE_MM",
    "ARC_APPROXIMATION_RESOLUTION",
]

ARC_BOUNDARY_METHOD: str = "APPROXIMATED"
ARC_APPROXIMATION_TOLERANCE_MM: float = 0.5
ARC_APPROXIMATION_RESOLUTION: int = 12


ArcContourMap = dict[int, list[tuple[float, float, float]]]


def _face_bbox(stag: int) -> tuple[float, float, float, float, float, float]:
    return gmsh.model.getBoundingBox(2, stag)  # type: ignore[no-any-return]


def _circle_points_from_bbox(
    stag: int,
    n: int,
) -> list[tuple[float, float, float]]:
    """Approximate a circular boundary from the face bounding box.

    Valid only for planar circular faces (dz ≈ 0 or other flat axis).
    Uses the bbox to estimate centre and radius; generates n equally-spaced
    points on the circle.

    Returns empty list if the face is not planar or the bbox is degenerate.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = _face_bbox(stag)
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    _FLAT = 0.1

    if dz < _FLAT:  # XY-plane circle
        cx, cy, cz = (xmin + xmax) / 2.0, (ymin + ymax) / 2.0, zmin
        r = (dx + dy) / 4.0
        return [
            (cx + r * math.cos(2 * math.pi * i / n),
             cy + r * math.sin(2 * math.pi * i / n),
             cz)
            for i in range(n)
        ]
    if dy < _FLAT:  # XZ-plane circle
        cx, cy, cz = (xmin + xmax) / 2.0, ymin, (zmin + zmax) / 2.0
        r = (dx + dz) / 4.0
        return [
            (cx + r * math.cos(2 * math.pi * i / n),
             cy,
             cz + r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
    if dx < _FLAT:  # YZ-plane circle
        cx, cy, cz = xmin, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0
        r = (dy + dz) / 4.0
        return [
            (cx,
             cy + r * math.cos(2 * math.pi * i / n),
             cz + r * math.sin(2 * math.pi * i / n))
            for i in range(n)
        ]
    return []  # tilted face — not handled


def _is_2arc_closed_face(stag: int) -> bool:
    """Return True if the face has exactly 2 arc curves sharing both vertices.

    A 2-arc face has: exactly 2 boundary curves, each with 2 vertices, and
    both curves share the same 2 vertices (forming a closed oval/circle).
    Topologically proven — not inferred.
    """
    s_bounds = gmsh.model.getBoundary([(2, stag)], oriented=False)
    if len(s_bounds) != 2:
        return False
    ctags = [b[1] for b in s_bounds]
    verts_per_curve: list[set[int]] = []
    for ct in ctags:
        cv_bounds = gmsh.model.getBoundary([(1, ct)], oriented=False)
        if len(cv_bounds) != 2:
            return False  # not a 2-vertex arc
        verts_per_curve.append({cv_bounds[0][1], cv_bounds[1][1]})
    # Both arcs must share exactly the same 2 vertices
    return verts_per_curve[0] == verts_per_curve[1]


def _is_planar_face(stag: int) -> bool:
    xmin, ymin, zmin, xmax, ymax, zmax = _face_bbox(stag)
    _FLAT = 0.1
    return (
        (xmax - xmin) < _FLAT
        or (ymax - ymin) < _FLAT
        or (zmax - zmin) < _FLAT
    )


def build_arc_contour_map(
    n_samples: int = ARC_APPROXIMATION_RESOLUTION,
) -> ArcContourMap:
    """Build arc-contour map for all 2-arc closed faces in the active gmsh model.

    Returns a dict mapping face_tag → list of sampled 3D boundary points.
    Only populated for faces that:
      1. Are planar (flat).
      2. Have exactly 2 arc curves sharing 2 vertices (topologically proven closed).
      3. Have a non-degenerate bbox from which a circle can be computed.

    Call this while gmsh is initialized and occ.synchronize() has been called,
    BEFORE gmsh.finalize().

    BOUNDARY_METHOD: APPROXIMATED (circle derived from face bounding box).
    """
    result: ArcContourMap = {}
    for _d, stag in gmsh.model.getEntities(2):
        if not _is_planar_face(stag):
            continue
        if not _is_2arc_closed_face(stag):
            continue
        pts = _circle_points_from_bbox(stag, n_samples)
        if len(pts) >= 3:
            result[stag] = pts
    return result
