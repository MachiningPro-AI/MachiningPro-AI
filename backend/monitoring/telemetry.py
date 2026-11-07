"""
Level-15 Simulated Telemetry.

TEST_ONLY — No real network, no real machine.
Provides deterministic synthetic production observations for tests.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .enums import (
    CycleState,
    DataQuality,
    ObservationSource,
    ObservationStatus,
)
from .models import ProductionObservation


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _uid() -> str:
    return str(uuid.uuid4())


def make_simulated_observation(
    machine_id: str,
    job_id: str,
    cycle_state: CycleState = CycleState.COMPLETE,
    actual_cycle_time: float | None = None,
    part_count: int | None = None,
    good_count: int | None = None,
    reject_count: int | None = None,
    alarm_codes: list[str] | None = None,
    tool_id: str | None = None,
    tool_usage_time: float | None = None,
    program_reference: str | None = None,
    program_hash: str | None = None,
    cutting_runtime: float | None = None,
    idle_runtime: float | None = None,
    alarm_runtime: float | None = None,
) -> ProductionObservation:
    """Create a deterministic synthetic observation (TEST_ONLY)."""
    return ProductionObservation(
        observation_id=_uid(),
        machine_id=machine_id,
        job_id=job_id,
        timestamp_start=_now(),
        timestamp_end=_now(),
        cycle_state=cycle_state,
        program_reference=program_reference,
        program_hash=program_hash,
        actual_cycle_time=actual_cycle_time,
        part_count=part_count,
        good_count=good_count,
        reject_count=reject_count,
        alarm_codes=alarm_codes or [],
        tool_id=tool_id,
        tool_usage_time=tool_usage_time,
        cutting_runtime=cutting_runtime,
        idle_runtime=idle_runtime,
        alarm_runtime=alarm_runtime,
        source=ObservationSource.SIMULATED_CONTROLLER,
        quality=DataQuality.RAW,
        status=ObservationStatus.COMPLETE,
        is_fabricated=False,
    )


# ---------------------------------------------------------------------------
# Standard test scenario factories
# ---------------------------------------------------------------------------


def test_machine_idle(machine_id: str = "TEST-M-001") -> ProductionObservation:
    """TEST_MACHINE_IDLE scenario."""
    return make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-IDLE",
        cycle_state=CycleState.IDLE,
    )


def test_machine_running(
    machine_id: str = "TEST-M-001",
    actual_cycle_time: float = 10.0,
) -> ProductionObservation:
    """TEST_MACHINE_RUNNING scenario."""
    return make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-RUN",
        cycle_state=CycleState.RUNNING,
        actual_cycle_time=actual_cycle_time,
        cutting_runtime=actual_cycle_time * 0.8,
        idle_runtime=actual_cycle_time * 0.2,
    )


def test_machine_alarm(
    machine_id: str = "TEST-M-001",
    alarm_code: str = "ALM-9001",
) -> ProductionObservation:
    """TEST_MACHINE_ALARM scenario."""
    return make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-ALARM",
        cycle_state=CycleState.ALARM,
        alarm_codes=[alarm_code],
        alarm_runtime=60.0,
    )


def test_machine_cycle_complete(
    machine_id: str = "TEST-M-001",
    actual_cycle_time: float = 10.0,
    good_count: int = 1,
    reject_count: int = 0,
) -> ProductionObservation:
    """TEST_MACHINE_CYCLE_COMPLETE scenario."""
    return make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-COMPLETE",
        cycle_state=CycleState.COMPLETE,
        actual_cycle_time=actual_cycle_time,
        part_count=(good_count or 0) + (reject_count or 0),
        good_count=good_count,
        reject_count=reject_count,
        cutting_runtime=actual_cycle_time * 0.75,
        idle_runtime=actual_cycle_time * 0.25,
    )


def test_program_mismatch(
    machine_id: str = "TEST-M-001",
) -> ProductionObservation:
    """Test case: observed program hash differs from planned."""
    return make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-MISMATCH",
        cycle_state=CycleState.COMPLETE,
        program_reference="O0001",
        program_hash="observed_hash_differs_from_planned",
        actual_cycle_time=11.0,
    )


def test_missing_telemetry(
    machine_id: str = "TEST-M-001",
) -> ProductionObservation:
    """Test case: missing telemetry — most fields None."""
    return make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-MISSING",
        cycle_state=CycleState.UNKNOWN,
    )


def test_duplicate_telemetry(
    machine_id: str = "TEST-M-001",
    actual_cycle_time: float = 10.0,
) -> tuple[ProductionObservation, ProductionObservation]:
    """Test case: two structurally identical observations (duplicate test)."""
    obs1 = test_machine_cycle_complete(machine_id, actual_cycle_time)
    obs2 = make_simulated_observation(
        machine_id=machine_id,
        job_id="TEST-JOB-COMPLETE",
        cycle_state=CycleState.COMPLETE,
        actual_cycle_time=actual_cycle_time,
        part_count=1,
        good_count=1,
        reject_count=0,
    )
    return obs1, obs2
