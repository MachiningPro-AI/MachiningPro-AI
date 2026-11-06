"""Level-10 Toolpath Generation — constraint validators.

Validates tool reach, machine envelope, and tool-radius offsets against
upstream Level-5 (tool selection) and machine requirement data.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.toolpath.enums import MachineEnvelopeStatus, ToolReachStatus


@dataclass(frozen=True)
class ToolReachResult:
    status: ToolReachStatus
    message: str
    path_depth_mm: float | None = None
    tool_reach_mm: float | None = None


def check_tool_reach(
    path_depth_mm: float | None,
    tool_reach_mm: float | None,
    flute_length_mm: float | None,
    holder_clearance_mm: float | None,
) -> ToolReachResult:
    """Validate path depth against tool reach and holder constraints.

    Returns TOOL_REACH_CONFLICT if path depth exceeds any verified limit.
    Returns UNKNOWN when tool data absent (never claims within-reach).
    """
    if path_depth_mm is None:
        return ToolReachResult(
            status=ToolReachStatus.UNKNOWN,
            message="PATH_DEPTH_UNKNOWN: cannot validate reach",
        )
    if tool_reach_mm is None and flute_length_mm is None:
        return ToolReachResult(
            status=ToolReachStatus.UNKNOWN,
            message="TOOL_REACH_DATA_ABSENT: cannot validate reach",
            path_depth_mm=path_depth_mm,
        )

    effective_reach = None
    if tool_reach_mm is not None:
        effective_reach = tool_reach_mm
    if flute_length_mm is not None:
        if effective_reach is None:
            effective_reach = flute_length_mm
        else:
            effective_reach = min(effective_reach, flute_length_mm)
    if holder_clearance_mm is not None and effective_reach is not None:
        effective_reach = min(effective_reach, holder_clearance_mm)

    if effective_reach is not None and path_depth_mm > effective_reach:
        return ToolReachResult(
            status=ToolReachStatus.TOOL_REACH_CONFLICT,
            message=(
                f"TOOL_REACH_CONFLICT: path depth {path_depth_mm:.3f} mm "
                f"exceeds effective reach {effective_reach:.3f} mm"
            ),
            path_depth_mm=path_depth_mm,
            tool_reach_mm=effective_reach,
        )
    if effective_reach is not None:
        return ToolReachResult(
            status=ToolReachStatus.WITHIN_REACH,
            message=f"Path depth {path_depth_mm:.3f} within reach {effective_reach:.3f}",
            path_depth_mm=path_depth_mm,
            tool_reach_mm=effective_reach,
        )
    return ToolReachResult(
        status=ToolReachStatus.UNKNOWN,
        message="REACH_UNDETERMINED",
        path_depth_mm=path_depth_mm,
    )


@dataclass(frozen=True)
class MachineEnvelopeResult:
    status: MachineEnvelopeStatus
    message: str
    conflict_points: tuple[tuple[float, float, float], ...] = ()


def check_machine_envelope(
    bounding_box_min: tuple[float, float, float] | None,
    bounding_box_max: tuple[float, float, float] | None,
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
) -> MachineEnvelopeResult:
    """Check generated path bounding box against machine travel.

    Returns UNKNOWN when no machine spec provided.
    Does NOT claim within-envelope without actual machine spec.
    """
    if travel_x_mm is None and travel_y_mm is None and travel_z_mm is None:
        return MachineEnvelopeResult(
            status=MachineEnvelopeStatus.UNKNOWN,
            message="MACHINE_ENVELOPE_STATUS=UNKNOWN: no machine spec provided",
        )
    if bounding_box_min is None or bounding_box_max is None:
        return MachineEnvelopeResult(
            status=MachineEnvelopeStatus.UNKNOWN,
            message="PATH_BOUNDS_UNKNOWN: no path bounding box to check",
        )

    min_pt = bounding_box_min
    max_pt = bounding_box_max
    path_x_range = abs(max_pt[0] - min_pt[0])
    path_y_range = abs(max_pt[1] - min_pt[1])
    path_z_range = abs(max_pt[2] - min_pt[2])

    conflicts = []
    if travel_x_mm is not None and path_x_range > travel_x_mm:
        conflicts.append(max_pt)
    if travel_y_mm is not None and path_y_range > travel_y_mm:
        conflicts.append(max_pt)
    if travel_z_mm is not None and path_z_range > travel_z_mm:
        conflicts.append(max_pt)

    if conflicts:
        return MachineEnvelopeResult(
            status=MachineEnvelopeStatus.ENVELOPE_CONFLICT,
            message=f"PATH_EXCEEDS_MACHINE_ENVELOPE: {len(conflicts)} axis conflicts",
            conflict_points=tuple(conflicts),
        )
    return MachineEnvelopeResult(
        status=MachineEnvelopeStatus.WITHIN_ENVELOPE,
        message="Path bounding box within machine travel limits",
    )


def validate_tool_radius_offset(
    tool_diameter_mm: float | None,
    offset_distance_mm: float | None,
) -> tuple[bool, str]:
    """Validate tool radius offset is consistent.

    Returns (valid, message).
    Invalid when: tool_diameter unknown, or offset > tool_radius.
    """
    if tool_diameter_mm is None:
        return False, "TOOL_DIAMETER_UNKNOWN: cannot validate offset"
    if offset_distance_mm is None:
        return False, "OFFSET_DISTANCE_UNKNOWN: cannot validate offset"
    tool_radius = tool_diameter_mm / 2.0
    if abs(offset_distance_mm) > tool_radius + 1e-6:
        return (
            False,
            f"OFFSET_EXCEEDS_TOOL_RADIUS: offset {offset_distance_mm:.3f} > "
            f"radius {tool_radius:.3f}",
        )
    return True, f"Offset {offset_distance_mm:.3f} within tool radius {tool_radius:.3f}"
