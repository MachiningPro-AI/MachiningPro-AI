"""
Phase N — High-Fidelity Stock Removal Engine

Two independent modes:
  FAST_APPROXIMATE  — existing voxel engine (VoxelGrid in stock.py)
  BREP_BOOLEAN      — OCC Boolean subtraction via gmsh, then getMass

FAST_APPROXIMATE is never re-labeled as exact.
BREP_BOOLEAN is only claimed when a valid closed solid results from the Boolean.

Fail-closed contract:
  Invalid B-Rep result → fall back to FAST_APPROXIMATE with explicit disclosure
  Missing stock geometry → NOT_AVAILABLE

FABRICATED_VOLUME=NO
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum

try:
    import gmsh
    _GMSH_AVAILABLE = True
except ImportError:
    _GMSH_AVAILABLE = False

from .brep_volume import compute_occ_entity_volume
from .enums import StockShape
from .stock import StockModel

_GMSH_LOCK = threading.Lock()


class StockRemovalMode(StrEnum):
    FAST_APPROXIMATE = "FAST_APPROXIMATE"
    BREP_BOOLEAN = "BREP_BOOLEAN"
    NOT_AVAILABLE = "NOT_AVAILABLE"


@dataclass
class StockRemovalResult:
    mode: str = "NOT_AVAILABLE"
    initial_volume_mm3: float | None = None
    initial_volume_method: str = "NOT_AVAILABLE"
    initial_volume_fidelity: str = "NOT_AVAILABLE"
    removed_volume_mm3: float | None = None
    removed_volume_method: str = "NOT_AVAILABLE"
    removed_volume_fidelity: str = "NOT_AVAILABLE"
    remaining_volume_mm3: float | None = None
    remaining_volume_method: str = "NOT_AVAILABLE"
    remaining_volume_fidelity: str = "NOT_AVAILABLE"
    removal_percent: float | None = None
    boolean_success: bool = False
    fallback_used: bool = False
    fallback_reason: str | None = None
    warnings: list[str] = field(default_factory=list)
    error: str | None = None


def compute_stock_removal_brep(
    stock: StockModel,
    tool_radius_mm: float,
    cutting_segments: list[tuple[float, float, float, float, float, float]],
    mesh_size_mm: float = 2.0,
) -> StockRemovalResult:
    """BREP_BOOLEAN stock removal using OCC cutting swept tool from stock.

    Each cutting segment is swept as a cylinder and subtracted from the stock.
    Volume is measured with OCC getMass (BREP_EXACT) on result.

    Falls back to FAST_APPROXIMATE if B-Rep Boolean fails, with explicit disclosure.
    """
    r = StockRemovalResult(mode="BREP_BOOLEAN")

    if not _GMSH_AVAILABLE:
        r.mode = "NOT_AVAILABLE"
        r.error = "gmsh not available"
        return r

    if not _can_build_stock_brep(stock):
        r.mode = "NOT_AVAILABLE"
        r.error = "stock geometry insufficient for B-Rep Boolean"
        return r

    with _GMSH_LOCK:
        return _run_brep_boolean(r, stock, tool_radius_mm, cutting_segments, mesh_size_mm)


def _can_build_stock_brep(stock: StockModel) -> bool:
    if stock.shape == StockShape.BOX:
        return stock.has_box_dims
    if stock.shape == StockShape.CYLINDER:
        return stock.has_cylinder_dims
    if stock.shape == StockShape.CUSTOM_BREP:
        from .enums import CustomBRepStatus
        return stock.custom_brep_status == CustomBRepStatus.VALID_CLOSED_SOLID
    return False


def _run_brep_boolean(
    r: StockRemovalResult,
    stock: StockModel,
    tool_radius_mm: float,
    cutting_segments: list[tuple],
    mesh_size_mm: float,
) -> StockRemovalResult:
    gmsh.initialize()
    gmsh.option.setNumber("General.Verbosity", 0)
    gmsh.model.add("stock_removal")
    occ = gmsh.model.occ

    try:
        # Build stock solid
        stock_tag = _build_stock_solid(occ, stock)
        if stock_tag is None:
            r.mode = "NOT_AVAILABLE"
            r.error = "could not construct stock solid"
            return r

        occ.synchronize()

        # Measure initial stock volume
        init_vol_result = compute_occ_entity_volume(gmsh, 3, stock_tag)
        if not init_vol_result.solid_valid:
            r.mode = "NOT_AVAILABLE"
            r.error = "initial stock volume measurement failed"
            return r

        r.initial_volume_mm3 = init_vol_result.volume_mm3
        r.initial_volume_method = "BREP_SOLID_VOLUME"
        r.initial_volume_fidelity = "BREP_EXACT"

        # Build swept tool volumes and subtract
        tool_tags = []
        import math
        for seg in cutting_segments:
            x1, y1, z1, x2, y2, z2 = seg
            dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
            length = math.sqrt(dx*dx + dy*dy + dz*dz)
            if length < 1e-6:
                continue
            tag = occ.addCylinder(x1, y1, z1, dx, dy, dz, tool_radius_mm)
            tool_tags.append((3, tag))

        if not tool_tags:
            # No cutting segments — remaining = initial
            r.removed_volume_mm3 = 0.0
            r.removed_volume_method = "ANALYTIC"
            r.removed_volume_fidelity = "ANALYTIC_EXACT"
            r.remaining_volume_mm3 = r.initial_volume_mm3
            r.remaining_volume_method = "BREP_SOLID_VOLUME"
            r.remaining_volume_fidelity = "BREP_EXACT"
            r.removal_percent = 0.0
            r.boolean_success = True
            return r

        occ.synchronize()

        # Boolean: stock minus union of tool sweeps
        try:
            result_map, _ = occ.cut([(3, stock_tag)], tool_tags, removeObject=True, removeTool=True)
        except Exception as e:
            r.warnings.append(f"B-Rep Boolean cut failed: {e}")
            r.fallback_used = True
            r.fallback_reason = str(e)
            return _fallback_to_voxel(r, stock, tool_radius_mm, cutting_segments)

        occ.synchronize()

        if not result_map:
            # Boolean produced empty result (over-cut entirely)
            r.removed_volume_mm3 = r.initial_volume_mm3
            r.remaining_volume_mm3 = 0.0
            r.removed_volume_fidelity = "BREP_EXACT"
            r.remaining_volume_fidelity = "BREP_EXACT"
            r.removed_volume_method = "BREP_SOLID_VOLUME"
            r.remaining_volume_method = "BREP_SOLID_VOLUME"
            r.removal_percent = 100.0
            r.boolean_success = True
            return r

        # Measure remaining volume
        remaining_tags = [tag for _, tag in result_map]
        total_remaining = 0.0
        all_valid = True
        for tag in remaining_tags:
            vr = compute_occ_entity_volume(gmsh, 3, tag)
            if vr.solid_valid:
                total_remaining += vr.volume_mm3
            else:
                all_valid = False
                r.warnings.append(f"entity {tag} volume measurement failed; fallback")

        if not all_valid:
            r.fallback_used = True
            r.fallback_reason = "one or more result entities failed getMass"
            return _fallback_to_voxel(r, stock, tool_radius_mm, cutting_segments)

        r.remaining_volume_mm3 = total_remaining
        r.remaining_volume_method = "BREP_SOLID_VOLUME"
        r.remaining_volume_fidelity = "BREP_EXACT"
        r.removed_volume_mm3 = r.initial_volume_mm3 - total_remaining
        r.removed_volume_method = "BREP_SOLID_VOLUME"
        r.removed_volume_fidelity = "BREP_EXACT"
        if r.initial_volume_mm3 > 0:
            r.removal_percent = 100.0 * r.removed_volume_mm3 / r.initial_volume_mm3
        r.boolean_success = True
        return r

    except Exception as e:
        r.error = str(e)
        r.fallback_used = True
        r.fallback_reason = str(e)
        return _fallback_to_voxel(r, stock, tool_radius_mm, cutting_segments)
    finally:
        gmsh.finalize()


def _build_stock_solid(occ, stock: StockModel) -> int | None:
    if stock.shape == StockShape.BOX and stock.has_box_dims:
        dx = stock.max_x_mm - stock.min_x_mm
        dy = stock.max_y_mm - stock.min_y_mm
        dz = stock.max_z_mm - stock.min_z_mm
        return occ.addBox(stock.min_x_mm, stock.min_y_mm, stock.min_z_mm, dx, dy, dz)
    if stock.shape == StockShape.CYLINDER and stock.has_cylinder_dims:
        return occ.addCylinder(
            stock.center_x_mm, stock.center_y_mm, stock.bottom_z_mm,
            0, 0, stock.height_mm,
            stock.radius_mm,
        )
    return None


def _fallback_to_voxel(
    r: StockRemovalResult,
    stock: StockModel,
    tool_radius_mm: float,
    cutting_segments: list[tuple],
) -> StockRemovalResult:
    """Fall back to voxel approximation. Always labeled FAST_APPROXIMATE."""
    from .stock import VoxelGrid
    from .tolerance import DEFAULT_TOLERANCE

    r.mode = "FAST_APPROXIMATE"
    r.removed_volume_method = "VOXEL_APPROXIMATE"
    r.removed_volume_fidelity = "APPROXIMATE_VOXEL"
    r.remaining_volume_method = "VOXEL_APPROXIMATE"
    r.remaining_volume_fidelity = "APPROXIMATE_VOXEL"

    grid = VoxelGrid.from_stock(stock, DEFAULT_TOLERANCE)
    if grid is None:
        r.error = "voxel grid construction failed"
        return r

    # Compute initial volume analytically
    if r.initial_volume_mm3 is None:
        r.initial_volume_mm3 = stock.volume_mm3()
        r.initial_volume_method = stock.volume_method().value
        r.initial_volume_fidelity = stock.volume_fidelity().value

    for seg in cutting_segments:
        x1, y1, z1, x2, y2, z2 = seg
        grid.remove_path_segment(x1, y1, z1, x2, y2, z2, tool_radius_mm)

    r.remaining_volume_mm3 = grid.volume_remaining_mm3()
    if r.initial_volume_mm3 and r.initial_volume_mm3 > 0:
        r.removed_volume_mm3 = r.initial_volume_mm3 - r.remaining_volume_mm3
        r.removal_percent = 100.0 * r.removed_volume_mm3 / r.initial_volume_mm3

    r.boolean_success = False  # voxel is not a Boolean result
    r.warnings.append("STOCK_REMOVAL_MODE=FAST_APPROXIMATE (voxel); not exact B-Rep Boolean")
    return r


def compute_stock_removal_fast(
    stock: StockModel,
    tool_radius_mm: float,
    cutting_segments: list[tuple[float, float, float, float, float, float]],
) -> StockRemovalResult:
    """FAST_APPROXIMATE voxel stock removal. Never labeled as exact."""
    r = StockRemovalResult(mode="FAST_APPROXIMATE")
    result = _fallback_to_voxel(r, stock, tool_radius_mm, cutting_segments)
    return result
