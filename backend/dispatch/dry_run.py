"""
Level-14 Dry-Run Dispatch.

Validates package completeness and machine-state compatibility.
NO real transfer occurs.
NO real machine is contacted for writes.
is_real_transfer is ALWAYS False.
is_dispatch_order is ALWAYS False.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .enums import (
    AlarmState,
    ApprovalStatus,
    DispatchErrorCode,
    DryRunStatus,
    PackageIntegrityStatus,
    SimulatedMachineState,
)
from .integrity import check_package_staleness
from .models import (
    DispatchApproval,
    DispatchPackage,
    DispatchPolicy,
    DryRunDispatchResult,
    MachineStateSnapshot,
    ShopFloorReadiness,
)
from .readiness import check_dispatch_readiness
from .simulated import SimulatedCNCController


def _now() -> str:
    return datetime.now(UTC).isoformat()


def run_dry_run(
    package: DispatchPackage,
    machine_state: MachineStateSnapshot | None = None,
    approval: DispatchApproval | None = None,
    policy: DispatchPolicy | None = None,
    current_nc_hash: str | None = None,
    current_assignment_ref: str | None = None,
) -> DryRunDispatchResult:
    """
    Execute a dry-run dispatch validation.

    Checks:
    - Package completeness
    - Machine target identity
    - NC hash integrity
    - Assignment consistency
    - Schedule / verification references
    - Tool and fixture presence
    - Approval validity
    - Machine-state snapshot

    Returns DryRunDispatchResult with is_real_transfer=False always.
    """
    result_id = str(uuid.uuid4())
    checks_passed: list[str] = []
    failures: list[DispatchErrorCode] = []
    warnings: list[str] = []

    # Integrity check
    integrity = check_package_staleness(
        package,
        current_nc_hash=current_nc_hash,
        current_assignment_ref=current_assignment_ref,
    )
    if integrity.status == PackageIntegrityStatus.STALE:
        failures.append(DispatchErrorCode.PACKAGE_STALE)
        for r in integrity.stale_reasons:
            if "NC_HASH" in r:
                failures.append(DispatchErrorCode.NC_HASH_MISMATCH)
            if "ASSIGNMENT" in r:
                failures.append(DispatchErrorCode.ASSIGNMENT_MISMATCH)
    elif integrity.status == PackageIntegrityStatus.INCOMPLETE:
        failures.append(DispatchErrorCode.INVALID_NC)
    else:
        checks_passed.append("PACKAGE_INTEGRITY_INTACT")

    # Package identity
    if package.machine_ref:
        checks_passed.append("MACHINE_REF_PRESENT")
    else:
        failures.append(DispatchErrorCode.MACHINE_IDENTITY_MISMATCH)

    # Machine state check
    if machine_state is not None:
        if machine_state.machine_id != package.machine_ref:
            failures.append(DispatchErrorCode.MACHINE_IDENTITY_MISMATCH)
        else:
            checks_passed.append("MACHINE_IDENTITY_MATCH")

        alarm = machine_state.alarm_state
        avail = machine_state.availability
        if alarm == AlarmState.ALARM:
            failures.append(DispatchErrorCode.MACHINE_ALARM)
        elif alarm == AlarmState.UNKNOWN:
            warnings.append("ALARM_STATE_UNKNOWN")
        else:
            checks_passed.append("NO_ACTIVE_ALARM")

        if avail in ("OFFLINE", SimulatedMachineState.OFFLINE):
            failures.append(DispatchErrorCode.MACHINE_OFFLINE)
        elif avail in ("MAINTENANCE", SimulatedMachineState.MAINTENANCE):
            failures.append(DispatchErrorCode.MACHINE_OFFLINE)
        elif avail in ("BUSY", SimulatedMachineState.BUSY):
            failures.append(DispatchErrorCode.MACHINE_BUSY)
        elif avail == "UNKNOWN":
            warnings.append("MACHINE_AVAILABILITY_UNKNOWN")
        else:
            checks_passed.append("MACHINE_AVAILABLE")
    else:
        warnings.append("NO_MACHINE_STATE_SNAPSHOT")

    # NC candidate
    if package.nc_candidate_ref and package.nc_hash:
        checks_passed.append("NC_CANDIDATE_PRESENT")
    else:
        failures.append(DispatchErrorCode.INVALID_NC)

    # Toolpath verification
    if package.verification_ref:
        checks_passed.append("VERIFICATION_REF_PRESENT")
    else:
        failures.append(DispatchErrorCode.UNVERIFIED_TOOLPATH)

    # Tool list
    if package.tool_list:
        checks_passed.append("TOOL_LIST_PRESENT")
    else:
        failures.append(DispatchErrorCode.TOOL_NOT_READY)

    # Fixture
    if package.fixture_ref:
        checks_passed.append("FIXTURE_REF_PRESENT")
    else:
        failures.append(DispatchErrorCode.FIXTURE_NOT_READY)

    # Approval
    if approval is None:
        failures.append(DispatchErrorCode.APPROVAL_MISSING)
    elif approval.status == ApprovalStatus.APPROVED_FOR_DRY_RUN:
        if approval.package_ref != package.package_id:
            failures.append(DispatchErrorCode.APPROVAL_MISSING)
        else:
            checks_passed.append("APPROVAL_VALID")
    elif approval.status == ApprovalStatus.EXPIRED:
        failures.append(DispatchErrorCode.APPROVAL_EXPIRED)
    else:
        failures.append(DispatchErrorCode.APPROVAL_MISSING)

    # Deduplicate failures
    seen: set[DispatchErrorCode] = set()
    unique_failures: list[DispatchErrorCode] = []
    for f in failures:
        if f not in seen:
            seen.add(f)
            unique_failures.append(f)

    status = DryRunStatus.PASSED if not unique_failures else DryRunStatus.FAILED

    return DryRunDispatchResult(
        result_id=result_id,
        package_ref=package.package_id,
        machine_ref=package.machine_ref,
        status=status,
        is_real_transfer=False,
        is_dispatch_order=False,
        checks_passed=checks_passed,
        failures=unique_failures,
        warnings=warnings,
        timestamp=_now(),
    )


def run_simulated_transfer(
    package: DispatchPackage,
    controller: SimulatedCNCController,
    approval: DispatchApproval | None = None,
) -> DryRunDispatchResult:
    """
    Simulated transfer to a SimulatedCNCController only.
    Never opens a real network connection.
    Never contacts a real CNC.
    """
    # Use the controller's own machine_id so identity mismatch is detected
    machine_state = controller.get_machine_state(controller.managed_machine_id)
    return run_dry_run(
        package=package,
        machine_state=machine_state,
        approval=approval,
    )


def check_shop_floor_readiness(
    package: DispatchPackage,
    machine_state: MachineStateSnapshot | None = None,
    approval: DispatchApproval | None = None,
    policy: DispatchPolicy | None = None,
    current_nc_hash: str | None = None,
    current_assignment_ref: str | None = None,
) -> ShopFloorReadiness:
    """Convenience wrapper around check_dispatch_readiness."""
    return check_dispatch_readiness(
        package=package,
        policy=policy,
        machine_state=machine_state,
        approval=approval,
        current_nc_hash=current_nc_hash,
        current_assignment_ref=current_assignment_ref,
    )
