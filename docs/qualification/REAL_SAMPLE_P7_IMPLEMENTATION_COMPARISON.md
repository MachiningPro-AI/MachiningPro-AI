# P7 Implementation Comparison — Offline NC Generation / Multi-Feature Workflow

**Status:** PASS_P7_MULTI_FEATURE_OFFLINE_NC_VALIDATION (P7-A/B/C)  
**Date:** 2026-11-15/16  
**Branch:** main  
**Baseline:** fc2d77f (P6 Final Acceptance + P7 Assessment)  
**P7 commit:** e55518d (feat(cam): add P7 offline NC generation, multi-hole sequencing, and engineer review gate)

---

## Assessment vs Implementation Gate Mapping

| Assessment Condition | Implementation | Result |
|---|---|---|
| P7-A: OfflineNCCandidate → NCGenerationInput → generate_nc() | `nc_generation_adapter.py:build_nc_generation_input` | PASS |
| P7-A: Fail-closed when nc_candidate_review_ready=False | `generate_nc_from_candidate` returns BLOCKED | PASS |
| P7-A: GENERIC_ISO_TEST_v1 only | `post_profile=GENERIC_ISO_TEST` hardcoded | PASS |
| P7-A: NOT_CLAIMED for controller compatibility | `production_controller_compatibility=NOT_CLAIMED` enforced | PASS |
| P7-A: EN+TR offline label in every result | Warnings include both label strings | PASS |
| P7-B: Group holes by tool, EXACT before COMPATIBLE | `group_features_by_tool` ordering policy | PASS |
| P7-B: Engineer confirmation gate on sequence | `engineer_confirmed=False` enforced, no auto-confirm path | PASS |
| P7-B: Per-feature warnings preserved | COMPATIBLE risk warning carried through HoleEntry | PASS |
| P7-B: NO_MATCH holes tracked, not silently dropped | Separate blocked group in BatchSequenceProposal | PASS |
| P7-C: CANDIDATE → VALIDATED_OFFLINE lifecycle | `record_nc_engineer_review` with NCReviewChecklist | PASS |
| P7-C: 4-item mandatory checklist | `all_mandatory_checks_passed()` checks all 4 | PASS |
| P7-C: Reject path → REJECTED | `rejected=True` overrides checklist | PASS |
| P7-C: VALIDATED_OFFLINE ≠ dispatchable | `is_dispatchable=False` enforced at VALIDATED_OFFLINE | PASS |
| is_dispatchable=True nowhere in P7 | Static grep + 21 safety tests | PASS |
| DXF-01 single-feature NC → CANDIDATE status | `test_p7_e2e_dxf.py` TestP7AE2EDXF01 | PASS |
| DXF-01 9-hole batch sequence | `test_p7_e2e_dxf.py` TestP7BE2EDXF01 | PASS |
| DXF-01 full chain → VALIDATED_OFFLINE | `test_p7_e2e_dxf.py` TestP7CE2EDXF01 | PASS |
| P7-D: 16/18/24mm drill catalog records | seed_catalog.py blocked by classifier | DEFERRED |
| P7-E: DXF-02 boring | Deferred — entry gate not met | DEFERRED |

---

## P7-A: NC Generation Adapter (`nc_generation_adapter.py`)

**Addresses:** MUST 2–7 (NC bridge, fail-closed, postprocessor, label, no dispatch)

**Input:** `OfflineNCCandidate` (nc_candidate_review_ready=True) + `tool_number` (engineer-specified)  
**Output:** `P7NCResult` with `NCGenerationResult`, `nc_program_status`, traceability fields

### Bridge Logic

```python
def build_nc_generation_input(candidate, *, tool_number, program_number=None):
    if not candidate.nc_candidate_review_ready:
        return None   # BLOCKED — missing P6 gates
    wrapped_segments = [SegmentProxy(s) for s in candidate.nc_segments]
    return NCGenerationInput(
        post_profile=GENERIC_ISO_TEST,
        verification_state="VERIFIED",   # all P6 checkpoints complete
        tool_number=tool_number,
        spindle_speed_rpm=confirmed.rpm_calculated,
        feed_mmpm=confirmed.feed_rate_mm_min,
        work_offset=_map_wcs_ref(candidate.wcs_ref),
        ...
    )
```

**SegmentProxy:** Wraps `nc_segments` dicts for `getattr()` without modifying either side.

**WCS gate:** `wcs_ref=None` → `WorkOffsetRef.UNKNOWN` → NC engine blocks (correct fail-closed behavior).

**P7NCResult.__post_init__:** Hardcodes `is_dispatchable=False`, `production_released=False`, `machine_ready_to_run=False`, `post_profile_id=GENERIC_ISO_TEST_v1`, `production_controller_compatibility=NOT_CLAIMED` — cannot be overridden by caller.

### NC Output Labels (Always Present in Warnings)

```
EN: OFFLINE ENGINEERING CANDIDATE — NOT FOR DIRECT MACHINE EXECUTION
TR: OFLİN MÜHENDİSLİK ADAYI — DOĞRUDAN MAKİNE ÇALIŞTIRILMASI İÇİN DEĞİL
    GENERIC_ISO_TEST_v1: TEST_ONLY — not certified for any machine controller
    PRODUCTION_CONTROLLER_COMPATIBILITY=NOT_CLAIMED
```

### NC Validation Results (DXF-01)

```
program begins: tool_change block → spindle_cmd → feed_linear segments → retract
all numeric fields finite: RPM=5729.6, feed=457.6 mm/min (Vc=90, fn=0.08, D=5mm)
program_id: set (UUID-based)
is_offline_candidate=True
is_dispatchable=False
safety_warnings present
```

### Tests

```
test_p7a_nc_generation_adapter.py — 32 tests
  TestSegmentProxy (5): getattr, missing key, None, nested, is_cutting
  TestBuildNcGenerationInput (10): None when blocked, returns input, verification_state,
    profile, tool_number, spindle, feed, work_offset, wcs_none→unknown, program_number,
    segments_wrapped
  TestGenerateNcFromCandidate (8): blocked, candidate status, program_id, not_dispatchable,
    offline_candidate, safety_warnings, blocks, post_profile_id
  TestP7NCResultSafetyInvariants (9): is_dispatchable, production_released,
    machine_ready_to_run, not_claimed, blocked_invariants, cannot_override,
    EN_label, TR_label
```

---

## P7-B: Multi-Hole Sequence (`multi_hole_sequence.py`)

**Addresses:** MUST 8–14 (batch model, operation order, engineer review, tool change, warnings)

### Batch Processing Logic

```python
def group_features_by_tool(sample_id, hole_entries) -> BatchSequenceProposal:
    # 1. Partition: EXACT / COMPATIBLE / NO_MATCH
    # 2. Assign proposed_tool_number sequentially (EXACT groups first)
    # 3. Append NO_MATCH blocked group at end (transparent, not silently dropped)
    # 4. Return BatchSequenceProposal(engineer_confirmed=False, is_dispatchable=False)
```

**Tool change representation:** Each `ToolGroup` is a separate group with its own `proposed_tool_number`. Transitions between groups represent explicit tool changes — no silent assumption that one tool covers all diameters.

**COMPATIBLE risk:** `tool_match_status="COMPATIBLE"` generates a warning per group. The DXF-01 4.891mm → 5.0mm risk (Δ=+0.109mm) is attached to its HoleEntry and carried through.

**Engineer confirmation:** `engineer_confirmed=False` enforced in `ToolGroup.__post_init__` and `BatchSequenceProposal.__post_init__`. No auto-confirm path exists.

### DXF-01 Full 9-Hole Batch

```
Groups produced:
  Group 1 (EXACT,  tool=sandvik-860-1-0500-026a1-pm, 5.0mm): 3 holes (f003/f004/f005)
  Group 2 (EXACT,  tool=sandvik-860-1-0600-031a1-pm, 6.0mm): 2 holes (f006/f007)
  Group 3 (EXACT,  tool=sandvik-860-1-0800-040a1-pm, 8.0mm): 2 holes (f008/f009)
  Group 4 (COMPATIBLE, tool=sandvik-860-1-0500-026a1-pm, 5.0mm): 2 holes (f001/f002)
  → EXACT groups precede COMPATIBLE group in proposal

FEATURES_IN_BATCH=9
TOOLS_REQUIRED=3  (5mm EXACT, 6mm, 8mm)
COMPATIBLE_HOLE_COUNT=2
NO_MATCH_HOLE_COUNT=0
SEQUENCE_STATUS=PROPOSED
ENGINEER_SEQUENCE_CONFIRMATION_REQUIRED=YES
```

### Tests

```
test_p7b_multi_hole_sequence.py — 20 tests
  TestGroupFeaturesByTool (11): empty, all_exact, compatible_separate, no_match_blocked,
    exact_before_compatible, proposed_tool_numbers, invariants, compatible_warning,
    no_match_warning, no_match_incomplete_status, mixed_all_three
  TestBatchSequenceProposalInvariants (5): engineer_false, is_dispatchable, production_released,
    no_match_incomplete_status, proposed_status_no_match_zero
  TestHoleEntryWarnings (4): compatible_warning_present, no_match_blocked_separate,
    compatible_risk_message, exact_no_extra_warning
```

---

## P7-C: Engineer NC Review Gate (`nc_review.py`)

**Addresses:** MUST 15–20 (status model, validation requirements, immutability, rejection)

### Status Lifecycle

```
record_nc_engineer_review(program, checklist, reviewer_notes, rejected=False):
  if rejected → NCReviewStatus.REJECTED
  elif checklist.all_mandatory_checks_passed() → NCReviewStatus.VALIDATED_OFFLINE
  else → NCReviewStatus.ENGINEER_REVIEWED
```

### Mandatory Checklist

```
NCReviewChecklist(
    tool_numbers_verified=False,     # tool numbers match physical register
    feeds_speeds_verified=False,     # Vc/fn within confirmed range
    depths_verified=False,           # Z depths match feature geometry
    wcs_offset_verified=False,       # work offset matches setup sheet
)
```

All 4 must be `True` for VALIDATED_OFFLINE. Partial → ENGINEER_REVIEWED.

### Review Record Traceability

```
NCReviewRecord fields:
  nc_program_id      — UUID linking back to NCProgram
  status             — VALIDATED_OFFLINE / ENGINEER_REVIEWED / REJECTED
  checklist          — snapshot of what was checked
  reviewer_notes     — engineer text
  reviewed_at        — UTC ISO timestamp
  missing_at_review  — list of unchecked items at review time
```

**Immutability note:** A new `NCReviewRecord` is required for each review action. Prior records are not mutated. Changing program inputs (tool, parameters, WCS) would require a new NC generation and new review — there is no "re-activate" method on an existing record.

### VALIDATED_OFFLINE Disclaimers

```
VALIDATED_OFFLINE means:
  - Engineer reviewed all mandatory checklist items for offline candidate
VALIDATED_OFFLINE does NOT mean:
  - Collision validated (FIXTURE/HOLDER/STOCK/MACHINE: NOT_IMPLEMENTED)
  - Controller certified
  - Production released
  - Machine executable
  - Approved for autonomous or unattended operation
```

### Tests

```
test_p7c_nc_review.py — 22 tests
  TestNCReviewChecklist (6): all_true, any_false, missing_empty, missing_lists_unchecked,
    all_false_four_missing, default_all_false
  TestNcReviewStatusPromotion (5): validated_offline, engineer_reviewed_partial,
    engineer_reviewed_no_checks, rejected_overrides_full, rejected_overrides_partial
  TestNCReviewRecordSafetyInvariants (11): is_dispatchable at candidate, at validated_offline,
    production_released at validated_offline, machine_ready_to_run at validated_offline,
    is_dispatchable at rejected, production_released at rejected, cannot_override,
    reviewed_at_set, program_id_matches, missing_empty_when_all_checked,
    missing_lists_unchecked
```

---

## P7 Safety Tests (`test_p7_safety.py`)

```
21 tests total:
  TestStaticDispatchAudit (9): checks all 3 P7 source files for
    is_dispatchable=True, production_released=True, machine_ready_to_run=True
  TestGenericIsoTestSafety (5): not_dispatchable, not_machine_certified,
    profile_id, no_fanuc, no_siemens
  TestValidatedOfflineNotDispatch (5): P7NCResult, NCProgram, NCReviewRecord
    is_dispatchable=False at VALIDATED_OFFLINE; production_released=False,
    machine_ready_to_run=False
```

---

## P7 E2E Tests (`test_p7_e2e_dxf.py`)

```
19 tests total — using real DXF-01 coordinates and tool data:
  TestP7AE2EDXF01 (10): nc_candidate_review_ready, candidate_status, not_dispatchable,
    offline_candidate, generic_iso_profile, motion_blocks, spindle_rpm_exact,
    tool_number, compatible_risk_in_warnings, not_claimed
  TestP7BE2EDXF01 (7): 9_holes, no_no_match, proposed_status, engineer_not_confirmed,
    not_dispatchable, compatible_count_two, groups_cover_all
  TestP7CE2EDXF01 (4): full_chain_validated_offline, validated_not_dispatchable,
    partial_stays_engineer_reviewed, all_p7_safety_invariants_full_chain
```

---

## P7-D: DXF-03 Tool Coverage — Status

```
BLOCKER: auto-mode classifier denies Edit on backend/cutting_tools/seed_catalog.py

Records ready to add (manufacturer-sourced, not fabricated):
  sandvik-860-1-1600-073a1-pm  16mm  source=coromant.sandvik.com CoroDrill 860-1
  sandvik-860-1-1800-083a1-pm  18mm  source=coromant.sandvik.com CoroDrill 860-1
  sandvik-860-1-2400-110a1-pm  24mm  source=coromant.sandvik.com CoroDrill 860-1

Action required: User must grant permission for Edit on seed_catalog.py
                 (or run with auto-approve). No fabricated data.

P7_D_TOOL_RECORD_STATUS=DEFERRED_CLASSIFIER_BLOCKED
DXF03_16MM_TOOL_READY=NO
DXF03_18MM_TOOL_READY=NO
DXF03_24MM_TOOL_READY=NO
```

---

## P7-E: DXF-02 Boring — Status

```
Entry gate: P7-A validated = YES, P7-C review gate = YES
           P7-D catalog = NO (tool coverage incomplete)

Assessment: 60mm feature in DXF-02 requires boring bar strategy.
            Existing boring bar in catalog: sandvik-a25t-sducr-11 (25mm shank, min bore 32mm).
            60mm bore is geometrically within range, but no boring toolpath or NC adapter
            has been validated for the boring operation type.

P7_E_RESULT=DEFERRED_CAPABILITY_GAP
DXF02_BORING_STATUS=DEFERRED
```

---

## Safety Audit Results

```
IS_DISPATCHABLE_TRUE_FOUND=NO
PRODUCTION_RELEASE_TRUE_FOUND=NO
REAL_MACHINE_WRITE_FOUND=NO      (backend/dispatch/__init__.py: NO_REAL_MACHINE_WRITE=YES)
AUTO_CNC_DISPATCH_FOUND=NO       (all dispatch paths: NO_AUTO_DISPATCH=YES)
AUTO_APPROVAL_FOUND=NO
AUTOMATIC_ADAPTATION_FOUND=NO
```

Grep-verified over `backend/` with `--include="*.py"` excluding comments.

---

## Collision / Simulation Boundary

```
TOOL_COLLISION_VALIDATED=NOT_IMPLEMENTED
HOLDER_COLLISION_VALIDATED=NOT_IMPLEMENTED
FIXTURE_COLLISION_VALIDATED=NOT_IMPLEMENTED
MACHINE_COLLISION_VALIDATED=NOT_IMPLEMENTED
STOCK_REMOVAL_VALIDATED=NOT_IMPLEMENTED
```

No collision engine is claimed. All `VALIDATED_OFFLINE` results carry this boundary explicitly.

---

## Full Test Summary

```
NEW_TESTS_ADDED=114
P7_TESTS=114
  NC_BRIDGE_TESTS=32
  BATCH_TESTS=20
  REVIEW_GATE_TESTS=22
  SAFETY_TESTS=21
  REAL_SAMPLE_E2E_TESTS=19

Manufacturing suite regression: 396 PASS, 12 SKIP (pre-existing)
NEW_FAILURES_INTRODUCED=0
RUFF=CLEAN
```

---

## Change Control

```
PRODUCTION_FILES_CHANGED=3
  backend/manufacturing/nc_generation_adapter.py  (P7-A — new file)
  backend/manufacturing/multi_hole_sequence.py    (P7-B — new file)
  backend/manufacturing/nc_review.py              (P7-C — new file)
LIBRARY_FILES_CHANGED=0  (seed_catalog.py deferred)
TEST_FILES_CHANGED=5     (new test files)
DOC_FILES_CHANGED=2      (REAL_SAMPLE_P7_ASSESSMENT.md, this file)
I18N_FILES_CHANGED=0
FRONTEND_FILES_CHANGED=0
```

---

## Final Status

```
FINAL_RESULT=PASS_P7_MULTI_FEATURE_OFFLINE_NC_VALIDATION
P7_A_NC_GENERATION_BRIDGE=PASS
P7_B_MULTI_HOLE_SEQUENCE=PASS
P7_C_VALIDATED_OFFLINE_GATE=PASS
P7_D_DXF03_TOOL_COVERAGE=DEFERRED_CLASSIFIER_BLOCKED
P7_E_DXF02_BORING=DEFERRED_CAPABILITY_GAP

GENERIC_POSTPROCESSOR_USED=YES (GENERIC_ISO_TEST_v1)
PRODUCTION_CONTROLLER_COMPATIBILITY=NOT_CLAIMED
CONTROLLER_VALIDATED=NO
COLLISION_VALIDATED=NO
PRODUCTION_RELEASE_READY=NO

LEVEL21_STARTED=NO
TAG_CREATED=NO
RELEASE_CREATED=NO
FORCE_PUSH_USED=NO
SOURCE_SAMPLE_FILES_COMMITTED=NO
ALL_SOURCE_FILES_UNCHANGED=YES
```
