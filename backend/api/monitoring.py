"""
Level-15 Shop Floor Monitoring API.

Allowed endpoints:
  POST /api/monitoring/ingest-observation
  GET  /api/monitoring/observations
  POST /api/monitoring/compare-planned-actual
  GET  /api/monitoring/performance-summary
  GET  /api/monitoring/alarms
  GET  /api/monitoring/tool-life-feedback
  GET  /api/monitoring/quality-observations
  GET  /api/monitoring/recommendation-candidates
  POST /api/monitoring/compute-oee
  GET  /api/monitoring/trends

Forbidden endpoints (NOT implemented):
  machine-control
  write-machine-parameter
  apply-corrective-action
  update-nc-program
  override-feed
  override-spindle

NO_REAL_MACHINE_WRITE=YES
NO_AUTOMATIC_CORRECTIVE_ACTION=YES
CLOSED_LOOP_MODE=PROPOSED_ONLY
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..monitoring import (
    CLOSED_LOOP_MODE,
    NO_AUTOMATIC_CORRECTIVE_ACTION,
    NO_REAL_MACHINE_WRITE,
    CycleState,
    DataQuality,
    ObservationSource,
    ObservationStatus,
    ProductionObservation,
    compare_planned_actual,
    compute_oee,
    compute_tool_life_feedback,
    detect_cycle_time_deviations,
    detect_process_deviations,
    make_quality_observation,
    make_simulated_observation,
    make_tool_usage,
)
from .auth import verify_token

router = APIRouter(prefix="/api/monitoring", tags=["monitoring"])


def _require_user(
    authorization: str | None = Header(default=None),  # noqa: B008
) -> dict[str, Any]:
    """Bearer token auth; fails closed with 401."""
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class IngestObservationRequest(BaseModel):
    machine_id: str
    job_id: str
    part_reference: str | None = None
    operation_ref: str | None = None
    cycle_state: str = "UNKNOWN"
    actual_cycle_time: float | None = None
    part_count: int | None = None
    good_count: int | None = None
    reject_count: int | None = None
    alarm_codes: list[str] = Field(default_factory=list)
    tool_id: str | None = None
    tool_usage_time: float | None = None
    cutting_runtime: float | None = None
    idle_runtime: float | None = None
    alarm_runtime: float | None = None
    program_reference: str | None = None
    program_hash: str | None = None
    source: str = "MANUAL_ENTRY"


class CompareRequest(BaseModel):
    machine_id: str
    job_id: str
    planned_cycle_time: float | None = None
    planned_cutting_time: float | None = None
    planned_setup_time: float | None = None
    planned_tool_usage: float | None = None
    planned_quantity: int | None = None
    planned_machine: str | None = None
    planned_nc_hash: str | None = None
    actual_cycle_time: float | None = None
    actual_cutting_time: float | None = None
    actual_tool_usage: float | None = None
    actual_completed_quantity: int | None = None
    observed_program_hash: str | None = None
    operation_ref: str | None = None


class OEERequest(BaseModel):
    machine_id: str | None = None
    planned_production_time: float | None = None
    run_time: float | None = None
    ideal_cycle_time: float | None = None
    total_count: int | None = None
    good_count: int | None = None


class ToolFeedbackRequest(BaseModel):
    tool_id: str
    predicted_life: float | None = None
    cutting_time: float | None = None
    observed_life: float | None = None
    machine_id: str | None = None
    job_id: str | None = None


class QualityObsRequest(BaseModel):
    characteristic: str
    measured_value: float | None = None
    nominal: float | None = None
    lower_limit: float | None = None
    upper_limit: float | None = None
    operation: str | None = None
    machine: str | None = None


class AlarmRequest(BaseModel):
    alarm_code: str
    machine_id: str
    duration_seconds: float | None = None
    alarm_text: str | None = None
    job_id: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/ingest-observation")
async def ingest_observation(
    request: IngestObservationRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Ingest a synthetic/manual production observation. No machine write."""
    try:
        cycle_state = CycleState(request.cycle_state)
    except ValueError:
        cycle_state = CycleState.UNKNOWN
    try:
        source = ObservationSource(request.source)
    except ValueError:
        source = ObservationSource.UNKNOWN

    observation = ProductionObservation(
        observation_id=str(uuid.uuid4()),
        machine_id=request.machine_id,
        job_id=request.job_id,
        part_reference=request.part_reference,
        operation_ref=request.operation_ref,
        cycle_state=cycle_state,
        actual_cycle_time=request.actual_cycle_time,
        part_count=request.part_count,
        good_count=request.good_count,
        reject_count=request.reject_count,
        alarm_codes=request.alarm_codes,
        tool_id=request.tool_id,
        tool_usage_time=request.tool_usage_time,
        cutting_runtime=request.cutting_runtime,
        idle_runtime=request.idle_runtime,
        alarm_runtime=request.alarm_runtime,
        program_reference=request.program_reference,
        program_hash=request.program_hash,
        source=source,
        quality=DataQuality.RAW,
        status=ObservationStatus.COMPLETE,
        is_fabricated=False,
    )
    return {
        "observation": observation.model_dump(),
        "is_fabricated": False,
        "no_machine_write": NO_REAL_MACHINE_WRITE,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.get("/observations")
async def get_observations(
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Return available observation sources and status."""
    return {
        "observation_sources": [s.value for s in ObservationSource],
        "cycle_states": [s.value for s in CycleState],
        "no_machine_write": NO_REAL_MACHINE_WRITE,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.post("/compare-planned-actual")
async def compare_planned_actual_endpoint(
    request: CompareRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Compare planned engineering data against actual observation."""
    observation = make_simulated_observation(
        machine_id=request.machine_id,
        job_id=request.job_id,
        actual_cycle_time=request.actual_cycle_time,
        cutting_runtime=request.actual_cutting_time,
        good_count=request.actual_completed_quantity,
        program_hash=request.observed_program_hash,
    )
    if request.operation_ref:
        observation = observation.model_copy(
            update={"operation_ref": request.operation_ref}
        )
    comparison = compare_planned_actual(
        observation=observation,
        planned_cycle_time=request.planned_cycle_time,
        planned_cutting_time=request.planned_cutting_time,
        planned_setup_time=request.planned_setup_time,
        planned_tool_usage=request.planned_tool_usage,
        planned_quantity=request.planned_quantity,
        planned_machine=request.planned_machine,
        planned_nc_hash=request.planned_nc_hash,
    )
    ct_devs = detect_cycle_time_deviations(comparison)
    proc_devs = detect_process_deviations(comparison)
    return {
        "comparison": comparison.model_dump(),
        "cycle_time_deviations": [d.model_dump() for d in ct_devs],
        "process_deviations": [d.model_dump() for d in proc_devs],
        "no_automatic_corrective_action": NO_AUTOMATIC_CORRECTIVE_ACTION,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.post("/compute-oee")
async def compute_oee_endpoint(
    request: OEERequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Compute OEE from valid production observations only."""
    result = compute_oee(
        machine_id=request.machine_id,
        planned_production_time=request.planned_production_time,
        run_time=request.run_time,
        ideal_cycle_time=request.ideal_cycle_time,
        total_count=request.total_count,
        good_count=request.good_count,
    )
    return {
        "oee_result": result.model_dump(),
        "no_fabricated_oee": True,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.get("/performance-summary")
async def get_performance_summary(
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Return performance KPI schema and summary of available metrics."""
    return {
        "available_kpis": [
            "actual_cycle_time",
            "average_cycle_time",
            "median_cycle_time",
            "cycle_time_variance",
            "cutting_time_share",
            "idle_time_share",
            "alarm_time_share",
            "good_count",
            "reject_count",
            "yield_rate",
        ],
        "oee_components": ["availability", "performance", "quality"],
        "no_fabricated_kpis": True,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.get("/alarms")
async def get_alarms(
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Return alarm model schema."""
    from ..monitoring.enums import AlarmSeverity
    return {
        "alarm_severities": [s.value for s in AlarmSeverity],
        "no_fabricated_alarms": True,
        "missing_alarm_data_is_not_zero": True,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.post("/tool-life-feedback")
async def tool_life_feedback(
    request: ToolFeedbackRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Compute tool-life feedback (PROPOSED_ONLY). No tool-offset write."""
    usage = make_tool_usage(
        tool_id=request.tool_id,
        cutting_time=request.cutting_time,
        observed_life=request.observed_life,
        machine_id=request.machine_id,
        job_id=request.job_id,
    )
    feedback = compute_tool_life_feedback(
        tool_id=request.tool_id,
        predicted_life=request.predicted_life,
        actual_usage=usage,
    )
    return {
        "feedback": feedback.model_dump(),
        "is_automatic_action": False,
        "no_tool_offset_write": True,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.post("/quality-observations")
async def ingest_quality_observation(
    request: QualityObsRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Ingest a quality observation. Tolerances from actual data only."""
    obs = make_quality_observation(
        characteristic=request.characteristic,
        measured_value=request.measured_value,
        nominal=request.nominal,
        lower_limit=request.lower_limit,
        upper_limit=request.upper_limit,
        operation=request.operation,
        machine=request.machine,
    )
    return {
        "quality_observation": obs.model_dump(),
        "no_fabricated_tolerances": True,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.post("/recommendation-candidates")
async def get_recommendations(
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Return recommendation types (proposals only, no auto-action)."""
    from ..monitoring.enums import RecommendationType
    return {
        "recommendation_types": [r.value for r in RecommendationType],
        "requires_review": True,
        "is_automatic_action": False,
        "closed_loop_mode": CLOSED_LOOP_MODE,
    }


@router.get("/trends")
async def get_trends(
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Return available trend metrics."""
    return {
        "available_trends": [
            "cycle_time",
            "alarm_count",
            "tool_life",
            "yield_rate",
            "idle_time_share",
        ],
        "closed_loop_mode": CLOSED_LOOP_MODE,
        "no_automatic_corrective_action": NO_AUTOMATIC_CORRECTIVE_ACTION,
    }
