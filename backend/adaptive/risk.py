"""Level-16 Quality risk and alarm risk estimation from historical records."""

from __future__ import annotations

import uuid

from .enums import AlarmRiskLevel, PredictionFidelity, QualityRiskLevel, SplitRole
from .models import AlarmRiskResult, ManufacturingLearningRecord, QualityRiskResult

_MIN_SAMPLES = 3

_QUALITY_THRESHOLDS = {
    "LOW": 0.05,
    "MEDIUM": 0.15,
}

_ALARM_THRESHOLDS = {
    "LOW": 0.10,
    "MEDIUM": 0.30,
}


def _fidelity(n: int) -> PredictionFidelity:
    if n >= 10:
        return PredictionFidelity.HIGH
    if n >= 5:
        return PredictionFidelity.MEDIUM
    if n >= _MIN_SAMPLES:
        return PredictionFidelity.LOW
    return PredictionFidelity.INSUFFICIENT


def estimate_quality_risk(
    records: list[ManufacturingLearningRecord],
) -> QualityRiskResult:
    pred_id = str(uuid.uuid4())[:8]
    eligible = [
        r for r in records
        if r.split_role in (SplitRole.TRAIN, None) and not r.is_fabricated
        and r.quality_result is not None
    ]
    if len(eligible) < _MIN_SAMPLES:
        return QualityRiskResult(
            prediction_id=pred_id,
            risk_level=QualityRiskLevel.INSUFFICIENT,
            reject_rate=None,
            sample_count=len(eligible),
            fidelity=PredictionFidelity.INSUFFICIENT,
            warnings=["INSUFFICIENT_QUALITY_DATA"],
            is_fabricated=False,
        )

    fail_count = sum(1 for r in eligible if r.quality_result not in ("PASS", "OK"))
    reject_rate = fail_count / len(eligible)

    if reject_rate <= _QUALITY_THRESHOLDS["LOW"]:
        level = QualityRiskLevel.LOW
    elif reject_rate <= _QUALITY_THRESHOLDS["MEDIUM"]:
        level = QualityRiskLevel.MEDIUM
    else:
        level = QualityRiskLevel.HIGH

    factors = [f"reject_rate={reject_rate:.3f}", f"sample_count={len(eligible)}"]

    return QualityRiskResult(
        prediction_id=pred_id,
        risk_level=level,
        reject_rate=round(reject_rate, 6),
        sample_count=len(eligible),
        fidelity=_fidelity(len(eligible)),
        factors=factors,
        is_fabricated=False,
    )


def estimate_alarm_risk(
    records: list[ManufacturingLearningRecord],
) -> AlarmRiskResult:
    pred_id = str(uuid.uuid4())[:8]
    eligible = [
        r for r in records
        if r.split_role in (SplitRole.TRAIN, None) and not r.is_fabricated
        and r.alarm_summary is not None
    ]
    if len(eligible) < _MIN_SAMPLES:
        return AlarmRiskResult(
            prediction_id=pred_id,
            risk_level=AlarmRiskLevel.INSUFFICIENT,
            alarm_rate=None,
            sample_count=len(eligible),
            fidelity=PredictionFidelity.INSUFFICIENT,
            warnings=["INSUFFICIENT_ALARM_DATA"],
            is_fabricated=False,
        )

    alarm_count = sum(1 for r in eligible if r.alarm_summary not in ("NONE", ""))
    alarm_rate = alarm_count / len(eligible)

    if alarm_rate <= _ALARM_THRESHOLDS["LOW"]:
        level = AlarmRiskLevel.LOW
    elif alarm_rate <= _ALARM_THRESHOLDS["MEDIUM"]:
        level = AlarmRiskLevel.MEDIUM
    else:
        level = AlarmRiskLevel.HIGH

    factors = [f"alarm_rate={alarm_rate:.3f}", f"sample_count={len(eligible)}"]

    return AlarmRiskResult(
        prediction_id=pred_id,
        risk_level=level,
        alarm_rate=round(alarm_rate, 6),
        sample_count=len(eligible),
        fidelity=_fidelity(len(eligible)),
        factors=factors,
        is_fabricated=False,
    )
