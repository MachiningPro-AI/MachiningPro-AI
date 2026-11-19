# P10 Phase 9 — Real STEP Toolpath Coverage Closure

**Task:** `MACHININGPRO_AI_P10_PHASE9_REAL_STEP_TOOLPATH_COVERAGE_CLOSURE`  
**Status:** `PASS_P10_PHASE9_WITH_TOOL_GEOMETRY_GAPS`  
**Date:** 2026-11-19  
**HEAD before:** `da04e11` (Phase 8 final)  
**HEAD after:** committed below  
**Previous:** [`P10_PHASE8_REAL_STEP_CAM_COVERAGE.md`](P10_PHASE8_REAL_STEP_CAM_COVERAGE.md)  

---

## Safety Invariants (enforced, never bypassed)

```
IS_DISPATCHABLE=False         (all modules, all outputs)
PRODUCTION_RELEASED=False
REAL_MACHINE_WRITE=False
AUTO_CNC_DISPATCH=False
AUTO_APPROVAL=False
AUTOMATIC_ADAPTATION=False
REVIEW_REQUIRED=True
WCS_PROVENANCE=SUGGESTED      (bbox-derived only; never USER_CONFIRMED)
FEATURE_CONFIRMED=NO          (CANDIDATE remains CANDIDATE)
P9B_TOOLPATH_READY=False      (always; FEATURE_CONFIRMED=NO gate)
P9C_PARAMETERIZED_CAM_READY=False  (Vc/fn not in scope for Phase 9)
UNKNOWN remains UNKNOWN
AMBIGUOUS remains AMBIGUOUS
NOT_VERIFIABLE remains NOT_VERIFIABLE
```

MUST 38 safety grep: **CLEAN** — no `is_dispatchable=True`, `production_released=True`,
`auto_cnc_dispatch=True`, `auto_approval=True`, or `automatic_adaptation=True` in any
Phase 9 source module.

---

## Baseline (Phase 8)

```
BRANCH=main
HEAD=da04e11
REAL_STEP_TOOLPATH_READY_FILES=4/6
REAL_STEP_WCS_READY=6/6
TOTAL_TESTS=5773
RUFF=CLEAN
```

---

## Phase 9 Objectives

| ID | Goal | Result |
|----|------|--------|
| 9A | Add `flute_length_mm` for kennametal-4cfl-12mm-solid-carbide | DEFERRED |
| 9B | Multi-face shoulder boundary extraction + CAM assessment | IMPLEMENTED |
| 9C | Drill cycle assessment with TOOL_CATALOG_GAP reporting (MUST 19) | IMPLEMENTED |

---

## P10-9A: End Mill Flute Length Enrichment

**Status:** DEFERRED — SOURCE_EVIDENCE_REQUIRED

**Record:** `kennametal-4cfl-12mm-solid-carbide`  
- `evidence_status="UNVERIFIED"`  
- `catalog_code=None`  
- `flute_length_mm=None`  

**Investigation:** Web searches for Kennametal 12mm solid carbide square-end mill
returned GOmill GP 4-flute and HARVI I TE families, but no specific product page
with verified `flute_length_mm` for a square-end 12mm 4-flute end mill matching
the existing unverified record.

**Decision:** HARD RULES 1–5 prohibit fabricating or inferring flute_length from
neighboring SKUs. Record remains unchanged. PM pocket blocked legitimately.

**Impact:** `FILES_WITH_TOOLPATH` unchanged (4/6).

---

## P10-9B: Multi-Face Shoulder Boundary Extraction

**Module:** `backend/step_brep/phase9_shoulder_cam.py`

### Design

Phase 8 extracted the OUTER BOUNDARY of the lower face (for pocket floor finishing).
Phase 9B extracts the SHOULDER EDGE — the set of edges shared between the lower face
and the wall face in the canonical topology. This edge is the actual milling contour
for a shoulder/profile milling operation.

**Method:**
1. For each `StepShoulderRecord`, call `_find_shared_edges(lower_face_tag, wall_face_tag, topo)`
2. Set intersection on existing topology — no second topology graph (MUST 10)
3. Classify shared edges via `_classify_shoulder_boundary` (reuses Phase 8 `_classify_traversal`)
4. Report `MultiShoulderStatus`: VALID_MULTI_FACE_SHOULDER | OPEN_CHAIN | DISCONNECTED | BRANCHED | NO_SHARED_EDGES

**Safety:**
- `TOOLPATH_READY=False` always — `FEATURE_CONFIRMED=YES` required (MUST 15)
- `tool_ready=False` always in Phase 9 (shoulder mill selection deferred)
- `cam_ready = boundary_ready AND depth_ready` (excludes tool_ready, deferred)

### Results

```
FILE  TOTAL  BOUNDARY_VALID  DEPTH_RDY  CAM_RDY  TOOLPATH
EE    7      5               6          5        0 (FEATURE_CONFIRMED=NO)
FB    3      3               2          2        0
FP    2      0               0          0        0
LB    2      2               1          1        0
PM    4      0               1          0        0
SK    1      1               1          1        0
---  ---    ---              ---       ---      ---
TOT  19      11              11         9        0
```

**Key observations:**
- PM: shoulder candidates have OPEN_CHAIN or NO_SHARED_EDGES (complex NURBS topology)
- FP: shared edges not found for the two shoulder candidates (planar plate geometry)
- 11 of 19 shoulders have VALID_MULTI_FACE_SHOULDER boundary — ready for shoulder
  milling when FEATURE_CONFIRMED policy is defined

---

## P10-9C: Drill Cycle Assessment

**Module:** `backend/step_brep/phase9_drill_cam.py`

### MUST 19 Separation

```
GEOMETRIC_TOOLPATH_READY = wcs_ready AND tool_ready AND depth_ready AND is_axial
PARAMETERIZED_CAM_READY  = GEOMETRIC_TOOLPATH_READY AND Vc/fn known
                         = always False (generate_drill_toolpath does NOT use Vc/fn)
```

The existing `generate_drill_toolpath` generates APPROACH/PLUNGE/RETRACT segments
using only geometry (position, depth, clearance). No cutting speed is required.
Therefore GEOMETRIC_TOOLPATH_READY = PARAMETERIZED_CAM_READY when tool matches,
and the separation is documented without blocking toolpath generation.

### Catalog Gap Analysis

All drill candidates in all 6 real STEP files have `TOOL_CATALOG_GAP=True`:

```
FILE  INTERNAL_CYLS  TOOL_MATCHED  CATALOG_GAP  GAPS (mm)
EE    8              0             8            2.5, 7.0
FB    1              0             1            20.0
FP    4              0             4            9.0
LB    4              0             4            6.6
PM    0              0             0            (no holes)
SK    0              0             0            (no INTERNAL cylinders)
```

**Gap sizes vs. catalog coverage:**

| Diameter | Gap | Available catalog | Closest available |
|----------|-----|-------------------|-------------------|
| 2.5mm | YES | 3.0mm Sandvik 860-1 / Kennametal B221A | COMPATIBLE_MATCH (compat=7%, dist=20%) — NO_MATCH |
| 6.6mm | YES | 6.0mm or 8.0mm | — NO_MATCH |
| 7.0mm | YES | 6.0mm or 8.0mm | COMPATIBLE_MATCH for 8mm possible? dist=14% > 7% limit — NO_MATCH |
| 9.0mm | YES | 8.0mm or 12.0mm | — NO_MATCH |
| 20.0mm | YES | 18.0mm or 24.0mm | — NO_MATCH |

**Investigation:** Web searches for Sandvik CoroDrill 860-1 7mm and 9mm returned no
official coromant.sandvik.com product pages confirming catalog codes for these sizes.
Kennametal B221A 7mm not found in B221A series (different series B211SGL confirmed).
No source-backed records added per HARD RULES 1–3.

**Result:** `DRILL_TOOLPATH_COUNT=0` for all files (tool catalog gaps not bridged).

---

## Phase 9 E2E Results

**Module:** `backend/step_brep/phase9_cam_e2e.py`

```
FILE   WCS  P8-TP  9B-SRDY  9C-GAP  9C-TP  TOTAL  ANY_TP
EE     True   2       5         8      0      2     True
FB     True   1       3         1      0      1     True
FP     True   0       0         4      0      0     False
LB     True   2       2         4      0      2     True
PM     True   0       0         0      0      0     False
SK     True   1       1         0      0      1     True

FILES_WITH_ANY_TOOLPATH=4/6    (unchanged from Phase 8)
FILES_BASELINE_PRESERVED=YES   (EE=2, FB=1, LB=2, SK=1)
NEW_TOOLPATHS_INTRODUCED=0     (catalog gaps block advancement)
```

**Why 4/6 unchanged:** All drill hole diameters in real STEP files (2.5, 6.6, 7.0,
9.0, 20.0mm) are absent from the catalog. Shoulder toolpaths blocked by MUST 15
(FEATURE_CONFIRMED=NO always). PM pocket blocked by P10-9A DEFERRED. No fabrication.

---

## Blockers Remaining

| File | Feature | Blocker | Action |
|------|---------|---------|--------|
| PM | pocket 0 | `kennametal-4cfl-12mm.flute_length_mm=None` | 9A deferred |
| FP | drill (4×9mm) | 9mm drill not in catalog | Add source-backed 9mm record |
| EE | drill (4×7mm, 4×2.5mm) | 7mm, 2.5mm not in catalog | Add source-backed records |
| LB | drill (4×6.6mm) | 6.6mm not in catalog | Add source-backed record |
| FB | drill (1×20mm) | 20mm not in catalog | Add source-backed record |
| All | shoulder toolpath | FEATURE_CONFIRMED=NO always | Define confirmation policy |

---

## Test Coverage

```
NEW_TESTS=80
FILE=tests/unit/step_brep/test_p10_phase9_cam.py

TestPhase9SafetyConstants:          15
TestMultiShoulderStatus:             8
TestFindSharedEdges:                 6
TestClassifyShoulderBoundary:        3
TestAssessShoulderCAM:              10
TestShoulderCAMResult:               4
TestDrillCycleAssessment:           12
TestDrillCycleResult:                5
TestPhase9E2ESafetyInvariants:       9
TestPhase9FalsePositive:             5
TestPhase9NegativeCases:             4
(1 test not counted — classified inline)

ALL_PASS=YES   RUFF=CLEAN
```

---

## Source File Integrity

```
ALL_REAL_CAD_SOURCE_FILES_UNCHANGED=YES
PATH=D:\makina_ogrenmesi\olcum_denemeleri  (READ ONLY, never committed)

sha256[:16]       size       filename
8596ec93c6b3fa01  504693     Pump Manifold v3.step
ee3f6c357a3c3b9e   96840     electronics-enclosure.step
a841f9969883e698   55727     flange-plate.step
1c2a82b15b1c78ba   19712     flanged-bushing (1).step
821f8113f6d6aa7b   43506     l-bracket.step
570efc7d414b5bab   44940     stepped-shaft-keyway.step
```

---

## Regression

```
PRE_EXISTING_FAILURES=8  (test_p10b_step_intake.py — stale since Phase 1; unrelated)
NEW_FAILURES_INTRODUCED=0
step_brep suite: ALL PASS
cutting_tools suite: ALL PASS
RUFF: CLEAN (all Phase 9 modules)
```

---

## Files Created

| File | Description |
|------|-------------|
| `backend/step_brep/phase9_shoulder_cam.py` | Multi-face shoulder boundary extraction + CAM |
| `backend/step_brep/phase9_drill_cam.py` | Drill cycle assessment (MUST 19 separation) |
| `backend/step_brep/phase9_cam_e2e.py` | Phase 9 E2E (wraps Phase 8 + 9B + 9C) |
| `tests/unit/step_brep/test_p10_phase9_cam.py` | 80 tests |
| `docs/qualification/P10_PHASE9_REAL_STEP_TOOLPATH_COVERAGE.md` | This file |

---

## Phase 10 Assessment

| ID | Item | Priority | Description |
|----|------|----------|-------------|
| 10A | End mill catalog expansion | CRITICAL | kennametal-4cfl-12mm flute_length from official catalog — unblocks PM pocket (5/6) |
| 10B | Drill catalog: 7mm, 9mm source-backed entries | HIGH | Unblocks EE (4×7mm) + FP (4×9mm) → 2+ new files toolpath-ready |
| 10C | Drill catalog: 6.6mm, 2.5mm, 20mm | MEDIUM | Additional drill coverage for LB, EE, FB |
| 10D | Shoulder mill selection wiring | MEDIUM | Phase 9B builds boundary; tool selection needed to complete CAM assessment |
| 10E | FEATURE_CONFIRMED policy | LOW | Explicit operator confirmation gate to advance CANDIDATE → CONFIRMED |
| 10F | NURBS surface classifier (PM) | LOW | Reclassify PM's UNKNOWN surfaces to unlock pocket/step recognition |
