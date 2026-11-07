"""
Level-14 Read-Only Connector Contract.

ALL connectors are READ-ONLY.
NO write methods are allowed.
NO machine-start, program-upload, or offset-write.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from .enums import AlarmState, ConnectionStatus, ConnectorType
from .models import ConnectorCapabilities, MachineStateSnapshot


class ReadOnlyConnector(ABC):
    """
    Abstract base for all shop-floor connectors.
    Connectors may only read machine state.
    No write, start, stop or upload methods are defined.
    """

    @property
    @abstractmethod
    def connector_type(self) -> ConnectorType: ...

    @property
    @abstractmethod
    def capabilities(self) -> ConnectorCapabilities: ...

    @abstractmethod
    def connect_read_only(self) -> ConnectionStatus: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def get_machine_state(self, machine_id: str) -> MachineStateSnapshot: ...

    @abstractmethod
    def get_alarm_state(self, machine_id: str) -> AlarmState: ...

    @abstractmethod
    def get_current_program_metadata(self, machine_id: str) -> dict: ...

    @abstractmethod
    def get_current_job_metadata(self, machine_id: str) -> dict: ...

    @abstractmethod
    def get_tool_state(self, machine_id: str) -> dict: ...

    @abstractmethod
    def get_queue_state(self, machine_id: str) -> dict: ...

    # --- Write operations are explicitly ABSENT ---
    # No write_program()
    # No start_machine()
    # No stop_machine()
    # No write_offsets()
    # No write_tool_data()
    # No upload_nc()
    # No dnc_send()
    # No ftp_transfer()
