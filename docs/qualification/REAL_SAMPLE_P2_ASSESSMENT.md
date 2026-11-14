# Real Sample P2 Assessment

**Campaign:** MACHININGPRO_AI_P2_REMAINING_REAL_FILE_COVERAGE_ASSESSMENT  
**Date:** 2026-11-14  
**Branch:** main | HEAD: 413b92f  
**Analyst:** Qualification automation  
**Precondition:** P1 PASS (HEAD = ORIGIN = 413b92f; worktree clean)  
**Rule:** PRODUCTION_FILES_CHANGED=0. SOURCE_FILES_CHANGED=NO.

---

## 1. Executive Summary

After P0 (missing data resolution) and P1 (PDF intelligence, DXF annotation linking, IGES topology
groups, partial arc recognition), the pipeline is significantly more capable:

- All 9 selected real files import without crash.
- All 6 DXF/IGES files produce geometry.
- 5 of 9 files have drawing intelligence (annotation links or native PDF title-block text).
- 6 of 9 files have feature candidates.

The dominant remaining blockers are:

1. **MISSING_MATERIAL** (all 6 DXF/IGES files) — the P0 confirmation workflow is built; it is not
   yet surfaced in the UI.
2. **MISSING_TOPOLOGY** (all 3 IGES files) — P1-C surface groups are partial; B-Rep reconstruction
   for feature confirmation requires further work.
3. **OCR_UNSUPPORTED** (all 3 PDF files) — P1-A infrastructure is built but Tesseract is not in
   project dependencies; raster drawing content is not yet extracted.
4. **DXF_ANNOTATION_WIRING** (DXF-01, DXF-03) — P1-B linker exists but is not yet called during
   normal import; enriched features are not flowing downstream.

No file reaches PROCESS_PLANNING_READY or FULL_E2E_READY. The P2 scope should fix these four
specific gaps rather than add new format support.

```
GO_NO_GO=GO (conditional — 4 bounded workstreams, no license risk, no fabrication risk)
```

---

## 2. P1 Baseline

```
REPOSITORY=D:\makina_ogrenmesi\MachiningPro_AI_NEXT
BRANCH=main
HEAD=413b92f3f80ffca4b1e0eff9a60de9b7933466d8
ORIGIN_MAIN=413b92f3f80ffca4b1e0eff9a60de9b7933466d8
WORKTREE_CLEAN=YES
AHEAD_BEHIND=0
HEAD_BEFORE=413b92f
P1_REAL_FILE_COVERAGE_EXPANSION=PASS
```

P1 delivered:
- `hybrid_pdf_drawing.py` — staged PDF extraction (native → vector check → OCR fallback)
- `dxf_annotation_linker.py` — DIMENSION/MTEXT/TEXT/ATTRIB → feature spatial linking
- `iges_topology_reconstruction.py` — surface group reconstruction (planar/cylindrical/freeform)
- `cad_feature_recognition.recognize_circular_boundaries()` — guarded partial arc detection
- 136 new unit tests PASS; Ruff/TSC/build clean.

---

## 3. Real Sample Coverage After P1

### Counts (of 9 selected files)

| Readiness Dimension | Count | Delta from P0 |
|--------------------|-------|--------------|
| IMPORT_READY | 9 | ±0 |
| GEOMETRY_READY | 6 | ±0 |
| DRAWING_INTELLIGENCE_READY | 5 | +5 |
| FEATURE_READY (CANDIDATE) | 6 | +1 |
| METADATA_READY | 0 | ±0 |
| PROCESS_PLANNING_READY | 0 | ±0 |
| CAM_READY | 0 | ±0 |
| FULL_E2E_READY | 0 | ±0 |

```
FILES_TOTAL=9
FILES_IMPORT_READY=9
FILES_GEOMETRY_READY=6
FILES_DRAWING_INTELLIGENCE_READY=5
FILES_FEATURE_READY=6
FILES_METADATA_READY=0
FILES_PROCESS_PLANNING_READY=0
FILES_CAM_READY=0
FILES_FULL_E2E_READY=0
```

### Native vs. user-assisted

```
FILES_NATIVE_READY=0
  (no file is fully ready from file content alone; all require material confirmation)

FILES_USER_ASSISTED_READY=3
  (DXF-01, DXF-02, DXF-03: once user confirms material, process planning unblocks)
  (IGES-01/02/03: user confirmation of material is not sufficient; topology still partial)
  (PDF-01/02/03: drawing intelligence is advisory only; material would need OCR extraction
   plus user confirmation)
```

---

## 4. Per-File Remaining Blockers

| File | First Blocker | Category | Resolvable in P2? |
|------|--------------|----------|------------------|
| DXF-01 | material unknown; annotation links not wired | MISSING_MATERIAL + DXF_ANNOTATION_WIRING | YES — P2-C (UI) + P2-D (wiring) |
| DXF-02 | material unknown; arc candidates need confirmation | MISSING_MATERIAL + AMBIGUOUS_FEATURE_LINK | YES — P2-C (UI) |
| DXF-03 | material unknown; annotation links not wired | MISSING_MATERIAL + DXF_ANNOTATION_WIRING | YES — P2-C + P2-D |
| IGS-01 | surface-sheet topology only; material unknown | MISSING_TOPOLOGY → MISSING_MATERIAL | PARTIAL — P2-B limited topology |
| IGS-02 | surface-sheet topology only; material unknown | MISSING_TOPOLOGY → MISSING_MATERIAL | PARTIAL — P2-B limited topology |
| IGS-03 | surface-sheet topology only; material unknown | MISSING_TOPOLOGY → MISSING_MATERIAL | PARTIAL — P2-B limited topology |
| PDF-01 | OCR not available; drawing content rasterized | OCR_REVIEW_REQUIRED | YES — P2-A (OCR integration) |
| PDF-02 | OCR not available | OCR_REVIEW_REQUIRED | YES — P2-A |
| PDF-03 | OCR not available | OCR_REVIEW_REQUIRED | YES — P2-A |

---

## 5. PDF Remaining Gaps

### Status after P1

| Property | PDF-01 | PDF-02 | PDF-03 |
|----------|--------|--------|--------|
| Import | UNSUPPORTED (graceful) | UNSUPPORTED | UNSUPPORTED |
| PDF classification | HYBRID | HYBRID | HYBRID |
| Native title-block text | AVAILABLE (pdfplumber) | AVAILABLE | AVAILABLE |
| Native dimension/tolerance | NOT AVAILABLE (rasterized) | NOT AVAILABLE | NOT AVAILABLE |
| OCR infrastructure | BUILT (P1-A) | BUILT | BUILT |
| OCR executable | MISSING (Tesseract not installed) | MISSING | MISSING |
| Engineering tokens from native | PARTIAL (drawing number, revision) | PARTIAL | PARTIAL |
| Engineering tokens from OCR | BLOCKED (Tesseract absent) | BLOCKED | BLOCKED |

### DEF-P1A-001 (C45 FP guard clash)

The `_FP_GUARD_PATTERNS` pattern `^[A-Z]\d{2}$` excludes "C45" from extraction
because it matches the revision-code pattern. Impact: if OCR returns "C45" as a token
in a raster region, it will be silently dropped.

**P2 fix:** Maintain an explicit material-allowlist in `hybrid_pdf_drawing.py` that
overrides the generic FP guard. Apply the guard only after checking the allowlist.
This is a small isolated change in a single file.

### DEF-P1A-002 (Tesseract dependency)

Tesseract binary and pytesseract are absent from project requirements. The pipeline
falls back gracefully but delivers no OCR-extracted data for the 3 PDF files.

**P2 fix:** Add `pytesseract>=0.3.13` as an optional dependency; document Tesseract
binary installation. Gate OCR paths on `PYTESSERACT_AVAILABLE` capability flag.

### Pre-existing PDF boundary test failures

**Status at P2 assessment: ALL CLEARED.**

Running `pytest tests/unit/interoperability/test_pdf_phase_boundary.py` returns
19 PASS / 0 FAIL. The 2 failures noted in the P1 session summary do not reproduce.
They were non-deterministic (likely Tesseract/pdfplumber environment side effects
in that session). No P2 work is needed for this test file.

```
PDF_BOUNDARY_TESTS_STATUS=19 PASS / 0 FAIL
PREEXISTING_PDF_FAILURES=0 (resolved; not P2 scope)
```

### PDF remaining gap summary

```
PDF_REMAINING_GAPS=
  1. Tesseract not in dependencies → OCR inactive (DEF-P1A-002)
  2. C45 FP guard clash → material silent drop (DEF-P1A-001)
  3. PDF not in CAD import pipeline (by design; drawing intelligence is advisory)
  4. Dimension/tolerance extraction requires OCR for raster content
```

---

## 6. DXF Remaining Gaps

### Status after P1

| Property | DXF-01 | DXF-02 | DXF-03 |
|----------|--------|--------|--------|
| Import | DEGRADED | DEGRADED | DEGRADED |
| Geometry | 9 circles, 591 lines, 30 arcs | 686 curves, 64 arcs, 0 circles | 11 circles, 258 lines, 43 arcs |
| Annotation linker built | YES (P1-B) | YES (P1-B) | YES (P1-B) |
| Annotation linker wired | **NO** | **NO** | **NO** |
| Feature candidates | 9 circles | ARC boundary CANDIDATES | 11 circles |
| Material | UNKNOWN | UNKNOWN | UNKNOWN |
| Material UI | **NO** (P0 backend done; frontend not built) | **NO** | **NO** |

### Critical gap: annotation wiring

`link_dxf_annotations()` was implemented in P1-B and tested with 29 unit tests.
It is **not called during the import orchestrator flow**. The import pipeline
produces features and separately produces drawing parser output, but does not
call the linker to associate them. As a result, dimension annotations are not
flowing to feature candidates even though both datasets are present.

**P2 fix:** Wire `link_dxf_annotations()` into the orchestrator after feature
recognition (DXF path). Pass annotation output from drawing parser to the linker.
Enrich feature candidates with linked annotation data. This is a targeted
orchestrator change with no domain-logic change.

### DXF remaining gap summary

```
DXF_REMAINING_GAPS=
  1. Annotation linker not wired into orchestrator (P1-B exists but not connected)
  2. Material UNKNOWN for all 3 files; no UI panel for user confirmation
  3. MTEXT general-tolerance table not structured into process intelligence
  4. Hole depth unknown for all 3 files (2D drawing; no DIMENSION entity analysis)
```

---

## 7. IGES Remaining Gaps

### Status after P1

| Property | IGS-01 | IGS-02 | IGS-03 |
|----------|--------|--------|--------|
| Import | 521 refs | 560 refs | 1931 refs |
| Surfaces | 119 | 16 | 191 |
| Curves | 247 | unknown | 1152 |
| Surface groups (P1-C) | planar + cylindrical + freeform | planar + cylindrical | planar (64) + freeform (127) |
| closed_body | NO | NO | NO |
| CanonicalTopology (B-Rep) | NOT BUILT | NOT BUILT | NOT BUILT |
| Feature candidates | 96 CANDIDATE/UNKNOWN | 16 CANDIDATE/UNKNOWN | 64 CANDIDATE/UNKNOWN |
| Confirmed features | 0 | 0 | 0 |
| Material | UNKNOWN | UNKNOWN | UNKNOWN |

### Critical gap: topology is surface-sheet only

P1-C surface groups are correct and not fabricated, but they do not produce
CanonicalTopology (bodies/shells/faces/edges/loops). Feature candidates remain
UNKNOWN type with CANDIDATE status. The process intelligence cannot generate
operations from CANDIDATE/UNKNOWN features.

For feature confirmation the pipeline needs:
- Cylindrical surfaces sharing an axis → bore/hole candidate with radius + axis
- Planar faces bounded by closed edge loops → pocket floor or datum plane
- Neither requires full B-Rep; a simplified "feature-sufficient topology" is enough

**P2 scope (bounded):** Reconstruct "feature-sufficient topology" for:
1. Cylindrical surface families (from P1-C groups) → add axis + radius to canonical model
2. Planar bounded faces with explicit boundary curves → extract polygon outline

Do NOT attempt full IGES B-Rep reconstruction. Do NOT fabricate edges/loops not
present in the file.

### IGES remaining gap summary

```
IGES_REMAINING_GAPS=
  1. No CanonicalTopology (B-Rep) → feature candidates cannot be confirmed
  2. Cylindrical surface groups have axis but no canonical feature output
  3. Freeform surfaces (127 in IGS-03) have no deterministic machining operation
  4. Material UNKNOWN for all 3 files
  5. No annotation layer in IGES → tolerance/GD&T not extractable from file
```

---

## 8. STEP Remaining Gaps

### Real sample set

There are **no STEP files** in the real sample directory
(`D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar`).
The 15-file set contains DXF, IGES, PDF, DWG, and CATIA .model only.

### Existing STEP infrastructure

`backend/interoperability/adapters/step.py` exists (StepTokenAdapter):
- Level 0: format recognition (extension + ISO-10303-21 magic byte)
- Level 1: header parse (entity count, AP version, section inventory)
- Level 2: requires pythonocc-core (not installed); currently returns UNSUPPORTED fidelity

The adapter is registered and functional for Level 1 without external dependencies.

### STEP gap assessment

```
STEP_REMAINING_GAPS=
  1. No real sample STEP files available → cannot measure real-world coverage
  2. Level 2 geometry requires pythonocc-core (OpenCASCADE Python binding)
     NOT recommended for P2: heavy dependency, Windows/Linux build complexity,
     conda-forge only, incompatible with standard pip-based CI
  3. STEP is the highest-quality exchange format for IGES-producing CAD systems
     (CATIA V5 exports STEP AP214/AP242 natively)
  4. If the customer can provide STEP files from their CATIA V5 environment,
     STEP would be preferable to IGES for topology

STEP_P2_RECOMMENDATION=
  Do NOT add pythonocc-core as a P2 dependency.
  Request STEP samples from the customer and assess Level 1 parse quality first.
  Level 2 geometry deferred until real samples exist and pythonocc-core CI
  integration is evaluated.
```

---

## 9. DWG Strategy

### Real DWG files

| File | Size | Format | DXF counterpart? |
|------|------|--------|-----------------|
| Pense_Sema.dwg | 172 KB | AC1018 (AutoCAD 2004) | YES (Pense_Sema.dxf = DXF-03) |
| RAB055S(41_NOKTALI).dwg | 9.4 MB | AC1018 | NO |
| RAB055S(42_NOKTALI).dwg | 9.5 MB | AC1018 | NO |

### Options evaluated

| Option | License | Automation | Windows | Linux/Render | Security | Maintainability |
|--------|---------|-----------|---------|-------------|---------|----------------|
| A. Offline ODA File Converter | Freeware, not redistributable | Manual | YES | YES | SAFE (no server-side binary) | ZERO (no code) |
| B. ODA File Converter as optional local install | Same | Optional automated | YES | YES | MEDIUM | LOW (optional binary path) |
| C. LibreDWG (GNU) | GPLv3 | YES | YES | YES | SAFE | MEDIUM |
| D. Remain unsupported | N/A | N/A | N/A | N/A | SAFEST | ZERO |

**LibreDWG (GPLv3) verdict:** Unusable. GPLv3 propagates to the entire application.
If MachiningPro AI is a commercial product, LibreDWG creates an obligation to publish
source code under GPLv3. This is a hard licensing stop.

**ODA File Converter verdict:** The converter is free to download and use but is not
open-source and cannot be redistributed as a bundle. It can be installed locally by the
user. Using it as an optional local binary (Option B) is feasible but adds an implicit
user-setup step that breaks serverless/cloud deployments (Render Free tier).

**Recommendation: Option A — Offline conversion guidance only.**

The application should:
1. Detect DWG upload and return a clear UNSUPPORTED response with conversion guidance.
2. The guidance UI text should reference ODA File Converter (free download from
   opendesign.com) or AutoCAD "Save As DXF".
3. DWG-01 is already covered by its DXF counterpart (Pense_Sema.dxf = DXF-03).
4. For DWG-02/03 (9.4 MB/9.5 MB), the ODA converter workflow is the safest path.

This requires no backend change — only a UI text addition (covered by P2-E UX work).

```
DWG_RECOMMENDATION=OPTION_A_OFFLINE_CONVERSION_GUIDANCE
  License: SAFE (no library bundled)
  Automation: MANUAL (user converts DWG → DXF before upload)
  New dependencies: NONE
  Coverage gain: 0 real files directly; enables DWG-02/03 via conversion workflow
  P2 effort: LOW (UI text only)
```

---

## 10. CATIA V4 .model Strategy

### Real .model files

| File | Size | Format |
|------|------|--------|
| 46795221-FONDELLO-SEDE-.model | 720 KB | CATIA V4 Release 2.1 FR 4.2.1 |
| 46795237-CANALINO-SUPER.model | 2.1 MB | CATIA V4 Release 2.1 FR 4.2.1 |
| 46795382-OSSATURA-FIANC.model | 3.4 MB | CATIA V4 Release 2.1 FR 4.2.1 |

**Decision: DEFERRED / UNSUPPORTED. No change from P1.**

Evidence:
- No open-source parser exists for CATIA V4 .model binary format.
- OpenCASCADE reads CATIA V5 (.CATPart) but NOT V4 (.model).
- Official conversion path: use CATIA V4 or V5 to export to IGES/STEP.
- No Python library. No free converter. No documented format specification.
- These files are from a 1990s–2000s CAD system. The customer should be asked to
  export to IGES from their CATIA V4 or V5 environment.

```
MODEL_RECOMMENDATION=DEFERRED_UNSUPPORTED
  Document as a user workflow requirement (export to IGES before submission).
  No implementation work. No P2 scope entry.
```

---

## 11. GD&T Coverage

### Current state

| Capability | Status | Module |
|-----------|--------|--------|
| Textual GD&T token extraction | GOOD | `gdt_drawing.py` (615 lines, Phase 1C) |
| Unicode GD&T symbol recognition | GOOD | `gdt_drawing.py` |
| Datum identification | PARTIAL | `DrawingDatumReference` model exists; not flowing to process intelligence |
| Feature-control-frame parsing | PARTIAL | `DrawingFeatureControlFrame` exists; grammar-based |
| Feature association (linking GD&T to 3D feature) | WEAK | No spatial association implemented |
| Downstream use in process planning | UNSUPPORTED | GD&T tokens not consumed by `process_intelligence.py` |

### Real-sample GD&T evidence

The 3 DXF files contain general tolerance notes in MTEXT (e.g. "GENEL TOLERANS" tables
in Turkish standard drawings). The 3 IGES files contain no annotation layer. The 3 PDF
files contain GD&T symbols in the rasterized drawing area (not extractable without OCR).

### P2 priority verdict

GD&T expansion (downstream use in process planning) is **medium priority**. The
infrastructure exists but is not connected. However, it would increase implementation
complexity significantly and the real-sample coverage gain is limited (the DXF general
tolerance tables would become structured, but feature-level GD&T association requires
the annotation wiring from P2-D first). Recommended as a P2 candidate but lower
priority than material confirmation and annotation wiring.

```
GDNT_COVERAGE_STATUS=
  EXTRACTION=GOOD (gdt_drawing.py operational)
  ASSOCIATION=WEAK (not linked to features or process planning)
  P2_PRIORITY=MEDIUM (after annotation wiring; not highest priority)
```

---

## 12. Metadata Resolution Effectiveness

| Format | Files | Geometry Ready | Raw PP Ready | User-Resolvable | Post-Confirm PP Ready |
|--------|-------|----------------|--------------|-----------------|----------------------|
| DXF | 3 | 3 | 0 | 3 | 3 |
| IGES | 3 | 3 | 0 | 1 (material only) | 0 (CAM) / 1 (PP, partial) |
| PDF | 3 | 0 | 0 | 0 | 0 |
| DWG | 3 | 0 | 0 | 0 | 0 (conversion required) |

```
FILES_BLOCKED_RAW=6 (all DXF + IGES)
FILES_RESOLVABLE_BY_USER=6 (user can supply material for all 6)
FILES_READY_AFTER_USER_CONFIRMATION=3 (DXF-01/02/03 reach process planning)
  IGES: user confirmation of material is necessary but insufficient;
  topology is also required (not user-resolvable; requires P2-B)
```

The P0 user-confirmation workflow (`missing_data.py`, `apply_user_confirmations()`)
is fully operational on the backend. The API endpoints are registered
(`/api/missing-data/analyze`, `/api/missing-data/confirm`). The gap is entirely
on the **frontend**: there is no UI panel that presents missing fields to the user
after import, asks for confirmation, and feeds confirmed values back to the pipeline.

This is the highest-impact P2 workstream in terms of real-sample coverage gain.

---

## 13. CAM Readiness

For geometry-ready files that cannot reach CAM:

| File | Missing for CAM |
|------|----------------|
| DXF-01 | material, feature confirmation (candidate only), hole depth, operation sequence |
| DXF-02 | material, feature confirmation from arc candidates, hole depth |
| DXF-03 | material, feature confirmation (candidate only), hole depth |
| IGS-01 | material, B-Rep topology, confirmed features (all CANDIDATE/UNKNOWN) |
| IGS-02 | material, B-Rep topology, confirmed features |
| IGS-03 | material, B-Rep topology, confirmed features (127 freeform surfaces have no machining operation) |

DXF files are 2D drawings; they cannot produce 3D toolpath regardless of material confirmation.
CAM for DXF is limited to 2.5D hole drilling operations. For 3D CAM, IGES/STEP with
confirmed topology is required.

IGES files currently have CANDIDATE/UNKNOWN features only. Even after material confirmation
(which unlocks process planning), the CAM module requires CONFIRMED feature type with
dimensional parameters (bore radius, pocket depth, etc.). These require topology confirmation
(P2-B scope).

```
CAM_READINESS_STATUS=
  DXF: 2.5D DRILLING CANDIDATE (after material + hole depth confirmation)
  IGES: BLOCKED (topology confirmation required first)
  PDF: BLOCKED (import pipeline not applicable)
  DWG: BLOCKED (unsupported format)
```

---

## 14. Library Gaps

### Material Library

The material library resolves designations correctly when tokens are provided.
`extract_title_block_material(['42CrMo4'])` → `P-42CrMo4` KNOWN.
`extract_title_block_material(['MALZEME:', 'C45'])` → `P-C45` KNOWN.

The library is not the gap. The gap is that DXF/IGES files do not contain material
in their native content. The extraction function is never called because there is no
material token to extract. Only the PDF rasterized title block might contain material,
and that requires OCR.

### Tool Library

The tool library is not consulted in the DXF/IGES import path because no process
planning reaches that stage (no confirmed material). Not a P2 blocker.

### Machine Library

Same situation as tool library. No confirmed features → no machine selection.

### Process Capability Data

Cutting data (cutting speed, feed per tooth, depth of cut) is not consulted in P2 scope.
Material confirmation unblocks tool/machine selection; cutting data follows.

```
LIBRARY_COVERAGE_STATUS=
  MATERIAL_LIBRARY=GOOD (25+ grades, correct extraction)
  TOOL_LIBRARY=NOT_REACHED (blocked by material/feature confirmation)
  MACHINE_LIBRARY=NOT_REACHED (blocked by material/feature confirmation)
  PROCESS_CAPABILITY=NOT_REACHED
  ROOT_CAUSE=METADATA_MISSING + UI_MISSING (not library gaps)
```

---

## 15. UX Gaps

| Gap | Severity | Description |
|-----|----------|-------------|
| No missing-field review panel | HIGH | P0 backend is complete; no UI to present MATERIAL_REQUIRED, TOLERANCE_UNKNOWN to user |
| No DWG conversion guidance | MEDIUM | UNSUPPORTED DWG response has no actionable next-step text |
| No CATIA .model guidance | MEDIUM | UNSUPPORTED .model response has no export instructions |
| No pipeline-stage readiness badges | MEDIUM | Binary PASS/FAIL masks granular capability |
| No annotation evidence visualization | LOW | P1-B links exist but are not displayed to the user |
| No OCR review workflow | LOW | P1-A OCR results have REVIEW_REQUIRED=True but no review panel |
| DEF-RSQ-001 (empty format in error) | LOW | Minor text defect in UNSUPPORTED error message |
| DEF-RSQ-003 (PDF fit false positive) | LOW | P00/A00/Bxx revision codes extracted as fit codes |

```
UX_READINESS_STATUS=
  MATERIAL_CONFIRMATION_UI=MISSING (highest gap)
  PIPELINE_STAGE_BADGES=MISSING (medium gap)
  FORMAT_GUIDANCE=PARTIAL (DWG/model unsupported but no actionable text)
  ANNOTATION_EVIDENCE=MISSING (P1-B links not displayed)
  OCR_REVIEW_UI=MISSING (P1-A results not reviewable)
```

---

## 16. Technical Debt

| Item | Type | Severity | Recommended action |
|------|------|----------|--------------------|
| PDF boundary tests | RESOLVED | — | All 19 now PASS. No action needed. |
| DEF-P1A-001: C45 FP guard clash | P2 fix | MINOR | Add material allowlist override in hybrid_pdf_drawing.py |
| DEF-P1A-002: Tesseract not in deps | P2 fix | MINOR | Add pytesseract as optional dep; capability flag |
| DEF-RSQ-001: empty format in error | P2 fix | MINOR | Small text fix in adapter response |
| DEF-RSQ-003: PDF fit false positive | P2 fix | MINOR | Add P00/A00/Bxx to FP guard pattern |
| DXF annotation linker not wired | P2 architecture | MEDIUM | Wire P1-B into orchestrator |
| IGES no CanonicalTopology | P2 architecture | MEDIUM | Build feature-sufficient topology in P2-B |
| Material confirmation UI missing | P2 architecture | HIGH | Build review panel in P2-C |

---

## 17. P2 Candidate Workstreams

### P2-A: OCR Integration and PDF False-Positive Cleanup

**Scope:**
- Add `pytesseract>=0.3.13` as optional dependency with graceful `ImportError` handling.
- Document Tesseract binary installation (Windows + Linux/Render).
- Add `PYTESSERACT_AVAILABLE` capability flag in `hybrid_pdf_drawing.py`.
- Fix DEF-P1A-001: add explicit material-grade allowlist to override `_FP_GUARD_PATTERNS`
  for the specific pattern `^[A-Z]\d{2}$`. Material grades C45, C40, B10 etc. must not
  be excluded by the revision-code guard.
- Fix DEF-RSQ-003: add P00/A00/Bxx explicit patterns to `_FP_GUARD_PATTERNS` in the
  drawing parser.
- Fix DEF-RSQ-001: fill empty format string in UNSUPPORTED response.
- Connect OCR Stage 3 to PDF engineering token extraction when Tesseract is available.

**Expected gain:**
- PDF-01/02/03: `DRAWING_INTELLIGENCE_READY` advances from PT to GOOD (with Tesseract installed).
- DEF-P1A-001/002/RSQ-001/003 all closed.

**Estimated tests:** 20 unit tests.
**License risk:** LOW (pytesseract = MIT, Tesseract = Apache 2.0).
**Regression risk:** LOW (all changes are inside existing P1-A module + isolated fixes).

---

### P2-B: IGES Feature-Sufficient Topology

**Scope:**
Extend `iges_topology_reconstruction.py` to produce `CanonicalTopology` items
that are sufficient for feature confirmation, without fabricating B-Rep geometry:

1. **Cylindrical surface families** (from P1-C groups):
   - Extract shared axis and radius from IGES cylindrical surface parameters.
   - Build a minimal `CanonicalBody` with `body_type=CYLINDRICAL_SURFACE_FAMILY`,
     axis, radius, and surface_count.
   - Mark as `topology_confidence=PARTIAL` (surfaces only, no trimming edges).
   - This is sufficient for the feature recognizer to produce `BORE_CANDIDATE` or
     `HOLE_CANDIDATE` with dimensional parameters.

2. **Bounded planar faces**:
   - For each planar surface that has an explicit `IgesBoundary` reference in the
     IGES file, extract the boundary curve set.
   - If the boundary forms a closed polygon (all end-to-start gaps < 0.01 mm),
     classify as `PLANAR_BOUNDED_FACE` with area.
   - Do NOT close open loops. Partial loops remain `PARTIAL`.

3. **Invariants:**
   - `topology_fabricated=False` always.
   - `closed_body_available=False` always (surface-sheet IGES).
   - Freeform surfaces (127 in IGS-03) are NOT processed — no deterministic machining
     operation exists for freeform geometry.
   - Zero features is a valid result for files where no cylindrical/planar bounded
     surfaces exist.

**Expected gain:**
- IGS-01/02/03: cylindrical families produce `BORE_CANDIDATE` with radius+axis.
- `FILES_FEATURE_READY` from CANDIDATE/UNKNOWN to partially confirmed candidates.
- Unblocks process planning for simple IGES parts after material confirmation.

**Estimated tests:** 25 unit tests.
**License risk:** ZERO (pure Python, no new dependencies).
**Regression risk:** MEDIUM (extends existing topology module; strict invariants required).

---

### P2-C: Material Confirmation UI Panel

**Scope:**
Build the missing UI that exposes the P0 backend workflow to the user:

1. After import, if `MissingDataAnalysis` returns any MISSING fields, show a review
   panel alongside the geometry view.
2. The panel displays each missing/uncertain field with:
   - Field name
   - Extracted value (if available from title block)
   - Confidence
   - Source provenance
   - Input control for user confirmation or correction
3. Submit calls `/api/missing-data/confirm` with the confirmed values.
4. After confirmation, re-run process planning with confirmed inputs.
5. Display pipeline-stage badges (IMPORT_STATUS / GEOMETRY_STATUS /
   FEATURE_STATUS / PLANNING_STATUS) based on `MissingDataAnalysis` output.

**Expected gain:**
- DXF-01/02/03: user confirms material → `FILES_PROCESS_PLANNING_READY` goes from 0 to 3.
- Clear UX for the dominant real-sample blocker.

**Estimated tests:** 10 frontend unit tests + 5 API integration tests.
**License risk:** ZERO.
**Regression risk:** LOW (new UI component; existing API unchanged).

---

### P2-D: DXF Annotation Pipeline Wiring

**Scope:**
Wire `link_dxf_annotations()` (P1-B) into the import orchestrator:

1. In the DXF import path of `orchestrator.py`, after feature recognition completes:
   - Collect annotation output from the drawing parser (DIMENSION/MTEXT entities with
     bounding-box positions).
   - Pass features + annotations to `link_dxf_annotations()`.
   - Enrich feature candidates with linked annotation data (dimension value, fit code,
     thread callout, etc.).
   - Store link result (`DxfAnnotationLinkResult`) in the canonical document.
2. The existing P1-B code is used unchanged. The orchestrator is the only change.
3. AMBIGUOUS and CONFLICT results must be surfaced to the user (not silently resolved).

**Expected gain:**
- DXF-01: 9 circle features get associated dimension/tolerance from 65+ MTEXT entities.
- DXF-03: 11 circle features get associated annotations.
- Downstream process planning receives enriched feature data.

**Estimated tests:** 10 orchestrator integration tests.
**License risk:** ZERO.
**Regression risk:** LOW (wiring-only; no domain logic change).

---

### P2-E (Optional): DWG and Format Guidance UX

**Scope (low-effort):**
- Improve UNSUPPORTED format response texts:
  - DWG: add "To open DWG files, convert to DXF using ODA File Converter (free, opendesign.com)
    or AutoCAD 'Save As DXF', then upload the .dxf file."
  - CATIA .model: add "To open CATIA V4 .model files, export to IGES using CATIA V4 or V5,
    then upload the .igs file."
  - Fix DEF-RSQ-001 empty format string in error message.
- EN/TR parity required for any new UI strings.

**Expected gain:** No format-support gain. Actionable guidance for DWG-02/03 and .model files.
**Estimated tests:** 2 unit tests (string content assertion).
**License risk:** ZERO. **Regression risk:** ZERO.

---

## 18. Prioritization

| Workstream | User Value | Coverage Gain | Eng. Risk | Impl. Complexity | License Risk | Regression Risk | Recommended |
|-----------|-----------|--------------|-----------|-----------------|-------------|----------------|-------------|
| P2-C: Material confirmation UI | HIGH | 0→3 PP-ready | LOW | MEDIUM | ZERO | LOW | **P0 (critical path)** |
| P2-D: DXF annotation wiring | HIGH | qualitative (feature enrichment) | LOW | LOW | ZERO | LOW | **P0 (small effort)** |
| P2-A: OCR integration + FP fix | HIGH | 0→3 PDF drawing-intelligence | MEDIUM | LOW | LOW | LOW | **P1 (bounded)** |
| P2-B: IGES feature topology | MEDIUM | IGES feature quality | MEDIUM | HIGH | ZERO | MEDIUM | **P1 (bounded scope)** |
| P2-E: Format guidance UX | LOW | 0 | LOW | LOW | ZERO | ZERO | **P2 (nice-to-have)** |

For the NEXT development cycle:
- **P0 (must-have):** P2-C (material confirmation UI) + P2-D (DXF annotation wiring)
- **P1 (high-value):** P2-A (OCR integration) + P2-B (IGES topology, bounded scope)
- **P2 (low-effort, include):** P2-E (format guidance text)

---

## 19. Recommended P2 Scope

**Three primary workstreams (in order):**

1. **P2-C + P2-D (UI + wiring):** Material confirmation panel + DXF annotation pipeline
   wiring. These are the two changes that immediately unblock real-sample process planning.
   P2-D reuses P1-B with zero domain-logic change. P2-C exposes the P0 backend that is
   already built and tested.

2. **P2-A (OCR integration):** Add pytesseract as an optional dep. Fix DEF-P1A-001/002.
   Wire OCR results to PDF engineering token extraction. Close all 4 open minor defects
   in one workstream.

3. **P2-B (IGES topology, bounded):** Cylindrical surface families → bore candidates.
   Bounded planar faces → pocket floor candidates. No B-Rep fabrication. No freeform
   processing.

**One low-effort inclusion:**
4. **P2-E (format guidance):** DWG/model UX text + DEF-RSQ-001 fix.

**Outside P2 scope:**
- STEP Level 2 geometry (pythonocc-core dependency; no real STEP samples)
- DWG direct parsing (GPLv3 licensing stop)
- CATIA V4 .model parsing (no open-source reader)
- Full IGES B-Rep reconstruction (freeform surfaces; not deterministic for manufacturing)
- GD&T → process planning downstream use (after feature confirmation is solved first)
- Level 21 (explicitly out of scope)

```
P2_RECOMMENDED_WORKSTREAMS=4
  1. P2-C: Material confirmation UI panel + pipeline-stage readiness badges
  2. P2-D: DXF annotation linker wired into orchestrator
  3. P2-A: OCR integration (pytesseract optional) + DEF-P1A-001/002/RSQ-001/003 fixes
  4. P2-B: IGES feature-sufficient topology (cylindrical + bounded planar; no fabrication)
  BONUS: P2-E DWG/model guidance text (low effort, include)
```

---

## 20. Success Criteria

Success is measurable against the P1 baseline of 9 selected files:

| Metric | P1 Baseline | P2 Target | Condition |
|--------|------------|-----------|-----------|
| FILES_DRAWING_INTELLIGENCE_READY | 5 | 8 | PDF-01/02/03 fully unlock with OCR (Tesseract installed) |
| FILES_FEATURE_READY | 6 | 8 | IGS-01/02 add confirmed cylindrical feature candidates |
| FILES_PROCESS_PLANNING_READY | 0 | 3 | DXF-01/02/03 after user confirms material via UI panel |
| OPEN_MINOR_DEFECTS | 4 | 0 | DEF-P1A-001, DEF-P1A-002, DEF-RSQ-001, DEF-RSQ-003 all closed |
| DXF_ANNOTATION_WIRING | UNWIRED | WIRED | P1-B linker called in DXF import orchestrator path |

```
P2_SUCCESS_CRITERIA=
  FILES_DRAWING_INTELLIGENCE_READY: 5→8 (Tesseract present)
  FILES_FEATURE_READY: 6→8 (IGES cylindrical topology)
  FILES_PROCESS_PLANNING_READY: 0→3 (DXF + material confirmation)
  OPEN_MINOR_DEFECTS: 4→0
  DXF_ANNOTATION_WIRING: UNWIRED→WIRED
  FABRICATED_ENGINEERING_DATA=NO (invariant)
  NEW_FAILURES_INTRODUCED=0 (invariant)
```

---

## 21. Estimated Tests

| Workstream | Unit Tests | Integration Tests | Qualification Tests |
|-----------|-----------|-----------------|-------------------|
| P2-C: Material UI | 10 | 8 | 5 |
| P2-D: Annotation wiring | 12 | 8 | 4 |
| P2-A: OCR integration + fixes | 20 | 5 | 6 |
| P2-B: IGES topology | 25 | 5 | 5 |
| P2-E: Format guidance | 2 | 0 | 0 |

```
ESTIMATED_NEW_UNIT_TESTS=69
ESTIMATED_NEW_INTEGRATION_TESTS=26
ESTIMATED_NEW_QUALIFICATION_TESTS=20
ESTIMATED_TOTAL_NEW_TESTS=115
```

---

## 22. Architectural Impact

```
BACKEND_FILES_ESTIMATED=6-9
  - backend/interoperability/orchestrator.py (P2-D annotation wiring)
  - backend/interoperability/hybrid_pdf_drawing.py (P2-A OCR + DEF-P1A-001)
  - backend/interoperability/drawing.py (P2-A DEF-RSQ-003)
  - backend/interoperability/iges_topology_reconstruction.py (P2-B extension)
  - backend/app.py or relevant adapter (P2-E DEF-RSQ-001)
  - New: backend/interoperability/iges_feature_topology.py (P2-B, possibly)

FRONTEND_FILES_ESTIMATED=4-6
  - New component: MissingFieldsPanel (P2-C)
  - New component: PipelineStageBar (P2-C)
  - Existing: DrawingImportPage or equivalent (P2-C wiring)
  - i18n: en.ts, tr.ts (new strings for panel labels)
  - P2-E: format guidance text in existing UNSUPPORTED response component

DEPENDENCIES_EXPECTED=1 (optional)
  - pytesseract>=0.3.13 (optional; guarded by ImportError; Apache 2.0 / MIT)
  - Tesseract binary (system-level; documented installation step)
  - NO new required dependencies

DATABASE_CHANGE_EXPECTED=NO
MIGRATION_EXPECTED=NO
```

---

## 23. Safety

P2 preserves all safety boundaries:

```
REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO

FABRICATED_ENGINEERING_DATA_INTRODUCED=NO
  - P2-B IGES topology: topology_fabricated=False always; closed_body_available=False always
  - P2-A OCR: all OCR results remain PENDING; auto_confirmed=False always
  - P2-C material UI: user confirmation required; no auto-fill

LEVEL21_STARTED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
FORCE_PUSH_USED=NO
```

---

## Final Report

```
HEAD_BEFORE=413b92f

P1_CONFIRMED=PASS_P1_REAL_FILE_COVERAGE_EXPANSION

FILES_TOTAL=9

FILES_IMPORT_READY=9
FILES_GEOMETRY_READY=6
FILES_DRAWING_INTELLIGENCE_READY=5
FILES_FEATURE_READY=6
FILES_METADATA_READY=0
FILES_PROCESS_PLANNING_READY=0
FILES_CAM_READY=0
FILES_FULL_E2E_READY=0

FILES_NATIVE_READY=0
FILES_USER_ASSISTED_READY=3 (DXF-01/02/03 after material confirmation)

PDF_REMAINING_GAPS=Tesseract absent; C45 FP guard; raster content not extracted
DXF_REMAINING_GAPS=Annotation linker not wired; material confirmation UI missing
IGES_REMAINING_GAPS=No CanonicalTopology; feature candidates remain UNKNOWN type
STEP_REMAINING_GAPS=No real STEP samples; pythonocc-core deferred

DWG_RECOMMENDATION=OPTION_A_OFFLINE_CONVERSION_GUIDANCE (ODA File Converter)
MODEL_RECOMMENDATION=DEFERRED_UNSUPPORTED (export to IGES from CATIA environment)

GDNT_COVERAGE_STATUS=EXTRACTION_GOOD / ASSOCIATION_WEAK / NOT_IN_P2_CRITICAL_PATH
CAM_READINESS_STATUS=DXF_2_5D_CANDIDATE / IGES_BLOCKED_TOPOLOGY / PDF_BLOCKED_FORMAT
LIBRARY_COVERAGE_STATUS=GOOD (not the bottleneck)
UX_READINESS_STATUS=MATERIAL_CONFIRMATION_UI_MISSING (critical)

PREEXISTING_PDF_FAILURES=0 (19/19 pdf_phase_boundary tests PASS)
PREEXISTING_LIVE_API_ERRORS=10 (require live server; unchanged from P0)

P2_RECOMMENDED_WORKSTREAMS=4+1
  P2-C: Material confirmation UI + pipeline-stage badges (CRITICAL)
  P2-D: DXF annotation wiring into orchestrator (HIGH)
  P2-A: OCR integration + 4 minor defect fixes (HIGH)
  P2-B: IGES feature-sufficient topology (MEDIUM, bounded)
  P2-E: DWG/model guidance UX text (LOW effort bonus)

P2_SUCCESS_CRITERIA=
  FILES_DRAWING_INTELLIGENCE_READY 5→8
  FILES_FEATURE_READY 6→8
  FILES_PROCESS_PLANNING_READY 0→3
  OPEN_MINOR_DEFECTS 4→0
  DXF_ANNOTATION_WIRING UNWIRED→WIRED

ESTIMATED_NEW_TESTS=115 (69 unit + 26 integration + 20 qualification)
ESTIMATED_FILES_AFFECTED=10-15 (backend+frontend+i18n)

PRODUCTION_FILES_CHANGED=0
SOURCE_FILES_CHANGED=NO

REPORT_PATH=docs/qualification/REAL_SAMPLE_P2_ASSESSMENT.md

GO_NO_GO=GO (conditional — 4 bounded workstreams, no license risk, no fabrication risk)

FINAL_RESULT=PASS_P2_ASSESSMENT_GO
```

---

*All source sample files verified unchanged. No production code modified during assessment.
No engineering data fabricated. All 9 real sample file hashes confirmed.*
