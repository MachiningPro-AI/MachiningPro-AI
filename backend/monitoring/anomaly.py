"""
Level-15 Anomaly Detection Foundation.

Deterministic policies: threshold, range, rolling deviation, IQR, z-score.
No ML model claimed unless actual ML is implemented.
"""

from __future__ import annotations

import math
import uuid

from .enums import AnomalyMethod
from .models import AnomalyPolicy, AnomalyResult


def _uid() -> str:
    return str(uuid.uuid4())


def detect_threshold_anomaly(
    metric: str,
    value: float,
    threshold: float,
    policy_id: str | None = None,
) -> AnomalyResult:
    """Detect anomaly when value exceeds a single threshold."""
    return AnomalyResult(
        anomaly_id=_uid(),
        policy_ref=policy_id or "threshold",
        metric=metric,
        value=value,
        is_anomaly=value > threshold,
        method=AnomalyMethod.THRESHOLD,
        details=f"value={value} threshold={threshold}",
    )


def detect_range_anomaly(
    metric: str,
    value: float,
    lower_bound: float,
    upper_bound: float,
    policy_id: str | None = None,
) -> AnomalyResult:
    """Detect anomaly when value is outside [lower_bound, upper_bound]."""
    is_anomaly = value < lower_bound or value > upper_bound
    return AnomalyResult(
        anomaly_id=_uid(),
        policy_ref=policy_id or "range",
        metric=metric,
        value=value,
        is_anomaly=is_anomaly,
        method=AnomalyMethod.RANGE,
        details=f"value={value} range=[{lower_bound},{upper_bound}]",
    )


def detect_rolling_deviation_anomaly(
    metric: str,
    values: list[float],
    window: int = 5,
    deviation_multiplier: float = 2.0,
    policy_id: str | None = None,
) -> list[AnomalyResult]:
    """Detect anomalies using rolling mean ± deviation_multiplier × std."""
    results: list[AnomalyResult] = []
    for i, val in enumerate(values):
        start = max(0, i - window + 1)
        window_vals = values[start:i]
        if len(window_vals) < 2:
            results.append(
                AnomalyResult(
                    anomaly_id=_uid(),
                    policy_ref=policy_id or "rolling",
                    metric=metric,
                    value=val,
                    is_anomaly=False,
                    method=AnomalyMethod.ROLLING_DEVIATION,
                    details="INSUFFICIENT_WINDOW",
                )
            )
            continue
        mean = sum(window_vals) / len(window_vals)
        std = math.sqrt(
            sum((x - mean) ** 2 for x in window_vals) / len(window_vals)
        )
        limit = deviation_multiplier * std
        is_anomaly = abs(val - mean) > limit if std > 0 else False
        results.append(
            AnomalyResult(
                anomaly_id=_uid(),
                policy_ref=policy_id or "rolling",
                metric=metric,
                value=val,
                is_anomaly=is_anomaly,
                method=AnomalyMethod.ROLLING_DEVIATION,
                details=f"mean={mean:.3f} std={std:.3f} limit={limit:.3f}",
            )
        )
    return results


def detect_iqr_anomalies(
    metric: str,
    values: list[float],
    iqr_multiplier: float = 1.5,
    policy_id: str | None = None,
) -> list[AnomalyResult]:
    """Detect anomalies using the IQR method."""
    if len(values) < 4:
        return [
            AnomalyResult(
                anomaly_id=_uid(),
                policy_ref=policy_id or "iqr",
                metric=metric,
                value=v,
                is_anomaly=False,
                method=AnomalyMethod.IQR,
                details="INSUFFICIENT_DATA_FOR_IQR",
            )
            for v in values
        ]
    sorted_v = sorted(values)
    n = len(sorted_v)
    q1 = sorted_v[n // 4]
    q3 = sorted_v[(3 * n) // 4]
    iqr = q3 - q1
    lower = q1 - iqr_multiplier * iqr
    upper = q3 + iqr_multiplier * iqr
    return [
        AnomalyResult(
            anomaly_id=_uid(),
            policy_ref=policy_id or "iqr",
            metric=metric,
            value=v,
            is_anomaly=v < lower or v > upper,
            method=AnomalyMethod.IQR,
            details=f"Q1={q1} Q3={q3} IQR={iqr} bounds=[{lower},{upper}]",
        )
        for v in values
    ]


def apply_anomaly_policy(
    policy: AnomalyPolicy,
    values: list[float],
) -> list[AnomalyResult]:
    """Apply a named anomaly policy to a list of values."""
    if policy.method == AnomalyMethod.THRESHOLD:
        if policy.threshold is None:
            return []
        return [
            detect_threshold_anomaly(
                policy.metric, v, policy.threshold, policy.policy_id
            )
            for v in values
        ]
    if policy.method == AnomalyMethod.RANGE:
        if policy.lower_bound is None or policy.upper_bound is None:
            return []
        return [
            detect_range_anomaly(
                policy.metric,
                v,
                policy.lower_bound,
                policy.upper_bound,
                policy.policy_id,
            )
            for v in values
        ]
    if policy.method == AnomalyMethod.ROLLING_DEVIATION:
        window = policy.window_size or 5
        multiplier = policy.z_score_limit or 2.0
        return detect_rolling_deviation_anomaly(
            policy.metric, values, window, multiplier, policy.policy_id
        )
    if policy.method == AnomalyMethod.IQR:
        multiplier = policy.iqr_multiplier or 1.5
        return detect_iqr_anomalies(
            policy.metric, values, multiplier, policy.policy_id
        )
    return []
