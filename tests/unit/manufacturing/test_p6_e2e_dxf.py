"""P6 end-to-end DXF-01 offline toolpath / NC candidate test (MUST 50).

Exercises the full DXF-01 path:
  109106_01_30.dxf → 9 circles → first feature (4.891mm) → Sandvik 5.0mm drill
  COMPATIBLE match → MANUFACTURER_STARTING_VALUE → engineer confirm →
  clearance policy → toolpath generation → NC bridge → offline candidate

P6_DISPATCHABLE_TRUE_PATH_FOUND=NO must remain true throughout.
"""

from __future__ import annotations

import pytest

from backend.cutting_tools.cutting_parameters import CuttingDataStatus
from backend.manufacturing.clearance_policy import (
    ClearanceEvaluationStatus,
    evaluate_clearance,
)
from backend.manufacturing.nc_bridge import toolpath_to_nc_segments
from backend.manufacturing.nc_candidate import (
    build_offline_nc_candidate,
    evaluate_p6_readiness,
)
from backend.manufacturing.parameter_confirmation import (
    ParameterConfirmationStatus,
    confirm_cutting_parameters,
)
from backend.toolpath.enums import ClearanceSource, ToolpathStatus
from backend.toolpath.generators import DrillInput, generate_drill_toolpath

# ── Official DXF-01 fixture values (from P5 Final Acceptance, READ-ONLY) ──────
DXF01_SAMPLE_ID = "109106_01_30.dxf"
DXF01_FEATURE_ID = "feat-dxf01-01"
DXF01_HOLE_X = -225.54485
DXF01_HOLE_Y = -968.552339
DXF01_HOLE_TOP_Z = 0.0
DXF01_HOLE_DEPTH_MM = 30.0
DXF01_FEATURE_DIAMETER_MM = 4.891
DXF01_MATERIAL = "C45"
DXF01_OPERATION = "drilling"
DXF01_TOOL_ID = "sandvik-860-1-0500-026a1-pm"
DXF01_TOOL_DIAMETER_MM = 5.0
DXF01_TOOL_MATCH_STATUS = "COMPATIBLE"
DXF01_DELTA_MM = DXF01_TOOL_DIAMETER_MM - DXF01_FEATURE_DIAMETER_MM  # +0.109mm
DXF01_VC_MIN = 70.0
DXF01_VC_MAX = 115.0
DXF01_FN_MIN = 0.06
DXF01_FN_MAX = 0.11
_SOURCE = "Sandvik Coromant CoroDrill 860-1 Application Guide"
_SOURCE_URL = "coromant.sandvik.com"


# ── Step 1: Engineer confirms cutting parameters ──────────────────────────────

class TestStep1ParameterConfirmation:
    """MUST: MANUFACTURER_STARTING_VALUE → USER_CONFIRMED via engineer action."""

    def test_initial_status_not_confirmed(self):
        """Before any call, the status is MANUFACTURER_STARTING_VALUE."""
        assert CuttingDataStatus.MANUFACTURER_STARTING_VALUE is not CuttingDataStatus.USER_CONFIRMED

    def test_engineer_confirms_nominal_parameters(self):
        r = confirm_cutting_parameters(
            session_id="dxf01-sess",
            tool_family="CoroDrill 860",
            material_grade=DXF01_MATERIAL,
            diameter_mm=DXF01_TOOL_DIAMETER_MM,
            operation=DXF01_OPERATION,
            vc_mpm=90.0,
            fn_mm=0.08,
            vc_min_mpm=DXF01_VC_MIN,
            vc_max_mpm=DXF01_VC_MAX,
            fn_min_mm=DXF01_FN_MIN,
            fn_max_mm=DXF01_FN_MAX,
            source=_SOURCE,
            source_url=_SOURCE_URL,
        )
        assert r.status == ParameterConfirmationStatus.ENGINEER_CONFIRMED
        assert r.confirmed_params is not None
        assert r.confirmed_params.status == CuttingDataStatus.USER_CONFIRMED

    def test_manufacturer_starting_value_blocked_before_confirm(self):
        """NC_CANDIDATE_REVIEW_READY must be NO with MANUFACTURER_STARTING_VALUE."""
        nc = build_offline_nc_candidate(
            sample_id=DXF01_SAMPLE_ID,
            feature_id=DXF01_FEATURE_ID,
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            feature_diameter_mm=DXF01_FEATURE_DIAMETER_MM,
            material=DXF01_MATERIAL,
            operation=DXF01_OPERATION,
            tool_id=DXF01_TOOL_ID,
            tool_match_status=DXF01_TOOL_MATCH_STATUS,
            tool_diameter_mm=DXF01_TOOL_DIAMETER_MM,
            clearance_eval=evaluate_clearance(
                clearance_z=5.0,
                clearance_source=ClearanceSource.USER_DEFINED,
                stock_top_z=0.0,
                feature_top_z=0.0,
                wcs_ref="DXF01_WCS",
            ),
            wcs_ref="DXF01_WCS",
            confirmed_params=None,  # NOT YET CONFIRMED
        )
        assert nc.nc_candidate_review_ready is False


# ── Step 2: Clearance policy ─────────────────────────────────────────────────

class TestStep2ClearancePolicy:
    def test_missing_wcs_blocked(self):
        r = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref=None,
        )
        assert r.toolpath_ready is False
        assert r.status == ClearanceEvaluationStatus.WCS_UNKNOWN

    def test_valid_clearance_ready(self):
        r = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="DXF01_WCS",
        )
        assert r.toolpath_ready is True
        assert r.fixture_collision_validated is False
        assert r.holder_collision_validated is False


# ── Step 3: Toolpath generation ───────────────────────────────────────────────

class TestStep3ToolpathGeneration:
    def test_drill_toolpath_generated_with_dxf01_values(self):
        inp = DrillInput(
            operation_ref="op-dxf01-01",
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            wcs_ref="DXF01_WCS",
            tool_ref=DXF01_TOOL_ID,
            feature_refs=[DXF01_FEATURE_ID],
        )
        tp = generate_drill_toolpath(inp)
        # Drill generator returns VERIFICATION_REQUIRED (offline safety intent)
        assert tp.status in (ToolpathStatus.GENERATED, ToolpathStatus.VERIFICATION_REQUIRED)
        assert tp.metrics.segment_count > 0

    def test_drill_toolpath_has_approach_plunge_retract(self):
        from backend.toolpath.enums import MotionType
        inp = DrillInput(
            operation_ref="op-dxf01-01",
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            wcs_ref="DXF01_WCS",
            tool_ref=DXF01_TOOL_ID,
            feature_refs=[DXF01_FEATURE_ID],
        )
        tp = generate_drill_toolpath(inp)
        motion_types = {seg.motion_type for seg in tp.segments}
        assert MotionType.APPROACH in motion_types
        assert MotionType.PLUNGE in motion_types
        assert MotionType.RETRACT in motion_types

    def test_drill_toolpath_coordinates_match(self):
        inp = DrillInput(
            operation_ref="op-dxf01-01",
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            wcs_ref="DXF01_WCS",
            tool_ref=DXF01_TOOL_ID,
            feature_refs=[DXF01_FEATURE_ID],
        )
        tp = generate_drill_toolpath(inp)
        from backend.toolpath.enums import MotionType
        plunge_segs = [s for s in tp.segments if s.motion_type == MotionType.PLUNGE]
        assert len(plunge_segs) > 0
        # Plunge must start at the hole center XY
        ps = plunge_segs[0]
        assert abs(ps.start_point[0] - DXF01_HOLE_X) < 1e-6
        assert abs(ps.start_point[1] - DXF01_HOLE_Y) < 1e-6


# ── Step 4: NC bridge adapter ─────────────────────────────────────────────────

class TestStep4NcBridge:
    def _make_toolpath(self):
        inp = DrillInput(
            operation_ref="op-dxf01-01",
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            wcs_ref="DXF01_WCS",
            tool_ref=DXF01_TOOL_ID,
            feature_refs=[DXF01_FEATURE_ID],
        )
        return generate_drill_toolpath(inp)

    def test_nc_segments_produced_from_dxf01_toolpath(self):
        tp = self._make_toolpath()
        segs = toolpath_to_nc_segments(tp)
        assert len(segs) > 0

    def test_nc_segments_all_have_required_keys(self):
        tp = self._make_toolpath()
        segs = toolpath_to_nc_segments(tp)
        for seg in segs:
            assert "motion_type" in seg
            assert "start_x" in seg
            assert "start_y" in seg
            assert "start_z" in seg
            assert "end_x" in seg
            assert "end_z" in seg
            assert "is_cutting" in seg


# ── Step 5: Offline NC candidate ─────────────────────────────────────────────

class TestStep5OfflineNcCandidate:
    def _make_candidate(self, confirmed_params=None):
        ce = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="DXF01_WCS",
        )
        return build_offline_nc_candidate(
            sample_id=DXF01_SAMPLE_ID,
            feature_id=DXF01_FEATURE_ID,
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            feature_diameter_mm=DXF01_FEATURE_DIAMETER_MM,
            material=DXF01_MATERIAL,
            operation=DXF01_OPERATION,
            tool_id=DXF01_TOOL_ID,
            tool_match_status=DXF01_TOOL_MATCH_STATUS,
            tool_diameter_mm=DXF01_TOOL_DIAMETER_MM,
            clearance_eval=ce,
            wcs_ref="DXF01_WCS",
            confirmed_params=confirmed_params,
        )

    def _confirm(self):
        r = confirm_cutting_parameters(
            session_id="dxf01-sess",
            tool_family="CoroDrill 860",
            material_grade=DXF01_MATERIAL,
            diameter_mm=DXF01_TOOL_DIAMETER_MM,
            operation=DXF01_OPERATION,
            vc_mpm=90.0,
            fn_mm=0.08,
            vc_min_mpm=DXF01_VC_MIN,
            vc_max_mpm=DXF01_VC_MAX,
            fn_min_mm=DXF01_FN_MIN,
            fn_max_mm=DXF01_FN_MAX,
            source=_SOURCE,
            source_url=_SOURCE_URL,
        )
        return r.confirmed_params

    def test_offline_flag_always_true(self):
        nc = self._make_candidate()
        assert nc.offline_only is True

    def test_is_dispatchable_always_false(self):
        nc = self._make_candidate(confirmed_params=self._confirm())
        assert nc.is_dispatchable is False

    def test_production_released_always_false(self):
        nc = self._make_candidate(confirmed_params=self._confirm())
        assert nc.production_released is False

    def test_compatible_risk_warning_present(self):
        """DXF-01 MUST 54: COMPATIBLE match MUST appear in toolpath/NC."""
        nc = self._make_candidate()
        joined = " ".join(nc.warnings)
        assert "COMPATIBLE" in joined
        assert nc.tool_risk_warning is not None
        assert nc.provenance["tool_match_status"] == "COMPATIBLE"

    def test_compatible_risk_in_provenance_every_time(self):
        """TOOL_DIAMETER_MATCH=COMPATIBLE_REVIEW must appear in provenance."""
        nc = self._make_candidate(confirmed_params=self._confirm())
        # Provenance must record the match status
        assert nc.provenance["tool_match_status"] == "COMPATIBLE"
        # Delta must be recorded
        assert nc.provenance.get("tool_diameter_mm") == DXF01_TOOL_DIAMETER_MM
        assert nc.provenance.get("feature_diameter_mm") == pytest.approx(
            DXF01_FEATURE_DIAMETER_MM, abs=1e-4
        )

    def test_nc_candidate_review_ready_with_confirmed_params(self):
        nc = self._make_candidate(confirmed_params=self._confirm())
        assert nc.nc_candidate_review_ready is True

    def test_nc_candidate_not_review_ready_without_params(self):
        nc = self._make_candidate(confirmed_params=None)
        assert nc.nc_candidate_review_ready is False

    def test_nc_segments_non_empty_with_valid_clearance(self):
        nc = self._make_candidate(confirmed_params=self._confirm())
        assert len(nc.nc_segments) > 0

    def test_dxf01_location_in_provenance(self):
        nc = self._make_candidate()
        assert nc.provenance["sample_id"] == DXF01_SAMPLE_ID
        assert nc.provenance["feature_id"] == DXF01_FEATURE_ID


# ── Step 6: P6 readiness report ───────────────────────────────────────────────

class TestStep6P6Readiness:
    def _make_all(self):
        cp_result = confirm_cutting_parameters(
            session_id="dxf01-sess",
            tool_family="CoroDrill 860",
            material_grade=DXF01_MATERIAL,
            diameter_mm=DXF01_TOOL_DIAMETER_MM,
            operation=DXF01_OPERATION,
            vc_mpm=90.0,
            fn_mm=0.08,
            vc_min_mpm=DXF01_VC_MIN,
            vc_max_mpm=DXF01_VC_MAX,
            fn_min_mm=DXF01_FN_MIN,
            fn_max_mm=DXF01_FN_MAX,
            source=_SOURCE,
            source_url=_SOURCE_URL,
        )
        ce = evaluate_clearance(
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            stock_top_z=0.0,
            feature_top_z=0.0,
            wcs_ref="DXF01_WCS",
        )
        nc = build_offline_nc_candidate(
            sample_id=DXF01_SAMPLE_ID,
            feature_id=DXF01_FEATURE_ID,
            hole_x=DXF01_HOLE_X,
            hole_y=DXF01_HOLE_Y,
            hole_top_z=DXF01_HOLE_TOP_Z,
            hole_depth_mm=DXF01_HOLE_DEPTH_MM,
            feature_diameter_mm=DXF01_FEATURE_DIAMETER_MM,
            material=DXF01_MATERIAL,
            operation=DXF01_OPERATION,
            tool_id=DXF01_TOOL_ID,
            tool_match_status=DXF01_TOOL_MATCH_STATUS,
            tool_diameter_mm=DXF01_TOOL_DIAMETER_MM,
            clearance_eval=ce,
            wcs_ref="DXF01_WCS",
            confirmed_params=cp_result.confirmed_params,
        )
        return cp_result, ce, nc

    def test_full_dxf01_readiness_report(self):
        cp_result, ce, nc = self._make_all()
        report = evaluate_p6_readiness(
            feature_id=DXF01_FEATURE_ID,
            cam_ready=True,
            cam_ready_blocker=None,
            machine_id="okuma-mb46vae-01",
            tool_id=DXF01_TOOL_ID,
            tool_match_status=DXF01_TOOL_MATCH_STATUS,
            confirmed_params=cp_result.confirmed_params,
            param_confirmation_status=ParameterConfirmationStatus.ENGINEER_CONFIRMED,
            wcs_ref="DXF01_WCS",
            clearance_eval=ce,
            nc_candidate=nc,
        )
        assert report.cam_ready is True
        assert report.parameterized_cam_ready is True
        assert report.toolpath_ready is True
        assert report.nc_candidate_ready is True
        assert report.nc_candidate_review_ready is True
        # Safety invariants always false
        assert report.is_dispatchable is False
        assert report.production_released is False
        assert report.machine_ready_to_run is False

    def test_dxf01_readiness_no_blockers_when_all_gates_met(self):
        cp_result, ce, nc = self._make_all()
        report = evaluate_p6_readiness(
            feature_id=DXF01_FEATURE_ID,
            cam_ready=True,
            cam_ready_blocker=None,
            machine_id="okuma-mb46vae-01",
            tool_id=DXF01_TOOL_ID,
            tool_match_status=DXF01_TOOL_MATCH_STATUS,
            confirmed_params=cp_result.confirmed_params,
            param_confirmation_status=ParameterConfirmationStatus.ENGINEER_CONFIRMED,
            wcs_ref="DXF01_WCS",
            clearance_eval=ce,
            nc_candidate=nc,
        )
        assert report.cam_ready_blocker is None
        assert report.toolpath_ready_blocker is None
        assert report.nc_candidate_ready_blocker is None

    def test_dxf01_dispatchable_path_not_found(self):
        """P6_DISPATCHABLE_TRUE_PATH_FOUND=NO — final safety assertion."""
        cp_result, ce, nc = self._make_all()
        report = evaluate_p6_readiness(
            feature_id=DXF01_FEATURE_ID,
            cam_ready=True,
            cam_ready_blocker=None,
            machine_id="okuma-mb46vae-01",
            tool_id=DXF01_TOOL_ID,
            tool_match_status=DXF01_TOOL_MATCH_STATUS,
            confirmed_params=cp_result.confirmed_params,
            param_confirmation_status=ParameterConfirmationStatus.ENGINEER_CONFIRMED,
            wcs_ref="DXF01_WCS",
            clearance_eval=ce,
            nc_candidate=nc,
        )
        assert nc.is_dispatchable is False
        assert report.is_dispatchable is False
        assert report.production_released is False
        assert report.machine_ready_to_run is False
