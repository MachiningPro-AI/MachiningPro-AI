# MachiningPro AI — v1.0.0-beta.3 Release Notes (DRAFT)

**Version:** 1.0.0-beta.3  
**Date:** 2026-11-26  
**Status:** RELEASE_CANDIDATE — engineer review required before distribution  
**HEAD:** `f3a1233` (pending release commit)  
**Qualification:** V1_0_0_BETA_3_RELEASE_CANDIDATE_QUALIFICATION_01  

---

## Summary

v1.0.0-beta.3 closes the two Live Acceptance blockers identified in the beta.2 qualification cycle. No new features are added; the release is a targeted hardening of the Auto CAM persistence and machine limit clamping subsystems.

---

## Changes Since v1.0.0-beta.2

### Auto CAM Plan Persistence (Phase A)

**AUTOCAM_PLAN_SURVIVES_BACKEND_RESTART: YES**

The in-memory plan store (Python `dict`) has been replaced with a SQLite-backed
`AutoCamPlanStore` using WAL mode and a threading lock — the same pattern already
used by `WorkflowStore` and `PersistentManufacturingPlanStore`.

- New file: `backend/autocam/plan_store.py`
- DB path: `data/autocam_plans.db`
- All plan fields survive a full process restart, including cost inputs, cost results,
  feature confirmations, and report status.
- Safety invariants (`AUTO_CAM_CAN_DISPATCH_CNC`, `AUTO_CAM_CAN_RELEASE_PRODUCTION`,
  `AUTO_CAM_CAN_AUTO_APPROVE`) are **re-enforced on every deserialization** in
  `_deserialise()`. A tampered DB payload cannot promote the dispatch state.
- `backend/persistence/__init__.py` exposes `get_autocam_plan_store()` singleton
  and closes the store on `reset_stores()`.

**Restart test evidence (MUST A2)**:
```
PLAN_ID=73ac4eb594c74117
COST_INPUTS_SURVIVE_RESTART=YES   (known_total=57.06 EUR)
REPORT_CONTEXT_SURVIVES_RESTART=YES  (report_status=REPORT_AVAILABLE)
STATE_SAFETY_INVARIANTS_MAINTAINED=YES
```

### Machine Limit Clamping — Live Acceptance (Phase B)

**MACHINE_LIMIT_CLAMPING_READY: YES**

The cutting parameter engine already clamped `rpm_raw` to `spindle_max_rpm` in
`cutting_params_engine.py` Phase P. Beta.3 adds the live acceptance test suite
that proves this path with explicit numeric evidence:

```
MACHINE_LIMIT_SOURCE=SYNTHETIC-TEST-MACHINE-LOW-RPM-001 (TEST_ONLY, spindle_max_rpm=1000)
RAW_CALCULATED_RPM=4244.1   (Vc=80 m/min, D=6mm drill, formula: 1000×Vc/(π×D))
MACHINE_MAX_RPM=1000
FINAL_SUGGESTED_RPM=1000.0
STATUS=CLAMPED_TO_MACHINE_LIMIT
FEED=140.0 mm/min  (at clamped RPM=1000, fn=0.14 mm/rev)
FEED_RECOMPUTED_AFTER_CLAMP=YES
USER_CAN_SEE_MACHINE_LIMIT_CLAMP=YES  (via provenance field)
```

The provenance field on `CuttingParamResult` now carries all four required clamp
evidence fields: `RAW_CALCULATED_VALUE`, `MACHINE_LIMIT`, `FINAL_SUGGESTED_VALUE`,
`LIMITING_REASON`.

### Documentation

- `KNOWN_LIMITATIONS.md` updated: KL-12b resolved (plan persistence), KL-19 added
  (other_cost structural NOT_PROVIDED), KL-20 added (DOCX not wired for Auto CAM).
- `report_bridge.py` docstring corrected: DOCX removed from supported-formats list.
- `docs/qualification/BETA3_FINAL_GATE_CLOSURE_01.md` added.

### Bug Fixes

- `backend/domain/base.py`: Resolved Ruff UP038 violations (`isinstance(x, (int, float))`
  → `isinstance(x, int | float)`). No behavior change.
- `backend/autocam/api.py`: `submit_cost_input` now persists the updated plan to the
  SQLite store. Previously cost inputs were silently lost on restart.

---

## Test Suite

| Module | Tests | Result |
|---|---|---|
| `test_autocam_persistence.py` | 12 | PASS |
| `test_autocam_machine_limit.py` | 10 | PASS |
| `test_autocam_params_engine.py` | 14 | PASS |
| `test_autocam_cost.py` | 19 | PASS |
| `test_autocam_orchestrator.py` | 26 | PASS |
| `test_autocam_api.py` | 11 | PASS |
| **Backend autocam total** | **92** | **PASS** |
| Frontend (vitest) | 1072 | PASS |

```
RUFF=CLEAN
TYPESCRIPT=CLEAN
FRONTEND_BUILD=CLEAN (1,656 kB / 427 kB gzip)
NEW_FAILURES_INTRODUCED=0
```

---

## Known Limitations

| ID | Description | Severity |
|---|---|---|
| KL-01 | STEP recognition via surface heuristics, not exact B-Rep | LOW |
| KL-02 | PYTHONOCC_REQUIRED=NO; full B-Rep features need manual classification | LOW |
| KL-05 | Cutting params NOT_AVAILABLE without MACHININGPRO_CUTTING_PARAM_REF_PATH | LOW |
| KL-07 | GOUGE_EXACT=NOT_VERIFIABLE always | BY_DESIGN |
| KL-19 | other_cost always NOT_PROVIDED; max completeness 87.5% | BY_DESIGN |
| KL-20 | DOCX export not wired for Auto CAM reports | LOW |

Full list: `KNOWN_LIMITATIONS.md`

---

## Upgrade Notes

- No schema migration required; `data/autocam_plans.db` is created on first startup.
- The `data/` directory is not committed to source control (`.gitignore`).
- Existing `data/workflows.db` and `data/plans.db` are unaffected.

---

## Safety Invariants (unchanged, always enforced)

```
AUTO_CAM_CAN_DISPATCH_CNC=NO
AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
AUTO_CAM_CAN_AUTO_APPROVE=NO
S19_DISPATCH_SAFETY_GATE=ALWAYS_BLOCKED
REAL_MACHINE_WRITE=DISABLED
COST_ANALYSIS_CAN_APPROVE_PRODUCTION=NO
REPORT_CAN_APPROVE_PRODUCTION=NO
```

---

*DRAFT — Do not distribute. TAG_CREATED=NO. This document will be finalized when the
beta.3 annotated tag and GitHub Release are created.*
