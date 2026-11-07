"""Level-15 Trend Foundation. Time-series support for monitoring metrics."""

from __future__ import annotations

import uuid

from .enums import DataQuality
from .models import Trend, TrendPoint


def _uid() -> str:
    return str(uuid.uuid4())


def build_cycle_time_trend(
    timestamps: list[str],
    cycle_times: list[float],
    machine_id: str | None = None,
    job_id: str | None = None,
) -> Trend:
    """Build a cycle-time trend from paired timestamp/value lists."""
    if len(timestamps) != len(cycle_times):
        return Trend(
            trend_id=_uid(),
            metric="cycle_time",
            machine_id=machine_id,
            job_id=job_id,
            data_quality=DataQuality.INVALID,
        )
    points = [
        TrendPoint(timestamp=ts, value=ct)
        for ts, ct in zip(timestamps, cycle_times, strict=False)
    ]
    quality = DataQuality.RAW if points else DataQuality.UNKNOWN
    return Trend(
        trend_id=_uid(),
        metric="cycle_time",
        machine_id=machine_id,
        job_id=job_id,
        points=points,
        data_quality=quality,
    )


def build_alarm_trend(
    timestamps: list[str],
    alarm_counts: list[float],
    machine_id: str | None = None,
) -> Trend:
    """Build an alarm-count trend."""
    if len(timestamps) != len(alarm_counts):
        return Trend(
            trend_id=_uid(),
            metric="alarm_count",
            machine_id=machine_id,
            data_quality=DataQuality.INVALID,
        )
    points = [
        TrendPoint(timestamp=ts, value=v)
        for ts, v in zip(timestamps, alarm_counts, strict=False)
    ]
    return Trend(
        trend_id=_uid(),
        metric="alarm_count",
        machine_id=machine_id,
        points=points,
        data_quality=DataQuality.RAW if points else DataQuality.UNKNOWN,
    )


def build_tool_life_trend(
    timestamps: list[str],
    tool_life_values: list[float],
    tool_id: str | None = None,
) -> Trend:
    """Build a tool-life trend."""
    if len(timestamps) != len(tool_life_values):
        return Trend(
            trend_id=_uid(),
            metric="tool_life",
            data_quality=DataQuality.INVALID,
        )
    points = [
        TrendPoint(timestamp=ts, value=v, label=tool_id)
        for ts, v in zip(timestamps, tool_life_values, strict=False)
    ]
    return Trend(
        trend_id=_uid(),
        metric="tool_life",
        points=points,
        data_quality=DataQuality.RAW if points else DataQuality.UNKNOWN,
    )


def build_quality_trend(
    timestamps: list[str],
    yield_rates: list[float],
    machine_id: str | None = None,
) -> Trend:
    """Build a quality/yield-rate trend."""
    if len(timestamps) != len(yield_rates):
        return Trend(
            trend_id=_uid(),
            metric="yield_rate",
            machine_id=machine_id,
            data_quality=DataQuality.INVALID,
        )
    points = [
        TrendPoint(timestamp=ts, value=v)
        for ts, v in zip(timestamps, yield_rates, strict=False)
    ]
    return Trend(
        trend_id=_uid(),
        metric="yield_rate",
        machine_id=machine_id,
        points=points,
        data_quality=DataQuality.RAW if points else DataQuality.UNKNOWN,
    )


def build_idle_time_trend(
    timestamps: list[str],
    idle_shares: list[float],
    machine_id: str | None = None,
) -> Trend:
    """Build an idle-time share trend."""
    if len(timestamps) != len(idle_shares):
        return Trend(
            trend_id=_uid(),
            metric="idle_time_share",
            machine_id=machine_id,
            data_quality=DataQuality.INVALID,
        )
    points = [
        TrendPoint(timestamp=ts, value=v)
        for ts, v in zip(timestamps, idle_shares, strict=False)
    ]
    return Trend(
        trend_id=_uid(),
        metric="idle_time_share",
        machine_id=machine_id,
        points=points,
        data_quality=DataQuality.RAW if points else DataQuality.UNKNOWN,
    )
