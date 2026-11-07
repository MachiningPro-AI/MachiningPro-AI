/**
 * Level-15 Monitoring Frontend Tests.
 *
 * Tests:
 * - Type contracts
 * - Safety invariants
 * - Separation: planned != actual
 * - Missing data handling
 * - Closed-loop PROPOSED_ONLY
 * - No automatic corrective action
 * - OEE only with complete valid inputs
 */

import { strict as assert } from 'node:assert';
import { describe, it } from 'node:test';

import {
  CLOSED_LOOP_MODE,
  NO_AUTOMATIC_CORRECTIVE_ACTION,
  NO_REAL_MACHINE_WRITE,
} from '../src/types/monitoring.ts';

import {
  MonitoringContractViolation,
  correlationIsNotCausation,
  enforceClosedLoopContract,
  enforceOEEContract,
  enforceObservationContract,
  enforceRecommendationContract,
  enforceRootCauseContract,
  enforceToolFeedbackContract,
  formatCycleTimeDelta,
  missingAlarmDataIsNotZero,
  oeeStatusLabel,
  plannedIsNotActual,
  proposedFeedIsNotMachineOverride,
  qualityFeedbackIsNotAutoChange,
  recommendationIsNotAutoAction,
  toolLifeFeedbackIsNotOffsetWrite,
  toolLifeLabel,
  unknownStateIsNotIdle,
} from '../src/services/monitoring.ts';

// ---------------------------------------------------------------------------
// Module-level constants
// ---------------------------------------------------------------------------

describe('Monitoring module constants', () => {
  it('CLOSED_LOOP_MODE is PROPOSED_ONLY', () => {
    assert.strictEqual(CLOSED_LOOP_MODE, 'PROPOSED_ONLY');
  });
  it('NO_AUTOMATIC_CORRECTIVE_ACTION is true', () => {
    assert.strictEqual(NO_AUTOMATIC_CORRECTIVE_ACTION, true);
  });
  it('NO_REAL_MACHINE_WRITE is true', () => {
    assert.strictEqual(NO_REAL_MACHINE_WRITE, true);
  });
});

// ---------------------------------------------------------------------------
// Observation contract
// ---------------------------------------------------------------------------

describe('Observation contract enforcement', () => {
  it('passes for is_fabricated=false', () => {
    assert.doesNotThrow(() =>
      enforceObservationContract({ is_fabricated: false })
    );
  });
  it('throws for is_fabricated=true', () => {
    assert.throws(
      () => enforceObservationContract({ is_fabricated: true } as any),
      MonitoringContractViolation
    );
  });
  it('throws when is_fabricated is missing', () => {
    assert.throws(
      () => enforceObservationContract({} as any),
      MonitoringContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// OEE contract
// ---------------------------------------------------------------------------

describe('OEE contract enforcement', () => {
  it('passes for CALCULATED with non-null oee', () => {
    assert.doesNotThrow(() =>
      enforceOEEContract({
        oee_id: 'x',
        machine_id: null,
        planned_production_time: 480,
        run_time: 400,
        availability: 0.83,
        ideal_cycle_time: 10,
        total_count: 36,
        performance: 0.9,
        good_count: 32,
        quality: 0.89,
        oee: 0.666,
        status: 'CALCULATED',
        warnings: [],
      })
    );
  });
  it('passes for INSUFFICIENT_DATA with null oee', () => {
    assert.doesNotThrow(() =>
      enforceOEEContract({
        oee_id: 'x',
        machine_id: null,
        planned_production_time: null,
        run_time: null,
        availability: null,
        ideal_cycle_time: null,
        total_count: null,
        performance: null,
        good_count: null,
        quality: null,
        oee: null,
        status: 'INSUFFICIENT_DATA',
        warnings: [],
      })
    );
  });
  it('throws for INSUFFICIENT_DATA with non-null oee', () => {
    assert.throws(
      () =>
        enforceOEEContract({
          oee_id: 'x',
          machine_id: null,
          planned_production_time: null,
          run_time: null,
          availability: null,
          ideal_cycle_time: null,
          total_count: null,
          performance: null,
          good_count: null,
          quality: null,
          oee: 0.5,
          status: 'INSUFFICIENT_DATA',
          warnings: [],
        }),
      MonitoringContractViolation
    );
  });
  it('throws for CALCULATED with null oee', () => {
    assert.throws(
      () =>
        enforceOEEContract({
          oee_id: 'x',
          machine_id: null,
          planned_production_time: 480,
          run_time: 400,
          availability: 0.83,
          ideal_cycle_time: 10,
          total_count: 36,
          performance: 0.9,
          good_count: 32,
          quality: 0.89,
          oee: null,
          status: 'CALCULATED',
          warnings: [],
        }),
      MonitoringContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Tool feedback contract
// ---------------------------------------------------------------------------

describe('Tool feedback contract', () => {
  it('passes for is_automatic_action=false', () => {
    assert.doesNotThrow(() =>
      enforceToolFeedbackContract({
        feedback_id: 'x',
        tool_id: 'T01',
        predicted_life: 100,
        observed_life: 90,
        status: 'TOOL_LIFE_SHORTER_THAN_EXPECTED',
        relative_delta: -0.1,
        data_quality: 'RAW',
        is_automatic_action: false,
      })
    );
  });
  it('throws for is_automatic_action=true', () => {
    assert.throws(
      () =>
        enforceToolFeedbackContract({
          feedback_id: 'x',
          tool_id: 'T01',
          predicted_life: 100,
          observed_life: 90,
          status: 'TOOL_LIFE_SHORTER_THAN_EXPECTED',
          relative_delta: -0.1,
          data_quality: 'RAW',
          is_automatic_action: true as any,
        }),
      MonitoringContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Recommendation contract
// ---------------------------------------------------------------------------

describe('Recommendation contract', () => {
  it('passes for valid recommendation', () => {
    assert.doesNotThrow(() =>
      enforceRecommendationContract({
        recommendation_id: 'r1',
        recommendation_type: 'REVIEW_TOOL_LIFE',
        candidate_ref: null,
        rationale: 'Tool life shorter than expected',
        requires_review: true,
        is_automatic_action: false,
        is_applied: false,
      })
    );
  });
  it('throws when requires_review=false', () => {
    assert.throws(
      () =>
        enforceRecommendationContract({
          recommendation_id: 'r1',
          recommendation_type: 'REVIEW_TOOL_LIFE',
          candidate_ref: null,
          rationale: '',
          requires_review: false as any,
          is_automatic_action: false,
          is_applied: false,
        }),
      MonitoringContractViolation
    );
  });
  it('throws when is_automatic_action=true', () => {
    assert.throws(
      () =>
        enforceRecommendationContract({
          recommendation_id: 'r1',
          recommendation_type: 'REVIEW_TOOL_LIFE',
          candidate_ref: null,
          rationale: '',
          requires_review: true,
          is_automatic_action: true as any,
          is_applied: false,
        }),
      MonitoringContractViolation
    );
  });
  it('throws when is_applied=true', () => {
    assert.throws(
      () =>
        enforceRecommendationContract({
          recommendation_id: 'r1',
          recommendation_type: 'REVIEW_TOOL_LIFE',
          candidate_ref: null,
          rationale: '',
          requires_review: true,
          is_automatic_action: false,
          is_applied: true as any,
        }),
      MonitoringContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Root cause contract
// ---------------------------------------------------------------------------

describe('Root cause contract', () => {
  it('passes for CANDIDATE', () => {
    assert.doesNotThrow(() =>
      enforceRootCauseContract({
        candidate_id: 'c1',
        status: 'CANDIDATE',
        observation_ref: null,
        comparison_ref: null,
        evidence: [],
        correlated_deviations: [],
        correlated_alarms: [],
        suggested_direction: 'REVIEW_MAINTENANCE',
        is_confirmed: false,
        is_causal_proof: false,
      })
    );
  });
  it('throws when is_confirmed=true', () => {
    assert.throws(
      () =>
        enforceRootCauseContract({
          candidate_id: 'c1',
          status: 'CANDIDATE',
          observation_ref: null,
          comparison_ref: null,
          evidence: [],
          correlated_deviations: [],
          correlated_alarms: [],
          suggested_direction: '',
          is_confirmed: true as any,
          is_causal_proof: false,
        }),
      MonitoringContractViolation
    );
  });
  it('throws when is_causal_proof=true', () => {
    assert.throws(
      () =>
        enforceRootCauseContract({
          candidate_id: 'c1',
          status: 'CANDIDATE',
          observation_ref: null,
          comparison_ref: null,
          evidence: [],
          correlated_deviations: [],
          correlated_alarms: [],
          suggested_direction: '',
          is_confirmed: false,
          is_causal_proof: true as any,
        }),
      MonitoringContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Closed-loop proposal contract
// ---------------------------------------------------------------------------

describe('Closed-loop proposal contract', () => {
  it('passes for valid proposal', () => {
    assert.doesNotThrow(() =>
      enforceClosedLoopContract({
        proposal_id: 'p1',
        proposal_type: 'NEW_FEED_CANDIDATE',
        observation_ref: null,
        comparison_ref: null,
        proposed_value: 150.0,
        current_value: 200.0,
        rationale: 'cycle time high',
        is_proposed_only: true,
        is_automatic_write: false,
      })
    );
  });
  it('throws when is_proposed_only=false', () => {
    assert.throws(
      () =>
        enforceClosedLoopContract({
          proposal_id: 'p1',
          proposal_type: 'NEW_FEED_CANDIDATE',
          observation_ref: null,
          comparison_ref: null,
          proposed_value: 150.0,
          current_value: 200.0,
          rationale: '',
          is_proposed_only: false as any,
          is_automatic_write: false,
        }),
      MonitoringContractViolation
    );
  });
  it('throws when is_automatic_write=true', () => {
    assert.throws(
      () =>
        enforceClosedLoopContract({
          proposal_id: 'p1',
          proposal_type: 'NEW_FEED_CANDIDATE',
          observation_ref: null,
          comparison_ref: null,
          proposed_value: 150.0,
          current_value: 200.0,
          rationale: '',
          is_proposed_only: true,
          is_automatic_write: true as any,
        }),
      MonitoringContractViolation
    );
  });
});

// ---------------------------------------------------------------------------
// Separation and negative tests
// ---------------------------------------------------------------------------

describe('Separation and negative tests', () => {
  it('planned value is not actual observation — different values', () => {
    assert.strictEqual(plannedIsNotActual(10.0, 12.0), true);
  });
  it('plannedIsNotActual handles nulls', () => {
    assert.strictEqual(plannedIsNotActual(null, null), true);
    assert.strictEqual(plannedIsNotActual(10.0, null), true);
    assert.strictEqual(plannedIsNotActual(null, 12.0), true);
  });
  it('missing alarm data is not zero alarms', () => {
    assert.strictEqual(missingAlarmDataIsNotZero(null), false);
    assert.strictEqual(missingAlarmDataIsNotZero(undefined), false);
    assert.strictEqual(missingAlarmDataIsNotZero([]), true);
  });
  it('correlation is not causation', () => {
    assert.strictEqual(correlationIsNotCausation(), false);
  });
  it('recommendation is not auto-action', () => {
    assert.strictEqual(recommendationIsNotAutoAction(), false);
  });
  it('proposed feed is not machine override', () => {
    assert.strictEqual(proposedFeedIsNotMachineOverride(), false);
  });
  it('tool-life feedback is not tool-offset write', () => {
    assert.strictEqual(toolLifeFeedbackIsNotOffsetWrite(), false);
  });
  it('quality feedback is not automatic process change', () => {
    assert.strictEqual(qualityFeedbackIsNotAutoChange(), false);
  });
  it('UNKNOWN cycle state is not IDLE', () => {
    assert.strictEqual(unknownStateIsNotIdle('UNKNOWN'), true);
  });
});

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

describe('Display helpers', () => {
  it('formatCycleTimeDelta for positive delta', () => {
    const result = formatCycleTimeDelta(2.0, 0.2);
    assert.ok(result.includes('+'));
  });
  it('formatCycleTimeDelta for null', () => {
    assert.strictEqual(formatCycleTimeDelta(null, null), 'UNKNOWN');
  });
  it('oeeStatusLabel for INSUFFICIENT_DATA', () => {
    assert.strictEqual(oeeStatusLabel(null, 'INSUFFICIENT_DATA'), 'INSUFFICIENT_DATA');
  });
  it('oeeStatusLabel for CALCULATED', () => {
    const result = oeeStatusLabel(0.75, 'CALCULATED');
    assert.ok(result.includes('%'));
  });
  it('toolLifeLabel known status', () => {
    assert.strictEqual(
      toolLifeLabel('TOOL_LIFE_SHORTER_THAN_EXPECTED'),
      'Shorter Than Expected'
    );
    assert.strictEqual(toolLifeLabel('INSUFFICIENT_DATA'), 'Insufficient Data');
  });
  it('toolLifeLabel unknown status falls back to UNKNOWN', () => {
    assert.strictEqual(toolLifeLabel('SOMETHING_ELSE'), 'UNKNOWN');
  });
});
