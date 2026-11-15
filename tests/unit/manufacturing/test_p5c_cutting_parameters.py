"""Tests for P5-C: cutting parameter selection (MUST 42, 14-21)."""
import math

import pytest

from backend.cutting_tools.cutting_parameters import (
    CuttingDataReadiness,
    MachineLimitStatus,
    calculate_feed_rate_mm_min,
    calculate_rpm,
    get_cutting_data,
)


class TestP5CCuttingDataCalculations:
    def test_rpm_formula_5mm_70mpm(self):
        """RPM = (Vc * 1000) / (pi * D)."""
        expected = round((70.0 * 1000) / (math.pi * 5.0))
        assert calculate_rpm(70.0, 5.0) == expected

    def test_feed_rate_formula(self):
        """feed_mm_min = RPM * fn_mm."""
        rpm = 4456
        fn = 0.06
        expected = round(rpm * fn, 1)
        assert calculate_feed_rate_mm_min(rpm, fn) == expected

    def test_rpm_raises_on_zero_diameter(self):
        with pytest.raises(ValueError, match="diameter_mm must be > 0"):
            calculate_rpm(90.0, 0.0)

    def test_rpm_raises_on_negative_vc(self):
        with pytest.raises(ValueError, match="vc_mpm must be > 0"):
            calculate_rpm(-10.0, 5.0)

    def test_feed_rate_raises_on_zero_rpm(self):
        with pytest.raises(ValueError):
            calculate_feed_rate_mm_min(0, 0.1)

    def test_unit_consistency_mpm(self):
        """Vc is in m/min not mm/min -- RPM for 5mm at Vc=90 m/min."""
        rpm = calculate_rpm(90.0, 5.0)
        # Expected: (90 * 1000) / (pi * 5) = 5729 (approx)
        assert 5500 <= rpm <= 6000, f"RPM {rpm} outside expected range"


class TestP5CCuttingDataLookup:
    def test_valid_c45_5mm_drilling(self):
        cd = get_cutting_data(tool_family="CoroDrill 860", material_grade="C45", diameter_mm=5.0)
        assert cd.readiness == CuttingDataReadiness.READY
        assert cd.vc_min_mpm == 70.0
        assert cd.vc_max_mpm == 115.0
        assert cd.fn_min_mm == 0.06
        assert cd.fn_max_mm == 0.11
        assert cd.rpm_min is not None and cd.rpm_min > 0
        assert cd.rpm_max is not None and cd.rpm_max > 0
        assert cd.feed_rate_min_mm_min is not None
        assert cd.feed_rate_max_mm_min is not None
        assert cd.source is not None
        assert cd.source_url is not None

    def test_valid_c45_6mm_drilling(self):
        cd = get_cutting_data(tool_family="CoroDrill 860", material_grade="C45", diameter_mm=6.0)
        assert cd.readiness == CuttingDataReadiness.READY

    def test_valid_c45_8mm_drilling(self):
        cd = get_cutting_data(tool_family="CoroDrill 860", material_grade="C45", diameter_mm=8.0)
        assert cd.readiness == CuttingDataReadiness.READY

    def test_missing_material_grade(self):
        cd = get_cutting_data(
            tool_family="CoroDrill 860", material_grade="UNKNOWN_GRADE_XYZ", diameter_mm=5.0
        )
        assert cd.readiness == CuttingDataReadiness.MATERIAL_UNKNOWN

    def test_missing_tool_family_no_data(self):
        cd = get_cutting_data(
            tool_family="NonExistentDrillBrand", material_grade="C45", diameter_mm=5.0
        )
        assert cd.readiness == CuttingDataReadiness.NO_DATA

    def test_no_data_for_unsupported_operation(self):
        cd = get_cutting_data(
            tool_family="CoroDrill 860", material_grade="C45", diameter_mm=5.0, operation="turning"
        )
        assert cd.readiness == CuttingDataReadiness.NO_DATA

    def test_rpm_min_less_than_rpm_max(self):
        cd = get_cutting_data(tool_family="CoroDrill 860", material_grade="C45", diameter_mm=5.0)
        assert cd.rpm_min < cd.rpm_max

    def test_feed_rate_min_less_than_max(self):
        cd = get_cutting_data(tool_family="CoroDrill 860", material_grade="C45", diameter_mm=5.0)
        assert cd.feed_rate_min_mm_min < cd.feed_rate_max_mm_min

    def test_b221a_family_uses_same_parameters(self):
        """Kennametal B221A is aliased to CoroDrill 860 parameters."""
        cd = get_cutting_data(tool_family="B221A", material_grade="C45", diameter_mm=5.0)
        assert cd.readiness == CuttingDataReadiness.READY

    def test_no_data_for_60mm_diameter(self):
        """60 mm is outside the parameter table range."""
        cd = get_cutting_data(tool_family="CoroDrill 860", material_grade="C45", diameter_mm=60.0)
        assert cd.readiness == CuttingDataReadiness.NO_DATA


class TestP5CMachineLimitCheck:
    def test_within_limits(self):
        cd = get_cutting_data(
            tool_family="CoroDrill 860",
            material_grade="C45",
            diameter_mm=5.0,
            machine_max_rpm=20000,
        )
        assert cd.readiness == CuttingDataReadiness.READY
        assert cd.machine_limit_status == MachineLimitStatus.WITHIN_LIMITS
        assert cd.rpm_clamped is None

    def test_proposed_constrained_on_low_max_rpm(self):
        cd = get_cutting_data(
            tool_family="CoroDrill 860",
            material_grade="C45",
            diameter_mm=5.0,
            machine_max_rpm=5000,
        )
        assert cd.machine_limit_status == MachineLimitStatus.PROPOSED_CONSTRAINED
        assert cd.rpm_clamped == 5000
        assert cd.feed_rate_clamped_mm_min is not None

    def test_no_machine_when_not_provided(self):
        cd = get_cutting_data(
            tool_family="CoroDrill 860",
            material_grade="C45",
            diameter_mm=5.0,
        )
        assert cd.machine_limit_status == MachineLimitStatus.NO_MACHINE
        assert cd.rpm_clamped is None

    def test_clamped_rpm_equals_machine_max(self):
        cd = get_cutting_data(
            tool_family="CoroDrill 860",
            material_grade="C45",
            diameter_mm=5.0,
            machine_max_rpm=3000,
        )
        assert cd.rpm_clamped == 3000
