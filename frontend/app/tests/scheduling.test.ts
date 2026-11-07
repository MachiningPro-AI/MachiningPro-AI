/**
 * Level-13 Machine Scheduling and Job Assignment — frontend unit tests.
 * Uses node:test runner (NOT vitest).
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  SchedulingContractViolation,
  algorithmLabel,
  eligibilityLabel,
  enforceAssignmentCandidate,
  enforceScheduleCandidate,
  enforceSchedulingContract,
  isBlocked,
  isCandidate,
  isReviewRequired,
  isUnknown,
  requiresApproval,
} from '../src/services/scheduling.ts';

import type {
  JobAssignmentCandidate,
  ScheduleCandidate,
} from '../src/types/scheduling.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScheduleCandidate(overrides: Partial<ScheduleCandidate> = {}): ScheduleCandidate {
  return {
    job_id: 'JOB-001',
    machine_id: 'MACHINE-001',
    queue_position: null,
    planned_start_iso: null,
    planned_finish_iso: null,
    duration: {
      setup_time_min: null,
      cycle_time_per_part_min: null,
      quantity: 1,
      total_estimated_min: null,
      status: 'UNKNOWN',
      assumptions: [],
      warnings: [],
    },
    score_components: {},
    hard_constraint_results: [],
    soft_preference_results: {},
    readiness: {
      status: 'UNKNOWN',
      engineering_complete: false,
      cam_ready: false,
      toolpath_verified: false,
      nc_readiness: {
        status: 'UNKNOWN',
        nc_candidate_ref: null,
        nc_candidate_status: null,
        toolpath_verified: false,
        is_stale: false,
        block_reasons: [],
        warnings: [],
      },
      machine_eligible: false,
      setup_readiness: {
        status: 'UNKNOWN',
        tool_statuses: {},
        holder_statuses: {},
        fixture_status: 'UNKNOWN',
        missing_tools: [],
        missing_holders: [],
        fixture_blocked: false,
        block_reasons: [],
        warnings: [],
      },
      schedule_slot_available: false,
      block_reasons: [],
      warnings: [],
      approval_required: true,
    },
    lateness_min: null,
    warnings: [],
    is_dispatch_order: false,
    approval_required: true,
    ...overrides,
  } as ScheduleCandidate;
}

function makeAssignmentCandidate(overrides: Partial<JobAssignmentCandidate> = {}): JobAssignmentCandidate {
  return {
    job_ref: 'JOB-001',
    machine_ref: 'MACHINE-001',
    setup_ref: null,
    nc_candidate_ref: null,
    tool_refs: [],
    fixture_ref: null,
    schedule_candidate: null,
    eligibility_report: {
      machine_id: 'MACHINE-001',
      result: 'UNKNOWN',
      checks: [],
      hard_constraint_failures: [],
      soft_preference_score: 0,
      unknown_data_fields: [],
      warnings: [],
    },
    setup_readiness: {
      status: 'UNKNOWN',
      tool_statuses: {},
      holder_statuses: {},
      fixture_status: 'UNKNOWN',
      missing_tools: [],
      missing_holders: [],
      fixture_blocked: false,
      block_reasons: [],
      warnings: [],
    },
    nc_readiness: {
      status: 'UNKNOWN',
      nc_candidate_ref: null,
      nc_candidate_status: null,
      toolpath_verified: false,
      is_stale: false,
      block_reasons: [],
      warnings: [],
    },
    readiness: {
      status: 'UNKNOWN',
      engineering_complete: false,
      cam_ready: false,
      toolpath_verified: false,
      nc_readiness: {
        status: 'UNKNOWN',
        nc_candidate_ref: null,
        nc_candidate_status: null,
        toolpath_verified: false,
        is_stale: false,
        block_reasons: [],
        warnings: [],
      },
      machine_eligible: false,
      setup_readiness: {
        status: 'UNKNOWN',
        tool_statuses: {},
        holder_statuses: {},
        fixture_status: 'UNKNOWN',
        missing_tools: [],
        missing_holders: [],
        fixture_blocked: false,
        block_reasons: [],
        warnings: [],
      },
      schedule_slot_available: false,
      block_reasons: [],
      warnings: [],
      approval_required: true,
    },
    eligibility_reasons: [],
    preference_reasons: [],
    unknown_data: [],
    warnings: [],
    approval_required: true,
    is_dispatch_order: false,
    ...overrides,
  } as JobAssignmentCandidate;
}

// ---------------------------------------------------------------------------
// enforceSchedulingContract
// ---------------------------------------------------------------------------

describe('enforceSchedulingContract', () => {
  it('passes when is_dispatch_order=false and approval_required=true', () => {
    assert.doesNotThrow(() =>
      enforceSchedulingContract({ is_dispatch_order: false, approval_required: true })
    );
  });

  it('throws when is_dispatch_order=true', () => {
    assert.throws(
      () => enforceSchedulingContract({ is_dispatch_order: true, approval_required: true }),
      SchedulingContractViolation
    );
  });

  it('throws when is_dispatch_order is missing (undefined)', () => {
    assert.throws(
      () => enforceSchedulingContract({ is_dispatch_order: undefined, approval_required: true }),
      SchedulingContractViolation
    );
  });

  it('throws when approval_required=false', () => {
    assert.throws(
      () => enforceSchedulingContract({ is_dispatch_order: false, approval_required: false }),
      SchedulingContractViolation
    );
  });

  it('throws when approval_required is missing (undefined)', () => {
    assert.throws(
      () => enforceSchedulingContract({ is_dispatch_order: false, approval_required: undefined }),
      SchedulingContractViolation
    );
  });

  it('error message contains SCHEDULING_CONTRACT_VIOLATION', () => {
    try {
      enforceSchedulingContract({ is_dispatch_order: true, approval_required: true });
      assert.fail('should have thrown');
    } catch (e) {
      assert.ok(e instanceof SchedulingContractViolation);
      assert.ok((e as Error).message.includes('SCHEDULING_CONTRACT_VIOLATION'));
    }
  });
});

// ---------------------------------------------------------------------------
// enforceScheduleCandidate
// ---------------------------------------------------------------------------

describe('enforceScheduleCandidate', () => {
  it('passes for valid candidate', () => {
    const candidate = makeScheduleCandidate();
    assert.doesNotThrow(() => enforceScheduleCandidate(candidate));
  });

  it('throws when is_dispatch_order=true', () => {
    const candidate = makeScheduleCandidate({ is_dispatch_order: true as unknown as false });
    assert.throws(() => enforceScheduleCandidate(candidate), SchedulingContractViolation);
  });

  it('throws when approval_required=false', () => {
    const candidate = makeScheduleCandidate({ approval_required: false as unknown as true });
    assert.throws(() => enforceScheduleCandidate(candidate), SchedulingContractViolation);
  });

  it('error is SchedulingContractViolation instance', () => {
    const candidate = makeScheduleCandidate({ is_dispatch_order: true as unknown as false });
    assert.throws(
      () => enforceScheduleCandidate(candidate),
      (err: unknown) => err instanceof SchedulingContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// enforceAssignmentCandidate
// ---------------------------------------------------------------------------

describe('enforceAssignmentCandidate', () => {
  it('passes for valid assignment candidate', () => {
    const c = makeAssignmentCandidate();
    assert.doesNotThrow(() => enforceAssignmentCandidate(c));
  });

  it('throws when is_dispatch_order=true', () => {
    const c = makeAssignmentCandidate({ is_dispatch_order: true as unknown as false });
    assert.throws(() => enforceAssignmentCandidate(c), SchedulingContractViolation);
  });

  it('throws when approval_required=false', () => {
    const c = makeAssignmentCandidate({ approval_required: false as unknown as true });
    assert.throws(() => enforceAssignmentCandidate(c), SchedulingContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Status helpers — isBlocked
// ---------------------------------------------------------------------------

describe('isBlocked', () => {
  it('returns true for SCHEDULING_BLOCKED', () => {
    assert.strictEqual(isBlocked('SCHEDULING_BLOCKED'), true);
  });

  it('returns true for DISPATCH_BLOCKED', () => {
    assert.strictEqual(isBlocked('DISPATCH_BLOCKED'), true);
  });

  it('returns true for BLOCKED', () => {
    assert.strictEqual(isBlocked('BLOCKED'), true);
  });

  it('returns true for INELIGIBLE', () => {
    assert.strictEqual(isBlocked('INELIGIBLE'), true);
  });

  it('returns false for ELIGIBLE', () => {
    assert.strictEqual(isBlocked('ELIGIBLE'), false);
  });

  it('returns false for UNKNOWN', () => {
    assert.strictEqual(isBlocked('UNKNOWN'), false);
  });

  it('returns false for SCHEDULED_CANDIDATE', () => {
    assert.strictEqual(isBlocked('SCHEDULED_CANDIDATE'), false);
  });

  it('returns false for READY_FOR_SCHEDULING', () => {
    assert.strictEqual(isBlocked('READY_FOR_SCHEDULING'), false);
  });
});

// ---------------------------------------------------------------------------
// Status helpers — isCandidate
// ---------------------------------------------------------------------------

describe('isCandidate', () => {
  it('returns true for SCHEDULED_CANDIDATE', () => {
    assert.strictEqual(isCandidate('SCHEDULED_CANDIDATE'), true);
  });

  it('returns true for ASSIGNMENT_REVIEW_REQUIRED', () => {
    assert.strictEqual(isCandidate('ASSIGNMENT_REVIEW_REQUIRED'), true);
  });

  it('returns false for ELIGIBLE', () => {
    assert.strictEqual(isCandidate('ELIGIBLE'), false);
  });

  it('returns false for UNKNOWN', () => {
    assert.strictEqual(isCandidate('UNKNOWN'), false);
  });

  it('returns false for BLOCKED', () => {
    assert.strictEqual(isCandidate('BLOCKED'), false);
  });
});

// ---------------------------------------------------------------------------
// Status helpers — isUnknown
// ---------------------------------------------------------------------------

describe('isUnknown', () => {
  it('returns true for UNKNOWN', () => {
    assert.strictEqual(isUnknown('UNKNOWN'), true);
  });

  it('returns false for AVAILABLE', () => {
    assert.strictEqual(isUnknown('AVAILABLE'), false);
  });

  it('returns false for BLOCKED', () => {
    assert.strictEqual(isUnknown('BLOCKED'), false);
  });

  it('UNKNOWN is not AVAILABLE (key invariant)', () => {
    // HARD RULE 22: unknown availability must not be treated as available
    assert.notStrictEqual(isUnknown('UNKNOWN'), false);
    assert.strictEqual(isUnknown('AVAILABLE'), false);
    assert.strictEqual(isUnknown('UNKNOWN'), true);
  });
});

// ---------------------------------------------------------------------------
// Status helpers — isReviewRequired
// ---------------------------------------------------------------------------

describe('isReviewRequired', () => {
  it('returns true for REVIEW_REQUIRED', () => {
    assert.strictEqual(isReviewRequired('REVIEW_REQUIRED'), true);
  });

  it('returns true for ASSIGNMENT_REVIEW_REQUIRED', () => {
    assert.strictEqual(isReviewRequired('ASSIGNMENT_REVIEW_REQUIRED'), true);
  });

  it('returns false for ELIGIBLE', () => {
    assert.strictEqual(isReviewRequired('ELIGIBLE'), false);
  });
});

// ---------------------------------------------------------------------------
// requiresApproval
// ---------------------------------------------------------------------------

describe('requiresApproval', () => {
  it('returns true when approval_required=true', () => {
    assert.strictEqual(requiresApproval({ approval_required: true }), true);
  });

  it('returns false when approval_required=false', () => {
    assert.strictEqual(requiresApproval({ approval_required: false }), false);
  });

  it('every ScheduleCandidate requires approval', () => {
    const c = makeScheduleCandidate();
    assert.strictEqual(requiresApproval(c), true);
  });

  it('every JobAssignmentCandidate requires approval', () => {
    const c = makeAssignmentCandidate();
    assert.strictEqual(requiresApproval(c), true);
  });
});

// ---------------------------------------------------------------------------
// algorithmLabel
// ---------------------------------------------------------------------------

describe('algorithmLabel', () => {
  it('FIFO returns First In First Out', () => {
    assert.strictEqual(algorithmLabel('FIFO'), 'First In First Out');
  });

  it('EDD returns Earliest Due Date', () => {
    assert.strictEqual(algorithmLabel('EDD'), 'Earliest Due Date');
  });

  it('SPT returns Shortest Processing Time', () => {
    assert.strictEqual(algorithmLabel('SPT'), 'Shortest Processing Time');
  });

  it('PRIORITY_FIRST returns Priority First', () => {
    assert.strictEqual(algorithmLabel('PRIORITY_FIRST'), 'Priority First');
  });

  it('unknown algorithm returns itself', () => {
    assert.strictEqual(algorithmLabel('MY_ALGO'), 'MY_ALGO');
  });
});

// ---------------------------------------------------------------------------
// eligibilityLabel
// ---------------------------------------------------------------------------

describe('eligibilityLabel', () => {
  it('ELIGIBLE returns Eligible', () => {
    assert.strictEqual(eligibilityLabel('ELIGIBLE'), 'Eligible');
  });

  it('PARTIALLY_ELIGIBLE returns Partially Eligible', () => {
    assert.strictEqual(eligibilityLabel('PARTIALLY_ELIGIBLE'), 'Partially Eligible');
  });

  it('INELIGIBLE returns Ineligible', () => {
    assert.strictEqual(eligibilityLabel('INELIGIBLE'), 'Ineligible');
  });

  it('UNKNOWN returns Unknown', () => {
    assert.strictEqual(eligibilityLabel('UNKNOWN'), 'Unknown');
  });

  it('unknown value returns itself', () => {
    assert.strictEqual(eligibilityLabel('SOME_NEW_VALUE'), 'SOME_NEW_VALUE');
  });
});

// ---------------------------------------------------------------------------
// Invariant cross-checks
// ---------------------------------------------------------------------------

describe('invariants', () => {
  it('makeScheduleCandidate always has is_dispatch_order=false', () => {
    const c = makeScheduleCandidate();
    assert.strictEqual(c.is_dispatch_order, false);
  });

  it('makeScheduleCandidate always has approval_required=true', () => {
    const c = makeScheduleCandidate();
    assert.strictEqual(c.approval_required, true);
  });

  it('makeAssignmentCandidate always has is_dispatch_order=false', () => {
    const c = makeAssignmentCandidate();
    assert.strictEqual(c.is_dispatch_order, false);
  });

  it('makeAssignmentCandidate always has approval_required=true', () => {
    const c = makeAssignmentCandidate();
    assert.strictEqual(c.approval_required, true);
  });

  it('UNKNOWN availability is NOT the same as AVAILABLE', () => {
    // Proves HARD RULE 22
    const unknownStatus = 'UNKNOWN';
    const availableStatus = 'AVAILABLE';
    assert.notStrictEqual(unknownStatus, availableStatus);
    assert.strictEqual(isUnknown(unknownStatus), true);
    assert.strictEqual(isUnknown(availableStatus), false);
  });

  it('INELIGIBLE is blocked', () => {
    // Proves HARD RULE 18: compatible != available
    assert.strictEqual(isBlocked('INELIGIBLE'), true);
  });

  it('ELIGIBLE is not blocked', () => {
    assert.strictEqual(isBlocked('ELIGIBLE'), false);
  });

  it('BLOCKED setup readiness does not mean dispatch ready', () => {
    const c = makeScheduleCandidate({
      readiness: {
        status: 'DISPATCH_BLOCKED',
        engineering_complete: false,
        cam_ready: false,
        toolpath_verified: false,
        nc_readiness: {
          status: 'BLOCKED',
          nc_candidate_ref: null,
          nc_candidate_status: null,
          toolpath_verified: false,
          is_stale: false,
          block_reasons: ['NC_CANDIDATE_BLOCKED'],
          warnings: [],
        },
        machine_eligible: false,
        setup_readiness: {
          status: 'BLOCKED',
          tool_statuses: {},
          holder_statuses: {},
          fixture_status: 'MISSING',
          missing_tools: ['TOOL-001'],
          missing_holders: [],
          fixture_blocked: true,
          block_reasons: ['TOOL_MISSING', 'FIXTURE_MISSING'],
          warnings: [],
        },
        schedule_slot_available: false,
        block_reasons: ['TOOL_MISSING'],
        warnings: [],
        approval_required: true,
      },
    });
    assert.strictEqual(isBlocked(c.readiness.status), true);
    assert.strictEqual(c.is_dispatch_order, false);
    assert.strictEqual(c.approval_required, true);
  });
});

// ---------------------------------------------------------------------------
// SchedulingContractViolation class
// ---------------------------------------------------------------------------

describe('SchedulingContractViolation', () => {
  it('is an instance of Error', () => {
    const e = new SchedulingContractViolation('test');
    assert.ok(e instanceof Error);
  });

  it('is an instance of SchedulingContractViolation', () => {
    const e = new SchedulingContractViolation('test');
    assert.ok(e instanceof SchedulingContractViolation);
  });

  it('name is SchedulingContractViolation', () => {
    const e = new SchedulingContractViolation('test');
    assert.strictEqual(e.name, 'SchedulingContractViolation');
  });

  it('message starts with SCHEDULING_CONTRACT_VIOLATION', () => {
    const e = new SchedulingContractViolation('test reason');
    assert.ok(e.message.startsWith('SCHEDULING_CONTRACT_VIOLATION:'));
  });

  it('message includes the reason', () => {
    const e = new SchedulingContractViolation('some reason');
    assert.ok(e.message.includes('some reason'));
  });
});
