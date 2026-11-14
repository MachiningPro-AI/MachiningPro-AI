# Real Sample P1 Defect Register

**Campaign:** MACHININGPRO_AI_P1_REAL_FILE_COVERAGE_EXPANSION  
**Date:** 2026-11-14  
**Branch:** main | HEAD_BEFORE: 17bcdc9  
**Status at campaign start:** P0_PASS confirmed (all DEF-RSQ-001 through DEF-RSQ-007 documented)  

---

## Open Defects from P0 (Carried Forward)

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| DEF-RSQ-001 | MINOR | Empty format string in UNSUPPORTED error message for PDF/DWG/model | OPEN — carry forward (not in P1 scope) |
| DEF-RSQ-003 | MINOR | PDF drawing analysis: revision code false-positive filter missing (P00/A00/Bxx) | OPEN — carry forward; P1-A adds FP guards that partially mitigate |

All MAJOR defects from P0 (DEF-RSQ-002, 004, 005, 006, 007) are CLOSED.

---

## P1-A Defects Found

### DEF-P1A-001 (MINOR)

| Field | Value |
|-------|-------|
| ID | DEF-P1A-001 |
| Severity | MINOR |
| Component | hybrid_pdf_drawing — false-positive guard |
| Description | The `_FP_GUARD_PATTERNS` list uses `^[A-Z]\d{2}$` which excludes the material designation "C45" because it matches the revision-code pattern (`C` + two digits). C45 is a valid steel grade. |
| Impact | C45 detected in PDF title block is silently dropped. User would not see the material designation. |
| Fix required | Extend false-positive guard to be context-aware: apply revision-code exclusion only outside material-extraction context, OR maintain an explicit material grade allowlist to override the FP guard. |
| Status | OPEN — Deferred to P2 (requires redesign of guard context; broader impact possible) |

### DEF-P1A-002 (MINOR)

| Field | Value |
|-------|-------|
| ID | DEF-P1A-002 |
| Severity | MINOR |
| Component | hybrid_pdf_drawing — OCR dependency |
| Description | The P1-A OCR path (Stage 3) requires Tesseract binary and pytesseract Python package. These are not in the current project dependencies. When unavailable, the pipeline falls back gracefully with `OCR_UNSUPPORTED` status, but no engineering drawing content is extracted for the 3 raster PDFs. |
| Impact | PDF-01/02/03 engineering drawing content (dimension callouts, tolerances) cannot be extracted without manual dependency installation. |
| Fix required | Document Tesseract installation step. Consider adding pytesseract as an optional dependency with a capability flag. |
| Status | OPEN — Non-blocking (graceful fallback active); documentation update recommended |

---

## P1-B Defects Found

None. DXF annotation linker correctly handles all test cases:  
- single unambiguous link → LINKED  
- multiple candidates → AMBIGUOUS  
- conflicting annotations → CONFLICT  
- no spatial evidence → UNRESOLVED  
- no features → all UNRESOLVED  

False-positive guard (black-box semantic-only linking prohibited) is active.

---

## P1-C Defects Found

None. IGES topology reconstruction correctly:  
- Groups planar, cylindrical, and freeform surfaces  
- Never fabricates B-Rep bodies or closed topology  
- Reports `closed_body_available=NO` for surface-only files  
- Passes through existing B-Rep topology without re-reconstruction  

---

## P1-D Defects Found

None. Partial circular boundary recognition correctly:  
- Requires arc_count ≥ 2  
- Requires coverage ≥ 60°  
- Groups by center+radius within 0.001 mm tolerance  
- Returns HOLE_CANDIDATE only for ≥358° coverage  
- Returns CIRCULAR_BOUNDARY_CANDIDATE with is_partial=True for 60°–358°  
- Excludes single ARCs, different-center ARCs, ellipses, and decorative arcs  

```
FALSE_POSITIVE_ARC_FEATURES=0
```

---

## Remaining Coverage Blockers (Post-P1)

These are known limitations, not new defects introduced by P1:

| Blocker | Files Affected | Resolution Path |
|---------|---------------|-----------------|
| MISSING_MATERIAL | DXF-01, DXF-03, IGS-01, IGS-02, IGS-03 | P0 user confirmation workflow; P1-A title-block extraction (DXF) |
| SURFACE_SHEET_TOPOLOGY_ONLY | IGS-01, IGS-02, IGS-03 | Confirmed B-Rep requires full IGES B-Rep reconstruction (P2+) |
| PDF_IMPORT_UNSUPPORTED | PDF-01, PDF-02, PDF-03 | PDFs not in CAD import pipeline (by design; drawing intelligence separate) |
| DWG_UNSUPPORTED | DWG-01, DWG-02, DWG-03 | Offline DWG→DXF conversion required (DWG-01 has DXF counterpart) |
| MODEL_UNSUPPORTED | MODEL-01, MODEL-02, MODEL-03 | CATIA V4 format deferred; export to IGES via CATIA required |

---

## Defect Count Summary

```
OPEN_MINOR_P1=2 (DEF-P1A-001, DEF-P1A-002)
OPEN_MAJOR_P1=0
OPEN_CRITICAL_P1=0
OPEN_BLOCKER_P1=0
CARRIED_FORWARD_MINOR=2 (DEF-RSQ-001, DEF-RSQ-003)
CLOSED_THIS_CAMPAIGN=0 (no P0 defects in P1 scope)
```

---

*No scope expansion beyond P1-A/B/C/D. No unrelated defect fixes applied.*
