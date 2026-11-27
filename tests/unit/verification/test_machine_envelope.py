"""
Phase J/K/L + Phase Z — Machine envelope, WCS, axis limit tests.

Includes deterministic TEST_ONLY machine configurations for pass/fail cases.
TEST_ONLY_MACHINE_IDs: TEST-MACHINE-LARGE-01, TEST-MACHINE-SMALL-01

MACHINE_ENVELOPE_PASS_CASE=PASS (TEST-MACHINE-LARGE-01)
MACHINE_ENVELOPE_FAIL_CASE=FAIL (TEST-MACHINE-SMALL-01)
"""

import pytest

from backend.verification.checks import (
    check_axis_limit,
    check_machine_envelope,
    check_machine_envelope_with_wcs,
)
from backend.verification.enums import VerificationStatus
from backend.verification.models import VerificationSegment


def _seg(sx=0.0, sy=0.0, sz=0.0, ex=50.0, ey=50.0, ez=-20.0, is_cutting=True):
    return VerificationSegment(
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type="CUT" if is_cutting else "RAPID",
        is_cutting=is_cutting,
    )


# ---------------------------------------------------------------------------
# Phase Z: TEST_ONLY machine configurations
# ---------------------------------------------------------------------------

# TEST-MACHINE-LARGE-01: travel 1000×800×500 — easily contains typical parts
_LARGE_MACHINE_X = 1000.0
_LARGE_MACHINE_Y = 800.0
_LARGE_MACHINE_Z = 500.0

# TEST-MACHINE-SMALL-01: travel 10×10×10 — will fail on typical toolpath
_SMALL_MACHINE_X = 10.0
_SMALL_MACHINE_Y = 10.0
_SMALL_MACHINE_Z = 10.0


class TestMachineEnvelopeLargePass:
    """Phase Z — MACHINE_ENVELOPE_PASS_CASE=PASS."""

    def test_large_machine_contains_part(self):
        """TEST-MACHINE-LARGE-01 easily contains the part — PASS."""
        segs = [
            _seg(sx=-100.0, sy=-100.0, sz=0.0, ex=100.0, ey=100.0, ez=-50.0),
        ]
        result = check_machine_envelope_with_wcs(
            segs,
            travel_x_mm=_LARGE_MACHINE_X,
            travel_y_mm=_LARGE_MACHINE_Y,
            travel_z_mm=_LARGE_MACHINE_Z,
            machine_id="TEST-MACHINE-LARGE-01",
            machine_limit_source="TEST_ONLY",
        )
        assert result.status == VerificationStatus.PASS, (
            f"MACHINE_ENVELOPE_PASS_CASE: Expected PASS. Got {result.status}. "
            f"Evidence: {result.evidence}"
        )


class TestMachineEnvelopeSmallFail:
    """Phase Z — MACHINE_ENVELOPE_FAIL_CASE=FAIL."""

    def test_small_machine_fails_part(self):
        """TEST-MACHINE-SMALL-01 is too small — FAIL."""
        segs = [
            _seg(sx=100.0, sy=100.0, sz=0.0, ex=200.0, ey=200.0, ez=-50.0),
        ]
        result = check_machine_envelope_with_wcs(
            segs,
            travel_x_mm=_SMALL_MACHINE_X,
            travel_y_mm=_SMALL_MACHINE_Y,
            travel_z_mm=_SMALL_MACHINE_Z,
            machine_id="TEST-MACHINE-SMALL-01",
            machine_limit_source="TEST_ONLY",
        )
        assert result.status == VerificationStatus.FAIL, (
            f"MACHINE_ENVELOPE_FAIL_CASE: Expected FAIL. Got {result.status}"
        )
        assert result.issues, "Expected issues for small machine"


# ---------------------------------------------------------------------------
# Phase K: WCS transform tests
# ---------------------------------------------------------------------------

class TestMachineEnvelopeWCS:
    def test_wcs_offset_keeps_part_in_envelope(self):
        """Part at x=200 raw; WCS offset -200 brings it to 0 → PASS."""
        segs = [_seg(sx=200.0, sy=0.0, sz=0.0, ex=200.0, ey=0.0, ez=-10.0)]
        result = check_machine_envelope_with_wcs(
            segs,
            travel_x_mm=600.0,
            travel_y_mm=600.0,
            travel_z_mm=600.0,
            wcs_offset_x_mm=-200.0,
        )
        assert result.status == VerificationStatus.PASS

    def test_wcs_offset_pushes_part_out_of_envelope(self):
        """Part at x=100 raw; WCS offset +400 → 500 which exceeds ±250 → FAIL."""
        segs = [_seg(sx=100.0, sy=0.0, sz=0.0, ex=100.0, ey=0.0, ez=-5.0)]
        result = check_machine_envelope_with_wcs(
            segs,
            travel_x_mm=500.0,  # ±250
            travel_y_mm=500.0,
            travel_z_mm=500.0,
            wcs_offset_x_mm=400.0,
        )
        assert result.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# Phase L: Axis limit violation tests (structured violations)
# ---------------------------------------------------------------------------

class TestAxisLimitViolations:
    def test_x_axis_violation(self):
        segs = [_seg(sx=400.0, ex=400.0)]
        axis_limits = {"X": (-300.0, 300.0), "Y": (-250.0, 250.0), "Z": (-400.0, 0.0)}
        result = check_axis_limit(segs, axis_limits)
        assert result.status == VerificationStatus.FAIL
        x_issues = [i for i in result.issues if "X" in i.evidence.get("AXIS", "")]
        assert x_issues, "Expected X axis violation"
        ev = x_issues[0].evidence
        assert ev["AXIS"] == "X"
        assert ev["COMMAND_POSITION"] == 400.0
        assert ev["LIMIT_MAX"] == 300.0
        assert ev["EXCESS_MM"] > 0

    def test_all_axes_in_range_pass(self):
        segs = [_seg(sx=100.0, sy=50.0, sz=-100.0, ex=150.0, ey=80.0, ez=-150.0)]
        axis_limits = {"X": (-300.0, 300.0), "Y": (-250.0, 250.0), "Z": (-400.0, 0.0)}
        result = check_axis_limit(segs, axis_limits)
        assert result.status == VerificationStatus.PASS

    def test_no_axis_limits_not_performed(self):
        segs = [_seg()]
        result = check_axis_limit(segs, None)
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_violation_reports_operation_id(self):
        segs = [
            VerificationSegment(
                start_x=500.0, start_y=0.0, start_z=0.0,
                end_x=500.0, end_y=0.0, end_z=0.0,
                motion_type="CUT", is_cutting=True,
                operation_id="SETUP_01_OP_01",
            )
        ]
        axis_limits = {"X": (-300.0, 300.0)}
        result = check_axis_limit(segs, axis_limits)
        assert result.status == VerificationStatus.FAIL
        assert result.issues[0].evidence.get("OPERATION_ID") == "SETUP_01_OP_01"


# ---------------------------------------------------------------------------
# Machine envelope insufficient data
# ---------------------------------------------------------------------------

class TestMachineEnvelopeInsufficient:
    def test_no_travel_limits(self):
        segs = [_seg()]
        result = check_machine_envelope_with_wcs(segs, None, None, None)
        assert result.status == VerificationStatus.INSUFFICIENT_DATA

    def test_no_segments_pass(self):
        result = check_machine_envelope_with_wcs(
            [], 600.0, 500.0, 400.0,
            machine_id="TEST-MACHINE-LARGE-01",
        )
        assert result.status == VerificationStatus.PASS
