/**
 * Level-17 CNC Job Planning & Machine Assignment — TypeScript types.
 *
 * ASSIGNMENT_IS_PROPOSED_ONLY: All recommendation objects have is_proposed_only=true
 * and is_automatic_dispatch=false as literal-type invariants.
 * Human approval is mandatory before any machine is assigned or any job dispatched.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type AssignmentStatus =
  | 'PROPOSED'
  | 'REVIEW_REQUIRED'
  | 'ACCEPTED_FOR_ENGINEERING_STUDY'
  | 'REJECTED';
// NOT PRESENT: DISPATCHED_TO_MACHINE, EXECUTING, AUTO_ASSIGNED

export type CapabilityMatchLevel =
  | 'FULL_MATCH'
  | 'PARTIAL_MATCH'
  | 'NO_MATCH'
  | 'UNKNOWN';

export type MaterialCompatibilityResult =
  | 'COMPATIBLE'
  | 'LIKELY_COMPATIBLE'
  | 'UNKNOWN'
  | 'INCOMPATIBLE';

export type WorkloadStatus =
  | 'LOW'
  | 'MODERATE'
  | 'HIGH'
  | 'OVERLOADED'
  | 'UNKNOWN';

export type PlanningBlockReason =
  | 'MISSING_CAM_OPERATION_DATA'
  | 'NO_ELIGIBLE_MACHINE'
  | 'CAPABILITY_UNKNOWN'
  | 'MATERIAL_INCOMPATIBLE'
  | 'SPINDLE_INSUFFICIENT'
  | 'MISSING_PROCESS_CAPABILITY'
  | 'NO_MACHINES_PROVIDED';

export type SpindleMatchResult =
  | 'WITHIN_RANGE'
  | 'AT_LIMIT'
  | 'OVER_LIMIT'
  | 'UNDER_SPEC'
  | 'UNKNOWN';

export type RankingObjective =
  | 'CAPABILITY_FIT'
  | 'MATERIAL_COMPATIBILITY'
  | 'SPINDLE_UTILIZATION'
  | 'WORKLOAD_BALANCE'
  | 'PROCESS_CAPABILITY';

// ---------------------------------------------------------------------------
// Models
// ---------------------------------------------------------------------------

export interface CamOperationRequirements {
  job_id: string;
  part_reference: string | null;
  material: string | null;
  operations: string[];
  required_machine_class: string;
  required_axis_count: number | null;
  required_spindle_rpm: number | null;
  required_spindle_power_kw: number | null;
  required_x_travel_mm: number | null;
  required_y_travel_mm: number | null;
  required_z_travel_mm: number | null;
  workpiece_mass_kg: number | null;
  requires_through_spindle_coolant: boolean;
  requires_live_tooling: boolean;
  requires_tapping: boolean;
  requires_boring: boolean;
  estimated_cycle_time_min: number | null;
  data_source: string;
  is_fabricated_requirements: false;  // invariant — always false
}

export interface MachineCapabilityProfile {
  machine_id: string;
  machine_class: string;
  axis_count: number | null;
  spindle_max_rpm: number | null;
  spindle_power_kw: number | null;
  travel_x_mm: number | null;
  travel_y_mm: number | null;
  travel_z_mm: number | null;
  table_load_kg: number | null;
  turning_capable: boolean;
  milling_capable: boolean;
  drilling_capable: boolean;
  through_spindle_coolant: boolean | null;
  has_live_tooling: boolean;
  capable_tapping: boolean | null;
  capable_boring: boolean | null;
  tool_magazine_capacity: number | null;
  is_fabricated_capability: false;  // invariant — always false
}

export interface CapabilityCheckResult {
  check_name: string;
  match_level: CapabilityMatchLevel;
  detail: string;
}

export interface MaterialCompatibilityCheck {
  material: string | null;
  machine_class: string;
  result: MaterialCompatibilityResult;
  reason: string;
}

export interface SpindleMatchCheck {
  required_rpm: number | null;
  machine_max_rpm: number | null;
  result: SpindleMatchResult;
  utilization_pct: number | null;
}

export interface WorkloadEstimate {
  machine_id: string;
  queue_depth: number;
  estimated_cycle_time_min: number | null;
  workload_status: WorkloadStatus;
  is_fabricated: false;  // invariant — always false
}

export interface AssignmentCandidate {
  machine_id: string;
  rank: number;
  capability_score: number;
  material_compatibility: MaterialCompatibilityResult;
  spindle_match: SpindleMatchResult;
  workload_status: WorkloadStatus;
  capability_checks: CapabilityCheckResult[];
  workload_estimate: WorkloadEstimate;
  incompatibility_reasons: string[];
  soft_preference_score: number;
  overall_score: number;
  explanation: string;
  is_proposed_only: true;        // invariant — always true
  is_automatic_dispatch: false;  // invariant — always false
}

export interface AssignmentRecommendation {
  job_id: string;
  status: AssignmentStatus;
  candidates: AssignmentCandidate[];
  best_candidate_id: string | null;
  planning_warnings: string[];
  blocking_reasons: PlanningBlockReason[];
  is_proposed_only: true;        // invariant — always true
  is_automatic_dispatch: false;  // invariant — always false
  review_required: true;         // invariant — always true
  is_fabricated_data: false;     // invariant — always false
  explanation: string;
  ranking_objective: RankingObjective;
}

// ---------------------------------------------------------------------------
// Safety constants — all true
// ---------------------------------------------------------------------------

export const NO_AUTOMATIC_MACHINE_ASSIGNMENT: true = true;
export const NO_AUTOMATIC_JOB_DISPATCH: true = true;
export const NO_FABRICATED_CAPABILITY_DATA: true = true;
export const MISSING_DATA_FAILS_CLOSED: true = true;
export const ASSIGNMENT_IS_PROPOSED_ONLY: true = true;
export const HUMAN_APPROVAL_MANDATORY: true = true;
export const UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE: true = true;
