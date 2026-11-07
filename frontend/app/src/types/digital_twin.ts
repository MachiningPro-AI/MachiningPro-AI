/**
 * Level-18 Manufacturing Digital Twin — TypeScript types.
 *
 * SAFETY INVARIANTS (literal types — cannot be changed):
 *   is_simulation_only: true (never false)
 *   is_production_plan: false (never true)
 *   is_proposed_only: true (never false)
 *   is_automatic_application: false (never true)
 *   review_required: true (never false)
 *   baseline_mutation_allowed: false (never true)
 */

// ---- Enums ----------------------------------------------------------------

export type ScenarioType =
  | 'BASELINE'
  | 'MACHINE_ALTERNATIVE'
  | 'TOOL_ALTERNATIVE'
  | 'CUTTING_DATA_ALTERNATIVE'
  | 'PROCESS_ALTERNATIVE'
  | 'SETUP_ALTERNATIVE'
  | 'SCHEDULE_ALTERNATIVE'
  | 'QUANTITY_ALTERNATIVE'
  | 'COMBINED_ALTERNATIVE';

export type ScenarioStatus =
  | 'DRAFT'
  | 'INCOMPLETE'
  | 'VALID'
  | 'INVALID'
  | 'SIMULATED'
  | 'REVIEW_REQUIRED'
  | 'REJECTED'
  | 'STALE';
// 'PRODUCTION_APPLIED' is intentionally absent

export type ObjectiveType =
  | 'MINIMIZE_CYCLE_TIME'
  | 'MINIMIZE_MANUFACTURING_COST'
  | 'MAXIMIZE_TOOL_LIFE'
  | 'MINIMIZE_QUALITY_RISK'
  | 'MINIMIZE_ALARM_RISK'
  | 'MINIMIZE_SETUP_TIME'
  | 'MINIMIZE_ENERGY'
  | 'MAXIMIZE_THROUGHPUT'
  | 'MINIMIZE_LATENESS'
  | 'MINIMIZE_MACHINE_LOAD';

export type KPIKey =
  | 'CYCLE_TIME'
  | 'SETUP_TIME'
  | 'BATCH_TIME'
  | 'THROUGHPUT'
  | 'MANUFACTURING_COST'
  | 'TOOL_LIFE'
  | 'TOOL_CONSUMPTION'
  | 'ENERGY'
  | 'MACHINE_LOAD'
  | 'LATENESS'
  | 'MATERIAL_UTILIZATION'
  | 'QUALITY_RISK'
  | 'ALARM_RISK';

export type FidelityLevel = 'INSUFFICIENT' | 'LOW' | 'MEDIUM' | 'HIGH';

export type CycleTimeSource =
  | 'DETERMINISTIC'
  | 'LEARNED'
  | 'SIMULATED'
  | 'OBSERVED'
  | 'UNKNOWN';

export type EnergyStatus =
  | 'COMPUTED'
  | 'ESTIMATED'
  | 'INSUFFICIENT_DATA';

export type RecommendationType =
  | 'FASTEST_VALID_SCENARIO'
  | 'LOWEST_KNOWN_COST_SCENARIO'
  | 'BEST_TOOL_LIFE_SCENARIO'
  | 'LOWEST_QUALITY_RISK_SCENARIO'
  | 'PARETO_CANDIDATE';

export type AuditEventType =
  | 'SCENARIO_CREATED'
  | 'SCENARIO_SIMULATED'
  | 'COMPARISON_RUN'
  | 'PARETO_CALCULATED'
  | 'RECOMMENDATION_GENERATED'
  | 'SCENARIO_REVIEWED'
  | 'SCENARIO_STALE';

export type StaleReason =
  | 'NEVER_SIMULATED'
  | 'BASELINE_CHANGED'
  | 'MACHINE_CATALOG_UPDATED'
  | 'TOOL_CATALOG_UPDATED'
  | 'MATERIAL_CATALOG_UPDATED'
  | 'CUTTING_DATA_CHANGED'
  | 'SCHEDULE_CHANGED'
  | 'MACHINE_CAPABILITY_CHANGED'
  | 'TOOL_GEOMETRY_CHANGED'
  | 'COST_MODEL_CHANGED'
  | 'EVALUATOR_VERSION_CHANGED';

// ---- Models ---------------------------------------------------------------

export interface ManufacturingTwinScenario {
  scenario_id: string;
  scenario_type: ScenarioType;
  baseline_ref?: string | null;
  part_ref?: string | null;
  machine_ref?: string | null;
  tool_refs: string[];
  cutting_data: Record<string, unknown>;
  quantity?: number | null;
  batch_size?: number | null;
  estimated_cycle_time_min?: number | null;
  machine_spindle_max_rpm?: number | null;
  machine_axis_count?: number | null;
  machine_idle_power_kw?: number | null;
  machine_cutting_power_kw?: number | null;
  required_spindle_rpm?: number | null;
  required_axis_count?: number | null;
  toolpath_verified: boolean;
  schedule_ref?: string | null;
  status: ScenarioStatus;
  fidelity: FidelityLevel;
  evaluation_version: string;
  // Safety invariants — literal types
  is_simulation_only: true;
  is_production_plan: false;
  review_required: true;
  baseline_mutation_allowed: false;
}

export interface ScenarioKPI {
  cycle_time_min?: number | null;
  cycle_time_source: CycleTimeSource;
  setup_time_min?: number | null;
  batch_time_min?: number | null;
  throughput_per_hour?: number | null;
  manufacturing_cost?: number | null;
  tool_life_min?: number | null;
  tool_consumption?: number | null;
  quality_risk_level?: string | null;
  alarm_risk_level?: string | null;
  machine_load_pct?: number | null;
  lateness_min?: number | null;
  energy_kwh?: number | null;
  energy_status: EnergyStatus;
  material_utilization_pct?: number | null;
  fidelity: FidelityLevel;
  unknowns: string[];
  is_fabricated: false;
}

export interface ConstraintResult {
  constraint_name: string;
  passed: boolean;
  fail_reason?: string | null;
  detail: string;
}

export interface SimulationResult {
  scenario_id: string;
  status: ScenarioStatus;
  kpi: ScenarioKPI;
  constraint_results: ConstraintResult[];
  hard_constraint_failures: string[];
  fidelity: FidelityLevel;
  warnings: string[];
  errors: string[];
  // Safety invariants
  is_simulation_only: true;
  is_production_plan: false;
}

export interface KPIDiff {
  kpi_name: string;
  baseline_value?: number | null;
  scenario_value?: number | null;
  absolute_diff?: number | null;
  relative_diff_pct?: number | null;
  improved?: boolean | null;
}

export interface ScenarioComparison {
  baseline_id: string;
  comparison_id: string;
  kpi_diffs: KPIDiff[];
  trade_offs: string[];
  unknown_diffs: string[];
  constraint_delta: string;
  is_fabricated: false;
}

export interface ObjectiveWeight {
  objective: ObjectiveType;
  weight: number;
}

export interface MultiObjectiveScore {
  scenario_id: string;
  component_scores: Record<string, number>;
  weighted_score?: number | null;
  weights_applied: ObjectiveWeight[];
  unknowns: string[];
}

export interface ParetoCandidate {
  scenario_id: string;
  dominated_by: string[];
  is_non_dominated: boolean;
  dominated_in: KPIKey[];
  dominates_in: KPIKey[];
}

export interface TwinRecommendation {
  recommendation_type: RecommendationType;
  scenario_id: string;
  why: string;
  constraints_passed: string[];
  data_fidelity: FidelityLevel;
  trade_offs: string[];
  unknowns: string[];
  // Safety invariants — literal types
  review_required: true;
  is_proposed_only: true;
  is_automatic_application: false;
}

export interface TwinAuditEvent {
  event_type: AuditEventType;
  scenario_id: string;
  actor: string;
  timestamp: string;
  payload: Record<string, unknown>;
  event_hash: string;
}

export interface TwinSearchLimits {
  max_machines: number;
  max_tools: number;
  max_parameter_candidates: number;
  max_combined_scenarios: number;
}

export interface StalenessCheck {
  scenario_id: string;
  is_stale: boolean;
  stale_reasons: StaleReason[];
  current_input_snapshot_hash: string;
  recorded_input_snapshot_hash?: string | null;
  evaluator_version: string;
  checked_at?: string | null;
  detail: string;
}

// ---- Safety constants (module-level) --------------------------------------

export const NO_AUTOMATIC_APPLICATION: true = true;
export const NO_CNC_WRITE: true = true;
export const NO_AUTOMATIC_DISPATCH: true = true;
export const NO_AUTOMATIC_CAM_CHANGE: true = true;
export const NO_AUTOMATIC_GCODE_REGENERATION: true = true;
export const NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT: true = true;
export const NO_AUTOMATIC_MACHINE_REASSIGNMENT: true = true;
export const NO_AUTOMATIC_SCHEDULING_CHANGE: true = true;
export const NO_AUTOMATIC_TOOL_SUBSTITUTION: true = true;
export const BASELINE_MUTATION_ALLOWED: false = false;
export const SCENARIO_IS_NOT_PRODUCTION_PLAN: true = true;
export const OPTIMIZED_SCENARIO_IS_NOT_APPROVED: true = true;
export const HUMAN_REVIEW_MANDATORY: true = true;
export const NO_FABRICATED_TWIN_RESULT: true = true;
export const UNKNOWN_INPUTS_STAY_UNKNOWN: true = true;
