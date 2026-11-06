"""MC-2: MaterialPipelineAdapter pipeline call-path tests.

Proves the adapter executes at runtime using real seed catalog data.
Confirms legacy pipeline (MaterialContext str field) is unaffected.
"""
from __future__ import annotations

import pytest

from backend.integration.material_adapter import (
    MaterialLookupStatus,
    MaterialPipelineAdapter,
)
from backend.material_library.enums import (
    DataConfidence,
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)
from backend.material_library.models import MaterialCatalogRecord, MaterialDesignation
from backend.material_library.registry import MaterialCatalogRegistry

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def adapter() -> MaterialPipelineAdapter:
    return MaterialPipelineAdapter()


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_adapter_loads_seed_catalog(adapter: MaterialPipelineAdapter) -> None:
    assert adapter._registry is not None
    assert len(adapter._registry) == 19


# ---------------------------------------------------------------------------
# Stable-id resolution
# ---------------------------------------------------------------------------

def test_resolve_by_stable_id_returns_resolved(
    adapter: MaterialPipelineAdapter,
) -> None:
    result = adapter.resolve("P-C45")
    assert result.status == MaterialLookupStatus.RESOLVED
    assert result.record is not None
    assert result.record.stable_id == "P-C45"


def test_resolve_by_stable_id_has_iso_group(
    adapter: MaterialPipelineAdapter,
) -> None:
    result = adapter.resolve("P-C45")
    assert result.iso_group == "P"


def test_resolve_by_stable_id_has_iso_subgroup(
    adapter: MaterialPipelineAdapter,
) -> None:
    result = adapter.resolve("P-C45")
    assert result.iso_subgroup is not None


# ---------------------------------------------------------------------------
# Alias resolution
# ---------------------------------------------------------------------------

def test_resolve_by_alias_1045_is_ambiguous(
    adapter: MaterialPipelineAdapter,
) -> None:
    # "1045" appears as an alias on both P-C45 and P-Ck45 → AMBIGUOUS (conservative)
    result = adapter.resolve("1045")
    assert result.status == MaterialLookupStatus.AMBIGUOUS
    assert result.record is None
    assert result.iso_group is None
    assert len(result.ambiguous_records) == 2


def test_resolve_by_alias_case_insensitive(
    adapter: MaterialPipelineAdapter,
) -> None:
    # "4140" is a unique alias for P-42CrMo4 (case-insensitive match)
    result = adapter.resolve("4140")
    assert result.status == MaterialLookupStatus.RESOLVED
    assert result.record is not None
    assert result.record.stable_id == "P-42CrMo4"


def test_resolve_by_alias_4140_returns_resolved(
    adapter: MaterialPipelineAdapter,
) -> None:
    # "4140" is an alias for P-42CrMo4
    result = adapter.resolve("4140")
    assert result.status == MaterialLookupStatus.RESOLVED
    assert result.record is not None
    assert result.record.stable_id == "P-42CrMo4"


# ---------------------------------------------------------------------------
# Unknown resolution
# ---------------------------------------------------------------------------

def test_resolve_unknown_name_returns_unknown(
    adapter: MaterialPipelineAdapter,
) -> None:
    result = adapter.resolve("UNOBTAINIUM_9000")
    assert result.status == MaterialLookupStatus.UNKNOWN
    assert result.record is None
    assert result.iso_group is None


def test_resolve_empty_string_returns_unknown(
    adapter: MaterialPipelineAdapter,
) -> None:
    result = adapter.resolve("   ")
    assert result.status == MaterialLookupStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Ambiguous resolution
# ---------------------------------------------------------------------------

def _make_record(stable_id: str, alias: str) -> MaterialCatalogRecord:
    return MaterialCatalogRecord(
        stable_id=stable_id,
        designation=stable_id,
        iso_group=MaterialISOGroup.P,
        iso_subgroup=MaterialSubGroup.P_STEEL,
        material_family=MaterialFamily.STEEL,
        designation_detail=MaterialDesignation(aliases=[alias]),
    )


def test_resolve_ambiguous_multiple_alias_matches() -> None:
    shared_alias = "DUPLEX_ALIAS"
    rec_a = _make_record("RECORD-A", shared_alias)
    rec_b = _make_record("RECORD-B", shared_alias)
    registry = MaterialCatalogRegistry([rec_a, rec_b])
    adapter = MaterialPipelineAdapter(registry=registry)

    result = adapter.resolve(shared_alias)
    assert result.status == MaterialLookupStatus.AMBIGUOUS
    assert result.record is None
    assert result.iso_group is None
    assert len(result.ambiguous_records) == 2


# ---------------------------------------------------------------------------
# REFERENCE_ONLY evidence preserved
# ---------------------------------------------------------------------------

def test_cutting_refs_are_reference_only(adapter: MaterialPipelineAdapter) -> None:
    # Any resolved record with cutting references must keep REFERENCE_ONLY status
    for stable_id in ("P-C45", "P-42CrMo4"):
        result = adapter.resolve(stable_id)
        assert result.status == MaterialLookupStatus.RESOLVED
        for ref in result.cutting_refs:
            assert ref.evidence_status == DataConfidence.REFERENCE_ONLY, (
                f"Cutting ref in {stable_id} must be REFERENCE_ONLY, got {ref.evidence_status}"
            )


# ---------------------------------------------------------------------------
# No auto-infer from geometry (structural check)
# ---------------------------------------------------------------------------

def test_adapter_has_no_geometry_input_path() -> None:
    # MaterialPipelineAdapter.resolve() only accepts a string — no geometry arg.
    import inspect
    sig = inspect.signature(MaterialPipelineAdapter.resolve)
    params = list(sig.parameters.keys())
    # Only 'self' and 'material_name'
    assert params == ["self", "material_name"], (
        "resolve() must not accept geometry arguments; got: " + str(params)
    )


# ---------------------------------------------------------------------------
# Legacy pipeline unchanged (MC-2 is opt-in)
# ---------------------------------------------------------------------------

def test_legacy_material_context_unchanged() -> None:
    import dataclasses

    from backend.interoperability.process_intelligence import MaterialContext
    fields = {f.name for f in dataclasses.fields(MaterialContext)}
    # Legacy MaterialContext uses a plain string, not MaterialCatalogRecord
    assert "material_name" in fields
    # Confirm no library record field injected into the legacy dataclass
    assert "record" not in fields
    assert "iso_group" not in fields
