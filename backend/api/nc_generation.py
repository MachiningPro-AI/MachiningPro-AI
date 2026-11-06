"""
Level-12 NC Generation API.

Endpoints: build NC candidate, validate NC candidate, get manifest.

NO CNC DISPATCH endpoint exists.
NO send-to-machine endpoint exists.
NO DNC/FTP transfer endpoint exists.
All output is OFFLINE_CANDIDATE only.

NO_GCODE_DISPATCH=YES  NO_CNC_CONNECTION=YES  OFFLINE_ONLY=YES
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from backend.api.auth import verify_token

from ..nc import (
    GENERIC_ISO_TEST,
    NCCoolantMode,
    NCCoordinateMode,
    NCCutterCompMode,
    NCGenerationBlockReason,
    NCGenerationInput,
    NCGenerationManifest,
    NCPlane,
    NCProgramStatus,
    NCSpindleDirection,
    NCUnitMode,
    WorkOffsetRef,
    build_manifest,
    generate_nc,
    get_profile,
    serialize_blocks_for_hash,
    validate_nc_program,
)

router = APIRouter(prefix="/api/nc", tags=["nc-generation"])


def _require_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
        )
    token = authorization.removeprefix("Bearer ")
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    return payload


class NCSegmentInput(BaseModel):
    segment_id: str
    motion_type: str
    start_x: float | None = None
    start_y: float | None = None
    start_z: float | None = None
    end_x: float | None = None
    end_y: float | None = None
    end_z: float | None = None
    arc_center: list[float] | None = None
    arc_radius: float | None = None
    is_cutting: bool = False
    operation_id: str | None = None
    tool_id: str | None = None
    setup_id: str | None = None
    feature_id: str | None = None


class NCBuildRequest(BaseModel):
    toolpath_id: str
    verification_state: str
    verification_session_id: str | None = None
    profile_id: str = GENERIC_ISO_TEST.profile_id
    segments: list[NCSegmentInput] = Field(default_factory=list)
    tool_id: str | None = None
    tool_number: int | None = None
    tool_diameter_mm: float | None = None
    spindle_speed_rpm: float | None = None
    spindle_direction: NCSpindleDirection = NCSpindleDirection.CW
    feed_mmpm: float | None = None
    work_offset: WorkOffsetRef = WorkOffsetRef.WORK_OFFSET_1
    unit_mode: NCUnitMode = NCUnitMode.MM
    plane: NCPlane = NCPlane.XY
    coordinate_mode: NCCoordinateMode = NCCoordinateMode.ABSOLUTE
    coolant_mode: NCCoolantMode = NCCoolantMode.OFF
    cutter_comp: NCCutterCompMode = NCCutterCompMode.COMPUTER_COMPENSATED
    program_number: str = "O9999"
    source_toolpath_hash: str = ""
    source_verification_hash: str = ""


class NCBuildResponse(BaseModel):
    status: NCProgramStatus
    block_reasons: list[NCGenerationBlockReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    program_id: str | None = None
    program_number: str | None = None
    block_count: int = 0
    is_offline_candidate: bool = True
    is_dispatchable: bool = False
    safety_warnings: list[str] = Field(default_factory=list)
    manifest: NCGenerationManifest | None = None


class NCValidateRequest(BaseModel):
    program_id: str
    profile_id: str = GENERIC_ISO_TEST.profile_id
    # program blocks serialized from a previous build
    program_blocks_json: str = ""
    unit_mode: NCUnitMode = NCUnitMode.MM
    coordinate_mode: NCCoordinateMode = NCCoordinateMode.ABSOLUTE
    toolpath_id: str | None = None
    is_dispatchable: bool = False


class NCValidateResponse(BaseModel):
    status: NCProgramStatus
    is_valid: bool
    error_count: int
    warning_count: int
    errors: list[str] = Field(default_factory=list)
    warnings_list: list[str] = Field(default_factory=list)


class NCManifestResponse(BaseModel):
    manifest: NCGenerationManifest


@router.post("/build", response_model=NCBuildResponse)
def build_nc_candidate(
    request: NCBuildRequest,
    authorization: str | None = Header(default=None),
) -> NCBuildResponse:
    """
    Build a controller-neutral NC candidate from a VERIFIED toolpath.

    Returns BLOCKED if verification gate fails or required inputs are missing.
    Returns CANDIDATE on success.

    is_dispatchable is always False — this is an OFFLINE CANDIDATE only.
    """
    _require_user(authorization)

    profile = get_profile(request.profile_id)
    if profile is None:
        return NCBuildResponse(
            status=NCProgramStatus.BLOCKED,
            block_reasons=[NCGenerationBlockReason.MISSING_POST_PROFILE],
            errors=[f"Profile not found: {request.profile_id!r}"],
        )

    inp = NCGenerationInput(
        toolpath_id=request.toolpath_id,
        verification_state=request.verification_state,
        verification_session_id=request.verification_session_id,
        post_profile=profile,
        segments=request.segments,
        tool_id=request.tool_id,
        tool_number=request.tool_number,
        tool_diameter_mm=request.tool_diameter_mm,
        spindle_speed_rpm=request.spindle_speed_rpm,
        spindle_direction=request.spindle_direction,
        feed_mmpm=request.feed_mmpm,
        work_offset=request.work_offset,
        unit_mode=request.unit_mode,
        plane=request.plane,
        coordinate_mode=request.coordinate_mode,
        coolant_mode=request.coolant_mode,
        cutter_comp=request.cutter_comp,
        program_number=request.program_number,
        source_toolpath_hash=request.source_toolpath_hash,
        source_verification_hash=request.source_verification_hash,
    )

    result = generate_nc(inp)

    manifest = None
    if result.program is not None:
        blocks_json = serialize_blocks_for_hash(result.program.blocks)
        manifest = build_manifest(
            manifest_id=str(uuid.uuid4()),
            toolpath_id=request.toolpath_id,
            verification_session_id=request.verification_session_id,
            verification_state=request.verification_state,
            verification_profile="UNKNOWN",
            post_profile_id=profile.profile_id,
            post_profile_name=profile.profile_name,
            post_profile_certification=profile.certification_status.value,
            program_id=result.program.program_id,
            program_number=result.program.program_number,
            program_status=result.status,
            program_blocks_json=blocks_json,
            generation_warnings=result.warnings,
        )

    return NCBuildResponse(
        status=result.status,
        block_reasons=result.block_reasons,
        warnings=result.warnings,
        errors=result.errors,
        program_id=result.program.program_id if result.program else None,
        program_number=result.program.program_number if result.program else None,
        block_count=result.program.block_count if result.program else 0,
        is_offline_candidate=True,
        is_dispatchable=False,
        safety_warnings=result.program.safety_warnings if result.program else [],
        manifest=manifest,
    )


@router.post("/validate", response_model=NCValidateResponse)
def validate_nc_candidate(
    request: NCValidateRequest,
    authorization: str | None = Header(default=None),
) -> NCValidateResponse:
    """
    Run offline syntax and semantic validation on an NC program.

    Does not connect to any machine. Returns VALIDATED_OFFLINE, REVIEW_REQUIRED,
    or REJECTED.
    """
    _require_user(authorization)

    profile = get_profile(request.profile_id)
    if profile is None:
        return NCValidateResponse(
            status=NCProgramStatus.REJECTED,
            is_valid=False,
            error_count=1,
            warning_count=0,
            errors=[f"Profile not found: {request.profile_id!r}"],
        )

    from ..nc.ir import NCProgram

    try:
        program = NCProgram(
            program_number=request.program_id,
            unit_mode=request.unit_mode,
            coordinate_mode=request.coordinate_mode,
            post_profile_id=request.profile_id,
            toolpath_id=request.toolpath_id,
            is_dispatchable=request.is_dispatchable,
        )
    except Exception as exc:
        return NCValidateResponse(
            status=NCProgramStatus.REJECTED,
            is_valid=False,
            error_count=1,
            warning_count=0,
            errors=[f"Cannot build program for validation: {exc}"],
        )

    vr = validate_nc_program(program, profile)

    return NCValidateResponse(
        status=vr.status,
        is_valid=vr.is_valid,
        error_count=vr.error_count,
        warning_count=vr.warning_count,
        errors=[i.message for i in vr.all_issues if i.severity == "ERROR"],
        warnings_list=[i.message for i in vr.all_issues if i.severity == "WARNING"],
    )


@router.get("/profiles", response_model=list[dict])
def list_profiles(
    authorization: str | None = Header(default=None),
) -> list[dict]:
    """List available postprocessor profiles."""
    from ..nc.postprocessor import PROFILE_REGISTRY

    _require_user(authorization)
    return [
        {
            "profile_id": p.profile_id,
            "profile_name": p.profile_name,
            "dialect": p.dialect,
            "certification_status": p.certification_status.value,
            "not_machine_certified": p.not_machine_certified,
            "not_dispatchable": p.not_dispatchable,
        }
        for p in PROFILE_REGISTRY.values()
    ]
