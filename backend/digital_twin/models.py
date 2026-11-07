"""Level-18 Manufacturing Digital Twin — data models.

SIMULATION_ONLY=YES
BASELINE_MUTATION_ALLOWED=NO
SCENARIO_IS_NOT_PRODUCTION_PLAN=YES
OPTIMIZATION_RESULT_IS_NOT_APPROVED=YES
HUMAN_REVIEW_MANDATORY=YES
NO_FABRICATED_DATA=YES
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from .enums import (
    AuditEventType,
    ConstraintFailReason,
    CycleTimeSource,
    EnergyStatus,
    ErrorType,
    FidelityLevel,
    KPIKey,
    ObjectiveType,
    RecommendationType,
    ScenarioStatus,
    ScenarioType,
    StaleReason,
)

# ---------------------------------------------------------------------------
# Digital Twin Scenario
# ---------------------------------------------------------------------------


class ManufacturingTwinScenario(BaseModel):
    """
    Manufacturing Digital Twin Scenario.

    SIMULATION / DECISION SUPPORT only.
    is_simulation_only=True, is_production_plan=False, review_required=True
    baseline_mutation_allowed=False — always immutable.
    """

    scenario_id: str
    scenario_type: ScenarioType = ScenarioType.BASELINE
    baseline_ref: str | None = None
    part_ref: str | None = None
    revision: str | None = None
    material_ref: str | None = None

    # Process references
    process_plan_ref: str | None = None
    machine_ref: str | None = None
    tool_refs: list[str] = Field(default_factory=list)
    holder_refs: list[str] = Field(default_factory=list)
    fixture_ref: str | None = None

    # Plan data
    cutting_data: dict = Field(default_factory=dict)
    setup_plan: dict = Field(default_factory=dict)
    cam_plan_ref: str | None = None
    toolpath_ref: str | None = None
    verification_ref: str | None = None
    nc_ref: str | None = None
    schedule_ref: str | None = None

    # Quantity
    quantity: int | None = None
    batch_size: int | None = None

    # Estimated values (never fabricated)
    estimated_cycle_time_min: float | None = None
    estimated_setup_time_min: float | None = None
    machine_spindle_max_rpm: int | None = None
    machine_axis_count: int | None = None
    machine_travel_x_mm: float | None = None
    machine_travel_y_mm: float | None = None
    machine_travel_z_mm: float | None = None
    machine_spindle_power_kw: float | None = None
    machine_idle_power_kw: float | None = None
    machine_cutting_power_kw: float | None = None
    required_spindle_rpm: float | None = None
    required_axis_count: int | None = None
    part_mass_kg: float | None = None
    toolpath_verified: bool = False

    # Status
    status: ScenarioStatus = ScenarioStatus.DRAFT
    fidelity: FidelityLevel = FidelityLevel.INSUFFICIENT
    warnings: list[str] = Field(default_factory=list)
    provenance: str | None = None

    # Versioning
    twin_model_id: str | None = None
    version: str = "1.0"
    baseline_hash: str | None = None
    scenario_hash: str | None = None
    input_snapshot_hash: str | None = None
    evaluation_version: str = "18.0"

    # Invariants — locked
    is_simulation_only: bool = True
    is_production_plan: bool = False
    review_required: bool = True
    baseline_mutation_allowed: bool = False


# ---------------------------------------------------------------------------
# Scenario KPI
# ---------------------------------------------------------------------------


class ScenarioKPI(BaseModel):
    """
    Scenario KPI result — never fabricated.

    Missing KPIs remain None with unknowns list.
    is_fabricated is always False.
    """

    # Cycle time
    cycle_time_min: float | None = None
    cycle_time_source: CycleTimeSource = CycleTimeSource.UNKNOWN

    # Time components
    setup_time_min: float | None = None
    batch_time_min: float | None = None
    throughput_per_hour: float | None = None

    # Cost
    manufacturing_cost: float | None = None
    cost_currency: str | None = None
    cost_known_subtotal: float | None = None
    cost_unknown_components: list[str] = Field(default_factory=list)

    # Tooling
    tool_life_min: float | None = None
    tool_consumption: float | None = None

    # Risk
    quality_risk_level: str | None = None
    alarm_risk_level: str | None = None

    # Load / lateness
    machine_load_pct: float | None = None
    lateness_min: float | None = None

    # Energy (optional)
    energy_kwh: float | None = None
    energy_status: EnergyStatus = EnergyStatus.INSUFFICIENT_DATA

    # Material
    material_utilization_pct: float | None = None

    # Meta
    fidelity: FidelityLevel = FidelityLevel.INSUFFICIENT
    unknowns: list[str] = Field(default_factory=list)
    is_fabricated: bool = False


# ---------------------------------------------------------------------------
# Constraint result
# ---------------------------------------------------------------------------


class ConstraintResult(BaseModel):
    """Result of a single hard constraint check."""

    constraint_name: str
    passed: bool
    fail_reason: ConstraintFailReason | None = None
    detail: str = ""


# ---------------------------------------------------------------------------
# Simulation result
# ---------------------------------------------------------------------------


class SimulationResult(BaseModel):
    """
    Result of evaluating a ManufacturingTwinScenario.

    SIMULATION / DECISION SUPPORT — never a production plan.
    is_simulation_only=True always.
    """

    scenario_id: str
    status: ScenarioStatus
    kpi: ScenarioKPI
    constraint_results: list[ConstraintResult] = Field(default_factory=list)
    hard_constraint_failures: list[ConstraintFailReason] = Field(default_factory=list)
    fidelity: FidelityLevel = FidelityLevel.INSUFFICIENT
    warnings: list[str] = Field(default_factory=list)
    errors: list[ErrorType] = Field(default_factory=list)
    is_simulation_only: bool = True
    is_production_plan: bool = False


# ---------------------------------------------------------------------------
# Scenario comparison
# ---------------------------------------------------------------------------


class KPIDiff(BaseModel):
    """Absolute and relative difference for one KPI between baseline and scenario."""

    kpi_name: str
    baseline_value: float | None = None
    scenario_value: float | None = None
    absolute_diff: float | None = None
    relative_diff_pct: float | None = None
    improved: bool | None = None  # True=improved, False=worsened, None=unknown


class ScenarioComparison(BaseModel):
    """Comparison of one scenario against baseline KPIs."""

    baseline_id: str
    comparison_id: str
    kpi_diffs: list[KPIDiff] = Field(default_factory=list)
    trade_offs: list[str] = Field(default_factory=list)
    unknown_diffs: list[str] = Field(default_factory=list)
    constraint_delta: str = ""
    is_fabricated: bool = False


# ---------------------------------------------------------------------------
# Multi-objective scoring
# ---------------------------------------------------------------------------


class ObjectiveWeight(BaseModel):
    """Explicit weight for a single objective."""

    objective: ObjectiveType
    weight: float  # 0.0 – 1.0 (normalized by caller)


class MultiObjectiveScore(BaseModel):
    """Weighted score breakdown for a scenario."""

    scenario_id: str
    component_scores: dict[str, float] = Field(default_factory=dict)
    weighted_score: float | None = None
    weights_applied: list[ObjectiveWeight] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Pareto frontier
# ---------------------------------------------------------------------------


class ParetoCandidate(BaseModel):
    """A non-dominated scenario candidate on the Pareto frontier."""

    scenario_id: str
    dominated_by: list[str] = Field(default_factory=list)  # empty = non-dominated
    is_non_dominated: bool = True
    dominated_in: list[KPIKey] = Field(default_factory=list)
    dominates_in: list[KPIKey] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Twin recommendation
# ---------------------------------------------------------------------------


class TwinRecommendation(BaseModel):
    """
    Engineering recommendation from the Digital Twin.

    PROPOSED ONLY — never automatically applied.
    is_proposed_only=True, is_automatic_application=False, review_required=True.
    """

    recommendation_type: RecommendationType
    scenario_id: str
    why: str = ""
    constraints_passed: list[str] = Field(default_factory=list)
    data_fidelity: FidelityLevel = FidelityLevel.INSUFFICIENT
    trade_offs: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    review_required: bool = True
    is_proposed_only: bool = True
    is_automatic_application: bool = False


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class TwinAuditEvent(BaseModel):
    """Audit event for digital twin operations — immutable once written."""

    event_type: AuditEventType
    scenario_id: str
    actor: str = "system"
    timestamp: datetime
    payload: dict = Field(default_factory=dict)
    event_hash: str = ""


# ---------------------------------------------------------------------------
# Search space limits
# ---------------------------------------------------------------------------


class TwinSearchLimits(BaseModel):
    """Limits to prevent combinatorial explosion."""

    max_machines: int = 10
    max_tools: int = 10
    max_parameter_candidates: int = 5
    max_combined_scenarios: int = 50


# ---------------------------------------------------------------------------
# Stale check result
# ---------------------------------------------------------------------------


class StalenessCheck(BaseModel):
    """Result of checking whether a scenario is stale."""

    scenario_id: str
    is_stale: bool = False
    stale_reasons: list[StaleReason] = Field(default_factory=list)
    current_input_snapshot_hash: str = ""
    recorded_input_snapshot_hash: str | None = None
    evaluator_version: str = ""
    checked_at: datetime | None = None
    detail: str = ""
