"""CAM Planning API (Level-9).

Provides a lightweight endpoint for creating a CAM planning candidate job
from upstream feature/material intelligence.

Safety contract
---------------
NO_GCODE=YES             — endpoint never returns G-code.
NO_FABRICATED_DATA=YES   — no synthetic coordinates or assumed data.
CANDIDATE_NOT_VERIFIED   — all outputs are candidates until human review.
SIMULATION_REQUIRED=YES  — every response declares simulation required.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.api.auth import verify_token
from backend.cam_planning.cam_engine import (
    CamPlanningInput,
    FeatureInput,
    create_cam_job,
)
from backend.cam_planning.enums import (
    StockSource,
    StockType,
)
from backend.cam_planning.models import CAMJob
from backend.cam_planning.readiness import check_cam_readiness


def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:
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


router = APIRouter(prefix="/api/cam", tags=["cam-planning"])


class FeatureInputBody(BaseModel):
    feature_id: str
    feature_type: str
    is_confirmed: bool = True
    has_tolerance_evidence: bool = False
    depth_diameter_ratio: float | None = None


class CamPlanRequest(BaseModel):
    part_id: str | None = None
    cad_reference: str | None = None
    material: str | None = None
    machine_type: str | None = None
    machine_requirement_refs: list[str] = Field(default_factory=list)
    features: list[FeatureInputBody] = Field(default_factory=list)
    cutting_data_refs: list[str] = Field(default_factory=list)
    is_2d_only: bool = False
    stock_type: str = "UNKNOWN"
    stock_source: str = "UNKNOWN"
    access_directions: list[str] = Field(default_factory=list)


class CamReadinessSummary(BaseModel):
    is_ready: bool
    cam_plan_status: str
    job_status: str
    blockers: list[str]
    warnings: list[str]
    missing_inputs: list[str]


class CamPlanResponse(BaseModel):
    job_id: str
    status: str
    cam_plan_status: str
    operation_count: int
    setup_count: int
    simulation_required: bool
    warnings: list[str]
    missing_inputs: list[str]
    readiness: CamReadinessSummary
    cam_job: dict


@router.post("/plan")
async def create_cam_plan(
    req: CamPlanRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> CamPlanResponse:
    """Create a CAM planning candidate job from upstream intelligence.

    Returns candidates only — no G-code, no toolpath coordinates.
    Every response sets simulation_required=True.
    """
    try:
        stock_type = StockType(req.stock_type)
    except ValueError:
        stock_type = StockType.UNKNOWN

    try:
        stock_source = StockSource(req.stock_source)
    except ValueError:
        stock_source = StockSource.UNKNOWN

    features = [
        FeatureInput(
            feature_id=f.feature_id,
            feature_type=f.feature_type,
            is_confirmed=f.is_confirmed,
            has_tolerance_evidence=f.has_tolerance_evidence,
            depth_diameter_ratio=f.depth_diameter_ratio,
        )
        for f in req.features
    ]

    inp = CamPlanningInput(
        part_id=req.part_id,
        cad_reference=req.cad_reference,
        material=req.material,
        machine_type=req.machine_type,
        machine_requirement_refs=req.machine_requirement_refs or None,
        features=features or None,
        cutting_data_refs=req.cutting_data_refs or None,
        is_2d_only=req.is_2d_only,
        stock_type=stock_type,
        stock_source=stock_source,
        access_directions=req.access_directions or None,
    )

    job: CAMJob = create_cam_job(inp)
    readiness = check_cam_readiness(job)

    updated_job = job.model_copy(update={
        "status": readiness.job_status,
        "cam_plan_status": readiness.cam_plan_status,
    })

    return CamPlanResponse(
        job_id=updated_job.job_id,
        status=updated_job.status.value,
        cam_plan_status=updated_job.cam_plan_status.value,
        operation_count=updated_job.operation_count,
        setup_count=updated_job.setup_count,
        simulation_required=updated_job.simulation_required,
        warnings=updated_job.warnings,
        missing_inputs=updated_job.missing_inputs,
        readiness=CamReadinessSummary(
            is_ready=readiness.is_ready,
            cam_plan_status=readiness.cam_plan_status.value,
            job_status=readiness.job_status.value,
            blockers=list(readiness.blockers),
            warnings=list(readiness.warnings),
            missing_inputs=list(readiness.missing_inputs),
        ),
        cam_job=updated_job.model_dump(),
    )
