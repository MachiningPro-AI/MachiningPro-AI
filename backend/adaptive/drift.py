"""Level-16 Data drift and model drift detection foundation."""

from __future__ import annotations

import hashlib
import uuid

from .enums import DriftStatus
from .models import DriftReport, ManufacturingLearningRecord, ModelSpec

_MIN_SAMPLES_DRIFT = 5


def _distribution_hash(values: list[float]) -> str:
    """Deterministic hash of a sorted value list for reference comparison."""
    s = sorted(values)
    raw = "|".join(f"{v:.4f}" for v in s)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_actual_values(
    records: list[ManufacturingLearningRecord],
    attribute: str,
) -> list[float]:
    vals: list[float] = []
    for r in records:
        v = getattr(r, attribute, None)
        if v is not None and isinstance(v, (int, float)) and v > 0:
            vals.append(float(v))
    return vals


def _mean(vals: list[float]) -> float:
    return sum(vals) / len(vals)


def _std(vals: list[float]) -> float:
    if len(vals) < 2:
        return 0.0
    m = _mean(vals)
    variance = sum((v - m) ** 2 for v in vals) / (len(vals) - 1)
    return variance ** 0.5


def detect_data_drift(
    reference_records: list[ManufacturingLearningRecord],
    current_records: list[ManufacturingLearningRecord],
    *,
    attribute: str = "actual_cycle_time",
    z_threshold: float = 2.0,
) -> DriftReport:
    """
    Compare distribution of reference vs current records for a given attribute.
    Uses simple Z-score comparison of means.
    """
    report_id = str(uuid.uuid4())[:8]

    ref_vals = _get_actual_values(reference_records, attribute)
    cur_vals = _get_actual_values(current_records, attribute)

    if len(ref_vals) < _MIN_SAMPLES_DRIFT or len(cur_vals) < _MIN_SAMPLES_DRIFT:
        return DriftReport(
            report_id=report_id,
            drift_status=DriftStatus.INSUFFICIENT_DATA,
            reference_sample_count=len(ref_vals),
            current_sample_count=len(cur_vals),
            warnings=[
                f"INSUFFICIENT_DATA — need {_MIN_SAMPLES_DRIFT}+ samples in each set"
            ],
        )

    ref_mean = _mean(ref_vals)
    ref_std = _std(ref_vals)
    cur_mean = _mean(cur_vals)

    if ref_std < 1e-9:
        return DriftReport(
            report_id=report_id,
            drift_status=DriftStatus.REVIEW_REQUIRED,
            reference_hash=_distribution_hash(ref_vals),
            current_hash=_distribution_hash(cur_vals),
            reference_sample_count=len(ref_vals),
            current_sample_count=len(cur_vals),
            warnings=["ZERO_VARIANCE_IN_REFERENCE — cannot compute Z-score"],
            review_required=True,
        )

    z_score = abs(cur_mean - ref_mean) / ref_std
    details: dict = {
        "attribute": attribute,
        "reference_mean": round(ref_mean, 4),
        "current_mean": round(cur_mean, 4),
        "reference_std": round(ref_std, 4),
        "z_score": round(z_score, 4),
        "z_threshold": z_threshold,
    }

    if z_score > z_threshold:
        status = DriftStatus.DRIFT_DETECTED
        drifted = [attribute]
        review = True
    else:
        status = DriftStatus.STABLE
        drifted = []
        review = False

    return DriftReport(
        report_id=report_id,
        drift_status=status,
        reference_hash=_distribution_hash(ref_vals),
        current_hash=_distribution_hash(cur_vals),
        reference_sample_count=len(ref_vals),
        current_sample_count=len(cur_vals),
        drifted_features=drifted,
        drift_details=details,
        review_required=review,
    )


def detect_model_drift(
    baseline_spec: ModelSpec,
    current_validation_mae: float | None,
    *,
    mae_ratio_threshold: float = 1.5,
) -> DriftReport:
    """
    Compare current validation MAE against baseline (trained) MAE.
    If ratio exceeds threshold → model drift detected.
    """
    report_id = str(uuid.uuid4())[:8]

    if baseline_spec.validation_mae is None:
        return DriftReport(
            report_id=report_id,
            drift_status=DriftStatus.INSUFFICIENT_DATA,
            warnings=["NO_BASELINE_MAE — cannot detect model drift"],
        )

    if current_validation_mae is None:
        return DriftReport(
            report_id=report_id,
            drift_status=DriftStatus.INSUFFICIENT_DATA,
            warnings=["NO_CURRENT_MAE — cannot detect model drift"],
        )

    baseline_mae = baseline_spec.validation_mae
    if baseline_mae < 1e-9:
        return DriftReport(
            report_id=report_id,
            drift_status=DriftStatus.REVIEW_REQUIRED,
            warnings=["ZERO_BASELINE_MAE — degenerate comparison"],
            review_required=True,
        )

    ratio = current_validation_mae / baseline_mae
    details: dict = {
        "baseline_mae": round(baseline_mae, 4),
        "current_mae": round(current_validation_mae, 4),
        "ratio": round(ratio, 4),
        "threshold": mae_ratio_threshold,
    }

    if ratio > mae_ratio_threshold:
        status = DriftStatus.DRIFT_DETECTED
        review = True
    else:
        status = DriftStatus.STABLE
        review = False

    return DriftReport(
        report_id=report_id,
        drift_status=status,
        drift_details=details,
        review_required=review,
    )
