"""
Level-15 Learning Dataset Foundation.

Normalized records for future learning.
Provenance is preserved.
Sensitive identifiers are anonymized by default.
No customer names, no machine credentials, no filesystem paths.
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from .enums import DataQuality
from .models import LearningRecord, PlannedActualComparison, ProductionObservation


def _uid() -> str:
    return str(uuid.uuid4())


def _provenance_hash(
    observation_id: str,
    machine_id: str,
    job_id: str,
) -> str:
    """Create a one-way hash of identifying fields for provenance."""
    raw = "|".join([observation_id, machine_id, job_id])
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def create_learning_record(
    observation: ProductionObservation,
    comparison: PlannedActualComparison | None = None,
    material: str | None = None,
    feature_process: str | None = None,
    machine_class: str | None = None,
    cutting_parameters: dict[str, Any] | None = None,
    quality_outcome: str | None = None,
    alarm_outcome: str | None = None,
    anonymize: bool = True,
) -> LearningRecord:
    """
    Create a normalized learning record from an observation.

    anonymize=True (default) suppresses raw identifiers.
    Provenance is preserved as a one-way hash.
    """
    prov = _provenance_hash(
        observation.observation_id,
        observation.machine_id,
        observation.job_id,
    )

    planned_ct: float | None = None
    if comparison is not None:
        planned_ct = comparison.planned_cycle_time

    alarm_out = alarm_outcome
    if alarm_out is None:
        if observation.alarm_codes:
            alarm_out = "ALARM_PRESENT"
        else:
            alarm_out = "NO_ALARM"

    tool_life: float | None = observation.tool_usage_time

    return LearningRecord(
        record_id=_uid(),
        material=material,
        feature_process=feature_process,
        machine_class=machine_class,
        tool_id=None if anonymize else observation.tool_id,
        planned_cycle_time=planned_ct,
        actual_cycle_time=observation.actual_cycle_time,
        tool_life=tool_life,
        quality_outcome=quality_outcome,
        alarm_outcome=alarm_out,
        cutting_parameters=cutting_parameters or {},
        source=observation.source,
        data_quality=observation.quality,
        is_anonymized=anonymize,
        anonymization_policy="DEFAULT",
        provenance_hash=prov,
    )


def anonymize_learning_records(
    records: list[LearningRecord],
) -> list[LearningRecord]:
    """
    Ensure all records have sensitive fields suppressed.

    Returns new record objects with tool_id=None and is_anonymized=True.
    """
    cleaned: list[LearningRecord] = []
    for rec in records:
        cleaned.append(
            rec.model_copy(
                update={"tool_id": None, "is_anonymized": True}
            )
        )
    return cleaned


def validate_learning_record(record: LearningRecord) -> list[str]:
    """
    Validate a learning record for dataset quality.

    Returns a list of warnings (empty = valid).
    """
    warnings: list[str] = []
    if record.provenance_hash is None:
        warnings.append("MISSING_PROVENANCE_HASH")
    if record.actual_cycle_time is not None and record.actual_cycle_time <= 0:
        warnings.append("INVALID_ACTUAL_CYCLE_TIME_ZERO_OR_NEGATIVE")
    if record.planned_cycle_time is not None and record.planned_cycle_time <= 0:
        warnings.append("INVALID_PLANNED_CYCLE_TIME_ZERO_OR_NEGATIVE")
    if record.data_quality == DataQuality.UNKNOWN:
        warnings.append("DATA_QUALITY_UNKNOWN")
    if not record.is_anonymized:
        warnings.append("RECORD_NOT_ANONYMIZED")
    return warnings
