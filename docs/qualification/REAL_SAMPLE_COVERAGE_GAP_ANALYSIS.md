# Real Sample Coverage Gap Analysis

**Campaign:** MACHININGPRO_AI_REAL_SAMPLE_COVERAGE_EXPANSION_ANALYSIS  
**Date (P0):** 2026-11-13 | **Date (P1 update):** 2026-11-14  
**Branch:** main | HEAD (P0): f723767 | HEAD_BEFORE_P1: 17bcdc9  
**Analyst:** Qualification automation  
**Precondition:** All 5 MAJOR defects (DEF-RSQ-002/004/005/006/007) fixed in f723767.  
**P1 completion:** P1-A (hybrid PDF), P1-B (DXF annotation linking), P1-C (IGES topology), P1-D (partial arc recognition) implemented and tested.  

> HARD RULE: No production code changed during P0 analysis. P1 changes tracked separately.  
> DWG and `.model` remain UNSUPPORTED / DEFERRED — NOT changed by P1.

---

## 1. Executive Summary

After fixing all 5 MAJOR defects the pipeline is more capable but no file achieves full end-to-end
manufacturing readiness. The root causes fall into four categories:

| Root Cause | Files Affected | Resolvable? |
|------------|---------------:|-------------|
| MISSING_MATERIAL | DXF-01, DXF-03, IGS-01, IGS-02, IGS-03 | Via user confirmation or title-block extraction |
| MISSING_TOPOLOGY | IGS-01, IGS-02, IGS-03 | Requires topology reconstruction from IGES B-Rep |
| NO_MANUFACTURING_FEATURE | DXF-02 | 2D drawing has no circle geometry; content-limited |
| UNSUPPORTED_FORMAT | PDF×3, DWG×3, .model×3 | PDF: OCR path viable; DWG: conversion needed; .model: infeasible |

---

## 2. Per-File Blocker Chain (Post-Fix State)

Legend: **P**=PASS | **PT**=PARTIAL | **BL**=BLOCKED | **US**=UNSUPPORTED | **NA**=NOT_APPLICABLE

### DXF-01 — `109106_01_30.dxf` (271 KB, 2D drawing, Turkish part)

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | DEGRADED, 20 refs (1 header + 9 circles + 10 lines sample) |
| parse | PT | 20 of 727 entities captured in entity_refs; 65 MTEXT entities accessible via drawing parser |
| geometry | P | 9 CIRCLE entities, 591 LINEs, 30 ARCs; unit=Millimeters (DxfHeader) |
| annotations | PT | MTEXT decoding active (DEF-RSQ-006 fixed); drawing parser extracts fits/threads; not auto-fed to process_intelligence |
| features | PT | 9 CANDIDATE holes from circles (from 2D geometry only; depth unknown) |
| material | **BL** | Not present in file; not in DxfHeader; Turkish title block untranslated |
| tolerance | PT | MTEXT contains general tolerance table ("GENEL TOLERANS") but not extracted into process_intelligence |
| process route | PT | CANDIDATE_PLAN 18 ops (CENTER_DRILLING + DRILLING pairs) from 9 circles |
| machine/tool | BL | No confirmed material or feature requirements |
| CAM | NA | 2D drawing; no 3D toolpath possible |

**FIRST TRUE BLOCKER: MISSING_MATERIAL**

---

### DXF-02 — `109106_01_38.dxf` (309 KB, 2D drawing)

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | DEGRADED, 599 refs |
| parse | PT | 599 entities; 65+ MTEXT entities accessible |
| geometry | PT | 686 curves (620 LINE, 64 ARC, 2 ELLIPSE); **0 CIRCLE entities** |
| annotations | PT | MTEXT decoding active; but no geometry anchors for features |
| features | **BL** | 0 mfg_features; ARC entities not classified as hole candidates |
| material | BL | Not present |
| tolerance | BL | No feature association possible |
| process route | BL | INSUFFICIENT_DATA |
| machine/tool | BL | — |
| CAM | NA | 2D drawing |

**FIRST TRUE BLOCKER: NO_MANUFACTURING_FEATURE**  
Root reason: This 2D drawing contains only LINEs, ARCs, and ELLIPSEs. The current feature recognizer
produces CANDIDATE holes from CIRCLE entities only. ARCs (which could be part-circles for pockets or
profiles) are not classified as manufacturing features in the 2D path.

---

### DXF-03 — `Pense_Sema.dxf` (894 KB, pliers schematic)

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | DEGRADED, 20 refs |
| parse | PT | 20 entity refs (11 circles + 8 lines + 1 header); file has rich MTEXT content |
| geometry | P | 11 CIRCLE entities, 258 LINEs, 43 ARCs; unit=Millimeters |
| annotations | PT | MTEXT decoding active; dimension/tolerance data present but not auto-linked |
| features | PT | 11 CANDIDATE holes from circles |
| material | **BL** | Not present in file |
| tolerance | PT | MTEXT contains tolerances; not extracted into process_intelligence |
| process route | PT | CANDIDATE_PLAN 22 ops (CENTER_DRILLING + DRILLING pairs) |
| machine/tool | BL | No material; no confirmed requirements |
| CAM | NA | 2D drawing |

**FIRST TRUE BLOCKER: MISSING_MATERIAL**

---

### IGS-01 — `agv03773.geo_fin001.006003.igs` (217 KB, 3D IGES)

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | DEGRADED, 521 refs; succeeded=True (DEF-RSQ-004 fixed) |
| parse | P | 521 entities; full entity histogram |
| geometry | P | 119 surfaces, 247 curves; bounding box present |
| annotations | NA | 3D IGES has no annotation layer |
| features | PT | 96 CANDIDATE/UNKNOWN mfg features from planar surfaces (DEF-RSQ-007 fixed) |
| material | **BL** | Not present in IGES file |
| tolerance | BL | Not extractable from IGES; would require GD&T annotation layer |
| process route | PT | CANDIDATE_PLAN; 0 operations (CANDIDATE/UNKNOWN features do not generate operations) |
| machine/tool | BL | No material; no confirmed feature type |
| CAM | BL | No CONFIRMED features; topology not reconstructed |

**FIRST TRUE BLOCKER: MISSING_TOPOLOGY**  
Root reason: 96 classified faces exist but all are UNKNOWN type with CANDIDATE status. Without
CanonicalTopology (bodies, shells, edges), it is impossible to determine whether a planar face is
a floor, a wall, a pocket, or a datum — no operation can be generated. After topology, MISSING_MATERIAL
would be the next blocker.

---

### IGS-02 — `fa00aaj27500_004999.igs` (221 KB, 3D IGES)

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | DEGRADED, 560 refs; succeeded=True (DEF-RSQ-005 fixed) |
| parse | P | 560 entities; full Hollerith-safe parse |
| geometry | P | 16 surfaces |
| annotations | NA | 3D IGES |
| features | PT | 16 CANDIDATE/UNKNOWN mfg features |
| material | **BL** | Not present |
| tolerance | BL | Not extractable |
| process route | PT | CANDIDATE_PLAN; 0 operations |
| machine/tool | BL | — |
| CAM | BL | — |

**FIRST TRUE BLOCKER: MISSING_TOPOLOGY** (then MISSING_MATERIAL)

---

### IGS-03 — `fa00aas38521.geo_fin001.004999.igs` (875 KB, 3D IGES)

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | DEGRADED, 1931 refs; succeeded=True |
| parse | P | 1931 entities; richest content |
| geometry | P | 191 surfaces (64 PLANAR + 127 FREEFORM), 1152 curves |
| annotations | NA | 3D IGES |
| features | PT | 64 CANDIDATE/UNKNOWN from planar surfaces; 127 FREEFORM not classified as mfg features |
| material | **BL** | Not present |
| tolerance | BL | — |
| process route | PT | CANDIDATE_PLAN; 0 operations |
| machine/tool | BL | — |
| CAM | BL | — |

**FIRST TRUE BLOCKER: MISSING_TOPOLOGY** (then MISSING_MATERIAL)

---

### PDF-01, PDF-02, PDF-03

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | Graceful UNSUPPORTED (DEF-RSQ-001: empty format string in error msg — MINOR, open) |
| parse | **US** | PDF not registered in CAD import pipeline |
| geometry | US | — |
| annotations | US | — |
| all downstream | NA | — |

**FIRST TRUE BLOCKER: UNSUPPORTED_FORMAT**  
(PDF drawing intelligence available as separate API; see section 4)

---

### DWG-01, DWG-02, DWG-03

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | Graceful UNSUPPORTED |
| parse | **US** | DWG adapter not registered |
| all downstream | NA | — |

**FIRST TRUE BLOCKER: UNSUPPORTED_FORMAT**  
(AC1018 = AutoCAD 2004; see section 5)

---

### MODEL-01, MODEL-02, MODEL-03

| Stage | Status | Evidence |
|-------|--------|----------|
| import | P | Graceful UNSUPPORTED |
| parse | **US** | .model adapter not registered |
| all downstream | NA | — |

**FIRST TRUE BLOCKER: UNSUPPORTED_FORMAT**  
(CATIA V4 binary; see section 6)

---

## 3. PDF File Analysis (MUST 3)

### File inspection results

All three PDF files inspected via raw binary analysis (pdfplumber not installed in test env;
pdfplumber was used at qualification time and extracted text successfully):

| Property | PDF-01 (DWG-00206402) | PDF-02 (DWG-00139945) | PDF-03 (DWG-00139946) |
|----------|----------------------|----------------------|----------------------|
| PDF version | 1.7 | 1.7 | 1.7 |
| Pages | 1 | 1 | 1 |
| File size | 342 KB | 422 KB | 506 KB |
| Font declared | YES (font reference present) | YES | YES |
| Font type (Type1/TrueType) | NO (embedded, non-standard) | NO | NO |
| Native text operators (BT/Tf/Tj) | NOT DETECTED in uncompressed sections | NOT DETECTED | NOT DETECTED |
| Image XObjects | 2 per page | 2 per page | 2 per page |
| Compression | FlateDecode | FlateDecode | FlateDecode |
| JPEG / JBIG2 raster | NO (FlateDecode only) | NO | NO |

**Interpretation:**  
The PDFs are PDF 1.7 files with the drawing content in compressed image XObjects (FlateDecode-encoded
raster images). The two image XObjects per page likely represent the drawing body and the title block.
pdfplumber previously extracted 767/497/541 text tokens from these files. These tokens come from
form-XObject-embedded text or from searchable-PDF text that is encoded in a compressed content stream
(which is why BT/Tf was not found in the uncompressed prefix).

**Key conclusion:** The PDFs contain some native text (title block elements) but the engineering drawing
content (dimension lines, tolerance callouts, GD&T symbols) is in rasterized form within the image
XObjects. The previously extracted tokens (P00, A2, K1) were title block text — not engineering data.

```
PDF_NATIVE_TEXT_AVAILABLE=PARTIAL
  (title block / revision block text is native; drawing area geometry is rasterized)
PDF_VECTOR_CONTENT_AVAILABLE=NO
  (no vector path operators detected; drawing area is raster image)
PDF_OCR_REQUIRED=YES
  (for engineering drawing content: dimensions, tolerances, GD&T symbols)
```

---

## 4. Safest PDF Architecture (MUST 4)

### Recommended pipeline

```
Stage 1 — Native text extraction (always first)
  Library: pdfplumber (MIT license) — already a project dependency
  Extracts: title block text, drawing number, revision codes, any embedded text
  Limitation: does not capture rasterized dimension lines or GD&T callouts

Stage 2 — Vector geometry extraction (when pdfplumber finds vector paths)
  Library: pdfplumber or pypdf (BSD/MIT) for path extraction
  Extracts: dimension lines, leader lines (if drawn as PDF vector paths)
  Applies to: drawings exported from CAD as pure vector PDF (not these samples)

Stage 3 — OCR fallback (only when Stages 1+2 yield insufficient engineering data)
  Library: pytesseract + Tesseract OCR (Apache 2.0 / dual-licensed) OR
           easyocr (Apache 2.0, requires PyTorch)
  Applies to: these three PDFs (rasterized drawing area)
  Risk: OCR can misread dimensions (1→l, 0→O, comma/period ambiguity)
  Mandatory guard: all OCR detections must be PENDING review (never auto-confirmed)
```

### Decision tree

```
load PDF
  → extract native text via pdfplumber
    → if text contains engineering tokens → annotate directly
  → extract vector paths via pdfplumber
    → if paths form dimension geometry → extract values
  → if engineering data still missing → trigger OCR
    → all OCR results: status=PENDING, requires user confirmation
    → NEVER auto-promote OCR result to CONFIRMED
```

### License assessment

| Library | License | Commercial use | Note |
|---------|---------|---------------|------|
| pdfplumber | MIT | YES | Already used; zero risk |
| pypdf | BSD 3-Clause | YES | Pure Python, light dependency |
| pytesseract | MIT wrapper + Tesseract Apache 2.0 | YES | Requires Tesseract binary (Apache 2.0) |
| easyocr | Apache 2.0 | YES | Requires PyTorch; heavy dependency |
| pdf2image | MIT | YES | Requires poppler; GPL component risk |

**Recommendation:** Use pdfplumber (already present) for native text. Add `Pillow + pytesseract`
for OCR fallback. Avoid pdf2image (poppler GPL dependency). OCR results must be PENDING review only.

---

## 5. DWG File Analysis (MUST 5)

### Version identification

| Test ID | File | Size | DWG signature | AutoCAD version |
|---------|------|-----:|---------------|-----------------|
| DWG-01 | Pense_Sema.dwg | 172 KB | AC1018 | AutoCAD 2004 (R2004) |
| DWG-02 | RAB055S(41_NOKTALI).dwg | 9.4 MB | AC1018 | AutoCAD 2004 (R2004) |
| DWG-03 | RAB055S(42_NOKTALI).dwg | 9.5 MB | AC1018 | AutoCAD 2004 (R2004) |

**Note on DWG-01:** `Pense_Sema.dwg` has an identical DXF counterpart (`Pense_Sema.dxf`) already
in the source directory. DXF-03 covers this part.

### DWG support options

**ezdxf 1.4.5 (already installed):**  
ezdxf reads DXF only. Attempting to read a DWG file raises `OSError: File is not a DXF file`.
ezdxf has no DWG decoding capability.

**Open-source DWG libraries:**

| Library | License | AC1018 support | Status |
|---------|---------|---------------|--------|
| LibreDWG (GNU) | GPLv3 | YES | Active. GPLv3 is incompatible with commercial use without publishing source. |
| ODA File Converter | Proprietary freeware | YES | Free to use; not open-source; not redistributable as dependency. |
| python-dwg | Unmaintained | Partial (older) | Last commit 2016; not production-safe. |

**Conclusion on direct DWG support:**  
No commercially-safe open-source DWG library exists. LibreDWG (GPLv3) would require the entire
application to be GPL-licensed. ODA File Converter is usable as an external offline conversion tool
but cannot be bundled.

**Recommended architecture:**  
Offline conversion workflow: user converts DWG → DXF using ODA File Converter (free download from
opendesign.com) or AutoCAD "Save As DXF", then imports the DXF. This requires no code change and
no license risk. The application should guide users to this conversion step.

```
DWG_DIRECT_SUPPORT_FEASIBLE=NO
DWG_CONVERSION_REQUIRED=YES (DWG must be converted to DXF before import)
DWG_RECOMMENDED_ARCHITECTURE=
  OFFLINE_CONVERSION: user converts DWG→DXF via ODA File Converter or AutoCAD;
  then imports resulting DXF through existing pipeline.
  NO new dependency. NO license risk. DWG-01 already has DXF counterpart.
```

---

## 6. CATIA .model File Analysis (MUST 6)

### File signatures

All three .model files have identical structural characteristics:

| Test ID | File | Size | First 8 bytes (hex) | Contains |
|---------|------|-----:|---------------------|---------|
| MODEL-01 | 46795221-FONDELLO-SEDE-.model | 720 KB | f4f6f7f9f5f2f2f1 | "CATIA SOLUTIONS V4 RELEASE 2.1 FR 4.2.1" |
| MODEL-02 | 46795237-CANALINO-SUPER.model | 2.1 MB | f4f6f7f9f5f2f3f7 | Same CATIA signature |
| MODEL-03 | 46795382-OSSATURA-FIANC.model | 3.4 MB | f4f6f7f9f5f3f8f2 | Same CATIA signature |

```
MODEL_FORMAT_IDENTIFIED=YES
  CATIA V4 binary format ("CATIA SOLUTIONS V4 RELEASE 2.1 FR 4.2.1")
  Big-endian binary structure
  First 8 bytes encode model metadata (not a magic number per se)
  Readable strings include: CATIA, DRAFT, AXS1, STANDARD (geometry layer names)

MODEL_ORIGIN=Dassault Systèmes CATIA V4 (Release 2.1, format 4.2.1)
  Proprietary, undocumented, binary format.
  Used for mechanical solid models in CATIA V4 (1990s–2000s CAD system).

MODEL_SUPPORT_FEASIBLE=NO
  No open-source reader exists for CATIA V4 .model files.
  OpenCASCADE/OCC reads CATIA V5 (.CATPart/.CATProduct) but NOT CATIA V4 (.model).
  Official conversion path: use CATIA V4 or V5 to export to IGES/STEP.
  No Python library. No free converter. No documented format specification.

MODEL_RECOMMENDATION=DEFER
  Support requires either:
    (a) Access to CATIA V4 environment for export → IGES/STEP (not automated),
    (b) Dassault-licensed converter (commercial).
  If the customer has CATIA V4 → recommend exporting to IGES before submission.
  Document this as a user workflow requirement, not an application defect.
```

---

## 7. Downstream Blockers — Geometry vs. Metadata (MUST 7)

This section separates GEOMETRY PROBLEMS (parser/format issues) from ENGINEERING METADATA MISSING
(the parser worked correctly; the information was absent from the source file).

### After DEF-RSQ-002/004/005/006/007 fixes

| File | Geometry Problem | Engineering Metadata Missing |
|------|-----------------|------------------------------|
| DXF-01 | NONE — geometry correctly extracted | material, hole depth, tolerance grade |
| DXF-02 | NO_CIRCLE_GEOMETRY — 2D drawing has no circle entities (ARC not classified) | material, all downstream |
| DXF-03 | NONE — geometry correctly extracted | material, hole depth, tolerance grade |
| IGS-01 | NONE — 119 surfaces extracted correctly | material, topology (bodies/shells/edges) |
| IGS-02 | NONE — 16 surfaces extracted correctly (Hollerith fix) | material, topology |
| IGS-03 | NONE — 191 surfaces extracted correctly | material, topology |
| PDF-01/02/03 | NOT_APPLICABLE — not in CAD import pipeline | drawing content is rasterized |
| DWG-01/02/03 | NOT_APPLICABLE — unsupported format | — |
| MODEL-01/02/03 | NOT_APPLICABLE — unsupported format | — |

**Key finding:** For all DXF/IGES files, the geometry parser is now working correctly. All remaining
downstream failures are caused by ENGINEERING METADATA MISSING, not parser failures.

---

## 8. Missing Metadata Resolution Paths (MUST 8)

For each missing piece of engineering metadata, the safest resolution approach:

### Material

| Path | Feasibility | Note |
|------|-------------|------|
| A. Drawing file evidence | PARTIAL | DXF title block (MTEXT) may contain material spec; depends on drawing standard |
| B. Title block extraction | LIKELY | Turkish drawings follow TS standard; material field in title block; extraction requires MTEXT decode + field recognition |
| C. User confirmation | ALWAYS AVAILABLE | Most reliable; user must confirm material grade before process planning |
| D. Library lookup | AVAILABLE IF named | If material designation extracted (e.g. "St37-2", "1.0038"), lookup in material library |
| E. Impossible | FOR IGES/3D | IGES files carry no material; user must supply |

**Recommendation for material:** Attempt title-block extraction from DXF MTEXT; if not found, block
with status "MATERIAL_REQUIRED" and require user to confirm.

### Unit

| Path | Feasibility | Note |
|------|-------------|------|
| A. Drawing file evidence | YES for DXF | DxfHeader `units` field present; DXF-01=Millimeters, DXF-03=Millimeters |
| A. IGES | PARTIAL | IGES header unit code present; already extracted |
| C. User confirmation | FALLBACK | For files where unit is not declared |

**Recommendation:** Unit is already resolved for DXF (from DxfHeader). UNIT_UNKNOWN is NOT a current
blocker for the tested files.

### Tolerance

| Path | Feasibility | Note |
|------|-------------|------|
| A. Drawing file evidence | PARTIAL for DXF | General tolerance table in MTEXT; needs structured extraction |
| B. Title block extraction | PARTIAL | General tolerance table often in drawing notes |
| C. User confirmation | ALWAYS AVAILABLE | For specific feature tolerances |
| E. For IGES | IMPOSSIBLE from file | IGES contains no tolerance; user must supply |

### Hole depth

| Path | Feasibility | Note |
|------|-------------|------|
| A. Drawing file evidence | POSSIBLE for DXF | Hole depth may appear as DIMENSION entity or MTEXT note |
| A. For IGES | PARTIAL | 3D surface geometry implies depth, but topology required to bound it |
| C. User confirmation | ALWAYS AVAILABLE | Most reliable for manufacturing planning |
| E. For 2D DXF circles | NOT AUTOMATICALLY | 2D circle has diameter but not depth |

### Topology (IGES)

| Path | Feasibility | Note |
|------|-------------|------|
| A. Drawing file evidence | NOT AVAILABLE | IGES CATIA V5 export produces surfaces, not B-Rep |
| B. Title block extraction | NOT APPLICABLE | — |
| C. User confirmation | NOT APPLICABLE | Topology cannot be confirmed by a user |
| D. Library lookup | NOT APPLICABLE | — |
| E. Topology reconstruction | TECHNICAL WORK | Build CanonicalTopology from IGES trimmed surface entities; medium-high complexity |

**Conclusion:** Topology is the hardest gap. It requires engineering implementation (IGES B-Rep
reconstruction), not a user workflow. This is a P1 task.

---

## 9. Missing Engineering Data Resolution Workflow (MUST 9)

### Proposed workflow

```
STEP 1 — Import
  File parsed → geometry extracted → features classified (CANDIDATE)
  Result: DEGRADED or PARTIAL import status

STEP 2 — Automatic resolution attempt
  For each missing metadata item:
    Unit:      read DxfHeader.units (DXF) or IGES unit code
    Material:  scan MTEXT/title block for material designation patterns
    Tolerance: scan MTEXT/title block for general tolerance table
  Items resolved automatically are tagged:
    source=FILE_EVIDENCE  confidence=PRELIMINARY  review_state=PENDING

STEP 3 — User confirmation gate (UI)
  Present to user:
    ┌─────────────────────────────────────────────────────────┐
    │ Geometry loaded successfully.                           │
    │                                                         │
    │ Missing before manufacturing planning can proceed:      │
    │   ✓ Unit: Millimeters (from file) — confirm?           │
    │   ? Material: Not found in file — please specify       │
    │   ? Tolerance grade: Not found — please specify        │
    │   ? Hole depth: Not found — please specify             │
    │                                                         │
    │  [Confirm & Proceed]  [Skip process planning]          │
    └─────────────────────────────────────────────────────────┘
  User can:
    - Confirm auto-extracted values (promotes to CONFIRMED)
    - Correct auto-extracted values
    - Provide missing values manually
    - Skip downstream planning (keeps CANDIDATE status)

STEP 4 — Manufacturing planning
  Proceeds ONLY after user confirmation of minimum required fields.
  Auto-extracted + unconfirmed values are NEVER passed downstream.
  User input is tagged: source=USER_CONFIRMED  review_state=ACCEPTED

HARD RULE:
  No value flows to process route / machine selection / cutting data
  without user confirmation. No auto-fill. No default injection.
```

---

## 10. Recommended UI Status Indicators (MUST 10)

Replace the current binary PASS/FAIL with granular pipeline-stage readiness indicators:

```
IMPORT_STATUS
  IMPORT_SUCCESS          → file parsed, geometry extracted
  IMPORT_DEGRADED         → partial parse; some entities skipped (non-fatal)
  IMPORT_UNSUPPORTED      → format not registered; no data extracted

GEOMETRY_STATUS
  GEOMETRY_READY          → geometry fully extracted; bounding box present
  GEOMETRY_PARTIAL        → some entities skipped; most geometry available
  GEOMETRY_UNAVAILABLE    → 2D drawing (expected) or parse failure

DRAWING_INTELLIGENCE_STATUS
  DRAWING_ANNOTATIONS_ACTIVE   → MTEXT decoded; drawing parser extracting values
  DRAWING_ANNOTATIONS_PENDING  → title block not yet scanned
  DRAWING_INTELLIGENCE_NA      → 3D IGES (expected; no annotation layer)

FEATURE_STATUS
  FEATURE_CANDIDATE           → features identified; type/depth/confirmation pending
  FEATURE_CONFIRMED           → features confirmed by topology and user
  NO_MANUFACTURING_FEATURE    → no recognizable feature geometry

MANUFACTURING_PLANNING_STATUS
  PLANNING_READY              → all required inputs confirmed; planning can proceed
  PLANNING_BLOCKED_MATERIAL   → material required before planning
  PLANNING_BLOCKED_TOLERANCE  → tolerance required before planning
  PLANNING_BLOCKED_TOPOLOGY   → 3D topology required for feature confirmation
  PLANNING_BLOCKED_DEPTH      → hole depth required for operation planning
  PLANNING_CANDIDATE          → geometry-only plan available; not manufacturing-ready
```

### UI badge mapping

| File state | Recommended badge |
|------------|------------------|
| DXF with circles, no material | `GEOMETRY_READY · FEATURE_CANDIDATE · PLANNING_BLOCKED_MATERIAL` |
| DXF with no circles | `GEOMETRY_READY · NO_MANUFACTURING_FEATURE · PLANNING_BLOCKED` |
| IGES with CANDIDATE surfaces | `GEOMETRY_READY · FEATURE_CANDIDATE · PLANNING_BLOCKED_TOPOLOGY` |
| PDF raster drawing | `IMPORT_SUCCESS · GEOMETRY_UNAVAILABLE · OCR_AVAILABLE` |
| DWG (unsupported) | `IMPORT_UNSUPPORTED · CONVERT_TO_DXF_REQUIRED` |
| CATIA .model | `IMPORT_UNSUPPORTED · EXPORT_TO_IGES_REQUIRED` |

---

## 11. Re-Evaluation of REAL_SAMPLE_PASS_COUNT=0 (MUST 11)

### Is the current score too strict?

YES. The current scoring uses a single binary pass/fail for the full end-to-end pipeline. This
masks significant capability that exists at earlier pipeline stages.

### Proposed granular readiness scores (post-fix state)

| Score | DXF-01 | DXF-02 | DXF-03 | IGS-01 | IGS-02 | IGS-03 | PDF×3 | DWG×3 | .model×3 |
|-------|:------:|:------:|:------:|:------:|:------:|:------:|:-----:|:-----:|:--------:|
| IMPORT_SUCCESS | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓* | ✓* | ✓* |
| GEOMETRY_SUCCESS | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — | — | — |
| DRAWING_INTELLIGENCE_SUCCESS | ~ | ~ | ~ | NA | NA | NA | — | — | — |
| FEATURE_SUCCESS (CANDIDATE) | ✓ | — | ✓ | ✓ | ✓ | ✓ | — | — | — |
| MANUFACTURING_PLANNING_READY | — | — | — | — | — | — | — | — | — |
| FULL_END_TO_END_READY | — | — | — | — | — | — | — | — | — |

*IMPORT_SUCCESS for UNSUPPORTED = graceful UNSUPPORTED response  
~ DRAWING_INTELLIGENCE: annotation pipeline active but not yet integrated into document model  

### Proposed revised metrics

```
IMPORT_SUCCESS_COUNT      = 15/15 (all files import without crash)
GEOMETRY_SUCCESS_COUNT    = 6/15  (DXF×3 + IGES×3)
FEATURE_SUCCESS_COUNT     = 5/15  (DXF-01 + DXF-03 + IGS-01 + IGS-02 + IGS-03)
MANUFACTURING_PLANNING_READY = 0/15
FULL_END_TO_END_READY     = 0/15
```

**Recommendation:** Report IMPORT_SUCCESS and GEOMETRY_SUCCESS as positive capability metrics.
Reserve FULL_END_TO_END_READY for files where material, tolerance, and topology are confirmed.

---

## 12. Architecture Recommendations

### IGES topology reconstruction

IGES files contain:
- `IgesCanonicalSurface` (bounded or trimmed) — surface geometry
- `IgesCurveOnParametricSurface` — boundary curves on surfaces
- `IgesTransformationMatrix` — reference frames

These are sufficient to reconstruct a CanonicalTopology for simple parts. For AGV03773 (96 planar,
23 freeform surfaces), topology reconstruction is feasible. The boundary curves already exist in
the entity_refs.

**Approach:**
1. Identify surface adjacency by shared boundary curves.
2. Group co-planar surfaces → potential flat faces.
3. Group cylindrical surfaces with shared axis → potential bore/hole.
4. Build CanonicalTopology from these groups.
5. Run existing feature recognizer (TOPOLOGY path) on the reconstructed topology.

### DXF annotation → feature linking

The drawing parser (MTEXT decoding) and the CAD feature recognizer are currently independent.
Engineering dimensions extracted from MTEXT should be associated with nearby geometric features
(circles, arcs).

**Approach:**
1. After MTEXT token extraction, extract bounding-box positions of detections.
2. For each CANDIDATE hole (circle entity), search MTEXT detections within proximity.
3. Associate diameter value with circle, depth with DIMENSION near leader line.
4. Update feature with PRELIMINARY_CONFIRMED status and source=FILE_EVIDENCE.

### DXF ARC → CANDIDATE feature

DXF-02 fails at the feature stage because it has no circles. The file has 64 ARC entities. Some of
these may represent partial circles (slot ends, pocket corners). Extending the 2D feature recognizer
to group connected ARCs with matching radii as potential circular pockets would recover DXF-02.

---

## 13. Priority Plan (MUST 13)

Prioritized by: user value · feasibility · license safety · engineering safety · coverage gain.

### P0 — Immediate value, low risk

| Task | Rationale | Coverage gain |
|------|-----------|---------------|
| P0-1: User confirmation UI for missing material/tolerance | Unblocks all DXF-01, DXF-03, IGS-01/02/03 for process planning | 5 files reach MANUFACTURING_PLANNING_READY |
| P0-2: Title block material extraction from DXF MTEXT | Most DXF drawings have material in title block; Turkish TS standard pattern | Reduces user burden for DXF files |
| P0-3: Granular pipeline status badges | Replaces binary PASS/FAIL; communicates correct readiness | All 6 supported-format files display meaningful state |

### P1 — High value, moderate engineering effort ✓ COMPLETED 2026-11-14

| Task | Rationale | Coverage gain | P1 Status |
|------|-----------|---------------|-----------|
| P1-1: IGES topology reconstruction (simple cases) | Surface grouping (planar/cylindrical/freeform); closed_body=NO for surface-only | IGS-01/02/03: TOPOLOGY_PARTIAL (surface groups); no fabricated B-Rep | **DONE** — `iges_topology_reconstruction.py` |
| P1-2: DXF annotation → feature association (proximity matching) | Spatial linking of DIMENSION/MTEXT/TEXT/ATTRIB to circle/arc features | DXF-01, DXF-03: annotation links AVAILABLE; DXF-02: links to arc candidates when confirmed | **DONE** — `dxf_annotation_linker.py` |
| P1-3: Hybrid PDF extraction (native text → vector check → OCR fallback) | 3-stage pipeline: native first, vector check, OCR only for raster regions | PDF-01/02/03: drawing intelligence PARTIAL (native text from title block; OCR available for raster area) | **DONE** — `hybrid_pdf_drawing.py` |
| P1-4: DXF ARC group → CIRCULAR_BOUNDARY_CANDIDATE (partial circle detection) | Guarded ARC grouping (≥2 arcs, compatible center+radius, ≥60° coverage) | DXF-02: 0→PT feature stage (ARC candidates); single-ARC false-positive guard active | **DONE** — `cad_feature_recognition.py` (recognize_circular_boundaries) |

**DWG and `.model` remain UNSUPPORTED / DEFERRED. NOT addressed in P1.**

### P2 — Medium value, notable complexity or external dependency

| Task | Rationale | Coverage gain |
|------|-----------|---------------|
| P2-1: DWG → DXF conversion guidance in UI | DWG-01 already has DXF counterpart; for DWG-02/03 user must convert offline | Guides users; no code needed |
| P2-2: PDF vector drawing support (pure-vector PDFs from CAD) | Future files exported from CAD as vector PDF could be parsed directly | 0 current files; future coverage |
| P2-3: IGES GD&T annotation support | IGES has annotation entity types (Type 212/214/228); currently ignored | Tolerance extraction for IGES files |
| P2-4: DEF-RSQ-003 fix (PDF fit false-positive filter) | Blocklist for revision codes P00/A00/Bxx | Reduces annotation noise |
| P2-5: DEF-RSQ-001 fix (empty format string in error message) | Minor UX improvement | — |

### DEFER — Low current coverage gain or licensing concern

| Task | Rationale |
|------|-----------|
| DWG direct read | No open-source GPL-free DWG library; legal and technical risk; conversion workflow sufficient |
| CATIA .model support | Proprietary format; no open-source reader; requires CATIA V4 environment for conversion |
| Full IGES topology for complex freeform | 127 FREEFORM surfaces in IGS-03 have no deterministic machining operation; topology alone is insufficient |
| OCR as primary PDF path | OCR introduces precision risk; must remain fallback only |

---

## 14. Summary Statistics

### Post-fix blocker root causes

| Root Blocker | Files |
|-------------|------:|
| UNSUPPORTED_FORMAT | 9 (PDF×3 + DWG×3 + .model×3) |
| MISSING_TOPOLOGY | 3 (IGS-01, IGS-02, IGS-03) |
| MISSING_MATERIAL | 2 (DXF-01, DXF-03) → also affects IGES after topology resolved |
| NO_MANUFACTURING_FEATURE | 1 (DXF-02 — no circle geometry) |

**Dominant solvable blocker:** MISSING_MATERIAL (5 of 6 supported-format files would reach
manufacturing planning if material is supplied by user).

### Format-level support summary

| Format | Current | P0 improvement | P1 improvement | P2 improvement |
|--------|---------|---------------|---------------|---------------|
| DXF (3 files) | PARTIAL | Planning-ready if material supplied | Depth-aware features | — |
| IGES (3 files) | PARTIAL | Planning-candidate | Topology → confirmed features | GD&T annotations |
| PDF (3 files) | UNSUPPORTED | — | OCR path | Vector PDF support |
| DWG (3 files) | UNSUPPORTED | Conversion guidance | — | — |
| .model (3 files) | UNSUPPORTED | — | — | DEFER |

---

*End of gap analysis. Production code unchanged. Source files unchanged.*

```
PRODUCTION_FILES_CHANGED=0
SOURCE_FILES_CHANGED=NO
SOURCE_FILES_COMMITTED=NO
```
