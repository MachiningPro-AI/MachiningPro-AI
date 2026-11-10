"""Level-19/20 Manufacturing Workflow API Router.

Endpoints:
  POST   /api/workflow                      — create workflow
  POST   /api/workflow/{id}/run             — run workflow
  POST   /api/workflow/{id}/resume          — resume workflow
  POST   /api/workflow/{id}/retry           — retry blocked/failed stages
  GET    /api/workflow/{id}                 — get workflow status
  GET    /api/workflow/{id}/stages          — get stage statuses
  GET    /api/workflow/{id}/plan            — get manufacturing plan
  POST   /api/workflow/{id}/cancel          — cancel workflow
  GET    /api/workflow/history              — recent workflows (Level 20)

Safety invariants:
  NO_CNC_WRITE=YES
  NO_AUTO_DISPATCH=YES
  NO_AUTO_APPROVAL=YES
  NO_MACHINE_CONTROL_ENDPOINTS=YES

Level-20 persistence:
  WORKFLOW_STORAGE=SQLITE
  RESTART_RECOVERY=YES
  FAIL_CLOSED=YES  — WorkflowStoreError → 503
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..observability import metrics
from ..observability.correlation import get_request_id
from ..persistence import WorkflowStoreError, get_workflow_store
from ..workflow.engine import WorkflowEngine
from ..workflow.enums import WorkflowMode, WorkflowObjective, WorkflowStage
from ..workflow.models import ManufacturingWorkflow
from .auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workflow", tags=["workflow"])

_engine = WorkflowEngine()

# Concurrency: one lock per workflow_id prevents two simultaneous mutations
_wf_locks: dict[str, Any] = {}
import threading  # noqa: E402

_locks_lock = threading.Lock()


def _get_wf_lock(workflow_id: str) -> threading.Lock:
    with _locks_lock:
        if workflow_id not in _wf_locks:
            _wf_locks[workflow_id] = threading.Lock()
        return _wf_locks[workflow_id]


def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:  # noqa: B008
    """Bearer token auth; fails closed with 401."""
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        metrics.increment(metrics.AUTH_FAILED)
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateWorkflowRequest(BaseModel):
    part_reference: str
    revision: str = "REV-A"
    source_file_ref: str | None = None
    requested_mode: WorkflowMode = WorkflowMode.FULL_MANUFACTURING_PLAN
    objective: WorkflowObjective = WorkflowObjective.BALANCED
    material_ref: str | None = None
    quantity: int = Field(default=1, ge=1)
    stock_ref: str | None = None


class WorkflowResponse(BaseModel):
    workflow_id: str
    part_reference: str
    revision: str
    requested_mode: str
    objective: str
    status: str
    current_stage: str | None
    created_at: datetime
    updated_at: datetime
    material_ref: str | None
    quantity: int
    stock_ref: str | None
    final_plan_ref: str | None
    blocking_issue_count: int
    known_unknown_count: int
    review_item_count: int
    audit_event_count: int


class StageStatusResponse(BaseModel):
    stage: str
    status: str
    duration_ms: float | None
    warnings: list[str]
    errors: list[str]
    blocking_reasons: list[str]
    review_required: bool


class RetryRequest(BaseModel):
    stage: WorkflowStage


class PlanResponse(BaseModel):
    plan_id: str
    workflow_id: str
    production_approved: bool = False
    dispatched: bool = False
    machine_started: bool = False
    part: dict[str, Any] | None = None
    revision: dict[str, Any] | None = None
    material: dict[str, Any] | None = None
    quantity: dict[str, Any] | None = None
    recommended_machine: dict[str, Any] | None = None
    cycle_time: dict[str, Any] | None = None
    cost_rfq: dict[str, Any] | None = None
    nc_status: dict[str, Any] | None = None
    blocking_issues: list[dict[str, Any]]
    known_unknowns: list[dict[str, Any]]
    review_items: list[dict[str, Any]]
    alternative_plans: list[dict[str, Any]]
    created_at: datetime


class WorkflowHistoryItem(BaseModel):
    workflow_id: str
    part_reference: str
    status: str
    created_at: str
    updated_at: str
    objective: str | None = None
    current_stage: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(workflow_id: str) -> ManufacturingWorkflow:
    try:
        store = get_workflow_store()
        wf = store.load(workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        logger.error(
            "Persistence error loading workflow %s request_id=%s: %s",
            workflow_id,
            get_request_id(),
            exc,
        )
        raise HTTPException(503, detail="Persistence unavailable — try again shortly") from exc
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id!r} not found")
    return wf


def _persist(wf: ManufacturingWorkflow) -> None:
    try:
        get_workflow_store().save(wf)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        logger.error(
            "Failed to persist workflow %s request_id=%s: %s",
            wf.workflow_id,
            get_request_id(),
            exc,
        )
        raise HTTPException(503, detail="Workflow created but could not be persisted") from exc


def _serialize_workflow(wf: ManufacturingWorkflow) -> WorkflowResponse:
    return WorkflowResponse(
        workflow_id=wf.workflow_id,
        part_reference=wf.part_reference,
        revision=wf.revision,
        requested_mode=str(wf.requested_mode),
        objective=str(wf.objective),
        status=str(wf.status),
        current_stage=str(wf.current_stage) if wf.current_stage else None,
        created_at=wf.created_at,
        updated_at=wf.updated_at,
        material_ref=wf.material_ref,
        quantity=wf.quantity,
        stock_ref=wf.stock_ref,
        final_plan_ref=wf.final_plan_ref,
        blocking_issue_count=len(wf.blocking_issues),
        known_unknown_count=len(wf.known_unknowns),
        review_item_count=len(wf.review_items),
        audit_event_count=len(wf.audit_log),
    )


def _serialize_ev(ev) -> dict[str, Any] | None:
    if ev is None:
        return None
    return {"value": ev.value, "label": str(ev.label), "source": ev.source}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/history")
def list_workflow_history(
    limit: int = 20,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> list[WorkflowHistoryItem]:
    """Return recent workflows for the history UI panel."""
    limit = max(1, min(limit, 100))
    try:
        rows = get_workflow_store().list_recent(limit)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    return [WorkflowHistoryItem(**r) for r in rows]


@router.post("", status_code=201)
def create_workflow(
    req: CreateWorkflowRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> WorkflowResponse:
    """Create a new manufacturing workflow (does not run it)."""
    wf = _engine.create_workflow(
        part_reference=req.part_reference,
        revision=req.revision,
        source_file_ref=req.source_file_ref,
        requested_mode=req.requested_mode,
        objective=req.objective,
        material_ref=req.material_ref,
        quantity=req.quantity,
        stock_ref=req.stock_ref,
    )
    _persist(wf)
    metrics.increment(metrics.WORKFLOW_CREATED)
    logger.info(
        "Workflow created workflow_id=%s part=%s request_id=%s",
        wf.workflow_id,
        wf.part_reference,
        get_request_id(),
    )
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/run")
def run_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Run the manufacturing analysis workflow."""
    wf = _get_or_404(workflow_id)
    lock = _get_wf_lock(workflow_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, detail="Workflow is already being modified — try again shortly")
    try:
        _engine.run_workflow(wf)
        _persist(wf)
        metrics.increment(metrics.WORKFLOW_RUN)
    finally:
        lock.release()
    logger.info(
        "Workflow run workflow_id=%s status=%s request_id=%s",
        workflow_id,
        wf.status,
        get_request_id(),
    )
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/resume")
def resume_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Resume a paused/partial/interrupted workflow, skipping already-passed stages."""
    wf = _get_or_404(workflow_id)
    lock = _get_wf_lock(workflow_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, detail="Workflow is already being modified")
    try:
        _engine.resume_workflow(wf)
        _persist(wf)
    finally:
        lock.release()
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/retry")
def retry_workflow(
    workflow_id: str,
    req: RetryRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> WorkflowResponse:
    """Retry a specific FAILED or BLOCKED stage."""
    wf = _get_or_404(workflow_id)
    lock = _get_wf_lock(workflow_id)
    if not lock.acquire(blocking=False):
        raise HTTPException(409, detail="Workflow is already being modified")
    try:
        _engine.retry_stage(wf, req.stage)
        _persist(wf)
    finally:
        lock.release()
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/cancel")
def cancel_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Cancel the workflow cleanly."""
    wf = _get_or_404(workflow_id)
    _engine.cancel_workflow(wf)
    _persist(wf)
    return _serialize_workflow(wf)


@router.get("/{workflow_id}")
def get_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Get the current workflow status."""
    wf = _get_or_404(workflow_id)
    return _serialize_workflow(wf)


@router.get("/{workflow_id}/stages")
def get_stages(workflow_id: str, _auth: dict = Depends(_require_user)) -> list[StageStatusResponse]:  # noqa: B008
    """Get status of all stages."""
    wf = _get_or_404(workflow_id)
    stages = []
    for stage in WorkflowStage:
        result = wf.stage_results.get(stage)
        if result:
            stages.append(
                StageStatusResponse(
                    stage=str(stage),
                    status=str(result.status),
                    duration_ms=result.duration_ms,
                    warnings=result.warnings,
                    errors=result.errors,
                    blocking_reasons=result.blocking_reasons,
                    review_required=result.review_required,
                )
            )
        else:
            stages.append(
                StageStatusResponse(
                    stage=str(stage),
                    status="NOT_STARTED",
                    duration_ms=None,
                    warnings=[],
                    errors=[],
                    blocking_reasons=[],
                    review_required=False,
                )
            )
    return stages


@router.get("/{workflow_id}/plan")
def get_plan(workflow_id: str, _auth: dict = Depends(_require_user)) -> PlanResponse:  # noqa: B008
    """Get the manufacturing plan summary."""
    wf = _get_or_404(workflow_id)
    if wf.final_plan is None:
        raise HTTPException(
            status_code=404,
            detail="Manufacturing plan not yet generated — run the workflow first",
        )

    plan = wf.final_plan
    return PlanResponse(
        plan_id=plan.plan_id,
        workflow_id=plan.workflow_id,
        production_approved=False,
        dispatched=False,
        machine_started=False,
        part=_serialize_ev(plan.part),
        revision=_serialize_ev(plan.revision),
        material=_serialize_ev(plan.material),
        quantity=_serialize_ev(plan.quantity),
        recommended_machine=_serialize_ev(plan.recommended_machine),
        cycle_time=_serialize_ev(plan.cycle_time),
        cost_rfq=_serialize_ev(plan.cost_rfq),
        nc_status=_serialize_ev(plan.nc_status),
        blocking_issues=[
            {
                "stage": str(bi.stage),
                "code": bi.code,
                "description": bi.description,
                "required_action": bi.required_action,
                "blocking": bi.blocking,
            }
            for bi in plan.blocking_issues
        ],
        known_unknowns=[
            {
                "category": ku.category,
                "description": ku.description,
                "stage": str(ku.stage) if ku.stage else None,
            }
            for ku in plan.known_unknowns
        ],
        review_items=[
            {
                "category": ri.category,
                "description": ri.description,
                "stage": str(ri.stage),
                "mandatory": ri.mandatory,
            }
            for ri in plan.review_items
        ],
        alternative_plans=[
            {
                "plan_type": str(ap.plan_type),
                "description": ap.description,
                "machine_id": ap.machine_id,
                "tool_ids": ap.tool_ids,
                "evidence": str(ap.evidence),
            }
            for ap in plan.alternative_plans
        ],
        created_at=plan.created_at,
    )
