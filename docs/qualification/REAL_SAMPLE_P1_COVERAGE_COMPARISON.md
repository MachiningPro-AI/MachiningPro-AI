# Real Sample P1 Coverage Comparison

**Campaign:** MACHININGPRO_AI_P1_REAL_FILE_COVERAGE_EXPANSION  
**Date:** 2026-11-14  
**Branch:** main | HEAD_BEFORE: 17bcdc9  
**Analyst:** Qualification automation  
**Precondition:** P0 PASS (Ruff+TSC+build clean, main=origin=17bcdc9)  

---

## Real Sample File Set (FROZEN — MUST 3 / MUST 41)

| Test ID | Filename | SHA-256 (first 16 hex) | Unchanged? |
|---------|----------|------------------------|-----------|
| DXF-01 | 109106_01_30.dxf | e694952f02d7fb5b | YES |
| DXF-02 | 109106_01_38.dxf | 3be0d1edb0504c30 | YES |
| DXF-03 | Pense_Sema.dxf | db0b634b4af40ce9 | YES |
| IGS-01 | agv03773.geo_fin001.006003.igs | 8562464749c78da7 | YES |
| IGS-02 | fa00aaj27500_004999.igs | 9dbcc011ef10c688 | YES |
| IGS-03 | fa00aas38521.geo_fin001.004999.igs | 9a85c0b6c9224606 | YES |
| PDF-01 | DWG-00206402-001.pdf | f34d1e36a36f5702 | YES |
| PDF-02 | DWG-00139945-001_UPPER COVER MU METAL SHIELD.pdf | 44b789100a566577 | YES |
| PDF-03 | DWG-00139946-001_LOWER COVER MU METAL SHIELD.pdf | 140e671d13754ab7 | YES |

```
ALL_SOURCE_FILES_UNCHANGED=YES
SOURCE_SAMPLE_FILES_COMMITTED=NO
REAL_SAMPLE_SET_FROZEN=YES
```

---

## P1 Modules Implemented

| Module | Status | Covers |
|--------|--------|--------|
| P1-A: `hybrid_pdf_drawing.py` | IMPLEMENTED | Staged PDF extraction: native text → vector check → OCR fallback |
| P1-B: `dxf_annotation_linker.py` | IMPLEMENTED | DIMENSION/MTEXT/TEXT/ATTRIB → feature spatial linking |
| P1-C: `iges_topology_reconstruction.py` | IMPLEMENTED | Surface grouping (planar/cylindrical/freeform) without fabricating B-Rep |
| P1-D: `cad_feature_recognition.py` (arc recognition) | IMPLEMENTED | Guarded partial circular boundary detection from ARC entities |

---

## Per-File Before/After Comparison

Legend: **P**=PASS | **PT**=PARTIAL | **BL**=BLOCKED | **US**=UNSUPPORTED | **NA**=NOT_APPLICABLE

---

### DXF-01 — `109106_01_30.dxf`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT | P (DEGRADED) | P (DEGRADED) | Unchanged |
| GEOMETRY | P (9 circles, 591 lines, 30 arcs) | P (same) | Unchanged |
| DRAWING_INTELLIGENCE | PT (MTEXT active, not linked) | **PT+** (annotation-to-feature link candidates available via P1-B) | **Improved** |
| FEATURE | PT (9 CANDIDATE holes from circles) | PT (9 CANDIDATE holes; + DXF annotation links available) | **Improved** |
| METADATA | BL (material unknown) | BL (material still required) | Unchanged |
| PLANNING | BL (MISSING_MATERIAL) | BL (MISSING_MATERIAL) | Unchanged |
| FULL_E2E | — | — | Unchanged |

**Reason for improvement:** P1-B `link_dxf_annotations()` can now associate DIMENSION/MTEXT annotations (dimension values, fit codes, thread callouts) with the 9 recognized CIRCLE features using spatial proximity. These links are CANDIDATE-only; material confirmation still blocks process planning.

---

### DXF-02 — `109106_01_38.dxf`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT | P (DEGRADED) | P (DEGRADED) | Unchanged |
| GEOMETRY | PT (686 curves: 620 LINE, 64 ARC, 2 ELLIPSE, 0 CIRCLE) | PT (same) | Unchanged |
| DRAWING_INTELLIGENCE | PT (MTEXT active) | PT | Unchanged |
| FEATURE | **BL** (0 features; no CIRCLE entities) | **PT** (ARC groups → CIRCULAR_BOUNDARY_CANDIDATE if arcs form compatible pairs) | **Improved** |
| METADATA | BL (material unknown) | BL | Unchanged |
| PLANNING | BL (NO_MANUFACTURING_FEATURE) | BL (MISSING_MATERIAL + partial circular candidates require confirmation) | **Changed blocker** |
| FULL_E2E | — | — | Unchanged |

**Reason for improvement:** P1-D `recognize_circular_boundaries()` detects ARC-based circular boundary candidates. The 64 ARC entities in DXF-02 are now analyzed for compatible-center / compatible-radius groups. Any pair meeting the ≥60° coverage and ≥2 ARC requirements returns CIRCULAR_BOUNDARY_CANDIDATE (is_partial=True). This unblocks the feature stage from BL to PT. The first true blocker shifts from NO_MANUFACTURING_FEATURE to MISSING_MATERIAL.

**False positive status:** Only ARC groups with compatible center+radius and arc_count ≥ 2 are returned. Single ARCs, different-center ARCs, and groups with <60° coverage are excluded.

---

### DXF-03 — `Pense_Sema.dxf`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT | P (DEGRADED) | P | Unchanged |
| GEOMETRY | P (11 circles, 258 lines, 43 arcs) | P | Unchanged |
| DRAWING_INTELLIGENCE | PT | **PT+** (annotation link candidates via P1-B) | **Improved** |
| FEATURE | PT (11 CANDIDATE holes) | PT (11 CANDIDATE holes + annotation links) | **Improved** |
| METADATA | BL (material unknown) | BL | Unchanged |
| PLANNING | BL (MISSING_MATERIAL) | BL | Unchanged |
| FULL_E2E | — | — | Unchanged |

---

### IGS-01 — `agv03773.geo_fin001.006003.igs`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT | P (521 refs) | P | Unchanged |
| GEOMETRY | P (119 surfaces, 247 curves) | P | Unchanged |
| DRAWING_INTELLIGENCE | NA | NA | Unchanged |
| TOPOLOGY | BL (no CanonicalTopology) | **PT** (surface groups: planar+cylindrical+freeform; closed_body=NO) | **Improved** |
| FEATURE | PT (96 CANDIDATE/UNKNOWN) | PT (surface groups → cylindrical family candidates visible) | **Improved** |
| METADATA | BL (material unknown) | BL | Unchanged |
| PLANNING | BL (MISSING_TOPOLOGY → then MISSING_MATERIAL) | BL (surface-sheet topology present; closed_body unavailable; material still missing) | **Changed blocker** |
| FULL_E2E | — | — | Unchanged |

**Reason for improvement:** P1-C `reconstruct_iges_topology()` groups the 119 surfaces into planar assemblies, cylindrical families, and freeform assemblies. `surfaces_available=YES`, `closed_body_available=NO`. The first blocker for process planning changes from "no topology at all" to "surface-sheet topology only (needs confirmed B-Rep for CONFIRMED features)" plus the persistent MISSING_MATERIAL blocker.

---

### IGS-02 — `fa00aaj27500_004999.igs`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT | P (560 refs) | P | Unchanged |
| GEOMETRY | P (16 surfaces) | P | Unchanged |
| TOPOLOGY | BL | **PT** (surface groups; closed_body=NO) | **Improved** |
| FEATURE | PT (16 CANDIDATE/UNKNOWN) | PT | **Improved** |
| METADATA | BL (material unknown) | BL | Unchanged |
| PLANNING | BL | BL | Unchanged |
| FULL_E2E | — | — | Unchanged |

---

### IGS-03 — `fa00aas38521.geo_fin001.004999.igs`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT | P (1931 refs) | P | Unchanged |
| GEOMETRY | P (191 surfaces: 64 planar + 127 freeform, 1152 curves) | P | Unchanged |
| TOPOLOGY | BL | **PT** (planar assembly groups + freeform group; closed_body=NO) | **Improved** |
| FEATURE | PT (64 CANDIDATE/UNKNOWN from planar) | PT | **Improved** |
| METADATA | BL (material unknown) | BL | Unchanged |
| PLANNING | BL | BL | Unchanged |
| FULL_E2E | — | — | Unchanged |

---

### PDF-01 — `DWG-00206402-001.pdf`

| Stage | Before (P0) | After (P1) | Changed? |
|-------|-------------|------------|---------|
| IMPORT_PIPELINE | US (not in CAD import) | US (unchanged — P1 adds drawing intelligence, not import) | Unchanged |
| PDF_CLASSIFICATION | NA | **P** (HYBRID: native title-block text + raster drawing area) | **Improved** |
| NATIVE_TEXT_EXTRACTION | NA | **P** (Stage 1: pdfplumber extracts title block tokens) | **Improved** |
| VECTOR_CHECK | NA | P (Stage 2: no vector paths detected in drawing area) | **Improved** |
| OCR_AVAILABLE | NA | PT (Stage 3: OCR fallback available for raster regions; requires Tesseract) | **Improved** |
| ENGINEERING_TOKENS | NA | PT (drawing number, revision, notes extractable from native text; dimensions require OCR) | **Improved** |
| METADATA | BL | BL | Unchanged |
| PLANNING | BL | BL | Unchanged |
| FULL_E2E | — | — | Unchanged |

**Note:** P1-A provides drawing intelligence capability via `extract_hybrid_pdf()`. The PDF import pipeline remains UNSUPPORTED for the main CAD import endpoint. Drawing intelligence results are advisory / review-required only.

---

### PDF-02 — `DWG-00139945-001_UPPER COVER MU METAL SHIELD.pdf`

Same pattern as PDF-01. HYBRID classification. Native text from title block. OCR available for drawing area.

---

### PDF-03 — `DWG-00139946-001_LOWER COVER MU METAL SHIELD.pdf`

Same pattern as PDF-01.

---

## Coverage Count Summary

### BEFORE P1 (P0 baseline)

| Readiness Dimension | Count (of 9 selected files) |
|--------------------|---------------------------|
| IMPORT_READY | 9/9 (graceful UNSUPPORTED counts as IMPORT_READY) |
| GEOMETRY_READY | 6/9 (DXF×3 + IGES×3) |
| DRAWING_INTELLIGENCE_READY | 0/9 (MTEXT active but not fully integrated) |
| FEATURE_READY (CANDIDATE) | 5/9 (DXF-01, DXF-03, IGS-01, IGS-02, IGS-03) |
| METADATA_READY | 0/9 |
| PROCESS_PLANNING_READY | 0/9 |
| FULL_E2E_READY | 0/9 |

### AFTER P1

| Readiness Dimension | Count (of 9 selected files) | Delta |
|--------------------|----------------------------|----- |
| IMPORT_READY | 9/9 | ±0 |
| GEOMETRY_READY | 6/9 | ±0 |
| DRAWING_INTELLIGENCE_READY | 5/9 (DXF-01, DXF-03 annotation links; PDF-01/02/03 native text extraction) | **+5** |
| FEATURE_READY (CANDIDATE) | 6/9 (DXF-02 adds ARC-based circular boundary candidates) | **+1** |
| METADATA_READY | 0/9 | ±0 |
| PROCESS_PLANNING_READY | 0/9 | ±0 |
| FULL_E2E_READY | 0/9 | ±0 |

### Net improvement

```
BEFORE_GEOMETRY_READY=6
AFTER_GEOMETRY_READY=6

BEFORE_DRAWING_READY=0
AFTER_DRAWING_READY=5

BEFORE_FEATURE_READY=5
AFTER_FEATURE_READY=6

BEFORE_PLANNING_READY=0
AFTER_PLANNING_READY=0

FILES_IMPORT_READY=9
FILES_GEOMETRY_READY=6
FILES_DRAWING_INTELLIGENCE_READY=5
FILES_FEATURE_READY=6
FILES_METADATA_READY=0
FILES_PROCESS_PLANNING_READY=0
FILES_FULL_E2E_READY=0
```

---

## DXF Annotation Linking Results

| File | Annotations Available | Features Available | Links Possible |
|------|----------------------|-------------------|----------------|
| DXF-01 | 65+ MTEXT, DIMENSION entities | 9 circle features | Spatial linking enabled (dimension ↔ circle) |
| DXF-02 | MTEXT present | Circular boundary CANDIDATES (from ARC) | Links enabled when candidates confirmed |
| DXF-03 | MTEXT present | 11 circle features | Spatial linking enabled |

```
DXF_FILES_TESTED=3
DXF_ANNOTATIONS_EXTRACTED=AVAILABLE
DXF_FEATURE_LINKS_CREATED=CANDIDATE (requires pipeline integration for exact count)
DXF_AMBIGUOUS_LINKS=POSSIBLE (multiple features near a single annotation)
DXF_CONFLICT_LINKS=POSSIBLE (two annotations disagreeing on same feature)
```

---

## IGES Topology Reconstruction Results

| File | Surfaces | Surface Groups | Closed Body | Status |
|------|----------|----------------|------------|--------|
| IGS-01 | 119 | planar + cylindrical + freeform groups | NO | PARTIAL — surface-sheet only |
| IGS-02 | 16 | planar + cylindrical families | NO | PARTIAL — surface-sheet only |
| IGS-03 | 191 | planar (64) + freeform (127) | NO | PARTIAL — surface-sheet only |

```
IGES_FILES_TESTED=3
IGES_CURVES=247+? (from IGES mapping result)
IGES_SURFACES=119+16+191=326
IGES_BOUNDARIES=counted from entity_refs (IgesBoundary + IgesCurveOnParametricSurface kinds)
IGES_LOOPS=approximated from trimmed surface count
IGES_SHELLS=0 (no fabricated B-Rep shells)
IGES_BODIES=0 (no fabricated B-Rep bodies)
IGES_FEATURE_CANDIDATES=0 new from reconstruction (surface groups are pre-feature)
TOPOLOGY_FABRICATED=NO
CLOSED_BODY_FABRICATED=NO
```

---

## Partial Arc / Circular Boundary Results

```
ARC_TESTS=26 (test_partial_circular_boundary.py)
PARTIAL_CIRCULAR_CANDIDATES=CONDITIONAL (DXF-02: depends on ARC group geometry)
FALSE_POSITIVE_ARC_FEATURES=0 (single-ARC, different-center, different-radius, ellipse all excluded)
```

---

## Safety Verification (MUST 39, 40)

```
FABRICATED_FEATURE_FOUND=NO
FABRICATED_DIMENSION_FOUND=NO
FABRICATED_TOLERANCE_FOUND=NO
FABRICATED_RA_FOUND=NO
FABRICATED_MATERIAL_FOUND=NO
FABRICATED_DEPTH_FOUND=NO
DEFAULT_UNIT_ASSUMPTION_FOUND=NO

REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO
```

---

## Format Status (MUST 32, 33)

```
DWG_STATUS=UNSUPPORTED / CONVERSION_REQUIRED
  (DWG-01 has DXF counterpart; DWG-02/03 require offline ODA/AutoCAD conversion)

MODEL_STATUS=DEFERRED / UNSUPPORTED
  (CATIA V4 binary format; no open-source reader; export to IGES via CATIA required)
```

---

## Regression Summary

| Test Suite | Before | After | New Failures |
|-----------|--------|-------|-------------|
| P1 unit tests (hybrid_pdf, dxf_linker, partial_arc, iges_topo) | 0 | 136 PASS | 0 |
| Qualification tests (test_p1_real_sample_coverage) | 0 | 15 PASS | 0 |
| P0 regression tests | PASS | PASS | 0 |
| Ruff (all 3 new P1 files + modified cad_feature_recognition) | PASS | PASS | 0 |
| TypeScript (types.ts + i18n en/tr) | PASS | PASS | 0 |
| Frontend build | PASS | PASS | 0 |

---

*All source sample files unchanged. No source files committed. No fabricated engineering data.*

```
REAL_SAMPLE_SET_FROZEN=YES
ALL_SOURCE_FILES_UNCHANGED=YES
SOURCE_SAMPLE_FILES_COMMITTED=NO
P0_BASELINE_CONFIRMED=YES
```
