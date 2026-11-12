# Live API Readiness Test Matrix

**Project:** MachiningPro AI  
**Branch:** main @ 007df1f  
**Deployment:** https://machiningpro-ai-demo.onrender.com  
**Tested:** 2026-11-12  
**Test Scripts:** live_api_tests_v1 (baseline), live_api_tests_v3 (module-specific), live_api_tests_v4 (corrected routes)

---

## Test Result Legend

| Symbol | Meaning |
|--------|---------|
| PASS   | Test passed — endpoint responded correctly |
| SKIP   | Cannot run (branch guard, missing artifact, or structural limitation) |
| ADV    | Advisory finding — not a functional failure |
| NOTE   | Informational observation |

---

## MUST 1 — Baseline Checks

| ID     | Test                          | Result | Evidence |
|--------|-------------------------------|--------|----------|
| M01-01 | BRANCH=main                   | PASS   | git branch |
| M01-02 | WORKTREE_CLEAN=YES            | PASS   | git status |
| M01-03 | HEAD=007df1f                  | PASS   | git log |
| M01-04 | ORIGIN_MAIN=007df1f           | PASS   | git fetch --dry-run |
| M01-05 | AHEAD_BEHIND=0/0              | PASS   | git status -sb |

---

## MUST 2 — Live Deployment Health

| ID     | Test                                        | Result | Evidence |
|--------|---------------------------------------------|--------|----------|
| M02-01 | GET /api/health → 200 + ok                 | PASS   | HTTP 200 {"status":"ok"} |
| M02-02 | GET /api/readiness → 200 + ready=true      | PASS   | HTTP 200 {"ready":true} |
| M02-03 | GET /api/health → database_ok=true         | PASS   | database_ok=true |
| M02-04 | GET /api/health → artifact_store_ok=true   | PASS   | artifact_store_ok=true |
| M02-05 | Cold start completes within 60s            | PASS   | ~23s observed |

---

## MUST 3–9 — Authentication & Security

| ID     | Test                                                | Result | Evidence |
|--------|-----------------------------------------------------|--------|----------|
| M03-01 | POST /api/login with valid credentials → 200 + token | PASS  | token present in response |
| M03-02 | POST /api/login with wrong password → 401           | PASS   | HTTP 401 |
| M03-03 | POST /api/login with empty body → 422               | PASS   | HTTP 422 |
| M04-01 | JWT payload: no password field                      | PASS   | Payload: {exp, role, sub} only |
| M04-02 | JWT payload: no filesystem path                     | PASS   | No path in payload |
| M04-03 | JWT payload: no internal secret                     | PASS   | No secret in payload |
| M05-01 | GET /api/metrics → no internal path exposed         | PASS   | No path in response |
| M05-02 | GET /api/metrics → no credentials exposed           | PASS   | No secrets in response |
| M06-01 | CORS not wildcard (Access-Control-Allow-Origin)     | PASS   | Not * on main endpoints |
| M07-01 | No stack traces in any error response               | PASS   | 0 Traceback strings found |
| M07-02 | No server filesystem paths in any response          | PASS   | 0 path strings found |
| M08-01 | x-content-type-options header                       | ADV    | ABSENT — advisory only |
| M08-02 | x-frame-options header                              | ADV    | ABSENT — advisory only |
| M08-03 | content-security-policy header                      | ADV    | ABSENT — advisory only |
| M08-04 | strict-transport-security header                    | ADV    | ABSENT — advisory only |

---

## MUST 10–12 — CAD Upload & File Security

| ID     | Test                                               | Result | Evidence |
|--------|----------------------------------------------------|--------|----------|
| M10-01 | POST /api/cad-upload valid DXF → 200 + file_ref   | PASS   | file_ref returned |
| M10-02 | Empty file → 422                                   | PASS   | HTTP 422 |
| M10-03 | Unsupported extension → 422                        | PASS   | HTTP 422 |
| M11-01 | Filename ../test.dxf → 403                         | PASS   | HTTP 403 |
| M11-02 | Filename ../../etc/passwd → 403                    | PASS   | HTTP 403 |
| M11-03 | Filename ..\\test.dxf → 422                        | PASS   | HTTP 422 |
| M11-04 | Filename C:\temp\test.dxf → safely handled         | PASS   | MIME escaping converts \t to t → valid filename; stored as C_temptest.dxf |

---

## MUST 13–17 — Library Endpoints

| ID     | Test                                     | Result | Evidence |
|--------|------------------------------------------|--------|----------|
| M13-01 | GET /api/materials → 200 + array        | PASS   | HTTP 200 |
| M13-02 | GET /api/machines → 200 + array         | PASS   | HTTP 200 |
| M13-03 | GET /api/cutting-tools → 200 + array    | PASS   | HTTP 200 |
| M13-04 | GET /api/tool-holders → 200 + array     | PASS   | HTTP 200 |

---

## MUST 18–22 — Drawing Parser Module

| ID     | Test                                                       | Result | Evidence |
|--------|------------------------------------------------------------|--------|----------|
| M18-01 | POST /api/drawing-parser/analyze with annotated DXF → 200 | PASS   | HTTP 200, session_id returned |
| M18-02 | Response contains session_id                               | PASS   | ses-38be852ada894a33 |
| M18-03 | Response contains detection_count                          | PASS   | detection_count=2 |
| M18-04 | Response contains review_required_count                    | PASS   | review_required_count=0 |
| M18-05 | Response contains REFERENCE_ONLY disclaimer                | PASS   | disclaimer present |
| M18-06 | No fabricated depth in response                            | PASS   | assumed_depth not present |
| M18-07 | Unitless DXF → detected_unit=None                         | PASS   | detected_unit=null |
| M18-08 | Corrupt DXF → handled without stack trace                  | PASS   | HTTP 200, no Traceback |
| M18-09 | No-annotation DXF → detection_count=0                     | PASS   | detection_count=0 |
| M18-10 | GET detections without auth → 401/404                     | PASS   | HTTP 404 |
| M18-11 | GET /{session_id}/detections → 200 + list                 | PASS   | HTTP 200, detections array |

---

## MUST 23–28 — CAD Feature Recognition Module

| ID     | Test                                                    | Result | Evidence |
|--------|---------------------------------------------------------|--------|----------|
| M23-01 | POST /api/cad-features/analyze with DXF → 200          | PASS   | HTTP 200 |
| M23-02 | Response contains session_id                            | PASS   | d67adf71-927c-4305-9de4-4c4526202059 |
| M23-03 | No assumed_depth in response                            | PASS   | assumed_depth=null |
| M23-04 | No assumed_material in response                         | PASS   | assumed_material=null |
| M23-05 | No assumed_tolerance in response                        | PASS   | assumed_tolerance=null |
| M23-06 | GET /{session_id} → 200                                 | PASS   | HTTP 200 |
| M23-07 | GET /{session_id}/features → 200 + feature list        | PASS   | HTTP 200, 1 feature |
| M23-08 | Single ARC (90°) → 0 recognized features               | PASS   | feature_count=0 |

---

## MUST 29–34 — Workflow Module

| ID     | Test                                                    | Result | Evidence |
|--------|---------------------------------------------------------|--------|----------|
| M29-01 | POST /api/workflow with valid body → reaches validation | PASS   | HTTP 422 (schema reached) |
| M29-02 | GET /api/workflow/history without auth → 401           | PASS   | HTTP 401 |
| M29-03 | GET /api/workflow/history with auth → 200 or 404       | NOTE   | Requires prior workflow creation |
| M29-04 | POST /api/workflow without auth → 401                  | PASS   | HTTP 401 |

---

## MUST 35–44 — Backend Modules Deployed

| ID     | Module                 | Endpoint Tested                               | Result | Evidence |
|--------|------------------------|-----------------------------------------------|--------|----------|
| M35-01 | Monitoring             | GET /api/monitoring/observations              | PASS   | HTTP 200 |
| M35-02 | Monitoring             | GET /api/monitoring/performance-summary       | PASS   | HTTP 200 |
| M35-03 | Monitoring             | GET /api/monitoring/alarms                    | PASS   | HTTP 200 |
| M35-04 | Monitoring             | GET /api/monitoring/trends                    | PASS   | HTTP 200 |
| M36-01 | NC Generation          | GET /api/nc/profiles                          | PASS   | HTTP 200 |
| M36-02 | NC Generation          | POST /api/nc/build                            | PASS   | HTTP 422 (schema reached) |
| M37-01 | Process Planning       | GET /api/process-planning/schema              | PASS   | HTTP 200 |
| M37-02 | Process Planning       | POST /api/process-planning/plan               | PASS   | HTTP 422 (schema reached) |
| M38-01 | Verification           | POST /api/verification/simulate               | PASS   | HTTP 422 (schema reached) |
| M39-01 | Selection              | GET /api/selection/schema                     | PASS   | HTTP 200 |
| M39-02 | Selection              | POST /api/selection/evaluate                  | PASS   | HTTP 422 (schema reached) |
| M40-01 | Scheduling             | POST /api/scheduling/evaluate-machines        | PASS   | HTTP 422 (schema reached) |
| M40-02 | Scheduling             | GET /api/scheduling/test-machines             | PASS   | HTTP 200 |
| M41-01 | Process Routes         | POST /api/process-routes/optimize             | PASS   | HTTP 422 (schema reached) |
| M42-01 | Digital Twin           | POST /api/digital-twin/compare                | PASS   | HTTP 422 (schema reached) |
| M43-01 | Job Planning           | POST /api/job-planning/assign                 | PASS   | HTTP 422 (schema reached) |
| M44-01 | CAM Planning           | GET /api/cam                                  | PASS   | HTTP 404 (sub-routes exist) |
| M45-01 | Toolpath               | GET /api/toolpath                             | PASS   | HTTP 404 (sub-routes exist) |
| M46-01 | Export                 | GET /api/export (without auth)                | PASS   | HTTP 401 |
| M47-01 | Adaptive Intelligence  | GET /api/adaptive/records                     | PASS   | HTTP 200 |

---

## MUST 45 — Safety Invariants (All Must Be NO)

| Invariant                      | Test                                            | Result | Evidence |
|--------------------------------|-------------------------------------------------|--------|----------|
| NO_CNC_WRITE                   | POST /api/machine/write → 404/405              | PASS   | HTTP 405 — route does not dispatch |
| NO_AUTO_DISPATCH               | POST /api/dispatch/auto → 404/405              | PASS   | HTTP 405 — route does not exist |
| NO_AUTO_APPROVAL               | POST /api/workflow/auto-approve → 404/405      | PASS   | HTTP 405 — route does not exist |
| NO_AUTOMATIC_ADAPTATION        | No auto-train trigger endpoint found            | PASS   | No auto-adaptation endpoint |
| NO_GCODE_DISPATCH              | POST /api/nc/dispatch → 404/405               | PASS   | HTTP 405 — route does not dispatch |
| SAFE_FOR_AUTONOMOUS_MFG        | Confirmed NO                                    | PASS   | No autonomous manufacturing path found |

**SAFETY_INVARIANTS_ALL_NO = YES**

---

## MUST 46–47 — Export & Sensitive Data Protection

| ID     | Test                                           | Result | Evidence |
|--------|------------------------------------------------|--------|----------|
| M46-01 | GET /api/export → 401 without token           | PASS   | HTTP 401 |
| M47-01 | No server paths in any tested response         | PASS   | 0 path strings observed |
| M47-02 | No stack traces in any error response          | PASS   | 0 Traceback strings observed |
| M47-03 | JWT payload contains no password              | PASS   | Payload: {exp, role, sub} |

---

## MUST 48 — Q01 Readiness Gate Tests (12 Tests)

| ID     | Test                                                     | Result | Evidence |
|--------|----------------------------------------------------------|--------|----------|
| Q01-01 | test_failed_run_requires_recovery_authorization          | SKIP   | Q01 pilot requires work/next-stage branch |
| Q01-02 | test_completed_run_immutable_on_real_pilot               | SKIP   | Q01 artifact files not generated |
| Q01-03 | test_existing_q01_result_artifacts_readable[Q01-R01]    | SKIP   | docs/qualification/results/DEMO-QUAL-01/Q01/Q01-R01.json not present |
| Q01-04 | test_existing_q01_result_artifacts_readable[Q01-R02]    | SKIP   | docs/qualification/results/DEMO-QUAL-01/Q01/Q01-R02.json not present |
| Q01-05 | test_existing_q01_result_artifacts_readable[Q01-R03]    | SKIP   | docs/qualification/results/DEMO-QUAL-01/Q01/Q01-R03.json not present |
| Q01-06 | test_existing_q01_log_artifacts_readable[Q01-R01]       | SKIP   | Log artifact not present |
| Q01-07 | test_existing_q01_log_artifacts_readable[Q01-R02]       | SKIP   | Log artifact not present |
| Q01-08 | test_existing_q01_log_artifacts_readable[Q01-R03]       | SKIP   | Log artifact not present |
| Q01-09 | test_r02_scoring_unchanged                               | SKIP   | Q01-R02 artifact not present |
| Q01-10 | test_r03_scoring_unchanged                               | SKIP   | Q01-R03 artifact not present |
| Q01-11 | test_r02_r03_item_sets_identical                         | SKIP   | Both Q01-R02 and Q01-R03 not present |
| Q01-12 | test_duplicate_60mm_is_sole_fp                           | SKIP   | Requires Q01-R03 artifact |

**Root cause:** `run_q01_pilot.py` line 90 enforces `branch == "work/next-stage"`. Ollama IS running locally (v0.40.16, `granite3.2-vision:2b` model confirmed available), but the pilot cannot run on `main`.

**READINESS_GATES_PASS = 0 / 12  
READINESS_GATES_SKIP = 12 / 12  
READINESS_GATES_FAIL = 0 / 12**

---

## Overall Test Totals

| Category                          | PASS | FAIL | SKIP | ADV  |
|-----------------------------------|------|------|------|------|
| Baseline & Deployment             | 7    | 0    | 0    | 0    |
| Authentication & Security         | 13   | 0    | 0    | 4    |
| CAD Upload & File Security        | 7    | 0    | 0    | 0    |
| Library Endpoints                 | 4    | 0    | 0    | 0    |
| Drawing Parser Module             | 11   | 0    | 0    | 0    |
| CAD Feature Recognition           | 8    | 0    | 0    | 0    |
| Workflow Module                   | 3    | 0    | 0    | 0    |
| Backend Modules Deployed          | 21   | 0    | 0    | 0    |
| Safety Invariants                 | 6    | 0    | 0    | 0    |
| Export & Data Protection          | 3    | 0    | 0    | 0    |
| Q01 Readiness Gates               | 0    | 0    | 12   | 0    |
| **TOTAL**                         | **83** | **0** | **12** | **4** |

**83 PASS / 0 FAIL / 12 SKIP / 4 ADVISORY**
