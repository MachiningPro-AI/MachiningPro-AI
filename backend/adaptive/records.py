"""Level-16 Manufacturing Learning Record management and synthetic test data."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from .enums import SplitRole
from .models import ManufacturingLearningRecord


def _make_record_hash(record_id: str, machine_class: str, operation_type: str) -> str:
    raw = f"{record_id}|{machine_class}|{operation_type}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def create_learning_record(
    record_id: str,
    *,
    part_family: str | None = None,
    material: str | None = None,
    machine_class: str | None = None,
    operation_type: str | None = None,
    tool_family: str | None = None,
    planned_cycle_time: float | None = None,
    actual_cycle_time: float | None = None,
    planned_tool_life: float | None = None,
    actual_tool_life: float | None = None,
    planned_cutting_data: dict | None = None,
    observed_cutting_data: dict | None = None,
    quality_result: str | None = None,
    alarm_summary: str | None = None,
    source: str = "HISTORICAL_DATA",
    data_quality: str = "VALIDATED",
    is_test_only: bool = False,
    split_role: SplitRole | None = None,
    anonymize: bool = True,
) -> ManufacturingLearningRecord:
    prov = _make_record_hash(
        record_id,
        machine_class or "UNKNOWN",
        operation_type or "UNKNOWN",
    )
    machine_anon = prov[:8] if anonymize and machine_class else machine_class
    return ManufacturingLearningRecord(
        record_id=record_id,
        part_family=part_family,
        material=material,
        machine_class=machine_class,
        machine_id_anonymized=machine_anon,
        tool_family=tool_family,
        operation_type=operation_type,
        planned_cutting_data=planned_cutting_data or {},
        observed_cutting_data=observed_cutting_data or {},
        planned_cycle_time=planned_cycle_time,
        actual_cycle_time=actual_cycle_time,
        planned_tool_life=planned_tool_life,
        actual_tool_life=actual_tool_life,
        quality_result=quality_result,
        alarm_summary=alarm_summary,
        source=source,
        provenance=prov,
        data_quality=data_quality,
        timestamp=datetime.now(UTC).isoformat(),
        is_fabricated=False,
        is_test_only=is_test_only,
        split_role=split_role,
    )


def validate_learning_record(record: ManufacturingLearningRecord) -> list[str]:
    """Return list of validation warnings; empty list means record is acceptable."""
    warnings: list[str] = []
    if record.is_fabricated:
        warnings.append("RECORD_IS_FABRICATED — not usable for real training")
    if record.actual_cycle_time is not None and record.actual_cycle_time <= 0:
        warnings.append("INVALID_CYCLE_TIME — actual_cycle_time must be positive")
    if record.actual_tool_life is not None and record.actual_tool_life < 0:
        warnings.append("INVALID_TOOL_LIFE — actual_tool_life must be non-negative")
    if record.data_quality == "UNKNOWN":
        warnings.append("UNKNOWN_DATA_QUALITY — record may not be usable")
    if not record.material:
        warnings.append("MISSING_MATERIAL — reduces prediction fidelity")
    if not record.machine_class:
        warnings.append("MISSING_MACHINE_CLASS — reduces prediction fidelity")
    if not record.operation_type:
        warnings.append("MISSING_OPERATION_TYPE — reduces prediction fidelity")
    return warnings


# ---------------------------------------------------------------------------
# TEST_ONLY synthetic dataset factory
# ---------------------------------------------------------------------------

def make_test_dataset_aluminium_turning() -> list[ManufacturingLearningRecord]:
    """Return TEST_ONLY synthetic aluminium turning records."""
    base_params = [
        (120.0, 115.0, 80.0, 72.0),
        (120.0, 118.0, 80.0, 75.0),
        (120.0, 122.0, 80.0, 68.0),
        (120.0, 110.0, 80.0, 90.0),
        (120.0, 125.0, 80.0, 65.0),
        (120.0, 116.0, 80.0, 71.0),
        (120.0, 119.0, 80.0, 74.0),
        (120.0, 121.0, 80.0, 69.0),
    ]
    records = []
    for i, (pct, act, ptl, atl) in enumerate(base_params, start=1):
        records.append(create_learning_record(
            record_id=f"TEST_AL_TURN_{i:03d}",
            part_family="DISC_FAMILY",
            material="AL_6082_T6",
            machine_class="CNC_TURNING_CENTER",
            operation_type="FINISH_TURNING",
            planned_cycle_time=pct,
            actual_cycle_time=act,
            planned_tool_life=ptl,
            actual_tool_life=atl,
            planned_cutting_data={"vc": 300.0, "fn": 0.15, "ap": 1.0},
            observed_cutting_data={"vc": 298.0, "fn": 0.15, "ap": 1.0},
            quality_result="PASS",
            alarm_summary="NONE",
            source="HISTORICAL_DATA",
            data_quality="VALIDATED",
            is_test_only=True,
        ))
    return records


def make_test_record_missing_data() -> ManufacturingLearningRecord:
    """TEST_ONLY record with intentional missing fields."""
    return create_learning_record(
        record_id="TEST_MISSING_001",
        material=None,
        machine_class=None,
        operation_type=None,
        actual_cycle_time=None,
        is_test_only=True,
        data_quality="UNKNOWN",
    )


def make_test_record_out_of_domain() -> ManufacturingLearningRecord:
    """TEST_ONLY record for out-of-domain material."""
    return create_learning_record(
        record_id="TEST_OOD_001",
        material="INCONEL_718",
        machine_class="FIVE_AXIS_MILL",
        operation_type="ROUGHING_MILLING",
        planned_cycle_time=600.0,
        actual_cycle_time=720.0,
        is_test_only=True,
    )
