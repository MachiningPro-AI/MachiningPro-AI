/**
 * Level-13 Machine Scheduling and Job Assignment — TypeScript types.
 *
 * NO_CNC_DISPATCH=YES
 * APPROVAL_REQUIRED=YES
 * is_dispatch_order is always false
 */

// -------------------------------------------------------------------------
// Enums
// -------------------------------------------------------------------------

export type JobStatus =
  | 'DRAFT'
  | 'ENGINEERING_INCOMPLETE'
  | 'READY_FOR_SCHEDULING'
  | 'SCHEDULING_BLOCKED'
  | 'SCHEDULED_CANDIDATE'
  | 'ASSIGNMENT_REVIEW_REQUIRED'
  | 'APPROVED_FOR_DISPATCH_FUTURE'
  | 'CANCELLED';
// NOT_PRESENT: RUNNING_ON_MACHINE

export type MachineAvailabilityStatus =
  | 'AVAILABLE'
  | 'BUSY'
  | 'MAINTENANCE'
  | 'OFFLINE'
  | 'RESERVED'
  | 'UNKNOWN';
// UNKNOWN !== AVAILABLE

export type MachineEligibilityResult =
  | 'ELIGIBLE'
  | 'PARTIALLY_ELIGIBLE'
  | 'INELIGIBLE'
  | 'UNKNOWN';

export type ToolAvailabilityStatus =
  | 'AVAILABLE'
  | 'LOADED_ON_MACHINE'
  | 'IN_TOOL_CRIB'
  | 'RESERVED'
  | 'MISSING'
  | 'UNKNOWN';

export type HolderAvailabilityStatus = 'AVAILABLE' | 'RESERVED' | 'MISSING' | 'UNKNOWN';

export type FixtureAvailabilityStatus =
  | 'AVAILABLE'
  | 'INSTALLED'
  | 'RESERVED'
  | 'MISSING'
  | 'UNKNOWN';

export type SetupReadinessStatus = 'READY' | 'PARTIAL' | 'BLOCKED' | 'UNKNOWN';

export type NCReadinessStatus = 'READY' | 'NOT_GENERATED' | 'STALE' | 'BLOCKED' | 'UNKNOWN';

export type JobPriority = 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';

export type SchedulingAlgorithm = 'FIFO' | 'EDD' | 'SPT' | 'PRIORITY_FIRST';

export type SchedulingObjective =
  | 'EARLIEST_COMPLETION'
  | 'MINIMIZE_LATENESS'
  | 'MINIMIZE_SETUP_CHANGES'
  | 'MINIMIZE_MACHINE_IDLE_TIME'
  | 'PRIORITY_WEIGHTED_COMPLETION'
  | 'BALANCE_MACHINE_LOAD';

export type ProductionReadinessStatus =
  | 'READY_FOR_SCHEDULING'
  | 'SCHEDULED'
  | 'DISPATCH_BLOCKED'
  | 'REVIEW_REQUIRED'
  | 'UNKNOWN';
// NOT_PRESENT: READY_FOR_DISPATCH

export type ResourceConflictType =
  | 'MACHINE_DOUBLE_BOOKING'
  | 'FIXTURE_DOUBLE_BOOKING'
  | 'TOOL_RESERVATION_CONFLICT'
  | 'MAINTENANCE_OVERLAP'
  | 'CALENDAR_OVERLAP';

export type SchedulingBlockReason =
  | 'TOOLPATH_UNVERIFIED'
  | 'NC_CANDIDATE_MISSING'
  | 'NC_CANDIDATE_STALE'
  | 'NC_CANDIDATE_BLOCKED'
  | 'MACHINE_INELIGIBLE'
  | 'MACHINE_UNAVAILABLE'
  | 'TOOL_MISSING'
  | 'FIXTURE_MISSING'
  | 'HOLDER_MISSING'
  | 'DUE_DATE_UNKNOWN'
  | 'QUEUE_CONFLICT'
  | 'ENGINEERING_INCOMPLETE';

export type MachineClass =
  | 'VMC_3AXIS'
  | 'VMC_4AXIS'
  | 'VMC_5AXIS'
  | 'HMC_3AXIS'
  | 'HMC_4AXIS'
  | 'LATHE_2AXIS'
  | 'LATHE_LIVE_TOOL'
  | 'TURN_MILL'
  | 'GRINDER'
  | 'WIRE_EDM'
  | 'UNKNOWN';

// -------------------------------------------------------------------------
// Core models
// -------------------------------------------------------------------------

export interface EligibilityCheckResult {
  check_name: string;
  passed: boolean;
  fail_reason: string | null;
  detail: string;
}

export interface EligibilityReport {
  machine_id: string;
  result: MachineEligibilityResult;
  checks: EligibilityCheckResult[];
  hard_constraint_failures: string[];
  soft_preference_score: number;
  unknown_data_fields: string[];
  warnings: string[];
}

export interface NCReadiness {
  status: NCReadinessStatus;
  nc_candidate_ref: string | null;
  nc_candidate_status: string | null;
  toolpath_verified: boolean;
  is_stale: boolean;
  block_reasons: SchedulingBlockReason[];
  warnings: string[];
}

export interface SetupReadiness {
  status: SetupReadinessStatus;
  tool_statuses: Record<string, ToolAvailabilityStatus>;
  holder_statuses: Record<string, HolderAvailabilityStatus>;
  fixture_status: FixtureAvailabilityStatus;
  missing_tools: string[];
  missing_holders: string[];
  fixture_blocked: boolean;
  block_reasons: SchedulingBlockReason[];
  warnings: string[];
}

export interface ProductionReadiness {
  status: ProductionReadinessStatus;
  engineering_complete: boolean;
  cam_ready: boolean;
  toolpath_verified: boolean;
  nc_readiness: NCReadiness;
  machine_eligible: boolean;
  setup_readiness: SetupReadiness;
  schedule_slot_available: boolean;
  block_reasons: SchedulingBlockReason[];
  warnings: string[];
  approval_required: true;  // always true
}

export interface DurationEstimate {
  setup_time_min: number | null;
  cycle_time_per_part_min: number | null;
  quantity: number;
  total_estimated_min: number | null;
  status: 'KNOWN' | 'PARTIAL' | 'UNKNOWN';
  assumptions: string[];
  warnings: string[];
}

export interface ScheduleCandidate {
  job_id: string;
  machine_id: string;
  queue_position: number | null;
  planned_start_iso: string | null;
  planned_finish_iso: string | null;
  duration: DurationEstimate;
  score_components: Record<string, number>;
  hard_constraint_results: EligibilityCheckResult[];
  soft_preference_results: Record<string, number>;
  readiness: ProductionReadiness;
  lateness_min: number | null;
  warnings: string[];
  is_dispatch_order: false;    // invariant — always false
  approval_required: true;     // invariant — always true
}

export interface JobAssignmentCandidate {
  job_ref: string;
  machine_ref: string;
  setup_ref: string | null;
  nc_candidate_ref: string | null;
  tool_refs: string[];
  fixture_ref: string | null;
  schedule_candidate: ScheduleCandidate | null;
  eligibility_report: EligibilityReport;
  setup_readiness: SetupReadiness;
  nc_readiness: NCReadiness;
  readiness: ProductionReadiness;
  eligibility_reasons: string[];
  preference_reasons: string[];
  unknown_data: string[];
  warnings: string[];
  approval_required: true;     // invariant — always true
  is_dispatch_order: false;    // invariant — always false
}

export interface ResourceConflict {
  conflict_type: ResourceConflictType;
  resource_id: string;
  job_ids: string[];
  description: string;
  severity: string;
}

// -------------------------------------------------------------------------
// API response shapes
// -------------------------------------------------------------------------

export interface EvaluateMachinesResponse {
  job_id: string;
  candidates: EligibilityReport[];
  total_evaluated: number;
  eligible_count: number;
  ineligible_count: number;
  approval_required: true;
  is_dispatch_order: false;
}

export interface ScheduleCandidateResponse {
  schedule_candidate: ScheduleCandidate;
  approval_required: true;
  is_dispatch_order: false;
}

export interface AssignmentResponse {
  assignment_candidate: JobAssignmentCandidate;
  approval_required: true;
  is_dispatch_order: false;
}

export interface ReadinessResponse {
  readiness: ProductionReadiness;
  approval_required: true;
  is_dispatch_order: false;
}
