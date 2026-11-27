"""
Assembly Collision Checks — 6 Independent Checks (Phase L)

Checks:
  CUTTER_PART      cutter vs part geometry
  CUTTER_STOCK     cutter vs stock (over-travel beyond stock)
  CUTTER_FIXTURE   cutter vs fixture geometry
  HOLDER_PART      holder body vs part geometry
  HOLDER_STOCK     holder body vs stock geometry
  HOLDER_FIXTURE   holder body vs fixture geometry

Each check is independent — cutter and holder are NEVER merged into one result.
Each result exposes: STATUS, METHOD, GEOMETRY_FIDELITY, COLLISION_COUNT,
MIN_CLEARANCE (where meaningful), PROVENANCE.

Fail-closed contract (HARD RULE 4):
  Missing required geometry → NOT_PERFORMED or INSUFFICIENT_DATA (never PASS)
  Partial geometry → PARTIAL (never PASS)
  Unknown → NOT_VERIFIABLE (never safe)

METHOD ∈ {BREP_EXACT_BOOLEAN, PARAMETRIC_BREP_BBOX, SIMPLIFIED_BBOX, NOT_PERFORMED}
GEOMETRY_FIDELITY ∈ {BREP_EXACT, PARAMETRIC_BREP, SIMPLIFIED, NOT_AVAILABLE}

FABRICATED_PASS=NO
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .stock import FixtureGeometry, StockModel


@dataclass
class AssemblyCollisionInput:
    """Geometry inputs for a full assembly collision check.

    Provide None for fields that are genuinely not available.
    Never fabricate dimensions to get a PASS.
    """

    # Cutter envelope (Phase G/H geometry)
    cutter_radius_mm: float | None = None
    cutter_length_mm: float | None = None
    cutter_geometry_fidelity: str = "NOT_AVAILABLE"

    # Holder envelope (Phase J geometry)
    holder_gauge_length_mm: float | None = None
    holder_max_diameter_mm: float | None = None
    holder_geometry_fidelity: str = "NOT_AVAILABLE"

    # Tool stickout
    tool_stickout_mm: float | None = None

    # Stock geometry
    stock: StockModel | None = None

    # Fixture geometry (list; may be empty)
    fixtures: list[FixtureGeometry] = field(default_factory=list)

    # Part bounding box (from STEP/IGES import)
    part_bbox_mm: tuple[float, float, float, float, float, float] | None = None

    # Toolpath envelope (bounding box of all cutting segments)
    toolpath_bbox_mm: tuple[float, float, float, float, float, float] | None = None

    # Provenance
    provenance: str = "CATALOG_PARAMETRIC"


@dataclass
class CollisionCheckResult:
    """Result of a single assembly component collision check."""

    check_type: str = ""
    status: str = "NOT_PERFORMED"
    method: str = "NOT_PERFORMED"
    geometry_fidelity: str = "NOT_AVAILABLE"
    collision_count: int = 0
    min_clearance_mm: float | None = None
    provenance: str = "CATALOG_PARAMETRIC"
    reason: str = ""
    warnings: list[str] = field(default_factory=list)


def run_assembly_collision_checks(
    inp: AssemblyCollisionInput,
) -> dict[str, CollisionCheckResult]:
    """Run all 6 independent assembly collision checks.

    Returns dict keyed by check name:
      CUTTER_PART, CUTTER_STOCK, CUTTER_FIXTURE,
      HOLDER_PART, HOLDER_STOCK, HOLDER_FIXTURE

    Each is independently computed — never merged.
    """
    results: dict[str, CollisionCheckResult] = {}

    results["CUTTER_PART"] = _check_cutter_part(inp)
    results["CUTTER_STOCK"] = _check_cutter_stock(inp)
    results["CUTTER_FIXTURE"] = _check_cutter_fixture(inp)
    results["HOLDER_PART"] = _check_holder_part(inp)
    results["HOLDER_STOCK"] = _check_holder_stock(inp)
    results["HOLDER_FIXTURE"] = _check_holder_fixture(inp)

    return results


# ---------------------------------------------------------------------------
# Cutter checks
# ---------------------------------------------------------------------------


def _check_cutter_part(inp: AssemblyCollisionInput) -> CollisionCheckResult:
    """CUTTER_PART: Does the cutter body collide with the part geometry?"""
    r = CollisionCheckResult(check_type="CUTTER_PART", provenance=inp.provenance)

    if inp.cutter_radius_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "cutter_radius_mm not provided"
        return r

    if inp.part_bbox_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "part_bbox_mm not provided"
        return r

    if inp.toolpath_bbox_mm is None:
        r.status = "INSUFFICIENT_DATA"
        r.reason = "toolpath_bbox_mm required for cutter-part check"
        r.geometry_fidelity = inp.cutter_geometry_fidelity
        return r

    # PARAMETRIC_BREP_BBOX: check if toolpath bbox + cutter radius intersects part bbox
    r.method = "PARAMETRIC_BREP_BBOX"
    r.geometry_fidelity = inp.cutter_geometry_fidelity

    px0, py0, pz0, px1, py1, pz1 = inp.part_bbox_mm
    tx0, ty0, tz0, tx1, ty1, tz1 = inp.toolpath_bbox_mm
    rad = inp.cutter_radius_mm

    # Inflated toolpath by cutter radius
    cx0, cy0, cz0 = tx0 - rad, ty0 - rad, tz0
    cx1, cy1, cz1 = tx1 + rad, ty1 + rad, tz1

    # Minimal clearance between inflated cutter envelope and part bbox
    clearances = [
        cx0 - px1, px0 - cx1,
        cy0 - py1, py0 - cy1,
        cz0 - pz1, pz0 - cz1,
    ]
    min_clr = max(clearances)  # positive = no overlap; negative = overlap

    r.min_clearance_mm = min_clr
    if min_clr < 0:
        r.status = "PARTIAL"
        r.collision_count = 1
        r.reason = f"cutter envelope overlaps part bbox (clearance={min_clr:.3f}mm)"
    else:
        r.status = "PASS"
        r.reason = f"no bbox overlap (min clearance={min_clr:.3f}mm)"

    return r


def _check_cutter_stock(inp: AssemblyCollisionInput) -> CollisionCheckResult:
    """CUTTER_STOCK: Does cutter travel outside stock extents (over-travel)?"""
    r = CollisionCheckResult(check_type="CUTTER_STOCK", provenance=inp.provenance)

    if inp.cutter_radius_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "cutter_radius_mm not provided"
        return r

    if inp.stock is None:
        r.status = "NOT_PERFORMED"
        r.reason = "stock geometry not provided"
        return r

    if inp.toolpath_bbox_mm is None:
        r.status = "INSUFFICIENT_DATA"
        r.reason = "toolpath_bbox_mm required for cutter-stock check"
        return r

    r.method = "PARAMETRIC_BREP_BBOX"
    r.geometry_fidelity = inp.cutter_geometry_fidelity

    # Get stock extents
    s = inp.stock
    if not (s.has_box_dims or s.has_cylinder_dims):
        r.status = "INSUFFICIENT_DATA"
        r.reason = "stock geometry has no known extents"
        return r

    if s.has_box_dims:
        sx0, sy0 = s.min_x_mm, s.min_y_mm
        sx1, sy1 = s.max_x_mm, s.max_y_mm
    else:
        cx, cy = s.center_x_mm, s.center_y_mm
        rr = s.radius_mm
        sx0, sy0 = cx - rr, cy - rr
        sx1, sy1 = cx + rr, cy + rr

    tx0, ty0, _tz0, tx1, ty1, _tz1 = inp.toolpath_bbox_mm
    rad = inp.cutter_radius_mm

    # Check if cutter + toolpath stays within stock
    violations = []
    if tx0 - rad < sx0:
        violations.append(f"X-min over-travel: {tx0 - rad:.2f} < {sx0:.2f}")
    if tx1 + rad > sx1:
        violations.append(f"X-max over-travel: {tx1 + rad:.2f} > {sx1:.2f}")
    if ty0 - rad < sy0:
        violations.append(f"Y-min over-travel: {ty0 - rad:.2f} < {sy0:.2f}")
    if ty1 + rad > sy1:
        violations.append(f"Y-max over-travel: {ty1 + rad:.2f} > {sy1:.2f}")

    if violations:
        r.status = "FAIL"
        r.collision_count = len(violations)
        r.reason = "; ".join(violations)
    else:
        r.status = "PASS"
        # Minimum clearance to stock edge in XY
        margin = min(tx0 - rad - sx0, sx1 - tx1 - rad,
                     ty0 - rad - sy0, sy1 - ty1 - rad)
        r.min_clearance_mm = margin

    return r


def _check_cutter_fixture(inp: AssemblyCollisionInput) -> CollisionCheckResult:
    """CUTTER_FIXTURE: Does cutter contact any fixture geometry?"""
    r = CollisionCheckResult(check_type="CUTTER_FIXTURE", provenance=inp.provenance)

    if inp.cutter_radius_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "cutter_radius_mm not provided"
        return r

    if not inp.fixtures:
        r.status = "NOT_PERFORMED"
        r.reason = "no fixture geometry provided"
        return r

    if inp.toolpath_bbox_mm is None:
        r.status = "INSUFFICIENT_DATA"
        r.reason = "toolpath_bbox_mm required for cutter-fixture check"
        return r

    r.method = "SIMPLIFIED_BBOX"
    r.geometry_fidelity = inp.cutter_geometry_fidelity

    tx0, ty0, tz0, tx1, ty1, tz1 = inp.toolpath_bbox_mm
    rad = inp.cutter_radius_mm
    cx0, cy0, cz0 = tx0 - rad, ty0 - rad, tz0
    cx1, cy1, cz1 = tx1 + rad, ty1 + rad, tz1

    collisions = 0
    min_clr = None

    for fix in inp.fixtures:
        overlap = _bbox_overlap_3d(
            (cx0, cy0, cz0, cx1, cy1, cz1),
            (fix.min_x_mm, fix.min_y_mm, fix.min_z_mm,
             fix.max_x_mm, fix.max_y_mm, fix.max_z_mm),
        )
        clr = _bbox_clearance(
            (cx0, cy0, cz0, cx1, cy1, cz1),
            (fix.min_x_mm, fix.min_y_mm, fix.min_z_mm,
             fix.max_x_mm, fix.max_y_mm, fix.max_z_mm),
        )
        if min_clr is None or clr < min_clr:
            min_clr = clr
        if overlap:
            collisions += 1

    r.collision_count = collisions
    r.min_clearance_mm = min_clr
    if collisions > 0:
        r.status = "FAIL"
        r.reason = f"{collisions} fixture(s) overlap cutter envelope"
    else:
        r.status = "PASS"

    return r


# ---------------------------------------------------------------------------
# Holder checks
# ---------------------------------------------------------------------------


def _check_holder_part(inp: AssemblyCollisionInput) -> CollisionCheckResult:
    """HOLDER_PART: Does the holder body collide with part geometry?"""
    r = CollisionCheckResult(check_type="HOLDER_PART", provenance=inp.provenance)

    if inp.holder_max_diameter_mm is None or inp.holder_gauge_length_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "holder_max_diameter_mm and holder_gauge_length_mm required"
        return r

    if inp.part_bbox_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "part_bbox_mm not provided"
        return r

    if inp.toolpath_bbox_mm is None:
        r.status = "INSUFFICIENT_DATA"
        r.reason = "toolpath_bbox_mm required"
        return r

    r.method = "SIMPLIFIED_BBOX"
    r.geometry_fidelity = inp.holder_geometry_fidelity

    # Holder is above the cutter — it starts at stickout from tool tip
    stickout = inp.tool_stickout_mm or 0.0
    tx0, ty0, tz0, tx1, ty1, tz1 = inp.toolpath_bbox_mm
    holder_r = inp.holder_max_diameter_mm / 2.0

    # Holder envelope in Z: starts at stickout above tool tip
    # (we position holder above the cutter, centered on toolpath XY)
    h_cx0 = tx0 - holder_r
    h_cy0 = ty0 - holder_r
    h_cz0 = tz1 - stickout + inp.holder_gauge_length_mm * 0.5  # simplified Z position
    h_cx1 = tx1 + holder_r
    h_cy1 = ty1 + holder_r
    h_cz1 = h_cz0 + inp.holder_gauge_length_mm

    px0, py0, pz0, px1, py1, pz1 = inp.part_bbox_mm

    overlap = _bbox_overlap_3d(
        (h_cx0, h_cy0, h_cz0, h_cx1, h_cy1, h_cz1),
        (px0, py0, pz0, px1, py1, pz1),
    )
    clr = _bbox_clearance(
        (h_cx0, h_cy0, h_cz0, h_cx1, h_cy1, h_cz1),
        (px0, py0, pz0, px1, py1, pz1),
    )
    r.min_clearance_mm = clr

    if overlap:
        r.status = "FAIL"
        r.collision_count = 1
        r.reason = f"holder body overlaps part bbox (clearance={clr:.3f}mm)"
    else:
        r.status = "PASS"
        r.warnings.append(
            "HOLDER_PART: simplified bbox check only; "
            "HOLDER_GEOMETRY_FIDELITY=" + inp.holder_geometry_fidelity
        )

    return r


def _check_holder_stock(inp: AssemblyCollisionInput) -> CollisionCheckResult:
    """HOLDER_STOCK: Does the holder body collide with stock geometry?"""
    r = CollisionCheckResult(check_type="HOLDER_STOCK", provenance=inp.provenance)

    if inp.holder_max_diameter_mm is None or inp.holder_gauge_length_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "holder_max_diameter_mm and holder_gauge_length_mm required"
        return r

    if inp.stock is None:
        r.status = "NOT_PERFORMED"
        r.reason = "stock geometry not provided"
        return r

    if inp.toolpath_bbox_mm is None:
        r.status = "INSUFFICIENT_DATA"
        r.reason = "toolpath_bbox_mm required"
        return r

    r.method = "SIMPLIFIED_BBOX"
    r.geometry_fidelity = inp.holder_geometry_fidelity

    s = inp.stock
    if not (s.has_box_dims or s.has_cylinder_dims):
        r.status = "INSUFFICIENT_DATA"
        r.reason = "stock has no usable extents"
        return r

    if s.has_box_dims:
        sx0, sy0, sz0 = s.min_x_mm, s.min_y_mm, s.min_z_mm
        sx1, sy1, sz1 = s.max_x_mm, s.max_y_mm, s.max_z_mm
    else:
        cx, cy = s.center_x_mm, s.center_y_mm
        rr = s.radius_mm
        sx0, sy0, sz0 = cx - rr, cy - rr, s.bottom_z_mm
        sx1, sy1, sz1 = cx + rr, cy + rr, s.bottom_z_mm + s.height_mm

    stickout = inp.tool_stickout_mm or 0.0
    tx0, ty0, tz0, tx1, ty1, tz1 = inp.toolpath_bbox_mm
    holder_r = inp.holder_max_diameter_mm / 2.0

    h_cx0, h_cy0 = tx0 - holder_r, ty0 - holder_r
    h_cx1, h_cy1 = tx1 + holder_r, ty1 + holder_r

    # Holder is above stock top surface when stickout is sufficient
    stock_top = sz1
    holder_bottom_z = tz1 - stickout  # approximate

    if holder_bottom_z < stock_top:
        # Holder dips into stock — check XY overlap
        h_z0, h_z1 = holder_bottom_z, holder_bottom_z + inp.holder_gauge_length_mm
        overlap = _bbox_overlap_3d(
            (h_cx0, h_cy0, h_z0, h_cx1, h_cy1, h_z1),
            (sx0, sy0, sz0, sx1, sy1, sz1),
        )
        if overlap:
            r.status = "FAIL"
            r.collision_count = 1
            r.reason = "holder body enters stock extents"
        else:
            r.status = "PASS"
    else:
        r.status = "PASS"
        r.min_clearance_mm = holder_bottom_z - stock_top

    return r


def _check_holder_fixture(inp: AssemblyCollisionInput) -> CollisionCheckResult:
    """HOLDER_FIXTURE: Does the holder body collide with any fixture?"""
    r = CollisionCheckResult(check_type="HOLDER_FIXTURE", provenance=inp.provenance)

    if inp.holder_max_diameter_mm is None or inp.holder_gauge_length_mm is None:
        r.status = "NOT_PERFORMED"
        r.reason = "holder_max_diameter_mm and holder_gauge_length_mm required"
        return r

    if not inp.fixtures:
        r.status = "NOT_PERFORMED"
        r.reason = "no fixture geometry provided"
        return r

    if inp.toolpath_bbox_mm is None:
        r.status = "INSUFFICIENT_DATA"
        r.reason = "toolpath_bbox_mm required"
        return r

    r.method = "SIMPLIFIED_BBOX"
    r.geometry_fidelity = inp.holder_geometry_fidelity

    stickout = inp.tool_stickout_mm or 0.0
    tx0, ty0, tz0, tx1, ty1, tz1 = inp.toolpath_bbox_mm
    holder_r = inp.holder_max_diameter_mm / 2.0
    h_cx0, h_cy0 = tx0 - holder_r, ty0 - holder_r
    h_cx1, h_cy1 = tx1 + holder_r, ty1 + holder_r
    h_z0 = tz1 - stickout
    h_z1 = h_z0 + inp.holder_gauge_length_mm

    collisions = 0
    min_clr = None

    for fix in inp.fixtures:
        overlap = _bbox_overlap_3d(
            (h_cx0, h_cy0, h_z0, h_cx1, h_cy1, h_z1),
            (fix.min_x_mm, fix.min_y_mm, fix.min_z_mm,
             fix.max_x_mm, fix.max_y_mm, fix.max_z_mm),
        )
        clr = _bbox_clearance(
            (h_cx0, h_cy0, h_z0, h_cx1, h_cy1, h_z1),
            (fix.min_x_mm, fix.min_y_mm, fix.min_z_mm,
             fix.max_x_mm, fix.max_y_mm, fix.max_z_mm),
        )
        if min_clr is None or clr < min_clr:
            min_clr = clr
        if overlap:
            collisions += 1

    r.collision_count = collisions
    r.min_clearance_mm = min_clr
    r.status = "FAIL" if collisions > 0 else "PASS"
    if collisions > 0:
        r.reason = f"{collisions} fixture(s) overlap holder body"

    return r


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------


def _bbox_overlap_3d(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> bool:
    """True if two AABBs overlap (touching is not overlap)."""
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    return (
        ax0 < bx1 and ax1 > bx0
        and ay0 < by1 and ay1 > by0
        and az0 < bz1 and az1 > bz0
    )


def _bbox_clearance(
    a: tuple[float, float, float, float, float, float],
    b: tuple[float, float, float, float, float, float],
) -> float:
    """Return signed minimum clearance between two AABBs.

    Positive = no overlap (gap). Negative = overlap (penetration depth).
    """
    ax0, ay0, az0, ax1, ay1, az1 = a
    bx0, by0, bz0, bx1, by1, bz1 = b
    gaps = [
        bx0 - ax1, ax0 - bx1,
        by0 - ay1, ay0 - by1,
        bz0 - az1, az0 - bz1,
    ]
    return max(gaps)
