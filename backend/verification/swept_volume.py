"""
Swept tool volume and geometric intersection utilities for verification.

AABB = axis-aligned bounding box.
All intersection tests are conservative (may over-approximate volume, never under).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .enums import SweptVolumeStatus


@dataclass(frozen=True)
class AABB:
    """Axis-aligned bounding box."""

    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    def expanded_by(self, r: float) -> AABB:
        return AABB(
            self.min_x - r,
            self.min_y - r,
            self.min_z - r,
            self.max_x + r,
            self.max_y + r,
            self.max_z + r,
        )

    def volume(self) -> float:
        return (
            max(0.0, self.max_x - self.min_x)
            * max(0.0, self.max_y - self.min_y)
            * max(0.0, self.max_z - self.min_z)
        )

    def contains_point(self, x: float, y: float, z: float) -> bool:
        return (
            self.min_x <= x <= self.max_x
            and self.min_y <= y <= self.max_y
            and self.min_z <= z <= self.max_z
        )

    def intersects(self, other: AABB) -> bool:
        return (
            self.min_x <= other.max_x
            and self.max_x >= other.min_x
            and self.min_y <= other.max_y
            and self.max_y >= other.min_y
            and self.min_z <= other.max_z
            and self.max_z >= other.min_z
        )

    @classmethod
    def from_points(cls, points: list[tuple[float, float, float]]) -> AABB:
        if not points:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in points]
        ys = [p[1] for p in points]
        zs = [p[2] for p in points]
        return cls(min(xs), min(ys), min(zs), max(xs), max(ys), max(zs))


def segment_intersects_aabb(
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
    aabb: AABB,
) -> bool:
    """
    Parametric slab-method intersection test for segment vs AABB.
    Returns True if any part of the segment [P1, P2] overlaps the AABB.
    """
    t_min = 0.0
    t_max = 1.0

    for d, o, lo, hi in (
        (x2 - x1, x1, aabb.min_x, aabb.max_x),
        (y2 - y1, y1, aabb.min_y, aabb.max_y),
        (z2 - z1, z1, aabb.min_z, aabb.max_z),
    ):
        if abs(d) < 1e-12:
            if o < lo or o > hi:
                return False
        else:
            t1 = (lo - o) / d
            t2 = (hi - o) / d
            if t1 > t2:
                t1, t2 = t2, t1
            t_min = max(t_min, t1)
            t_max = min(t_max, t2)
            if t_min > t_max:
                return False

    return True


def segment_cylinder_intersects_aabb(
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
    radius: float,
    aabb: AABB,
) -> bool:
    """
    Conservative check: swept cylinder (capsule) along segment vs AABB.
    Expands the AABB by radius in all directions, then uses slab method.
    This may produce false positives at corners but never misses a real collision.
    """
    return segment_intersects_aabb(x1, y1, z1, x2, y2, z2, aabb.expanded_by(radius))


def point_to_segment_distance(
    px: float,
    py: float,
    pz: float,
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
) -> float:
    """Minimum distance from point P to segment [P1, P2]."""
    dx = x2 - x1
    dy = y2 - y1
    dz = z2 - z1
    seg_len2 = dx * dx + dy * dy + dz * dz
    if seg_len2 < 1e-12:
        return math.sqrt((px - x1) ** 2 + (py - y1) ** 2 + (pz - z1) ** 2)
    t = ((px - x1) * dx + (py - y1) * dy + (pz - z1) * dz) / seg_len2
    t = max(0.0, min(1.0, t))
    cx = x1 + t * dx
    cy = y1 + t * dy
    cz = z1 + t * dz
    return math.sqrt((px - cx) ** 2 + (py - cy) ** 2 + (pz - cz) ** 2)


@dataclass(frozen=True)
class SweptVolume:
    status: SweptVolumeStatus
    tool_type: str
    tool_radius: float
    aabb: AABB | None = None
    warnings: tuple = ()


def compute_swept_aabb(
    segments: list,
    tool_diameter_mm: float | None,
    tool_length_mm: float | None = None,
) -> SweptVolume:
    """
    Compute conservative AABB of swept tool volume along path segments.
    Unknown tool geometry → INSUFFICIENT_DATA.
    """
    if tool_diameter_mm is None:
        return SweptVolume(
            status=SweptVolumeStatus.INSUFFICIENT_DATA,
            tool_type="UNKNOWN",
            tool_radius=0.0,
            warnings=("Tool diameter unknown; swept volume cannot be computed",),
        )

    radius = tool_diameter_mm / 2.0
    if not segments:
        return SweptVolume(
            status=SweptVolumeStatus.NOT_COMPUTED,
            tool_type="CYLINDRICAL",
            tool_radius=radius,
        )

    points: list[tuple[float, float, float]] = []
    for seg in segments:
        points.append((seg.start_x, seg.start_y, seg.start_z))
        points.append((seg.end_x, seg.end_y, seg.end_z))

    path_aabb = AABB.from_points(points)
    tool_aabb = path_aabb.expanded_by(radius)

    return SweptVolume(
        status=SweptVolumeStatus.APPROXIMATE,
        tool_type="CYLINDRICAL",
        tool_radius=radius,
        aabb=tool_aabb,
        warnings=(
            "Swept volume is a conservative AABB approximation; "
            "exact swept-mesh not computed at Level 11",
        ),
    )
