/**
 * Level-17 CNC Job Planning & Machine Assignment — TypeScript contract tests.
 *
 * Tests verify safety invariants, contract enforcement, and utility functions.
 * No real machines are commanded. All test data is synthetic.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
  NO_AUTOMATIC_MACHINE_ASSIGNMENT,
  NO_AUTOMATIC_JOB_DISPATCH,
  NO_FABRICATED_CAPABILITY_DATA,
  MISSING_DATA_FAILS_CLOSED,
  ASSIGNMENT_IS_PROPOSED_ONLY,
  HUMAN_APPROVAL_MANDATORY,
  UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
} from '../src/types/job_planning.ts';

import {
  JobPlanningContractViolation,
  enforceRequirementsContract,
  enforceCapabilityProfileContract,
  enforceWorkloadContract,
  enforceCandidateContract,
  enforceRecommendationContract,
  enforceNoDispatch,
  isSuitableCandidate,
  summarizeRecommendation,
  summarizeCandidate,
  missingDataFailsClosed,
} from '../src/services/job_planning.ts';

import type {
  AssignmentCandidate,
  AssignmentRecommendation,
  CamOperationRequirements,
  MachineCapabilityProfile,
  WorkloadEstimate,
} from '../src/types/job_planning.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeRequirements(overrides: Partial<CamOperationRequirements> = {}): CamOperationRequirements {
  return {
    job_id: 'JOB_TEST_001',
    part_reference: 'PART_A',
    material: 'AL_6082_T6',
    operations: ['MILLING'],
    required_machine_class: 'VMC_3AXIS',
    required_axis_count: 3,
    required_spindle_rpm: 6000,
    required_spindle_power_kw: null,
    required_x_travel_mm: 400,
    required_y_travel_mm: 300,
    required_z_travel_mm: 300,
    workpiece_mass_kg: null,
    requires_through_spindle_coolant: false,
    requires_live_tooling: false,
    requires_tapping: false,
    requires_boring: false,
    estimated_cycle_time_min: 45,
    data_source: 'CAM_PLAN',
    is_fabricated_requirements: false,
    ...overrides,
  };
}

function makeProfile(overrides: Partial<MachineCapabilityProfile> = {}): MachineCapabilityProfile {
  return {
    machine_id: 'MACHINE_VMC_001',
    machine_class: 'VMC_3AXIS',
    axis_count: 3,
    spindle_max_rpm: 12000,
    spindle_power_kw: 15,
    travel_x_mm: 600,
    travel_y_mm: 500,
    travel_z_mm: 400,
    table_load_kg: 300,
    turning_capable: false,
    milling_capable: true,
    drilling_capable: true,
    through_spindle_coolant: true,
    has_live_tooling: false,
    capable_tapping: true,
    capable_boring: true,
    tool_magazine_capacity: 24,
    is_fabricated_capability: false,
    ...overrides,
  };
}

function makeWorkload(overrides: Partial<WorkloadEstimate> = {}): WorkloadEstimate {
  return {
    machine_id: 'MACHINE_VMC_001',
    queue_depth: 0,
    estimated_cycle_time_min: 45,
    workload_status: 'LOW',
    is_fabricated: false,
    ...overrides,
  };
}

function makeCandidate(overrides: Partial<AssignmentCandidate> = {}): AssignmentCandidate {
  return {
    machine_id: 'MACHINE_VMC_001',
    rank: 1,
    capability_score: 0.9,
    material_compatibility: 'COMPATIBLE',
    spindle_match: 'WITHIN_RANGE',
    workload_status: 'LOW',
    capability_checks: [],
    workload_estimate: makeWorkload(),
    incompatibility_reasons: [],
    soft_preference_score: 0.5,
    overall_score: 0.85,
    explanation: 'Good match',
    is_proposed_only: true,
    is_automatic_dispatch: false,
    ...overrides,
  };
}

function makeRecommendation(overrides: Partial<AssignmentRecommendation> = {}): AssignmentRecommendation {
  return {
    job_id: 'JOB_TEST_001',
    status: 'PROPOSED',
    candidates: [makeCandidate()],
    best_candidate_id: 'MACHINE_VMC_001',
    planning_warnings: [],
    blocking_reasons: [],
    is_proposed_only: true,
    is_automatic_dispatch: false,
    review_required: true,
    is_fabricated_data: false,
    explanation: 'Proposed assignment',
    ranking_objective: 'CAPABILITY_FIT',
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Safety constants
// ---------------------------------------------------------------------------

describe('Safety constants', () => {
  it('NO_AUTOMATIC_MACHINE_ASSIGNMENT is true', () => {
    assert.strictEqual(NO_AUTOMATIC_MACHINE_ASSIGNMENT, true);
  });
  it('NO_AUTOMATIC_JOB_DISPATCH is true', () => {
    assert.strictEqual(NO_AUTOMATIC_JOB_DISPATCH, true);
  });
  it('NO_FABRICATED_CAPABILITY_DATA is true', () => {
    assert.strictEqual(NO_FABRICATED_CAPABILITY_DATA, true);
  });
  it('MISSING_DATA_FAILS_CLOSED is true', () => {
    assert.strictEqual(MISSING_DATA_FAILS_CLOSED, true);
  });
  it('ASSIGNMENT_IS_PROPOSED_ONLY is true', () => {
    assert.strictEqual(ASSIGNMENT_IS_PROPOSED_ONLY, true);
  });
  it('HUMAN_APPROVAL_MANDATORY is true', () => {
    assert.strictEqual(HUMAN_APPROVAL_MANDATORY, true);
  });
  it('UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE is true', () => {
    assert.strictEqual(UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE, true);
  });
});

// ---------------------------------------------------------------------------
// Requirements contract
// ---------------------------------------------------------------------------

describe('CamOperationRequirements contract', () => {
  it('valid requirements passes contract check', () => {
    const req = makeRequirements();
    assert.doesNotThrow(() => enforceRequirementsContract(req));
  });
  it('is_fabricated_requirements=false is the invariant', () => {
    const req = makeRequirements();
    assert.strictEqual(req.is_fabricated_requirements, false);
  });
  it('fabricated requirements throws contract violation', () => {
    const req = { ...makeRequirements(), is_fabricated_requirements: true as unknown as false };
    assert.throws(
      () => enforceRequirementsContract(req),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('contract violation error name is set', () => {
    const req = { ...makeRequirements(), is_fabricated_requirements: true as unknown as false };
    try {
      enforceRequirementsContract(req);
      assert.fail('should have thrown');
    } catch (e) {
      assert.ok(e instanceof JobPlanningContractViolation);
      assert.strictEqual(e.name, 'JobPlanningContractViolation');
    }
  });
});

// ---------------------------------------------------------------------------
// Capability profile contract
// ---------------------------------------------------------------------------

describe('MachineCapabilityProfile contract', () => {
  it('valid profile passes contract check', () => {
    const profile = makeProfile();
    assert.doesNotThrow(() => enforceCapabilityProfileContract(profile));
  });
  it('is_fabricated_capability=false is the invariant', () => {
    const profile = makeProfile();
    assert.strictEqual(profile.is_fabricated_capability, false);
  });
  it('fabricated capability throws contract violation', () => {
    const profile = { ...makeProfile(), is_fabricated_capability: true as unknown as false };
    assert.throws(
      () => enforceCapabilityProfileContract(profile),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Workload contract
// ---------------------------------------------------------------------------

describe('WorkloadEstimate contract', () => {
  it('valid workload passes contract check', () => {
    const wl = makeWorkload();
    assert.doesNotThrow(() => enforceWorkloadContract(wl));
  });
  it('is_fabricated=false is the invariant', () => {
    const wl = makeWorkload();
    assert.strictEqual(wl.is_fabricated, false);
  });
  it('fabricated workload throws contract violation', () => {
    const wl = { ...makeWorkload(), is_fabricated: true as unknown as false };
    assert.throws(
      () => enforceWorkloadContract(wl),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Candidate contract
// ---------------------------------------------------------------------------

describe('AssignmentCandidate contract', () => {
  it('valid candidate passes contract check', () => {
    const c = makeCandidate();
    assert.doesNotThrow(() => enforceCandidateContract(c));
  });
  it('is_proposed_only=true is invariant', () => {
    const c = makeCandidate();
    assert.strictEqual(c.is_proposed_only, true);
  });
  it('is_automatic_dispatch=false is invariant', () => {
    const c = makeCandidate();
    assert.strictEqual(c.is_automatic_dispatch, false);
  });
  it('is_proposed_only=false throws', () => {
    const c = { ...makeCandidate(), is_proposed_only: false as unknown as true };
    assert.throws(
      () => enforceCandidateContract(c),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('is_automatic_dispatch=true throws', () => {
    const c = { ...makeCandidate(), is_automatic_dispatch: true as unknown as false };
    assert.throws(
      () => enforceCandidateContract(c),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Recommendation contract
// ---------------------------------------------------------------------------

describe('AssignmentRecommendation contract', () => {
  it('valid recommendation passes all contract checks', () => {
    const rec = makeRecommendation();
    assert.doesNotThrow(() => enforceRecommendationContract(rec));
    assert.doesNotThrow(() => enforceNoDispatch(rec));
  });
  it('is_proposed_only=true is invariant', () => {
    const rec = makeRecommendation();
    assert.strictEqual(rec.is_proposed_only, true);
  });
  it('is_automatic_dispatch=false is invariant', () => {
    const rec = makeRecommendation();
    assert.strictEqual(rec.is_automatic_dispatch, false);
  });
  it('review_required=true is invariant', () => {
    const rec = makeRecommendation();
    assert.strictEqual(rec.review_required, true);
  });
  it('is_fabricated_data=false is invariant', () => {
    const rec = makeRecommendation();
    assert.strictEqual(rec.is_fabricated_data, false);
  });
  it('review_required=false throws', () => {
    const rec = { ...makeRecommendation(), review_required: false as unknown as true };
    assert.throws(
      () => enforceRecommendationContract(rec),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('is_fabricated_data=true throws', () => {
    const rec = { ...makeRecommendation(), is_fabricated_data: true as unknown as false };
    assert.throws(
      () => enforceRecommendationContract(rec),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('DISPATCHED_TO_MACHINE status throws enforceNoDispatch', () => {
    const rec = { ...makeRecommendation(), status: 'DISPATCHED_TO_MACHINE' as 'PROPOSED' };
    assert.throws(
      () => enforceNoDispatch(rec),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('EXECUTING status throws enforceNoDispatch', () => {
    const rec = { ...makeRecommendation(), status: 'EXECUTING' as 'PROPOSED' };
    assert.throws(
      () => enforceNoDispatch(rec),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('AUTO_ASSIGNED status throws enforceNoDispatch', () => {
    const rec = { ...makeRecommendation(), status: 'AUTO_ASSIGNED' as 'PROPOSED' };
    assert.throws(
      () => enforceNoDispatch(rec),
      (e) => e instanceof JobPlanningContractViolation
    );
  });
  it('PROPOSED status does not throw', () => {
    const rec = makeRecommendation({ status: 'PROPOSED' });
    assert.doesNotThrow(() => enforceNoDispatch(rec));
  });
  it('REVIEW_REQUIRED status does not throw', () => {
    const rec = makeRecommendation({ status: 'REVIEW_REQUIRED' });
    assert.doesNotThrow(() => enforceNoDispatch(rec));
  });
});

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

describe('isSuitableCandidate', () => {
  it('compatible material, within-range spindle, positive score → suitable', () => {
    const c = makeCandidate({
      material_compatibility: 'COMPATIBLE',
      spindle_match: 'WITHIN_RANGE',
      capability_score: 0.8,
    });
    assert.strictEqual(isSuitableCandidate(c), true);
  });
  it('INCOMPATIBLE material → not suitable', () => {
    const c = makeCandidate({ material_compatibility: 'INCOMPATIBLE' });
    assert.strictEqual(isSuitableCandidate(c), false);
  });
  it('OVER_LIMIT spindle → not suitable', () => {
    const c = makeCandidate({ spindle_match: 'OVER_LIMIT' });
    assert.strictEqual(isSuitableCandidate(c), false);
  });
  it('zero capability score → not suitable', () => {
    const c = makeCandidate({ capability_score: 0 });
    assert.strictEqual(isSuitableCandidate(c), false);
  });
  it('UNKNOWN material → suitable (unknown is not incompatible)', () => {
    const c = makeCandidate({ material_compatibility: 'UNKNOWN' });
    assert.strictEqual(isSuitableCandidate(c), true);
  });
});

describe('summarizeRecommendation', () => {
  it('includes job_id, status, candidates, best_candidate_id, review_required', () => {
    const rec = makeRecommendation();
    const summary = summarizeRecommendation(rec);
    assert.ok(summary.includes('JOB_TEST_001'));
    assert.ok(summary.includes('PROPOSED'));
    assert.ok(summary.includes('MACHINE_VMC_001'));
    assert.ok(summary.includes('review_required=true'));
  });
  it('best=NONE when no best candidate', () => {
    const rec = makeRecommendation({ best_candidate_id: null });
    assert.ok(summarizeRecommendation(rec).includes('best=NONE'));
  });
});

describe('summarizeCandidate', () => {
  it('includes rank, machine_id, score, material, spindle, workload', () => {
    const c = makeCandidate();
    const summary = summarizeCandidate(c);
    assert.ok(summary.includes('rank=1'));
    assert.ok(summary.includes('MACHINE_VMC_001'));
    assert.ok(summary.includes('COMPATIBLE'));
    assert.ok(summary.includes('WITHIN_RANGE'));
    assert.ok(summary.includes('LOW'));
  });
});

describe('missingDataFailsClosed', () => {
  it('complete profile → false (data present)', () => {
    const profile = makeProfile();
    assert.strictEqual(missingDataFailsClosed(profile), false);
  });
  it('null axis_count → true (data missing)', () => {
    const profile = makeProfile({ axis_count: null });
    assert.strictEqual(missingDataFailsClosed(profile), true);
  });
  it('null spindle_max_rpm → true', () => {
    const profile = makeProfile({ spindle_max_rpm: null });
    assert.strictEqual(missingDataFailsClosed(profile), true);
  });
  it('UNKNOWN machine class → true', () => {
    const profile = makeProfile({ machine_class: 'UNKNOWN' });
    assert.strictEqual(missingDataFailsClosed(profile), true);
  });
});
