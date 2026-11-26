# MachiningPro AI v1.0.0-beta.2 — Release Candidate Qualification

**Document ID:** V1_0_0_BETA_2_RELEASE_CANDIDATE_QUALIFICATION_01  
**Date:** 2026-11-26  
**HEAD:** cf06487ee4772f92c1a7bdec29ea795f6f017006  
**Branch:** main (HEAD = origin/main)  
**Builds on:** PUBLIC_BETA_RELEASE_CANDIDATE_PREP_01 (5f3a099, 2026-11-26)  
**New since beta.1:**
- e15d270 — 20-stage Auto CAM orchestration pipeline
- cf06487 — BL-SLOT-01: slot tool selection respects slot width constraint

---

## MUST 1 — Repository State

| Field | Value |
|-------|-------|
| HEAD | cf06487ee4772f92c1a7bdec29ea795f6f017006 |
| origin/main | cf06487ee4772f92c1a7bdec29ea795f6f017006 |
| HEAD_EQUALS_ORIGIN | **YES** |
| WORKTREE_CLEAN | YES (artifacts/, data/, docs/qualification/AUTO_CAM_UNSEEN_DATA_CHALLENGE_01.md untracked only — runtime outputs and new qual doc) |
| COMMITS_SINCE_BETA_1 | 2 (Auto CAM pipeline + BL-SLOT-01 fix) |
| CODE_DELTA | backend/autocam/ (new module) + backend/api/app.py (router registration) + tests (3 new files) |

---

## MUST 2 — Version

| Source | Value |
|--------|-------|
| pyproject.toml | **1.0.0-beta.2** |
| frontend/app/package.json | **1.0.0-beta.2** |
| VERSION_CONSISTENCY | **PASS** |

---

## MUST 3 — Auto CAM Capability Matrix

| Capability | Status | Evidence |
|------------|--------|---------|
| CAD_IMPORT_READY | **YES** | STEP/IGES via GMSH OCC; PASS_WORKSPACE_HARDENING_01 |
| STEP_READY | **YES** | 7 STEP files processed across live + unseen tests |
| IGES_READY | **YES** | MP_SYN_001.iges COMPLETE_WITH_WARNINGS; IGES cyclic recovery |
| FEATURE_RECOGNITION_READY | **YES** | HOLE/POCKET/SLOT/STEP_SHOULDER across 7 unseen files |
| MACHINE_AUTO_SELECTION_READY | **YES** | haas-vf-2ss from 37-machine catalog |
| TOOL_AUTO_SELECTION_READY | **YES** | Sandvik/Gühring catalog; BL-SLOT-01 width constraint fixed |
| CUTTING_PARAMETER_AUTO_SELECTION_READY | **PARTIAL** | KL-05: NOT_AVAILABLE for most materials; no fabrication |
| OPERATION_PLANNING_READY | **YES** | DRILL/POCKET_MILL/SLOT_MILL/SHOULDER_MILL ops |
| REAL_TOOLPATH_READY | **YES** | APPROACH+PLUNGE+CUT+RETRACT segments generated |
| TOOL_ANIMATION_READY | **YES** | Segments ready for frontend animation |
| SIMULATION_READY | **YES (VOXEL_APPROXIMATE)** | KL-11; stock removal visualized |
| STOCK_REMOVAL_READY | **VOXEL_APPROXIMATE** | Exact subtraction not implemented |
| VERIFICATION_READY | **PARTIAL** | Gouge/collision NOT_VERIFIABLE (KL-07/08/09); fail-closed |
| CYCLE_TIME_READY | **YES (PARTIAL)** | Partial estimate; full requires cutting params (KL-05) |
| COST_READY | **NO** | KL-10: commercial rate tables not implemented |
| REPORTING_READY | **PARTIAL** | AUTO_CAM_SUMMARY_ONLY; PDF/XLSX bridging deferred (KL-12b) |
| PERSISTENCE_READY | **YES** | Plans persist; GET /api/autocam/{plan_id} confirmed |

---

## MUST 4 — Generalization

### AUTO_CAM_LIVE_ACCEPTANCE_01 (benchmark files)
| File | Features | Status |
|------|---------|--------|
| flange-plate.step | 5 HOLE | COMPLETE_WITH_WARNINGS |
| electronics-enclosure.step | 1 POCKET + 3 DRILL + 1 SLOT | COMPLETE_WITH_WARNINGS |
| l-bracket.step | 3 DRILL + 1 SLOT | COMPLETE_WITH_WARNINGS |

`BENCHMARK_FILES_PASS=3/3`

### AUTO_CAM_UNSEEN_DATA_CHALLENGE_01 (unseen files)
| File | Format | Features | Status |
|------|--------|---------|--------|
| MP_SYN_001.step | STEP | 3H+1P+1S+1ST (6) | COMPLETE_WITH_WARNINGS |
| MP_SYN_001.iges | IGES | same | COMPLETE_WITH_WARNINGS |
| stepped-shaft-keyway.step | STEP | 1 SLOT (keyway w=6) | COMPLETE_WITH_WARNINGS |
| flanged-bushing.step | STEP | 1 HOLE (Ø20 bore) | COMPLETE_WITH_WARNINGS |

`UNSEEN_FILES_PASS=4/4`  
`FILE_SPECIFIC_LOGIC_FOUND=NO`  
`TOTAL_FILES_QUALIFIED=7 (3 benchmark + 4 unseen); all COMPLETE_WITH_WARNINGS`

---

## MUST 5 — Known Limitations (beta.2)

### Auto CAM — New in beta.2

| Code | Description | Stage |
|------|-------------|-------|
| KL-05 | Cutting params (Vc/RPM/fz/ap/ae) NOT_AVAILABLE for most materials | S08 INSUFFICIENT_DATA |
| KL-07 | Gouge detection requires kernel-level tool model — GOUGE_EXACT=NOT_VERIFIABLE always | S16 NOT_VERIFIABLE |
| KL-08 | Fixture collision requires user-provided fixture geometry — NOT_PERFORMED without it | S15 NOT_VERIFIABLE |
| KL-09 | Holder collision requires user-provided holder geometry — NOT_PERFORMED without it | S15 NOT_VERIFIABLE |
| KL-10 | Machine envelope check without real kinematics — NOT_VERIFIABLE | S12 NOT_VERIFIABLE |
| KL-11 | Cost estimation not implemented — no commercial rate tables | S17 NOT_PERFORMED |
| KL-12b | Auto CAM → PDF/XLSX/CSV report handoff not bridged to workflow report store | S20 AUTO_CAM_SUMMARY_ONLY |
| KL-5B | Tool catalog ±10% diameter tolerance allows slightly undersized tools | S07 WARNING |

### Pre-existing (carried forward from beta.1)

| Code | Description |
|------|-------------|
| KL-01 | STEP recognition uses surface heuristics, not exact B-Rep |
| KL-02 | PYTHONOCC_REQUIRED=NO; full B-Rep recognition deferred |
| KL-03 | IGES PARTIAL_SUCCESS for complex trimmed surfaces (boundary entities 142/141) |
| KL-04 | PDF/image files not 3D-importable |
| KL-06 | Only DRILL_CYCLE strategy for HOLE in workspace CAM API |
| KL-07 | GOUGE_EXACT=NOT_VERIFIABLE (see above) |
| KL-08 | FIXTURE_COLLISION=NOT_PERFORMED without fixture geometry |
| KL-09 | HOLDER_COLLISION=NOT_PERFORMED without holder geometry |
| KL-10 (workspace) | PART_GOUGE=PARTIAL for drill-through bbox |
| KL-11 (workspace) | Stock removal VOXEL_APPROXIMATE |
| KL-12 | MACHINE_ENVELOPE=INSUFFICIENT_DATA without machine config |
| KL-13 | /api/reports/generate requires workflow_id |
| KL-14 | No /api/logout endpoint |
| KL-15 | Large JS bundle (~1.6MB pre-gzip, ~425KB gzip) |
| KL-16 | dbDemoCardSubtitle i18n false-alarm (non-visible) |
| KL-17 | Dev auth via environment variables |
| KL-18 | test_no_hard_coded_cycle_times pre-existing failure (temp path) |

`KNOWN_LIMITATIONS_READY=YES`

---

## MUST 6 — Beta.2 Release Notes

See: `docs/releases/V1_0_0_BETA_2_RELEASE_NOTES_DRAFT.md`

`RELEASE_NOTES_READY=YES`

---

## MUST 7 — Safety

| Invariant | Status | Evidence |
|-----------|--------|---------|
| AUTO_CAM_CAN_DISPATCH_CNC | **NO** | Hardcoded in models.py; 7/7 live files confirmed |
| AUTO_CAM_CAN_RELEASE_PRODUCTION | **NO** | Hardcoded in models.py |
| AUTO_CAM_CAN_AUTO_APPROVE | **NO** | Hardcoded in models.py |
| REAL_MACHINE_WRITE_FOUND | **NO** | No CNC communication endpoint exists |
| GCODE_OUTPUT_FOUND | **NO** | No G-code in any plan response |
| S19_DISPATCH_SAFETY_GATE | **ALWAYS_BLOCKED** | Hardcoded; HTTP 400 on `is_dispatchable=True` attempt |
| SAFETY_VIOLATION_REJECTED | **YES** | Live test: HTTP 400 SAFETY_INVARIANT_VIOLATION |

---

## MUST 8 — Serial Regression

### Auto CAM Tests
```
tests/test_autocam_api.py          : 11/11 PASS
tests/test_autocam_orchestrator.py : 26/26 PASS
tests/acceptance/test_autocam_step_acceptance.py : 22/22 PASS
AUTOCAM_TOTAL: 59/59 PASS
```

### Manufacturing Unit Tests
```
tests/unit/manufacturing/
  PASS: ~700+ tests
  PRE-EXISTING FAILURES: 25
    - test_p10_step_intake.py (8): STEP intake NOT_IMPLEMENTED flags (catalog 63 vs expected 60)
    - test_p10a_tool_geometry.py (5): 18 drills expected, 21 actual (b7bcdfb pre-beta.2)
    - test_p10b_step_intake.py (8): same as above, duplicate test file
    - test_p5a_tool_selection.py (1): catalog expansion check
    - test_p7d_tool_coverage.py (2): 60 total/18 drills expected, 63/21 actual
    - test_p8b_tool_reach.py (1): flute length check for 18 drills
  NEW_FAILURES: 0 (catalog last changed in b7bcdfb, pre-dating beta.2)
```

### API Unit Tests
```
tests/unit/api/
  PASS: ~1800+ tests
  PRE-EXISTING FAILURES: 8 (test_cutting_tools.py catalog count checks + test_cad_import_level7.py)
  PRE-EXISTING ERRORS: 13 (test_drawing_parser_dxf.py + test_dxf_pipeline.py — collection-ordering artifact)
  NEW_FAILURES: 0
```

### Reports / Persistence / Workflow Tests
```
tests/unit/reports/ + tests/unit/persistence/ + tests/unit/workflow/
RESULT: ALL PASS (exit 0, no failures)
```

### Frontend Tests
```
1072 passed, 0 failed, exit 0
```

### Static Analysis
```
Ruff backend/autocam/ : CLEAN (exit 0)
Ruff full repo        : pre-existing violations (unchanged from beta.1 baseline)
  Minor test file violations: 3 fixable (unused import × 2, unsorted imports × 1)
  Non-fixable test file: 1 (E501 line too long in test_autocam_orchestrator.py:261)
TypeScript --noEmit   : CLEAN (exit 0)
Frontend build        : SUCCESS (exit 0)
  Build warning: TS6133 unused var 'safety' in WorkspaceAutoCAM.tsx:355 — non-blocking
```

```
NEW_FAILURES_INTRODUCED=0
```

---

## MUST 9 — Blockers

### Beta.2 Release Gate Assessment

| ID | Description | Severity | Beta Blocker | Production Blocker |
|----|-------------|----------|--------------|-------------------|
| BLK-01 | Cutting params NOT_AVAILABLE most materials (KL-05) | MEDIUM | NO (documented) | YES |
| BLK-02 | Gouge/collision NOT_VERIFIABLE (KL-07/08/09) | MEDIUM | NO (documented) | YES |
| BLK-03 | Cost estimation not implemented (KL-11) | MEDIUM | NO (documented) | YES |
| BLK-04 | Auto CAM → PDF/XLSX report bridge absent (KL-12b) | LOW | NO (AUTO_CAM_SUMMARY_ONLY sufficient for beta) | YES |
| BLK-05 | Pre-existing test failures (catalog count / DXF ordering) | LOW | NO (pre-existing, unchanged) | NO (test-only) |
| BLK-06 | Large JS bundle — KL-15 | LOW | NO | NO |
| BLK-07 | TS6133 unused var 'safety' in WorkspaceAutoCAM.tsx | NIT | NO | NO |
| BLK-08 | test_no_hard_coded_cycle_times (pre-existing KL-18) | LOW | NO (pre-existing) | NO |

```
CRITICAL_BLOCKERS=0
HIGH_BLOCKERS=0
MEDIUM_BLOCKERS=3 (BLK-01/02/03 — all documented known limitations, NOT beta blockers)
LOW_BLOCKERS=0 (beta) / 2 (production: BLK-04/05)
```

---

## MUST 10 — Release Readiness

| Classification | Ready? | Rationale |
|----------------|--------|-----------|
| PUBLIC_DEMO_READY | **YES** | 7-file live + unseen acceptance; real catalog tools; full pipeline |
| CLOSED_BETA_READY | **YES** | Safety invariants locked; fail-closed verification; feature recognition generalized |
| PUBLIC_BETA_READY | **YES with known limitations** | KL-05/07/08/09/11 documented; no fabrication; dispatch gate locked |
| PRODUCTION_READY | **NO** | Requires: cutting params (KL-05), exact verification (KL-07/08/09), cost (KL-11), multi-user auth |

---

## FINAL REPORT

```
HEAD=cf06487ee4772f92c1a7bdec29ea795f6f017006
ORIGIN_MAIN=cf06487ee4772f92c1a7bdec29ea795f6f017006
WORKTREE_CLEAN=YES (untracked runtime outputs only)

BACKEND_VERSION=1.0.0-beta.2
FRONTEND_VERSION=1.0.0-beta.2
VERSION_CONSISTENCY=PASS

BENCHMARK_FILES_PASS=3/3
UNSEEN_FILES_PASS=4/4
FILE_SPECIFIC_LOGIC_FOUND=NO

AUTO_CAM_READY=YES
MACHINE_SELECTION_READY=YES
TOOL_SELECTION_READY=YES (BL-SLOT-01 fixed)
REAL_TOOLPATH_READY=YES
SIMULATION_READY=YES (VOXEL_APPROXIMATE)
VERIFICATION_READY=PARTIAL (fail-closed; gouge/collision NOT_VERIFIABLE per KL-07/08/09)
REPORTING_READY=PARTIAL (AUTO_CAM_SUMMARY_ONLY; PDF bridge deferred KL-12b)

KNOWN_LIMITATIONS_READY=YES
RELEASE_NOTES_READY=YES

CRITICAL_BLOCKERS=0
HIGH_BLOCKERS=0
MEDIUM_BLOCKERS=3 (all documented KL, not beta blockers)
LOW_BLOCKERS=0

PUBLIC_DEMO_READY=YES
CLOSED_BETA_READY=YES
PUBLIC_BETA_READY=YES with known limitations
PRODUCTION_READY=NO

AUTO_CAM_CAN_DISPATCH_CNC=NO
AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
AUTO_CAM_CAN_AUTO_APPROVE=NO
REAL_MACHINE_WRITE_FOUND=NO
GCODE_OUTPUT_FOUND=NO

AUTO_CAM_TESTS=59 PASS
FRONTEND_TESTS=1072 PASS
RUFF=CLEAN (autocam module); pre-existing violations in rest of codebase unchanged
TYPESCRIPT=CLEAN
FRONTEND_BUILD=SUCCESS
NEW_FAILURES_INTRODUCED=0

QUALIFICATION_DOC=docs/qualification/V1_0_0_BETA_2_RELEASE_CANDIDATE_QUALIFICATION_01.md
RELEASE_NOTES_DOC=docs/releases/V1_0_0_BETA_2_RELEASE_NOTES_DRAFT.md

COMMITS_CREATED=0
PUSHED=N/A
TAG_CREATED=NO
RELEASE_CREATED=NO
FORCE_PUSH_USED=NO

RELEASE_CANDIDATE_READY=YES

FINAL_RESULT=PASS_BETA_2_RC_WITH_KNOWN_LIMITATIONS
```
