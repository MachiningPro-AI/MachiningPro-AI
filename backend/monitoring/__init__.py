"""
Level-15 Shop Floor Monitoring and Closed-Loop Feedback.

OBSERVE → COMPARE → DIAGNOSE → RECOMMEND.
NO automatic corrective action.
NO real machine write.
NO fabricated observation data.
"""

from __future__ import annotations

from .alarms import AlarmObservation, analyze_alarms, make_alarm_observation
from .anomaly import (
    AnomalyPolicy,
    AnomalyResult,
    apply_anomaly_policy,
    detect_iqr_anomalies,
    detect_range_anomaly,
    detect_rolling_deviation_anomaly,
    detect_threshold_anomaly,
)
from .comparison import (
    compare_planned_actual,
    detect_cycle_time_deviations,
    detect_process_deviations,
)
from .enums import (
    AlarmSeverity,
    AnomalyMethod,
    ClosedLoopProposalType,
    CycleState,
    DataQuality,
    DeviationType,
    ObservationSource,
    ObservationStatus,
    OEEStatus,
    ProductionEventType,
    QualitySource,
    RecommendationType,
    RootCauseCandidateStatus,
    ToolLifeStatus,
)
from .kpis import (
    compute_availability,
    compute_oee,
    compute_performance,
    compute_performance_kpis,
    compute_quality_kpi,
    compute_rolling_median,
    compute_z_scores,
)
from .learning import (
    anonymize_learning_records,
    create_learning_record,
    validate_learning_record,
)
from .models import (
    ActualToolUsage,
    AlarmAnalytics,
    ClosedLoopProposal,
    EngineeringRecommendation,
    LearningRecord,
    ObservationBaseline,
    OEEResult,
    PerformanceKPIs,
    PlannedActualComparison,
    ProcessDeviation,
    ProductionEvent,
    ProductionObservation,
    QualityObservation,
    RootCauseCandidate,
    ToolLifeFeedback,
    Trend,
    TrendPoint,
)
from .quality import (
    compute_yield,
    make_quality_observation,
    summarize_quality,
)
from .recommendations import (
    generate_recommendations,
    make_closed_loop_proposal,
)
from .root_cause import identify_root_cause_candidates
from .telemetry import (
    make_simulated_observation,
    test_machine_alarm,
    test_machine_cycle_complete,
    test_machine_idle,
    test_machine_running,
    test_missing_telemetry,
    test_program_mismatch,
)
from .tool_feedback import compute_tool_life_feedback, make_tool_usage
from .trends import (
    build_alarm_trend,
    build_cycle_time_trend,
    build_idle_time_trend,
    build_quality_trend,
    build_tool_life_trend,
)

# Safety invariants
NO_AUTOMATIC_CORRECTIVE_ACTION: bool = True
NO_REAL_MACHINE_WRITE: bool = True
OBSERVE_COMPARE_DIAGNOSE_RECOMMEND: str = (
    "OBSERVE → COMPARE → DIAGNOSE → RECOMMEND"
)
CLOSED_LOOP_MODE: str = "PROPOSED_ONLY"

__all__ = [
    # enums
    "AlarmSeverity",
    "AnomalyMethod",
    "ClosedLoopProposalType",
    "CycleState",
    "DataQuality",
    "DeviationType",
    "ObservationSource",
    "ObservationStatus",
    "OEEStatus",
    "ProductionEventType",
    "QualitySource",
    "RecommendationType",
    "RootCauseCandidateStatus",
    "ToolLifeStatus",
    # models
    "ActualToolUsage",
    "AlarmAnalytics",
    "AlarmObservation",
    "AnomalyPolicy",
    "AnomalyResult",
    "ClosedLoopProposal",
    "EngineeringRecommendation",
    "LearningRecord",
    "ObservationBaseline",
    "OEEResult",
    "PerformanceKPIs",
    "PlannedActualComparison",
    "ProcessDeviation",
    "ProductionEvent",
    "ProductionObservation",
    "QualityObservation",
    "RootCauseCandidate",
    "ToolLifeFeedback",
    "Trend",
    "TrendPoint",
    # functions
    "analyze_alarms",
    "anonymize_learning_records",
    "apply_anomaly_policy",
    "build_alarm_trend",
    "build_cycle_time_trend",
    "build_idle_time_trend",
    "build_quality_trend",
    "build_tool_life_trend",
    "compare_planned_actual",
    "compute_availability",
    "compute_oee",
    "compute_performance",
    "compute_performance_kpis",
    "compute_quality_kpi",
    "compute_rolling_median",
    "compute_tool_life_feedback",
    "compute_yield",
    "compute_z_scores",
    "create_learning_record",
    "detect_cycle_time_deviations",
    "detect_iqr_anomalies",
    "detect_process_deviations",
    "detect_range_anomaly",
    "detect_rolling_deviation_anomaly",
    "detect_threshold_anomaly",
    "generate_recommendations",
    "identify_root_cause_candidates",
    "make_alarm_observation",
    "make_closed_loop_proposal",
    "make_quality_observation",
    "make_simulated_observation",
    "make_tool_usage",
    "summarize_quality",
    "test_machine_alarm",
    "test_machine_cycle_complete",
    "test_machine_idle",
    "test_machine_running",
    "test_missing_telemetry",
    "test_program_mismatch",
    "validate_learning_record",
    # safety
    "NO_AUTOMATIC_CORRECTIVE_ACTION",
    "NO_REAL_MACHINE_WRITE",
    "CLOSED_LOOP_MODE",
]
