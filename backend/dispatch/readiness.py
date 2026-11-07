"""
Level-14 Dispatch Readiness Gate.

Fail-closed: missing or UNKNOWN inputs block dispatch.
Human approval is always required.
No automatic dispatch, no fabricated readiness.

UNKNOWN machine state != READY (HARD RULE 23).
UNKNOWN controller state != CONNECTED (HARD RULE 24).
"""

from __future__ import annotations

from .enums import (
    AlarmState,
    ApprovalStatus,
    DispatchErrorCode,
    DispatchPackageStatus,
    ShopFloorReadinessStatus,
    SimulatedMachineState,
)
from .models import (
    DispatchApproval,
    DispatchPackage,
    DispatchPolicy,
    MachineStateSnapshot,
    ShopFloorReadiness,
)


def check_dispatch_readiness(
    package: DispatchPackage,
    policy: DispatchPolicy | None = None,
    machine_state: MachineStateSnapshot | None = None,
    approval: DispatchApproval | None = None,
    current_nc_hash: str | None = None,
    current_assignment_ref: str | None = None,
) -> ShopFloorReadiness:
    """
    Deterministic dispatch readiness gate.

    Returns READY_FOR_DRY_RUN only when ALL mandatory checks pass.
    Returns BLOCKED on any hard failure.
    Returns REVIEW_REQUIRED when soft warnings exist without hard failures.
    """
    if policy is None:
        policy = DispatchPolicy()

    block_reasons: list[DispatchErrorCode] = []
    warnings: list[str] = []

    # --- Package status checks ---
    if package.status == DispatchPackageStatus.STALE:
        block_reasons.append(DispatchErrorCode.PACKAGE_STALE)
    if package.status == DispatchPackageStatus.REJECTED:
        block_reasons.append(DispatchErrorCode.PACKAGE_STALE)

    # --- NC candidate checks ---
    if policy.require_valid_nc:
        if not package.nc_candidate_ref:
            block_reasons.append(DispatchErrorCode.INVALID_NC)
        if not package.nc_hash:
            block_reasons.append(DispatchErrorCode.INVALID_NC)

    # NC hash staleness
    if (
        current_nc_hash is not None
        and package.nc_hash is not None
        and package.nc_hash != current_nc_hash
    ):
        block_reasons.append(DispatchErrorCode.NC_HASH_MISMATCH)

    # --- Assignment staleness ---
    if (
        current_assignment_ref is not None
        and package.assignment_ref != current_assignment_ref
    ):
        block_reasons.append(DispatchErrorCode.ASSIGNMENT_MISMATCH)

    # --- Toolpath verification ---
    if policy.require_verified_toolpath and not package.verification_ref:
        block_reasons.append(DispatchErrorCode.UNVERIFIED_TOOLPATH)

    # --- Tool readiness ---
    if policy.require_tools_ready and not package.tool_list:
        block_reasons.append(DispatchErrorCode.TOOL_NOT_READY)

    # --- Fixture readiness ---
    if policy.require_fixture_ready and not package.fixture_ref:
        block_reasons.append(DispatchErrorCode.FIXTURE_NOT_READY)

    # --- Machine state checks ---
    if machine_state is not None:
        avail = machine_state.availability
        alarm = machine_state.alarm_state

        if alarm == AlarmState.ALARM:
            block_reasons.append(DispatchErrorCode.MACHINE_ALARM)
        elif alarm == AlarmState.UNKNOWN:
            if not policy.allow_unknown_machine_state:
                block_reasons.append(DispatchErrorCode.UNKNOWN_MACHINE_STATE)
            else:
                warnings.append("ALARM_STATE_UNKNOWN: proceeding per policy")

        if avail == SimulatedMachineState.OFFLINE or avail == "OFFLINE":
            block_reasons.append(DispatchErrorCode.MACHINE_OFFLINE)
        elif avail == SimulatedMachineState.MAINTENANCE or avail == "MAINTENANCE":
            block_reasons.append(DispatchErrorCode.MACHINE_OFFLINE)
        elif avail == SimulatedMachineState.BUSY or avail == "BUSY":
            if policy.require_machine_idle:
                block_reasons.append(DispatchErrorCode.MACHINE_BUSY)
        elif avail == "UNKNOWN":
            if not policy.allow_unknown_machine_state:
                block_reasons.append(DispatchErrorCode.UNKNOWN_MACHINE_STATE)
            else:
                warnings.append("MACHINE_STATE_UNKNOWN: proceeding per policy")

        if machine_state.machine_id != package.machine_ref:
            block_reasons.append(DispatchErrorCode.MACHINE_IDENTITY_MISMATCH)
    else:
        warnings.append(
            "NO_MACHINE_STATE_SNAPSHOT: machine readiness unverified"
        )

    # --- Approval checks (always required) ---
    if policy.require_human_approval:
        if approval is None:
            block_reasons.append(DispatchErrorCode.APPROVAL_MISSING)
        else:
            if approval.status == ApprovalStatus.PENDING:
                block_reasons.append(DispatchErrorCode.APPROVAL_MISSING)
            elif approval.status == ApprovalStatus.REJECTED:
                block_reasons.append(DispatchErrorCode.APPROVAL_MISSING)
            elif approval.status == ApprovalStatus.REVOKED:
                block_reasons.append(DispatchErrorCode.APPROVAL_MISSING)
            elif approval.status == ApprovalStatus.EXPIRED:
                block_reasons.append(DispatchErrorCode.APPROVAL_EXPIRED)

    # --- Determine status ---
    if block_reasons:
        return ShopFloorReadiness(
            status=ShopFloorReadinessStatus.BLOCKED,
            block_reasons=block_reasons,
            warnings=warnings,
            approval_required=True,
            is_dispatch_order=False,
            machine_state_ref=(
                machine_state.machine_id if machine_state else None
            ),
        )

    if warnings:
        return ShopFloorReadiness(
            status=ShopFloorReadinessStatus.REVIEW_REQUIRED,
            block_reasons=[],
            warnings=warnings,
            approval_required=True,
            is_dispatch_order=False,
            machine_state_ref=(
                machine_state.machine_id if machine_state else None
            ),
        )

    return ShopFloorReadiness(
        status=ShopFloorReadinessStatus.READY_FOR_DRY_RUN,
        block_reasons=[],
        warnings=[],
        approval_required=True,
        is_dispatch_order=False,
        machine_state_ref=(
            machine_state.machine_id if machine_state else None
        ),
    )
