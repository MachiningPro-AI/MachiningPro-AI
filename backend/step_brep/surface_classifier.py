"""
Surface and curve classification helpers for STEP B-Rep (P10 Phase 3).

Uses bounding-box heuristics and normal sampling — no extra dependencies.
All classifications are bounded by real gmsh geometry; nothing is fabricated.

Classification rules:
  PLANAR:     one bbox dimension is essentially zero (flat surface)
  CYLINDRICAL: all boundary curves are circular (no flat dimension in surface bbox)
  UNKNOWN:    anything else

Circular edge detection:
  A full circle has zero extent in one axis and equal extent in the other two.
  Diameter = average of the two non-zero extents.

HARD RULE: If classification is ambiguous, return UNKNOWN — never invent a type.
"""

from __future__ import annotations

from enum import StrEnum

import gmsh  # type: ignore[import]

__all__ = [
    "SurfaceClass",
    "classify_surface",
    "is_circular_curve",
    "estimate_cylinder_axis",
    "estimate_cylinder_diameter",
]

_FLAT_THRESHOLD = 1e-6
_CIRCLE_REL_TOL = 0.02  # 2% relative tolerance for circular arc diameter equality


class SurfaceClass(StrEnum):
    PLANAR = "PLANAR"
    CYLINDRICAL = "CYLINDRICAL"
    UNKNOWN = "UNKNOWN"


def classify_surface(tag: int, circ_curve_tags: set[int] | None = None) -> SurfaceClass:
    """Classify a gmsh surface by tag.

    circ_curve_tags: pre-computed set of circular curve tags (optional, avoids re-computation).
    gmsh model must be initialized and synchronized.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, tag)
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin

    # PLANAR: one dimension is essentially zero
    if dx < _FLAT_THRESHOLD or dy < _FLAT_THRESHOLD or dz < _FLAT_THRESHOLD:
        return SurfaceClass.PLANAR

    # CYLINDRICAL: all boundary curves are circles, non-flat 3D bbox
    bounds = gmsh.model.getBoundary([(2, tag)], oriented=False)
    bound_ctags = [b[1] for b in bounds]

    if not bound_ctags:
        return SurfaceClass.UNKNOWN

    if circ_curve_tags is not None:
        all_circ = all(ct in circ_curve_tags for ct in bound_ctags)
    else:
        all_circ = all(is_circular_curve(ct)[0] for ct in bound_ctags)

    if all_circ:
        return SurfaceClass.CYLINDRICAL

    return SurfaceClass.UNKNOWN


def is_circular_curve(tag: int) -> tuple[bool, float]:
    """Return (is_circle, diameter_mm).

    A circle has zero extent in one axis and approximately equal extent in the other two.
    Returns (False, 0.0) if not a circle or ambiguous.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(1, tag)
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin

    def _equal(a: float, b: float) -> bool:
        denom = max(abs(a), abs(b), 1e-10)
        return abs(a - b) / denom < _CIRCLE_REL_TOL

    if dz < _FLAT_THRESHOLD and dx > _FLAT_THRESHOLD and dy > _FLAT_THRESHOLD and _equal(dx, dy):
        return True, (dx + dy) / 2.0
    if dy < _FLAT_THRESHOLD and dx > _FLAT_THRESHOLD and dz > _FLAT_THRESHOLD and _equal(dx, dz):
        return True, (dx + dz) / 2.0
    if dx < _FLAT_THRESHOLD and dy > _FLAT_THRESHOLD and dz > _FLAT_THRESHOLD and _equal(dy, dz):
        return True, (dy + dz) / 2.0
    return False, 0.0


def estimate_cylinder_axis(surface_tag: int) -> str | None:
    """Return 'X', 'Y', or 'Z' for the axis a cylinder runs along.

    Determined from the bbox: a cylinder running along Z has bbox flat only in XY circles
    but extended in Z.  Returns None if ambiguous.
    gmsh model must be initialized and synchronized.
    """
    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, surface_tag)
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
    _SMALL = _FLAT_THRESHOLD

    if dx < _SMALL or dy < _SMALL:
        return "Z"
    if dx < _SMALL or dz < _SMALL:
        return "Y"
    if dy < _SMALL or dz < _SMALL:
        return "X"

    # Non-flat in all three dimensions — axis ambiguous
    # Heuristic: the longest dimension is the cylinder axis
    extents = {"X": dx, "Y": dy, "Z": dz}
    sorted_axes = sorted(extents, key=lambda k: extents[k], reverse=True)
    # Compare longest to second longest: if significantly longer, that's the axis
    if extents[sorted_axes[0]] > 1.5 * extents[sorted_axes[1]]:
        return sorted_axes[0]
    return None


def estimate_cylinder_diameter(surface_tag: int) -> float | None:
    """Return estimated cylinder diameter in mm from bbox.

    For a Z-axis cylinder: diameter = max(bbox_x, bbox_y).
    Returns None if surface is not cylindrical or axis is unknown.
    """
    axis = estimate_cylinder_axis(surface_tag)
    if axis is None:
        return None

    xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, surface_tag)
    dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin

    if axis == "Z":
        return (dx + dy) / 2.0
    if axis == "Y":
        return (dx + dz) / 2.0
    if axis == "X":
        return (dy + dz) / 2.0
    return None
