/**
 * Level-16 Adaptive Manufacturing Intelligence service.
 *
 * Contract enforcement helpers ensure the invariants from types/adaptive.ts
 * are upheld at runtime.
 *
 * MUST NEVER:
 *   - Write to CNC / machine controller
 *   - Apply feed/spindle/tool/work offsets automatically
 *   - Replace cutting data automatically
 *   - Apply CAM or NC changes automatically
 *   - Change scheduling automatically
 *   - Dispatch jobs automatically
 */

import type {
  AdaptiveRecommendation,
  DriftReport,
  ManufacturingLearningRecord,
  ModelSpec,
  PredictionResult,
  QualityRiskResult,
  WhatIfScenario,
} from '../types/adaptive.ts';

export {
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
} from '../types/adaptive.ts';

// ---------------------------------------------------------------------------
// Contract violation error
// ---------------------------------------------------------------------------

export class AdaptiveContractViolation extends Error {
  constructor(rule: string, detail: string) {
    super(`ADAPTIVE_CONTRACT_VIOLATION [${rule}]: ${detail}`);
    this.name = 'AdaptiveContractViolation';
  }
}

// ---------------------------------------------------------------------------
// Invariant enforcement
// ---------------------------------------------------------------------------

export function enforceRecordContract(record: ManufacturingLearningRecord): void {
  if (record.is_fabricated !== false) {
    throw new AdaptiveContractViolation(
      'RECORD_INVARIANT',
      'is_fabricated must be false for all real learning records'
    );
  }
}

export function enforcePredictionContract(pred: PredictionResult): void {
  if (pred.is_fabricated !== false) {
    throw new AdaptiveContractViolation(
      'PREDICTION_INVARIANT',
      'is_fabricated must be false — predictions must not fabricate accuracy'
    );
  }
}

export function enforceRecommendationContract(rec: AdaptiveRecommendation): void {
  if (rec.is_automatic_application !== false) {
    throw new AdaptiveContractViolation(
      'RECOMMENDATION_INVARIANT',
      'is_automatic_application must be false — adaptive recommendations are PROPOSED only'
    );
  }
  if (rec.review_required !== true) {
    throw new AdaptiveContractViolation(
      'RECOMMENDATION_INVARIANT',
      'review_required must be true — human engineering review is mandatory'
    );
  }
}

export function enforceWhatIfContract(scenario: WhatIfScenario): void {
  if (scenario.mutates_baseline !== false) {
    throw new AdaptiveContractViolation(
      'WHATIF_INVARIANT',
      'mutates_baseline must be false — what-if engine must not alter the baseline record'
    );
  }
}

export function enforceModelContract(spec: ModelSpec): void {
  if (spec.is_fabricated_accuracy !== false) {
    throw new AdaptiveContractViolation(
      'MODEL_INVARIANT',
      'is_fabricated_accuracy must be false — model metrics must not be fabricated'
    );
  }
}

export function enforceRiskContract(result: QualityRiskResult): void {
  if (result.is_fabricated !== false) {
    throw new AdaptiveContractViolation(
      'RISK_INVARIANT',
      'is_fabricated must be false — risk estimates must not be fabricated'
    );
  }
}

// ---------------------------------------------------------------------------
// Separation helpers (documentation / guard functions)
// ---------------------------------------------------------------------------

export function predictionIsNotMeasuredFact(pred: PredictionResult): void {
  if (pred.predicted_value !== null && pred.fidelity === 'INSUFFICIENT') {
    throw new AdaptiveContractViolation(
      'FIDELITY_GATE',
      'Cannot present INSUFFICIENT fidelity prediction as a measured fact'
    );
  }
}

export function recommendationIsNotApprovedChange(rec: AdaptiveRecommendation): void {
  const forbidden = ['APPLIED_TO_MACHINE', 'EXECUTING', 'APPROVED'] as const;
  if ((forbidden as readonly string[]).includes(rec.status)) {
    throw new AdaptiveContractViolation(
      'STATUS_GATE',
      `Recommendation status '${rec.status}' is not an allowed adaptive status`
    );
  }
}

export function correlationIsNotCausation(): void {
  // Always throw when called — this is a documentation guard
  throw new AdaptiveContractViolation(
    'CORRELATION_CAUSATION',
    'Correlation between historical cases does not imply causation'
  );
}

export function outOfDomainIsNotPrediction(pred: PredictionResult): void {
  if (pred.out_of_domain && pred.predicted_value !== null) {
    throw new AdaptiveContractViolation(
      'OUT_OF_DOMAIN',
      'Out-of-domain predictions must not be presented as reliable'
    );
  }
}

export function driftIsNotAutoRetrain(report: DriftReport): void {
  if (report.drift_status === 'DRIFT_DETECTED') {
    // Drift detection does not automatically trigger retraining
    // This is a no-op guard that documents the invariant
    return;
  }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

export function isSufficientFidelity(pred: PredictionResult): boolean {
  return pred.fidelity !== 'INSUFFICIENT' && !pred.out_of_domain && !pred.is_fabricated;
}

export function summarizeRecommendation(rec: AdaptiveRecommendation): string {
  return (
    `[${rec.recommendation_type}] fidelity=${rec.fidelity}` +
    ` samples=${rec.sample_count}` +
    ` status=${rec.status}` +
    ` review_required=${String(rec.review_required)}`
  );
}
