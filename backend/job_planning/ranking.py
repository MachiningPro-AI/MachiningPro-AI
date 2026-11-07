"""Level-17 machine assignment ranking.

Scores capability checks and ranks candidates. PROPOSED ONLY.
"""

from __future__ import annotations

from .enums import (
    CapabilityMatchLevel,
    MaterialCompatibilityResult,
    RankingObjective,
    SpindleMatchResult,
    WorkloadStatus,
)
from .models import AssignmentCandidate, CapabilityCheckResult
from .workload import workload_score

# ---------------------------------------------------------------------------
# Scoring weights by objective
# ---------------------------------------------------------------------------

_WEIGHTS: dict[RankingObjective, dict[str, float]] = {
    RankingObjective.CAPABILITY_FIT: {
        "capability": 0.50,
        "material": 0.20,
        "spindle": 0.15,
        "workload": 0.15,
    },
    RankingObjective.MATERIAL_COMPATIBILITY: {
        "capability": 0.25,
        "material": 0.45,
        "spindle": 0.15,
        "workload": 0.15,
    },
    RankingObjective.SPINDLE_UTILIZATION: {
        "capability": 0.25,
        "material": 0.15,
        "spindle": 0.45,
        "workload": 0.15,
    },
    RankingObjective.WORKLOAD_BALANCE: {
        "capability": 0.25,
        "material": 0.15,
        "spindle": 0.10,
        "workload": 0.50,
    },
    RankingObjective.PROCESS_CAPABILITY: {
        "capability": 0.60,
        "material": 0.15,
        "spindle": 0.15,
        "workload": 0.10,
    },
}


def compute_capability_score(checks: list[CapabilityCheckResult]) -> float:
    """Return 0–1 capability score based on check results.

    NO_MATCH = 0.0 contribution, UNKNOWN = 0.4, PARTIAL_MATCH = 0.7, FULL_MATCH = 1.0.
    Empty checks → 1.0 (no constraints to violate).
    """
    if not checks:
        return 1.0

    _level_score = {
        CapabilityMatchLevel.FULL_MATCH: 1.0,
        CapabilityMatchLevel.PARTIAL_MATCH: 0.7,
        CapabilityMatchLevel.UNKNOWN: 0.4,
        CapabilityMatchLevel.NO_MATCH: 0.0,
    }
    total = sum(_level_score[c.match_level] for c in checks)
    return total / len(checks)


def material_compat_score(result: MaterialCompatibilityResult) -> float:
    """Return 0–1 score for material compatibility."""
    return {
        MaterialCompatibilityResult.COMPATIBLE: 1.0,
        MaterialCompatibilityResult.LIKELY_COMPATIBLE: 0.7,
        MaterialCompatibilityResult.UNKNOWN: 0.4,
        MaterialCompatibilityResult.INCOMPATIBLE: 0.0,
    }[result]


def spindle_match_score(result: SpindleMatchResult) -> float:
    """Return 0–1 score for spindle match."""
    return {
        SpindleMatchResult.WITHIN_RANGE: 1.0,
        SpindleMatchResult.AT_LIMIT: 0.5,
        SpindleMatchResult.OVER_LIMIT: 0.0,
        SpindleMatchResult.UNDER_SPEC: 0.2,
        SpindleMatchResult.UNKNOWN: 0.4,
    }[result]


def compute_overall_score(
    capability: float,
    material: MaterialCompatibilityResult,
    spindle: SpindleMatchResult,
    workload: WorkloadStatus,
    objective: RankingObjective = RankingObjective.CAPABILITY_FIT,
) -> float:
    """Compute weighted overall score 0–1 for a candidate."""
    weights = _WEIGHTS[objective]
    s_cap = capability
    s_mat = material_compat_score(material)
    s_spl = spindle_match_score(spindle)
    s_wld = workload_score(workload)

    return (
        weights["capability"] * s_cap
        + weights["material"] * s_mat
        + weights["spindle"] * s_spl
        + weights["workload"] * s_wld
    )


def rank_candidates(
    candidates: list[AssignmentCandidate],
    objective: RankingObjective = RankingObjective.CAPABILITY_FIT,
) -> list[AssignmentCandidate]:
    """Return candidates sorted by overall_score descending, with updated ranks."""
    sorted_candidates = sorted(candidates, key=lambda c: c.overall_score, reverse=True)
    ranked = []
    for idx, candidate in enumerate(sorted_candidates, start=1):
        ranked.append(candidate.model_copy(update={"rank": idx}))
    return ranked
