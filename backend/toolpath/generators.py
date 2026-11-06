"""Level-10 Toolpath Generation — path generators.

Each generator produces deterministic, coordinate-frame-explicit toolpath
segments from verified geometric inputs.

Safety contract
---------------
NO_GCODE=YES
NO_FABRICATED_DATA=YES   — blocked when any required input is absent.
NO_FAKE_COLLISION_STATUS — COLLISION_CHECK=NOT_PERFORMED always.
NO_DEFAULT_STEPDOWN      — stepdown/stepover must be supplied explicitly.
NO_DEFAULT_CLEARANCE     — clearance must be supplied with a valid source.
"""

from __future__ import annotations

import math
import uuid
from dataclasses import dataclass, field

from backend.toolpath.enums import (
    ClearanceSource,
    CompensationSide,
    CoordinateFrame,
    EntryType,
    ExitType,
    LinkStatus,
    MotionType,
    PocketStrategy,
    ProfileSide,
    SegmentGeometryType,
    ToolpathFidelity,
    ToolpathStatus,
    TurningMotionType,
)
from backend.toolpath.geometry import (
    Point3D,
    PolylineSegment,
    compute_z_levels,
    offset_polyline_2d,
)
from backend.toolpath.models import (
    ClearancePlane,
    PathMetrics,
    StepParameters,
    Toolpath,
    ToolpathSegment,
    VisualizationData,
)


def _seg_id() -> str:
    return uuid.uuid4().hex[:10]


def _tp_id() -> str:
    return uuid.uuid4().hex[:12]


def _make_segment(
    op_ref: str,
    motion_type: MotionType,
    geometry_type: SegmentGeometryType,
    frame: CoordinateFrame,
    start: tuple[float, float, float] | None = None,
    end: tuple[float, float, float] | None = None,
    length: float | None = None,
    setup_ref: str | None = None,
    wcs_ref: str | None = None,
    tool_ref: str | None = None,
    feature_refs: list[str] | None = None,
    strategy: str | None = None,
    source_evidence: list[str] | None = None,
    warnings: list[str] | None = None,
    arc_center: tuple[float, float, float] | None = None,
    arc_clockwise: bool = False,
    helix_radius: float | None = None,
    helix_pitch: float | None = None,
    polyline_points: list[tuple[float, float, float]] | None = None,
) -> ToolpathSegment:
    return ToolpathSegment(
        segment_id=_seg_id(),
        operation_ref=op_ref,
        motion_type=motion_type,
        geometry_type=geometry_type,
        frame=frame,
        start_point=start,
        end_point=end,
        computed_length_mm=length,
        setup_ref=setup_ref,
        wcs_ref=wcs_ref,
        tool_ref=tool_ref,
        feature_refs=feature_refs or [],
        strategy=strategy,
        source_evidence=source_evidence or [],
        warnings=warnings or [],
        arc_center=arc_center,
        arc_clockwise=arc_clockwise,
        helix_radius=helix_radius,
        helix_pitch=helix_pitch,
        polyline_points=polyline_points or [],
        status=ToolpathStatus.GENERATED,
    )


def _metrics_from_segments(segments: list[ToolpathSegment]) -> PathMetrics:
    cut = 0.0
    link = 0.0
    retracts = 0
    for seg in segments:
        length = seg.computed_length_mm or 0.0
        if seg.motion_type in (MotionType.CUT, MotionType.PLUNGE, MotionType.RAMP,
                                MotionType.HELIX, MotionType.ENTRY, MotionType.EXIT):
            cut += length
        else:
            link += length
        if seg.motion_type == MotionType.RETRACT:
            retracts += 1
    total = cut + link
    all_pts = [
        Point3D(*p)
        for seg in segments
        if seg.start_point
        for p in [seg.start_point]
    ] + [
        Point3D(*p)
        for seg in segments
        if seg.end_point
        for p in [seg.end_point]
    ]
    bmin = bmax = None
    if all_pts:
        xs = [p.x for p in all_pts]
        ys = [p.y for p in all_pts]
        zs = [p.z for p in all_pts]
        bmin = (min(xs), min(ys), min(zs))
        bmax = (max(xs), max(ys), max(zs))
    return PathMetrics(
        cut_length_mm=round(cut, 6),
        link_or_rapid_length_mm=round(link, 6),
        total_length_mm=round(total, 6),
        segment_count=len(segments),
        retract_count=retracts,
        bounding_box_min=bmin,
        bounding_box_max=bmax,
        is_exact=True,
    )


def _viz_from_segments(
    segments: list[ToolpathSegment],
    frame: CoordinateFrame,
) -> VisualizationData:
    pts: list[tuple[float, float, float]] = []
    arcs: list[dict] = []
    motions: list[str] = []
    for seg in segments:
        if seg.start_point:
            pts.append(seg.start_point)
            motions.append(seg.motion_type.value)
        if seg.end_point:
            pts.append(seg.end_point)
            motions.append(seg.motion_type.value)
        if seg.geometry_type == SegmentGeometryType.ARC and seg.arc_center:
            arcs.append({
                "start": seg.start_point,
                "end": seg.end_point,
                "center": seg.arc_center,
                "clockwise": seg.arc_clockwise,
            })
    return VisualizationData(
        polyline_points=pts,
        arcs=arcs,
        motion_types=motions,
        frame=frame,
    )


# ---------------------------------------------------------------------------
# Drilling generator
# ---------------------------------------------------------------------------

@dataclass
class DrillInput:
    operation_ref: str
    hole_x: float
    hole_y: float
    hole_top_z: float
    hole_depth_mm: float
    axis_vector: tuple[float, float, float] = (0.0, 0.0, -1.0)
    clearance_z: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)


def generate_drill_toolpath(inp: DrillInput) -> Toolpath:
    """Generate drilling path: APPROACH → PLUNGE → RETRACT.

    Blocked when any of: hole location, depth, WCS unknown.
    Does NOT fabricate depth or clearance.
    """
    warnings: list[str] = []
    missing: list[str] = []
    segments: list[ToolpathSegment] = []

    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["clearance_z: safe Z value not supplied"],
            warnings=["CLEARANCE_UNKNOWN: cannot generate drilling path"],
        )

    if inp.wcs_ref is None:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["wcs_ref: WCS not defined"],
            warnings=["WCS_UNKNOWN: cannot generate drilling path"],
        )

    clear_z = inp.clearance_z
    top_z = inp.hole_top_z
    bottom_z = inp.hole_top_z - inp.hole_depth_mm
    pos_x, pos_y = inp.hole_x, inp.hole_y

    approach_len = abs(clear_z - top_z)
    drill_len = inp.hole_depth_mm
    retract_len = abs(clear_z - bottom_z)

    segments = [
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.APPROACH,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(pos_x, pos_y, clear_z),
            end=(pos_x, pos_y, top_z),
            length=approach_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="DRILL_CYCLE",
            source_evidence=["confirmed_hole", "known_depth", "wcs_defined"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.PLUNGE,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(pos_x, pos_y, top_z),
            end=(pos_x, pos_y, bottom_z),
            length=drill_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="DRILL_CYCLE",
            source_evidence=["confirmed_hole", "known_depth"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.RETRACT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(pos_x, pos_y, bottom_z),
            end=(pos_x, pos_y, clear_z),
            length=retract_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="DRILL_CYCLE",
        ),
    ]

    metrics = _metrics_from_segments(segments)
    metrics = metrics.model_copy(update={"depth_level_count": 1, "max_depth_mm": inp.hole_depth_mm})
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        clearance=ClearancePlane(value_mm=inp.clearance_z, source=inp.clearance_source),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
        warnings=warnings,
        missing_inputs=missing,
    )


# ---------------------------------------------------------------------------
# Peck drilling generator
# ---------------------------------------------------------------------------

@dataclass
class PeckDrillInput(DrillInput):
    peck_depth_mm: float | None = None


def generate_peck_drill_toolpath(inp: PeckDrillInput) -> Toolpath:
    """Generate peck drilling path.

    Blocked when peck depth not explicitly supplied — no default peck depth.
    """
    if inp.peck_depth_mm is None or inp.peck_depth_mm <= 0:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["peck_depth_mm: peck depth not supplied"],
            warnings=["PECK_DEPTH_UNKNOWN: cannot generate peck drilling path"],
        )

    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["clearance_z"],
            warnings=["CLEARANCE_UNKNOWN"],
        )

    if inp.wcs_ref is None:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["wcs_ref"],
            warnings=["WCS_UNKNOWN"],
        )

    clear_z = inp.clearance_z
    top_z = inp.hole_top_z
    total_depth = inp.hole_depth_mm
    peck = inp.peck_depth_mm
    pos_x, pos_y = inp.hole_x, inp.hole_y
    segments: list[ToolpathSegment] = []
    current_z = top_z
    while current_z > top_z - total_depth:
        next_z = max(current_z - peck, top_z - total_depth)
        plunge_len = abs(next_z - current_z)
        segments.append(_make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.PLUNGE,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(pos_x, pos_y, current_z),
            end=(pos_x, pos_y, next_z),
            length=plunge_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="PECK_CYCLE",
            source_evidence=["confirmed_hole", "explicit_peck_depth"],
        ))
        if next_z > top_z - total_depth:
            ret_len = abs(clear_z - next_z)
            segments.append(_make_segment(
                op_ref=inp.operation_ref,
                motion_type=MotionType.RETRACT,
                geometry_type=SegmentGeometryType.LINE,
                frame=CoordinateFrame.WCS_COORDINATES,
                start=(pos_x, pos_y, next_z),
                end=(pos_x, pos_y, clear_z),
                length=ret_len,
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                tool_ref=inp.tool_ref,
                feature_refs=inp.feature_refs,
                strategy="PECK_CYCLE",
            ))
            app_len = abs(clear_z - next_z)
            segments.append(_make_segment(
                op_ref=inp.operation_ref,
                motion_type=MotionType.APPROACH,
                geometry_type=SegmentGeometryType.LINE,
                frame=CoordinateFrame.WCS_COORDINATES,
                start=(pos_x, pos_y, clear_z),
                end=(pos_x, pos_y, next_z),
                length=app_len,
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                tool_ref=inp.tool_ref,
                feature_refs=inp.feature_refs,
                strategy="PECK_CYCLE",
            ))
        current_z = next_z
        if abs(current_z - (top_z - total_depth)) < 1e-6:
            break

    fin_ret = abs(clear_z - (top_z - total_depth))
    segments.append(_make_segment(
        op_ref=inp.operation_ref,
        motion_type=MotionType.RETRACT,
        geometry_type=SegmentGeometryType.LINE,
        frame=CoordinateFrame.WCS_COORDINATES,
        start=(pos_x, pos_y, top_z - total_depth),
        end=(pos_x, pos_y, clear_z),
        length=fin_ret,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        strategy="PECK_CYCLE",
    ))

    metrics = _metrics_from_segments(segments)
    peck_count = max(1, math.ceil(total_depth / peck))
    metrics = metrics.model_copy(update={
        "depth_level_count": peck_count,
        "max_depth_mm": total_depth,
    })
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        clearance=ClearancePlane(value_mm=inp.clearance_z, source=inp.clearance_source),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
    )


# ---------------------------------------------------------------------------
# Profile toolpath generator
# ---------------------------------------------------------------------------

@dataclass
class ProfileInput:
    operation_ref: str
    contour_points: list[tuple[float, float]]
    contour_z: float
    tool_diameter_mm: float | None
    profile_side: ProfileSide
    compensation_side: CompensationSide
    clearance_z: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)
    closed: bool = True


def generate_profile_toolpath(inp: ProfileInput) -> Toolpath:
    """Generate 2D profile path along a confirmed planar contour.

    Blocked when: WCS unknown, side unknown, tool diameter unknown for offset.
    """
    warnings: list[str] = []

    if inp.wcs_ref is None:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["wcs_ref"],
            warnings=["WCS_UNKNOWN: cannot generate profile path"],
        )

    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["clearance_z"],
            warnings=["CLEARANCE_UNKNOWN: cannot generate profile path"],
        )

    if inp.profile_side == ProfileSide.UNKNOWN:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["profile_side"],
            warnings=["PROFILE_SIDE_UNKNOWN: REVIEW_REQUIRED"],
        )

    if len(inp.contour_points) < 2:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["contour_points: insufficient points"],
            warnings=["CONTOUR_INSUFFICIENT"],
        )

    pts_3d = [Point3D(p[0], p[1], inp.contour_z) for p in inp.contour_points]

    if inp.compensation_side != CompensationSide.CENTERLINE:
        if inp.tool_diameter_mm is None or inp.tool_diameter_mm <= 0:
            return Toolpath(
                toolpath_id=_tp_id(),
                operation_ref=inp.operation_ref,
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                status=ToolpathStatus.BLOCKED,
                fidelity=ToolpathFidelity.BLOCKED,
                missing_inputs=["tool_diameter_mm"],
                warnings=["TOOL_DIAMETER_UNKNOWN: cannot compute offset path"],
            )
        offset = inp.tool_diameter_mm / 2.0
        side = "LEFT" if inp.compensation_side == CompensationSide.LEFT_OFFSET else "RIGHT"
        pts_3d_offset = offset_polyline_2d(pts_3d, offset, side)
        if len(pts_3d_offset) < 2:
            warnings.append("OFFSET_DEGENERATE: tool radius offset collapsed contour")
        else:
            pts_3d = pts_3d_offset

    pts_tuples = [(p.x, p.y, p.z) for p in pts_3d]

    clear_z = inp.clearance_z
    first_pt = pts_tuples[0]
    last_pt = pts_tuples[-1]

    app_len = abs(clear_z - inp.contour_z)
    contour_poly = PolylineSegment(
        points=tuple(Point3D(*p) for p in pts_tuples),
        frame=CoordinateFrame.WCS_COORDINATES,
        closed=inp.closed,
    )
    contour_len = contour_poly.length

    segments: list[ToolpathSegment] = [
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.APPROACH,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(first_pt[0], first_pt[1], clear_z),
            end=(first_pt[0], first_pt[1], inp.contour_z),
            length=app_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="CONTOUR_PROFILE",
            source_evidence=["validated_contour", "wcs_defined"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.CUT,
            geometry_type=SegmentGeometryType.POLYLINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=first_pt,
            end=last_pt,
            length=contour_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="CONTOUR_PROFILE",
            polyline_points=pts_tuples,
            source_evidence=["validated_contour"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.RETRACT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(last_pt[0], last_pt[1], inp.contour_z),
            end=(last_pt[0], last_pt[1], clear_z),
            length=app_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="CONTOUR_PROFILE",
        ),
    ]

    metrics = _metrics_from_segments(segments)
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        compensation_side=inp.compensation_side,
        clearance=ClearancePlane(value_mm=clear_z, source=inp.clearance_source),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Face milling generator
# ---------------------------------------------------------------------------

@dataclass
class FaceMillInput:
    operation_ref: str
    region_x_min: float
    region_x_max: float
    region_y_min: float
    region_y_max: float
    face_z: float
    tool_diameter_mm: float | None
    stepover_mm: float | None
    clearance_z: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)


def generate_face_mill_toolpath(inp: FaceMillInput) -> Toolpath:
    """Generate raster face milling path for a rectangular region.

    Blocked when: tool diameter unknown, stepover unknown, WCS unknown.
    Does NOT invent stepover percentage.
    """
    if inp.wcs_ref is None:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["wcs_ref"],
            warnings=["WCS_UNKNOWN: cannot generate face milling path"],
        )

    if inp.tool_diameter_mm is None or inp.tool_diameter_mm <= 0:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["tool_diameter_mm"],
            warnings=["TOOL_DIAMETER_UNKNOWN: cannot generate face milling path"],
        )

    if inp.stepover_mm is None or inp.stepover_mm <= 0:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["stepover_mm: stepover not supplied — no default"],
            warnings=["STEPOVER_UNKNOWN: cannot generate face milling path"],
        )

    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["clearance_z"],
            warnings=["CLEARANCE_UNKNOWN: cannot generate face milling path"],
        )

    clear_z = inp.clearance_z
    tool_r = inp.tool_diameter_mm / 2.0
    stepover = inp.stepover_mm
    x_start = inp.region_x_min - tool_r
    x_end = inp.region_x_max + tool_r
    y = inp.region_y_min - tool_r

    segments: list[ToolpathSegment] = []
    pass_num = 0
    while y <= inp.region_y_max + tool_r:
        x_from = x_start if pass_num % 2 == 0 else x_end
        x_to = x_end if pass_num % 2 == 0 else x_start
        pass_len = abs(x_to - x_from)
        if pass_num == 0:
            segments.append(_make_segment(
                op_ref=inp.operation_ref,
                motion_type=MotionType.APPROACH,
                geometry_type=SegmentGeometryType.LINE,
                frame=CoordinateFrame.WCS_COORDINATES,
                start=(x_from, y, clear_z),
                end=(x_from, y, inp.face_z),
                length=abs(clear_z - inp.face_z),
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                tool_ref=inp.tool_ref,
                feature_refs=inp.feature_refs,
                strategy="FACE_RASTER",
                source_evidence=["planar_region", "tool_diameter", "stepover", "wcs"],
            ))
        segments.append(_make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.CUT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(x_from, y, inp.face_z),
            end=(x_to, y, inp.face_z),
            length=pass_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="FACE_RASTER",
            source_evidence=["planar_region"],
        ))
        y = round(y + stepover, 6)
        pass_num += 1
        if y <= inp.region_y_max + tool_r:
            next_y = y
            segments.append(_make_segment(
                op_ref=inp.operation_ref,
                motion_type=MotionType.LINK,
                geometry_type=SegmentGeometryType.LINE,
                frame=CoordinateFrame.WCS_COORDINATES,
                start=(x_to, y - stepover, inp.face_z),
                end=(x_to if pass_num % 2 == 0 else x_start, next_y, inp.face_z),
                length=stepover,
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                tool_ref=inp.tool_ref,
                feature_refs=inp.feature_refs,
                strategy="FACE_RASTER",
                warnings=["LINK_PATH_STATUS: VERIFICATION_REQUIRED"],
            ))

    last_seg = segments[-1]
    if last_seg.end_point:
        ep = last_seg.end_point
        segments.append(_make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.RETRACT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=ep,
            end=(ep[0], ep[1], clear_z),
            length=abs(clear_z - ep[2]),
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="FACE_RASTER",
        ))

    metrics = _metrics_from_segments(segments)
    metrics = metrics.model_copy(update={"depth_level_count": 1, "max_depth_mm": 0.0})
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        link_status=LinkStatus.VERIFICATION_REQUIRED,
        clearance=ClearancePlane(value_mm=clear_z, source=inp.clearance_source),
        step_parameters=StepParameters(
            stepover_mm=inp.stepover_mm,
            stepover_source="USER_DEFINED",
        ),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
    )


# ---------------------------------------------------------------------------
# Pocket toolpath generator (offset strategy)
# ---------------------------------------------------------------------------

@dataclass
class PocketInput:
    operation_ref: str
    boundary_points: list[tuple[float, float]]
    pocket_top_z: float
    pocket_bottom_z: float
    tool_diameter_mm: float | None
    stepdown_mm: float | None
    stepover_mm: float | None
    strategy: PocketStrategy = PocketStrategy.OFFSET
    clearance_z: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)


def generate_pocket_toolpath(inp: PocketInput) -> Toolpath:
    """Generate simple offset pocket path.

    Blocked when: tool diameter, stepdown, stepover, WCS, or clearance unknown.
    ADAPTIVE_CANDIDATE emits a placeholder segment, not a real adaptive path.
    """
    missing: list[str] = []
    warnings: list[str] = []

    if inp.wcs_ref is None:
        missing.append("wcs_ref")
        warnings.append("WCS_UNKNOWN")
    if inp.tool_diameter_mm is None or inp.tool_diameter_mm <= 0:
        missing.append("tool_diameter_mm")
        warnings.append("TOOL_DIAMETER_UNKNOWN")
    if inp.stepdown_mm is None or inp.stepdown_mm <= 0:
        missing.append("stepdown_mm: no default stepdown")
        warnings.append("STEPDOWN_UNKNOWN")
    if inp.stepover_mm is None or inp.stepover_mm <= 0:
        missing.append("stepover_mm: no default stepover")
        warnings.append("STEPOVER_UNKNOWN")
    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        missing.append("clearance_z")
        warnings.append("CLEARANCE_UNKNOWN")

    if missing:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=missing,
            warnings=warnings,
        )

    if inp.strategy == PocketStrategy.ADAPTIVE_CANDIDATE:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            status=ToolpathStatus.PARTIAL,
            fidelity=ToolpathFidelity.PARTIAL,
            warnings=[
                "ADAPTIVE_STRATEGY_CANDIDATE: adaptive clearing is a strategy "
                "requirement for Level 10 — full adaptive algorithm requires Level 11+"
            ],
            missing_inputs=["adaptive_algorithm: not implemented at Level 10"],
        )

    try:
        z_levels = compute_z_levels(
            inp.pocket_top_z, inp.pocket_bottom_z, inp.stepdown_mm  # type: ignore[arg-type]
        )
    except ValueError:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=["valid stepdown"],
            warnings=["STEPDOWN_INVALID"],
        )

    tool_r = inp.tool_diameter_mm / 2.0  # type: ignore[operator]
    clear_z = inp.clearance_z  # type: ignore[assignment]
    boundary_3d = [Point3D(p[0], p[1], inp.pocket_top_z) for p in inp.boundary_points]
    segments: list[ToolpathSegment] = []
    first = True
    for z_level in z_levels:
        offset_pts = offset_polyline_2d(boundary_3d, -tool_r, "LEFT")
        if not offset_pts:
            warnings.append(f"OFFSET_DEGENERATE at z={z_level}: tool too large for pocket")
            break
        pts_at_z = [(p.x, p.y, z_level) for p in offset_pts]
        if first:
            first_pt = pts_at_z[0]
            app_len = abs(clear_z - z_level)
            segments.append(_make_segment(
                op_ref=inp.operation_ref,
                motion_type=MotionType.APPROACH,
                geometry_type=SegmentGeometryType.LINE,
                frame=CoordinateFrame.WCS_COORDINATES,
                start=(first_pt[0], first_pt[1], clear_z),
                end=(first_pt[0], first_pt[1], z_level),
                length=app_len,
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                tool_ref=inp.tool_ref,
                feature_refs=inp.feature_refs,
                strategy=inp.strategy.value,
                source_evidence=["pocket_boundary", "tool_diameter", "stepdown", "wcs"],
            ))
            first = False
        poly = PolylineSegment(
            points=tuple(Point3D(*p) for p in pts_at_z),
            frame=CoordinateFrame.WCS_COORDINATES,
            closed=True,
        )
        segments.append(_make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.CUT,
            geometry_type=SegmentGeometryType.POLYLINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=pts_at_z[0],
            end=pts_at_z[-1],
            length=poly.length,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy=inp.strategy.value,
            polyline_points=pts_at_z,
            source_evidence=["pocket_boundary"],
        ))

    if segments:
        last_end = segments[-1].end_point
        if last_end:
            segments.append(_make_segment(
                op_ref=inp.operation_ref,
                motion_type=MotionType.RETRACT,
                geometry_type=SegmentGeometryType.LINE,
                frame=CoordinateFrame.WCS_COORDINATES,
                start=last_end,
                end=(last_end[0], last_end[1], clear_z),
                length=abs(clear_z - last_end[2]),
                setup_ref=inp.setup_ref,
                wcs_ref=inp.wcs_ref,
                tool_ref=inp.tool_ref,
                feature_refs=inp.feature_refs,
                strategy=inp.strategy.value,
            ))

    metrics = _metrics_from_segments(segments)
    metrics = metrics.model_copy(update={
        "depth_level_count": len(z_levels),
        "max_depth_mm": abs(inp.pocket_bottom_z - inp.pocket_top_z),
    })
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        clearance=ClearancePlane(value_mm=clear_z, source=inp.clearance_source),
        step_parameters=StepParameters(
            stepdown_mm=inp.stepdown_mm,
            stepover_mm=inp.stepover_mm,
            stepdown_source="USER_DEFINED",
            stepover_source="USER_DEFINED",
        ),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Slot toolpath generator
# ---------------------------------------------------------------------------

@dataclass
class SlotInput:
    operation_ref: str
    slot_start: tuple[float, float]
    slot_end: tuple[float, float]
    slot_z: float
    slot_width_mm: float | None
    slot_depth_mm: float | None
    tool_diameter_mm: float | None
    clearance_z: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)


def generate_slot_toolpath(inp: SlotInput) -> Toolpath:
    """Generate straight-slot centerline path.

    Blocked when tool wider than slot, or any required input absent.
    """
    missing: list[str] = []

    if inp.wcs_ref is None:
        missing.append("wcs_ref")
    if inp.slot_width_mm is None:
        missing.append("slot_width_mm")
    if inp.slot_depth_mm is None:
        missing.append("slot_depth_mm")
    if inp.tool_diameter_mm is None:
        missing.append("tool_diameter_mm")
    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        missing.append("clearance_z")

    if missing:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=missing,
            warnings=[f"{m.upper().split(':')[0].replace(' ', '_')}_UNKNOWN" for m in missing],
        )

    if inp.tool_diameter_mm > inp.slot_width_mm:  # type: ignore[operator]
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            warnings=[
                f"TOOL_TOO_LARGE: tool diameter {inp.tool_diameter_mm} > "
                f"slot width {inp.slot_width_mm}"
            ],
        )

    clear_z = inp.clearance_z
    bottom_z = inp.slot_z - inp.slot_depth_mm  # type: ignore[operator]
    sx, sy = inp.slot_start
    ex, ey = inp.slot_end
    slot_len = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)

    segments = [
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.APPROACH,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(sx, sy, clear_z),
            end=(sx, sy, inp.slot_z),
            length=abs(clear_z - inp.slot_z),
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="SLOT_MILL",
            source_evidence=["slot_geometry", "tool_fits_slot", "wcs_defined"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.PLUNGE,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(sx, sy, inp.slot_z),
            end=(sx, sy, bottom_z),
            length=inp.slot_depth_mm,  # type: ignore[arg-type]
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="SLOT_MILL",
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.CUT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(sx, sy, bottom_z),
            end=(ex, ey, bottom_z),
            length=slot_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="SLOT_MILL",
            source_evidence=["slot_geometry"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.RETRACT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(ex, ey, bottom_z),
            end=(ex, ey, clear_z),
            length=abs(clear_z - bottom_z),
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="SLOT_MILL",
        ),
    ]

    metrics = _metrics_from_segments(segments)
    metrics = metrics.model_copy(update={
        "depth_level_count": 1,
        "max_depth_mm": inp.slot_depth_mm,
    })
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        clearance=ClearancePlane(value_mm=clear_z, source=inp.clearance_source),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
    )


# ---------------------------------------------------------------------------
# Chamfer toolpath generator
# ---------------------------------------------------------------------------

@dataclass
class ChamferInput:
    operation_ref: str
    contour_points: list[tuple[float, float]]
    contour_z: float
    tool_diameter_mm: float | None
    tool_angle_deg: float | None
    chamfer_depth_mm: float | None
    clearance_z: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)


def generate_chamfer_toolpath(inp: ChamferInput) -> Toolpath:
    """Generate chamfer path. Blocked when tool geometry or depth unknown."""
    missing: list[str] = []
    warnings: list[str] = []

    if inp.wcs_ref is None:
        missing.append("wcs_ref")
    if inp.tool_diameter_mm is None:
        missing.append("tool_diameter_mm")
    if inp.tool_angle_deg is None:
        missing.append("tool_angle_deg")
    if inp.chamfer_depth_mm is None:
        missing.append("chamfer_depth_mm")
    if inp.clearance_z is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        missing.append("clearance_z")
    if len(inp.contour_points) < 2:
        missing.append("contour_points")

    if missing:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=missing,
            warnings=["CHAMFER_BLOCKED: required inputs absent"],
        )

    contact_z = inp.contour_z - inp.chamfer_depth_mm  # type: ignore[operator]
    pts_tuples = [(p[0], p[1], contact_z) for p in inp.contour_points]
    clear_z = inp.clearance_z
    first_pt = pts_tuples[0]
    last_pt = pts_tuples[-1]
    contour_len = sum(
        math.sqrt((pts_tuples[i + 1][0] - pts_tuples[i][0])**2 +
                  (pts_tuples[i + 1][1] - pts_tuples[i][1])**2)
        for i in range(len(pts_tuples) - 1)
    )
    app_len = abs(clear_z - contact_z)

    segments = [
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.APPROACH,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(first_pt[0], first_pt[1], clear_z),
            end=first_pt,
            length=app_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="CHAMFER",
            source_evidence=["confirmed_chamfer", "tool_angle_known", "depth_derivable"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.CUT,
            geometry_type=SegmentGeometryType.POLYLINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=first_pt,
            end=last_pt,
            length=contour_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="CHAMFER",
            polyline_points=pts_tuples,
            source_evidence=["confirmed_chamfer"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.RETRACT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=last_pt,
            end=(last_pt[0], last_pt[1], clear_z),
            length=app_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy="CHAMFER",
        ),
    ]

    metrics = _metrics_from_segments(segments)
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        clearance=ClearancePlane(value_mm=clear_z, source=inp.clearance_source),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# Turning path generator
# ---------------------------------------------------------------------------

@dataclass
class TurningInput:
    operation_ref: str
    turning_motion_type: TurningMotionType
    start_z: float
    end_z: float
    start_x: float
    end_x: float
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = field(default_factory=list)
    clearance_x: float | None = None
    clearance_source: ClearanceSource = ClearanceSource.UNKNOWN


def generate_turning_toolpath(inp: TurningInput) -> Toolpath:
    """Generate turning primitive path in XZ lathe coordinate space.

    Uses lathe XZ semantics — does NOT mix with milling XYZ.
    Blocked when WCS unknown or clearance unknown.
    """
    missing: list[str] = []
    warnings: list[str] = []

    if inp.wcs_ref is None:
        missing.append("wcs_ref")
        warnings.append("WCS_UNKNOWN: cannot generate turning path")
    if inp.clearance_x is None or inp.clearance_source == ClearanceSource.UNKNOWN:
        missing.append("clearance_x")
        warnings.append("CLEARANCE_UNKNOWN: cannot generate turning path")

    if missing:
        return Toolpath(
            toolpath_id=_tp_id(),
            operation_ref=inp.operation_ref,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            status=ToolpathStatus.BLOCKED,
            fidelity=ToolpathFidelity.BLOCKED,
            missing_inputs=missing,
            warnings=warnings,
        )

    clear_x = inp.clearance_x
    turning_z_len = abs(inp.end_z - inp.start_z)
    turning_x_len = abs(inp.end_x - inp.start_x)

    if inp.turning_motion_type in (TurningMotionType.AXIAL_CUT,
                                   TurningMotionType.PROFILE_CUT):
        motion_len = math.sqrt(turning_z_len**2 + turning_x_len**2)
    elif inp.turning_motion_type == TurningMotionType.FACE_CUT:
        motion_len = turning_x_len
    else:
        motion_len = max(turning_z_len, turning_x_len)

    app_len = abs(clear_x - inp.start_x)

    segments = [
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.APPROACH,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(clear_x, 0.0, inp.start_z),
            end=(inp.start_x, 0.0, inp.start_z),
            length=app_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy=inp.turning_motion_type.value,
            source_evidence=["turning_coordinate_xz", "wcs_defined"],
            warnings=["TURNING_XZ_SEMANTICS: lathe XZ, not milling XYZ"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.CUT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(inp.start_x, 0.0, inp.start_z),
            end=(inp.end_x, 0.0, inp.end_z),
            length=motion_len,
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy=inp.turning_motion_type.value,
            source_evidence=["turning_geometry"],
        ),
        _make_segment(
            op_ref=inp.operation_ref,
            motion_type=MotionType.RETRACT,
            geometry_type=SegmentGeometryType.LINE,
            frame=CoordinateFrame.WCS_COORDINATES,
            start=(inp.end_x, 0.0, inp.end_z),
            end=(clear_x, 0.0, inp.end_z),
            length=abs(clear_x - inp.end_x),
            setup_ref=inp.setup_ref,
            wcs_ref=inp.wcs_ref,
            tool_ref=inp.tool_ref,
            feature_refs=inp.feature_refs,
            strategy=inp.turning_motion_type.value,
        ),
    ]

    metrics = _metrics_from_segments(segments)
    metrics = metrics.model_copy(update={"max_depth_mm": turning_x_len})
    viz = _viz_from_segments(segments, CoordinateFrame.WCS_COORDINATES)

    return Toolpath(
        toolpath_id=_tp_id(),
        operation_ref=inp.operation_ref,
        setup_ref=inp.setup_ref,
        wcs_ref=inp.wcs_ref,
        tool_ref=inp.tool_ref,
        feature_refs=inp.feature_refs,
        frame=CoordinateFrame.WCS_COORDINATES,
        segments=segments,
        entry_type=EntryType.PLUNGE,
        exit_type=ExitType.DIRECT_RETRACT,
        clearance=ClearancePlane(value_mm=clear_x, source=inp.clearance_source),
        metrics=metrics,
        visualization=viz,
        fidelity=ToolpathFidelity.EXACT_GENERATED,
        status=ToolpathStatus.VERIFICATION_REQUIRED,
        warnings=warnings,
    )
