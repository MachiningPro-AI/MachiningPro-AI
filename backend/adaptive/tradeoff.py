"""Level-16 Trade-off analysis and Pareto foundation."""

from __future__ import annotations

import uuid

from .models import TradeOffAnalysis, TradeOffCandidate


def _dominates(a: dict[str, float | None], b: dict[str, float | None]) -> bool:
    """Return True if candidate 'a' weakly dominates 'b' on all objectives (minimize)."""
    # a dominates b if a <= b on all and a < b on at least one
    at_least_one_better = False
    for key in a:
        va = a.get(key)
        vb = b.get(key)
        if va is None or vb is None:
            return False  # missing data — cannot determine dominance
        if va > vb:
            return False
        if va < vb:
            at_least_one_better = True
    return at_least_one_better


def compute_pareto_front(
    candidates: list[TradeOffCandidate],
    minimize_objectives: list[str] | None = None,
) -> list[TradeOffCandidate]:
    """
    Mark Pareto-optimal candidates.
    Returns the full list with is_pareto_optimal updated.
    No single best is chosen — the trade-off set is returned as-is.
    """
    if not candidates:
        return []

    objectives = minimize_objectives or []
    if not objectives:
        # Cannot determine dominance without explicit objectives
        for c in candidates:
            c.is_pareto_optimal = False
        return candidates

    for i, cand in enumerate(candidates):
        dominated = False
        for j, other in enumerate(candidates):
            if i == j:
                continue
            # Extract objective values
            a_vals = {obj: other.objectives.get(obj) for obj in objectives}
            b_vals = {obj: cand.objectives.get(obj) for obj in objectives}
            if _dominates(a_vals, b_vals):
                dominated = True
                break
        # Create new instance with updated is_pareto_optimal
        candidates[i] = cand.model_copy(update={"is_pareto_optimal": not dominated})

    return candidates


def build_trade_off_analysis(
    description: str,
    parameters_list: list[dict],
    objectives_list: list[dict[str, float | None]],
    objective_names: list[str],
    minimize_objectives: list[str] | None = None,
) -> TradeOffAnalysis:
    """
    Build a trade-off analysis for a set of candidate parameter configurations.
    No single 'best' is selected — the user gets the full Pareto-aware set.
    """
    if len(parameters_list) != len(objectives_list):
        return TradeOffAnalysis(
            analysis_id=str(uuid.uuid4())[:8],
            warnings=["PARAMETERS_AND_OBJECTIVES_LENGTH_MISMATCH"],
        )

    warnings: list[str] = ["NO_SINGLE_BEST — review trade-offs before selecting"]

    candidates = [
        TradeOffCandidate(
            candidate_id=f"CAND_{i:03d}",
            description=f"Configuration {i + 1}",
            parameters=parameters_list[i],
            objectives=objectives_list[i],
            trade_offs=[
                f"{obj}={objectives_list[i].get(obj)}" for obj in objective_names
            ],
        )
        for i in range(len(parameters_list))
    ]

    if minimize_objectives:
        candidates = compute_pareto_front(candidates, minimize_objectives)

    pareto_ids = [c.candidate_id for c in candidates if c.is_pareto_optimal]

    return TradeOffAnalysis(
        analysis_id=str(uuid.uuid4())[:8],
        objective_names=objective_names,
        candidates=candidates,
        pareto_front_ids=pareto_ids,
        no_single_best=True,
        warnings=warnings,
    )
