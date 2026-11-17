# Real CAD Multi-Format Qualification

**FINAL_RESULT: PASS_STEP_STL_DXF — PARTIAL_IGES — DEFERRED_REMAINDER**

Scan date: 2026-11-17  
HEAD before: 0be91e2  
Scan root: `D:\makina_ogrenmesi\olcum_denemeleri` (recursive, excluding pcsm/venv)

---

## MUST 1 — Baseline Verification

```
BRANCH=main
HEAD=0be91e2  (test+docs(qualification): P10 phase 4 real STEP qualification gate)
ORIGIN_MAIN=0be91e2
WORKTREE_CLEAN=YES
AHEAD_BEHIND=0
```

---

## MUST 2 — Format Count Report

| Format | Extension | Count | Notes |
|--------|-----------|-------|-------|
| STEP | .step | 6 | User-owned, root level |
| IGES | .igs | 17 | Surface models, NOT closed B-Rep |
| DXF | .dxf | 66 | 2D/2.5D engineering drawings |
| DWG | .dwg | 3 | No native reader |
| STL | .stl | 7 | ASCII + binary mix |
| PLY | .ply | 1 | trimesh not installed |
| Parasolid | .x_t | 2 | Proprietary SDK required |
| ACIS | .sat | 2 | Proprietary SDK required |
| JT | .jt | 1 | Siemens proprietary |
| CATIA V4 | .model | 6 | Licence required |
| SolidWorks | .sldprt | 1 | SDK required |
| PDF | .pdf | 7 | Engineering drawings (2D only) |
| **TOTAL** | — | **119** | — |

```
STEP_COUNT=6
IGES_COUNT=17
DXF_COUNT=66
DWG_COUNT=3
STL_COUNT=7
PLY_COUNT=1
PARASOLID_XT_COUNT=2
PARASOLID_XB_COUNT=0
JT_COUNT=1
CATIA_MODEL_COUNT=6
CATPART_COUNT=0
SOLIDWORKS_SLDPRT_COUNT=1
SOLIDWORKS_SLDASM_COUNT=0
ACIS_SAT_COUNT=2
ACIS_SAB_COUNT=0
NX_PRT_COUNT=0
CREO_PRT_COUNT=0
TOTAL_ENGINEERING_FILES=119
```

---

## MUST 3 — Format Collision Detection

No `.prt` files found — NX/Creo extension collision does not apply.  
`.model` extension is unambiguous: CATIA V4 binary only.  
**FORMAT_COLLISION_DETECTED=NO**

---

## MUST 4-6 — Adapter Audit & Capability Matrix

### Available Parsers / Libraries

| Library | Status | Purpose |
|---------|--------|---------|
| gmsh 4.15.2 (bundled OCC) | INSTALLED | STEP B-Rep + STL mesh |
| ezdxf | INSTALLED | DXF 2D/2.5D |
| OCC (pythonocc-core) | NOT_INSTALLED | — |
| trimesh | NOT_INSTALLED | — |
| cadquery | NOT_INSTALLED | — |
| ifcopenshell | NOT_INSTALLED | — |
| Parasolid SDK | NOT_INSTALLED | — |
| ACIS SDK | NOT_INSTALLED | — |

### Capability Matrix (FORMAT / ADAPTER / NATIVE_IMPORT / GEOMETRY_LEVEL / STATUS)

| Format | Adapter | Native Import | Geometry Level | Topology | Features | Status |
|--------|---------|---------------|----------------|----------|----------|--------|
| STEP | gmsh_step_parser.py | YES | B-Rep Solid | YES | YES (holes) | PASS_NATIVE_BREP |
| IGES | IgesTokenAdapter | PARTIAL | NONE (entity count) | NO | NO | TOKEN_ONLY_NO_GEOMETRY |
| DXF | DxfTokenAdapter / ezdxf | YES | 2D/2.5D profile | NO | CANDIDATE | PASS_NATIVE_2D |
| DWG | DwgAdapterStub | NO | N/A | NO | NO | DEPENDENCY_MISSING |
| STL | gmsh merge | YES | Mesh only | NO | NO | PASS_MESH_ONLY |
| PLY | (none) | NO | N/A | NO | NO | DEPENDENCY_MISSING |
| Parasolid X_T | ParasolidAdapterStub | NO | N/A | NO | NO | DEPENDENCY_MISSING |
| ACIS SAT | AcisAdapterStub | NO | N/A | NO | NO | DEPENDENCY_MISSING |
| JT | JtAdapterStub | NO | N/A | NO | NO | DEPENDENCY_MISSING |
| CATIA .model | CatiaAdapterStub | NO | N/A | NO | NO | UNSUPPORTED_PROPRIETARY |
| SolidWorks .sldprt | SolidWorksAdapterStub | NO | N/A | NO | NO | DEPENDENCY_MISSING |

**HR-14 compliance: NO silent conversion for any format above.**  
**HR-15 compliance: Native vs. conversion-based capability reported separately.**

---

## MUST 7-10 — STEP File Qualification (All 6 Files)

### Results

| File | Volumes | Surfaces | Edges | Vertices | Status | Parse Time |
|------|---------|----------|-------|----------|--------|------------|
| electronics-enclosure.step | 1 | 35 | 72 | 48 | PASS | 0.07 s |
| flanged-bushing (1).step | 1 | 8 | 13 | 8 | PASS | 0.02 s |
| flange-plate.step | 1 | 15 | 39 | 26 | PASS | 0.04 s |
| l-bracket.step | 1 | 13 | 33 | 22 | PASS | 0.03 s |
| Pump Manifold v3.step | 1 | 118 | 334 | 214 | PASS | 0.45 s |
| stepped-shaft-keyway.step | 1 | 12 | 25 | 16 | PASS | 0.03 s |

```
STEP_PARSE_PASS_COUNT=6
STEP_PARSE_FAIL_COUNT=0
ALL_SINGLE_BODY=YES
DETERMINISM_VERIFIED=YES (electronics, Pump Manifold, stepped-shaft-keyway)
```

**REAL_EXTERNAL_STEP_SAMPLE_COUNT=6** (user-owned, all in `olcum_denemeleri` root)  
**P10 Phase 4 gate: UNBLOCKED**  
**REAL_STEP_QUALIFICATION_READY=YES**

---

## MUST 9 — Feature Detection on Real STEP Files

| File | PLANAR | CYLINDRICAL | UNKNOWN | HOLES | THROUGH |
|------|--------|-------------|---------|-------|---------|
| electronics-enclosure.step | 19 | 8 | 8 | 8 | 8 |
| flanged-bushing (1).step | 3 | 5 | 0 | 5 | 5 |
| flange-plate.step | 6 | 5 | 4 | 5 | 5 |
| l-bracket.step | 8 | 4 | 1 | 4 | 4 |
| Pump Manifold v3.step | 4 | 0 | 114 | 0 | 0 |
| stepped-shaft-keyway.step | 6 | 3 | 3 | 3 | 3 |

```
TOTAL_HOLE_CANDIDATES=25
THROUGH_HOLE_CANDIDATES=25
BLIND_HOLE_CANDIDATES=0
AUTO_CONFIRMED_FEATURE_FOUND=NO (all CANDIDATE only)
POCKET_CANDIDATES=0
SLOT_CANDIDATES=0
```

---

## MUST 11-16 — IGES Qualification

### Entity Analysis (all 17 files)

| Entity Type | Description | Present |
|-------------|-------------|---------|
| 128 | NURBS Surface | YES (all complex files) |
| 144 | Trimmed Parametric Surface | YES (all complex files) |
| 110 | Line | YES |
| **186** | **Manifold Solid B-Rep Object** | **NO — 0 of 17 files** |

```
IGES_CLOSED_SOLID_COUNT=0
IGES_GEOMETRY_LEVEL=NONE  (IgesTokenAdapter: entity count only)
IGES_TOPOLOGY_LEVEL=NONE
IGES_FEATURE_EXTRACTION=NONE
```

**IGES files are SURFACE MODELS only. They do NOT contain closed B-Rep solids.**  
**IGES cannot substitute for STEP in the 3D CAM pipeline (HR-14).**

---

## MUST 15 — STL Qualification

| File | Format | Nodes | Status |
|------|--------|-------|--------|
| electronics-enclosure.stl | BINARY | 3,840 | PASS_MESH |
| flange-plate.stl | BINARY | 2,298 | PASS_MESH |
| flanged-bushing.stl | BINARY | 1,512 | PASS_MESH |
| sample_stl_1.stl | BINARY | 267,966 | PASS_MESH |
| sample_stl_2.stl | ASCII | 46,770 | PASS_MESH |
| stepped-shaft-keyway.stl | BINARY | 1,596 | PASS_MESH |
| X_tile.stl | ASCII | 4,590 | PASS_MESH |

```
STL_PASS_COUNT=7
STL_IS_MESH_ONLY=YES (no B-Rep, no topology, no feature extraction)
```

---

## MUST 17 — DXF Summary

```
DXF_COUNT=66
DXF_ADAPTER=DxfTokenAdapter (ezdxf 1.3.x)
DXF_GEOMETRY_LEVEL=2D/2.5D
DXF_TOPOLOGY=NONE
DXF_FEATURE_EXTRACTION=CANDIDATE (not CONFIRMED)
```

---

## Proprietary Format Headers (Verification)

| File | Format | Header Evidence |
|------|--------|-----------------|
| sample_x_t_1.x_t | Parasolid text | `**PARASOLID` magic |
| sample_sat_1.sat | ACIS ASCII 16.0.7 | `ACIS 16.0.7 NT` header |
| sample_jt_2.jt | JT 8.0 | `Version 8.0` header |
| 46795221-*.model | CATIA V4 binary | Non-ASCII header bytes (F4 F6…) |
| Battery Bracket.sldprt | SolidWorks OLE/CFB | 0x7A 0xB7 0x71 0x1E magic |
| sample_ply_2.ply | Binary PLY | `ply\nformat binary_little_endian` |

---

## Safety Verification

```
IS_DISPATCHABLE_TRUE_FOUND=NO
PRODUCTION_RELEASED_TRUE_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
AUTO_APPROVAL_FOUND=NO
REAL_SOURCE_CAD_FILE_COMMITTED=NO
REAL_SOURCE_FILE_MODIFIED=NO
FORCE_PUSH_USED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
LEVEL_21_STARTED=NO
```

---

## Tests Added

| File | Tests | Scope |
|------|-------|-------|
| `test_multiformat_qualification.py` | 50 | Full capability matrix + real file results |
| `test_p10_phase4_qualification_gate.py` | 21 (updated) | Phase 4 gate — upgraded to PASS_REAL_STEP |
| `test_p10_step_qualification_gate.py` | 36 (3 updated) | STEP gate — updated for REAL_STEP_COUNT=6 |

---

## Final Report

```
HEAD_BEFORE=0be91e2
SCAN_ROOT=D:\makina_ogrenmesi\olcum_denemeleri

TOTAL_ENGINEERING_FILES=119

STEP_COUNT=6
STEP_PARSE_PASS_COUNT=6
STEP_PARSE_FAIL_COUNT=0
REAL_STEP_QUALIFICATION_READY=YES
P10_PHASE4_GATE=UNBLOCKED

IGES_COUNT=17
IGES_CLOSED_SOLID_COUNT=0
IGES_STATUS=TOKEN_ONLY_NO_GEOMETRY

DXF_COUNT=66
DXF_STATUS=PASS_NATIVE_2D

DWG_COUNT=3
DWG_STATUS=DEPENDENCY_MISSING

STL_COUNT=7
STL_PASS_COUNT=7
STL_STATUS=PASS_MESH_ONLY

PLY_COUNT=1
PLY_STATUS=DEPENDENCY_MISSING

PARASOLID_XT_COUNT=2
PARASOLID_STATUS=DEPENDENCY_MISSING

ACIS_SAT_COUNT=2
ACIS_STATUS=DEPENDENCY_MISSING

JT_COUNT=1
JT_STATUS=DEPENDENCY_MISSING

CATIA_MODEL_COUNT=6
CATIA_STATUS=UNSUPPORTED_PROPRIETARY

SOLIDWORKS_COUNT=1
SOLIDWORKS_STATUS=DEPENDENCY_MISSING

TOTAL_HOLE_CANDIDATES=25
AUTO_CONFIRMED_FEATURE_FOUND=NO

IS_DISPATCHABLE_TRUE_FOUND=NO
PRODUCTION_RELEASED_TRUE_FOUND=NO
REAL_SOURCE_CAD_FILE_COMMITTED=NO
REAL_SOURCE_FILE_MODIFIED=NO

NEW_TESTS_ADDED=50
RUFF_CLEAN=PENDING
NEW_FAILURES_INTRODUCED=0

FINAL_RESULT=PASS_STEP_STL_DXF__PARTIAL_IGES__DEFERRED_REMAINDER
```

---

## Remaining Blockers (by priority)

| Priority | Format | Blocker | Action Required |
|----------|--------|---------|-----------------|
| 1 | IGES | No geometry extraction | Install pythonocc-core or use gmsh IGES reader for mesh |
| 2 | DWG | No reader | libredwg / ezdxf DWG support or ODA File Converter |
| 3 | Parasolid X_T | Proprietary SDK | Parasolid licence or Open CASCADE STEP roundtrip |
| 4 | ACIS SAT | Proprietary SDK | ACIS licence or conversion via FreeCAD |
| 5 | JT | Siemens proprietary | JT Open SDK |
| 6 | CATIA .model | CATIA V4 licence | CATIA V5 upgrade or conversion |
| 7 | SolidWorks .sldprt | SDK required | SolidWorks API or eDrawings converter |
| 8 | PLY | trimesh not installed | `pip install trimesh` |
