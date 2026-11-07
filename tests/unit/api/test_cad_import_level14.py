"""
Level-14 Shop Floor Integration and Safe Dispatch Foundation — unit tests.

NO_REAL_MACHINE_WRITE=YES
NO_AUTO_DISPATCH=YES
APPROVAL_REQUIRED=YES
READ_ONLY_CONNECTORS=YES
DRY_RUN_ONLY=YES
"""

from __future__ import annotations

from backend.dispatch import (
    APPROVAL_REQUIRED,
    DRY_RUN_ONLY,
    IS_DISPATCH_ORDER,
    NO_REAL_MACHINE_WRITE,
    AlarmState,
    ApprovalStatus,
    ConnectionStatus,
    DispatchApproval,
    DispatchAuditEvent,
    DispatchErrorCode,
    DispatchPackage,
    DispatchPackageStatus,
    DispatchPolicy,
    DryRunStatus,
    MachineStateHistory,
    MachineStateSnapshot,
    PackageIntegrityStatus,
    ShopFloorReadinessStatus,
    SimulatedCNCController,
    SimulatedMachineState,
    audit_approval_granted,
    audit_approval_rejected,
    audit_approval_requested,
    audit_dry_run_failed,
    audit_dry_run_passed,
    audit_dry_run_started,
    audit_machine_state_read,
    audit_package_created,
    audit_package_stale,
    check_dispatch_readiness,
    check_package_staleness,
    compute_package_hash,
    run_dry_run,
    run_simulated_transfer,
)
from backend.dispatch.enums import (
    ConnectorType,
    CycleState,
    DispatchAuditEventType,
    MachineMode,
)

# ===========================================================================
# Helpers
# ===========================================================================


def make_package(**kwargs) -> DispatchPackage:
    defaults = {
        "package_id": "PKG-001",
        "job_ref": "J-001",
        "assignment_ref": "ASN-001",
        "machine_ref": "M-001",
        "nc_candidate_ref": "NC-001",
        "nc_hash": "abc123",
        "post_profile_ref": "PP-001",
        "tool_list": ["T001", "T002"],
        "holder_list": ["H001"],
        "fixture_ref": "FIX-001",
        "setup_ref": "SETUP-001",
        "work_offset_ref": "WO-001",
        "verification_ref": "VER-001",
        "schedule_ref": "SCH-001",
        "created_at": "2026-11-07T00:00:00Z",
    }
    defaults.update(kwargs)
    return DispatchPackage(**defaults)


def make_approval(**kwargs) -> DispatchApproval:
    defaults = {
        "approval_id": "APR-001",
        "package_ref": "PKG-001",
        "approved_by": "operator",
        "approved_at": "2026-11-07T00:00:00Z",
        "scope": "DRY_RUN_ONLY",
        "status": ApprovalStatus.APPROVED_FOR_DRY_RUN,
    }
    defaults.update(kwargs)
    return DispatchApproval(**defaults)


def make_state(**kwargs) -> MachineStateSnapshot:
    defaults = {
        "machine_id": "M-001",
        "timestamp": "2026-11-07T00:00:00Z",
        "connection_status": ConnectionStatus.CONNECTED,
        "availability": SimulatedMachineState.IDLE,
        "alarm_state": AlarmState.NO_ALARM,
        "source": "SIMULATED_TEST",
        "quality": "TEST_ONLY",
    }
    defaults.update(kwargs)
    return MachineStateSnapshot(**defaults)


# ===========================================================================
# Safety invariant constants
# ===========================================================================


class TestSafetyInvariants:
    def test_approval_required_constant_true(self):
        assert APPROVAL_REQUIRED is True

    def test_is_dispatch_order_constant_false(self):
        assert IS_DISPATCH_ORDER is False

    def test_no_real_machine_write_constant_true(self):
        assert NO_REAL_MACHINE_WRITE is True

    def test_dry_run_only_constant_true(self):
        assert DRY_RUN_ONLY is True

    def test_dispatch_package_invariants(self):
        p = make_package()
        assert p.is_dispatch_order is False
        assert p.approval_required is True

    def test_dry_run_result_invariants(self):
        p = make_package()
        result = run_dry_run(p, approval=make_approval())
        assert result.is_real_transfer is False
        assert result.is_dispatch_order is False

    def test_machine_state_invariants(self):
        ctrl = SimulatedCNCController("M-001")
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.is_fabricated is False
        assert state.is_real_machine_write is False

    def test_approval_invariants(self):
        appr = make_approval()
        assert appr.is_automatic is False
        assert appr.is_execution_approval is False


# ===========================================================================
# MachineStateSnapshot model
# ===========================================================================


class TestMachineStateSnapshot:
    def test_missing_fields_are_unknown(self):
        state = MachineStateSnapshot(machine_id="M-001", timestamp="2026-11-07T00:00:00Z")
        assert state.connection_status == ConnectionStatus.UNKNOWN
        assert state.alarm_state == AlarmState.UNKNOWN
        assert state.mode == MachineMode.UNKNOWN

    def test_unknown_connection_not_connected(self):
        state = MachineStateSnapshot(machine_id="M-001", timestamp="2026-11-07T00:00:00Z")
        assert state.connection_status != ConnectionStatus.CONNECTED

    def test_connector_type_defaults_unknown(self):
        state = MachineStateSnapshot(machine_id="M-001", timestamp="2026-11-07T00:00:00Z")
        assert state.connector_type == ConnectorType.UNKNOWN

    def test_state_history_foundation(self):
        history = MachineStateHistory(machine_id="M-001")
        state = make_state()
        history.snapshots.append(state)
        assert len(history.snapshots) == 1
        assert history.machine_id == "M-001"


# ===========================================================================
# Read-only connector contract
# ===========================================================================


class TestReadOnlyConnector:
    def test_simulated_connector_type(self):
        ctrl = SimulatedCNCController("M-001")
        assert ctrl.connector_type == ConnectorType.SIMULATED

    def test_simulated_capabilities_no_write(self):
        ctrl = SimulatedCNCController("M-001")
        caps = ctrl.capabilities
        assert caps.WRITE_PROGRAM is False
        assert caps.START_MACHINE is False
        assert caps.STOP_MACHINE is False
        assert caps.WRITE_OFFSETS is False
        assert caps.WRITE_TOOL_DATA is False

    def test_simulated_capabilities_read_allowed(self):
        ctrl = SimulatedCNCController("M-001")
        caps = ctrl.capabilities
        assert caps.READ_MACHINE_STATE is True
        assert caps.READ_ALARMS is True
        assert caps.READ_PROGRAM_METADATA is True

    def test_connect_read_only_returns_connected(self):
        ctrl = SimulatedCNCController("M-001")
        status = ctrl.connect_read_only()
        assert status == ConnectionStatus.CONNECTED

    def test_disconnect_clears_connection(self):
        ctrl = SimulatedCNCController("M-001")
        ctrl.connect_read_only()
        ctrl.disconnect()
        state = ctrl.get_machine_state("M-001")
        assert state.connection_status == ConnectionStatus.UNKNOWN

    def test_simulated_certification(self):
        assert SimulatedCNCController.CERTIFICATION == "TEST_ONLY"


# ===========================================================================
# Simulated controller deterministic states
# ===========================================================================


class TestSimulatedController:
    def test_idle_state(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.IDLE)
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.alarm_state == AlarmState.NO_ALARM
        assert state.cycle_state == CycleState.IDLE

    def test_busy_state(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.BUSY)
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.cycle_state == CycleState.RUNNING

    def test_alarm_state(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.ALARM)
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.alarm_state == AlarmState.ALARM

    def test_offline_state(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.OFFLINE)
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.availability == SimulatedMachineState.OFFLINE

    def test_maintenance_state(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.MAINTENANCE)
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.availability == SimulatedMachineState.MAINTENANCE

    def test_set_state_helper(self):
        ctrl = SimulatedCNCController("M-001")
        ctrl.set_state(SimulatedMachineState.ALARM)
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-001")
        assert state.alarm_state == AlarmState.ALARM

    def test_wrong_machine_identity(self):
        ctrl = SimulatedCNCController("M-001")
        ctrl.connect_read_only()
        state = ctrl.get_machine_state("M-999")
        assert state.connection_status == ConnectionStatus.UNKNOWN
        assert len(state.warnings) > 0

    def test_get_alarm_state_mismatch(self):
        ctrl = SimulatedCNCController("M-001")
        result = ctrl.get_alarm_state("M-999")
        assert result == AlarmState.UNKNOWN

    def test_set_program(self):
        ctrl = SimulatedCNCController("M-001")
        ctrl.set_program("O0001")
        meta = ctrl.get_current_program_metadata("M-001")
        assert meta["program"] == "O0001"

    def test_queue_busy(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.BUSY)
        queue = ctrl.get_queue_state("M-001")
        assert queue["queue_depth"] == 1

    def test_queue_idle(self):
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.IDLE)
        queue = ctrl.get_queue_state("M-001")
        assert queue["queue_depth"] == 0


# ===========================================================================
# Package integrity and staleness
# ===========================================================================


class TestPackageIntegrity:
    def test_intact_when_no_changes(self):
        p = make_package()
        result = check_package_staleness(p, current_nc_hash="abc123")
        assert result.status == PackageIntegrityStatus.INTACT

    def test_stale_on_nc_hash_change(self):
        p = make_package(nc_hash="abc123")
        result = check_package_staleness(p, current_nc_hash="xyz999")
        assert result.status == PackageIntegrityStatus.STALE
        assert any("NC_HASH" in r for r in result.stale_reasons)

    def test_stale_on_assignment_change(self):
        p = make_package(assignment_ref="ASN-001")
        result = check_package_staleness(p, current_assignment_ref="ASN-002")
        assert result.status == PackageIntegrityStatus.STALE
        assert any("ASSIGNMENT" in r for r in result.stale_reasons)

    def test_stale_on_fixture_change(self):
        p = make_package(fixture_ref="FIX-001")
        result = check_package_staleness(p, current_fixture_ref="FIX-002")
        assert result.status == PackageIntegrityStatus.STALE

    def test_stale_on_tool_list_change(self):
        p = make_package(tool_list=["T001"])
        result = check_package_staleness(p, current_tool_list=["T001", "T002"])
        assert result.status == PackageIntegrityStatus.STALE

    def test_incomplete_when_no_nc_hash(self):
        p = make_package(nc_hash=None, nc_candidate_ref=None)
        result = check_package_staleness(p)
        assert result.status == PackageIntegrityStatus.INCOMPLETE

    def test_hash_deterministic(self):
        p = make_package()
        h1 = compute_package_hash(p)
        h2 = compute_package_hash(p)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_hash_changes_with_nc_hash(self):
        p1 = make_package(nc_hash="abc")
        p2 = make_package(nc_hash="xyz")
        assert compute_package_hash(p1) != compute_package_hash(p2)


# ===========================================================================
# Approval model
# ===========================================================================


class TestApprovalModel:
    def test_approval_scope_dry_run_only(self):
        appr = make_approval()
        assert appr.scope == "DRY_RUN_ONLY"

    def test_no_automatic_approval(self):
        appr = make_approval()
        assert appr.is_automatic is False

    def test_no_execution_approval(self):
        appr = make_approval()
        assert appr.is_execution_approval is False

    def test_pending_status(self):
        appr = make_approval(status=ApprovalStatus.PENDING)
        assert appr.status == ApprovalStatus.PENDING

    def test_expired_status(self):
        appr = make_approval(status=ApprovalStatus.EXPIRED)
        assert appr.status == ApprovalStatus.EXPIRED

    def test_revoked_status(self):
        appr = make_approval(status=ApprovalStatus.REVOKED)
        assert appr.status == ApprovalStatus.REVOKED

    def test_no_approved_for_execution_status(self):
        statuses = [s.value for s in ApprovalStatus]
        assert "APPROVED_FOR_EXECUTION" not in statuses


# ===========================================================================
# Dispatch readiness gate
# ===========================================================================


class TestDispatchReadiness:
    def test_blocked_when_no_nc_candidate(self):
        p = make_package(nc_candidate_ref=None, nc_hash=None)
        r = check_dispatch_readiness(p)
        assert r.status == ShopFloorReadinessStatus.BLOCKED
        assert DispatchErrorCode.INVALID_NC in r.block_reasons

    def test_blocked_when_verification_missing(self):
        p = make_package(verification_ref=None)
        r = check_dispatch_readiness(p)
        assert r.status == ShopFloorReadinessStatus.BLOCKED
        assert DispatchErrorCode.UNVERIFIED_TOOLPATH in r.block_reasons

    def test_blocked_when_no_tools(self):
        p = make_package(tool_list=[])
        r = check_dispatch_readiness(p)
        assert r.status == ShopFloorReadinessStatus.BLOCKED
        assert DispatchErrorCode.TOOL_NOT_READY in r.block_reasons

    def test_blocked_when_no_fixture(self):
        p = make_package(fixture_ref=None)
        r = check_dispatch_readiness(p)
        assert r.status == ShopFloorReadinessStatus.BLOCKED
        assert DispatchErrorCode.FIXTURE_NOT_READY in r.block_reasons

    def test_blocked_when_no_approval(self):
        p = make_package()
        r = check_dispatch_readiness(
            p, machine_state=make_state()
        )
        assert r.status == ShopFloorReadinessStatus.BLOCKED
        assert DispatchErrorCode.APPROVAL_MISSING in r.block_reasons

    def test_approval_always_required(self):
        r = check_dispatch_readiness(make_package())
        assert r.approval_required is True

    def test_is_dispatch_order_always_false(self):
        r = check_dispatch_readiness(make_package())
        assert r.is_dispatch_order is False

    def test_blocked_on_nc_hash_mismatch(self):
        p = make_package(nc_hash="abc123")
        r = check_dispatch_readiness(p, current_nc_hash="xyz999")
        assert DispatchErrorCode.NC_HASH_MISMATCH in r.block_reasons

    def test_blocked_on_assignment_mismatch(self):
        p = make_package(assignment_ref="ASN-001")
        r = check_dispatch_readiness(p, current_assignment_ref="ASN-999")
        assert DispatchErrorCode.ASSIGNMENT_MISMATCH in r.block_reasons

    def test_no_ready_to_run_machine_status(self):
        statuses = [s.value for s in ShopFloorReadinessStatus]
        assert "READY_TO_RUN_MACHINE" not in statuses


# ===========================================================================
# Machine state influences readiness
# ===========================================================================


class TestMachineStateReadiness:
    def test_alarm_blocks_dispatch(self):
        p = make_package()
        state = make_state(alarm_state=AlarmState.ALARM, machine_id="M-001")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_ALARM in r.block_reasons

    def test_offline_blocks_dispatch(self):
        p = make_package()
        state = make_state(availability="OFFLINE", machine_id="M-001")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_OFFLINE in r.block_reasons

    def test_maintenance_blocks_dispatch(self):
        p = make_package()
        state = make_state(availability="MAINTENANCE", machine_id="M-001")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_OFFLINE in r.block_reasons

    def test_busy_blocks_dispatch_by_default(self):
        p = make_package()
        state = make_state(availability="BUSY", machine_id="M-001")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_BUSY in r.block_reasons

    def test_unknown_state_blocks_by_default(self):
        p = make_package()
        state = make_state(availability="UNKNOWN", machine_id="M-001")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert r.status == ShopFloorReadinessStatus.BLOCKED

    def test_identity_mismatch_blocks(self):
        p = make_package(machine_ref="M-001")
        state = make_state(machine_id="M-999")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_IDENTITY_MISMATCH in r.block_reasons

    def test_ready_for_dry_run_on_idle_machine(self):
        p = make_package()
        state = make_state(machine_id="M-001", availability="IDLE", alarm_state=AlarmState.NO_ALARM)
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert r.status == ShopFloorReadinessStatus.READY_FOR_DRY_RUN


# ===========================================================================
# Dry-run dispatch
# ===========================================================================


class TestDryRunDispatch:
    def test_dry_run_never_real_transfer(self):
        p = make_package()
        appr = make_approval()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.is_real_transfer is False
        assert result.is_dispatch_order is False

    def test_dry_run_passes_with_valid_package(self):
        p = make_package()
        appr = make_approval()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.status == DryRunStatus.PASSED

    def test_dry_run_fails_on_alarm(self):
        p = make_package()
        appr = make_approval()
        state = make_state(alarm_state=AlarmState.ALARM)
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.MACHINE_ALARM in result.failures

    def test_dry_run_fails_on_offline(self):
        p = make_package()
        appr = make_approval()
        state = make_state(availability="OFFLINE")
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.MACHINE_OFFLINE in result.failures

    def test_dry_run_fails_on_busy(self):
        p = make_package()
        appr = make_approval()
        state = make_state(availability="BUSY")
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.MACHINE_BUSY in result.failures

    def test_dry_run_fails_missing_approval(self):
        p = make_package()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=None)
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.APPROVAL_MISSING in result.failures

    def test_dry_run_fails_expired_approval(self):
        p = make_package()
        appr = make_approval(status=ApprovalStatus.EXPIRED)
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.APPROVAL_EXPIRED in result.failures

    def test_dry_run_fails_nc_hash_mismatch(self):
        p = make_package(nc_hash="abc123")
        appr = make_approval()
        state = make_state()
        result = run_dry_run(
            p, machine_state=state, approval=appr, current_nc_hash="xyz999"
        )
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.NC_HASH_MISMATCH in result.failures

    def test_dry_run_fails_wrong_machine(self):
        p = make_package(machine_ref="M-001")
        appr = make_approval()
        state = make_state(machine_id="M-999")
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert result.status == DryRunStatus.FAILED

    def test_dry_run_fails_missing_fixture(self):
        p = make_package(fixture_ref=None)
        appr = make_approval()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.FIXTURE_NOT_READY in result.failures

    def test_dry_run_fails_missing_tools(self):
        p = make_package(tool_list=[])
        appr = make_approval()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.TOOL_NOT_READY in result.failures

    def test_dry_run_fails_unverified_toolpath(self):
        p = make_package(verification_ref=None)
        appr = make_approval()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.UNVERIFIED_TOOLPATH in result.failures


# ===========================================================================
# Simulated transfer
# ===========================================================================


class TestSimulatedTransfer:
    def test_simulated_transfer_idle_passes(self):
        p = make_package()
        appr = make_approval()
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.IDLE)
        ctrl.connect_read_only()
        result = run_simulated_transfer(p, ctrl, appr)
        assert result.is_real_transfer is False
        assert result.status == DryRunStatus.PASSED

    def test_simulated_transfer_alarm_fails(self):
        p = make_package()
        appr = make_approval()
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.ALARM)
        ctrl.connect_read_only()
        result = run_simulated_transfer(p, ctrl, appr)
        assert result.status == DryRunStatus.FAILED

    def test_simulated_transfer_offline_fails(self):
        p = make_package()
        appr = make_approval()
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.OFFLINE)
        ctrl.connect_read_only()
        result = run_simulated_transfer(p, ctrl, appr)
        assert result.status == DryRunStatus.FAILED

    def test_simulated_transfer_wrong_machine(self):
        p = make_package(machine_ref="M-001")
        appr = make_approval()
        ctrl = SimulatedCNCController("M-999", SimulatedMachineState.IDLE)
        ctrl.connect_read_only()
        result = run_simulated_transfer(p, ctrl, appr)
        assert result.status == DryRunStatus.FAILED

    def test_simulated_transfer_missing_approval(self):
        p = make_package()
        ctrl = SimulatedCNCController("M-001", SimulatedMachineState.IDLE)
        ctrl.connect_read_only()
        result = run_simulated_transfer(p, ctrl, None)
        assert DispatchErrorCode.APPROVAL_MISSING in result.failures


# ===========================================================================
# Audit trail
# ===========================================================================


class TestAuditTrail:
    def test_audit_package_created(self):
        event = audit_package_created("PKG-001", "J-001", "M-001", "operator")
        assert event.event_type == DispatchAuditEventType.PACKAGE_CREATED
        assert event.package_ref == "PKG-001"
        assert event.actor == "operator"

    def test_audit_approval_requested(self):
        event = audit_approval_requested("PKG-001", "operator")
        assert event.event_type == DispatchAuditEventType.APPROVAL_REQUESTED
        assert event.result == "PENDING"

    def test_audit_approval_granted(self):
        event = audit_approval_granted("PKG-001", "supervisor")
        assert event.event_type == DispatchAuditEventType.APPROVAL_GRANTED_DRY_RUN

    def test_audit_approval_rejected(self):
        event = audit_approval_rejected("PKG-001", "supervisor", "not ready")
        assert event.event_type == DispatchAuditEventType.APPROVAL_REJECTED
        assert event.result == "REJECTED"

    def test_audit_dry_run_started(self):
        event = audit_dry_run_started("PKG-001", "M-001", "operator")
        assert event.event_type == DispatchAuditEventType.DRY_RUN_STARTED

    def test_audit_dry_run_passed(self):
        event = audit_dry_run_passed("PKG-001", "M-001", "operator")
        assert event.event_type == DispatchAuditEventType.DRY_RUN_PASSED

    def test_audit_dry_run_failed(self):
        event = audit_dry_run_failed("PKG-001", "M-001", "operator", "alarm")
        assert event.event_type == DispatchAuditEventType.DRY_RUN_FAILED
        assert event.reason == "alarm"

    def test_audit_package_stale(self):
        event = audit_package_stale("PKG-001", "system", "nc hash changed")
        assert event.event_type == DispatchAuditEventType.PACKAGE_STALE

    def test_audit_machine_state_read(self):
        event = audit_machine_state_read("M-001", "operator")
        assert event.event_type == DispatchAuditEventType.MACHINE_STATE_READ

    def test_audit_events_have_unique_ids(self):
        e1 = audit_package_created("PKG-001", "J-001", "M-001", "op")
        e2 = audit_package_created("PKG-001", "J-001", "M-001", "op")
        assert e1.event_id != e2.event_id

    def test_audit_event_has_timestamp(self):
        event = audit_machine_state_read("M-001", "op")
        assert len(event.timestamp) > 0

    def test_audit_event_is_model(self):
        event = audit_package_created("P", "J", "M", "op")
        assert isinstance(event, DispatchAuditEvent)


# ===========================================================================
# Dispatch policy
# ===========================================================================


class TestDispatchPolicy:
    def test_default_policy_fails_closed(self):
        policy = DispatchPolicy()
        assert policy.require_human_approval is True
        assert policy.require_verified_toolpath is True
        assert policy.require_valid_nc is True
        assert policy.require_machine_idle is True
        assert policy.require_no_alarm is True
        assert policy.allow_unknown_machine_state is False

    def test_human_approval_always_required(self):
        policy = DispatchPolicy()
        assert policy.require_human_approval is True


# ===========================================================================
# Negative / security boundary tests
# ===========================================================================


class TestNegativeTests:
    def test_schedule_candidate_is_not_dispatch(self):
        # A schedule candidate never equals a dispatch order
        result = run_dry_run(make_package(), approval=make_approval())
        assert result.is_dispatch_order is False

    def test_assignment_candidate_is_not_dispatch(self):
        p = make_package()
        assert p.is_dispatch_order is False

    def test_nc_candidate_not_machine_approved(self):
        # NC candidate presence alone is not machine approval
        p = make_package(nc_candidate_ref="NC-001", nc_hash="abc")
        result = run_dry_run(p, approval=None)
        assert DispatchErrorCode.APPROVAL_MISSING in result.failures

    def test_approved_dry_run_is_not_execution(self):
        appr = make_approval()
        assert appr.is_execution_approval is False
        assert appr.scope == "DRY_RUN_ONLY"

    def test_connected_machine_is_not_ready(self):
        p = make_package()
        # Even CONNECTED machine still requires approval
        state = make_state(connection_status=ConnectionStatus.CONNECTED)
        result = run_dry_run(p, machine_state=state, approval=None)
        assert DispatchErrorCode.APPROVAL_MISSING in result.failures

    def test_unknown_state_is_not_ready(self):
        p = make_package()
        state = make_state(availability="UNKNOWN")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        # UNKNOWN state should block by default
        assert r.status == ShopFloorReadinessStatus.BLOCKED

    def test_busy_machine_not_dry_run_ready(self):
        p = make_package()
        state = make_state(availability="BUSY")
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_BUSY in r.block_reasons

    def test_alarm_machine_not_dry_run_ready(self):
        p = make_package()
        state = make_state(alarm_state=AlarmState.ALARM)
        appr = make_approval()
        r = check_dispatch_readiness(p, machine_state=state, approval=appr)
        assert DispatchErrorCode.MACHINE_ALARM in r.block_reasons

    def test_missing_approval_always_blocked(self):
        p = make_package()
        r = check_dispatch_readiness(p, approval=None)
        assert DispatchErrorCode.APPROVAL_MISSING in r.block_reasons

    def test_stale_package_blocked(self):
        p = make_package(nc_hash="abc")
        r = check_dispatch_readiness(p, current_nc_hash="xyz")
        assert DispatchErrorCode.NC_HASH_MISMATCH in r.block_reasons

    def test_hash_mismatch_blocked(self):
        p = make_package(nc_hash="v1")
        appr = make_approval()
        state = make_state()
        result = run_dry_run(p, machine_state=state, approval=appr, current_nc_hash="v2")
        assert result.status == DryRunStatus.FAILED
        assert DispatchErrorCode.NC_HASH_MISMATCH in result.failures

    def test_no_send_to_machine_in_module(self):
        import inspect

        import backend.dispatch.dry_run as mod
        src = inspect.getsource(mod)
        forbidden = ["send_to_machine", "socket.send", "ftplib", "paramiko", "dnc_send"]
        for f in forbidden:
            assert f not in src, f"Forbidden: {f}"

    def test_no_real_write_in_simulated(self):
        import inspect

        import backend.dispatch.simulated as mod
        src = inspect.getsource(mod)
        forbidden = [
            "socket.send", "ftplib", "paramiko",
            "PLC write", "opc_ua_write", "write_value",
            "machine_start", "cycle_start",
        ]
        for f in forbidden:
            assert f.lower() not in src.lower(), f"Forbidden: {f}"

    def test_no_auto_dispatch_in_readiness(self):
        import inspect

        import backend.dispatch.readiness as mod
        src = inspect.getsource(mod)
        forbidden = ["auto_dispatch", "automatic_dispatch", "auto_start"]
        for f in forbidden:
            assert f not in src, f"Forbidden: {f}"

    def test_no_sent_to_machine_status(self):
        statuses = [s.value for s in DispatchPackageStatus]
        assert "SENT_TO_MACHINE" not in statuses

    def test_no_running_status_in_package(self):
        statuses = [s.value for s in DispatchPackageStatus]
        assert "RUNNING" not in statuses
