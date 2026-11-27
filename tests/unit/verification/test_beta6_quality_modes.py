"""Phase Y — Quality mode tests."""

import pytest
from backend.verification.quality_modes import (
    QualityMode,
    QualityModeConfig,
    get_quality_mode_config,
    annotate_result_with_quality_mode,
    QUALITY_MODE_FAST,
    QUALITY_MODE_BALANCED,
    QUALITY_MODE_HIGH_FIDELITY,
)


class TestQualityModeConfigs:
    def test_fast_stock_method(self):
        assert QUALITY_MODE_FAST.stock_removal_method == "FAST_APPROXIMATE"

    def test_fast_collision_disabled(self):
        assert not QUALITY_MODE_FAST.assembly_collision_enabled
        assert not QUALITY_MODE_FAST.machine_collision_enabled

    def test_balanced_assembly_enabled(self):
        assert QUALITY_MODE_BALANCED.assembly_collision_enabled

    def test_balanced_machine_collision_disabled(self):
        assert not QUALITY_MODE_BALANCED.machine_collision_enabled

    def test_high_fidelity_brep_boolean(self):
        assert QUALITY_MODE_HIGH_FIDELITY.stock_removal_method == "BREP_BOOLEAN"

    def test_high_fidelity_all_collision_enabled(self):
        assert QUALITY_MODE_HIGH_FIDELITY.assembly_collision_enabled
        assert QUALITY_MODE_HIGH_FIDELITY.machine_collision_enabled

    def test_high_fidelity_brep_exact_volume(self):
        assert QUALITY_MODE_HIGH_FIDELITY.volume_fidelity == "BREP_EXACT"

    def test_fast_approximate_label(self):
        assert "APPROXIMATE" in QUALITY_MODE_FAST.stock_removal_fidelity.upper() \
            or "APPROXIMATE" in QUALITY_MODE_FAST.volume_fidelity.upper()

    def test_all_modes_have_description(self):
        for m in (QUALITY_MODE_FAST, QUALITY_MODE_BALANCED, QUALITY_MODE_HIGH_FIDELITY):
            assert m.description and len(m.description) > 5

    def test_no_mode_claims_exact_when_voxel(self):
        # FAST must not claim BREP_EXACT
        assert "BREP_EXACT" not in QUALITY_MODE_FAST.volume_fidelity
        assert "BREP_EXACT" not in QUALITY_MODE_BALANCED.volume_fidelity


class TestGetQualityModeConfig:
    def test_enum_lookup(self):
        cfg = get_quality_mode_config(QualityMode.FAST)
        assert cfg.mode == QualityMode.FAST

    def test_string_lookup(self):
        cfg = get_quality_mode_config("BALANCED")
        assert cfg.mode == QualityMode.BALANCED

    def test_invalid_raises(self):
        with pytest.raises((KeyError, ValueError)):
            get_quality_mode_config("ULTRA")

    def test_high_fidelity_string(self):
        cfg = get_quality_mode_config("HIGH_FIDELITY")
        assert cfg.mode == QualityMode.HIGH_FIDELITY


class TestAnnotateResult:
    def test_adds_quality_mode_field(self):
        d = {"volume_mm3": 500.0}
        annotate_result_with_quality_mode(d, "FAST")
        assert "QUALITY_MODE" in d
        assert d["QUALITY_MODE"] == "FAST"

    def test_adds_description(self):
        d = {}
        annotate_result_with_quality_mode(d, "HIGH_FIDELITY")
        assert "QUALITY_MODE_DESCRIPTION" in d
        assert len(d["QUALITY_MODE_DESCRIPTION"]) > 0

    def test_returns_same_dict(self):
        d = {"x": 1}
        r = annotate_result_with_quality_mode(d, "BALANCED")
        assert r is d
