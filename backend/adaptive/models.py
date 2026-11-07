"""Level-16 Adaptive Manufacturing Intelligence Pydantic Models."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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


class ManufacturingLearningRecord(BaseModel):
    record_id: str
    part_family: str | None = None
    feature_family: str | None = None
    material: str | None = None
    material_condition: str | None = None
    machine_class: str | None = None
    machine_id_anonymized: str | None = None
    tool_family: str | None = None
    tool_id_anonymized: str | None = None
    operation_type: str | None = None
    planned_cutting_data: dict[str, Any] = Field(default_factory=dict)
    observed_cutting_data: dict[str, Any] = Field(default_factory=dict)
    planned_cycle_time: float | None = None
    actual_cycle_time: float | None = None
    planned_tool_life: float | None = None
    actual_tool_life: float | None = None
    quality_result: str | None = None
    alarm_summary: str | None = None
    source: str = "UNKNOWN"
    provenance: str | None = None
    data_quality: str = "UNKNOWN"
    timestamp: str | None = None
    is_fabricated: bool = False
    is_test_only: bool = False
    split_role: SplitRole | None = None


class FeatureVector(BaseModel):
    record_id: str
    features: dict[str, float | None] = Field(default_factory=dict)
    missing_features: list[str] = Field(default_factory=list)
    is_complete: bool = False
    data_quality: str = "UNKNOWN"
    out_of_domain: bool = False
    out_of_domain_reasons: list[str] = Field(default_factory=list)


class SimilarCase(BaseModel):
    case_id: str
    record_ref: str
    similarity_score: float
    similarity_factors: dict[str, float] = Field(default_factory=dict)
    matched_features: list[str] = Field(default_factory=list)
    actual_cycle_time: float | None = None
    actual_tool_life: float | None = None
    quality_result: str | None = None


class ModelSpec(BaseModel):
    model_id: str
    version: str
    target: PredictionTarget
    model_type: ModelType = ModelType.HISTORICAL_MEDIAN
    training_data_hash: str | None = None
    feature_schema_version: str = "1.0"
    training_timestamp: str | None = None
    sample_count: int = 0
    train_mae: float | None = None
    validation_mae: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)
    status: ModelStatus = ModelStatus.TRAINED
    is_fabricated_accuracy: bool = False


class ModelParams(BaseModel):
    """Serialized model parameters — interpretable types only."""

    model_type: ModelType
    target: PredictionTarget
    median_value: float | None = None
    mean_value: float | None = None
    slope: float | None = None
    intercept: float | None = None
    feature_name: str | None = None
    sample_count: int = 0
    training_records: list[str] = Field(default_factory=list)
    stale: bool = False


class PredictionResult(BaseModel):
    prediction_id: str
    target: PredictionTarget
    model_ref: str | None = None
    engineering_baseline: float | None = None
    historical_prediction: float | None = None
    predicted_value: float | None = None
    fidelity: PredictionFidelity = PredictionFidelity.INSUFFICIENT
    sample_count: int = 0
    similar_case_ids: list[str] = Field(default_factory=list)
    uncertainty_description: str = ""
    warnings: list[str] = Field(default_factory=list)
    is_fabricated: bool = False
    out_of_domain: bool = False


class QualityRiskResult(BaseModel):
    prediction_id: str
    risk_level: QualityRiskLevel = QualityRiskLevel.INSUFFICIENT
    reject_rate: float | None = None
    sample_count: int = 0
    fidelity: PredictionFidelity = PredictionFidelity.INSUFFICIENT
    factors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_fabricated: bool = False


class AlarmRiskResult(BaseModel):
    prediction_id: str
    risk_level: AlarmRiskLevel = AlarmRiskLevel.INSUFFICIENT
    alarm_rate: float | None = None
    sample_count: int = 0
    fidelity: PredictionFidelity = PredictionFidelity.INSUFFICIENT
    factors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    is_fabricated: bool = False


class AdaptiveRecommendation(BaseModel):
    recommendation_id: str
    recommendation_type: AdaptiveRecommendationType
    current_state: dict[str, Any] = Field(default_factory=dict)
    proposed_state: dict[str, Any] = Field(default_factory=dict)
    objective: PredictionObjective = PredictionObjective.BALANCED
    evidence: list[str] = Field(default_factory=list)
    model_ref: str | None = None
    sample_count: int = 0
    fidelity: PredictionFidelity = PredictionFidelity.INSUFFICIENT
    predicted_effect: dict[str, Any] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = True
    status: RecommendationStatus = RecommendationStatus.PROPOSED
    is_automatic_application: bool = False


class WhatIfScenario(BaseModel):
    scenario_id: str
    description: str
    parameter_changes: dict[str, Any] = Field(default_factory=dict)
    baseline_values: dict[str, Any] = Field(default_factory=dict)
    predicted_outputs: dict[str, Any] = Field(default_factory=dict)
    status: WhatIfStatus = WhatIfStatus.INSUFFICIENT_DATA
    fidelity: PredictionFidelity = PredictionFidelity.INSUFFICIENT
    mutates_baseline: bool = False
    sample_count: int = 0
    warnings: list[str] = Field(default_factory=list)


class TradeOffCandidate(BaseModel):
    candidate_id: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    objectives: dict[str, float | None] = Field(default_factory=dict)
    is_pareto_optimal: bool = False
    trade_offs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class TradeOffAnalysis(BaseModel):
    analysis_id: str
    objective_names: list[str] = Field(default_factory=list)
    candidates: list[TradeOffCandidate] = Field(default_factory=list)
    pareto_front_ids: list[str] = Field(default_factory=list)
    no_single_best: bool = True
    warnings: list[str] = Field(default_factory=list)


class DriftReport(BaseModel):
    report_id: str
    drift_status: DriftStatus = DriftStatus.INSUFFICIENT_DATA
    reference_hash: str | None = None
    current_hash: str | None = None
    reference_sample_count: int = 0
    current_sample_count: int = 0
    drifted_features: list[str] = Field(default_factory=list)
    drift_details: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    review_required: bool = False


class AdaptiveAuditEvent(BaseModel):
    event_id: str
    event_type: AdaptiveAuditEventType
    timestamp: str
    actor: str = "system"
    model_ref: str | None = None
    recommendation_ref: str | None = None
    prediction_ref: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class SplitResult(BaseModel):
    total: int = 0
    train_count: int = 0
    validation_count: int = 0
    test_count: int = 0
    train_ids: list[str] = Field(default_factory=list)
    validation_ids: list[str] = Field(default_factory=list)
    test_ids: list[str] = Field(default_factory=list)
    group_aware: bool = False
    warnings: list[str] = Field(default_factory=list)
