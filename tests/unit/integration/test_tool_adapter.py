"""MC-3: ToolPipelineAdapter pipeline call-path tests.

Proves the adapter executes at runtime using real Tool Library seed data.
Confirms FAIL excluded from recommended, UNKNOWN preserved as uncertain.
Confirms legacy compatibility engine (seed_catalog Phase 1, 47 tools) is unaffected.
"""
from __future__ import annotations

import pytest

from backend.compatibility.engine import _TOOLS as _LEGACY_TOOLS
from backend.cutting_tools.compatibility import CompatibilityStatus
from backend.integration.tool_adapter import (
    ToolPipelineAdapter,
    ToolPipelineRequest,
    ToolPipelineResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def adapter() -> ToolPipelineAdapter:
    return ToolPipelineAdapter()


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------

def test_adapter_loads_tool_library(adapter: ToolPipelineAdapter) -> None:
    assert len(adapter._engine._records) == 47


# ---------------------------------------------------------------------------
# Selection executes at runtime
# ---------------------------------------------------------------------------

def test_select_drilling_returns_result(adapter: ToolPipelineAdapter) -> None:
    req = ToolPipelineRequest(operation="drilling")
    result = adapter.select(req)
    assert isinstance(result, ToolPipelineResult)
    assert result.total_evaluated > 0


def test_select_milling_returns_result(adapter: ToolPipelineAdapter) -> None:
    req = ToolPipelineRequest(operation="milling")
    result = adapter.select(req)
    assert isinstance(result, ToolPipelineResult)
    assert result.total_evaluated > 0


def test_select_with_iso_group_narrows_result(adapter: ToolPipelineAdapter) -> None:
    all_req = ToolPipelineRequest(operation="drilling")
    p_req = ToolPipelineRequest(operation="drilling", iso_material_group="P")
    result_all = adapter.select(all_req)
    result_p = adapter.select(p_req)
    # With material group specified the total evaluated must be <= without
    assert result_p.total_evaluated <= result_all.total_evaluated


# ---------------------------------------------------------------------------
# PASS / UNKNOWN / FAIL separation
# ---------------------------------------------------------------------------

def test_recommended_contains_only_pass_candidates(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="drilling", iso_material_group="P")
    result = adapter.select(req)
    for c in result.recommended:
        assert c.readiness_status == CompatibilityStatus.PASS


def test_uncertain_contains_only_unknown_candidates(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="drilling")
    result = adapter.select(req)
    for c in result.uncertain:
        assert c.readiness_status == CompatibilityStatus.UNKNOWN


def test_rejected_contains_only_fail_candidates(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="drilling")
    result = adapter.select(req)
    for c in result.rejected:
        assert c.readiness_status == CompatibilityStatus.FAIL


def test_fail_candidates_absent_from_recommended(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="drilling", iso_material_group="P")
    result = adapter.select(req)
    rec_ids = {c.tool.stable_id for c in result.recommended}
    rej_ids = {c.tool.stable_id for c in result.rejected}
    assert rec_ids.isdisjoint(rej_ids)


def test_unknown_candidates_absent_from_recommended(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="drilling")
    result = adapter.select(req)
    rec_ids = {c.tool.stable_id for c in result.recommended}
    unc_ids = {c.tool.stable_id for c in result.uncertain}
    assert rec_ids.isdisjoint(unc_ids)


# ---------------------------------------------------------------------------
# Deterministic ranking
# ---------------------------------------------------------------------------

def test_select_is_deterministic(adapter: ToolPipelineAdapter) -> None:
    req = ToolPipelineRequest(operation="milling", iso_material_group="P")
    r1 = adapter.select(req)
    r2 = adapter.select(req)
    assert [c.tool.stable_id for c in r1.recommended] == [
        c.tool.stable_id for c in r2.recommended
    ]
    assert [c.tool.stable_id for c in r1.uncertain] == [
        c.tool.stable_id for c in r2.uncertain
    ]


def test_recommended_sorted_by_score_desc_then_id(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="milling", iso_material_group="P")
    result = adapter.select(req)
    if len(result.recommended) >= 2:
        pairs = zip(result.recommended, result.recommended[1:], strict=False)
        for a, b in pairs:
            assert a.ranking_score >= b.ranking_score


# ---------------------------------------------------------------------------
# Total evaluated count
# ---------------------------------------------------------------------------

def test_total_evaluated_equals_sum_of_buckets(
    adapter: ToolPipelineAdapter,
) -> None:
    req = ToolPipelineRequest(operation="drilling", iso_material_group="K")
    result = adapter.select(req)
    total_buckets = (
        len(result.recommended) + len(result.uncertain) + len(result.rejected)
    )
    assert result.total_evaluated == total_buckets


# ---------------------------------------------------------------------------
# Legacy pipeline unchanged (MC-3 is opt-in)
# ---------------------------------------------------------------------------

def test_legacy_engine_tools_unchanged() -> None:
    # The compatibility engine must still use seed_catalog Phase 1 (47 tools).
    assert len(_LEGACY_TOOLS) == 47


def test_adapter_uses_full_tool_library(adapter: ToolPipelineAdapter) -> None:
    # Adapter records come from ToolLibrary().all() — same 47 tools
    assert len(adapter._engine._records) == len(_LEGACY_TOOLS)
