"""MC-1: Machine Library pipeline adapter.

Opt-in bridge between backend.machine_library and the production pipeline.
The legacy compatibility engine (backend.compatibility.engine) is NOT modified;
its backend.machines.seed_catalog catalog (37 machines) remains the default.

Only callers that explicitly instantiate MachinePipelineAdapter receive
new-library behaviour.

Design constraints:
  LEGACY_PIPELINE_UNCHANGED=YES   — backend.machines.* untouched
  OPT_IN_ONLY=YES                  — no automatic activation
  UNKNOWN_FOR_MISSING=YES          — missing spindle data → UNKNOWN, not FAIL
  CAT40_NE_BT40=YES                — different families enforced by normalizer
  FABRICATED_SPEC=NO
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.machine_library.interfaces import (
    InterfaceVerificationStatus,
    NormalizedMachineInterface,
    normalize_interface_string,
)
from backend.machine_library.models import MachineCatalogRecord
from backend.machine_library.registry import MachineCatalogError, MachineCatalogRegistry
from backend.machine_library.seed_catalog import seed_machine_library

__all__ = [
    "MachineLookupStatus",
    "MachineLookupResult",
    "MachinePipelineAdapter",
]


class MachineLookupStatus(StrEnum):
    RESOLVED = "RESOLVED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class MachineLookupResult:
    status: MachineLookupStatus
    record: MachineCatalogRecord | None
    # Normalized spindle interface; None when no interface data present.
    normalized_spindle: NormalizedMachineInterface | None


class MachinePipelineAdapter:
    """Opt-in adapter: wraps Machine Library for production-planning pipeline use.

    Instantiate once per planning session and call lookup() with a stable_id.
    Missing machines or missing spindle interface data return UNKNOWN — never
    promoted to FAIL or PASS without evidence.
    CAT-40 and BT-40 are distinct families and are never treated as equivalent.

    The legacy compatibility engine (backend.compatibility.engine) uses
    backend.machines.seed_catalog and is unaffected by this adapter.
    """

    def __init__(self, registry: MachineCatalogRegistry | None = None) -> None:
        if registry is None:
            registry = MachineCatalogRegistry()
            for rec in seed_machine_library():
                registry.register(rec)
        self._registry = registry

    def lookup(self, stable_id: str) -> MachineLookupResult:
        """Return RESOLVED if the machine is in the catalog, UNKNOWN otherwise."""
        try:
            record = self._registry.get(stable_id)
        except MachineCatalogError:
            return MachineLookupResult(
                status=MachineLookupStatus.UNKNOWN,
                record=None,
                normalized_spindle=None,
            )
        normalized_spindle = self.normalize_spindle(record.spindle.interface)
        return MachineLookupResult(
            status=MachineLookupStatus.RESOLVED,
            record=record,
            normalized_spindle=normalized_spindle,
        )

    def normalize_spindle(
        self, raw: str | None
    ) -> NormalizedMachineInterface | None:
        """Normalize a raw spindle interface string using Machine Library rules.

        Returns None when raw is None — missing interface stays UNKNOWN, not PASS.
        CAT-40 and BT-40 resolve to distinct InterfaceFamily values.
        """
        if raw is None:
            return None
        return normalize_interface_string(
            raw,
            source_note="MachineCatalogRecord.spindle.interface",
            verification_status=InterfaceVerificationStatus.MANUFACTURER_CONFIRMED,
        )

    def is_process_capable(
        self, record: MachineCatalogRecord, operation: str
    ) -> bool | None:
        """Return True/False for known process capability, None when unavailable.

        None (caller must treat as UNKNOWN) is returned when the operation
        cannot be mapped to a capability flag on this record.
        """
        op = operation.lower().strip()
        cap = record.capability
        mapping: dict[str, bool | None] = {
            "milling": cap.milling_capable,
            "turning": cap.turning_capable,
            "drilling": cap.drilling_capable,
            "grinding": cap.grinding_capable,
            "edm": cap.edm_capable,
            "tapping": cap.capable_tapping,
            "boring": cap.capable_boring,
            "threading": cap.capable_threading,
            "reaming": cap.capable_reaming,
        }
        return mapping.get(op)
