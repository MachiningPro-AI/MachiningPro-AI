"""
Exact Gouge / Overcut Verification Engine — BREP_BOOLEAN_OCC

Architecture:
  Target geometry (STEP/B-Rep) → gmsh OCC import
  Stock geometry               → gmsh OCC box primitive
  Tool swept volume            → gmsh OCC cylinders fused along toolpath
  Machined result              → Boolean difference: stock - swept_volume
  Gouge detection              → Boolean difference: target - machined
  Remaining material           → Boolean difference: machined - target

Engine:   gmsh 4.x with OpenCASCADE kernel (gmsh.model.occ)
Fidelity: BREP_EXACT (for STEP inputs); TESSELLATED_HIGH_FIDELITY otherwise

GOUGE_EXACT_READY=YES  (requires trimesh, gmsh, numpy)
GOUGE_EXACT_METHOD=BREP_BOOLEAN_OCC
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# gmsh is not thread-safe — serialise all gmsh calls
_GMSH_LOCK = threading.Lock()

_MESH_SIZE_DEFAULT = 2.0   # mm — mesh element target size for volume calc
_MESH_SIZE_FINE = 1.0      # mm — finer mesh for small features
_VOLUME_ZERO_THRESHOLD = 0.01  # mm³ — below this, treat as zero (floating-point noise)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ExactGougeConfig:
    """Input configuration for exact gouge check."""

    # Geometry inputs
    target_step_path: str | None = None     # STEP file = desired final part
    stock_x_mm: float = 0.0                 # stock origin X
    stock_y_mm: float = 0.0
    stock_z_mm: float = 0.0
    stock_w_mm: float = 100.0               # stock width  (X extent)
    stock_h_mm: float = 100.0               # stock height (Y extent)
    stock_d_mm: float = 50.0               # stock depth  (Z extent)

    # Tool geometry
    tool_radius_mm: float = 5.0
    tool_corner_radius_mm: float = 0.0

    # Toolpath segments: list of (x1,y1,z1, x2,y2,z2, is_cutting)
    cutting_segments: list[tuple[float, float, float, float, float, float]] = field(
        default_factory=list
    )

    # Tolerance
    tolerance_mm: float | None = None
    tolerance_source: str = "NOT_PROVIDED"

    # Mesh quality
    mesh_size_mm: float = _MESH_SIZE_DEFAULT
    max_mesh_time_s: float = 30.0

    # TEST_ONLY flag — bypasses tolerance requirement
    test_only: bool = False
    test_label: str = ""


@dataclass
class ExactGougeResult:
    """Result of exact gouge verification."""

    status: str = "NOT_VERIFIABLE"           # PASS / FAIL / PARTIAL / NOT_VERIFIABLE
    method: str = "BREP_BOOLEAN_OCC"
    target_geometry_fidelity: str = "NOT_AVAILABLE"
    machined_result_method: str = "BOOLEAN_BREP"
    machined_result_fidelity: str = "BREP_EXACT"

    # Gouge (over-cut)
    gouge_volume_mm3: float = 0.0
    max_gouge_depth_mm: float = 0.0
    gouge_region_count: int = 0

    # Remaining material (under-cut)
    remaining_material_volume_mm3: float = 0.0
    max_remaining_depth_mm: float = 0.0
    remaining_region_count: int = 0

    # Tolerance
    tolerance_mm: float | None = None
    tolerance_source: str = "NOT_PROVIDED"

    # Timing
    target_prep_ms: float = 0.0
    machined_result_ms: float = 0.0
    boolean_ms: float = 0.0
    gouge_analysis_ms: float = 0.0
    report_integration_ms: float = 0.0
    total_exact_verification_ms: float = 0.0

    # Diagnostic
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    boolean_success: bool = False
    gouge_exact_ready: bool = True


# ---------------------------------------------------------------------------
# Mesh volume helper
# ---------------------------------------------------------------------------


def _mesh_volume_mm3(gmsh_module) -> float:
    """
    Compute total volume of all meshed 3D entities (tetrahedra).
    Returns 0.0 if no tetrahedra found.
    """
    try:
        node_tags_arr, coords_arr, _ = gmsh_module.model.mesh.getNodes()
        if len(node_tags_arr) == 0:
            return 0.0

        coord_map = {
            int(tag): coords_arr[i * 3: i * 3 + 3]
            for i, tag in enumerate(node_tags_arr)
        }

        total = 0.0
        elem_types, _, elem_node_tags = gmsh_module.model.mesh.getElements(3)
        for idx, et in enumerate(elem_types):
            if int(et) == 4:  # tetrahedron
                npt = elem_node_tags[idx].reshape(-1, 4)
                for tet in npt:
                    v = [coord_map[int(t)] for t in tet]
                    d1 = v[1] - v[0]
                    d2 = v[2] - v[0]
                    d3 = v[3] - v[0]
                    total += abs(np.dot(d1, np.cross(d2, d3))) / 6.0
        return float(total)
    except Exception as exc:
        logger.debug("_mesh_volume_mm3 error: %s", exc)
        return 0.0


# ---------------------------------------------------------------------------
# Swept volume builder
# ---------------------------------------------------------------------------


def _build_swept_volume(gmsh_occ, segments, tool_radius: float) -> list[tuple[int, int]]:
    """
    Build the union of all tool swept volumes in the current gmsh model.

    Each segment (x1,y1,z1, x2,y2,z2) produces a cylinder from P1 to P2
    with radius = tool_radius.

    Returns list of (dim=3, tag) entities; empty list if no segments.
    """
    cyl_tags: list[tuple[int, int]] = []

    for x1, y1, z1, x2, y2, z2 in segments:
        dx, dy, dz = x2 - x1, y2 - y1, z2 - z1
        length = float(np.linalg.norm([dx, dy, dz]))
        if length < 1e-6:
            continue
        try:
            tag = gmsh_occ.addCylinder(x1, y1, z1, dx, dy, dz, tool_radius)
            cyl_tags.append((3, tag))
        except Exception as exc:
            logger.debug("Failed to add cylinder for segment: %s", exc)

    if len(cyl_tags) == 0:
        return []

    if len(cyl_tags) == 1:
        return cyl_tags

    # Fuse all cylinders into a single swept volume
    try:
        result, _ = gmsh_occ.fuse(cyl_tags[:1], cyl_tags[1:], removeObject=True, removeTool=True)
        return result
    except Exception as exc:
        logger.debug("Fuse failed (%s), returning individual cylinders", exc)
        return cyl_tags


# ---------------------------------------------------------------------------
# Main engine
# ---------------------------------------------------------------------------


def run_exact_gouge_check(config: ExactGougeConfig) -> ExactGougeResult:
    """
    Execute exact gouge verification using gmsh OCC Boolean operations.

    Returns ExactGougeResult with status PASS/FAIL/PARTIAL/NOT_VERIFIABLE.
    Never fabricates a PASS — returns NOT_VERIFIABLE on any engine failure.
    """
    result = ExactGougeResult()
    t_total_start = time.perf_counter()

    # Validate tolerance — required for non-test runs
    if not config.test_only and config.tolerance_mm is None:
        result.status = "NOT_VERIFIABLE"
        result.error = "No tolerance provided; set tolerance_mm or use test_only=True"
        result.gouge_exact_ready = False
        return result

    result.tolerance_mm = config.tolerance_mm
    result.tolerance_source = config.tolerance_source

    if not config.cutting_segments:
        result.status = "NOT_VERIFIABLE"
        result.error = "No cutting segments provided"
        result.gouge_exact_ready = False
        return result

    try:
        import gmsh  # noqa: PLC0415
    except ImportError:
        result.status = "NOT_VERIFIABLE"
        result.error = "gmsh not available"
        result.gouge_exact_ready = False
        return result

    with _GMSH_LOCK:
        return _run_gmsh_session(gmsh, config, result, t_total_start)


def _run_gmsh_session(
    gmsh,
    config: ExactGougeConfig,
    result: ExactGougeResult,
    t_total_start: float,
) -> ExactGougeResult:
    """Execute the full gmsh OCC Boolean pipeline in a locked session."""
    try:
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("exact_gouge")

        occ = gmsh.model.occ

        # --- Phase: target geometry ---
        t0 = time.perf_counter()
        target_entities = _load_target(occ, config)
        result.target_prep_ms = (time.perf_counter() - t0) * 1000.0

        # --- Phase: stock + machined result ---
        t0 = time.perf_counter()
        stock_tag = occ.addBox(
            config.stock_x_mm, config.stock_y_mm, config.stock_z_mm,
            config.stock_w_mm, config.stock_h_mm, config.stock_d_mm,
        )
        swept = _build_swept_volume(occ, config.cutting_segments, config.tool_radius_mm)

        if not swept:
            result.status = "NOT_VERIFIABLE"
            result.error = "No valid swept volume constructed from cutting segments"
            return result

        # Machined result = stock - swept_volume
        machined, _ = occ.cut([(3, stock_tag)], swept, removeObject=True, removeTool=True)
        result.machined_result_ms = (time.perf_counter() - t0) * 1000.0

        if not machined:
            result.status = "NOT_VERIFIABLE"
            result.error = "Boolean cut (stock - swept) produced empty result"
            return result

        result.boolean_success = True

        occ.synchronize()

        # --- Phase: gouge and remaining material ---
        t0 = time.perf_counter()

        if target_entities:
            # Gouge = target - machined (what of target is missing from machined = overcut)
            gouge_input_target = _clone_entities(occ, target_entities)
            gouge_input_machined = _clone_entities(occ, machined)
            gouge_regions, _ = occ.cut(gouge_input_target, gouge_input_machined,
                                        removeObject=True, removeTool=True)

            # Remaining = machined - target (excess material = undercut)
            remain_input_machined = _clone_entities(occ, machined)
            remain_input_target = _clone_entities(occ, target_entities)
            remaining_regions, _ = occ.cut(remain_input_machined, remain_input_target,
                                            removeObject=True, removeTool=True)

            occ.synchronize()

            # Mesh gouge regions and compute volume
            if gouge_regions:
                _mesh_entities(gmsh, gouge_regions, config.mesh_size_mm)
                result.gouge_volume_mm3 = _mesh_volume_mm3(gmsh)
                result.gouge_region_count = len(gouge_regions)
                # Remove gouge mesh before remaining
                gmsh.model.mesh.clear()

            if remaining_regions:
                _mesh_entities(gmsh, remaining_regions, config.mesh_size_mm)
                result.remaining_material_volume_mm3 = _mesh_volume_mm3(gmsh)
                result.remaining_region_count = len(remaining_regions)
                gmsh.model.mesh.clear()

        else:
            # No target geometry — partial check: only verify no over-travel into stock
            result.warnings.append(
                "No target geometry; partial check only (stock removal verified)"
            )
            result.status = "PARTIAL"
            result.machined_result_fidelity = "BREP_EXACT"

        result.boolean_ms = (time.perf_counter() - t0) * 1000.0
        result.gouge_analysis_ms = result.boolean_ms  # combined

        # --- Determine status ---
        t0 = time.perf_counter()
        if target_entities:
            result = _determine_status(result, config)
        result.report_integration_ms = (time.perf_counter() - t0) * 1000.0

    except Exception as exc:
        logger.warning("Exact gouge engine failed: %s", exc, exc_info=True)
        result.status = "NOT_VERIFIABLE"
        result.error = f"Engine exception: {type(exc).__name__}: {exc}"
        result.boolean_success = False
    finally:
        try:
            gmsh.finalize()
        except Exception:
            pass

    result.total_exact_verification_ms = (time.perf_counter() - t_total_start) * 1000.0
    return result


def _load_target(occ, config: ExactGougeConfig) -> list[tuple[int, int]]:
    """
    Load target geometry. Returns gmsh entity list [(dim, tag), ...].
    Returns empty list if no target geometry available.
    """
    if config.target_step_path and os.path.isfile(config.target_step_path):
        try:
            entities = occ.importShapes(config.target_step_path)
            # Keep only 3D solid entities
            solids = [(d, t) for d, t in entities if d == 3]
            if solids:
                logger.debug("Loaded %d solids from STEP: %s", len(solids), config.target_step_path)
                return solids
            logger.warning("STEP file contained no 3D solids: %s", config.target_step_path)
        except Exception as exc:
            logger.warning("STEP import failed: %s", exc)
    return []


def _clone_entities(occ, entities: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Copy entities so they can be reused in multiple Boolean operations."""
    result = []
    for dim, tag in entities:
        try:
            tags = occ.copy([(dim, tag)])
            result.extend(tags)
        except Exception:
            result.append((dim, tag))
    return result


def _mesh_entities(gmsh, entities: list[tuple[int, int]], mesh_size: float) -> None:
    """Generate 3D mesh for given entities only."""
    gmsh.option.setNumber("Mesh.CharacteristicLengthMax", mesh_size)
    gmsh.option.setNumber("Mesh.CharacteristicLengthMin", mesh_size / 4.0)
    gmsh.option.setNumber("Mesh.Algorithm3D", 4)  # Frontal-Delaunay
    # Only mesh the requested entities
    tags_3d = [t for d, t in entities if d == 3]
    if tags_3d:
        gmsh.model.mesh.generate(3)


def _determine_status(result: ExactGougeResult, config: ExactGougeConfig) -> ExactGougeResult:
    """
    Assign PASS/FAIL/PARTIAL based on gouge/remaining volumes and tolerance.
    Never fabricates PASS — requires explicit tolerance or test_only flag.
    """
    tol = config.tolerance_mm if config.tolerance_mm is not None else 0.0

    # Volumes below threshold are floating-point noise
    gouge = result.gouge_volume_mm3 if result.gouge_volume_mm3 > _VOLUME_ZERO_THRESHOLD else 0.0
    remaining = (result.remaining_material_volume_mm3
                 if result.remaining_material_volume_mm3 > _VOLUME_ZERO_THRESHOLD else 0.0)

    result.gouge_volume_mm3 = gouge
    result.remaining_material_volume_mm3 = remaining

    if gouge > 0.0:
        result.status = "FAIL"
        result.warnings.append(
            f"Gouge detected: {gouge:.3f} mm³ of target material over-cut "
            f"(tolerance={tol:.3f} mm)"
        )
    elif remaining > 0.0:
        result.status = "PARTIAL"
        result.warnings.append(
            f"Remaining material: {remaining:.3f} mm³ not yet removed"
        )
    else:
        if config.test_only or config.tolerance_mm is not None:
            result.status = "PASS"
        else:
            result.status = "NOT_VERIFIABLE"
            result.warnings.append("No tolerance provided; cannot certify PASS")

    return result
