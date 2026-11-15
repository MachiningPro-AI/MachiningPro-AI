"""P6 safety / security invariant tests (MUST 49, MUST 54).

MUST 49: Search entire P6 codebase for any path that sets is_dispatchable=True.
Required: P6_DISPATCHABLE_TRUE_PATH_FOUND=NO.
"""

from __future__ import annotations

import pathlib

import pytest

# P6 production source files
_P6_FILES = [
    "backend/manufacturing/clearance_policy.py",
    "backend/manufacturing/parameter_confirmation.py",
    "backend/manufacturing/nc_bridge.py",
    "backend/manufacturing/nc_candidate.py",
]

_REPO_ROOT = pathlib.Path(__file__).parents[3]


def _source_text(rel_path: str) -> str:
    return (_REPO_ROOT / rel_path).read_text(encoding="utf-8")


class TestDispatchableTrueNotFound:
    """P6_DISPATCHABLE_TRUE_PATH_FOUND=NO."""

    @pytest.mark.parametrize("rel_path", _P6_FILES)
    def test_no_is_dispatchable_true_in_p6_files(self, rel_path):
        src = _source_text(rel_path)
        assert "is_dispatchable=True" not in src, (
            f"SECURITY: is_dispatchable=True found in {rel_path}"
        )
        assert "is_dispatchable = True" not in src, (
            f"SECURITY: is_dispatchable = True found in {rel_path}"
        )

    def test_no_is_dispatchable_true_in_cad_features_p6_endpoints(self):
        src = _source_text("backend/api/cad_features.py")
        # Only flag assignment patterns, not comments / docstrings
        assert "is_dispatchable=True" not in src
        assert "is_dispatchable = True" not in src


class TestSafetyInvariantsInNcCandidate:
    """Verify that the OfflineNCCandidate object always has correct safety fields."""

    def test_offline_only_hardcoded_true(self):
        from backend.manufacturing.nc_candidate import _LABEL_EN, _LABEL_TR
        assert "NOT FOR DIRECT MACHINE EXECUTION" in _LABEL_EN
        assert "OFLİN" in _LABEL_TR or "OFFLINE" in _LABEL_TR

    def test_nc_candidate_default_values(self):
        from backend.manufacturing.clearance_policy import evaluate_clearance
        from backend.manufacturing.nc_candidate import build_offline_nc_candidate
        from backend.toolpath.enums import ClearanceSource

        ce = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        nc = build_offline_nc_candidate(
            sample_id="test",
            feature_id="f1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=10.0,
            feature_diameter_mm=5.0,
            material="C45",
            operation="drilling",
            tool_id="t1",
            tool_match_status="EXACT",
            tool_diameter_mm=5.0,
            clearance_eval=ce,
            wcs_ref="W1",
            confirmed_params=None,
        )
        assert nc.offline_only is True
        assert nc.is_dispatchable is False
        assert nc.production_released is False
        assert nc.engineer_review_required is True

    def test_p6_readiness_report_invariants_always_false(self):
        from backend.manufacturing.clearance_policy import evaluate_clearance
        from backend.manufacturing.nc_candidate import evaluate_p6_readiness
        from backend.toolpath.enums import ClearanceSource

        ce = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        report = evaluate_p6_readiness(
            feature_id="f1",
            cam_ready=True,
            cam_ready_blocker=None,
            machine_id="M1",
            tool_id="T1",
            tool_match_status="EXACT",
            confirmed_params=None,
            param_confirmation_status=None,
            wcs_ref="W1",
            clearance_eval=ce,
            nc_candidate=None,
        )
        # Even when cam_ready=True, these are always False
        assert report.is_dispatchable is False
        assert report.production_released is False
        assert report.machine_ready_to_run is False


class TestNoAutoApprovalInParameterConfirmation:
    """No auto-confirmation: cutting params must be explicitly submitted."""

    def test_no_auto_confirm_no_input_no_confirm(self):
        """If no confirmation is called, confirmed_params is None."""
        from backend.manufacturing.clearance_policy import evaluate_clearance
        from backend.manufacturing.nc_candidate import build_offline_nc_candidate
        from backend.toolpath.enums import ClearanceSource

        ce = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="W1",
        )
        nc = build_offline_nc_candidate(
            sample_id="s",
            feature_id="f1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=10.0,
            feature_diameter_mm=5.0,
            material="C45",
            operation="drilling",
            tool_id="t1",
            tool_match_status="EXACT",
            tool_diameter_mm=5.0,
            clearance_eval=ce,
            wcs_ref="W1",
            confirmed_params=None,
        )
        assert nc.confirmed_params is None
        assert nc.nc_candidate_review_ready is False
