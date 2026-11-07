/**
 * Level-13 Machine Scheduling and Job Assignment — frontend service.
 *
 * Contract invariants (enforced client-side):
 *   is_dispatch_order must ALWAYS be false
 *   approval_required must ALWAYS be true
 *
 * NO_CNC_DISPATCH=YES
 * NO_SEND_NC=YES
 * NO_START_MACHINE=YES
 */

import type {
  AssignmentResponse,
  EvaluateMachinesResponse,
  JobAssignmentCandidate,
  ReadinessResponse,
  ScheduleCandidate,
  ScheduleCandidateResponse,
} from '../types/scheduling.ts';

// ---------------------------------------------------------------------------
// Contract error
// ---------------------------------------------------------------------------

export class SchedulingContractViolation extends Error {
  constructor(message: string) {
    super(`SCHEDULING_CONTRACT_VIOLATION: ${message}`);
    this.name = 'SchedulingContractViolation';
  }
}

// ---------------------------------------------------------------------------
// Contract enforcement
// ---------------------------------------------------------------------------

export function enforceSchedulingContract(response: {
  is_dispatch_order: unknown;
  approval_required: unknown;
}): void {
  if (response.is_dispatch_order !== false) {
    throw new SchedulingContractViolation(
      `is_dispatch_order must be false, got: ${JSON.stringify(response.is_dispatch_order)}`
    );
  }
  if (response.approval_required !== true) {
    throw new SchedulingContractViolation(
      `approval_required must be true, got: ${JSON.stringify(response.approval_required)}`
    );
  }
}

export function enforceScheduleCandidate(candidate: ScheduleCandidate): void {
  if (candidate.is_dispatch_order !== false) {
    throw new SchedulingContractViolation(
      `ScheduleCandidate.is_dispatch_order must be false`
    );
  }
  if (candidate.approval_required !== true) {
    throw new SchedulingContractViolation(
      `ScheduleCandidate.approval_required must be true`
    );
  }
}

export function enforceAssignmentCandidate(candidate: JobAssignmentCandidate): void {
  if (candidate.is_dispatch_order !== false) {
    throw new SchedulingContractViolation(
      `JobAssignmentCandidate.is_dispatch_order must be false`
    );
  }
  if (candidate.approval_required !== true) {
    throw new SchedulingContractViolation(
      `JobAssignmentCandidate.approval_required must be true`
    );
  }
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

export function isBlocked(status: string): boolean {
  return (
    status === 'SCHEDULING_BLOCKED' ||
    status === 'DISPATCH_BLOCKED' ||
    status === 'BLOCKED' ||
    status === 'INELIGIBLE'
  );
}

export function isCandidate(status: string): boolean {
  return (
    status === 'SCHEDULED_CANDIDATE' ||
    status === 'ASSIGNMENT_REVIEW_REQUIRED'
  );
}

export function isUnknown(status: string): boolean {
  return status === 'UNKNOWN';
}

export function isReviewRequired(status: string): boolean {
  return (
    status === 'REVIEW_REQUIRED' ||
    status === 'ASSIGNMENT_REVIEW_REQUIRED'
  );
}

export function requiresApproval(candidate: { approval_required: unknown }): boolean {
  return candidate.approval_required === true;
}

// ---------------------------------------------------------------------------
// Algorithm display helpers
// ---------------------------------------------------------------------------

export function algorithmLabel(algorithm: string): string {
  const labels: Record<string, string> = {
    FIFO: 'First In First Out',
    EDD: 'Earliest Due Date',
    SPT: 'Shortest Processing Time',
    PRIORITY_FIRST: 'Priority First',
  };
  return labels[algorithm] ?? algorithm;
}

export function eligibilityLabel(result: string): string {
  const labels: Record<string, string> = {
    ELIGIBLE: 'Eligible',
    PARTIALLY_ELIGIBLE: 'Partially Eligible',
    INELIGIBLE: 'Ineligible',
    UNKNOWN: 'Unknown',
  };
  return labels[result] ?? result;
}

// ---------------------------------------------------------------------------
// API client functions — parse and enforce contract on every response
// ---------------------------------------------------------------------------

async function fetchJson<T>(url: string, init: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(`HTTP ${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

function authHeaders(token: string): HeadersInit {
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  };
}

export async function evaluateMachines(
  token: string,
  payload: object
): Promise<EvaluateMachinesResponse> {
  const data = await fetchJson<EvaluateMachinesResponse>(
    '/api/scheduling/evaluate-machines',
    { method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload) }
  );
  enforceSchedulingContract(data);
  return data;
}

export async function createScheduleCandidate(
  token: string,
  payload: object
): Promise<ScheduleCandidateResponse> {
  const data = await fetchJson<ScheduleCandidateResponse>(
    '/api/scheduling/create-schedule-candidate',
    { method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload) }
  );
  enforceSchedulingContract(data);
  enforceScheduleCandidate(data.schedule_candidate);
  return data;
}

export async function evaluateAssignment(
  token: string,
  payload: object
): Promise<AssignmentResponse> {
  const data = await fetchJson<AssignmentResponse>(
    '/api/scheduling/evaluate-assignment',
    { method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload) }
  );
  enforceSchedulingContract(data);
  enforceAssignmentCandidate(data.assignment_candidate);
  return data;
}

export async function checkReadiness(
  token: string,
  payload: object
): Promise<ReadinessResponse> {
  const data = await fetchJson<ReadinessResponse>(
    '/api/scheduling/check-readiness',
    { method: 'POST', headers: authHeaders(token), body: JSON.stringify(payload) }
  );
  enforceSchedulingContract(data);
  return data;
}
