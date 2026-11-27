"""
Phase V — Machine Component Collision

Independent checks:
  HEAD_PART, HEAD_STOCK, HEAD_FIXTURE
  SPINDLE_PART, SPINDLE_FIXTURE
  TABLE_TOOL, TABLE_HOLDER

Missing component geometry → NOT_VERIFIABLE (never PASS)
No fabricated PASS for missing geometry.

MACHINE_COLLISION_READY=YES
FABRICATED_PASS=NO
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MachineComponentCollisionResult:
    check_type: str = ""
    status: str = "NOT_VERIFIABLE"
    method: str = "NOT_PERFORMED"
    geometry_fidelity: str = "NOT_AVAILABLE"
    collision_count: int = 0
    min_clearance_mm: float | None = None
    provenance: str = "CATALOG_PARAMETRIC"
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


@dataclass
class MachineComponentGeometry:
    """Bounding box for a machine component. Must come from catalog/import — never fabricated."""
    component_id: str
    min_x_mm: float
    min_y_mm: float
    min_z_mm: float
    max_x_mm: float
    max_y_mm: float
    max_z_mm: float
    geometry_fidelity: str = "SIMPLIFIED"
    source: str = "CATALOG"


def run_machine_collision_checks(
    head_geom: MachineComponentGeometry | None,
    spindle_geom: MachineComponentGeometry | None,
    table_geom: MachineComponentGeometry | None,
    part_bbox: tuple | None,
    stock_bbox: tuple | None,
    fixtures: list = None,
    tool_bbox: tuple | None = None,
    holder_bbox: tuple | None = None,
) -> dict[str, MachineComponentCollisionResult]:
    """Run all machine component collision checks independently.

    Returns dict keyed by check name.
    """
    checks = {}

    checks["HEAD_PART"] = _check_pair(
        "HEAD_PART", head_geom, part_bbox, "part_bbox"
    )
    checks["HEAD_STOCK"] = _check_pair(
        "HEAD_STOCK", head_geom, stock_bbox, "stock_bbox"
    )
    checks["HEAD_FIXTURE"] = _check_component_vs_fixtures(
        "HEAD_FIXTURE", head_geom, fixtures or []
    )
    checks["SPINDLE_PART"] = _check_pair(
        "SPINDLE_PART", spindle_geom, part_bbox, "part_bbox"
    )
    checks["SPINDLE_FIXTURE"] = _check_component_vs_fixtures(
        "SPINDLE_FIXTURE", spindle_geom, fixtures or []
    )
    checks["TABLE_TOOL"] = _check_pair(
        "TABLE_TOOL", table_geom, tool_bbox, "tool_bbox"
    )
    checks["TABLE_HOLDER"] = _check_pair(
        "TABLE_HOLDER", table_geom, holder_bbox, "holder_bbox"
    )

    return checks


def _check_pair(
    name: str,
    component: MachineComponentGeometry | None,
    target_bbox: tuple | None,
    target_name: str,
) -> MachineComponentCollisionResult:
    r = MachineComponentCollisionResult(check_type=name)

    if component is None:
        r.status = "NOT_VERIFIABLE"
        r.reason = f"{name}: machine component geometry not provided"
        return r

    if target_bbox is None:
        r.status = "NOT_PERFORMED"
        r.reason = f"{name}: {target_name} not provided"
        return r

    r.method = "SIMPLIFIED_BBOX"
    r.geometry_fidelity = component.geometry_fidelity

    comp_bbox = (
        component.min_x_mm, component.min_y_mm, component.min_z_mm,
        component.max_x_mm, component.max_y_mm, component.max_z_mm,
    )

    overlap = _bbox_overlap_3d(comp_bbox, target_bbox)
    clr = _bbox_clearance(comp_bbox, target_bbox)
    r.min_clearance_mm = clr

    if overlap:
        r.status = "FAIL"
        r.collision_count = 1
        r.reason = f"{name}: bounding boxes overlap (clearance={clr:.3f}mm)"
    else:
        r.status = "PASS"

    return r


def _check_component_vs_fixtures(
    name: str,
    component: MachineComponentGeometry | None,
    fixtures: list,
) -> MachineComponentCollisionResult:
    r = MachineComponentCollisionResult(check_type=name)

    if component is None:
        r.status = "NOT_VERIFIABLE"
        r.reason = f"{name}: machine component geometry not provided"
        return r

    if not fixtures:
        r.status = "NOT_PERFORMED"
        r.reason = f"{name}: no fixture geometry provided"
        return r

    r.method = "SIMPLIFIED_BBOX"
    r.geometry_fidelity = component.geometry_fidelity

    comp_bbox = (
        component.min_x_mm, component.min_y_mm, component.min_z_mm,
        component.max_x_mm, component.max_y_mm, component.max_z_mm,
    )

    collisions = 0
    min_clr = None
    for fix in fixtures:
        fix_bbox = (fix.min_x_mm, fix.min_y_mm, fix.min_z_mm,
                    fix.max_x_mm, fix.max_y_mm, fix.max_z_mm)
        clr = _bbox_clearance(comp_bbox, fix_bbox)
        if min_clr is None or clr < min_clr:
            min_clr = clr
        if _bbox_overlap_3d(comp_bbox, fix_bbox):
            collisions += 1

    r.collision_count = collisions
    r.min_clearance_mm = min_clr
    r.status = "FAIL" if collisions > 0 else "PASS"
    return r


def _bbox_overlap_3d(a: tuple, b: tuple) -> bool:
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    return (ax0 < bx1 and ax1 > bx0
            and ay0 < by1 and ay1 > by0
            and az0 < bz1 and az1 > bz0)


def _bbox_clearance(a: tuple, b: tuple) -> float:
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    return max(bx0 - ax1, ax0 - bx1, by0 - ay1, ay0 - by1, bz0 - az1, az0 - bz1)
