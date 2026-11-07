"""
Level-15 Quality Observation Handling.

Tolerances come from actual data only.
Scrap/reject from observation, not inferred from alarms.
"""

from __future__ import annotations

import uuid

from .enums import DataQuality, QualitySource
from .models import QualityObservation


def _uid() -> str:
    return str(uuid.uuid4())


def make_quality_observation(
    characteristic: str,
    measured_value: float | None = None,
    nominal: float | None = None,
    lower_limit: float | None = None,
    upper_limit: float | None = None,
    operation: str | None = None,
    tool: str | None = None,
    machine: str | None = None,
    timestamp: str | None = None,
    source: QualitySource = QualitySource.MANUAL_INSPECTION,
) -> QualityObservation:
    """Create a quality observation from actual measurement data."""
    pass_fail: bool | None = None
    warnings: list[str] = []

    if measured_value is not None:
        if lower_limit is not None and upper_limit is not None:
            pass_fail = lower_limit <= measured_value <= upper_limit
        else:
            warnings.append("LIMITS_NOT_PROVIDED_CANNOT_EVALUATE")
    else:
        warnings.append("NO_MEASURED_VALUE")

    quality = DataQuality.RAW if measured_value is not None else DataQuality.UNKNOWN

    return QualityObservation(
        quality_obs_id=_uid(),
        characteristic=characteristic,
        nominal=nominal,
        lower_limit=lower_limit,
        upper_limit=upper_limit,
        measured_value=measured_value,
        pass_fail=pass_fail,
        operation=operation,
        tool=tool,
        machine=machine,
        timestamp=timestamp,
        source=source,
        data_quality=quality,
    )


def compute_yield(
    good_count: int | None,
    total_count: int | None,
) -> float | None:
    """
    Compute yield = good_count / total_count.

    Returns None when inputs are invalid.
    """
    if good_count is None or total_count is None:
        return None
    if total_count <= 0:
        return None
    return good_count / total_count


def summarize_quality(
    observations: list[QualityObservation],
) -> dict[str, int]:
    """Count pass/fail/unknown from a list of quality observations."""
    result = {"pass": 0, "fail": 0, "unknown": 0}
    for obs in observations:
        if obs.pass_fail is True:
            result["pass"] += 1
        elif obs.pass_fail is False:
            result["fail"] += 1
        else:
            result["unknown"] += 1
    return result
