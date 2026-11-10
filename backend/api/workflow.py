"""Level-19 Manufacturing Workflow API Router.

Endpoints:
  POST   /api/workflow                      — create workflow
  POST   /api/workflow/{id}/run             — run workflow
  POST   /api/workflow/{id}/resume          — resume workflow
  POST   /api/workflow/{id}/retry           — retry blocked/failed stages
  GET    /api/workflow/{id}                 — get workflow status
  GET    /api/workflow/{id}/stages          — get stage statuses
  GET    /api/workflow/{id}/plan            — get manufacturing plan
  POST   /api/workflow/{id}/cancel          — cancel workflow

Safety invariants:
  NO_CNC_WRITE=YES
  NO_AUTO_DISPATCH=YES
  NO_AUTO_APPROVAL=YES
  NO_MACHINE_CONTROL_ENDPOINTS=YES
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.workflow.engine import WorkflowEngine
from backend.workflow.enums import WorkflowMode, WorkflowObjective, WorkflowStage
from backend.workflow.models import ManufacturingWorkflow

from .auth import verify_token

router = APIRouter(prefix="/api/workflow", tags=["workflow"])


def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:  # noqa: B008
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

# In-memory workflow store (no DB required for Level 19)
_WORKFLOWS: dict[str, ManufacturingWorkflow] = {}
_engine = WorkflowEngine()


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_or_404(workflow_id: str) -> ManufacturingWorkflow:
    wf = _WORKFLOWS.get(workflow_id)
    if wf is None:
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_id!r} not found")
    return wf


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
    _WORKFLOWS[wf.workflow_id] = wf
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/run")
def run_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Run the manufacturing analysis workflow."""
    wf = _get_or_404(workflow_id)
    _engine.run_workflow(wf)
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/resume")
def resume_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Resume a paused/partial workflow, skipping already-passed stages."""
    wf = _get_or_404(workflow_id)
    _engine.resume_workflow(wf)
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/retry")
def retry_workflow(
    workflow_id: str,
    req: RetryRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> WorkflowResponse:
    """Retry a specific FAILED or BLOCKED stage."""
    wf = _get_or_404(workflow_id)
    _engine.retry_stage(wf, req.stage)
    return _serialize_workflow(wf)


@router.post("/{workflow_id}/cancel")
def cancel_workflow(workflow_id: str, _auth: dict = Depends(_require_user)) -> WorkflowResponse:  # noqa: B008
    """Cancel the workflow cleanly."""
    wf = _get_or_404(workflow_id)
    _engine.cancel_workflow(wf)
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
