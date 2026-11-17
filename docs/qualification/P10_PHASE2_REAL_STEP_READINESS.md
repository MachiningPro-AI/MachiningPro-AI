# P10 Phase 2 — Real STEP Qualification Readiness Report

**Document class:** Qualification Readiness Report  
**Status:** DEFERRED_REAL_STEP_SAMPLES_REQUIRED  
**Repository:** MachiningPro AI NEXT  
**Date:** 2026-11-17  
**Preceding phase:** P10 Phase 1 Pre-STEP Implementation (HEAD=7399bdc)  

---

## MUST 1 — Baseline Verification

```
BRANCH=main
HEAD=7399bdc
ORIGIN/MAIN=7399bdc
HEAD=ORIGIN=YES
WORKTREE_CLEAN=YES
```

Note: Task specification referenced HEAD=b3375cf (the commit at task-writing time).
7399bdc is the Phase 1 documentation commit that followed b3375cf; it is the legitimate
continuation. main=origin=7399bdc is the correct Phase 2 baseline.

---

## MUST 2 — Real Sample Directory Scan

Directory: `D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar`

```
REAL_STEP_SAMPLE_COUNT=0        (.stp, .step, .p21 → none found)
REAL_IGES_SAMPLE_COUNT=15       (.igs files present — surfaces, NOT closed B-Rep)
DXF_SAMPLE_COUNT=57
DWG_COUNT=3
PDF_COUNT=3
CATIA_MODEL_COUNT=6             (.model — proprietary format, cannot parse)
TOTAL_FILES=84
```

IGES files (15 present) carry B-spline/NURBS surface data. They do NOT provide:
- Closed B-Rep solid bodies
- Confirmed feature depth evidence
- Volumetric stock geometry

IGES is therefore **not a substitute** for STEP at the P10 gate. The 6 CATIA `.model`
files require a CATIA licence to parse and are excluded entirely.

**REAL_STEP_SAMPLE_COUNT=0 — no STEP samples available.**

---

## MUST 3 — STEP Adapter and Parser Architecture Audit

### Stage 4C Token Adapter

**File:** `backend/interoperability/adapters/step.py`

| Layer | Implementation | Dependency | Status |
|-------|---------------|------------|--------|
| Level 0 — RECOGNIZE | `StepTokenAdapter.can_handle()` | None (pure Python) | IMPLEMENTED |
| Level 1 — PARSE | `_parse_step_header()` — ISO-10303-21 header, section inventory, AP version, entity count | None (pure Python) | IMPLEMENTED |
| Level 2 — NORMALIZE | `_normalize_geometry()` — OCCT STEPControl_Reader, B-Rep shape transfer | `pythonocc-core` | BLOCKED (not installed) |

```
STEP_ADAPTER_EXISTS=YES          (backend/interoperability/adapters/step.py)
STEP_ADAPTER_LEVEL_1=IMPLEMENTED
STEP_ADAPTER_LEVEL_2=BLOCKED     (pythonocc-core not installed)
OCCT_AVAILABLE=NO
MAX_CAPABILITY_LEVEL=LEVEL_1_PARSED
```

### P10-B Intake Gate

**File:** `backend/cad_import/step_intake.py`

```
STEP_INTAKE_GATE_EXISTS=YES
STEP_IMPORT_READY=False
BREP_TOPOLOGY_READY=False
FEATURE_EXTRACTION_READY=False
REAL_STEP_SAMPLE_COUNT=0
```

4-stage gate: extension → existence → size → parser availability.
When no parser is installed, any file that passes extension+existence+size checks
returns `DEFERRED_NO_PARSER` (not PASS, not geometry).

---

## MUST 4 — Fail-Closed Import Verification

Verified behavior:

| Input | Expected | Actual |
|-------|----------|--------|
| File with `.dxf` extension | REJECTED_WRONG_EXTENSION | REJECTED_WRONG_EXTENSION ✓ |
| File with `.igs` extension | REJECTED_WRONG_EXTENSION | REJECTED_WRONG_EXTENSION ✓ |
| Non-existent `.stp` path | REJECTED_FILE_NOT_FOUND | REJECTED_FILE_NOT_FOUND ✓ |
| Existing `.stp` file, no parser | DEFERRED_NO_PARSER | DEFERRED_NO_PARSER ✓ |
| ISO-10303-21 content, no OCCT | normalization_status=SUCCESS (Level 1) | SUCCESS ✓ |
| Non-STEP content (`notes` field) | normalization_status=FAILED | FAILED ✓ |

`is_qualified=False` for all DEFERRED_NO_PARSER results.
`part_bbox_min=None` and `part_bbox_max=None` for all results (never fabricated).

FAIL_CLOSED_VERIFIED=YES

---

## MUST 5 — B-Rep Topology Pipeline Readiness

**File:** `backend/interoperability/topology.py` (Stage 4B)

Stage 4B provides **data models only** — no kernel, no manifold proof, no Boolean ops,
no feature recognition. The topology container (`CanonicalTopology`) stores:

```
CanonicalVertex   → Point3D reference
CanonicalEdge     → Curve reference + start/end vertex
CanonicalLoop     → ordered edges (boundary loop)
CanonicalFace     → Surface reference + outer/inner loops
CanonicalShell    → faces + closure type (OPEN/CLOSED/UNKNOWN)
CanonicalBody     → shells + body type
CanonicalTopology → bodies container
```

Architecture position:
```
SOURCE STEP FILE
    ↓
StepTokenAdapter (Level 2, requires pythonocc-core)  ← BLOCKED
    ↓
CanonicalGeometry + CanonicalTopology                ← POPULATED (once Level 2 runs)
    ↓
feature_recognition.py (Level 3)                     ← BLOCKED without topology
    ↓
ManufacturingFeature (HOLE_CONFIRMED, POCKET_CONFIRMED, ...)
```

```
TOPOLOGY_DATAMODELS_AVAILABLE=YES    (topology.py imports without kernel)
TOPOLOGY_POPULATED=NO               (no STEP file has been parsed at Level 2)
BREP_TOPOLOGY_READY=NO
```

---

## MUST 6 — Manufacturing Feature Pipeline Readiness

**File:** `backend/interoperability/feature_recognition.py`

Recognition paths:

| Path | Input | Feature status | Current activation |
|------|-------|---------------|-------------------|
| TOPOLOGY | CanonicalTopology + CanonicalGeometry | CONFIRMED possible | BLOCKED (no STEP Level 2) |
| GEOMETRY_ONLY | 3D geometry, no topology | CANDIDATE only | BLOCKED (no STEP Level 2) |
| 2D_GEOMETRY_ONLY | DXF 2D drawing | CANDIDATE only (DXF circle → hole candidate) | ACTIVE (DXF pipeline) |
| NONE | No geometric data | Empty result | Fallback |

Confirmation rules require **TOPOLOGY path**:

| Feature | Required evidence |
|---------|------------------|
| HOLE_CONFIRMED | Cylindrical face + ≥1 bounding planar face + inner circular loop sharing cylinder axis |
| POCKET_CONFIRMED | Planar floor + ≥2 wall faces + inner boundary loop |
| SLOT_CONFIRMED | 2 parallel planar walls + floor + 2 end faces, AR > 1.5 |
| CHAMFER_CONFIRMED | Conical face between 2 planar faces, 15° ≤ θ ≤ 75° |
| FILLET_CONFIRMED | Cylindrical/toroidal face tangent to 2 planar faces |

```
FEATURE_PIPELINE_EXISTS=YES        (feature_recognition.py imports cleanly)
FEATURE_CONFIRMATION_POSSIBLE=NO   (topology path blocked; DXF produces CANDIDATE only)
FEATURE_EXTRACTION_READY=NO
```

---

## MUST 7 — Feature Provenance Requirements

A manufacturing feature can reach `CONFIRMED` status ONLY when:

1. **Source format** provides full B-Rep topology: STEP (AP203/AP214/AP242)
2. **Topology path** (`recognize_features(path="TOPOLOGY")`) processes populated
   `CanonicalTopology` and `CanonicalGeometry`
3. **Geometric evidence** is deterministic: cylindrical face ID, axis vector, radius,
   bounding planar face IDs, inner loop entity ID — all traceable to the STEP file
4. **Provenance field** = `STEP_FILE_EVIDENCE` (not `USER_CONFIRMED`, not `INFERRED`,
   not `UNKNOWN`)

The existing DXF pipeline can only produce `CANDIDATE` features because:
- DXF circles have no depth evidence
- DXF closed polylines have no wall faces
- 2D geometry alone cannot satisfy the TOPOLOGY confirmation rules

**FEATURE_PROVENANCE_PATH**: STEP_FILE_EVIDENCE requires STEP Level 2 → BLOCKED

---

## MUST 8 — Real 3D CAM Chain Readiness

From `_3d_pipeline_readiness()` in `backend/cad_import/step_intake.py`:

| Stage | Status | Blocker |
|-------|--------|---------|
| STEP_IMPORT | NOT_IMPLEMENTED | cadquery/pythonocc-core not installed |
| BREP_TOPOLOGY | NOT_IMPLEMENTED | Requires STEP_IMPORT |
| SOLID_CLASSIFIER | NOT_IMPLEMENTED | Requires BREP_TOPOLOGY |
| FEATURE_EXTRACTION | NOT_IMPLEMENTED | Requires BREP_TOPOLOGY |
| ROUTE_GENERATION_3D | NOT_IMPLEMENTED | Requires FEATURE_EXTRACTION |
| MACHINE_SELECTION_3D | PARTIAL | DXF-based classification exists |
| TOOL_SELECTION_3D | PARTIAL | DXF + catalog matching exists |
| CAM_STRATEGY_3D | PARTIAL | Routing engine has 3D-aware branch (depth from DXF annotation only) |
| TOOLPATH_3D | PARTIAL | Toolpath generator can produce 3D segments; Z from DXF only |
| VERIFICATION_3D | PARTIAL | Voxel approximation; GOUGE=NOT_VERIFIABLE |
| SIMULATION_3D | PARTIAL | VOXEL_APPROXIMATION; no exact Boolean |

```
3D_CAM_CHAIN_READY=NO
STEPS_BLOCKED=5 (STEP_IMPORT, BREP_TOPOLOGY, SOLID_CLASSIFIER, FEATURE_EXTRACTION, ROUTE_GENERATION_3D)
STEPS_PARTIAL=6 (downstream stages that can run on DXF inputs)
```

---

## MUST 9/10 — Sample Intake Recommendations

See `docs/qualification/P10_REAL_STEP_SAMPLE_INTAKE.md` for the full sample specification.

**Minimum first intake: 2 files (3 strongly recommended)**

| Sample | Type | Mandatory | Key features |
|--------|------|-----------|-------------|
| P10-S1 | Simple drilled plate | YES | 1 through-hole + 1 blind hole (Ø8–12 mm) |
| P10-S2 | Prismatic pocket+slot | YES | Pocket depth > 10 mm, slot AR > 1.5 |
| P10-S3 | Turning part | Recommended | Cylindrical body, groove, chamfer |

**Acquisition path:** FreeCAD in-house design (preferred) or CC0 public domain.
No proprietary downloads.

---

## MUST 11 — Qualification Test Harness

**File:** `tests/unit/interoperability/test_p10_step_qualification_gate.py`

```
TEST_COUNT=36
TESTS_PASS=36
TEST_FIXTURE_ONLY=YES  (no fabricated geometry; minimal ISO-10303-21 header strings)
REAL_GEOMETRY_FABRICATED=NO
IS_DISPATCHABLE_TRUE_IN_TESTS=NO
PRODUCTION_RELEASED_TRUE_IN_TESTS=NO
```

Test categories:
- A: Pipeline readiness constants (REAL_STEP_SAMPLE_COUNT=0, STEP_IMPORT_READY=False, …)
- B: Live filesystem scan of real sample directory (STEP files found = 0)
- C: Fail-closed intake gate (REJECTED_WRONG_EXTENSION, REJECTED_FILE_NOT_FOUND, DEFERRED_NO_PARSER)
- D: StepTokenAdapter Level 0–1 (pure Python; OCCT not available; FAILED on invalid magic)
- E: STEP_DESCRIPTORS coverage (AP203, AP214, AP242)
- F: 3D pipeline readiness constants (NOT_IMPLEMENTED / PARTIAL per stage)
- G: Topology + feature data model imports without geometry kernel
- H: REAL_STEP_QUALIFICATION_READY=NO gate

---

## MUST 12 — REAL_STEP_QUALIFICATION_READY Gate Definition

```
REAL_STEP_QUALIFICATION_READY = YES  requires ALL of:
  [1] pythonocc-core OR cadquery installed
  [2] REAL_STEP_SAMPLE_COUNT >= 3  (P10-S1 + P10-S2 mandatory; P10-S3 recommended)
  [3] StepTokenAdapter Level 2 OR cadquery ingest returns part solid (not Level 1 only)
  [4] At least 1 HOLE_CONFIRMED from B-Rep topology (FeatureStatus.CONFIRMED, not CANDIDATE)
  [5] Part bounding box derived from B-Rep (provenance=STEP_FILE_EVIDENCE, not UNKNOWN)
  [6] GOUGE_VALIDATED exits NOT_VERIFIABLE (PASS or FAIL on at least 1 candidate)
  [7] is_dispatchable=False and production_released=False maintained

Current status:
  [1] BLOCKED
  [2] BLOCKED (count=0)
  [3] BLOCKED
  [4] BLOCKED
  [5] BLOCKED
  [6] BLOCKED
  [7] PASS (enforced unconditionally)

REAL_STEP_QUALIFICATION_READY=NO
```

---

## MUST 13 — Tool Geometry Status

**Catalog size:** 60 tools (expanded from 18 drills/mills in P9 scope)

The P10 flute-length gap report covers tools relevant to the **holemaking qualification
workflow** (Levels 7–9: hole depth validation, tool reach check):

```
UNSUPPORTED_TOOL_GEOMETRY_COUNT=9
  Kennametal B221A: 6 records
    kennametal-b221a-0300-cfh  (Ø3.0 mm)
    kennametal-b221a-0400-cfh  (Ø4.0 mm)
    kennametal-b221a-0500-cfh  (Ø5.0 mm)
    kennametal-b221a-0600-cfh  (Ø6.0 mm)
    kennametal-b221a-0800-cfh  (Ø8.0 mm)
    kennametal-b221a-1200-cfh  (Ø12.0 mm)
  Walter Titex DC150: 3 records
    walter-titex-dc150-05-05000a1-wj30et  (Ø5.0 mm)
    walter-titex-dc150-06-06000a1-wj30et  (Ø6.0 mm)
    walter-titex-dc150-08-08000a1-wj30et  (Ø8.0 mm)

SOURCEABLE_NOW_COUNT=9
  Kennametal B221A flute data: kennametal.com product page
  Walter Titex DC150 flute data: walter-tools.com product page
```

Note: The full catalog has 47 tools without `flute_length_mm`, but most are intentionally
N/A (turning inserts, face mill inserts, taps, grinding wheels, EDM electrodes) where
`flute_length_mm` is not an applicable geometry field. The 9 above are the drills/end
mills where the gap blocks holemaking depth validation.

---

## MUST 14 — DXF-02 Boring Deferred

```
DXF02_STATUS=DEFERRED_CAPABILITY_GAP
DXF02_ADVANCED_HOLEMAKING_BLOCKER=BORING_CAM+TOOLPATH
```

**Exact blockers:**

1. **Tool geometry gap**: DXF-02 requires a boring head or boring bar for Ø60 mm bore.
   - `sandvik-a25t-sducr-11` (CoroTurn 107) exists in catalog with
     `supported_operations=['boring']` and `tool_category='Boring Bar'`.
   - This is a **turning-style** boring bar, not a milling boring head.
   - It has `cutting_diameter_mm=None` — not 60 mm — so there is no diameter match.

2. **Toolpath generation gap**: No `generate_boring_toolpath()` function exists.
   The DXF pipeline can generate drilling toolpaths (Z-axis feed) but not the
   interpolated circular feed motion required for boring.

3. **CAM strategy gap**: No boring operation type in `CAM_STRATEGY` / `OperationType`
   enum that maps DXF circle → boring cycle (G76 or equivalent).

**Resumption condition:** Boring unblocks when:
- A milling-type boring head is added to the catalog with the correct `cutting_diameter_mm`
- `generate_boring_toolpath()` is implemented
- DXF-02 circle entity with Ø60 mm is mapped to `OperationType.BORING`

---

## MUST 15 — Safety Search

Searched all `backend/**/*.py` for `is_dispatchable=True` and `production_released=True`.

| Search | Hits | Type | Safe? |
|--------|------|------|-------|
| `is_dispatchable` + `True` | 2 | Comment/docstring + error message | YES (false positives) |
| `production_released` + `True` | 0 | — | YES |

```
IS_DISPATCHABLE_TRUE_FOUND=NO      (hits are documentation strings only)
PRODUCTION_RELEASED_TRUE_FOUND=NO
SAFETY_INVARIANTS_INTACT=YES
```

---

## MUST 16 — Source Integrity

```
ALL_EXISTING_REAL_SAMPLE_FILES_UNCHANGED=YES
REAL_STEP_SAMPLE_FILES_COMMITTED=NO       (none exist — nothing to commit)
DXF_FILES_MODIFIED_BY_THIS_SESSION=NO
IGES_FILES_MODIFIED_BY_THIS_SESSION=NO
SYNTHETIC_STEP_CALLED_REAL=NO
FABRICATED_BREP_TOPOLOGY=NO
FABRICATED_FEATURES=NO
FABRICATED_DEPTHS=NO
FABRICATED_TOLERANCES=NO
FABRICATED_MATERIAL=NO
FABRICATED_STOCK=NO
FABRICATED_FIXTURE=NO
FABRICATED_HOLDER=NO
```

The test harness uses minimal ISO-10303-21 header strings (TEST_FIXTURE) for
token-parser testing only. These are explicitly labelled as fixtures, not real samples,
and do not create any `CanonicalGeometry` or `CanonicalTopology` objects.

---

## Summary Table

| MUST | Check | Result |
|------|-------|--------|
| MUST 1 | Baseline HEAD=origin=7399bdc, clean tree | PASS |
| MUST 2 | REAL_STEP_SAMPLE_COUNT=0 | CONFIRMED |
| MUST 3 | STEP adapter Level 1 implemented; Level 2 BLOCKED | CONFIRMED |
| MUST 4 | Fail-closed: DEFERRED/REJECTED/FAILED for all non-STEP inputs | PASS |
| MUST 5 | Topology data models available; pipeline BLOCKED without STEP | CONFIRMED |
| MUST 6 | Feature pipeline exists; CONFIRMATION blocked; CANDIDATE only | CONFIRMED |
| MUST 7 | STEP_FILE_EVIDENCE provenance required for CONFIRMED features | DOCUMENTED |
| MUST 8 | 3D CAM chain: 5 NOT_IMPLEMENTED, 6 PARTIAL | CONFIRMED |
| MUST 9 | P10_REAL_STEP_SAMPLE_INTAKE.md created | DONE |
| MUST 10 | Minimum intake: 2–3 STEP files (P10-S1, P10-S2, P10-S3) | DOCUMENTED |
| MUST 11 | Test harness: 36 PASS, no fabricated geometry | DONE |
| MUST 12 | REAL_STEP_QUALIFICATION_READY=NO — 6/7 gates BLOCKED | CONFIRMED |
| MUST 13 | 9 tools without flute_length_mm; SOURCEABLE_NOW=YES | CONFIRMED |
| MUST 14 | DXF-02 boring: BORING_CAM+TOOLPATH blocker | CONFIRMED |
| MUST 15 | IS_DISPATCHABLE_TRUE=NO, PRODUCTION_RELEASED_TRUE=NO | PASS |
| MUST 16 | All real sample files unchanged; no fabricated content | PASS |

---

## Final Result

```
FINAL_RESULT=DEFERRED_REAL_STEP_SAMPLES_REQUIRED

FINAL_RESULT_REASON:
  REAL_STEP_SAMPLE_COUNT=0 — no .stp/.step/.p21 files in sample directory.
  STEP parser (cadquery / pythonocc-core Level 2) not installed.
  Speculative STEP implementation is NOT created per hard rule:
    "If no real STEP exists: DO NOT implement speculative STEP behavior
     merely to obtain PASS."
  P10 phase 2 produces a precise acquisition/readiness report only.

IS_DISPATCHABLE=ALWAYS_FALSE (enforced unconditionally)
PRODUCTION_RELEASED=ALWAYS_FALSE (enforced unconditionally)
NO_TAG=YES
NO_RELEASE=YES
NO_FORCE_PUSH=YES
DO_NOT_START_LEVEL_21=YES
```

---

## Next Steps

1. **Acquire STEP samples**: Design P10-S1 and P10-S2 in FreeCAD or source CC0 files.
2. **Install cadquery**: After samples confirmed in directory (not before).
3. **Re-run intake gate**: `scan_step_samples()` on real sample directory.
4. **Update constants**: `STEP_IMPORT_READY = True` in `step_intake.py` once cadquery works.
5. **Run P10 Phase 3**: Wire `accept_step_file()` → `build_verification_input()` →
   `part_bbox` → `GOUGE_VALIDATED` exits NOT_VERIFIABLE.
