"""
Level-13 Machine Scheduling and Job Assignment package.

NO_CNC_DISPATCH=YES
NO_AUTO_ASSIGNMENT=YES
NO_FABRICATED_AVAILABILITY=YES
UNKNOWN_IS_NOT_AVAILABLE=YES
APPROVAL_REQUIRED=YES
"""

from .conflicts import detect_conflicts
from .eligibility import check_machine_eligibility, rank_eligible_machines
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
from .models import (
    DurationEstimate,
    EligibilityCheckResult,
    EligibilityReport,
    FixtureAvailability,
    HolderAvailability,
    JobAssignmentCandidate,
    MachineCalendar,
    MachineCalendarEvent,
    MachineQueue,
    MachineQueueEntry,
    MachineRequirements,
    MachineResource,
    NCReadiness,
    PlanningReservation,
    ProductionJob,
    ProductionReadiness,
    QueueScheduleResult,
    ResourceConflict,
    ScheduleCandidate,
    SchedulingObjectiveConfig,
    SetupReadiness,
    ToolAvailability,
)
from .readiness import (
    check_nc_readiness,
    check_production_readiness,
    check_setup_readiness,
)
from .scheduler import (
    apply_scheduling_algorithm,
    create_schedule_candidate,
    evaluate_job_assignment,
    evaluate_machine_candidates,
)

# Safety invariants
APPROVAL_REQUIRED: bool = True
NO_CNC_DISPATCH: bool = True
IS_DISPATCHABLE: bool = False

__all__ = [
    # enums
    "CalendarEventType",
    "ChangeoverRequired",
    "DueDateStatus",
    "DurationStatus",
    "EligibilityFailReason",
    "FixtureAvailabilityStatus",
    "HolderAvailabilityStatus",
    "JobPriority",
    "JobStatus",
    "MachineAvailabilityStatus",
    "MachineClass",
    "MachineEligibilityResult",
    "NCReadinessStatus",
    "PrioritySource",
    "ProductionReadinessStatus",
    "ReservationStatus",
    "ResourceConflictType",
    "ResourceDataSource",
    "SchedulingAlgorithm",
    "SchedulingBlockReason",
    "SchedulingObjective",
    "SetupReadinessStatus",
    "ToolAvailabilityStatus",
    # models
    "DurationEstimate",
    "EligibilityCheckResult",
    "EligibilityReport",
    "FixtureAvailability",
    "HolderAvailability",
    "JobAssignmentCandidate",
    "MachineCalendar",
    "MachineCalendarEvent",
    "MachineQueue",
    "MachineQueueEntry",
    "MachineRequirements",
    "MachineResource",
    "NCReadiness",
    "PlanningReservation",
    "ProductionJob",
    "ProductionReadiness",
    "QueueScheduleResult",
    "ResourceConflict",
    "ScheduleCandidate",
    "SchedulingObjectiveConfig",
    "SetupReadiness",
    "ToolAvailability",
    # functions
    "apply_scheduling_algorithm",
    "check_machine_eligibility",
    "check_nc_readiness",
    "check_production_readiness",
    "check_setup_readiness",
    "create_schedule_candidate",
    "detect_conflicts",
    "evaluate_job_assignment",
    "evaluate_machine_candidates",
    "rank_eligible_machines",
    # invariants
    "APPROVAL_REQUIRED",
    "IS_DISPATCHABLE",
    "NO_CNC_DISPATCH",
]
