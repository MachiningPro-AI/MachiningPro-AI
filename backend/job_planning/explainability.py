"""Level-17 explainability — human-readable explanations for assignment recommendations.

All explanations are summaries of computed data only.
No capability data is fabricated or assumed.
"""

from __future__ import annotations

from .enums import (
    CapabilityMatchLevel,
    MaterialCompatibilityResult,
    SpindleMatchResult,
    WorkloadStatus,
)
from .models import AssignmentCandidate, AssignmentRecommendation, CamOperationRequirements


def explain_candidate(
    candidate: AssignmentCandidate,
    requirements: CamOperationRequirements,
) -> str:
    """Generate a human-readable explanation for a single assignment candidate."""
    lines: list[str] = [
        f"Machine {candidate.machine_id} (rank #{candidate.rank}):",
        f"  Overall score: {candidate.overall_score:.2f}",
        f"  Capability score: {candidate.capability_score:.2f}",
    ]

    # Material compatibility
    mat_line = {
        MaterialCompatibilityResult.COMPATIBLE: "COMPATIBLE",
        MaterialCompatibilityResult.LIKELY_COMPATIBLE: "LIKELY COMPATIBLE",
        MaterialCompatibilityResult.UNKNOWN: "UNKNOWN (data missing)",
        MaterialCompatibilityResult.INCOMPATIBLE: "INCOMPATIBLE",
    }[candidate.material_compatibility]
    if requirements.material:
        lines.append(f"  Material ({requirements.material}): {mat_line}")

    # Spindle
    spindle_line = {
        SpindleMatchResult.WITHIN_RANGE: "WITHIN RANGE",
        SpindleMatchResult.AT_LIMIT: "AT LIMIT (high utilization)",
        SpindleMatchResult.OVER_LIMIT: "OVER LIMIT — insufficient",
        SpindleMatchResult.UNDER_SPEC: "UNDER SPEC",
        SpindleMatchResult.UNKNOWN: "UNKNOWN (data missing)",
    }[candidate.spindle_match]
    lines.append(f"  Spindle: {spindle_line}")

    # Workload
    wl_line = {
        WorkloadStatus.LOW: "LOW queue",
        WorkloadStatus.MODERATE: "MODERATE queue",
        WorkloadStatus.HIGH: "HIGH queue",
        WorkloadStatus.OVERLOADED: "OVERLOADED",
        WorkloadStatus.UNKNOWN: "UNKNOWN queue depth",
    }[candidate.workload_status]
    lines.append(f"  Workload: {wl_line} (depth={candidate.workload_estimate.queue_depth})")

    # Process checks
    no_match = [
        c for c in candidate.capability_checks
        if c.match_level == CapabilityMatchLevel.NO_MATCH
    ]
    unknown = [
        c for c in candidate.capability_checks
        if c.match_level == CapabilityMatchLevel.UNKNOWN
    ]

    if no_match:
        lines.append(f"  GAPS: {', '.join(c.check_name for c in no_match)}")
    if unknown:
        lines.append(f"  UNKNOWN: {', '.join(c.check_name for c in unknown)}")
    if candidate.incompatibility_reasons:
        lines.append(f"  Incompatibility reasons: {'; '.join(candidate.incompatibility_reasons)}")

    lines.append("  [PROPOSED ONLY — human review required before dispatch]")
    return "\n".join(lines)


def explain_recommendation(
    recommendation: AssignmentRecommendation,
    requirements: CamOperationRequirements,
) -> str:
    """Generate a human-readable explanation for the full assignment recommendation."""
    lines: list[str] = [
        f"Job Planning Report — Job: {recommendation.job_id}",
        f"Status: {recommendation.status}",
        f"Candidates evaluated: {len(recommendation.candidates)}",
    ]

    if recommendation.best_candidate_id:
        lines.append(f"Best candidate: {recommendation.best_candidate_id}")
    else:
        lines.append("Best candidate: NONE (no suitable machine found)")

    if recommendation.blocking_reasons:
        lines.append(
            f"Blocking reasons: {', '.join(str(r) for r in recommendation.blocking_reasons)}"
        )
    if recommendation.planning_warnings:
        for w in recommendation.planning_warnings:
            lines.append(f"  WARNING: {w}")

    lines.append("")
    for candidate in recommendation.candidates:
        lines.append(explain_candidate(candidate, requirements))
        lines.append("")

    lines.append(
        "IMPORTANT: This is a PROPOSED recommendation only. "
        "No machine has been assigned. Human review and approval required before dispatch."
    )
    return "\n".join(lines)
