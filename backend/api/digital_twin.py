"""Level-18 Manufacturing Digital Twin API endpoints.

SIMULATION_ONLY: All endpoints return simulation results — never production plans.
NO_AUTOMATIC_APPLICATION: No endpoint applies changes automatically.
HUMAN_REVIEW_MANDATORY: Every recommendation requires human approval.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.auth import verify_token
from backend.digital_twin import (
    BASELINE_MUTATION_ALLOWED,
    EVALUATOR_VERSION,
    HUMAN_REVIEW_MANDATORY,
    NO_AUTOMATIC_APPLICATION,
    NO_AUTOMATIC_CAM_CHANGE,
    NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT,
    NO_AUTOMATIC_DISPATCH,
    NO_AUTOMATIC_GCODE_REGENERATION,
    NO_AUTOMATIC_MACHINE_REASSIGNMENT,
    NO_AUTOMATIC_SCHEDULING_CHANGE,
    NO_AUTOMATIC_TOOL_SUBSTITUTION,
    NO_CNC_WRITE,
    NO_FABRICATED_TWIN_RESULT,
    OPTIMIZED_SCENARIO_IS_NOT_APPROVED,
    SCENARIO_IS_NOT_PRODUCTION_PLAN,
    UNKNOWN_INPUTS_STAY_UNKNOWN,
    ManufacturingTwinScenario,
    ObjectiveType,
    ObjectiveWeight,
    TwinSearchLimits,
    check_staleness,
    compare_scenarios,
    compute_input_snapshot_hash,
    compute_multi_objective_scores,
    compute_pareto_frontier,
    evaluate_constraints,
    explain_comparison,
    explain_recommendation,
    explain_scenario,
    generate_cutting_data_alternatives,
    generate_machine_alternatives,
    generate_quantity_alternatives,
    generate_recommendation,
    generate_schedule_alternatives,
    generate_tool_alternatives,
    record_comparison_run,
    record_pareto_calculated,
    record_recommendation_generated,
    record_scenario_created,
    record_scenario_reviewed,
    record_scenario_simulated,
    simulate_scenario,
)

router = APIRouter(prefix="/api/digital-twin", tags=["digital-twin"])


def _require_user(token: str = Depends(verify_token)):  # noqa: B008
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token


# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------


@router.get("/safety-constants")
def get_safety_constants(_token: str = Depends(_require_user)):  # noqa: B008
    """Return all safety constants — verify they are intact."""
    return {
        "NO_AUTOMATIC_APPLICATION": NO_AUTOMATIC_APPLICATION,
        "NO_CNC_WRITE": NO_CNC_WRITE,
        "NO_AUTOMATIC_DISPATCH": NO_AUTOMATIC_DISPATCH,
        "NO_AUTOMATIC_CAM_CHANGE": NO_AUTOMATIC_CAM_CHANGE,
        "NO_AUTOMATIC_GCODE_REGENERATION": NO_AUTOMATIC_GCODE_REGENERATION,
        "NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT": NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT,
        "NO_AUTOMATIC_MACHINE_REASSIGNMENT": NO_AUTOMATIC_MACHINE_REASSIGNMENT,
        "NO_AUTOMATIC_SCHEDULING_CHANGE": NO_AUTOMATIC_SCHEDULING_CHANGE,
        "NO_AUTOMATIC_TOOL_SUBSTITUTION": NO_AUTOMATIC_TOOL_SUBSTITUTION,
        "BASELINE_MUTATION_ALLOWED": BASELINE_MUTATION_ALLOWED,
        "SCENARIO_IS_NOT_PRODUCTION_PLAN": SCENARIO_IS_NOT_PRODUCTION_PLAN,
        "OPTIMIZED_SCENARIO_IS_NOT_APPROVED": OPTIMIZED_SCENARIO_IS_NOT_APPROVED,
        "HUMAN_REVIEW_MANDATORY": HUMAN_REVIEW_MANDATORY,
        "NO_FABRICATED_TWIN_RESULT": NO_FABRICATED_TWIN_RESULT,
        "UNKNOWN_INPUTS_STAY_UNKNOWN": UNKNOWN_INPUTS_STAY_UNKNOWN,
        "EVALUATOR_VERSION": EVALUATOR_VERSION,
    }


# ---------------------------------------------------------------------------
# Scenario lifecycle
# ---------------------------------------------------------------------------


@router.post("/scenario")
def create_scenario(
    scenario: ManufacturingTwinScenario,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Register a new scenario and record its creation in the audit trail."""
    if not scenario.is_simulation_only:
        raise HTTPException(status_code=400, detail="Scenario must be simulation-only")
    if scenario.is_production_plan:
        raise HTTPException(status_code=400, detail="Scenario must not be a production plan")

    audit = record_scenario_created(
        scenario_id=scenario.scenario_id,
        scenario_type=str(scenario.scenario_type),
        baseline_ref=scenario.baseline_ref,
    )
    return {
        "scenario_id": scenario.scenario_id,
        "status": scenario.status,
        "is_simulation_only": True,
        "is_production_plan": False,
        "review_required": True,
        "audit_event": audit.model_dump(mode="json"),
    }


@router.post("/scenario/{scenario_id}/validate")
def validate_scenario(
    scenario_id: str,
    scenario: ManufacturingTwinScenario,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Evaluate hard constraints on a scenario."""
    if scenario.scenario_id != scenario_id:
        raise HTTPException(
            status_code=400,
            detail="scenario_id in body must match path",
        )
    constraint_results, hard_failures, warnings = evaluate_constraints(scenario)
    return {
        "scenario_id": scenario_id,
        "constraint_results": [c.model_dump() for c in constraint_results],
        "hard_failures": [str(f) for f in hard_failures],
        "warnings": warnings,
        "is_valid": len(hard_failures) == 0,
    }


@router.post("/scenario/{scenario_id}/simulate")
def simulate_scenario_endpoint(
    scenario_id: str,
    scenario: ManufacturingTwinScenario,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Simulate a scenario and return KPI estimates."""
    if scenario.scenario_id != scenario_id:
        raise HTTPException(
            status_code=400,
            detail="scenario_id in body must match path",
        )
    result = simulate_scenario(scenario)
    audit = record_scenario_simulated(
        scenario_id=scenario_id,
        status=str(result.status),
        fidelity=str(result.fidelity),
        constraint_failure_count=len(result.hard_constraint_failures),
    )
    explanation = explain_scenario(scenario, result)
    return {
        "result": result.model_dump(mode="json"),
        "audit_event": audit.model_dump(mode="json"),
        "explanation": explanation,
        "is_simulation_only": True,
        "is_production_plan": False,
    }


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


class CompareRequest(BaseModel):
    baseline_scenario: ManufacturingTwinScenario
    scenario: ManufacturingTwinScenario


@router.post("/compare")
def compare_scenarios_endpoint(
    request: CompareRequest,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Compare a scenario against baseline."""
    baseline_result = simulate_scenario(request.baseline_scenario)
    scenario_result = simulate_scenario(request.scenario)
    comparison = compare_scenarios(baseline_result, scenario_result)
    audit = record_comparison_run(
        baseline_id=request.baseline_scenario.scenario_id,
        scenario_id=request.scenario.scenario_id,
        kpi_diff_count=len(comparison.kpi_diffs),
        unknown_diff_count=len(comparison.unknown_diffs),
    )
    explanation = explain_comparison(comparison)
    return {
        "comparison": comparison.model_dump(mode="json"),
        "audit_event": audit.model_dump(mode="json"),
        "explanation": explanation,
    }


# ---------------------------------------------------------------------------
# Alternatives generation
# ---------------------------------------------------------------------------


class GenerateAlternativesRequest(BaseModel):
    baseline: ManufacturingTwinScenario
    machine_refs: list[str] | None = None
    tool_ref_sets: list[list[str]] | None = None
    cutting_data_candidates: list[dict] | None = None
    quantities: list[int] | None = None
    schedule_refs: list[str] | None = None
    limits: TwinSearchLimits | None = None


@router.post("/alternatives")
def generate_alternatives(
    request: GenerateAlternativesRequest,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Generate alternative scenarios from a baseline."""
    if not request.baseline.is_simulation_only:
        raise HTTPException(status_code=400, detail="Baseline must be simulation-only")
    alternatives = []
    if request.machine_refs:
        alternatives += generate_machine_alternatives(
            request.baseline, request.machine_refs, request.limits
        )
    if request.tool_ref_sets:
        alternatives += generate_tool_alternatives(
            request.baseline, request.tool_ref_sets, request.limits
        )
    if request.cutting_data_candidates:
        alternatives += generate_cutting_data_alternatives(
            request.baseline, request.cutting_data_candidates, request.limits
        )
    if request.quantities:
        alternatives += generate_quantity_alternatives(
            request.baseline, request.quantities, request.limits
        )
    if request.schedule_refs:
        alternatives += generate_schedule_alternatives(
            request.baseline, request.schedule_refs, request.limits
        )
    return {
        "baseline_id": request.baseline.scenario_id,
        "alternatives": [a.model_dump(mode="json") for a in alternatives],
        "count": len(alternatives),
    }


# ---------------------------------------------------------------------------
# Pareto frontier
# ---------------------------------------------------------------------------


class ParetoRequest(BaseModel):
    scenarios: list[ManufacturingTwinScenario]


@router.post("/pareto")
def pareto_frontier(
    request: ParetoRequest,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Compute Pareto frontier across a set of scenarios."""
    results = [simulate_scenario(s) for s in request.scenarios]
    candidates = compute_pareto_frontier(results)
    non_dominated_ids = [c.scenario_id for c in candidates if c.is_non_dominated]
    audit = record_pareto_calculated(
        scenario_ids=[r.scenario_id for r in results],
        non_dominated_count=len(non_dominated_ids),
    )
    return {
        "pareto_candidates": [c.model_dump(mode="json") for c in candidates],
        "non_dominated": non_dominated_ids,
        "audit_event": audit.model_dump(mode="json"),
    }


# ---------------------------------------------------------------------------
# Multi-objective scoring + recommendation
# ---------------------------------------------------------------------------


class RecommendationRequest(BaseModel):
    scenarios: list[ManufacturingTwinScenario]
    objective: ObjectiveType | None = None
    weights: list[ObjectiveWeight] | None = None


@router.post("/recommendation")
def recommendation_endpoint(
    request: RecommendationRequest,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Generate an engineering recommendation from a set of scenarios."""
    results = [simulate_scenario(s) for s in request.scenarios]
    weighted_scores = compute_multi_objective_scores(results, request.weights)
    pareto_candidates = compute_pareto_frontier(results)
    recommendation = generate_recommendation(
        results,
        objective=request.objective,
        weighted_scores=weighted_scores if request.weights else None,
        pareto_candidates=pareto_candidates,
    )
    if recommendation is None:
        return {
            "recommendation": None,
            "reason": "No valid scenarios available.",
            "is_proposed_only": True,
            "is_automatic_application": False,
            "review_required": True,
        }
    audit = record_recommendation_generated(
        scenario_id=recommendation.scenario_id,
        recommendation_type=str(recommendation.recommendation_type),
        data_fidelity=str(recommendation.data_fidelity),
    )
    best_result = next((r for r in results if r.scenario_id == recommendation.scenario_id), None)
    best_scenario = next(
        (s for s in request.scenarios if s.scenario_id == recommendation.scenario_id), None
    )
    explanation = ""
    if best_result and best_scenario:
        explanation = explain_recommendation(recommendation, results)
    return {
        "recommendation": recommendation.model_dump(mode="json"),
        "weighted_scores": [s.model_dump(mode="json") for s in weighted_scores],
        "pareto_candidates": [c.model_dump(mode="json") for c in pareto_candidates],
        "explanation": explanation,
        "audit_event": audit.model_dump(mode="json"),
        "is_proposed_only": True,
        "is_automatic_application": False,
        "review_required": True,
    }


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


class ReviewRequest(BaseModel):
    scenario_id: str
    review_outcome: str
    reviewer: str
    notes: str = ""


@router.post("/scenario/{scenario_id}/review")
def review_scenario(
    scenario_id: str,
    request: ReviewRequest,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Record human review decision on a scenario."""
    if request.scenario_id != scenario_id:
        raise HTTPException(
            status_code=400,
            detail="scenario_id in body must match path",
        )
    audit = record_scenario_reviewed(
        scenario_id=scenario_id,
        review_outcome=request.review_outcome,
        reviewer=request.reviewer,
        notes=request.notes,
    )
    return {
        "scenario_id": scenario_id,
        "review_outcome": request.review_outcome,
        "reviewer": request.reviewer,
        "audit_event": audit.model_dump(mode="json"),
        "is_automatic_application": False,
        "review_required": True,
    }


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------


class StalenessRequest(BaseModel):
    scenario: ManufacturingTwinScenario
    machine_catalog_version: str | None = None
    tool_catalog_version: str | None = None
    material_catalog_version: str | None = None


@router.post("/staleness")
def staleness_check(
    request: StalenessRequest,
    _token: str = Depends(_require_user),  # noqa: B008
):
    """Check whether a scenario is stale and needs re-simulation."""
    current_hash = compute_input_snapshot_hash(
        request.scenario,
        machine_catalog_version=request.machine_catalog_version,
        tool_catalog_version=request.tool_catalog_version,
        material_catalog_version=request.material_catalog_version,
    )
    result = check_staleness(
        scenario=request.scenario,
        current_input_snapshot_hash=current_hash,
        recorded_input_snapshot_hash=request.scenario.input_snapshot_hash,
        recorded_evaluator_version=request.scenario.evaluation_version,
    )
    return result.model_dump(mode="json")
