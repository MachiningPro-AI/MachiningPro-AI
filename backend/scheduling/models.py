"""
Level-13 Machine Scheduling and Job Assignment — data models.

NO_CNC_DISPATCH=YES
NO_AUTO_ASSIGNMENT=YES
APPROVAL_REQUIRED=YES
UNKNOWN_IS_NOT_AVAILABLE=YES
NO_FABRICATED_DATA=YES
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import (
    CalendarEventType,
    ChangeoverRequired,
    DueDateStatus,
    DurationStatus,
    EligibilityFailReason,
    FixtureAvailabilityStatus,
    HolderAvailabilityStatus,
    JobPriority,
    JobStatus,
    MachineAvailabilityStatus,
    MachineClass,
    MachineEligibilityResult,
    NCReadinessStatus,
    PrioritySource,
    ProductionReadinessStatus,
    ReservationStatus,
    ResourceConflictType,
    ResourceDataSource,
    SchedulingAlgorithm,
    SchedulingBlockReason,
    SchedulingObjective,
    SetupReadinessStatus,
    ToolAvailabilityStatus,
)

# ---------------------------------------------------------------------------
# Machine requirements (from job/process plan)
# ---------------------------------------------------------------------------

class MachineRequirements(BaseModel):
    """Machine capability requirements derived from job/process plan."""
    required_machine_class: MachineClass = MachineClass.UNKNOWN
    required_axis_count: int | None = None          # None = unknown
    required_x_travel_mm: float | None = None
    required_y_travel_mm: float | None = None
    required_z_travel_mm: float | None = None
    required_spindle_speed_rpm: float | None = None
    required_spindle_power_kw: float | None = None
    requires_turning: bool = False
    requires_milling: bool = False
    required_post_profile_id: str | None = None
    required_controller_family: str | None = None
    max_workpiece_mass_kg: float | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Production Job
# ---------------------------------------------------------------------------

class ProductionJob(BaseModel):
    """
    A production job representing work to be scheduled and assigned to a machine.

    status transitions:
      DRAFT → ENGINEERING_INCOMPLETE | READY_FOR_SCHEDULING
      READY_FOR_SCHEDULING → SCHEDULING_BLOCKED | SCHEDULED_CANDIDATE
      SCHEDULED_CANDIDATE → ASSIGNMENT_REVIEW_REQUIRED
      ASSIGNMENT_REVIEW_REQUIRED → APPROVED_FOR_DISPATCH_FUTURE | CANCELLED

    RUNNING_ON_MACHINE is NOT present — not authorised at Level 13.
    """

    job_id: str
    part_reference: str | None = None
    revision: str | None = None
    quantity: int = 1
    priority: JobPriority = JobPriority.NORMAL
    priority_source: PrioritySource = PrioritySource.USER_DEFINED
    due_date: str | None = None           # ISO 8601 date string; None = unknown
    due_date_status: DueDateStatus = DueDateStatus.UNKNOWN
    release_date: str | None = None

    # upstream references
    process_plan_ref: str | None = None
    cam_plan_ref: str | None = None
    toolpath_ref: str | None = None
    toolpath_verified: bool = False
    nc_candidate_ref: str | None = None
    nc_candidate_status: str | None = None   # maps to NCProgramStatus string
    nc_candidate_stale: bool = False

    # machine requirements
    machine_requirements: MachineRequirements = Field(
        default_factory=MachineRequirements
    )

    # required resources
    required_tools: list[str] = Field(default_factory=list)
    required_holders: list[str] = Field(default_factory=list)
    required_fixture: str | None = None
    required_setup: str | None = None

    # time estimates — from upstream Level-7 cycle time; never fabricated
    estimated_cycle_time_min: float | None = None
    setup_time_min: float | None = None

    status: JobStatus = JobStatus.DRAFT
    warnings: list[str] = Field(default_factory=list)
    evidence: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Machine Resource
# ---------------------------------------------------------------------------

class MachineResource(BaseModel):
    """
    A production machine resource available for scheduling evaluation.

    UNKNOWN availability != AVAILABLE.
    Machine compatibility check is separate from availability check.
    Data source must be explicit — no fabricated machine data.
    """

    machine_id: str
    machine_name: str
    machine_class: MachineClass = MachineClass.UNKNOWN
    source: ResourceDataSource = ResourceDataSource.UNKNOWN

    # capabilities (None = unknown)
    axis_count: int | None = None
    x_travel_mm: float | None = None
    y_travel_mm: float | None = None
    z_travel_mm: float | None = None
    spindle_speed_max_rpm: float | None = None
    spindle_power_kw: float | None = None
    table_load_capacity_kg: float | None = None
    chuck_capacity_mm: float | None = None
    supports_turning: bool = False
    supports_milling: bool = True
    controller_family: str | None = None
    supported_post_profile_ids: list[str] = Field(default_factory=list)

    # availability — UNKNOWN by default; must be asserted explicitly
    availability_status: MachineAvailabilityStatus = MachineAvailabilityStatus.UNKNOWN
    maintenance_status: str | None = None

    # current state
    current_job_id: str | None = None

    # available tooling/fixtures at this machine
    available_tool_ids: list[str] = Field(default_factory=list)
    installed_fixture_id: str | None = None
    fixture_capabilities: list[str] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    status: str = "ACTIVE"


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

class MachineCalendarEvent(BaseModel):
    machine_id: str
    event_type: CalendarEventType = CalendarEventType.UNKNOWN
    start_iso: str | None = None   # ISO 8601
    end_iso: str | None = None
    job_id: str | None = None
    description: str | None = None


class MachineCalendar(BaseModel):
    machine_id: str
    events: list[MachineCalendarEvent] = Field(default_factory=list)

    def has_blocking_event(self, event_types: list[CalendarEventType]) -> bool:
        return any(e.event_type in event_types for e in self.events)

    def has_maintenance(self) -> bool:
        return self.has_blocking_event([
            CalendarEventType.MAINTENANCE,
            CalendarEventType.PLANNED_DOWNTIME,
        ])


# ---------------------------------------------------------------------------
# Queue
# ---------------------------------------------------------------------------

class MachineQueueEntry(BaseModel):
    job_id: str
    queue_position: int
    estimated_duration_min: float | None = None
    planned_start_iso: str | None = None
    planned_finish_iso: str | None = None
    duration_status: DurationStatus = DurationStatus.UNKNOWN
    status: str = "QUEUED"


class MachineQueue(BaseModel):
    machine_id: str
    entries: list[MachineQueueEntry] = Field(default_factory=list)

    @property
    def total_known_duration_min(self) -> float | None:
        mins = [e.estimated_duration_min for e in self.entries if e.estimated_duration_min]
        return sum(mins) if mins else None

    @property
    def depth(self) -> int:
        return len(self.entries)


# ---------------------------------------------------------------------------
# Resource availability
# ---------------------------------------------------------------------------

class ToolAvailability(BaseModel):
    tool_id: str
    status: ToolAvailabilityStatus = ToolAvailabilityStatus.UNKNOWN
    located_at_machine_id: str | None = None
    reserved_for_job_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class HolderAvailability(BaseModel):
    holder_id: str
    status: HolderAvailabilityStatus = HolderAvailabilityStatus.UNKNOWN
    reserved_for_job_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


class FixtureAvailability(BaseModel):
    fixture_id: str
    status: FixtureAvailabilityStatus = FixtureAvailabilityStatus.UNKNOWN
    installed_at_machine_id: str | None = None
    reserved_for_job_id: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Duration estimate
# ---------------------------------------------------------------------------

class DurationEstimate(BaseModel):
    """Duration estimate from Level-7 cycle time evidence. Never fabricated."""
    setup_time_min: float | None = None
    cycle_time_per_part_min: float | None = None
    quantity: int = 1
    total_estimated_min: float | None = None
    status: DurationStatus = DurationStatus.UNKNOWN
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @classmethod
    def from_job(cls, job: ProductionJob) -> DurationEstimate:
        setup = job.setup_time_min
        cycle = job.estimated_cycle_time_min
        qty = max(job.quantity, 1)
        if setup is not None and cycle is not None:
            total = setup + cycle * qty
            return cls(
                setup_time_min=setup,
                cycle_time_per_part_min=cycle,
                quantity=qty,
                total_estimated_min=total,
                status=DurationStatus.KNOWN,
            )
        elif setup is not None or cycle is not None:
            partial_total = (setup or 0.0) + (cycle or 0.0) * qty
            return cls(
                setup_time_min=setup,
                cycle_time_per_part_min=cycle,
                quantity=qty,
                total_estimated_min=partial_total,
                status=DurationStatus.PARTIAL,
                warnings=["Duration is partial — some components unknown"],
            )
        return cls(
            quantity=qty,
            status=DurationStatus.UNKNOWN,
            warnings=["Duration unknown — no cycle or setup time data"],
        )


# ---------------------------------------------------------------------------
# Changeover
# ---------------------------------------------------------------------------

class ChangeoverPenalty(BaseModel):
    """Changeover evidence model. No fabricated minutes."""
    fixture_change_required: ChangeoverRequired = ChangeoverRequired.UNKNOWN
    tool_set_change_required: ChangeoverRequired = ChangeoverRequired.UNKNOWN
    material_change_required: ChangeoverRequired = ChangeoverRequired.UNKNOWN
    overall: ChangeoverRequired = ChangeoverRequired.UNKNOWN
    estimated_minutes: float | None = None   # None unless explicitly provided
    evidence: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Eligibility
# ---------------------------------------------------------------------------

class EligibilityCheckResult(BaseModel):
    check_name: str
    passed: bool
    fail_reason: EligibilityFailReason | None = None
    detail: str = ""


class EligibilityReport(BaseModel):
    machine_id: str = ""
    result: MachineEligibilityResult = MachineEligibilityResult.UNKNOWN
    checks: list[EligibilityCheckResult] = Field(default_factory=list)
    hard_constraint_failures: list[EligibilityFailReason] = Field(default_factory=list)
    soft_preference_score: float = 0.0   # higher = more preferred
    unknown_data_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# NC Readiness
# ---------------------------------------------------------------------------

class NCReadiness(BaseModel):
    status: NCReadinessStatus = NCReadinessStatus.UNKNOWN
    nc_candidate_ref: str | None = None
    nc_candidate_status: str | None = None
    toolpath_verified: bool = False
    is_stale: bool = False
    block_reasons: list[SchedulingBlockReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Setup Readiness
# ---------------------------------------------------------------------------

class SetupReadiness(BaseModel):
    status: SetupReadinessStatus = SetupReadinessStatus.UNKNOWN
    tool_statuses: dict[str, ToolAvailabilityStatus] = Field(default_factory=dict)
    holder_statuses: dict[str, HolderAvailabilityStatus] = Field(default_factory=dict)
    fixture_status: FixtureAvailabilityStatus = FixtureAvailabilityStatus.UNKNOWN
    missing_tools: list[str] = Field(default_factory=list)
    missing_holders: list[str] = Field(default_factory=list)
    fixture_blocked: bool = False
    block_reasons: list[SchedulingBlockReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Production Readiness
# ---------------------------------------------------------------------------

class ProductionReadiness(BaseModel):
    status: ProductionReadinessStatus = ProductionReadinessStatus.UNKNOWN
    engineering_complete: bool = False
    cam_ready: bool = False
    toolpath_verified: bool = False
    nc_readiness: NCReadiness = Field(default_factory=NCReadiness)
    machine_eligible: bool = False
    setup_readiness: SetupReadiness = Field(default_factory=SetupReadiness)
    schedule_slot_available: bool = False
    block_reasons: list[SchedulingBlockReason] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # APPROVAL_REQUIRED is always True
    approval_required: bool = True


# ---------------------------------------------------------------------------
# Scheduling objective config
# ---------------------------------------------------------------------------

class SchedulingObjectiveConfig(BaseModel):
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.FIFO
    objective: SchedulingObjective = SchedulingObjective.EARLIEST_COMPLETION
    assumptions: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Schedule Candidate
# ---------------------------------------------------------------------------

class ScheduleCandidate(BaseModel):
    """
    A candidate schedule slot for a job on a machine.

    This is a CANDIDATE only — not a machine execution order.
    APPROVAL_REQUIRED=True always.
    """

    job_id: str
    machine_id: str
    queue_position: int | None = None
    planned_start_iso: str | None = None   # None when calendar/queue unknown
    planned_finish_iso: str | None = None
    duration: DurationEstimate = Field(default_factory=DurationEstimate)
    objective: SchedulingObjectiveConfig = Field(
        default_factory=SchedulingObjectiveConfig
    )
    score_components: dict[str, float] = Field(default_factory=dict)
    hard_constraint_results: list[EligibilityCheckResult] = Field(default_factory=list)
    soft_preference_results: dict[str, float] = Field(default_factory=dict)
    readiness: ProductionReadiness = Field(default_factory=ProductionReadiness)
    changeover: ChangeoverPenalty = Field(default_factory=ChangeoverPenalty)
    lateness_min: float | None = None    # None when due date or finish unknown
    warnings: list[str] = Field(default_factory=list)
    # invariants
    is_dispatch_order: bool = False
    approval_required: bool = True


# ---------------------------------------------------------------------------
# Job Assignment Candidate
# ---------------------------------------------------------------------------

class JobAssignmentCandidate(BaseModel):
    """
    A recommended machine assignment candidate for a production job.

    This is a CANDIDATE only — APPROVAL_REQUIRED=True always.
    Not a machine execution order. Not a dispatch command.
    """

    job_ref: str
    machine_ref: str
    setup_ref: str | None = None
    nc_candidate_ref: str | None = None
    tool_refs: list[str] = Field(default_factory=list)
    fixture_ref: str | None = None
    schedule_candidate: ScheduleCandidate | None = None
    eligibility_report: EligibilityReport = Field(default_factory=EligibilityReport)
    setup_readiness: SetupReadiness = Field(default_factory=SetupReadiness)
    nc_readiness: NCReadiness = Field(default_factory=NCReadiness)
    readiness: ProductionReadiness = Field(default_factory=ProductionReadiness)
    # why this machine was chosen
    eligibility_reasons: list[str] = Field(default_factory=list)
    preference_reasons: list[str] = Field(default_factory=list)
    unknown_data: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    # invariants
    approval_required: bool = True
    is_dispatch_order: bool = False


# ---------------------------------------------------------------------------
# Planning Reservation
# ---------------------------------------------------------------------------

class PlanningReservation(BaseModel):
    """Temporary planning reservation — PLANNING_ONLY, no MES/ERP write."""
    reservation_id: str
    job_id: str
    machine_id: str
    tool_ids: list[str] = Field(default_factory=list)
    fixture_id: str | None = None
    planned_start_iso: str | None = None
    planned_finish_iso: str | None = None
    status: ReservationStatus = ReservationStatus.PLANNING_ONLY
    created_at: str | None = None
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Resource conflict
# ---------------------------------------------------------------------------

class ResourceConflict(BaseModel):
    conflict_type: ResourceConflictType
    resource_id: str
    job_ids: list[str] = Field(default_factory=list)
    description: str = ""
    severity: str = "ERROR"


# ---------------------------------------------------------------------------
# Queue schedule result
# ---------------------------------------------------------------------------

class QueueScheduleResult(BaseModel):
    machine_id: str
    algorithm: SchedulingAlgorithm
    objective: SchedulingObjective
    ordered_job_ids: list[str] = Field(default_factory=list)
    queue_entries: list[MachineQueueEntry] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
