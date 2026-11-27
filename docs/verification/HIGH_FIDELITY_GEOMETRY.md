# High-Fidelity Geometry — Exact Gouge Verification

**Beta**: 1.0.0-beta.5

---

## Fidelity Model

MachiningPro AI distinguishes two fidelity layers for exact gouge detection:

### A. Geometric Gouge Classification (B-Rep Boolean, exact)

The question "did the tool overcut the target?" is answered using
real OpenCASCADE B-Rep Boolean operations.

```
GOUGE_GEOMETRY_METHOD  = BREP_BOOLEAN_OCC
GOUGE_GEOMETRY_FIDELITY = BREP_EXACT
```

This is correct at the precision limit of floating-point B-Rep.
A gouge region either exists or does not exist as a solid in the
Boolean result. There is no volumetric approximation in this step.

### B. Gouge Volume Measurement (tetrahedral mesh, approximate)

Volume reporting uses tetrahedral mesh integration:

```
GOUGE_VOLUME_METHOD  = TETRAHEDRAL_MESH_INTEGRATION
GOUGE_VOLUME_FIDELITY = APPROXIMATE_NUMERICAL_INTEGRATION
VOLUME_INTEGRATION_ERROR_PCT = 0.42  (measured, not suppressed)
```

The ~0.42% error is consistent across test cases. It arises from
tetrahedral facet approximation of curved surfaces (cylinder caps,
swept tool paths).

**Do not display this volume as "exact B-Rep volume".**

---

## Target Geometry

When a target STEP file is provided:

```
TARGET_GEOMETRY_SOURCE = STEP_FILE
TARGET_GEOMETRY_FIDELITY = BREP_EXACT
```

The gmsh OCC kernel imports the STEP file as B-Rep solids via
`gmsh.model.occ.importShapes(path)`. The returned solids retain
the full OpenCASCADE B-Rep representation.

Without a target STEP file:

```
TARGET_GEOMETRY_FIDELITY = NOT_AVAILABLE
GOUGE_EXACT_STATUS = PARTIAL  (stock removal only)
```

---

## Comparison to Prior State

| Attribute | beta.4 (KL-07 open) | beta.5 (KL-07 resolved) |
|-----------|---------------------|-------------------------|
| Engine | NOT_AVAILABLE | BREP_BOOLEAN_OCC |
| Geometry fidelity | N/A | BREP_EXACT |
| Volume fidelity | N/A | APPROXIMATE_NUMERICAL_INTEGRATION |
| Gouge classification | NOT_VERIFIABLE | PASS / FAIL / PARTIAL |
| Required install | pythonocc (not available) | gmsh 4.x (already installed) |

---

## KL-07 Resolution

**KL-07** was raised in beta.4: "Exact gouge detection requires
mesh-vs-mesh or B-Rep Boolean engine not available in this
environment (pythonocc not installed)."

**Resolution** (beta.5): gmsh 4.x provides the OpenCASCADE B-Rep
Boolean API (`gmsh.model.occ.*`) without requiring pythonocc.
The same OCC Boolean operations (cut, fuse, addBox, addCylinder)
are available through the gmsh Python interface.

**What remains approximate**: the numerical *volume* of the gouge
region is computed via tetrahedral mesh integration, with ~0.42%
measured error. The *presence/absence* of the gouge region is
determined by exact B-Rep Boolean operations.

**Missing tolerance still returns NOT_VERIFIABLE**: if no tolerance
is provided and `test_only=False`, the engine returns NOT_VERIFIABLE
rather than silently PASS. This is the correct fail-closed behavior.
