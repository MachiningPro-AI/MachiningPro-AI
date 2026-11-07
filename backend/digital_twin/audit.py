"""Level-18 Digital Twin — audit trail.

Records events for every scenario lifecycle step.
Immutable once written — no event is modified or deleted.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .enums import AuditEventType
from .models import TwinAuditEvent


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _short_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def record_scenario_created(
    scenario_id: str,
    scenario_type: str,
    baseline_ref: str | None,
    actor: str = "system",
) -> TwinAuditEvent:
    payload = {
        "scenario_id": scenario_id,
        "scenario_type": scenario_type,
        "baseline_ref": baseline_ref,
    }
    return TwinAuditEvent(
        event_type=AuditEventType.SCENARIO_CREATED,
        scenario_id=scenario_id,
        actor=actor,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def record_scenario_simulated(
    scenario_id: str,
    status: str,
    fidelity: str,
    constraint_failure_count: int,
    actor: str = "system",
) -> TwinAuditEvent:
    payload = {
        "scenario_id": scenario_id,
        "status": status,
        "fidelity": fidelity,
        "constraint_failure_count": constraint_failure_count,
    }
    return TwinAuditEvent(
        event_type=AuditEventType.SCENARIO_SIMULATED,
        scenario_id=scenario_id,
        actor=actor,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def record_comparison_run(
    baseline_id: str,
    scenario_id: str,
    kpi_diff_count: int,
    unknown_diff_count: int,
    actor: str = "system",
) -> TwinAuditEvent:
    payload = {
        "baseline_id": baseline_id,
        "scenario_id": scenario_id,
        "kpi_diff_count": kpi_diff_count,
        "unknown_diff_count": unknown_diff_count,
    }
    return TwinAuditEvent(
        event_type=AuditEventType.COMPARISON_RUN,
        scenario_id=scenario_id,
        actor=actor,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def record_pareto_calculated(
    scenario_ids: list[str],
    non_dominated_count: int,
    actor: str = "system",
) -> TwinAuditEvent:
    payload = {
        "scenario_ids": scenario_ids,
        "non_dominated_count": non_dominated_count,
    }
    # Use the first scenario_id as the anchor
    anchor = scenario_ids[0] if scenario_ids else "PARETO"
    return TwinAuditEvent(
        event_type=AuditEventType.PARETO_CALCULATED,
        scenario_id=anchor,
        actor=actor,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def record_recommendation_generated(
    scenario_id: str,
    recommendation_type: str,
    data_fidelity: str,
    actor: str = "system",
) -> TwinAuditEvent:
    payload = {
        "scenario_id": scenario_id,
        "recommendation_type": recommendation_type,
        "data_fidelity": data_fidelity,
    }
    return TwinAuditEvent(
        event_type=AuditEventType.RECOMMENDATION_GENERATED,
        scenario_id=scenario_id,
        actor=actor,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def record_scenario_reviewed(
    scenario_id: str,
    review_outcome: str,
    reviewer: str,
    notes: str = "",
) -> TwinAuditEvent:
    payload = {
        "scenario_id": scenario_id,
        "review_outcome": review_outcome,
        "reviewer": reviewer,
        "notes": notes,
    }
    return TwinAuditEvent(
        event_type=AuditEventType.SCENARIO_REVIEWED,
        scenario_id=scenario_id,
        actor=reviewer,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def record_scenario_stale(
    scenario_id: str,
    stale_reason: str,
    actor: str = "system",
) -> TwinAuditEvent:
    payload = {
        "scenario_id": scenario_id,
        "stale_reason": stale_reason,
    }
    return TwinAuditEvent(
        event_type=AuditEventType.SCENARIO_STALE,
        scenario_id=scenario_id,
        actor=actor,
        timestamp=_now_utc(),
        payload=payload,
        event_hash=_short_hash(payload),
    )


def verify_audit_integrity(events: list[TwinAuditEvent]) -> bool:
    """Verify no event has been tampered with post-recording."""
    for event in events:
        expected = _short_hash(event.payload)
        if event.event_hash != expected:
            return False
    return True
