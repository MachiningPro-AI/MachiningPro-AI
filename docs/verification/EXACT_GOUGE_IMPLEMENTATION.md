# Exact Gouge Detection — Implementation

**Version**: 1.0.0-beta.5  
**KL-07**: RESOLVED  
**Geometry Engine**: BREP_BOOLEAN_OCC (gmsh 4.x OpenCASCADE kernel)

---

## Architecture

### Geometric Classification (B-Rep Boolean, exact)

The engine uses `gmsh.model.occ` (OpenCASCADE) for all Boolean operations.
No pythonocc or OCC installation is required.

```
stock_solid       → gmsh.model.occ.addBox(x, y, z, w, h, d)
swept_volume      → union of gmsh.model.occ.addCylinder per cutting segment
machined_result   → gmsh.model.occ.cut(stock, swept_volume)
gouge_region      → gmsh.model.occ.cut(target, machined_result)
remaining_region  → gmsh.model.occ.cut(machined_result, target)
```

The Boolean intersection result is B-Rep exact.
`GOUGE_GEOMETRY_FIDELITY = BREP_EXACT`

### Volume Measurement (tetrahedral mesh integration, approximate)

Volume is computed by meshing the Boolean result solid with
`gmsh.model.mesh.generate(3)` and summing tetrahedral element volumes:

```
V = Σ |dot(d1, cross(d2, d3))| / 6  for each tetrahedron
```

Measured error: ~0.42% on analytic reference cases.
`GOUGE_VOLUME_FIDELITY = APPROXIMATE_NUMERICAL_INTEGRATION`

**Important**: do NOT describe reported volumes as mathematically exact.
The geometric presence/absence decision is exact (B-Rep); the numeric
volume is an approximation.

### Volume Isolation

`_isolate_and_mesh()` removes all 3D model entities except the
measurement target before calling `gmsh.model.mesh.generate(3)`.
Without this isolation, adjacent solids (machined result, target)
inflate the reported volume.

---

## Status / Fidelity Fields

| Field | Value | Meaning |
|-------|-------|---------|
| `GOUGE_GEOMETRY_METHOD` | `BREP_BOOLEAN_OCC` | OCC B-Rep Boolean intersection |
| `GOUGE_GEOMETRY_FIDELITY` | `BREP_EXACT` | B-Rep solids, exact classification |
| `GOUGE_VOLUME_METHOD` | `TETRAHEDRAL_MESH_INTEGRATION` | Tetrahedral mesh volume |
| `GOUGE_VOLUME_FIDELITY` | `APPROXIMATE_NUMERICAL_INTEGRATION` | ~0.42% error |
| `VOLUME_INTEGRATION_ERROR_PCT` | `0.42` | Measured, preserved, not hidden |

---

## Engine Result Status

| Status | Meaning |
|--------|---------|
| `PASS` | Boolean succeeded; no material overcut beyond tolerance |
| `FAIL` | Boolean succeeded; gouge_region volume > tolerance |
| `PARTIAL` | Stock removal verified; no target STEP file provided |
| `NOT_VERIFIABLE` | Boolean failed, missing tolerance, or engine error |

---

## Safety Invariants

The exact gouge result **cannot** mutate any dispatch or approval gate.
All six invariants are hardcoded `False` in the orchestrator Phase Q:

- `EXACT_VERIFICATION_CAN_AUTO_APPROVE = NO`
- `EXACT_VERIFICATION_CAN_RELEASE_PRODUCTION = NO`
- `VERIFICATION_CAN_DISPATCH_CNC = NO`
- `AUTO_CAM_CAN_DISPATCH_CNC = NO`
- `REAL_MACHINE_WRITE_FOUND = NO`
- `GCODE_DISPATCH_FOUND = NO`

---

## Thread Safety

`_GMSH_LOCK = threading.Lock()` serializes all gmsh sessions.
gmsh is not thread-safe; concurrent requests are serialized.

---

## Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| `test_exact_gouge.py` | 24 | PASS |
| `test_exact_gouge_phase15_20.py` | 36 | PASS |
| `test_exact_gouge_must21_26.py` | 17 | PASS |
| `test_gouge_semantics.py` | 48 | PASS |
| **Total verification** | **124** | **PASS** |
