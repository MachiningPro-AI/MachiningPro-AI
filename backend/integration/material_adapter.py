"""MC-2: Material Library pipeline adapter.

Opt-in bridge between backend.material_library and the production pipeline.
The legacy MaterialContext(material_name: str | None) in
backend.interoperability.process_intelligence is NOT modified.

Only callers that explicitly instantiate MaterialPipelineAdapter receive
new-library resolution behaviour.

Design constraints:
  LEGACY_PIPELINE_UNCHANGED=YES     — process_intelligence.MaterialContext untouched
  OPT_IN_ONLY=YES                    — no automatic activation
  UNKNOWN_FOR_NO_MATCH=YES           — unresolvable name → UNKNOWN, never guessed
  AMBIGUOUS_FOR_MULTIPLE_MATCHES=YES — multiple alias matches → AMBIGUOUS, not PASS
  AUTO_INFER_FROM_GEOMETRY=NO        — material is NEVER inferred from CAD geometry
  REFERENCE_ONLY_PRESERVED=YES       — cutting refs keep DataConfidence.REFERENCE_ONLY
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.material_library.models import MaterialCatalogRecord, MaterialCuttingRef
from backend.material_library.registry import MaterialCatalogRegistry
from backend.material_library.seed_catalog import seed_material_library

__all__ = [
    "MaterialLookupStatus",
    "MaterialLookupResult",
    "MaterialPipelineAdapter",
]


class MaterialLookupStatus(StrEnum):
    RESOLVED = "RESOLVED"
    AMBIGUOUS = "AMBIGUOUS"   # multiple alias matches — conservative, not PASS
    UNKNOWN = "UNKNOWN"       # no match found


@dataclass(frozen=True)
class MaterialLookupResult:
    status: MaterialLookupStatus
    record: MaterialCatalogRecord | None
    iso_group: str | None          # None when UNKNOWN or AMBIGUOUS
    iso_subgroup: str | None       # None when UNKNOWN or AMBIGUOUS
    # REFERENCE_ONLY cutting refs from the resolved record (empty when not RESOLVED)
    cutting_refs: list[MaterialCuttingRef] = field(default_factory=list)
    # Populated only when status == AMBIGUOUS
    ambiguous_records: list[MaterialCatalogRecord] = field(default_factory=list)


class MaterialPipelineAdapter:
    """Opt-in adapter: resolves a material name string against the Material Library.

    Resolution order:
      1. Exact stable_id match (case-sensitive).
      2. Exact alias match via find_by_alias() (case-insensitive).
      3. 0 matches → UNKNOWN.  >1 matches → AMBIGUOUS.

    Material is NEVER inferred from CAD geometry or feature recognition output.
    All cutting reference data retains REFERENCE_ONLY evidence status.

    The legacy pipeline's MaterialContext(material_name: str) is unaffected.
    """

    def __init__(self, registry: MaterialCatalogRegistry | None = None) -> None:
        if registry is None:
            registry = MaterialCatalogRegistry(seed_material_library())
        self._registry = registry

    def resolve(self, material_name: str) -> MaterialLookupResult:
        """Attempt to resolve *material_name* against the catalog.

        Returns RESOLVED (one match), AMBIGUOUS (multiple alias matches),
        or UNKNOWN (no match). Never raises; always returns a result.
        """
        name = material_name.strip()

        # 1. Exact stable_id match
        record = self._registry.get(name)
        if record is not None:
            return self._resolved(record)

        # 2. Alias search (case-insensitive)
        matches = self._registry.find_by_alias(name)
        if len(matches) == 1:
            return self._resolved(matches[0])
        if len(matches) > 1:
            return MaterialLookupResult(
                status=MaterialLookupStatus.AMBIGUOUS,
                record=None,
                iso_group=None,
                iso_subgroup=None,
                cutting_refs=[],
                ambiguous_records=list(matches),
            )

        return MaterialLookupResult(
            status=MaterialLookupStatus.UNKNOWN,
            record=None,
            iso_group=None,
            iso_subgroup=None,
        )

    @staticmethod
    def _resolved(record: MaterialCatalogRecord) -> MaterialLookupResult:
        return MaterialLookupResult(
            status=MaterialLookupStatus.RESOLVED,
            record=record,
            iso_group=record.iso_group.value,
            iso_subgroup=record.iso_subgroup.value,
            cutting_refs=list(record.cutting_references),
        )
