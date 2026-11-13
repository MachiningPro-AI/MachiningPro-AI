# Real Sample Metadata Resolution Comparison

**Project:** MachiningPro AI  
**Branch:** main  
**Baseline commit:** f723767  
**Analysis date:** 2026-11-13  
**Task:** P0 — Missing Engineering Data Resolution

---

## Purpose

Documents per-sample metadata readiness before and after the P0 missing-data
resolution workflow. Each row shows:

- **Raw Import Status** — what the pipeline returns without user input  
- **Geometry Ready** — whether geometry was extracted  
- **Raw Manufacturing Planning Ready** — whether process planning can begin
  with file data alone  
- **Blocking Fields** — which required fields are UNKNOWN after import  
- **User Resolution Possible** — whether the user can supply the missing values  
- **Post-Confirmation Planning Ready** — whether process planning becomes
  unblocked once a user provides the missing values  

---

## Conventions

| Symbol | Meaning |
|--------|---------|
| YES    | Ready / resolved |
| NO     | Not ready |
| PARTIAL| Some features extracted but not all |
| –      | Not applicable to this format |

**Fabrication policy:** No field is auto-filled, assumed, or defaulted.
UNKNOWN means the information is genuinely absent from the file.
USER_CONFIRMED means the user explicitly supplied the value.
Values reported as USER_CONFIRMED are NEVER reported as file evidence.

---

## DXF Files

### DXF-01 — 109106_01_30.dxf

| Property | Value |
|----------|-------|
| Import Status | DEGRADED |
| Entity refs | 20 |
| Manufacturing features | 9 |
| Geometry Ready | YES |
| Raw Manufacturing Planning Ready | NO |
| Blocking Fields | material, tolerance_general, surface_finish, hole_depth |
| User Resolution Possible | YES |
| Post-Confirmation Planning Ready | YES (after material + unit confirmation) |
| Notes | Unit extracted as Millimeters from DXF header. No material in title block. |

### DXF-02 — 109106_01_38.dxf

| Property | Value |
|----------|-------|
| Import Status | DEGRADED |
| Entity refs | 599 |
| Manufacturing features | 0 |
| Geometry Ready | YES (geometry present, 0 manufacturing features) |
| Raw Manufacturing Planning Ready | NO |
| Blocking Fields | material, tolerance_general, surface_finish |
| User Resolution Possible | YES |
| Post-Confirmation Planning Ready | YES (after material confirmation) |
| Notes | Assembly drawing with no isolated machining features. Unit in file header. |

### DXF-03 — Pense_Sema.dxf

| Property | Value |
|----------|-------|
| Import Status | DEGRADED |
| Entity refs | 20 |
| Manufacturing features | 11 |
| Geometry Ready | YES |
| Raw Manufacturing Planning Ready | NO |
| Blocking Fields | material, tolerance_general, surface_finish, hole_depth |
| User Resolution Possible | YES |
| Post-Confirmation Planning Ready | YES (after material confirmation) |
| Notes | Schema drawing. No material designation found in title block tokens. |

---

## IGES Files

### IGS-01 — agv03773.geo_fin001.006003.igs

| Property | Value |
|----------|-------|
| Import Status | DEGRADED |
| Entity refs | 521 |
| Manufacturing features | 96 |
| Geometry Ready | YES |
| Raw Manufacturing Planning Ready | NO |
| Blocking Fields | material, topology, tolerance_general, surface_finish |
| User Resolution Possible | YES (material) |
| Post-Confirmation Planning Ready | YES for process planning (after material). CAM blocked until topology resolved. |
| Notes | Surfaces-only IGES. No topology present. CANDIDATE_PLAN returned. |

### IGS-02 — fa00aaj27500_004999.igs

| Property | Value |
|----------|-------|
| Import Status | DEGRADED |
| Entity refs | 560 |
| Manufacturing features | 16 |
| Geometry Ready | YES |
| Raw Manufacturing Planning Ready | NO |
| Blocking Fields | material, topology, tolerance_general, surface_finish |
| User Resolution Possible | YES (material) |
| Post-Confirmation Planning Ready | YES for process planning (after material). CAM blocked. |
| Notes | Medium-complexity IGES part. No topology. |

### IGS-03 — fa00aas38521.geo_fin001.004999.igs

| Property | Value |
|----------|-------|
| Import Status | DEGRADED |
| Entity refs | 1931 |
| Manufacturing features | 64 |
| Geometry Ready | YES |
| Raw Manufacturing Planning Ready | NO |
| Blocking Fields | material, topology, tolerance_general, surface_finish |
| User Resolution Possible | YES (material) |
| Post-Confirmation Planning Ready | YES for process planning (after material). CAM blocked. |
| Notes | Large IGES file. No topology. 64 CANDIDATE manufacturing features. |

---

## PDF Files (UNSUPPORTED — planned P1)

### PDF-01 — DWG-00206402-001.pdf
### PDF-02 — DWG-00139945-001_UPPER COVER MU METAL SHIELD.pdf
### PDF-03 — DWG-00139946-001_LOWER COVER MU METAL SHIELD.pdf

| Property | Value |
|----------|-------|
| Import Status | UNSUPPORTED (graceful) |
| Geometry Ready | NO |
| Raw Manufacturing Planning Ready | NO |
| User Resolution Possible | NO — geometry not extracted |
| Post-Confirmation Planning Ready | NO — format not supported in P0 |
| Notes | All 3 PDFs are hybrid: native title-block text + rasterized drawing area. OCR path required (pdfplumber + pytesseract). Deferred to P1. |

---

## DWG Files (UNSUPPORTED — planned P2)

### DWG-01..DWG-03 (3 files)

| Property | Value |
|----------|-------|
| Import Status | UNSUPPORTED (graceful) |
| Geometry Ready | NO |
| User Resolution Possible | NO |
| Notes | AC1018 (R2004) binary format. ezdxf cannot read DWG directly. LibreDWG is GPLv3-incompatible. Offline DWG→DXF conversion is the recommended path. Deferred to P2. |

---

## CATIA .model Files (UNSUPPORTED — DEFER)

### MODEL-01..MODEL-06 (6 files)

| Property | Value |
|----------|-------|
| Import Status | UNSUPPORTED (graceful) |
| Geometry Ready | NO |
| User Resolution Possible | NO |
| Notes | CATIA V4 Release 2.1 FR 4.2.1 proprietary binary. No open-source reader available. Deferred indefinitely. |

---

## Summary

| Format | Files | Geometry Ready | Raw PP Ready | User-Resolvable | Post-Confirm PP Ready |
|--------|-------|----------------|--------------|------------------|-----------------------|
| DXF    | 3     | 3              | 0            | 3                | 3 |
| IGES   | 3     | 3              | 0            | 3                | 3 (PP) / 0 (CAM) |
| PDF    | 3     | 0              | 0            | 0                | 0 (P1 pending) |
| DWG    | 3     | 0              | 0            | 0                | 0 (P2 pending) |
| .model | 6     | 0              | 0            | 0                | 0 (DEFER) |

**Key finding:** The dominant blocker for all 6 DXF/IGES files is MISSING_MATERIAL.
Once a user confirms material (e.g. "42CrMo4"), PROCESS_PLANNING is unblocked
for all 6 files. CAM for IGES files additionally requires topology reconstruction.

---

## P0 Implementation: What Was Delivered

| Component | Status |
|-----------|--------|
| `backend/interoperability/missing_data.py` | DONE — EngineeringField, MissingDataAnalysis, apply_user_confirmations, _compute_readiness |
| `backend/interoperability/title_block_material.py` | DONE — 25+ material aliases, pattern matching, no false positives |
| `backend/api/missing_data.py` | DONE — POST /api/missing-data/analyze + /confirm |
| `backend/api/app.py` router registration | DONE |
| `frontend/app/src/i18n/en.ts` i18n keys | DONE — 40 keys added |
| `frontend/app/src/i18n/tr.ts` i18n keys | DONE — Turkish equivalents |
| `tests/unit/interoperability/test_missing_data.py` | DONE — 50 tests |
| `tests/unit/interoperability/test_title_block_material.py` | DONE — 36 tests |
| `tests/qualification/test_real_sample_missing_data.py` | DONE — 49 tests |

**Total new tests:** 135 / 135 PASS

---

## Hard Rules Compliance

| Hard Rule | Status |
|-----------|--------|
| HARD RULE 1: UNKNOWN remains UNKNOWN | COMPLIANT — no defaults injected |
| HARD RULE 2: Never infer material/unit | COMPLIANT — patterns only match explicit designations |
| HARD RULE 3: No silent defaults | COMPLIANT — all defaults rejected |
| HARD RULE 4: No hidden fallback values (P, Ra=1.6, IT9) | COMPLIANT |
| HARD RULE 5: Every resolved value carries provenance | COMPLIANT — all fields have source |
| HARD RULE 6: USER_CONFIRMED ≠ file-extracted | COMPLIANT — source field enforced |
| HARD RULE 7: No overwrite of original extraction | COMPLIANT — original_extracted_value immutable |
| HARD RULE 8: Source files not altered | COMPLIANT |
| HARD RULE 9: Source files not committed | COMPLIANT — SOURCE_SAMPLE_FILES_COMMITTED=NO |
| HARD RULE 10: Review requirements unchanged | COMPLIANT |
| HARD RULE 11: No automatic manufacturing action | COMPLIANT |
| HARD RULE 12: No CNC dispatch | COMPLIANT — CNC_DISPATCH=NO in all modules |
| HARD RULE 13: No automatic adaptation | COMPLIANT |
| HARD RULE 14: Level 21 not started | COMPLIANT |
| HARD RULE 15: No force push | COMPLIANT |
| HARD RULE 16: No tag/release | COMPLIANT |

MINOR_DEFECTS_UNCHANGED=YES  
ALL_SOURCE_FILES_UNCHANGED=YES  
SOURCE_SAMPLE_FILES_COMMITTED=NO
