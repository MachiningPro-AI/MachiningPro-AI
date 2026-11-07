"""Level-18 Digital Twin — multi-objective scoring and Pareto frontier.

Multi-objective scoring requires explicit weights — no default hidden weights.
UNKNOWN KPIs are not normalized to zero.
Pareto dominance is deterministic and conservative with UNKNOWN values.
"""

from __future__ import annotations

from .enums import KPIKey, ObjectiveType, ScenarioStatus
from .models import (
    MultiObjectiveScore,
    ObjectiveWeight,
    ParetoCandidate,
    SimulationResult,
)

# Objective → KPI attribute mapping (attr name, lower_is_better)
_OBJECTIVE_KPI: dict[ObjectiveType, tuple[str, bool]] = {
    ObjectiveType.MINIMIZE_CYCLE_TIME: ("cycle_time_min", True),
    ObjectiveType.MINIMIZE_MANUFACTURING_COST: ("manufacturing_cost", True),
    ObjectiveType.MAXIMIZE_TOOL_LIFE: ("tool_life_min", False),
    ObjectiveType.MINIMIZE_QUALITY_RISK: ("quality_risk_level", True),
    ObjectiveType.MINIMIZE_ALARM_RISK: ("alarm_risk_level", True),
    ObjectiveType.MINIMIZE_SETUP_TIME: ("setup_time_min", True),
    ObjectiveType.MINIMIZE_ENERGY: ("energy_kwh", True),
    ObjectiveType.MAXIMIZE_THROUGHPUT: ("throughput_per_hour", False),
}

# Pareto KPI keys and their lower_is_better flag
_PARETO_KPI: list[tuple[KPIKey, str, bool]] = [
    (KPIKey.CYCLE_TIME, "cycle_time_min", True),
    (KPIKey.MANUFACTURING_COST, "manufacturing_cost", True),
    (KPIKey.TOOL_LIFE, "tool_life_min", False),
    (KPIKey.ENERGY, "energy_kwh", True),
    (KPIKey.THROUGHPUT, "throughput_per_hour", False),
]


def _normalize_values(
    values: list[float | None],
    lower_is_better: bool,
) -> list[float | None]:
    """
    Normalize known values to [0, 1] range.

    Unknown (None) values are NOT normalized to zero — returned as None.
    """
    known = [v for v in values if v is not None]
    if not known:
        return [None] * len(values)
    min_v = min(known)
    max_v = max(known)
    if min_v == max_v:
        return [0.5 if v is not None else None for v in values]
    result: list[float | None] = []
    for v in values:
        if v is None:
            result.append(None)
        else:
            norm = (v - min_v) / (max_v - min_v)
            # For lower_is_better, invert so that lower value → higher score
            result.append(1.0 - norm if lower_is_better else norm)
    return result


def compute_multi_objective_scores(
    results: list[SimulationResult],
    weights: list[ObjectiveWeight] | None = None,
) -> list[MultiObjectiveScore]:
    """
    Compute multi-objective scores for simulation results.

    When weights are provided: return weighted composite score.
    When no weights: return component scores separately — no hidden aggregation.
    Unknown KPIs are not normalized to zero.
    """
    if not results:
        return []

    scores: list[MultiObjectiveScore] = []

    # Collect values by objective
    if weights:
        # Normalize weights
        total_weight = sum(w.weight for w in weights)
        norm_weights = [
            ObjectiveWeight(objective=w.objective, weight=w.weight / total_weight)
            for w in weights
            if total_weight > 0
        ]
    else:
        norm_weights = []

    # Build per-objective value lists
    objective_values: dict[ObjectiveType, list[float | None]] = {}
    for obj, (attr, _lower) in _OBJECTIVE_KPI.items():
        objective_values[obj] = [
            getattr(r.kpi, attr, None) for r in results
        ]

    # Normalize each objective
    normalized: dict[ObjectiveType, list[float | None]] = {}
    for obj, (_attr, lower_is_better) in _OBJECTIVE_KPI.items():
        normalized[obj] = _normalize_values(objective_values[obj], lower_is_better)

    for idx, result in enumerate(results):
        component_scores: dict[str, float] = {}
        unknowns: list[str] = []

        for obj, (_attr, _lower) in _OBJECTIVE_KPI.items():
            norm_v = normalized[obj][idx]
            if norm_v is not None:
                component_scores[obj.value] = norm_v
            else:
                unknowns.append(obj.value)

        # Weighted score only if weights provided
        weighted_score: float | None = None
        if norm_weights:
            known_contributions = []
            for nw in norm_weights:
                v = component_scores.get(nw.objective.value)
                if v is not None:
                    known_contributions.append(v * nw.weight)
            if known_contributions:
                weighted_score = sum(known_contributions)

        scores.append(MultiObjectiveScore(
            scenario_id=result.scenario_id,
            component_scores=component_scores,
            weighted_score=weighted_score,
            weights_applied=norm_weights if norm_weights else [],
            unknowns=unknowns,
        ))

    return scores


def _dominates(
    a: SimulationResult,
    b: SimulationResult,
    kpi_list: list[tuple[KPIKey, str, bool]],
) -> bool:
    """
    Return True if scenario A dominates scenario B.

    A dominates B when:
    - A is at least as good as B on all known KPIs
    - A is strictly better on at least one known KPI
    - Unknown KPIs are treated conservatively (A cannot claim dominance via unknowns)
    """
    at_least_as_good = True
    strictly_better = False

    for _kpi_key, attr, lower_is_better in kpi_list:
        va = getattr(a.kpi, attr, None)
        vb = getattr(b.kpi, attr, None)
        if va is None or vb is None:
            # Cannot claim dominance when data is unknown
            at_least_as_good = False
            continue
        if lower_is_better:
            if va > vb:
                at_least_as_good = False
            elif va < vb:
                strictly_better = True
        else:
            if va < vb:
                at_least_as_good = False
            elif va > vb:
                strictly_better = True

    return at_least_as_good and strictly_better


def compute_pareto_frontier(
    results: list[SimulationResult],
    kpi_list: list[tuple[KPIKey, str, bool]] | None = None,
) -> list[ParetoCandidate]:
    """
    Identify non-dominated scenarios (Pareto frontier).

    Uses conservative dominance: UNKNOWN KPIs do not give dominance advantage.
    Invalid scenarios are excluded from the Pareto calculation.
    """
    if kpi_list is None:
        kpi_list = _PARETO_KPI

    # Only consider valid/simulated scenarios
    valid = [
        r for r in results
        if r.status in (ScenarioStatus.SIMULATED, ScenarioStatus.VALID)
    ]

    candidates: list[ParetoCandidate] = []

    for result in valid:
        dominated_by: list[str] = []
        dominates_in_set: set[KPIKey] = set()
        dominated_in_set: set[KPIKey] = set()

        for other in valid:
            if other.scenario_id == result.scenario_id:
                continue
            if _dominates(other, result, kpi_list):
                dominated_by.append(other.scenario_id)
                # Find which KPIs cause domination
                for kpi_key, attr, lower_is_better in kpi_list:
                    va = getattr(result.kpi, attr, None)
                    vb = getattr(other.kpi, attr, None)
                    if va is not None and vb is not None:
                        if lower_is_better and vb < va:
                            dominated_in_set.add(kpi_key)
                        elif not lower_is_better and vb > va:
                            dominated_in_set.add(kpi_key)
            elif _dominates(result, other, kpi_list):
                for kpi_key, attr, lower_is_better in kpi_list:
                    va = getattr(result.kpi, attr, None)
                    vb = getattr(other.kpi, attr, None)
                    if va is not None and vb is not None:
                        if lower_is_better and va < vb:
                            dominates_in_set.add(kpi_key)
                        elif not lower_is_better and va > vb:
                            dominates_in_set.add(kpi_key)

        candidates.append(ParetoCandidate(
            scenario_id=result.scenario_id,
            dominated_by=dominated_by,
            is_non_dominated=len(dominated_by) == 0,
            dominated_in=list(dominated_in_set),
            dominates_in=list(dominates_in_set),
        ))

    return candidates
