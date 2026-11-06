"""MC-6: material_resolution runtime entry-point tests.

Proves:
  - resolve_material_for_selection() invokes MaterialPipelineAdapter at runtime.
  - RESOLVED status carries a valid ISO group string.
  - AMBIGUOUS status returns None for iso_group (never guesses).
  - UNKNOWN status returns None for iso_group (never guesses).
  - REFERENCE_ONLY evidence status preserved on cutting_refs.
  - Function signature has no geometry input path.
  - Custom adapter injection works (opt-in behavior).
  - resolve_iso_group_for_selection() convenience function works correctly.
"""

from __future__ import annotations

import inspect

from backend.integration.material_adapter import MaterialLookupStatus
from backend.integration.material_resolution import (
    MaterialResolutionResult,
    resolve_iso_group_for_selection,
    resolve_material_for_selection,
)
from backend.material_library.enums import DataConfidence

# ---------------------------------------------------------------------------
# Instantiation / return type
# ---------------------------------------------------------------------------


def test_resolve_returns_material_resolution_result() -> None:
    result = resolve_material_for_selection("P-C45")
    assert isinstance(result, MaterialResolutionResult)


def test_resolve_seed_catalog_has_expected_count() -> None:
    # Confirm the adapter loaded the full seed catalog (19 grades)
    from backend.integration.material_resolution import _get_default_adapter
    adapter = _get_default_adapter()
    assert len(adapter._registry) == 19


# ---------------------------------------------------------------------------
# RESOLVED: known stable_id
# ---------------------------------------------------------------------------


def test_resolved_known_stable_id_status() -> None:
    result = resolve_material_for_selection("P-C45")
    assert result.status == MaterialLookupStatus.RESOLVED


def test_resolved_known_stable_id_iso_group() -> None:
    result = resolve_material_for_selection("P-C45")
    assert result.iso_group == "P"


def test_resolved_record_stable_id_matches() -> None:
    result = resolve_material_for_selection("P-C45")
    assert result.record is not None
    assert result.record.stable_id == "P-C45"


def test_resolved_iso_subgroup_present() -> None:
    result = resolve_material_for_selection("P-C45")
    assert result.iso_subgroup is not None


def test_resolved_evidence_note_non_empty() -> None:
    result = resolve_material_for_selection("P-C45")
    assert len(result.evidence_note) > 0


# ---------------------------------------------------------------------------
# AMBIGUOUS: "1045" matches P-C45 and P-Ck45
# ---------------------------------------------------------------------------


def test_ambiguous_1045_status() -> None:
    result = resolve_material_for_selection("1045")
    assert result.status == MaterialLookupStatus.AMBIGUOUS


def test_ambiguous_iso_group_is_none() -> None:
    # Must not guess the ISO group when ambiguous
    result = resolve_material_for_selection("1045")
    assert result.iso_group is None


def test_ambiguous_record_is_none() -> None:
    result = resolve_material_for_selection("1045")
    assert result.record is None


def test_ambiguous_has_candidate_records() -> None:
    result = resolve_material_for_selection("1045")
    assert len(result.ambiguous_records) == 2


# ---------------------------------------------------------------------------
# UNKNOWN: unrecognized material
# ---------------------------------------------------------------------------


def test_unknown_material_status() -> None:
    result = resolve_material_for_selection("UNOBTAINIUM_9000")
    assert result.status == MaterialLookupStatus.UNKNOWN


def test_unknown_iso_group_is_none() -> None:
    result = resolve_material_for_selection("UNOBTAINIUM_9000")
    assert result.iso_group is None


def test_unknown_record_is_none() -> None:
    result = resolve_material_for_selection("UNOBTAINIUM_9000")
    assert result.record is None


# ---------------------------------------------------------------------------
# REFERENCE_ONLY evidence status preserved
# ---------------------------------------------------------------------------


def test_cutting_refs_evidence_reference_only() -> None:
    result = resolve_material_for_selection("P-C45")
    assert result.status == MaterialLookupStatus.RESOLVED
    for ref in result.cutting_refs:
        assert ref.evidence_status == DataConfidence.REFERENCE_ONLY, (
            f"Expected REFERENCE_ONLY, got {ref.evidence_status}"
        )


# ---------------------------------------------------------------------------
# No geometry input path (structural check)
# ---------------------------------------------------------------------------


def test_resolve_accepts_no_geometry_input() -> None:
    sig = inspect.signature(resolve_material_for_selection)
    param_names = list(sig.parameters.keys())
    # Only 'material_name' (positional) and 'adapter' (keyword-only)
    assert "material_name" in param_names
    assert "adapter" in param_names
    # No geometry, cad, feature, or shape parameters
    for name in param_names:
        assert name not in ("geometry", "cad", "feature", "shape", "dxf", "iges"), (
            f"Unexpected geometry parameter: {name}"
        )


# ---------------------------------------------------------------------------
# Custom adapter injection (opt-in)
# ---------------------------------------------------------------------------


def test_custom_adapter_injection() -> None:
    from backend.integration.material_adapter import MaterialPipelineAdapter
    from backend.material_library.enums import (
        MaterialFamily,
        MaterialISOGroup,
        MaterialSubGroup,
    )
    from backend.material_library.models import (
        MaterialCatalogRecord,
        MaterialDesignation,
    )
    from backend.material_library.registry import MaterialCatalogRegistry

    custom_record = MaterialCatalogRecord(
        stable_id="TEST-STEEL-01",
        designation="TEST-STEEL-01",
        iso_group=MaterialISOGroup.P,
        iso_subgroup=MaterialSubGroup.P_STEEL,
        material_family=MaterialFamily.STEEL,
        designation_detail=MaterialDesignation(aliases=["custom-alias"]),
    )
    registry = MaterialCatalogRegistry([custom_record])
    adapter = MaterialPipelineAdapter(registry=registry)

    result = resolve_material_for_selection("TEST-STEEL-01", adapter=adapter)
    assert result.status == MaterialLookupStatus.RESOLVED
    assert result.iso_group == "P"


# ---------------------------------------------------------------------------
# Convenience function: resolve_iso_group_for_selection
# ---------------------------------------------------------------------------


def test_iso_group_resolved_returns_letter() -> None:
    iso = resolve_iso_group_for_selection("P-42CrMo4")
    assert iso == "P"


def test_iso_group_ambiguous_returns_none() -> None:
    iso = resolve_iso_group_for_selection("1045")
    assert iso is None


def test_iso_group_unknown_returns_none() -> None:
    iso = resolve_iso_group_for_selection("NOT_IN_CATALOG")
    assert iso is None
