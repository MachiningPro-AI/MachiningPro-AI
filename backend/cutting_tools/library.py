"""ToolLibrary — query interface over the cutting tool catalog.

Usage
-----
    from backend.cutting_tools import ToolLibrary

    lib = ToolLibrary()

    # All 8 mm through-coolant drills that cut ISO P and M steel:
    drills = (
        lib.query()
        .by_family(ToolFamily.DRILLING)
        .by_diameter(min_mm=7.9, max_mm=8.1)
        .by_material_groups(["P", "M"])
        .by_through_coolant(True)
        .results()
    )

    # Quick one-shot helpers:
    turning_inserts = lib.by_family(ToolFamily.TURNING)
    summary = lib.summary()
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .catalog_models import CuttingToolCatalogRecord, CuttingToolCatalogSummary
from .families import ToolFamily, category_codes_for_family
from .seed_catalog import get_catalog


class ToolLibraryQuery:
    """Chainable, immutable filter chain over catalog records.

    Each filter method returns a *new* query object so chains can be branched
    without side-effects.
    """

    __slots__ = ("_records",)

    def __init__(self, records: list[CuttingToolCatalogRecord]) -> None:
        self._records = records

    # ── Filter methods ────────────────────────────────────────────────────────

    def by_family(self, family: ToolFamily) -> ToolLibraryQuery:
        """Keep only tools whose tool_category_code maps to *family*."""
        codes = category_codes_for_family(family)
        return ToolLibraryQuery(
            [r for r in self._records if r.tool_category_code in codes]
        )

    def by_operation(self, operation: str) -> ToolLibraryQuery:
        """Keep only tools that list *operation* in supported_operations."""
        op = operation.lower().strip()
        return ToolLibraryQuery(
            [r for r in self._records if op in [o.lower() for o in r.supported_operations]]
        )

    def by_manufacturer(self, manufacturer: str) -> ToolLibraryQuery:
        """Case-insensitive exact match on manufacturer name."""
        target = manufacturer.strip().lower()
        return ToolLibraryQuery(
            [r for r in self._records if r.manufacturer.lower() == target]
        )

    def by_material_groups(self, groups: list[str]) -> ToolLibraryQuery:
        """Keep tools compatible with *any* of the supplied ISO material groups."""
        targets = {g.upper() for g in groups}
        return ToolLibraryQuery(
            [r for r in self._records if targets & set(r.iso_material_groups)]
        )

    def by_material_groups_all(self, groups: list[str]) -> ToolLibraryQuery:
        """Keep tools compatible with *all* of the supplied ISO material groups."""
        targets = {g.upper() for g in groups}
        return ToolLibraryQuery(
            [r for r in self._records if targets <= set(r.iso_material_groups)]
        )

    def by_diameter(
        self,
        *,
        min_mm: float | None = None,
        max_mm: float | None = None,
    ) -> ToolLibraryQuery:
        """Filter by cutting_diameter_mm range (inclusive).

        Records without a cutting_diameter_mm are excluded when either bound
        is specified.
        """
        filtered = []
        for r in self._records:
            d = r.cutting_diameter_mm
            if min_mm is not None or max_mm is not None:
                if d is None:
                    continue
                if min_mm is not None and d < min_mm:
                    continue
                if max_mm is not None and d > max_mm:
                    continue
            filtered.append(r)
        return ToolLibraryQuery(filtered)

    def by_shank_diameter(
        self,
        *,
        min_mm: float | None = None,
        max_mm: float | None = None,
    ) -> ToolLibraryQuery:
        """Filter by shank_diameter_mm range (inclusive)."""
        filtered = []
        for r in self._records:
            d = r.shank_diameter_mm
            if min_mm is not None or max_mm is not None:
                if d is None:
                    continue
                if min_mm is not None and d < min_mm:
                    continue
                if max_mm is not None and d > max_mm:
                    continue
            filtered.append(r)
        return ToolLibraryQuery(filtered)

    def by_overall_length(
        self,
        *,
        min_mm: float | None = None,
        max_mm: float | None = None,
    ) -> ToolLibraryQuery:
        """Filter by overall_length_mm range (inclusive)."""
        filtered = []
        for r in self._records:
            length = r.overall_length_mm
            if min_mm is not None or max_mm is not None:
                if length is None:
                    continue
                if min_mm is not None and length < min_mm:
                    continue
                if max_mm is not None and length > max_mm:
                    continue
            filtered.append(r)
        return ToolLibraryQuery(filtered)

    def by_cutting_length(
        self,
        *,
        min_mm: float | None = None,
        max_mm: float | None = None,
    ) -> ToolLibraryQuery:
        """Filter by cutting_length_mm range (inclusive)."""
        filtered = []
        for r in self._records:
            cl = r.cutting_length_mm
            if min_mm is not None or max_mm is not None:
                if cl is None:
                    continue
                if min_mm is not None and cl < min_mm:
                    continue
                if max_mm is not None and cl > max_mm:
                    continue
            filtered.append(r)
        return ToolLibraryQuery(filtered)

    def by_flute_count(
        self,
        *,
        min_flutes: int | None = None,
        max_flutes: int | None = None,
    ) -> ToolLibraryQuery:
        """Filter by number_of_flutes range (inclusive)."""
        filtered = []
        for r in self._records:
            n = r.number_of_flutes
            if min_flutes is not None or max_flutes is not None:
                if n is None:
                    continue
                if min_flutes is not None and n < min_flutes:
                    continue
                if max_flutes is not None and n > max_flutes:
                    continue
            filtered.append(r)
        return ToolLibraryQuery(filtered)

    def by_substrate_code(self, code: str) -> ToolLibraryQuery:
        """Filter by substrate_material_code (case-insensitive)."""
        target = code.strip().upper()
        return ToolLibraryQuery(
            [
                r for r in self._records
                if r.substrate_material_code and r.substrate_material_code.upper() == target
            ]
        )

    def by_coating_type(self, coating_type: str) -> ToolLibraryQuery:
        """Filter by coating_type (case-insensitive, e.g. 'CVD', 'PVD')."""
        target = coating_type.strip().upper()
        return ToolLibraryQuery(
            [
                r for r in self._records
                if r.coating_type and r.coating_type.upper() == target
            ]
        )

    def by_through_coolant(self, enabled: bool) -> ToolLibraryQuery:
        """Filter by through-coolant availability."""
        return ToolLibraryQuery(
            [r for r in self._records if r.through_coolant is enabled]
        )

    def by_category_code(self, code: str) -> ToolLibraryQuery:
        """Filter by exact tool_category_code."""
        return ToolLibraryQuery(
            [r for r in self._records if r.tool_category_code == code]
        )

    def by_shank_interface(self, interface_keyword: str) -> ToolLibraryQuery:
        """Case-insensitive substring match on shank_interface."""
        kw = interface_keyword.lower()
        return ToolLibraryQuery(
            [
                r for r in self._records
                if r.shank_interface and kw in r.shank_interface.lower()
            ]
        )

    def by_evidence_status(self, status: str) -> ToolLibraryQuery:
        """Filter by exact evidence_status value.

        Use ``'MANUFACTURER_CATALOG'`` for verified records only, or
        ``'UNVERIFIED'`` to surface records lacking a resolvable catalog reference.
        """
        return ToolLibraryQuery(
            [r for r in self._records if r.evidence_status == status]
        )

    # ── Terminal methods ──────────────────────────────────────────────────────

    def results(self) -> list[CuttingToolCatalogRecord]:
        """Return the filtered records as a list."""
        return list(self._records)

    def first(self) -> CuttingToolCatalogRecord | None:
        """Return the first matching record, or None."""
        return self._records[0] if self._records else None

    def count(self) -> int:
        """Return the number of matching records."""
        return len(self._records)


@dataclass(frozen=True)
class ToolLibrary:
    """Main facade for querying the cutting tool catalog.

    Instantiate once and reuse; it is stateless (all queries read from the
    global seed catalog via :func:`get_catalog`).
    """

    # ── Entry points ──────────────────────────────────────────────────────────

    def query(self) -> ToolLibraryQuery:
        """Return a fresh chainable query over the full catalog."""
        return ToolLibraryQuery(get_catalog())

    def all(self) -> list[CuttingToolCatalogRecord]:
        """Return all catalog records."""
        return get_catalog()

    # ── Convenience one-shot helpers ──────────────────────────────────────────

    def by_family(self, family: ToolFamily) -> list[CuttingToolCatalogRecord]:
        """All tools in a given ToolFamily."""
        return self.query().by_family(family).results()

    def by_operation(self, operation: str) -> list[CuttingToolCatalogRecord]:
        """All tools that support *operation*."""
        return self.query().by_operation(operation).results()

    def by_material_groups(self, groups: list[str]) -> list[CuttingToolCatalogRecord]:
        """All tools compatible with any of *groups* (ISO P/M/K/N/S/H)."""
        return self.query().by_material_groups(groups).results()

    def by_manufacturer(self, manufacturer: str) -> list[CuttingToolCatalogRecord]:
        """All tools from a given manufacturer."""
        return self.query().by_manufacturer(manufacturer).results()

    def find_by_id(self, stable_id: str) -> CuttingToolCatalogRecord | None:
        """Look up a single tool by its stable_id."""
        for r in get_catalog():
            if r.stable_id == stable_id:
                return r
        return None

    # ── Summary ───────────────────────────────────────────────────────────────

    def summary(self) -> CuttingToolCatalogSummary:
        """Return high-level counts and distinct value lists for the catalog."""
        records = get_catalog()
        manufacturers = sorted({r.manufacturer for r in records})
        categories = sorted({r.tool_category for r in records})
        tool_materials = sorted({r.tool_material for r in records if r.tool_material})
        iso_groups: set[str] = set()
        for r in records:
            iso_groups.update(r.iso_material_groups)

        source_titles = {r.source_title for r in records}
        source_title = next(iter(source_titles)) if source_titles else ""
        evidence_status_counts = Counter(r.evidence_status for r in records)
        evidence_status = (
            evidence_status_counts.most_common(1)[0][0] if evidence_status_counts else ""
        )

        return CuttingToolCatalogSummary(
            tool_count=len(records),
            manufacturer_count=len(manufacturers),
            category_count=len(categories),
            tool_material_count=len(tool_materials),
            manufacturers=manufacturers,
            categories=categories,
            tool_materials=tool_materials,
            iso_material_groups=sorted(iso_groups),
            source_title=source_title,
            evidence_status=evidence_status,
        )

    # ── Family coverage report ────────────────────────────────────────────────

    def family_coverage(self) -> dict[str, int]:
        """Return {family_name: tool_count} for all 9 families."""
        return {
            family.value: self.query().by_family(family).count()
            for family in ToolFamily
        }
