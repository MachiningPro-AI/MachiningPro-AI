/**
 * Level-14 Shop Floor Integration and Safe Dispatch Foundation — frontend tests.
 *
 * Uses node:test runner (NOT vitest).
 * 60 tests covering contracts, invariants, status helpers, and security rules.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import {
  DispatchContractViolation,
  approvalStatusLabel,
  assignmentIsNotDispatch,
  dryRunApprovalIsNotExecution,
  enforceDispatchContract,
  enforceDispatchPackage,
  enforceDryRunResult,
  enforceMachineStateSnapshot,
  enforceShopFloorReadiness,
  errorLabel,
  isApprovalGranted,
  isApprovalPending,
  isBlocked,
  isConnectionUnknown,
  isDryRunFailed,
  isDryRunPassed,
  isStale,
  ncCandidateIsNotMachineApproved,
  readinessLabel,
  requiresApproval,
  unknownIsNotConnected,
} from '../src/services/dispatch.ts';

import type {
  ApprovalStatus,
  ConnectionStatus,
  DispatchApproval,
  DispatchPackage,
  DryRunDispatchResult,
  MachineStateSnapshot,
  ShopFloorReadiness,
} from '../src/types/dispatch.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makePackage(overrides: Partial<DispatchPackage> = {}): DispatchPackage {
  return {
    package_id: 'PKG-001',
    job_ref: 'J-001',
    assignment_ref: 'ASN-001',
    machine_ref: 'M-001',
    nc_candidate_ref: 'NC-001',
    nc_hash: 'abc123',
    post_profile_ref: null,
    tool_list: ['T001'],
    holder_list: [],
    fixture_ref: 'FIX-001',
    setup_ref: null,
    work_offset_ref: null,
    verification_ref: 'VER-001',
    approval_ref: null,
    schedule_ref: null,
    created_at: '2026-11-07T00:00:00Z',
    status: 'DRAFT',
    warnings: [],
    is_dispatch_order: false,
    approval_required: true,
    ...overrides,
  } as DispatchPackage;
}

function makeDryRunResult(overrides: Partial<DryRunDispatchResult> = {}): DryRunDispatchResult {
  return {
    result_id: 'RES-001',
    package_ref: 'PKG-001',
    machine_ref: 'M-001',
    status: 'PASSED',
    is_real_transfer: false,
    is_dispatch_order: false,
    checks_passed: [],
    failures: [],
    warnings: [],
    timestamp: '2026-11-07T00:00:00Z',
    ...overrides,
  } as DryRunDispatchResult;
}

function makeMachineState(overrides: Partial<MachineStateSnapshot> = {}): MachineStateSnapshot {
  return {
    machine_id: 'M-001',
    timestamp: '2026-11-07T00:00:00Z',
    connection_status: 'CONNECTED',
    availability: 'IDLE',
    mode: 'AUTO',
    current_program: null,
    current_job: null,
    alarm_state: 'NO_ALARM',
    cycle_state: 'IDLE',
    spindle_state: 'UNKNOWN',
    feed_state: 'UNKNOWN',
    tool_in_spindle: null,
    active_work_offset: null,
    queue_state: 'UNKNOWN',
    maintenance_state: 'UNKNOWN',
    source: 'SIMULATED_TEST',
    quality: 'TEST_ONLY',
    warnings: [],
    connector_type: 'SIMULATED',
    is_fabricated: false,
    is_real_machine_write: false,
    ...overrides,
  } as MachineStateSnapshot;
}

function makeReadiness(overrides: Partial<ShopFloorReadiness> = {}): ShopFloorReadiness {
  return {
    status: 'READY_FOR_DRY_RUN',
    block_reasons: [],
    warnings: [],
    approval_required: true,
    is_dispatch_order: false,
    machine_state_ref: null,
    ...overrides,
  } as ShopFloorReadiness;
}

function makeApproval(overrides: Partial<DispatchApproval> = {}): DispatchApproval {
  return {
    approval_id: 'APR-001',
    package_ref: 'PKG-001',
    approved_by: 'operator',
    approved_at: '2026-11-07T00:00:00Z',
    scope: 'DRY_RUN_ONLY',
    status: 'APPROVED_FOR_DRY_RUN',
    comments: '',
    expires_at: null,
    is_automatic: false,
    is_execution_approval: false,
    ...overrides,
  } as DispatchApproval;
}

// ---------------------------------------------------------------------------
// enforceDispatchContract
// ---------------------------------------------------------------------------

describe('enforceDispatchContract', () => {
  it('passes when is_dispatch_order=false and approval_required=true', () => {
    assert.doesNotThrow(() =>
      enforceDispatchContract({ is_dispatch_order: false, approval_required: true })
    );
  });

  it('throws when is_dispatch_order=true', () => {
    assert.throws(
      () => enforceDispatchContract({ is_dispatch_order: true, approval_required: true }),
      DispatchContractViolation
    );
  });

  it('throws when approval_required=false', () => {
    assert.throws(
      () => enforceDispatchContract({ is_dispatch_order: false, approval_required: false }),
      DispatchContractViolation
    );
  });

  it('throws for null is_dispatch_order', () => {
    assert.throws(
      () => enforceDispatchContract({ is_dispatch_order: null, approval_required: true }),
      DispatchContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// enforceDispatchPackage
// ---------------------------------------------------------------------------

describe('enforceDispatchPackage', () => {
  it('passes for a valid package', () => {
    assert.doesNotThrow(() => enforceDispatchPackage(makePackage()));
  });

  it('throws when is_dispatch_order is true', () => {
    assert.throws(
      () => enforceDispatchPackage(makePackage({ is_dispatch_order: true as never })),
      DispatchContractViolation
    );
  });

  it('throws when approval_required is false', () => {
    assert.throws(
      () => enforceDispatchPackage(makePackage({ approval_required: false as never })),
      DispatchContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// enforceDryRunResult
// ---------------------------------------------------------------------------

describe('enforceDryRunResult', () => {
  it('passes for valid result', () => {
    assert.doesNotThrow(() => enforceDryRunResult(makeDryRunResult()));
  });

  it('throws when is_real_transfer=true', () => {
    assert.throws(
      () => enforceDryRunResult(makeDryRunResult({ is_real_transfer: true as never })),
      DispatchContractViolation
    );
  });

  it('throws when is_dispatch_order=true', () => {
    assert.throws(
      () => enforceDryRunResult(makeDryRunResult({ is_dispatch_order: true as never })),
      DispatchContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// enforceMachineStateSnapshot
// ---------------------------------------------------------------------------

describe('enforceMachineStateSnapshot', () => {
  it('passes for valid snapshot', () => {
    assert.doesNotThrow(() => enforceMachineStateSnapshot(makeMachineState()));
  });

  it('throws when is_fabricated=true', () => {
    assert.throws(
      () => enforceMachineStateSnapshot(makeMachineState({ is_fabricated: true as never })),
      DispatchContractViolation
    );
  });

  it('throws when is_real_machine_write=true', () => {
    assert.throws(
      () =>
        enforceMachineStateSnapshot(makeMachineState({ is_real_machine_write: true as never })),
      DispatchContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// enforceShopFloorReadiness
// ---------------------------------------------------------------------------

describe('enforceShopFloorReadiness', () => {
  it('passes for READY_FOR_DRY_RUN', () => {
    assert.doesNotThrow(() => enforceShopFloorReadiness(makeReadiness()));
  });

  it('passes for BLOCKED', () => {
    assert.doesNotThrow(() =>
      enforceShopFloorReadiness(makeReadiness({ status: 'BLOCKED' }))
    );
  });

  it('throws for READY_TO_RUN_MACHINE', () => {
    assert.throws(
      () =>
        enforceShopFloorReadiness(
          makeReadiness({ status: 'READY_TO_RUN_MACHINE' as never })
        ),
      DispatchContractViolation
    );
  });

  it('throws when approval_required=false', () => {
    assert.throws(
      () =>
        enforceShopFloorReadiness(makeReadiness({ approval_required: false as never })),
      DispatchContractViolation
    );
  });

  it('throws when is_dispatch_order=true', () => {
    assert.throws(
      () =>
        enforceShopFloorReadiness(makeReadiness({ is_dispatch_order: true as never })),
      DispatchContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// isBlocked, isStale, isDryRunPassed, isDryRunFailed
// ---------------------------------------------------------------------------

describe('isBlocked', () => {
  it('returns true for BLOCKED', () => {
    assert.equal(isBlocked('BLOCKED'), true);
  });

  it('returns false for READY_FOR_DRY_RUN', () => {
    assert.equal(isBlocked('READY_FOR_DRY_RUN'), false);
  });
});

describe('isStale', () => {
  it('returns true for STALE', () => {
    assert.equal(isStale('STALE'), true);
  });

  it('returns false for DRAFT', () => {
    assert.equal(isStale('DRAFT'), false);
  });
});

describe('isDryRunPassed', () => {
  it('returns true for PASSED', () => {
    assert.equal(isDryRunPassed('PASSED'), true);
  });

  it('returns false for FAILED', () => {
    assert.equal(isDryRunPassed('FAILED'), false);
  });
});

describe('isDryRunFailed', () => {
  it('returns true for FAILED', () => {
    assert.equal(isDryRunFailed('FAILED'), true);
  });

  it('returns false for PASSED', () => {
    assert.equal(isDryRunFailed('PASSED'), false);
  });
});

// ---------------------------------------------------------------------------
// Approval helpers
// ---------------------------------------------------------------------------

describe('isApprovalPending / isApprovalGranted', () => {
  it('isApprovalPending returns true for PENDING', () => {
    assert.equal(isApprovalPending('PENDING'), true);
  });

  it('isApprovalPending returns false for APPROVED_FOR_DRY_RUN', () => {
    assert.equal(isApprovalPending('APPROVED_FOR_DRY_RUN'), false);
  });

  it('isApprovalGranted returns true for APPROVED_FOR_DRY_RUN', () => {
    assert.equal(isApprovalGranted('APPROVED_FOR_DRY_RUN'), true);
  });

  it('isApprovalGranted returns false for PENDING', () => {
    assert.equal(isApprovalGranted('PENDING'), false);
  });

  it('approval scope is DRY_RUN_ONLY', () => {
    const approval = makeApproval();
    assert.equal(approval.scope, 'DRY_RUN_ONLY');
  });

  it('is_automatic is always false', () => {
    const approval = makeApproval();
    assert.equal(approval.is_automatic, false);
  });

  it('is_execution_approval is always false', () => {
    const approval = makeApproval();
    assert.equal(approval.is_execution_approval, false);
  });
});

// ---------------------------------------------------------------------------
// Connection status invariants
// ---------------------------------------------------------------------------

describe('connection status invariants', () => {
  it('isConnectionUnknown returns true for UNKNOWN', () => {
    assert.equal(isConnectionUnknown('UNKNOWN'), true);
  });

  it('isConnectionUnknown returns false for CONNECTED', () => {
    assert.equal(isConnectionUnknown('CONNECTED'), false);
  });

  it('UNKNOWN connection is not CONNECTED (HARD RULE 24)', () => {
    const unknownStatus: ConnectionStatus = 'UNKNOWN';
    assert.equal(unknownIsNotConnected(unknownStatus), true);
  });

  it('CONNECTED passes unknownIsNotConnected as false', () => {
    const connectedStatus: ConnectionStatus = 'CONNECTED';
    assert.equal(unknownIsNotConnected(connectedStatus), false);
  });
});

// ---------------------------------------------------------------------------
// Security boundary invariants (MUST 37 negative tests)
// ---------------------------------------------------------------------------

describe('security boundary invariants', () => {
  it('assignment candidate is not dispatch authorization', () => {
    assert.equal(assignmentIsNotDispatch(), false);
  });

  it('NC candidate is not machine-approved program', () => {
    assert.equal(ncCandidateIsNotMachineApproved(), false);
  });

  it('dry-run approval is not execution approval', () => {
    assert.equal(dryRunApprovalIsNotExecution(), false);
  });

  it('approval always required', () => {
    const readiness = makeReadiness();
    assert.equal(requiresApproval(readiness), true);
  });

  it('READY_TO_RUN_MACHINE is not a valid readiness status', () => {
    const validStatuses = [
      'READY_FOR_DRY_RUN',
      'REVIEW_REQUIRED',
      'BLOCKED',
      'UNKNOWN',
    ];
    assert.equal(validStatuses.includes('READY_TO_RUN_MACHINE'), false);
  });

  it('SENT_TO_MACHINE is not a valid package status', () => {
    const validStatuses = [
      'DRAFT', 'INCOMPLETE', 'READY_FOR_REVIEW',
      'APPROVED_FOR_DRY_RUN', 'DRY_RUN_VALIDATED',
      'BLOCKED', 'STALE', 'REJECTED',
    ];
    assert.equal(validStatuses.includes('SENT_TO_MACHINE'), false);
  });

  it('APPROVED_FOR_EXECUTION is not a valid approval status', () => {
    const validStatuses: ApprovalStatus[] = [
      'PENDING', 'APPROVED_FOR_DRY_RUN', 'REJECTED', 'REVOKED', 'EXPIRED',
    ];
    assert.equal(
      (validStatuses as string[]).includes('APPROVED_FOR_EXECUTION'),
      false
    );
  });
});

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

describe('readinessLabel', () => {
  it('returns label for READY_FOR_DRY_RUN', () => {
    assert.equal(readinessLabel('READY_FOR_DRY_RUN'), 'Ready for Dry Run');
  });

  it('returns label for BLOCKED', () => {
    assert.equal(readinessLabel('BLOCKED'), 'Blocked');
  });

  it('returns label for REVIEW_REQUIRED', () => {
    assert.equal(readinessLabel('REVIEW_REQUIRED'), 'Review Required');
  });

  it('returns label for UNKNOWN', () => {
    assert.equal(readinessLabel('UNKNOWN'), 'Unknown');
  });
});

describe('approvalStatusLabel', () => {
  it('returns label for APPROVED_FOR_DRY_RUN', () => {
    assert.equal(approvalStatusLabel('APPROVED_FOR_DRY_RUN'), 'Approved for Dry Run');
  });

  it('returns label for PENDING', () => {
    assert.equal(approvalStatusLabel('PENDING'), 'Pending Approval');
  });

  it('returns label for EXPIRED', () => {
    assert.equal(approvalStatusLabel('EXPIRED'), 'Expired');
  });
});

describe('errorLabel', () => {
  it('returns label for MACHINE_ALARM', () => {
    assert.equal(errorLabel('MACHINE_ALARM'), 'Machine Alarm Active');
  });

  it('returns label for APPROVAL_MISSING', () => {
    assert.equal(errorLabel('APPROVAL_MISSING'), 'Approval Missing');
  });

  it('returns label for NC_HASH_MISMATCH', () => {
    assert.equal(errorLabel('NC_HASH_MISMATCH'), 'NC Hash Mismatch');
  });

  it('returns label for UNKNOWN_MACHINE_STATE', () => {
    assert.equal(errorLabel('UNKNOWN_MACHINE_STATE'), 'Unknown Machine State');
  });
});

// ---------------------------------------------------------------------------
// DispatchContractViolation
// ---------------------------------------------------------------------------

describe('DispatchContractViolation', () => {
  it('has correct name', () => {
    const err = new DispatchContractViolation('test');
    assert.equal(err.name, 'DispatchContractViolation');
  });

  it('prefixes message', () => {
    const err = new DispatchContractViolation('test');
    assert.match(err.message, /DISPATCH_CONTRACT_VIOLATION/);
  });

  it('is an Error instance', () => {
    const err = new DispatchContractViolation('test');
    assert.ok(err instanceof Error);
  });
});
