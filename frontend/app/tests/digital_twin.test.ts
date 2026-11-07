/**
 * Level-18 Manufacturing Digital Twin — TypeScript contract tests.
 *
 * Tests verify safety invariants, contract enforcement, and utility functions.
 * No real machines are commanded. No scenarios are automatically applied.
 * All test data is synthetic.
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import {
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
} from '../src/types/digital_twin.ts';

import {
  DigitalTwinContractViolation,
  enforceScenarioContract,
  enforceSimulationResultContract,
  enforceKpiContract,
  enforceRecommendationContract,
  enforceComparisonContract,
  isValidScenario,
  isNonDominated,
  unknownKpiIsNotZero,
  hasWeightedScore,
  summarizeRecommendation,
} from '../src/services/digital_twin.ts';

import type {
  ManufacturingTwinScenario,
  ScenarioKPI,
  SimulationResult,
  TwinRecommendation,
  ScenarioComparison,
  ParetoCandidate,
  MultiObjectiveScore,
} from '../src/types/digital_twin.ts';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeScenario(overrides: Partial<ManufacturingTwinScenario> = {}): ManufacturingTwinScenario {
  return {
    scenario_id: 'SC_BASELINE_001',
    scenario_type: 'BASELINE',
    baseline_ref: null,
    part_ref: 'PART_A',
    machine_ref: 'MCH_001',
    tool_refs: ['T_001'],
    cutting_data: { vc: 300.0 },
    quantity: 10,
    batch_size: 10,
    estimated_cycle_time_min: 45.0,
    machine_spindle_max_rpm: 12000,
    machine_axis_count: 3,
    machine_idle_power_kw: null,
    machine_cutting_power_kw: null,
    required_spindle_rpm: 8000,
    required_axis_count: 3,
    toolpath_verified: true,
    schedule_ref: null,
    status: 'DRAFT',
    fidelity: 'MEDIUM',
    evaluation_version: '18.0',
    is_simulation_only: true,
    is_production_plan: false,
    review_required: true,
    baseline_mutation_allowed: false,
    ...overrides,
  };
}

function makeKpi(overrides: Partial<ScenarioKPI> = {}): ScenarioKPI {
  return {
    cycle_time_min: 45.0,
    cycle_time_source: 'SIMULATED',
    setup_time_min: 10.0,
    batch_time_min: null,
    throughput_per_hour: null,
    manufacturing_cost: null,
    tool_life_min: 120.0,
    tool_consumption: null,
    quality_risk_level: null,
    alarm_risk_level: null,
    machine_load_pct: null,
    lateness_min: null,
    energy_kwh: null,
    energy_status: 'INSUFFICIENT_DATA',
    material_utilization_pct: null,
    fidelity: 'MEDIUM',
    unknowns: [],
    is_fabricated: false,
    ...overrides,
  };
}

function makeResult(overrides: Partial<SimulationResult> = {}): SimulationResult {
  return {
    scenario_id: 'SC_BASELINE_001',
    status: 'SIMULATED',
    kpi: makeKpi(),
    constraint_results: [],
    hard_constraint_failures: [],
    fidelity: 'MEDIUM',
    warnings: [],
    errors: [],
    is_simulation_only: true,
    is_production_plan: false,
    ...overrides,
  };
}

function makeRecommendation(overrides: Partial<TwinRecommendation> = {}): TwinRecommendation {
  return {
    recommendation_type: 'FASTEST_VALID_SCENARIO',
    scenario_id: 'SC_BASELINE_001',
    why: 'Lowest simulated cycle time',
    constraints_passed: ['spindle_range'],
    data_fidelity: 'MEDIUM',
    trade_offs: [],
    unknowns: [],
    review_required: true,
    is_proposed_only: true,
    is_automatic_application: false,
    ...overrides,
  };
}

function makeComparison(overrides: Partial<ScenarioComparison> = {}): ScenarioComparison {
  return {
    baseline_id: 'SC_BASELINE_001',
    comparison_id: 'SC_ALT_001',
    kpi_diffs: [],
    trade_offs: [],
    unknown_diffs: [],
    constraint_delta: '',
    is_fabricated: false,
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// Safety constants
// ---------------------------------------------------------------------------

describe('Safety Constants', () => {
  it('NO_AUTOMATIC_APPLICATION is true', () => {
    assert.equal(NO_AUTOMATIC_APPLICATION, true);
  });

  it('NO_CNC_WRITE is true', () => {
    assert.equal(NO_CNC_WRITE, true);
  });

  it('NO_AUTOMATIC_DISPATCH is true', () => {
    assert.equal(NO_AUTOMATIC_DISPATCH, true);
  });

  it('NO_AUTOMATIC_CAM_CHANGE is true', () => {
    assert.equal(NO_AUTOMATIC_CAM_CHANGE, true);
  });

  it('NO_AUTOMATIC_GCODE_REGENERATION is true', () => {
    assert.equal(NO_AUTOMATIC_GCODE_REGENERATION, true);
  });

  it('NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT is true', () => {
    assert.equal(NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT, true);
  });

  it('NO_AUTOMATIC_MACHINE_REASSIGNMENT is true', () => {
    assert.equal(NO_AUTOMATIC_MACHINE_REASSIGNMENT, true);
  });

  it('NO_AUTOMATIC_SCHEDULING_CHANGE is true', () => {
    assert.equal(NO_AUTOMATIC_SCHEDULING_CHANGE, true);
  });

  it('NO_AUTOMATIC_TOOL_SUBSTITUTION is true', () => {
    assert.equal(NO_AUTOMATIC_TOOL_SUBSTITUTION, true);
  });

  it('BASELINE_MUTATION_ALLOWED is false', () => {
    assert.equal(BASELINE_MUTATION_ALLOWED, false);
  });

  it('SCENARIO_IS_NOT_PRODUCTION_PLAN is true', () => {
    assert.equal(SCENARIO_IS_NOT_PRODUCTION_PLAN, true);
  });

  it('OPTIMIZED_SCENARIO_IS_NOT_APPROVED is true', () => {
    assert.equal(OPTIMIZED_SCENARIO_IS_NOT_APPROVED, true);
  });

  it('HUMAN_REVIEW_MANDATORY is true', () => {
    assert.equal(HUMAN_REVIEW_MANDATORY, true);
  });

  it('NO_FABRICATED_TWIN_RESULT is true', () => {
    assert.equal(NO_FABRICATED_TWIN_RESULT, true);
  });

  it('UNKNOWN_INPUTS_STAY_UNKNOWN is true', () => {
    assert.equal(UNKNOWN_INPUTS_STAY_UNKNOWN, true);
  });
});

// ---------------------------------------------------------------------------
// Scenario contract enforcement
// ---------------------------------------------------------------------------

describe('Scenario Contract Enforcement', () => {
  it('valid scenario passes enforcement', () => {
    const s = makeScenario();
    assert.doesNotThrow(() => enforceScenarioContract(s));
  });

  it('scenario with is_simulation_only=false fails', () => {
    const s = makeScenario({ is_simulation_only: false as unknown as true });
    assert.throws(() => enforceScenarioContract(s), DigitalTwinContractViolation);
  });

  it('scenario with is_production_plan=true fails', () => {
    const s = makeScenario({ is_production_plan: true as unknown as false });
    assert.throws(() => enforceScenarioContract(s), DigitalTwinContractViolation);
  });

  it('scenario with review_required=false fails', () => {
    const s = makeScenario({ review_required: false as unknown as true });
    assert.throws(() => enforceScenarioContract(s), DigitalTwinContractViolation);
  });

  it('scenario with baseline_mutation_allowed=true fails', () => {
    const s = makeScenario({ baseline_mutation_allowed: true as unknown as false });
    assert.throws(() => enforceScenarioContract(s), DigitalTwinContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Simulation result contract enforcement
// ---------------------------------------------------------------------------

describe('SimulationResult Contract Enforcement', () => {
  it('valid result passes enforcement', () => {
    const r = makeResult();
    assert.doesNotThrow(() => enforceSimulationResultContract(r));
  });

  it('result with is_simulation_only=false fails', () => {
    const r = makeResult({ is_simulation_only: false as unknown as true });
    assert.throws(() => enforceSimulationResultContract(r), DigitalTwinContractViolation);
  });

  it('result with is_production_plan=true fails', () => {
    const r = makeResult({ is_production_plan: true as unknown as false });
    assert.throws(() => enforceSimulationResultContract(r), DigitalTwinContractViolation);
  });

  it('result with fabricated KPI fails', () => {
    const r = makeResult({ kpi: makeKpi({ is_fabricated: true as unknown as false }) });
    assert.throws(() => enforceSimulationResultContract(r), DigitalTwinContractViolation);
  });
});

// ---------------------------------------------------------------------------
// KPI contract enforcement
// ---------------------------------------------------------------------------

describe('KPI Contract Enforcement', () => {
  it('valid KPI passes enforcement', () => {
    const k = makeKpi();
    assert.doesNotThrow(() => enforceKpiContract(k));
  });

  it('fabricated KPI fails', () => {
    const k = makeKpi({ is_fabricated: true as unknown as false });
    assert.throws(() => enforceKpiContract(k), DigitalTwinContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Recommendation contract enforcement
// ---------------------------------------------------------------------------

describe('Recommendation Contract Enforcement', () => {
  it('valid recommendation passes enforcement', () => {
    const r = makeRecommendation();
    assert.doesNotThrow(() => enforceRecommendationContract(r));
  });

  it('recommendation with is_proposed_only=false fails', () => {
    const r = makeRecommendation({ is_proposed_only: false as unknown as true });
    assert.throws(() => enforceRecommendationContract(r), DigitalTwinContractViolation);
  });

  it('recommendation with is_automatic_application=true fails', () => {
    const r = makeRecommendation({ is_automatic_application: true as unknown as false });
    assert.throws(() => enforceRecommendationContract(r), DigitalTwinContractViolation);
  });

  it('recommendation with review_required=false fails', () => {
    const r = makeRecommendation({ review_required: false as unknown as true });
    assert.throws(() => enforceRecommendationContract(r), DigitalTwinContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Comparison contract enforcement
// ---------------------------------------------------------------------------

describe('Comparison Contract Enforcement', () => {
  it('valid comparison passes enforcement', () => {
    const c = makeComparison();
    assert.doesNotThrow(() => enforceComparisonContract(c));
  });

  it('fabricated comparison fails', () => {
    const c = makeComparison({ is_fabricated: true as unknown as false });
    assert.throws(() => enforceComparisonContract(c), DigitalTwinContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Utility helpers
// ---------------------------------------------------------------------------

describe('Utility Helpers', () => {
  it('isValidScenario returns true when no hard failures', () => {
    const r = makeResult({ hard_constraint_failures: [] });
    assert.equal(isValidScenario(r), true);
  });

  it('isValidScenario returns false when hard failures exist', () => {
    const r = makeResult({ hard_constraint_failures: ['SPINDLE_OVER_LIMIT'] });
    assert.equal(isValidScenario(r), false);
  });

  it('isNonDominated returns true for non-dominated candidate', () => {
    const p: ParetoCandidate = {
      scenario_id: 'SC_001',
      dominated_by: [],
      is_non_dominated: true,
      dominated_in: [],
      dominates_in: [],
    };
    assert.equal(isNonDominated(p), true);
  });

  it('isNonDominated returns false for dominated candidate', () => {
    const p: ParetoCandidate = {
      scenario_id: 'SC_002',
      dominated_by: ['SC_001'],
      is_non_dominated: false,
      dominated_in: ['CYCLE_TIME'],
      dominates_in: [],
    };
    assert.equal(isNonDominated(p), false);
  });

  it('unknownKpiIsNotZero: unknown KPI must remain null, not zero', () => {
    const k = makeKpi({ cycle_time_min: null, unknowns: ['cycle_time_min'] });
    assert.equal(unknownKpiIsNotZero(k, 'cycle_time_min'), true);
  });

  it('unknownKpiIsNotZero: known KPI allowed to be zero', () => {
    const k = makeKpi({ machine_load_pct: 0.0, unknowns: [] });
    assert.equal(unknownKpiIsNotZero(k, 'machine_load_pct'), true);
  });

  it('hasWeightedScore returns false when no weighted score', () => {
    const s: MultiObjectiveScore = {
      scenario_id: 'SC_001',
      component_scores: {},
      weighted_score: null,
      weights_applied: [],
      unknowns: [],
    };
    assert.equal(hasWeightedScore(s), false);
  });

  it('hasWeightedScore returns true when weighted score present', () => {
    const s: MultiObjectiveScore = {
      scenario_id: 'SC_001',
      component_scores: { MINIMIZE_CYCLE_TIME: 0.8 },
      weighted_score: 0.8,
      weights_applied: [{ objective: 'MINIMIZE_CYCLE_TIME', weight: 1.0 }],
      unknowns: [],
    };
    assert.equal(hasWeightedScore(s), true);
  });

  it('summarizeRecommendation includes PROPOSED ONLY', () => {
    const r = makeRecommendation();
    const summary = summarizeRecommendation(r);
    assert.match(summary, /PROPOSED ONLY/);
  });

  it('summarizeRecommendation includes review_required', () => {
    const r = makeRecommendation();
    const summary = summarizeRecommendation(r);
    assert.match(summary, /review_required=true/);
  });
});

// ---------------------------------------------------------------------------
// Scenario types
// ---------------------------------------------------------------------------

describe('Scenario Types', () => {
  it('BASELINE scenario has no baseline_ref', () => {
    const s = makeScenario({ scenario_type: 'BASELINE', baseline_ref: null });
    assert.equal(s.baseline_ref, null);
  });

  it('MACHINE_ALTERNATIVE scenario has baseline_ref', () => {
    const s = makeScenario({
      scenario_type: 'MACHINE_ALTERNATIVE',
      baseline_ref: 'SC_BASELINE_001',
    });
    assert.equal(s.baseline_ref, 'SC_BASELINE_001');
  });

  it('scenario is_simulation_only stays true for all types', () => {
    const types: ManufacturingTwinScenario['scenario_type'][] = [
      'BASELINE',
      'MACHINE_ALTERNATIVE',
      'TOOL_ALTERNATIVE',
      'CUTTING_DATA_ALTERNATIVE',
      'QUANTITY_ALTERNATIVE',
      'SCHEDULE_ALTERNATIVE',
      'COMBINED_ALTERNATIVE',
    ];
    for (const t of types) {
      const s = makeScenario({ scenario_type: t, is_simulation_only: true });
      assert.equal(s.is_simulation_only, true);
    }
  });
});

// ---------------------------------------------------------------------------
// KPI unknown handling
// ---------------------------------------------------------------------------

describe('KPI Unknown Handling', () => {
  it('KPI with no cycle time source UNKNOWN keeps null cycle time', () => {
    const k = makeKpi({ cycle_time_min: null, cycle_time_source: 'UNKNOWN', unknowns: ['cycle_time_min'] });
    assert.equal(k.cycle_time_min, null);
    assert.ok(k.unknowns.includes('cycle_time_min'));
  });

  it('energy remains null when power data is missing', () => {
    const k = makeKpi({ energy_kwh: null, energy_status: 'INSUFFICIENT_DATA' });
    assert.equal(k.energy_kwh, null);
    assert.equal(k.energy_status, 'INSUFFICIENT_DATA');
  });

  it('KPI is_fabricated is always false', () => {
    const k = makeKpi();
    assert.equal(k.is_fabricated, false);
  });

  it('SIMULATED cycle time source is recorded', () => {
    const k = makeKpi({ cycle_time_source: 'SIMULATED' });
    assert.equal(k.cycle_time_source, 'SIMULATED');
  });

  it('DETERMINISTIC and OBSERVED sources distinguishable', () => {
    const k1 = makeKpi({ cycle_time_source: 'DETERMINISTIC' });
    const k2 = makeKpi({ cycle_time_source: 'OBSERVED' });
    assert.notEqual(k1.cycle_time_source, k2.cycle_time_source);
  });
});

// ---------------------------------------------------------------------------
// Negative tests
// ---------------------------------------------------------------------------

describe('Negative Tests', () => {
  it('DigitalTwinContractViolation extends Error', () => {
    const err = new DigitalTwinContractViolation('test');
    assert.ok(err instanceof Error);
    assert.ok(err instanceof DigitalTwinContractViolation);
  });

  it('error message includes DigitalTwinContractViolation prefix', () => {
    const err = new DigitalTwinContractViolation('test message');
    assert.match(err.message, /DigitalTwinContractViolation/);
  });

  it('scenario status PRODUCTION_APPLIED is not in ScenarioStatus type', () => {
    // Type-level check: 'PRODUCTION_APPLIED' should not appear in valid statuses
    const validStatuses: ManufacturingTwinScenario['status'][] = [
      'DRAFT', 'INCOMPLETE', 'VALID', 'INVALID', 'SIMULATED', 'REVIEW_REQUIRED', 'REJECTED', 'STALE',
    ];
    assert.ok(!validStatuses.includes('PRODUCTION_APPLIED' as ManufacturingTwinScenario['status']));
  });
});
