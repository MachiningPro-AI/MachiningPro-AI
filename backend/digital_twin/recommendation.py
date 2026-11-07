"""Level-18 Digital Twin — engineering recommendation engine.

PROPOSED ONLY — never automatically applied.
Human review mandatory.
"""

from __future__ import annotations

from .enums import FidelityLevel, ObjectiveType, RecommendationType, ScenarioStatus
from .models import (
    MultiObjectiveScore,
    ParetoCandidate,
    SimulationResult,
    TwinRecommendation,
)
from .scoring import compute_pareto_frontier


def _fidelity_min(results: list[SimulationResult]) -> FidelityLevel:
    order = [
        FidelityLevel.INSUFFICIENT,
        FidelityLevel.LOW,
        FidelityLevel.MEDIUM,
        FidelityLevel.HIGH,
    ]
    min_idx = len(order)
    for r in results:
        try:
            idx = order.index(r.fidelity)
        except ValueError:
            idx = 0
        if idx < min_idx:
            min_idx = idx
    return order[min_idx] if min_idx < len(order) else FidelityLevel.INSUFFICIENT


def generate_recommendation(
    results: list[SimulationResult],
    objective: ObjectiveType | None = None,
    weighted_scores: list[MultiObjectiveScore] | None = None,
    pareto_candidates: list[ParetoCandidate] | None = None,
) -> TwinRecommendation | None:
    """
    Generate an engineering recommendation from simulation results.

    Returns PROPOSED ONLY — never automatically applied.
    Returns None when no valid scenarios exist.

    "BEST" is only used when an explicit objective is configured.
    """
    valid = [
        r for r in results
        if r.status in (ScenarioStatus.SIMULATED, ScenarioStatus.VALID)
        and not r.hard_constraint_failures
    ]
    if not valid:
        return None

    recommendation_type: RecommendationType
    best_id: str
    why: str
    trade_offs: list[str] = []
    unknowns: list[str] = []

    if pareto_candidates:
        # Prefer non-dominated Pareto candidates
        non_dominated = [p for p in pareto_candidates if p.is_non_dominated]
        if non_dominated:
            best_id = non_dominated[0].scenario_id
            recommendation_type = RecommendationType.PARETO_CANDIDATE
            why = (
                f"Scenario {best_id!r} is non-dominated on the Pareto frontier — "
                "no other valid scenario is better on all evaluated KPIs."
            )
            trade_offs = [
                f"Dominates in: {', '.join(str(k) for k in non_dominated[0].dominates_in)}"
            ] if non_dominated[0].dominates_in else []
        else:
            # All dominated — pick by objective
            best_id = valid[0].scenario_id
            recommendation_type = RecommendationType.PARETO_CANDIDATE
            why = "All valid scenarios are dominated — selecting top candidate for review."
    elif objective == ObjectiveType.MINIMIZE_CYCLE_TIME:
        ranked = sorted(
            [r for r in valid if r.kpi.cycle_time_min is not None],
            key=lambda r: r.kpi.cycle_time_min,  # type: ignore[arg-type]
        )
        if not ranked:
            unknowns.append("cycle_time_min")
            return None
        best_id = ranked[0].scenario_id
        recommendation_type = RecommendationType.FASTEST_VALID_SCENARIO
        why = (
            f"Scenario {best_id!r} has the lowest simulated cycle time "
            f"({ranked[0].kpi.cycle_time_min:.1f} min)."
        )
    elif objective == ObjectiveType.MINIMIZE_MANUFACTURING_COST:
        ranked = sorted(
            [r for r in valid if r.kpi.manufacturing_cost is not None],
            key=lambda r: r.kpi.manufacturing_cost,  # type: ignore[arg-type]
        )
        if not ranked:
            unknowns.append("manufacturing_cost")
            return None
        best_id = ranked[0].scenario_id
        recommendation_type = RecommendationType.LOWEST_KNOWN_COST_SCENARIO
        why = (
            f"Scenario {best_id!r} has the lowest known manufacturing cost "
            f"({ranked[0].kpi.manufacturing_cost:.2f})."
        )
    elif objective == ObjectiveType.MAXIMIZE_TOOL_LIFE:
        ranked = sorted(
            [r for r in valid if r.kpi.tool_life_min is not None],
            key=lambda r: r.kpi.tool_life_min,  # type: ignore[arg-type]
            reverse=True,
        )
        if not ranked:
            unknowns.append("tool_life_min")
            return None
        best_id = ranked[0].scenario_id
        recommendation_type = RecommendationType.BEST_TOOL_LIFE_SCENARIO
        why = (
            f"Scenario {best_id!r} maximizes tool life "
            f"({ranked[0].kpi.tool_life_min:.1f} min)."
        )
    elif objective == ObjectiveType.MINIMIZE_QUALITY_RISK:
        ranked = sorted(
            [r for r in valid if r.kpi.quality_risk_level is not None],
            key=lambda r: r.kpi.quality_risk_level or "",
        )
        if not ranked:
            unknowns.append("quality_risk_level")
            return None
        best_id = ranked[0].scenario_id
        recommendation_type = RecommendationType.LOWEST_QUALITY_RISK_SCENARIO
        why = (
            f"Scenario {best_id!r} has the lowest quality risk level "
            f"({ranked[0].kpi.quality_risk_level})."
        )
    elif weighted_scores:
        ranked_ws = sorted(
            [s for s in weighted_scores if s.weighted_score is not None],
            key=lambda s: s.weighted_score or 0.0,
            reverse=True,
        )
        if not ranked_ws:
            return None
        best_id = ranked_ws[0].scenario_id
        recommendation_type = RecommendationType.PARETO_CANDIDATE
        why = (
            f"Scenario {best_id!r} has the highest weighted score "
            f"({ranked_ws[0].weighted_score:.3f}) under the configured objectives."
        )
    else:
        # No objective — cannot name a "best" — return Pareto candidate
        pareto = compute_pareto_frontier(valid)
        non_dom = [p for p in pareto if p.is_non_dominated]
        if non_dom:
            best_id = non_dom[0].scenario_id
            recommendation_type = RecommendationType.PARETO_CANDIDATE
            why = (
                f"Scenario {best_id!r} is non-dominated. "
                "No single objective was specified — Pareto frontier used."
            )
        else:
            best_id = valid[0].scenario_id
            recommendation_type = RecommendationType.PARETO_CANDIDATE
            why = "No single objective configured — first valid scenario returned for review."

    # Collect constraint passes
    best_result = next((r for r in results if r.scenario_id == best_id), None)
    constraints_passed = [
        c.constraint_name
        for c in (best_result.constraint_results if best_result else [])
        if c.passed
    ]
    if best_result:
        unknowns.extend(best_result.kpi.unknowns)

    return TwinRecommendation(
        recommendation_type=recommendation_type,
        scenario_id=best_id,
        why=why,
        constraints_passed=constraints_passed,
        data_fidelity=_fidelity_min(valid),
        trade_offs=trade_offs,
        unknowns=list(set(unknowns)),
        review_required=True,
        is_proposed_only=True,
        is_automatic_application=False,
    )
