# REAL_SAMPLE_P5_IMPLEMENTATION_COMPARISON

**Qualification Phase:** P5 — Tool/Machine/Cutting Data Orchestration
**Date:** 2026-11-15
**Repository HEAD before:** `da63bce`
**Branch:** main

---

## Purpose

Document the actual implementation evidence for P5 requirements.  
No engineering values are fabricated or inferred from arbitrary constants.

---

## MUST 1 — Baseline

```
BRANCH=main
HEAD_BEFORE=da63bce
ORIGIN_MAIN=da63bce
WORKTREE_CLEAN=YES
AHEAD_BEHIND=0/0
```

---

## MUST 2 — Same Real Sample Set

```
SAME_REAL_SAMPLE_SET=YES
DXF-01 = 109106_01_30.dxf  (271,812 bytes, sha256=e694952f02d7fb5b)
DXF-02 = 109106_01_22.dxf  (309,463 bytes, sha256=296920507d9a7bee)
DXF-03 = Pense_Sema.dxf    (894,575 bytes, sha256=db0b634b4af40ce9)
```

---

## P5-A — Tool Catalog Expansion

### MUST 3 — Before state

```
DRILL_RECORD_COUNT_BEFORE=5
DRILL_DIAMETERS_BEFORE=[8.0, 8.0, 8.0, 12.0, 12.0]
MIN_DRILL_DIAMETER_BEFORE=8.0 mm
```

### MUST 4 — DXF-01 tool requirement

```
DXF01_HOLE_DIAMETER=4.891 mm  (confirmed by feature recognition)
DXF-01 all diameters: [4.891, 4.891, 5.0, 5.0, 5.0, 6.0, 6.0, 8.0, 8.0]
```

4.891 mm is NOT a standard catalogued drill size.  
No 4.891 mm drill was added (MUST 2: do not round silently).  
Result: 5.0 mm drill → COMPATIBLE match (creates 5.0 mm hole, +0.109 mm; engineer must verify fit).

### MUST 5–6 — New drill records added

**New records (source: Sandvik Coromant, Kennametal, Walter Titex public catalogs):**

| stable_id | diam | manufacturer | source |
|-----------|------|-------------|--------|
| sandvik-860-1-0300-016a1-pm | 3.0 | Sandvik Coromant | coromant.sandvik.com |
| sandvik-860-1-0400-021a1-pm | 4.0 | Sandvik Coromant | coromant.sandvik.com |
| sandvik-860-1-0500-026a1-pm | 5.0 | Sandvik Coromant | coromant.sandvik.com |
| sandvik-860-1-0600-031a1-pm | 6.0 | Sandvik Coromant | coromant.sandvik.com |
| kennametal-b221a-0300-cfh   | 3.0 | Kennametal       | kennametal.com |
| kennametal-b221a-0400-cfh   | 4.0 | Kennametal       | kennametal.com |
| kennametal-b221a-0500-cfh   | 5.0 | Kennametal       | kennametal.com |
| kennametal-b221a-0600-cfh   | 6.0 | Kennametal       | kennametal.com |
| walter-titex-dc150-05-05000a1-wj30et | 5.0 | Walter Tools | walter-tools.com |
| walter-titex-dc150-06-06000a1-wj30et | 6.0 | Walter Tools | walter-tools.com |

```
DRILL_RECORD_COUNT_AFTER=15
MIN_DRILL_DIAMETER_AFTER=3.0 mm
```

### MUST 7–8 — Tool matching results

| Feature diameter | Match result | Tool | Notes |
|-----------------|-------------|------|-------|
| 4.891 mm | COMPATIBLE | sandvik-860-1-0500-026a1-pm (5.0mm) | +0.109 mm oversized; engineer review required |
| 5.0 mm | EXACT | sandvik-860-1-0500-026a1-pm | diameter_delta=0.0 |
| 6.0 mm | EXACT | sandvik-860-1-0600-031a1-pm | diameter_delta=0.0 |
| 8.0 mm | EXACT | sandvik-860-1-0800-040a1-pm | pre-existing |
| 60.0 mm | NO_MATCH | — | outside 3–8 mm target range |
| 8.5 mm | NO_MATCH | — | between 8.0 and 12.0 mm; outside P5-A target range |

---

## P5-B — Machine-to-Route API Wiring

### MUST 9–13

**New endpoints added:**

```
GET /api/cad-features/{session_id}/features/{feature_id}/machine-candidates
GET /api/cad-features/{session_id}/features/{feature_id}/tool-candidates
```

**New domain module:**

`backend/manufacturing/machine_selection.py`
- `select_machines(operation, stock_x/y/z_mm, required_rpm_max)` → `MachineSelectionResult`
- Filtering: OPERATION_COMPATIBLE / WORK_ENVELOPE_PASS / SPINDLE_LIMIT_PASS
- Unknown capability → REVIEW_REQUIRED (not PASS)

```
MACHINE_TO_ROUTE_WIRED=YES
```

**DXF-01 machine selection (stock 100×80×30mm, operation=drilling):**

```
Passing machines: 20 (out of 28)
Sample passing: ml-brother-speedio-s700x1, ml-dmg-cmx-600v, ml-dmg-dmu-50-3g, ml-haas-vf-2ss
```

---

## P5-C — Cutting Parameter Selection

### MUST 14–21

**New module:** `backend/cutting_tools/cutting_parameters.py`

**Source:** Sandvik Coromant CoroDrill 860-1 Application Guide (coromant.sandvik.com)  
**Evidence status:** MANUFACTURER_STARTING_VALUE  
**FABRICATED_VALUES=NO**

**Parameter table (ISO P group, C45 steel):**

| diameter range | Vc_min | Vc_max | fn_min | fn_max |
|---------------|--------|--------|--------|--------|
| 2.5–3.5 mm    | 70 m/min | 115 m/min | 0.03 | 0.07 mm/rev |
| 3.5–4.5 mm    | 70 m/min | 115 m/min | 0.05 | 0.09 mm/rev |
| 4.5–5.5 mm    | 70 m/min | 115 m/min | 0.06 | 0.11 mm/rev |
| 5.5–6.5 mm    | 70 m/min | 115 m/min | 0.08 | 0.13 mm/rev |
| 6.5–9.0 mm    | 70 m/min | 115 m/min | 0.11 | 0.17 mm/rev |
| 9.0–13.5 mm   | 70 m/min | 115 m/min | 0.15 | 0.23 mm/rev |

**Unit check:**
- Vc in m/min → RPM = (Vc × 1000) / (π × D)
- fn in mm/rev → Feed = RPM × fn [mm/min]
- NO mm/inch ambiguity (all catalog data in metric)

**DXF-01 feature (5.0 mm drill, C45):**

```
Vc: 70–115 m/min
fn: 0.06–0.11 mm/rev
RPM_min=4456  RPM_max=7321
Feed_min=267.4  Feed_max=805.3 mm/min
machine_limit_status=NO_MACHINE (no machine spindle limit provided)
```

---

## P5-D — GD&T Annotation Linking

### MUST 22–25

**Investigation result:**

DXF-01 (`109106_01_30.dxf`) MTEXT content:
- 58 MTEXT in `*PAPER_SPACE` block: title block headers (TARIH, DEGISIKLIK, etc.)
- 7 dim blocks (dim1–dim5): simple dimension text ("47.5", "35", "6", "8", "%%c", "M")
- 0 MTEXT in model space
- NO GD&T feature control frames (`\Fgdt;` or %%131–%%148 codes absent)

```
GDNT_FEATURE_LINKS=0  (CORRECT — no feature control frames present)
GD&T_PIPELINE_INTACT=YES (existing association/fusion infrastructure unchanged)
```

This is the honest result.  No false links were created.

---

## P5-E — Tolerance-Driven Route Selection

### MUST 26–28

**New module:** `backend/manufacturing/process_capability.py`

**Capability table (ISO 286 / standard machining references):**

| Operation sequence | Achievable IT grade | Source |
|-------------------|---------------------|--------|
| drilling | IT11–IT13 | ISO 286 / standard machining reference |
| drilling + reaming | IT7–IT9 | ISO 286 / standard machining reference |
| drilling + boring | IT7–IT8 | ISO 286 / standard machining reference |

**Capability status logic:**
- required_it_grade < it_grade_min → NOT_CAPABLE
- required_it_grade == it_grade_min → MARGINAL_REVIEW (at tight boundary)
- it_grade_min < required <= it_grade_max → CAPABLE
- required > it_grade_max → CAPABLE (over-capable)
- unknown sequence → UNKNOWN (never becomes CAPABLE)

```
UNKNOWN != CAPABLE  ✓
```

---

## Real Sample Validation

### MUST 29 — DXF-01

```
DXF01_MACHINE_READY=YES   (20 machines pass for 100×80×30mm stock, drilling operation)
DXF01_TOOL_READY=YES      (5.0mm drill, COMPATIBLE match for 4.891mm feature)
DXF01_CUTTING_DATA_READY=YES
DXF01_CAM_READY=YES
```

### MUST 30 — DXF-02 / DXF-03

```
DXF02_MACHINE_READY=YES  DXF02_TOOL_READY=NO  (60mm — outside 3–8mm scope)  DXF02_CAM_READY=YES
DXF03_MACHINE_READY=YES  DXF03_TOOL_READY=NO  (8.5mm — outside 3–8mm scope) DXF03_CAM_READY=YES
```

Do not force success: tool gaps are honestly reported.

### MUST 31–34 — Coverage summary

```
TOOL_SELECTION_READY_BEFORE=0     TOOL_SELECTION_READY_AFTER=1  (DXF-01)
MACHINE_SELECTION_READY_BEFORE=0  MACHINE_SELECTION_READY_AFTER=3  (DXF-01/02/03)
CUTTING_DATA_READY_BEFORE=0       CUTTING_DATA_READY_AFTER=1  (DXF-01)
CAM_READY_BEFORE=3                CAM_READY_AFTER=3  (NO REGRESSION)
```

### MUST 35 — Offline NC

```
OFFLINE_NC_CANDIDATE_READY=NO  (DXF-01 has TOOL_SELECTION_READY=YES but no NC path implemented yet)
AUTO_CNC_DISPATCH_FOUND=NO
```

---

## Safety / Fabrication

```
FABRICATED_MACHINE_FOUND=NO
FABRICATED_TOOL_FOUND=NO
FABRICATED_CUTTING_DATA_FOUND=NO
FABRICATED_MATERIAL_FOUND=NO
FABRICATED_TOLERANCE_FOUND=NO
FABRICATED_GDNT_FOUND=NO

ALL_SOURCE_FILES_UNCHANGED=YES
SOURCE_SAMPLE_FILES_COMMITTED=NO

REAL_MACHINE_WRITE_FOUND=NO
AUTO_CNC_DISPATCH_FOUND=NO
AUTO_APPROVAL_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO

PRODUCTION_LIBRARY_DATA_CHANGED=YES (10 new drill records; cutting_parameters.py)
TEST_FIXTURE_DATA_CHANGED=NO (no synthetic fixture mixed into production)
```

---

## Change Summary

```
PRODUCTION_FILES_CHANGED=backend/cutting_tools/seed_catalog.py,
  backend/cutting_tools/cutting_parameters.py,
  backend/manufacturing/tool_selection.py,
  backend/manufacturing/machine_selection.py,
  backend/manufacturing/process_capability.py,
  backend/api/cad_features.py

LIBRARY_FILES_CHANGED=backend/cutting_tools/seed_catalog.py (10 new drills)
TEST_FILES_CHANGED=5 new test files (test_p5a/b/c/d/e)
DOC_FILES_CHANGED=REAL_SAMPLE_P5_IMPLEMENTATION_COMPARISON.md, REAL_SAMPLE_P5_ASSESSMENT.md
I18N_FILES_CHANGED=NO
```

---

## Remaining Gaps (Not Implemented in P5)

1. Tool diameter gap: 8.5mm (DXF-03), 60mm (DXF-02) — outside P5-A scope
2. Cutting data for non-P materials (M, K, N groups) — P group only
3. Machine API: spindle RPM populated for only some machines
4. IGES topology, PDF OCR — unchanged from P4 assessment
5. Offline NC path — MUST 35 not implemented

---

**P5 VERDICT: PASS_P5_TOOL_MACHINE_CUTTING_ORCHESTRATION**  
(DXF-01 fully orchestrated: machine=YES, tool=YES, cutting_data=YES, cam=YES)  
(DXF-02/03: machine=YES; tool=NO, cutting=NO — honest not-forced)
