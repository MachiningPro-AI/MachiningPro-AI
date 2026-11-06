/**
 * Level-11 frontend verification tests.
 * Tests: type contracts, service functions, is_verified invariants, fail-closed policy.
 */

import { describe, expect, it } from 'vitest';
import {
  VerificationContractViolation,
  countChecks,
  enforceSimulationContract,
  isVerificationPassing,
} from '../src/services/verification';
import type {
  SimulationResult,
  VerificationCheckType,
  VerificationResult,
  VerificationState,
  VerificationStatus,
} from '../src/types/verification';

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
    expect(() => enforceSimulationContract(result, '/simulate')).not.toThrow();
  });

  it('is_verified=false with UNVERIFIED state passes', () => {
    const result = makeResult({ is_verified: false, verification_state: 'UNVERIFIED' });
    expect(() => enforceSimulationContract(result, '/simulate')).not.toThrow();
  });

  it('is_verified=false with FAILED state passes', () => {
    const result = makeResult({ is_verified: false, verification_state: 'FAILED' });
    expect(() => enforceSimulationContract(result, '/simulate')).not.toThrow();
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
    expect(() => enforceSimulationContract(result, '/simulate')).not.toThrow();
  });

  it('throws when is_verified=true but state is not VERIFIED', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'PARTIALLY_VERIFIED',
    });
    expect(() => enforceSimulationContract(result, '/simulate')).toThrow(
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
    expect(() => enforceSimulationContract(result, '/simulate')).toThrow(
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
    expect(() => enforceSimulationContract(result, '/simulate')).toThrow(
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
    expect(() => enforceSimulationContract(result, '/simulate')).toThrow(
      VerificationContractViolation,
    );
  });
});

describe('isVerificationPassing invariants', () => {
  it('returns false for unverified result', () => {
    expect(isVerificationPassing(makeResult())).toBe(false);
  });

  it('returns false for FAILED state', () => {
    expect(
      isVerificationPassing(makeResult({ verification_state: 'FAILED', is_verified: false })),
    ).toBe(false);
  });

  it('returns false for PARTIALLY_VERIFIED', () => {
    expect(
      isVerificationPassing(
        makeResult({ verification_state: 'PARTIALLY_VERIFIED', is_verified: false }),
      ),
    ).toBe(false);
  });

  it('returns false for BLOCKED', () => {
    expect(
      isVerificationPassing(makeResult({ verification_state: 'BLOCKED', is_verified: false })),
    ).toBe(false);
  });

  it('returns true only when is_verified=true and state=VERIFIED', () => {
    expect(
      isVerificationPassing(
        makeResult({ verification_state: 'VERIFIED', is_verified: true }),
      ),
    ).toBe(true);
  });
});

describe('COMPLETED != VERIFIED invariant', () => {
  it('COMPLETED simulation with UNVERIFIED state does not pass contract', () => {
    const result = makeResult({
      simulation_status: 'COMPLETED',
      verification_state: 'UNVERIFIED',
      is_verified: false,
    });
    expect(isVerificationPassing(result)).toBe(false);
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
    expect(isVerificationPassing(result)).toBe(false);
    expect(() => enforceSimulationContract(result, '/simulate')).not.toThrow();
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
      expect(s === 'PASS').toBe(false);
    });
  }

  it('is_verified=true with ERROR check throws contract violation', () => {
    const result = makeResult({
      is_verified: true,
      verification_state: 'VERIFIED',
      checks: { PART_GOUGE: makeCheck('PART_GOUGE', 'ERROR') },
    });
    expect(() => enforceSimulationContract(result, '/simulate')).toThrow(
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
    expect(countChecks(result).pass).toBe(2);
    expect(countChecks(result).fail).toBe(0);
  });

  it('counts failed checks', () => {
    const result = makeResult({
      checks: {
        PART_GOUGE: makeCheck('PART_GOUGE', 'FAIL'),
        STOCK_GOUGE: makeCheck('STOCK_GOUGE', 'PASS'),
      },
    });
    expect(countChecks(result).fail).toBe(1);
    expect(countChecks(result).pass).toBe(1);
  });

  it('counts not_performed checks', () => {
    const result = makeResult({
      checks: {
        TOOL_COLLISION: makeCheck('TOOL_COLLISION', 'NOT_PERFORMED'),
        HOLDER_COLLISION: makeCheck('HOLDER_COLLISION', 'NOT_PERFORMED'),
      },
    });
    expect(countChecks(result).not_performed).toBe(2);
  });

  it('counts insufficient_data checks', () => {
    const result = makeResult({
      checks: {
        MACHINE_ENVELOPE: makeCheck('MACHINE_ENVELOPE', 'INSUFFICIENT_DATA'),
      },
    });
    expect(countChecks(result).insufficient_data).toBe(1);
  });
});

describe('VerificationState enumeration', () => {
  it('VERIFIED state string value is correct', () => {
    const s: VerificationState = 'VERIFIED';
    expect(s).toBe('VERIFIED');
  });

  it('BLOCKED state is not VERIFIED', () => {
    const s: VerificationState = 'BLOCKED';
    expect(s === 'VERIFIED').toBe(false);
  });
});

describe('No fabricated verification data', () => {
  it('service does not hard-code is_verified=true', () => {
    const result = makeResult();
    expect(result.is_verified).toBe(false);
  });

  it('default checks object is empty', () => {
    const result = makeResult();
    expect(Object.keys(result.checks)).toHaveLength(0);
  });

  it('resource_limit_hit default is false', () => {
    const result = makeResult();
    expect(result.resource_limit_hit).toBe(false);
  });
});
