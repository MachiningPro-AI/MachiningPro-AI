"""Deterministic, fail-closed Material Catalog Registry.

Design constraints
------------------
FAIL_CLOSED=YES          — unknown stable_id returns None, never raises
DUPLICATE_ID_RAISES=YES  — duplicate stable_id at load time raises MaterialCatalogError
MISSING_RECORD_AS_NONE=YES  — get() returns None for unknown ids
"""

from __future__ import annotations

from backend.material_library.enums import MaterialFamily, MaterialISOGroup, MaterialSubGroup
from backend.material_library.models import MaterialCatalogRecord

__all__ = [
    "MaterialCatalogError",
    "MaterialCatalogRegistry",
]


class MaterialCatalogError(Exception):
    """Raised when the catalog is in an invalid state (duplicate id, etc.)."""


class MaterialCatalogRegistry:
    """Read-only registry of MaterialCatalogRecord instances.

    Loaded once at construction time from a list of records.
    All lookups are deterministic and fail-closed.
    """

    def __init__(self, records: list[MaterialCatalogRecord]) -> None:
        self._by_id: dict[str, MaterialCatalogRecord] = {}
        for rec in records:
            if rec.stable_id in self._by_id:
                raise MaterialCatalogError(
                    f"Duplicate stable_id in material catalog: {rec.stable_id!r}"
                )
            self._by_id[rec.stable_id] = rec

    # ------------------------------------------------------------------
    # Primary lookup
    # ------------------------------------------------------------------

    def get(self, stable_id: str) -> MaterialCatalogRecord | None:
        """Return the record for *stable_id*, or None if not found."""
        return self._by_id.get(stable_id)

    def all(self) -> list[MaterialCatalogRecord]:
        """Return all records in insertion order."""
        return list(self._by_id.values())

    # ------------------------------------------------------------------
    # Filtered lookups
    # ------------------------------------------------------------------

    def by_iso_group(self, group: MaterialISOGroup) -> list[MaterialCatalogRecord]:
        """Return all records with the given ISO group."""
        return [r for r in self._by_id.values() if r.iso_group is group]

    def by_subgroup(self, subgroup: MaterialSubGroup) -> list[MaterialCatalogRecord]:
        """Return all records with the given ISO sub-group."""
        return [r for r in self._by_id.values() if r.iso_subgroup is subgroup]

    def by_family(self, family: MaterialFamily) -> list[MaterialCatalogRecord]:
        """Return all records with the given material family."""
        return [r for r in self._by_id.values() if r.material_family is family]

    def find_by_alias(self, alias: str) -> list[MaterialCatalogRecord]:
        """Case-insensitive search across designation and all aliases.

        Returns every record whose primary designation or any alias matches
        *alias* exactly (after stripping and uppercasing).
        Empty list when nothing matches — never raises.
        """
        norm = alias.strip().upper()
        result: list[MaterialCatalogRecord] = []
        for rec in self._by_id.values():
            if rec.designation.strip().upper() == norm:
                result.append(rec)
                continue
            if any(a.strip().upper() == norm for a in rec.designation_detail.aliases):
                result.append(rec)
        return result

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._by_id)

    def __contains__(self, stable_id: object) -> bool:
        if not isinstance(stable_id, str):
            return False
        return stable_id in self._by_id

    def __repr__(self) -> str:
        return f"MaterialCatalogRegistry({len(self)} records)"
