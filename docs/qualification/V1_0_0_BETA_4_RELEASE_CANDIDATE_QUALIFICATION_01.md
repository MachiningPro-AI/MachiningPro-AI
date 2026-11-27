# V1_0_0_BETA_4_RELEASE_CANDIDATE_QUALIFICATION_01

**Product:** MachiningPro AI  
**Version:** 1.0.0-beta.4  
**Qualification Type:** Release Candidate  
**Date:** 2026-11-27  
**Commits:** cac09c9 (feat) + 852ca0a (fix)  
**Qualified By:** RC Qualification Task MACHININGPRO_AI_V1_0_0_BETA_4_RELEASE_CANDIDATE_QUALIFICATION_01

---

## 1. Repository State

| Field | Value |
|---|---|
| HEAD | 852ca0a |
| origin/main | 2f25fa2 (beta.3) |
| HEAD_EQUALS_ORIGIN | NO — 2 commits ahead, push pending |
| WORKTREE_CLEAN | YES (artifacts/ and data/ gitignored) |
| FORCE_PUSH_USED | NO |

---

## 2. Version Consistency

| Source | Version |
|---|---|
| `pyproject.toml` | 1.0.0-beta.4 |
| `frontend/app/package.json` | 1.0.0-beta.4 |
| VERSION_CONSISTENCY | PASS |

---

## 3. Collision Capability Verification

| Check | Ready | Method | Fidelity | Missing Geometry |
|---|---|---|---|---|
| Holder geometry model | YES | HolderGeometryRecord | CATALOG_GEOMETRY/PARAMETRIC/SIMPLIFIED/NOT_AVAILABLE | NOT_PROVIDED |
| HOLDER_PART_COLLISION | YES | BBOX_CYLINDER | SIMPLIFIED_CYLINDER | NOT_PERFORMED |
| HOLDER_STOCK_COLLISION | YES | BBOX_CYLINDER | SIMPLIFIED_CYLINDER | NOT_PERFORMED |
| HOLDER_FIXTURE_COLLISION | YES | BBOX_CYLINDER | SIMPLIFIED_CYLINDER | NOT_PERFORMED |
| Fixture geometry | YES | FixtureGeometrySource enum | STEP/IGES/STL/PROJECT_ARTIFACT/NOT_PROVIDED | NOT_PERFORMED |
| TOOL_FIXTURE_COLLISION | YES | BBOX_SWEEP | SIMPLIFIED | NOT_PERFORMED |
| PART_FIXTURE_INTERFERENCE | YES | BBOX_OVERLAP | — | NOT_PERFORMED; overlap → PARTIAL |

**Fail-closed confirmed:** All checks return NOT_PERFORMED when geometry is absent.
No check promotes to PASS without evidence.

---

## 4. Machine Envelope

| Feature | Status |
|---|---|
| MACHINE_ENVELOPE_READY | YES |
| MACHINE_AXIS_LIMITS_READY | YES |
| WCS_ENVELOPE_READY | YES |
| WCS transform formula | `machine_x = program_x + wcs_offset_x_mm` |
| Z convention | `[-z_travel, 0]` (negative = plunge into part) |
| PASS case | TEST-MACHINE-LARGE-01 (1000×800×500mm) |
| FAIL case | TEST-MACHINE-SMALL-01 (10×10×10mm) |
| Axis violation structure | AXIS/COMMAND_POSITION/LIMIT_MIN/LIMIT_MAX/EXCESS_MM/OPERATION_ID |

---

## 5. Gouge Check Semantics

| Check | Status | Method | Note |
|---|---|---|---|
| GOUGE_EXACT | NOT_VERIFIABLE | — | pythonocc/BRepAlgoAPI not installed; KL-07; fail-closed |
| GOUGE_CONSERVATIVE | PARTIAL/FAIL | BBOX_SWEEP | Never returns PASS; PARTIAL when clear (inconclusive), FAIL when below part floor |

`GOUGE_EXACT_READY=NO`  
`CONSERVATIVE_GOUGE_WARNING_READY=YES`  
Exact and conservative results are separated — different check_types, independent results.

---

## 6. Auto CAM DOCX Report Bridge (KL-20 Closure)

| Format | Status | Size |
|---|---|---|
| PDF | YES | 9312 bytes (live test) |
| DOCX | YES | 3761 bytes (live test) |
| XLSX | YES | 5555 bytes (live test) |
| CSV | YES | 262 bytes (live test) |
| JSON | YES | 8523 bytes (live test) |
| ZIP | YES | 18182 bytes (live test) |

`REPORT_SNAPSHOT_CANONICAL=YES` — single `build_autocam_report_document()` call;
all formats derive from same `ReportDocument` object.

KL-20 is RESOLVED in beta.4.

---

## 7. Verification UI

| Check | Displayed |
|---|---|
| Tool-Part | YES |
| Tool-Stock | YES |
| Tool-Fixture | YES |
| Holder-Part | YES |
| Holder-Stock | YES |
| Holder-Fixture | YES |
| Machine Envelope | YES |
| Axis Limits | YES |
| Tool Reach | YES |
| Gouge (exact) | YES |
| Gouge (conserv.) | YES |
| Stock Removal | YES |

`NOT_VERIFIABLE_DISPLAY_CLEAR=YES` — blue info icon, blue text, never green  
`NOT_PERFORMED_DISPLAY_CLEAR=YES` — gray text, no check icon  
`FAIL_DISPLAY_CLEAR=YES` — red X icon, red text  
`WARNING_DISPLAY_CLEAR=YES` — amber text for dispatch lock banner

---

## 8. Blocker Navigation

`VERIFICATION_BLOCKER_NAVIGATION_READY=PARTIAL`

Stage code and message are displayed in the global blockers panel and inline
in the stage tracker. Click-to-navigate (select operation, highlight toolpath
segment, move camera) is not implemented in beta.4. Documented as KL-23.

---

## 9. Persistence

`VERIFICATION_STATE_SURVIVES_RESTART=YES`

Confirmed via round-trip test (`AutoCamPlanStore.save` → restart → `.get`):
- gouge_exact, holder_part_collision, machine_id, wcs_ref all round-trip correctly
- Safety invariants (verification_can_dispatch_cnc=False) survive restart
- Beta.3 plans load correctly; new fields default to NOT_PERFORMED

---

## 10. Known Limitations Summary

| ID | Limitation | Blocker? | Type |
|---|---|---|---|
| KL-07 | GOUGE_EXACT=NOT_VERIFIABLE | PRODUCTION_BLOCKER | Low (fail-closed) |
| KL-21 | SIMPLIFIED_CYLINDER fidelity for holder collision | PRODUCTION_BLOCKER | Low |
| KL-22 | 3D fixture geometry import deferred | PRODUCTION_BLOCKER | Medium |
| KL-23 | Blocker navigation PARTIAL | NOT A BLOCKER | Low |
| KL-24 | Machine envelope uses catalog travel | KNOWN | Low |
| KL-25 | PART_FIXTURE_INTERFERENCE=PARTIAL not FAIL | BY_DESIGN | — |

---

## 11. Safety Invariants

```
VERIFICATION_CAN_AUTO_APPROVE=NO     (hardcoded False in VerificationSummaryResult)
VERIFICATION_CAN_RELEASE_PRODUCTION=NO   (hardcoded False)
VERIFICATION_CAN_DISPATCH_CNC=NO    (hardcoded False)
AUTO_CAM_CAN_DISPATCH_CNC=NO        (S19 ALWAYS_BLOCKED)
REAL_MACHINE_WRITE_FOUND=NO         (backend/dispatch/simulated.py: is_real_machine_write=False)
GCODE_DISPATCH_FOUND=NO             (backend/nc: NO_GCODE_DISPATCH=YES in all modules)
```

---

## 12. Test Results

| Suite | Tests | Result |
|---|---|---|
| Verification (holder/fixture/envelope/gouge/semantics) | 65 | PASS |
| — Holder collision (Phase G+W+X) | 23 | PASS |
| — Fixture collision (Phase I) | 9 | PASS |
| — Machine envelope (Phase J/K/L/Z) | 10 | PASS |
| — Gouge semantics (Phase Y) | 14 | PASS |
| — Verification semantics (Phase O) | 9 | PASS |
| Auto CAM orchestrator + cost | 45 | PASS |
| Reporting | 370 | PASS |
| Persistence | 175 | PASS |
| Backend API (level11–13) | 319 | PASS |
| Frontend (node:test) | 1072 | PASS |
| **Ruff** | — | **CLEAN** |
| **TypeScript** | — | **CLEAN (exit 0)** |
| **Frontend build** | — | **CLEAN (1.16s)** |

`NEW_FAILURES_INTRODUCED=0`

Pre-existing failures (confirmed at beta.3 baseline 2f25fa2):
- `test_no_hard_coded_cycle_times` (KL-18, temp path dependency)
- `test_p5a_*/test_p7d_*/test_p8b_*` (catalog count tests)
- DXF pipeline tests (server not running in test mode)

---

## 13. Blocker Classification

```
CRITICAL_BLOCKERS=0
HIGH_BLOCKERS=0
MEDIUM_BLOCKERS=0
LOW_BLOCKERS=1
  └── KL-07: GOUGE_EXACT=NOT_VERIFIABLE (not a public-beta blocker; fail-closed)
```

**PUBLIC_BETA_BLOCKER count=0** — KL-07 is a production limitation only.
Fail-closed semantics (never PASS) mean public beta users receive accurate,
honest results.

---

## 14. Readiness Classification

```
PUBLIC_DEMO_READY=YES
CLOSED_BETA_READY=YES
PUBLIC_BETA_READY=YES
PRODUCTION_READY=NO
```

Production readiness requires:
1. KL-07 resolved: exact gouge (pythonocc/BRepAlgoAPI installed and integrated)
2. KL-22 resolved: 3D fixture geometry upload and import
3. KL-21 mitigated: full holder profile collision (not just simplified cylinder)
4. All safety gates remain hardcoded (not configurable per deployment)

---

## 15. Release Gate

```
TAG_CREATED=NO
RELEASE_CREATED=NO
FORCE_PUSH_USED=NO
LEVEL21_STARTED=NO

RELEASE_CANDIDATE_READY=YES
FINAL_RESULT=PASS_V1_0_0_BETA_4_RELEASE_CANDIDATE_READY
```
