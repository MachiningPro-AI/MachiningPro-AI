"""
Level-14 Shop Floor Integration and Safe Dispatch Foundation — data models.

NO_REAL_MACHINE_WRITE=YES
NO_AUTO_DISPATCH=YES
APPROVAL_REQUIRED=YES
READ_ONLY_CONNECTORS=YES
DRY_RUN_ONLY=YES
UNKNOWN_IS_NOT_READY=YES
NO_FABRICATED_SHOPFLOOR_DATA=YES
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import (
    AlarmState,
    ApprovalStatus,
    ConnectionStatus,
    ConnectorType,
    CycleState,
    DispatchAuditEventType,
    DispatchErrorCode,
    DispatchPackageStatus,
    DryRunStatus,
    MachineMode,
    PackageIntegrityStatus,
    ShopFloorReadinessStatus,
)


class ConnectorCapabilities(BaseModel):
    """Declares what a connector can and cannot do. Writes are always False."""

    READ_MACHINE_STATE: bool = False
    READ_ALARMS: bool = False
    READ_PROGRAM_METADATA: bool = False
    READ_TOOL_STATE: bool = False
    READ_QUEUE_STATE: bool = False
    READ_WORK_OFFSETS: bool = False
    # Writes permanently locked to False
    WRITE_PROGRAM: bool = False
    START_MACHINE: bool = False
    STOP_MACHINE: bool = False
    WRITE_OFFSETS: bool = False
    WRITE_TOOL_DATA: bool = False


class MachineStateSnapshot(BaseModel):
    """
    Read-only snapshot of machine state.
    Missing fields remain UNKNOWN.
    is_fabricated is always False in production.
    """

    machine_id: str
    timestamp: str
    connection_status: ConnectionStatus = ConnectionStatus.UNKNOWN
    availability: str = "UNKNOWN"
    mode: MachineMode = MachineMode.UNKNOWN
    current_program: str | None = None
    current_job: str | None = None
    alarm_state: AlarmState = AlarmState.UNKNOWN
    cycle_state: CycleState = CycleState.UNKNOWN
    spindle_state: str = "UNKNOWN"
    feed_state: str = "UNKNOWN"
    tool_in_spindle: str | None = None
    active_work_offset: str | None = None
    queue_state: str = "UNKNOWN"
    maintenance_state: str = "UNKNOWN"
    source: str = "UNKNOWN"
    quality: str = "UNKNOWN"
    warnings: list[str] = Field(default_factory=list)
    connector_type: ConnectorType = ConnectorType.UNKNOWN
    # Safety invariants
    is_fabricated: bool = False
    is_real_machine_write: bool = False


class MachineStateHistory(BaseModel):
    """Foundation for machine state history — no real-time guarantee."""

    machine_id: str
    snapshots: list[MachineStateSnapshot] = Field(default_factory=list)
    max_snapshots: int = 100


class DispatchPackage(BaseModel):
    """
    Collects all references needed for a dry-run dispatch check.
    is_dispatch_order is ALWAYS False — this is never an execution order.
    approval_required is ALWAYS True.
    """

    package_id: str
    job_ref: str
    assignment_ref: str
    machine_ref: str
    nc_candidate_ref: str | None = None
    nc_hash: str | None = None
    post_profile_ref: str | None = None
    tool_list: list[str] = Field(default_factory=list)
    holder_list: list[str] = Field(default_factory=list)
    fixture_ref: str | None = None
    setup_ref: str | None = None
    work_offset_ref: str | None = None
    verification_ref: str | None = None
    approval_ref: str | None = None
    schedule_ref: str | None = None
    created_at: str
    status: DispatchPackageStatus = DispatchPackageStatus.DRAFT
    warnings: list[str] = Field(default_factory=list)
    # Invariants
    is_dispatch_order: bool = False
    approval_required: bool = True


class DispatchApproval(BaseModel):
    """
    Human approval record for dry-run only.
    is_automatic is always False — no AI self-approval.
    """

    approval_id: str
    package_ref: str
    approved_by: str
    approved_at: str | None = None
    scope: str = "DRY_RUN_ONLY"
    status: ApprovalStatus = ApprovalStatus.PENDING
    comments: str = ""
    expires_at: str | None = None
    # Invariants
    is_automatic: bool = False
    is_execution_approval: bool = False


class DryRunDispatchResult(BaseModel):
    """
    Result of a simulated dry-run. No real transfer occurs.
    is_real_transfer is always False.
    is_dispatch_order is always False.
    """

    result_id: str
    package_ref: str
    machine_ref: str
    status: DryRunStatus
    is_real_transfer: bool = False
    is_dispatch_order: bool = False
    checks_passed: list[str] = Field(default_factory=list)
    failures: list[DispatchErrorCode] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    timestamp: str


class ShopFloorReadiness(BaseModel):
    """
    Gate result for dispatch readiness.
    READY_TO_RUN_MACHINE is never a valid status.
    """

    status: ShopFloorReadinessStatus
    block_reasons: list[DispatchErrorCode] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    approval_required: bool = True
    is_dispatch_order: bool = False
    machine_state_ref: str | None = None


class DispatchPolicy(BaseModel):
    """
    Explicit dispatch policy. Defaults fail closed.
    require_human_approval is always True.
    """

    require_verified_toolpath: bool = True
    require_valid_nc: bool = True
    require_machine_idle: bool = True
    require_no_alarm: bool = True
    require_tools_ready: bool = True
    require_fixture_ready: bool = True
    require_human_approval: bool = True
    allow_unknown_machine_state: bool = False


class DispatchAuditEvent(BaseModel):
    """Immutable-style audit record for dispatch lifecycle events."""

    event_id: str
    event_type: DispatchAuditEventType
    timestamp: str
    actor: str
    job_ref: str | None = None
    machine_ref: str | None = None
    package_ref: str | None = None
    result: str = "UNKNOWN"
    reason: str = ""
    reference_hash: str | None = None


class PackageIntegrityResult(BaseModel):
    """Result of package integrity / staleness check."""

    status: PackageIntegrityStatus
    stale_reasons: list[str] = Field(default_factory=list)
    expected_nc_hash: str | None = None
    actual_nc_hash: str | None = None
    expected_assignment_ref: str | None = None
    actual_assignment_ref: str | None = None
