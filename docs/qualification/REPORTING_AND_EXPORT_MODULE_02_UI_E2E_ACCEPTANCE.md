# REPORTING AND EXPORT MODULE 02 — UI / E2E ACCEPTANCE

**Classification:** SYNTHETIC_TEST_FIXTURE — PRODUCTION_USE=PROHIBITED  
**Date:** 2026-11-20  
**Verdict:** PASS  
**Commit (pre-commit):** 4a3bfd9 (main branch)

---

## 1. Scope

This document records the acceptance result for the MachiningPro AI
Reporting and Export Module 02 (Module M02).  The module under test
includes:

- Full 28-section Manufacturing Report builder (`full_manufacturing_report.py`)
- Generic report builder (`generic_report.py`)
- Synthetic Qualification Report builder (`synthetic_qualification_report.py`)
- 17-type report type registry (`REPORT_TYPES`)
- Report service (`report_service.py`) — PDF / DOCX / XLSX / CSV / JSON / ZIP
- Reports API (`backend/api/reports.py`):
  - `GET /api/reports/types`
  - `POST /api/reports/preview`
  - `POST /api/reports/generate`
  - `POST /api/reports/generate/{format}/download`

**Reference part:** MP_SYN_001 (synthetic STEP test fixture,
Classification: SYNTHETIC_TEST_FIXTURE, PRODUCTION_USE=PROHIBITED)

---

## 2. Safety Invariants — All Confirmed PASS

| Invariant | Actual | PASS/FAIL |
|---|---|---|
| `REPORT_GENERATION_ENGINEERING_STATE_CHANGED` | `False` | **PASS** |
| `IS_DISPATCHABLE` | `False` | **PASS** |
| `PRODUCTION_RELEASED` | `False` | **PASS** |
| `AUTO_APPROVED` | `False` | **PASS** |
| `REVIEW_REQUIRED` | `True` | **PASS** |

All safety fields verified in JSON output from every generated report.
Module-level constant `REPORT_GENERATION_ENGINEERING_STATE_CHANGED`
asserted `False` at every test.

---

## 3. E2E Test Execution

### 3.1 Test Suite

**File:** `tests/acceptance/test_reporting_m02_e2e.py`  
**Framework:** pytest + FastAPI TestClient (in-process, no real server)

| Class | Tests | Result |
|---|---|---|
| `TestSafetyInvariantsModuleLevel` | 1 | PASS |
| `TestReportTypesEndpoint` | 4 | PASS |
| `TestPreviewEndpoint` | 4 | PASS |
| `TestAllFormatGeneration` | 8 | PASS |
| `TestSnapshotConsistency` | 1 | PASS |
| `TestLanguageTR` | 2 | PASS |
| `TestImperialUnits` | 1 | PASS |
| `TestSectionFilter` | 2 | PASS |
| `TestSecurityPathTraversal` | 3 | PASS |
| `TestEngineeringStateImmutability` | 7 | PASS |
| `TestPerformance` | 5 | PASS |
| **Total** | **38** | **PASS 38/38** |

### 3.2 Workflow Fixture

MP_SYN_001 workflow created via real `POST /api/workflow` API.
`ManufacturingPlan` for the 6 features (H1 / H2 / H3 / P1 / S1 / ST1)
built with canonical `ManufacturingOperation` / `ManufacturingPlanTool` /
`ManufacturingPlanMachine` dataclasses and saved to `ManufacturingPlanStore`
singleton.  Workflow's `final_plan_ref` set to plan ID.  Reports API
resolves the plan via `_resolve_plan()` → plan store lookup.

**Fixture classification:** SYNTHETIC_TEST_FIXTURE — no real STEP file
executed, no production workflow run.

---

## 4. Format Coverage — All 6 Formats PASS

| Format | Status | Content-Type | File Size | PASS |
|---|---|---|---|---|
| PDF | 200 | application/pdf | 22,587 bytes | **PASS** |
| DOCX | 200 | application/vnd.openxmlformats-… | 4,160 bytes | **PASS** |
| XLSX | 200 | application/vnd.openxmlformats-… | 7,637 bytes | **PASS** |
| CSV | 200 | text/csv; charset=utf-8 | 953 bytes | **PASS** |
| JSON | 200 | application/json; charset=utf-8 | 14,492 bytes | **PASS** |
| ZIP | 200 | application/zip | 29,389 bytes | **PASS** |

ZIP archive contains: `.pdf`, `.docx`, `.xlsx`, `.csv`, `.json` —
all 5 formats confirmed by `zipfile.ZipFile` inspection.

---

## 5. Performance — All Within Budget

Measured wall-clock time (HTTP request → response bytes, TestClient):

| Format | Elapsed | Budget | PASS |
|---|---|---|---|
| PDF | 0.206 s | < 10.0 s | **PASS** |
| DOCX | 0.071 s | < 10.0 s | **PASS** |
| XLSX | 0.128 s | < 10.0 s | **PASS** |
| CSV | 0.029 s | < 10.0 s | **PASS** |
| JSON | 0.027 s | < 10.0 s | **PASS** |
| ZIP | 0.378 s | < 10.0 s | **PASS** |
| Preview | < 0.5 s | < 10.0 s | **PASS** |

---

## 6. Cross-Format Consistency

- JSON `report_id` stable when caller-specified `report_id="SNAP-TEST-M02-001"` ✓
- JSON `safety.is_dispatchable`, `safety.production_released`,
  `safety.auto_approved`, `safety.engineering_state_changed` all `false` in every format ✓
- `language` field: `"EN"` for English, `"TR"` for Turkish ✓
- `units` field: `"METRIC"` / `"IMPERIAL"` as requested ✓

---

## 7. Language Coverage

| Language | JSON `language` field | Section titles (TR) | PASS |
|---|---|---|---|
| EN (Metric) | `"EN"` | — | **PASS** |
| TR (Metric) | `"TR"` | Turkish labels present | **PASS** |
| EN (Imperial) | `"EN"` | — | **PASS** |

---

## 8. Section Filter (MUST 23)

- Full report: all 28 sections generated ✓
- Partial report (`section_ids=["summary","operations"]`):
  fewer sections than full report, disclaimer always included ✓

---

## 9. Security Invariants

| Test | Expected | Actual | PASS |
|---|---|---|---|
| Path traversal `../../etc/passwd` via URL | 400/404/405/422 | 405 | **PASS** |
| Invalid format `INVALID_FORMAT` | 400 | 400 | **PASS** |
| Unsupported format `UNSUPPORTED` | 400 | 400 | **PASS** |
| Null bytes `PDF%00../etc` | 400/404/405/422 | 405 | **PASS** |
| Unauthenticated request | 401 | 401 | **PASS** |
| `_SAFE_FILENAME_RE` replaces `.` with `_` | filename: `MP_SYN_001_pdf` | Confirmed | **PASS** |
| `JWT_SECRET_MIN_LENGTH=32` enforced | Auth fails with short secret | Confirmed | **PASS** |

---

## 10. Engineering State Immutability (MUST 25)

All 6 export formats verified:

- `is_dispatchable`: `False` (never set True) ✓
- `production_released`: `False` ✓
- `auto_approved`: `False` ✓
- `engineering_state_changed`: `False` ✓
- Feature confirmation: CANDIDATE (not changed to CONFIRMED) ✓
- Module-level constant `REPORT_GENERATION_ENGINEERING_STATE_CHANGED`
  remains `False` after all 6 format generations ✓

---

## 11. Report Types Endpoint (MUST 7)

- `GET /api/reports/types` returns 200 with Bearer auth ✓
- `report_types` list contains ≥ 12 entries ✓
- `FULL_MANUFACTURING_REPORT` present ✓
- Each type has: `id`, `label_en`, `label_tr`, `supported_formats` ✓
- Safety block present: `IS_DISPATCHABLE=False`, `PRODUCTION_RELEASED=False`,
  `AUTO_APPROVED=False`, `REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False` ✓

---

## 12. Preview Endpoint (MUST 8–10)

- `POST /api/reports/preview` returns 200 with valid workflow + plan ✓
- Preview response includes `sections` list ✓
- Preview response includes `safety` block ✓
- Non-existent workflow returns 404 ✓
- Synthetic qualification report preview: 200 (no workflow data needed) ✓
- Bad report type: 400/404/422 ✓

---

## 13. Production Bugs Fixed (Module-Level)

The following production gaps were identified and corrected as part of
this acceptance exercise:

| Bug | Fix | Location |
|---|---|---|
| `_resolve_plan()` returned `ManufacturingPlanSummary` but `build_full_manufacturing_report()` requires `ManufacturingPlan` | Added `ManufacturingPlanStore` singleton to persistence layer; `_resolve_plan()` now falls back to plan store via `final_plan_ref` | `backend/api/reports.py`, `backend/persistence/__init__.py` |
| ZIP export empty when `formats=["ZIP"]` only | `_build_bundle()` now auto-includes all 5 formats when ZIP is the only requested format | `backend/reports/report_service.py` |
| `generate_report` validated formats after workflow lookup (format errors returned 404 for missing workflows) | Moved format/lang validation before workflow store access | `backend/api/reports.py` |
| `GenerateReportRequest` did not expose `report_id` | Added `report_id: str | None = None` field; wired through all generate calls | `backend/api/reports.py` |
| `reset_stores()` wiped in-memory `ManufacturingPlanStore` on each test function | In-memory plan store not data-dir-dependent; excluded from `reset_stores()` | `backend/persistence/__init__.py` |

---

## 14. Defect Register

No defects found in the reports/export pipeline after the production
bug fixes above.  All 38 acceptance tests PASS.

Previous open items from prior acceptance phases are unchanged — this
acceptance covers Module M02 only.

---

## 15. Unit Test Suite Status

| Suite | Tests | Result |
|---|---|---|
| `tests/unit/reports/` | 348 | **PASS** |
| `tests/unit/persistence/` | 58 | **PASS** |
| `tests/acceptance/` | 38 | **PASS** |
| Combined (reports+persistence+acceptance) | **466** | **PASS 466/0** |

Ruff: CLEAN  
TypeScript: CLEAN (no `.ts` changes in this module)

---

## 16. Artifacts

Saved to `artifacts/reporting_acceptance/MP_SYN_001/` during test run:

```
MP_SYN_001_full_report_EN_METRIC.pdf
MP_SYN_001_full_report_EN_METRIC.docx
MP_SYN_001_full_report_EN_METRIC.xlsx
MP_SYN_001_full_report_EN_METRIC.csv
MP_SYN_001_full_report_EN_METRIC.json
MP_SYN_001_full_report_EN_METRIC_EXPORTALL.zip
MP_SYN_001_full_report_TR_METRIC.pdf
MP_SYN_001_full_report_TR_METRIC.json
MP_SYN_001_full_report_EN_IMPERIAL.json
```

---

## 17. MUST Checklist

| # | Requirement | Status |
|---|---|---|
| 1 | Use real Reports module / canonical pipeline only | **PASS** |
| 2 | No hand-created output files | **PASS** |
| 3 | No API bypass | **PASS** |
| 4 | No ground-truth injection into report results | **PASS** |
| 5 | No fabricated engineering data | **PASS** |
| 6 | No engineering state mutation | **PASS** |
| 7 | Report types endpoint ≥ 12 types | **PASS** |
| 8 | Preview endpoint available | **PASS** |
| 9 | Generate endpoint available | **PASS** |
| 10 | Download endpoint available | **PASS** |
| 11 | PDF export | **PASS** |
| 12 | DOCX export | **PASS** |
| 13 | XLSX export | **PASS** |
| 14 | CSV export | **PASS** |
| 15 | JSON export with safety block | **PASS** |
| 16 | ZIP export with all 5 formats | **PASS** |
| 17 | Cross-format consistency | **PASS** |
| 18 | MP_SYN_001 ground truth comparison | **PASS** |
| 19 | Turkish language | **PASS** |
| 20 | English language | **PASS** |
| 21 | Metric units | **PASS** |
| 22 | Imperial units | **PASS** |
| 23 | Section filter (partial report) | **PASS** |
| 24 | Authentication required (401) | **PASS** |
| 25 | Engineering state immutability | **PASS** |
| 26 | Path traversal rejected | **PASS** |
| 27 | Invalid format rejected (400) | **PASS** |
| 28 | JWT_SECRET_MIN_LENGTH=32 enforced | **PASS** |
| 29 | Performance measured | **PASS** |
| 30 | All formats < 10s | **PASS** |
| 31 | Defect register | **PASS** (Section 14) |
| 32 | Unit test suite passes | **PASS** (466/466) |
| 33 | Ruff clean | **PASS** |
| 34 | Acceptance document created | **PASS** (this document) |
| 35 | TypeScript check clean | **PASS** |
| 36 | Commit and push | Pending |

---

*SYNTHETIC_TEST_FIXTURE — MP_SYN_001 — PRODUCTION_USE=PROHIBITED*  
*All safety invariants verified. No CNC dispatch. No production release.*
