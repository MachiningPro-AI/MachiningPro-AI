"""
Level-12 NC Generation Engine.

Verification gate: only VerificationState.VERIFIED toolpaths may proceed.
All feed, spindle, tool, and work-offset data must be real — never fabricated.
Generated programs are OFFLINE_CANDIDATE only — never dispatchable.

NO_CNC_DISPATCH=YES  NO_FABRICATED_DATA=YES  OFFLINE_ONLY=YES
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field

from .enums import (
    ArcMode,
    NCCoolantMode,
    NCCoordinateMode,
    NCCutterCompMode,
    NCFeedMode,
    NCGenerationBlockReason,
    NCMotionType,
    NCPlane,
    NCProgramStatus,
    NCSpindleDirection,
    NCUnitMode,
    WorkOffsetRef,
)
from .ir import (
    NCBlock,
    NCCoolantCommand,
    NCCoordinateModeDeclaration,
    NCCutterCompDeclaration,
    NCFeedCommand,
    NCMotion,
    NCPlaneDeclaration,
    NCProgram,
    NCSourceTrace,
    NCSpindleCommand,
    NCToolChange,
    NCUnitDeclaration,
    NCWorkOffsetDeclaration,
)
from .postprocessor import PostProcessorProfile

# ---------------------------------------------------------------------------
# Generation request / result
# ---------------------------------------------------------------------------


@dataclass
class NCGenerationInput:
    """All inputs required for NC generation — none fabricated."""

    toolpath_id: str
    verification_state: str  # must be "VERIFIED"
    verification_session_id: str | None
    post_profile: PostProcessorProfile
    # segments from Level-11 VerificationSegment or Level-10 ToolpathSegment
    segments: list  # list of objects with start/end xyz, motion_type
    # tool data — real values or None (None blocks cutting output)
    tool_id: str | None
    tool_number: int | None
    tool_diameter_mm: float | None
    # spindle data — real values or None
    spindle_speed_rpm: float | None
    spindle_direction: NCSpindleDirection
    # feed data — real value or None (None blocks cutting output)
    feed_mmpm: float | None
    # work offset — unknown blocks output when profile requires it
    work_offset: WorkOffsetRef
    # unit mode — unknown blocks output
    unit_mode: NCUnitMode
    # plane
    plane: NCPlane
    # coordinate mode
    coordinate_mode: NCCoordinateMode
    # coolant
    coolant_mode: NCCoolantMode
    # cutter comp — default computer compensated (do not apply controller comp)
    cutter_comp: NCCutterCompMode
    # program identifier (non-production)
    program_number: str
    # optional hashes for stale detection
    source_toolpath_hash: str = ""
    source_verification_hash: str = ""


@dataclass
class NCGenerationResult:
    """Result of one NC generation attempt."""

    status: NCProgramStatus
    block_reasons: list[NCGenerationBlockReason] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    program: NCProgram | None = None


# ---------------------------------------------------------------------------
# Verification gate
# ---------------------------------------------------------------------------


def _check_verification_gate(
    verification_state: str,
) -> NCGenerationBlockReason | None:
    state = verification_state.upper()
    if state == "VERIFIED":
        return None
    if state == "PARTIALLY_VERIFIED":
        return NCGenerationBlockReason.PARTIAL_VERIFICATION
    if state == "FAILED":
        return NCGenerationBlockReason.FAILED_VERIFICATION
    if state == "BLOCKED":
        return NCGenerationBlockReason.BLOCKED_VERIFICATION
    # UNVERIFIED or anything else
    return NCGenerationBlockReason.UNVERIFIED_TOOLPATH


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def _collect_block_reasons(inp: NCGenerationInput) -> list[NCGenerationBlockReason]:
    reasons: list[NCGenerationBlockReason] = []

    if inp.unit_mode == NCUnitMode.UNKNOWN:
        reasons.append(NCGenerationBlockReason.UNKNOWN_UNITS)

    if inp.work_offset == WorkOffsetRef.UNKNOWN:
        reasons.append(NCGenerationBlockReason.UNKNOWN_WORK_OFFSET)

    if inp.tool_id is None or inp.tool_number is None:
        reasons.append(NCGenerationBlockReason.MISSING_TOOL_NUMBER)

    if inp.unit_mode not in inp.post_profile.supported_unit_modes:
        if inp.unit_mode != NCUnitMode.UNKNOWN:
            reasons.append(NCGenerationBlockReason.UNKNOWN_UNITS)

    # Check feed for any cutting segment
    has_cutting = any(
        getattr(s, "is_cutting", False)
        or getattr(s, "motion_type", "") in ("CUT", "FEED_LINEAR")
        for s in inp.segments
    )
    if has_cutting and (inp.feed_mmpm is None or inp.feed_mmpm <= 0):
        reasons.append(NCGenerationBlockReason.MISSING_FEED)

    return reasons


# ---------------------------------------------------------------------------
# Motion mapping
# ---------------------------------------------------------------------------

_TOOLPATH_TO_NC_MOTION: dict[str, NCMotionType] = {
    "RAPID": NCMotionType.RAPID_LINEAR,
    "APPROACH": NCMotionType.RAPID_LINEAR,
    "RETRACT": NCMotionType.RAPID_LINEAR,
    "LINK": NCMotionType.RAPID_LINEAR,
    "CUT": NCMotionType.FEED_LINEAR,
    "ENTRY": NCMotionType.FEED_LINEAR,
    "EXIT": NCMotionType.FEED_LINEAR,
    "PLUNGE": NCMotionType.FEED_LINEAR,
    "RAMP": NCMotionType.FEED_LINEAR,
    "FEED_LINEAR": NCMotionType.FEED_LINEAR,
    "RAPID_LINEAR": NCMotionType.RAPID_LINEAR,
    "ARC_CW": NCMotionType.ARC_CW,
    "ARC_CCW": NCMotionType.ARC_CCW,
    "DWELL": NCMotionType.DWELL,
}


def _map_motion_type(raw: str) -> NCMotionType | None:
    return _TOOLPATH_TO_NC_MOTION.get(raw.upper())


def _is_cutting_motion(mt: NCMotionType) -> bool:
    return mt in (NCMotionType.FEED_LINEAR, NCMotionType.ARC_CW, NCMotionType.ARC_CCW)


def _build_motion_element(
    seg: object,
    nc_motion_type: NCMotionType,
    feed_mmpm: float | None,
    profile: PostProcessorProfile,
) -> dict:
    _ep = getattr(seg, "end_point", None)
    _ex = getattr(seg, "end_x", None)
    end_x = _ex if _ex is not None else (_ep[0] if _ep is not None else None)
    _ey = getattr(seg, "end_y", None)
    end_y = _ey if _ey is not None else (_ep[1] if _ep is not None else None)
    _ez = getattr(seg, "end_z", None)
    end_z = _ez if _ez is not None else (_ep[2] if _ep is not None else None)

    arc_center = getattr(seg, "arc_center", None)
    arc_i = arc_j = arc_k = arc_radius = None
    arc_mode = None

    if nc_motion_type in (NCMotionType.ARC_CW, NCMotionType.ARC_CCW):
        if arc_center and len(arc_center) == 3 and ArcMode.CENTER_OFFSET in profile.arc_modes:
            # I/J/K are offsets from start point; accept tuple or separate attrs
            start_pt = getattr(seg, "start_point", None)
            if start_pt is None:
                _sx = getattr(seg, "start_x", None)
                _sy = getattr(seg, "start_y", None)
                _sz = getattr(seg, "start_z", None)
                if _sx is not None:
                    start_pt = (
                        _sx,
                        _sy if _sy is not None else 0.0,
                        _sz if _sz is not None else 0.0,
                    )
            if start_pt is not None:
                arc_i = arc_center[0] - start_pt[0]
                arc_j = arc_center[1] - start_pt[1]
                arc_k = arc_center[2] - start_pt[2]
                arc_mode = ArcMode.CENTER_OFFSET
        elif ArcMode.RADIUS in profile.arc_modes:
            r = getattr(seg, "helix_radius", None) or getattr(seg, "arc_radius", None)
            if r is not None:
                arc_radius = r
                arc_mode = ArcMode.RADIUS

    motion = NCMotion(
        motion_type=nc_motion_type,
        end_x=end_x,
        end_y=end_y,
        end_z=end_z,
        arc_i=arc_i,
        arc_j=arc_j,
        arc_k=arc_k,
        arc_radius=arc_radius,
        arc_mode=arc_mode,
        arc_plane=NCPlane.XY,
        feed_mmpm=feed_mmpm if _is_cutting_motion(nc_motion_type) else None,
        source=NCSourceTrace(
            toolpath_id=getattr(seg, "toolpath_id", None),
            segment_id=getattr(seg, "segment_id", None),
            operation_id=getattr(seg, "operation_id", None),
            tool_id=getattr(seg, "tool_id", None),
            setup_id=getattr(seg, "setup_id", None),
            feature_id=getattr(seg, "feature_id", None),
        ),
    )
    return {"kind": "motion", "data": motion.model_dump()}


# ---------------------------------------------------------------------------
# Arc validation
# ---------------------------------------------------------------------------


def _validate_arc(seg: object, nc_type: NCMotionType, profile: PostProcessorProfile) -> bool:
    """Return False if arc data is invalid/insufficient for the profile."""
    if nc_type not in (NCMotionType.ARC_CW, NCMotionType.ARC_CCW):
        return True
    if not profile.arc_modes:
        return False
    arc_center = getattr(seg, "arc_center", None)
    # Accept either end_point tuple or separate end_x/end_y/end_z attributes
    end_pt = getattr(seg, "end_point", None)
    has_end = end_pt is not None or getattr(seg, "end_x", None) is not None
    if not has_end:
        return False
    # Accept either start_point tuple or separate start_x/start_y/start_z attributes
    start_pt = getattr(seg, "start_point", None)
    has_start = start_pt is not None or getattr(seg, "start_x", None) is not None
    if ArcMode.CENTER_OFFSET in profile.arc_modes and arc_center and has_start:
        return True
    arc_r = getattr(seg, "helix_radius", None) or getattr(seg, "arc_radius", None)
    if ArcMode.RADIUS in profile.arc_modes and arc_r is not None:
        return True
    return False


# ---------------------------------------------------------------------------
# Safe start / end blocks
# ---------------------------------------------------------------------------


def _build_safe_start_blocks(inp: NCGenerationInput) -> list[NCBlock]:
    blocks: list[NCBlock] = []

    # Safety banner from profile
    for banner_line in inp.post_profile.safety_banner_lines:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append({"kind": "comment", "data": {"text": banner_line}})
        blocks.append(b)

    # Program start comment
    if inp.post_profile.program_start_comment:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {"kind": "comment", "data": {"text": inp.post_profile.program_start_comment}}
        )
        blocks.append(b)

    # Traceability comment
    b = NCBlock(block_id=str(uuid.uuid4())[:8])
    b.elements.append(
        {
            "kind": "comment",
            "data": {
                "text": (
                    f"( TOOLPATH: {inp.toolpath_id} | "
                    f"PROFILE: {inp.post_profile.profile_id} | "
                    f"VERIFICATION: {inp.verification_session_id or 'UNKNOWN'} )"
                )
            },
        }
    )
    blocks.append(b)

    # Unit declaration
    if inp.post_profile.requires_unit_declaration and inp.unit_mode != NCUnitMode.UNKNOWN:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {"kind": "unit_decl", "data": NCUnitDeclaration(unit_mode=inp.unit_mode).model_dump()}
        )
        blocks.append(b)

    # Plane declaration
    if inp.post_profile.requires_plane_declaration and inp.plane != NCPlane.UNKNOWN:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {"kind": "plane_decl", "data": NCPlaneDeclaration(plane=inp.plane).model_dump()}
        )
        blocks.append(b)

    # Coordinate mode declaration
    if inp.post_profile.requires_coordinate_mode_declaration:
        if inp.coordinate_mode != NCCoordinateMode.UNKNOWN:
            b = NCBlock(block_id=str(uuid.uuid4())[:8])
            b.elements.append(
                {
                    "kind": "coord_mode_decl",
                    "data": NCCoordinateModeDeclaration(
                        coord_mode=inp.coordinate_mode
                    ).model_dump(),
                }
            )
            blocks.append(b)

    # Feed mode (always FEED_PER_MINUTE at Level 12 unless profile says otherwise)
    b = NCBlock(block_id=str(uuid.uuid4())[:8])
    b.elements.append(
        {
            "kind": "feed_cmd",
            "data": NCFeedCommand(
                feed_value=inp.feed_mmpm or 0.0,
                feed_mode=NCFeedMode.FEED_PER_MINUTE,
            ).model_dump(),
        }
    )
    blocks.append(b)

    # Cutter comp declaration
    b = NCBlock(block_id=str(uuid.uuid4())[:8])
    b.elements.append(
        {
            "kind": "cutter_comp_decl",
            "data": NCCutterCompDeclaration(comp_mode=inp.cutter_comp).model_dump(),
        }
    )
    blocks.append(b)

    # Work offset declaration
    if inp.work_offset != WorkOffsetRef.UNKNOWN:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {
                "kind": "work_offset",
                "data": NCWorkOffsetDeclaration(offset_ref=inp.work_offset).model_dump(),
            }
        )
        blocks.append(b)

    # Tool change
    if inp.tool_id and inp.tool_number is not None:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {
                "kind": "tool_change",
                "data": NCToolChange(
                    tool_id=inp.tool_id,
                    tool_number=inp.tool_number,
                ).model_dump(),
            }
        )
        blocks.append(b)

    # Spindle
    if inp.spindle_speed_rpm is not None and inp.spindle_direction != NCSpindleDirection.OFF:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {
                "kind": "spindle_cmd",
                "data": NCSpindleCommand(
                    speed_rpm=inp.spindle_speed_rpm,
                    direction=inp.spindle_direction,
                    source_operation_id=inp.toolpath_id,
                ).model_dump(),
            }
        )
        blocks.append(b)

    # Coolant
    if inp.coolant_mode != NCCoolantMode.UNKNOWN:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {
                "kind": "coolant_cmd",
                "data": NCCoolantCommand(coolant_mode=inp.coolant_mode).model_dump(),
            }
        )
        blocks.append(b)

    return blocks


def _build_safe_end_blocks(inp: NCGenerationInput) -> list[NCBlock]:
    blocks: list[NCBlock] = []

    # Spindle stop
    b = NCBlock(block_id=str(uuid.uuid4())[:8])
    b.elements.append(
        {
            "kind": "spindle_cmd",
            "data": NCSpindleCommand(speed_rpm=None, direction=NCSpindleDirection.OFF).model_dump(),
        }
    )
    blocks.append(b)

    # Coolant off
    b = NCBlock(block_id=str(uuid.uuid4())[:8])
    b.elements.append(
        {
            "kind": "coolant_cmd",
            "data": NCCoolantCommand(coolant_mode=NCCoolantMode.OFF).model_dump(),
        }
    )
    blocks.append(b)

    # Program end
    for cmd in inp.post_profile.program_end_commands:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append({"kind": "program_end", "data": {"command": cmd}})
        blocks.append(b)

    # End comment
    if inp.post_profile.program_end_comment:
        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        b.elements.append(
            {"kind": "comment", "data": {"text": inp.post_profile.program_end_comment}}
        )
        blocks.append(b)

    return blocks


# ---------------------------------------------------------------------------
# Main generation entry point
# ---------------------------------------------------------------------------


def generate_nc(inp: NCGenerationInput) -> NCGenerationResult:
    """
    Generate a controller-neutral NC program from a VERIFIED toolpath.

    Returns BLOCKED with reasons if any gate fails.
    Returns CANDIDATE on success (never READY_TO_RUN or MACHINE_APPROVED).
    """
    block_reasons: list[NCGenerationBlockReason] = []
    warnings: list[str] = []

    # --- Verification gate (HARD RULES 10-13) ---
    gate_reason = _check_verification_gate(inp.verification_state)
    if gate_reason is not None:
        block_reasons.append(gate_reason)
        return NCGenerationResult(
            status=NCProgramStatus.BLOCKED,
            block_reasons=block_reasons,
            errors=[f"NC generation blocked: {gate_reason.value}"],
        )

    # --- Profile gate ---
    if inp.post_profile is None:
        block_reasons.append(NCGenerationBlockReason.MISSING_POST_PROFILE)
        return NCGenerationResult(
            status=NCProgramStatus.BLOCKED,
            block_reasons=block_reasons,
            errors=["NC generation blocked: no postprocessor profile provided"],
        )

    # --- Input validation ---
    input_reasons = _collect_block_reasons(inp)
    if input_reasons:
        return NCGenerationResult(
            status=NCProgramStatus.BLOCKED,
            block_reasons=input_reasons,
            errors=[f"Blocked: {r.value}" for r in input_reasons],
        )

    # --- Build blocks ---
    all_blocks: list[NCBlock] = []

    # Safe start
    all_blocks.extend(_build_safe_start_blocks(inp))

    # Segment blocks
    unsupported: list[str] = []
    invalid_arcs: list[str] = []

    for seg in inp.segments:
        raw_motion = str(getattr(seg, "motion_type", "UNKNOWN"))
        nc_type = _map_motion_type(raw_motion)

        if nc_type is None:
            unsupported.append(raw_motion)
            warnings.append(f"UNSUPPORTED_MOTION: {raw_motion} — segment skipped")
            continue

        # Helix — only emit if profile supports it (not in GENERIC_ISO_TEST)
        if nc_type == NCMotionType.HELIX or raw_motion.upper() == "HELIX":
            if NCMotionType.HELIX not in inp.post_profile.supported_motion_types:
                unsupported.append(raw_motion)
                warnings.append(
                    f"UNSUPPORTED_MOTION: HELIX not supported by profile "
                    f"{inp.post_profile.profile_id} — segment skipped"
                )
                continue

        # Arc validation
        if nc_type in (NCMotionType.ARC_CW, NCMotionType.ARC_CCW):
            if not _validate_arc(seg, nc_type, inp.post_profile):
                seg_id = getattr(seg, "segment_id", "?")
                invalid_arcs.append(seg_id)
                warnings.append(f"INVALID_ARC: segment {seg_id} — insufficient arc data, skipped")
                continue

        # Feed requirement for cutting motions
        if _is_cutting_motion(nc_type) and (inp.feed_mmpm is None or inp.feed_mmpm <= 0):
            warnings.append(
                f"MISSING_FEED: cutting segment {getattr(seg, 'segment_id', '?')} skipped"
            )
            continue

        b = NCBlock(block_id=str(uuid.uuid4())[:8])
        motion_elem = _build_motion_element(seg, nc_type, inp.feed_mmpm, inp.post_profile)
        b.elements.append(motion_elem)
        b.source = NCSourceTrace(
            toolpath_id=inp.toolpath_id,
            segment_id=getattr(seg, "segment_id", None),
            operation_id=getattr(seg, "operation_id", None),
            tool_id=inp.tool_id,
        )
        all_blocks.append(b)

    # If all segments were unsupported/skipped and there were any segments, block
    if inp.segments and not any(
        b.elements and b.elements[0].get("kind") == "motion"
        for b in all_blocks
    ):
        if unsupported or invalid_arcs:
            return NCGenerationResult(
                status=NCProgramStatus.BLOCKED,
                block_reasons=[NCGenerationBlockReason.UNSUPPORTED_MOTION],
                warnings=warnings,
                errors=["All segments were unsupported or invalid — no motion blocks generated"],
            )

    # Safe end
    all_blocks.extend(_build_safe_end_blocks(inp))

    program = NCProgram(
        program_number=inp.program_number,
        unit_mode=inp.unit_mode,
        coordinate_mode=inp.coordinate_mode,
        blocks=all_blocks,
        toolpath_id=inp.toolpath_id,
        verification_session_id=inp.verification_session_id,
        post_profile_id=inp.post_profile.profile_id,
        source_toolpath_hash=inp.source_toolpath_hash,
        source_verification_hash=inp.source_verification_hash,
        is_offline_candidate=True,
        is_dispatchable=False,
        generation_warnings=warnings,
    )

    return NCGenerationResult(
        status=NCProgramStatus.CANDIDATE,
        warnings=warnings,
        program=program,
    )


# ---------------------------------------------------------------------------
# Content hash
# ---------------------------------------------------------------------------


def compute_program_hash(program: NCProgram) -> str:
    """Deterministic SHA-256 hash of program block content for stale detection."""
    import json

    content = json.dumps(
        [b.model_dump() for b in program.blocks],
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(content.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Stale detection
# ---------------------------------------------------------------------------


def is_program_stale(
    program: NCProgram,
    current_toolpath_hash: str,
    current_verification_hash: str,
    current_profile_id: str,
) -> tuple[bool, list[str]]:
    """Return (is_stale, reasons) based on hash comparison."""
    reasons: list[str] = []
    if program.source_toolpath_hash and program.source_toolpath_hash != current_toolpath_hash:
        reasons.append("TOOLPATH_CHANGED")
    if (
        program.source_verification_hash
        and program.source_verification_hash != current_verification_hash
    ):
        reasons.append("VERIFICATION_CHANGED")
    if program.post_profile_id != current_profile_id:
        reasons.append("PROFILE_CHANGED")
    return bool(reasons), reasons
