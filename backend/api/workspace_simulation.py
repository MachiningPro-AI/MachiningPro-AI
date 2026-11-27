"""
Workspace Simulation Endpoint.

POST /api/workspace-sim/run

Accepts VerificationSegments (from workspace-cam toolpath groups or existing
toolpath endpoints) plus stock/tool geometry, runs the existing Level-11
run_simulation() engine, and returns a structured SimulationResult.

Safety contract:
  NO_CNC_DISPATCH=YES
  NO_AUTO_APPROVE=YES
  is_dispatchable=false
  production_released=false
  SIMULATION_OFFLINE_ONLY=YES        (HR-12)
  SIMULATION_RESULT_NOT_APPROVAL=YES (HR-13)
  HARD_RULE_11=YES                   — missing input → NOT_VERIFIABLE, never PASS
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator

from backend.api.auth import verify_token
from backend.verification.enums import (
    StockFidelity,
    StockShape,
    VerificationProfileEnum,
)
from backend.verification.models import SimulationRequest, SimulationResult
from backend.verification.simulation import run_simulation
from backend.verification.stock import StockModel

router = APIRouter(prefix="/api/workspace-sim", tags=["workspace-sim"])

_SAFETY = {
    "is_dispatchable": False,
    "production_released": False,
    "simulation_offline_only": True,
    "simulation_result_is_not_machining_approval": True,
    "no_cnc_dispatch": True,
    "no_auto_approve": True,
    "hard_rule_11": "MISSING_INPUT_NEVER_PASS",
    "hard_rule_12": "OFFLINE_SIMULATION_ONLY",
    "hard_rule_13": "RESULT_NOT_APPROVAL",
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


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class WsSimSegment(BaseModel):
    """Lightweight segment shape for workspace simulation request."""
    segment_id: str | None = None
    start_x: float
    start_y: float
    start_z: float
    end_x: float
    end_y: float
    end_z: float
    motion_type: str = "CUT"
    is_cutting: bool = True
    operation_id: str | None = None
    tool_id: str | None = None

    @model_validator(mode='after')
    def _derive_is_cutting(self) -> WsSimSegment:
        _NON_CUTTING = {"RAPID", "RETRACT", "DWELL", "TOOL_CHANGE"}
        if self.motion_type.upper() in _NON_CUTTING:
            self.is_cutting = False
        return self


class WsStockBbox(BaseModel):
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float


class WsSimRequest(BaseModel):
    toolpath_id: str
    segments: list[WsSimSegment] = Field(default_factory=list)
    profile: str = "GEOMETRY_ONLY"
    # Tool geometry — None means NOT_VERIFIABLE for tool-dependent checks
    tool_diameter_mm: float | None = None
    tool_length_mm: float | None = None
    tool_flute_length_mm: float | None = None
    holder_diameter_mm: float | None = None
    holder_length_mm: float | None = None
    # Stock
    stock_bbox: WsStockBbox | None = None
    # Part bbox (for gouge checks)
    part_bbox_min: list[float] | None = None
    part_bbox_max: list[float] | None = None
    # Machine travel limits
    machine_travel_x_mm: float | None = None
    machine_travel_y_mm: float | None = None
    machine_travel_z_mm: float | None = None


# ---------------------------------------------------------------------------
# Response models (re-wraps SimulationResult with safety envelope)
# ---------------------------------------------------------------------------

class CheckResultFE(BaseModel):
    status: str
    severity: str
    warnings: list[str]
    errors: list[str]
    issues: list[dict[str, Any]]


class VisualizationFE(BaseModel):
    cutting_points: list[list[float]]
    rapid_points: list[list[float]]
    stock_bbox: dict[str, float] | None
    part_bbox: dict[str, float] | None
    collision_points: list[list[float]]
    gouge_points: list[list[float]]
    remaining_stock_note: str | None


class WsSimResponse(BaseModel):
    session_id: str
    toolpath_id: str
    simulation_status: str
    verification_state: str
    is_verified: bool
    profile: str
    checks: dict[str, CheckResultFE]
    initial_stock_volume_mm3: float | None
    remaining_stock_volume_mm3: float | None
    removed_volume_mm3: float | None
    stock_removal_fidelity: str
    # Phase B: gouge semantics split
    gouge_exact: str = "NOT_VERIFIABLE"
    gouge_conservative_warning: str = "NOT_PERFORMED"
    # Phase B fidelity semantics (beta.5, KL-07 RESOLVED)
    gouge_geometry_method: str = "BREP_BOOLEAN_OCC"
    gouge_geometry_fidelity: str = "NOT_AVAILABLE"
    gouge_volume_method: str = "TETRAHEDRAL_MESH_INTEGRATION"
    gouge_volume_fidelity: str = "APPROXIMATE_NUMERICAL_INTEGRATION"
    # Phase C: stock volume label
    stock_volume_method: str = "NOT_VERIFIABLE"
    approx_remaining_volume_mm3: float | None = None
    approx_removed_volume_mm3: float | None = None
    # Phase D: missing geometry blockers
    holder_geometry_required: bool = True
    fixture_geometry_required: bool = True
    visualization: VisualizationFE
    warnings: list[str]
    errors: list[str]
    resource_limit_hit: bool
    safety: dict[str, Any]
    offline_only: bool = True
    simulation_result_is_not_machining_approval: bool = True


def _coerce_profile(raw: str) -> VerificationProfileEnum:
    try:
        return VerificationProfileEnum(raw.upper())
    except ValueError:
        return VerificationProfileEnum.GEOMETRY_ONLY


def _to_stock(bbox: WsStockBbox) -> StockModel:
    return StockModel(
        shape=StockShape.BOX,
        fidelity=StockFidelity.ANALYTIC_PRIMITIVE,
        min_x_mm=bbox.min_x,
        min_y_mm=bbox.min_y,
        min_z_mm=bbox.min_z,
        max_x_mm=bbox.max_x,
        max_y_mm=bbox.max_y,
        max_z_mm=bbox.max_z,
    )


def _sv(obj: object) -> str:
    """Return StrEnum .value or str()."""
    return obj.value if hasattr(obj, "value") else str(obj)  # type: ignore[return-value]


def _adapt_result(res: SimulationResult) -> WsSimResponse:
    viz_src = res.visualization
    viz = VisualizationFE(
        cutting_points=list(viz_src.cutting_points),
        rapid_points=list(viz_src.rapid_points),
        stock_bbox=viz_src.stock_bbox,
        part_bbox=viz_src.part_bbox,
        collision_points=list(viz_src.collision_points),
        gouge_points=list(viz_src.gouge_points),
        remaining_stock_note=viz_src.remaining_stock_note,
    )
    checks_fe: dict[str, CheckResultFE] = {}
    for k, v in res.checks.items():
        checks_fe[k] = CheckResultFE(
            status=_sv(v.status),
            severity=_sv(v.severity),
            warnings=list(v.warnings),
            errors=list(v.errors),
            issues=[
                {
                    "issue_id": iss.issue_id,
                    "check_type": _sv(iss.check_type),
                    "severity": _sv(iss.severity),
                    "message": iss.message,
                }
                for iss in v.issues
            ],
        )
    # Phase B: derive gouge_conservative_warning from part_gouge check status
    part_gouge_chk = res.checks.get("part_gouge")
    if part_gouge_chk is not None:
        pg_status = _sv(part_gouge_chk.status)
        if pg_status in {"PASS"}:
            gouge_conservative = "CONSERVATIVE_PASS"
        elif pg_status in {"PARTIAL"}:
            gouge_conservative = "CONSERVATIVE_WARNING"
        elif pg_status in {"FAIL"}:
            gouge_conservative = "CONSERVATIVE_FAIL"
        elif pg_status in {"INSUFFICIENT_DATA", "NOT_PERFORMED"}:
            gouge_conservative = pg_status
        else:
            gouge_conservative = pg_status
    else:
        gouge_conservative = "NOT_PERFORMED"

    # Phase C: stock volume method
    if res.remaining_stock_volume_mm3 is not None:
        stock_vol_method = "VOXEL_APPROXIMATE"
    else:
        stock_vol_method = "NOT_VERIFIABLE"

    # Phase B: extract gouge_exact status and fidelity from simulation check result
    gouge_exact_chk = res.checks.get("gouge_exact")
    if gouge_exact_chk is not None:
        gouge_exact_status = _sv(gouge_exact_chk.status)
        ge_ev = gouge_exact_chk.evidence if hasattr(gouge_exact_chk, "evidence") else {}
        gouge_geom_method = ge_ev.get("gouge_geometry_method", "BREP_BOOLEAN_OCC")
        gouge_geom_fidelity = ge_ev.get("gouge_geometry_fidelity", "NOT_AVAILABLE")
        gouge_vol_method = ge_ev.get("gouge_volume_method", "TETRAHEDRAL_MESH_INTEGRATION")
        gouge_vol_fidelity = ge_ev.get("gouge_volume_fidelity", "APPROXIMATE_NUMERICAL_INTEGRATION")
    else:
        gouge_exact_status = "NOT_VERIFIABLE"
        gouge_geom_method = "BREP_BOOLEAN_OCC"
        gouge_geom_fidelity = "NOT_AVAILABLE"
        gouge_vol_method = "TETRAHEDRAL_MESH_INTEGRATION"
        gouge_vol_fidelity = "APPROXIMATE_NUMERICAL_INTEGRATION"

    return WsSimResponse(
        session_id=res.session_id,
        toolpath_id=res.toolpath_id,
        simulation_status=_sv(res.simulation_status),
        verification_state=_sv(res.verification_state),
        is_verified=res.is_verified,
        profile=_sv(res.profile),
        checks=checks_fe,
        initial_stock_volume_mm3=res.initial_stock_volume_mm3,
        remaining_stock_volume_mm3=res.remaining_stock_volume_mm3,
        removed_volume_mm3=res.removed_volume_mm3,
        stock_removal_fidelity=_sv(res.stock_removal_fidelity),
        gouge_exact=gouge_exact_status,
        gouge_conservative_warning=gouge_conservative,
        gouge_geometry_method=gouge_geom_method,
        gouge_geometry_fidelity=gouge_geom_fidelity,
        gouge_volume_method=gouge_vol_method,
        gouge_volume_fidelity=gouge_vol_fidelity,
        stock_volume_method=stock_vol_method,
        approx_remaining_volume_mm3=res.remaining_stock_volume_mm3,
        approx_removed_volume_mm3=res.removed_volume_mm3,
        holder_geometry_required=True,
        fixture_geometry_required=True,
        visualization=viz,
        warnings=list(res.warnings),
        errors=list(res.errors),
        resource_limit_hit=res.resource_limit_hit,
        safety=_SAFETY,
    )


@router.post("/run", response_model=WsSimResponse)
def workspace_sim_run(
    req: WsSimRequest,
    authorization: str | None = Header(default=None),
) -> WsSimResponse:
    """
    Run offline toolpath simulation using the Level-11 verification engine.

    This is OFFLINE ONLY — no machine communication takes place.
    A VERIFIED result does NOT imply machining approval.
    Missing tool or stock data → affected checks return NOT_VERIFIABLE / INSUFFICIENT_DATA.
    """
    _require_user(authorization)

    if not req.segments:
        return WsSimResponse(
            session_id="no-segments",
            toolpath_id=req.toolpath_id,
            simulation_status="FAILED",
            verification_state="BLOCKED",
            is_verified=False,
            profile=req.profile,
            checks={},
            initial_stock_volume_mm3=None,
            remaining_stock_volume_mm3=None,
            removed_volume_mm3=None,
            stock_removal_fidelity="UNKNOWN",
            visualization=VisualizationFE(
                cutting_points=[], rapid_points=[],
                stock_bbox=None, part_bbox=None,
                collision_points=[], gouge_points=[],
                remaining_stock_note=None,
            ),
            warnings=["NO_SEGMENTS: no toolpath segments provided — simulation cannot run"],
            errors=["NO_SEGMENTS"],
            resource_limit_hit=False,
            safety=_SAFETY,
        )

    from backend.verification.models import VerificationSegment

    ver_segs = [
        VerificationSegment(
            segment_id=s.segment_id or f"ws_seg_{i}",
            start_x=s.start_x,
            start_y=s.start_y,
            start_z=s.start_z,
            end_x=s.end_x,
            end_y=s.end_y,
            end_z=s.end_z,
            motion_type=s.motion_type,
            is_cutting=s.is_cutting,
            operation_id=s.operation_id,
            tool_id=s.tool_id,
        )
        for i, s in enumerate(req.segments)
    ]

    stock = _to_stock(req.stock_bbox) if req.stock_bbox else None

    part_min: tuple[float, float, float] | None = None
    part_max: tuple[float, float, float] | None = None
    if req.part_bbox_min and len(req.part_bbox_min) >= 3:
        part_min = (req.part_bbox_min[0], req.part_bbox_min[1], req.part_bbox_min[2])
    if req.part_bbox_max and len(req.part_bbox_max) >= 3:
        part_max = (req.part_bbox_max[0], req.part_bbox_max[1], req.part_bbox_max[2])

    sim_req = SimulationRequest(
        toolpath_id=req.toolpath_id,
        segments=ver_segs,
        profile=_coerce_profile(req.profile),
        tool_diameter_mm=req.tool_diameter_mm,
        tool_length_mm=req.tool_length_mm,
        tool_flute_length_mm=req.tool_flute_length_mm,
        holder_diameter_mm=req.holder_diameter_mm,
        holder_length_mm=req.holder_length_mm,
        stock=stock,
        machine_travel_x_mm=req.machine_travel_x_mm,
        machine_travel_y_mm=req.machine_travel_y_mm,
        machine_travel_z_mm=req.machine_travel_z_mm,
        part_bbox_min=part_min,
        part_bbox_max=part_max,
    )

    result = run_simulation(sim_req)
    return _adapt_result(result)
