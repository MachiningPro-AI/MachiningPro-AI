/**
 * Level-16 Adaptive Manufacturing Intelligence TypeScript types.
 *
 * Hard invariants enforced as literal types:
 *   is_fabricated: false
 *   is_automatic_application: false
 *   review_required: true
 *   mutates_baseline: false
 *   RECOMMENDATION_ONLY: true
 *   HUMAN_REVIEW_MANDATORY: true
 */

export const RECOMMENDATION_ONLY = true as const;
export const HUMAN_REVIEW_MANDATORY = true as const;
export const PREDICTION_IS_NOT_MEASURED_FACT = true as const;
export const RECOMMENDATION_IS_NOT_APPROVED_CHANGE = true as const;
export const CORRELATION_IS_NOT_CAUSATION = true as const;
export const NO_AUTOMATIC_CNC_CHANGE = true as const;
export const NO_AUTOMATIC_FEED_OVERRIDE = true as const;
export const NO_AUTOMATIC_SPINDLE_OVERRIDE = true as const;
export const NO_AUTOMATIC_TOOL_OFFSET_CHANGE = true as const;
export const NO_AUTOMATIC_WORK_OFFSET_CHANGE = true as const;

export type PredictionFidelity = 'HIGH' | 'MEDIUM' | 'LOW' | 'INSUFFICIENT';
export type ModelStatus = 'TRAINED' | 'VALIDATED' | 'REJECTED' | 'STALE' | 'REVIEW_REQUIRED';
export type RecommendationStatus =
  | 'PROPOSED'
  | 'REVIEW_REQUIRED'
  | 'ACCEPTED_FOR_ENGINEERING_STUDY'
  | 'REJECTED'
  | 'STALE';
// NOT_PRESENT: 'APPLIED_TO_MACHINE'

export type AdaptiveRecommendationType =
  | 'VC_REVIEW_CANDIDATE'
  | 'FEED_REVIEW_CANDIDATE'
  | 'AP_REVIEW_CANDIDATE'
  | 'AE_REVIEW_CANDIDATE'
  | 'PROCESS_REVIEW_CANDIDATE'
  | 'ROUGHING_STRATEGY_REVIEW'
  | 'FINISHING_STRATEGY_REVIEW'
  | 'SETUP_CONSOLIDATION_REVIEW'
  | 'MACHINE_PERFORMANCE_RECOMMENDATION'
  | 'TOOL_RECOMMENDATION_CANDIDATE';

export type PredictionObjective =
  | 'MINIMIZE_CYCLE_TIME'
  | 'MAXIMIZE_TOOL_LIFE'
  | 'MINIMIZE_QUALITY_RISK'
  | 'MINIMIZE_ALARM_RISK'
  | 'BALANCED';

export type PredictionTarget =
  | 'CYCLE_TIME'
  | 'TOOL_LIFE'
  | 'QUALITY_RISK'
  | 'ALARM_RISK'
  | 'CUTTING_DATA_PERFORMANCE'
  | 'MACHINE_PERFORMANCE';

export type QualityRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'INSUFFICIENT';
export type AlarmRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'INSUFFICIENT';

export type WhatIfStatus =
  | 'PREDICTED_IMPROVEMENT'
  | 'PREDICTED_DEGRADATION'
  | 'NO_CHANGE_PREDICTED'
  | 'INSUFFICIENT_DATA'
  | 'OUT_OF_DOMAIN'
  | 'BLOCKED_BY_CONSTRAINT';

export type DriftStatus =
  | 'STABLE'
  | 'DRIFT_DETECTED'
  | 'REVIEW_REQUIRED'
  | 'INSUFFICIENT_DATA';

export type AdaptiveAuditEventType =
  | 'MODEL_TRAINED'
  | 'MODEL_EVALUATED'
  | 'PREDICTION_CREATED'
  | 'RECOMMENDATION_CREATED'
  | 'RECOMMENDATION_REVIEWED'
  | 'RECOMMENDATION_ACCEPTED'
  | 'RECOMMENDATION_REJECTED'
  | 'WHAT_IF_EVALUATED'
  | 'DATA_DRIFT_DETECTED'
  | 'MODEL_DRIFT_DETECTED';

// ---------------------------------------------------------------------------
// Core models with locked invariants
// ---------------------------------------------------------------------------

export interface ManufacturingLearningRecord {
  record_id: string;
  part_family: string | null;
  material: string | null;
  machine_class: string | null;
  operation_type: string | null;
  planned_cutting_data: Record<string, number>;
  observed_cutting_data: Record<string, number>;
  planned_cycle_time: number | null;
  actual_cycle_time: number | null;
  planned_tool_life: number | null;
  actual_tool_life: number | null;
  quality_result: string | null;
  alarm_summary: string | null;
  source: string;
  provenance: string | null;
  data_quality: string;
  timestamp: string | null;
  is_fabricated: false;        // invariant — never true for real records
  is_test_only: boolean;
}

export interface PredictionResult {
  prediction_id: string;
  target: PredictionTarget;
  model_ref: string | null;
  engineering_baseline: number | null;
  historical_prediction: number | null;
  predicted_value: number | null;
  fidelity: PredictionFidelity;
  sample_count: number;
  similar_case_ids: string[];
  uncertainty_description: string;
  warnings: string[];
  is_fabricated: false;        // invariant
  out_of_domain: boolean;
}

export interface AdaptiveRecommendation {
  recommendation_id: string;
  recommendation_type: AdaptiveRecommendationType;
  current_state: Record<string, unknown>;
  proposed_state: Record<string, unknown>;
  objective: PredictionObjective;
  evidence: string[];
  model_ref: string | null;
  sample_count: number;
  fidelity: PredictionFidelity;
  predicted_effect: Record<string, unknown>;
  constraints: string[];
  warnings: string[];
  review_required: true;      // invariant — always requires engineering review
  status: RecommendationStatus;
  is_automatic_application: false;  // invariant — never automatically applied
}

export interface WhatIfScenario {
  scenario_id: string;
  description: string;
  parameter_changes: Record<string, unknown>;
  baseline_values: Record<string, unknown>;
  predicted_outputs: Record<string, unknown>;
  status: WhatIfStatus;
  fidelity: PredictionFidelity;
  mutates_baseline: false;    // invariant — never modifies the baseline record
  sample_count: number;
  warnings: string[];
}

export interface ModelSpec {
  model_id: string;
  version: string;
  target: PredictionTarget;
  training_data_hash: string | null;
  sample_count: number;
  train_mae: number | null;
  validation_mae: number | null;
  metrics: Record<string, number>;
  limitations: string[];
  status: ModelStatus;
  is_fabricated_accuracy: false;  // invariant
}

export interface SimilarCase {
  case_id: string;
  record_ref: string;
  similarity_score: number;
  similarity_factors: Record<string, number>;
  matched_features: string[];
  actual_cycle_time: number | null;
  actual_tool_life: number | null;
  quality_result: string | null;
}

export interface DriftReport {
  report_id: string;
  drift_status: DriftStatus;
  reference_sample_count: number;
  current_sample_count: number;
  drifted_features: string[];
  drift_details: Record<string, unknown>;
  warnings: string[];
  review_required: boolean;
}

export interface TradeOffAnalysis {
  analysis_id: string;
  objective_names: string[];
  candidates: TradeOffCandidate[];
  pareto_front_ids: string[];
  no_single_best: boolean;
  warnings: string[];
}

export interface TradeOffCandidate {
  candidate_id: string;
  description: string;
  parameters: Record<string, unknown>;
  objectives: Record<string, number | null>;
  is_pareto_optimal: boolean;
  trade_offs: string[];
  warnings: string[];
}

export interface AdaptiveAuditEvent {
  event_id: string;
  event_type: AdaptiveAuditEventType;
  timestamp: string;
  actor: string;
  model_ref: string | null;
  recommendation_ref: string | null;
  prediction_ref: string | null;
  details: Record<string, unknown>;
}

export interface QualityRiskResult {
  prediction_id: string;
  risk_level: QualityRiskLevel;
  reject_rate: number | null;
  sample_count: number;
  fidelity: PredictionFidelity;
  factors: string[];
  warnings: string[];
  is_fabricated: false;
}

export interface AlarmRiskResult {
  prediction_id: string;
  risk_level: AlarmRiskLevel;
  alarm_rate: number | null;
  sample_count: number;
  fidelity: PredictionFidelity;
  factors: string[];
  warnings: string[];
  is_fabricated: false;
}
