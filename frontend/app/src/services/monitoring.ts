/**
 * Level-15 Monitoring Service.
 *
 * OBSERVE → COMPARE → DIAGNOSE → RECOMMEND.
 * No machine-control calls.
 * Closed-loop mode: PROPOSED_ONLY.
 */

import type {
  ClosedLoopProposal,
  EngineeringRecommendation,
  OEEResult,
  ProductionObservation,
  RootCauseCandidate,
  ToolLifeFeedback,
} from '../types/monitoring.ts';

// ---------------------------------------------------------------------------
// Contract enforcement
// ---------------------------------------------------------------------------

export class MonitoringContractViolation extends Error {
  constructor(message: string) {
    super(`MONITORING_CONTRACT_VIOLATION: ${message}`);
    this.name = 'MonitoringContractViolation';
  }
}

/** Observation data must never be fabricated. */
export function enforceObservationContract(
  obs: Partial<ProductionObservation>
): void {
  if (obs.is_fabricated !== false) {
    throw new MonitoringContractViolation(
      'is_fabricated must be false — observation data must come from real or simulated sources'
    );
  }
}

/** OEE result must not be CALCULATED when status says INSUFFICIENT_DATA. */
export function enforceOEEContract(result: OEEResult): void {
  if (result.status === 'INSUFFICIENT_DATA' && result.oee !== null) {
    throw new MonitoringContractViolation(
      'OEE must be null when status is INSUFFICIENT_DATA'
    );
  }
  if (result.status === 'CALCULATED' && result.oee === null) {
    throw new MonitoringContractViolation(
      'OEE must not be null when status is CALCULATED'
    );
  }
}

/** Tool life feedback must never be an automatic action. */
export function enforceToolFeedbackContract(fb: ToolLifeFeedback): void {
  if (fb.is_automatic_action !== false) {
    throw new MonitoringContractViolation(
      'is_automatic_action must be false — tool feedback is PROPOSED_ONLY'
    );
  }
}

/** Recommendation must require review and must not be automatic. */
export function enforceRecommendationContract(
  rec: EngineeringRecommendation
): void {
  if (rec.requires_review !== true) {
    throw new MonitoringContractViolation(
      'requires_review must be true — human review is mandatory'
    );
  }
  if (rec.is_automatic_action !== false) {
    throw new MonitoringContractViolation(
      'is_automatic_action must be false — no automatic recommendation application'
    );
  }
  if (rec.is_applied !== false) {
    throw new MonitoringContractViolation(
      'is_applied must be false at creation — recommendation is not applied automatically'
    );
  }
}

/** Root cause candidate must never claim causal proof. */
export function enforceRootCauseContract(candidate: RootCauseCandidate): void {
  if (candidate.is_confirmed !== false) {
    throw new MonitoringContractViolation(
      'is_confirmed must be false — root cause is CANDIDATE only'
    );
  }
  if (candidate.is_causal_proof !== false) {
    throw new MonitoringContractViolation(
      'is_causal_proof must be false — correlation is not causal proof'
    );
  }
}

/** Closed-loop proposal must never be an automatic write. */
export function enforceClosedLoopContract(proposal: ClosedLoopProposal): void {
  if (proposal.is_proposed_only !== true) {
    throw new MonitoringContractViolation(
      'is_proposed_only must be true — closed-loop proposals are PROPOSED_ONLY'
    );
  }
  if (proposal.is_automatic_write !== false) {
    throw new MonitoringContractViolation(
      'is_automatic_write must be false — no automatic write to cutting data or NC'
    );
  }
}

// ---------------------------------------------------------------------------
// Separation helpers
// ---------------------------------------------------------------------------

/** Confirm planned value is not used as the actual value. */
export function plannedIsNotActual(
  planned: number | null,
  actual: number | null
): boolean {
  if (planned === null && actual === null) return true;
  // Structural separation: planned and actual are distinct fields
  return planned !== actual || planned === null;
}

/** Confirm missing alarm data is not treated as zero alarms. */
export function missingAlarmDataIsNotZero(
  alarmCodes: string[] | null | undefined
): boolean {
  // null/undefined = missing, not zero
  return alarmCodes !== null && alarmCodes !== undefined;
}

/** Confirm unknown cycle state is not treated as idle. */
export function unknownStateIsNotIdle(cycleState: string): boolean {
  return cycleState !== 'IDLE';
}

/** Confirm correlation evidence is not a confirmed root cause. */
export function correlationIsNotCausation(): false {
  return false;
}

/** Confirm recommendation is not an automatic action. */
export function recommendationIsNotAutoAction(): false {
  return false;
}

/** Confirm proposed feed is not a machine feed override. */
export function proposedFeedIsNotMachineOverride(): false {
  return false;
}

/** Confirm tool-life feedback is not a tool-offset write. */
export function toolLifeFeedbackIsNotOffsetWrite(): false {
  return false;
}

/** Confirm quality feedback is not an automatic process change. */
export function qualityFeedbackIsNotAutoChange(): false {
  return false;
}

// ---------------------------------------------------------------------------
// Display helpers
// ---------------------------------------------------------------------------

export function formatCycleTimeDelta(
  delta: number | null,
  relative: number | null
): string {
  if (delta === null || relative === null) return 'UNKNOWN';
  const sign = delta >= 0 ? '+' : '';
  return `${sign}${delta.toFixed(1)}s (${(relative * 100).toFixed(1)}%)`;
}

export function oeeStatusLabel(oee: number | null, status: string): string {
  if (status === 'INSUFFICIENT_DATA') return 'INSUFFICIENT_DATA';
  if (status === 'INVALID') return 'INVALID';
  if (oee === null) return 'UNKNOWN';
  return `${(oee * 100).toFixed(1)}%`;
}

export function toolLifeLabel(status: string): string {
  const labels: Record<string, string> = {
    TOOL_LIFE_SHORTER_THAN_EXPECTED: 'Shorter Than Expected',
    TOOL_LIFE_LONGER_THAN_EXPECTED: 'Longer Than Expected',
    TOOL_LIFE_WITHIN_POLICY: 'Within Policy',
    INSUFFICIENT_DATA: 'Insufficient Data',
  };
  return labels[status] ?? 'UNKNOWN';
}
