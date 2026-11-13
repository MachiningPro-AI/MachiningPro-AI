# MachiningPro AI — Real Sample Files Qualification Report

**Campaign:** MACHININGPRO_AI_REAL_SAMPLE_FILES_QUALIFICATION  
**Date:** 2026-11-13  
**Branch:** main  
**HEAD (before):** 6e3765c (test(qualification): add real sample file qualification evidence)  
**Engineer:** Qualification automation  
**Source files:** READ-ONLY at `[SAMPLE_ROOT]` (outside repository — absolute path not published)

---

## 1. Executive Summary

| Metric | Value |
|--------|-------|
| Source files discovered | 84 |
| File types discovered | 5 (.dxf, .igs, .dwg, .model, .pdf) |
| Files selected for testing | 15 |
| Automated pytest cases (RSQ) | 119 PASS / 0 FAIL |
| Localization tests | 35 PASS / 0 FAIL |
| Upload PASS (supported formats) | 6 / 6 |
| Upload UNSUPPORTED (graceful) | 9 / 9 |
| Drawing parser detections (DXF) | 0 (FAIL — MTEXT not decoded) |
| Drawing parser detections (PDF) | False-positives only (FAIL — revision codes misidentified) |
| Manufacturing features extracted | 0 (IGES surfaces classified but no mfg features) |
| Process plans generated | 2 CANDIDATE (DXF-01, DXF-03) from 2D geometry only |
| Machine/Tool/Cutting/CAM downstream | BLOCKED for all files (insufficient data) |
| Defects recorded | 7 (5 MAJOR, 2 MINOR, 0 BLOCKER/CRITICAL) |
| Source files changed | 0 / 15 |
| Source files committed | NO |
| All security invariants | PASS |

**Verdict: PARTIAL_REAL_SAMPLE_COMPATIBILITY**

The import pipeline is stable and fail-closed. Supported formats (DXF, IGES) produce partial results. No fabricated engineering data was detected. Five major defects prevent full end-to-end manufacturing workflow from real sample files in the current environment. These are documented for prioritized repair.

---

## 2. Tested Commit

```
HEAD_BEFORE=6e3765c
BRANCH=main
ORIGIN_MAIN=6e3765c
WORKTREE_CLEAN=YES
```

---

## 3. Source Dataset Overview

| Extension | Count | Import Support |
|-----------|------:|----------------|
| .dxf      | 57    | SUPPORTED (Level 1 without ezdxf; Level 2 with ezdxf) |
| .igs      | 15    | SUPPORTED (Level 0–2 varies by file content) |
| .dwg      | 3     | UNSUPPORTED (no registered adapter) |
| .model    | 6     | UNSUPPORTED (CATIA V4 proprietary) |
| .pdf      | 3     | UNSUPPORTED via import pipeline (pdfplumber available separately) |
| **Total** | **84**| |

No .step, .stp, .stl, .png, .jpg, .jpeg, .svg files found in the source directory.

---

## 4. File Selection Method

Three files per supported format, selected for size diversity (small / medium / large):

```
DXF_SELECTED=3    (DXF-01=271 KB, DXF-02=309 KB, DXF-03=895 KB)
STEP_SELECTED=0   (not present)
IGES_SELECTED=3   (IGS-01=217 KB, IGS-02=221 KB, IGS-03=876 KB)
PDF_SELECTED=3    (all 3 available: 342 KB, 422 KB, 506 KB)
PNG_SELECTED=0    (not present)
JPG_SELECTED=0    (not present)
DWG_SELECTED=3    (all 3: 172 KB, 9.5 MB, 9.5 MB)
MODEL_SELECTED=3  (3 of 6: 720 KB, 2.1 MB, 3.4 MB)
```

No cherry-picking: files were selected by size rank, not by expected pass probability.

---

## 5. Safety / Privacy Rules Observed

- Source files never edited, renamed, moved, or deleted.
- Source files not copied into repository paths.
- Absolute source directory path not included in public-facing reports.
- No NC code dispatched to any machine.
- No auto-approval of extracted engineering data.
- No production code modifications in this campaign.

---

## 6. Files Tested — Pre-Test Hashes

| Test ID | Format | Size (bytes) | SHA-256 (first 16 hex) |
|---------|--------|-------------:|------------------------|
| DXF-01  | DXF    | 271 812      | e694952f02d7fb5b |
| DXF-02  | DXF    | 309 463      | 296920507d9a7bee |
| DXF-03  | DXF    | 894 575      | db0b634b4af40ce9 |
| IGS-01  | IGES   | 217 054      | 8562464749c78da7 |
| IGS-02  | IGES   | 221 292      | 9dbcc011ef10c688 |
| IGS-03  | IGES   | 875 514      | 9a85c0b6c9224606 |
| PDF-01  | PDF    | 342 397      | f34d1e36a36f5702 |
| PDF-02  | PDF    | 421 527      | 44b789100a566577 |
| PDF-03  | PDF    | 505 823      | 140e671d13754ab7 |
| DWG-01  | DWG    | 172 340      | 81140812206525b3 |
| DWG-02  | DWG    | 9 473 951    | 92db6a2f788bfd0c |
| DWG-03  | DWG    | 9 474 430    | c234eef6bd9aaa61 |
| MODEL-01| .model | 720 160      | 4586fb9702d90fda |
| MODEL-02| .model | 2 089 200    | e197331b27bbfdf2 |
| MODEL-03| .model | 3 384 880    | 0cb31e9c2e83d681 |

---

## 7. DXF Results

### File-Level Outcomes

| Test ID | Status | entity_refs | Curves | Capability | Parse Time |
|---------|--------|------------:|-------:|-----------|----------:|
| DXF-01  | DEGRADED | 1 (DxfHeader) | 632 (591 LINE, 9 CIRCLE, 30 ARC, 2 ELLIPSE) | LEVEL_8_COST_RFQ_INTELLIGENCE | 0.31 s |
| DXF-02  | DEGRADED | 1 (DxfHeader) | 686 (620 LINE, 64 ARC, 2 ELLIPSE) | LEVEL_8_COST_RFQ_INTELLIGENCE | 0.08 s |
| DXF-03  | DEGRADED | 1 (DxfHeader) | 313 (258 LINE, 43 ARC, 11 CIRCLE, 1 POLYLINE) | LEVEL_8_COST_RFQ_INTELLIGENCE | 0.17 s |

**DXF Upload:** PASS for all 3 (accepted without exception).  
**DXF Status DEGRADED:** Correct — ezdxf not installed; Level 1 token adapter only.  
**Entity_refs:** 1 per file (DxfHeader only) — defect DEF-RSQ-002.  
**Geometry:** Correctly extracted at CanonicalGeometry level despite DEGRADED status.  
**normalization_status:** SUCCESS for all 3.

### DXF Annotation Content (observed)

DXF-01 contains MTEXT-formatted annotations including:
- Numeric dimension values (47.5, 35, 8, 6, 1 visible in raw tokens)
- Surface finish table header ("PURUZLULUK Ra (MIKRON)")
- General tolerance table ("GENEL TOLERANS", "BOYUT (mm)", "TOLERANS")
- Turkish title block ("TARIH", "DEGISIKLIK", revision data)
- Drawing standard reference: "FORM NO: ETQBE-006-31F"
- Copyright notice visible in MTEXT

None of this annotation content was extracted by the drawing parser due to MTEXT formatting codes (defect DEF-RSQ-006).

**DETECTED_UNIT:** UNKNOWN (mm implied by "BOYUT (mm)" annotation, but not programmatically extracted)  
**ANNOTATIONS_FOUND:** FAIL — 0 engineering detections  
**FEATURES_FOUND:** PARTIAL — geometry only  
**FACE_COUNT:** 0 (2D drawing — expected)  
**BODY_COUNT:** 0 (2D drawing — expected)

---

## 8. STEP Results

```
STEP_FILES_TESTED=0
STEP_STATUS=NOT_APPLICABLE (no STEP files in source directory)
```

---

## 9. IGES Results

### File-Level Outcomes

| Test ID | Status | entity_refs | Curves | Surfaces | Classified Faces | Mfg Features | Parse Time |
|---------|--------|------------:|-------:|---------:|----------------:|-------------:|----------:|
| IGS-01  | UNSUPPORTED | 521 | 247 | 119 | 119 (96 PLANAR, 23 FREEFORM) | 0 | 0.16 s |
| IGS-02  | PARTIAL | 1 | 0 | 0 | 0 | 0 | 0.02 s |
| IGS-03  | DEGRADED | 1931 | 1152 | 191 | 191 (64 PLANAR, 127 FREEFORM) | 0 | 0.56 s |

### Entity Kind Histogram

**IGS-01 (521 entities):**
- IgesCanonicalCurve: 247
- IgesCanonicalSurface: 118
- IgesUnsupportedMetadataEntity: 67
- IgesUnsupportedGeometryType: 42
- IgesTransformationMatrix: 39
- IgesCurveOnParametricSurface: 4
- IgesCanonicalBoundedSurface: 1
- IgesHeader: 1, IgesUnsupportedEntity: 1

**IGS-02 (1 entity):**
- IgesHeader: 1 (only)

**IGS-03 (1931 entities):**
- IgesCanonicalCurve: 1152
- IgesUnsupportedGeometryType: 384
- IgesCanonicalSurface: 191
- IgesTransformationMatrix: 152
- IgesUnsupportedMetadataEntity: 48
- IgesCurveOnParametricSurface: 2
- IgesHeader: 1
- IgesUnsupportedPresentationEntity: 1

**Notes:**
- IGS-01 has valid geometry (bounding box present, curves + surfaces extracted) but status=UNSUPPORTED due to defect DEF-RSQ-004.
- IGS-02 produces only a header entity from a 221 KB file — defect DEF-RSQ-005.
- IGS-03 has the richest content: 1931 entities, 1152 curves, 191 classified faces.
- No manufacturing features extracted from any IGES file — defect DEF-RSQ-007.

---

## 10. PDF Results

### Upload Pipeline (CadImportOrchestrator)

| Test ID | Status | Error Message | Controlled |
|---------|--------|--------------|-----------|
| PDF-01  | UNSUPPORTED | "No adapter registered for format ''" | YES |
| PDF-02  | UNSUPPORTED | "No adapter registered for format ''" | YES |
| PDF-03  | UNSUPPORTED | "No adapter registered for format ''" | YES |

UNSUPPORTED is correct behavior. Format string empty — defect DEF-RSQ-001.

### Drawing Intelligence (pdfplumber pathway)

PDF files are Turkish engineering drawings. pdfplumber successfully extracts text.

| Test ID | Pages | Total Tokens | Detections | Types | False Positives |
|---------|------:|-------------:|----------:|-------|----------------|
| PDF-01  | 1 | 767 | 3 | FIT (P00, P00, K1) | 3 / 3 (all false positives) |
| PDF-02  | 1 | 497 | 2 | FIT (P00, A2) | 2 / 2 (all false positives) |
| PDF-03  | 1 | 541 | 2 | FIT (P00, A2) | 2 / 2 (all false positives) |

PDF files contain:
- Turkish revision block (TASNIF DISI, DEG.NO, TARIH columns)
- Material specification: DIN17405/SS-EN 60404-1/JIS C 2531 (PDF-02, PDF-03)
- Drawing numbers with "DWG-00xxxxxx-001" format
- Notes in Turkish (PARÇA DIN17405... UYG text)

The token extractor misclassifies title-block revision codes (P00, A2, K1) as ISO tolerance fit codes — defect DEF-RSQ-003.

**OCR_REQUIRED:** NO (native PDF text extraction successful via pdfplumber)  
**DIMENSIONS_FOUND:** 0 (no dimension values extracted)  
**TOLERANCES_FOUND:** 0  
**GD&T_FOUND:** 0  
**FALSE_POSITIVE_OBSERVED:** YES (fit codes)

---

## 11. Image Drawing Results

```
PNG_FILES_TESTED=0
JPG_FILES_TESTED=0
IMAGE_DRAWING_STATUS=NOT_APPLICABLE (no image drawing files in source directory)
```

---

## 12. Drawing Parser Results

| TEST_ID | FORMAT | UNIT | DETECTIONS | DIMENSIONS | TOLERANCES | FIT | THREAD | SURFACE_FINISH | GD&T | DATUM | NOTES | WARNINGS | STATUS |
|---------|--------|------|----------:|----------:|----------:|----:|-------:|---------------:|----:|------:|-------|----------|--------|
| DXF-01 | DXF | UNKNOWN | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | MTEXT present | MTEXT codes not stripped | FAIL |
| DXF-02 | DXF | UNKNOWN | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | MTEXT codes not stripped | FAIL |
| DXF-03 | DXF | UNKNOWN | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | — | MTEXT codes not stripped | FAIL |
| IGS-01 | IGES | — | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 3D geometry | NOT_APPLICABLE | NOT_APPLICABLE |
| IGS-02 | IGES | — | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 3D geometry | NOT_APPLICABLE | NOT_APPLICABLE |
| IGS-03 | IGES | — | N/A | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 3D geometry | NOT_APPLICABLE | NOT_APPLICABLE |
| PDF-01 | PDF | UNKNOWN | 3 | 0 | 0 | 3 (FP) | 0 | 0 | 0 | 0 | Turkish rev table | Revision codes → false FIT | FAIL |
| PDF-02 | PDF | UNKNOWN | 2 | 0 | 0 | 2 (FP) | 0 | 0 | 0 | 0 | Turkish rev table | Same | FAIL |
| PDF-03 | PDF | UNKNOWN | 2 | 0 | 0 | 2 (FP) | 0 | 0 | 0 | 0 | Turkish rev table | Same | FAIL |

FP = False Positive

---

## 13. CAD Feature Recognition Results

| TEST_ID | GEOMETRY_ENTITIES | BODY_COUNT | FACE_COUNT | FEATURE_COUNT | FEATURE_TYPES | RECOGNITION_METHOD | WARNINGS | STATUS |
|---------|-------------------|----------:|----------:|-------------:|---------------|-------------------|----------|--------|
| DXF-01 | 632 curves (2D) | 0 | 0 | 0 (mfg_features) | CANDIDATE drilling from 9 circles via process_intel | 2D_GEOMETRY_ONLY | ezdxf absent; no topology | PARTIAL |
| DXF-02 | 686 curves (2D) | 0 | 0 | 0 | None — INSUFFICIENT_DATA | 2D_GEOMETRY_ONLY | No circles detected | PARTIAL |
| DXF-03 | 313 curves (2D) | 0 | 0 | 0 (mfg_features) | CANDIDATE drilling from 11 circles | 2D_GEOMETRY_ONLY | ezdxf absent; no topology | PARTIAL |
| IGS-01 | 247 curves + 119 surfaces | 0 | 119 | 0 | 119 classified (96 PLANAR, 23 FREEFORM) | GEOMETRY_ONLY | No topology → no mfg features | PARTIAL |
| IGS-02 | 0 | 0 | 0 | 0 | None | — | Header-only parse | FAIL |
| IGS-03 | 1152 curves + 191 surfaces | 0 | 191 | 0 | 191 classified (64 PLANAR, 127 FREEFORM) | GEOMETRY_ONLY | No topology → no mfg features | PARTIAL |

---

## 14. Process Route Results

| TEST_ID | PLAN_STATUS | RECOGNITION_BASIS | OPS | MATERIAL_KNOWN | TOLERANCE_KNOWN | STATUS |
|---------|------------|-------------------|----:|---------------:|----------------:|--------|
| DXF-01 | CANDIDATE_PLAN | 2D_GEOMETRY_ONLY | 18 | NO | NO | PARTIAL |
| DXF-02 | INSUFFICIENT_DATA | 2D_GEOMETRY_ONLY | 0 | NO | NO | BLOCKED |
| DXF-03 | CANDIDATE_PLAN | 2D_GEOMETRY_ONLY | 22 | NO | NO | PARTIAL |
| IGS-01 | INSUFFICIENT_DATA | GEOMETRY_ONLY | 0 | NO | NO | BLOCKED |
| IGS-02 | None | — | — | NO | NO | BLOCKED |
| IGS-03 | INSUFFICIENT_DATA | GEOMETRY_ONLY | 0 | NO | NO | BLOCKED |

Process route handoff from DXF geometry produces CANDIDATE operations (CENTER_DRILLING + DRILLING pairs for each detected circle). This is based solely on 2D circle geometry — no tolerances, no material, no surface finish.

---

## 15. Process Planning Results

| TEST_ID | PLAN_STATUS | ACTIONABLE | MISSING_INPUTS | STATUS |
|---------|------------|-----------|----------------|--------|
| DXF-01 | CANDIDATE_PLAN | NO | material, tolerance, surface_finish, work_envelope | PARTIAL |
| DXF-02 | INSUFFICIENT_DATA | NO | All inputs | BLOCKED |
| DXF-03 | CANDIDATE_PLAN | NO | material, tolerance, surface_finish, work_envelope | PARTIAL |
| IGS-01 | INSUFFICIENT_DATA | NO | All inputs | BLOCKED |
| IGS-02 | None | NO | All inputs | BLOCKED |
| IGS-03 | INSUFFICIENT_DATA | NO | All inputs | BLOCKED |

CANDIDATE_PLAN correctly signals that the plan is geometry-derived only, not manufacturing-ready.

---

## 16. Machine Selection Results

```
MACHINE_SELECTION_STATUS=BLOCKED for all tested files
REASON=No confirmed manufacturing requirements (material, work envelope, tolerance grade all UNKNOWN)
```

---

## 17. Tool Selection Results

```
TOOL_SELECTION_STATUS=BLOCKED for all tested files
REASON=No confirmed operations with known material and feature geometry
```

---

## 18. Cutting Data Results

```
CUTTING_DATA_STATUS=BLOCKED_MISSING_MATERIAL for all tested files
REASON=Material UNKNOWN for all sample files; cutting data lookup requires material grade
```

---

## 19. CAM / Toolpath Results

```
CAM_STATUS=NOT_APPLICABLE for 2D DXF files; BLOCKED for IGES (no mfg features)
TOOLPATH_STATUS=NOT_APPLICABLE / BLOCKED
MISSING_INPUTS=3D topology, confirmed features, material, operation parameters
```

---

## 20. NC Safety Results

```
OFFLINE_CANDIDATE=True  (no NC generated; nothing to dispatch)
NOT_DISPATCHED=True
AUTO_CNC_DISPATCH_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
```

---

## 21. TR Localization

Localization test suite: **35 PASS**.

Backend error messages during real file testing: all in English (no TR leakage).

Backend error messages observed:
- "No adapter registered for format ''" (DWG/PDF/MODEL — controlled, no TR content)
- No other error messages for supported formats (DXF/IGES import succeeded without error)

Frontend i18n: 1815 TR keys (parity with EN: PASS).

```
TR_LANGUAGE_LEAK_COUNT=0
TR_LANGUAGE_LEAK_EXAMPLES=none
```

---

## 22. EN Localization

```
EN_LANGUAGE_LEAK_COUNT=0
EN_LANGUAGE_LEAK_EXAMPLES=none
```

Pre-existing localization defect (from prior audit, not in scope here): ~86 hardcoded EN strings in `ProcessRoutesPage.tsx` and other frontend components that bypass the `t()` function. These were documented in `LOCALIZATION_AUDIT.md` and are not new findings from this campaign.

---

## 23. Error Handling

All backend error messages in this campaign were:

| Property | Observed |
|----------|---------|
| Controlled (no raw exception text) | YES for all 15 files |
| No Python Traceback | YES for all 15 files |
| No server filesystem path | YES for all 15 files |
| No raw stack trace | YES for all 15 files |
| Localized message where applicable | YES (English) |

```
ERROR_HANDLING_STATUS=PASS
```

One defect: error message text uses empty format string instead of format name (DEF-RSQ-001 — MINOR).

---

## 24. Cross-Module Consistency

### Diameter consistency (DXF)

No diameter values were extracted by the drawing parser (0 detections). The process intelligence generates CANDIDATE operations for circle geometry, but nominal diameters are not propagated to the operation record (operation.nominal_diameter is not set). Therefore diameter consistency across modules could not be verified — not a fabrication issue, but a capability limitation.

### Material consistency

Material is UNKNOWN for all files. No module in the pipeline injected a default material at any stage. Consistent: UNKNOWN → UNKNOWN across Drawing Parser, Process Planning, Cutting Data.

### Feature type consistency

DXF geometry circles → process_intelligence CANDIDATE operations (CENTER_DRILLING + DRILLING).
No inconsistency found — the same feature IDs are referenced in the candidate operations.

---

## 25. Format Scorecard

### DXF

```
FILES_TESTED=3
UPLOAD_PASS=3/3
PARSE_PASS=0/3     (FAIL — MTEXT not decoded; 0 engineering detections)
FEATURE_PASS=0/3   (PARTIAL only — geometry extracted but no mfg features)
DOWNSTREAM_PASS=0/3 (BLOCKED — material/tolerance unknown)
```

### IGES

```
FILES_TESTED=3
UPLOAD_PASS=3/3    (accepted without exception)
PARSE_PASS=1/3     (IGS-03 DEGRADED with 1931 entity_refs; IGS-01 UNSUPPORTED despite geometry; IGS-02 header-only)
FEATURE_PASS=0/3   (surface classification only; no manufacturing features)
DOWNSTREAM_PASS=0/3 (BLOCKED — no mfg features)
```

### PDF

```
FILES_TESTED=3
UPLOAD_PASS=0/3    (not supported via CAD import — UNSUPPORTED is correct behavior)
PARSE_PASS=0/3     (false-positive detections; no genuine engineering data extracted)
FEATURE_PASS=0/3   (NOT_APPLICABLE)
DOWNSTREAM_PASS=0/3 (NOT_APPLICABLE)
```

### DWG

```
FILES_TESTED=3
UPLOAD_PASS=0/3    (UNSUPPORTED — correct behavior; no adapter registered)
PARSE_PASS=0/3     (NOT_APPLICABLE)
FEATURE_PASS=0/3   (NOT_APPLICABLE)
DOWNSTREAM_PASS=0/3 (NOT_APPLICABLE)
```

### CATIA .model

```
FILES_TESTED=3
UPLOAD_PASS=0/3    (UNSUPPORTED — correct behavior; proprietary format)
PARSE_PASS=0/3     (NOT_APPLICABLE)
FEATURE_PASS=0/3   (NOT_APPLICABLE)
DOWNSTREAM_PASS=0/3 (NOT_APPLICABLE)
```

---

## 26. Defects

| DEFECT_ID | FORMAT | MODULE | SEVERITY | SUMMARY |
|-----------|--------|--------|----------|---------|
| DEF-RSQ-001 | PDF/DWG/.model | Format detection | MINOR | Error message contains empty format string instead of format name |
| DEF-RSQ-002 | DXF | DxfTokenAdapter | MAJOR | ezdxf absent → Level 1 only; entity_refs limited to DxfHeader |
| DEF-RSQ-003 | PDF | run_token_extraction | MINOR | Revision codes (P00, A2, K1) falsely classified as ISO fit codes |
| DEF-RSQ-004 | IGES | IgesTokenAdapter | MAJOR | IGS-01 status UNSUPPORTED despite valid geometry extraction |
| DEF-RSQ-005 | IGES | IgesTokenAdapter | MAJOR | IGS-02 (221 KB) produces only IgesHeader entity |
| DEF-RSQ-006 | DXF | Drawing parser | MAJOR | MTEXT formatting codes not stripped → 0 engineering detections |
| DEF-RSQ-007 | IGES | CAD feature recognition | MAJOR | IGES surface classification does not produce manufacturing features |

Full details: `docs/qualification/REAL_SAMPLE_FILE_DEFECT_REGISTER.md`

---

## 27. Blockers

```
BLOCKER_COUNT=0
```

No campaign-level blockers. The qualification ran to completion. All files were tested; defects were observed and recorded.

---

## 28. Real-World File Compatibility

| Format | Stability | Geometry Extraction | Engineering Data Extraction | Downstream Usability |
|--------|-----------|---------------------|-----------------------------|--------------------|
| DXF | GOOD (no crashes) | GOOD (curves/arcs/circles) | FAIL (annotation not extracted) | PARTIAL (geometry-only CANDIDATE) |
| IGES | GOOD (no crashes) | GOOD (surfaces/curves) | NOT_APPLICABLE | BLOCKED |
| PDF | GOOD (graceful UNSUPPORTED) | NOT_APPLICABLE | PARTIAL (text extractable but false positives) | NOT_APPLICABLE |
| DWG | GOOD (graceful UNSUPPORTED) | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |
| CATIA .model | GOOD (graceful UNSUPPORTED) | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE |

---

## 29. Recommended Fix Priority

| Priority | Defect | Rationale |
|----------|--------|-----------|
| 1 (HIGH) | DEF-RSQ-002 — Install ezdxf | Unlocks Level 2 DXF import; enables full entity histogram; enables MTEXT access |
| 2 (HIGH) | DEF-RSQ-006 — MTEXT preprocessing | Enables engineering annotation extraction from all DXF files |
| 3 (HIGH) | DEF-RSQ-007 — IGES mfg features | Enables process route generation from IGES geometry |
| 4 (MEDIUM) | DEF-RSQ-004 — IGES UNSUPPORTED status | Prevents IGS-01 from reaching downstream modules despite valid geometry |
| 5 (MEDIUM) | DEF-RSQ-005 — IGS-02 header-only | Investigate IGES variant compatibility |
| 6 (LOW) | DEF-RSQ-003 — PDF false-positive fits | Improve fit token parser to require dimension context |
| 7 (LOW) | DEF-RSQ-001 — Empty format string | Cosmetic improvement to error messages |

---

## 30. Final Verdict

```
HEAD_BEFORE=6e3765c

SOURCE_FILES_DISCOVERED=84
FILE_TYPES_DISCOVERED=5

DXF_FILES_TESTED=3
STEP_FILES_TESTED=0
IGES_FILES_TESTED=3
PDF_FILES_TESTED=3
PNG_FILES_TESTED=0
JPG_FILES_TESTED=0
DWG_FILES_TESTED=3
MODEL_FILES_TESTED=3
OTHER_FILES_TESTED=0

TOTAL_FILES_TESTED=15

UPLOAD_PASS_COUNT=6
DRAWING_PARSER_PASS_COUNT=0
CAD_FEATURE_PASS_COUNT=0
PROCESS_ROUTE_PASS_COUNT=0
PROCESS_PLANNING_PASS_COUNT=0
MACHINE_SELECTION_PASS_COUNT=0
TOOL_SELECTION_PASS_COUNT=0
CAM_PASS_COUNT=0

PARTIAL_COUNT=12
FAIL_COUNT=9
BLOCKED_COUNT=22
UNSUPPORTED_COUNT=9

FABRICATED_FEATURE_FOUND=NO
FABRICATED_DIMENSION_FOUND=NO
FABRICATED_TOLERANCE_FOUND=NO
FABRICATED_RA_FOUND=NO
FABRICATED_MATERIAL_FOUND=NO

TR_LANGUAGE_LEAK_COUNT=0
EN_LANGUAGE_LEAK_COUNT=0

BLOCKER_COUNT=0
CRITICAL_COUNT=0
MAJOR_COUNT=5
MINOR_COUNT=2
COSMETIC_COUNT=0

ALL_SOURCE_FILES_UNCHANGED=YES
SOURCE_SAMPLE_FILES_COMMITTED=NO

REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO

FORMAT_SCORECARD_PATH=docs/qualification/MACHININGPRO_AI_REAL_SAMPLE_FILES_QUALIFICATION_REPORT.md#25-format-scorecard
TEST_MATRIX_PATH=docs/qualification/REAL_SAMPLE_FILE_TEST_MATRIX.md
DEFECT_REGISTER_PATH=docs/qualification/REAL_SAMPLE_FILE_DEFECT_REGISTER.md
FINAL_REPORT_PATH=docs/qualification/MACHININGPRO_AI_REAL_SAMPLE_FILES_QUALIFICATION_REPORT.md

PRODUCTION_FILES_CHANGED=0

FINAL_RESULT=PARTIAL_REAL_SAMPLE_COMPATIBILITY
```
