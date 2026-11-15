# Real Sample P6 Assessment

**Campaign:** MACHININGPRO_AI_P6_ASSESSMENT  
**Date:** 2026-11-15  
**Repository:** D:\makina_ogrenmesi\MachiningPro_AI_NEXT  
**Branch:** main | HEAD: 614241f  
**Precondition:** P5 Final Acceptance = PASS_P5_FINAL_ACCEPTANCE_AND_P6_ASSESSMENT_GO  
**Analyst:** Assessment only — no production code changes

---

## P6 Scope: Tool-to-Toolpath-to-NC-Candidate Pipeline

P5 ended at: machine candidates, tool selection, and cutting parameters are computable for DXF-01.  
P6 goal: wire those P5 outputs into an OFFLINE NC candidate (a CNC program file that an engineer can review and sign off, never auto-dispatched).

**P6 is NOT:**
- NC dispatch to a machine
- Auto-approval of cutting parameters
- CNC connection
- Autonomous adaptation

---

## P6 Infrastructure Audit (Pre-existing, Verified)

### Toolpath API (`backend/api/toolpath.py`)

```
ENDPOINT_DRILL=YES      /api/toolpath/drill
ENDPOINT_PROFILE=YES    /api/toolpath/profile
ENDPOINT_FACEMILL=YES   /api/toolpath/face-mill
ENDPOINT_POCKET=YES     /api/toolpath/pocket
ENDPOINT_SLOT=YES       /api/toolpath/slot
ENDPOINT_CHAMFER=YES    /api/toolpath/chamfer
ENDPOINT_TURNING=YES    /api/toolpath/turning
AUTH_REQUIRED=YES       (Bearer token, all endpoints)
NO_GCODE=YES            (file header, all endpoints)
```

`ToolpathResponse` returns:
- `toolpath_id`: UUID (input to NCBuildRequest)
- `toolpaths`: list of segment dicts with motion_type, start/end coordinates

### NC Generation API (`backend/api/nc_generation.py`)

```
ENDPOINT_NC_BUILD=YES        /api/nc/build (POST)
ENDPOINT_NC_VALIDATE=YES     /api/nc/validate (POST)
ENDPOINT_NC_PROFILES=YES     /api/nc/profiles (GET)
AUTH_REQUIRED=YES            (Bearer token)
NO_DISPATCH=YES              (file header)
OFFLINE_CANDIDATE_ONLY=YES   (is_offline_candidate=True in NCBuildResponse)
IS_DISPATCHABLE=ALWAYS_NO    (NCBuildResponse.is_dispatchable=False)
```

`NCBuildRequest` accepts:
- `toolpath_id`: from ToolpathResponse
- `spindle_speed_rpm`: from P5-C cutting data
- `feed_mmpm`: from P5-C cutting data
- `tool_id`: from P5-A tool selection
- `tool_diameter_mm`: from selected tool
- `segments`: list of NCSegmentInput (derived from toolpath segment dicts)

### Feature Location Coordinates (Verified)

```python
# DXF-01 first feature (diameter=4.891mm), confirmed from live API call:
feature.location = {'x_mm': -225.54485, 'y_mm': -968.552339, 'z_mm': 0.0}
feature.axis     = {'x': 0.0, 'y': 0.0, 'z': 1.0}
feature.depth_mm = 25.0  (engineer-confirmed in P4)
feature.diameter_mm = 4.891
```

Hole center coordinates are available from `feature.location` — NOT a P6 blocker.

---

## P6 Gap Analysis — What Does Not Yet Exist

### GAP-1: Tool-to-Toolpath Bridge

A new service or endpoint is needed that takes:
- `feature_id` (from confirmed feature)
- `tool_selection_result` (from P5-A)
- `clearance_z` (engineer-specified safety retract height)

And calls `generate_drill_toolpath()` with the hole location, depth, and tool ref.

The bridge must derive `DrillToolpathRequest` from:
```
hole_x     ← feature.location.x_mm
hole_y     ← feature.location.y_mm
hole_top_z ← feature.location.z_mm (stock surface)
hole_depth_mm ← feature.depth_mm
peck_depth_mm ← engineer-specified or strategy-derived (not catalog)
clearance_z   ← MISSING: requires engineer input or stock-top + safety margin
tool_ref      ← tool_selection_result.selected_tool.stable_id
```

**Blocker:** `clearance_z` is not currently derivable from CAD session state. Requires engineer input or a new stock-geometry inference rule (e.g., stock.top_z + 5mm safety margin). This is a small but explicit design decision.

### GAP-2: Toolpath-Segment-to-NC-Segment Adapter

`NCBuildRequest.segments` requires a list of `NCSegmentInput` objects with fields:
```
segment_id, motion_type, start_x/y/z, end_x/y/z, is_cutting
```

The toolpath API returns segment dicts from `tp.segments`. An adapter function is needed to convert `ToolpathResponse.toolpaths` into `NCSegmentInput` items for the NC build call.

This is non-trivial but straightforward: each toolpath dict is a motion segment; mapping `start`, `end`, `type` fields is a 1-to-1 conversion.

### GAP-3: Cutting Data → NC Parameterization Gate

P5-C returns:
```
Vc_range: 70–115 m/min | fn_range: 0.06–0.11 mm/rev
RPM: 4456–7321 | Feed: 267–805 mm/min
evidence_status: MANUFACTURER_STARTING_VALUE
```

Before these values are written into an NC candidate (`NCBuildRequest.spindle_speed_rpm` and `feed_mmpm`), an engineer must confirm specific values from the ranges. P6 needs an engineer-confirmation gate that:
1. Presents the P5-C range to the engineer
2. Records the confirmed RPM and feed_mmpm
3. Changes `evidence_status`: MANUFACTURER_STARTING_VALUE → ENGINEER_CONFIRMED_VALUE
4. Only then allows NC build to proceed

**Without this gate:** any NC candidate built from MANUFACTURER_STARTING_VALUE is an UNCONFIRMED candidate. This must be flagged in the NC candidate's status.

### GAP-4: Batch Drilling for DXF-01

DXF-01 has 9 holes of mixed diameters:
```
4.891mm × 2 | 5.0mm × 3 | 6.0mm × 2 | 8.0mm × 2
```

P5-A currently selects a tool for one feature at a time. A batch coordinator is needed to:
1. Group features by compatible tool (5.0mm drill covers 4.891mm + 5.0mm)
2. Generate one toolpath per tool with all holes for that tool
3. Assign tool numbers and program the tool change sequence in the NC candidate

Each distinct tool diameter requires its own drill pass, tool change, and cutting parameter set.

### GAP-5: Catalog Gap — DXF-02 (60mm) and DXF-03 (8.5mm)

**DXF-02 (60.0mm hole):**  
No drill scope covers 60mm. Strategy options:
- Boring bar (single-point boring) — requires a boring bar catalog entry
- Circular milling interpolation — requires a milling endmill + helical interpolation strategy
Neither strategy exists in the current library. This is an **architecture decision** (boring bar vs. circular milling), not just a catalog addition.

**DXF-03 (8.5mm hole):**  
Current catalog has 8.0mm and 12.0mm drills; 8.5mm is a catalog gap.
Resolution options:
- Add 8.5mm drill (Sandvik 860-1-0850 or equivalent from catalog) — small addition
- Use 8.0mm drill + reaming to 8.5mm — requires reamer catalog entry

This is a **catalog-level gap**, smaller than DXF-02's strategic gap.

---

## P6 Blockers Per Sample

| Sample | Diameter | P6 Blocker | Resolution |
|--------|----------|------------|------------|
| DXF-01 | 4.891mm (5.0mm compatible) | GAP-1 (clearance_z), GAP-3 (cutting data confirmation gate) | Small: clearance_z rule + confirmation gate |
| DXF-02 | 60.0mm | GAP-5 (strategy: boring bar vs. milling interpolation) | Medium: architecture decision + new catalog entry |
| DXF-03 | 8.5mm | GAP-5 (catalog: add 8.5mm drill) | Small: catalog addition |

**DXF-01 is the primary P6 candidate.** It is the only sample with TOOL_SELECTION_READY=YES and CUTTING_DATA_READY=YES, and its blockers are small.

---

## P6 Workstreams (Recommended Priority Order)

### P6-A: Clearance Height Policy (DXF-01 unblock)
Add a `clearance_height_strategy` to the session setup:
- Default: `stock_top_z + 5.0mm` (conservative safe retract)
- Engineer-overridable
- Status: `STRATEGY_DEFAULT` (not ENGINEER_CONFIRMED)

This unblocks GAP-1 without requiring a new engineer interaction for simple parts.

### P6-B: Toolpath Segment Adapter (GAP-2)
Add `toolpath_segments_to_nc_inputs()` in a new `backend/manufacturing/nc_bridge.py`:
- Input: `ToolpathResponse.toolpaths` (list of dicts)
- Output: `list[NCSegmentInput]`

This is a data transformation, no domain knowledge required.

### P6-C: Cutting Parameter Confirmation Gate (GAP-3, safety-critical)
Add an engineer confirmation endpoint:
```
POST /{session_id}/features/{feature_id}/confirm-cutting-parameters
Body: {tool_ref, spindle_speed_rpm, feed_mmpm}
```
- Validates rpm is within P5-C range
- Sets `evidence_status=ENGINEER_CONFIRMED`
- Returns `confirmed_cutting_params_ref` for NCBuildRequest

Without this gate, every NC candidate built in P6 must carry `is_confirmed=False` in its status.

### P6-D: NC Candidate Builder for DXF-01 Drilling
Wire GAP-1 + GAP-2 + GAP-3 into a single:
```
POST /{session_id}/features/{feature_id}/build-nc-candidate
Body: {tool_ref, spindle_speed_rpm, feed_mmpm, clearance_z?}
```
Returns: `NCBuildResponse` with `is_offline_candidate=True`, `is_dispatchable=False`

The resulting NC candidate is review-status=PENDING_REVIEW.

### P6-E: Catalog Expansion for DXF-03
Add 8.5mm Sandvik CoroDrill 860-1 (or Kennametal B221A equivalent) to `seed_catalog.py`.  
Source: manufacturer catalog (same evidence standard as P5-A — no fabrication).  
This unblocks DXF-03's TOOL_SELECTION_READY from NO to YES.

### P6-F: DXF-02 Strategy (deferred)
DXF-02 requires an architecture decision (boring bar vs. circular milling). This is out of scope for P6-A through P6-E and should be assessed as a separate workstream after the drilling pipeline is validated end-to-end.

---

## P6 Safety Invariants (Must Carry Forward)

All P5 safety invariants apply unchanged. P6 adds:

```
NC_CANDIDATE_AUTO_DISPATCH=NEVER
NC_CANDIDATE_AUTO_APPROVE=NEVER
CUTTING_PARAMS_FROM_MANUFACTURER_STARTING_VALUE=FLAGGED_IN_NC_CANDIDATE
COMPATIBLE_MATCH_DIMENSIONAL_RISK=FLAGGED_IN_NC_CANDIDATE
  (5.0mm drill on 4.891mm feature → resulting hole ~5.0mm, not 4.891mm)
REAL_MACHINE_WRITE=NEVER
NC_FILE_DISTRIBUTION=OFFLINE_CANDIDATE_ONLY
FORCE_PUSH=NO | TAG=NO | RELEASE=NO
```

---

## P6 Risk Assessment

| Risk | Level | Mitigation |
|------|-------|------------|
| COMPATIBLE match (5.0mm on 4.891mm) → hole oversize | MEDIUM | NC candidate carries dimensional risk flag; engineer must verify fit tolerance |
| MANUFACTURER_STARTING_VALUE → not production-tested | HIGH | Cutting parameter confirmation gate (P6-C) is mandatory before any NC candidate is REVIEW_COMPLETE |
| clearance_z derived automatically → crash risk on complex parts | MEDIUM | Default rule conservative (+5mm); engineer can override; flag as STRATEGY_DEFAULT |
| Batch drilling tool sequence error → wrong tool, wrong hole | MEDIUM | Each tool assignment in batch must be explicitly reviewed; no auto-ordering |
| DXF-02 boring bar catalog entries not yet held to same provenance standard | HIGH | Do not add boring bar records without manufacturer catalog source; defer DXF-02 until P6-F |

---

## P6 Pre-Implementation Checklist

Before writing the first P6 line of code, the following must be confirmed:

```
P6_PREREQ_1: P5 Final Acceptance = PASS ✓ (confirmed this document)
P6_PREREQ_2: Toolpath API auth mechanism understood (Bearer token) = YES ✓
P6_PREREQ_3: NCBuildRequest.is_dispatchable=False is enforced by existing code = YES ✓ (verified)
P6_PREREQ_4: Clearance height policy agreed (default +5mm vs. engineer-required) = PENDING
P6_PREREQ_5: Cutting parameter confirmation gate design agreed = PENDING
P6_PREREQ_6: Batch hole grouping strategy agreed = PENDING
P6_PREREQ_7: DXF-03 8.5mm catalog source identified (manufacturer catalog) = PENDING
```

P6_PREREQ_4 through P6_PREREQ_7 are design decisions that require agreement before implementation begins.

---

## P6 Assessment Verdict

```
STOPPED_P6_SAFETY_RISK=NO
STOPPED_P6_ARCHITECTURAL_RISK=NO
STOPPED_P6_DATA_QUALITY_RISK=NO
DEFER_P6=NO

P6_ASSESSMENT=GO_WITH_CONDITIONS
```

**Conditions for P6 GO:**
1. P6-C (cutting parameter confirmation gate) must be implemented before any NC candidate is considered REVIEW_READY. NC candidates built without confirmed cutting parameters must carry `is_confirmed=False`.
2. P6-F (DXF-02 boring bar strategy) must be deferred until the DXF-01 drilling pipeline is validated end-to-end.
3. The 4.891mm COMPATIBLE match dimensional risk must be carried in every NC candidate for DXF-01 (not just the tool selection result).
4. P6 must not add any endpoints or code paths that set `is_dispatchable=True`.

**Primary P6 workstream sequence:**  
P6-A (clearance policy) → P6-B (segment adapter) → P6-C (confirmation gate) → P6-D (NC candidate builder) → P6-E (8.5mm catalog) → P6-F (DXF-02 strategy, separate workstream)
