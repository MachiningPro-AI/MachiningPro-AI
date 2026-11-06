"""Level-10 Toolpath Generation — geometry primitives.

All geometry is vendor-neutral and coordinate-frame-explicit.
No G-code, no NC output, no fabricated coordinates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import NamedTuple

from backend.toolpath.enums import CoordinateFrame, SegmentGeometryType


class Point3D(NamedTuple):
    """Immutable 3D point in explicit coordinate frame."""

    x: float
    y: float
    z: float

    def distance_to(self, other: Point3D) -> float:
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def __add__(self, other: Point3D) -> Point3D:  # type: ignore[override]
        return Point3D(self.x + other.x, self.y + other.y, self.z + other.z)

    def __sub__(self, other: Point3D) -> Point3D:  # type: ignore[override]
        return Point3D(self.x - other.x, self.y - other.y, self.z - other.z)


class Vector3D(NamedTuple):
    """Immutable 3D direction vector."""

    i: float
    j: float
    k: float

    @property
    def magnitude(self) -> float:
        return math.sqrt(self.i**2 + self.j**2 + self.k**2)

    def normalize(self) -> Vector3D:
        m = self.magnitude
        if m < 1e-10:
            return Vector3D(0.0, 0.0, 0.0)
        return Vector3D(self.i / m, self.j / m, self.k / m)


@dataclass(frozen=True)
class LineSegment:
    """Straight-line toolpath segment."""

    start: Point3D
    end: Point3D
    frame: CoordinateFrame
    geometry_type: SegmentGeometryType = SegmentGeometryType.LINE

    @property
    def length(self) -> float:
        return self.start.distance_to(self.end)


@dataclass(frozen=True)
class ArcSegment:
    """Circular arc toolpath segment in XY plane (milling arc)."""

    start: Point3D
    end: Point3D
    center: Point3D
    frame: CoordinateFrame
    clockwise: bool = False
    geometry_type: SegmentGeometryType = SegmentGeometryType.ARC

    @property
    def radius(self) -> float:
        return self.start.distance_to(self.center)

    @property
    def length(self) -> float:
        r = self.radius
        if r < 1e-10:
            return 0.0
        dx_s = self.start.x - self.center.x
        dy_s = self.start.y - self.center.y
        dx_e = self.end.x - self.center.x
        dy_e = self.end.y - self.center.y
        angle_start = math.atan2(dy_s, dx_s)
        angle_end = math.atan2(dy_e, dx_e)
        if self.clockwise:
            if angle_end >= angle_start:
                angle_end -= 2 * math.pi
        else:
            if angle_end <= angle_start:
                angle_end += 2 * math.pi
        return abs(angle_end - angle_start) * r


@dataclass(frozen=True)
class HelixSegment:
    """Helical arc — entry helix or peck-drill helix."""

    center_xy: tuple[float, float]
    radius: float
    start_z: float
    end_z: float
    pitch: float
    frame: CoordinateFrame
    clockwise: bool = False
    geometry_type: SegmentGeometryType = SegmentGeometryType.HELIX

    @property
    def axial_depth(self) -> float:
        return abs(self.end_z - self.start_z)

    @property
    def length(self) -> float:
        if self.pitch < 1e-10 or self.radius < 1e-10:
            return self.axial_depth
        turns = self.axial_depth / self.pitch
        circ = 2 * math.pi * self.radius
        return math.sqrt((turns * circ) ** 2 + self.axial_depth**2)


@dataclass(frozen=True)
class PolylineSegment:
    """Multi-point polyline (profile / pocket contour)."""

    points: tuple[Point3D, ...]
    frame: CoordinateFrame
    closed: bool = False
    geometry_type: SegmentGeometryType = SegmentGeometryType.POLYLINE

    @property
    def length(self) -> float:
        total = 0.0
        pts = list(self.points)
        for i in range(len(pts) - 1):
            total += pts[i].distance_to(pts[i + 1])
        if self.closed and len(pts) >= 2:
            total += pts[-1].distance_to(pts[0])
        return total

    @property
    def bounding_box(self) -> tuple[Point3D, Point3D]:
        """Return (min_point, max_point) bounding box."""
        xs = [p.x for p in self.points]
        ys = [p.y for p in self.points]
        zs = [p.z for p in self.points]
        return (
            Point3D(min(xs), min(ys), min(zs)),
            Point3D(max(xs), max(ys), max(zs)),
        )


def offset_polyline_2d(
    points: list[Point3D],
    offset: float,
    side: str = "LEFT",
) -> list[Point3D]:
    """Return a 2D offset of a planar polyline (z unchanged from first point).

    offset > 0 = outward; < 0 = inward.
    side: 'LEFT' or 'RIGHT' relative to traversal direction.

    Returns empty list if fewer than 2 points or offset would self-intersect
    (simple convex case only — no full polygon offsetting).
    """
    if len(points) < 2:
        return []
    sign = 1.0 if side.upper() == "LEFT" else -1.0
    result: list[Point3D] = []
    z = points[0].z
    for i in range(len(points) - 1):
        p0 = points[i]
        p1 = points[i + 1]
        dx = p1.x - p0.x
        dy = p1.y - p0.y
        length = math.sqrt(dx**2 + dy**2)
        if length < 1e-10:
            continue
        nx = -dy / length
        ny = dx / length
        ox = sign * offset * nx
        oy = sign * offset * ny
        if i == 0:
            result.append(Point3D(p0.x + ox, p0.y + oy, z))
        result.append(Point3D(p1.x + ox, p1.y + oy, z))
    return result


def compute_z_levels(
    top_z: float,
    bottom_z: float,
    stepdown: float,
) -> list[float]:
    """Return ordered list of Z cutting levels from top to bottom.

    Requires explicit stepdown > 0 — no default.
    """
    if stepdown <= 0:
        raise ValueError("stepdown must be > 0")
    levels: list[float] = []
    z = top_z - stepdown
    while z > bottom_z:
        levels.append(round(z, 6))
        z -= stepdown
    levels.append(round(bottom_z, 6))
    return levels


def ramp_path(
    start: Point3D,
    end_xy: tuple[float, float],
    start_z: float,
    end_z: float,
    frame: CoordinateFrame,
) -> LineSegment:
    """Return a linear ramp segment descending from start_z to end_z."""
    return LineSegment(
        start=Point3D(start.x, start.y, start_z),
        end=Point3D(end_xy[0], end_xy[1], end_z),
        frame=frame,
    )
