/**
 * Level-14 Shop Floor Integration and Safe Dispatch Foundation — service layer.
 *
 * Contract enforcement:
 * - is_dispatch_order must always be false
 * - approval_required must always be true
 * - is_real_transfer must always be false
 * - READY_TO_RUN_MACHINE must never appear as a readiness status
 */

import type {
  ApprovalResponse,
  ApprovalStatus,
  ConnectionStatus,
  CreatePackageResponse,
  DispatchAuditEvent,
  DispatchErrorCode,
  DispatchPackage,
  DispatchPackageStatus,
  DryRunDispatchResult,
  DryRunResponse,
  DryRunStatus,
  MachineStateResponse,
  MachineStateSnapshot,
  ShopFloorReadiness,
  ShopFloorReadinessStatus,
} from '../types/dispatch.ts';

// ---------------------------------------------------------------------------
// Contract violation error
// ---------------------------------------------------------------------------

export class DispatchContractViolation extends Error {
  constructor(message: string) {
    super(`DISPATCH_CONTRACT_VIOLATION: ${message}`);
    this.name = 'DispatchContractViolation';
  }
}

// ---------------------------------------------------------------------------
// Contract enforcement
// ---------------------------------------------------------------------------

export function enforceDispatchContract(response: {
  is_dispatch_order: unknown;
  approval_required: unknown;
}): void {
  if (response.is_dispatch_order !== false) {
    throw new DispatchContractViolation(
      `is_dispatch_order must be false, got: ${String(response.is_dispatch_order)}`
    );
  }
  if (response.approval_required !== true) {
    throw new DispatchContractViolation(
      `approval_required must be true, got: ${String(response.approval_required)}`
    );
  }
}

export function enforceDispatchPackage(pkg: DispatchPackage): void {
  if (pkg.is_dispatch_order !== false) {
    throw new DispatchContractViolation(
      `DispatchPackage.is_dispatch_order must be false`
    );
  }
  if (pkg.approval_required !== true) {
    throw new DispatchContractViolation(
      `DispatchPackage.approval_required must be true`
    );
  }
}

export function enforceDryRunResult(result: DryRunDispatchResult): void {
  if (result.is_real_transfer !== false) {
    throw new DispatchContractViolation(
      `DryRunDispatchResult.is_real_transfer must be false`
    );
  }
  if (result.is_dispatch_order !== false) {
    throw new DispatchContractViolation(
      `DryRunDispatchResult.is_dispatch_order must be false`
    );
  }
}

export function enforceMachineStateSnapshot(state: MachineStateSnapshot): void {
  if (state.is_fabricated !== false) {
    throw new DispatchContractViolation(
      `MachineStateSnapshot.is_fabricated must be false`
    );
  }
  if (state.is_real_machine_write !== false) {
    throw new DispatchContractViolation(
      `MachineStateSnapshot.is_real_machine_write must be false`
    );
  }
}

export function enforceShopFloorReadiness(readiness: ShopFloorReadiness): void {
  if (readiness.status === ('READY_TO_RUN_MACHINE' as ShopFloorReadinessStatus)) {
    throw new DispatchContractViolation(
      `ShopFloorReadiness.status must never be READY_TO_RUN_MACHINE`
    );
  }
  if (readiness.approval_required !== true) {
    throw new DispatchContractViolation(
      `ShopFloorReadiness.approval_required must be true`
    );
  }
  if (readiness.is_dispatch_order !== false) {
    throw new DispatchContractViolation(
      `ShopFloorReadiness.is_dispatch_order must be false`
    );
  }
}

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------

export function isBlocked(status: ShopFloorReadinessStatus | DispatchPackageStatus): boolean {
  return status === 'BLOCKED';
}

export function isStale(status: DispatchPackageStatus | string): boolean {
  return status === 'STALE';
}

export function isDryRunPassed(status: DryRunStatus): boolean {
  return status === 'PASSED';
}

export function isDryRunFailed(status: DryRunStatus): boolean {
  return status === 'FAILED';
}

export function isApprovalPending(status: ApprovalStatus): boolean {
  return status === 'PENDING';
}

export function isApprovalGranted(status: ApprovalStatus): boolean {
  return status === 'APPROVED_FOR_DRY_RUN';
}

export function isConnectionUnknown(status: ConnectionStatus): boolean {
  return status === 'UNKNOWN';
}

export function requiresApproval(_readiness: ShopFloorReadiness): true {
  return true;
}

// ---------------------------------------------------------------------------
// Invariant checks
// ---------------------------------------------------------------------------

/** HARD RULE: UNKNOWN connection state !== CONNECTED */
export function unknownIsNotConnected(status: ConnectionStatus): boolean {
  return status !== 'CONNECTED';
}

/** HARD RULE: Assignment candidate !== dispatch authorization */
export function assignmentIsNotDispatch(): false {
  return false;
}

/** HARD RULE: NC candidate !== machine-approved program */
export function ncCandidateIsNotMachineApproved(): false {
  return false;
}

/** HARD RULE: Approved dry-run !== execution approval */
export function dryRunApprovalIsNotExecution(): false {
  return false;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export function readinessLabel(status: ShopFloorReadinessStatus): string {
  const labels: Record<ShopFloorReadinessStatus, string> = {
    READY_FOR_DRY_RUN: 'Ready for Dry Run',
    REVIEW_REQUIRED: 'Review Required',
    BLOCKED: 'Blocked',
    UNKNOWN: 'Unknown',
  };
  return labels[status] ?? status;
}

export function approvalStatusLabel(status: ApprovalStatus): string {
  const labels: Record<ApprovalStatus, string> = {
    PENDING: 'Pending Approval',
    APPROVED_FOR_DRY_RUN: 'Approved for Dry Run',
    REJECTED: 'Rejected',
    REVOKED: 'Revoked',
    EXPIRED: 'Expired',
  };
  return labels[status] ?? status;
}

export function errorLabel(code: DispatchErrorCode): string {
  const labels: Record<DispatchErrorCode, string> = {
    MACHINE_OFFLINE: 'Machine Offline',
    MACHINE_BUSY: 'Machine Busy',
    MACHINE_ALARM: 'Machine Alarm Active',
    PACKAGE_STALE: 'Package Stale',
    NC_HASH_MISMATCH: 'NC Hash Mismatch',
    ASSIGNMENT_MISMATCH: 'Assignment Mismatch',
    TOOL_NOT_READY: 'Tool Not Ready',
    FIXTURE_NOT_READY: 'Fixture Not Ready',
    APPROVAL_MISSING: 'Approval Missing',
    APPROVAL_EXPIRED: 'Approval Expired',
    UNVERIFIED_TOOLPATH: 'Toolpath Not Verified',
    INVALID_NC: 'Invalid NC Candidate',
    UNKNOWN_MACHINE_STATE: 'Unknown Machine State',
    MACHINE_IDENTITY_MISMATCH: 'Machine Identity Mismatch',
    SETUP_INCOMPLETE: 'Setup Incomplete',
    CONNECTOR_READ_ONLY_VIOLATION: 'Connector Write Attempt Blocked',
  };
  return labels[code] ?? code;
}

// ---------------------------------------------------------------------------
// API client functions
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  url: string,
  options: RequestInit = {}
): Promise<T> {
  const resp = await fetch(url, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });
  if (!resp.ok) {
    throw new Error(`API error ${resp.status}: ${url}`);
  }
  return resp.json() as Promise<T>;
}

export async function createDispatchPackage(
  token: string,
  body: object
): Promise<CreatePackageResponse> {
  const result = await apiFetch<CreatePackageResponse>('/api/dispatch/create-package', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  enforceDispatchContract(result);
  enforceDispatchPackage(result.package);
  return result;
}

export async function runDryRun(
  token: string,
  body: object
): Promise<DryRunResponse> {
  const result = await apiFetch<DryRunResponse>('/api/dispatch/run-dry-run', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  enforceDispatchContract(result);
  enforceDryRunResult(result.dry_run_result);
  return result;
}

export async function getMachineState(
  token: string,
  machineId: string
): Promise<MachineStateResponse> {
  const result = await apiFetch<MachineStateResponse>(
    `/api/dispatch/machine-state/${machineId}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  enforceDispatchContract(result);
  enforceMachineStateSnapshot(result.machine_state);
  return result;
}

export async function approveForDryRun(
  token: string,
  body: object
): Promise<ApprovalResponse> {
  const result = await apiFetch<ApprovalResponse>('/api/dispatch/approve-dry-run', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });
  enforceDispatchContract(result);
  return result;
}

export async function getAuditEvents(token: string): Promise<DispatchAuditEvent[]> {
  const result = await apiFetch<{ audit_event_types: string[] }>(
    '/api/dispatch/audit-events',
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return result.audit_event_types.map((t, i) => ({
    event_id: `schema-${i}`,
    event_type: t as DispatchAuditEvent['event_type'],
    timestamp: '',
    actor: 'schema',
    job_ref: null,
    machine_ref: null,
    package_ref: null,
    result: 'SCHEMA',
    reason: '',
    reference_hash: null,
  }));
}
