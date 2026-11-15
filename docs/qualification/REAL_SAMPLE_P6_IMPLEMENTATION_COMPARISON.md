# P6 Implementation Comparison — Offline Toolpath / NC Candidate

**Status:** PASS_P6_OFFLINE_TOOLPATH_NC_CANDIDATE  
**Date:** 2026-11-15  
**Branch:** main  
**Baseline:** d0e537e (P5 Final Acceptance + P6 Assessment)

---

## Assessment vs Implementation Gate Mapping

| Assessment Condition | Implementation Gate | Result |
|---|---|---|
| P6-A: Clearance policy before toolpath | `backend/manufacturing/clearance_policy.py` | PASS |
| P6-B: Toolpath adapter to NC segments | `backend/manufacturing/nc_bridge.py` | PASS |
| P6-C: Engineer confirmation of cutting params | `backend/manufacturing/parameter_confirmation.py` | PASS |
| P6-D: Offline NC candidate builder | `backend/manufacturing/nc_candidate.py` | PASS |
| MANUFACTURER_STARTING_VALUE → ENGINEER_CONFIRMED before review-ready | `nc_candidate.py:nc_candidate_review_ready` logic | PASS |
| DXF-02 boring strategy DEFERRED | No DXF-02 endpoint or toolpath added | PASS |
| DXF-01 COMPATIBLE match always visible | `build_offline_nc_candidate` TOOL_DIAMETER_MATCH=COMPATIBLE_REVIEW | PASS |
| is_dispatchable=True nowhere in P6 path | Static grep + safety tests | PASS |

---

## P6-A: Clearance Policy (`clearance_policy.py`)

**Addresses:** MUST 44 (clearance gate before toolpath)

**Input:** `clearance_z`, `clearance_source`, `stock_top_z`, `feature_top_z`, `wcs_ref`  
**Output:** `ClearanceEvaluationResult` with `toolpath_ready: bool`

**Blocking conditions (all block toolpath, never fabricate):**
- `wcs_ref=None` → `WCS_UNKNOWN`
- `clearance_z=None` or `source=UNKNOWN` → `CLEARANCE_Z_REQUIRED`
- `clearance_z` not finite (NaN, Inf) → `INVALID_CLEARANCE`
- `clearance_z <= feature_top_z` → `CLEARANCE_BELOW_MACHINING_REGION`
- `clearance_z < stock_top_z` (when known) → `CLEARANCE_BELOW_STOCK`

**Safety notes always present:**  
`FIXTURE_COLLISION_VALIDATED=NO`, `HOLDER_COLLISION_VALIDATED=NO`, `STOCK_REMOVAL_VALIDATED=NO`

**Tests:** `tests/unit/manufacturing/test_p6a_clearance_policy.py` — 12 tests, all pass

---

## P6-B: NC Bridge Adapter (`nc_bridge.py`)

**Addresses:** MUST 47 (toolpath → NC segment translation without fabrication)

**Motion type mapping:**
| Toolpath MotionType | NC motion_type | is_cutting |
|---|---|---|
| APPROACH, RETRACT, RAPID, LINK, DWELL | RAPID_LINEAR | False |
| PLUNGE, CUT, ENTRY, EXIT, RAMP, ARC | FEED_LINEAR | True |
| HELIX | HELIX | True |

**Guarantees:**
- Blocked toolpath → empty list (never fabricates segments)
- Preserves `tool_ref`, `feature_refs[0]`, `operation_ref`, all coordinates
- Does not call `generate_nc()` directly

**Tests:** `tests/unit/manufacturing/test_p6b_nc_bridge.py` — 12 tests, all pass

---

## P6-C: Parameter Confirmation Gate (`parameter_confirmation.py`)

**Addresses:** MUST 1 condition (MANUFACTURER_STARTING_VALUE → ENGINEER_CONFIRMED)

**Validation chain:**
1. Finite positive `vc_mpm`, `fn_mm` → else `INVALID_PARAMETERS`
2. Within manufacturer range (`vc_min…vc_max`, `fn_min…fn_max`) → else `OUT_OF_MANUFACTURER_RANGE`
3. Machine RPM/feed check (warnings + `REVIEW_REQUIRED` if exceeded, params still returned)
4. On pass: `status=USER_CONFIRMED`, `confirmed_at` timestamp, RPM + feed recalculated from Vc/fn

**Key invariant:** `confirmed_params.status == CuttingDataStatus.USER_CONFIRMED` only after explicit call to `confirm_cutting_parameters()`

**Tests:** `tests/unit/manufacturing/test_p6c_parameter_confirmation.py` — 20 tests, all pass

---

## P6-D: Offline NC Candidate (`nc_candidate.py`)

**Addresses:** MUSTs 21–26 (candidate metadata, safety invariants, labels, traceability)

**Safety invariants (hardcoded in `__post_init__`, cannot be overridden):**
- `offline_only=True`
- `is_dispatchable=False`
- `production_released=False`
- `engineer_review_required=True`
- `label_en="OFFLINE ENGINEERING CANDIDATE — NOT FOR DIRECT MACHINE EXECUTION"`
- `label_tr="OFLİN MÜHENDİSLİK ADAYI — DOĞRUDAN MAKİNE ÇALIŞTIRILMASI İÇİN DEĞİL"`

**NC_CANDIDATE_REVIEW_READY=YES requires ALL of:**
1. Clearance gate passes (`clearance_eval.toolpath_ready=True`)
2. WCS reference is defined
3. Toolpath generator produces segments (GENERATED or VERIFICATION_REQUIRED)
4. `confirmed_params.status == CuttingDataStatus.USER_CONFIRMED`

**DXF-01 COMPATIBLE risk (Condition 3):**  
Every candidate with `tool_match_status="COMPATIBLE"` appends both EN and TR warnings.  
`provenance["tool_match_status"]="COMPATIBLE"` persists throughout.

**Tests:** `tests/unit/manufacturing/test_p6d_nc_candidate.py` — 23 tests, all pass

---

## Security Audit: P6_DISPATCHABLE_TRUE_PATH_FOUND=NO

Searched all P6 production files for `is_dispatchable=True` / `is_dispatchable = True`:

| File | Result |
|---|---|
| `backend/manufacturing/clearance_policy.py` | CLEAN |
| `backend/manufacturing/parameter_confirmation.py` | CLEAN |
| `backend/manufacturing/nc_bridge.py` | CLEAN |
| `backend/manufacturing/nc_candidate.py` | CLEAN |
| `backend/api/cad_features.py` (P6 endpoints) | CLEAN |

**Tests:** `tests/unit/manufacturing/test_p6_safety.py` — 9 tests, all pass

---

## E2E Validation: DXF-01

Sample: `109106_01_30.dxf` — first feature (4.891mm hole, x=-225.54, y=-968.55)  
Tool: `sandvik-860-1-0500-026a1-pm` (5.0mm), COMPATIBLE match (+0.109mm delta)

| Step | Gate | Result |
|---|---|---|
| 1 | MANUFACTURER_STARTING_VALUE confirmed by engineer | USER_CONFIRMED |
| 2 | WCS=DXF01_WCS + clearance_z=5.0mm above stock | TOOLPATH_READY |
| 3 | `generate_drill_toolpath()` APPROACH+PLUNGE+RETRACT | VERIFICATION_REQUIRED (3 segs) |
| 4 | `toolpath_to_nc_segments()` → 3 NC dicts | RAPID_LINEAR × 2 + FEED_LINEAR × 1 |
| 5 | `build_offline_nc_candidate()` | nc_candidate_review_ready=True |
| 6 | `evaluate_p6_readiness()` | all 5 levels PASS, is_dispatchable=False |

**Tests:** `tests/unit/manufacturing/test_p6_e2e_dxf.py` — 22 tests, all pass

---

## New Test Files

| File | Test Count |
|---|---|
| `tests/unit/manufacturing/test_p6a_clearance_policy.py` | 12 |
| `tests/unit/manufacturing/test_p6c_parameter_confirmation.py` | 20 |
| `tests/unit/manufacturing/test_p6b_nc_bridge.py` | 12 |
| `tests/unit/manufacturing/test_p6d_nc_candidate.py` | 23 |
| `tests/unit/manufacturing/test_p6_safety.py` | 9 |
| `tests/unit/manufacturing/test_p6_e2e_dxf.py` | 22 |
| **Total P6** | **98** |

---

## Deferred Scope

- **DXF-02** (60mm boring): DEFERRED per P6 Mandatory Condition 2.  
  Waiting for DXF-01 pipeline validated end-to-end by engineering.
- **P6-E** (cam_gate integration with live sessions): Deferred to P6 final sign-off.
- **P6-F** (session-level E2E via API endpoints): Deferred — requires live DXF parse.

---

## Conclusion

P6 offline toolpath/NC candidate implementation satisfies all assessment conditions.  
`P6_DISPATCHABLE_TRUE_PATH_FOUND=NO`. No offline candidate can be dispatched to a machine.  
All 98 new P6 tests pass. Ruff and Pyright clean.
