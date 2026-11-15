"""P6-A clearance policy tests (MUST 45)."""

from __future__ import annotations

import math

from backend.manufacturing.clearance_policy import (
    ClearanceEvaluationStatus,
    evaluate_clearance,
)
from backend.toolpath.enums import ClearanceSource


class TestMissingClearance:
    def test_none_clearance_z_returns_required(self):
        r = evaluate_clearance(
            clearance_z=None,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.CLEARANCE_Z_REQUIRED
        assert r.blocker is not None
        assert "CLEARANCE_Z_REQUIRED" in r.blocker

    def test_unknown_source_returns_required(self):
        r = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.UNKNOWN,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.CLEARANCE_Z_REQUIRED


class TestUserConfirmedClearance:
    def test_user_defined_above_stock_passes(self):
        r = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="SETUP_1_WCS",
        )
        assert r.toolpath_ready is True
        assert r.status == ClearanceEvaluationStatus.TOOLPATH_READY
        assert r.clearance_plane.value_mm == 5.0
        assert r.clearance_plane.source == ClearanceSource.USER_DEFINED
        assert r.blocker is None

    def test_user_supplied_above_stock_passes(self):
        r = evaluate_clearance(
            clearance_z=10.0,
            clearance_source=ClearanceSource.USER_SUPPLIED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W2",
        )
        assert r.toolpath_ready is True

    def test_fixture_configuration_passes(self):
        r = evaluate_clearance(
            clearance_z=20.0,
            clearance_source=ClearanceSource.FIXTURE_CONFIGURATION,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="FIXTURE_WCS",
        )
        assert r.toolpath_ready is True


class TestInvalidClearance:
    def test_nan_clearance_blocked(self):
        r = evaluate_clearance(
            clearance_z=math.nan,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.INVALID_CLEARANCE

    def test_inf_clearance_blocked(self):
        r = evaluate_clearance(
            clearance_z=math.inf,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.INVALID_CLEARANCE


class TestClearanceBelowCuttingRegion:
    def test_clearance_below_feature_top_blocked(self):
        r = evaluate_clearance(
            clearance_z=-5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=None,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.CLEARANCE_BELOW_MACHINING_REGION

    def test_clearance_at_feature_top_blocked(self):
        r = evaluate_clearance(
            clearance_z=0.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=None,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        # 0.0 is not strictly above 0.0, so it should be blocked
        assert r.toolpath_ready is False


class TestClearanceBelowStock:
    def test_clearance_below_stock_blocked(self):
        r = evaluate_clearance(
            clearance_z=-2.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=-5.0,
            wcs_ref="W1",
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.CLEARANCE_BELOW_STOCK


class TestUnknownWCS:
    def test_wcs_none_blocked(self):
        r = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref=None,
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.WCS_UNKNOWN
        assert "WCS_UNKNOWN" in (r.blocker or "")


class TestValidWCSAndClearance:
    def test_all_valid_passes_with_collision_warnings(self):
        r = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="TEST_WCS",
        )
        assert r.toolpath_ready is True
        # Collision / simulation safety notes are always present
        assert r.fixture_collision_validated is False
        assert r.holder_collision_validated is False
        assert r.stock_removal_validated is False
        # Notes mention validation state
        notes_joined = " ".join(r.validation_notes)
        assert "FIXTURE_COLLISION_VALIDATED=NO" in notes_joined
        assert "HOLDER_COLLISION_VALIDATED=NO" in notes_joined
        assert "STOCK_REMOVAL_VALIDATED=NO" in notes_joined
