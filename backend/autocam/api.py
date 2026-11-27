"""Auto CAM API — MACHININGPRO_AI_AUTO_CAM_END_TO_END_01.

POST /api/autocam/run                       — run the 20-stage Auto CAM pipeline
GET  /api/autocam/{plan_id}                 — retrieve a plan by ID
POST /api/autocam/{plan_id}/cost-input      — submit cost inputs, recompute S17
GET  /api/autocam/{plan_id}/report/{format} — download plan report (JSON/CSV/PDF/XLSX/ZIP)

Safety contract (enforced by orchestrator, not by this router):
  AUTO_CAM_CAN_DISPATCH_CNC=NO
  AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
  AUTO_CAM_CAN_AUTO_APPROVE=NO
  REAL_MACHINE_WRITE_FOUND=NO
  REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import Response

from backend.api.auth import verify_token

from .cost_estimate import compute_autocam_cost
from .models import AutoCamCostInput, AutoCamPlan, AutoCamRequest
from .orchestrator import _get_store, get_plan, run_auto_cam
from .report_bridge import generate_autocam_report

router = APIRouter(prefix="/api/autocam", tags=["autocam"])

_SAFETY = {
    "AUTO_CAM_CAN_DISPATCH_CNC": False,
    "AUTO_CAM_CAN_RELEASE_PRODUCTION": False,
    "AUTO_CAM_CAN_AUTO_APPROVE": False,
    "REAL_MACHINE_WRITE_FOUND": False,
    "DISPATCH_GATE": "ALWAYS_BLOCKED",
    "SIMULATION_REQUIRED": True,
}


def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


@router.post("/run", response_model=AutoCamPlan, status_code=200)
def run_autocam(
    request: AutoCamRequest,
    authorization: str | None = Header(default=None),
) -> AutoCamPlan:
    """Execute the 20-stage Auto CAM orchestration pipeline.

    Safety invariants are hardcoded in the orchestrator and cannot be
    overridden by any field in AutoCamRequest.
    """
    _require_user(authorization)

    # Safety: enforce is_dispatchable=False regardless of request field
    if request.is_dispatchable or request.production_released:
        raise HTTPException(
            400,
            detail={
                "error_code": "SAFETY_INVARIANT_VIOLATION",
                "message": "is_dispatchable and production_released must be false",
                "safety": _SAFETY,
            },
        )

    return run_auto_cam(request)


@router.get("/{plan_id}", response_model=AutoCamPlan)
def get_autocam_plan(
    plan_id: str,
    authorization: str | None = Header(default=None),
) -> AutoCamPlan:
    """Retrieve a previously computed Auto CAM plan by ID."""
    _require_user(authorization)
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            404,
            detail={
                "error_code": "PLAN_NOT_FOUND",
                "plan_id": plan_id,
            },
        )
    return plan


@router.post("/{plan_id}/cost-input", response_model=AutoCamPlan)
def submit_cost_input(
    plan_id: str,
    cost_input: AutoCamCostInput,
    authorization: str | None = Header(default=None),
) -> AutoCamPlan:
    """Submit user-provided cost rates and recompute the S17 cost estimate.

    COST_ANALYSIS_DOES_NOT_APPROVE_MANUFACTURING=True always.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    No CNC dispatch. No production release. No auto-approval.
    """
    _require_user(authorization)
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            404,
            detail={"error_code": "PLAN_NOT_FOUND", "plan_id": plan_id},
        )
    # Recompute cost estimate from existing cycle_time + machine + new inputs
    new_estimate = compute_autocam_cost(plan.cycle_time, plan.machine, cost_input)
    updated_plan = plan.model_copy(update={
        "cost_estimate": new_estimate,
        "cost_estimate_status": new_estimate.total_status,
    })
    _get_store().save(updated_plan)
    return updated_plan


_MIME: dict[str, str] = {
    "JSON": "application/json",
    "CSV": "text/csv",
    "PDF": "application/pdf",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    # KL-20 RESOLVED (beta.4): DOCX wired via existing docx_exporter.py
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "ZIP": "application/zip",
}


@router.get("/{plan_id}/report/{fmt}")
def download_report(
    plan_id: str,
    fmt: str,
    language: str = "EN",
    authorization: str | None = Header(default=None),
) -> Response:
    """Download an Auto CAM plan report.

    Supported formats: JSON, CSV, PDF, XLSX, DOCX, ZIP
    KL-20 RESOLVED: DOCX now supported via existing docx_exporter.py.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False — read-only.
    """
    _require_user(authorization)
    plan = get_plan(plan_id)
    if plan is None:
        raise HTTPException(
            404,
            detail={"error_code": "PLAN_NOT_FOUND", "plan_id": plan_id},
        )
    fmt_upper = fmt.upper()
    if fmt_upper not in _MIME:
        raise HTTPException(
            400,
            detail={
                "error_code": "UNSUPPORTED_FORMAT",
                "format": fmt,
                "supported": list(_MIME.keys()),
            },
        )
    try:
        item = generate_autocam_report(plan, fmt_upper, language=language)
    except Exception as exc:
        raise HTTPException(
            500,
            detail={
                "error_code": "REPORT_GENERATION_FAILED",
                "detail": str(exc),
            },
        ) from exc

    return Response(
        content=item.content,
        media_type=item.mime_type,
        headers={
            "Content-Disposition": f'attachment; filename="{item.filename}"',
            "X-Report-Engineering-State-Changed": "false",
            "X-Is-Dispatchable": "false",
        },
    )
