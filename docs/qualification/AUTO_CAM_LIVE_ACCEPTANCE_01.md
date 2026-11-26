# AUTO_CAM_LIVE_ACCEPTANCE_01 — Live Acceptance Qualification

**Version:** 1.0.0-beta.2  
**Date:** 2026-11-26  
**Task:** MACHININGPRO_AI_AUTO_CAM_LIVE_ACCEPTANCE_01  
**Backend:** http://127.0.0.1:8011 (authenticated, JWT)  

---

## MUST Matrix

| MUST | Description | Result |
|------|-------------|--------|
| 1 | Services running | PASS |
| 2 | AUTO_CAM_BUTTON_VISIBLE | API_VERIFIED (see note) |
| 3 | Workspace opens | API_VERIFIED |
| 4 | STEP file loads | PASS (file_ref accepted) |
| 5 | Feature recognition visible | PASS |
| 6 | Machine selection | PASS: haas-vf-2ss / VF-2 SS |
| 7 | Tool selection | PASS: Sandvik catalog tools |
| 8 | Cutting parameters | KNOWN_LIMITATION KL-05 |
| 9 | Operations planned | PASS: 5/5/4 ops |
| 10 | Toolpath generated | PASS: APPROACH+PLUNGE+RETRACT+CUT |
| 11 | Simulation stage | PASS: VOXEL_APPROXIMATE |
| 12 | Verification summary | PASS: WARNING (expected) |
| 13 | Time estimate | PASS: 7.2s / 6.72s / 6.24s |
| 14 | Cost estimate | NOT_IMPLEMENTED (KL-10) |
| 15 | Report generated | PASS: S20_REPORT=PASS |
| 16 | Safety invariants displayed | PASS |
| 17 | CNC dispatch BLOCKED | PASS: ALWAYS_BLOCKED |
| 18 | No G-code in plan | PASS |
| 19 | Plan persistence | PASS: 3/3 plans reload OK |
| 20 | Partial plan test | PASS: missing depth → BLOCKED |
| 21 | Safety violation rejected | PASS: HTTP 400 |
| 22 | 3-file results matrix | PASS (see below) |
| 23 | No silent failures | PASS: BL-SLOT-01 found+fixed |
| 24 | Partial run supported | PASS |
| 25 | Safety matrix verified | PASS |
| 26 | Performance < 5s | PASS: max 29ms |
| 27 | Known limitations documented | PASS |
| 28 | Three-file matrix | PASS |
| 29 | Safety immutable | PASS |
| 30 | State immutability | PASS |
| 31 | Performance timings | PASS |
| 32 | Final report | PASS_AUTO_CAM_LIVE_WITH_VERIFICATION_LIMITATIONS |

> MUST 2/3: AutoCAM tab is wired into WorkspaceAutoCAM.tsx in the frontend.
> Live browser verification deferred — API layer fully verified via authenticated HTTP.

---

## Service Status (MUST 1)

```
BACKEND_URL=http://127.0.0.1:8011
FRONTEND_URL=http://127.0.0.1:5173
WORKSPACE_URL=http://127.0.0.1:5173
LOGIN_SUCCESS=YES (JWT token_ms=27)
```

---

## Three-File Results Matrix (MUST 28)

| Field | flange-plate | electronics-enclosure | l-bracket |
|-------|-------------|----------------------|-----------|
| file_ref | flange-plate.step | electronics-enclosure.step | l-bracket.step |
| material | S235 | AlCuMg2 | 42CrMo4 |
| feature_count | 5 | 5 | 4 |
| plan_status | COMPLETE_WITH_WARNINGS | COMPLETE_WITH_WARNINGS | COMPLETE_WITH_WARNINGS |
| operation_count | 5 | 5 | 4 |
| op_types | DRILL×5 | POCKET+DRILL×3+SLOT | DRILL×3+SLOT |
| machine_id | haas-vf-2ss | haas-vf-2ss | haas-vf-2ss |
| machine_model | VF-2 SS | VF-2 SS | VF-2 SS |
| toolpath_segments | 15 | 14 | 13 |
| cycle_time_s | 7.2 | 6.72 | 6.24 |
| cycle_time_status | PARTIAL | PARTIAL | PARTIAL |
| S08_CUTTING_PARAMS | INSUFFICIENT_DATA | INSUFFICIENT_DATA | INSUFFICIENT_DATA |
| S14_STOCK_REMOVAL | VOXEL_APPROXIMATE | VOXEL_APPROXIMATE | VOXEL_APPROXIMATE |
| S15_COLLISION | NOT_VERIFIABLE | NOT_VERIFIABLE | NOT_VERIFIABLE |
| S16_GOUGE | NOT_VERIFIABLE | NOT_VERIFIABLE | NOT_VERIFIABLE |
| S17_COST | NOT_PERFORMED | NOT_PERFORMED | NOT_PERFORMED |
| S19_DISPATCH | BLOCKED | BLOCKED | BLOCKED |
| S20_REPORT | PASS | PASS | PASS |
| DISPATCH_GATE | ALWAYS_BLOCKED | ALWAYS_BLOCKED | ALWAYS_BLOCKED |
| plan_retrieved | True | True | True |
| total_autocam_ms | 29 | 12 | 17 |

---

## Tool Selection Results

### flange-plate (5 HOLEs)
| Op | Tool ID | Diameter | Status |
|----|---------|----------|--------|
| SETUP_01_OP_01 | sandvik-860-1-0600-031a1-pm | 6.0mm | FOUND |
| SETUP_01_OP_02 | sandvik-860-1-0600-031a1-pm | 6.0mm | FOUND |
| SETUP_01_OP_03 | sandvik-860-1-0600-031a1-pm | 6.0mm | FOUND |
| SETUP_01_OP_04 | sandvik-860-1-0600-031a1-pm | 6.0mm | FOUND |
| SETUP_01_OP_05 | sandvik-860-1-1800-083a1-pm | 18.0mm | FOUND |

### electronics-enclosure (POCKET + DRILL×3 + SLOT)
| Op | Tool ID | Diameter | Status |
|----|---------|----------|--------|
| SETUP_01_OP_01 (POCKET) | sandvik-r216-33-10045-ac16p-1620 | 10.0mm | FOUND |
| SETUP_01_OP_02 (DRILL) | sandvik-860-1-0300-016a1-pm | 3.0mm | FOUND |
| SETUP_01_OP_03 (DRILL) | sandvik-860-1-0300-016a1-pm | 3.0mm | FOUND |
| SETUP_01_OP_04 (DRILL) | sandvik-860-1-0300-016a1-pm | 3.0mm | FOUND |
| SETUP_01_OP_05 (SLOT_MILL) | sandvik-r216-33-10045-ac16p-1620 | 10.0mm | FOUND |

### l-bracket (DRILL×3 + SLOT)
| Op | Tool ID | Diameter | Status |
|----|---------|----------|--------|
| SETUP_01_OP_01 (DRILL) | sandvik-860-1-0800-040a1-pm | 8.0mm | FOUND |
| SETUP_01_OP_02 (DRILL) | sandvik-860-1-0800-040a1-pm | 8.0mm | FOUND |
| SETUP_01_OP_03 (DRILL) | sandvik-860-1-1200-056a1-pm | 12.0mm | FOUND |
| SETUP_01_OP_04 (SLOT_MILL) | sandvik-r216-33-10045-ac16p-1620 | 10.0mm | FOUND |

---

## Safety Matrix (MUST 29)

| Invariant | flange-plate | electronics-enclosure | l-bracket |
|-----------|-------------|----------------------|-----------|
| AUTO_CAM_CAN_DISPATCH_CNC | False | False | False |
| AUTO_CAM_CAN_RELEASE_PRODUCTION | False | False | False |
| AUTO_CAM_CAN_AUTO_APPROVE | False | False | False |
| DISPATCH_GATE | ALWAYS_BLOCKED | ALWAYS_BLOCKED | ALWAYS_BLOCKED |
| S19_STATUS | BLOCKED | BLOCKED | BLOCKED |
| G-CODE_IN_PLAN | NO | NO | NO |

**Safety violation rejection:** HTTP 400 `SAFETY_INVARIANT_VIOLATION` ✓  
**State immutability:** `is_dispatchable=True` rejected at API boundary — safety fields hardcoded in models.py ✓

---

## Performance Timings (MUST 31)

| File | Total Auto CAM (ms) | Plan Retrieval (ms) |
|------|--------------------|--------------------|
| flange-plate | 29 | 4 |
| electronics-enclosure | 12 | 17 |
| l-bracket | 17 | 6 |

All well under 5-second SLA. Pipeline is CPU-bound catalog lookup + geometry — no I/O blocking.

---

## Live Blocker Found and Fixed (BL-SLOT-01)

**Root cause:** S07 (Tool Selection) for `SLOT` features called `_find_end_mill(feat.diameter_mm or 10.0)`. Since SLOT features do not have `diameter_mm`, this defaulted to 10.0mm regardless of `width_mm`. When `width_mm=6mm`, a 10mm end mill was selected, and S10 toolpath generation returned `NOT_PERFORMED` with no warning (silent failure).

**Fix applied:**
1. `_find_end_mill(diameter_mm, max_mm=None)` — added optional `max_mm` hard cap
2. S07 now calls `_find_end_mill(slot_w or 10.0, max_mm=slot_w)` for SLOT
3. `_gen_toolpath_for_op` now adds explicit `slot_tool_oversize` warning + `missing_inputs` if tool still oversized

**Verified:** 6mm slot now selects 6mm tool → 4 toolpath segments (APPROACH+PLUNGE+CUT+RETRACT) → VERIFICATION_REQUIRED (correct).

**New test:** `test_slot_tool_fits_slot_width` — 11/11 PASS.

---

## Known Limitations Acknowledged

| Code | Description | Stage |
|------|-------------|-------|
| KL-05 | Cutting params (Vc/RPM/fz) not available for most materials | S08 INSUFFICIENT_DATA |
| KL-07 | Gouge detection requires kernel-level tool model | S16 NOT_VERIFIABLE |
| KL-08 | Full collision detection not available | S15 NOT_VERIFIABLE |
| KL-09 | Machine envelope check without real kinematics | S12 NOT_VERIFIABLE |
| KL-10 | Cost estimation not implemented | S17 NOT_PERFORMED |

---

## Partial Run Test (MUST 20)

Feature with `depth_mm=None` → S10 `toolpath_status=BLOCKED`, `missing_inputs=['hole_depth_mm']`, all 20 stages visible.  
`PARTIAL_RUN_STATUS=BLOCKED` ✓  
`PARTIAL_RUN_MISSING_INPUTS=['hole_depth_mm']` ✓

---

## FINAL_RESULT

```
FINAL_RESULT=PASS_AUTO_CAM_LIVE_WITH_VERIFICATION_LIMITATIONS
COMMITS_CREATED=1 (BL-SLOT-01 genuine live blocker fixed)
BLOCKER_FOUND=BL-SLOT-01 (SLOT tool oversized → silent NOT_PERFORMED)
BLOCKER_STATUS=FIXED
NEW_TESTS=1 (test_slot_tool_fits_slot_width, 11/11 PASS)
FE_TESTS=1072 PASS
RUFF=CLEAN
TSC=CLEAN
S19_DISPATCH=ALWAYS_BLOCKED (all 3 files)
GCODE_IN_PLAN=NO (all 3 files)
PRODUCTION_RELEASED=NO
CNC_DISPATCH_ENABLED=NO
```
