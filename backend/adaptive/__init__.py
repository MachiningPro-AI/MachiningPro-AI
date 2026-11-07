"""
Level-16 Adaptive Manufacturing Intelligence.

Historical + Observed Production Data + Engineering Baseline →
Comparable Manufacturing Cases → Performance Learning →
Prediction → Recommendation Candidates → What-if Evaluation →
Engineering Review.

HARD CONSTRAINTS (all must remain True):
  NO_AUTOMATIC_CNC_CHANGE
  NO_AUTOMATIC_FEED_OVERRIDE
  NO_AUTOMATIC_SPINDLE_OVERRIDE
  NO_AUTOMATIC_TOOL_OFFSET_CHANGE
  NO_AUTOMATIC_WORK_OFFSET_CHANGE
  NO_AUTOMATIC_CAM_MODIFICATION
  NO_AUTOMATIC_TOOLPATH_REGEN
  NO_AUTOMATIC_NC_REGEN
  NO_AUTOMATIC_SCHEDULING_CHANGE
  NO_AUTOMATIC_JOB_DISPATCH
  NO_AUTOMATIC_MACHINE_SELECTION
  NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT
  RECOMMENDATION_ONLY
  HUMAN_REVIEW_MANDATORY
  PREDICTION_IS_NOT_MEASURED_FACT
  RECOMMENDATION_IS_NOT_APPROVED_CHANGE
  CORRELATION_IS_NOT_CAUSATION
"""

from __future__ import annotations

from .audit import (
    audit_data_drift_detected,
    audit_model_drift_detected,
    audit_model_evaluated,
    audit_model_trained,
    audit_prediction_created,
    audit_recommendation_created,
    audit_recommendation_reviewed,
    audit_what_if_evaluated,
)
from .drift import detect_data_drift, detect_model_drift
from .enums import (
    AdaptiveAuditEventType,
    AdaptiveRecommendationType,
    AlarmRiskLevel,
    DriftStatus,
    ModelStatus,
    ModelType,
    PredictionFidelity,
    PredictionObjective,
    PredictionTarget,
    QualityRiskLevel,
    RecommendationStatus,
    SplitRole,
    WhatIfStatus,
)
from .features import extract_features
from .models import (
    AdaptiveAuditEvent,
    AdaptiveRecommendation,
    AlarmRiskResult,
    DriftReport,
    FeatureVector,
    ManufacturingLearningRecord,
    ModelParams,
    ModelSpec,
    PredictionResult,
    QualityRiskResult,
    SimilarCase,
    SplitResult,
    TradeOffAnalysis,
    TradeOffCandidate,
    WhatIfScenario,
)
from .predictors import (
    LinearRegressionPredictor,
    MedianPredictor,
    NearestNeighborPredictor,
)
from .recommendations import (
    build_recommendation_from_prediction,
    generate_cutting_data_recommendations,
    generate_machine_recommendations,
    generate_tool_recommendations,
    review_recommendation,
)
from .records import (
    create_learning_record,
    make_test_dataset_aluminium_turning,
    make_test_record_missing_data,
    make_test_record_out_of_domain,
    validate_learning_record,
)
from .registry import ModelRegistry, get_registry, reset_registry
from .risk import estimate_alarm_risk, estimate_quality_risk
from .similarity import find_similar_cases
from .splitting import split_records
from .tradeoff import build_trade_off_analysis, compute_pareto_front
from .whatif import run_what_if_machine_change, run_what_if_vc_change

# ---------------------------------------------------------------------------
# Hard safety constants — must all remain True
# ---------------------------------------------------------------------------

NO_AUTOMATIC_CNC_CHANGE: bool = True
NO_AUTOMATIC_FEED_OVERRIDE: bool = True
NO_AUTOMATIC_SPINDLE_OVERRIDE: bool = True
NO_AUTOMATIC_TOOL_OFFSET_CHANGE: bool = True
NO_AUTOMATIC_WORK_OFFSET_CHANGE: bool = True
NO_AUTOMATIC_CAM_MODIFICATION: bool = True
NO_AUTOMATIC_TOOLPATH_REGEN: bool = True
NO_AUTOMATIC_NC_REGEN: bool = True
NO_AUTOMATIC_SCHEDULING_CHANGE: bool = True
NO_AUTOMATIC_JOB_DISPATCH: bool = True
NO_AUTOMATIC_MACHINE_SELECTION: bool = True
NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT: bool = True
RECOMMENDATION_ONLY: bool = True
HUMAN_REVIEW_MANDATORY: bool = True
PREDICTION_IS_NOT_MEASURED_FACT: bool = True
RECOMMENDATION_IS_NOT_APPROVED_CHANGE: bool = True
CORRELATION_IS_NOT_CAUSATION: bool = True

__all__ = [
    # constants
    "NO_AUTOMATIC_CNC_CHANGE",
    "NO_AUTOMATIC_FEED_OVERRIDE",
    "NO_AUTOMATIC_SPINDLE_OVERRIDE",
    "NO_AUTOMATIC_TOOL_OFFSET_CHANGE",
    "NO_AUTOMATIC_WORK_OFFSET_CHANGE",
    "NO_AUTOMATIC_CAM_MODIFICATION",
    "NO_AUTOMATIC_TOOLPATH_REGEN",
    "NO_AUTOMATIC_NC_REGEN",
    "NO_AUTOMATIC_SCHEDULING_CHANGE",
    "NO_AUTOMATIC_JOB_DISPATCH",
    "NO_AUTOMATIC_MACHINE_SELECTION",
    "NO_AUTOMATIC_CUTTING_DATA_REPLACEMENT",
    "RECOMMENDATION_ONLY",
    "HUMAN_REVIEW_MANDATORY",
    "PREDICTION_IS_NOT_MEASURED_FACT",
    "RECOMMENDATION_IS_NOT_APPROVED_CHANGE",
    "CORRELATION_IS_NOT_CAUSATION",
    # enums
    "PredictionFidelity",
    "ModelStatus",
    "RecommendationStatus",
    "AdaptiveRecommendationType",
    "PredictionObjective",
    "QualityRiskLevel",
    "AlarmRiskLevel",
    "PredictionTarget",
    "SplitRole",
    "WhatIfStatus",
    "DriftStatus",
    "AdaptiveAuditEventType",
    "ModelType",
    # models
    "ManufacturingLearningRecord",
    "FeatureVector",
    "SimilarCase",
    "ModelSpec",
    "ModelParams",
    "PredictionResult",
    "QualityRiskResult",
    "AlarmRiskResult",
    "AdaptiveRecommendation",
    "WhatIfScenario",
    "TradeOffCandidate",
    "TradeOffAnalysis",
    "DriftReport",
    "AdaptiveAuditEvent",
    "SplitResult",
    # records
    "create_learning_record",
    "validate_learning_record",
    "make_test_dataset_aluminium_turning",
    "make_test_record_missing_data",
    "make_test_record_out_of_domain",
    # features
    "extract_features",
    # similarity
    "find_similar_cases",
    # splitting
    "split_records",
    # predictors
    "MedianPredictor",
    "NearestNeighborPredictor",
    "LinearRegressionPredictor",
    # risk
    "estimate_quality_risk",
    "estimate_alarm_risk",
    # recommendations
    "generate_cutting_data_recommendations",
    "generate_machine_recommendations",
    "generate_tool_recommendations",
    "review_recommendation",
    "build_recommendation_from_prediction",
    # what-if
    "run_what_if_vc_change",
    "run_what_if_machine_change",
    # trade-off
    "build_trade_off_analysis",
    "compute_pareto_front",
    # registry
    "ModelRegistry",
    "get_registry",
    "reset_registry",
    # drift
    "detect_data_drift",
    "detect_model_drift",
    # audit
    "audit_model_trained",
    "audit_model_evaluated",
    "audit_prediction_created",
    "audit_recommendation_created",
    "audit_recommendation_reviewed",
    "audit_what_if_evaluated",
    "audit_data_drift_detected",
    "audit_model_drift_detected",
]
