"""Level-17 workload estimation for machine assignment ranking.

Workload is estimated from queue depth — never fabricated.
UNKNOWN queue → UNKNOWN workload (fail-closed).
"""

from __future__ import annotations

from .enums import WorkloadStatus
from .models import WorkloadEstimate

# Queue-depth thresholds for workload classification
_QUEUE_LOW_MAX = 1
_QUEUE_MODERATE_MAX = 3
_QUEUE_HIGH_MAX = 6


def estimate_workload(
    machine_id: str,
    queue_depth: int | None,
    estimated_cycle_time_min: float | None = None,
) -> WorkloadEstimate:
    """Estimate workload for a machine based on queue depth.

    queue_depth=None → UNKNOWN (fail-closed, not assumed LOW).
    queue_depth=0 → LOW.
    is_fabricated is always False.
    """
    if queue_depth is None:
        return WorkloadEstimate(
            machine_id=machine_id,
            queue_depth=0,
            estimated_cycle_time_min=estimated_cycle_time_min,
            workload_status=WorkloadStatus.UNKNOWN,
            is_fabricated=False,
        )

    if queue_depth <= _QUEUE_LOW_MAX:
        status = WorkloadStatus.LOW
    elif queue_depth <= _QUEUE_MODERATE_MAX:
        status = WorkloadStatus.MODERATE
    elif queue_depth <= _QUEUE_HIGH_MAX:
        status = WorkloadStatus.HIGH
    else:
        status = WorkloadStatus.OVERLOADED

    return WorkloadEstimate(
        machine_id=machine_id,
        queue_depth=queue_depth,
        estimated_cycle_time_min=estimated_cycle_time_min,
        workload_status=status,
        is_fabricated=False,
    )


def workload_score(status: WorkloadStatus) -> float:
    """Return a 0–1 score for workload suitability (higher = better for assignment)."""
    return {
        WorkloadStatus.LOW: 1.0,
        WorkloadStatus.MODERATE: 0.75,
        WorkloadStatus.HIGH: 0.4,
        WorkloadStatus.OVERLOADED: 0.1,
        WorkloadStatus.UNKNOWN: 0.5,
    }[status]
