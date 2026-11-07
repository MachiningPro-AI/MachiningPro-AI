"""Level-16 Interpretable prediction models — median, nearest-neighbor, linear regression."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import NamedTuple

from .enums import ModelStatus, ModelType, PredictionFidelity, PredictionTarget, SplitRole
from .models import ManufacturingLearningRecord, ModelParams, ModelSpec, PredictionResult
from .similarity import find_similar_cases

_MIN_TRAIN_MEDIAN = 3
_MIN_TRAIN_NN = 3
_MIN_TRAIN_LR = 5


def _training_hash(records: list[ManufacturingLearningRecord]) -> str:
    ids = "|".join(sorted(r.record_id for r in records))
    return hashlib.sha256(ids.encode()).hexdigest()[:16]


def _fidelity(sample_count: int) -> PredictionFidelity:
    if sample_count >= 10:
        return PredictionFidelity.HIGH
    if sample_count >= 5:
        return PredictionFidelity.MEDIUM
    if sample_count >= _MIN_TRAIN_MEDIAN:
        return PredictionFidelity.LOW
    return PredictionFidelity.INSUFFICIENT


def _get_actual_values(
    records: list[ManufacturingLearningRecord],
    target: PredictionTarget,
) -> list[float]:
    vals: list[float] = []
    for r in records:
        if target == PredictionTarget.CYCLE_TIME:
            v = r.actual_cycle_time
        elif target == PredictionTarget.TOOL_LIFE:
            v = r.actual_tool_life
        else:
            continue
        if v is not None and v > 0:
            vals.append(v)
    return vals


def _median(values: list[float]) -> float:
    s = sorted(values)
    n = len(s)
    mid = n // 2
    return (s[mid - 1] + s[mid]) / 2 if n % 2 == 0 else s[mid]


def _mae(predicted: float, actuals: list[float]) -> float:
    if not actuals:
        return float("nan")
    return sum(abs(a - predicted) for a in actuals) / len(actuals)


# ---------------------------------------------------------------------------
# Median predictor
# ---------------------------------------------------------------------------

class MedianPredictor:
    def __init__(self, target: PredictionTarget, model_id: str = "median_predictor") -> None:
        self.target = target
        self.model_id = model_id
        self._median: float | None = None
        self._sample_count: int = 0
        self._data_hash: str | None = None
        self._trained_at: str | None = None
        self._val_mae: float | None = None

    def train(
        self,
        train_records: list[ManufacturingLearningRecord],
        validation_records: list[ManufacturingLearningRecord] | None = None,
    ) -> ModelSpec:
        # Only train on TRAIN split records
        eligible = [
            r for r in train_records
            if r.split_role in (SplitRole.TRAIN, None) and not r.is_fabricated
        ]
        values = _get_actual_values(eligible, self.target)
        if len(values) < _MIN_TRAIN_MEDIAN:
            return ModelSpec(
                model_id=self.model_id,
                version="1.0",
                target=self.target,
                model_type=ModelType.HISTORICAL_MEDIAN,
                sample_count=len(values),
                status=ModelStatus.REVIEW_REQUIRED,
                limitations=["INSUFFICIENT_TRAINING_DATA"],
                is_fabricated_accuracy=False,
            )
        self._median = _median(values)
        self._sample_count = len(values)
        self._data_hash = _training_hash(eligible)
        self._trained_at = datetime.now(UTC).isoformat()

        val_mae = None
        if validation_records:
            val_values = _get_actual_values(
                [r for r in validation_records if r.split_role == SplitRole.VALIDATION],
                self.target,
            )
            if val_values and self._median is not None:
                val_mae = round(_mae(self._median, val_values), 4)
        self._val_mae = val_mae

        metrics: dict[str, float] = {}
        if val_mae is not None:
            metrics["validation_mae"] = val_mae

        return ModelSpec(
            model_id=self.model_id,
            version="1.0",
            target=self.target,
            model_type=ModelType.HISTORICAL_MEDIAN,
            training_data_hash=self._data_hash,
            training_timestamp=self._trained_at,
            sample_count=self._sample_count,
            validation_mae=val_mae,
            metrics=metrics,
            status=ModelStatus.TRAINED,
            is_fabricated_accuracy=False,
        )

    def predict(
        self,
        query: ManufacturingLearningRecord,
        prediction_id: str,
        engineering_baseline: float | None = None,
    ) -> PredictionResult:
        if self._median is None or self._sample_count < _MIN_TRAIN_MEDIAN:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.INSUFFICIENT,
                sample_count=0,
                warnings=["MODEL_NOT_TRAINED"],
                is_fabricated=False,
            )
        return PredictionResult(
            prediction_id=prediction_id,
            target=self.target,
            model_ref=self.model_id,
            engineering_baseline=engineering_baseline,
            historical_prediction=round(self._median, 4),
            predicted_value=round(self._median, 4),
            fidelity=_fidelity(self._sample_count),
            sample_count=self._sample_count,
            uncertainty_description=(
                f"Historical median over {self._sample_count} validated records"
            ),
            is_fabricated=False,
        )

    def get_params(self) -> ModelParams:
        return ModelParams(
            model_type=ModelType.HISTORICAL_MEDIAN,
            target=self.target,
            median_value=self._median,
            sample_count=self._sample_count,
        )


# ---------------------------------------------------------------------------
# Nearest-neighbor predictor
# ---------------------------------------------------------------------------

class NearestNeighborPredictor:
    def __init__(self, target: PredictionTarget, model_id: str = "nn_predictor") -> None:
        self.target = target
        self.model_id = model_id
        self._training_records: list[ManufacturingLearningRecord] = []
        self._data_hash: str | None = None
        self._trained_at: str | None = None

    def train(
        self,
        train_records: list[ManufacturingLearningRecord],
        validation_records: list[ManufacturingLearningRecord] | None = None,
    ) -> ModelSpec:
        eligible = [
            r for r in train_records
            if r.split_role in (SplitRole.TRAIN, None)
            and not r.is_fabricated
            and _get_actual_values([r], self.target)
        ]
        if len(eligible) < _MIN_TRAIN_NN:
            return ModelSpec(
                model_id=self.model_id,
                version="1.0",
                target=self.target,
                model_type=ModelType.NEAREST_NEIGHBOR,
                sample_count=len(eligible),
                status=ModelStatus.REVIEW_REQUIRED,
                limitations=["INSUFFICIENT_TRAINING_DATA"],
                is_fabricated_accuracy=False,
            )
        self._training_records = eligible
        self._data_hash = _training_hash(eligible)
        self._trained_at = datetime.now(UTC).isoformat()
        return ModelSpec(
            model_id=self.model_id,
            version="1.0",
            target=self.target,
            model_type=ModelType.NEAREST_NEIGHBOR,
            training_data_hash=self._data_hash,
            training_timestamp=self._trained_at,
            sample_count=len(eligible),
            status=ModelStatus.TRAINED,
            is_fabricated_accuracy=False,
        )

    def predict(
        self,
        query: ManufacturingLearningRecord,
        prediction_id: str,
        engineering_baseline: float | None = None,
        top_k: int = 5,
    ) -> PredictionResult:
        if len(self._training_records) < _MIN_TRAIN_NN:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.INSUFFICIENT,
                sample_count=0,
                warnings=["MODEL_NOT_TRAINED"],
                is_fabricated=False,
            )

        similar = find_similar_cases(query, self._training_records, top_k=top_k)
        if not similar:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.INSUFFICIENT,
                sample_count=0,
                warnings=["NO_SIMILAR_CASES_FOUND"],
                is_fabricated=False,
                out_of_domain=True,
            )

        # Weighted average by similarity score
        values_weights: list[tuple[float, float]] = []
        for case in similar:
            if self.target == PredictionTarget.CYCLE_TIME and case.actual_cycle_time:
                values_weights.append((case.actual_cycle_time, case.similarity_score))
            elif self.target == PredictionTarget.TOOL_LIFE and case.actual_tool_life:
                values_weights.append((case.actual_tool_life, case.similarity_score))

        if not values_weights:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.INSUFFICIENT,
                sample_count=0,
                warnings=["SIMILAR_CASES_MISSING_TARGET_VALUE"],
                is_fabricated=False,
            )

        total_w = sum(w for _, w in values_weights)
        pred = sum(v * w for v, w in values_weights) / total_w
        fidelity = _fidelity(len(values_weights))

        warnings: list[str] = []
        top_case = similar[0]
        if top_case.similarity_score < 0.5:
            warnings.append(
                f"LOW_SIMILARITY_SCORE — best match score={top_case.similarity_score:.3f}"
            )

        return PredictionResult(
            prediction_id=prediction_id,
            target=self.target,
            model_ref=self.model_id,
            engineering_baseline=engineering_baseline,
            historical_prediction=round(pred, 4),
            predicted_value=round(pred, 4),
            fidelity=fidelity,
            sample_count=len(values_weights),
            similar_case_ids=[c.case_id for c in similar],
            uncertainty_description=(
                f"Weighted average of {len(values_weights)} similar cases"
            ),
            warnings=warnings,
            is_fabricated=False,
        )

    def get_params(self) -> ModelParams:
        return ModelParams(
            model_type=ModelType.NEAREST_NEIGHBOR,
            target=self.target,
            sample_count=len(self._training_records),
            training_records=[r.record_id for r in self._training_records],
        )


# ---------------------------------------------------------------------------
# Simple linear regression (pure Python, no numpy)
# ---------------------------------------------------------------------------

class _LRResult(NamedTuple):
    slope: float
    intercept: float
    r_squared: float


def _simple_linear_regression(
    x_vals: list[float], y_vals: list[float]
) -> _LRResult | None:
    n = len(x_vals)
    if n < 2:
        return None
    sx = sum(x_vals)
    sy = sum(y_vals)
    sxx = sum(xi * xi for xi in x_vals)
    sxy = sum(xi * yi for xi, yi in zip(x_vals, y_vals, strict=False))
    denom = n * sxx - sx * sx
    if abs(denom) < 1e-12:
        return None
    slope = (n * sxy - sx * sy) / denom
    intercept = (sy - slope * sx) / n
    # R²
    y_mean = sy / n
    ss_tot = sum((yi - y_mean) ** 2 for yi in y_vals)
    if ss_tot < 1e-12:
        r_sq = 1.0
    else:
        y_pred = [slope * xi + intercept for xi in x_vals]
        ss_res = sum((yi - yp) ** 2 for yi, yp in zip(y_vals, y_pred, strict=False))
        r_sq = 1.0 - ss_res / ss_tot
    return _LRResult(slope=slope, intercept=intercept, r_squared=r_sq)


class LinearRegressionPredictor:
    """Single-feature linear regression: planned → actual."""

    def __init__(
        self,
        target: PredictionTarget,
        feature: str = "planned_cycle_time",
        model_id: str = "lr_predictor",
    ) -> None:
        self.target = target
        self.feature = feature
        self.model_id = model_id
        self._slope: float | None = None
        self._intercept: float | None = None
        self._r_squared: float | None = None
        self._sample_count: int = 0
        self._data_hash: str | None = None
        self._trained_at: str | None = None

    def _get_feature_value(self, record: ManufacturingLearningRecord) -> float | None:
        if self.feature == "planned_cycle_time":
            return record.planned_cycle_time
        if self.feature == "planned_tool_life":
            return record.planned_tool_life
        return record.planned_cutting_data.get(self.feature)

    def train(
        self,
        train_records: list[ManufacturingLearningRecord],
        validation_records: list[ManufacturingLearningRecord] | None = None,
    ) -> ModelSpec:
        eligible = [
            r for r in train_records
            if r.split_role in (SplitRole.TRAIN, None) and not r.is_fabricated
        ]
        pairs: list[tuple[float, float]] = []
        for r in eligible:
            x = self._get_feature_value(r)
            vals = _get_actual_values([r], self.target)
            if x is not None and vals:
                pairs.append((x, vals[0]))

        if len(pairs) < _MIN_TRAIN_LR:
            return ModelSpec(
                model_id=self.model_id,
                version="1.0",
                target=self.target,
                model_type=ModelType.LINEAR_REGRESSION,
                sample_count=len(pairs),
                status=ModelStatus.REVIEW_REQUIRED,
                limitations=["INSUFFICIENT_TRAINING_DATA"],
                is_fabricated_accuracy=False,
            )

        xs = [p[0] for p in pairs]
        ys = [p[1] for p in pairs]
        lr = _simple_linear_regression(xs, ys)
        if lr is None:
            return ModelSpec(
                model_id=self.model_id,
                version="1.0",
                target=self.target,
                model_type=ModelType.LINEAR_REGRESSION,
                sample_count=len(pairs),
                status=ModelStatus.REVIEW_REQUIRED,
                limitations=["DEGENERATE_REGRESSION — zero variance in predictor"],
                is_fabricated_accuracy=False,
            )

        self._slope = lr.slope
        self._intercept = lr.intercept
        self._r_squared = lr.r_squared
        self._sample_count = len(pairs)
        self._data_hash = _training_hash(eligible)
        self._trained_at = datetime.now(UTC).isoformat()

        metrics: dict[str, float] = {"r_squared": round(lr.r_squared, 4)}

        return ModelSpec(
            model_id=self.model_id,
            version="1.0",
            target=self.target,
            model_type=ModelType.LINEAR_REGRESSION,
            training_data_hash=self._data_hash,
            training_timestamp=self._trained_at,
            sample_count=self._sample_count,
            metrics=metrics,
            status=ModelStatus.TRAINED,
            is_fabricated_accuracy=False,
        )

    def predict(
        self,
        query: ManufacturingLearningRecord,
        prediction_id: str,
        engineering_baseline: float | None = None,
    ) -> PredictionResult:
        if self._slope is None:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.INSUFFICIENT,
                sample_count=0,
                warnings=["MODEL_NOT_TRAINED"],
                is_fabricated=False,
            )

        x = self._get_feature_value(query)
        if x is None:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.INSUFFICIENT,
                sample_count=self._sample_count,
                warnings=[f"MISSING_FEATURE — {self.feature} required for prediction"],
                is_fabricated=False,
            )

        raw = self._slope * x + self._intercept
        if raw <= 0:
            return PredictionResult(
                prediction_id=prediction_id,
                target=self.target,
                model_ref=self.model_id,
                engineering_baseline=engineering_baseline,
                fidelity=PredictionFidelity.LOW,
                sample_count=self._sample_count,
                warnings=["NEGATIVE_PREDICTION_CLAMPED — extrapolation beyond training range"],
                is_fabricated=False,
                out_of_domain=True,
            )

        warnings: list[str] = []
        r2 = self._r_squared or 0.0
        if r2 < 0.5:
            warnings.append(f"LOW_R_SQUARED={r2:.3f} — prediction has low reliability")

        return PredictionResult(
            prediction_id=prediction_id,
            target=self.target,
            model_ref=self.model_id,
            engineering_baseline=engineering_baseline,
            historical_prediction=round(raw, 4),
            predicted_value=round(raw, 4),
            fidelity=_fidelity(self._sample_count),
            sample_count=self._sample_count,
            uncertainty_description=(
                f"Linear regression slope={self._slope:.4f} intercept={self._intercept:.4f}"
                f" R²={r2:.4f} over {self._sample_count} records"
            ),
            warnings=warnings,
            is_fabricated=False,
        )

    def get_params(self) -> ModelParams:
        return ModelParams(
            model_type=ModelType.LINEAR_REGRESSION,
            target=self.target,
            slope=self._slope,
            intercept=self._intercept,
            feature_name=self.feature,
            sample_count=self._sample_count,
        )
