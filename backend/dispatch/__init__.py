"""
Level-14 Shop Floor Integration and Safe Dispatch Foundation.

NO_REAL_MACHINE_WRITE=YES
NO_AUTO_DISPATCH=YES
NO_FABRICATED_SHOPFLOOR_DATA=YES
READ_ONLY_CONNECTORS=YES
DRY_RUN_ONLY=YES
APPROVAL_REQUIRED=YES
UNKNOWN_IS_NOT_READY=YES
"""

from .audit import (
    audit_approval_granted,
    audit_approval_rejected,
    audit_approval_requested,
    audit_dry_run_failed,
    audit_dry_run_passed,
    audit_dry_run_started,
    audit_machine_state_read,
    audit_package_created,
    audit_package_stale,
    create_audit_event,
)
from .connector import ReadOnlyConnector
from .dry_run import (
    check_shop_floor_readiness,
    run_dry_run,
    run_simulated_transfer,
)
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
    SimulatedMachineState,
)
from .integrity import check_package_staleness, compute_package_hash
from .models import (
    ConnectorCapabilities,
    DispatchApproval,
    DispatchAuditEvent,
    DispatchPackage,
    DispatchPolicy,
    DryRunDispatchResult,
    MachineStateHistory,
    MachineStateSnapshot,
    PackageIntegrityResult,
    ShopFloorReadiness,
)
from .readiness import check_dispatch_readiness
from .simulated import SimulatedCNCController

# Safety invariants
APPROVAL_REQUIRED: bool = True
IS_DISPATCH_ORDER: bool = False
NO_REAL_MACHINE_WRITE: bool = True
DRY_RUN_ONLY: bool = True

__all__ = [
    # enums
    "AlarmState",
    "ApprovalStatus",
    "ConnectionStatus",
    "ConnectorType",
    "CycleState",
    "DispatchAuditEventType",
    "DispatchErrorCode",
    "DispatchPackageStatus",
    "DryRunStatus",
    "MachineMode",
    "PackageIntegrityStatus",
    "ShopFloorReadinessStatus",
    "SimulatedMachineState",
    # models
    "ConnectorCapabilities",
    "DispatchApproval",
    "DispatchAuditEvent",
    "DispatchPackage",
    "DispatchPolicy",
    "DryRunDispatchResult",
    "MachineStateHistory",
    "MachineStateSnapshot",
    "PackageIntegrityResult",
    "ShopFloorReadiness",
    # connector
    "ReadOnlyConnector",
    "SimulatedCNCController",
    # functions
    "check_dispatch_readiness",
    "check_package_staleness",
    "check_shop_floor_readiness",
    "compute_package_hash",
    "run_dry_run",
    "run_simulated_transfer",
    # audit
    "audit_approval_granted",
    "audit_approval_rejected",
    "audit_approval_requested",
    "audit_dry_run_failed",
    "audit_dry_run_passed",
    "audit_dry_run_started",
    "audit_machine_state_read",
    "audit_package_created",
    "audit_package_stale",
    "create_audit_event",
    # invariants
    "APPROVAL_REQUIRED",
    "DRY_RUN_ONLY",
    "IS_DISPATCH_ORDER",
    "NO_REAL_MACHINE_WRITE",
]
