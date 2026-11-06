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
    check_holder_collision,
    check_kinematic,
    check_machine_envelope,
    check_overtravel,
    check_part_gouge,
    check_rapid_clearance,
    check_stock_gouge,
    check_stock_remaining,
    check_tool_collision,
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
    SimulationRequest,
    SimulationResult,
    VerificationIssue,
    VerificationResult,
    VerificationSummary,
    VisualizationData,
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
    all_non_pass = all(
        r.status in (VerificationStatus.NOT_PERFORMED, VerificationStatus.INSUFFICIENT_DATA)
        for r in checks.values()
    )

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
    return VerificationSummary(
        verification_state=state,
        profile=profile,
        checks_performed=sum(
            1 for r in all_results if r.status not in (VerificationStatus.NOT_PERFORMED,)
        ),
        checks_passed=sum(1 for r in all_results if r.status == VerificationStatus.PASS),
        checks_failed=sum(1 for r in all_results if r.status == VerificationStatus.FAIL),
        checks_not_performed=sum(
            1 for r in all_results if r.status == VerificationStatus.NOT_PERFORMED
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


def _build_visualization(request: SimulationRequest) -> VisualizationData:
    viz = VisualizationData()
    for seg in request.segments:
        pt = [seg.start_x, seg.start_y, seg.start_z]
        if seg.is_cutting:
            viz.cutting_points.append(pt)
        else:
            viz.rapid_points.append(pt)

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
    hd = request.holder_diameter_mm
    hl = request.holder_length_mm
    tx = request.machine_travel_x_mm
    ty = request.machine_travel_y_mm
    tz = request.machine_travel_z_mm
    pmin = request.part_bbox_min
    pmax = request.part_bbox_max

    checks: dict[str, VerificationResult] = {}

    r_part_gouge = check_part_gouge(segs, pmin, pmax, td, tol)
    checks[VerificationCheckType.PART_GOUGE.value] = r_part_gouge

    r_stock_gouge = check_stock_gouge(segs, stock, td, tol)
    checks[VerificationCheckType.STOCK_GOUGE.value] = r_stock_gouge

    r_tool_col = check_tool_collision(segs, fixtures, td, tol)
    checks[VerificationCheckType.TOOL_COLLISION.value] = r_tool_col

    r_holder_col = check_holder_collision(segs, fixtures, tl, hd, hl, tol)
    checks[VerificationCheckType.HOLDER_COLLISION.value] = r_holder_col

    r_fix_col = check_fixture_collision(segs, fixtures, td, hd, tl, hl, tol)
    checks[VerificationCheckType.FIXTURE_COLLISION.value] = r_fix_col

    r_rapid = check_rapid_clearance(segs, fixtures, td, tol)
    checks[VerificationCheckType.RAPID_CLEARANCE.value] = r_rapid

    r_env = check_machine_envelope(segs, tx, ty, tz, tol)
    checks[VerificationCheckType.MACHINE_ENVELOPE.value] = r_env

    r_overtravel = check_overtravel(segs, tx, ty, tz, tol)
    checks[VerificationCheckType.OVERTRAVEL.value] = r_overtravel

    r_axis = check_axis_limit(segs, None, tol)
    checks[VerificationCheckType.AXIS_LIMIT.value] = r_axis

    r_reach = check_tool_reach(segs, fl, None, tol)
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

    summary = _build_summary(checks, all_issues, state, request.profile)
    viz = _build_visualization(request)

    for r in checks.values():
        for issue in r.issues:
            if not issue.toolpath_id:
                issue.toolpath_id = request.toolpath_id

    sim_status = (
        SimulationStatus.PARTIAL
        if resource_hit
        else SimulationStatus.COMPLETED
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
    )
