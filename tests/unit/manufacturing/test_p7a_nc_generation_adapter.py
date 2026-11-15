"""
P7-A tests: NC generation adapter — OfflineNCCandidate → NCGenerationInput → NCProgram.

Tests verify:
  - build_nc_generation_input returns None when nc_candidate_review_ready=False
  - SegmentProxy correctly wraps dict segments for getattr access
  - generate_nc_from_candidate produces NCProgramStatus.CANDIDATE on success
  - generate_nc_from_candidate returns BLOCKED when not review-ready
  - Safety invariants: is_dispatchable=False, production_released=False in every result
  - GENERIC_ISO_TEST_v1 is the only profile used (NOT_CLAIMED for controller)
  - WCS=None → UNKNOWN work offset → NC engine blocks
  - P7NCResult invariants cannot be overridden
"""

from __future__ import annotations

import pytest

from backend.manufacturing.clearance_policy import (
    ClearanceSource,
    evaluate_clearance,
)
from backend.manufacturing.nc_candidate import OfflineNCCandidate, build_offline_nc_candidate
from backend.manufacturing.nc_generation_adapter import (
    SegmentProxy,
    build_nc_generation_input,
    generate_nc_from_candidate,
)
from backend.manufacturing.parameter_confirmation import confirm_cutting_parameters
from backend.nc import NCProgramStatus, WorkOffsetRef

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_confirmed_params():
    result = confirm_cutting_parameters(
        session_id="test-session",
        tool_family="CoroDrill 860",
        material_grade="C45",
        diameter_mm=5.0,
        operation="drilling",
        vc_mpm=90.0,
        fn_mm=0.08,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.06,
        fn_max_mm=0.11,
        source="Sandvik Coromant Application Guide",
        source_url="coromant.sandvik.com",
    )
    return result.confirmed_params


def _make_clearance_eval():
    return evaluate_clearance(
        clearance_z=5.0,
        clearance_source=ClearanceSource.USER_SUPPLIED,
        stock_top_z=0.0,
        feature_top_z=0.0,
        wcs_ref="DXF01_WCS",
    )


def _make_review_ready_candidate() -> OfflineNCCandidate:
    confirmed = _make_confirmed_params()
    clearance = _make_clearance_eval()
    return build_offline_nc_candidate(
        sample_id="DXF-01",
        feature_id="feat-001",
        hole_x=-225.54485,
        hole_y=-968.552339,
        hole_top_z=0.0,
        hole_depth_mm=25.0,
        feature_diameter_mm=4.891,
        material="C45",
        operation="drilling",
        tool_id="sandvik-860-1-0500-026a1-pm",
        tool_match_status="COMPATIBLE",
        tool_diameter_mm=5.0,
        clearance_eval=clearance,
        wcs_ref="DXF01_WCS",
        confirmed_params=confirmed,
    )


def _make_unconfirmed_candidate() -> OfflineNCCandidate:
    clearance = _make_clearance_eval()
    return build_offline_nc_candidate(
        sample_id="DXF-01",
        feature_id="feat-001",
        hole_x=-225.54485,
        hole_y=-968.552339,
        hole_top_z=0.0,
        hole_depth_mm=25.0,
        feature_diameter_mm=4.891,
        material="C45",
        operation="drilling",
        tool_id="sandvik-860-1-0500-026a1-pm",
        tool_match_status="COMPATIBLE",
        tool_diameter_mm=5.0,
        clearance_eval=clearance,
        wcs_ref="DXF01_WCS",
        confirmed_params=None,
    )


# ---------------------------------------------------------------------------
# SegmentProxy tests
# ---------------------------------------------------------------------------

class TestSegmentProxy:
    def test_getattr_returns_dict_value(self):
        proxy = SegmentProxy({"motion_type": "FEED_LINEAR", "end_x": 1.5})
        assert proxy.motion_type == "FEED_LINEAR"
        assert proxy.end_x == 1.5

    def test_missing_key_raises_attribute_error(self):
        proxy = SegmentProxy({"motion_type": "RAPID_LINEAR"})
        with pytest.raises(AttributeError):
            _ = proxy.nonexistent_key

    def test_none_value_is_accessible(self):
        proxy = SegmentProxy({"arc_center": None})
        assert proxy.arc_center is None

    def test_nested_dict_accessible(self):
        proxy = SegmentProxy({"start_x": -225.5, "end_z": -25.0})
        assert proxy.start_x == pytest.approx(-225.5)
        assert proxy.end_z == pytest.approx(-25.0)

    def test_is_cutting_accessible(self):
        proxy = SegmentProxy({"is_cutting": True, "motion_type": "FEED_LINEAR"})
        assert proxy.is_cutting is True


# ---------------------------------------------------------------------------
# build_nc_generation_input tests
# ---------------------------------------------------------------------------

class TestBuildNcGenerationInput:
    def test_returns_none_when_not_review_ready(self):
        candidate = _make_unconfirmed_candidate()
        assert not candidate.nc_candidate_review_ready
        result = build_nc_generation_input(candidate, tool_number=1)
        assert result is None

    def test_returns_input_when_review_ready(self):
        candidate = _make_review_ready_candidate()
        assert candidate.nc_candidate_review_ready
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None

    def test_verification_state_is_verified(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None
        assert nc_inp.verification_state == "VERIFIED"

    def test_uses_generic_iso_test_profile(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None
        assert nc_inp.post_profile.profile_id == "GENERIC_ISO_TEST_v1"

    def test_tool_number_propagated(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=3)
        assert nc_inp is not None
        assert nc_inp.tool_number == 3

    def test_spindle_speed_from_confirmed_params(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None
        assert nc_inp.spindle_speed_rpm == pytest.approx(candidate.confirmed_params.rpm_calculated)

    def test_feed_from_confirmed_params(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None
        assert nc_inp.feed_mmpm == pytest.approx(candidate.confirmed_params.feed_rate_mm_min)

    def test_work_offset_set_when_wcs_ref_present(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None
        assert nc_inp.work_offset != WorkOffsetRef.UNKNOWN

    def test_wcs_none_gives_unknown_work_offset(self):
        candidate = _make_review_ready_candidate()
        object.__setattr__(candidate, "wcs_ref", None)
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        # wcs_ref=None → UNKNOWN → NC engine will block
        assert nc_inp is not None
        assert nc_inp.work_offset == WorkOffsetRef.UNKNOWN

    def test_custom_program_number(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1, program_number="TEST-001")
        assert nc_inp is not None
        assert nc_inp.program_number == "TEST-001"

    def test_segments_wrapped_as_proxies(self):
        candidate = _make_review_ready_candidate()
        nc_inp = build_nc_generation_input(candidate, tool_number=1)
        assert nc_inp is not None
        assert len(nc_inp.segments) > 0
        # Each segment must expose motion_type via getattr
        for seg in nc_inp.segments:
            mt = getattr(seg, "motion_type", None)
            assert mt is not None


# ---------------------------------------------------------------------------
# generate_nc_from_candidate tests
# ---------------------------------------------------------------------------

class TestGenerateNcFromCandidate:
    def test_blocked_when_not_review_ready(self):
        candidate = _make_unconfirmed_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.nc_program_status == NCProgramStatus.BLOCKED

    def test_candidate_status_on_success(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.nc_program_status == NCProgramStatus.CANDIDATE

    def test_nc_program_id_set_on_success(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.nc_program_id is not None

    def test_nc_program_is_not_dispatchable(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        program = result.generation_result.program
        assert program is not None
        assert program.is_dispatchable is False

    def test_nc_program_is_offline_candidate(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        program = result.generation_result.program
        assert program is not None
        assert program.is_offline_candidate is True

    def test_nc_program_has_safety_warnings(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        program = result.generation_result.program
        assert program is not None
        assert len(program.safety_warnings) > 0

    def test_nc_program_has_blocks(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        program = result.generation_result.program
        assert program is not None
        assert program.block_count > 0

    def test_post_profile_id_in_result(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.post_profile_id == "GENERIC_ISO_TEST_v1"


# ---------------------------------------------------------------------------
# P7NCResult safety invariant tests
# ---------------------------------------------------------------------------

class TestP7NCResultSafetyInvariants:
    def test_is_dispatchable_always_false(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.is_dispatchable is False

    def test_production_released_always_false(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.production_released is False

    def test_machine_ready_to_run_always_false(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.machine_ready_to_run is False

    def test_production_controller_compatibility_not_claimed(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.production_controller_compatibility == "NOT_CLAIMED"

    def test_blocked_result_also_has_false_invariants(self):
        candidate = _make_unconfirmed_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.is_dispatchable is False
        assert result.production_released is False
        assert result.machine_ready_to_run is False

    def test_safety_invariants_cannot_be_overridden(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        # Attempt to override — __post_init__ must enforce False
        result.is_dispatchable = True  # direct attribute set
        result.__post_init__()
        assert result.is_dispatchable is False

    def test_warnings_contain_offline_label_en(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert any("OFFLINE ENGINEERING CANDIDATE" in w for w in result.warnings)

    def test_warnings_contain_offline_label_tr(self):
        candidate = _make_review_ready_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert any("OFLİN" in w for w in result.warnings)
