"""
NC segment adapter for P6-B.

Translates validated ToolpathSegment objects into NCSegmentInput-compatible
dicts for use with the NC generation API.

Required chain:
    Feature → Toolpath Candidate → NC Segment Candidate

HARD RULES:
  - Only translates VALIDATED toolpath primitives; never raw feature geometry.
  - Does NOT fabricate coordinates.
  - Does NOT call generate_nc() directly (requires VERIFIED toolpath).
  - Preserves segment provenance (operation_ref, tool_ref, feature_refs).

TOOLPATH_ENGINE_FOUND=YES  (backend.toolpath)
NC_GENERATION_ENGINE_FOUND=YES  (backend.nc)
"""

from __future__ import annotations

from backend.toolpath.enums import MotionType
from backend.toolpath.models import Toolpath, ToolpathSegment

__all__ = [
    "segment_to_nc_input",
    "toolpath_to_nc_segments",
]

# Maps toolpath motion types to NC motion type strings.
# NC motion type strings match NCMotionType values in backend.nc.enums.
_MOTION_TYPE_MAP: dict[MotionType, str] = {
    MotionType.RAPID: "RAPID_LINEAR",
    MotionType.APPROACH: "RAPID_LINEAR",
    MotionType.RETRACT: "RAPID_LINEAR",
    MotionType.LINK: "RAPID_LINEAR",
    MotionType.DWELL: "RAPID_LINEAR",
    MotionType.PLUNGE: "FEED_LINEAR",
    MotionType.CUT: "FEED_LINEAR",
    MotionType.ENTRY: "FEED_LINEAR",
    MotionType.EXIT: "FEED_LINEAR",
    MotionType.RAMP: "FEED_LINEAR",
    MotionType.ARC: "FEED_LINEAR",
    MotionType.HELIX: "HELIX",
}

# Motion types that represent active material removal.
_CUTTING_MOTIONS: frozenset[MotionType] = frozenset({
    MotionType.CUT,
    MotionType.PLUNGE,
    MotionType.RAMP,
    MotionType.ENTRY,
    MotionType.EXIT,
    MotionType.HELIX,
})


def segment_to_nc_input(seg: ToolpathSegment) -> dict:
    """Convert one ToolpathSegment to an NCSegmentInput-compatible dict.

    Returns a dict whose keys match the NCSegmentInput pydantic model in
    backend.api.nc_generation.NCSegmentInput.  None values are omitted
    so that the downstream pydantic model uses its own defaults.
    """
    nc_motion = _MOTION_TYPE_MAP.get(seg.motion_type, "RAPID_LINEAR")
    is_cutting = seg.motion_type in _CUTTING_MOTIONS

    result: dict = {
        "segment_id": seg.segment_id,
        "motion_type": nc_motion,
        "is_cutting": is_cutting,
        "operation_id": seg.operation_ref,
    }
    if seg.tool_ref is not None:
        result["tool_id"] = seg.tool_ref
    if seg.setup_ref is not None:
        result["setup_id"] = seg.setup_ref
    if seg.feature_refs:
        result["feature_id"] = seg.feature_refs[0]

    if seg.start_point is not None:
        result["start_x"] = seg.start_point[0]
        result["start_y"] = seg.start_point[1]
        result["start_z"] = seg.start_point[2]

    if seg.end_point is not None:
        result["end_x"] = seg.end_point[0]
        result["end_y"] = seg.end_point[1]
        result["end_z"] = seg.end_point[2]

    if seg.arc_center is not None:
        result["arc_center"] = list(seg.arc_center)
    if seg.helix_radius is not None:
        result["arc_radius"] = seg.helix_radius

    return result


def toolpath_to_nc_segments(toolpath: Toolpath) -> list[dict]:
    """Convert all segments from a Toolpath to NCSegmentInput-compatible dicts.

    Only call this after confirming toolpath.status != BLOCKED and
    toolpath.has_segments is True.  Empty toolpath → empty list.
    """
    return [segment_to_nc_input(seg) for seg in toolpath.segments]
