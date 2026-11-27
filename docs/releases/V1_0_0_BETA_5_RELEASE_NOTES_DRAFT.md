# MachiningPro AI v1.0.0-beta.5 — Exact Gouge & High-Fidelity Geometry Public Beta

**Version**: 1.0.0-beta.5  
**Date**: 2026-11-27  
**Status**: Public Beta — NOT PRODUCTION READY  
**Commits**: 90fa353 → 541aea0 → 609b19b → (version bump)

---

## Summary

v1.0.0-beta.5 delivers the Exact Gouge Detection milestone: the first release
where `GOUGE_EXACT` can return `PASS`, `FAIL`, or `PARTIAL` on real part geometry,
rather than always `NOT_VERIFIABLE` (KL-07, resolved).

The engine uses the OpenCASCADE B-Rep Boolean API provided by gmsh 4.x
(`BREP_BOOLEAN_OCC`). No pythonocc or separate OCC installation is required.

---

## What's New

### Exact Gouge Detection (KL-07 Resolved)

**Geometric classification uses B-Rep Boolean operations (exact).**

The tool swept-volume is constructed as a union of cylinder solids along each
cutting segment. The machined result is computed as `stock − swept_volume`.
The gouge region is `target − machined_result`. The remaining material region
is `machined_result − target`. All three operations use OpenCASCADE B-Rep
Boolean algebra.

```
GOUGE_GEOMETRY_METHOD  = BREP_BOOLEAN_OCC
GOUGE_GEOMETRY_FIDELITY = BREP_EXACT
```

**Volume measurement uses tetrahedral mesh integration (approximate).**

The Boolean result solid is meshed with `gmsh.model.mesh.generate(3)` and
volumes are computed by summing tetrahedral element volumes. Measured error:
~0.42%. This is explicitly disclosed — do not describe reported volumes as
mathematically exact.

```
GOUGE_VOLUME_METHOD  = TETRAHEDRAL_MESH_INTEGRATION
GOUGE_VOLUME_FIDELITY = APPROXIMATE_NUMERICAL_INTEGRATION
VOLUME_INTEGRATION_ERROR_PCT = 0.42
```

### Real STEP Target Geometry

Target part geometry is imported directly from STEP files via
`gmsh.model.occ.importShapes`. The imported solid retains full B-Rep
representation for Boolean operations.

```
TARGET_GEOMETRY_SOURCE   = STEP_FILE
TARGET_GEOMETRY_FIDELITY = BREP_EXACT
```

### Machined-Result Geometry

The machined result (`stock − swept_volume`) is a true B-Rep solid,
not a voxel approximation.

```
MACHINED_RESULT_METHOD   = BOOLEAN_BREP
MACHINED_RESULT_FIDELITY = BREP_EXACT
```

### Gouge / Overcut Detection

```
KNOWN_NO_GOUGE_RESULT  = PASS   (exact tool match, no overcut)
KNOWN_GOUGE_RESULT     = FAIL   (oversized tool → gouge_volume > 0)
BOOLEAN_FAILURE_RETURNS_PASS = NO (fail-closed: not PASS without confirmed Boolean)
```

### Remaining Material Detection

Insufficient material removal (undersized tool, missed passes):

```
KNOWN_REMAINING_RESULT = DETECTED
REMAINING_VOLUME > 0
```

Gouge and remaining material are independent — both can be non-zero on the
same operation.

### Tolerance-Aware Verification

Tolerance source is always explicit:

```
tolerance_source ∈ {DRAWING_REQUIREMENT, USER_PROVIDED, PROJECT_SETTING,
                    ENGINEER_CONFIRMED, TEST_ONLY_DIAGNOSTIC}
```

Missing tolerance → `NOT_VERIFIABLE` (not `PASS`).

### Exact/Conservative Verification Separation

The exact engine (`GOUGE_EXACT`) and the conservative bbox check (`PART_GOUGE`)
are independent. Conservative `PARTIAL` is never promoted to exact `PASS`.

```
CONSERVATIVE_RESULT_NOT_PROMOTED_TO_EXACT = YES
```

### Exact Result Persistence

Exact gouge status, method, and fidelity survive backend restart via
Pydantic JSON round-trip through the ManufacturingPlan SQLite store.

```
GOUGE_RESULT_SURVIVES_RESTART   = YES
GOUGE_METHOD_SURVIVES_RESTART   = YES
GOUGE_TOLERANCE_SURVIVES_RESTART = YES
GOUGE_PROVENANCE_SURVIVES_RESTART = YES
```

### Exact Verification Reporting

All existing export formats now include exact gouge fields:

| Format | Status |
|--------|--------|
| PDF    | YES |
| DOCX   | YES |
| XLSX   | YES |
| JSON   | YES |
| ZIP    | YES |

Report includes: Exact Gouge Status, Geometry Method, Geometry Fidelity,
Volume Method, Volume Fidelity, Tolerance, Tolerance Source, Gouge Volume,
Max Gouge Depth, Gouge Region Count, Remaining Material Volume.

### Fail-Closed Boolean Semantics

Engine failure, missing geometry, or degenerate input → `NOT_VERIFIABLE`.
Never silent `PASS` on Boolean failure.

---

## Safety

All safety invariants from prior releases are preserved and enforced
in orchestrator Phase Q:

```
EXACT_VERIFICATION_CAN_AUTO_APPROVE    = NO
EXACT_VERIFICATION_CAN_RELEASE_PRODUCTION = NO
VERIFICATION_CAN_DISPATCH_CNC          = NO
AUTO_CAM_CAN_DISPATCH_CNC              = NO
REAL_MACHINE_WRITE_FOUND               = NO
GCODE_DISPATCH_FOUND                   = NO
```

GOUGE_EXACT=PASS does NOT authorize machining, dispatch, or production release.

---

## Known Limitations

| ID | Description | Severity |
|----|-------------|----------|
| KL-26 | Gouge **volume** is approximate (tetrahedral mesh, ~0.42% error) | MEDIUM — always disclosed |
| KL-27 | Tool geometry is parametric cylinder only (no taper/radius/flute) | MEDIUM — conservative for FAIL |
| KL-11 | Stock removal uses VOXEL_APPROXIMATE | MEDIUM — existing |
| KL-08 | Fixture collision NOT_PERFORMED without fixture geometry | LOW |
| KL-09 | Holder collision NOT_PERFORMED without holder geometry | LOW |
| KL-21 | Holder/fixture collision uses SIMPLIFIED_CYLINDER fidelity | LOW |
| KL-05 | Cutting parameters NOT_AVAILABLE for most materials | LOW |
| KL-19 | other_cost always NOT_PROVIDED; max completeness 87.5% | LOW |

---

## Readiness

```
PUBLIC_DEMO_READY    = YES
CLOSED_BETA_READY    = YES
PUBLIC_BETA_READY    = YES
PRODUCTION_READY     = NO
```

**Production readiness** requires broader independently demonstrated
manufacturing validation beyond this beta qualification. The
approximate volume (KL-26) and parametric tool model (KL-27) must be
evaluated for each production use case by a qualified engineer.

---

## Test Coverage

| Suite | Tests | Status |
|-------|-------|--------|
| Exact geometry (Phases 1-14) | 24 | PASS |
| Safety + live acceptance (Phases 15-20) | 36 | PASS |
| Unit/perf/persist/sep (MUSTs 21-26) | 17 | PASS |
| Gouge semantics | 48 | PASS |
| **Total verification** | **141** | **PASS** |
| Reports | 348 | PASS |
| Persistence / manufacturing plan | 759 | PASS |
| Backend unit (total) | 12,462 | PASS |
| New failures introduced | 0 | — |

---

## Upgrade Notes

- No migration required for existing AutoCAM plans
- New `VerificationSummaryResult` fields (`gouge_geometry_method`,
  `gouge_geometry_fidelity`, `gouge_volume_method`, `gouge_volume_fidelity`)
  default to `BREP_BOOLEAN_OCC` / `NOT_AVAILABLE` / `TETRAHEDRAL_MESH_INTEGRATION`
  / `APPROXIMATE_NUMERICAL_INTEGRATION` on old plans
- `WsSimResponse` gains 4 new fidelity fields; existing clients ignore them
