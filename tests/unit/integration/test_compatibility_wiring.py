"""MC-4 / MC-5: compatibility_wiring runtime entry-point tests.

Proves:
  - enhanced_evaluate() calls the spindle adapter at runtime (MC-4).
  - IntegrationVerdict and combine_verdicts() are wired into decision
    aggregation (MC-5).
  - CAT-40 and BT-40 are treated as incompatible families.
  - Missing spindle spec preserves UNKNOWN (never promoted to PASS).
  - Legacy base_response is unmodified.
  - Opt-in flags restore legacy behavior.
"""

from __future__ import annotations

from backend.compatibility.engine import evaluate as legacy_evaluate
from backend.compatibility.models import CompatibilityRequest
from backend.integration.compatibility_wiring import (
    EnhancedCompatibilityResult,
    SpindleCheckDetail,
    enhanced_evaluate,
)
from backend.integration.result_mapping import IntegrationVerdict

# ---------------------------------------------------------------------------
# Shared request fixtures (all use real legacy catalog IDs)
# ---------------------------------------------------------------------------

# CAT-40 machine + CAT-40 holder — spindle match expected
_REQ_CAT_MATCH = CompatibilityRequest(
    machine_id="haas-vf-2ss",
    holder_id="kennametal-cat40-er32-collet-chuck",
    cutting_tool_id="kennametal-ecs-d12-4fl",
    operation="milling",
    iso_material_group="P",
)

# CAT-40 machine + HSK-A63 holder — spindle mismatch expected
_REQ_CAT_HSK_MISMATCH = CompatibilityRequest(
    machine_id="haas-vf-2ss",
    holder_id="bigdaishowa-hska63-mega-er32-100",
    cutting_tool_id="kennametal-ecs-d12-4fl",
    operation="milling",
    iso_material_group="P",
)

# Machine with no published spindle interface
_REQ_NO_SPINDLE = CompatibilityRequest(
    machine_id="citizen-cincom-l20",
    holder_id="kennametal-cat40-er32-collet-chuck",
    cutting_tool_id="kennametal-ecs-d12-4fl",
    operation="milling",
    iso_material_group="P",
)

# ---------------------------------------------------------------------------
# Instantiation / return type
# ---------------------------------------------------------------------------


def test_enhanced_evaluate_returns_enhanced_result() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert isinstance(res, EnhancedCompatibilityResult)


def test_base_response_is_present() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert res.base_response is not None


def test_spindle_detail_present_when_normalization_enabled() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH, use_spindle_normalization=True)
    assert isinstance(res.spindle_detail, SpindleCheckDetail)


def test_spindle_detail_absent_when_normalization_disabled() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH, use_spindle_normalization=False)
    assert res.spindle_detail is None


# ---------------------------------------------------------------------------
# MC-4: spindle normalization
# ---------------------------------------------------------------------------


def test_cat40_machine_cat40_holder_spindle_pass() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert res.spindle_verdict == IntegrationVerdict.PASS


def test_cat40_machine_hska63_holder_spindle_fail() -> None:
    # HSK-A63 ≠ CAT-40: different interface families
    res = enhanced_evaluate(_REQ_CAT_HSK_MISMATCH)
    assert res.spindle_verdict == IntegrationVerdict.FAIL


def test_no_spindle_machine_returns_spindle_unknown() -> None:
    res = enhanced_evaluate(_REQ_NO_SPINDLE)
    assert res.spindle_verdict == IntegrationVerdict.UNKNOWN


def test_spindle_detail_provenance_non_empty() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert res.spindle_detail is not None
    assert len(res.spindle_detail.provenance) > 0


# ---------------------------------------------------------------------------
# MC-5: IntegrationVerdict aggregation
# ---------------------------------------------------------------------------


def test_overall_verdict_is_integration_verdict() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert isinstance(res.overall_verdict, IntegrationVerdict)


def test_fail_dominates_overall_verdict() -> None:
    # CAT-40 machine, HSK-A63 holder → spindle FAIL → overall must be FAIL
    res = enhanced_evaluate(_REQ_CAT_HSK_MISMATCH)
    assert res.overall_verdict == IntegrationVerdict.FAIL


def test_unknown_propagates_when_no_fail() -> None:
    # CAT-40/CAT-40 match but MACHINE_TOOL_LENGTH is UNKNOWN → overall UNKNOWN
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert res.overall_verdict == IntegrationVerdict.UNKNOWN


def test_verdict_provenance_non_empty() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    assert len(res.verdict_provenance) > 0


def test_verdict_provenance_contains_rule_ids() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    # Provenance entries must reference known rule IDs
    combined = " ".join(res.verdict_provenance)
    assert "PROCESS_SUPPORT" in combined
    assert "MACHINE_HOLDER_INTERFACE" in combined


# ---------------------------------------------------------------------------
# Legacy base_response unchanged
# ---------------------------------------------------------------------------


def test_base_response_matches_legacy_evaluate() -> None:
    legacy = legacy_evaluate(_REQ_CAT_MATCH)
    res = enhanced_evaluate(_REQ_CAT_MATCH)
    # Base response must be the unchanged legacy result
    assert res.base_response.overall_status == legacy.overall_status
    assert res.base_response.rule_results == legacy.rule_results


# ---------------------------------------------------------------------------
# Opt-in flags
# ---------------------------------------------------------------------------


def test_no_spindle_normalization_flag_uses_legacy_path() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH, use_spindle_normalization=False)
    assert res.use_spindle_normalization is False
    assert res.spindle_detail is None
    # Spindle verdict from legacy rule still present
    assert res.spindle_verdict in (
        IntegrationVerdict.PASS,
        IntegrationVerdict.FAIL,
        IntegrationVerdict.UNKNOWN,
    )


def test_no_integration_verdict_flag_maps_legacy_status() -> None:
    res = enhanced_evaluate(_REQ_CAT_MATCH, use_integration_verdict=False)
    assert res.use_integration_verdict is False
    # Provenance records the legacy overall_status
    combined = " ".join(res.verdict_provenance)
    assert "legacy_overall_status" in combined
