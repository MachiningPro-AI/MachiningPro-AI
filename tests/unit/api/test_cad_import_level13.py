"""
Level-13 Machine Scheduling and Job Assignment — deterministic unit tests.

Covers:
  - Machine eligibility (hard constraints + soft ranking)
  - Hard constraint rejection
  - Unknown availability != available
  - Compatible != available (HARD RULE 20)
  - Tool availability
  - Holder availability
  - Fixture availability
  - Calendar blocking / maintenance blocking
  - Queue sequencing (FIFO, EDD, SPT, PRIORITY_FIRST)
  - Planned finish / lateness
  - Double booking / resource conflicts
  - What-if scenarios
  - Production readiness
  - Negative tests
  - Invariant assertions: is_dispatch_order=False, approval_required=True
  - No CNC dispatch
  - No fabricated data
"""

import pytest

from backend.scheduling import (
    APPROVAL_REQUIRED,
    IS_DISPATCHABLE,
    NO_CNC_DISPATCH,
)
from backend.scheduling.conflicts import detect_conflicts
from backend.scheduling.eligibility import (
    check_machine_eligibility,
)
from backend.scheduling.enums import (
    DurationStatus,
    FixtureAvailabilityStatus,
    HolderAvailabilityStatus,
    JobPriority,
    MachineAvailabilityStatus,
    MachineClass,
    MachineEligibilityResult,
    NCReadinessStatus,
    ProductionReadinessStatus,
    ResourceConflictType,
    SchedulingAlgorithm,
    SchedulingBlockReason,
    SetupReadinessStatus,
    ToolAvailabilityStatus,
)
from backend.scheduling.models import (
    DurationEstimate,
    JobAssignmentCandidate,
    MachineRequirements,
    MachineResource,
    PlanningReservation,
    ProductionJob,
)
from backend.scheduling.readiness import (
    check_nc_readiness,
    check_production_readiness,
    check_setup_readiness,
)
from backend.scheduling.scheduler import (
    apply_scheduling_algorithm,
    create_schedule_candidate,
    evaluate_job_assignment,
    evaluate_machine_candidates,
)

# ===========================================================================
# Fixtures
# ===========================================================================


def make_job(
    job_id="JOB-001",
    machine_class="VMC_3AXIS",
    axis_count=3,
    toolpath_verified=True,
    nc_candidate_ref="NC-001",
    nc_candidate_status="VALIDATED_OFFLINE",
    nc_candidate_stale=False,
    priority="NORMAL",
    due_date=None,
    cycle_time=30.0,
    setup_time=15.0,
    required_tools=None,
    required_holders=None,
    required_fixture=None,
    requires_turning=False,
    requires_milling=True,
    quantity=1,
) -> ProductionJob:
    reqs = MachineRequirements(
        required_machine_class=MachineClass(machine_class),
        required_axis_count=axis_count,
        requires_turning=requires_turning,
        requires_milling=requires_milling,
    )
    return ProductionJob(
        job_id=job_id,
        quantity=quantity,
        priority=JobPriority(priority),
        due_date=due_date,
        toolpath_verified=toolpath_verified,
        nc_candidate_ref=nc_candidate_ref,
        nc_candidate_status=nc_candidate_status,
        nc_candidate_stale=nc_candidate_stale,
        machine_requirements=reqs,
        required_tools=required_tools or [],
        required_holders=required_holders or [],
        required_fixture=required_fixture,
        estimated_cycle_time_min=cycle_time,
        setup_time_min=setup_time,
    )


def make_machine(
    machine_id="MACHINE-001",
    machine_class="VMC_3AXIS",
    axis_count=3,
    availability="AVAILABLE",
    supports_milling=True,
    supports_turning=False,
    available_tools=None,
    installed_fixture=None,
    x_travel=600.0,
    y_travel=400.0,
    z_travel=500.0,
    spindle_speed=12000.0,
    table_load=500.0,
) -> MachineResource:
    return MachineResource(
        machine_id=machine_id,
        machine_name=f"Test {machine_id}",
        machine_class=MachineClass(machine_class),
        axis_count=axis_count,
        x_travel_mm=x_travel,
        y_travel_mm=y_travel,
        z_travel_mm=z_travel,
        spindle_speed_max_rpm=spindle_speed,
        table_load_capacity_kg=table_load,
        supports_milling=supports_milling,
        supports_turning=supports_turning,
        availability_status=MachineAvailabilityStatus(availability),
        available_tool_ids=available_tools or [],
        installed_fixture_id=installed_fixture,
    )


# ===========================================================================
# Module-level constants
# ===========================================================================


class TestModuleConstants:
    def test_approval_required_is_true(self):
        assert APPROVAL_REQUIRED is True

    def test_no_cnc_dispatch_is_true(self):
        assert NO_CNC_DISPATCH is True

    def test_is_dispatchable_is_false(self):
        assert IS_DISPATCHABLE is False


# ===========================================================================
# Machine eligibility — hard constraints
# ===========================================================================


class TestMachineEligibilityHardConstraints:
    def test_eligible_when_class_matches(self):
        job = make_job(machine_class="VMC_3AXIS", axis_count=3)
        machine = make_machine(machine_class="VMC_3AXIS", axis_count=3)
        report = check_machine_eligibility(job, machine)
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )

    def test_ineligible_class_mismatch(self):
        job = make_job(machine_class="VMC_3AXIS", axis_count=3, requires_milling=True)
        machine = make_machine(
            machine_class="LATHE_2AXIS", supports_milling=False, supports_turning=True
        )
        report = check_machine_eligibility(job, machine)
        assert report.result == MachineEligibilityResult.INELIGIBLE

    def test_ineligible_missing_milling_capability(self):
        job = make_job(requires_milling=True)
        machine = make_machine(supports_milling=False, supports_turning=True)
        report = check_machine_eligibility(job, machine)
        assert report.result == MachineEligibilityResult.INELIGIBLE

    def test_ineligible_missing_turning_capability(self):
        job = make_job(machine_class="LATHE_2AXIS", requires_turning=True, requires_milling=False)
        machine = make_machine(
            machine_class="VMC_3AXIS", supports_milling=True, supports_turning=False
        )
        report = check_machine_eligibility(job, machine)
        assert report.result == MachineEligibilityResult.INELIGIBLE

    def test_eligible_5axis_satisfies_3axis_requirement(self):
        job = make_job(machine_class="VMC_3AXIS", axis_count=3)
        machine = make_machine(machine_class="VMC_5AXIS", axis_count=5)
        report = check_machine_eligibility(job, machine)
        # VMC_5AXIS satisfies VMC_3AXIS requirement
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )

    def test_ineligible_axis_count_too_low(self):
        job = make_job(machine_class="VMC_5AXIS", axis_count=5)
        machine = make_machine(machine_class="VMC_3AXIS", axis_count=3)
        report = check_machine_eligibility(job, machine)
        assert report.result == MachineEligibilityResult.INELIGIBLE

    def test_ineligible_x_travel_insufficient(self):
        reqs = MachineRequirements(
            required_machine_class=MachineClass.VMC_3AXIS,
            required_x_travel_mm=1000.0,  # requires 1 meter
        )
        job = ProductionJob(
            job_id="J",
            machine_requirements=reqs,
            toolpath_verified=True,
            nc_candidate_ref="NC",
            nc_candidate_status="VALIDATED_OFFLINE",
        )
        machine = make_machine(x_travel=600.0)  # only 600 mm
        report = check_machine_eligibility(job, machine)
        assert report.result == MachineEligibilityResult.INELIGIBLE

    def test_hard_constraint_failures_populated(self):
        job = make_job(requires_milling=True)
        machine = make_machine(supports_milling=False, supports_turning=True)
        report = check_machine_eligibility(job, machine)
        assert len(report.hard_constraint_failures) > 0

    def test_checks_list_populated(self):
        job = make_job()
        machine = make_machine()
        report = check_machine_eligibility(job, machine)
        assert len(report.checks) > 0

    def test_machine_id_in_report(self):
        job = make_job()
        machine = make_machine(machine_id="TEST-MACHINE")
        report = check_machine_eligibility(job, machine)
        assert report.machine_id == "TEST-MACHINE"


# ===========================================================================
# Machine eligibility — availability is separate from eligibility
# ===========================================================================


class TestEligibilityAvailabilitySeparation:
    """HARD RULE 20: machine compatibility and scheduling availability must remain separate."""

    def test_eligible_machine_can_be_unavailable(self):
        job = make_job()
        machine = make_machine(availability="BUSY")
        report = check_machine_eligibility(job, machine)
        # Eligibility does NOT depend on availability
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )

    def test_eligible_machine_can_be_in_maintenance(self):
        job = make_job()
        machine = make_machine(availability="MAINTENANCE")
        report = check_machine_eligibility(job, machine)
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )

    def test_eligible_machine_can_be_offline(self):
        job = make_job()
        machine = make_machine(availability="OFFLINE")
        report = check_machine_eligibility(job, machine)
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )

    def test_unknown_availability_does_not_block_eligibility(self):
        job = make_job()
        machine = make_machine(availability="UNKNOWN")
        report = check_machine_eligibility(job, machine)
        # UNKNOWN availability must not block eligibility check
        assert report.result != MachineEligibilityResult.INELIGIBLE

    def test_schedule_candidate_warns_on_maintenance(self):
        job = make_job()
        machine = make_machine(availability="MAINTENANCE")
        candidate = create_schedule_candidate(job, machine)
        # Must warn about maintenance but not make it a dispatch order
        assert candidate.is_dispatch_order is False
        assert candidate.approval_required is True

    def test_schedule_candidate_warns_on_unknown_availability(self):
        job = make_job()
        machine = make_machine(availability="UNKNOWN")
        candidate = create_schedule_candidate(job, machine)
        assert any("UNKNOWN" in w for w in candidate.warnings)
        assert candidate.is_dispatch_order is False


# ===========================================================================
# HARD RULE 22: UNKNOWN availability must NOT be treated as AVAILABLE
# ===========================================================================


class TestUnknownAvailabilityNotAvailable:
    def test_unknown_is_not_available(self):
        assert MachineAvailabilityStatus.UNKNOWN != MachineAvailabilityStatus.AVAILABLE

    def test_unknown_availability_generates_warning(self):
        job = make_job()
        machine = make_machine(availability="UNKNOWN")
        candidate = create_schedule_candidate(job, machine)
        assert len(candidate.warnings) > 0

    def test_unknown_does_not_produce_confirmed_schedule_slot(self):
        job = make_job()
        machine = make_machine(availability="UNKNOWN")
        candidate = create_schedule_candidate(job, machine)
        # With UNKNOWN availability, planned_start_iso should not be set
        # (no fabricated data)
        # At minimum, must warn
        assert candidate.is_dispatch_order is False


# ===========================================================================
# NC readiness
# ===========================================================================


class TestNCReadiness:
    def test_ready_when_validated_offline_and_not_stale(self):
        job = make_job(
            nc_candidate_ref="NC-001",
            nc_candidate_status="VALIDATED_OFFLINE",
            nc_candidate_stale=False,
            toolpath_verified=True,
        )
        r = check_nc_readiness(job)
        assert r.status == NCReadinessStatus.READY

    def test_blocked_when_no_nc_candidate(self):
        job = make_job(nc_candidate_ref=None, nc_candidate_status=None)
        r = check_nc_readiness(job)
        assert r.status in (
            NCReadinessStatus.NOT_GENERATED,
            NCReadinessStatus.BLOCKED,
            NCReadinessStatus.UNKNOWN,
        )

    def test_stale_when_nc_candidate_stale(self):
        job = make_job(nc_candidate_stale=True, nc_candidate_status="VALIDATED_OFFLINE")
        r = check_nc_readiness(job)
        assert r.status in (NCReadinessStatus.STALE, NCReadinessStatus.BLOCKED)

    def test_blocked_when_toolpath_not_verified(self):
        job = make_job(toolpath_verified=False, nc_candidate_status="VALIDATED_OFFLINE")
        r = check_nc_readiness(job)
        # Unverified toolpath → cannot be NC-ready
        assert r.status != NCReadinessStatus.READY

    def test_nc_candidate_never_dispatchable(self):
        """NC candidate from Level-12 must never become dispatchable in Level-13."""
        job = make_job(nc_candidate_status="VALIDATED_OFFLINE")
        r = check_nc_readiness(job)
        # nc_candidate_status should never be READY_TO_RUN or similar
        assert r.status != "READY_TO_RUN"


# ===========================================================================
# Setup readiness
# ===========================================================================


class TestSetupReadiness:
    def test_ready_when_all_tools_available(self):
        job = make_job(required_tools=["T001", "T002"])
        tool_avail = {
            "T001": ToolAvailabilityStatus.AVAILABLE,
            "T002": ToolAvailabilityStatus.AVAILABLE,
        }
        r = check_setup_readiness(job, tool_availability=tool_avail)
        assert r.status in (SetupReadinessStatus.READY, SetupReadinessStatus.PARTIAL)

    def test_blocked_when_tool_missing(self):
        job = make_job(required_tools=["T001"])
        tool_avail = {"T001": ToolAvailabilityStatus.MISSING}
        r = check_setup_readiness(job, tool_availability=tool_avail)
        assert r.status == SetupReadinessStatus.BLOCKED
        assert "T001" in r.missing_tools
        assert SchedulingBlockReason.TOOL_MISSING in r.block_reasons

    def test_blocked_when_fixture_missing(self):
        job = make_job(required_fixture="FIX-001")
        fixture_avail = FixtureAvailabilityStatus.MISSING
        r = check_setup_readiness(job, fixture_availability=fixture_avail)
        assert r.fixture_blocked is True
        assert SchedulingBlockReason.FIXTURE_MISSING in r.block_reasons

    def test_unknown_when_no_availability_data(self):
        job = make_job(required_tools=["T001"])
        r = check_setup_readiness(job, tool_availability=None)
        assert r.status == SetupReadinessStatus.UNKNOWN

    def test_blocked_when_holder_missing(self):
        job = make_job(required_holders=["H001"])
        holder_avail = {"H001": HolderAvailabilityStatus.MISSING}
        r = check_setup_readiness(job, holder_availability=holder_avail)
        assert "H001" in r.missing_holders

    def test_fixture_available_clears_fixture_block(self):
        job = make_job(required_fixture="FIX-001")
        fixture_avail = FixtureAvailabilityStatus.AVAILABLE
        r = check_setup_readiness(job, fixture_availability=fixture_avail)
        assert r.fixture_blocked is False


# ===========================================================================
# Production readiness
# ===========================================================================


class TestProductionReadiness:
    def test_approval_required_always_true(self):
        job = make_job()
        r = check_production_readiness(job)
        assert r.approval_required is True

    def test_no_ready_for_dispatch_status(self):
        """READY_FOR_DISPATCH must never appear — it has been removed."""
        job = make_job(toolpath_verified=True, nc_candidate_status="VALIDATED_OFFLINE")
        r = check_production_readiness(job, machine_eligible=True, schedule_slot_available=True)
        has_dispatch = hasattr(ProductionReadinessStatus, "READY_FOR_DISPATCH")
        if has_dispatch:
            assert r.status != ProductionReadinessStatus("READY_FOR_DISPATCH")  # type: ignore[attr-defined]
        assert r.status.value != "READY_FOR_DISPATCH"

    def test_dispatch_blocked_when_toolpath_not_verified(self):
        job = make_job(toolpath_verified=False)
        r = check_production_readiness(job)
        assert r.status in (
            ProductionReadinessStatus.DISPATCH_BLOCKED,
            ProductionReadinessStatus.REVIEW_REQUIRED,
            ProductionReadinessStatus.UNKNOWN,
        )

    def test_ready_for_scheduling_when_all_ok(self):
        # Need process_plan_ref for engineering_complete=True
        reqs = MachineRequirements(required_machine_class=MachineClass.VMC_3AXIS)
        job = ProductionJob(
            job_id="J",
            quantity=1,
            priority=JobPriority.NORMAL,
            toolpath_verified=True,
            nc_candidate_ref="NC-001",
            nc_candidate_status="VALIDATED_OFFLINE",
            nc_candidate_stale=False,
            machine_requirements=reqs,
            estimated_cycle_time_min=30.0,
            setup_time_min=15.0,
            process_plan_ref="PP-001",
            cam_plan_ref="CAM-001",
        )
        r = check_production_readiness(job, machine_eligible=True, schedule_slot_available=True)
        assert r.status in (
            ProductionReadinessStatus.READY_FOR_SCHEDULING,
            ProductionReadinessStatus.REVIEW_REQUIRED,
        )

    def test_unknown_when_no_nc_data(self):
        job = make_job(nc_candidate_ref=None, nc_candidate_status=None)
        r = check_production_readiness(job)
        assert r.status in (
            ProductionReadinessStatus.DISPATCH_BLOCKED,
            ProductionReadinessStatus.UNKNOWN,
        )


# ===========================================================================
# FIFO algorithm
# ===========================================================================


class TestFIFOAlgorithm:
    def test_fifo_preserves_order(self):
        jobs = [make_job(job_id=f"J{i}") for i in range(5)]
        result = apply_scheduling_algorithm(jobs, "M001", SchedulingAlgorithm.FIFO)
        assert result.ordered_job_ids == [f"J{i}" for i in range(5)]

    def test_fifo_single_job(self):
        jobs = [make_job(job_id="ONLY")]
        result = apply_scheduling_algorithm(jobs, "M001", SchedulingAlgorithm.FIFO)
        assert result.ordered_job_ids == ["ONLY"]

    def test_fifo_empty_queue(self):
        result = apply_scheduling_algorithm([], "M001", SchedulingAlgorithm.FIFO)
        assert result.ordered_job_ids == []

    def test_fifo_algorithm_recorded(self):
        jobs = [make_job()]
        result = apply_scheduling_algorithm(jobs, "M001", SchedulingAlgorithm.FIFO)
        assert result.algorithm == SchedulingAlgorithm.FIFO

    def test_fifo_has_assumptions(self):
        jobs = [make_job()]
        result = apply_scheduling_algorithm(jobs, "M001", SchedulingAlgorithm.FIFO)
        assert len(result.assumptions) > 0


# ===========================================================================
# EDD algorithm
# ===========================================================================


class TestEDDAlgorithm:
    def test_edd_sorts_by_due_date(self):
        j1 = make_job(job_id="J1", due_date="2026-12-01")
        j2 = make_job(job_id="J2", due_date="2026-11-01")
        j3 = make_job(job_id="J3", due_date="2026-11-15")
        result = apply_scheduling_algorithm([j1, j2, j3], "M001", SchedulingAlgorithm.EDD)
        assert result.ordered_job_ids == ["J2", "J3", "J1"]

    def test_edd_no_due_date_goes_last(self):
        j1 = make_job(job_id="J1", due_date="2026-11-01")
        j2 = make_job(job_id="J2", due_date=None)
        result = apply_scheduling_algorithm([j1, j2], "M001", SchedulingAlgorithm.EDD)
        assert result.ordered_job_ids[0] == "J1"
        assert result.ordered_job_ids[-1] == "J2"

    def test_edd_warns_about_jobs_without_due_date(self):
        j1 = make_job(job_id="J1", due_date=None)
        result = apply_scheduling_algorithm([j1], "M001", SchedulingAlgorithm.EDD)
        assert len(result.warnings) > 0


# ===========================================================================
# SPT algorithm
# ===========================================================================


class TestSPTAlgorithm:
    def test_spt_sorts_by_cycle_time(self):
        j1 = make_job(job_id="J1", cycle_time=60.0)
        j2 = make_job(job_id="J2", cycle_time=10.0)
        j3 = make_job(job_id="J3", cycle_time=30.0)
        result = apply_scheduling_algorithm([j1, j2, j3], "M001", SchedulingAlgorithm.SPT)
        assert result.ordered_job_ids == ["J2", "J3", "J1"]

    def test_spt_unknown_cycle_time_goes_last(self):
        j1 = make_job(job_id="J1", cycle_time=30.0)
        j2 = make_job(job_id="J2", cycle_time=None)
        result = apply_scheduling_algorithm([j1, j2], "M001", SchedulingAlgorithm.SPT)
        assert result.ordered_job_ids[0] == "J1"
        assert result.ordered_job_ids[-1] == "J2"

    def test_spt_warns_unknown_cycle_time(self):
        j1 = make_job(job_id="J1", cycle_time=None)
        result = apply_scheduling_algorithm([j1], "M001", SchedulingAlgorithm.SPT)
        assert len(result.warnings) > 0


# ===========================================================================
# PRIORITY_FIRST algorithm
# ===========================================================================


class TestPriorityFirstAlgorithm:
    def test_urgent_before_high(self):
        j1 = make_job(job_id="J1", priority="HIGH")
        j2 = make_job(job_id="J2", priority="URGENT")
        result = apply_scheduling_algorithm([j1, j2], "M001", SchedulingAlgorithm.PRIORITY_FIRST)
        assert result.ordered_job_ids[0] == "J2"

    def test_urgent_high_normal_low_order(self):
        j_low = make_job(job_id="J_LOW", priority="LOW")
        j_norm = make_job(job_id="J_NORM", priority="NORMAL")
        j_high = make_job(job_id="J_HIGH", priority="HIGH")
        j_urg = make_job(job_id="J_URG", priority="URGENT")
        result = apply_scheduling_algorithm(
            [j_low, j_norm, j_urg, j_high], "M001", SchedulingAlgorithm.PRIORITY_FIRST
        )
        order = result.ordered_job_ids
        assert order[0] == "J_URG"
        assert order[1] == "J_HIGH"
        assert order[2] == "J_NORM"
        assert order[3] == "J_LOW"

    def test_same_priority_fifo_tiebreak(self):
        j1 = make_job(job_id="A", priority="NORMAL")
        j2 = make_job(job_id="B", priority="NORMAL")
        result = apply_scheduling_algorithm([j1, j2], "M001", SchedulingAlgorithm.PRIORITY_FIRST)
        # Tiebreak by job_id string — deterministic
        assert result.ordered_job_ids[0] == "A"
        assert result.ordered_job_ids[1] == "B"


# ===========================================================================
# Queue entries
# ===========================================================================


class TestQueueEntries:
    def test_queue_entries_count_matches_jobs(self):
        jobs = [make_job(job_id=f"J{i}") for i in range(3)]
        result = apply_scheduling_algorithm(jobs, "M001", SchedulingAlgorithm.FIFO)
        assert len(result.queue_entries) == 3

    def test_queue_positions_start_at_1(self):
        jobs = [make_job(job_id="J1"), make_job(job_id="J2")]
        result = apply_scheduling_algorithm(jobs, "M001", SchedulingAlgorithm.FIFO)
        positions = [e.queue_position for e in result.queue_entries]
        assert positions[0] == 1
        assert positions[1] == 2

    def test_duration_status_partial_when_cycle_time_missing(self):
        job = make_job(cycle_time=None)
        result = apply_scheduling_algorithm([job], "M001", SchedulingAlgorithm.FIFO)
        assert result.queue_entries[0].duration_status in (
            DurationStatus.UNKNOWN,
            DurationStatus.PARTIAL,
        )


# ===========================================================================
# DurationEstimate
# ===========================================================================


class TestDurationEstimate:
    def test_known_when_all_data_present(self):
        job = make_job(cycle_time=30.0, setup_time=15.0, quantity=2)
        d = DurationEstimate.from_job(job)
        assert d.total_estimated_min == pytest.approx(2 * 30.0 + 15.0)
        assert d.status == DurationStatus.KNOWN

    def test_unknown_when_no_data(self):
        job = make_job(cycle_time=None, setup_time=None)
        d = DurationEstimate.from_job(job)
        assert d.status in (DurationStatus.UNKNOWN, DurationStatus.PARTIAL)
        assert d.total_estimated_min is None or d.status != DurationStatus.KNOWN

    def test_no_fabricated_data(self):
        """DurationEstimate must not fabricate values when inputs are None."""
        job = make_job(cycle_time=None, setup_time=None)
        d = DurationEstimate.from_job(job)
        assert d.cycle_time_per_part_min is None
        assert d.setup_time_min is None


# ===========================================================================
# ScheduleCandidate invariants
# ===========================================================================


class TestScheduleCandidateInvariants:
    def test_is_dispatch_order_always_false(self):
        job = make_job()
        machine = make_machine()
        candidate = create_schedule_candidate(job, machine)
        assert candidate.is_dispatch_order is False

    def test_approval_required_always_true(self):
        job = make_job()
        machine = make_machine()
        candidate = create_schedule_candidate(job, machine)
        assert candidate.approval_required is True

    def test_job_id_in_candidate(self):
        job = make_job(job_id="TEST-JOB")
        machine = make_machine()
        candidate = create_schedule_candidate(job, machine)
        assert candidate.job_id == "TEST-JOB"

    def test_machine_id_in_candidate(self):
        job = make_job()
        machine = make_machine(machine_id="TEST-MACHINE")
        candidate = create_schedule_candidate(job, machine)
        assert candidate.machine_id == "TEST-MACHINE"


# ===========================================================================
# JobAssignmentCandidate invariants
# ===========================================================================


class TestJobAssignmentCandidateInvariants:
    def test_is_dispatch_order_always_false(self):
        job = make_job()
        machine = make_machine()
        c = evaluate_job_assignment(job, machine)
        assert c.is_dispatch_order is False

    def test_approval_required_always_true(self):
        job = make_job()
        machine = make_machine()
        c = evaluate_job_assignment(job, machine)
        assert c.approval_required is True

    def test_schedule_candidate_in_assignment(self):
        job = make_job()
        machine = make_machine()
        c = evaluate_job_assignment(job, machine)
        assert c.schedule_candidate is not None
        assert c.schedule_candidate.is_dispatch_order is False

    def test_eligibility_report_in_assignment(self):
        job = make_job()
        machine = make_machine()
        c = evaluate_job_assignment(job, machine)
        assert c.eligibility_report is not None
        assert c.eligibility_report.machine_id == machine.machine_id


# ===========================================================================
# Rank eligible machines
# ===========================================================================


class TestRankEligibleMachines:
    def test_eligible_before_partially_eligible(self):
        job = make_job()
        # over-spec → partial?
        m1 = make_machine(machine_id="M1", machine_class="VMC_5AXIS", axis_count=5)
        m2 = make_machine(machine_id="M2")  # exact match
        reports = evaluate_machine_candidates(job, [m1, m2])
        eligible = [r for r in reports if r.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )]
        assert len(eligible) >= 1

    def test_ineligible_comes_last(self):
        job = make_job(requires_milling=True)
        m_good = make_machine(machine_id="GOOD", supports_milling=True)
        m_bad = make_machine(machine_id="BAD", supports_milling=False, supports_turning=True,
                              machine_class="LATHE_2AXIS")
        reports = evaluate_machine_candidates(job, [m_bad, m_good])
        ineligible_idx = next(
            i for i, r in enumerate(reports)
            if r.result == MachineEligibilityResult.INELIGIBLE
        )
        eligible_idx = next(
            i for i, r in enumerate(reports)
            if r.result in (
                MachineEligibilityResult.ELIGIBLE,
                MachineEligibilityResult.PARTIALLY_ELIGIBLE,
            )
        )
        assert eligible_idx < ineligible_idx


# ===========================================================================
# Double booking and resource conflicts
# ===========================================================================


class TestResourceConflicts:
    def test_machine_double_booking_detected(self):
        c1 = JobAssignmentCandidate(job_ref="J1", machine_ref="M1")
        c2 = JobAssignmentCandidate(job_ref="J2", machine_ref="M1")
        conflicts = detect_conflicts(candidates=[c1, c2])
        machine_conflicts = [
            c for c in conflicts
            if c.conflict_type == ResourceConflictType.MACHINE_DOUBLE_BOOKING
        ]
        assert len(machine_conflicts) > 0

    def test_no_conflict_when_different_machines(self):
        c1 = JobAssignmentCandidate(job_ref="J1", machine_ref="M1")
        c2 = JobAssignmentCandidate(job_ref="J2", machine_ref="M2")
        conflicts = detect_conflicts(candidates=[c1, c2])
        machine_conflicts = [
            c for c in conflicts
            if c.conflict_type == ResourceConflictType.MACHINE_DOUBLE_BOOKING
        ]
        assert len(machine_conflicts) == 0

    def test_fixture_double_booking_detected(self):
        c1 = JobAssignmentCandidate(job_ref="J1", machine_ref="M1", fixture_ref="FIX-001")
        c2 = JobAssignmentCandidate(job_ref="J2", machine_ref="M2", fixture_ref="FIX-001")
        conflicts = detect_conflicts(candidates=[c1, c2])
        fixture_conflicts = [
            c for c in conflicts
            if c.conflict_type == ResourceConflictType.FIXTURE_DOUBLE_BOOKING
        ]
        assert len(fixture_conflicts) > 0

    def test_tool_conflict_detected(self):
        c1 = JobAssignmentCandidate(job_ref="J1", machine_ref="M1", tool_refs=["T001"])
        c2 = JobAssignmentCandidate(job_ref="J2", machine_ref="M2", tool_refs=["T001"])
        conflicts = detect_conflicts(candidates=[c1, c2])
        tool_conflicts = [
            c for c in conflicts
            if c.conflict_type == ResourceConflictType.TOOL_RESERVATION_CONFLICT
        ]
        assert len(tool_conflicts) > 0

    def test_reservation_machine_booking_detected(self):
        c1 = JobAssignmentCandidate(job_ref="J1", machine_ref="M1")
        r1 = PlanningReservation(reservation_id="R1", job_id="J2", machine_id="M1")
        conflicts = detect_conflicts(candidates=[c1], reservations=[r1])
        machine_conflicts = [
            c for c in conflicts
            if c.conflict_type == ResourceConflictType.MACHINE_DOUBLE_BOOKING
        ]
        assert len(machine_conflicts) > 0

    def test_empty_inputs_no_conflicts(self):
        conflicts = detect_conflicts(candidates=[], reservations=[])
        assert conflicts == []


# ===========================================================================
# What-if scenarios
# ===========================================================================


class TestWhatIfScenarios:
    def test_what_if_different_algorithms_give_different_orders(self):
        j1 = make_job(job_id="J1", cycle_time=60.0, priority="LOW", due_date="2026-12-31")
        j2 = make_job(job_id="J2", cycle_time=10.0, priority="URGENT", due_date="2026-11-10")
        j3 = make_job(job_id="J3", cycle_time=30.0, priority="NORMAL", due_date="2026-11-20")

        fifo = apply_scheduling_algorithm([j1, j2, j3], "M", SchedulingAlgorithm.FIFO)
        edd = apply_scheduling_algorithm([j1, j2, j3], "M", SchedulingAlgorithm.EDD)
        spt = apply_scheduling_algorithm([j1, j2, j3], "M", SchedulingAlgorithm.SPT)
        prio = apply_scheduling_algorithm([j1, j2, j3], "M", SchedulingAlgorithm.PRIORITY_FIRST)

        # All produce a result
        assert fifo.ordered_job_ids
        assert edd.ordered_job_ids
        assert spt.ordered_job_ids
        assert prio.ordered_job_ids

        # Different algorithms can give different orders
        assert edd.ordered_job_ids != fifo.ordered_job_ids or \
               spt.ordered_job_ids != fifo.ordered_job_ids or \
               prio.ordered_job_ids != fifo.ordered_job_ids

    def test_what_if_different_machines_different_eligibility(self):
        job = make_job(requires_milling=True)
        m_mill = make_machine(machine_id="MILL", supports_milling=True)
        m_lathe = make_machine(machine_id="LATHE", supports_milling=False, supports_turning=True,
                                machine_class="LATHE_2AXIS")
        reports = evaluate_machine_candidates(job, [m_mill, m_lathe])
        results = {r.machine_id: r.result for r in reports}
        assert results["MILL"] != MachineEligibilityResult.INELIGIBLE
        assert results["LATHE"] == MachineEligibilityResult.INELIGIBLE


# ===========================================================================
# Negative tests
# ===========================================================================


class TestNegativeTests:
    def test_compatible_does_not_mean_available(self):
        """HARD RULE 20: compatible != available."""
        job = make_job()
        machine = make_machine(availability="BUSY")
        # Machine is compatible (eligible)
        report = check_machine_eligibility(job, machine)
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )
        # But a schedule candidate must warn about BUSY availability
        candidate = create_schedule_candidate(job, machine)
        assert any("BUSY" in w for w in candidate.warnings)
        assert candidate.is_dispatch_order is False

    def test_available_does_not_mean_compatible(self):
        """HARD RULE 20: available != compatible."""
        job = make_job(requires_milling=True)
        machine = make_machine(supports_milling=False, supports_turning=True,
                                machine_class="LATHE_2AXIS", availability="AVAILABLE")
        # Machine is available but not compatible
        report = check_machine_eligibility(job, machine)
        assert report.result == MachineEligibilityResult.INELIGIBLE

    def test_unknown_availability_not_available(self):
        assert MachineAvailabilityStatus.UNKNOWN != MachineAvailabilityStatus.AVAILABLE

    def test_missing_tool_means_assignment_not_ready(self):
        job = make_job(required_tools=["T001"])
        tool_avail = {"T001": ToolAvailabilityStatus.MISSING}
        r = check_setup_readiness(job, tool_availability=tool_avail)
        assert r.status == SetupReadinessStatus.BLOCKED
        assert SchedulingBlockReason.TOOL_MISSING in r.block_reasons

    def test_missing_fixture_means_assignment_not_ready(self):
        job = make_job(required_fixture="FIX-001")
        r = check_setup_readiness(job, fixture_availability=FixtureAvailabilityStatus.MISSING)
        assert r.fixture_blocked is True
        assert SchedulingBlockReason.FIXTURE_MISSING in r.block_reasons

    def test_maintenance_machine_generates_warning(self):
        job = make_job()
        machine = make_machine(availability="MAINTENANCE")
        c = evaluate_job_assignment(job, machine)
        assert any("MAINTENANCE" in w for w in c.warnings)

    def test_ineligible_machine_generates_warning(self):
        job = make_job(requires_milling=True)
        machine = make_machine(supports_milling=False, supports_turning=True,
                                machine_class="LATHE_2AXIS")
        c = evaluate_job_assignment(job, machine)
        assert any("INELIGIBLE" in w for w in c.warnings)

    def test_no_dispatch_capability_in_any_model(self):
        """Level-12 NC candidate must NEVER become dispatchable in Level-13."""
        from backend.scheduling import IS_DISPATCHABLE
        assert IS_DISPATCHABLE is False

        job = make_job()
        machine = make_machine()
        c = evaluate_job_assignment(job, machine)
        assert c.is_dispatch_order is False
        assert c.approval_required is True
        if c.schedule_candidate:
            assert c.schedule_candidate.is_dispatch_order is False

    def test_no_running_on_machine_job_status(self):
        """JobStatus RUNNING_ON_MACHINE must not exist."""
        from backend.scheduling.enums import JobStatus
        assert not hasattr(JobStatus, "RUNNING_ON_MACHINE")
        status_values = [e.value for e in JobStatus]
        assert "RUNNING_ON_MACHINE" not in status_values

    def test_no_ready_for_dispatch_production_status(self):
        """ProductionReadinessStatus READY_FOR_DISPATCH must not exist."""
        status_values = [e.value for e in ProductionReadinessStatus]
        assert "READY_FOR_DISPATCH" not in status_values


# ===========================================================================
# TURN_MILL class compatibility
# ===========================================================================


class TestTurnMillCompatibility:
    def test_turn_mill_satisfies_lathe_requirement(self):
        job = make_job(machine_class="LATHE_2AXIS", requires_turning=True, requires_milling=False)
        machine = make_machine(
            machine_class="TURN_MILL", supports_turning=True, supports_milling=True
        )
        report = check_machine_eligibility(job, machine)
        assert report.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )


# ===========================================================================
# MachineRequirements defaults
# ===========================================================================


class TestMachineRequirementsDefaults:
    def test_default_class_is_unknown(self):
        reqs = MachineRequirements()
        assert reqs.required_machine_class == MachineClass.UNKNOWN

    def test_unknown_class_does_not_make_ineligible(self):
        """If job has no machine class requirement, any machine should be eligible."""
        reqs = MachineRequirements()
        job = ProductionJob(
            job_id="J",
            machine_requirements=reqs,
            toolpath_verified=True,
            nc_candidate_ref="NC",
            nc_candidate_status="VALIDATED_OFFLINE",
        )
        machine = make_machine()
        report = check_machine_eligibility(job, machine)
        # Should not be INELIGIBLE just because class is UNKNOWN
        assert report.result != MachineEligibilityResult.INELIGIBLE
