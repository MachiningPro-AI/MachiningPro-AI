"""MC-1: MachinePipelineAdapter pipeline call-path tests.

Proves the adapter executes at runtime using real seed catalog data.
Confirms legacy compatibility engine is unaffected (still uses 37 old-catalog machines).
"""
from __future__ import annotations

import pytest

from backend.compatibility.engine import _MACHINES as _LEGACY_MACHINES
from backend.integration.machine_adapter import (
    MachineLookupStatus,
    MachinePipelineAdapter,
)
from backend.machine_library.interfaces import InterfaceFamily

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def adapter() -> MachinePipelineAdapter:
    return MachinePipelineAdapter()


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_adapter_loads_seed_catalog(adapter: MachinePipelineAdapter) -> None:
    assert adapter._registry is not None


def test_adapter_catalog_has_expected_count(adapter: MachinePipelineAdapter) -> None:
    # Machine Library seed has 28 records (richer than legacy 37-flat catalog)
    assert len(adapter._registry._records) == 28


# ---------------------------------------------------------------------------
# Successful lookup
# ---------------------------------------------------------------------------

def test_lookup_known_machine_returns_resolved(adapter: MachinePipelineAdapter) -> None:
    result = adapter.lookup("ml-haas-vf-2ss")
    assert result.status == MachineLookupStatus.RESOLVED
    assert result.record is not None
    assert result.record.stable_id == "ml-haas-vf-2ss"


def test_lookup_resolved_carries_normalized_spindle(
    adapter: MachinePipelineAdapter,
) -> None:
    result = adapter.lookup("ml-haas-vf-2ss")
    assert result.normalized_spindle is not None
    assert result.normalized_spindle.family == InterfaceFamily.CAT


def test_lookup_sk40_machine_normalized(adapter: MachinePipelineAdapter) -> None:
    result = adapter.lookup("ml-dmg-cmx-600v")
    assert result.status == MachineLookupStatus.RESOLVED
    assert result.normalized_spindle is not None
    assert result.normalized_spindle.family == InterfaceFamily.SK


# ---------------------------------------------------------------------------
# Unknown lookup
# ---------------------------------------------------------------------------

def test_lookup_unknown_id_returns_unknown(adapter: MachinePipelineAdapter) -> None:
    result = adapter.lookup("DOES_NOT_EXIST")
    assert result.status == MachineLookupStatus.UNKNOWN
    assert result.record is None
    assert result.normalized_spindle is None


# ---------------------------------------------------------------------------
# CAT-40 ≠ BT-40 enforcement
# ---------------------------------------------------------------------------

def test_cat40_and_bt40_normalize_to_different_families(
    adapter: MachinePipelineAdapter,
) -> None:
    cat = adapter.normalize_spindle("CAT-40")
    bt = adapter.normalize_spindle("BT-40")
    assert cat is not None
    assert bt is not None
    assert cat.family == InterfaceFamily.CAT
    assert bt.family == InterfaceFamily.BT
    assert cat.family != bt.family


def test_normalize_none_spindle_returns_none(
    adapter: MachinePipelineAdapter,
) -> None:
    assert adapter.normalize_spindle(None) is None


# ---------------------------------------------------------------------------
# Process capability
# ---------------------------------------------------------------------------

def test_is_process_capable_milling_on_milling_machine(
    adapter: MachinePipelineAdapter,
) -> None:
    result = adapter.lookup("ml-haas-vf-2ss")
    assert result.record is not None
    assert adapter.is_process_capable(result.record, "milling") is True


def test_is_process_capable_turning_on_milling_machine_is_false(
    adapter: MachinePipelineAdapter,
) -> None:
    result = adapter.lookup("ml-haas-vf-2ss")
    assert result.record is not None
    # VF-2SS is a VMC — not turning capable
    assert adapter.is_process_capable(result.record, "turning") is False


def test_is_process_capable_unknown_operation_returns_none(
    adapter: MachinePipelineAdapter,
) -> None:
    result = adapter.lookup("ml-haas-vf-2ss")
    assert result.record is not None
    # Caller must treat None as UNKNOWN
    assert adapter.is_process_capable(result.record, "laser_cutting") is None


# ---------------------------------------------------------------------------
# Legacy pipeline unchanged (MC-1 is opt-in)
# ---------------------------------------------------------------------------

def test_legacy_engine_machines_unchanged() -> None:
    # The compatibility engine must still use the old 37-machine catalog.
    # This test fails if the engine is accidentally rewired to the new library.
    assert len(_LEGACY_MACHINES) == 37


def test_legacy_machines_are_separate_from_library(
    adapter: MachinePipelineAdapter,
) -> None:
    legacy_ids = set(_LEGACY_MACHINES.keys())
    library_ids = set(adapter._registry._records.keys())
    # The two catalogs use distinct stable_id namespaces
    assert legacy_ids.isdisjoint(library_ids), (
        "Legacy and library catalogs share stable_ids — they must remain separate"
    )
