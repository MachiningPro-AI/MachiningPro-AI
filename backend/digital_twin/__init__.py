"""Level-18 Manufacturing Digital Twin — module entry.

SAFETY CONSTANTS (all True, never changed):
  NO_AUTOMATIC_APPLICATION = True
  NO_CNC_WRITE = True
  NO_AUTOMATIC_DISPATCH = True
  NO_AUTOMATIC_CAM_CHANGE = True
  NO_AUTOMATIC_GCODE_REGENERATION = True
  NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT = True
  NO_AUTOMATIC_MACHINE_REASSIGNMENT = True
  NO_AUTOMATIC_SCHEDULING_CHANGE = True
  NO_AUTOMATIC_TOOL_SUBSTITUTION = True
  BASELINE_MUTATION_ALLOWED = False
  SCENARIO_IS_NOT_PRODUCTION_PLAN = True
  OPTIMIZED_SCENARIO_IS_NOT_APPROVED = True
  HUMAN_REVIEW_MANDATORY = True
  NO_FABRICATED_TWIN_RESULT = True
  UNKNOWN_INPUTS_STAY_UNKNOWN = True
"""

# Safety constants — module-level, always enforced
NO_AUTOMATIC_APPLICATION: bool = True
NO_CNC_WRITE: bool = True
NO_AUTOMATIC_DISPATCH: bool = True
NO_AUTOMATIC_CAM_CHANGE: bool = True
NO_AUTOMATIC_GCODE_REGENERATION: bool = True
NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT: bool = True
NO_AUTOMATIC_MACHINE_REASSIGNMENT: bool = True
NO_AUTOMATIC_SCHEDULING_CHANGE: bool = True
NO_AUTOMATIC_TOOL_SUBSTITUTION: bool = True
BASELINE_MUTATION_ALLOWED: bool = False
SCENARIO_IS_NOT_PRODUCTION_PLAN: bool = True
OPTIMIZED_SCENARIO_IS_NOT_APPROVED: bool = True
HUMAN_REVIEW_MANDATORY: bool = True
NO_FABRICATED_TWIN_RESULT: bool = True
UNKNOWN_INPUTS_STAY_UNKNOWN: bool = True

from .audit import (  # noqa: E402
    record_comparison_run,
    record_pareto_calculated,
    record_recommendation_generated,
    record_scenario_created,
    record_scenario_reviewed,
    record_scenario_simulated,
    record_scenario_stale,
    verify_audit_integrity,
)
from .comparison import compare_scenarios  # noqa: E402
from .constraints import evaluate_constraints  # noqa: E402
from .enums import (  # noqa: E402
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
from .explainability import (  # noqa: E402
    explain_comparison,
    explain_recommendation,
    explain_scenario,
)
from .generator import (  # noqa: E402
    generate_cutting_data_alternatives,
    generate_machine_alternatives,
    generate_quantity_alternatives,
    generate_schedule_alternatives,
    generate_tool_alternatives,
)
from .models import (  # noqa: E402
    ConstraintResult,
    KPIDiff,
    ManufacturingTwinScenario,
    MultiObjectiveScore,
    ObjectiveWeight,
    ParetoCandidate,
    ScenarioComparison,
    ScenarioKPI,
    SimulationResult,
    StalenessCheck,
    TwinAuditEvent,
    TwinRecommendation,
    TwinSearchLimits,
)
from .recommendation import generate_recommendation  # noqa: E402
from .scoring import compute_multi_objective_scores, compute_pareto_frontier  # noqa: E402
from .simulation import simulate_scenario  # noqa: E402
from .versioning import (  # noqa: E402
    EVALUATOR_VERSION,
    check_staleness,
    compute_input_snapshot_hash,
    compute_scenario_hash,
)

__all__ = [
    # Safety constants
    "NO_AUTOMATIC_APPLICATION",
    "NO_CNC_WRITE",
    "NO_AUTOMATIC_DISPATCH",
    "NO_AUTOMATIC_CAM_CHANGE",
    "NO_AUTOMATIC_GCODE_REGENERATION",
    "NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT",
    "NO_AUTOMATIC_MACHINE_REASSIGNMENT",
    "NO_AUTOMATIC_SCHEDULING_CHANGE",
    "NO_AUTOMATIC_TOOL_SUBSTITUTION",
    "BASELINE_MUTATION_ALLOWED",
    "SCENARIO_IS_NOT_PRODUCTION_PLAN",
    "OPTIMIZED_SCENARIO_IS_NOT_APPROVED",
    "HUMAN_REVIEW_MANDATORY",
    "NO_FABRICATED_TWIN_RESULT",
    "UNKNOWN_INPUTS_STAY_UNKNOWN",
    "EVALUATOR_VERSION",
    # Enums
    "AuditEventType",
    "ConstraintFailReason",
    "CycleTimeSource",
    "EnergyStatus",
    "ErrorType",
    "FidelityLevel",
    "KPIKey",
    "ObjectiveType",
    "RecommendationType",
    "ScenarioStatus",
    "ScenarioType",
    "StaleReason",
    # Models
    "ManufacturingTwinScenario",
    "ScenarioKPI",
    "ConstraintResult",
    "SimulationResult",
    "KPIDiff",
    "ScenarioComparison",
    "ObjectiveWeight",
    "MultiObjectiveScore",
    "ParetoCandidate",
    "TwinRecommendation",
    "TwinAuditEvent",
    "TwinSearchLimits",
    "StalenessCheck",
    # Functions
    "evaluate_constraints",
    "simulate_scenario",
    "compare_scenarios",
    "compute_multi_objective_scores",
    "compute_pareto_frontier",
    "generate_recommendation",
    "generate_machine_alternatives",
    "generate_tool_alternatives",
    "generate_cutting_data_alternatives",
    "generate_quantity_alternatives",
    "generate_schedule_alternatives",
    "explain_scenario",
    "explain_comparison",
    "explain_recommendation",
    "record_scenario_created",
    "record_scenario_simulated",
    "record_comparison_run",
    "record_pareto_calculated",
    "record_recommendation_generated",
    "record_scenario_reviewed",
    "record_scenario_stale",
    "verify_audit_integrity",
    "compute_scenario_hash",
    "compute_input_snapshot_hash",
    "check_staleness",
]
