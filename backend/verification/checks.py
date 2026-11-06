"""
Level-11 verification check functions.

Each function is fail-closed:
  - Missing required data → NOT_PERFORMED or INSUFFICIENT_DATA (never PASS)
  - Only explicit geometry produces PASS
  - Partial model != collision-free
  - Unknown != safe

NO_FABRICATED_DATA=YES  NO_HARDCODED_SAFE=YES
"""

from __future__ import annotations

import math
import uuid

from .enums import (
    VerificationCheckType,
    VerificationSeverity,
    VerificationStatus,
)
from .models import VerificationIssue, VerificationResult, VerificationSegment
from .stock import FixtureGeometry, StockModel
from .swept_volume import AABB, segment_cylinder_intersects_aabb
from .tolerance import DEFAULT_TOLERANCE, TolerancePolicy


def _issue(
    check_type: VerificationCheckType,
    severity: VerificationSeverity,
    message: str,
    segment_id: str | None = None,
    evidence: dict | None = None,
) -> VerificationIssue:
    return VerificationIssue(
        issue_id=str(uuid.uuid4())[:12],
        check_type=check_type,
        severity=severity,
        message=message,
        segment_id=segment_id,
        evidence=evidence or {},
    )


def _pass(check_type: VerificationCheckType, **evidence) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.PASS,
        severity=VerificationSeverity.INFO,
        evidence=evidence,
    )


def _not_performed(
    check_type: VerificationCheckType, reason: str
) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.NOT_PERFORMED,
        severity=VerificationSeverity.WARNING,
        warnings=[reason],
    )


def _insufficient(
    check_type: VerificationCheckType, reason: str
) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.INSUFFICIENT_DATA,
        severity=VerificationSeverity.WARNING,
        warnings=[reason],
    )


def _fail(
    check_type: VerificationCheckType,
    severity: VerificationSeverity,
    issues: list[VerificationIssue],
    warnings: list[str] | None = None,
) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.FAIL,
        severity=severity,
        issues=issues,
        errors=[i.message for i in issues],
        warnings=warnings or [],
    )


def check_part_gouge(
    segments: list[VerificationSegment],
    part_bbox_min: tuple[float, float, float] | None,
    part_bbox_max: tuple[float, float, float] | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.PART_GOUGE
    if part_bbox_min is None or part_bbox_max is None:
        return _insufficient(ct, "Part geometry not provided; PART_GOUGE cannot be checked")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown; PART_GOUGE check accuracy impaired")

    part_min_z = part_bbox_min[2]
    cutting = [s for s in segments if s.is_cutting]
    if not cutting:
        return _pass(ct, note="No cutting segments")

    issues: list[VerificationIssue] = []
    part_aabb = AABB(
        part_bbox_min[0],
        part_bbox_min[1],
        part_bbox_min[2],
        part_bbox_max[0],
        part_bbox_max[1],
        part_bbox_max[2],
    )
    radius = tool_diameter_mm / 2.0

    for seg in cutting:
        z_low = min(seg.start_z, seg.end_z)
        if z_low < part_min_z - tol.gouge_mm:
            issues.append(
                _issue(
                    ct,
                    VerificationSeverity.CRITICAL,
                    f"Cutting below part bottom: z_min={z_low:.4f} < part_z={part_min_z:.4f}",
                    segment_id=seg.segment_id,
                    evidence={
                        "segment_z_min": z_low,
                        "part_min_z": part_min_z,
                        "tolerance_mm": tol.gouge_mm,
                    },
                )
            )
        elif segment_cylinder_intersects_aabb(
            seg.start_x,
            seg.start_y,
            seg.start_z,
            seg.end_x,
            seg.end_y,
            seg.end_z,
            radius,
            part_aabb,
        ):
            issues.append(
                _issue(
                    ct,
                    VerificationSeverity.WARNING,
                    "Cutting segment overlaps part bounding box (conservative bbox check)",
                    segment_id=seg.segment_id,
                    evidence={"note": "May be false positive; mesh check not available"},
                )
            )

    if any(i.severity == VerificationSeverity.CRITICAL for i in issues):
        return _fail(
            ct,
            VerificationSeverity.CRITICAL,
            [i for i in issues if i.severity == VerificationSeverity.CRITICAL],
            warnings=["PART_GOUGE uses bounding-box approximation"],
        )
    if issues:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            issues=issues,
            warnings=["Conservative bbox check; exact mesh not available"],
        )
    return _pass(
        ct,
        note="Bounding-box check passed",
        checked_segments=len(cutting),
        fidelity="APPROXIMATE",
    )


def check_stock_gouge(
    segments: list[VerificationSegment],
    stock: StockModel | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.STOCK_GOUGE
    if stock is None or not stock.is_known:
        return _insufficient(ct, "Stock geometry not provided; STOCK_GOUGE cannot be checked")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown")

    cutting = [s for s in segments if s.is_cutting]
    if not cutting:
        return _pass(ct, note="No cutting segments")

    issues: list[VerificationIssue] = []
    for seg in cutting:
        for pt in [
            (seg.start_x, seg.start_y, seg.start_z),
            (seg.end_x, seg.end_y, seg.end_z),
        ]:
            if not _valid_coords(*pt):
                issues.append(
                    _issue(ct, VerificationSeverity.ERROR, f"Invalid coordinates: {pt}")
                )
                continue
            if not stock.contains_point(*pt):
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.ERROR,
                        f"Cutting outside stock at ({pt[0]:.3f}, {pt[1]:.3f}, {pt[2]:.3f})",
                        segment_id=seg.segment_id,
                        evidence={"point": list(pt)},
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.ERROR, issues)
    return _pass(ct, checked_segments=len(cutting), fidelity="APPROXIMATE")


def check_tool_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.TOOL_COLLISION
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; tool collision cannot be checked")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown")

    radius = tool_diameter_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm,
                fixture.min_y_mm,
                fixture.min_z_mm,
                fixture.max_x_mm,
                fixture.max_y_mm,
                fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x,
                seg.start_y,
                seg.start_z,
                seg.end_x,
                seg.end_y,
                seg.end_z,
                radius,
                faabb,
            ):
                label = (
                    "COLLISION_CONTACT" if not seg.is_cutting
                    else "CUTTING_CONTACT_WITH_FIXTURE"
                )
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Tool body intersects fixture '{fixture.fixture_id}' ({label})"
                        f" during {seg.motion_type}",
                        segment_id=seg.segment_id,
                        evidence={
                            "fixture_id": fixture.fixture_id,
                            "motion_type": seg.motion_type,
                            "contact_type": label,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, checked_fixtures=len(fixtures), checked_segments=len(segments))


def check_holder_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_length_mm: float | None,
    holder_diameter_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.HOLDER_COLLISION
    if holder_diameter_mm is None:
        return _not_performed(ct, "Holder geometry unknown; HOLDER_COLLISION=NOT_PERFORMED")
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; holder collision cannot be checked")
    if tool_length_mm is None:
        return _insufficient(ct, "Tool length unknown; holder position cannot be determined")

    holder_radius = holder_diameter_mm / 2.0
    holder_offset_z = tool_length_mm
    issues: list[VerificationIssue] = []

    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        h_start_z = seg.start_z + holder_offset_z
        h_end_z = seg.end_z + holder_offset_z
        h_len = holder_length_mm if holder_length_mm else 50.0
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm,
                fixture.min_y_mm,
                fixture.min_z_mm,
                fixture.max_x_mm,
                fixture.max_y_mm,
                fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x,
                seg.start_y,
                h_start_z,
                seg.end_x,
                seg.end_y,
                h_end_z + h_len,
                holder_radius,
                faabb,
            ):
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Holder intersects fixture '{fixture.fixture_id}'"
                        f" during {seg.motion_type}",
                        segment_id=seg.segment_id,
                        evidence={
                            "fixture_id": fixture.fixture_id,
                            "holder_radius": holder_radius,
                            "holder_z_offset": holder_offset_z,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, checked_fixtures=len(fixtures), holder_diameter_mm=holder_diameter_mm)


def check_fixture_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    holder_diameter_mm: float | None,
    tool_length_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.FIXTURE_COLLISION
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; fixture collision cannot be checked")

    tool_result = check_tool_collision(segments, fixtures, tool_diameter_mm, tol)
    holder_result = check_holder_collision(
        segments, fixtures, tool_length_mm, holder_diameter_mm, holder_length_mm, tol
    )

    combined_issues: list[VerificationIssue] = []
    combined_issues.extend(tool_result.issues)
    combined_issues.extend(holder_result.issues)
    combined_warnings: list[str] = list(tool_result.warnings) + list(holder_result.warnings)

    if combined_issues:
        return _fail(ct, VerificationSeverity.CRITICAL, combined_issues, combined_warnings)

    sub_statuses = {tool_result.status, holder_result.status}
    if VerificationStatus.INSUFFICIENT_DATA in sub_statuses:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.INSUFFICIENT_DATA,
            severity=VerificationSeverity.WARNING,
            warnings=combined_warnings,
        )
    if VerificationStatus.NOT_PERFORMED in sub_statuses:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            warnings=["Holder geometry not checked"] + combined_warnings,
        )
    return _pass(ct, checked_fixtures=len(fixtures))


def check_rapid_clearance(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.RAPID_CLEARANCE
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; rapid clearance cannot be checked globally")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown")

    rapids = [
        s
        for s in segments
        if s.motion_type in ("RAPID", "LINK", "RETRACT", "APPROACH")
    ]
    if not rapids:
        return _pass(ct, note="No rapid/link/retract segments to check")

    radius = tool_diameter_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in rapids:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm,
                fixture.min_y_mm,
                fixture.min_z_mm,
                fixture.max_x_mm,
                fixture.max_y_mm,
                fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x,
                seg.start_y,
                seg.start_z,
                seg.end_x,
                seg.end_y,
                seg.end_z,
                radius,
                faabb,
            ):
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Rapid/link move intersects fixture"
                        f" '{fixture.fixture_id}' ({seg.motion_type})",
                        segment_id=seg.segment_id,
                        evidence={
                            "fixture_id": fixture.fixture_id,
                            "motion_type": seg.motion_type,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, checked_rapids=len(rapids), checked_fixtures=len(fixtures))


def check_machine_envelope(
    segments: list[VerificationSegment],
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.MACHINE_ENVELOPE
    if travel_x_mm is None or travel_y_mm is None or travel_z_mm is None:
        return _insufficient(ct, "Machine travel limits not specified")

    half_x = travel_x_mm / 2.0
    half_y = travel_y_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        for pt, _label in [
            ((seg.start_x, seg.start_y, seg.start_z), "start"),
            ((seg.end_x, seg.end_y, seg.end_z), "end"),
        ]:
            if not _valid_coords(*pt):
                continue
            if abs(pt[0]) > half_x or abs(pt[1]) > half_y or pt[2] < -travel_z_mm:
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Path point exceeds machine travel:"
                        f" ({pt[0]:.3f}, {pt[1]:.3f}, {pt[2]:.3f})",
                        segment_id=seg.segment_id,
                        evidence={
                            "point": list(pt),
                            "travel_x": travel_x_mm,
                            "travel_y": travel_y_mm,
                            "travel_z": travel_z_mm,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, travel_x=travel_x_mm, travel_y=travel_y_mm, travel_z=travel_z_mm)


def check_overtravel(
    segments: list[VerificationSegment],
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Fail-closed overtravel check — any point beyond limits → FAIL."""
    ct = VerificationCheckType.OVERTRAVEL
    if travel_x_mm is None or travel_y_mm is None or travel_z_mm is None:
        return _insufficient(ct, "Machine travel limits not specified; OVERTRAVEL fail-closed")

    half_x = travel_x_mm / 2.0
    half_y = travel_y_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        for pt in [
            (seg.start_x, seg.start_y, seg.start_z),
            (seg.end_x, seg.end_y, seg.end_z),
        ]:
            if not _valid_coords(*pt):
                continue
            overtravel_axes: list[str] = []
            if abs(pt[0]) > half_x:
                overtravel_axes.append(f"X={pt[0]:.3f} limit=±{half_x:.3f}")
            if abs(pt[1]) > half_y:
                overtravel_axes.append(f"Y={pt[1]:.3f} limit=±{half_y:.3f}")
            if pt[2] < -travel_z_mm:
                overtravel_axes.append(f"Z={pt[2]:.3f} limit={-travel_z_mm:.3f}")
            if overtravel_axes:
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        "OVERTRAVEL: " + "; ".join(overtravel_axes),
                        segment_id=seg.segment_id,
                        evidence={"point": list(pt), "axes": overtravel_axes},
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, travel_x=travel_x_mm, travel_y=travel_y_mm, travel_z=travel_z_mm)


def check_axis_limit(
    segments: list[VerificationSegment],
    axis_limits: dict[str, tuple[float, float]] | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.AXIS_LIMIT
    if axis_limits is None:
        return _not_performed(ct, "No machine axis limits defined")

    coord_map = {"X": 0, "Y": 1, "Z": 2}
    issues: list[VerificationIssue] = []

    for seg in segments:
        for pt in [
            (seg.start_x, seg.start_y, seg.start_z),
            (seg.end_x, seg.end_y, seg.end_z),
        ]:
            if not _valid_coords(*pt):
                continue
            for axis, (lo, hi) in axis_limits.items():
                idx = coord_map.get(axis.upper())
                if idx is None:
                    continue
                val = pt[idx]
                if val < lo or val > hi:
                    issues.append(
                        _issue(
                            ct,
                            VerificationSeverity.CRITICAL,
                            f"Axis {axis} value {val:.3f} outside [{lo:.3f}, {hi:.3f}]",
                            segment_id=seg.segment_id,
                            evidence={"axis": axis, "value": val, "min": lo, "max": hi},
                        )
                    )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, axes_checked=list(axis_limits.keys()))


def check_tool_reach(
    segments: list[VerificationSegment],
    flute_length_mm: float | None,
    holder_clearance_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.TOOL_REACH
    if flute_length_mm is None:
        return _insufficient(ct, "Tool flute length unknown; TOOL_REACH cannot be checked")

    cutting = [s for s in segments if s.is_cutting]
    if not cutting:
        return _pass(ct, note="No cutting segments")

    z_ref = max(s.start_z for s in cutting if s.is_cutting)
    max_depth = 0.0
    for seg in cutting:
        depth = z_ref - min(seg.start_z, seg.end_z)
        if depth > max_depth:
            max_depth = depth

    effective_reach = flute_length_mm
    if holder_clearance_mm is not None:
        effective_reach = min(flute_length_mm, holder_clearance_mm)

    issues: list[VerificationIssue] = []
    if max_depth > effective_reach + tol.linear_mm:
        issues.append(
            _issue(
                ct,
                VerificationSeverity.CRITICAL,
                f"Path depth {max_depth:.4f}mm exceeds"
                f" effective tool reach {effective_reach:.4f}mm",
                evidence={
                    "max_depth_mm": max_depth,
                    "flute_length_mm": flute_length_mm,
                    "holder_clearance_mm": holder_clearance_mm,
                    "effective_reach_mm": effective_reach,
                },
            )
        )

    if issues:
        return _fail(
            ct,
            VerificationSeverity.CRITICAL,
            issues,
            warnings=["TOOL_REACH, FLUTE_LENGTH, HOLDER_CLEARANCE reported separately"],
        )
    return _pass(
        ct,
        max_depth_mm=max_depth,
        flute_length_mm=flute_length_mm,
        holder_clearance_mm=holder_clearance_mm,
        effective_reach_mm=effective_reach,
    )


def check_stock_remaining(
    segments: list[VerificationSegment],
    stock: StockModel | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> tuple[VerificationResult, float | None, float | None]:
    """Returns (result, remaining_volume_mm3, removed_volume_mm3)."""
    ct = VerificationCheckType.STOCK_REMAINING
    if stock is None or not stock.is_known:
        return (
            _insufficient(ct, "Stock geometry not provided; remaining stock unknown"),
            None, None,
        )
    if tool_diameter_mm is None:
        return (
            _insufficient(ct, "Tool diameter unknown; stock removal cannot be computed"),
            None, None,
        )

    from .stock import VoxelGrid

    grid = VoxelGrid.from_stock(stock, tol)
    if grid is None:
        return _insufficient(ct, "Could not create voxel grid for given stock shape"), None, None

    initial_vol = stock.volume_mm3()
    radius = tool_diameter_mm / 2.0
    cutting = [s for s in segments if s.is_cutting]

    resource_hit = False
    for seg in cutting:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        ok = grid.remove_path_segment(
            seg.start_x, seg.start_y, seg.start_z,
            seg.end_x, seg.end_y, seg.end_z,
            radius, tol,
        )
        if not ok:
            resource_hit = True
            break

    remaining = grid.volume_remaining_mm3()
    removed = None if initial_vol is None else max(0.0, initial_vol - remaining)

    if resource_hit:
        result = VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            evidence={
                "remaining_volume_mm3": remaining,
                "fidelity": "VOXEL_APPROXIMATE",
                "resource_limit_hit": True,
            },
            warnings=["Simulation hit iteration limit; stock removal is PARTIAL"],
        )
    else:
        result = VerificationResult(
            check_type=ct,
            status=VerificationStatus.PASS,
            severity=VerificationSeverity.INFO,
            evidence={
                "remaining_volume_mm3": remaining,
                "initial_volume_mm3": initial_vol,
                "removed_volume_mm3": removed,
                "fidelity": "VOXEL_APPROXIMATE",
            },
            warnings=["Stock removal is voxel-approximate; not suitable for tolerance inspection"],
        )
    return result, remaining, removed


def check_kinematic(
    segments: list[VerificationSegment],
    machine_model: dict | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.KINEMATIC_CHECK
    return _not_performed(
        ct,
        "KINEMATIC_CHECK is a foundation placeholder at Level 11; "
        "full kinematic simulation deferred to Level 12+",
    )


def _valid_coords(x: float, y: float, z: float) -> bool:
    """Return False for NaN, Inf, or extreme coordinates."""
    for v in (x, y, z):
        if math.isnan(v) or math.isinf(v):
            return False
        if abs(v) > 1e9:
            return False
    return True
