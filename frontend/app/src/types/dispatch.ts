/**
 * Level-14 Shop Floor Integration and Safe Dispatch Foundation — TypeScript types.
 *
 * NO_REAL_MACHINE_WRITE=YES
 * NO_AUTO_DISPATCH=YES
 * APPROVAL_REQUIRED=YES
 * DRY_RUN_ONLY=YES
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type DispatchPackageStatus =
  | 'DRAFT'
  | 'INCOMPLETE'
  | 'READY_FOR_REVIEW'
  | 'APPROVED_FOR_DRY_RUN'
  | 'DRY_RUN_VALIDATED'
  | 'BLOCKED'
  | 'STALE'
  | 'REJECTED';
// NOT PRESENT: SENT_TO_MACHINE, RUNNING

export type ApprovalStatus =
  | 'PENDING'
  | 'APPROVED_FOR_DRY_RUN'
  | 'REJECTED'
  | 'REVOKED'
  | 'EXPIRED';
// NOT PRESENT: APPROVED_FOR_EXECUTION

export type ConnectionStatus = 'CONNECTED' | 'DISCONNECTED' | 'UNKNOWN';
// HARD RULE: UNKNOWN !== CONNECTED

export type MachineMode = 'AUTO' | 'MDI' | 'JOG' | 'EDIT' | 'MANUAL' | 'UNKNOWN';

export type AlarmState = 'NO_ALARM' | 'ALARM' | 'WARNING' | 'UNKNOWN';

export type CycleState = 'IDLE' | 'RUNNING' | 'PAUSED' | 'FINISHED' | 'UNKNOWN';

export type ShopFloorReadinessStatus =
  | 'READY_FOR_DRY_RUN'
  | 'REVIEW_REQUIRED'
  | 'BLOCKED'
  | 'UNKNOWN';
// NOT PRESENT: READY_TO_RUN_MACHINE

export type DryRunStatus = 'NOT_STARTED' | 'PASSED' | 'FAILED' | 'BLOCKED';

export type DispatchAuditEventType =
  | 'PACKAGE_CREATED'
  | 'PACKAGE_UPDATED'
  | 'APPROVAL_REQUESTED'
  | 'APPROVAL_GRANTED_DRY_RUN'
  | 'APPROVAL_REJECTED'
  | 'DRY_RUN_STARTED'
  | 'DRY_RUN_PASSED'
  | 'DRY_RUN_FAILED'
  | 'PACKAGE_STALE'
  | 'MACHINE_STATE_READ';

export type DispatchErrorCode =
  | 'MACHINE_OFFLINE'
  | 'MACHINE_BUSY'
  | 'MACHINE_ALARM'
  | 'PACKAGE_STALE'
  | 'NC_HASH_MISMATCH'
  | 'ASSIGNMENT_MISMATCH'
  | 'TOOL_NOT_READY'
  | 'FIXTURE_NOT_READY'
  | 'APPROVAL_MISSING'
  | 'APPROVAL_EXPIRED'
  | 'UNVERIFIED_TOOLPATH'
  | 'INVALID_NC'
  | 'UNKNOWN_MACHINE_STATE'
  | 'MACHINE_IDENTITY_MISMATCH'
  | 'SETUP_INCOMPLETE'
  | 'CONNECTOR_READ_ONLY_VIOLATION';

export type SimulatedMachineState =
  | 'IDLE'
  | 'BUSY'
  | 'ALARM'
  | 'MAINTENANCE'
  | 'OFFLINE'
  | 'READY_FOR_TEST_DISPATCH';

export type ConnectorType =
  | 'SIMULATED'
  | 'OPC_UA_READ_ONLY'
  | 'MTCONNECT_READ_ONLY'
  | 'VENDOR_API_READ_ONLY'
  | 'MES_READ_ONLY'
  | 'UNKNOWN';

export type PackageIntegrityStatus = 'INTACT' | 'STALE' | 'INCOMPLETE' | 'UNKNOWN';

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export interface ConnectorCapabilities {
  READ_MACHINE_STATE: boolean;
  READ_ALARMS: boolean;
  READ_PROGRAM_METADATA: boolean;
  READ_TOOL_STATE: boolean;
  READ_QUEUE_STATE: boolean;
  READ_WORK_OFFSETS: boolean;
  // Always false
  WRITE_PROGRAM: false;
  START_MACHINE: false;
  STOP_MACHINE: false;
  WRITE_OFFSETS: false;
  WRITE_TOOL_DATA: false;
}

export interface MachineStateSnapshot {
  machine_id: string;
  timestamp: string;
  connection_status: ConnectionStatus;
  availability: string;
  mode: MachineMode;
  current_program: string | null;
  current_job: string | null;
  alarm_state: AlarmState;
  cycle_state: CycleState;
  spindle_state: string;
  feed_state: string;
  tool_in_spindle: string | null;
  active_work_offset: string | null;
  queue_state: string;
  maintenance_state: string;
  source: string;
  quality: string;
  warnings: string[];
  connector_type: ConnectorType;
  // Invariants
  is_fabricated: false;
  is_real_machine_write: false;
}

export interface DispatchPackage {
  package_id: string;
  job_ref: string;
  assignment_ref: string;
  machine_ref: string;
  nc_candidate_ref: string | null;
  nc_hash: string | null;
  post_profile_ref: string | null;
  tool_list: string[];
  holder_list: string[];
  fixture_ref: string | null;
  setup_ref: string | null;
  work_offset_ref: string | null;
  verification_ref: string | null;
  approval_ref: string | null;
  schedule_ref: string | null;
  created_at: string;
  status: DispatchPackageStatus;
  warnings: string[];
  // Invariants
  is_dispatch_order: false;
  approval_required: true;
}

export interface DispatchApproval {
  approval_id: string;
  package_ref: string;
  approved_by: string;
  approved_at: string | null;
  scope: string;
  status: ApprovalStatus;
  comments: string;
  expires_at: string | null;
  // Invariants
  is_automatic: false;
  is_execution_approval: false;
}

export interface DryRunDispatchResult {
  result_id: string;
  package_ref: string;
  machine_ref: string;
  status: DryRunStatus;
  // Invariants
  is_real_transfer: false;
  is_dispatch_order: false;
  checks_passed: string[];
  failures: DispatchErrorCode[];
  warnings: string[];
  timestamp: string;
}

export interface ShopFloorReadiness {
  status: ShopFloorReadinessStatus;
  block_reasons: DispatchErrorCode[];
  warnings: string[];
  // Invariants
  approval_required: true;
  is_dispatch_order: false;
  machine_state_ref: string | null;
}

export interface DispatchPolicy {
  require_verified_toolpath: boolean;
  require_valid_nc: boolean;
  require_machine_idle: boolean;
  require_no_alarm: boolean;
  require_tools_ready: boolean;
  require_fixture_ready: boolean;
  require_human_approval: boolean;
  allow_unknown_machine_state: boolean;
}

export interface DispatchAuditEvent {
  event_id: string;
  event_type: DispatchAuditEventType;
  timestamp: string;
  actor: string;
  job_ref: string | null;
  machine_ref: string | null;
  package_ref: string | null;
  result: string;
  reason: string;
  reference_hash: string | null;
}

export interface PackageIntegrityResult {
  status: PackageIntegrityStatus;
  stale_reasons: string[];
  expected_nc_hash: string | null;
  actual_nc_hash: string | null;
  expected_assignment_ref: string | null;
  actual_assignment_ref: string | null;
}

// ---------------------------------------------------------------------------
// API response shapes
// ---------------------------------------------------------------------------

export interface CreatePackageResponse {
  package: DispatchPackage;
  audit_event: DispatchAuditEvent;
  approval_required: true;
  is_dispatch_order: false;
}

export interface DryRunResponse {
  dry_run_result: DryRunDispatchResult;
  start_event: DispatchAuditEvent;
  end_event: DispatchAuditEvent;
  approval_required: true;
  is_dispatch_order: false;
  is_real_transfer: false;
}

export interface MachineStateResponse {
  machine_state: MachineStateSnapshot;
  audit_event: DispatchAuditEvent;
  source: string;
  certification: string;
  is_real_machine_read: false;
  approval_required: true;
  is_dispatch_order: false;
}

export interface ApprovalResponse {
  approval: DispatchApproval;
  audit_event: DispatchAuditEvent;
  approval_required: true;
  is_dispatch_order: false;
}
