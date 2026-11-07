"""
Level-13 Machine Scheduling — scheduling algorithms and candidate creation.

Supported algorithms: FIFO, EDD, SPT, PRIORITY_FIRST.
Every result reports algorithm, objective, inputs, constraints and assumptions.
Schedules are CANDIDATES only — not machine execution orders.
APPROVAL_REQUIRED=True always.

NO_CNC_DISPATCH=YES
NO_FABRICATED_DATA=YES
UNKNOWN_IS_NOT_AVAILABLE=YES
"""

from __future__ import annotations

from .eligibility import check_machine_eligibility, rank_eligible_machines
from .enums import (
    MachineAvailabilityStatus,
    MachineEligibilityResult,
    SchedulingAlgorithm,
    SchedulingObjective,
)
from .models import (
    DurationEstimate,
    EligibilityReport,
    JobAssignmentCandidate,
    MachineQueue,
    MachineQueueEntry,
    MachineResource,
    ProductionJob,
    QueueScheduleResult,
    ScheduleCandidate,
    SchedulingObjectiveConfig,
)
from .readiness import check_nc_readiness, check_production_readiness, check_setup_readiness

# Priority ordering for PRIORITY_FIRST algorithm
_PRIORITY_ORDER = {"URGENT": 0, "HIGH": 1, "NORMAL": 2, "LOW": 3}


def evaluate_machine_candidates(
    job: ProductionJob,
    machines: list[MachineResource],
    queue_depths: dict[str, int] | None = None,
) -> list[EligibilityReport]:
    """
    Evaluate all machines for a job and return ranked eligible candidates.

    INELIGIBLE machines are included in the returned list (at the end, unranked)
    so that callers can explain rejected candidates (MUST 21).

    Availability is checked separately — UNKNOWN != AVAILABLE.
    Eligibility and availability are independent checks (HARD RULE 20).
    """
    reports = []
    for machine in machines:
        report = check_machine_eligibility(job, machine)
        reports.append(report)

    eligible = [
        r for r in reports
        if r.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )
    ]
    ranked = rank_eligible_machines(eligible, queue_depths)
    ineligible = [
        r for r in reports
        if r.result == MachineEligibilityResult.INELIGIBLE
    ]
    unknown = [
        r for r in reports
        if r.result == MachineEligibilityResult.UNKNOWN
    ]

    # Return: ranked eligible first, then unknown, then ineligible
    return ranked + unknown + ineligible


def create_schedule_candidate(
    job: ProductionJob,
    machine: MachineResource,
    queue: MachineQueue | None = None,
    objective_config: SchedulingObjectiveConfig | None = None,
    tool_availability: dict | None = None,
    holder_availability: dict | None = None,
    fixture_availability=None,
) -> ScheduleCandidate:
    """
    Create a ScheduleCandidate for a job on a machine.

    planned_start/finish are UNKNOWN when calendar/queue data is absent.
    Result is CANDIDATE only — not a dispatch order.
    approval_required=True always.
    """
    obj_cfg = objective_config or SchedulingObjectiveConfig()
    eligibility = check_machine_eligibility(job, machine)
    nc_r = check_nc_readiness(job)
    setup_r = check_setup_readiness(
        job, tool_availability, holder_availability, fixture_availability
    )

    machine_eligible = eligibility.result in (
        MachineEligibilityResult.ELIGIBLE,
        MachineEligibilityResult.PARTIALLY_ELIGIBLE,
    )
    queue_depth = queue.depth if queue else 0
    readiness = check_production_readiness(
        job,
        machine_eligible=machine_eligible,
        schedule_slot_available=(queue is not None),
        nc_readiness=nc_r,
        setup_readiness=setup_r,
    )

    duration = DurationEstimate.from_job(job)
    warnings: list[str] = []

    # Availability is independent from eligibility — UNKNOWN != AVAILABLE
    if machine.availability_status == MachineAvailabilityStatus.UNKNOWN:
        warnings.append("Machine availability UNKNOWN — cannot confirm schedule slot")
    elif machine.availability_status != MachineAvailabilityStatus.AVAILABLE:
        warnings.append(
            f"Machine availability is {machine.availability_status} — slot not confirmed"
        )

    # Planned start/finish — only when calendar+queue+duration are known
    planned_start: str | None = None
    planned_finish: str | None = None
    # (Full calendar arithmetic is deferred to a future level with real calendar data)

    # Lateness: only when both planned_finish and due_date are known
    lateness_min: float | None = None

    # Score components (soft preferences)
    score: dict[str, float] = {
        "eligibility": 1.0 if eligibility.result == MachineEligibilityResult.ELIGIBLE else 0.5,
        "soft_preference": eligibility.soft_preference_score,
        "queue_depth_penalty": -queue_depth * 0.1,
    }

    return ScheduleCandidate(
        job_id=job.job_id,
        machine_id=machine.machine_id,
        queue_position=queue_depth + 1 if queue is not None else None,
        planned_start_iso=planned_start,
        planned_finish_iso=planned_finish,
        duration=duration,
        objective=obj_cfg,
        score_components=score,
        hard_constraint_results=eligibility.checks,
        soft_preference_results={
            "queue_depth": float(queue_depth),
            "post_profile_match": eligibility.soft_preference_score,
        },
        readiness=readiness,
        lateness_min=lateness_min,
        warnings=warnings,
        is_dispatch_order=False,
        approval_required=True,
    )


def evaluate_job_assignment(
    job: ProductionJob,
    machine: MachineResource,
    queue: MachineQueue | None = None,
    objective_config: SchedulingObjectiveConfig | None = None,
    tool_availability: dict | None = None,
    holder_availability: dict | None = None,
    fixture_availability=None,
) -> JobAssignmentCandidate:
    """
    Build a JobAssignmentCandidate explaining the assignment rationale.

    Returns CANDIDATE with APPROVAL_REQUIRED=True.
    Not a dispatch order.
    """
    eligibility = check_machine_eligibility(job, machine)
    nc_r = check_nc_readiness(job)
    setup_r = check_setup_readiness(
        job, tool_availability, holder_availability, fixture_availability
    )
    machine_eligible = eligibility.result in (
        MachineEligibilityResult.ELIGIBLE,
        MachineEligibilityResult.PARTIALLY_ELIGIBLE,
    )
    readiness = check_production_readiness(
        job,
        machine_eligible=machine_eligible,
        schedule_slot_available=(queue is not None),
        nc_readiness=nc_r,
        setup_readiness=setup_r,
    )

    schedule_cand = create_schedule_candidate(
        job, machine, queue, objective_config,
        tool_availability, holder_availability, fixture_availability,
    )

    # Build rationale
    eligibility_reasons = [
        c.detail for c in eligibility.checks if c.passed
    ]
    preference_reasons = []
    if eligibility.soft_preference_score > 0:
        preference_reasons.append(
            f"Soft preference score: {eligibility.soft_preference_score:.2f}"
        )
    if machine.availability_status == MachineAvailabilityStatus.AVAILABLE:
        preference_reasons.append("Machine is available")

    unknown_data = list(eligibility.unknown_data_fields)
    if nc_r.block_reasons:
        unknown_data.append("nc_readiness_blocked")
    if setup_r.status.value in ("UNKNOWN", "BLOCKED"):
        unknown_data.append("setup_readiness_issues")

    warnings: list[str] = []
    if eligibility.result == MachineEligibilityResult.INELIGIBLE:
        warnings.append("Machine is INELIGIBLE — this assignment cannot proceed")
    if machine.availability_status == MachineAvailabilityStatus.MAINTENANCE:
        warnings.append("Machine is under MAINTENANCE — cannot be scheduled")

    return JobAssignmentCandidate(
        job_ref=job.job_id,
        machine_ref=machine.machine_id,
        setup_ref=job.required_setup,
        nc_candidate_ref=job.nc_candidate_ref,
        tool_refs=list(job.required_tools),
        fixture_ref=job.required_fixture,
        schedule_candidate=schedule_cand,
        eligibility_report=eligibility,
        setup_readiness=setup_r,
        nc_readiness=nc_r,
        readiness=readiness,
        eligibility_reasons=eligibility_reasons,
        preference_reasons=preference_reasons,
        unknown_data=unknown_data,
        warnings=warnings,
        approval_required=True,
        is_dispatch_order=False,
    )


def apply_scheduling_algorithm(
    jobs: list[ProductionJob],
    machine_id: str,
    algorithm: SchedulingAlgorithm = SchedulingAlgorithm.FIFO,
    objective: SchedulingObjective = SchedulingObjective.EARLIEST_COMPLETION,
) -> QueueScheduleResult:
    """
    Apply a deterministic scheduling algorithm to order a list of jobs.

    Algorithms:
    - FIFO: order by job_id string (insertion order preserved)
    - EDD: order by due_date ascending (jobs with no due date go last)
    - SPT: order by estimated_cycle_time_min ascending (unknown = last)
    - PRIORITY_FIRST: order URGENT > HIGH > NORMAL > LOW, then FIFO within tier

    Every result reports algorithm, objective, assumptions.
    Result is a CANDIDATE queue — not a machine execution order.
    """
    assumptions: list[str] = []
    warnings: list[str] = []

    if not jobs:
        return QueueScheduleResult(
            machine_id=machine_id,
            algorithm=algorithm,
            objective=objective,
            ordered_job_ids=[],
            queue_entries=[],
            assumptions=["No jobs provided"],
            warnings=[],
        )

    ordered: list[ProductionJob]

    if algorithm == SchedulingAlgorithm.FIFO:
        ordered = list(jobs)
        assumptions.append("FIFO: jobs ordered by submission sequence (original list order)")

    elif algorithm == SchedulingAlgorithm.EDD:
        def edd_key(j: ProductionJob) -> tuple[int, str]:
            if j.due_date:
                return (0, j.due_date)
            return (1, "")  # no due date → go last
        ordered = sorted(jobs, key=edd_key)
        no_due = [j.job_id for j in jobs if not j.due_date]
        if no_due:
            warnings.append(
                f"EDD: {len(no_due)} job(s) have no due date — placed at end: {no_due}"
            )
        assumptions.append("EDD: jobs with earlier due dates are scheduled first")

    elif algorithm == SchedulingAlgorithm.SPT:
        def spt_key(j: ProductionJob) -> tuple[int, float]:
            if j.estimated_cycle_time_min is not None:
                return (0, j.estimated_cycle_time_min)
            return (1, 0.0)  # unknown → go last
        ordered = sorted(jobs, key=spt_key)
        unknown_time = [j.job_id for j in jobs if j.estimated_cycle_time_min is None]
        if unknown_time:
            warnings.append(
                f"SPT: {len(unknown_time)} job(s) have unknown cycle time"
                f" — placed at end: {unknown_time}"
            )
        assumptions.append("SPT: shorter jobs are scheduled first to minimise mean flow time")

    elif algorithm == SchedulingAlgorithm.PRIORITY_FIRST:
        def priority_key(j: ProductionJob) -> tuple[int, str]:
            tier = _PRIORITY_ORDER.get(j.priority, 99)
            return (tier, j.job_id)
        ordered = sorted(jobs, key=priority_key)
        assumptions.append(
            "PRIORITY_FIRST: URGENT > HIGH > NORMAL > LOW, then FIFO within each tier"
        )

    else:
        ordered = list(jobs)
        warnings.append(f"Unknown algorithm {algorithm!r} — falling back to FIFO")
        assumptions.append("Fallback FIFO applied")

    entries: list[MachineQueueEntry] = []
    for pos, j in enumerate(ordered, start=1):
        d_est = DurationEstimate.from_job(j)
        entries.append(MachineQueueEntry(
            job_id=j.job_id,
            queue_position=pos,
            estimated_duration_min=d_est.total_estimated_min,
            duration_status=d_est.status,
        ))

    return QueueScheduleResult(
        machine_id=machine_id,
        algorithm=algorithm,
        objective=objective,
        ordered_job_ids=[j.job_id for j in ordered],
        queue_entries=entries,
        assumptions=assumptions,
        warnings=warnings,
    )
