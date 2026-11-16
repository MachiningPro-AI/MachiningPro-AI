# MachiningPro AI — P9 Assessment

**Status:** P8_FINAL_ACCEPTANCE_PASS → P9_ASSESSMENT_GO  
**Date:** 2026-11-16  
**Branch:** main  
**HEAD:** e849ff9  
**Assessment type:** Read-only audit — NO production code modified.

---

## Phase A: P8 Final Acceptance

### MUST 1 — Repository State

```
BRANCH=main
HEAD=e849ff9
ORIGIN_MAIN=e849ff9
WORKTREE_CLEAN=YES
AHEAD_BEHIND=0/0
HEAD_BEFORE=7ee8e04
```

### MUST 2 — Background Shell Audit

```
BACKGROUND_SHELLS_ACTIVE=NO
BACKGROUND_SHELL_RESULTS=N/A
  (Two background test runners from P8 session completed with exit code 0.
   No duplicate suites running at P9 session start.)
```

### MUST 3 — P8 Evidence Read

```
DOCS_READ:
  docs/qualification/REAL_SAMPLE_P8_ASSESSMENT.md — Phase C implementation results read
  docs/qualification/REAL_SAMPLE_P8_IMPLEMENTATION_COMPARISON.md — full comparison read
  backend/manufacturing/verification_adapter.py — full source read

P8_A_IMPLEMENTED=YES
P8_B_IMPLEMENTED=YES  (data gap 0/18 flute; code correct)
P8_C_IMPLEMENTED=YES
P8_D_IMPLEMENTED=YES
P8_E_IMPLEMENTED=YES
P8_F_DOCUMENT_WRITTEN=YES
P8_H_IMPLEMENTED=NO  (HARD RULE 16)
```

### MUST 4 — Verification Engine Wiring

```
VERIFICATION_ENGINE_WIRED=YES
  run_p8_verification() calls run_simulation() from backend/verification/simulation.py
  Source verified: 'run_simulation' in inspect.getsource(run_p8_verification) = True

PARALLEL_VERIFICATION_ENGINE_CREATED=NO
  'def check_tool_collision' in verification_adapter.py = False
  'def check_tool_reach' in verification_adapter.py = False
  'def run_simulation' in verification_adapter.py = False
  All 12 check functions remain in backend/verification/checks.py (unchanged)
```

### MUST 5 — Verification Provenance

```
VERIFICATION_PROVENANCE_PRESERVED=YES

GeometryFieldProvenance(StrEnum): KNOWN | USER_CONFIRMED | PROPOSED | UNKNOWN

All safety-critical fields carry explicit provenance labels:
  tool_diameter_provenance
  tool_flute_length_provenance
  tool_overall_length_provenance
  tool_cutting_length_provenance
  holder_diameter_provenance
  holder_length_provenance
  stock_provenance
  machine_travel_provenance
  part_bbox_provenance

UNKNOWN fields remain UNKNOWN — no silent promotion.
Provenance audit trail stored in P8VerificationInput.provenance_notes.
```

### MUST 6 — Fail-Closed Behavior

```
FAIL_CLOSED_TEST (minimal candidate — no tool geometry, no machine, no fixture):

  tool_reach_validated      = INSUFFICIENT_DATA  ✓ (not false PASS)
  machine_envelope_validated = INSUFFICIENT_DATA  ✓ (not false PASS)
  tool_collision_validated   = NOT_VERIFIABLE     ✓ (not false PASS)
  holder_collision_validated = NOT_VERIFIABLE     ✓ (not false PASS)
  fixture_collision_validated = NOT_VERIFIABLE    ✓ (not false PASS)
  stock_removal_validated    = NOT_VERIFIABLE     ✓ (not false PASS)
  gouge_validated            = NOT_VERIFIABLE     ✓ (not false PASS)
  geometry_verification_ready = False             ✓
  is_dispatchable            = False              ✓
  production_released        = False              ✓

FALSE_PASS_FOUND=NO
```

### MUST 7 — Tool Reach Audit

```
TOTAL_TOOL_RECORDS=60
DRILL_RECORDS=18
TOOLS_WITH_FLUTE_LENGTH=0/18   ← DATA GAP (not code gap)
TOOLS_WITH_CUTTING_LENGTH=8/18
TOOLS_WITH_OVERALL_LENGTH=5/18
TOOLS_WITH_HOLDER_GEOMETRY=0   (holder catalog is separate from cutting tool catalog)
```

### MUST 8 — Flute Length Safety

```
MISSING_FLUTE_LENGTH_AUTO_PASS_FOUND=NO

Code path (verified):
  if vi.tool_flute_length_mm is None:
      tool_reach_status = _INSUFFICIENT_DATA   ← correct

TOOL_REACH_WHEN_FLUTE_UNKNOWN=INSUFFICIENT_DATA
  NOT false PASS, NOT NOT_VERIFIABLE.
  INSUFFICIENT_DATA is correct — the check could run if data were provided,
  but cannot run without it. This distinguishes from NOT_VERIFIABLE (geometry
  structurally absent) and NOT_PERFORMED (check not attempted).
```

### MUST 9 — Machine Envelope

```
MACHINE_ID=haas-vf-2ss
X_TRAVEL=762.0
Y_TRAVEL=406.0
Z_TRAVEL=508.0

STATIC_MACHINE_SELECTION_SEPARATE_FROM_PATH_VALIDATION=YES
  machine_selection.py: static capacity matching (spindle_power, travel, pallet_size)
  check_machine_envelope(): path-level per-segment coordinate check
  These are architecturally separate. Machine selection PASS ≠ envelope PASS.

BOUNDARY_TESTS:
  x=381mm on 762mm travel: PASS (at exact half-travel limit)
  x=500mm on 200mm travel: FAIL (overflow detected correctly)
  travel=None: INSUFFICIENT_DATA (not FAIL)
```

### MUST 10 — Fixture

```
FIXTURE_SCHEMA_AVAILABLE=YES
  FixtureInput (frozen dataclass): fixture_id, fixture_type, source, provenance,
  min/max x/y/z_mm; to_fixture_geometry() → FixtureGeometry

FIXTURE_GEOMETRY_AVAILABLE=NO
  No fixture catalog seeded in production workflow.
  build_verification_input() default: fixture_inputs=[] (never auto-populated).

FIXTURE_COLLISION_VALIDATED=NOT_VERIFIABLE
  When fixture_inputs=[] or all UNKNOWN-provenance → NOT_VERIFIABLE (correct).
  When USER_CONFIRMED fixture supplied → PASS or FAIL (verified in test_p8c_fixture.py).
```

### MUST 11 — Holder

```
HOLDER_GEOMETRY_AVAILABLE=NO
  Holder catalog has 17 records; body_diameter_mm populated for 3/17; overall_length 0/17.
  P8 adapter: holder_diameter_mm always UNKNOWN in P8 (not populated from catalog chain).

HOLDER_COLLISION_VALIDATED=NOT_VERIFIABLE
  When holder_diameter_mm=None → NOT_VERIFIABLE (correct, enforced in run_p8_verification).
```

### MUST 12 — Tool Collision Scope

```
TOOL_PART_COLLISION=NOT_VERIFIABLE  (requires STEP — part_bbox always UNKNOWN from DXF)
TOOL_STOCK_COLLISION=NOT_VERIFIABLE (requires StockModel — stock_model=None unless engineer supplies)
TOOL_FIXTURE_COLLISION=NOT_VERIFIABLE (requires fixture geometry — not in production workflow)
  Exception: when USER_CONFIRMED FixtureInput supplied → PASS or FAIL
```

### MUST 13 — Stock Removal

```
STOCK_REMOVAL_ENGINE=VOXEL_ENGINE_IMPLEMENTED_IN_VERIFICATION_BACKEND
  VoxelGrid.from_stock() + check_stock_remaining() in backend/verification/stock.py
  Engine is FUNCTIONAL — called when StockModel is provided.

STOCK_REMOVAL_VALIDATED=NOT_VERIFIABLE
  For current DXF samples: no StockDefinition provided → stock_model=None → NOT_VERIFIABLE.
  Engine would run if engineer supplies stock dimensions via StockDefinition.
```

### MUST 14 — Gouge

```
GOUGE_ENGINE=BBOX_CHECK_IMPLEMENTED_IN_VERIFICATION_BACKEND
  check_part_gouge() uses part_bbox_min/max for Z under-cut detection.
  check_stock_gouge() uses stock contains_point for out-of-stock detection.
  Both implemented in backend/verification/checks.py (unchanged).

GOUGE_VALIDATED=NOT_VERIFIABLE
  For all DXF samples: part_bbox_min=None (no STEP geometry available).
  HARD RULE HR-19a: cannot claim 3D collision from 2D DXF alone. Correct.
```

### MUST 15 — DXF-01 Real Replay

```
DXF-01 = 109106_01_30.dxf (sha256[:16]=e694952f02d7fb5b)
Candidate: dxf01-feat-001, x=-225.54485, y=-968.552339, z=0.0, depth=25mm
Machine: haas-vf-2ss (travel 762×406×508mm)
NC_SEGMENTS=3 (approach→drill→retract)

TOOL_REACH        = INSUFFICIENT_DATA
  (flute_length_mm=None for sandvik-860-1-0500-026a1-pm; check blocked)
MACHINE_ENVELOPE  = FAIL
  (DXF raw y=-968mm > Y travel 406mm; correct — WCS origin offset required by engineer)
TOOL_COLLISION    = NOT_VERIFIABLE  (no fixture geometry)
HOLDER_COLLISION  = NOT_VERIFIABLE  (no holder geometry)
FIXTURE_COLLISION = NOT_VERIFIABLE  (no fixture geometry)
STOCK_REMOVAL     = NOT_VERIFIABLE  (no stock definition)
GOUGE             = NOT_VERIFIABLE  (no STEP geometry)
SCOPE             = TOOLPATH_WIRED+STATIC_ENVELOPE_CHECK+CLEARANCE_CHECK_2_5D
IS_DISPATCHABLE   = False
PRODUCTION_RELEASED = False
GEOMETRY_VERIFICATION_READY = True

NOTE: MACHINE_ENVELOPE=FAIL is architecturally correct.
DXF-01 uses global drawing coordinates (y≈-968mm origin).
Machine travel envelope is WCS-relative. The engineer must configure a WCS origin
offset (G54/G55) to map drawing coordinates into machine travel range.
The P8 engine correctly detects this raw-coordinate overflow as a FAIL — the
toolpath path as given (without WCS setup) would exceed machine Y travel.
This is NOT a bug in the P8 implementation; it is the correct safety check result.
```

### MUST 16 — DXF-02 and DXF-03

```
DXF-02 = 109106_01_22.dxf (60mm bore, z-origin, 24mm drill stub proxy)
TOOL_REACH        = INSUFFICIENT_DATA  (flute_length_mm=None for 24mm drill)
MACHINE_ENVELOPE  = PASS  (z=0 origin, well within Haas envelope)
TOOL_COLLISION    = NOT_VERIFIABLE
HOLDER_COLLISION  = NOT_VERIFIABLE
GOUGE             = NOT_VERIFIABLE
NOTE: DXF-02 boring CAM strategy (P8-G) remains deferred.
      24mm drill is a proxy; actual boring bar process not modeled.

DXF-03 = Pense_Sema.dxf (16/18/24mm features)
TOOL_REACH        = INSUFFICIENT_DATA  (flute_length_mm=None for 16mm drill)
MACHINE_ENVELOPE  = PASS  (z=0 origin, well within Haas envelope)
TOOL_COLLISION    = NOT_VERIFIABLE
HOLDER_COLLISION  = NOT_VERIFIABLE
GOUGE             = NOT_VERIFIABLE
DXF03_FIRST_BLOCKER=flute_length_mm missing for sandvik-860-1-1600/1800/2400
  cutting_length_mm is populated (73/83/110mm) but NOT a substitute for flute_length.
  Source: Sandvik CoroDrill 860-1 technical data sheet → flute length per model.
```

### MUST 17 — P7 Regression

```
P7_TESTS=21 PASS (test_p7_e2e_dxf.py — full DXF-01 chain)
MANUFACTURING_SUITE=974 PASS, 12 SKIP, 1 xpassed (manufacturing + qualification)
  (538 manufacturing unit + 436 qualification)
NEW_FAILURES_INTRODUCED=0

P7 NC generation, multi-feature sequence, VALIDATED_OFFLINE lifecycle, risk warnings,
and non-dispatchability all verified in regression. P8 adapter does NOT break P7.
```

### MUST 18 — Safety Search

```
IS_DISPATCHABLE_TRUE_FOUND=NO
  nc/validator.py:285 — validator ERROR MESSAGE string (guards against dispatchable=True)
  NOT an assignment. The validator actively rejects is_dispatchable=True.
  verification_adapter.py — no dispatchable=True assignment.

PRODUCTION_RELEASE_TRUE_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO
```

### MUST 19 — Source Integrity

```
ALL_SOURCE_FILES_UNCHANGED=YES
  DXF-01 sha256[:16]: e694952f02d7fb5b  (109106_01_30.dxf) ✓
  DXF-02 sha256[:16]: 296920507d9a7bee  (109106_01_22.dxf) ✓
  DXF-03 sha256[:16]: db0b634b4af40ce9  (Pense_Sema.dxf) ✓

SOURCE_SAMPLE_FILES_COMMITTED=NO
```

### MUST 20 — Test Evidence

```
P8_TESTS=90 PASS
  test_p8a_verification_adapter.py: 42
  test_p8b_tool_reach.py:           10
  test_p8c_fixture.py:               8
  test_p8d_collision_status.py:      7
  test_p8e_machine_envelope.py:      9
  test_p8_safety.py:                14

VERIFICATION_TESTS=90  (all in P8 test files above)
TOOL_REACH_TESTS=10    (test_p8b_tool_reach.py)
FIXTURE_TESTS=8        (test_p8c_fixture.py)
MACHINE_ENVELOPE_TESTS=9  (test_p8e_machine_envelope.py)
COLLISION_STATUS_TESTS=7  (test_p8d_collision_status.py)
QUALIFICATION_TESTS=436 PASS (tests/qualification/)
MANUFACTURING_TESTS=538 PASS, 12 SKIP (tests/unit/manufacturing/)
CUTTING_TOOL_TESTS=366 PASS (included in manufacturing suite)
RUFF=CLEAN (all P8 source + test files)
NEW_FAILURES_INTRODUCED=0
```

### MUST 21 — P8 Final Verdict

```
P8_FAIL_CLOSED=YES
  Missing geometry → INSUFFICIENT_DATA or NOT_VERIFIABLE. Never false PASS.

P8_TOOL_REACH_ACCEPTED=YES
  flute_length_mm=None → INSUFFICIENT_DATA (correct; data gap documented).

P8_MACHINE_ENVELOPE_ACCEPTED=YES
  PASS/FAIL/INSUFFICIENT_DATA per travel availability. Static selection ≠ path validation.
  DXF-01 raw FAIL is architecturally correct (WCS origin offset required).

P8_FIXTURE_ACCEPTED=YES
  Absent fixture → NOT_VERIFIABLE. Trustworthy fixture → PASS/FAIL. UNKNOWN excluded.

P8_COLLISION_STATUS_ACCEPTED=YES
  GEOMETRY_CHECK_PASS ≠ COLLISION_VALIDATED (separate fields, separate logic).
  Holder always NOT_VERIFIABLE (correct — holder geometry not in P8 catalog chain).

SAFETY_INVARIANTS=PASS
  is_dispatchable=False enforced unconditionally (__post_init__ override).
  production_released=False enforced unconditionally.
  Validator guards against dispatchable=True in NC pipeline.

P8_FINAL_ACCEPTANCE=PASS_P8_FINAL_ACCEPTANCE_WITH_GEOMETRY_DATA_GAPS
  Data gaps (flute 0/18, holder geometry, no STEP, no fixture catalog) are
  documented and correctly manifest as INSUFFICIENT_DATA/NOT_VERIFIABLE —
  not hidden or silently passed. This is the correct engineering state.
```

---

## Phase B: P9 Assessment

### MUST 22 — Real Sample Inventory

```
Sample directory: D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar

DXF=57 files
PDF=3 files
IGES=15 files  (.igs extension)
STEP=0 files
DWG=3 files
CATIA_MODEL=6 files  (.model extension)
OTHER=0
TOTAL=84 files

No STEP/B-Rep samples available. IGES files are surface/wireframe (not solid B-Rep).
The 57 DXF files are 2D cross-section drawings.
```

### MUST 23 — Real STEP Priority

```
P9_REAL_STEP_PRIORITY=REQUIRED

Rationale:
  - part gouge check: blocked (requires part_bbox_min/max from solid B-Rep)
  - check_part_gouge(): implemented but has no geometry to check against for any sample
  - 57 DXF files: provide 2D feature geometry only
  - 15 IGES files: surface/wireframe topology — no closed solid volumes
  - Without STEP, gouge_validated=NOT_VERIFIABLE for ALL samples permanently
  - Collision validation beyond envelope check requires part solid
  - STEP is the unresolvable blocker for the highest-value remaining checks

STEP_SAMPLE_REQUIREMENT=See docs/qualification/STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md
  Minimum viable P9 set: 3 STEP files (2× Class A prismatic + 1× Class B pocket)
```

### MUST 24 — Tool Geometry Data Gap

```
flute_length_mm:
  STATUS=REQUIRED_NOW
  CURRENT=0/18 drills
  IMPACT: tool_reach_validated=INSUFFICIENT_DATA for ALL drills (high)
  SOURCE: Sandvik CoroDrill 860-1 technical data sheets contain flute length per model
  ACTION: Populate from manufacturer catalog; each stable_id maps to a unique product code

overall_length_mm:
  STATUS=HIGH_VALUE
  CURRENT=5/18 drills
  IMPACT: needed for holder offset calculation in future holder_clearance check
  SOURCE: Sandvik product data sheet (overall length per cutting diameter)

cutting_length_mm:
  STATUS=LATER (8/18 populated; partial coverage acceptable)
  CURRENT=8/18 drills; not a substitute for flute_length
  IMPACT: limited (cutting_length is a secondary metric; flute_length is primary)

shank_diameter_mm:
  STATUS=LATER
  CURRENT=18/18 populated
  IMPACT=None (already complete)

neck_diameter:
  STATUS=NOT_REQUIRED (CoroDrill 860 has straight shank; no neck relief needed)

stickout:
  STATUS=NOT_REQUIRED (engineer-confirmed at setup time, not catalog data)

holder_interface:
  STATUS=HIGH_VALUE
  CURRENT: machine_interface field populated in holder catalog (17 records)
  IMPACT: needed to map tool→holder compatibility for holder selection

tip_geometry (point angle, tip radius):
  STATUS=LATER
  IMPACT: needed for precise depth-to-shoulder calculations; secondary to flute_length
```

### MUST 25 — Sourceability

```
TOOL_GEOMETRY_ENRICHMENT_FEASIBLE=YES

Evidence:
  All 18 drill records have:
    manufacturer = "Sandvik Coromant"
    catalog_code = "860.1-{DIAM}-{CUT}A1-PM 4234" (fully specified)
    source_note = "coromant.sandvik.com" (all 3 P7-D records; pattern consistent)

  Sandvik CoroDrill 860-1 technical data:
    - Flute length: published per cutting diameter in Sandvik's technical guide
    - Overall length: published in catalog dimensions table
    - Both values derivable from catalog_code without fabrication

  Mapping strategy (no fabrication):
    stable_id → catalog_code → Sandvik 860-1 technical data sheet → flute_length_mm
    E.g. sandvik-860-1-0500-026a1-pm → 860.1-0500-026A1-PM → Lc=26mm → flute_length from table

  For existing 8 records with cutting_length_mm populated, flute_length follows a
  known ratio (flute_length ≈ 1.1–1.3× cutting_length for CoroDrill 860-1 — to be
  confirmed from data sheet, never assumed).

ENRICHMENT_APPROACH=Manual population from manufacturer data sheet per record.
  Do NOT auto-populate or approximate. Each value must be confirmed from Sandvik catalog.
```

### MUST 26 — Holder Library

```
HOLDER_LIBRARY_EXISTS=YES
  backend/tool_holders/ — full library structure
  backend/tool_holders/catalog_models.py — ToolHolderCatalogRecord (Pydantic)
  backend/tool_holders/seed_catalog.py — 17 holder records

HOLDER_RECORD_COUNT=17

HOLDER_GEOMETRY_COMPLETENESS=PARTIAL
  body_diameter_mm:    3/17 populated  ← needed for holder_collision check outer envelope
  overall_length_mm:   0/17 populated  ← needed for holder_length_mm in SimulationRequest
  gauge_length_mm:    15/17 populated  ← not directly usable for collision bounds
  nose_diameter_mm:    0/17 populated

P8_ADAPTER_GAP:
  P8VerificationInput requires holder_diameter_mm (outer envelope) and holder_length_mm.
  These fields are body_diameter_mm and overall_length_mm in ToolHolderCatalogRecord.
  A mapping function is needed: ToolHolderCatalogRecord → (holder_diameter_mm, holder_length_mm).
  Currently: holder geometry always UNKNOWN in build_verification_input (not populated from catalog).

P9_HOLDER_ENRICHMENT_FEASIBLE=YES
  Holder records have manufacturer + product_family + catalog_code fields.
  body_diameter and overall_length derivable from manufacturer technical data.
```

### MUST 27 — Fixture / Workholding

```
FIXTURE_LIBRARY_STATUS=SCHEMA_ONLY_NO_CATALOG

What P8 provides:
  FixtureInput: frozen dataclass with provenance tracking
  to_fixture_geometry(): converts to FixtureGeometry for verification engine
  Trustworthy filter: UNKNOWN-provenance excluded from collision checks

What is missing for P9:
  1. FIXTURE PRIMITIVES (seed catalog):
     Standard vise jaws for DXF-01/03 workpiece size (~50×80mm part)
     Standard ER32/ER40 collet dimensions (for cylindrical workpieces)
     Clamp geometry for flat plate workholding

  2. FIXTURE WORKFLOW WIRING:
     Engineer must supply FixtureInput at NC generation time.
     No API endpoint, no session state, no production workflow step currently
     propagates fixture geometry from engineer input to build_verification_input.

  3. CUSTOM FIXTURE IMPORT:
     Not required for P9 — standard primitives cover DXF-01/03 workholding.

  PRIORITY RANKING:
  1. Fixture primitives (vise + clamps): HIGH_VALUE — unblocks ALL collision checks
  2. Production workflow wiring (fixture at NC gen time): REQUIRED_FOR_PRODUCTION_USE
  3. Custom fixture import: LATER
  4. Keep-out zones: covered by FixtureInput box primitives
  5. Clamping surfaces: LATER (requires 3D solid, not primitives)
```

### MUST 28 — Stock Simulation

```
MINIMUM_VIABLE_TRUSTWORTHY_SIMULATION:

Candidate approach comparison:

2.5D height-map:
  Fit for prismatic/drilling: GOOD (DXF-01 vertical holes, uniform depth)
  Complexity: MEDIUM (requires scanline or column simulation)
  Accuracy: MEDIUM (misses side-wall encounters)
  Dependencies: none (pure Python)
  Windows/Linux: YES/YES
  Licensing: N/A

Voxel (current implementation):
  Fit for prismatic/drilling: GOOD (discrete but accurate for drill depth)
  Complexity: ALREADY IMPLEMENTED in backend/verification/stock.py
  Accuracy: Conservative (voxel size trades accuracy for speed)
  Dependencies: none (pure Python numpy-compatible)
  Windows/Linux: YES/YES
  Licensing: N/A
  Status: FUNCTIONAL BUT NOT WIRED (StockModel not propagated from StockDefinition)

Mesh boolean (OpenMesh, trimesh):
  Fit for prismatic/drilling: EXCELLENT
  Complexity: HIGH (B-Rep boolean operations)
  Dependencies: trimesh (MIT) or pymeshlab (GPL-3 risk) — large binary
  Windows/Linux: YES/YES (trimesh); UNCERTAIN (pymeshlab on Windows)
  Licensing: trimesh=MIT (safe); pymeshlab=GPL-3 (requires legal review)
  Recommendation: AVOID for P9

B-Rep boolean (pythonocc-core, cadquery):
  Fit: EXCELLENT; Complexity: VERY HIGH; Dependencies: pythonocc (200MB+)
  Recommendation: DEFER to P10

RECOMMENDED FOR P9:
  Voxel engine — already implemented, no new dependency.
  Wire StockDefinition → StockModel → run_simulation().
  This gives functional stock removal simulation for all prismatic samples.
```

### MUST 29 — Collision Engine Priority

```
MINIMUM P9 COLLISION SCOPE (ranked by value):

1. tool vs fixture (HIGH):
   - Requires: fixture seed catalog + workflow wiring + FixtureInput in build_vi
   - Engine: check_tool_collision() — IMPLEMENTED
   - Current state: NOT_VERIFIABLE (no fixture geometry)
   - P9 target: PASS/FAIL for standard vise workholding

2. machine envelope (DONE in P8-E):
   - Already wired; PASS/FAIL for DXF-02/03; FAIL for DXF-01 raw (WCS offset expected)

3. tool vs stock (HIGH):
   - Requires: StockModel from StockDefinition (voxel wiring)
   - Engine: check_stock_gouge() + check_stock_remaining() — IMPLEMENTED
   - Current state: NOT_VERIFIABLE (stock_model=None)
   - P9 target: PASS/FAIL for explicitly supplied stock

4. holder vs fixture (MEDIUM):
   - Requires: holder geometry population BEFORE fixture wiring
   - Blocked by: holder body_diameter=3/17, overall_length=0/17
   - P9 target: PASS/FAIL only after holder enrichment

5. tool vs part (DEFER to STEP availability):
   - Requires: part_bbox_min/max from STEP solid
   - Current: NOT_VERIFIABLE permanently without STEP
   - Cannot be unblocked without Class A STEP sample

6. holder vs part (DEFER):
   - Requires: holder geometry + part solid
   - Both absent → double-blocked
```

### MUST 30 — Toolpath Verification

```
TOOLPATH_GEOMETRY_MATURITY=MEDIUM

Current P7 toolpath structure:
  nc_segments: list of dicts with start/end x/y/z, motion_type, is_cutting, operation_id
  3 segments per hole: APPROACH (RAPID) + DRILL (CUT) + RETRACT (RAPID)
  Coordinates derived from hole center + depth + clearance height

What is sufficient for P9:
  Segment sampling: YES (segments have 6 DOF start/end points)
  Swept-volume approximation: PARTIAL — cylinder swept from diameter + segment line
    is what check_tool_collision() uses; sufficient for simple prismatic
  Rapid validation: YES — RAPID segments present (approach/retract wired)
  Feed-motion validation: YES — CUT segments present (drill stroke wired)

What is missing for future phases:
  Helix motion: HELIX mapped to CUT — tangential velocity not modeled
  5-axis kinematics: not present (all segments are linear)
  Arc motion: not present (drilling is linear only)
  Tool axis vector: not in current segment model — needed for 3-axis sim

P9 scope (prismatic/drilling) is well-served by current toolpath geometry.
```

### MUST 31 — Simulation Dependency

```
REQUIRED_FOR_P9=NO new dependencies

Voxel stock simulation: numpy only (already in requirements)
  LICENSE=BSD-3; COMMERCIAL_USE=YES; WINDOWS=YES; LINUX=YES
  BINARY_SIZE_RISK=NONE (already installed); RECOMMENDATION=USE_EXISTING_ENGINE

Required for STEP parsing (P9-F only):
cadquery:
  LICENSE=Apache-2.0; COMMERCIAL_USE=YES; WINDOWS=YES; LINUX=YES
  PYTHON_SUPPORT=YES; BINARY_SIZE_RISK=MEDIUM (~150MB conda/pip install)
  MAINTENANCE_STATUS=Active (weekly commits); RECOMMENDATION=USE_IF_STEP_REQUIRED

pythonocc-core:
  LICENSE=LGPL-2.1; COMMERCIAL_USE=YES (LGPL); WINDOWS=YES; LINUX=YES
  PYTHON_SUPPORT=YES; BINARY_SIZE_RISK=HIGH (~200MB); MAINTENANCE_STATUS=Active
  RECOMMENDATION=ALTERNATIVE_TO_CADQUERY (lower-level OCCT access)

trimesh (mesh-based collision only):
  LICENSE=MIT; COMMERCIAL_USE=YES; WINDOWS=YES; LINUX=YES
  PYTHON_SUPPORT=YES; BINARY_SIZE_RISK=LOW (~10MB + scipy optional)
  MAINTENANCE_STATUS=Active; RECOMMENDATION=MEDIUM_TERM_OPTION (after STEP)

ACTION: DO NOT INSTALL anything until STEP samples are confirmed available.
```

### MUST 32 — Boring Priority

```
BORING_REAL_SAMPLE_VALUE=LOW
  DXF-02 is a single sample with one ~60mm bore feature.
  The P8 verification infrastructure (collision, stock, envelope) applies equally
  to boring and drilling — boring is a CAM strategy gap, not a verification gap.

BORING_IMPLEMENTATION_COMPLEXITY=HIGH
  New CAM operation type: single-point boring (reciprocating motion, sizing pass)
  New toolpath generator: generate_boring_toolpath() (not drill-based)
  New process parameters: boring bar Vc, fn, back engagement, fine pass allowance
  New catalog capability: boring bar eligible for boring operation (new flag)
  Risk: boring requires precise cutting data confirmation; no current data sourced

BORING_P9_PRIORITY=LOW
  Rationale:
  - Only one real sample (DXF-02) benefits from boring
  - Verification infrastructure (collision/stock/envelope) is higher safety value
  - Flute geometry enrichment unblocks tool_reach for ALL 18 drills vs. 1 boring sample
  - Boring implementation requires significant CAM + catalog work for minimal sample gain
  - DEFER until geometric verification baseline (fixture, stock, STEP) is established
```

### MUST 33 — DXF-03 Large Tools

```
FIRST_BLOCKER=flute_length_mm missing for sandvik-860-1-1600/1800/2400

Detail:
  sandvik-860-1-1600-073a1-pm: cutting_length=73mm, flute_length=None
  sandvik-860-1-1800-083a1-pm: cutting_length=83mm, flute_length=None
  sandvik-860-1-2400-110a1-pm: cutting_length=110mm, flute_length=None

After flute_length population:
  NEXT_BLOCKER=fixture geometry (tool_collision=NOT_VERIFIABLE)
  THEN=stock definition (stock_removal=NOT_VERIFIABLE)
  THEN=STEP (gouge=NOT_VERIFIABLE)

Cutting data: not in catalog (engineer-confirmed at parameter confirmation time — correct).
Machine capability: Haas VF-2SS spindle supports all three diameters.
Toolpath support: generate_drill_toolpath() supports any diameter.
```

### MUST 34 — STEP Qualification Requirements

```
STEP intake requirements: See docs/qualification/STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md

Recommended parts (non-confidential, simplest valid geometry):

1. simple_drilling_block.step
   Description: 100×80×30mm rectangular block, 4× Ø5mm through-holes on 20mm pitch
   Features: prismatic exterior, 4× through holes
   Why: matches DXF-01 feature type; enables immediate part-gouge and stock-removal test
   Qualification: Class A

2. blind_hole_block.step
   Description: 60×60×25mm block, 2× Ø8mm blind holes, depth 20mm
   Features: blind holes (no exit face)
   Why: tests depth check without through-hole simplification
   Qualification: Class A

3. pocket_block.step
   Description: 80×60×30mm block, one 30×20×15mm rectangular pocket
   Features: closed pocket, vertical walls, floor radius
   Why: requires holder clearance check; end-mill reach scenario
   Qualification: Class B

ACQUISITION PATH:
  Option 1: Design in-house using FreeCAD or similar (CC0, full provenance)
  Option 2: NIST MBE PMI Validation test cases (STEP AP214, public domain)
  Option 3: Engineer-supplied anonymized part (remove metadata before commit)
```

### MUST 35 — Postprocessor Priority

```
POSTPROCESSOR_P9_PRIORITY=DEFER

Rationale:
  Current state: GENERIC_ISO_TEST_V1 (test/offline profile only; NOT_CLAIMED for any controller)
  P9 value: LOW — adding a controller-specific postprocessor profile requires:
    1. Physical machine test (actual G-code execution on real machine) — not available
    2. Controller reference documentation + application engineering
    3. Cycle definition validation (canned cycles: G81, G83, etc.)
    4. Machine-specific alarm codes, axis limits, block format
  Without a physical machine test, ANY controller-specific profile would be fabricated
  compatibility — expressly forbidden by architecture invariant.

  Higher P9 priorities (fixture, flute data, stock) contribute directly to collision
  safety without requiring machine access. Postprocessor validation is a separate
  engineering domain that requires hardware, not software.

  Recommendation: DEFER postprocessor validation until:
  - Geometric verification is at PASS state (not just INSUFFICIENT_DATA)
  - A physical machine test facility is identified and accessible
```

### MUST 36 — P9 Candidates

```
Evidence-backed candidates:

P9-A — Manufacturer-backed Tool Geometry Enrichment
  Populate flute_length_mm and overall_length_mm for all 18 drills
  from Sandvik CoroDrill 860-1 technical data sheets.
  Also: wire build_verification_input to pass tool_record from cutting tool catalog.
  
P9-B — Holder Geometry Library Completion
  Populate body_diameter_mm and overall_length_mm for all 17 holder records.
  Implement build_verification_input → ToolHolderCatalogRecord lookup
  to populate holder_diameter_mm, holder_length_mm in P8VerificationInput.

P9-C — Fixture / Workholding Geometry
  Seed FixtureInput catalog with standard primitives:
    - Standard 100mm machinist vise (jaw width, opening range, jaw height)
    - 150mm vise (larger capacity for DXF-03 features)
    - Step clamp sets (simple box primitives)
  Wire engineer-supplied FixtureInput into production NC generation workflow.

P9-D — Bounded Offline Collision Engine (voxel wiring)
  Wire StockDefinition → stock_definition_to_stock_model() → SimulationRequest.stock
  Requires: engineer supplies StockDefinition at NC generation time.
  No new dependencies — VoxelGrid already implemented.

P9-F — Real STEP/B-Rep Qualification
  Acquire 3 STEP samples (see MUST 34 intake spec).
  Implement STEP parser → part_bbox_min/max extraction.
  Wire part_bbox into build_verification_input.
  Enables: check_part_gouge() PASS/FAIL for first time.
  Requires: cadquery or pythonocc-core (new dependency).

Excluded candidates:
  P9-G — Boring: LOW priority (single sample, high complexity — DEFER)
  P9-H — Postprocessor: DEFER (requires physical machine test)
```

### MUST 37 — Prioritization

| Candidate | SAFETY | ENGINEERING | SAMPLE_GAIN | COMMERCIAL | DATA_AVAIL | COMPLEXITY | DEP_RISK | TESTABILITY | Rank |
|---|---|---|---|---|---|---|---|---|---|
| **P9-A** Tool Geometry Enrichment | HIGH | HIGH | HIGH | MEDIUM | HIGH | LOW | NONE | HIGH | **CRITICAL** |
| **P9-C** Fixture/Workholding | HIGH | HIGH | HIGH | MEDIUM | MEDIUM | MEDIUM | NONE | HIGH | **CRITICAL** |
| **P9-D** Voxel Stock Wiring | MEDIUM | HIGH | MEDIUM | MEDIUM | HIGH | LOW | NONE | HIGH | **HIGH** |
| **P9-B** Holder Geometry | MEDIUM | HIGH | MEDIUM | MEDIUM | HIGH | LOW | NONE | HIGH | **HIGH** |
| **P9-F** STEP Qualification | HIGH | HIGH | HIGH | HIGH | LOW | HIGH | MEDIUM | MEDIUM | **HIGH** (conditional) |
| **P9-G** Boring | LOW | MEDIUM | LOW | MEDIUM | MEDIUM | HIGH | LOW | MEDIUM | **LOW** |
| **P9-H** Postprocessor | LOW | MEDIUM | LOW | HIGH | LOW | HIGH | LOW | LOW | **DEFER** |

### MUST 38 — Selected P9 Workstreams

```
P9_RECOMMENDED_WORKSTREAMS=[P9-A, P9-C, P9-D, P9-B, P9-F]

Maximum 5 workstreams selected:

P9-A (CRITICAL): Manufacturer-backed tool geometry enrichment
  Primary: flute_length_mm for all 18 drills → unblocks tool_reach for ALL samples
  Secondary: overall_length_mm for all 18 drills → enables holder offset position
  Also: wire tool_record parameter through build_verification_input from catalog lookup
  Data source: Sandvik CoroDrill 860-1 technical data sheets (no fabrication)
  Tests: ~20 (per-record flute completeness, tool_reach PASS/FAIL replaces INSUFFICIENT)

P9-C (CRITICAL): Fixture / workholding geometry  
  Seed fixture primitive catalog: standard vise + clamps for DXF-01/03 workpiece size
  Wire FixtureInput into production NC generation workflow
  Enables: tool_collision_validated and fixture_collision_validated to exit NOT_VERIFIABLE
  Tests: ~25 (fixture catalog, workflow wiring, collision PASS/FAIL per sample)

P9-D (HIGH): Voxel stock removal wiring
  Wire StockDefinition → stock_definition_to_stock_model() → SimulationRequest.stock
  Add StockDefinition input to build_verification_input / NC generation workflow
  Enables: stock_removal_validated to exit NOT_VERIFIABLE for explicit stock
  Tests: ~15 (stock adapter, voxel integration, stock removal per sample)

P9-B (HIGH): Holder geometry library completion
  Populate body_diameter_mm + overall_length_mm for all 17 holder records
  Wire ToolHolderCatalogRecord → holder_diameter_mm in P8VerificationInput
  Enables: holder_collision_validated to exit NOT_VERIFIABLE for known holders
  Tests: ~15 (holder catalog audit, adapter wiring, holder collision PASS/FAIL)

P9-F (HIGH, conditional): Real STEP qualification
  Conditional on: 3 STEP samples acquired per STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md
  Implement STEP bbox extraction → part_bbox_min/max in build_verification_input
  Enables: gouge_validated to exit NOT_VERIFIABLE for first time
  New dependency: cadquery (Apache-2.0) or pythonocc-core (LGPL-2.1)
  Tests: ~15 (STEP parser, bbox extraction, gouge PASS/FAIL)
  
  NOTE: P9-F execution is gated on STEP sample availability.
  If samples not acquired, P9-F scope = write STEP intake spec only (already done).
```

### MUST 39 — P9 Success Metrics

```
Based on actual P8 baseline:

TOOL_GEOMETRY_READY:
  Baseline: flute_length_mm 0/18, overall_length_mm 5/18
  P9-A target: flute_length_mm 18/18, overall_length_mm 18/18
  Metric: TOOL_REACH_VALIDATED ∈ {PASS, FAIL} for all DXF-01/02/03 features
  (not INSUFFICIENT_DATA)

HOLDER_GEOMETRY_READY:
  Baseline: body_diameter_mm 3/17, overall_length_mm 0/17
  P9-B target: body_diameter_mm 17/17, overall_length_mm 17/17
  Metric: holder_collision_validated ∈ {PASS, FAIL} for at least 1 DXF feature

FIXTURE_GEOMETRY_READY:
  Baseline: no fixture catalog; fixture_collision=NOT_VERIFIABLE for all samples
  P9-C target: standard vise primitive seeded; engineer-supplied fixture wired
  Metric: tool_collision_validated ∈ {PASS, FAIL} for DXF-01/03 with standard vise

TOOL_REACH_VALIDATED:
  Baseline: INSUFFICIENT_DATA for all 18 drills
  P9-A target: PASS or FAIL (depending on feature depth vs. flute length)
  Metric: TOOL_REACH_INSUFFICIENT_DATA_COUNT = 0 for Sandvik 860-1 tools

COLLISION_CHECK_READY:
  Baseline: NOT_VERIFIABLE for all collision checks (fixture-dependent)
  P9-C target: PASS or FAIL for tool vs fixture with standard vise
  Metric: tool_collision_validated ∉ {NOT_VERIFIABLE, NOT_PERFORMED} for ≥1 DXF feature

STOCK_SIMULATION_READY:
  Baseline: NOT_VERIFIABLE (stock_model=None)
  P9-D target: PASS or FAIL for explicitly supplied stock dimensions
  Metric: stock_removal_validated ∉ {NOT_VERIFIABLE} for ≥1 sample with stock

GOUGE_CHECK_READY:
  Baseline: NOT_VERIFIABLE (no STEP geometry)
  P9-F target (conditional): PASS or FAIL for STEP Class A sample
  Metric: gouge_validated ∉ {NOT_VERIFIABLE} for ≥1 STEP sample

REAL_STEP_QUALIFIED:
  Baseline: P8_STEP_QUALIFICATION_STATUS=DEFERRED_REAL_SAMPLE_REQUIRED
  P9-F target: P9_STEP_QUALIFICATION_STATUS=PASS_CLASS_A (after 2 Class A samples tested)

VALIDATED_OFFLINE_WITH_GEOMETRY_CHECK:
  Baseline: VALIDATED_OFFLINE status exists (P7-C); P8 adds P8VerificationResult
  P9 target: VALIDATED_OFFLINE AND at least 2 P8 checks ∈ {PASS, FAIL} for a DXF feature
  (Currently machine_envelope is the only PASS/FAIL check; P9 target ≥2)
```

### MUST 40 — Safety Limit

```
P9 remains OFFLINE_ONLY

Future invariants maintained:
  is_dispatchable=False      ← P8VerificationResult.__post_init__ enforced
  production_released=False  ← P8VerificationResult.__post_init__ enforced
  real_machine_write=False   ← backend/dispatch maintained
  auto_dispatch=False        ← workflow/stage_runners maintained

No geometry enrichment changes NC dispatch eligibility.
No collision check results change dispatch eligibility.
Only engineer-confirmed VALIDATED_OFFLINE status advances the NC candidate —
and even VALIDATED_OFFLINE does not set is_dispatchable=True.
```

### MUST 41 — P9 Test Estimates

```
ESTIMATED_UNIT_TESTS=70-90
  P9-A (flute enrichment):         ~20 (per-record completeness, tool_reach PASS/FAIL)
  P9-B (holder geometry):          ~15 (holder catalog audit, adapter, collision)
  P9-C (fixture wiring):           ~25 (fixture catalog, workflow, collision PASS/FAIL)
  P9-D (stock wiring):             ~15 (stock adapter, voxel integration)

ESTIMATED_INTEGRATION_TESTS=15-20
  DXF-01 tool_reach PASS/FAIL (after flute enrichment)
  DXF-01 tool_collision PASS/FAIL (after fixture wiring)
  DXF-03 tool_reach for 16/18/24mm tools

ESTIMATED_GEOMETRY_TESTS=10-15
  Stock → StockModel adapter, bbox extraction (P9-F conditional)

ESTIMATED_SIMULATION_TESTS=10-15
  Voxel stock removal per sample (P9-D)
  Gouge check (P9-F conditional)

ESTIMATED_REAL_SAMPLE_TESTS=5-10
  DXF-01 → collision WIRED (tool + fixture PASS/FAIL)
  STEP Class A → gouge PASS/FAIL (conditional)

ESTIMATED_TOTAL_NEW_TESTS=110-150
```

### MUST 42 — Architecture Estimate

```
BACKEND_FILES_ESTIMATED=8-12
  cutting_tools/seed_catalog.py         (P9-A: flute_length population)
  cutting_tools/catalog_models.py       (P9-A: no field change needed)
  manufacturing/verification_adapter.py (P9-A/B: wire tool_record + holder_record)
  tool_holders/seed_catalog.py          (P9-B: body_diameter/overall_length population)
  manufacturing/fixture_seed.py         (P9-C: new fixture primitive catalog)
  manufacturing/nc_generation_adapter.py (P9-C/D: wire fixture + stock into build_vi)
  manufacturing/setup_stock.py          (P9-D: StockDefinition already exists; adapter wired)
  cad_import/ (new STEP parser module)  (P9-F conditional)

FRONTEND_FILES_ESTIMATED=0  (P9 is backend-only geometric verification)

LIBRARY_FILES_ESTIMATED=2-4
  Catalog data files for drill flute enrichment and holder geometry
  (P9-F conditional): cadquery requirements.txt addition

NEW_DEPENDENCY_EXPECTED=CONDITIONAL
  P9-A/B/C/D: NO new dependencies
  P9-F (STEP): cadquery or pythonocc-core (confirm after STEP sample acquisition)

DATABASE_CHANGE_EXPECTED=NO
  ArtifactStore sufficient for P8 verification results
```

### MUST 43 — P9 Report Path

```
P9_REPORT_PATH=docs/qualification/REAL_SAMPLE_P9_ASSESSMENT.md
```

---

## Final Report

```
P8_HEAD=e849ff9
P8_ORIGIN_MAIN=e849ff9
P8_WORKTREE_CLEAN=YES

P8_VERIFICATION_ENGINE_WIRED=YES
P8_FAIL_CLOSED=YES
P8_TOOL_REACH_ACCEPTED=YES
P8_MACHINE_ENVELOPE_ACCEPTED=YES
P8_FIXTURE_ACCEPTED=YES
P8_COLLISION_STATUS_ACCEPTED=YES

DXF01_TOOL_REACH        = INSUFFICIENT_DATA  (flute_length_mm missing; correct)
DXF01_MACHINE_ENVELOPE  = FAIL               (raw y=-968mm > Y travel 406mm; WCS setup required)
DXF01_TOOL_COLLISION    = NOT_VERIFIABLE     (no fixture geometry)
DXF01_HOLDER_COLLISION  = NOT_VERIFIABLE     (no holder geometry)
DXF01_FIXTURE_COLLISION = NOT_VERIFIABLE     (no fixture geometry)
DXF01_STOCK_REMOVAL     = NOT_VERIFIABLE     (no stock model)
DXF01_GOUGE             = NOT_VERIFIABLE     (no STEP geometry)

TOOLS_WITH_FLUTE_LENGTH=0/18
TOOLS_WITH_OVERALL_LENGTH=5/18
TOOLS_WITH_HOLDER_GEOMETRY=0  (body_diameter 3/17, overall_length 0/17 in holder catalog)

REAL_STEP_SAMPLE_COUNT=0
REAL_IGES_SAMPLE_COUNT=15
REAL_DXF_SAMPLE_COUNT=57

IS_DISPATCHABLE_TRUE_FOUND=NO
  (validator.py:285 is a guard ERROR message, not an assignment)
PRODUCTION_RELEASE_TRUE_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO

NEW_FAILURES_INTRODUCED=0
REGRESSION_SUITE=974 PASS / 12 SKIP / 1 XPASSED

P8_FINAL_ACCEPTANCE=PASS_P8_FINAL_ACCEPTANCE_WITH_GEOMETRY_DATA_GAPS

P9_ASSESSMENT_EXECUTED=YES

P9_PRIMARY_BOTTLENECK=TOOL_GEOMETRY_DATA_GAP_AND_FIXTURE_GEOMETRY_ABSENT
  flute_length_mm=0/18 → ALL tool_reach checks return INSUFFICIENT_DATA
  fixture_inputs=[] by default → ALL collision checks return NOT_VERIFIABLE
  These two gaps together prevent any PASS/FAIL status except machine_envelope.

P9_REAL_STEP_PRIORITY=REQUIRED
TOOL_GEOMETRY_ENRICHMENT_FEASIBLE=YES  (Sandvik catalog codes → data sheets)
HOLDER_LIBRARY_STATUS=PARTIAL  (17 records; body_diameter 3/17; overall_length 0/17)
FIXTURE_LIBRARY_STATUS=SCHEMA_ONLY_NO_CATALOG
TOOLPATH_GEOMETRY_MATURITY=MEDIUM  (linear 3-segment model sufficient for P9 prismatic)
COLLISION_ENGINE_STATUS=IMPLEMENTED_GEOMETRY_ABSENT
  (All 12 checks implemented; blocked by missing data, not missing code)
STOCK_SIMULATION_STATUS=VOXEL_IMPLEMENTED_NOT_WIRED
GOUGE_STATUS=BBOX_CHECK_IMPLEMENTED_STEP_REQUIRED
BORING_P9_PRIORITY=LOW  (defer; single sample, high complexity)
POSTPROCESSOR_P9_PRIORITY=DEFER  (requires physical machine test)

P9_RECOMMENDED_WORKSTREAMS=[P9-A, P9-C, P9-D, P9-B, P9-F]
  P9-A — Manufacturer-backed Tool Geometry Enrichment (CRITICAL)
  P9-C — Fixture / Workholding Geometry (CRITICAL)
  P9-D — Bounded Offline Collision Engine / Voxel Stock Wiring (HIGH)
  P9-B — Holder Geometry Library Completion (HIGH)
  P9-F — Real STEP/B-Rep Qualification (HIGH, conditional on STEP sample acquisition)

P9_SUCCESS_CRITERIA=
  TOOL_REACH_VALIDATED: INSUFFICIENT_DATA → PASS/FAIL for all 18 drills
  FIXTURE_COLLISION_VALIDATED: NOT_VERIFIABLE → PASS/FAIL for DXF-01/03 with vise
  HOLDER_COLLISION_VALIDATED: NOT_VERIFIABLE → PASS/FAIL for ≥1 DXF feature
  STOCK_REMOVAL_VALIDATED: NOT_VERIFIABLE → PASS/FAIL for explicit stock
  GOUGE_VALIDATED: NOT_VERIFIABLE → PASS/FAIL for STEP Class A (conditional)

P9_ESTIMATED_NEW_TESTS=110-150
P9_ESTIMATED_FILES_AFFECTED=8-12 backend files

PRODUCTION_FILES_CHANGED=0
SOURCE_FILES_CHANGED=NO

P9_REPORT_PATH=docs/qualification/REAL_SAMPLE_P9_ASSESSMENT.md

GO_NO_GO=GO

FINAL_RESULT=PASS_P8_FINAL_ACCEPTANCE_WITH_GEOMETRY_DATA_GAPS_AND_P9_ASSESSMENT_GO
```
