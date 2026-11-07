"""
Level-15 Performance KPI Calculations.

OEE is only calculated when Availability, Performance, and Quality
are all backed by valid production observations.
Missing observations stay None, not zero.
"""

from __future__ import annotations

import math
import uuid

from .enums import DataQuality, OEEStatus
from .models import OEEResult, PerformanceKPIs, ProductionObservation


def _uid() -> str:
    return str(uuid.uuid4())


def compute_availability(
    planned_production_time: float | None,
    run_time: float | None,
) -> float | None:
    """
    Availability = run_time / planned_production_time.

    Returns None when either value is missing or denominator is zero.
    """
    if planned_production_time is None or run_time is None:
        return None
    if planned_production_time <= 0:
        return None
    return run_time / planned_production_time


def compute_performance(
    ideal_cycle_time: float | None,
    total_count: int | None,
    run_time: float | None,
) -> float | None:
    """
    Performance = (ideal_cycle_time × total_count) / run_time.

    ideal_cycle_time must be from a documented valid basis.
    Returns None when any value is missing or denominator is zero.
    """
    if ideal_cycle_time is None or total_count is None or run_time is None:
        return None
    if run_time <= 0 or ideal_cycle_time <= 0:
        return None
    return (ideal_cycle_time * total_count) / run_time


def compute_quality_kpi(
    good_count: int | None,
    total_count: int | None,
) -> float | None:
    """
    Quality KPI = good_count / total_count.

    Returns None when inputs are invalid.
    """
    if good_count is None or total_count is None:
        return None
    if total_count <= 0:
        return None
    return good_count / total_count


def compute_oee(
    machine_id: str | None = None,
    planned_production_time: float | None = None,
    run_time: float | None = None,
    ideal_cycle_time: float | None = None,
    total_count: int | None = None,
    good_count: int | None = None,
) -> OEEResult:
    """
    OEE = Availability × Performance × Quality.

    Returns INSUFFICIENT_DATA when any component is missing.
    Does NOT fabricate OEE.
    """
    oee_id = _uid()
    warnings: list[str] = []

    availability = compute_availability(planned_production_time, run_time)
    performance = compute_performance(ideal_cycle_time, total_count, run_time)
    quality = compute_quality_kpi(good_count, total_count)

    if availability is None:
        warnings.append("AVAILABILITY_MISSING")
    if performance is None:
        warnings.append("PERFORMANCE_MISSING")
    if quality is None:
        warnings.append("QUALITY_MISSING")

    if availability is None or performance is None or quality is None:
        return OEEResult(
            oee_id=oee_id,
            machine_id=machine_id,
            planned_production_time=planned_production_time,
            run_time=run_time,
            availability=availability,
            ideal_cycle_time=ideal_cycle_time,
            total_count=total_count,
            performance=performance,
            good_count=good_count,
            quality=quality,
            oee=None,
            status=OEEStatus.INSUFFICIENT_DATA,
            warnings=warnings,
        )

    oee_value = availability * performance * quality

    return OEEResult(
        oee_id=oee_id,
        machine_id=machine_id,
        planned_production_time=planned_production_time,
        run_time=run_time,
        availability=availability,
        ideal_cycle_time=ideal_cycle_time,
        total_count=total_count,
        performance=performance,
        good_count=good_count,
        quality=quality,
        oee=oee_value,
        status=OEEStatus.CALCULATED,
        warnings=warnings,
    )


def compute_performance_kpis(
    observations: list[ProductionObservation],
    machine_id: str | None = None,
    job_id: str | None = None,
) -> PerformanceKPIs:
    """
    Compute factual KPIs from a list of observations.

    Missing fields remain None, not zero.
    """
    kpi_id = _uid()
    warnings: list[str] = []

    if not observations:
        return PerformanceKPIs(
            kpi_id=kpi_id,
            machine_id=machine_id,
            job_id=job_id,
            observation_count=0,
            data_quality=DataQuality.UNKNOWN,
            warnings=["NO_OBSERVATIONS"],
        )

    cycle_times = [
        o.actual_cycle_time
        for o in observations
        if o.actual_cycle_time is not None
    ]
    total_cutting = sum(
        o.cutting_runtime for o in observations if o.cutting_runtime is not None
    )
    total_idle = sum(
        o.idle_runtime for o in observations if o.idle_runtime is not None
    )
    total_alarm = sum(
        o.alarm_runtime for o in observations if o.alarm_runtime is not None
    )
    total_time = total_cutting + total_idle + total_alarm

    # Counts
    good_counts = [o.good_count for o in observations if o.good_count is not None]
    reject_counts = [o.reject_count for o in observations if o.reject_count is not None]
    good_total = sum(good_counts) if good_counts else None
    reject_total = sum(reject_counts) if reject_counts else None

    avg_ct: float | None = None
    med_ct: float | None = None
    var_ct: float | None = None

    if cycle_times:
        avg_ct = sum(cycle_times) / len(cycle_times)
        sorted_ct = sorted(cycle_times)
        n = len(sorted_ct)
        if n % 2 == 1:
            med_ct = sorted_ct[n // 2]
        else:
            med_ct = (sorted_ct[n // 2 - 1] + sorted_ct[n // 2]) / 2.0
        if len(cycle_times) > 1:
            var_ct = sum((x - avg_ct) ** 2 for x in cycle_times) / len(cycle_times)
    else:
        warnings.append("NO_CYCLE_TIME_DATA")

    cutting_share: float | None = None
    idle_share: float | None = None
    alarm_share: float | None = None
    if total_time > 0:
        cutting_share = total_cutting / total_time
        idle_share = total_idle / total_time
        alarm_share = total_alarm / total_time

    # Yield
    yield_rate: float | None = None
    if good_total is not None and reject_total is not None:
        total_parts = good_total + reject_total
        if total_parts > 0:
            yield_rate = good_total / total_parts

    quality = DataQuality.RAW if cycle_times else DataQuality.PARTIAL

    return PerformanceKPIs(
        kpi_id=kpi_id,
        machine_id=machine_id,
        job_id=job_id,
        observation_count=len(observations),
        actual_cycle_times=cycle_times,
        average_cycle_time=avg_ct,
        median_cycle_time=med_ct,
        cycle_time_variance=var_ct,
        cutting_time_share=cutting_share,
        idle_time_share=idle_share,
        alarm_time_share=alarm_share,
        good_count=good_total,
        reject_count=reject_total,
        yield_rate=yield_rate,
        data_quality=quality,
        warnings=warnings,
    )


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def compute_rolling_median(values: list[float], window: int = 5) -> list[float | None]:
    """Compute rolling median for trend analysis."""
    result: list[float | None] = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        window_vals = values[start : i + 1]
        result.append(_median(window_vals))
    return result


def compute_z_scores(values: list[float]) -> list[float] | None:
    """Compute z-scores for anomaly detection. Returns None if std is zero."""
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    std = math.sqrt(variance)
    if std == 0:
        return None
    return [(x - mean) / std for x in values]
