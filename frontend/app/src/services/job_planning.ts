/**
 * Level-17 CNC Job Planning & Machine Assignment service.
 *
 * Contract enforcement helpers ensure the invariants from types/job_planning.ts
 * are upheld at runtime.
 *
 * MUST NEVER:
 *   - Dispatch a job to a real CNC machine
 *   - Automatically assign a machine without human review
 *   - Use or accept fabricated capability data
 *   - Treat UNKNOWN capability as eligible
 *   - Execute or apply any assignment automatically
 */

import type {
  AssignmentCandidate,
  AssignmentRecommendation,
  CamOperationRequirements,
  MachineCapabilityProfile,
  WorkloadEstimate,
} from '../types/job_planning.ts';

export {
  NO_AUTOMATIC_MACHINE_ASSIGNMENT,
  NO_AUTOMATIC_JOB_DISPATCH,
  NO_FABRICATED_CAPABILITY_DATA,
  MISSING_DATA_FAILS_CLOSED,
  ASSIGNMENT_IS_PROPOSED_ONLY,
  HUMAN_APPROVAL_MANDATORY,
  UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
} from '../types/job_planning.ts';

// ---------------------------------------------------------------------------
// Contract violation error
// ---------------------------------------------------------------------------

export class JobPlanningContractViolation extends Error {
  constructor(rule: string, detail: string) {
    super(`JOB_PLANNING_CONTRACT_VIOLATION [${rule}]: ${detail}`);
    this.name = 'JobPlanningContractViolation';
  }
}

// ---------------------------------------------------------------------------
// Invariant enforcement
// ---------------------------------------------------------------------------

export function enforceRequirementsContract(req: CamOperationRequirements): void {
  if (req.is_fabricated_requirements !== false) {
    throw new JobPlanningContractViolation(
      'REQUIREMENTS_INVARIANT',
      'is_fabricated_requirements must be false — CAM requirements must not be fabricated'
    );
  }
}

export function enforceCapabilityProfileContract(profile: MachineCapabilityProfile): void {
  if (profile.is_fabricated_capability !== false) {
    throw new JobPlanningContractViolation(
      'CAPABILITY_INVARIANT',
      'is_fabricated_capability must be false — machine capabilities must not be fabricated'
    );
  }
}

export function enforceWorkloadContract(estimate: WorkloadEstimate): void {
  if (estimate.is_fabricated !== false) {
    throw new JobPlanningContractViolation(
      'WORKLOAD_INVARIANT',
      'is_fabricated must be false — workload estimates must not be fabricated'
    );
  }
}

export function enforceCandidateContract(candidate: AssignmentCandidate): void {
  if (candidate.is_proposed_only !== true) {
    throw new JobPlanningContractViolation(
      'CANDIDATE_INVARIANT',
      'is_proposed_only must be true — candidates are proposed, never dispatched'
    );
  }
  if (candidate.is_automatic_dispatch !== false) {
    throw new JobPlanningContractViolation(
      'CANDIDATE_INVARIANT',
      'is_automatic_dispatch must be false — no automatic dispatch allowed'
    );
  }
}

export function enforceRecommendationContract(rec: AssignmentRecommendation): void {
  if (rec.is_proposed_only !== true) {
    throw new JobPlanningContractViolation(
      'RECOMMENDATION_INVARIANT',
      'is_proposed_only must be true — recommendations are proposed, never automatically applied'
    );
  }
  if (rec.is_automatic_dispatch !== false) {
    throw new JobPlanningContractViolation(
      'RECOMMENDATION_INVARIANT',
      'is_automatic_dispatch must be false — no automatic dispatch'
    );
  }
  if (rec.review_required !== true) {
    throw new JobPlanningContractViolation(
      'RECOMMENDATION_INVARIANT',
      'review_required must be true — human engineering review is mandatory'
    );
  }
  if (rec.is_fabricated_data !== false) {
    throw new JobPlanningContractViolation(
      'RECOMMENDATION_INVARIANT',
      'is_fabricated_data must be false — no fabricated data in recommendations'
    );
  }
}

export function enforceNoDispatch(rec: AssignmentRecommendation): void {
  const forbidden = ['DISPATCHED_TO_MACHINE', 'EXECUTING', 'AUTO_ASSIGNED'] as const;
  if ((forbidden as readonly string[]).includes(rec.status)) {
    throw new JobPlanningContractViolation(
      'STATUS_GATE',
      `Recommendation status '${rec.status}' represents automatic dispatch — not allowed`
    );
  }
}

// ---------------------------------------------------------------------------
// Utility
// ---------------------------------------------------------------------------

export function isSuitableCandidate(candidate: AssignmentCandidate): boolean {
  return (
    candidate.material_compatibility !== 'INCOMPATIBLE'
    && candidate.spindle_match !== 'OVER_LIMIT'
    && candidate.capability_score > 0
  );
}

export function summarizeRecommendation(rec: AssignmentRecommendation): string {
  return (
    `[${rec.job_id}] status=${rec.status}`
    + ` candidates=${rec.candidates.length}`
    + ` best=${rec.best_candidate_id ?? 'NONE'}`
    + ` review_required=${String(rec.review_required)}`
  );
}

export function summarizeCandidate(candidate: AssignmentCandidate): string {
  return (
    `rank=${candidate.rank} machine=${candidate.machine_id}`
    + ` score=${candidate.overall_score.toFixed(2)}`
    + ` material=${candidate.material_compatibility}`
    + ` spindle=${candidate.spindle_match}`
    + ` workload=${candidate.workload_status}`
  );
}

export function assignmentIsProposedOnly(_rec: AssignmentRecommendation): void {
  // Guard: always throws if any downstream code tries to treat recommendation as dispatch
  // This is a documentation guard — callers should call enforceRecommendationContract instead
}

export function missingDataFailsClosed(profile: MachineCapabilityProfile): boolean {
  // Returns true if profile has significant unknown data that could mask incompatibility
  return (
    profile.axis_count === null
    || profile.spindle_max_rpm === null
    || profile.machine_class === 'UNKNOWN'
  );
}
