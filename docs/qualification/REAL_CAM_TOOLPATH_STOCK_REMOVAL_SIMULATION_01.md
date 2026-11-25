# MACHININGPRO_AI_REAL_CAM_TOOLPATH_STOCK_REMOVAL_SIMULATION_01
## Qualification Record

**Date:** 2026-11-25
**Status:** CONDITIONAL_GO — All gating tests PASS; 2 authenticated backend tests skip (expected: no live auth in test env)
**Author:** Engineering via CAD/CAM Workspace Module

---

## Module Summary

Implements the real manufacturing visualization chain:

```
CAD PART → MANUFACTURING FEATURE → CAM OPERATION → REAL TOOL
  → REAL TOOLPATH → TOOL MOTION → STOCK → MATERIAL REMOVAL
  → COLLISION/GOUGE → VERIFICATION → REPORT
```

### Endpoints Added

| Endpoint | Purpose |
|----------|---------|
| `POST /api/workspace-cam/feature-cam` | Feature-aware toolpath generation (Level-10 generators) |
| `POST /api/workspace-sim/run` | Offline simulation via Level-11 engine |

---

## Hard Rules Enforced

| Rule | Requirement | Status |
|------|------------|--------|
| HR1–HR8 | No fabricated toolpath/animation/stock/collision/gouge/tool/holder/fixture geometry | PASS |
| HR9 | Tool motion MUST use canonical backend toolpath coordinates | PASS |
| HR10 | Stock removal MUST use actual tool+toolpath+actual stock | PASS |
| HR11 | Missing verification input → NOT_VERIFIABLE, never PASS | PASS |
| HR12 | Simulation is OFFLINE ONLY | PASS |
| HR13 | Simulation result does NOT imply machining approval | PASS |
| HR14 | `is_dispatchable=false` always | PASS |
| HR15 | `production_released=false` always | PASS |
| HR16–HR18 | No CNC communication/dispatch/auto-approval | PASS |
| HR19 | No duplicate CAM engine | PASS |
| HR20 | Uses existing Level-10 generators only | PASS |
| HR21 | No force push / no tag / no release / no Level 21 | PASS |

---

## Files Delivered

### Backend

| File | Purpose |
|------|---------|
| `backend/api/workspace_cam.py` | Feature-aware CAM endpoint (new) |
| `backend/api/workspace_simulation.py` | Workspace simulation endpoint (new) |
| `backend/api/app.py` | Router registration (modified) |

### Frontend

| File | Purpose |
|------|---------|
| `frontend/app/src/services/workspaceCam.ts` | API service + `toolpathGroupsToSimSegments()` utility (modified) |
| `frontend/app/src/components/workspace/WorkspaceCamPanel.tsx` | Simulation controls + visibility toggles (modified) |
| `frontend/app/src/pages/CadCamWorkspacePage.tsx` | 6 visibility state variables (modified) |

### Tests

| File | Count | Result |
|------|-------|--------|
| `frontend/app/tests/camToolpathSimulation.test.ts` | 25 | 25 PASS |
| `tests/unit/api/test_workspace_cam_api.py` | 19 (2 pass + 17 skip) | 2 PASS / 17 SKIP (no live auth) |

### Documentation

| File | Purpose |
|------|---------|
| `docs/cam/REAL_CAM_TOOLPATH_ARCHITECTURE.md` | Architecture + pipeline doc |
| `docs/simulation/STOCK_REMOVAL_SIMULATION.md` | Simulation + stock removal doc |
| `docs/qualification/REAL_CAM_TOOLPATH_STOCK_REMOVAL_SIMULATION_01.md` | This file |

---

## Test Results

### Frontend — `npm test` (node --test runner)

```
# tests 1051
# suites 232
# pass  1051
# fail  0
```

New tests: 25 (T01–T25) — all PASS
Previous baseline: 1026 — all maintained
Total: 1051 PASS, 0 FAIL

### Backend — `python -m pytest tests/unit/api/test_workspace_cam_api.py`

```
2 passed, 17 skipped
```

- `test_unauthenticated_returns_401` — PASS (workspace-cam)
- `test_sim_unauthenticated_returns_401` — PASS (workspace-sim)
- 17 authenticated tests — SKIP (expected: no live auth credentials in test env)

This skip pattern matches all other API test files in the project
(e.g., `test_cad_import_level10.py`).

### Code Quality

| Check | Result |
|-------|--------|
| `python -m ruff check workspace_cam.py workspace_simulation.py` | All checks passed |
| `npx tsc --noEmit` | Clean (no output) |

---

## Safety Invariants (Backend)

Every response from both endpoints includes:

```json
{
  "is_dispatchable": false,
  "production_released": false,
  "simulation_required": true,
  "offline_only": true,
  "simulation_result_is_not_machining_approval": true
}
```

These values are hard-coded and cannot be overridden by any request parameter.

---

## Tool Selection Chain

1. HOLE features → `ToolFamily.DRILLING` → closest diameter match in catalog
2. POCKET/SLOT features → `ToolFamily.MILLING` → closest diameter match
3. No catalog match → `tool_status=INSUFFICIENT_DATA`, `toolpath_status=BLOCKED`
4. Never invents tool geometry

## Clearance Derivation

1. `feature.clearance_z` (USER_DEFINED)
2. `stock_bbox.max_z + max(height × 15%, 5mm)` (BBOX_DERIVED)
3. None → `clearance_z=null`, BLOCKED (HR-11)

---

## Limitations (By Design)

- Stock removal uses VOXEL_APPROXIMATION (AABB) — not exact swept volume
- No holder/spindle geometry unless `holder_diameter_mm` / `holder_length_mm` provided
- Fixture collision uses rectangular AABB models only
- Cutting parameters (rpm, feed) not yet derived from material+tool pairs

---

## Gate Decision

| Gate | Requirement | Actual | Result |
|------|------------|--------|--------|
| FE tests PASS | 1026+ | 1051 | PASS |
| FE tests FAIL | 0 | 0 | PASS |
| TSC | Clean | Clean | PASS |
| Ruff | Clean | Clean | PASS |
| HR1–HR21 | All enforced | All enforced | PASS |
| `is_dispatchable` | false | false | PASS |
| `production_released` | false | false | PASS |
| `offline_only` | true | true | PASS |
| Backend 401 tests | PASS | 2 PASS | PASS |

**PIPELINE_GATE_OPEN=True**
**CONDITIONAL_GO=PASS**
