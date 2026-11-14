# Real Sample P4 Assessment

**Campaign:** MACHININGPRO_AI_P4_ASSESSMENT  
**Date:** 2026-11-14  
**Branch:** main | HEAD: 7e19ee6  
**Analyst:** Qualification automation  
**Precondition:** P3 PASS (HEAD = ORIGIN = 7e19ee6; worktree clean)  
**Rule:** PRODUCTION_FILES_CHANGED=0. SOURCE_FILES_CHANGED=NO.

---

## 1. P3 Final State

P3 delivered five committed workstreams (ab62780 → 7e19ee6):

| Workstream | Commit | Status |
|-----------|--------|--------|
| P3-A: Feature & Dimension Review | 7f6cd7e | PASS |
| P3-B: Setup and Stock Definition | 2514cef | PASS |
| P3-C: OCR Activation Path | 356a152 | PASS |
| P3-D: STEP Sample Intake Guide | 4f20890 | DEFERRED (0 real samples) |
| P3-E: GD&T → Process Integration | 7e19ee6 | PASS |

### P3 Metric Achievement

```
P3_FEATURE_CONFIRMED_WORKFLOW=EXISTS (P3-A — live runs pending)
P3_SETUP_STOCK_WORKFLOW=EXISTS (P3-B)
P3_OCR_ACTIVATION_PATH=EXISTS (P3-C — Tesseract binary deferred to deploy)
P3_STEP_INTAKE_GUIDE=EXISTS (P3-D — samples deferred)
P3_GDT_PROCESS_WIRED=YES (P3-E — R-RT-GDT-007/008 in route_generator)

P3_DRAWING_INTELLIGENCE_READY_BEFORE=5
P3_DRAWING_INTELLIGENCE_READY_AFTER=5 (8 when Tesseract installed)

P3_PROCESS_PLANNING_READY_BEFORE=3 (user-assisted)
P3_PROCESS_PLANNING_READY_AFTER=INFRA_COMPLETE (live E2E pending P4-A/B)

P3_CAM_READY_BEFORE=0
P3_CAM_READY_AFTER=0 (blocked on route-wiring gap — see P4-A)

P3_OPEN_DEFECTS=0
P3_NEW_FAILURES_INTRODUCED=0
```

---

## 2. Post-P3 Remaining Blockers

For each of the 9 real sample files, the FIRST blocker preventing CAM_READY.

| File | Current Tier | First Blocker | P4 Workstream |
|------|-------------|--------------|---------------|
| DXF-01 | PROCESS_PLANNING | Confirmed feature not auto-wired to route generator | P4-A |
| DXF-02 | PROCESS_PLANNING | Same + arc ambiguity needs disambiguation | P4-A |
| DXF-03 | PROCESS_PLANNING | Same as DXF-01 | P4-A |
| IGS-01 | FEATURE_CANDIDATE | Material+depth from user; confirmed bore → route wiring | P4-A |
| IGS-02 | FEATURE_CANDIDATE | Same as IGS-01 | P4-A |
| IGS-03 | FEATURE_CANDIDATE | No deterministic machining for 127 freeform surfaces | DEFERRED |
| PDF-01 | DRAWING_INTELLIGENCE | Tesseract not installed → no dimension extraction | P4-F (ops) |
| PDF-02 | DRAWING_INTELLIGENCE | Same | P4-F (ops) |
| PDF-03 | DRAWING_INTELLIGENCE | Same | P4-F (ops) |

---

## 3. Pipeline Wiring Gap Analysis

### Confirmed Feature → Route (P3-A → Level 10 gap)

The P3-A workflow stores confirmed features with `confidence=USER_CONFIRMED` and `depth_mm` from the engineer. However:

1. `POST /confirm-with-dimension` returns the confirmed feature **but does not call `route_generator.generate()`**.
2. `RecognizedFeature` (the route generator's input) wraps a `ManufacturingFeature` from the drawing intelligence pipeline — not from the CAD feature recognition pipeline where P3-A operates.
3. There is no bridge that takes a USER_CONFIRMED `ManufacturingFeature` → `RecognizedFeature` → route generation.

```
ROUTE_WIRING_STATUS=MISSING
  P3-A produces: ManufacturingFeature(confidence=USER_CONFIRMED, depth_mm=<user>)
  Route generator expects: RecognizedFeature (drawing_intelligence pipeline)
  Bridge: DOES NOT EXIST → P4-A
```

### Setup/Stock → CAM Prerequisite Gate (P3-B → CAM gate gap)

The `SetupStockSession` captures all prerequisites (material + stock + setup) but:
1. No `cam_prerequisites_met()` function exists.
2. No endpoint returns `CAM_READY_STATE` per file.
3. The confirmation chain is not checked atomically before routing.

```
CAM_PREREQUISITE_GATE_STATUS=MISSING → P4-B
```

---

## 4. P4 Candidate Workstreams

### Candidate A: Confirmed Feature → Route Generator Bridge (CRITICAL)

**What:** Build the bridge from P3-A's USER_CONFIRMED `ManufacturingFeature` to the route generator. This is the last structural gap before CAM_READY can be measured.

- Adapter: `ManufacturingFeature(USER_CONFIRMED) → RecognizedFeature` with engineer-supplied depth_mm
- Call `route_generator.generate(rf, req_set)` after confirmation
- Include GD&T constraints (P3-E) in the route generation context
- Return generated routes in the `confirm-with-dimension` response
- Safety: routes are advisory; never auto-approve; engineer must review
- Never infer depth from geometry — only use the user-supplied value

**Coverage gain:**
- CAM_READY: 0→3 (DXF-01/02/03 after material + feature confirmation + depth supply)
- ROUTE_GENERATION_WIRED: NO→YES

**Risk:** MEDIUM — adapter must preserve all provenance tags; no fabrication allowed  
**Tests:** ~30 unit + ~10 integration

---

### Candidate B: CAM Prerequisite Gate

**What:** Add `cam_prerequisites_met(session_id)` that checks all blocking prerequisites atomically before route generation is attempted.

- Checks: material confirmed + feature confirmed + feature_type known + depth_mm non-None + stock defined + setup defined
- Returns `CamPrerequisiteState` with per-requirement status
- Exposed as GET `/api/setup-stock/{session_id}/cam-status`
- Route generation endpoint rejects with 422 if prerequisites not met
- Safety: gate never bypassed; human must satisfy each requirement

**Coverage gain:**
- CAM_READY observable: meaningful counter tracked per file
- Prevents fabricated-data routes from slipping through

**Risk:** LOW  
**Tests:** ~20 unit + ~5 integration

---

### Candidate C: Process Route Report Generation

**What:** Generate a human-readable engineering process route report for each confirmed CAM-ready file.

- Input: confirmed features + generated routes + GD&T constraints + stock/setup definition
- Output: HTML report with per-feature route table, operation sequence, GD&T warnings, disclaimer
- Engineering review section: sign-off field (not auto-approved; "PENDING REVIEW" until human confirms)
- Export: HTML (primary), JSON (machine-readable)
- Uses existing HTML export infrastructure from Stage 21C/21D/21E

**Coverage gain:**
- Qualitative: routes move from internal data structure → engineer-reviewable document

**Risk:** LOW  
**Tests:** ~20 unit + ~5 integration

---

### Candidate D: STEP Sample Intake (deferred)

**What:** When real STEP samples arrive, run Level-1 assessment per `docs/qualification/STEP_REAL_SAMPLE_INTAKE_GUIDE.md`.

- Zero code required until samples available
- Level-1 acceptance: import, B-Rep, solids, topology, feature candidates, depth evidence
- Evaluate `pythonocc-core` LGPL license compatibility only after Level-1 confirms value
- If Level-1 passes: consider P4 STEP parser (Level 2 geometry) in P5

**Coverage gain:**
- Potential: IGES replaced by STEP → bore depth recoverable from closed B-Rep
- 0 direct coverage gain until samples arrive

**Risk:** LOW for assessment; HIGH for parser (pythonocc-core build complexity)  
**Decision:** No code in P4; request samples from customer first

---

### Candidate E: Real Sample End-to-End Run

**What:** Run DXF-01 (simple hole drawing) through the full confirmed pipeline:
1. Upload → CAD feature recognition → CIRCLE feature recognized
2. Material confirmed by engineer (C45 or customer-specified)
3. Feature confirmed with depth_mm supplied by engineer
4. Setup defined (stock dimensions + datum A)
5. CAM prerequisites gate: all green
6. Route generated: DRILLING → REAMING (or DRILLING + BORING for tight tolerance)
7. GD&T warnings applied (R-RT-GDT-001 through R-RT-GDT-008)
8. Process route report generated

**Coverage gain:**
- CAM_READY: 0→1 (DXF-01 as proof-of-concept)
- Validates P4-A wiring on real data

**Risk:** MEDIUM — depends on P4-A and P4-B completion; may reveal additional gaps  
**Prerequisites:** P4-A + P4-B must pass first

---

### Candidate F: Tesseract Deployment (ops)

**What:** Install Tesseract binary in development and CI environments.

- Windows dev: `choco install tesseract` or MSI installer at known path
- Render.com: `apt-get install tesseract-ocr` in Dockerfile
- Configure in `hybrid_pdf_drawing.py` via `configure_tesseract_path()`
- Activate Stage 3 OCR for PDF-01/02/03

**Coverage gain:**
- FILES_DRAWING_INTELLIGENCE_READY: 5→8

**Risk:** LOW (code already built in P3-C)  
**Tests:** 3 OCR integration tests (extend existing)

---

## 5. P4 Prioritization Scoring

| Candidate | User Value | Real-Sample Coverage | Eng. Risk | Complexity | Score |
|-----------|-----------|---------------------|-----------|------------|-------|
| A: Confirmed → Route Wiring | HIGH | BLOCKS P4-B/C/E | MEDIUM | MEDIUM | **P0** |
| B: CAM Prerequisite Gate | HIGH | Enables measurement | LOW | LOW | **P0** (combine with A) |
| C: Route Report | HIGH | Actionable output | LOW | LOW | **P1** |
| E: DXF-01 E2E Run | HIGH | 0→1 CAM_READY | MEDIUM | MEDIUM | **P1** (after A+B) |
| F: Tesseract Deployment | MEDIUM | 5→8 drawing-ready | LOW | LOW | **P1** (easy win) |
| D: STEP Intake | MEDIUM (future) | 0 direct | LOW | LOW | **P2** (prerequisite: samples) |

**Recommended P4 workstreams (4 primary + 1 ops):**

1. **P4-A: Confirmed Feature → Route Generator Bridge** (critical path; enables all downstream)
2. **P4-B: CAM Prerequisite Gate** (companion to P4-A; measurable output)
3. **P4-C: Process Route Report Generation** (engineer-reviewable output)
4. **P4-E: Real Sample E2E Run — DXF-01** (validation after P4-A/B)
5. **P4-F: Tesseract Deployment** (ops; easy win; unblocks PDF files)

P4-D deferred until STEP samples arrive.

---

## 6. P4 Success Metrics (Post-P3 Baseline)

```
P4_SUCCESS_CRITERIA=

  ROUTE_GENERATION_WIRED: NO→YES
    (P3-A confirmed ManufacturingFeature bridges to route_generator.generate())

  CAM_READY: 0→3
    (DXF-01/02/03 after material + confirmed feature + depth + setup)
    (At minimum: DXF-01 proof-of-concept via P4-E)

  CAM_PREREQUISITE_GATE: MISSING→EXISTS
    (cam_prerequisites_met() function + API endpoint)

  PROCESS_ROUTE_REPORT: MISSING→EXISTS
    (HTML report with operation sequence, GD&T constraints, review field)

  FILES_DRAWING_INTELLIGENCE_READY: 5→8 (via P4-F Tesseract deployment)

  OPEN_DEFECTS: 0 (invariant — not to be increased)

SAFETY_INVARIANTS_UNCHANGED (carry forward from P3):
  REAL_MACHINE_WRITE_FOUND=NO
  AUTO_CNC_DISPATCH_FOUND=NO
  AUTO_APPROVAL_FOUND=NO
  AUTOMATIC_ADAPTATION_FOUND=NO
  FABRICATED_ENGINEERING_DATA=NO
  LEVEL21_STARTED=NO
```

---

## 7. Architecture Notes for P4

### P4-A: Confirmed Feature → Route Bridge

New bridge module: `backend/interoperability/confirmed_feature_bridge.py`

```
ManufacturingFeature(USER_CONFIRMED) → RecognizedFeature
  - feature_type: from confirmed ManufacturingFeature.feature_type
  - depth_mm: MUST come from confirmed feature; never inferred
  - diameter_mm: from confirmed feature if available
  - recognition_method: USER_CONFIRMED (not geometry-matched)
  - source_req_ids: empty set (no drawing requirements linked yet)
```

After bridge, call:
```python
route_result = route_generator.generate(rf, req_set)
gdt_constraints = extract_gdt_process_constraints(req_set, confidence_map)
```

Return both in `confirm-with-dimension` response under new `route_generation` field.  
Safety notes: `AUTO_APPROVE=NO`. Route is advisory. Response includes disclaimer.

### P4-B: CAM Prerequisite Gate

New function in `backend/manufacturing/setup_stock.py`:

```python
def cam_prerequisites_met(session: SetupStockSession) -> CamPrerequisiteState:
    # Checks: material + feature_confirmed + depth_mm + stock + setup
    # Returns: state per requirement + overall CAM_READY bool
```

New endpoint: `GET /api/setup-stock/{session_id}/cam-status`

### P4-C: Route Report

New module: `backend/drawing_intelligence/route_report.py`

- Uses existing HTML export infrastructure from Stage 21 (audit_package)
- Engineering sign-off field: status=PENDING_REVIEW until human action
- No auto-approval path

---

## 8. P4 Hard Rules (carry forward)

All P3 hard rules remain in force for P4. Additional P4 constraints:

```
P4 HARD RULES:
  Do NOT auto-approve generated routes.
  Do NOT infer depth_mm from geometry in P4-A bridge.
  Do NOT fabricate route_generator output.
  Do NOT start Level 21.
  Do NOT implement STEP parser without real samples.
  Do NOT install pythonocc-core without license review.
  NO force push.
  NO tag.
  NO release.
```

---

## 9. DWG and CATIA V4 Strategy (Unchanged)

```
DWG_STRATEGY=OFFLINE_CONVERSION_GUIDANCE_ONLY (from P2-E; unchanged)
CATIA_V4_STRATEGY=DEFERRED_UNSUPPORTED (unchanged from P1)
```

---

## Final Report

```
P3_HEAD=7e19ee69187e4657ddfe50239d68c9970c4ac562
P3_ORIGIN_MAIN=7e19ee69187e4657ddfe50239d68c9970c4ac562
P3_WORKTREE_CLEAN=YES
P3_FINAL_RESULT=PASS_P3_FINAL_ACCEPTANCE

P4_ASSESSMENT_EXECUTED=YES

P4_REMAINING_BLOCKERS=
  DXF-01/02/03: confirmed feature → route wiring gap (P4-A)
  IGES-01/02: material + depth from user; route wiring gap (P4-A)
  IGES-03: no deterministic machining for freeform (deferred)
  PDF-01/02/03: Tesseract not installed (P4-F ops)
  DWG/MODEL: unsupported format (guidance provided; unchanged)

P4_RECOMMENDED_WORKSTREAMS=5
  P4-A: Confirmed Feature → Route Generator Bridge (critical path)
  P4-B: CAM Prerequisite Gate (companion to P4-A)
  P4-C: Process Route Report Generation
  P4-E: DXF-01 Real Sample E2E Run (after P4-A/B)
  P4-F: Tesseract Deployment (ops; unblocks PDF files)

P4_SUCCESS_CRITERIA=
  ROUTE_GENERATION_WIRED: NO→YES
  CAM_READY: 0→3 (DXF-01/02/03 after full confirmation chain)
  CAM_PREREQUISITE_GATE: MISSING→EXISTS
  PROCESS_ROUTE_REPORT: MISSING→EXISTS
  FILES_DRAWING_INTELLIGENCE_READY: 5→8 (Tesseract)
  OPEN_DEFECTS: 0 (invariant)

P4_ESTIMATED_NEW_TESTS=~85
  P4-A: ~40 (bridge + route endpoint)
  P4-B: ~25 (prerequisite gate)
  P4-C: ~20 (report generation)
  P4-E: 0 new tests (validation run; test coverage from P4-A/B)
  P4-F: ~3 (OCR integration)

PRODUCTION_FILES_CHANGED=0
SOURCE_FILES_CHANGED=NO

P4_REPORT_PATH=docs/qualification/REAL_SAMPLE_P4_ASSESSMENT.md

GO_NO_GO=GO (3 bounded workstreams + 1 validation run + 1 ops task)

FINAL_RESULT=PASS_P3_FINAL_ACCEPTANCE_AND_P4_ASSESSMENT_GO
```

---

*All source sample files verified unchanged. No production code modified during this assessment.
No engineering data fabricated. SAFETY INVARIANTS UNCHANGED.*
