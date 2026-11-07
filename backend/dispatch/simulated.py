"""
Level-14 Simulated CNC Controller.

TEST_ONLY
NO_REAL_NETWORK
NO_REAL_MACHINE

This controller is fully synthetic and deterministic.
It never opens a real network connection.
It never touches a real CNC, PLC, or industrial controller.
"""

from __future__ import annotations

from datetime import UTC, datetime

from .connector import ReadOnlyConnector
from .enums import (
    AlarmState,
    ConnectionStatus,
    ConnectorType,
    CycleState,
    MachineMode,
    SimulatedMachineState,
)
from .models import ConnectorCapabilities, MachineStateSnapshot


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SimulatedCNCController(ReadOnlyConnector):
    """
    Synthetic test controller with deterministic state transitions.

    CERTIFICATION=TEST_ONLY
    NO_REAL_NETWORK=YES
    NO_REAL_MACHINE=YES

    Use set_state() to configure deterministic test scenarios.
    """

    CERTIFICATION: str = "TEST_ONLY"
    SOURCE: str = "SIMULATED_TEST"

    def __init__(
        self,
        machine_id: str,
        initial_state: SimulatedMachineState = SimulatedMachineState.IDLE,
    ) -> None:
        self._machine_id = machine_id
        self._state = initial_state
        self._connected = False
        self._current_program: str | None = None
        self._current_job: str | None = None

    @property
    def managed_machine_id(self) -> str:
        """The machine this controller manages."""
        return self._machine_id

    def set_state(self, state: SimulatedMachineState) -> None:
        """Test helper: configure deterministic machine state."""
        self._state = state

    def set_program(self, program: str | None) -> None:
        """Test helper: set current program metadata."""
        self._current_program = program

    def set_job(self, job: str | None) -> None:
        """Test helper: set current job metadata."""
        self._current_job = job

    @property
    def connector_type(self) -> ConnectorType:
        return ConnectorType.SIMULATED

    @property
    def capabilities(self) -> ConnectorCapabilities:
        return ConnectorCapabilities(
            READ_MACHINE_STATE=True,
            READ_ALARMS=True,
            READ_PROGRAM_METADATA=True,
            READ_TOOL_STATE=True,
            READ_QUEUE_STATE=True,
            READ_WORK_OFFSETS=False,
            WRITE_PROGRAM=False,
            START_MACHINE=False,
            STOP_MACHINE=False,
            WRITE_OFFSETS=False,
            WRITE_TOOL_DATA=False,
        )

    def connect_read_only(self) -> ConnectionStatus:
        self._connected = True
        return ConnectionStatus.CONNECTED

    def disconnect(self) -> None:
        self._connected = False

    def get_machine_state(self, machine_id: str) -> MachineStateSnapshot:
        if machine_id != self._machine_id:
            return MachineStateSnapshot(
                machine_id=machine_id,
                timestamp=_now(),
                connection_status=ConnectionStatus.UNKNOWN,
                availability="UNKNOWN",
                alarm_state=AlarmState.UNKNOWN,
                source=self.SOURCE,
                quality=self.CERTIFICATION,
                connector_type=ConnectorType.SIMULATED,
                warnings=["MACHINE_IDENTITY_MISMATCH: not managed by this controller"],
            )
        conn = (
            ConnectionStatus.CONNECTED if self._connected else ConnectionStatus.UNKNOWN
        )
        alarm = (
            AlarmState.ALARM
            if self._state == SimulatedMachineState.ALARM
            else AlarmState.NO_ALARM
        )
        cycle = (
            CycleState.RUNNING
            if self._state == SimulatedMachineState.BUSY
            else CycleState.IDLE
        )
        mode = (
            MachineMode.AUTO
            if self._state
            in (SimulatedMachineState.BUSY, SimulatedMachineState.READY_FOR_TEST_DISPATCH)
            else MachineMode.UNKNOWN
        )
        return MachineStateSnapshot(
            machine_id=machine_id,
            timestamp=_now(),
            connection_status=conn,
            availability=self._state.value,
            mode=mode,
            current_program=self._current_program,
            current_job=self._current_job,
            alarm_state=alarm,
            cycle_state=cycle,
            source=self.SOURCE,
            quality=self.CERTIFICATION,
            connector_type=ConnectorType.SIMULATED,
            is_fabricated=False,
            is_real_machine_write=False,
        )

    def get_alarm_state(self, machine_id: str) -> AlarmState:
        if machine_id != self._machine_id:
            return AlarmState.UNKNOWN
        return (
            AlarmState.ALARM
            if self._state == SimulatedMachineState.ALARM
            else AlarmState.NO_ALARM
        )

    def get_current_program_metadata(self, machine_id: str) -> dict:
        if machine_id != self._machine_id:
            return {"error": "MACHINE_IDENTITY_MISMATCH", "program": None}
        return {
            "machine_id": machine_id,
            "program": self._current_program,
            "source": self.SOURCE,
            "certification": self.CERTIFICATION,
        }

    def get_current_job_metadata(self, machine_id: str) -> dict:
        if machine_id != self._machine_id:
            return {"error": "MACHINE_IDENTITY_MISMATCH", "job": None}
        return {
            "machine_id": machine_id,
            "job": self._current_job,
            "source": self.SOURCE,
            "certification": self.CERTIFICATION,
        }

    def get_tool_state(self, machine_id: str) -> dict:
        if machine_id != self._machine_id:
            return {"error": "MACHINE_IDENTITY_MISMATCH"}
        return {
            "machine_id": machine_id,
            "tool_state": "UNKNOWN",
            "source": self.SOURCE,
            "certification": self.CERTIFICATION,
        }

    def get_queue_state(self, machine_id: str) -> dict:
        if machine_id != self._machine_id:
            return {"error": "MACHINE_IDENTITY_MISMATCH"}
        busy = self._state == SimulatedMachineState.BUSY
        return {
            "machine_id": machine_id,
            "queue_depth": 1 if busy else 0,
            "source": self.SOURCE,
            "certification": self.CERTIFICATION,
        }
