"""
Level-15 Monitoring Models.

Planned vs Actual.  OBSERVE → COMPARE → DIAGNOSE → RECOMMEND.
NO automatic corrective action.
NO fabricated observation data.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

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


class ProductionObservation(BaseModel):
    """
    Observed shop-floor data for one job/operation cycle.

    is_fabricated MUST stay False.
    Missing fields remain None (not zero).
    """

    observation_id: str
    machine_id: str
    job_id: str
    part_reference: str | None = None
    operation_ref: str | None = None
    timestamp_start: str | None = None
    timestamp_end: str | None = None

    cycle_state: CycleState = CycleState.UNKNOWN
    program_reference: str | None = None
    program_hash: str | None = None
    part_count: int | None = None
    good_count: int | None = None
    reject_count: int | None = None

    spindle_runtime: float | None = None
    cutting_runtime: float | None = None
    idle_runtime: float | None = None
    alarm_runtime: float | None = None

    actual_cycle_time: float | None = None
    actual_feed: float | None = None
    actual_spindle_speed: float | None = None

    tool_id: str | None = None
    tool_usage_time: float | None = None
    tool_change_event: bool = False

    alarm_codes: list[str] = Field(default_factory=list)
    quality_results: list[str] = Field(default_factory=list)

    source: ObservationSource = ObservationSource.UNKNOWN
    quality: DataQuality = DataQuality.UNKNOWN
    status: ObservationStatus = ObservationStatus.UNKNOWN
    warnings: list[str] = Field(default_factory=list)

    is_fabricated: bool = False


class PlannedActualComparison(BaseModel):
    """
    Comparison of planned engineering data against actual observations.

    planned_* fields come from upstream levels (Level-7 cycle time, etc.).
    actual_* fields come from ProductionObservation only.
    """

    comparison_id: str
    observation_ref: str
    job_ref: str
    machine_ref: str
    operation_ref: str | None = None

    planned_cycle_time: float | None = None
    actual_cycle_time: float | None = None
    cycle_time_delta: float | None = None
    cycle_time_relative_delta: float | None = None

    planned_cutting_time: float | None = None
    actual_cutting_time: float | None = None

    planned_setup_time: float | None = None
    actual_setup_time: float | None = None

    planned_tool_usage: float | None = None
    actual_tool_usage: float | None = None

    planned_quantity: int | None = None
    actual_completed_quantity: int | None = None

    planned_machine: str | None = None
    actual_machine: str | None = None

    planned_nc_hash: str | None = None
    observed_program_hash: str | None = None

    deviations: list[str] = Field(default_factory=list)
    data_quality: DataQuality = DataQuality.UNKNOWN
    warnings: list[str] = Field(default_factory=list)


class ProcessDeviation(BaseModel):
    """A detected deviation between planned and actual values."""

    deviation_id: str
    deviation_type: DeviationType
    comparison_ref: str
    observation_ref: str | None = None
    absolute_delta: float | None = None
    relative_delta: float | None = None
    threshold_used: float | None = None
    evidence: str = ""
    is_confirmed: bool = False


class ProductionEvent(BaseModel):
    """
    A discrete production event observed on the shop floor.

    Event deduplication: event_id MUST be stable for the same occurrence.
    """

    event_id: str
    event_type: ProductionEventType
    machine_id: str
    job_id: str | None = None
    operation_ref: str | None = None
    timestamp: str
    details: dict[str, Any] = Field(default_factory=dict)
    source: ObservationSource = ObservationSource.UNKNOWN
    is_duplicate: bool = False


class AlarmObservation(BaseModel):
    """
    One alarm occurrence observed from the shop floor.

    alarm_text is None unless the data source explicitly provides it.
    Do NOT invent alarm descriptions.
    """

    alarm_obs_id: str
    alarm_code: str
    alarm_text: str | None = None
    severity: AlarmSeverity = AlarmSeverity.UNKNOWN
    start: str | None = None
    end: str | None = None
    duration_seconds: float | None = None
    machine_id: str
    job_id: str | None = None
    operation_ref: str | None = None
    source: ObservationSource = ObservationSource.UNKNOWN


class AlarmAnalytics(BaseModel):
    """Aggregate analysis of alarm observations. No root-cause claims."""

    machine_id: str | None = None
    total_alarm_count: int = 0
    total_alarm_duration: float | None = None
    alarm_frequency_per_hour: float | None = None
    repeat_alarm_candidates: list[str] = Field(default_factory=list)
    operation_associated: dict[str, int] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    data_quality: DataQuality = DataQuality.UNKNOWN


class ActualToolUsage(BaseModel):
    """
    Observed tool usage data.

    All fields are None if no telemetry is available (not zero).
    """

    tool_usage_id: str
    tool_id: str
    machine_id: str | None = None
    job_id: str | None = None
    cutting_time: float | None = None
    spindle_time: float | None = None
    parts_produced: int | None = None
    tool_change_count: int | None = None
    observed_life: float | None = None
    source: ObservationSource = ObservationSource.UNKNOWN
    data_quality: DataQuality = DataQuality.UNKNOWN
    warnings: list[str] = Field(default_factory=list)


class ToolLifeFeedback(BaseModel):
    """
    Tool-life feedback comparing predicted vs observed.

    PROPOSED_ONLY — no automatic tool-offset write.
    """

    feedback_id: str
    tool_id: str
    predicted_life: float | None = None
    observed_life: float | None = None
    status: ToolLifeStatus = ToolLifeStatus.INSUFFICIENT_DATA
    relative_delta: float | None = None
    data_quality: DataQuality = DataQuality.UNKNOWN
    is_automatic_action: bool = False


class QualityObservation(BaseModel):
    """
    One dimensional quality measurement.

    tolerances MUST come from actual data, not invented.
    """

    quality_obs_id: str
    characteristic: str
    nominal: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    measured_value: float | None = None
    pass_fail: bool | None = None
    operation: str | None = None
    tool: str | None = None
    machine: str | None = None
    timestamp: str | None = None
    source: QualitySource = QualitySource.UNKNOWN
    data_quality: DataQuality = DataQuality.UNKNOWN


class OEEResult(BaseModel):
    """
    OEE = Availability × Performance × Quality.

    oee is None unless all three components are valid.
    """

    oee_id: str
    machine_id: str | None = None
    planned_production_time: float | None = None
    run_time: float | None = None
    availability: float | None = None
    ideal_cycle_time: float | None = None
    total_count: int | None = None
    performance: float | None = None
    good_count: int | None = None
    quality: float | None = None
    oee: float | None = None
    status: OEEStatus = OEEStatus.INSUFFICIENT_DATA
    warnings: list[str] = Field(default_factory=list)


class PerformanceKPIs(BaseModel):
    """
    Factual performance KPIs derived from observations.

    Missing observations = None (not zero).
    """

    kpi_id: str
    machine_id: str | None = None
    job_id: str | None = None
    observation_count: int = 0
    actual_cycle_times: list[float] = Field(default_factory=list)
    average_cycle_time: float | None = None
    median_cycle_time: float | None = None
    cycle_time_variance: float | None = None
    cutting_time_share: float | None = None
    idle_time_share: float | None = None
    alarm_time_share: float | None = None
    good_count: int | None = None
    reject_count: int | None = None
    yield_rate: float | None = None
    data_quality: DataQuality = DataQuality.UNKNOWN
    warnings: list[str] = Field(default_factory=list)


class TrendPoint(BaseModel):
    """One data point in a time-series trend."""

    timestamp: str
    value: float
    label: str | None = None


class Trend(BaseModel):
    """Time-series trend for one KPI/metric."""

    trend_id: str
    metric: str
    machine_id: str | None = None
    job_id: str | None = None
    points: list[TrendPoint] = Field(default_factory=list)
    data_quality: DataQuality = DataQuality.UNKNOWN


class ObservationBaseline(BaseModel):
    """
    Observed baseline for comparison.

    Does NOT automatically overwrite engineering baseline.
    """

    baseline_id: str
    machine_id: str | None = None
    operation_ref: str | None = None
    rolling_median_cycle_time: float | None = None
    validated_historical_average: float | None = None
    sample_count: int = 0
    data_quality: DataQuality = DataQuality.UNKNOWN
    is_engineering_baseline: bool = False


class AnomalyPolicy(BaseModel):
    """Policy for deterministic anomaly detection."""

    policy_id: str
    metric: str
    method: AnomalyMethod
    threshold: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    window_size: int | None = None
    z_score_limit: float | None = None
    iqr_multiplier: float | None = None


class AnomalyResult(BaseModel):
    """Result of anomaly detection against a policy."""

    anomaly_id: str
    policy_ref: str
    metric: str
    value: float
    is_anomaly: bool
    method: AnomalyMethod
    details: str = ""


class RootCauseCandidate(BaseModel):
    """
    Correlation-based root cause candidate.

    status MUST be CANDIDATE or NOT_CONFIRMED.
    Causal proof is never claimed from correlation alone.
    """

    candidate_id: str
    status: RootCauseCandidateStatus = RootCauseCandidateStatus.CANDIDATE
    observation_ref: str | None = None
    comparison_ref: str | None = None
    evidence: list[str] = Field(default_factory=list)
    correlated_deviations: list[str] = Field(default_factory=list)
    correlated_alarms: list[str] = Field(default_factory=list)
    suggested_direction: str = ""
    is_confirmed: bool = False
    is_causal_proof: bool = False


class EngineeringRecommendation(BaseModel):
    """
    Engineering recommendation for review.

    is_automatic_action MUST stay False.
    is_applied MUST stay False at creation.
    """

    recommendation_id: str
    recommendation_type: RecommendationType
    candidate_ref: str | None = None
    rationale: str = ""
    requires_review: bool = True
    is_automatic_action: bool = False
    is_applied: bool = False


class ClosedLoopProposal(BaseModel):
    """
    Closed-loop candidate proposal.

    PROPOSED_ONLY.
    No automatic write to Level-6 cutting data or Level-12 NC.
    """

    proposal_id: str
    proposal_type: ClosedLoopProposalType
    observation_ref: str | None = None
    comparison_ref: str | None = None
    proposed_value: float | None = None
    current_value: float | None = None
    rationale: str = ""
    is_proposed_only: bool = True
    is_automatic_write: bool = False


class LearningRecord(BaseModel):
    """
    Normalized record for future learning dataset.

    Provenance fields must be preserved.
    Sensitive identifiers are anonymized by default.
    """

    record_id: str
    material: str | None = None
    feature_process: str | None = None
    machine_class: str | None = None
    tool_id: str | None = None
    planned_cycle_time: float | None = None
    actual_cycle_time: float | None = None
    tool_life: float | None = None
    quality_outcome: str | None = None
    alarm_outcome: str | None = None
    cutting_parameters: dict[str, Any] = Field(default_factory=dict)
    source: ObservationSource = ObservationSource.UNKNOWN
    data_quality: DataQuality = DataQuality.UNKNOWN
    is_anonymized: bool = True
    anonymization_policy: str = "DEFAULT"
    provenance_hash: str | None = None
