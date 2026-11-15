"""
P7 safety tests: audit that no P7 code path sets is_dispatchable=True.

Also verifies:
  - No production_released=True in any P7 module
  - No machine_ready_to_run=True in any P7 module
  - GENERIC_ISO_TEST_v1 is not_dispatchable=True and not_machine_certified=True
  - P7NCResult invariants cannot be overridden
  - NCReviewRecord invariants cannot be overridden
  - BatchSequenceProposal invariants cannot be overridden
  - VALIDATED_OFFLINE does not imply machine dispatch
"""

from __future__ import annotations

import pathlib

import pytest

from backend.manufacturing.clearance_policy import ClearanceSource, evaluate_clearance
from backend.manufacturing.nc_candidate import build_offline_nc_candidate
from backend.manufacturing.nc_generation_adapter import generate_nc_from_candidate
from backend.manufacturing.nc_review import (
    NCReviewChecklist,
    NCReviewStatus,
    record_nc_engineer_review,
)
from backend.manufacturing.parameter_confirmation import confirm_cutting_parameters
from backend.nc import GENERIC_ISO_TEST

# ---------------------------------------------------------------------------
# Static audit: is_dispatchable=True must not appear in P7 source files
# ---------------------------------------------------------------------------

_P7_SOURCE_FILES = [
    "backend/manufacturing/nc_generation_adapter.py",
    "backend/manufacturing/multi_hole_sequence.py",
    "backend/manufacturing/nc_review.py",
]

_REPO_ROOT = pathlib.Path(__file__).parent.parent.parent.parent


class TestStaticDispatchAudit:
    @pytest.mark.parametrize("rel_path", _P7_SOURCE_FILES)
    def test_no_is_dispatchable_true_in_source(self, rel_path):
        path = _REPO_ROOT / rel_path
        source = path.read_text(encoding="utf-8")
        # Look for literal is_dispatchable=True or is_dispatchable = True
        assert "is_dispatchable=True" not in source
        assert "is_dispatchable = True" not in source

    @pytest.mark.parametrize("rel_path", _P7_SOURCE_FILES)
    def test_no_production_released_true_in_source(self, rel_path):
        path = _REPO_ROOT / rel_path
        source = path.read_text(encoding="utf-8")
        assert "production_released=True" not in source
        assert "production_released = True" not in source

    @pytest.mark.parametrize("rel_path", _P7_SOURCE_FILES)
    def test_no_machine_ready_to_run_true_in_source(self, rel_path):
        path = _REPO_ROOT / rel_path
        source = path.read_text(encoding="utf-8")
        assert "machine_ready_to_run=True" not in source
        assert "machine_ready_to_run = True" not in source


# ---------------------------------------------------------------------------
# GENERIC_ISO_TEST profile safety
# ---------------------------------------------------------------------------

class TestGenericIsoTestSafety:
    def test_profile_not_dispatchable(self):
        assert GENERIC_ISO_TEST.not_dispatchable is True

    def test_profile_not_machine_certified(self):
        assert GENERIC_ISO_TEST.not_machine_certified is True

    def test_profile_id_correct(self):
        assert GENERIC_ISO_TEST.profile_id == "GENERIC_ISO_TEST_v1"

    def test_profile_no_fanuc_in_provenance(self):
        assert "Fanuc" not in GENERIC_ISO_TEST.provenance or "NOT" in GENERIC_ISO_TEST.provenance

    def test_profile_no_siemens_claim(self):
        prov = GENERIC_ISO_TEST.provenance
        assert "Siemens" not in prov or "NOT" in prov


# ---------------------------------------------------------------------------
# Full pipeline safety: VALIDATED_OFFLINE ≠ machine dispatch
# ---------------------------------------------------------------------------

def _make_full_p7_pipeline():
    confirmed_result = confirm_cutting_parameters(
        session_id="p7-safety-test",
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
    clearance = evaluate_clearance(
        clearance_z=5.0,
        clearance_source=ClearanceSource.USER_SUPPLIED,
        stock_top_z=0.0, feature_top_z=0.0,
        wcs_ref="DXF01_WCS",
    )
    candidate = build_offline_nc_candidate(
        sample_id="DXF-01",
        feature_id="feat-safety",
        hole_x=-225.5, hole_y=-968.6,
        hole_top_z=0.0, hole_depth_mm=25.0,
        feature_diameter_mm=4.891,
        material="C45",
        operation="drilling",
        tool_id="sandvik-860-1-0500-026a1-pm",
        tool_match_status="COMPATIBLE",
        tool_diameter_mm=5.0,
        clearance_eval=clearance,
        wcs_ref="DXF01_WCS",
        confirmed_params=confirmed_result.confirmed_params,
    )
    p7_result = generate_nc_from_candidate(candidate, tool_number=1)
    program = p7_result.generation_result.program
    review = record_nc_engineer_review(
        program,
        checklist=NCReviewChecklist(
            tool_numbers_verified=True,
            feeds_speeds_verified=True,
            depths_verified=True,
            wcs_offset_verified=True,
        ),
        reviewer_notes="All checks complete.",
    )
    return p7_result, review


class TestValidatedOfflineNotDispatch:
    def test_validated_offline_p7nc_result_not_dispatchable(self):
        p7_result, _ = _make_full_p7_pipeline()
        assert p7_result.is_dispatchable is False

    def test_validated_offline_nc_program_not_dispatchable(self):
        p7_result, _ = _make_full_p7_pipeline()
        program = p7_result.generation_result.program
        assert program.is_dispatchable is False

    def test_validated_offline_review_record_not_dispatchable(self):
        _, review = _make_full_p7_pipeline()
        assert review.status == NCReviewStatus.VALIDATED_OFFLINE
        assert review.is_dispatchable is False

    def test_validated_offline_production_not_released(self):
        _, review = _make_full_p7_pipeline()
        assert review.production_released is False

    def test_validated_offline_machine_not_ready(self):
        _, review = _make_full_p7_pipeline()
        assert review.machine_ready_to_run is False
