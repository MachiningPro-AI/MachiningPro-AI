/**
 * Level-15 Monitoring TypeScript Types.
 *
 * OBSERVE → COMPARE → DIAGNOSE → RECOMMEND.
 * No machine-control types are defined here.
 */

export type CycleState =
  | 'IDLE'
  | 'SETUP'
  | 'READY'
  | 'RUNNING'
  | 'FEED_HOLD'
  | 'ALARM'
  | 'STOPPED'
  | 'COMPLETE'
  | 'UNKNOWN';

export type ObservationSource =
  | 'SIMULATED_CONTROLLER'
  | 'OPC_UA_READ'
  | 'MTCONNECT_READ'
  | 'MES_READ'
  | 'ERP_READ'
  | 'MANUAL_ENTRY'
  | 'IMPORT_FILE'
  | 'HISTORICAL_DATA'
  | 'UNKNOWN';

export type DataQuality =
  | 'VALIDATED'
  | 'RAW'
  | 'PARTIAL'
  | 'STALE'
  | 'CONFLICT'
  | 'INVALID'
  | 'UNKNOWN';

export type DeviationType =
  | 'CYCLE_TIME_HIGH'
  | 'CYCLE_TIME_LOW'
  | 'CUTTING_TIME_HIGH'
  | 'IDLE_TIME_HIGH'
  | 'SETUP_TIME_HIGH'
  | 'TOOL_CHANGE_FREQUENCY_HIGH'
  | 'PROGRAM_MISMATCH'
  | 'MACHINE_ASSIGNMENT_MISMATCH'
  | 'FEED_DEVIATION'
  | 'SPINDLE_SPEED_DEVIATION'
  | 'QUALITY_DEVIATION'
  | 'ALARM_FREQUENCY_HIGH';

export type ToolLifeStatus =
  | 'TOOL_LIFE_SHORTER_THAN_EXPECTED'
  | 'TOOL_LIFE_LONGER_THAN_EXPECTED'
  | 'TOOL_LIFE_WITHIN_POLICY'
  | 'INSUFFICIENT_DATA';

export type OEEStatus = 'CALCULATED' | 'INSUFFICIENT_DATA' | 'INVALID';

export type RecommendationType =
  | 'REVIEW_CUTTING_DATA'
  | 'REVIEW_TOOL_SELECTION'
  | 'REVIEW_TOOL_LIFE'
  | 'REVIEW_MACHINE_ASSIGNMENT'
  | 'REVIEW_SETUP_METHOD'
  | 'REVIEW_FIXTURE'
  | 'REVIEW_NC_PROGRAM'
  | 'REVIEW_MAINTENANCE'
  | 'REVIEW_QUALITY_PROCESS';

export type ClosedLoopProposalType =
  | 'NEW_FEED_CANDIDATE'
  | 'NEW_SPINDLE_CANDIDATE'
  | 'NEW_TOOL_CANDIDATE'
  | 'NEW_CYCLE_TIME_BASELINE';

export type RootCauseCandidateStatus = 'CANDIDATE' | 'NOT_CONFIRMED';

export interface ProductionObservation {
  observation_id: string;
  machine_id: string;
  job_id: string;
  part_reference: string | null;
  operation_ref: string | null;
  timestamp_start: string | null;
  timestamp_end: string | null;
  cycle_state: CycleState;
  program_reference: string | null;
  program_hash: string | null;
  part_count: number | null;
  good_count: number | null;
  reject_count: number | null;
  spindle_runtime: number | null;
  cutting_runtime: number | null;
  idle_runtime: number | null;
  alarm_runtime: number | null;
  actual_cycle_time: number | null;
  actual_feed: number | null;
  actual_spindle_speed: number | null;
  tool_id: string | null;
  tool_usage_time: number | null;
  tool_change_event: boolean;
  alarm_codes: string[];
  quality_results: string[];
  source: ObservationSource;
  quality: DataQuality;
  warnings: string[];
  /** Must always be false. Fabricated observation data is never valid. */
  is_fabricated: false;
}

export interface PlannedActualComparison {
  comparison_id: string;
  observation_ref: string;
  job_ref: string;
  machine_ref: string;
  operation_ref: string | null;
  planned_cycle_time: number | null;
  actual_cycle_time: number | null;
  cycle_time_delta: number | null;
  cycle_time_relative_delta: number | null;
  planned_cutting_time: number | null;
  actual_cutting_time: number | null;
  planned_setup_time: number | null;
  actual_setup_time: number | null;
  planned_tool_usage: number | null;
  actual_tool_usage: number | null;
  planned_quantity: number | null;
  actual_completed_quantity: number | null;
  planned_machine: string | null;
  actual_machine: string | null;
  planned_nc_hash: string | null;
  observed_program_hash: string | null;
  deviations: string[];
  data_quality: DataQuality;
  warnings: string[];
}

export interface ProcessDeviation {
  deviation_id: string;
  deviation_type: DeviationType;
  comparison_ref: string;
  observation_ref: string | null;
  absolute_delta: number | null;
  relative_delta: number | null;
  threshold_used: number | null;
  evidence: string;
  is_confirmed: false;
}

export interface OEEResult {
  oee_id: string;
  machine_id: string | null;
  planned_production_time: number | null;
  run_time: number | null;
  availability: number | null;
  ideal_cycle_time: number | null;
  total_count: number | null;
  performance: number | null;
  good_count: number | null;
  quality: number | null;
  oee: number | null;
  status: OEEStatus;
  warnings: string[];
}

export interface ToolLifeFeedback {
  feedback_id: string;
  tool_id: string;
  predicted_life: number | null;
  observed_life: number | null;
  status: ToolLifeStatus;
  relative_delta: number | null;
  data_quality: DataQuality;
  /** Must always be false. Tool feedback is PROPOSED_ONLY. */
  is_automatic_action: false;
}

export interface RootCauseCandidate {
  candidate_id: string;
  status: RootCauseCandidateStatus;
  observation_ref: string | null;
  comparison_ref: string | null;
  evidence: string[];
  correlated_deviations: string[];
  correlated_alarms: string[];
  suggested_direction: string;
  /** Must always be false. Correlation is not proof. */
  is_confirmed: false;
  /** Must always be false. */
  is_causal_proof: false;
}

export interface EngineeringRecommendation {
  recommendation_id: string;
  recommendation_type: RecommendationType;
  candidate_ref: string | null;
  rationale: string;
  /** Must always be true. Human review is required. */
  requires_review: true;
  /** Must always be false. No automatic action is ever applied. */
  is_automatic_action: false;
  /** Must always be false at creation. */
  is_applied: false;
}

export interface ClosedLoopProposal {
  proposal_id: string;
  proposal_type: ClosedLoopProposalType;
  observation_ref: string | null;
  comparison_ref: string | null;
  proposed_value: number | null;
  current_value: number | null;
  rationale: string;
  /** Must always be true. */
  is_proposed_only: true;
  /** Must always be false. No automatic write to cutting data or NC. */
  is_automatic_write: false;
}

/** Dashboard display labels for observed/calculated/proposed/unknown states. */
export type ObservationLabel = 'OBSERVED' | 'CALCULATED' | 'PROPOSED' | 'UNKNOWN';

export const CLOSED_LOOP_MODE = 'PROPOSED_ONLY' as const;
export const NO_AUTOMATIC_CORRECTIVE_ACTION = true as const;
export const NO_REAL_MACHINE_WRITE = true as const;
