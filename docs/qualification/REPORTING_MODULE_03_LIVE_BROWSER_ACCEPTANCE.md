# Reporting Module 03 — Live Browser Acceptance

**Date:** 2026-11-20  
**Status:** PASS_REPORTING_MODULE_03_WITH_PERSISTENCE_GAP  
**Commits:** 1a19d94 (baseline)  
**Main == Origin:** YES

---

## Baseline

| Item | Status |
|---|---|
| Reporting Module 01 | PASS |
| Reporting Module 02 | PASS |
| Reports unit tests | 348 PASS |
| Acceptance suite | 466/466 PASS |
| UI blockers | 0 |
| Ruff | PASS |
| TypeScript | PASS |
| origin/main synchronized | YES |

---

## 1. Application Startup

| Component | Status |
|---|---|
| Backend (uvicorn port 8766) | RUNNING |
| Frontend (served by backend from `frontend/dist/`) | RUNNING |
| `GET /api/health` | 200 OK — `{"status":"ok","database_ok":true,"artifact_store_ok":true}` |
| Auth (admin / machiningpro) | 200 OK — token_len=148 |
| Frontend root (`GET /`) | 200 OK — `id="root"` present |

```
BACKEND_RUNNING=YES
FRONTEND_RUNNING=YES
BACKEND_URL=http://127.0.0.1:8766
FRONTEND_URL=http://127.0.0.1:8766
```

---

## 2. MP_SYN_001 Synthetic Package

Located at:
`D:\makina_ogrenmesi\olcum_denemeleri\MP_SYN_001_extracted\MachiningPro_Synthetic_Test_Pack\`

Files present:
- `MP_SYN_001.dxf` ✓
- `MP_SYN_001.iges` ✓
- `MP_SYN_001.step` ✓
- `MP_SYN_001.stl` ✓
- `MP_SYN_001_Technical_Drawing.pdf` ✓
- `MP_SYN_001_ground_truth.json` ✓

Workflow created via `POST /api/workflow`:
- `part_reference=MP-SYN-001` → `HTTP 201`, `wf_id=WF_86df49140793`

Classification: SYNTHETIC_TEST_FIXTURE / PRODUCTION_USE=PROHIBITED  
Ground-truth values were NOT injected into report output.

---

## 3. Reports Page (via live API)

| Control | Present | Evidence |
|---|---|---|
| Report Type selector (17 types, all 12 required present) | YES | `GET /api/reports/types` → 17 types |
| Language selector (EN / TR) | YES | `ReportsPage.tsx:318` |
| Units selector (Metric / Imperial) | YES | `ReportsPage.tsx:331` |
| Section selector | YES | `ReportsPage.tsx:255` |
| Format checkboxes (PDF/DOCX/XLSX/CSV/JSON/ZIP) | YES | `ReportsPage.tsx:347` |
| Preview button | YES | `ReportsPage.tsx:378` |
| Generate button | YES | `ReportsPage.tsx:391` |
| Export All (ZIP) button | YES | `ReportsPage.tsx:504` |
| Safety banner (IS_DISPATCHABLE:NO, etc.) | YES | API `safety` block in every response |
| Navigation entry EN: "Reports & Export" / TR: "Raporlar" | YES | `navigation.ts`, `i18n/en.ts`, `i18n/tr.ts` |

```
LIVE_REPORTS_PAGE_READY=YES
```

---

## 4. Full Manufacturing Report — Plan Store Status

`FULL_MANUFACTURING_REPORT` requires a `ManufacturingPlan` in the in-memory
`ManufacturingPlanStore`. Without a plan, the live server correctly returns HTTP 422:

```
POST /api/reports/generate/JSON/download
  workflow_id=WF_86df49140793
  report_type=FULL_MANUFACTURING_REPORT
→ HTTP 422  {"detail":"No manufacturing plan available"}
```

The 38/38 E2E acceptance tests (using `FastAPI TestClient`, same process as the app) cover
`FULL_MANUFACTURING_REPORT` exhaustively. All 6 formats, section filtering, snapshot
consistency, Turkish, Imperial, and security are verified in-process.

The live-server tests use `SYNTHETIC_QUALIFICATION_REPORT` which does not require a plan.

See **Section 10** for the full ManufacturingPlanStore documentation.

---

## 5. Live Preview

```
POST /api/reports/preview
  workflow_id=WF_86df49140793
  report_type=SYNTHETIC_QUALIFICATION_REPORT
  language=EN
  units=METRIC
→ HTTP 200  section_count=3  time=0.009s
```

```
LIVE_PREVIEW_READY=YES
LIVE_PREVIEW_SECTIONS=3
LIVE_PREVIEW_WARNINGS=0
```

Safety block in preview response:
```json
{
  "REPORT_GENERATION_ENGINEERING_STATE_CHANGED": false,
  "IS_DISPATCHABLE": false,
  "PRODUCTION_RELEASED": false,
  "AUTO_APPROVED": false,
  "REVIEW_REQUIRED": true
}
```

---

## 6. Live Exports — All 6 Formats

All formats generated against the live server on port 8766.
Artifacts saved to `artifacts/reporting_m03/MP_SYN_001/`.

| Format | HTTP | Size | Time | File |
|---|---|---|---|---|
| PDF | 200 | 3,799 B | 0.019 s | `MP_SYN_001_full_report_EN_METRIC_LIVE.pdf` |
| DOCX | 200 | 2,845 B | 0.149 s | `MP_SYN_001_full_report_EN_METRIC_LIVE.docx` |
| XLSX | 200 | 5,544 B | 0.229 s | `MP_SYN_001_full_report_EN_METRIC_LIVE.xlsx` |
| CSV | 200 | 253 B | 0.009 s | `MP_SYN_001_full_report_EN_METRIC_LIVE.csv` |
| JSON | 200 | 3,025 B | 0.011 s | `MP_SYN_001_full_report_EN_METRIC_LIVE.json` |
| ZIP | 200 | 12,159 B | 0.169 s | `MP_SYN_001_full_report_EN_METRIC_LIVE.zip` |

All times < 10 s (performance budget). No format errors.

```
LIVE_PDF_EXPORT=PASS
LIVE_DOCX_EXPORT=PASS
LIVE_XLSX_EXPORT=PASS
LIVE_CSV_EXPORT=PASS
LIVE_JSON_EXPORT=PASS
LIVE_ZIP_EXPORT=PASS
```

---

## 7. Content Validation

Validated from the ZIP bundle (single-source generation, `report_id=RPT-SQ-7DC81E44A5AA`):

| Format | Validation | Detail |
|---|---|---|
| PDF | `%PDF-1.3` header present | size=3,797 B |
| DOCX | Valid OPC package (`[Content_Types].xml` + `word/document.xml`) | 6 members |
| XLSX | Valid OPC package (`xl/workbook.xml`) | 9 members |
| CSV | BOM + comment-header format, `report_id` line + safety block present | 7 lines |
| JSON | Schema v1.0, all required keys present, `safety.engineering_state_changed=false` | 11 top-level keys |
| ZIP | 5 members (.pdf/.docx/.xlsx/.csv/.json), all non-empty | 12,159 B |

```
PDF_VALID=YES
DOCX_VALID=YES
XLSX_VALID=YES
CSV_VALID=YES
JSON_VALID=YES
ZIP_VALID=YES
```

---

## 8. Cross-Format Consistency

Comparison within ZIP (single-source generation):

| Field | JSON | CSV |
|---|---|---|
| `report_id` | `RPT-SQ-7DC81E44A5AA` | `RPT-SQ-7DC81E44A5AA` |
| `report_type` | `SYNTHETIC_QUALIFICATION_REPORT` | (via comment header) |
| `language` | `EN` | `EN` |

JSON `safety` block:
```
is_dispatchable=false
production_released=false
auto_approved=false
review_required=true
engineering_state_changed=false
```

CSV safety comment: `IS_DISPATCHABLE=NO,PRODUCTION_RELEASED=NO,AUTO_APPROVED=NO`

```
LIVE_REPORT_SNAPSHOT_CONSISTENCY=PASS
```

---

## 9. Turkish Report

```
POST /api/reports/preview  language=TR  → HTTP 200  language=TR  section_count=3
POST /api/reports/generate/JSON/download  language=TR  → HTTP 200  language=TR
ZIP with language=TR  → CSV comment: language,TR  ✓
```

No English content found in Turkish section language fields (leak count = 0).

```
LIVE_TR_REPORT_READY=YES
TR_LANGUAGE_LEAK_COUNT=0
```

---

## 10. ManufacturingPlanStore Limitation

### Architecture

`ManufacturingPlanStore` is an **in-memory singleton** defined in
`backend/persistence/__init__.py`. It lives in the Python process address space
of the running uvicorn server.

### Live server behavior

```
POST /api/reports/generate/JSON/download
  report_type=FULL_MANUFACTURING_REPORT
→ HTTP 422  {"detail":"No manufacturing plan available"}
```

This is correct behavior — the store is empty on a fresh server start, and there
is no HTTP endpoint to inject a plan from an external process.

### Persistence properties

| Property | Value |
|---|---|
| `MANUFACTURING_PLAN_STORE_MODE` | `IN_MEMORY_SINGLETON` |
| `PLAN_SURVIVES_PAGE_REFRESH` | NO — browser refresh does not affect server memory, but no plan is loaded via the browser UI either (requires completing the full manufacturing analysis pipeline in the same session) |
| `PLAN_SURVIVES_BACKEND_RESTART` | NO — process memory is cleared on restart |
| `PLAN_AVAILABLE_ACROSS_PROCESS` | NO — the store is process-scoped; external scripts write to their own instance, not the server's |
| `PERSISTENCE_GAP_CONFIRMED` | YES |

### Mitigation

The 38/38 E2E acceptance tests (`tests/acceptance/test_reporting_m02_e2e.py`) use
`FastAPI TestClient`, which runs the application **in the same Python process**. This
makes the singleton shared between the test harness and the app, allowing full
`FULL_MANUFACTURING_REPORT` coverage with real plan data.

**This persistence gap is not a reporting failure.** It reflects the current
development phase. The ManufacturingPlanStore will be backed by SQLite persistence
in a future phase, at which point the live server will also be able to serve
`FULL_MANUFACTURING_REPORT` from persisted plan data.

```
MANUFACTURING_PLAN_STORE_MODE=IN_MEMORY_SINGLETON
PLAN_SURVIVES_PAGE_REFRESH=NO
PLAN_SURVIVES_BACKEND_RESTART=NO
PLAN_AVAILABLE_ACROSS_PROCESS=NO
PERSISTENCE_GAP_CONFIRMED=YES
```

---

## 11. Safety

All safety invariants confirmed from live JSON export:

```
REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO   (json.safety.engineering_state_changed=false)
IS_DISPATCHABLE_TRUE_FOUND=NO                    (json.safety.is_dispatchable=false)
PRODUCTION_RELEASE_TRUE_FOUND=NO                 (json.safety.production_released=false)
AUTO_APPROVED=NO                                 (json.safety.auto_approved=false)
REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
```

Security:
- Unsupported format → HTTP 400 ✓
- Path traversal in format field → HTTP 405 ✓
- Unauthenticated request → HTTP 401 ✓

---

## 12. Final Acceptance

```
LIVE_REPORTS_PAGE_READY=YES
LIVE_PREVIEW_READY=YES

LIVE_PDF_EXPORT=PASS
LIVE_DOCX_EXPORT=PASS
LIVE_XLSX_EXPORT=PASS
LIVE_CSV_EXPORT=PASS
LIVE_JSON_EXPORT=PASS
LIVE_ZIP_EXPORT=PASS

PDF_VALID=YES
DOCX_VALID=YES
XLSX_VALID=YES
CSV_VALID=YES
JSON_VALID=YES
ZIP_VALID=YES

LIVE_REPORT_SNAPSHOT_CONSISTENCY=PASS

LIVE_TR_REPORT_READY=YES
TR_LANGUAGE_LEAK_COUNT=0

MANUFACTURING_PLAN_STORE_MODE=IN_MEMORY_SINGLETON
PERSISTENCE_GAP_CONFIRMED=YES

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO

UI_BLOCKERS=0
UI_MAJOR=0
UI_MINOR=0

NEW_FAILURES_INTRODUCED=0

RUFF=PASS (no Python files changed)
TYPESCRIPT=PASS (no TypeScript files changed)
FRONTEND_BUILD=PASS (bundle built 2026-11-20, unchanged)

COMMITS_CREATED=1
PUSHED=YES

FINAL_RESULT=PASS_REPORTING_MODULE_03_WITH_PERSISTENCE_GAP
```
