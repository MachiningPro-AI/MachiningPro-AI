# Real Sample File Test Matrix

**Campaign:** MACHININGPRO_AI_REAL_SAMPLE_FILES_QUALIFICATION  
**Date:** 2026-11-13  
**Branch:** main | HEAD: 6e3765c  

Legend — STATUS column:  
PASS | PARTIAL | FAIL | BLOCKED | NOT_APPLICABLE | UNSUPPORTED

---

## DXF Files

| TEST_ID | MODULE | EXPECTED | ACTUAL | STATUS | WARNINGS | DEFECT_ID |
|---------|--------|----------|--------|--------|----------|-----------|
| DXF-01 | Upload / Format ID | Accepted | Accepted (DEGRADED) | PARTIAL | ezdxf absent — Level 1 only | DEF-RSQ-002 |
| DXF-01 | Drawing Parser (token) | Engineering detections | 0 detections | FAIL | MTEXT formatting codes not stripped | DEF-RSQ-006 |
| DXF-01 | CAD Feature Recognition | Mfg features | 0 mfg_features; CANDIDATE via process_intel | PARTIAL | 2D only; 9 circles found | — |
| DXF-01 | Process Route Handoff | Route generation | CANDIDATE_PLAN 18 ops (2D_GEOMETRY_ONLY) | PARTIAL | material/tolerance UNKNOWN | — |
| DXF-01 | Process Planning | Actionable plan | CANDIDATE_PLAN | PARTIAL | Not actionable: missing material | — |
| DXF-01 | Machine Selection | Machine candidates | BLOCKED | BLOCKED | No confirmed requirements | — |
| DXF-01 | Tool Selection | Tool candidates | BLOCKED | BLOCKED | No confirmed requirements | — |
| DXF-01 | Cutting Data | Cutting parameters | BLOCKED | BLOCKED | material UNKNOWN | — |
| DXF-01 | CAM / Toolpath | 3D toolpath | NOT_APPLICABLE | NOT_APPLICABLE | 2D drawing | — |
| DXF-01 | NC Generation | NC code | NOT_APPLICABLE | NOT_APPLICABLE | 2D drawing | — |
| DXF-02 | Upload / Format ID | Accepted | Accepted (DEGRADED) | PARTIAL | ezdxf absent | DEF-RSQ-002 |
| DXF-02 | Drawing Parser (token) | Engineering detections | 0 detections | FAIL | MTEXT not decoded | DEF-RSQ-006 |
| DXF-02 | CAD Feature Recognition | Mfg features | 0 mfg_features; INSUFFICIENT_DATA | PARTIAL | No circles in geometry | — |
| DXF-02 | Process Route Handoff | Routes | INSUFFICIENT_DATA | BLOCKED | No suitable features | — |
| DXF-02 | Process Planning and downstream | Plan | BLOCKED | BLOCKED | — | — |
| DXF-03 | Upload / Format ID | Accepted | Accepted (DEGRADED) | PARTIAL | ezdxf absent | DEF-RSQ-002 |
| DXF-03 | Drawing Parser (token) | Engineering detections | 0 detections | FAIL | MTEXT not decoded | DEF-RSQ-006 |
| DXF-03 | CAD Feature Recognition | Mfg features | 0 mfg_features; CANDIDATE via process_intel | PARTIAL | 11 circles found; 22 candidate ops | — |
| DXF-03 | Process Route Handoff | Routes | CANDIDATE_PLAN 22 ops | PARTIAL | 2D_GEOMETRY_ONLY | — |
| DXF-03 | Process Planning | Plan | CANDIDATE_PLAN | PARTIAL | Missing material/tolerance | — |
| DXF-03 | Machine/Tool/Cutting/CAM/NC | Various | BLOCKED | BLOCKED | — | — |

---

## IGES Files

| TEST_ID | MODULE | EXPECTED | ACTUAL | STATUS | WARNINGS | DEFECT_ID |
|---------|--------|----------|--------|--------|----------|-----------|
| IGS-01 | Upload / Format ID | Accepted | Accepted; norm=UNSUPPORTED | PARTIAL | 521 entity_refs; adapter parsed but could not normalize | DEF-RSQ-004 |
| IGS-01 | Drawing Parser | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | 3D geometry has no annotation layer | — |
| IGS-01 | CAD Feature Recognition | Mfg features | 119 classified_faces (96 PLANAR, 23 FREEFORM); 0 mfg_features | PARTIAL | Face classification works; mfg feature extraction absent | DEF-RSQ-007 |
| IGS-01 | Process Route Handoff | Routes | BLOCKED | BLOCKED | No mfg features | — |
| IGS-01 | Process Planning and downstream | Plan | BLOCKED | BLOCKED | INSUFFICIENT_DATA | — |
| IGS-02 | Upload / Format ID | Accepted | Accepted (PARTIAL — header only) | PARTIAL | 221 KB file; only IgesHeader entity parsed | DEF-RSQ-005 |
| IGS-02 | Drawing Parser | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |
| IGS-02 | CAD Feature Recognition | Geometry + features | No geometry; no features | FAIL | Only 1 entity_ref (IgesHeader) for 221 KB file | DEF-RSQ-005 |
| IGS-02 | Process Planning and downstream | Plan | No process_intelligence | BLOCKED | — | — |
| IGS-03 | Upload / Format ID | Accepted | Accepted (DEGRADED) | PARTIAL | 1931 entity_refs; norm=PARTIAL | — |
| IGS-03 | Drawing Parser | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |
| IGS-03 | CAD Feature Recognition | Mfg features | 191 classified_faces (64 PLANAR, 127 FREEFORM); 0 mfg_features | PARTIAL | Surface classification works; mfg features absent | DEF-RSQ-007 |
| IGS-03 | Process Route Handoff | Routes | BLOCKED | BLOCKED | INSUFFICIENT_DATA | — |
| IGS-03 | Process Planning and downstream | Plan | BLOCKED | BLOCKED | — | — |

---

## PDF Files

| TEST_ID | MODULE | EXPECTED | ACTUAL | STATUS | WARNINGS | DEFECT_ID |
|---------|--------|----------|--------|--------|----------|-----------|
| PDF-01 | Upload (CAD import) | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Error msg: "No adapter registered for format ''" | DEF-RSQ-001 |
| PDF-01 | Drawing Parser (pdfplumber) | Dimension/tolerance detections | 3 FIT detections (P00, P00, K1) — false positives | FAIL | Revision codes misidentified as fit codes | DEF-RSQ-003 |
| PDF-01 | CAD Feature / downstream | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |
| PDF-02 | Upload (CAD import) | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Same empty format string | DEF-RSQ-001 |
| PDF-02 | Drawing Parser (pdfplumber) | Dimension/tolerance detections | 2 FIT detections (P00, A2) — false positives | FAIL | Same pattern | DEF-RSQ-003 |
| PDF-02 | CAD Feature / downstream | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |
| PDF-03 | Upload (CAD import) | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Same | DEF-RSQ-001 |
| PDF-03 | Drawing Parser (pdfplumber) | Dimension/tolerance detections | 2 FIT detections (P00, A2) — false positives | FAIL | Same pattern | DEF-RSQ-003 |
| PDF-03 | CAD Feature / downstream | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |

---

## DWG Files

| TEST_ID | MODULE | EXPECTED | ACTUAL | STATUS | WARNINGS | DEFECT_ID |
|---------|--------|----------|--------|--------|----------|-----------|
| DWG-01 | Upload / Format ID | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Error msg: format='' | DEF-RSQ-001 |
| DWG-01 | All downstream | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |
| DWG-02 | Upload / Format ID | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Same | DEF-RSQ-001 |
| DWG-03 | Upload / Format ID | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Same | DEF-RSQ-001 |

---

## CATIA .model Files

| TEST_ID | MODULE | EXPECTED | ACTUAL | STATUS | WARNINGS | DEFECT_ID |
|---------|--------|----------|--------|--------|----------|-----------|
| MODEL-01 | Upload / Format ID | Graceful UNSUPPORTED | UNSUPPORTED | PASS | format='' in error | DEF-RSQ-001 |
| MODEL-01 | All downstream | NOT_APPLICABLE | NOT_APPLICABLE | NOT_APPLICABLE | — | — |
| MODEL-02 | Upload / Format ID | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Same | DEF-RSQ-001 |
| MODEL-03 | Upload / Format ID | Graceful UNSUPPORTED | UNSUPPORTED | PASS | Same | DEF-RSQ-001 |

---

## Security / Safety Checks

| CHECK | STATUS |
|-------|--------|
| REAL_MACHINE_WRITE_FOUND | NO |
| AUTO_CNC_DISPATCH_FOUND | NO |
| AUTO_APPROVAL_FOUND | NO |
| AUTOMATIC_ADAPTATION_FOUND | NO |
| SOURCE_SAMPLE_FILES_COMMITTED | NO |
| NC_DISPATCHED | NO (OFFLINE_CANDIDATE=True, NOT_DISPATCHED=True) |

---

## Anti-Fabrication Audit

| CHECK | STATUS |
|-------|--------|
| FABRICATED_FEATURE_FOUND | NO |
| FABRICATED_DIAMETER_FOUND | NO |
| FABRICATED_TOLERANCE_FOUND | NO |
| FABRICATED_RA_FOUND | NO |
| FABRICATED_MATERIAL_FOUND | NO |

Note: DXF-01 and DXF-03 show CANDIDATE_PLAN from 2D_GEOMETRY_ONLY. Operations are derived from actual detected circles/arcs in the file geometry — not injected defaults. No material, tolerance, Ra, or IT grade is present in any candidate operation.

---

## Module Summary Totals

| Module | PASS | PARTIAL | FAIL | BLOCKED | NOT_APPLICABLE | UNSUPPORTED |
|--------|-----:|--------:|-----:|--------:|---------------:|------------:|
| Upload / Format ID | 6 | 6 | 0 | 0 | 0 | 9 |
| Drawing Parser | 0 | 0 | 6 | 0 | 9 | 0 |
| CAD Feature Recognition | 0 | 4 | 1 | 0 | 9 | 0 |
| Process Route Handoff | 0 | 2 | 0 | 4 | 9 | 0 |
| Process Planning | 0 | 2 | 0 | 4 | 9 | 0 |
| Machine Selection | 0 | 0 | 0 | 6 | 9 | 0 |
| Tool Selection | 0 | 0 | 0 | 6 | 9 | 0 |
| Cutting Data | 0 | 0 | 0 | 6 | 9 | 0 |
| CAM / Toolpath | 0 | 0 | 0 | 3 | 12 | 0 |
| NC Generation | 0 | 0 | 0 | 3 | 12 | 0 |
