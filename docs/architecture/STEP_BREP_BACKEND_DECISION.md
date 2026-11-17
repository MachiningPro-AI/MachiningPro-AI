# STEP B-Rep Backend Decision — P10 Phase 3

**Decision date:** 2026-11-17  
**Decision ID:** BREP-BACKEND-P10-PHASE3  
**Status:** ACTIVE

---

## Decision

**SELECTED_BREP_BACKEND = gmsh**  
**SELECTED_VERSION = gmsh==4.15.2** (already declared in `pyproject.toml`)

---

## Context

P10 Phase 2 established that `REAL_STEP_SAMPLE_COUNT=0` and no B-Rep parser was
installed.  Phase 3 requires a minimal STEP/B-Rep parser that can:

1. Read a STEP file (AP214/AP242/AP203) and report entity counts
2. Extract topology: volumes, surfaces, edges, vertices, bounding boxes
3. Classify surface types: PLANAR, CYLINDRICAL, UNKNOWN
4. Detect hole candidates from cylindrical surfaces
5. Write in-house benchmark STEP files for qualification

The constraint is: **zero new package dependencies**.

---

## Candidates Evaluated

| Candidate | Available? | New deps? | Notes |
|-----------|-----------|-----------|-------|
| `pythonocc-core` | No | ~~1~~ | Not on pip for Python 3.12 Windows |
| `cadquery 2.8.0` | Yes (pip) | Yes (~500 MB) | Pulls vtk, trame, casadi, numba |
| `gmsh==4.15.2` | **Already installed** | Zero | Bundles OpenCASCADE internally |
| `build123d` | No pip install | Yes | Not available |

---

## Selection Rationale

### gmsh 4.15.2 — Zero new dependencies

`gmsh==4.15.2` is already declared in `pyproject.toml` (added in Stage 22D.3 for
meshing and STEP binary detection).  It bundles OpenCASCADE internally and exposes
its full Python API including:

- `gmsh.model.occ.importShapes(path)` — read STEP into OCC model
- `gmsh.write("file.step")` — write STEP files
- `gmsh.model.getEntities(dim)` — topology counts: 3=volumes, 2=surfaces, 1=curves, 0=vertices
- `gmsh.model.getBoundingBox(dim, tag)` — per-entity bounding box
- `gmsh.model.getNormal(tag, [u, v])` — surface normal at parametric point
- `gmsh.model.getBoundary(entities)` — topological adjacency
- `gmsh.model.occ.addBox()`, `addCylinder()`, boolean operations — geometry creation

Smoke tests (2026-11-17) confirmed:
- Box: v=1, s=6, c=12, write/read-back PASS
- Drilled block (60×40×20, Ø10 through hole): v=1, s=7, c=15, write/read-back PASS
- Surface classification via bbox: PLANAR (flat dimension), CYLINDRICAL (2 loops)
- Circular arc detection: bbox (10×10×0) → diameter=10 mm

---

## Architecture Constraints

| Constraint | Value |
|------------|-------|
| `REAL_STEP_SAMPLE_COUNT` | Remains 0 (counts only real external samples) |
| `IN_HOUSE_BENCHMARK_STEP_COUNT` | ≥ 3 after Phase 3 |
| `is_dispatchable` | Always `False` |
| `production_released` | Always `False` |
| Sample origin label | `IN_HOUSE_BENCHMARK` for generated files |
| External label | `UNKNOWN_EXTERNAL` until provenance verified |
| Fabricated topology | NEVER |
| Fabricated body/face count | NEVER |
| Fabricated bounding box | NEVER |

---

## Implementation Files

```
backend/step_brep/
  __init__.py
  gmsh_step_parser.py      — Core STEP parser (MUST 9-11)
  surface_classifier.py    — PLANAR/CYLINDRICAL/UNKNOWN (MUST 15-16)
  topology_adapter.py      — CanonicalTopology wiring (MUST 12-14)
  feature_detector.py      — HOLE_CANDIDATE from cylindrical faces (MUST 17)
  verification_adapter.py  — P8/P9 verification input (MUST 24-26)
  benchmark_generator.py   — IN_HOUSE_BENCHMARK STEP files (MUST 18-20)
```

---

## Dependency Files Changed

`DEPENDENCY_FILES_CHANGED = NO` — gmsh already in `pyproject.toml`.

---

## References

- `pyproject.toml` — `gmsh==4.15.2` dependency
- `docs/STEP_LEVEL2_DEPENDENCY.md` — prior dependency notes
- `backend/cad_import/step_intake.py` — P10-B intake gate
- `docs/qualification/P10_PHASE2_REAL_STEP_READINESS.md` — Phase 2 readiness assessment
