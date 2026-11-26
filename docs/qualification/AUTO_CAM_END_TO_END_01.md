# AUTO_CAM_END_TO_END_01 — Qualification Document

**Date:** 2026-11-26  
**Task ID:** MACHININGPRO_AI_AUTO_CAM_END_TO_END_01  
**Version:** 1.0.0-beta.2  
**Author:** MachiningPro AI Engineering

---

## 1. Scope

This document qualifies the 20-stage Auto CAM orchestration pipeline introduced in `backend/autocam/`. The pipeline accepts CAD feature inputs and runs them through a fully orchestrated sequence of existing backend engines to produce a candidate manufacturing plan.

**Out of scope:**
- Real CNC dispatch (hardcoded BLOCKED at S19)
- Production release (hardcoded False)
- Auto-approve (hardcoded False)

---

## 2. Safety Invariants

The following safety invariants are **hardcoded** in `backend/autocam/models.py` and cannot be overridden by any API input:

| Invariant | Value | Note |
|---|---|---|
| `AUTO_CAM_CAN_DISPATCH_CNC` | `False` | Locked |
| `AUTO_CAM_CAN_RELEASE_PRODUCTION` | `False` | Locked |
| `AUTO_CAM_CAN_AUTO_APPROVE` | `False` | Locked |
| `REAL_MACHINE_WRITE_FOUND` | `False` | Locked |
| `DISPATCH_GATE` | `"ALWAYS_BLOCKED"` | S19 always BLOCKED |
| `SIMULATION_REQUIRED` | `True` | Always required |
| `CANDIDATE_ONLY` | `True` | Candidate plan only |
| `ENGINEER_REVIEW_REQUIRED` | `True` | Always required |

---

## 3. Pipeline Stages

| Stage | ID | Function | Failure Mode |
|---|---|---|---|
| S01 | Input Validation | Checks file_ref + features present | BLOCKED if no features |
| S02 | Stock Gate | Validates stock_bbox | BLOCKED (WARNING) if missing |
| S03 | Feature Classification | Maps features to operation types | BLOCKED if no supported features |
| S04 | Machine Selection | Selects machine from catalog | WARNING if no match |
| S05 | Feasibility | Checks feature/machine compatibility | WARNING |
| S06 | Tool Selection | Selects tools from ToolLibrary | WARNING if no match |
| S07 | Operation Planning | Plans operations per feature | BLOCKED if unsupported |
| S08 | Cutting Parameters | Looks up feed/speed | INSUFFICIENT_DATA (KL-05) |
| S09 | Toolpath Generation | Generates drill/pocket/slot paths | Per-operation BLOCKED |
| S10 | Toolpath Validation | Validates generated paths | WARNING |
| S11 | Stock Removal Sim | Voxel simulation via existing engine | PARTIAL |
| S12 | Gouge Check | Checks for gouging | NOT_VERIFIABLE (KL-07) |
| S13 | Collision Check | Checks for collisions | NOT_VERIFIABLE (KL-08/09) |
| S14 | Cycle Time | Estimates cycle time | PARTIAL |
| S15 | Tool Reach | Checks tool reach | NOT_VERIFIABLE (KL-07) |
| S16 | Machine Envelope | Checks machine travel limits | NOT_VERIFIABLE |
| S17 | Cost Estimation | Estimates cost | NOT_PERFORMED (not implemented) |
| S18 | Report Generation | Generates summary | PASS |
| **S19** | **Dispatch Safety Gate** | **ALWAYS_BLOCKED** | **Never PASS** |
| S20 | Final Report | Saves plan | PASS |

---

## 4. Known Limitations (KL)

| ID | Description | Status |
|---|---|---|
| KL-05 | Cutting parameters unavailable for most material grades | Advisory |
| KL-07 | Gouge / tool reach: requires holder geometry not in input | NOT_VERIFIABLE |
| KL-08 | Collision check: requires fixture geometry | NOT_VERIFIABLE |
| KL-09 | Collision check: requires holder assembly | NOT_VERIFIABLE |
| KL-10 | Cost estimation: engine not implemented | NOT_PERFORMED |

---

## 5. Test Results

### 5.1 Backend Unit Tests (`tests/test_autocam_orchestrator.py`)

**26 tests, 26 PASS**

| Group | Tests | Result |
|---|---|---|
| Safety Invariants | 10 | PASS |
| Pipeline Correctness | 8 | PASS |
| Fail-Closed | 8 | PASS |

### 5.2 Backend API Tests (`tests/test_autocam_api.py`)

**10 tests, 10 PASS**

| Test | Result |
|---|---|
| `test_run_requires_auth` | PASS |
| `test_run_returns_plan` | PASS |
| `test_run_safety_invariants` | PASS |
| `test_run_20_stages` | PASS |
| `test_get_plan` | PASS |
| `test_get_plan_not_found` | PASS |
| `test_run_blocked_no_features` | PASS |
| `test_run_safety_violation_rejected` | PASS |
| `test_run_multiple_features` | PASS |
| `test_s19_always_blocked_in_api` | PASS |

### 5.3 Real STEP Acceptance Tests (`tests/acceptance/test_autocam_step_acceptance.py`)

**22 tests, 22 PASS**

| Part | Features | Operations | S19 | Safety |
|---|---|---|---|---|
| flange-plate.step | 5 × HOLE | 5 × DRILL | BLOCKED | PASS |
| electronics-enclosure.step | 1 × POCKET + 3 × HOLE | 1 × POCKET_MILL + 3 × DRILL | BLOCKED | PASS |
| l-bracket.step | 2 × HOLE + 1 × SLOT | 2 × DRILL + 1 × SLOT_MILL | BLOCKED | PASS |

### 5.4 Frontend Tests (`frontend/app/tests/autocam.test.ts`)

**Tests in suite: ≥10 (embedded in full 1072-test run), all PASS**

| Group | Coverage |
|---|---|
| AutoCamFeatureInput shape | Type contract |
| AutoCamStockBbox shape | Type contract |
| WorkspaceAutoCAMProps | canRun logic |
| Safety invariants | is_dispatchable=false |
| AutoCamPlan shape | No G-code, dispatch gate |
| Stage definitions | 20 unique stages, S19 position |

---

## 6. Code Quality

| Check | Result |
|---|---|
| `python -m ruff check backend/autocam/` | CLEAN |
| `npx tsc --noEmit` | CLEAN |
| Backend total test count | 36 (autocam) |

---

## 7. Files Created / Modified

### New files

| File | Purpose |
|---|---|
| `backend/autocam/__init__.py` | Package init |
| `backend/autocam/enums.py` | StageStatus, AutoCamStage, AutoCamPlanStatus, BlockerCode |
| `backend/autocam/models.py` | AutoCamRequest, AutoCamPlan, all result models |
| `backend/autocam/orchestrator.py` | 20-stage pipeline + get_plan() |
| `backend/autocam/api.py` | POST /api/autocam/run, GET /api/autocam/{plan_id} |
| `frontend/app/src/components/workspace/WorkspaceAutoCAM.tsx` | Frontend panel |
| `tests/test_autocam_orchestrator.py` | 26 BE tests |
| `tests/test_autocam_api.py` | 10 API tests |
| `tests/acceptance/test_autocam_step_acceptance.py` | 22 real-geometry tests |
| `frontend/app/tests/autocam.test.ts` | FE tests |

### Modified files

| File | Change |
|---|---|
| `backend/api/app.py` | Registered autocam_router |
| `frontend/app/src/i18n/types.ts` | Added 52 autocam_* keys |
| `frontend/app/src/i18n/en.ts` | Added 52 English values |
| `frontend/app/src/i18n/tr.ts` | Added 52 Turkish values |

---

## 8. API Endpoints

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/autocam/run` | POST | Bearer JWT | Run 20-stage pipeline |
| `/api/autocam/{plan_id}` | GET | Bearer JWT | Retrieve plan by ID |

**Safety enforcement at API layer:**  
- `is_dispatchable=True` → HTTP 400 `SAFETY_INVARIANT_VIOLATION`
- `production_released=True` → HTTP 400 `SAFETY_INVARIANT_VIOLATION`
- Unauthenticated → HTTP 401

---

## 9. Qualification Verdict

```
PASS_AUTO_CAM_END_TO_END_01
```

| Gate | Status |
|---|---|
| Safety invariants immutable | PASS |
| 20 stages complete | PASS |
| Fail-closed on empty features | PASS |
| Fail-closed on unsupported types | PASS |
| S19 always BLOCKED | PASS |
| No G-code in output | PASS |
| Ruff clean | PASS |
| TSC clean | PASS |
| Backend tests ≥15 | PASS (36) |
| Frontend tests ≥10 | PASS |
| Real STEP acceptance | PASS (22) |
| `AUTO_CAM_CAN_DISPATCH_CNC=NO` | PASS |
| `AUTO_CAM_CAN_RELEASE_PRODUCTION=NO` | PASS |
| `AUTO_CAM_CAN_AUTO_APPROVE=NO` | PASS |
| `REAL_MACHINE_WRITE_FOUND=NO` | PASS |
| `DUPLICATE_ENGINE_CREATED=NO` | PASS |
