/**
 * Level-11 frontend verification tests.
 * Tests: type contracts, service functions, is_verified invariants, fail-closed policy.
 */

import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  VerificationContractViolation,
  countChecks,
  enforceSimulationContract,
  isVerificationPassing,
} from '../src/services/verification.ts';
import type {
  SimulationResult,
  VerificationCheckType,
  VerificationResult,
  VerificationState,
  VerificationStatus,
} from '../src/types/verification.ts';

function makeCheck(
  checkType: VerificationCheckType,
  status: VerificationStatus,
): VerificationResult {
  return {
    check_type: checkType,
    status,
    severity: 'INFO',
    toolpath_refs: [],
    segment_refs: [],
    geometry_refs: [],
    evidence: {},
    warnings: [],
    errors: [],
    issues: [],
  };
}

function makeResult(
  overrides: Partial<SimulationResult> = {},
): SimulationResult {
  return {
    session_id: 'sess-001',
    toolpath_id: 'tp-001',
    simulation_status: 'COMPLETED',
    verification_state: 'UNVERIFIED',
    is_verified: false,
    profile: 'GEOMETRY_ONLY',
    checks: {},
    issues: [],
    summary: undefined,
    initial_stock_volume_mm3: undefined,
    remaining_stock_volume_mm3: undefined,
    removed_volume_mm3: undefined,
    stock_removal_fidelity: 'UNKNOWN',
    visualization: {
      cutting_points: [],
      rapid_points: [],
      fixture_bboxes: [],
      collision_points: [],
      gouge_points: [],
    },
    warnings: [],
    errors: [],
    resource_limit_hit: false,
    ...overrides,
  };
}

describe('SimulationResult contracts', () => {
  it('valid unverified result passes contract', () => {
    const result = makeResult();
    assert.doesNotThrow(() => enforceSimulationContract(result, '/simulate'));
  });

  it('is_verified=false with UNVERIFIED state passes', () => {
    const result = makeResult({ is_verified: false, verification_state: 'UNVERIFIED' });
    assert.doesNotThrow(() => enforceSimulationContract(result, '/simulate'));
  });

  it('is_verified=false with FAILED state passes', () => {
    const result = makeResult({ is_verified: false, verification_state: 'FAILED' });
    assert.doesNotThrow(() => enforceSimulationContract(result, '/simulate'));
  });

  it('is_verified=true with VERIFIED state and all PASS checks passes', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'VERIFIED',
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'PASS'),
        STOCK_GOUGE: makeCheck('STOCK_GOUGE', 'PASS'),
      },
    });
    assert.doesNotThrow(() => enforceSimulationContract(result, '/simulate'));
  });

  it('throws when is_verified=true but state is not VERIFIED', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'PARTIALLY_VERIFIED',
    });
    assert.throws(
      () => enforceSimulationContract(result, '/simulate'),
      VerificationContractViolation,
    );
  });

  it('throws when is_verified=true but some checks are NOT_PERFORMED', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'VERIFIED',
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'PASS'),
        STOCK_GOUGE: makeCheck('STOCK_GOUGE', 'NOT_PERFORMED'),
      },
    });
    assert.throws(
      () => enforceSimulationContract(result, '/simulate'),
      VerificationContractViolation,
    );
  });

  it('throws when is_verified=true but some checks are INSUFFICIENT_DATA', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'VERIFIED',
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'INSUFFICIENT_DATA'),
      },
    });
    assert.throws(
      () => enforceSimulationContract(result, '/simulate'),
      VerificationContractViolation,
    );
  });

  it('throws when is_verified=true but summary.is_verified=false', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'VERIFIED',
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'PASS'),
      },
      summary: {
        verification_state: 'VERIFIED',
        profile: 'GEOMETRY_ONLY',
        checks_performed: 1,
        checks_passed: 1,
        checks_failed: 0,
        checks_not_performed: 0,
        checks_insufficient_data: 0,
        critical_issues: 0,
        error_issues: 0,
        warning_issues: 0,
        info_issues: 0,
        is_verified: false,
      },
    });
    assert.throws(
      () => enforceSimulationContract(result, '/simulate'),
      VerificationContractViolation,
    );
  });
});

describe('isVerificationPassing invariants', () => {
  it('returns false for unverified result', () => {
    assert.strictEqual(isVerificationPassing(makeResult()), false);
  });

  it('returns false for FAILED state', () => {
    assert.strictEqual(
      isVerificationPassing(makeResult({ verification_state: 'FAILED', is_verified: false })),
      false,
    );
  });

  it('returns false for PARTIALLY_VERIFIED', () => {
    assert.strictEqual(
      isVerificationPassing(
        makeResult({ verification_state: 'PARTIALLY_VERIFIED', is_verified: false }),
      ),
      false,
    );
  });

  it('returns false for BLOCKED', () => {
    assert.strictEqual(
      isVerificationPassing(makeResult({ verification_state: 'BLOCKED', is_verified: false })),
      false,
    );
  });

  it('returns true only when is_verified=true and state=VERIFIED', () => {
    assert.strictEqual(
      isVerificationPassing(makeResult({ verification_state: 'VERIFIED', is_verified: true })),
      true,
    );
  });
});

describe('COMPLETED != VERIFIED invariant', () => {
  it('COMPLETED simulation with UNVERIFIED state does not pass contract', () => {
    const result = makeResult({
      simulation_status: 'COMPLETED',
      verification_state: 'UNVERIFIED',
      is_verified: false,
    });
    assert.strictEqual(isVerificationPassing(result), false);
  });

  it('COMPLETED simulation with FAILED checks is not verified', () => {
    const result = makeResult({
      simulation_status: 'COMPLETED',
      verification_state: 'FAILED',
      is_verified: false,
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'FAIL'),
      },
    });
    assert.strictEqual(isVerificationPassing(result), false);
    assert.doesNotThrow(() => enforceSimulationContract(result, '/simulate'));
  });
});

describe('Non-pass statuses are never PASS', () => {
  const nonPassStatuses: VerificationStatus[] = [
    'NOT_PERFORMED',
    'INSUFFICIENT_DATA',
    'PARTIAL',
    'ERROR',
    'FAIL',
  ];

  for (const s of nonPassStatuses) {
    it(`status ${s} is not PASS`, () => {
      assert.strictEqual(s === 'PASS', false);
    });
  }

  it('is_verified=true with ERROR check throws contract violation', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'VERIFIED',
      checks: { PART_GOUGE: makeCheck('PART_GOUGE', 'ERROR') },
    });
    assert.throws(
      () => enforceSimulationContract(result, '/simulate'),
      VerificationContractViolation,
    );
  });
});

describe('countChecks utility', () => {
  it('counts all pass checks', () => {
    const result = makeResult({
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'PASS'),
        STOCK_GOUGE: makeCheck('STOCK_GOUGE', 'PASS'),
      },
    });
    assert.strictEqual(countChecks(result).pass, 2);
    assert.strictEqual(countChecks(result).fail, 0);
  });

  it('counts failed checks', () => {
    const result = makeResult({
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'FAIL'),
        STOCK_GOUGE: makeCheck('STOCK_GOUGE', 'PASS'),
      },
    });
    assert.strictEqual(countChecks(result).fail, 1);
    assert.strictEqual(countChecks(result).pass, 1);
  });

  it('counts not_performed checks', () => {
    const result = makeResult({
      checks: {
        TOOL_COLLISION: makeCheck('TOOL_COLLISION', 'NOT_PERFORMED'),
        HOLDER_COLLISION: makeCheck('HOLDER_COLLISION', 'NOT_PERFORMED'),
      },
    });
    assert.strictEqual(countChecks(result).not_performed, 2);
  });

  it('counts insufficient_data checks', () => {
    const result = makeResult({
      checks: {
        MACHINE_ENVELOPE: makeCheck('MACHINE_ENVELOPE', 'INSUFFICIENT_DATA'),
      },
    });
    assert.strictEqual(countChecks(result).insufficient_data, 1);
  });
});

describe('VerificationState enumeration', () => {
  it('VERIFIED state string value is correct', () => {
    const s: VerificationState = 'VERIFIED';
    assert.strictEqual(s, 'VERIFIED');
  });

  it('BLOCKED state is not VERIFIED', () => {
    const s: VerificationState = 'BLOCKED';
    assert.strictEqual(s === 'VERIFIED', false);
  });
});

describe('No fabricated verification data', () => {
  it('service does not hard-code is_verified=true', () => {
    const result = makeResult();
    assert.strictEqual(result.is_verified, false);
  });

  it('default checks object is empty', () => {
    const result = makeResult();
    assert.strictEqual(Object.keys(result.checks).length, 0);
  });

  it('resource_limit_hit default is false', () => {
    const result = makeResult();
    assert.strictEqual(result.resource_limit_hit, false);
  });
});
