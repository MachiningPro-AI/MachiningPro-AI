"""Level-16 What-if engine — recalculates only, never alters baseline."""

from __future__ import annotations

import uuid

from .enums import PredictionFidelity, PredictionTarget, WhatIfStatus
from .models import ManufacturingLearningRecord, WhatIfScenario
from .predictors import MedianPredictor, NearestNeighborPredictor


def run_what_if_vc_change(
    baseline_record: ManufacturingLearningRecord,
    training_records: list[ManufacturingLearningRecord],
    *,
    vc_change_pct: float,
    description: str | None = None,
) -> WhatIfScenario:
    """
    Predict cycle time effect of changing Vc by vc_change_pct (e.g. 0.05 = +5%).
    Does NOT alter baseline_record or any training record.
    mutates_baseline is always False.
    """
    scenario_id = str(uuid.uuid4())[:8]
    warnings: list[str] = []

    current_vc = baseline_record.planned_cutting_data.get("vc")
    if current_vc is None:
        return WhatIfScenario(
            scenario_id=scenario_id,
            description=description or f"Vc change {vc_change_pct:+.1%}",
            parameter_changes={"vc_change_pct": vc_change_pct},
            baseline_values={},
            status=WhatIfStatus.INSUFFICIENT_DATA,
            fidelity=PredictionFidelity.INSUFFICIENT,
            mutates_baseline=False,
            warnings=["MISSING_VC — cannot evaluate what-if without baseline Vc"],
        )

    proposed_vc = current_vc * (1.0 + vc_change_pct)
    if proposed_vc <= 0:
        return WhatIfScenario(
            scenario_id=scenario_id,
            description=description or f"Vc change {vc_change_pct:+.1%}",
            parameter_changes={"vc": proposed_vc, "vc_change_pct": vc_change_pct},
            baseline_values={"vc": current_vc},
            status=WhatIfStatus.BLOCKED_BY_CONSTRAINT,
            fidelity=PredictionFidelity.INSUFFICIENT,
            mutates_baseline=False,
            warnings=["NEGATIVE_VC_NOT_ALLOWED"],
        )

    # Build a temporary query record — baseline_record is NOT modified
    temp_record = ManufacturingLearningRecord(
        record_id=f"WHATIF_{scenario_id}",
        part_family=baseline_record.part_family,
        material=baseline_record.material,
        machine_class=baseline_record.machine_class,
        operation_type=baseline_record.operation_type,
        planned_cutting_data={
            **baseline_record.planned_cutting_data,
            "vc": proposed_vc,
        },
        planned_cycle_time=baseline_record.planned_cycle_time,
        is_fabricated=False,
        is_test_only=True,
    )

    # Use nearest-neighbor predictor on training set
    predictor = NearestNeighborPredictor(
        PredictionTarget.CYCLE_TIME, model_id=f"whatif_{scenario_id}"
    )
    predictor.train(training_records)

    pred = predictor.predict(temp_record, f"PRED_WHATIF_{scenario_id}")

    baseline_pred = None
    if baseline_record.actual_cycle_time is not None:
        baseline_pred = baseline_record.actual_cycle_time
    elif baseline_record.planned_cycle_time is not None:
        baseline_pred = baseline_record.planned_cycle_time

    predicted_outputs: dict = {
        "predicted_cycle_time": pred.predicted_value,
        "fidelity": pred.fidelity.value,
        "sample_count": pred.sample_count,
    }
    if baseline_pred is not None:
        predicted_outputs["baseline_cycle_time"] = baseline_pred
        if pred.predicted_value is not None:
            delta_pct = (pred.predicted_value - baseline_pred) / baseline_pred
            predicted_outputs["delta_pct"] = round(delta_pct, 4)

    warnings.extend(pred.warnings)

    if pred.fidelity == PredictionFidelity.INSUFFICIENT or pred.predicted_value is None:
        status = WhatIfStatus.INSUFFICIENT_DATA
    elif pred.out_of_domain:
        status = WhatIfStatus.OUT_OF_DOMAIN
    elif baseline_pred is not None and pred.predicted_value is not None:
        if pred.predicted_value < baseline_pred * 0.99:
            status = WhatIfStatus.PREDICTED_IMPROVEMENT
        elif pred.predicted_value > baseline_pred * 1.01:
            status = WhatIfStatus.PREDICTED_DEGRADATION
        else:
            status = WhatIfStatus.NO_CHANGE_PREDICTED
    else:
        status = WhatIfStatus.INSUFFICIENT_DATA

    return WhatIfScenario(
        scenario_id=scenario_id,
        description=description or f"Vc change {vc_change_pct:+.1%}",
        parameter_changes={"vc": proposed_vc, "vc_change_pct": vc_change_pct},
        baseline_values={"vc": current_vc, "cycle_time": baseline_pred},
        predicted_outputs=predicted_outputs,
        status=status,
        fidelity=pred.fidelity,
        mutates_baseline=False,
        sample_count=pred.sample_count,
        warnings=warnings,
    )


def run_what_if_machine_change(
    baseline_record: ManufacturingLearningRecord,
    training_records: list[ManufacturingLearningRecord],
    *,
    proposed_machine_class: str,
    description: str | None = None,
) -> WhatIfScenario:
    """
    Predict cycle time for a different machine class.
    Does NOT alter baseline_record. mutates_baseline is always False.
    """
    scenario_id = str(uuid.uuid4())[:8]
    warnings: list[str] = []

    eligible = [
        r for r in training_records
        if r.machine_class == proposed_machine_class and r.actual_cycle_time is not None
    ]
    if not eligible:
        return WhatIfScenario(
            scenario_id=scenario_id,
            description=description or f"Machine class → {proposed_machine_class}",
            parameter_changes={"machine_class": proposed_machine_class},
            baseline_values={"machine_class": baseline_record.machine_class},
            status=WhatIfStatus.INSUFFICIENT_DATA,
            fidelity=PredictionFidelity.INSUFFICIENT,
            mutates_baseline=False,
            warnings=[
                f"NO_RECORDS_FOR_MACHINE_CLASS_{proposed_machine_class}"
            ],
        )

    predictor = MedianPredictor(PredictionTarget.CYCLE_TIME, model_id=f"whatif_mc_{scenario_id}")
    predictor.train(eligible)
    pred = predictor.predict(
        ManufacturingLearningRecord(
            record_id=f"WHATIF_MC_{scenario_id}",
            machine_class=proposed_machine_class,
            is_fabricated=False,
            is_test_only=True,
        ),
        f"PRED_WHATIF_MC_{scenario_id}",
        engineering_baseline=baseline_record.planned_cycle_time,
    )

    baseline_ct = baseline_record.actual_cycle_time or baseline_record.planned_cycle_time
    predicted_outputs: dict = {
        "predicted_cycle_time": pred.predicted_value,
        "fidelity": pred.fidelity.value,
        "sample_count": pred.sample_count,
        "proposed_machine_class": proposed_machine_class,
    }
    if baseline_ct is not None and pred.predicted_value is not None:
        delta_pct = (pred.predicted_value - baseline_ct) / baseline_ct
        predicted_outputs["baseline_cycle_time"] = baseline_ct
        predicted_outputs["delta_pct"] = round(delta_pct, 4)

    warnings.extend(pred.warnings)
    warnings.append(
        "MACHINE_CHANGE_IS_NOT_AUTOMATIC — this is a what-if simulation only"
    )

    if pred.fidelity == PredictionFidelity.INSUFFICIENT or pred.predicted_value is None:
        status = WhatIfStatus.INSUFFICIENT_DATA
    elif baseline_ct is not None and pred.predicted_value is not None:
        if pred.predicted_value < baseline_ct * 0.99:
            status = WhatIfStatus.PREDICTED_IMPROVEMENT
        elif pred.predicted_value > baseline_ct * 1.01:
            status = WhatIfStatus.PREDICTED_DEGRADATION
        else:
            status = WhatIfStatus.NO_CHANGE_PREDICTED
    else:
        status = WhatIfStatus.INSUFFICIENT_DATA

    return WhatIfScenario(
        scenario_id=scenario_id,
        description=description or f"Machine class → {proposed_machine_class}",
        parameter_changes={"machine_class": proposed_machine_class},
        baseline_values={"machine_class": baseline_record.machine_class, "cycle_time": baseline_ct},
        predicted_outputs=predicted_outputs,
        status=status,
        fidelity=pred.fidelity,
        mutates_baseline=False,
        sample_count=pred.sample_count,
        warnings=warnings,
    )
