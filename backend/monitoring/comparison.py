"""
Level-15 Planned vs Actual Comparison.

Planned values come from upstream levels (Level-7 cycle time, etc.).
Actual values MUST come from ProductionObservation.
planned != actual — they must remain separate.
"""

from __future__ import annotations

import uuid

from .enums import DataQuality, DeviationType
from .models import (
    PlannedActualComparison,
    ProcessDeviation,
    ProductionObservation,
)


def _uid() -> str:
    return str(uuid.uuid4())


def compare_planned_actual(
    observation: ProductionObservation,
    planned_cycle_time: float | None = None,
    planned_cutting_time: float | None = None,
    planned_setup_time: float | None = None,
    planned_tool_usage: float | None = None,
    planned_quantity: int | None = None,
    planned_machine: str | None = None,
    planned_nc_hash: str | None = None,
) -> PlannedActualComparison:
    """
    Build a PlannedActualComparison from one observation and planned data.

    Does NOT derive actual from planned.
    Does NOT fabricate deltas when either side is missing.
    """
    warnings: list[str] = []
    deviations: list[str] = []

    # Cycle time delta
    ct_delta: float | None = None
    ct_rel_delta: float | None = None
    if (
        observation.actual_cycle_time is not None
        and planned_cycle_time is not None
    ):
        if planned_cycle_time > 0:
            ct_delta = observation.actual_cycle_time - planned_cycle_time
            ct_rel_delta = ct_delta / planned_cycle_time
        else:
            warnings.append("PLANNED_CYCLE_TIME_ZERO_OR_NEGATIVE")

    # Program hash
    if planned_nc_hash and observation.program_hash:
        if observation.program_hash != planned_nc_hash:
            deviations.append(DeviationType.PROGRAM_MISMATCH.value)

    # Machine assignment
    if planned_machine and planned_machine != observation.machine_id:
        deviations.append(DeviationType.MACHINE_ASSIGNMENT_MISMATCH.value)

    quality = DataQuality.RAW
    if observation.actual_cycle_time is None and planned_cycle_time is None:
        quality = DataQuality.UNKNOWN

    return PlannedActualComparison(
        comparison_id=_uid(),
        observation_ref=observation.observation_id,
        job_ref=observation.job_id,
        machine_ref=observation.machine_id,
        operation_ref=observation.operation_ref,
        planned_cycle_time=planned_cycle_time,
        actual_cycle_time=observation.actual_cycle_time,
        cycle_time_delta=ct_delta,
        cycle_time_relative_delta=ct_rel_delta,
        planned_cutting_time=planned_cutting_time,
        actual_cutting_time=observation.cutting_runtime,
        planned_setup_time=planned_setup_time,
        planned_tool_usage=planned_tool_usage,
        actual_tool_usage=observation.tool_usage_time,
        planned_quantity=planned_quantity,
        actual_completed_quantity=observation.good_count,
        planned_machine=planned_machine,
        actual_machine=observation.machine_id,
        planned_nc_hash=planned_nc_hash,
        observed_program_hash=observation.program_hash,
        deviations=deviations,
        data_quality=quality,
        warnings=warnings,
    )


def detect_cycle_time_deviations(
    comparison: PlannedActualComparison,
    high_threshold: float = 0.1,
    low_threshold: float = -0.1,
) -> list[ProcessDeviation]:
    """
    Detect cycle-time deviations based on policy thresholds.

    Thresholds are configuration-driven, not hard-coded defaults.
    """
    results: list[ProcessDeviation] = []

    if comparison.cycle_time_relative_delta is None:
        return results

    rel = comparison.cycle_time_relative_delta
    ct_delta = comparison.cycle_time_delta

    if rel > high_threshold:
        results.append(
            ProcessDeviation(
                deviation_id=_uid(),
                deviation_type=DeviationType.CYCLE_TIME_HIGH,
                comparison_ref=comparison.comparison_id,
                observation_ref=comparison.observation_ref,
                absolute_delta=ct_delta,
                relative_delta=rel,
                threshold_used=high_threshold,
                evidence=(
                    f"actual={comparison.actual_cycle_time} "
                    f"planned={comparison.planned_cycle_time}"
                ),
                is_confirmed=False,
            )
        )
    elif rel < low_threshold:
        results.append(
            ProcessDeviation(
                deviation_id=_uid(),
                deviation_type=DeviationType.CYCLE_TIME_LOW,
                comparison_ref=comparison.comparison_id,
                observation_ref=comparison.observation_ref,
                absolute_delta=ct_delta,
                relative_delta=rel,
                threshold_used=low_threshold,
                evidence=(
                    f"actual={comparison.actual_cycle_time} "
                    f"planned={comparison.planned_cycle_time}"
                ),
                is_confirmed=False,
            )
        )

    return results


def detect_process_deviations(
    comparison: PlannedActualComparison,
    idle_time_share_threshold: float = 0.4,
    alarm_time_share_threshold: float = 0.1,
) -> list[ProcessDeviation]:
    """
    Detect process-level deviations.

    Returns deviation list; always CANDIDATE, never confirmed root cause.
    """
    results: list[ProcessDeviation] = []

    # Program mismatch
    if DeviationType.PROGRAM_MISMATCH.value in comparison.deviations:
        results.append(
            ProcessDeviation(
                deviation_id=_uid(),
                deviation_type=DeviationType.PROGRAM_MISMATCH,
                comparison_ref=comparison.comparison_id,
                observation_ref=comparison.observation_ref,
                evidence=(
                    f"planned_hash={comparison.planned_nc_hash} "
                    f"observed_hash={comparison.observed_program_hash}"
                ),
            )
        )

    # Machine assignment mismatch
    if DeviationType.MACHINE_ASSIGNMENT_MISMATCH.value in comparison.deviations:
        results.append(
            ProcessDeviation(
                deviation_id=_uid(),
                deviation_type=DeviationType.MACHINE_ASSIGNMENT_MISMATCH,
                comparison_ref=comparison.comparison_id,
                observation_ref=comparison.observation_ref,
                evidence=(
                    f"planned={comparison.planned_machine} "
                    f"actual={comparison.actual_machine}"
                ),
            )
        )

    return results
