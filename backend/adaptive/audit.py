"""Level-16 Adaptive intelligence audit trail."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .enums import AdaptiveAuditEventType
from .models import AdaptiveAuditEvent


def _now() -> str:
    return datetime.now(UTC).isoformat()


def audit_model_trained(
    model_id: str,
    sample_count: int,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.MODEL_TRAINED,
        timestamp=_now(),
        actor=actor,
        model_ref=model_id,
        details={"sample_count": sample_count},
    )


def audit_model_evaluated(
    model_id: str,
    validation_mae: float | None,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.MODEL_EVALUATED,
        timestamp=_now(),
        actor=actor,
        model_ref=model_id,
        details={"validation_mae": validation_mae},
    )


def audit_prediction_created(
    prediction_id: str,
    model_id: str | None,
    target: str,
    fidelity: str,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.PREDICTION_CREATED,
        timestamp=_now(),
        actor=actor,
        prediction_ref=prediction_id,
        model_ref=model_id,
        details={"target": target, "fidelity": fidelity},
    )


def audit_recommendation_created(
    recommendation_id: str,
    rec_type: str,
    fidelity: str,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.RECOMMENDATION_CREATED,
        timestamp=_now(),
        actor=actor,
        recommendation_ref=recommendation_id,
        details={"recommendation_type": rec_type, "fidelity": fidelity},
    )


def audit_recommendation_reviewed(
    recommendation_id: str,
    new_status: str,
    reviewer: str,
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.RECOMMENDATION_REVIEWED,
        timestamp=_now(),
        actor=reviewer,
        recommendation_ref=recommendation_id,
        details={"new_status": new_status},
    )


def audit_what_if_evaluated(
    scenario_id: str,
    status: str,
    fidelity: str,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.WHAT_IF_EVALUATED,
        timestamp=_now(),
        actor=actor,
        details={"scenario_id": scenario_id, "status": status, "fidelity": fidelity},
    )


def audit_data_drift_detected(
    report_id: str,
    attribute: str,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.DATA_DRIFT_DETECTED,
        timestamp=_now(),
        actor=actor,
        details={"report_id": report_id, "attribute": attribute},
    )


def audit_model_drift_detected(
    report_id: str,
    model_id: str,
    actor: str = "system",
) -> AdaptiveAuditEvent:
    return AdaptiveAuditEvent(
        event_id=str(uuid.uuid4())[:8],
        event_type=AdaptiveAuditEventType.MODEL_DRIFT_DETECTED,
        timestamp=_now(),
        actor=actor,
        model_ref=model_id,
        details={"report_id": report_id},
    )
