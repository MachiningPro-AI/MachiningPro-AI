/**
 * Level-11 Verification service.
 *
 * enforceSimulationContract: validation gate that throws if the response
 * violates the Level-11 invariants.
 *
 * Invariants (non-negotiable):
 *   is_verified must NEVER be true unless verification_state = VERIFIED
 *   COMPLETED simulation != VERIFIED toolpath
 *   NOT_PERFORMED / INSUFFICIENT_DATA / PARTIAL / ERROR != PASS
 */

import type {
  SimulationRequest,
  SimulationResult,
  VerificationState,
  VerificationStatus,
} from '../types/verification';

const API_BASE = '/api/verification';

export class VerificationContractViolation extends Error {
  constructor(message: string) {
    super(`VERIFICATION_CONTRACT_VIOLATION: ${message}`);
    this.name = 'VerificationContractViolation';
  }
}

const NON_PASS_STATUSES: VerificationStatus[] = [
  'NOT_PERFORMED',
  'INSUFFICIENT_DATA',
  'PARTIAL',
  'ERROR',
];

const VERIFIED_STATE: VerificationState = 'VERIFIED';

export function enforceSimulationContract(
  result: SimulationResult,
  endpoint: string,
): void {
  if (result.is_verified && result.verification_state !== VERIFIED_STATE) {
    throw new VerificationContractViolation(
      `${endpoint}: is_verified=true but verification_state=${result.verification_state}`,
    );
  }

  if (result.is_verified) {
    const hasNonPass = Object.values(result.checks).some((check) =>
      NON_PASS_STATUSES.includes(check.status),
    );
    if (hasNonPass) {
      throw new VerificationContractViolation(
        `${endpoint}: is_verified=true but some checks are not PASS`,
      );
    }
  }

  if (result.summary && result.summary.is_verified !== result.is_verified) {
    throw new VerificationContractViolation(
      `${endpoint}: summary.is_verified inconsistent with top-level is_verified`,
    );
  }
}

async function postSimulation(
  endpoint: string,
  request: SimulationRequest,
  authToken: string,
): Promise<SimulationResult> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${authToken}`,
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`Verification API error ${response.status}: ${text}`);
  }

  const data: SimulationResult = await response.json();
  enforceSimulationContract(data, endpoint);
  return data;
}

export function requestSimulation(
  request: SimulationRequest,
  authToken: string,
): Promise<SimulationResult> {
  return postSimulation('/simulate', request, authToken);
}

export function requestGeometryOnlySimulation(
  request: SimulationRequest,
  authToken: string,
): Promise<SimulationResult> {
  return postSimulation('/simulate/geometry-only', request, authToken);
}

export function isVerificationPassing(result: SimulationResult): boolean {
  return result.is_verified && result.verification_state === 'VERIFIED';
}

export function countChecks(result: SimulationResult) {
  const checks = Object.values(result.checks);
  return {
    pass: checks.filter((c) => c.status === 'PASS').length,
    fail: checks.filter((c) => c.status === 'FAIL').length,
    not_performed: checks.filter((c) => c.status === 'NOT_PERFORMED').length,
    insufficient_data: checks.filter((c) => c.status === 'INSUFFICIENT_DATA').length,
    partial: checks.filter((c) => c.status === 'PARTIAL').length,
  };
}
