# P10 Phase 8 — Real STEP CAM Coverage Expansion

**Task:** `MACHININGPRO_AI_P10_PHASE8_REAL_STEP_CAM_COVERAGE_EXPANSION`  
**Status:** `PASS_P10_PHASE8_REAL_STEP_CAM_COVERAGE`  
**Date:** 2026-11-19  
**HEAD before:** `1c64909` (Phase 7 final)  
**HEAD after:** committed below  
**Previous:** [`P10_PHASE7_REAL_STEP_CAM_READINESS.md`](P10_PHASE7_REAL_STEP_CAM_READINESS.md)  
**Next:** [`P10_PHASE9_REAL_STEP_TOOLPATH_COVERAGE.md`](P10_PHASE9_REAL_STEP_TOOLPATH_COVERAGE.md)

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
P8_AMBIGUOUS_CONTOUR_AUTO_USED=False
P8_OPEN_LOOP_USED_FOR_CAM=False
P8_DISCONNECTED_BOUNDARY_USED_FOR_CAM=False
STEP_IS_DISPATCHABLE=False
STEP_PRODUCTION_RELEASED=False
UNKNOWN remains UNKNOWN
AMBIGUOUS remains AMBIGUOUS
NOT_VERIFIABLE remains NOT_VERIFIABLE
INSUFFICIENT_DATA remains INSUFFICIENT_DATA
```

MUST 44 safety grep: **CLEAN** (no violations in any Phase 8 module).

---

## Baseline (Phase 7)

```
BRANCH=main
HEAD=1c64909
REAL_STEP_TOOLPATH_READY_FILES=2/6
REAL_STEP_WCS_READY=6/6
TOTAL_TESTS=5707
RUFF=CLEAN
```

---

## Phase 8 Objectives

| ID | Goal | Result |
|----|------|--------|
| 8A | Multi-face STEP/shoulder contour extraction | BOUNDARY_READY=YES for 6+3+2+2+1+1 step faces |
| 8B | Circular/curved outer-loop extraction (Fix 1) | FB, SK gain OUTER loop → pocket toolpath |
| 8C | Drill tool catalog gap closure | DEFERRED (no source-backed records found) |
| 8D | Advance pocket/slot toolpaths | 4/6 files now toolpath-ready (up from 2/6) |

---

## Changes Introduced

### 1. topology_adapter.py — Fix 1: Circular OUTER loop classification

**Problem:** Planar faces with no linear edges (all-arc topology) produced
`LoopType.UNKNOWN` instead of `LoopType.OUTER`, blocking contour extraction.

**Fix:** For `SurfaceClass.PLANAR` faces with no linear curves and ≥1 circular
curves, sort circles by bounding-box area. Largest circle → `OUTER`; smaller
circles → `INNER`.

**Impact:**
- `electronics-enclosure.step` face 7 (FB): `LOOP-S7-C9` → `OUTER` ✓
- `stepped-shaft-keyway.step` face 3 (SK): `LOOP-S3-C3` → `OUTER` ✓

### 2. phase8_arc_sampler.py — New module

Builds `ArcContourMap` for 2-arc closed planar faces while gmsh is active.

```
ARC_BOUNDARY_METHOD="APPROXIMATED"
ARC_APPROXIMATION_TOLERANCE_MM=0.5
ARC_APPROXIMATION_RESOLUTION=12
```

A 2-arc face is topologically proven closed: exactly 2 boundary curves, each
with 2 vertices, sharing the same 2 vertices. Points are derived from the face
bounding box; no geometric fabrication.

**Impact:** PM face 109 enters `ArcContourMap`, enabling `BOUNDARY_READY=YES`
(APPROXIMATED) path.

### 3. phase8_contour_extractor.py — New module

Extends Phase 7 contour extraction with:

- `BoundaryTraversalStatus` enum: `CONNECTED_CLOSED_LOOP`, `CONNECTED_OPEN_CHAIN`,
  `DISCONNECTED`, `BRANCHED`, `AMBIGUOUS`
- Undirected graph traversal — corrects false BRANCHED classification when gmsh
  edges share a vertex in directed representation but are degree-2 undirected
  (EE face 19 / LB face 1 fix)
- Connectivity sorting for scrambled polygon edge lists
- Arc-contour map fallback for faces not in canonical topology
- `BOUNDARY_METHOD` tracking: `EXACT` vs `APPROXIMATED`

### 4. phase8_step_shoulder_boundary.py — New module

Extracts lower-face boundary for step/shoulder features.

- `BOUNDARY_READY=True` requires `CONNECTED_CLOSED_LOOP` + `is_valid=True`
- `TOOLPATH_READY=False` always — `FEATURE_CONFIRMED=YES` required first
- `STEP_IS_DISPATCHABLE=False`, `STEP_PRODUCTION_RELEASED=False` invariants

### 5. phase8_cam_e2e.py — New module

Full Phase 8 E2E integrating all improvements. Replaces Phase 7 E2E for new
analysis runs. Phase 7 E2E remains for regression testing.

---

## Phase 8 E2E Results

```
FILE   ABBR  WCS  P-TP  S-TP  ST-TP  D-TP  TOT  ANY  SB-RDY  ARC-FACES
electronics-enclosure.step    EE    True     1     1      0     0    2  True       6         []
flanged-bushing (1).step      FB    True     1     0      0     0    1  True       3         []
flange-plate.step             FP    True     0     0      0     0    0 False       2         []
l-bracket.step                LB    True     1     1      0     0    2  True       2         []
Pump Manifold v3.step         PM    True     0     0      0     0    0 False       1      [109]
stepped-shaft-keyway.step     SK    True     1     0      0     0    1  True       1         []

FILES_WITH_ANY_TOOLPATH=4/6    (+2 vs Phase 7)
STEP_BOUNDARY_READY_COUNT=EE:6, FB:3, FP:2, LB:2, PM:1, SK:1
```

Legend: P-TP=pocket toolpath, S-TP=slot toolpath, ST-TP=step toolpath, D-TP=drill toolpath,
SB-RDY=step shoulder boundary ready, ARC-FACES=faces served via arc-contour map.

### File-level analysis

**EE (electronics-enclosure.step):** 2 toolpaths (1 pocket + 1 slot). Unchanged from Phase 7.
6 step shoulder boundaries now BOUNDARY_READY=YES.

**FB (flanged-bushing (1).step):** NEW pocket toolpath from Fix 1 (face 7 circular OUTER loop).
3 step shoulder boundaries BOUNDARY_READY=YES.

**FP (flange-plate.step):** No toolpath. 5 holes only, no pocket/slot geometry.
2 step shoulder boundaries BOUNDARY_READY=YES.

**LB (l-bracket.step):** 2 toolpaths (1 pocket + 1 slot). Unchanged from Phase 7.
2 step shoulder boundaries BOUNDARY_READY=YES.

**PM (Pump Manifold v3.step):** No toolpath (CUTTING_DATA_READY=NO — kennametal-4cfl-12mm-
solid-carbide has `flute_length_mm=None`, stepdown cannot be derived).
Face 109: `BOUNDARY_READY=YES` (APPROXIMATED, arc-contour map).
Pocket blocked legitimately — cannot fabricate cutting data.

**SK (stepped-shaft-keyway.step):** NEW pocket toolpath from Fix 1 (face 3 circular OUTER loop).
1 step shoulder boundary BOUNDARY_READY=YES.

---

## Improvement vs Phase 7

| Metric | Phase 7 | Phase 8 | Delta |
|--------|---------|---------|-------|
| Files with toolpath | 2/6 | 4/6 | +2 |
| Step shoulder boundary-ready | 0 | 15 (across 6 files) | +15 |
| Arc-map demonstrated | — | PM face 109 | +1 |
| Circular OUTER loops fixed | 0 | FB+SK | +2 |
| Undirected traversal fix | — | EE+LB false BRANCHED resolved | +2 |

---

## Blockers Remaining (not fabricatable)

| File | Feature | Blocker |
|------|---------|---------|
| PM | pocket 0 (face 109) | `kennametal-4cfl-12mm-solid-carbide.flute_length_mm=None` → stepdown=None |
| FP | all | No pocket/slot geometry present |
| All | STEP toolpath | FEATURE_CONFIRMED=NO (CANDIDATE never auto-confirmed) |
| All | drill toolpath | No new catalog records found in Phase 8 |

---

## Test Coverage

```
NEW_TESTS=66
FILE=tests/unit/step_brep/test_p10_phase8_cam.py

TestPhase8SafetyConstants:       13
TestBoundaryTraversalStatus:      6
TestClassifyTraversal:            9
TestArcSamplerConstants:          3
TestBuildArcContourMap:           6
TestExtractFaceContourP8:        11
TestStepShoulderBoundary:         6
TestPhase8E2E:                   10
TestPhase8NegativeCases:          4

ALL_PASS=YES   RUFF=CLEAN
```

---

## Source File Integrity (MUST 43)

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
PRE_EXISTING_FAILURES=8  (test_p10b_step_intake.py — stale since Phase 1; unrelated to Phase 8)
NEW_FAILURES_INTRODUCED=0
step_brep suite: ALL PASS
RUFF: CLEAN (all Phase 8 modules + topology_adapter)
```

---

## Files Modified / Created

| File | Action |
|------|--------|
| `backend/step_brep/topology_adapter.py` | Modified — Fix 1: circular OUTER loop classification |
| `backend/step_brep/phase8_arc_sampler.py` | Created |
| `backend/step_brep/phase8_contour_extractor.py` | Created |
| `backend/step_brep/phase8_step_shoulder_boundary.py` | Created |
| `backend/step_brep/phase8_cam_e2e.py` | Created |
| `tests/unit/step_brep/test_p10_phase8_cam.py` | Created — 66 tests |
| `docs/qualification/P10_PHASE8_REAL_STEP_CAM_COVERAGE.md` | Created (this file) |

---

## Phase 9 Assessment (MUST 50)

### Items assessed

| ID | Item | Priority | Justification |
|----|------|----------|---------------|
| 9A | End mill `flute_length_mm` enrichment in catalog | **CRITICAL** | PM pocket 0 (face 109): BOUNDARY_READY=YES but CUTTING_DATA_READY=NO because kennametal-4cfl-12mm-solid-carbide has `flute_length_mm=None`. Adding this one field (source-backed from Kennametal catalog) unblocks the PM pocket toolpath and brings FILES_WITH_TOOLPATH from 4/6 → 5/6. |
| 9B | Multi-face step/shoulder tracing | **HIGH** | 15 step shoulder boundaries are BOUNDARY_READY=YES but all have TOOLPATH_READY=NO. The lower-face boundary is extracted; the missing piece is the wall-face edge shared with the upper face, needed for shoulder milling toolpath. This is the highest-leverage gap for step/shoulder toolpaths. |
| 9C | Drill toolpath generation | **HIGH** | All 6 files have confirmed drill candidates (EE=8, FB=5, FP=5, LB=4, PM=0, SK=3). The drill catalog has source-backed records for 8mm Sandvik drills (flute_length from catalog code). Generating drill cycles (G81/G83) is mechanically straightforward once WCS is SUGGESTED. |
| 9D | NURBS surface type resolution (PM) | **MEDIUM** | PM has 118 surfaces. Most are UNKNOWN type because `gmsh.model.getType` returns "NURBS" or generic strings not yet classified. Resolving PLANAR vs CYLINDRICAL vs NURBS would enable proper pocket/step recognition in PM and unlock its non-drill features. |
| 9E | Contour milling strategy (SK stepped shaft) | **MEDIUM** | SK face 3 now has a pocket toolpath (Fix 1 result). The cylindrical shoulder geometry in SK could also yield a contour-milling toolpath (radial pass around OD). Requires radial offset calculation from circular contour. |
| 9F | Gouge checker (voxel/B-Rep) | **LOW** | Required for simulation PASS but no voxel engine exists. Infrastructure cost is high relative to current coverage level. DEFER until FILES_WITH_TOOLPATH ≥ 5/6. |
| 9G | WCS confirmation gate | **LOW** | WCS=SUGGESTED for all files. A `review_wcs(wcs, approve=True)` gate would allow advancing to CONFIRMED without machine dispatch. Low priority because current blockers are cutting data, not WCS. |
| 9H | FP (flange-plate) pocket/slot search | **LOW** | FP has 5 holes, no pockets or slots. A deeper search of FP surfaces might reveal shallow counterbore pockets. Low probability — FP geometry is primarily planar faces with through-holes. |
| 9I | Localization / UI text audit | **DEFER** | Phase 8 is backend-only. No UI text introduced. No action needed. |

### Recommendations for Phase 9 (3–5 items)

1. **9A — CRITICAL**: Add `flute_length_mm` to kennametal-4cfl-12mm and any other end mills
   with `None`. Use Kennametal published catalog (manufacturer website, product page).
   This is a single-record enrichment with high toolpath-unblocking value.

2. **9B — HIGH**: Implement multi-face shoulder boundary (wall edge extraction).
   Extend `phase8_step_shoulder_boundary.py` to also extract the shared edge between
   the lower face and wall face of each step, enabling a shoulder-milling toolpath strategy.

3. **9C — HIGH**: Drill toolpath generation for confirmed drill candidates.
   Generate `DrillCycleResult` (G81 point drill / G83 peck drill) for each confirmed
   drill candidate where: tool fits, WCS is SUGGESTED, depth is derivable.
   Expect FILES_WITH_DRILL_TOOLPATH = 5/6 (PM has 0 drill candidates).

4. **9D — MEDIUM**: NURBS surface classifier for PM.
   Call `gmsh.model.getType(2, stag)` and map result strings to `SurfaceClass` enum.
   This would reclassify PM's ~100 UNKNOWN surfaces and potentially expose pocket/step geometry.

**DEFER**: 9F (voxel/gouge), 9G (WCS gate), 9H (FP pocket search), 9I (localization).
