"""
Level-11 simulation orchestration.

run_simulation runs all 12 check types for the requested profile.
SimulationStatus.COMPLETED != VerificationState.VERIFIED — they are separate concepts.
is_verified is a derived property — TRUE only when all mandatory checks PASS.
"""

from __future__ import annotations

import uuid

from .checks import (
    check_axis_limit,
    check_fixture_collision,
    check_holder_fixture_collision,
    check_holder_part_collision,
    check_holder_stock_collision,
    check_kinematic,
    check_machine_envelope_with_wcs,
    check_overtravel,
    check_part_fixture_interference,
    check_part_gouge,
    check_part_gouge_exact,
    check_rapid_clearance,
    check_stock_gouge,
    check_stock_remaining,
    check_tool_fixture_collision,
    check_tool_reach,
)
from .enums import (
    SimulationStatus,
    StockRemovalFidelity,
    VerificationCheckType,
    VerificationSeverity,
    VerificationState,
    VerificationStatus,
)
from .models import (
    AxisLimitViolation,
    MachineEnvelopeRecord,
    SimulationRequest,
    SimulationResult,
    VerificationIssue,
    VerificationResult,
    VerificationSummary,
    VisualizationData,
    WCSEnvelopeRecord,
)
from .profiles import get_mandatory_checks
from .tolerance import DEFAULT_TOLERANCE, TolerancePolicy


def derive_verification_state(
    checks: dict[str, VerificationResult],
    profile_mandatory: frozenset[VerificationCheckType],
) -> VerificationState:
    if not checks:
        return VerificationState.UNVERIFIED

    has_fail = any(r.status == VerificationStatus.FAIL for r in checks.values())
    if has_fail:
        return VerificationState.FAILED

    mandatory_statuses = {
        ct: checks.get(ct.value, VerificationResult(
            check_type=ct,
            status=VerificationStatus.NOT_PERFORMED,
            severity=VerificationSeverity.WARNING,
        )).status
        for ct in profile_mandatory
    }

    all_mandatory_pass = all(
        s == VerificationStatus.PASS for s in mandatory_statuses.values()
    )
    if all_mandatory_pass and profile_mandatory:
        return VerificationState.VERIFIED

    any_pass = any(r.status == VerificationStatus.PASS for r in checks.values())
    _non_positive = {
        VerificationStatus.NOT_PERFORMED,
        VerificationStatus.INSUFFICIENT_DATA,
        VerificationStatus.NOT_VERIFIABLE,
    }
    all_non_pass = all(r.status in _non_positive for r in checks.values())

    if all_non_pass and not any_pass:
        return VerificationState.BLOCKED
    if any_pass:
        return VerificationState.PARTIALLY_VERIFIED
    return VerificationState.UNVERIFIED


def _build_summary(
    checks: dict[str, VerificationResult],
    issues: list[VerificationIssue],
    state: VerificationState,
    profile,
) -> VerificationSummary:
    all_results = list(checks.values())
    _not_attempted = {
        VerificationStatus.NOT_PERFORMED,
        VerificationStatus.NOT_VERIFIABLE,
    }
    return VerificationSummary(
        verification_state=state,
        profile=profile,
        checks_performed=sum(
            1 for r in all_results if r.status not in _not_attempted
        ),
        checks_passed=sum(1 for r in all_results if r.status == VerificationStatus.PASS),
        checks_failed=sum(1 for r in all_results if r.status == VerificationStatus.FAIL),
        checks_not_performed=sum(
            1 for r in all_results if r.status in _not_attempted
        ),
        checks_insufficient_data=sum(
            1 for r in all_results if r.status == VerificationStatus.INSUFFICIENT_DATA
        ),
        critical_issues=sum(
            1 for i in issues if i.severity == VerificationSeverity.CRITICAL
        ),
        error_issues=sum(
            1 for i in issues if i.severity == VerificationSeverity.ERROR
        ),
        warning_issues=sum(
            1 for i in issues if i.severity == VerificationSeverity.WARNING
        ),
        info_issues=sum(
            1 for i in issues if i.severity == VerificationSeverity.INFO
        ),
    )


def _build_visualization(
    request: SimulationRequest,
    checks: dict[str, VerificationResult] | None = None,
) -> VisualizationData:
    viz = VisualizationData()
    for seg in request.segments:
        pt = [seg.start_x, seg.start_y, seg.start_z]
        if seg.is_cutting:
            viz.cutting_points.append(pt)
        else:
            viz.rapid_points.append(pt)
    viz.has_tool_layer = bool(request.tool_diameter_mm)

    if request.stock is not None and request.stock.has_box_dims:
        s = request.stock
        viz.stock_bbox = {
            "min_x": s.min_x_mm, "min_y": s.min_y_mm, "min_z": s.min_z_mm,
            "max_x": s.max_x_mm, "max_y": s.max_y_mm, "max_z": s.max_z_mm,
        }

    if request.part_bbox_min and request.part_bbox_max:
        viz.part_bbox = {
            "min_x": request.part_bbox_min[0],
            "min_y": request.part_bbox_min[1],
            "min_z": request.part_bbox_min[2],
            "max_x": request.part_bbox_max[0],
            "max_y": request.part_bbox_max[1],
            "max_z": request.part_bbox_max[2],
        }

    for fix in request.fixtures:
        viz.fixture_bboxes.append({
            "id": fix.fixture_id,
            "min_x": fix.min_x_mm, "min_y": fix.min_y_mm, "min_z": fix.min_z_mm,
            "max_x": fix.max_x_mm, "max_y": fix.max_y_mm, "max_z": fix.max_z_mm,
        })
    viz.has_fixture_layer = bool(request.fixtures)

    # Phase M: holder bbox layer
    hg = request.holder_geometry
    hd = hg.max_diameter_mm if hg else request.holder_diameter_mm
    hl = hg.gauge_length_mm if hg else request.holder_length_mm
    if hd is not None and request.tool_length_mm is not None:
        viz.has_holder_layer = True
        # Represent holder as a set of bboxes centered on each toolpath point
        for seg in request.segments[:20]:  # limit visualization to avoid overload
            center_z = seg.start_z + request.tool_length_mm
            r = hd / 2.0
            h = hl if hl else 50.0
            viz.holder_bboxes.append({
                "cx": seg.start_x, "cy": seg.start_y,
                "z_bottom": center_z, "z_top": center_z + h,
                "radius": r,
            })

    # Phase M: collect collision/gouge points from checks
    if checks:
        from .enums import VerificationStatus
        for check_key, result in checks.items():
            if result.status == VerificationStatus.FAIL:
                for issue in result.issues:
                    pt_data = issue.evidence.get("point")
                    if pt_data and len(pt_data) >= 3:
                        if "GOUGE" in check_key.upper():
                            viz.gouge_points.append(list(pt_data[:3]))
                        else:
                            viz.collision_points.append(list(pt_data[:3]))
        viz.has_collision_layer = bool(viz.collision_points)
        viz.has_gouge_layer = bool(viz.gouge_points)

    # Toolpath extents
    if request.segments:
        xs = [s.start_x for s in request.segments] + [s.end_x for s in request.segments]
        ys = [s.start_y for s in request.segments] + [s.end_y for s in request.segments]
        zs = [s.start_z for s in request.segments] + [s.end_z for s in request.segments]
        viz.toolpath_extents = {
            "min_x": min(xs), "max_x": max(xs),
            "min_y": min(ys), "max_y": max(ys),
            "min_z": min(zs), "max_z": max(zs),
        }
    return viz


def run_simulation(
    request: SimulationRequest,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> SimulationResult:
    """
    Run all 12 verification check types for the given profile.

    Every check is always attempted — profile determines which are mandatory for VERIFIED.
    COMPLETED simulation != VERIFIED toolpath.
    """
    if len(request.segments) > tol.max_path_segments:
        return SimulationResult(
            session_id=str(uuid.uuid4()),
            toolpath_id=request.toolpath_id,
            simulation_status=SimulationStatus.FAILED,
            verification_state=VerificationState.BLOCKED,
            profile=request.profile,
            errors=[
                f"Segment count {len(request.segments)} exceeds limit {tol.max_path_segments}"
            ],
            resource_limit_hit=True,
        )

    segs = request.segments
    stock = request.stock
    fixtures = request.fixtures
    td = request.tool_diameter_mm
    tl = request.tool_length_mm
    fl = request.tool_flute_length_mm
    pmin = request.part_bbox_min
    pmax = request.part_bbox_max

    # Resolve holder geometry: rich record takes precedence over simple floats
    hg = request.holder_geometry
    hd = hg.max_diameter_mm if hg else request.holder_diameter_mm
    hl = hg.gauge_length_mm if hg else request.holder_length_mm

    # Resolve machine axis limits: explicit dict takes precedence over travel scalars
    # Apply WCS offsets to travel checks when WCS is non-zero
    tx = request.machine_travel_x_mm
    ty = request.machine_travel_y_mm
    tz = request.machine_travel_z_mm
    axis_limits = request.axis_limits
    if axis_limits is None and tx is not None and ty is not None and tz is not None:
        # Build axis_limits from travel scalars for explicit limit tracking
        half_x = tx / 2.0
        half_y = ty / 2.0
        # Apply WCS offset to limits so they represent machine coordinates
        cx = request.wcs_offset_x_mm
        cy = request.wcs_offset_y_mm
        cz = request.wcs_offset_z_mm
        axis_limits = {
            "X": (-half_x + cx, half_x + cx),
            "Y": (-half_y + cy, half_y + cy),
            "Z": (-tz + cz, 0.0 + cz),
        }

    checks: dict[str, VerificationResult] = {}

    # Phase D: PART_GOUGE (conservative bbox) — NEVER returns PASS per HARD RULE 1+2
    r_part_gouge = check_part_gouge(segs, pmin, pmax, td, tol)
    checks[VerificationCheckType.PART_GOUGE.value] = r_part_gouge

    # Phase D: GOUGE_EXACT — always NOT_VERIFIABLE (mesh engine not available, KL-07)
    r_gouge_exact = check_part_gouge_exact(segs, pmin, pmax, td, tol)
    checks[VerificationCheckType.GOUGE_EXACT.value] = r_gouge_exact

    r_stock_gouge = check_stock_gouge(segs, stock, td, tol)
    checks[VerificationCheckType.STOCK_GOUGE.value] = r_stock_gouge

    # Phase I: explicit TOOL_FIXTURE_COLLISION
    r_tool_fix = check_tool_fixture_collision(segs, fixtures, td, tol)
    checks[VerificationCheckType.TOOL_FIXTURE_COLLISION.value] = r_tool_fix
    # Backward-compat TOOL_COLLISION alias
    checks[VerificationCheckType.TOOL_COLLISION.value] = r_tool_fix

    # Phase G: separate holder collision sub-checks
    r_holder_part = check_holder_part_collision(segs, pmin, pmax, tl, hd, hl, tol)
    checks[VerificationCheckType.HOLDER_PART_COLLISION.value] = r_holder_part

    r_holder_stock = check_holder_stock_collision(segs, stock, tl, hd, hl, tol)
    checks[VerificationCheckType.HOLDER_STOCK_COLLISION.value] = r_holder_stock

    r_holder_fix = check_holder_fixture_collision(segs, fixtures, tl, hd, hl, tol)
    checks[VerificationCheckType.HOLDER_FIXTURE_COLLISION.value] = r_holder_fix
    # Backward-compat HOLDER_COLLISION alias
    checks[VerificationCheckType.HOLDER_COLLISION.value] = r_holder_fix

    # Phase I: explicit FIXTURE_COLLISION (combined sub-check)
    r_fix_col = check_fixture_collision(segs, fixtures, td, hd, tl, hl, tol)
    checks[VerificationCheckType.FIXTURE_COLLISION.value] = r_fix_col

    # Phase I: PART_FIXTURE_INTERFERENCE (static setup check)
    r_part_fix = check_part_fixture_interference(pmin, pmax, fixtures, tol)
    checks[VerificationCheckType.PART_FIXTURE_INTERFERENCE.value] = r_part_fix

    r_rapid = check_rapid_clearance(segs, fixtures, td, tol)
    checks[VerificationCheckType.RAPID_CLEARANCE.value] = r_rapid

    # Phase J/K: machine envelope with WCS transform
    r_env = check_machine_envelope_with_wcs(
        segs, tx, ty, tz,
        wcs_offset_x_mm=request.wcs_offset_x_mm,
        wcs_offset_y_mm=request.wcs_offset_y_mm,
        wcs_offset_z_mm=request.wcs_offset_z_mm,
        part_bbox_min=pmin,
        part_bbox_max=pmax,
        stock_bbox_min=(
            (stock.min_x_mm, stock.min_y_mm, stock.min_z_mm)
            if stock and stock.has_box_dims else None
        ),
        stock_bbox_max=(
            (stock.max_x_mm, stock.max_y_mm, stock.max_z_mm)
            if stock and stock.has_box_dims else None
        ),
        machine_id=request.machine_id,
        machine_limit_source=(
            request.machine_envelope.machine_limit_source
            if request.machine_envelope else "CATALOG"
        ),
        tol=tol,
    )
    checks[VerificationCheckType.MACHINE_ENVELOPE.value] = r_env

    r_overtravel = check_overtravel(segs, tx, ty, tz, tol)
    checks[VerificationCheckType.OVERTRAVEL.value] = r_overtravel

    # Phase L: AXIS_LIMIT uses explicit per-axis dict (derived from travel or user-provided)
    r_axis = check_axis_limit(segs, axis_limits, tol)
    checks[VerificationCheckType.AXIS_LIMIT.value] = r_axis

    # Holder clearance: use max_tool_reach from holder geometry if available
    holder_clearance = hg.max_tool_reach_mm if hg else None
    r_reach = check_tool_reach(segs, fl, holder_clearance, tol)
    checks[VerificationCheckType.TOOL_REACH.value] = r_reach

    r_kinematic = check_kinematic(segs, None, tol)
    checks[VerificationCheckType.KINEMATIC_CHECK.value] = r_kinematic

    r_stock_rem, remaining_vol, removed_vol = check_stock_remaining(segs, stock, td, tol)
    checks[VerificationCheckType.STOCK_REMAINING.value] = r_stock_rem

    all_issues: list[VerificationIssue] = []
    for r in checks.values():
        all_issues.extend(r.issues)

    mandatory = get_mandatory_checks(request.profile)
    state = derive_verification_state(checks, mandatory)

    initial_vol = stock.volume_mm3() if stock else None

    stock_fidelity = (
        StockRemovalFidelity.VOXEL_APPROXIMATE
        if remaining_vol is not None
        else StockRemovalFidelity.UNKNOWN
    )

    resource_hit = getattr(r_stock_rem, "resource_limit_hit", False)

    # Phase L: extract structured axis limit violations
    axis_violations: list[AxisLimitViolation] = []
    for issue in r_axis.issues:
        ev = issue.evidence
        if "AXIS" in ev:
            axis_violations.append(AxisLimitViolation(
                axis=ev.get("AXIS", ""),
                command_position=ev.get("COMMAND_POSITION", 0.0),
                limit_min=ev.get("LIMIT_MIN", 0.0),
                limit_max=ev.get("LIMIT_MAX", 0.0),
                excess_mm=ev.get("EXCESS_MM", 0.0),
                operation_id=ev.get("OPERATION_ID"),
                toolpath_segment=ev.get("TOOLPATH_SEGMENT"),
            ))

    summary = _build_summary(checks, all_issues, state, request.profile)
    viz = _build_visualization(request, checks)

    for r in checks.values():
        for issue in r.issues:
            if not issue.toolpath_id:
                issue.toolpath_id = request.toolpath_id

    sim_status = (
        SimulationStatus.PARTIAL
        if resource_hit
        else SimulationStatus.COMPLETED
    )

    # Phase J: resolve machine envelope record for result
    machine_env_record = request.machine_envelope
    if machine_env_record is None and (tx or ty or tz):
        from .enums import MachineEnvelopeStatus
        env_status = (
            MachineEnvelopeStatus.PASS if r_env.status.value == "PASS"
            else MachineEnvelopeStatus.FAIL if r_env.status.value == "FAIL"
            else MachineEnvelopeStatus.NOT_VERIFIABLE
        )
        machine_env_record = MachineEnvelopeRecord(
            machine_id=request.machine_id,
            x_travel_mm=tx,
            y_travel_mm=ty,
            z_travel_mm=tz,
            machine_envelope_status=env_status,
        )

    # Phase K: build WCS envelope record
    wcs_env = request.wcs_envelope
    if wcs_env is None:
        tpe = viz.toolpath_extents
        wcs_env = WCSEnvelopeRecord(
            wcs_offset_x_mm=request.wcs_offset_x_mm,
            wcs_offset_y_mm=request.wcs_offset_y_mm,
            wcs_offset_z_mm=request.wcs_offset_z_mm,
            part_extents_mm=(
                {
                    "min_x": pmin[0], "min_y": pmin[1], "min_z": pmin[2],
                    "max_x": pmax[0], "max_y": pmax[1], "max_z": pmax[2],
                } if pmin and pmax else None
            ),
            stock_extents_mm=viz.stock_bbox,
            toolpath_extents_mm=tpe,
        )

    return SimulationResult(
        session_id=str(uuid.uuid4()),
        toolpath_id=request.toolpath_id,
        simulation_status=sim_status,
        verification_state=state,
        profile=request.profile,
        checks=checks,
        issues=all_issues,
        summary=summary,
        initial_stock_volume_mm3=initial_vol,
        remaining_stock_volume_mm3=remaining_vol,
        removed_volume_mm3=removed_vol,
        stock_removal_fidelity=stock_fidelity,
        visualization=viz,
        resource_limit_hit=resource_hit,
        wcs_envelope=wcs_env,
        machine_envelope=machine_env_record,
        axis_limit_violations=axis_violations,
    )
