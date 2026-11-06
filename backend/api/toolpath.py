"""Toolpath Generation API (Level-10).

Provides lightweight endpoints for generating vendor-neutral toolpath geometry
from upstream CAM planning candidate inputs (Level 9).

Safety contract
---------------
NO_GCODE=YES             — endpoint never returns G-code or NC code.
NO_FABRICATED_DATA=YES   — no synthetic coordinates, no assumed clearance,
                           no assumed stepdown/stepover, no assumed WCS.
COLLISION_CHECK=NOT_PERFORMED  — declared on every generated toolpath.
GOUGE_CHECK=NOT_PERFORMED      — declared on every generated toolpath.
FIXTURE_CHECK=NOT_PERFORMED    — declared on every generated toolpath.
MACHINE_COLLISION_CHECK=NOT_PERFORMED  — declared on every toolpath.
SIMULATION_REQUIRED=YES        — every response declares simulation required.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from backend.api.auth import verify_token
from backend.toolpath.cycle_time import (
    bridge_to_cycle_time,
    extract_cycle_time_input,
)
from backend.toolpath.enums import (
    ClearanceSource,
    CompensationSide,
    PocketStrategy,
    ProfileSide,
    TurningMotionType,
)
from backend.toolpath.generators import (
    ChamferInput,
    DrillInput,
    FaceMillInput,
    PeckDrillInput,
    PocketInput,
    ProfileInput,
    SlotInput,
    TurningInput,
    generate_chamfer_toolpath,
    generate_drill_toolpath,
    generate_face_mill_toolpath,
    generate_peck_drill_toolpath,
    generate_pocket_toolpath,
    generate_profile_toolpath,
    generate_slot_toolpath,
    generate_turning_toolpath,
)
from backend.toolpath.models import Toolpath


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


router = APIRouter(prefix="/api/toolpath", tags=["toolpath"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class DrillToolpathRequest(BaseModel):
    operation_ref: str
    hole_x: float
    hole_y: float
    hole_top_z: float
    hole_depth_mm: float
    peck_depth_mm: float | None = None
    clearance_z: float | None = None
    clearance_source: str = "UNKNOWN"
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)


class ProfileToolpathRequest(BaseModel):
    operation_ref: str
    contour_points: list[tuple[float, float]]
    contour_z: float
    tool_diameter_mm: float | None = None
    profile_side: str = "UNKNOWN"
    compensation_side: str = "CENTERLINE"
    clearance_z: float | None = None
    clearance_source: str = "UNKNOWN"
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)
    closed: bool = True


class FaceMillToolpathRequest(BaseModel):
    operation_ref: str
    region_x_min: float
    region_x_max: float
    region_y_min: float
    region_y_max: float
    face_z: float
    tool_diameter_mm: float | None = None
    stepover_mm: float | None = None
    clearance_z: float | None = None
    clearance_source: str = "UNKNOWN"
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)


class PocketToolpathRequest(BaseModel):
    operation_ref: str
    boundary_points: list[tuple[float, float]]
    pocket_top_z: float
    pocket_bottom_z: float
    tool_diameter_mm: float | None = None
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    strategy: str = "OFFSET"
    clearance_z: float | None = None
    clearance_source: str = "UNKNOWN"
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)


class SlotToolpathRequest(BaseModel):
    operation_ref: str
    slot_start: tuple[float, float]
    slot_end: tuple[float, float]
    slot_z: float
    slot_width_mm: float | None = None
    slot_depth_mm: float | None = None
    tool_diameter_mm: float | None = None
    clearance_z: float | None = None
    clearance_source: str = "UNKNOWN"
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)


class ChamferToolpathRequest(BaseModel):
    operation_ref: str
    contour_points: list[tuple[float, float]]
    contour_z: float
    tool_diameter_mm: float | None = None
    tool_angle_deg: float | None = None
    chamfer_depth_mm: float | None = None
    clearance_z: float | None = None
    clearance_source: str = "UNKNOWN"
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)


class TurningToolpathRequest(BaseModel):
    operation_ref: str
    turning_motion_type: str
    start_z: float
    end_z: float
    start_x: float
    end_x: float
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)
    clearance_x: float | None = None
    clearance_source: str = "UNKNOWN"


class ToolpathMetricsSummary(BaseModel):
    cut_length_mm: float
    link_or_rapid_length_mm: float
    total_length_mm: float
    segment_count: int
    retract_count: int
    depth_level_count: int
    max_depth_mm: float | None
    is_exact: bool


class VerificationRequirements(BaseModel):
    collision_check: str
    gouge_check: str
    fixture_check: str
    machine_collision_check: str
    note: str
    simulation_required: bool


class CycleTimeBridgeSummary(BaseModel):
    cut_path_mm: float | None
    total_path_mm: float | None
    path_length_type: str
    path_length_source: str
    cycle_time_ready: bool
    missing_inputs: list[str]
    limitations: list[str]


class ToolpathResponse(BaseModel):
    toolpath_id: str
    operation_ref: str
    status: str
    fidelity: str
    simulation_required: bool
    is_verified: bool
    toolpath_summary: str
    toolpaths: list[dict]
    toolpath_metrics: ToolpathMetricsSummary
    toolpath_fidelity: str
    verification_requirements: VerificationRequirements
    cycle_time_bridge: CycleTimeBridgeSummary
    warnings: list[str]
    missing_inputs: list[str]


def _toolpath_to_response(tp: Toolpath) -> ToolpathResponse:
    """Convert a generated Toolpath to API response format."""
    from backend.toolpath.enums import ToolpathFidelity

    fidelity_val = tp.fidelity if hasattr(tp, "fidelity") else "NOT_GENERATED"
    fidelity_enum = (
        ToolpathFidelity(str(fidelity_val))
        if isinstance(fidelity_val, str)
        else fidelity_val
    )

    ct_input = extract_cycle_time_input(
        operation_ref=tp.operation_ref,
        toolpath_id=tp.toolpath_id,
        metrics=tp.metrics,
        fidelity=fidelity_enum,
    )
    ct_bridge = bridge_to_cycle_time(ct_input)

    return ToolpathResponse(
        toolpath_id=tp.toolpath_id,
        operation_ref=tp.operation_ref,
        status=tp.status.value,
        fidelity=str(fidelity_val),
        simulation_required=tp.simulation_required,
        is_verified=tp.is_verified,
        toolpath_summary=(
            f"status={tp.status.value} segments={tp.metrics.segment_count} "
            f"cut_length={tp.metrics.cut_length_mm:.3f}mm fidelity={fidelity_val}"
        ),
        toolpaths=[seg.model_dump() for seg in tp.segments],
        toolpath_metrics=ToolpathMetricsSummary(
            cut_length_mm=tp.metrics.cut_length_mm,
            link_or_rapid_length_mm=tp.metrics.link_or_rapid_length_mm,
            total_length_mm=tp.metrics.total_length_mm,
            segment_count=tp.metrics.segment_count,
            retract_count=tp.metrics.retract_count,
            depth_level_count=tp.metrics.depth_level_count,
            max_depth_mm=tp.metrics.max_depth_mm,
            is_exact=tp.metrics.is_exact,
        ),
        toolpath_fidelity=str(fidelity_val),
        verification_requirements=VerificationRequirements(
            collision_check=tp.verification.collision_check.value,
            gouge_check=tp.verification.gouge_check.value,
            fixture_check=tp.verification.fixture_check.value,
            machine_collision_check=tp.verification.machine_collision_check.value,
            note=tp.verification.note,
            simulation_required=tp.simulation_required,
        ),
        cycle_time_bridge=CycleTimeBridgeSummary(
            cut_path_mm=ct_bridge.cut_path_mm,
            total_path_mm=ct_bridge.total_path_mm,
            path_length_type=ct_bridge.path_length_type.value,
            path_length_source=ct_bridge.path_length_source,
            cycle_time_ready=ct_bridge.cycle_time_ready,
            missing_inputs=ct_bridge.missing_inputs,
            limitations=ct_bridge.limitations,
        ),
        warnings=tp.warnings,
        missing_inputs=tp.missing_inputs,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/drill")
async def generate_drill(
    req: DrillToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate drilling or peck-drilling toolpath geometry.

    Returns NO G-code. All verification checks are NOT_PERFORMED.
    """
    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    if req.peck_depth_mm is not None:
        inp = PeckDrillInput(
            operation_ref=req.operation_ref,
            hole_x=req.hole_x,
            hole_y=req.hole_y,
            hole_top_z=req.hole_top_z,
            hole_depth_mm=req.hole_depth_mm,
            clearance_z=req.clearance_z,
            clearance_source=cs,
            setup_ref=req.setup_ref,
            wcs_ref=req.wcs_ref,
            tool_ref=req.tool_ref,
            feature_refs=req.feature_refs,
            peck_depth_mm=req.peck_depth_mm,
        )
        tp = generate_peck_drill_toolpath(inp)
    else:
        inp_d = DrillInput(
            operation_ref=req.operation_ref,
            hole_x=req.hole_x,
            hole_y=req.hole_y,
            hole_top_z=req.hole_top_z,
            hole_depth_mm=req.hole_depth_mm,
            clearance_z=req.clearance_z,
            clearance_source=cs,
            setup_ref=req.setup_ref,
            wcs_ref=req.wcs_ref,
            tool_ref=req.tool_ref,
            feature_refs=req.feature_refs,
        )
        tp = generate_drill_toolpath(inp_d)

    return _toolpath_to_response(tp)


@router.post("/profile")
async def generate_profile(
    req: ProfileToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate 2D profile toolpath geometry. NO G-code, NOT collision-free."""
    try:
        ps = ProfileSide(req.profile_side)
    except ValueError:
        ps = ProfileSide.UNKNOWN

    try:
        comp = CompensationSide(req.compensation_side)
    except ValueError:
        comp = CompensationSide.CENTERLINE

    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    inp = ProfileInput(
        operation_ref=req.operation_ref,
        contour_points=req.contour_points,
        contour_z=req.contour_z,
        tool_diameter_mm=req.tool_diameter_mm,
        profile_side=ps,
        compensation_side=comp,
        clearance_z=req.clearance_z,
        clearance_source=cs,
        setup_ref=req.setup_ref,
        wcs_ref=req.wcs_ref,
        tool_ref=req.tool_ref,
        feature_refs=req.feature_refs,
        closed=req.closed,
    )
    return _toolpath_to_response(generate_profile_toolpath(inp))


@router.post("/face-mill")
async def generate_face_mill(
    req: FaceMillToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate face milling raster toolpath geometry. NO G-code."""
    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    inp = FaceMillInput(
        operation_ref=req.operation_ref,
        region_x_min=req.region_x_min,
        region_x_max=req.region_x_max,
        region_y_min=req.region_y_min,
        region_y_max=req.region_y_max,
        face_z=req.face_z,
        tool_diameter_mm=req.tool_diameter_mm,
        stepover_mm=req.stepover_mm,
        clearance_z=req.clearance_z,
        clearance_source=cs,
        setup_ref=req.setup_ref,
        wcs_ref=req.wcs_ref,
        tool_ref=req.tool_ref,
        feature_refs=req.feature_refs,
    )
    return _toolpath_to_response(generate_face_mill_toolpath(inp))


@router.post("/pocket")
async def generate_pocket(
    req: PocketToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate pocket toolpath geometry. NO G-code, NOT adaptive-cleared."""
    try:
        strategy = PocketStrategy(req.strategy)
    except ValueError:
        strategy = PocketStrategy.OFFSET

    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    inp = PocketInput(
        operation_ref=req.operation_ref,
        boundary_points=req.boundary_points,
        pocket_top_z=req.pocket_top_z,
        pocket_bottom_z=req.pocket_bottom_z,
        tool_diameter_mm=req.tool_diameter_mm,
        stepdown_mm=req.stepdown_mm,
        stepover_mm=req.stepover_mm,
        strategy=strategy,
        clearance_z=req.clearance_z,
        clearance_source=cs,
        setup_ref=req.setup_ref,
        wcs_ref=req.wcs_ref,
        tool_ref=req.tool_ref,
        feature_refs=req.feature_refs,
    )
    return _toolpath_to_response(generate_pocket_toolpath(inp))


@router.post("/slot")
async def generate_slot(
    req: SlotToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate straight-slot toolpath geometry. NO G-code."""
    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    inp = SlotInput(
        operation_ref=req.operation_ref,
        slot_start=req.slot_start,
        slot_end=req.slot_end,
        slot_z=req.slot_z,
        slot_width_mm=req.slot_width_mm,
        slot_depth_mm=req.slot_depth_mm,
        tool_diameter_mm=req.tool_diameter_mm,
        clearance_z=req.clearance_z,
        clearance_source=cs,
        setup_ref=req.setup_ref,
        wcs_ref=req.wcs_ref,
        tool_ref=req.tool_ref,
        feature_refs=req.feature_refs,
    )
    return _toolpath_to_response(generate_slot_toolpath(inp))


@router.post("/chamfer")
async def generate_chamfer(
    req: ChamferToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate chamfer toolpath geometry. NO G-code."""
    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    inp = ChamferInput(
        operation_ref=req.operation_ref,
        contour_points=req.contour_points,
        contour_z=req.contour_z,
        tool_diameter_mm=req.tool_diameter_mm,
        tool_angle_deg=req.tool_angle_deg,
        chamfer_depth_mm=req.chamfer_depth_mm,
        clearance_z=req.clearance_z,
        clearance_source=cs,
        setup_ref=req.setup_ref,
        wcs_ref=req.wcs_ref,
        tool_ref=req.tool_ref,
        feature_refs=req.feature_refs,
    )
    return _toolpath_to_response(generate_chamfer_toolpath(inp))


@router.post("/turning")
async def generate_turning(
    req: TurningToolpathRequest,
    _user: dict[str, Any] = Depends(_require_user),  # noqa: B008
) -> ToolpathResponse:
    """Generate turning primitive toolpath geometry in XZ lathe space. NO G-code."""
    try:
        motion_type = TurningMotionType(req.turning_motion_type)
    except ValueError:
        motion_type = TurningMotionType.AXIAL_CUT

    try:
        cs = ClearanceSource(req.clearance_source)
    except ValueError:
        cs = ClearanceSource.UNKNOWN

    inp = TurningInput(
        operation_ref=req.operation_ref,
        turning_motion_type=motion_type,
        start_z=req.start_z,
        end_z=req.end_z,
        start_x=req.start_x,
        end_x=req.end_x,
        setup_ref=req.setup_ref,
        wcs_ref=req.wcs_ref,
        tool_ref=req.tool_ref,
        feature_refs=req.feature_refs,
        clearance_x=req.clearance_x,
        clearance_source=cs,
    )
    return _toolpath_to_response(generate_turning_toolpath(inp))
