/**
 * Level-16 Adaptive Manufacturing Intelligence frontend tests.
 * Uses node:test + node:assert/strict (Node.js native test runner).
 */

import { describe, it } from 'node:test';
import assert from 'node:assert/strict';

import type {
  AdaptiveRecommendation,
  DriftReport,
  ManufacturingLearningRecord,
  ModelSpec,
  PredictionResult,
  QualityRiskResult,
  WhatIfScenario,
} from '../src/types/adaptive.ts';

import {
  AdaptiveContractViolation,
  enforceRecordContract,
  enforcePredictionContract,
  enforceRecommendationContract,
  enforceWhatIfContract,
  enforceModelContract,
  enforceRiskContract,
  predictionIsNotMeasuredFact,
  recommendationIsNotApprovedChange,
  correlationIsNotCausation,
  outOfDomainIsNotPrediction,
  driftIsNotAutoRetrain,
  isSufficientFidelity,
  summarizeRecommendation,
  RECOMMENDATION_ONLY,
  HUMAN_REVIEW_MANDATORY,
  PREDICTION_IS_NOT_MEASURED_FACT,
  RECOMMENDATION_IS_NOT_APPROVED_CHANGE,
  CORRELATION_IS_NOT_CAUSATION,
  NO_AUTOMATIC_CNC_CHANGE,
  NO_AUTOMATIC_FEED_OVERRIDE,
  NO_AUTOMATIC_SPINDLE_OVERRIDE,
  NO_AUTOMATIC_TOOL_OFFSET_CHANGE,
  NO_AUTOMATIC_WORK_OFFSET_CHANGE,
} from '../src/services/adaptive.ts';

// ---------------------------------------------------------------------------
// Module constants
// ---------------------------------------------------------------------------

describe('Module safety constants', () => {
  it('RECOMMENDATION_ONLY is true', () => {
    assert.equal(RECOMMENDATION_ONLY, true);
  });

  it('HUMAN_REVIEW_MANDATORY is true', () => {
    assert.equal(HUMAN_REVIEW_MANDATORY, true);
  });

  it('PREDICTION_IS_NOT_MEASURED_FACT is true', () => {
    assert.equal(PREDICTION_IS_NOT_MEASURED_FACT, true);
  });

  it('RECOMMENDATION_IS_NOT_APPROVED_CHANGE is true', () => {
    assert.equal(RECOMMENDATION_IS_NOT_APPROVED_CHANGE, true);
  });

  it('CORRELATION_IS_NOT_CAUSATION is true', () => {
    assert.equal(CORRELATION_IS_NOT_CAUSATION, true);
  });

  it('NO_AUTOMATIC_CNC_CHANGE is true', () => {
    assert.equal(NO_AUTOMATIC_CNC_CHANGE, true);
  });

  it('NO_AUTOMATIC_FEED_OVERRIDE is true', () => {
    assert.equal(NO_AUTOMATIC_FEED_OVERRIDE, true);
  });

  it('NO_AUTOMATIC_SPINDLE_OVERRIDE is true', () => {
    assert.equal(NO_AUTOMATIC_SPINDLE_OVERRIDE, true);
  });

  it('NO_AUTOMATIC_TOOL_OFFSET_CHANGE is true', () => {
    assert.equal(NO_AUTOMATIC_TOOL_OFFSET_CHANGE, true);
  });

  it('NO_AUTOMATIC_WORK_OFFSET_CHANGE is true', () => {
    assert.equal(NO_AUTOMATIC_WORK_OFFSET_CHANGE, true);
  });
});

// ---------------------------------------------------------------------------
// Record contract
// ---------------------------------------------------------------------------

describe('Learning record contract', () => {
  const validRecord: ManufacturingLearningRecord = {
    record_id: 'TEST_001',
    part_family: 'DISC',
    material: 'AL_6082_T6',
    machine_class: 'CNC_TURNING_CENTER',
    operation_type: 'FINISH_TURNING',
    planned_cutting_data: { vc: 300 },
    observed_cutting_data: { vc: 298 },
    planned_cycle_time: 120,
    actual_cycle_time: 115,
    planned_tool_life: 80,
    actual_tool_life: 72,
    quality_result: 'PASS',
    alarm_summary: 'NONE',
    source: 'HISTORICAL_DATA',
    provenance: 'abc123',
    data_quality: 'VALIDATED',
    timestamp: '2026-11-07T00:00:00Z',
    is_fabricated: false,
    is_test_only: true,
  };

  it('passes contract for valid record', () => {
    assert.doesNotThrow(() => enforceRecordContract(validRecord));
  });

  it('rejects fabricated record', () => {
    const bad = { ...validRecord, is_fabricated: true } as unknown as ManufacturingLearningRecord;
    assert.throws(() => enforceRecordContract(bad), AdaptiveContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Prediction contract
// ---------------------------------------------------------------------------

describe('Prediction contract', () => {
  const validPred: PredictionResult = {
    prediction_id: 'PRED_001',
    target: 'CYCLE_TIME',
    model_ref: 'median_v1',
    engineering_baseline: 120,
    historical_prediction: 116.5,
    predicted_value: 116.5,
    fidelity: 'HIGH',
    sample_count: 8,
    similar_case_ids: [],
    uncertainty_description: 'Historical median',
    warnings: [],
    is_fabricated: false,
    out_of_domain: false,
  };

  it('passes contract for valid prediction', () => {
    assert.doesNotThrow(() => enforcePredictionContract(validPred));
  });

  it('rejects fabricated prediction', () => {
    const bad = { ...validPred, is_fabricated: true } as unknown as PredictionResult;
    assert.throws(() => enforcePredictionContract(bad), AdaptiveContractViolation);
  });

  it('INSUFFICIENT fidelity with value triggers gate', () => {
    const insuffPred: PredictionResult = {
      ...validPred,
      fidelity: 'INSUFFICIENT',
      predicted_value: 100,
    };
    assert.throws(() => predictionIsNotMeasuredFact(insuffPred), AdaptiveContractViolation);
  });

  it('null predicted_value with INSUFFICIENT fidelity does not throw', () => {
    const insuffPred: PredictionResult = {
      ...validPred,
      fidelity: 'INSUFFICIENT',
      predicted_value: null,
    };
    assert.doesNotThrow(() => predictionIsNotMeasuredFact(insuffPred));
  });

  it('out-of-domain prediction with value throws', () => {
    const oodPred: PredictionResult = {
      ...validPred,
      out_of_domain: true,
      predicted_value: 999,
    };
    assert.throws(() => outOfDomainIsNotPrediction(oodPred), AdaptiveContractViolation);
  });

  it('out-of-domain prediction without value does not throw', () => {
    const oodPred: PredictionResult = {
      ...validPred,
      out_of_domain: true,
      predicted_value: null,
    };
    assert.doesNotThrow(() => outOfDomainIsNotPrediction(oodPred));
  });
});

// ---------------------------------------------------------------------------
// Recommendation contract
// ---------------------------------------------------------------------------

describe('Recommendation contract', () => {
  const validRec: AdaptiveRecommendation = {
    recommendation_id: 'REC_001',
    recommendation_type: 'VC_REVIEW_CANDIDATE',
    current_state: { vc: 300 },
    proposed_state: { vc: 320 },
    objective: 'MINIMIZE_CYCLE_TIME',
    evidence: ['Improvement 5%'],
    model_ref: null,
    sample_count: 8,
    fidelity: 'HIGH',
    predicted_effect: { cycle_time_reduction_pct: 0.05 },
    constraints: [],
    warnings: [],
    review_required: true,
    status: 'PROPOSED',
    is_automatic_application: false,
  };

  it('passes contract for valid recommendation', () => {
    assert.doesNotThrow(() => enforceRecommendationContract(validRec));
  });

  it('rejects is_automatic_application=true', () => {
    const bad = { ...validRec, is_automatic_application: true } as unknown as AdaptiveRecommendation;
    assert.throws(() => enforceRecommendationContract(bad), AdaptiveContractViolation);
  });

  it('rejects review_required=false', () => {
    const bad = { ...validRec, review_required: false } as unknown as AdaptiveRecommendation;
    assert.throws(() => enforceRecommendationContract(bad), AdaptiveContractViolation);
  });

  it('status APPLIED_TO_MACHINE is not allowed', () => {
    const bad = { ...validRec, status: 'APPLIED_TO_MACHINE' as typeof validRec.status };
    assert.throws(() => recommendationIsNotApprovedChange(bad as AdaptiveRecommendation), AdaptiveContractViolation);
  });

  it('status PROPOSED passes guard', () => {
    assert.doesNotThrow(() => recommendationIsNotApprovedChange(validRec));
  });

  it('status ACCEPTED_FOR_ENGINEERING_STUDY passes guard', () => {
    const accepted: AdaptiveRecommendation = { ...validRec, status: 'ACCEPTED_FOR_ENGINEERING_STUDY' };
    assert.doesNotThrow(() => recommendationIsNotApprovedChange(accepted));
  });

  it('summarizeRecommendation returns expected fields', () => {
    const summary = summarizeRecommendation(validRec);
    assert.ok(summary.includes('VC_REVIEW_CANDIDATE'));
    assert.ok(summary.includes('review_required=true'));
    assert.ok(summary.includes('PROPOSED'));
  });
});

// ---------------------------------------------------------------------------
// What-if contract
// ---------------------------------------------------------------------------

describe('What-if contract', () => {
  const validScenario: WhatIfScenario = {
    scenario_id: 'WHATIF_001',
    description: 'Vc +5%',
    parameter_changes: { vc_change_pct: 0.05 },
    baseline_values: { vc: 300 },
    predicted_outputs: { predicted_cycle_time: 112 },
    status: 'PREDICTED_IMPROVEMENT',
    fidelity: 'MEDIUM',
    mutates_baseline: false,
    sample_count: 8,
    warnings: [],
  };

  it('passes contract for valid what-if scenario', () => {
    assert.doesNotThrow(() => enforceWhatIfContract(validScenario));
  });

  it('rejects mutates_baseline=true', () => {
    const bad = { ...validScenario, mutates_baseline: true } as unknown as WhatIfScenario;
    assert.throws(() => enforceWhatIfContract(bad), AdaptiveContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Model contract
// ---------------------------------------------------------------------------

describe('Model contract', () => {
  const validSpec: ModelSpec = {
    model_id: 'median_cycle_time',
    version: '1.0',
    target: 'CYCLE_TIME',
    training_data_hash: 'abc123',
    sample_count: 8,
    train_mae: null,
    validation_mae: 4.5,
    metrics: { validation_mae: 4.5 },
    limitations: [],
    status: 'VALIDATED',
    is_fabricated_accuracy: false,
  };

  it('passes contract for valid model spec', () => {
    assert.doesNotThrow(() => enforceModelContract(validSpec));
  });

  it('rejects is_fabricated_accuracy=true', () => {
    const bad = { ...validSpec, is_fabricated_accuracy: true } as unknown as ModelSpec;
    assert.throws(() => enforceModelContract(bad), AdaptiveContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Risk contract
// ---------------------------------------------------------------------------

describe('Risk contract', () => {
  const validResult: QualityRiskResult = {
    prediction_id: 'RISK_001',
    risk_level: 'LOW',
    reject_rate: 0.0,
    sample_count: 8,
    fidelity: 'HIGH',
    factors: ['reject_rate=0.000'],
    warnings: [],
    is_fabricated: false,
  };

  it('passes contract for valid risk result', () => {
    assert.doesNotThrow(() => enforceRiskContract(validResult));
  });

  it('rejects fabricated risk', () => {
    const bad = { ...validResult, is_fabricated: true } as unknown as QualityRiskResult;
    assert.throws(() => enforceRiskContract(bad), AdaptiveContractViolation);
  });
});

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

describe('Utility helpers', () => {
  it('isSufficientFidelity returns true for HIGH fidelity non-fabricated', () => {
    const pred: PredictionResult = {
      prediction_id: 'P1',
      target: 'CYCLE_TIME',
      model_ref: null,
      engineering_baseline: null,
      historical_prediction: 115,
      predicted_value: 115,
      fidelity: 'HIGH',
      sample_count: 10,
      similar_case_ids: [],
      uncertainty_description: '',
      warnings: [],
      is_fabricated: false,
      out_of_domain: false,
    };
    assert.equal(isSufficientFidelity(pred), true);
  });

  it('isSufficientFidelity returns false for INSUFFICIENT fidelity', () => {
    const pred: PredictionResult = {
      prediction_id: 'P2',
      target: 'CYCLE_TIME',
      model_ref: null,
      engineering_baseline: null,
      historical_prediction: null,
      predicted_value: null,
      fidelity: 'INSUFFICIENT',
      sample_count: 0,
      similar_case_ids: [],
      uncertainty_description: '',
      warnings: [],
      is_fabricated: false,
      out_of_domain: false,
    };
    assert.equal(isSufficientFidelity(pred), false);
  });

  it('isSufficientFidelity returns false for out-of-domain', () => {
    const pred: PredictionResult = {
      prediction_id: 'P3',
      target: 'CYCLE_TIME',
      model_ref: null,
      engineering_baseline: null,
      historical_prediction: 200,
      predicted_value: 200,
      fidelity: 'LOW',
      sample_count: 3,
      similar_case_ids: [],
      uncertainty_description: '',
      warnings: [],
      is_fabricated: false,
      out_of_domain: true,
    };
    assert.equal(isSufficientFidelity(pred), false);
  });
});

// ---------------------------------------------------------------------------
// Drift contract
// ---------------------------------------------------------------------------

describe('Drift contract', () => {
  it('drift detection does not trigger auto-retrain', () => {
    const report: DriftReport = {
      report_id: 'DRIFT_001',
      drift_status: 'DRIFT_DETECTED',
      reference_sample_count: 8,
      current_sample_count: 8,
      drifted_features: ['actual_cycle_time'],
      drift_details: {},
      warnings: [],
      review_required: true,
    };
    // driftIsNotAutoRetrain is a no-op guard — does NOT throw, does NOT retrain
    assert.doesNotThrow(() => driftIsNotAutoRetrain(report));
  });

  it('correlationIsNotCausation always throws', () => {
    assert.throws(() => correlationIsNotCausation(), AdaptiveContractViolation);
  });
});
