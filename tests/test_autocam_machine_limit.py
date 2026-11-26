"""Live machine-limit clamping acceptance tests — PHASE B.

Proves that the cutting parameter engine correctly clamps RPM to the
machine spindle_max_rpm and recomputes feed using the clamped value.

SYNTHETIC_TEST_ONLY=YES — machine and tool fixtures are synthetic,
labeled clearly, and are outside production catalogs.

PHASE B requirements verified here:
  CLAMPING_TRIGGERED=YES                           (Phase B)
  FEED_RECOMPUTED_AFTER_CLAMP=YES                  (MUST B1)
  USER_CAN_SEE_MACHINE_LIMIT_CLAMP=YES             (MUST B2 — provenance field)
  STATUS=CLAMPED_TO_MACHINE_LIMIT                  (Phase B)
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from backend.autocam.cutting_params_engine import _set_registry, compute_cutting_params
from backend.autocam.models import AutoCamFeatureInput, CuttingParamResult, MachineResult, ToolResult
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.cutting_parameters.seed_reference import seed_reference_registry


# Seed the registry from the reference file once for this module.
# Falls back gracefully if the file is absent (tests skip).
_REF_PATH = Path(__file__).parent.parent / "data" / "cutting_param_reference.md"


@pytest.fixture(autouse=True, scope="module")
def _seeded_registry():
    """Inject a pre-seeded registry so clamp tests do not depend on env vars.

    Restores None after module to prevent cross-module registry contamination.
    """
    reg = CuttingParameterRegistry()
    if _REF_PATH.is_file():
        seed_reference_registry(reg, str(_REF_PATH))
    _set_registry(reg)
    yield
    _set_registry(None)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Synthetic fixtures — TEST_ONLY, not production catalog entries
# ---------------------------------------------------------------------------

_SYNTHETIC_MACHINE_LOW_RPM = MachineResult(
    machine_id="SYNTHETIC-TEST-MACHINE-LOW-RPM-001",  # TEST_ONLY
    manufacturer="SYNTHETIC_TEST",
    model="TEST_CLAMP_FIXTURE",
    machine_type_code="VERTICAL_MACHINING_CENTER",
    spindle_max_rpm=1000,  # deliberately low to force clamping
    status="CALCULATED",
)

_SYNTHETIC_MACHINE_NORMAL = MachineResult(
    machine_id="SYNTHETIC-TEST-MACHINE-NORMAL-001",   # TEST_ONLY
    manufacturer="SYNTHETIC_TEST",
    model="TEST_NO_CLAMP_FIXTURE",
    machine_type_code="VERTICAL_MACHINING_CENTER",
    spindle_max_rpm=12000,
    status="CALCULATED",
)

_DRILL_FEATURE_6MM = AutoCamFeatureInput(
    feature_id="TEST_F1",
    feature_type="HOLE",
    diameter_mm=6.0,  # 6mm drill
    depth_mm=15.0,
    center_x=0.0,
    center_y=0.0,
    center_z_top=0.0,
)

_DRILL_TOOL_6MM = ToolResult(
    tool_id="SYNTHETIC-DRILL-6MM-TEST",   # TEST_ONLY
    tool_type="TWIST_DRILL",
    tool_diameter_mm=6.0,
    cutting_length_mm=30.0,
    tool_status="CALCULATED",
    provenance="TEST_FIXTURE",
)

_MILLING_FEATURE_4MM = AutoCamFeatureInput(
    feature_id="TEST_F2",
    feature_type="POCKET",
    diameter_mm=4.0,
    depth_mm=5.0,
    width_mm=10.0,
    length_mm=20.0,
    center_x=0.0,
    center_y=0.0,
    center_z_top=0.0,
)

_MILLING_TOOL_4MM = ToolResult(
    tool_id="SYNTHETIC-ENDMILL-4MM-TEST",  # TEST_ONLY
    tool_type="END_MILL",
    tool_diameter_mm=4.0,
    cutting_length_mm=12.0,
    tool_status="CALCULATED",
    provenance="TEST_FIXTURE",
)


# ---------------------------------------------------------------------------
# Phase B tests — clamping triggered
# ---------------------------------------------------------------------------

class TestMachineLimitClamping:
    """MACHINE_LIMIT_SOURCE=SYNTHETIC_TEST_FIXTURE spindle_max_rpm=1000"""

    def test_drilling_rpm_clamped_to_machine_limit(self) -> None:
        """6mm drill at Vc≈80 m/min → raw RPM ≈ 4244, clamped to 1000."""
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        # Only verify clamping if we got cutting params from the registry
        if result.status == "NOT_AVAILABLE":
            pytest.skip("No cutting param record for ISO-P drilling — registry not seeded")

        assert result.status == "CLAMPED_TO_MACHINE_LIMIT", (
            f"Expected CLAMPED_TO_MACHINE_LIMIT, got {result.status}"
        )
        assert result.rpm is not None
        assert result.rpm == float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm), (
            f"Expected RPM={_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm}, got {result.rpm}"
        )

    def test_clamped_rpm_less_than_raw_calculated(self) -> None:
        """Final RPM after clamp must be strictly less than raw calculated RPM."""
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        # Verify raw RPM formula for Vc=80, D=6:
        # RPM_raw = 1000 × 80 / (π × 6) ≈ 4244
        expected_raw_approx = 1000 * 80.0 / (math.pi * 6.0)
        assert expected_raw_approx > _SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm

        assert result.rpm == float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm)

    def test_feed_recomputed_after_clamp(self) -> None:
        """MUST B1: feed must be based on clamped RPM, not raw RPM.

        Feed = clamped_RPM × fn_mid
        Feed must NOT equal feed calculated from raw RPM.
        """
        result_clamped = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        result_unclamped = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_NORMAL,  # 12000 RPM limit — not clamped
        )
        if result_clamped.status == "NOT_AVAILABLE" or result_unclamped.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        # Clamped feed must be less than unclamped feed
        assert result_clamped.feed_mm_per_min is not None
        assert result_unclamped.feed_mm_per_min is not None
        assert result_clamped.feed_mm_per_min < result_unclamped.feed_mm_per_min, (
            f"Clamped feed ({result_clamped.feed_mm_per_min}) must be less than "
            f"unclamped feed ({result_unclamped.feed_mm_per_min})"
        )

    def test_clamping_provenance_contains_all_required_fields(self) -> None:
        """MUST B2: provenance must expose raw value, machine limit, final value, reason."""
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        prov = result.provenance
        assert "CLAMPED_TO_MACHINE_LIMIT" in prov
        assert "RAW_CALCULATED_VALUE=" in prov
        assert "MACHINE_LIMIT=" in prov
        assert "FINAL_SUGGESTED_VALUE=" in prov
        assert "LIMITING_REASON=" in prov

    def test_milling_clamped_to_machine_limit(self) -> None:
        """4mm end mill at Vc≈120 m/min → raw RPM ≈ 9549, clamped to 1000."""
        result = compute_cutting_params(
            _MILLING_FEATURE_4MM,
            _MILLING_TOOL_4MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("No cutting param record for ISO-P milling — registry not seeded")

        assert result.status == "CLAMPED_TO_MACHINE_LIMIT"
        assert result.rpm == float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm)

    def test_no_clamp_when_rpm_below_limit(self) -> None:
        """With a 12000 RPM machine, 6mm drill should NOT be clamped."""
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_NORMAL,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        # RPM ≈ 4244 — below 12000 → should not be clamped
        assert result.status in ("CALCULATED", "PARTIAL"), (
            f"Expected CALCULATED/PARTIAL, got {result.status}"
        )
        assert result.rpm is not None
        assert result.rpm < _SYNTHETIC_MACHINE_NORMAL.spindle_max_rpm

    def test_rpm_clamp_values_explicit(self) -> None:
        """Explicit numeric verification of clamping.

        MACHINE_LIMIT_SOURCE=SYNTHETIC_TEST_FIXTURE
        RAW_CALCULATED_RPM ≈ 4244 (Vc=80, D=6mm)
        MACHINE_MAX_RPM=1000
        FINAL_SUGGESTED_RPM=1000
        CLAMPING_TRIGGERED=YES
        """
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        raw_rpm_expected = 1000 * 80.0 / (math.pi * 6.0)  # ≈ 4244
        machine_max = float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm)  # 1000

        assert raw_rpm_expected > machine_max, (
            f"Test precondition: raw RPM {raw_rpm_expected:.1f} must exceed machine limit {machine_max}"
        )
        assert result.rpm == machine_max, (
            f"FINAL_SUGGESTED_RPM must equal MACHINE_MAX_RPM={machine_max}, got {result.rpm}"
        )
        assert "CLAMPED_TO_MACHINE_LIMIT" in result.provenance


# ---------------------------------------------------------------------------
# MUST B2 — user-visible clamp evidence
# ---------------------------------------------------------------------------

class TestClampUserVisibility:
    """USER_CAN_SEE_MACHINE_LIMIT_CLAMP=YES"""

    def test_provenance_raw_value_recorded(self) -> None:
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        # Extract RAW_CALCULATED_VALUE from provenance
        prov = result.provenance
        idx = prov.find("RAW_CALCULATED_VALUE=")
        assert idx >= 0
        raw_str = prov[idx + len("RAW_CALCULATED_VALUE="):].split()[0]
        raw_val = float(raw_str)
        # Must be the unclamped RPM (> machine limit)
        assert raw_val > float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm)

    def test_provenance_machine_limit_recorded(self) -> None:
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        prov = result.provenance
        idx = prov.find("MACHINE_LIMIT=")
        assert idx >= 0
        limit_str = prov[idx + len("MACHINE_LIMIT="):].split()[0]
        limit_val = float(limit_str)
        assert limit_val == float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm)

    def test_provenance_final_value_equals_machine_limit(self) -> None:
        result = compute_cutting_params(
            _DRILL_FEATURE_6MM,
            _DRILL_TOOL_6MM,
            _SYNTHETIC_MACHINE_LOW_RPM,
        )
        if result.status == "NOT_AVAILABLE":
            pytest.skip("Registry not seeded")

        prov = result.provenance
        idx = prov.find("FINAL_SUGGESTED_VALUE=")
        assert idx >= 0
        final_str = prov[idx + len("FINAL_SUGGESTED_VALUE="):].split()[0]
        final_val = float(final_str)
        assert final_val == float(_SYNTHETIC_MACHINE_LOW_RPM.spindle_max_rpm)
