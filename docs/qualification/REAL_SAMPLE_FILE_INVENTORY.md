# Real Sample File Inventory

**Campaign:** MACHININGPRO_AI_REAL_SAMPLE_FILES_QUALIFICATION (extends RSQ 2026-11-12)  
**Date:** 2026-11-13  
**Source directory:** `[SAMPLE_ROOT]` (READ-ONLY, outside repo — absolute path not published)  
**Total files found:** 84  

---

## Summary by format

| Format | Count | Import support | Notes |
|--------|------:|----------------|-------|
| DXF    |    57 | SUPPORTED — Level 1 (Level 2 requires optional ezdxf) | 2D engineering drawings, `109106_01_*` series + `Pense_Sema.dxf` |
| IGES (.igs) | 15 | SUPPORTED — Level 0/1/2 varies by file | 3D surface/solid geometry |
| PDF    |     3 | NOT SUPPORTED via import pipeline (drawing analysis API available separately) | Dimensioned engineering drawings |
| DWG    |     3 | NOT SUPPORTED (no registered adapter) | AutoCAD native format |
| CATIA .model | 6 | NOT SUPPORTED (proprietary, no adapter) | CATIA V4 native format |

---

## DXF files (57 total)

All DXF files follow the `109106_01_NN[_X].dxf` naming convention except `Pense_Sema.dxf`.

| Filename | Size (bytes) |
|----------|------------:|
| 109106_01_00.dxf | ~270 000 |
| 109106_01_01.dxf through 109106_01_38.dxf | 270 000 – 9 100 000 |
| 109106_01_11_A.dxf, 109106_01_11_B.dxf, 109106_01_11_C.dxf | detail sheets |
| 109106_01_13_A.dxf, 109106_01_13_B.dxf | detail sheets |
| 109106_01_16_A.dxf | detail sheet |
| Pense_Sema.dxf | 894 575 |

**Selected for qualification testing:**

| File | Size (bytes) | Selection rationale |
|------|------------:|---------------------|
| `109106_01_30.dxf` | 271 812 | Small file; representative of series |
| `109106_01_38.dxf` | 599 563 | Medium file; likely contains more entities |
| `Pense_Sema.dxf` | 894 575 | Different drawing series; pliers schematic |

---

## IGES files (15 total)

| Filename | Size (bytes) | Notes |
|----------|------------:|-------|
| agv03773.geo_fin001.006003.igs | 217 054 | Smallest — selected |
| fa00aaj27500_004999.igs | 221 292 | Small — selected |
| fa00aan96666_001999.igs | 322 947 | |
| fa00aas38521.geo_fin001.004999.igs | 875 514 | Medium — selected |
| fa00aas24062.geo_fin001.004999.igs | 1 081 580 | |
| fa00aas38515.geo_fin001.004999.igs | 1 440 002 | |
| fa00aas38653.geo_fin001.006999.igs | 1 559 230 | |
| fa00aas24061.geo_fin001.003999.igs | 3 092 220 | |
| fa00aas38652.geo_fin001.004999.igs | 3 546 008 | |
| fa00aat46855.geo_fin001.004999.igs | 4 331 158 | |
| fa00aas07581.geo_fin001.007999.igs | 7 978 272 | |
| fa00aas26021.geo_fin001.007999.igs | 8 374 578 | |
| fa00aat29007.geo_fin001.004999.igs | 14 095 062 | |
| fa00aac86588.geo_fin001.004999.igs | 15 202 971 | |
| fa00aac86615.geo_fin001.005999.igs | 64 344 456 | ≥64 MB — exceeds MAX_IMPORT_BYTES; not selected |

**Note:** `fa00aac86615.geo_fin001.005999.igs` (64 MB) is at the import size limit. It was not selected for qualification testing to avoid ambiguous results at the boundary.

---

## PDF files (3 total)

| Filename | Size (bytes) | Notes |
|----------|------------:|-------|
| DWG-00206402-001.pdf | 342 000 | General arrangement drawing |
| DWG-00139945-001_UPPER COVER MU METAL SHIELD.pdf | 422 000 | Upper cover sheet |
| DWG-00139946-001_LOWER COVER MU METAL SHIELD.pdf | 506 000 | Lower cover sheet |

PDF files are not supported by the CAD import pipeline (`/api/import`). Drawing analysis is available via the separate `/api/drawings` endpoint (VLM-based, advisory only). All 3 PDFs selected for fail-closed verification.

---

## DWG files (3 total)

| Filename | Size (bytes) | Notes |
|----------|------------:|-------|
| Pense_Sema.dwg | 172 000 | AutoCAD native — same part as Pense_Sema.dxf |
| RAB055S(41_NOKTALI).dwg | 9 400 000 | Large — not selected |
| RAB055S(42_NOKTALI).dwg | 9 500 000 | Large — not selected |

`Pense_Sema.dwg` (DWG-01) selected; large RAB055S files (DWG-02, DWG-03) selected to exercise size handling on UNSUPPORTED path.

**Extended selection (2026-11-13 campaign):**

| Test ID | Filename | Size (bytes) | SHA-256 (first 16 hex) |
|---------|----------|-------------:|------------------------|
| DWG-01  | Pense_Sema.dwg | 172 340 | 81140812206525b3 |
| DWG-02  | RAB055S(41_NOKTALI).dwg | 9 473 951 | 92db6a2f788bfd0c |
| DWG-03  | RAB055S(42_NOKTALI).dwg | 9 474 430 | c234eef6bd9aaa61 |

---

## CATIA .model files (6 total)

| Filename | Size (bytes) |
|----------|------------:|
| 46795221-FONDELLO-SEDE-.model | 720 160 |
| 46795219-RINFORZO-MONTA.model | 2 104 480 |
| 46795237-CANALINO-SUPER.model | 2 089 200 |
| 46795365-RINFORZO-DX-OS.model | 1 201 520 |
| 46795382-OSSATURA-FIANC.model | 3 384 880 |
| 46792434-CS-FIANCATA-D-.model | 14 009 760 |

Three files selected (small/medium/large) to verify UNSUPPORTED handling across sizes.

**Extended selection (2026-11-13 campaign):**

| Test ID  | Filename | Size (bytes) | SHA-256 (first 16 hex) |
|----------|----------|-------------:|------------------------|
| MODEL-01 | 46795221-FONDELLO-SEDE-.model | 720 160    | 4586fb9702d90fda |
| MODEL-02 | 46795237-CANALINO-SUPER.model | 2 089 200  | e197331b27bbfdf2 |
| MODEL-03 | 46795382-OSSATURA-FIANC.model | 3 384 880  | 0cb31e9c2e83d681 |

---

## Format support reference

From `backend/interoperability/orchestrator.py` and `backend/interoperability/adapters/registry_helpers.py`:

| Format ID | Adapter | Level 0 | Level 1 | Level 2 | Requires |
|-----------|---------|:-------:|:-------:|:-------:|---------|
| DXF | DxfTokenAdapter | ✓ | ✓ | ✓* | Level 2: ezdxf (optional) |
| IGES | IgesTokenAdapter | ✓ | ✓ | ✓ | Pure Python |
| STEP-* | StepAdapter | ✓ | — | — | Pure Python stub |
| PDF | — | — | — | — | Not registered for import |
| DWG | — | — | — | — | Not registered |
| CATIA .model | — | — | — | — | Not registered |

---

---

## Post-Test Integrity Verification (2026-11-13)

All 15 selected source files re-hashed after testing. Result:

```
ALL_SOURCE_FILES_UNCHANGED=YES
SOURCE_SAMPLE_FILES_COMMITTED=NO
```

*Source files are READ-ONLY. This document records their existence and properties only. No sample files have been copied into the repository.*
