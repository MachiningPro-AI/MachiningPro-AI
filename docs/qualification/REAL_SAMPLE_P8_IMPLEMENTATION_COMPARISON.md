# P8 Offline Geometric Verification — Implementation vs. Architecture Comparison

**Document class:** Qualification Comparison  
**Status:** PASS — P8-A through P8-E implemented  
**Date:** 2026-11-16

---

## 1. What Was Planned (P8 Architecture Assessment)

The P8 architecture assessment (see `REAL_SAMPLE_P8_ASSESSMENT.md`) identified the
following scope items:

| Item | Description |
|------|-------------|
| P8-A | Wire P7 toolpath segments into verification engine |
| P8-B | Tool reach validation against flute/cutting length |
| P8-C | Fixture geometry input model and provenance tracking |
| P8-D | Collision status classification with geometry-dependency gates |
| P8-E | Machine envelope validation against catalog travel limits |
| P8-F | STEP sample requirements document |
| P8-H | Postprocessor (DEFERRED — HARD RULE 16) |

---

## 2. What Was Implemented

### P8-A: Segment Conversion and Verification Engine Wiring

**File:** `backend/manufacturing/verification_adapter.py`  
**Function:** `nc_segments_to_verification_segments()`

- Converts `nc_bridge` output dicts (`motion_type="RAPID_LINEAR"/"FEED_LINEAR"/"HELIX"`)
  to `VerificationSegment` objects (`motion_type="RAPID"/"CUT"`)
- Skips segments with missing/invalid coordinates; count reported in `provenance_notes`
- `run_p8_verification()` calls `run_simulation()` from the unchanged verification engine

**Matches plan:** YES

---

### P8-B: Tool Reach Validation

**File:** `backend/manufacturing/verification_adapter.py`  
**Logic in:** `run_p8_verification()`

- If `tool_flute_length_mm is None` → `tool_reach_validated = INSUFFICIENT_DATA`
  (not PASS, not NOT_VERIFIABLE — the distinction matters for the gate)
- Overall length does not substitute for flute length (HARD RULE — cannot fabricate)
- `cutting_length_mm` is available for 8/18 drills; not used as flute substitute
- 0/18 catalog drills have `flute_length_mm` populated (audit confirmed)

**Matches plan:** YES  
**Gap noted:** Flute length gap (0/18 drills) is a data gap, not a code gap. Addressed
in catalog improvement backlog, not in P8 scope.

---

### P8-C: Fixture Geometry Input Model

**File:** `backend/manufacturing/verification_adapter.py`  
**Classes:** `FixtureInput`, `GeometryFieldProvenance`

- `FixtureInput` is a frozen dataclass: `fixture_id`, `fixture_type`, `source`,
  `provenance`, `min/max x/y/z_mm`
- `is_trustworthy` property: True only if `provenance ∈ {USER_CONFIRMED, KNOWN}`
- Fixtures with `provenance=UNKNOWN` are filtered out before the collision check
- Filtered fixture list (`fixture_geoms`) determines `NOT_VERIFIABLE` vs. `PASS/FAIL`
- Holder geometry is always UNKNOWN (not in P7 workflow) →
  `holder_collision_validated = NOT_VERIFIABLE`

**Matches plan:** YES

---

### P8-D: Collision Status Classification

**File:** `backend/manufacturing/verification_adapter.py`  
**Logic in:** `run_p8_verification()`

| Check | Condition | Status |
|-------|-----------|--------|
| Tool collision | No trustworthy fixtures | NOT_VERIFIABLE |
| Tool collision | Trustworthy fixtures present | PASS or FAIL (from engine) |
| Holder collision | holder_diameter_mm is None | NOT_VERIFIABLE |
| Fixture collision | No trustworthy fixtures | NOT_VERIFIABLE |
| Gouge (part) | part_bbox_min is None | NOT_VERIFIABLE |
| Gouge (stock) | stock_model is None | NOT_VERIFIABLE |
| `GEOMETRY_CHECK_PASS` ≠ `COLLISION_VALIDATED` | Enforced in P8VerificationResult | YES |

**Matches plan:** YES

---

### P8-E: Machine Envelope Validation

**File:** `backend/manufacturing/verification_adapter.py`  
**Logic in:** `run_p8_verification()` and `build_verification_input()`

- Machine travel extracted from `machine_record` dict: `travel_x_mm`, `travel_y_mm`,
  `travel_z_mm`
- If any travel dimension is None → `machine_envelope_validated = INSUFFICIENT_DATA`
- `check_machine_envelope()` from verification engine receives half-travel as axis limit
- Haas VF-2SS travel verified: 762 × 406 × 508 mm (catalog audit confirmed)

**Matches plan:** YES

---

### P8-F: STEP Sample Requirements Document

**File:** `docs/qualification/STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md`

- Defines Class A (prismatic/holes), Class B (pocket), Class C (contoured, deferred P9),
  Class D (assembly+fixture, deferred P9)
- Minimum viable set: 3 files (2× Class A, 1× Class B)
- Current status: `P8_STEP_QUALIFICATION_STATUS=DEFERRED_REAL_SAMPLE_REQUIRED`

**Matches plan:** YES

---

### P8-H: Postprocessor

**Status: NOT IMPLEMENTED**  
**Reason:** HARD RULE 16 — Do NOT implement P8-H postprocessor  
This item remains deferred indefinitely.

---

## 3. Safety Invariants — Verified

| Invariant | Mechanism | Test |
|-----------|-----------|------|
| `is_dispatchable=False` always | `__post_init__` override | test_p8_safety.py |
| `production_released=False` always | `__post_init__` override | test_p8_safety.py |
| No real machine write | Static source check | test_p8_safety.py |
| No auto dispatch | Static source check | test_p8_safety.py |
| No auto approval | Static source check | test_p8_safety.py |
| GEOMETRY_CHECK_PASS ≠ COLLISION_VALIDATED | Separate fields, separate logic | test_p8d_collision_status.py |
| UNKNOWN remains UNKNOWN | No provenance upgrade without evidence | Multiple P8 test files |

---

## 4. Test Coverage

| File | Tests | Scope |
|------|-------|-------|
| test_p8a_verification_adapter.py | 42 | Segment conversion, build_vi, stock, run |
| test_p8b_tool_reach.py | 10 | Tool reach, flute audit, Sandvik 860 |
| test_p8c_fixture.py | 8 | Fixture model, trustworthy, conversion |
| test_p8d_collision_status.py | 7 | Collision classification, GEOMETRY_CHECK |
| test_p8e_machine_envelope.py | 9 | Machine envelope, Haas VF-2SS |
| test_p8_safety.py | 14 | Safety invariants, source-level checks |
| **Total** | **90** | |

---

## 5. Unchanged Components

The following components were audited and NOT modified:

- `backend/verification/simulation.py` — `run_simulation()` unchanged
- `backend/verification/checks.py` — all 12 check functions unchanged
- `backend/verification/models.py` — SimulationRequest, SimulationResult unchanged
- `backend/verification/stock.py` — StockModel, FixtureGeometry unchanged
- `backend/manufacturing/nc_candidate.py` — OfflineNCCandidate unchanged
- `backend/manufacturing/nc_bridge.py` — segment_to_nc_input unchanged
- All source engineering files — read-only (HARD RULE 12)

---

## 6. Gaps Remaining After P8

| Gap | Status | Path Forward |
|-----|--------|-------------|
| 0/18 drills have flute_length_mm | Data gap — catalog backlog | P9 catalog enrichment |
| STEP samples not yet acquired | Deferred | See STEP_CAM_VERIFICATION_SAMPLE_REQUIREMENTS.md |
| Part bbox always UNKNOWN (DXF-only) | Architectural limit | Requires STEP integration |
| Holder geometry always UNKNOWN | P7 workflow gap | Requires holder catalog in P9 |
| GOUGE always NOT_VERIFIABLE | Requires part solid | Requires STEP Class A sample |

---

*All hard rules remain in force. This document records what was built, not what can be claimed.*
