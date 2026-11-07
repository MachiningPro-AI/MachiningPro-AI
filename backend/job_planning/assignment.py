"""Level-17 CNC job planning — main assignment engine.

Produces PROPOSED_ONLY ranked assignment recommendations.
NEVER dispatches to real machines.
NEVER fabricates capability data.
Missing data fails closed — unknown != eligible.
"""

from __future__ import annotations

from .enums import (
    AssignmentStatus,
    MaterialCompatibilityResult,
    PlanningBlockReason,
    RankingObjective,
    SpindleMatchResult,
)
from .explainability import explain_candidate, explain_recommendation
from .matching import (
    check_material_compatibility,
    check_process_capabilities,
    check_spindle_requirements,
)
from .models import (
    AssignmentCandidate,
    AssignmentRecommendation,
    CamOperationRequirements,
    MachineCapabilityProfile,
    WorkloadEstimate,
)
from .ranking import compute_capability_score, compute_overall_score, rank_candidates
from .workload import estimate_workload


def _collect_incompatibility_reasons(
    candidate: AssignmentCandidate,
) -> list[str]:
    """Collect incompatibility reasons from checks."""
    from .enums import CapabilityMatchLevel
    reasons = []
    for check in candidate.capability_checks:
        if check.match_level == CapabilityMatchLevel.NO_MATCH:
            reasons.append(f"{check.check_name}: {check.detail}")
    if candidate.material_compatibility == MaterialCompatibilityResult.INCOMPATIBLE:
        reasons.append("material_incompatible")
    if candidate.spindle_match == SpindleMatchResult.OVER_LIMIT:
        reasons.append("spindle_over_limit")
    return reasons


def plan_job_assignment(
    requirements: CamOperationRequirements,
    machines: list[MachineCapabilityProfile],
    queue_depths: dict[str, int] | None = None,
    objective: RankingObjective = RankingObjective.CAPABILITY_FIT,
) -> AssignmentRecommendation:
    """
    Produce a ranked assignment recommendation for a job.

    PROPOSED ONLY — never dispatches to real machines.
    Missing capability data fails closed — UNKNOWN != eligible.
    is_proposed_only=True and is_automatic_dispatch=False are invariants.
    review_required=True is mandatory.
    """
    warnings: list[str] = []
    blocking_reasons: list[PlanningBlockReason] = []

    if not machines:
        return AssignmentRecommendation(
            job_id=requirements.job_id,
            status=AssignmentStatus.REVIEW_REQUIRED,
            candidates=[],
            best_candidate_id=None,
            planning_warnings=["No machine profiles provided"],
            blocking_reasons=[PlanningBlockReason.NO_MACHINES_PROVIDED],
            is_proposed_only=True,
            is_automatic_dispatch=False,
            review_required=True,
            is_fabricated_data=False,
            explanation="No machines available to evaluate",
            ranking_objective=objective,
        )

    if requirements.material is None:
        warnings.append(
            "Material not specified — material compatibility cannot be assessed"
        )

    # Build candidates
    raw_candidates: list[AssignmentCandidate] = []

    for profile in machines:
        # Material compatibility
        mat_check = check_material_compatibility(
            requirements.material,
            profile.machine_class,
        )

        # Spindle match
        spindle_check = check_spindle_requirements(
            requirements.required_spindle_rpm,
            profile.spindle_max_rpm,
        )

        # Process capability checks
        capability_checks = check_process_capabilities(requirements, profile)
        capability_score = compute_capability_score(capability_checks)

        # Workload estimate
        q_depth = queue_depths.get(profile.machine_id) if queue_depths else None
        workload_est: WorkloadEstimate = estimate_workload(
            machine_id=profile.machine_id,
            queue_depth=q_depth,
            estimated_cycle_time_min=requirements.estimated_cycle_time_min,
        )

        # Overall score
        overall = compute_overall_score(
            capability=capability_score,
            material=mat_check.result,
            spindle=spindle_check.result,
            workload=workload_est.workload_status,
            objective=objective,
        )

        candidate = AssignmentCandidate(
            machine_id=profile.machine_id,
            rank=0,  # filled by rank_candidates()
            capability_score=capability_score,
            material_compatibility=mat_check.result,
            spindle_match=spindle_check.result,
            workload_status=workload_est.workload_status,
            capability_checks=capability_checks,
            workload_estimate=workload_est,
            incompatibility_reasons=[],
            soft_preference_score=0.0,
            overall_score=overall,
            explanation="",
            is_proposed_only=True,
            is_automatic_dispatch=False,
        )

        # Collect incompatibility reasons
        reasons = _collect_incompatibility_reasons(candidate)
        candidate = candidate.model_copy(update={"incompatibility_reasons": reasons})
        raw_candidates.append(candidate)

    # Rank candidates
    ranked = rank_candidates(raw_candidates, objective)

    # Generate explanations
    final_candidates: list[AssignmentCandidate] = []
    for candidate in ranked:
        explanation = explain_candidate(candidate, requirements)
        final_candidates.append(candidate.model_copy(update={"explanation": explanation}))

    # Best candidate — highest rank (rank==1) with no hard incompatibilities
    best_id: str | None = None
    if final_candidates:
        top = final_candidates[0]
        no_hard_block = (
            top.material_compatibility != MaterialCompatibilityResult.INCOMPATIBLE
            and top.spindle_match != SpindleMatchResult.OVER_LIMIT
        )
        if no_hard_block:
            best_id = top.machine_id
        else:
            blocking_reasons.append(PlanningBlockReason.MATERIAL_INCOMPATIBLE)

    status = (
        AssignmentStatus.PROPOSED if best_id else AssignmentStatus.REVIEW_REQUIRED
    )

    recommendation = AssignmentRecommendation(
        job_id=requirements.job_id,
        status=status,
        candidates=final_candidates,
        best_candidate_id=best_id,
        planning_warnings=warnings,
        blocking_reasons=blocking_reasons,
        is_proposed_only=True,
        is_automatic_dispatch=False,
        review_required=True,
        is_fabricated_data=False,
        ranking_objective=objective,
    )

    # Final explanation
    full_explanation = explain_recommendation(recommendation, requirements)
    return recommendation.model_copy(update={"explanation": full_explanation})
