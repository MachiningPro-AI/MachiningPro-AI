/**
 * Level-18 Manufacturing Digital Twin — service layer.
 *
 * Re-exports safety constants.
 * Enforces invariants at every boundary:
 *   - Scenario must be simulation-only, not a production plan
 *   - Recommendations must be proposed-only, no automatic application
 *   - Review is always required
 *   - Unknown KPIs are never coerced to zero
 */

import type {
  ManufacturingTwinScenario,
  MultiObjectiveScore,
  ParetoCandidate,
  ScenarioComparison,
  ScenarioKPI,
  SimulationResult,
  TwinRecommendation,
} from '../types/digital_twin.ts';

export {
  BASELINE_MUTATION_ALLOWED,
  HUMAN_REVIEW_MANDATORY,
  NO_AUTOMATIC_APPLICATION,
  NO_AUTOMATIC_CAM_CHANGE,
  NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT,
  NO_AUTOMATIC_DISPATCH,
  NO_AUTOMATIC_GCODE_REGENERATION,
  NO_AUTOMATIC_MACHINE_REASSIGNMENT,
  NO_AUTOMATIC_SCHEDULING_CHANGE,
  NO_AUTOMATIC_TOOL_SUBSTITUTION,
  NO_CNC_WRITE,
  NO_FABRICATED_TWIN_RESULT,
  OPTIMIZED_SCENARIO_IS_NOT_APPROVED,
  SCENARIO_IS_NOT_PRODUCTION_PLAN,
  UNKNOWN_INPUTS_STAY_UNKNOWN,
} from '../types/digital_twin.ts';

// ---------------------------------------------------------------------------
// Contract violation error
// ---------------------------------------------------------------------------

export class DigitalTwinContractViolation extends Error {
  constructor(message: string) {
    super(`[DigitalTwinContractViolation] ${message}`);
    this.name = 'DigitalTwinContractViolation';
  }
}

// ---------------------------------------------------------------------------
// Scenario contract enforcement
// ---------------------------------------------------------------------------

export function enforceScenarioContract(scenario: ManufacturingTwinScenario): void {
  if (!scenario.is_simulation_only) {
    throw new DigitalTwinContractViolation(
      `scenario ${scenario.scenario_id}: is_simulation_only must be true`
    );
  }
  if (scenario.is_production_plan) {
    throw new DigitalTwinContractViolation(
      `scenario ${scenario.scenario_id}: is_production_plan must be false`
    );
  }
  if (!scenario.review_required) {
    throw new DigitalTwinContractViolation(
      `scenario ${scenario.scenario_id}: review_required must be true`
    );
  }
  if (scenario.baseline_mutation_allowed) {
    throw new DigitalTwinContractViolation(
      `scenario ${scenario.scenario_id}: baseline_mutation_allowed must be false`
    );
  }
}

// ---------------------------------------------------------------------------
// Simulation result contract enforcement
// ---------------------------------------------------------------------------

export function enforceSimulationResultContract(result: SimulationResult): void {
  if (!result.is_simulation_only) {
    throw new DigitalTwinContractViolation(
      `result ${result.scenario_id}: is_simulation_only must be true`
    );
  }
  if (result.is_production_plan) {
    throw new DigitalTwinContractViolation(
      `result ${result.scenario_id}: is_production_plan must be false`
    );
  }
  if (result.kpi.is_fabricated) {
    throw new DigitalTwinContractViolation(
      `result ${result.scenario_id}: kpi.is_fabricated must be false`
    );
  }
}

// ---------------------------------------------------------------------------
// KPI contract enforcement
// ---------------------------------------------------------------------------

export function enforceKpiContract(kpi: ScenarioKPI): void {
  if (kpi.is_fabricated) {
    throw new DigitalTwinContractViolation('KPI is_fabricated must be false');
  }
}

// ---------------------------------------------------------------------------
// Recommendation contract enforcement
// ---------------------------------------------------------------------------

export function enforceRecommendationContract(rec: TwinRecommendation): void {
  if (!rec.is_proposed_only) {
    throw new DigitalTwinContractViolation(
      `recommendation for ${rec.scenario_id}: is_proposed_only must be true`
    );
  }
  if (rec.is_automatic_application) {
    throw new DigitalTwinContractViolation(
      `recommendation for ${rec.scenario_id}: is_automatic_application must be false`
    );
  }
  if (!rec.review_required) {
    throw new DigitalTwinContractViolation(
      `recommendation for ${rec.scenario_id}: review_required must be true`
    );
  }
}

// ---------------------------------------------------------------------------
// Comparison contract enforcement
// ---------------------------------------------------------------------------

export function enforceComparisonContract(comparison: ScenarioComparison): void {
  if (comparison.is_fabricated) {
    throw new DigitalTwinContractViolation(
      `comparison ${comparison.comparison_id}: is_fabricated must be false`
    );
  }
}

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

/** True when the scenario has no hard constraint failures. */
export function isValidScenario(result: SimulationResult): boolean {
  return result.hard_constraint_failures.length === 0;
}

/** True when the scenario is non-dominated on the Pareto frontier. */
export function isNonDominated(pareto: ParetoCandidate): boolean {
  return pareto.is_non_dominated;
}

/** Unknown KPIs are UNKNOWN — never coerced to zero. */
export function unknownKpiIsNotZero(kpi: ScenarioKPI, field: keyof ScenarioKPI): boolean {
  return kpi.unknowns.includes(field as string)
    ? kpi[field] === null || kpi[field] === undefined
    : true;
}

/** Multi-objective score requires explicit weights for a composite result. */
export function hasWeightedScore(score: MultiObjectiveScore): boolean {
  return score.weighted_score !== null && score.weighted_score !== undefined;
}

/** Summarize a recommendation for display. */
export function summarizeRecommendation(rec: TwinRecommendation): string {
  return (
    `[PROPOSED ONLY] ${rec.recommendation_type}: scenario=${rec.scenario_id} ` +
    `fidelity=${rec.data_fidelity} review_required=${rec.review_required}`
  );
}
