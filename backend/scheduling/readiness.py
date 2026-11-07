"""
Level-13 Machine Scheduling — readiness checks.

NCReadiness, SetupReadiness, ProductionReadiness.

NO_CNC_DISPATCH=YES
APPROVAL_REQUIRED=YES
READY_FOR_DISPATCH is NOT a valid status at Level 13.
"""

from __future__ import annotations

from .enums import (
    FixtureAvailabilityStatus,
    HolderAvailabilityStatus,
    NCReadinessStatus,
    ProductionReadinessStatus,
    SchedulingBlockReason,
    SetupReadinessStatus,
    ToolAvailabilityStatus,
)
from .models import (
    FixtureAvailability,
    HolderAvailability,
    NCReadiness,
    ProductionJob,
    ProductionReadiness,
    SetupReadiness,
    ToolAvailability,
)

_NC_CANDIDATE_ACTIVE_STATUSES = {"CANDIDATE", "VALIDATED_OFFLINE"}
_TOOL_AVAILABLE_STATUSES = {
    ToolAvailabilityStatus.AVAILABLE,
    ToolAvailabilityStatus.LOADED_ON_MACHINE,
    ToolAvailabilityStatus.IN_TOOL_CRIB,
}
_HOLDER_AVAILABLE_STATUSES = {HolderAvailabilityStatus.AVAILABLE}
_FIXTURE_AVAILABLE_STATUSES = {
    FixtureAvailabilityStatus.AVAILABLE,
    FixtureAvailabilityStatus.INSTALLED,
}


def check_nc_readiness(job: ProductionJob) -> NCReadiness:
    """
    Evaluate NC candidate readiness for a job.

    Requirements for READY:
    - toolpath is verified
    - NC candidate exists and is CANDIDATE or VALIDATED_OFFLINE
    - NC candidate is not stale

    Does not authorize machine transfer.
    """
    block_reasons: list[SchedulingBlockReason] = []
    warnings: list[str] = []

    # --- toolpath verification ---
    if not job.toolpath_verified:
        block_reasons.append(SchedulingBlockReason.TOOLPATH_UNVERIFIED)

    # --- NC candidate ---
    if not job.nc_candidate_ref:
        block_reasons.append(SchedulingBlockReason.NC_CANDIDATE_MISSING)
        return NCReadiness(
            status=NCReadinessStatus.NOT_GENERATED,
            nc_candidate_ref=None,
            nc_candidate_status=None,
            toolpath_verified=job.toolpath_verified,
            is_stale=False,
            block_reasons=block_reasons,
            warnings=warnings,
        )

    nc_status = job.nc_candidate_status or ""

    # --- stale check ---
    if job.nc_candidate_stale:
        block_reasons.append(SchedulingBlockReason.NC_CANDIDATE_STALE)
        return NCReadiness(
            status=NCReadinessStatus.STALE,
            nc_candidate_ref=job.nc_candidate_ref,
            nc_candidate_status=nc_status,
            toolpath_verified=job.toolpath_verified,
            is_stale=True,
            block_reasons=block_reasons,
            warnings=["NC candidate is stale — regeneration required"],
        )

    # --- status check ---
    if nc_status not in _NC_CANDIDATE_ACTIVE_STATUSES:
        block_reasons.append(SchedulingBlockReason.NC_CANDIDATE_BLOCKED)
        return NCReadiness(
            status=NCReadinessStatus.BLOCKED,
            nc_candidate_ref=job.nc_candidate_ref,
            nc_candidate_status=nc_status,
            toolpath_verified=job.toolpath_verified,
            is_stale=False,
            block_reasons=block_reasons,
            warnings=[f"NC candidate status {nc_status!r} does not qualify for scheduling"],
        )

    if block_reasons:
        # NC candidate itself is ok but toolpath unverified
        warnings.append("NC candidate present but toolpath verification incomplete")
        return NCReadiness(
            status=NCReadinessStatus.BLOCKED,
            nc_candidate_ref=job.nc_candidate_ref,
            nc_candidate_status=nc_status,
            toolpath_verified=job.toolpath_verified,
            is_stale=False,
            block_reasons=block_reasons,
            warnings=warnings,
        )

    return NCReadiness(
        status=NCReadinessStatus.READY,
        nc_candidate_ref=job.nc_candidate_ref,
        nc_candidate_status=nc_status,
        toolpath_verified=job.toolpath_verified,
        is_stale=False,
        block_reasons=[],
        warnings=[],
    )


def check_setup_readiness(
    job: ProductionJob,
    tool_availability: dict[str, ToolAvailability | ToolAvailabilityStatus] | None = None,
    holder_availability: dict[str, HolderAvailability | HolderAvailabilityStatus] | None = None,
    fixture_availability: FixtureAvailability | FixtureAvailabilityStatus | None = None,
) -> SetupReadiness:
    """
    Check tool, holder and fixture availability for a job.

    Missing resources block scheduling.
    UNKNOWN availability is not treated as AVAILABLE.
    """
    block_reasons: list[SchedulingBlockReason] = []
    warnings: list[str] = []
    tool_statuses: dict[str, ToolAvailabilityStatus] = {}
    holder_statuses: dict[str, HolderAvailabilityStatus] = {}
    missing_tools: list[str] = []
    missing_holders: list[str] = []
    fixture_blocked = False

    # --- tools ---
    for tool_id in job.required_tools:
        avail = (tool_availability or {}).get(tool_id)
        if avail is None:
            status = ToolAvailabilityStatus.UNKNOWN
            warnings.append(f"Tool {tool_id!r} availability unknown")
        elif isinstance(avail, ToolAvailabilityStatus):
            status = avail
        else:
            status = avail.status
        tool_statuses[tool_id] = status
        if status == ToolAvailabilityStatus.MISSING:
            missing_tools.append(tool_id)
            block_reasons.append(SchedulingBlockReason.TOOL_MISSING)

    # --- holders ---
    for holder_id in job.required_holders:
        avail = (holder_availability or {}).get(holder_id)
        if avail is None:
            status = HolderAvailabilityStatus.UNKNOWN
            warnings.append(f"Holder {holder_id!r} availability unknown")
        elif isinstance(avail, HolderAvailabilityStatus):
            status = avail
        else:
            status = avail.status
        holder_statuses[holder_id] = status
        if status == HolderAvailabilityStatus.MISSING:
            missing_holders.append(holder_id)
            block_reasons.append(SchedulingBlockReason.HOLDER_MISSING)

    # --- fixture ---
    fixture_status_val = FixtureAvailabilityStatus.UNKNOWN
    if job.required_fixture:
        if fixture_availability is None:
            fixture_status_val = FixtureAvailabilityStatus.UNKNOWN
            warnings.append(f"Fixture {job.required_fixture!r} availability unknown")
        elif isinstance(fixture_availability, FixtureAvailabilityStatus):
            fixture_status_val = fixture_availability
            if fixture_availability == FixtureAvailabilityStatus.MISSING:
                fixture_blocked = True
                block_reasons.append(SchedulingBlockReason.FIXTURE_MISSING)
        else:
            fixture_status_val = fixture_availability.status
            if fixture_availability.status == FixtureAvailabilityStatus.MISSING:
                fixture_blocked = True
                block_reasons.append(SchedulingBlockReason.FIXTURE_MISSING)

    # --- determine overall status ---
    unique_blocks = list(dict.fromkeys(block_reasons))
    if missing_tools or missing_holders or fixture_blocked:
        status = SetupReadinessStatus.BLOCKED
    elif (
        any(s == ToolAvailabilityStatus.UNKNOWN for s in tool_statuses.values())
        or any(s == HolderAvailabilityStatus.UNKNOWN for s in holder_statuses.values())
        or (job.required_fixture and fixture_status_val == FixtureAvailabilityStatus.UNKNOWN)
    ):
        status = SetupReadinessStatus.UNKNOWN
    elif tool_statuses or holder_statuses or job.required_fixture:
        # All explicitly available
        status = SetupReadinessStatus.READY
    else:
        # No resources required
        status = SetupReadinessStatus.READY

    return SetupReadiness(
        status=status,
        tool_statuses=tool_statuses,
        holder_statuses=holder_statuses,
        fixture_status=fixture_status_val,
        missing_tools=missing_tools,
        missing_holders=missing_holders,
        fixture_blocked=fixture_blocked,
        block_reasons=unique_blocks,
        warnings=warnings,
    )


def check_production_readiness(
    job: ProductionJob,
    machine_eligible: bool = False,
    schedule_slot_available: bool = False,
    nc_readiness: NCReadiness | None = None,
    setup_readiness: SetupReadiness | None = None,
) -> ProductionReadiness:
    """
    Compute overall ProductionReadiness for a job.

    READY_FOR_DISPATCH is NOT returned at Level 13.
    APPROVAL_REQUIRED is always True.
    """
    nc_r = nc_readiness or check_nc_readiness(job)
    setup_r = setup_readiness or check_setup_readiness(job)

    block_reasons: list[SchedulingBlockReason] = []
    warnings: list[str] = []

    engineering_complete = bool(job.process_plan_ref or job.cam_plan_ref)
    cam_ready = bool(job.cam_plan_ref)

    if not engineering_complete:
        block_reasons.append(SchedulingBlockReason.ENGINEERING_INCOMPLETE)

    block_reasons.extend(nc_r.block_reasons)
    block_reasons.extend(setup_r.block_reasons)

    if not machine_eligible:
        block_reasons.append(SchedulingBlockReason.MACHINE_INELIGIBLE)

    unique_blocks = list(dict.fromkeys(block_reasons))

    # --- determine status ---
    if unique_blocks:
        status = ProductionReadinessStatus.DISPATCH_BLOCKED
    elif not schedule_slot_available:
        status = ProductionReadinessStatus.REVIEW_REQUIRED
        warnings.append("No confirmed schedule slot — review required")
    elif (
        nc_r.status == NCReadinessStatus.READY
        and setup_r.status == SetupReadinessStatus.READY
        and machine_eligible
        and engineering_complete
    ):
        status = ProductionReadinessStatus.READY_FOR_SCHEDULING
    else:
        status = ProductionReadinessStatus.UNKNOWN

    return ProductionReadiness(
        status=status,
        engineering_complete=engineering_complete,
        cam_ready=cam_ready,
        toolpath_verified=job.toolpath_verified,
        nc_readiness=nc_r,
        machine_eligible=machine_eligible,
        setup_readiness=setup_r,
        schedule_slot_available=schedule_slot_available,
        block_reasons=unique_blocks,
        warnings=warnings,
        approval_required=True,
    )
