"""
Level-15 Alarm Analysis.

No root-cause claims from alarm codes alone.
No fabricated alarm descriptions.
Missing alarm data != zero alarms.
"""

from __future__ import annotations

import uuid
from collections import Counter

from .enums import DataQuality, ObservationSource
from .models import AlarmAnalytics, AlarmObservation


def _uid() -> str:
    return str(uuid.uuid4())


def make_alarm_observation(
    alarm_code: str,
    machine_id: str,
    start: str | None = None,
    end: str | None = None,
    duration_seconds: float | None = None,
    alarm_text: str | None = None,
    job_id: str | None = None,
    operation_ref: str | None = None,
    source: ObservationSource = ObservationSource.SIMULATED_CONTROLLER,
) -> AlarmObservation:
    """Create an alarm observation from observed data only."""
    return AlarmObservation(
        alarm_obs_id=_uid(),
        alarm_code=alarm_code,
        alarm_text=alarm_text,
        start=start,
        end=end,
        duration_seconds=duration_seconds,
        machine_id=machine_id,
        job_id=job_id,
        operation_ref=operation_ref,
        source=source,
    )


def analyze_alarms(
    observations: list[AlarmObservation],
    planned_hours: float | None = None,
) -> AlarmAnalytics:
    """
    Aggregate alarm analytics.

    Does NOT claim root cause.
    alarm_frequency_per_hour requires planned_hours > 0.
    """
    if not observations:
        return AlarmAnalytics(
            total_alarm_count=0,
            data_quality=DataQuality.UNKNOWN,
            warnings=["NO_ALARM_DATA — cannot assume zero alarms"],
        )

    total = len(observations)
    code_counts: Counter[str] = Counter()
    op_counts: Counter[str] = Counter()
    total_duration: float = 0.0
    has_duration = False

    for obs in observations:
        code_counts[obs.alarm_code] += 1
        if obs.operation_ref:
            op_counts[obs.operation_ref] += 1
        if obs.duration_seconds is not None:
            total_duration += obs.duration_seconds
            has_duration = True

    # Alarms that appear more than once are repeat candidates
    repeat_candidates = [
        code for code, count in code_counts.items() if count > 1
    ]

    freq: float | None = None
    if planned_hours is not None and planned_hours > 0:
        freq = total / planned_hours

    warnings: list[str] = []
    if not has_duration:
        warnings.append("ALARM_DURATION_UNKNOWN")

    return AlarmAnalytics(
        total_alarm_count=total,
        total_alarm_duration=total_duration if has_duration else None,
        alarm_frequency_per_hour=freq,
        repeat_alarm_candidates=repeat_candidates,
        operation_associated=dict(op_counts),
        data_quality=DataQuality.RAW,
        warnings=warnings,
    )


def detect_alarm_frequency_deviation(
    analytics: AlarmAnalytics,
    threshold_per_hour: float,
) -> bool:
    """Return True when alarm frequency exceeds threshold."""
    if analytics.alarm_frequency_per_hour is None:
        return False
    return analytics.alarm_frequency_per_hour > threshold_per_hour
