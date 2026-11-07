"""
Level-13 Machine Scheduling — resource conflict detection.

Fail-closed: overlapping assignments are always flagged.
"""

from __future__ import annotations

from .enums import ResourceConflictType
from .models import JobAssignmentCandidate, PlanningReservation, ResourceConflict


def detect_conflicts(
    candidates: list[JobAssignmentCandidate] | None = None,
    reservations: list[PlanningReservation] | None = None,
) -> list[ResourceConflict]:
    """
    Detect scheduling conflicts across assignment candidates and reservations.

    Checks:
    - Machine double-booking (same machine_id in multiple active assignments)
    - Fixture double-booking (same fixture_ref in multiple jobs)
    - Tool reservation conflicts (same tool in multiple jobs)
    - Maintenance overlap (machine marked maintenance + assigned)

    Returns list of ResourceConflict.  Empty = no conflicts detected.
    """
    conflicts: list[ResourceConflict] = []
    all_items = list(candidates or []) + list(reservations or [])

    # --- machine double-booking ---
    machine_jobs: dict[str, list[str]] = {}
    for item in all_items:
        machine_id = item.machine_id if isinstance(item, PlanningReservation) else item.machine_ref
        job_id = item.job_id if isinstance(item, PlanningReservation) else item.job_ref
        machine_jobs.setdefault(machine_id, []).append(job_id)

    for machine_id, job_ids in machine_jobs.items():
        unique = list(dict.fromkeys(job_ids))
        if len(unique) > 1:
            conflicts.append(ResourceConflict(
                conflict_type=ResourceConflictType.MACHINE_DOUBLE_BOOKING,
                resource_id=machine_id,
                job_ids=unique,
                description=f"Machine {machine_id!r} assigned to {len(unique)} jobs simultaneously",
                severity="ERROR",
            ))

    # --- fixture double-booking ---
    fixture_jobs: dict[str, list[str]] = {}
    for item in all_items:
        if isinstance(item, PlanningReservation):
            fixture_id = item.fixture_id
            job_id = item.job_id
        else:
            fixture_id = item.fixture_ref
            job_id = item.job_ref
        if fixture_id:
            fixture_jobs.setdefault(fixture_id, []).append(job_id)

    for fixture_id, job_ids in fixture_jobs.items():
        unique = list(dict.fromkeys(job_ids))
        if len(unique) > 1:
            conflicts.append(ResourceConflict(
                conflict_type=ResourceConflictType.FIXTURE_DOUBLE_BOOKING,
                resource_id=fixture_id,
                job_ids=unique,
                description=f"Fixture {fixture_id!r} required by {len(unique)} jobs simultaneously",
                severity="ERROR",
            ))

    # --- tool reservation conflicts ---
    tool_jobs: dict[str, list[str]] = {}
    for item in all_items:
        if isinstance(item, PlanningReservation):
            tool_ids = item.tool_ids
            job_id = item.job_id
        else:
            tool_ids = item.tool_refs
            job_id = item.job_ref
        for tool_id in tool_ids:
            tool_jobs.setdefault(tool_id, []).append(job_id)

    for tool_id, job_ids in tool_jobs.items():
        unique = list(dict.fromkeys(job_ids))
        if len(unique) > 1:
            conflicts.append(ResourceConflict(
                conflict_type=ResourceConflictType.TOOL_RESERVATION_CONFLICT,
                resource_id=tool_id,
                job_ids=unique,
                description=f"Tool {tool_id!r} reserved for {len(unique)} jobs simultaneously",
                severity="WARNING",
            ))

    # --- maintenance overlap (from candidates) ---
    for item in candidates or []:
        if (
            item.eligibility_report
            and item.eligibility_report.warnings
            and any("MAINTENANCE" in w for w in item.eligibility_report.warnings)
        ):
            conflicts.append(ResourceConflict(
                conflict_type=ResourceConflictType.MAINTENANCE_OVERLAP,
                resource_id=item.machine_ref,
                job_ids=[item.job_ref],
                description=f"Machine {item.machine_ref!r} has maintenance warning",
                severity="ERROR",
            ))

    return conflicts
