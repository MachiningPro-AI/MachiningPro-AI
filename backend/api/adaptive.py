"""Level-16 Adaptive Manufacturing Intelligence API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.adaptive import (
    MedianPredictor,
    NearestNeighborPredictor,
    PredictionTarget,
    build_trade_off_analysis,
    create_learning_record,
    detect_data_drift,
    estimate_alarm_risk,
    estimate_quality_risk,
    find_similar_cases,
    generate_cutting_data_recommendations,
    generate_machine_recommendations,
    generate_tool_recommendations,
    get_registry,
    make_test_dataset_aluminium_turning,
    run_what_if_machine_change,
    run_what_if_vc_change,
    split_records,
    validate_learning_record,
)
from backend.adaptive.models import ManufacturingLearningRecord, ModelSpec
from backend.api.auth import verify_token

router = APIRouter(prefix="/api/adaptive", tags=["adaptive"])

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _require_user(token: str = Depends(verify_token)):  # noqa: B008
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token


# ---------------------------------------------------------------------------
# Session-scoped record store (non-persistent, cleared on restart)
# ---------------------------------------------------------------------------

_record_store: list[ManufacturingLearningRecord] = []
_model_store: dict[str, ModelSpec] = {}
_recommendation_store: dict[str, object] = {}
_audit_log: list[object] = []


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class IngestRecordRequest(BaseModel):
    record_id: str
    part_family: str | None = None
    material: str | None = None
    machine_class: str | None = None
    operation_type: str | None = None
    planned_cycle_time: float | None = None
    actual_cycle_time: float | None = None
    planned_tool_life: float | None = None
    actual_tool_life: float | None = None
    planned_cutting_data: dict = {}
    observed_cutting_data: dict = {}
    quality_result: str | None = None
    alarm_summary: str | None = None
    is_test_only: bool = False


class PredictRequest(BaseModel):
    record_id: str
    part_family: str | None = None
    material: str | None = None
    machine_class: str | None = None
    operation_type: str | None = None
    planned_cycle_time: float | None = None
    planned_tool_life: float | None = None
    planned_cutting_data: dict = {}


class WhatIfVcRequest(BaseModel):
    record_id: str
    material: str | None = None
    machine_class: str | None = None
    operation_type: str | None = None
    planned_cutting_data: dict = {}
    planned_cycle_time: float | None = None
    actual_cycle_time: float | None = None
    vc_change_pct: float = 0.05


class WhatIfMachineRequest(BaseModel):
    record_id: str
    material: str | None = None
    machine_class: str | None = None
    planned_cycle_time: float | None = None
    actual_cycle_time: float | None = None
    proposed_machine_class: str = ""


class RecommendationReviewRequest(BaseModel):
    recommendation_id: str
    new_status: str
    reviewer: str = "engineer"


class CuttingDataRecsRequest(BaseModel):
    record_id: str
    material: str | None = None
    machine_class: str | None = None
    operation_type: str | None = None
    baseline_cutting_data: dict = {}


class TradeOffRequest(BaseModel):
    description: str
    parameters_list: list[dict]
    objectives_list: list[dict]
    objective_names: list[str]
    minimize_objectives: list[str] = []


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/load-test-dataset")
async def load_test_dataset(_token=Depends(_require_user)):  # noqa: B008
    """Load TEST_ONLY aluminium turning dataset into session store."""
    global _record_store
    test_records = make_test_dataset_aluminium_turning()
    _record_store = test_records
    return {
        "loaded": len(test_records),
        "is_test_only": True,
        "source": "TEST_ONLY_SYNTHETIC",
    }


@router.post("/ingest-record")
async def ingest_record(req: IngestRecordRequest, _token=Depends(_require_user)):  # noqa: B008
    """Ingest a manufacturing learning record."""
    record = create_learning_record(
        record_id=req.record_id,
        part_family=req.part_family,
        material=req.material,
        machine_class=req.machine_class,
        operation_type=req.operation_type,
        planned_cycle_time=req.planned_cycle_time,
        actual_cycle_time=req.actual_cycle_time,
        planned_tool_life=req.planned_tool_life,
        actual_tool_life=req.actual_tool_life,
        planned_cutting_data=req.planned_cutting_data,
        observed_cutting_data=req.observed_cutting_data,
        quality_result=req.quality_result,
        alarm_summary=req.alarm_summary,
        is_test_only=req.is_test_only,
    )
    warnings = validate_learning_record(record)
    _record_store.append(record)
    return {"record_id": record.record_id, "warnings": warnings}


@router.get("/records")
async def list_records(_token=Depends(_require_user)):  # noqa: B008
    return {"count": len(_record_store), "is_test_only": all(r.is_test_only for r in _record_store)}


@router.post("/build-dataset")
async def build_dataset(_token=Depends(_require_user)):  # noqa: B008
    """Split records into train/validation/test sets."""
    if not _record_store:
        return {"status": "NO_RECORDS", "split": None}
    result = split_records(list(_record_store))
    return result.model_dump()


@router.post("/train")
async def train_model(_token=Depends(_require_user)):  # noqa: B008
    """Train median and nearest-neighbor models on current record store."""
    if not _record_store:
        return {"status": "NO_RECORDS_TO_TRAIN", "models": []}

    train_records = [r for r in _record_store if not r.is_fabricated]
    registry = get_registry()

    models = []
    for target in [PredictionTarget.CYCLE_TIME, PredictionTarget.TOOL_LIFE]:
        mid = f"median_{target.value.lower()}"
        predictor = MedianPredictor(target, model_id=mid)
        spec = predictor.train(train_records)
        registry.register(spec)
        _model_store[mid] = spec
        models.append(spec.model_dump())

    return {"trained": len(models), "models": models}


@router.post("/predict")
async def predict(req: PredictRequest, _token=Depends(_require_user)):  # noqa: B008
    """Predict cycle time for a query record."""
    query = ManufacturingLearningRecord(
        record_id=req.record_id,
        part_family=req.part_family,
        material=req.material,
        machine_class=req.machine_class,
        operation_type=req.operation_type,
        planned_cycle_time=req.planned_cycle_time,
        planned_tool_life=req.planned_tool_life,
        planned_cutting_data=req.planned_cutting_data,
        is_fabricated=False,
    )

    train_records = [r for r in _record_store if not r.is_fabricated]
    if not train_records:
        return {"status": "NO_TRAINING_DATA", "prediction": None}

    predictor = NearestNeighborPredictor(PredictionTarget.CYCLE_TIME, model_id="nn_live")
    predictor.train(train_records)
    pred = predictor.predict(query, f"PRED_{req.record_id}")
    return pred.model_dump()


@router.post("/similar-cases")
async def query_similar(req: PredictRequest, _token=Depends(_require_user)):  # noqa: B008
    """Find similar historical cases for a query record."""
    query = ManufacturingLearningRecord(
        record_id=req.record_id,
        material=req.material,
        machine_class=req.machine_class,
        operation_type=req.operation_type,
        planned_cutting_data=req.planned_cutting_data,
        planned_cycle_time=req.planned_cycle_time,
        is_fabricated=False,
    )
    similar = find_similar_cases(query, list(_record_store))
    return {"count": len(similar), "cases": [c.model_dump() for c in similar]}


@router.post("/cutting-data-recommendations")
async def cutting_data_recommendations(
    req: CuttingDataRecsRequest,
    _token=Depends(_require_user),  # noqa: B008
):
    """Generate cutting data review candidates."""
    recs = generate_cutting_data_recommendations(
        list(_record_store),
        req.baseline_cutting_data,
    )
    return {"count": len(recs), "recommendations": [r.model_dump() for r in recs]}


@router.post("/machine-recommendations")
async def machine_recommendations(
    req: PredictRequest,
    _token=Depends(_require_user),  # noqa: B008
):
    """Generate machine-class recommendation candidates."""
    recs = generate_machine_recommendations(list(_record_store), req.machine_class)
    return {"count": len(recs), "recommendations": [r.model_dump() for r in recs]}


@router.post("/tool-recommendations")
async def tool_recommendations(
    req: PredictRequest,
    _token=Depends(_require_user),  # noqa: B008
):
    """Generate tool recommendation candidates."""
    recs = generate_tool_recommendations(list(_record_store), None)
    return {"count": len(recs), "recommendations": [r.model_dump() for r in recs]}


@router.post("/what-if/vc-change")
async def what_if_vc(req: WhatIfVcRequest, _token=Depends(_require_user)):  # noqa: B008
    """Evaluate Vc change what-if scenario."""
    baseline = ManufacturingLearningRecord(
        record_id=req.record_id,
        material=req.material,
        machine_class=req.machine_class,
        planned_cutting_data=req.planned_cutting_data,
        planned_cycle_time=req.planned_cycle_time,
        actual_cycle_time=req.actual_cycle_time,
        is_fabricated=False,
    )
    scenario = run_what_if_vc_change(
        baseline,
        list(_record_store),
        vc_change_pct=req.vc_change_pct,
    )
    return scenario.model_dump()


@router.post("/what-if/machine-change")
async def what_if_machine(req: WhatIfMachineRequest, _token=Depends(_require_user)):  # noqa: B008
    """Evaluate machine class change what-if scenario."""
    baseline = ManufacturingLearningRecord(
        record_id=req.record_id,
        material=req.material,
        machine_class=req.machine_class,
        planned_cycle_time=req.planned_cycle_time,
        actual_cycle_time=req.actual_cycle_time,
        is_fabricated=False,
    )
    scenario = run_what_if_machine_change(
        baseline,
        list(_record_store),
        proposed_machine_class=req.proposed_machine_class,
    )
    return scenario.model_dump()


@router.post("/trade-off")
async def trade_off_analysis(req: TradeOffRequest, _token=Depends(_require_user)):  # noqa: B008
    """Compute trade-off analysis with Pareto front."""
    analysis = build_trade_off_analysis(
        req.description,
        req.parameters_list,
        req.objectives_list,
        req.objective_names,
        minimize_objectives=req.minimize_objectives,
    )
    return analysis.model_dump()


@router.get("/models")
async def list_models(_token=Depends(_require_user)):  # noqa: B008
    """List registered models."""
    registry = get_registry()
    models = registry.list_all()
    return {"count": len(models), "models": [m.model_dump() for m in models]}


@router.get("/quality-risk")
async def quality_risk(_token=Depends(_require_user)):  # noqa: B008
    """Estimate quality risk from current record store."""
    result = estimate_quality_risk(list(_record_store))
    return result.model_dump()


@router.get("/alarm-risk")
async def alarm_risk(_token=Depends(_require_user)):  # noqa: B008
    """Estimate alarm risk from current record store."""
    result = estimate_alarm_risk(list(_record_store))
    return result.model_dump()


@router.post("/drift/data")
async def data_drift(_token=Depends(_require_user)):  # noqa: B008
    """Detect data drift between first and second halves of the record store."""
    n = len(_record_store)
    if n < 10:
        return {"status": "INSUFFICIENT_DATA", "n": n}
    mid = n // 2
    report = detect_data_drift(list(_record_store[:mid]), list(_record_store[mid:]))
    return report.model_dump()


@router.get("/audit-log")
async def audit_log(_token=Depends(_require_user)):  # noqa: B008
    """Return current session audit log."""
    return {"count": len(_audit_log), "events": []}


# ---------------------------------------------------------------------------
# Forbidden endpoints — explicitly NOT implemented
# ---------------------------------------------------------------------------
# write-machine-parameter, apply-to-cnc, apply-feed-override,
# apply-spindle-override, apply-tool-offset, apply-work-offset,
# apply-cutting-data, apply-cam-change, apply-nc-change,
# auto-schedule-change, auto-dispatch
