"""Level-16 Adaptive recommendations — PROPOSED only, review_required=True always."""

from __future__ import annotations

import uuid

from .enums import (
    AdaptiveRecommendationType,
    PredictionFidelity,
    PredictionObjective,
    RecommendationStatus,
    SplitRole,
)
from .models import AdaptiveRecommendation, ManufacturingLearningRecord, PredictionResult

# Safe parameter change bounds for cutting data recommendations
_VC_MAX_CHANGE_PCT = 0.15
_FEED_MAX_CHANGE_PCT = 0.20
_AP_MAX_CHANGE_PCT = 0.25

# Minimum historical improvement to generate a recommendation
_MIN_IMPROVEMENT_PCT = 0.03


def _safe_bounds_check(
    current_vc: float | None,
    proposed_vc: float | None,
    *,
    vc_min: float = 10.0,
    vc_max: float = 1500.0,
) -> list[str]:
    warnings: list[str] = []
    if proposed_vc is not None:
        if proposed_vc < vc_min:
            warnings.append(f"VC_BELOW_MINIMUM — proposed {proposed_vc} < min {vc_min}")
        if proposed_vc > vc_max:
            warnings.append(f"VC_EXCEEDS_MAXIMUM — proposed {proposed_vc} > max {vc_max}")
        if current_vc is not None:
            change_pct = abs(proposed_vc - current_vc) / max(current_vc, 1e-6)
            if change_pct > _VC_MAX_CHANGE_PCT:
                warnings.append(
                    f"VC_CHANGE_EXCEEDS_SAFETY_BOUND — {change_pct:.1%} > {_VC_MAX_CHANGE_PCT:.0%}"
                )
    return warnings


def generate_cutting_data_recommendations(
    records: list[ManufacturingLearningRecord],
    baseline_cutting_data: dict,
    *,
    objective: PredictionObjective = PredictionObjective.BALANCED,
) -> list[AdaptiveRecommendation]:
    eligible = [
        r for r in records
        if r.split_role in (SplitRole.TRAIN, None)
        and not r.is_fabricated
        and r.actual_cycle_time is not None
    ]
    if not eligible:
        return []

    best_actual = min(r.actual_cycle_time for r in eligible if r.actual_cycle_time is not None)
    baseline_ct = None
    for r in eligible:
        if r.planned_cycle_time is not None:
            baseline_ct = r.planned_cycle_time
            break

    if baseline_ct is None:
        return []

    improvement = (baseline_ct - best_actual) / baseline_ct if baseline_ct > 0 else 0
    if improvement < _MIN_IMPROVEMENT_PCT:
        return []

    best_records = [r for r in eligible if r.actual_cycle_time == best_actual]
    if not best_records:
        return []
    best_rec = best_records[0]

    proposed_vc = (
        best_rec.observed_cutting_data.get("vc") or best_rec.planned_cutting_data.get("vc")
    )
    current_vc = baseline_cutting_data.get("vc")

    warnings = []
    if proposed_vc is not None and current_vc is not None:
        warnings = _safe_bounds_check(current_vc, proposed_vc)

    # Block if safety bounds exceeded
    if any("EXCEEDS" in w or "BELOW" in w for w in warnings):
        return [AdaptiveRecommendation(
            recommendation_id=str(uuid.uuid4())[:8],
            recommendation_type=AdaptiveRecommendationType.VC_REVIEW_CANDIDATE,
            current_state=baseline_cutting_data,
            proposed_state={},
            objective=objective,
            evidence=[
                f"Best observed actual_cycle_time={best_actual}s from record {best_rec.record_id}"
            ],
            constraints=["RECOMMENDATION=BLOCKED — proposed parameters exceed safety bounds"],
            warnings=warnings,
            review_required=True,
            status=RecommendationStatus.REVIEW_REQUIRED,
            is_automatic_application=False,
            fidelity=PredictionFidelity.LOW,
            sample_count=len(eligible),
        )]

    proposed_data = {**baseline_cutting_data}
    if proposed_vc is not None:
        proposed_data["vc"] = proposed_vc

    evidence = [
        f"Best observed actual_cycle_time={best_actual}s from record {best_rec.record_id}",
        f"Improvement vs planned: {improvement:.1%}",
        f"Based on {len(eligible)} historical records",
    ]

    return [AdaptiveRecommendation(
        recommendation_id=str(uuid.uuid4())[:8],
        recommendation_type=AdaptiveRecommendationType.VC_REVIEW_CANDIDATE,
        current_state=baseline_cutting_data,
        proposed_state=proposed_data,
        objective=objective,
        evidence=evidence,
        sample_count=len(eligible),
        fidelity=_fidelity_from_count(len(eligible)),
        predicted_effect={"cycle_time_reduction_pct": round(improvement, 4)},
        warnings=warnings,
        review_required=True,
        status=RecommendationStatus.PROPOSED,
        is_automatic_application=False,
    )]


def generate_machine_recommendations(
    records: list[ManufacturingLearningRecord],
    current_machine_class: str | None,
) -> list[AdaptiveRecommendation]:
    eligible = [
        r for r in records
        if r.split_role in (SplitRole.TRAIN, None)
        and not r.is_fabricated
        and r.machine_class is not None
        and r.machine_class != current_machine_class
        and r.actual_cycle_time is not None
    ]
    if not eligible:
        return []

    # Find machine class with best median actual cycle time
    class_times: dict[str, list[float]] = {}
    for r in eligible:
        mc = r.machine_class
        if mc and r.actual_cycle_time is not None:
            class_times.setdefault(mc, []).append(r.actual_cycle_time)

    if not class_times:
        return []

    def _med(vals: list[float]) -> float:
        s = sorted(vals)
        n = len(s)
        return (s[n // 2 - 1] + s[n // 2]) / 2 if n % 2 == 0 else s[n // 2]

    best_class = min(class_times, key=lambda k: _med(class_times[k]))
    best_median = _med(class_times[best_class])
    n = len(class_times[best_class])

    return [AdaptiveRecommendation(
        recommendation_id=str(uuid.uuid4())[:8],
        recommendation_type=AdaptiveRecommendationType.MACHINE_PERFORMANCE_RECOMMENDATION,
        current_state={"machine_class": current_machine_class},
        proposed_state={"machine_class": best_class},
        objective=PredictionObjective.MINIMIZE_CYCLE_TIME,
        evidence=[
            f"Machine class '{best_class}' shows median actual_cycle_time={best_median:.1f}s",
            f"Based on {n} historical records",
        ],
        sample_count=n,
        fidelity=_fidelity_from_count(n),
        warnings=["MACHINE_CHANGE_IS_ENGINEERING_DECISION — requires capacity+tooling review"],
        review_required=True,
        status=RecommendationStatus.PROPOSED,
        is_automatic_application=False,
    )]


def generate_tool_recommendations(
    records: list[ManufacturingLearningRecord],
    current_tool_family: str | None,
) -> list[AdaptiveRecommendation]:
    eligible = [
        r for r in records
        if r.split_role in (SplitRole.TRAIN, None)
        and not r.is_fabricated
        and r.tool_family is not None
        and r.tool_family != current_tool_family
        and r.actual_tool_life is not None
    ]
    if not eligible:
        return []

    family_life: dict[str, list[float]] = {}
    for r in eligible:
        tf = r.tool_family
        if tf and r.actual_tool_life is not None:
            family_life.setdefault(tf, []).append(r.actual_tool_life)

    if not family_life:
        return []

    def _med(vals: list[float]) -> float:
        s = sorted(vals)
        n = len(s)
        return (s[n // 2 - 1] + s[n // 2]) / 2 if n % 2 == 0 else s[n // 2]

    best_family = max(family_life, key=lambda k: _med(family_life[k]))
    best_median = _med(family_life[best_family])
    n = len(family_life[best_family])

    return [AdaptiveRecommendation(
        recommendation_id=str(uuid.uuid4())[:8],
        recommendation_type=AdaptiveRecommendationType.TOOL_RECOMMENDATION_CANDIDATE,
        current_state={"tool_family": current_tool_family},
        proposed_state={"tool_family": best_family},
        objective=PredictionObjective.MAXIMIZE_TOOL_LIFE,
        evidence=[
            f"Tool family '{best_family}' shows median actual_tool_life={best_median:.1f} min",
            f"Based on {n} historical records",
        ],
        sample_count=n,
        fidelity=_fidelity_from_count(n),
        warnings=["TOOL_CHANGE_IS_ENGINEERING_DECISION — requires process qualification"],
        review_required=True,
        status=RecommendationStatus.PROPOSED,
        is_automatic_application=False,
    )]


def _fidelity_from_count(n: int) -> PredictionFidelity:
    if n >= 10:
        return PredictionFidelity.HIGH
    if n >= 5:
        return PredictionFidelity.MEDIUM
    if n >= 3:
        return PredictionFidelity.LOW
    return PredictionFidelity.INSUFFICIENT


def review_recommendation(
    rec: AdaptiveRecommendation,
    new_status: RecommendationStatus,
) -> AdaptiveRecommendation:
    """Engineering review — status transitions only. is_automatic_application never changes."""
    allowed = {
        RecommendationStatus.PROPOSED: {
            RecommendationStatus.REVIEW_REQUIRED,
            RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY,
            RecommendationStatus.REJECTED,
        },
        RecommendationStatus.REVIEW_REQUIRED: {
            RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY,
            RecommendationStatus.REJECTED,
        },
        RecommendationStatus.ACCEPTED_FOR_ENGINEERING_STUDY: {
            RecommendationStatus.REJECTED,
            RecommendationStatus.STALE,
        },
    }
    if new_status not in allowed.get(rec.status, set()):
        return rec.model_copy(update={
            "warnings": rec.warnings + [
                f"INVALID_TRANSITION {rec.status.value} -> {new_status.value}"
            ]
        })
    return rec.model_copy(update={
        "status": new_status,
        "is_automatic_application": False,
    })


def build_recommendation_from_prediction(
    prediction: PredictionResult,
    rec_type: AdaptiveRecommendationType,
    current_state: dict,
    proposed_state: dict,
    objective: PredictionObjective = PredictionObjective.BALANCED,
) -> AdaptiveRecommendation:
    warnings: list[str] = list(prediction.warnings)
    if prediction.out_of_domain:
        warnings.append("OUT_OF_DOMAIN — recommendation reliability is LOW")

    return AdaptiveRecommendation(
        recommendation_id=str(uuid.uuid4())[:8],
        recommendation_type=rec_type,
        current_state=current_state,
        proposed_state=proposed_state,
        objective=objective,
        evidence=[
            f"Prediction fidelity={prediction.fidelity.value}",
            f"Sample count={prediction.sample_count}",
        ],
        model_ref=prediction.model_ref,
        sample_count=prediction.sample_count,
        fidelity=prediction.fidelity,
        predicted_effect={
            "predicted_value": prediction.predicted_value,
            "engineering_baseline": prediction.engineering_baseline,
        },
        warnings=warnings,
        review_required=True,
        status=RecommendationStatus.PROPOSED,
        is_automatic_application=False,
    )
