"""MC-6 — MaterialPipelineAdapter wiring for operation planning.

Bridges a part material name or grade identifier to a resolved ISO group and
cutting-data references, for use in operation planning and compatibility
evaluation (SelectionRequest.iso_material_group).

Design constraints:
  AUTO_INFER_FROM_GEOMETRY=NO   — material must be provided explicitly.
  REFERENCE_ONLY_PRESERVED=YES  — cutting data evidence stays REFERENCE_ONLY.
  UNKNOWN_AS_PASS=NO            — AMBIGUOUS or UNKNOWN → iso_group=None.
  FABRICATED_CUTTING_DATA=NO    — only catalog-sourced data returned.
  OPT_IN_ONLY=YES               — legacy pipeline (MaterialContext str field) untouched.

AMBIGUOUS resolution
--------------------
When a material name matches multiple catalog records (e.g. "1045" matches both
P-C45 and P-Ck45), ``status=AMBIGUOUS`` and ``iso_group=None``.  The caller must
provide a more specific identifier or choose from ``ambiguous_records``.

UNKNOWN resolution
------------------
When a material name is not found in the catalog, ``status=UNKNOWN`` and
``iso_group=None``.  The caller must supply a raw ISO group directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.integration.material_adapter import (
    MaterialLookupResult,
    MaterialLookupStatus,
    MaterialPipelineAdapter,
)
from backend.material_library.models import MaterialCatalogRecord, MaterialCuttingRef

__all__ = [
    "MaterialResolutionResult",
    "resolve_material_for_selection",
    "resolve_iso_group_for_selection",
]

# Module-level shared adapter (lazy-initialized; tests may inject their own).
_default_adapter: MaterialPipelineAdapter | None = None


def _get_default_adapter() -> MaterialPipelineAdapter:
    global _default_adapter
    if _default_adapter is None:
        _default_adapter = MaterialPipelineAdapter()
    return _default_adapter


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MaterialResolutionResult:
    """Result of resolving a material name via the Material Library.

    ``iso_group`` is a single-letter ISO group string ("P", "M", "K", "N",
    "S", "H") suitable for direct use in ``SelectionRequest.iso_material_group``
    or ``CompatibilityRequest.iso_material_group``.  It is None when
    ``status`` is AMBIGUOUS or UNKNOWN.

    ``cutting_refs`` is preserved at REFERENCE_ONLY evidence status as returned
    by the catalog; callers must NOT promote it to VERIFIED.
    """

    status: MaterialLookupStatus
    iso_group: str | None
    iso_subgroup: str | None
    record: MaterialCatalogRecord | None
    cutting_refs: list[MaterialCuttingRef] = field(default_factory=list)
    ambiguous_records: list[MaterialCatalogRecord] = field(default_factory=list)
    evidence_note: str = ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iso_group_from_lookup(result: MaterialLookupResult) -> str | None:
    """Extract the ISO group letter, or None if not resolvable."""
    if result.status != MaterialLookupStatus.RESOLVED or result.iso_group is None:
        return None
    # iso_group from MaterialLookupResult is already the letter ("P", "M", ...)
    # Strip "UNKNOWN" sentinel from the enum value
    if result.iso_group.upper() == "UNKNOWN":
        return None
    return result.iso_group


def _build_evidence_note(
    material_name: str,
    result: MaterialLookupResult,
) -> str:
    if result.status == MaterialLookupStatus.RESOLVED and result.record is not None:
        refs = len(result.cutting_refs)
        ref_note = (
            f"{refs} REFERENCE_ONLY cutting reference(s) in catalog."
            if refs > 0
            else "No cutting references in catalog."
        )
        return (
            f"Resolved '{material_name}' to '{result.record.stable_id}' "
            f"(ISO {result.iso_group}/{result.iso_subgroup}). {ref_note}"
        )
    if result.status == MaterialLookupStatus.AMBIGUOUS:
        ids = [r.stable_id for r in result.ambiguous_records]
        return (
            f"'{material_name}' is ambiguous — matches {ids}. "
            "Provide a more specific identifier."
        )
    return (
        f"'{material_name}' not found in Material Library catalog "
        f"({MaterialLookupStatus.UNKNOWN}). Provide explicit ISO group."
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_material_for_selection(
    material_name: str,
    *,
    adapter: MaterialPipelineAdapter | None = None,
) -> MaterialResolutionResult:
    """Resolve a material name to a catalog record and ISO group.

    Uses ``MaterialPipelineAdapter`` to look up the name in the Material Library.
    Returns RESOLVED with an ISO group, AMBIGUOUS with candidate records, or
    UNKNOWN when the name is not in the catalog.

    ``adapter`` is optional; pass a custom instance for testing or to share a
    pre-built adapter.  The module-level default adapter is used otherwise.

    Does NOT accept geometry or CAD inputs — material must be provided explicitly.
    """
    _adapter = adapter if adapter is not None else _get_default_adapter()
    result: MaterialLookupResult = _adapter.resolve(material_name)

    iso_group = _iso_group_from_lookup(result)
    iso_subgroup = result.iso_subgroup if result.status == MaterialLookupStatus.RESOLVED else None
    evidence_note = _build_evidence_note(material_name, result)

    return MaterialResolutionResult(
        status=result.status,
        iso_group=iso_group,
        iso_subgroup=iso_subgroup,
        record=result.record,
        cutting_refs=list(result.cutting_refs),
        ambiguous_records=list(result.ambiguous_records),
        evidence_note=evidence_note,
    )


def resolve_iso_group_for_selection(
    material_name: str,
    *,
    adapter: MaterialPipelineAdapter | None = None,
) -> str | None:
    """Convenience: return only the ISO group string, or None if unresolvable.

    Returns None for AMBIGUOUS and UNKNOWN statuses — callers must handle None
    and must NOT substitute a default ISO group.
    """
    result = resolve_material_for_selection(material_name, adapter=adapter)
    return result.iso_group
