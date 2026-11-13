# Real Sample File Defect Register

**Campaign:** MACHININGPRO_AI_REAL_SAMPLE_FILES_QUALIFICATION  
**Date:** 2026-11-13  
**Branch:** main | HEAD: 6e3765c  

> HARD RULE 9: Defects are RECORDED only. No automatic repair in this campaign.  
> Fix priority will be decided separately after report review.

---

## Summary

| Severity | Count |
|----------|------:|
| BLOCKER  | 0 |
| CRITICAL | 0 |
| MAJOR    | 5 |
| MINOR    | 2 |
| COSMETIC | 0 |
| **Total**| **7** |

---

## DEF-RSQ-001 — Format detection returns empty string for unsupported formats

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-001 |
| **TEST_IDs** | PDF-01, PDF-02, PDF-03, DWG-01, DWG-02, DWG-03, MODEL-01, MODEL-02, MODEL-03 |
| **FORMAT** | PDF, DWG, CATIA .model |
| **MODULE** | CadImportOrchestrator — format detection |
| **SEVERITY** | MINOR |
| **EXPECTED** | Error message: "No adapter registered for format 'PDF'" (or 'DWG', 'MODEL') |
| **ACTUAL** | Error message: "No adapter registered for format ''" (empty string) |
| **REPRODUCTION** | Pass any PDF, DWG, or .model file to `CadImportOrchestrator.import_source()`. Check `result.error_message`. |
| **ROOT_CAUSE_IF_KNOWN** | Format detection resolves from file extension; PDF/DWG/.model extensions are not in the ALLOWED_EXTENSIONS allowlist so the extension → format lookup returns empty string instead of the raw extension value. |
| **RECOMMENDED_FIX** | In format detection, fall back to the uppercase file extension when no registered format maps to it. The error message should read "No adapter registered for format 'PDF'" etc. |
| **STATUS** | OPEN — not fixed in this campaign |

---

## DEF-RSQ-002 — DXF import DEGRADED due to absent ezdxf optional dependency

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-002 |
| **TEST_IDs** | DXF-01, DXF-02, DXF-03 |
| **FORMAT** | DXF |
| **MODULE** | DxfTokenAdapter / CadImportOrchestrator |
| **SEVERITY** | MAJOR |
| **EXPECTED** | DXF imports reach Level 2 (NORMALIZED) with full entity histogram (LINE, ARC, CIRCLE, LWPOLYLINE, INSERT, DIMENSION, TEXT, MTEXT counts) |
| **ACTUAL** | DXF imports are DEGRADED (Level 1 only). Only 1 entity_ref (DxfHeader) returned. Full entity counts are not exposed even though geometry IS extracted at the CanonicalGeometry level (632 / 686 / 313 curves). |
| **REPRODUCTION** | Run `CadImportOrchestrator.import_source()` on any .dxf file without `ezdxf` installed. Check `result.status == ImportStatus.DEGRADED` and `len(result.document.entity_refs) == 1`. |
| **ROOT_CAUSE_IF_KNOWN** | `ezdxf` is listed as an optional dependency. Without it, the DxfTokenAdapter falls back to Level 1 (header-only entity_refs) even though the token-level geometry extraction still succeeds. |
| **RECOMMENDED_FIX** | (a) Add `ezdxf` to production environment requirements. (b) Alternatively, populate entity_refs with geometry-derived curve/arc/circle counts from the Level 1 extraction so the entity histogram is not empty when ezdxf is absent. |
| **STATUS** | OPEN — ezdxf not installed in test environment |

---

## DEF-RSQ-003 — PDF drawing parser produces false-positive FIT detections for revision codes

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-003 |
| **TEST_IDs** | PDF-01, PDF-02, PDF-03 |
| **FORMAT** | PDF |
| **MODULE** | `run_token_extraction` (semantic_extraction) |
| **SEVERITY** | MINOR |
| **EXPECTED** | Token extraction correctly ignores revision block codes (P00, A2, K1). Zero detections for non-engineering tokens. |
| **ACTUAL** | "P00", "A2", "K1" are classified as FIT detections (NormalizedDetectionType.FIT). These are drawing revision codes from the title block, not ISO tolerance fits. |
| **REPRODUCTION** | Extract text tokens from any PDF with a revision table containing codes like "P00", "A2", "K1". Pass to `run_token_extraction()`. Observe FIT detections with raw_text in {P00, A2, K1}. |
| **ROOT_CAUSE_IF_KNOWN** | The fit token parser matches short alphanumeric codes (letter+digits) without sufficient context. Title-block revision codes (Pxx, Axx) match the ISO fit pattern (letter+number). |
| **RECOMMENDED_FIX** | Add a blocklist of common revision code patterns (P00, A00, Bxx) to the fit token parser, OR require surrounding dimension context (a numeric value) before classifying a code as a fit. |
| **STATUS** | OPEN — not fixed in this campaign |

---

## DEF-RSQ-004 — IGS-01 status UNSUPPORTED despite successful geometry extraction

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-004 |
| **TEST_IDs** | IGS-01 |
| **FORMAT** | IGES |
| **MODULE** | IgesTokenAdapter / CadImportOrchestrator |
| **SEVERITY** | MAJOR |
| **EXPECTED** | File with 521 entity_refs and valid CanonicalGeometry (247 curves + 119 surfaces, bounding box) should achieve at minimum PARTIAL or DEGRADED status. |
| **ACTUAL** | ImportStatus=UNSUPPORTED, normalization_status=UNSUPPORTED. Despite the document having geometry, topology=None, and 42 IgesUnsupportedGeometryType + 67 IgesUnsupportedMetadataEntity entries, the orchestrator surfaces this as UNSUPPORTED rather than PARTIAL. |
| **REPRODUCTION** | Import `agv03773.geo_fin001.006003.igs` via `CadImportOrchestrator`. Observe `result.status == ImportStatus.UNSUPPORTED` while `result.document.geometry` contains 247 curves and 119 surfaces. |
| **ROOT_CAUSE_IF_KNOWN** | The normalization decision is likely driven by the presence of IgesUnsupportedGeometryType entities; if the fraction of unsupported entities exceeds a threshold, the whole import is demoted to UNSUPPORTED even when significant valid geometry was extracted. |
| **RECOMMENDED_FIX** | When CanonicalGeometry is populated with meaningful content (curves + surfaces + bounding box), status should be at least PARTIAL. Reserve UNSUPPORTED for cases where the adapter cannot parse the file at all. |
| **STATUS** | OPEN — not fixed in this campaign |

---

## DEF-RSQ-005 — IGS-02 (221 KB IGES file) produces only IgesHeader entity

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-005 |
| **TEST_IDs** | IGS-02 |
| **FORMAT** | IGES |
| **MODULE** | IgesTokenAdapter |
| **SEVERITY** | MAJOR |
| **EXPECTED** | A 221 KB IGES file should produce significant geometry. Expected: multiple surface and curve entity_refs with CanonicalGeometry populated. |
| **ACTUAL** | Only 1 entity_ref (IgesHeader). geometry=None, topology=None, features=None, process_intelligence=None. Status=PARTIAL but no usable content. |
| **REPRODUCTION** | Import `fa00aaj27500_004999.igs` via `CadImportOrchestrator`. Observe `len(result.document.entity_refs) == 1` and `result.document.geometry is None`. |
| **ROOT_CAUSE_IF_KNOWN** | Unknown. The file may use an IGES variant (e.g., with unusual parameter delimiter or FreeForm entity types) that the token adapter fails to tokenize beyond the header section. |
| **RECOMMENDED_FIX** | Add diagnostic logging to the IGES adapter when entity parsing yields fewer than expected results relative to file size. Consider adding a minimum-entity warning to `ImportDiagnostics`. |
| **STATUS** | OPEN — not fixed in this campaign |

---

## DEF-RSQ-006 — DXF drawing parser produces zero detections: MTEXT formatting codes not stripped

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-006 |
| **TEST_IDs** | DXF-01, DXF-02, DXF-03 |
| **FORMAT** | DXF |
| **MODULE** | `run_token_extraction` (semantic_extraction) / DXF annotation pathway |
| **SEVERITY** | MAJOR |
| **EXPECTED** | Engineering annotation text visible in DXF files (dimensions, tolerances, general tolerance tables, surface finish symbols) should be extracted and classified. |
| **ACTUAL** | Zero detections from DXF annotation tokens. DXF MTEXT entity text is encoded with formatting codes (`\W0.963;47,5`, `\fsimplex.shx;\H1.50;text`). The token extraction engine receives these raw codes and cannot match engineering patterns. |
| **REPRODUCTION** | Extract group code 1 values from any DXF file using MTEXT entities. Pass to `run_token_extraction()`. Observe 0 detections even when annotation text clearly contains numeric dimension values. |
| **ROOT_CAUSE_IF_KNOWN** | The DXF-to-token pipeline does not include an MTEXT formatting code stripper before invoking the token extractor. MTEXT codes must be stripped (remove `\Wn.nnn;`, `\f...;`, `\H...;`, `\P` etc.) to expose clean text. Additionally, DXF dimension values are stored in geometry fields (group codes 10, 11, etc.) rather than text fields, so group code 1 extraction alone is insufficient. |
| **RECOMMENDED_FIX** | Add a DXF MTEXT preprocessor that strips AutoCAD formatting codes before token extraction. For dimension values, also read DXF DIMENSION entity geometry coordinates. This would enable the drawing parser to correctly extract annotation data from DXF files. |
| **STATUS** | OPEN — not fixed in this campaign |

---

## DEF-RSQ-007 — IGES surface classification does not produce manufacturing features

| Field | Value |
|-------|-------|
| **DEFECT_ID** | DEF-RSQ-007 |
| **TEST_IDs** | IGS-01, IGS-03 |
| **FORMAT** | IGES |
| **MODULE** | `recognize_manufacturing_features` / CAD feature recognition |
| **SEVERITY** | MAJOR |
| **EXPECTED** | IGES files with classified surfaces (PLANAR/FREEFORM) and significant geometry should produce at least candidate manufacturing features (e.g., planar faces → milling candidates, cylindrical surfaces → turning/boring candidates). |
| **ACTUAL** | manufacturing_features=0 for all IGES files despite classified_faces > 0 (IGS-01: 119 classified, IGS-03: 191 classified). The FeatureRecognitionResult only contains ClassifiedFace entries; ManufacturingFeatureType instances are never created. |
| **REPRODUCTION** | Import any IGES file with geometry. Check `doc.features.manufacturing_features`. Observe count=0 even when `doc.features.classified_faces` contains meaningful data. |
| **ROOT_CAUSE_IF_KNOWN** | The manufacturing feature recognition step requires a CanonicalTopology (bodies, shells, edges) in addition to CanonicalGeometry. IGES import currently populates geometry but not topology (topology=None). Without topology, the feature recognizer cannot identify bounded features (pockets, bosses, holes) from free surface groups. |
| **RECOMMENDED_FIX** | (a) Build CanonicalTopology from IGES trimmed surface/bounded surface entities. (b) Alternatively, implement a geometry-only feature recognizer that can identify cylindrical, planar, and helical surface groups as manufacturing feature candidates without full topology. |
| **STATUS** | OPEN — not fixed in this campaign |

---

*End of defect register. 7 defects recorded. No defects fixed in this campaign.*
