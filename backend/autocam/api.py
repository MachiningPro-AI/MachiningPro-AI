"""Auto CAM API — MACHININGPRO_AI_AUTO_CAM_END_TO_END_01.

POST /api/autocam/run   — run the 20-stage Auto CAM pipeline
GET  /api/autocam/{plan_id} — retrieve a plan by ID

Safety contract (enforced by orchestrator, not by this router):
  AUTO_CAM_CAN_DISPATCH_CNC=NO
  AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
  AUTO_CAM_CAN_AUTO_APPROVE=NO
  REAL_MACHINE_WRITE_FOUND=NO
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException

from backend.api.auth import verify_token

from .models import AutoCamPlan, AutoCamRequest
from .orchestrator import get_plan, run_auto_cam

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
