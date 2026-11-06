"""Machine Library catalog registry.

Provides deterministic registration and lookup of MachineCatalogRecord
instances.  All queries return deterministic (sorted) results.

Lookup semantics
----------------
* Exact stable_id lookup raises MachineCatalogError when absent.
* Collection queries return sorted tuples (deterministic).
* Duplicate stable_id is rejected at registration (fail closed).
* No ranking, no fuzzy search, no AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.machine_library.enums import MachineClass
from backend.machine_library.models import MachineCatalogRecord

__all__ = ["MachineCatalogRegistry", "MachineCatalogError"]


class MachineCatalogError(Exception):
    """Raised by the MachineCatalogRegistry on invalid operations."""


@dataclass
class MachineCatalogRegistry:
    """In-memory registry of MachineCatalogRecord instances.

    All mutation goes through :meth:`register`.
    """

    _records: dict[str, MachineCatalogRecord] = field(
        default_factory=dict, init=False
    )

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, record: MachineCatalogRecord) -> MachineCatalogRecord:
        """Register *record*; raise on duplicate stable_id.

        Args:
            record: A fully constructed MachineCatalogRecord.

        Returns:
            The registered record (same object).

        Raises:
            TypeError:            when *record* is not a MachineCatalogRecord.
            MachineCatalogError:  when stable_id is already registered.
        """
        if not isinstance(record, MachineCatalogRecord):
            raise TypeError("only MachineCatalogRecord instances can be registered")
        if record.stable_id in self._records:
            raise MachineCatalogError(
                f"stable_id {record.stable_id!r} is already registered"
            )
        self._records[record.stable_id] = record
        return record

    # ------------------------------------------------------------------
    # Exact-ID lookup
    # ------------------------------------------------------------------

    def get(self, stable_id: str) -> MachineCatalogRecord:
        """Return the record with *stable_id*.

        Raises:
            MachineCatalogError: when not registered.
        """
        record = self._records.get(stable_id)
        if record is None:
            raise MachineCatalogError(f"no record with stable_id {stable_id!r}")
        return record

    def has(self, stable_id: str) -> bool:
        """True when *stable_id* is registered."""
        return stable_id in self._records

    # ------------------------------------------------------------------
    # Collection queries
    # ------------------------------------------------------------------

    def find_by_class(
        self, machine_class: MachineClass
    ) -> tuple[MachineCatalogRecord, ...]:
        """All records of the given MachineClass, sorted by stable_id."""
        return tuple(
            sorted(
                (
                    r for r in self._records.values()
                    if r.capability.machine_class is machine_class
                ),
                key=lambda r: r.stable_id,
            )
        )

    def find_by_manufacturer(
        self, manufacturer: str
    ) -> tuple[MachineCatalogRecord, ...]:
        """All records from *manufacturer* (case-insensitive), sorted."""
        m = manufacturer.lower()
        return tuple(
            sorted(
                (
                    r for r in self._records.values()
                    if r.manufacturer.lower() == m
                ),
                key=lambda r: r.stable_id,
            )
        )

    def find_capable(
        self,
        *,
        turning: bool = False,
        milling: bool = False,
        drilling: bool = False,
        grinding: bool = False,
        edm: bool = False,
    ) -> tuple[MachineCatalogRecord, ...]:
        """All records satisfying ALL specified capability flags."""
        def match(r: MachineCatalogRecord) -> bool:
            c = r.capability
            if turning and not c.turning_capable:
                return False
            if milling and not c.milling_capable:
                return False
            if drilling and not c.drilling_capable:
                return False
            if grinding and not c.grinding_capable:
                return False
            if edm and not c.edm_capable:
                return False
            return True

        return tuple(
            sorted(
                (r for r in self._records.values() if match(r)),
                key=lambda r: r.stable_id,
            )
        )

    def all(self) -> tuple[MachineCatalogRecord, ...]:
        """All registered records sorted by stable_id."""
        return tuple(sorted(self._records.values(), key=lambda r: r.stable_id))

    def stable_ids(self) -> tuple[str, ...]:
        """All registered stable_ids in registration order."""
        return tuple(self._records)

    def classes_present(self) -> frozenset[MachineClass]:
        """The set of machine classes represented in the registry."""
        return frozenset(r.capability.machine_class for r in self._records.values())

    def manufacturer_names(self) -> tuple[str, ...]:
        """Distinct manufacturer names in sorted order."""
        return tuple(sorted({r.manufacturer for r in self._records.values()}))

    def __len__(self) -> int:
        return len(self._records)

    def __contains__(self, stable_id: str) -> bool:
        return self.has(stable_id)
