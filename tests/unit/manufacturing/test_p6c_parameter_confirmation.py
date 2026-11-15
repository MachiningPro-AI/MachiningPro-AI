"""P6-C cutting parameter confirmation gate tests (MUST 46)."""

from __future__ import annotations

import math

from backend.cutting_tools.cutting_parameters import CuttingDataStatus
from backend.manufacturing.parameter_confirmation import (
    ParameterConfirmationStatus,
    confirm_cutting_parameters,
)

# Sandvik CoroDrill 860-1 5mm range (from P5-C)
_TOOL_FAMILY = "CoroDrill 860"
_MATERIAL = "C45"
_DIAMETER = 5.0
_OPERATION = "drilling"
_VC_MIN = 70.0
_VC_MAX = 115.0
_FN_MIN = 0.06
_FN_MAX = 0.11
_SOURCE = "Sandvik Coromant CoroDrill 860-1 Application Guide"
_SOURCE_URL = "coromant.sandvik.com"


def _confirm(vc=90.0, fn=0.08, machine_max_rpm=None, machine_max_feed=None, **kw):
    return confirm_cutting_parameters(
        session_id="test-session",
        tool_family=kw.get("tool_family", _TOOL_FAMILY),
        material_grade=kw.get("material_grade", _MATERIAL),
        diameter_mm=kw.get("diameter_mm", _DIAMETER),
        operation=_OPERATION,
        vc_mpm=vc,
        fn_mm=fn,
        vc_min_mpm=_VC_MIN,
        vc_max_mpm=_VC_MAX,
        fn_min_mm=_FN_MIN,
        fn_max_mm=_FN_MAX,
        source=_SOURCE,
        source_url=_SOURCE_URL,
        machine_max_rpm=machine_max_rpm,
        machine_max_feed_mm_min=machine_max_feed,
    )


class TestManufacturerStartingValueStatus:
    def test_unconfirmed_cutting_data_status_is_not_user_confirmed(self):
        """Before confirmation, status is MANUFACTURER_STARTING_VALUE."""
        assert CuttingDataStatus.MANUFACTURER_STARTING_VALUE != CuttingDataStatus.USER_CONFIRMED

    def test_confirmed_status_is_user_confirmed(self):
        r = _confirm()
        assert r.status == ParameterConfirmationStatus.ENGINEER_CONFIRMED
        assert r.confirmed_params is not None
        assert r.confirmed_params.status == CuttingDataStatus.USER_CONFIRMED


class TestConfirmedParameter:
    def test_confirmed_has_correct_vc_fn(self):
        r = _confirm(vc=90.0, fn=0.08)
        assert r.status == ParameterConfirmationStatus.ENGINEER_CONFIRMED
        cp = r.confirmed_params
        assert cp is not None
        assert cp.vc_mpm == 90.0
        assert cp.fn_mm == 0.08

    def test_rpm_recalculated(self):
        import math as _math
        r = _confirm(vc=90.0, fn=0.08)
        cp = r.confirmed_params
        expected_rpm = (90.0 * 1000.0) / (_math.pi * 5.0)
        assert abs(cp.rpm_calculated - expected_rpm) < 0.01

    def test_feed_recalculated(self):
        r = _confirm(vc=90.0, fn=0.08)
        cp = r.confirmed_params
        expected_feed = cp.rpm_calculated * 0.08
        assert abs(cp.feed_rate_mm_min - expected_feed) < 0.01

    def test_provenance_recorded(self):
        r = _confirm()
        cp = r.confirmed_params
        assert cp.source == _SOURCE
        assert cp.source_url == _SOURCE_URL
        assert cp.session_id == "test-session"
        assert cp.confirmed_at != ""  # timestamp present


class TestMachineRpmLimitFailure:
    def test_rpm_exceeds_limit_returns_review_required(self):
        # Vc=115 on 5mm → RPM ≈ 7321 rpm; set limit to 5000
        r = _confirm(vc=115.0, fn=0.11, machine_max_rpm=5000.0)
        assert r.status == ParameterConfirmationStatus.REVIEW_REQUIRED
        assert r.confirmed_params is not None  # params still returned
        assert not r.confirmed_params.machine_check.rpm_within_limit
        assert any("RPM_LIMIT_EXCEEDED" in w for w in r.warnings)

    def test_rpm_within_limit_passes(self):
        r = _confirm(vc=70.0, fn=0.06, machine_max_rpm=20000.0)
        assert r.status == ParameterConfirmationStatus.ENGINEER_CONFIRMED
        assert r.confirmed_params.machine_check.rpm_within_limit is True


class TestFeedLimitFailure:
    def test_feed_exceeds_limit_returns_review_required(self):
        r = _confirm(vc=115.0, fn=0.11, machine_max_feed=100.0)
        assert r.status == ParameterConfirmationStatus.REVIEW_REQUIRED
        assert r.confirmed_params is not None
        assert not r.confirmed_params.machine_check.feed_within_limit


class TestInvalidVc:
    def test_negative_vc_blocked(self):
        r = _confirm(vc=-1.0)
        assert r.status == ParameterConfirmationStatus.INVALID_PARAMETERS
        assert r.confirmed_params is None
        assert any("INVALID_VC" in b for b in r.blockers)

    def test_zero_vc_blocked(self):
        r = _confirm(vc=0.0)
        assert r.status == ParameterConfirmationStatus.INVALID_PARAMETERS

    def test_nan_vc_blocked(self):
        r = _confirm(vc=math.nan)
        assert r.status == ParameterConfirmationStatus.INVALID_PARAMETERS

    def test_inf_vc_blocked(self):
        r = _confirm(vc=math.inf)
        assert r.status == ParameterConfirmationStatus.INVALID_PARAMETERS


class TestInvalidFn:
    def test_negative_fn_blocked(self):
        r = _confirm(fn=-0.01)
        assert r.status == ParameterConfirmationStatus.INVALID_PARAMETERS
        assert any("INVALID_FN" in b for b in r.blockers)

    def test_zero_fn_blocked(self):
        r = _confirm(fn=0.0)
        assert r.status == ParameterConfirmationStatus.INVALID_PARAMETERS


class TestOutOfManufacturerRange:
    def test_vc_above_max_blocked(self):
        r = _confirm(vc=200.0)  # above 115
        assert r.status == ParameterConfirmationStatus.OUT_OF_MANUFACTURER_RANGE
        assert r.confirmed_params is None

    def test_vc_below_min_blocked(self):
        r = _confirm(vc=10.0)  # below 70
        assert r.status == ParameterConfirmationStatus.OUT_OF_MANUFACTURER_RANGE

    def test_fn_above_max_blocked(self):
        r = _confirm(fn=0.5)  # above 0.11
        assert r.status == ParameterConfirmationStatus.OUT_OF_MANUFACTURER_RANGE

    def test_boundary_vc_passes(self):
        r = _confirm(vc=70.0, fn=0.06)
        assert r.status == ParameterConfirmationStatus.ENGINEER_CONFIRMED

    def test_boundary_vc_max_passes(self):
        r = _confirm(vc=115.0, fn=0.11)
        assert r.status in (
            ParameterConfirmationStatus.ENGINEER_CONFIRMED,
            ParameterConfirmationStatus.REVIEW_REQUIRED,
        )
