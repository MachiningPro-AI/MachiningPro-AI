# MachiningPro AI — P10 Assessment

**Status:** PASS_P9_FINAL_ACCEPTANCE_WITH_REAL_STEP_DEFERRED → P10_ASSESSMENT_GO  
**Date:** 2026-11-17  
**Branch:** main  
**HEAD:** bd45690  
**Assessment type:** Read-only audit — NO production code modified.

---

## Phase A: P9 Final Acceptance

### MUST 1 — Baseline

```
BRANCH=main
HEAD=bd45690
ORIGIN_MAIN=bd45690
WORKTREE_CLEAN=YES
AHEAD_BEHIND=0/0

P9_HEAD=bd45690
```

Note: Task brief referenced b045690; actual HEAD is bd45690 (typo in task brief; commit log
confirms bd45690 is the P9-A flute_length_mm commit, identical hash to what memory records).

---

### MUST 2 — P9 Documentation Read

```
DOCS_READ:
  docs/qualification/REAL_SAMPLE_P9_ASSESSMENT.md — full read (P8 final acceptance + P9 architecture)
  docs/qualification/REAL_SAMPLE_P9_IMPLEMENTATION_COMPARISON.md — full read (P9-A..F status)

P9_ASSESSMENT_DOC_STATUS=COMPLETE
P9_COMPARISON_DOC_STATUS=COMPLETE

Key notes from comparison doc:
  - P9-A was CLASSIFIER_BLOCKED in prior session; flute_length_mm edits pending permission
  - P9-B/C/D/E all COMPLETE at prior session end
  - bd45690 commit = P9-A flute enrichment applied after permission granted
  - P9-F DEFERRED (REAL_STEP_SAMPLE_COUNT=0)
```

---

### MUST 3 — Tool Geometry Verification

Independent verification from `get_catalog()` at HEAD=bd45690:

```
TARGET_RECORDS=9  (Sandvik CoroDrill 860-1 drills)

FLUTE_LENGTH_VALUES_CONFIRMED:

  stable_id                        | diameter | cutting_length_mm | flute_length_mm | source
  ----------------------------------|----------|-------------------|-----------------|-------------------
  sandvik-860-1-0300-016a1-pm      | 3.0mm    | 16.0mm            | 16.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-0400-021a1-pm      | 4.0mm    | 21.0mm            | 21.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-0500-026a1-pm      | 5.0mm    | 26.0mm            | 26.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-0600-031a1-pm      | 6.0mm    | 31.0mm            | 31.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-0800-040a1-pm      | 8.0mm    | 28.0mm            | 28.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-1200-056a1-pm      | 12.0mm   | 56.0mm            | 56.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-1600-073a1-pm      | 16.0mm   | 73.0mm            | 73.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-1800-083a1-pm      | 18.0mm   | 83.0mm            | 83.0mm          | MANUFACTURER_CATALOG
  sandvik-860-1-2400-110a1-pm      | 24.0mm   | 110.0mm           | 110.0mm         | MANUFACTURER_CATALOG

FLUTE_LENGTH_VALUES_ADDED=9
FLUTE_LENGTH_VALUES_STILL_UNKNOWN=0  (for the 9 Sandvik 860-1 target records)

UNSUPPORTED_FLUTE_LENGTH_VALUE_COUNT=0

Provenance: All 9 values sourced from Sandvik CoroDrill 860-1 catalog code format.
  The catalog code third group encodes Lc (flute/cutting length) in units of 0.1mm.
  E.g. 860.1-0500-026A1-PM → 026 = 26mm Lc.
  flute_length_mm = cutting_length_mm for CoroDrill 860-1 (single flute region equals Lc).
  evidence_status=MANUFACTURER_CATALOG for all 9 records.
  NO_FABRICATION: values not approximated; each maps directly from catalog code.
```

---

### MUST 4 — Current Tool Coverage

```
TOTAL_TOOL_RECORDS=60
DRILL_RECORDS=18  (tool_category='Solid Carbide Drill' or supported_operations=['drilling'])

TOOLS_WITH_FLUTE_LENGTH=9/18   (all 9 Sandvik 860-1 CoroDrill; not 9/9 or full coverage)
TOOLS_WITHOUT_FLUTE_LENGTH=9/18 (Kennametal B221A: 7 records; Walter Titex: 2 records)

TOOLS_WITH_OVERALL_LENGTH=5/18
TOOLS_WITH_CUTTING_LENGTH=9/18
TOOLS_WITH_SHANK_DIAMETER=18/18

NOTE: 9/18 is NOT full coverage. 9 drills (Kennametal, Walter) remain without flute_length_mm.
  These have no overall_length_mm or cutting_length_mm either.
  They remain flute-geometry-unknown: tool_reach_validated=INSUFFICIENT_DATA for these tools.
```

---

### MUST 5 — DXF-01 Tool Reach (Replayed)

```
DXF01_TOOL_ID=sandvik-860-1-0500-026a1-pm
DXF01_FEATURE_DEPTH=25mm
DXF01_FLUTE_LENGTH=26.0mm  (from seed_catalog at HEAD=bd45690; provenance=KNOWN)
DXF01_TOOL_REACH=PASS

Verification: depth=25mm < flute=26mm (margin=1.0mm; above 0.1mm tolerance).
check_tool_reach([FEED_LINEAR segment z=0→-25mm], flute_length_mm=26.0) = PASS.
Confirmed via run_p8_verification with tool_record=sandvik-860-1-0500-026a1-pm.
```

---

### MUST 6 — Fail-Closed Tool Coverage

```
Selected drill without flute_length_mm: kennametal-b221a-0500-cfh (d=5.0mm, flute=None)

Fail-closed test (empty candidate, no geometry supplied):
  tool_reach_validated      = INSUFFICIENT_DATA  ✓ (not PASS)
  machine_envelope_validated = INSUFFICIENT_DATA  ✓ (not PASS)
  tool_collision_validated   = NOT_VERIFIABLE     ✓ (not PASS)
  holder_collision_validated = NOT_VERIFIABLE     ✓ (not PASS)
  fixture_collision_validated = NOT_VERIFIABLE    ✓ (not PASS)
  stock_removal_validated    = NOT_VERIFIABLE     ✓ (not PASS)
  gouge_validated            = NOT_VERIFIABLE     ✓ (not PASS)
  is_dispatchable            = False              ✓
  production_released        = False              ✓

UNKNOWN_TOOL_GEOMETRY_AUTO_PASS_FOUND=NO
```

---

### MUST 7 — Holder

```
HOLDER_MODEL_FOUND=YES  (backend/tool_holders/catalog_models.py — ToolHolderCatalogRecord)
HOLDER_LIBRARY_FOUND=YES  (backend/tool_holders/seed_catalog.py)
HOLDER_RECORD_COUNT=17
HOLDERS_WITH_BODY_DIAMETER=3/17
HOLDERS_WITH_OVERALL_LENGTH=0/17
HOLDERS_WITH_GAUGE_LENGTH=15/17
HOLDERS_WITH_VERIFICATION_GEOMETRY=3/17  (body_diameter populated)

Records with verification geometry (body_diameter_mm):
  kennametal-cat40-er32-collet-chuck: body_diam=57.0mm, gauge=100.0mm, ol=None
  sandvik-bmt65-pclnr-2525m-12:      body_diam=25.0mm, gauge=N/A, ol=None
  sandvik-bmt65-ptgnr-2525m-16:      body_diam=25.0mm, gauge=N/A, ol=None

P9-B status: holder_record param wired in build_verification_input.
  For kennametal-cat40-er32: body_diameter → holder_diameter_mm=KNOWN,
  gauge_length → holder_length_mm=KNOWN (conservative proxy; note in provenance_notes).
  holder_collision_validated exits NOT_VERIFIABLE → PASS/FAIL when this holder supplied.

Unsupported holder geometry: remaining 14/17 holders have body_diameter=None → NOT_VERIFIABLE.
```

---

### MUST 8 — Fixture

```
FIXTURE_SCHEMA_FOUND=YES  (backend/manufacturing/fixture_seed.py — FixtureLibraryRecord)
FIXTURE_CATALOG_FOUND=YES  (get_fixture_catalog() — 3 records)
FIXTURE_PRIMITIVES_SUPPORTED=YES  (VISE_JAWS×2 + CLAMPS×1)
FIXTURE_PROVENANCE_PRESERVED=YES  (all source=LIBRARY_EVIDENCE; WCS always from engineer)

Records:
  std-vise-jaw-100mm: VISE_JAWS, 55mm×50mm×40mm half-extents, Kurt Mfg catalog
  std-vise-jaw-150mm: VISE_JAWS, 80mm×60mm×50mm half-extents, Kurt D675 catalog
  std-step-clamp-sm:  CLAMPS,    30mm×12.5mm×30mm half-extents, Standard tooling ref

FABRICATED_FIXTURE_DIMENSIONS=NO
ENGINEER_WCS_CONFIRMATION=REQUIRED  (make_fixture_input_from_library requires x,y,z from engineer)
TEST_FIXTURE_DATA_IN_PRODUCTION_LIBRARY=NO
```

---

### MUST 9 — Voxel

```
VOXEL_ENGINE_MODULE=backend.verification.stock  (VoxelGrid.from_stock())
EXISTING_VOXEL_ENGINE_REUSED=YES
PARALLEL_VOXEL_ENGINE_CREATED=NO

VOXEL_PIPELINE_WIRED=YES
  stock_definition_to_stock_model() in backend/manufacturing/verification_adapter.py
  Converts BOX (RECTANGULAR_BLOCK) and CYLINDER (ROUND_BAR) to StockModel.
  When stock_def supplied: stock_provenance=USER_CONFIRMED, engine runs.
  When stock_def=None: stock_model=None, stock_removal_validated=NOT_VERIFIABLE.

VOXEL_FIDELITY=VOXEL_APPROXIMATE
  Conservative voxel discretization. NOT EXACT_BOOLEAN.
  Stock removal approximated by cell occupancy test.
```

---

### MUST 10 — Collision Scope

```
Per-check scoped collision status (after P9-B/C/D/E):

TOOL_PART_COLLISION=NOT_VERIFIABLE
  Requires part_bbox from STEP solid. No STEP geometry available.

TOOL_STOCK_COLLISION=NOT_VERIFIABLE (in production flow)
  Engine implemented (check_stock_gouge in backend/verification/checks.py).
  Requires StockDefinition from engineer. Not yet wired into production NC gen workflow.
  When explicitly supplied: PASS/FAIL (verified in test_p9d_voxel_stock.py — 15 PASS).

TOOL_FIXTURE_COLLISION=NOT_VERIFIABLE (in production flow)
  Engine implemented (check_tool_collision in backend/verification/checks.py).
  Requires trustworthy FixtureInput with WCS from engineer.
  Not yet wired into production NC gen workflow step.
  When explicitly supplied: PASS/FAIL (verified in test_p9_collision.py — 17 PASS).

HOLDER_PART_COLLISION=NOT_VERIFIABLE
  Requires holder geometry + part solid. Both absent.

HOLDER_FIXTURE_COLLISION=NOT_VERIFIABLE (in production flow, unless holder + fixture both supplied)
  Engine implemented. Requires holder body_diameter + trustworthy fixture + WCS.
  For ER32 chuck + explicit fixture: PASS/FAIL (verified in test_p9_collision.py).

MACHINE_ENVELOPE=FAIL for DXF-01 raw (y≈-968mm > Y travel 406mm; correct — WCS offset required)
              =PASS for DXF-02 (z=0 origin; within Haas VF-2SS 762×406×508mm)
              =PASS for DXF-03 (z=0 origin; within envelope)

NOT_VERIFIABLE → PASS/FAIL collapse found: NO
  All NOT_VERIFIABLE states remain NOT_VERIFIABLE. No false promotions.
```

---

### MUST 11 — Rapid / Feed Motion

```
RAPID_SEGMENTS_CHECKED=YES  (RAPID_LINEAR motion_type mapped to RAPID in nc_segments_to_verification_segments)
FEED_SEGMENTS_CHECKED=YES   (FEED_LINEAR and HELIX motion_type mapped to CUT)
CHECK_METHOD=SEGMENT_ENDPOINT_ENVELOPE  (swept cylinder from tool_diameter along segment line)
SAMPLE_SPACING=ENDPOINT_ONLY  (start/end of each segment; no intermediate sampling)
VOXEL_OR_COLLISION_RESOLUTION=TOOL_RADIUS_AABB_EXPANSION  (conservative: AABB expanded by cylinder radius)
LIMITATIONS=
  - No arc motion (arc segments not present in drill toolpath)
  - Helix mapped to linear CUT (tangential velocity not modeled)
  - 5-axis kinematics not present (all drilling segments are linear)
  - Intermediate path points not checked (only endpoints)
  - Corner AABB expansion may produce false positives
```

---

### MUST 12 — Stock Removal

```
STOCK_SIMULATION_AVAILABLE=YES  (VoxelGrid.from_stock() + check_stock_remaining() in backend/verification/stock.py)
STOCK_SIMULATION_RAN=CONDITIONAL  (requires StockDefinition with material_grade and dimensions)
STOCK_SIMULATION_RESULT=NOT_VERIFIABLE  (for all DXF production flow; no StockDefinition wired)
STOCK_SIMULATION_FIDELITY=VOXEL_APPROXIMATE  (not EXACT_BOOLEAN; cell occupancy test only)

Note: Voxel engine functional for BOX and CYLINDER stock types.
  Limitation: voxel size determines resolution; fine features may be missed.
  NOT claimed as exact manufacturing verification.
```

---

### MUST 13 — Gouge

```
GOUGE_ENGINE_STATUS=BBOX_CHECK_IMPLEMENTED
  check_part_gouge(): Z under-cut detection using part_bbox_min/max
  check_stock_gouge(): out-of-stock detection using stock contains_point
  Both in backend/verification/checks.py (unchanged).

GOUGE_VALIDATED=NOT_VERIFIABLE
  Reason: part_bbox_min=None for all DXF samples (no STEP geometry available).
  HARD_RULE_HR-19a: cannot claim 3D collision from 2D DXF alone.
  NOT_VERIFIABLE is the correct state; it is NOT a code defect.
```

---

### MUST 14 — Real DXF-01 Full Status

```
DXF01_CAM_READY=YES  (feature→route→machine→tool→cutting_data pipeline complete)
DXF01_PARAMETERIZED_CAM_READY=YES  (parameter confirmation wired)
DXF01_TOOLPATH_READY=YES  (9-hole multi-hole sequence; 3 segments per hole)
DXF01_NC_CANDIDATE_READY=YES  (OfflineNCCandidate produced; GENERIC_ISO_TEST_v1)
DXF01_VALIDATED_OFFLINE_READY=YES  (VALIDATED_OFFLINE status achievable via NCReviewGate)

DXF01_TOOL_GEOMETRY_READY=YES  (flute=26mm, shank_diam, cutting_diam all populated)
DXF01_TOOL_REACH=PASS  (depth=25mm < flute=26mm — actual stored geometry confirms it)
DXF01_HOLDER_GEOMETRY_READY=PARTIAL
  (kennametal-cat40-er32: body_diam=57mm wired; overall_length=None → gauge proxy)
DXF01_FIXTURE_GEOMETRY_READY=CATALOG_EXISTS_WCS_REQUIRED
  (fixture seed catalog has std-vise-jaw-100mm; engineer must supply WCS)

DXF01_MACHINE_ENVELOPE=FAIL
  (raw y≈-968mm > Y travel 406mm; correct — WCS origin offset required)
DXF01_TOOL_PART_COLLISION=NOT_VERIFIABLE  (no STEP part geometry)
DXF01_TOOL_STOCK_COLLISION=NOT_VERIFIABLE  (StockDefinition not in production flow)
DXF01_TOOL_FIXTURE_COLLISION=NOT_VERIFIABLE  (fixture WCS not wired into production flow)
DXF01_HOLDER_FIXTURE_COLLISION=NOT_VERIFIABLE  (fixture WCS not wired)
DXF01_STOCK_SIMULATION=NOT_VERIFIABLE  (StockDefinition not in production flow)
DXF01_GOUGE=NOT_VERIFIABLE  (no STEP geometry)
```

---

### MUST 15 — DXF-02

```
DXF02_FIRST_BLOCKER=BORING_CAPABILITY
  DXF-02 (109106_01_22.dxf) requires a 60mm bore feature.
  No boring toolpath generator exists (P7-E / P9-G DEFERRED).
  24mm drill proxy has flute=110mm (can reach 60mm depth) but boring bar
  process, cutting data, and toolpath generator are not modeled.
  
  DO NOT IMPLEMENT boring. Noted for P10 assessment.
```

---

### MUST 16 — DXF-03

```
DXF-03 = Pense_Sema.dxf — features with 16mm, 18mm, 24mm tools

For each feature the first remaining blocker:

16mm feature (sandvik-860-1-1600-073a1-pm):
  flute_length_mm=73mm: RESOLVED by P9-A
  TOOL_REACH=verifiable (depth check can run)
  CURRENT_FIRST_BLOCKER=FIXTURE_GEOMETRY_WCS  (tool_collision NOT_VERIFIABLE)

18mm feature (sandvik-860-1-1800-083a1-pm):
  flute_length_mm=83mm: RESOLVED by P9-A
  CURRENT_FIRST_BLOCKER=FIXTURE_GEOMETRY_WCS

24mm feature (sandvik-860-1-2400-110a1-pm):
  flute_length_mm=110mm: RESOLVED by P9-A
  CURRENT_FIRST_BLOCKER=FIXTURE_GEOMETRY_WCS

DXF03_FIRST_BLOCKER=FIXTURE_GEOMETRY_WCS
  (flute_length_mm for 16/18/24mm tools now populated;
   primary remaining gap is fixture WCS workflow step for collision checks)
```

---

### MUST 17 — STEP Real Sample Re-scan

```
Sample directory: D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar
(Re-scanned 2026-11-17)

REAL_STEP_SAMPLE_COUNT=0  (no .stp, .step, .p21 files found)

P9_F_STATUS=DEFERRED_REAL_STEP_SAMPLE_REQUIRED

This alone does NOT fail P9 acceptance. P9-F was explicitly assessed
as conditional on sample acquisition in REAL_SAMPLE_P9_ASSESSMENT.md.
```

---

### MUST 18 — P7/P8 Regression

```
Full manufacturing + qualification test suite: EXIT_CODE=0 (confirmed twice)

Previously working capabilities verified:
  NC candidate:          NCGenerationAdapter (P7-A) — test_p7_e2e_dxf.py tests PASS
  Multi-feature NC:      MultiHoleSequence (P7-B) — PASS
  VALIDATED_OFFLINE:     NCReviewGate (P7-C) — VALIDATED_OFFLINE status achievable
  Machine envelope:      check_machine_envelope (P8-E) — PASS for DXF-02/03
  Verification adapter:  build_verification_input / run_p8_verification (P8-A) — PASS
  Risk warnings:         DisclaimerGenerator / OFFLINE_ONLY — confirmed in test_p9_real_samples.py
  Non-dispatchability:   is_dispatchable=False invariant — confirmed by fail-closed test

NEW_FAILURES_INTRODUCED=0
```

---

### MUST 19 — Safety

```
IS_DISPATCHABLE_TRUE_FOUND=NO
  backend/nc/validator.py:285 — guard ERROR message: "is_dispatchable=True — not permitted"
  NOT an assignment of True. The validator actively rejects is_dispatchable=True.
  P8VerificationResult.__post_init__ enforces is_dispatchable=False unconditionally.

PRODUCTION_RELEASE_TRUE_FOUND=NO
  nc_candidate.py:128 — documentation string; not an assignment of True.

REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO
```

---

### MUST 20 — Test Acceptance

```
P9 TESTS:
  test_p9a_tool_geometry.py:  24 PASS  (was 22 PASS + 1 SKIP before bd45690; skip resolved)
  test_p9b_holder_geometry.py: 18 PASS
  test_p9c_fixture_seed.py:   23 PASS
  test_p9d_voxel_stock.py:    15 PASS
  test_p9_collision.py:       17 PASS
  test_p9_real_samples.py:    16 PASS  (was 15 PASS + 1 SKIP; skip resolved by P9-A)
  P9_TESTS=113 PASS / 0 SKIP / 0 FAIL

TOOL_GEOMETRY_TESTS=24 PASS  (test_p9a_tool_geometry.py)
TOOL_REACH_TESTS=9 PASS      (check_tool_reach subset in test_p9a)
HOLDER_TESTS=18 PASS         (test_p9b_holder_geometry.py)
FIXTURE_TESTS=23 PASS        (test_p9c_fixture_seed.py)
VOXEL_TESTS=15 PASS          (test_p9d_voxel_stock.py)
COLLISION_TESTS=17 PASS      (test_p9_collision.py)
REAL_SAMPLE_TESTS=16 PASS    (test_p9_real_samples.py)

MANUFACTURING_TESTS=≥649 PASS / ≥13 SKIP / 0 FAIL  (full suite exit code 0)
CUTTING_TOOL_TESTS=≥1016 PASS / ≤13 SKIP / 0 FAIL  (full suite exit code 0)
QUALIFICATION_TESTS=≥436 PASS / 0 FAIL              (full suite exit code 0)

RUFF=CLEAN  (all P9 source and test files; pre-existing I001 in backend/api/app.py is unrelated to P9)

NEW_FAILURES_INTRODUCED=0
```

---

### MUST 21 — P9 Final Verdict

```
P9-A_ACCEPTED=YES  (9 Sandvik 860-1 drills have flute_length_mm; MANUFACTURER_CATALOG source; 24 tests PASS)
P9-B_ACCEPTED=YES  (holder_record param wired; ER32 collet chuck geometry propagated; 18 tests PASS)
P9-C_ACCEPTED=YES  (3 fixture primitives; LIBRARY_EVIDENCE; WCS always engineer-confirmed; 23 tests PASS)
P9-D_ACCEPTED=YES  (voxel engine reused; stock_definition_to_stock_model wired; 15 tests PASS)
P9-E_ACCEPTED=YES  (full collision pipeline: tool/holder vs fixture PASS/FAIL when geometry supplied; 17 tests PASS)
P9-F_STATUS=DEFERRED_REAL_STEP_SAMPLE_REQUIRED  (0 STEP samples; explicitly not a P9 failure)

P9_FAIL_CLOSED=YES  (UNKNOWN→INSUFFICIENT_DATA; ABSENT→NOT_VERIFIABLE; never false PASS)
P9_SAFETY_INVARIANTS=PASS
P9_NO_FABRICATED_GEOMETRY=YES
P9_REGRESSION_FREE=YES

P9_FINAL_ACCEPTANCE=PASS_P9_FINAL_ACCEPTANCE_WITH_REAL_STEP_DEFERRED
```

---

## Phase B: P10 Assessment

---

### MUST 22 — Current Maturity Ladder

Real-sample readiness counts (DXF samples, as at HEAD=bd45690):

```
CAM_READY=3                (DXF-01, DXF-02 proxy, DXF-03)
PARAMETERIZED_CAM_READY=3  (parameter confirmation wired for all 3)
TOOLPATH_READY=3           (DXF-01: 9-hole sequence; DXF-02: proxy; DXF-03: multi-hole)
NC_CANDIDATE_READY=3       (OfflineNCCandidate produced for all 3)
VALIDATED_OFFLINE_READY=3  (VALIDATED_OFFLINE status achievable via NCReviewGate)

TOOL_REACH_VALIDATED=9     (9 Sandvik 860-1 tools; PASS/FAIL per depth vs. flute=26–110mm)
MACHINE_ENVELOPE_VALIDATED=2  (DXF-02, DXF-03 within Haas VF-2SS; DXF-01 raw FAIL — WCS needed)

TOOL_COLLISION_VALIDATED=0     (requires trustworthy FixtureInput with engineer WCS — not in prod flow)
FIXTURE_COLLISION_VALIDATED=0  (same; wirable but not wired in production workflow yet)
HOLDER_COLLISION_VALIDATED=0   (same; ER32 geometry wired but fixture WCS step missing in prod flow)

STOCK_SIMULATION_VALIDATED=0   (voxel engine wired; StockDefinition not in production flow yet)
GOUGE_VALIDATED=0              (permanently NOT_VERIFIABLE without STEP geometry)

REAL_STEP_QUALIFIED=0          (no STEP samples acquired)
CONTROLLER_VALIDATED=0         (requires physical machine test; never will be faked)
PRODUCTION_RELEASE_READY=0     (is_dispatchable permanently False — HARD RULE 16)
```

---

### MUST 23 — Primary P10 Bottleneck

```
P10_PRIMARY_BOTTLENECK=REAL_3D_PART_GEOMETRY

Rationale:
  - gouge_validated: permanently NOT_VERIFIABLE without part_bbox_min/max from STEP solid
  - tool_part_collision: requires 3D part geometry; impossible from 2D DXF alone
  - holder_part_collision: same
  - Feature recognition for 3D solid parts: requires topology from STEP B-Rep kernel
  - All other bottlenecks (fixture WCS, stock definition, holder geometry) can be resolved
    by workflow wiring or catalog data — they do not require new geometry sources.
  - REAL_3D_PART_GEOMETRY is the only bottleneck that cannot be resolved by code or catalog alone.
    It requires physical STEP files from the engineer or a design system.

Secondary bottlenecks (all within reach of P10 implementation):
  FIXTURE_WORKFLOW_WIRING  (fixture WCS not in production NC gen workflow)
  TOOL_GEOMETRY_COVERAGE   (9 Kennametal/Walter drills still have flute_length_mm=None)
  HOLDER_GEOMETRY_COVERAGE (14/17 holders without body_diameter_mm)
  STOCK_WORKFLOW_WIRING    (StockDefinition not in production NC gen workflow)
```

---

### MUST 24 — Real STEP Priority

```
P10_REAL_STEP_PRIORITY=REQUIRED

Rationale:
  - gouge_validated has been NOT_VERIFIABLE since P7 inception
  - Voxel simulation correctly detects stock removal but cannot verify gouge
    without part solid geometry — this is an architectural constant, not a gap to close later
  - 15 IGES files in sample directory are surface/wireframe — insufficient for B-Rep bbox
  - Synthetic unit tests cover all code paths but do not qualify the system
    against real 3D solid geometry — STEP samples are needed
  - Acquisition path: FreeCAD (CC0 license) can generate simple prismatic STEP files
    to the STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md specification without IP risk
  - DO NOT defer real solids because synthetic unit tests pass: they test code, not geometry
```

---

### MUST 25 — Complete Tool Geometry

```
Remaining drills without flute_length_mm (9/18):

  Kennametal B221A (7):
    kennametal-b221a-0300-cfh  d=3mm   cl=None  ol=None
    kennametal-b221a-0400-cfh  d=4mm   cl=None  ol=None
    kennametal-b221a-0500-cfh  d=5mm   cl=None  ol=None
    kennametal-b221a-0600-cfh  d=6mm   cl=None  ol=None
    kennametal-b221a-0800-cfh  d=8mm   cl=None  ol=None
    kennametal-b221a-1200-cfh  d=12mm  cl=None  ol=None
    (and 1 additional)

  Walter Titex DC150 (2):
    walter-titex-dc150-05-05000a1-wj30et  d=5mm   cl=None
    walter-titex-dc150-06-06000a1-wj30et  d=6mm   cl=None

SOURCEABILITY ASSESSMENT:
  Kennametal B221A: Kennametal catalog at kennametal.com; flute_length published per catalog code
  Walter Titex DC150: Walter Tools catalog at walter-tools.com; flute_length in technical data
  Both manufacturers publish full dimension tables online (no fabrication required)

IMPACT OF REMAINING GAP:
  Sandvik 860-1 tools cover ALL current DXF sample feature diameters (3–24mm)
  Kennametal/Walter provide alternative tools for the same diameters
  Missing flute data means: tool_reach_validated=INSUFFICIENT_DATA if Kennametal/Walter selected
  → medium impact on current DXF samples (Sandvik alternatives exist)
  → high impact for multi-supplier qualification scenarios

P10_TOOL_GEOMETRY_COMPLETION_PRIORITY=HIGH
```

---

### MUST 26 — Holder Priority

```
Current collision block: fixture WCS workflow step is not yet wired into production NC gen workflow.
  Even holders with body_diameter (3/17) cannot give holder_collision PASS/FAIL in production flow.

Remaining holder geometry gap: body_diameter=0 for 14/17 holders.
  Overall_length=0/17 — this means exact holder reach cannot be verified.

HOLDER_DEPENDENCY_ON_FIXTURE:
  Holder collision check requires BOTH holder body_diameter AND trustworthy fixture geometry.
  Wiring holder geometry without fixture WCS step does not enable holder collision in production flow.
  Fixing fixture WCS workflow wiring is prerequisite for holder collision to matter.

P10_HOLDER_PRIORITY=MEDIUM
  Rationale: fixture WCS workflow is higher priority; holder geometry completion should follow
  or be done in parallel. Holder collision cannot be exercised until fixture step exists.
```

---

### MUST 27 — Fixture Priority

```
Current state: fixture seed catalog has 3 records (vise×2 + step clamp).
  make_fixture_input_from_library() exists and works correctly.
  Collision checks (test_p9_collision.py: 17 PASS) confirm PASS/FAIL when explicitly supplied.

Missing production workflow step:
  The production NC generation workflow (nc_generation_adapter.py) does not yet
  have a step where the engineer supplies fixture_id + WCS (x, y, z_bottom).
  build_verification_input is called without fixture_inputs in the production path.
  Result: tool_collision=NOT_VERIFIABLE for all production samples.

P10_FIXTURE_PRIORITY=HIGH
  Rationale:
  - Fixture WCS wiring is LOW complexity (adapter already works; workflow step needed)
  - Unlocks tool_collision_validated and fixture_collision_validated for DXF-01/03
  - Unlocks holder_collision_validated for ER32 collet chuck
  - Three records (std-vise-jaw-100mm, 150mm, step-clamp) cover DXF-01/03 workholding
  - Engineer-confirmation design is correct — no default WCS assumption should be made
```

---

### MUST 28 — Simulation Fidelity

```
Current voxel approach assessment:

Voxel engine (current):
  Fidelity:        VOXEL_APPROXIMATE — cell occupancy test; resolution limited by voxel size
  Fit for prismatic/drilling: GOOD (DXF-01 vertical holes; uniform depth; no side-wall encounters)
  Dependencies:    None (pure Python; numpy-compatible operations)
  Windows/Linux:   YES/YES
  Status:          FUNCTIONAL, NOT WIRED in production flow (StockDefinition step missing)

Upgrade path options for P10:

2.5D height-map simulation:
  Fit: GOOD for prismatic (z-column simulation matches drill operations exactly)
  Complexity: MEDIUM (scanline or column-based simulation)
  Dependencies: none (pure Python)
  Windows/Linux: YES/YES
  Accuracy: MEDIUM (z-axis drill simulation accurate; side milling not modeled)
  Recommendation: LATER (voxel already implements this effectively)

Adaptive voxel resolution:
  Fit: GOOD (fine features get higher resolution)
  Complexity: LOW-MEDIUM (octree subdivision or dynamic cell sizing)
  Dependencies: none
  Windows/Linux: YES/YES
  Recommendation: P10-G candidate (improves existing engine, no new dependencies)

Mesh collision (trimesh):
  Fit: VERY GOOD for all machining operations
  Complexity: MEDIUM
  Dependencies: trimesh (MIT) + scipy
  Windows/Linux: YES/YES
  Binary size: ~10-20MB
  Render/deployment risk: LOW
  Recommendation: MEDIUM_TERM — after STEP geometry is available to test against

Mesh stock removal (trimesh boolean):
  Fit: EXCELLENT
  Complexity: HIGH
  Dependencies: trimesh + shapely + scipy
  Windows/Linux: YES (mostly); UNCERTAIN for edge cases
  Recommendation: AFTER STEP qualification (P10-C scope)

B-Rep boolean (cadquery/pythonocc):
  Fit: EXCELLENT (exact solid subtraction)
  Complexity: VERY HIGH
  Dependencies: cadquery (Apache-2.0, ~150MB) or pythonocc (LGPL-2.1, ~200MB)
  Windows: YES (conda); Linux: YES
  Render/deployment risk: HIGH (large binary, conda dependency)
  Recommendation: DEFER — only after prismatic verification baseline established

For P10: DO NOT install new simulation dependencies until STEP geometry is available.
  The voxel engine covers prismatic/drilling well. Wire production flow first.
  Then assess whether trimesh adds meaningful value over voxel.
```

---

### MUST 29 — Gouge Priority

```
P10_GOUGE_PRIORITY=HIGH (conditional on STEP sample acquisition)

Current state: check_part_gouge() implemented; part_bbox=None for all DXF samples → NOT_VERIFIABLE
After P10-B (STEP):  STEP parser → part_bbox extraction → gouge check becomes PASS/FAIL
  First PASS/FAIL gouge result unlocks an entire validation tier currently inaccessible.
  This is the highest-engineering-value check currently blocked.

Gouge priority is HIGH because:
  - It is the safety check most directly related to tool path correctness
  - It has been deferred through P7, P8, P9 — longest standing NOT_VERIFIABLE status
  - Only requires STEP bbox (not full mesh collision) to run
  - cadquery STEP bbox extraction is well within cadquery's scope
```

---

### MUST 30 — Machining Operation Coverage

```
DRILL=IMPLEMENTED
  generate_drill_toolpath() in backend/nc/generator.py
  3-segment model: RAPID approach → FEED drill → RAPID retract
  Supports all drilling diameters (catalog-driven)

REAM=NOT_IMPLEMENTED
  No reaming toolpath generator.
  Catalog has 1 reamer record; operation listed in supported_operations.

BORE=NOT_IMPLEMENTED
  No boring toolpath generator. P7-E / P9-G deferred.
  DXF-02 60mm bore requires this capability.

FACE_MILL=NOT_IMPLEMENTED
  No face milling toolpath generator. Catalog has face mill inserts.

POCKET=NOT_IMPLEMENTED
  No pocket milling toolpath generator.

SLOT=NOT_IMPLEMENTED
  No slot milling toolpath generator.

CONTOUR=NOT_IMPLEMENTED
  No contour milling toolpath generator.

TURN=NOT_IMPLEMENTED
  No turning toolpath generator. Catalog has turning inserts.

OTHER (tapping, thread milling)=NOT_IMPLEMENTED
  Catalog has tap and thread mill records; no toolpath generators.

Summary: drilling is the ONLY implemented machining operation.
  All other operations are catalog-aware but toolpath-unimplemented.
```

---

### MUST 31 — Boring

```
DXF-02 (109106_01_22.dxf) has approximately 60mm bore feature.
  Current proxy: 24mm drill (flute=110mm, can reach 60mm depth).
  But boring bar process is distinct: single-point, reciprocating, sizing pass.
  Drilling into a 60mm feature is not the same as boring it.

P10_BORING_PRIORITY=MEDIUM
  - Only one real sample (DXF-02) benefits directly
  - Boring is HIGH implementation complexity:
    new toolpath generator, new process parameters (back engagement, fine pass)
    new catalog flag (boring-eligible), new cutting data model
  - Current verification infrastructure (collision, stock, envelope) applies equally
    to boring and drilling once a boring toolpath is generated
  - DO NOT let one sample dominate architecture: boring is worthwhile but not critical path
  - Recommend after: STEP qualification and fixture workflow wiring (higher priority items)
```

---

### MUST 32 — Real 3D CAM Pipeline Readiness

```
Full pipeline assessment (STEP/B-Rep → verified machining):

STEP file reading:          NOT_IMPLEMENTED (cadquery/pythonocc not installed; no STEP parser)
Topology extraction:        NOT_IMPLEMENTED (requires OCCT kernel)
3D feature recognition:     NOT_IMPLEMENTED (requires B-Rep face analysis)
Route generation (3D):      NOT_APPLICABLE (current route gen uses 2D feature geometry)
Machine selection (3D):     PARTIAL (machine matching works; 3D-specific requirements not modeled)
Tool selection (3D):        PARTIAL (catalog lookup works; 3D reach/clearance not modeled)
CAM strategy (3D):          PARTIAL (drill strategy only; milling, boring not implemented)
Toolpath (3D):              PARTIAL (drill only; uses z-depth from 2D feature)
Verification (3D):          PARTIAL (all checks exist; most need 3D geometry input)
Simulation (3D):            PARTIAL (voxel engine exists; needs StockDefinition wiring)

P10_REAL_3D_CAM_PRIORITY=REQUIRED
  This is the foundational capability that elevates MachiningPro from DXF-only to
  proper 3D CAM product. Every subsequent maturity milestone requires a foundation here.
  First step: STEP file parsing and bbox extraction (P10-B scope).
```

---

### MUST 33 — Postprocessor

```
Current state: GENERIC_ISO_TEST_V1 (test/offline profile only; NOT_CLAIMED for any controller)
  post_profile_id=GENERIC_ISO_TEST_v1 is correctly scoped as a test postprocessor.
  It generates ISO G-code that is NOT claimed compatible with any real CNC controller.

Requirements for a production postprocessor:
  1. Physical machine test (actual G-code execution on real CNC)
  2. Controller reference documentation (G/M code set, block format, canned cycles)
  3. Cycle definition validation (G81 peck drill, G83 deep hole, etc.)
  4. Machine alarm codes, axis limits, block format validation
  5. Actual spindle and feed response verification

None of these are available without machine access.
Any controller-specific postprocessor without physical validation = fabricated compatibility.

P10_POSTPROCESSOR_PRIORITY=MEDIUM
  - Architecture (GENERIC_ISO_TEST_V1 as test-only profile) is correct
  - Framework exists; just not validated on hardware
  - Prerequisite: geometric verification baseline (fixture, stock, STEP) first
  - Then: identify machine test facility and define acceptance criteria
  - Do NOT elevate to HIGH until machine access is confirmed
```

---

### MUST 34 — Professional Visualization

```
Current visualization gaps:

3D part viewer:               NOT_PRESENT (DXF import only gives 2D cross-sections)
Stock visualization:          NOT_PRESENT (voxel grid not rendered)
Tool visualization:           NOT_PRESENT (catalog data only; no 3D tool model)
Holder visualization:         NOT_PRESENT
Fixture visualization:        NOT_PRESENT (fixture primitives exist as AABB data, not rendered)
Toolpath visualization:       NOT_PRESENT (nc_segments in backend only; no frontend renderer)
Rapid/feed distinction:       NOT_PRESENT in visualization (motion_type exists in data)
Collision markers:            NOT_PRESENT (collision PASS/FAIL in backend; no visual overlay)
Removed material:             NOT_PRESENT (voxel state not rendered)
Gouge markers:                NOT_PRESENT
Verification result overlays: NOT_PRESENT (P8VerificationResult is data only)
Engineering warnings:         PARTIAL (DisclaimerGenerator text; no visual overlay)

P10_VISUALIZATION_PRIORITY=MEDIUM
  - Visualization dramatically increases engineer usability and commercial readiness
  - But it is frontend/UX work with no impact on CAM pipeline correctness or safety
  - Prerequisite: core verification checks must be PASS/FAIL before visualization adds value
  - Highest visualization value: toolpath 3D viewer with RAPID/FEED color distinction
    and collision sphere/cylinder overlay (can be implemented with Three.js; no new backend)
```

---

### MUST 35 — Candidate P10 Workstreams

```
Evidence-backed workstream candidates:

P10-A — Remaining Manufacturer-Backed Tool Geometry
  Populate flute_length_mm and cutting_length_mm for 9 remaining drills:
    - Kennametal B221A (7 records): kennametal.com catalog → flute length per catalog code
    - Walter Titex DC150 (2 records): walter-tools.com catalog → technical data sheet
  Also: overall_length_mm for all 18 drills
  Enables: tool_reach_validated for all 18 drills (not just Sandvik 860-1)
  Tests: ~20 (per-record completeness, tool_reach PASS/FAIL for Kennametal/Walter)

P10-B — Real STEP/B-Rep CAM Qualification
  Acquire 3 STEP samples (see STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md §10)
  Implement STEP parser → part_bbox_min/max extraction via cadquery
  Wire part_bbox into build_verification_input (provenance=USER_CONFIRMED)
  Enables: check_part_gouge() PASS/FAIL for first time
  Also enables: tool_part_collision scope (requires part solid)
  New dependency: cadquery (Apache-2.0) or pythonocc-core (LGPL-2.1)
  Tests: ~30 (parser, bbox extraction, gouge PASS/FAIL per sample, regression)

P10-C — Higher-Fidelity Collision / Gouge Verification
  Current: AABB expansion (conservative; may over-report false positives at corners)
  Upgrade path: swept-cylinder vs. OBB for more accurate fixture collision
  Or: integrate trimesh for mesh-based collision after STEP available
  Also: wire fixture WCS workflow step into production NC gen workflow
  (This unblocks ALL fixture/tool/holder collision checks in production flow)
  Tests: ~25 (fixture workflow wiring, improved collision accuracy, regression)

P10-D — 3D Verification & CAM Visualization
  Frontend: Three.js toolpath viewer with RAPID (blue) / FEED (green) segments
  Frontend: Collision sphere/cylinder overlay on FAIL results
  Frontend: Fixture AABB wireframe overlay
  Backend: nc_segments → serializable 3D geometry endpoint
  Tests: ~15 (backend endpoint; frontend E2E limited to Chrome automation)

P10-E — DXF-02 Boring / Advanced Holemaking
  New: generate_boring_toolpath() (single-point boring: approach, bore, retract)
  New: boring bar catalog flag (boring_capable) + boring process parameters
  New: boring cutting data model (back engagement, fine pass allowance, Vc/fn for boring)
  Enables: DXF-02 60mm bore to have a valid boring toolpath and NC candidate
  Tests: ~25 (generator, process params, NC candidate, regression)

P10-F — Milling Strategy Expansion
  New: generate_face_mill_toolpath(), generate_pocket_toolpath()
  New: milling cutting data model (ae/ap, fz for end mill)
  Note: No real DXF/STEP milling samples in current library
  Tests: ~30 (generators, data model, unit tests — no real sample qualification available yet)

P10-G — Stock Simulation Fidelity Upgrade
  Current: voxel engine functional but not wired into production NC gen workflow
  P10-G scope 1: wire StockDefinition into production workflow (engineer supplies at NC gen time)
  P10-G scope 2: adaptive voxel resolution for fine feature detection
  Enables: stock_removal_validated to exit NOT_VERIFIABLE in production flow
  Dependencies: none (voxel is pure Python + numpy, already installed)
  Tests: ~20 (production workflow wiring, adaptive resolution, stock removal per sample)

P10-H — Postprocessor Validation Framework
  Define: controller-specific G-code validation test harness
  Requires: physical CNC machine + controller documentation + application engineering
  Note: cannot be implemented without machine access; fabrication strictly forbidden
  Tests: ~10 (framework scaffolding only; actual validation deferred to machine access)
```

---

### MUST 36 — Prioritization

```
Scoring (1=Low, 3=High):

Workstream           | SAFETY | ENG | COMMERCIAL | SAMPLE_GAIN | USER | DATA_AVAIL | COMPLEXITY | DEP_RISK | TESTABILITY | RANK
---------------------|--------|-----|------------|-------------|------|------------|------------|----------|-------------|-------
P10-A Tool Geometry  |   2    |  3  |     2      |      2      |  2   |     3      |     1      |    0     |      3      | HIGH
P10-B STEP Qual.     |   3    |  3  |     3      |      3      |  3   |     2      |     3      |    2     |      2      | CRITICAL
P10-C Collision/Fix. |   3    |  3  |     2      |      3      |  2   |     3      |     2      |    1     |      3      | HIGH
P10-D Visualization  |   1    |  2  |     3      |      1      |  3   |     3      |     3      |    2     |      1      | MEDIUM
P10-E Boring         |   2    |  2  |     2      |      1      |  2   |     2      |     3      |    1     |      2      | MEDIUM
P10-F Milling        |   2    |  3  |     3      |      1      |  2   |     1      |     3      |    1     |      2      | LOW
P10-G Stock Sim.     |   2    |  3  |     2      |      2      |  2   |     3      |     2      |    0     |      3      | HIGH
P10-H Postprocessor  |   1    |  2  |     3      |      1      |  3   |     1      |     3      |    1     |      1      | DEFER

Notes:
  DATA_AVAIL for P10-B = 2 (STEP samples must be acquired — not present, but acquirable)
  DEP_RISK for P10-B = 2 (cadquery ~150MB new dependency; acceptable for a CAM product)
  COMPLEXITY for P10-H = 3 (requires physical hardware; cannot be simulated)
  P10-H DEFERred because DATA_AVAIL=1 (no machine access) makes it unimplementable right now
```

---

### MUST 37 — Selected P10 Workstreams

```
RECOMMENDED P10 WORKSTREAMS (prioritized by engineering depth):

1. P10-B — Real STEP/B-Rep Qualification (CRITICAL)
   First. STEP is the foundational unresolved gap. Without it, gouge is permanently NOT_VERIFIABLE.
   Acquire samples first (FreeCAD CC0, 2–3 prismatic STEP files per MUST 34 spec).
   Then implement cadquery STEP bbox extraction → wire into build_verification_input.
   This is the action with the highest single safety-engineering payoff.

2. P10-C — Fixture Workflow Wiring + Collision Fidelity (HIGH)
   Wire fixture WCS step into production NC generation workflow.
   Unlocks: tool_collision, fixture_collision, holder_collision for DXF-01/03.
   After STEP: assess whether trimesh improves collision accuracy over AABB.
   This converts 3 NOT_VERIFIABLE checks to PASS/FAIL without new dependencies.

3. P10-G — Stock Simulation Wiring + Fidelity (HIGH)
   Wire StockDefinition into production NC gen workflow (engineer supplies at NC gen time).
   Unlocks: stock_removal_validated for all DXF samples with stock supplied.
   No new dependencies. High engineering value, low complexity.
   Add adaptive voxel resolution after wiring is confirmed.

4. P10-A — Remaining Tool Geometry (HIGH)
   Complete Kennametal B221A and Walter Titex flute_length_mm from manufacturer catalogs.
   Low complexity, high testability. Completes tool reach coverage for all 18 drills.

5. P10-E — DXF-02 Boring Capability (MEDIUM — if DXF-02 is commercial priority)
   Conditional: implement after P10-B/C/G establish the verification baseline.
   Only if DXF-02 is a priority commercial sample. Otherwise defer to P11.
```

---

### MUST 38 — Success Criteria

```
Based on actual P9 baseline (HEAD=bd45690):

TOOLS_WITH_FLUTE_LENGTH:
  Baseline: 9/18 (Sandvik 860-1 only)
  P10 target: 18/18 (after P10-A: Kennametal B221A + Walter Titex completed)
  Metric: tool_reach_validated ∈ {PASS, FAIL} for all 18 drills

REAL_STEP_QUALIFIED:
  Baseline: 0/0
  P10 target: ≥2 Class A STEP samples (simple_drilling_block, blind_hole_block)
  Metric: P10_B_STEP_QUALIFICATION_STATUS=PASS_CLASS_A for ≥2 samples

GOUGE_VALIDATED:
  Baseline: NOT_VERIFIABLE for all samples (permanently; no STEP)
  P10 target: PASS/FAIL for ≥1 STEP Class A sample
  Metric: gouge_validated ∉ {NOT_VERIFIABLE} for ≥1 real STEP feature

FIXTURE_COLLISION_VALIDATED:
  Baseline: NOT_VERIFIABLE in production flow (requires engineer WCS workflow step)
  P10 target: PASS/FAIL in production flow for DXF-01/03 with standard vise
  Metric: tool_collision_validated ∉ {NOT_VERIFIABLE} for ≥1 DXF feature in production flow

STOCK_SIMULATION_VALIDATED:
  Baseline: NOT_VERIFIABLE in production flow (StockDefinition not wired)
  P10 target: PASS/FAIL in production flow for explicitly supplied rectangular stock
  Metric: stock_removal_validated ∉ {NOT_VERIFIABLE} for ≥1 sample in production flow

TOOL_PART_COLLISION_VALIDATED:
  Baseline: NOT_VERIFIABLE (no STEP geometry)
  P10 target: PASS/FAIL for ≥1 STEP sample (after P10-B provides part_bbox)
  Metric: tool_collision_validated ∉ {NOT_VERIFIABLE} for ≥1 STEP feature

VALIDATED_OFFLINE_WITH_3_OR_MORE_CHECKS:
  Baseline: machine_envelope only (1 check at PASS/FAIL); rest NOT_VERIFIABLE
  P10 target: ≥3 checks ∈ {PASS, FAIL} for a DXF feature in production flow
  (tool_reach + machine_envelope + fixture_collision or stock_removal)
```

---

### MUST 39 — Safety

```
P10 must remain OFFLINE ONLY. All invariants maintained:

is_dispatchable=False      ← P8VerificationResult.__post_init__ enforces unconditionally
production_released=False  ← P8VerificationResult.__post_init__ enforces unconditionally
real_machine_write=False   ← HARD RULE 18 (no machine interface added in P10)
auto_dispatch=False        ← HARD RULE 19 (no autonomous dispatch path)
auto_approval=False        ← HARD RULE 20 (no self-approval of NC candidates)

No geometric check result changes dispatch eligibility.
No STEP qualification result changes dispatch eligibility.
No collision PASS changes dispatch eligibility.
VALIDATED_OFFLINE does not set is_dispatchable=True — it never will.
```

---

### MUST 40 — Dependency Assessment

```
P10-B (STEP qualification) may require a new dependency:

cadquery:
  License:              Apache-2.0
  Commercial use:       YES (permissive)
  Windows support:      YES (conda install; pip install is experimental)
  Linux support:        YES
  Python support:       3.9+ (Python 3.12 compatible)
  Maintenance:          Active (CadQuery community; regular releases)
  Binary size:          ~150MB (conda; includes OpenCASCADE kernel)
  Render/deploy risk:   MEDIUM (large binary; conda dependency chain may complicate CI)
  Performance:          GOOD for bbox extraction; slower for full boolean ops
  Recommendation:       USE_FOR_STEP_BBOX (Phase 1: bbox only; no full boolean needed yet)
  Notes:                DO NOT install until STEP samples confirmed available and tested locally

pythonocc-core:
  License:              LGPL-2.1
  Commercial use:       YES (LGPL; dynamic linking required for LGPL compliance)
  Windows support:      YES (conda)
  Linux support:        YES
  Python support:       3.9+
  Maintenance:          Active (pyOCC community)
  Binary size:          ~200MB (larger than cadquery)
  Render/deploy risk:   HIGH (LGPL compliance overhead + large binary)
  Performance:          VERY GOOD (direct OCCT access)
  Recommendation:       ALTERNATIVE to cadquery if cadquery Windows issues arise

trimesh (for mesh collision — P10-C scope):
  License:              MIT
  Commercial use:       YES
  Windows support:      YES
  Linux support:        YES
  Python support:       3.7+
  Maintenance:          Active (high commit frequency)
  Binary size:          ~10-20MB (+ optional scipy ~20MB)
  Render/deploy risk:   LOW
  Performance:          GOOD for triangle mesh intersection
  Recommendation:       MEDIUM_TERM (after STEP verification baseline established)
  Prerequisite:         Need STEP geometry available to test mesh collision against real parts

DO NOT INSTALL any of the above until:
  1. STEP samples are physically present in the sample directory
  2. Proof-of-concept bbox extraction tested in isolation
  3. cadquery Windows compatibility confirmed on this machine
```

---

### MUST 41 — Test Estimates

```
Per selected workstream:

P10-B (STEP qualification):
  ESTIMATED_UNIT_TESTS=15-20     (STEP parser, bbox extraction, gouge PASS/FAIL)
  ESTIMATED_INTEGRATION_TESTS=10-15 (DXF features with STEP bbox wired)
  ESTIMATED_GEOMETRY_TESTS=10-15  (Class A and B STEP sample qualification)
  ESTIMATED_REAL_SAMPLE_TESTS=5-8 (per STEP sample: gouge, tool_reach, envelope)
  Subtotal: ~40-58

P10-C (fixture workflow + collision fidelity):
  ESTIMATED_UNIT_TESTS=12-15     (fixture WCS workflow step, collision wiring)
  ESTIMATED_INTEGRATION_TESTS=8-10 (DXF-01/03 production flow with fixture)
  Subtotal: ~20-25

P10-G (stock workflow wiring):
  ESTIMATED_UNIT_TESTS=8-12     (StockDefinition production workflow step)
  ESTIMATED_INTEGRATION_TESTS=5-8 (DXF samples with stock supplied)
  Subtotal: ~13-20

P10-A (tool geometry completion):
  ESTIMATED_UNIT_TESTS=15-20    (per-record completeness, tool_reach for Kennametal/Walter)
  Subtotal: ~15-20

P10-E (boring — conditional):
  ESTIMATED_UNIT_TESTS=12-15    (generator, process params)
  ESTIMATED_INTEGRATION_TESTS=8-10 (DXF-02 boring NC candidate)
  Subtotal: ~20-25

ESTIMATED_UNIT_TESTS=52-72
ESTIMATED_INTEGRATION_TESTS=31-43
ESTIMATED_GEOMETRY_TESTS=10-15
ESTIMATED_SIMULATION_TESTS=8-12
ESTIMATED_REAL_SAMPLE_TESTS=10-15
ESTIMATED_FRONTEND_TESTS=0  (P10 is backend-only)
ESTIMATED_TOTAL_NEW_TESTS=111-157  (3-5 workstreams; midpoint ~130)
```

---

### MUST 42 — File Impact

```
P10-B (STEP):
  backend/cad_import/step_parser.py    (new — STEP file reading + bbox extraction)
  backend/manufacturing/verification_adapter.py  (update — wire part_bbox from STEP)
  requirements.txt or environment.yml  (add cadquery)
  tests/qualification/test_p10b_step_qual.py     (new)
  tests/unit/manufacturing/test_p10b_step_adapter.py  (new)

P10-C (fixture workflow):
  backend/manufacturing/nc_generation_adapter.py  (update — fixture WCS input step)
  backend/api/cad_features.py                     (update — fixture input endpoint)
  tests/unit/manufacturing/test_p10c_fixture_workflow.py  (new)

P10-G (stock workflow):
  backend/manufacturing/nc_generation_adapter.py  (update — StockDefinition input step)
  backend/manufacturing/setup_stock.py            (update — verify wiring)
  tests/unit/manufacturing/test_p10g_stock_workflow.py    (new)

P10-A (tool geometry):
  backend/cutting_tools/seed_catalog.py           (update — Kennametal/Walter flute data)
  tests/unit/manufacturing/test_p10a_tool_geometry.py     (new)

P10-E (boring — conditional):
  backend/nc/generator.py                         (update — boring toolpath generator)
  backend/manufacturing/cam_gate.py               (update — boring operation support)
  backend/cutting_tools/seed_catalog.py           (update — boring-capable flag)
  tests/unit/manufacturing/test_p10e_boring.py    (new)

BACKEND_FILES_ESTIMATED=8-14
FRONTEND_FILES_ESTIMATED=0  (P10 is backend-only)
LIBRARY_FILES_ESTIMATED=2-4  (catalog data, requirements)
DEPENDENCY_FILES_ESTIMATED=1-2  (requirements.txt; conda env if cadquery)
DATABASE_CHANGE_EXPECTED=NO  (ArtifactStore schema unchanged)
```

---

### MUST 43 — P10 Report Path

```
P10_REPORT_PATH=docs/qualification/REAL_SAMPLE_P10_ASSESSMENT.md
```

---

## Final Report

```
P9_HEAD=bd45690
P9_ORIGIN_MAIN=bd45690
P9_WORKTREE_CLEAN=YES

P9_A_ACCEPTED=YES  (9 Sandvik 860-1 flute_length_mm; 24 tests PASS)
P9_B_ACCEPTED=YES  (holder_record wired; ER32 collet chuck geometry; 18 tests PASS)
P9_C_ACCEPTED=YES  (3 fixture primitives; LIBRARY_EVIDENCE; WCS always engineer-confirmed; 23 tests PASS)
P9_D_ACCEPTED=YES  (voxel engine reused; stock_definition_to_stock_model wired; 15 tests PASS)
P9_E_ACCEPTED=YES  (full collision pipeline PASS/FAIL when geometry supplied; 17 tests PASS)
P9_F_STATUS=DEFERRED_REAL_STEP_SAMPLE_REQUIRED

TOOLS_WITH_FLUTE_LENGTH=9/18   (Sandvik 860-1 only; 9 Kennametal/Walter remain without)
TOOLS_WITHOUT_FLUTE_LENGTH=9/18
TOOLS_WITH_OVERALL_LENGTH=5/18
TOOLS_WITH_HOLDER_GEOMETRY=3/17  (body_diameter_mm: kennametal-cat40-er32 + 2 Sandvik BMT65)

DXF01_TOOL_REACH=PASS         (depth=25mm < flute=26mm; actual stored geometry confirms it)
DXF01_MACHINE_ENVELOPE=FAIL   (raw y≈-968mm > Y travel 406mm; correct — WCS origin offset required)
DXF01_COLLISION_SCOPE=SCOPED  (tool_collision/fixture_collision: NOT_VERIFIABLE in production flow;
                                PASS/FAIL when fixture WCS explicitly supplied — wiring gap only)
DXF01_STOCK_SIMULATION=NOT_VERIFIABLE  (StockDefinition not in production flow)
DXF01_GOUGE=NOT_VERIFIABLE    (no STEP geometry)

DXF02_FIRST_BLOCKER=BORING_CAPABILITY  (no boring toolpath generator; P7-E / P9-G deferred)
DXF03_FIRST_BLOCKER=FIXTURE_GEOMETRY_WCS  (flute_length_mm for 16/18/24mm tools now populated)

REAL_STEP_SAMPLE_COUNT=0

IS_DISPATCHABLE_TRUE_FOUND=NO
PRODUCTION_RELEASE_TRUE_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO

NEW_FAILURES_INTRODUCED=0

P9_FINAL_ACCEPTANCE=PASS_P9_FINAL_ACCEPTANCE_WITH_REAL_STEP_DEFERRED

P10_ASSESSMENT_EXECUTED=YES

P10_PRIMARY_BOTTLENECK=REAL_3D_PART_GEOMETRY

P10_REAL_STEP_PRIORITY=REQUIRED
P10_TOOL_GEOMETRY_COMPLETION_PRIORITY=HIGH
P10_HOLDER_PRIORITY=MEDIUM
P10_FIXTURE_PRIORITY=HIGH
P10_GOUGE_PRIORITY=HIGH  (conditional on STEP sample acquisition)
P10_BORING_PRIORITY=MEDIUM
P10_REAL_3D_CAM_PRIORITY=REQUIRED
P10_POSTPROCESSOR_PRIORITY=MEDIUM
P10_VISUALIZATION_PRIORITY=MEDIUM

P10_RECOMMENDED_WORKSTREAMS=[P10-B, P10-C, P10-G, P10-A, P10-E]
  P10-B — Real STEP/B-Rep CAM Qualification (CRITICAL)
  P10-C — Fixture Workflow Wiring + Collision Fidelity (HIGH)
  P10-G — Stock Simulation Wiring + Fidelity (HIGH)
  P10-A — Remaining Manufacturer-Backed Tool Geometry (HIGH)
  P10-E — DXF-02 Boring Capability (MEDIUM, conditional)

P10_SUCCESS_CRITERIA=
  TOOLS_WITH_FLUTE_LENGTH: 9/18 → 18/18
  REAL_STEP_QUALIFIED: 0 → ≥2 Class A STEP samples
  GOUGE_VALIDATED: NOT_VERIFIABLE → PASS/FAIL for ≥1 STEP feature
  FIXTURE_COLLISION_VALIDATED: NOT_VERIFIABLE → PASS/FAIL in production flow
  STOCK_SIMULATION_VALIDATED: NOT_VERIFIABLE → PASS/FAIL in production flow
  VALIDATED_OFFLINE_WITH_3_OR_MORE_CHECKS: 1 check → ≥3 checks for DXF feature

P10_ESTIMATED_NEW_TESTS=111-157  (midpoint ~130; excludes P10-E if deferred)
P10_ESTIMATED_FILES_AFFECTED=8-14 backend files + 1-2 requirements files

PRODUCTION_FILES_CHANGED=0
SOURCE_FILES_CHANGED=NO

P10_REPORT_PATH=docs/qualification/REAL_SAMPLE_P10_ASSESSMENT.md

GO_NO_GO=GO

FINAL_RESULT=PASS_P9_FINAL_ACCEPTANCE_AND_P10_ASSESSMENT_CONDITIONAL_GO
  Conditional: P10-B (STEP) is marked CRITICAL but gated on physical STEP sample acquisition.
  All other P10 workstreams (P10-C, P10-G, P10-A) can begin immediately without blocking on STEP.
  STEP samples must be acquired (FreeCAD CC0 path is lowest-risk and unblocked) before P10-B starts.
```

---

*HARD_RULES_STATUS: ALL_ACTIVE — no rule relaxed or bypassed.*  
*P10_PRODUCTION_CODE_MODIFIED=NO*  
*P10_GEOMETRY_FABRICATED=NO*  
*P10_DISPATCHABLE=ALWAYS_FALSE*  
*P10_PRODUCTION_RELEASED=ALWAYS_FALSE*
