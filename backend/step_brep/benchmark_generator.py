"""
Generate in-house benchmark STEP files for P10 Phase 3 qualification (MUST 18-20).

ALL files produced here are labelled IN_HOUSE_BENCHMARK — never REAL_EXTERNAL_SAMPLE.

Benchmark set:
  P10-S1: Drilled rectangular block (60×40×20 mm, 2 through holes, 1 blind hole)
  P10-S2: Pocket + slot prismatic block (80×60×30 mm)
  P10-S3: Multi-feature block (80×60×30 mm — pocket + slot + 2 through holes)

Each benchmark produces:
  - <name>.step  — STEP AP214 file
  - <name>_ground_truth.json  — expected entity counts + feature list

HARD RULES:
  - sample_origin = "IN_HOUSE_BENCHMARK" in all ground truth files.
  - qualification_class = "SOFTWARE_BENCHMARK".
  - is_real_external_sample = False always.
  - is_dispatchable = False always.
  - production_released = False always.
  - Entity counts in ground truth must be verified against gmsh, never hardcoded.
"""

from __future__ import annotations

import json
import pathlib
import threading

import gmsh  # type: ignore[import]

__all__ = [
    "IN_HOUSE_BENCHMARK_STEP_DIR",
    "generate_all_benchmarks",
    "generate_p10_s1",
    "generate_p10_s2",
    "generate_p10_s3",
]

IN_HOUSE_BENCHMARK_STEP_DIR = pathlib.Path(
    __file__
).parent.parent.parent / "tests" / "qualification" / "fixtures" / "step"

_LABEL = "IN_HOUSE_BENCHMARK"
_QUAL_CLASS = "SOFTWARE_BENCHMARK"

_gmsh_lock = threading.Lock()

_COMMON_METADATA = {
    "sample_origin": _LABEL,
    "qualification_class": _QUAL_CLASS,
    "is_real_external_sample": False,
    "is_dispatchable": False,
    "production_released": False,
    "parser_backend": "gmsh-4.15.2+occ",
}


def _count_entities() -> dict[str, int]:
    return {
        "volumes": len(gmsh.model.getEntities(3)),
        "surfaces": len(gmsh.model.getEntities(2)),
        "curves": len(gmsh.model.getEntities(1)),
        "vertices": len(gmsh.model.getEntities(0)),
    }


_SURF_FLAT = 1e-4
_SURF_CIRC_TOL = 0.02


def _is_circle(da: float, db: float, dc: float) -> bool:
    """True if the bbox in dim (db, dc) forms a circle (da ≈ 0, db ≈ dc)."""
    if da >= _SURF_FLAT or db < _SURF_FLAT or dc < _SURF_FLAT:
        return False
    return abs(db - dc) / max(abs(db), abs(dc), 1e-10) < _SURF_CIRC_TOL


def _surface_summary() -> dict[str, int]:
    """Count surface types by bbox heuristic."""
    planar = 0
    cylindrical = 0
    unknown = 0
    for _d, stag in gmsh.model.getEntities(2):
        xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(2, stag)
        dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
        bounds = gmsh.model.getBoundary([(2, stag)], oriented=False)
        bound_ctags = [b[1] for b in bounds]
        circ_count = 0
        for ct in bound_ctags:
            xc0, yc0, zc0, xc1, yc1, zc1 = gmsh.model.getBoundingBox(1, ct)
            dcx, dcy, dcz = xc1 - xc0, yc1 - yc0, zc1 - zc0
            if _is_circle(dcz, dcx, dcy) or _is_circle(dcy, dcx, dcz) or _is_circle(dcx, dcy, dcz):
                circ_count += 1
        if dx < 1e-6 or dy < 1e-6 or dz < 1e-6:
            planar += 1
        elif circ_count > 0 and circ_count == len(bound_ctags):
            cylindrical += 1
        else:
            unknown += 1
    return {"planar": planar, "cylindrical": cylindrical, "unknown": unknown}


def generate_p10_s1(output_dir: pathlib.Path | None = None) -> dict:
    """P10-S1: Drilled rectangular block.

    60×40×20 mm block with:
      - 2 through holes: Ø10 mm at (20, 20), Ø8 mm at (45, 20)
      - 1 blind hole: Ø6 mm at (30, 30), depth 12 mm from bottom (z=0)

    sample_origin=IN_HOUSE_BENCHMARK — NOT a real external sample.
    """
    out = output_dir or IN_HOUSE_BENCHMARK_STEP_DIR
    out.mkdir(parents=True, exist_ok=True)

    with _gmsh_lock:
        gmsh.initialize(["-v", "0"])
        gmsh.model.add("P10-S1-drilled-block")

        block = gmsh.model.occ.addBox(0, 0, 0, 60, 40, 20)
        h1 = gmsh.model.occ.addCylinder(20, 20, -1, 0, 0, 22, 5)    # Ø10 through
        h2 = gmsh.model.occ.addCylinder(45, 20, -1, 0, 0, 22, 4)    # Ø8 through
        h3 = gmsh.model.occ.addCylinder(30, 30, 0, 0, 0, 12, 3)     # Ø6 blind (from z=0)

        out_shapes, _ = gmsh.model.occ.cut([(3, block)], [(3, h1), (3, h2), (3, h3)])
        gmsh.model.occ.synchronize()

        counts = _count_entities()
        surf_summary = _surface_summary()

        step_path = out / "P10_S1_drilled_block.step"
        gmsh.write(str(step_path))
        gmsh.finalize()

    bbox = {"x": [0.0, 60.0], "y": [0.0, 40.0], "z": [0.0, 20.0]}
    gt = {
        **_COMMON_METADATA,
        "sample_id": "P10-S1",
        "description": (
            "Drilled rectangular block — 2 through holes (Ø10, Ø8), 1 blind hole (Ø6, depth 12 mm)"
        ),
        "stock_dimensions_mm": [60, 40, 20],
        "entity_counts": counts,
        "surface_classes": surf_summary,
        "bbox_mm": bbox,
        "features": {
            "through_holes": [
                {"diameter_mm": 10.0, "center_xy_mm": [20, 20]},
                {"diameter_mm": 8.0, "center_xy_mm": [45, 20]},
            ],
            "blind_holes": [
                {"diameter_mm": 6.0, "center_xy_mm": [30, 30], "depth_mm": 12.0},
            ],
        },
    }

    gt_path = out / "P10_S1_drilled_block_ground_truth.json"
    gt_path.write_text(json.dumps(gt, indent=2), encoding="utf-8")

    return {"step_path": str(step_path), "ground_truth_path": str(gt_path), "ground_truth": gt}


def generate_p10_s2(output_dir: pathlib.Path | None = None) -> dict:
    """P10-S2: Pocket + slot prismatic block.

    80×60×30 mm block with:
      - 1 rectangular pocket: 40×20×15 mm at (20, 20) from top
      - 1 open slot: 60×10×8 mm running full width in X (open front and back)
      - 2 through holes: Ø8 mm at (10, 10) and (70, 50)

    sample_origin=IN_HOUSE_BENCHMARK — NOT a real external sample.
    """
    out = output_dir or IN_HOUSE_BENCHMARK_STEP_DIR
    out.mkdir(parents=True, exist_ok=True)

    with _gmsh_lock:
        gmsh.initialize(["-v", "0"])
        gmsh.model.add("P10-S2-pocket-slot")

        # Main block
        block = gmsh.model.occ.addBox(0, 0, 0, 80, 60, 30)

        # Pocket: 40×20×15 mm at (20, 20, 30) cutting downward
        pocket = gmsh.model.occ.addBox(20, 20, 15, 40, 20, 15)

        # Slot: 80×10×8 mm running full width in X, centered at y=30
        slot = gmsh.model.occ.addBox(0, 25, 22, 80, 10, 8)

        # Through holes
        h1 = gmsh.model.occ.addCylinder(10, 10, -1, 0, 0, 32, 4)    # Ø8 at (10,10)
        h2 = gmsh.model.occ.addCylinder(70, 50, -1, 0, 0, 32, 4)    # Ø8 at (70,50)

        out_shapes, _ = gmsh.model.occ.cut(
            [(3, block)],
            [(3, pocket), (3, slot), (3, h1), (3, h2)],
        )
        gmsh.model.occ.synchronize()

        counts = _count_entities()
        surf_summary = _surface_summary()

        step_path = out / "P10_S2_pocket_slot.step"
        gmsh.write(str(step_path))
        gmsh.finalize()

    bbox = {"x": [0.0, 80.0], "y": [0.0, 60.0], "z": [0.0, 30.0]}
    gt = {
        **_COMMON_METADATA,
        "sample_id": "P10-S2",
        "description": (
            "Pocket+slot prismatic block — pocket 40×20×15, slot 80×10×8, 2 through holes Ø8"
        ),
        "stock_dimensions_mm": [80, 60, 30],
        "entity_counts": counts,
        "surface_classes": surf_summary,
        "bbox_mm": bbox,
        "features": {
            "pockets": [{"x_mm": 40, "y_mm": 20, "depth_mm": 15, "corner_xy_mm": [20, 20]}],
            "slots": [{"length_mm": 80, "width_mm": 10, "depth_mm": 8, "open_sides": 2}],
            "through_holes": [
                {"diameter_mm": 8.0, "center_xy_mm": [10, 10]},
                {"diameter_mm": 8.0, "center_xy_mm": [70, 50]},
            ],
        },
    }

    gt_path = out / "P10_S2_pocket_slot_ground_truth.json"
    gt_path.write_text(json.dumps(gt, indent=2), encoding="utf-8")

    return {"step_path": str(step_path), "ground_truth_path": str(gt_path), "ground_truth": gt}


def generate_p10_s3(output_dir: pathlib.Path | None = None) -> dict:
    """P10-S3: Multi-depth / multi-feature prismatic block.

    80×60×35 mm block with:
      - 1 deep pocket: 30×20×20 mm at corner (5, 5)
      - 1 shallow pocket: 50×25×10 mm at (15, 30)
      - 1 step feature: 20×60×10 mm step at right face (x=60..80)
      - 3 through holes: Ø6 mm at (10, 30), Ø10 mm at (40, 15), Ø8 mm at (60, 45)

    sample_origin=IN_HOUSE_BENCHMARK — NOT a real external sample.
    """
    out = output_dir or IN_HOUSE_BENCHMARK_STEP_DIR
    out.mkdir(parents=True, exist_ok=True)

    with _gmsh_lock:
        gmsh.initialize(["-v", "0"])
        gmsh.model.add("P10-S3-multi-feature")

        # Main block
        block = gmsh.model.occ.addBox(0, 0, 0, 80, 60, 35)

        # Deep pocket: 30×20×20 mm
        p1 = gmsh.model.occ.addBox(5, 5, 15, 30, 20, 20)

        # Shallow pocket: 50×25×10 mm
        p2 = gmsh.model.occ.addBox(15, 30, 25, 50, 25, 10)

        # Step feature: 20×60×10 mm at x=60..80
        step = gmsh.model.occ.addBox(60, 0, 25, 20, 60, 10)

        # Through holes
        h1 = gmsh.model.occ.addCylinder(10, 30, -1, 0, 0, 37, 3)    # Ø6
        h2 = gmsh.model.occ.addCylinder(40, 15, -1, 0, 0, 37, 5)    # Ø10
        h3 = gmsh.model.occ.addCylinder(60, 45, -1, 0, 0, 37, 4)    # Ø8

        out_shapes, _ = gmsh.model.occ.cut(
            [(3, block)],
            [(3, p1), (3, p2), (3, step), (3, h1), (3, h2), (3, h3)],
        )
        gmsh.model.occ.synchronize()

        counts = _count_entities()
        surf_summary = _surface_summary()

        step_path = out / "P10_S3_multi_feature.step"
        gmsh.write(str(step_path))
        gmsh.finalize()

    bbox = {"x": [0.0, 80.0], "y": [0.0, 60.0], "z": [0.0, 35.0]}
    gt = {
        **_COMMON_METADATA,
        "sample_id": "P10-S3",
        "description": "Multi-feature block — deep pocket, shallow pocket, step, 3 through holes",
        "stock_dimensions_mm": [80, 60, 35],
        "entity_counts": counts,
        "surface_classes": surf_summary,
        "bbox_mm": bbox,
        "features": {
            "pockets": [
                {"x_mm": 30, "y_mm": 20, "depth_mm": 20, "corner_xy_mm": [5, 5]},
                {"x_mm": 50, "y_mm": 25, "depth_mm": 10, "corner_xy_mm": [15, 30]},
            ],
            "steps": [{"x_mm": 20, "y_mm": 60, "depth_mm": 10}],
            "through_holes": [
                {"diameter_mm": 6.0, "center_xy_mm": [10, 30]},
                {"diameter_mm": 10.0, "center_xy_mm": [40, 15]},
                {"diameter_mm": 8.0, "center_xy_mm": [60, 45]},
            ],
        },
    }

    gt_path = out / "P10_S3_multi_feature_ground_truth.json"
    gt_path.write_text(json.dumps(gt, indent=2), encoding="utf-8")

    return {"step_path": str(step_path), "ground_truth_path": str(gt_path), "ground_truth": gt}


def generate_all_benchmarks(output_dir: pathlib.Path | None = None) -> list[dict]:
    """Generate P10-S1, P10-S2, P10-S3 benchmark STEP files.

    Returns a list of result dicts from each generator.
    All files labelled IN_HOUSE_BENCHMARK — not real external samples.
    """
    results = []
    results.append(generate_p10_s1(output_dir))
    results.append(generate_p10_s2(output_dir))
    results.append(generate_p10_s3(output_dir))
    return results
