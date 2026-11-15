"""
P7-C tests: Engineer NC review gate — CANDIDATE → VALIDATED_OFFLINE.

Tests verify:
  - NCReviewChecklist.all_mandatory_checks_passed() returns correct values
  - NCReviewChecklist.missing_checks() lists unchecked items
  - record_nc_engineer_review promotes to VALIDATED_OFFLINE when all checks pass
  - Partial checklist → ENGINEER_REVIEWED (not VALIDATED_OFFLINE)
  - rejected=True → REJECTED regardless of checklist
  - is_dispatchable=False in every NCReviewRecord
  - production_released=False in every NCReviewRecord
  - machine_ready_to_run=False in every NCReviewRecord
  - Safety invariants cannot be overridden in NCReviewRecord
  - reviewed_at timestamp is set
  - missing_at_review list is populated correctly
"""

from __future__ import annotations

from backend.manufacturing.clearance_policy import ClearanceSource, evaluate_clearance
from backend.manufacturing.nc_candidate import build_offline_nc_candidate
from backend.manufacturing.nc_generation_adapter import generate_nc_from_candidate
from backend.manufacturing.nc_review import (
    NCReviewChecklist,
    NCReviewStatus,
    record_nc_engineer_review,
)
from backend.manufacturing.parameter_confirmation import confirm_cutting_parameters

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_nc_program():
    """Build a real NCProgram by running the full P6+P7-A pipeline."""
    confirmed_result = confirm_cutting_parameters(
        session_id="p7c-test",
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
        stock_top_z=0.0,
        feature_top_z=0.0,
        wcs_ref="DXF01_WCS",
    )
    candidate = build_offline_nc_candidate(
        sample_id="DXF-01",
        feature_id="feat-p7c",
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
    assert p7_result.generation_result.program is not None, "Setup: NCProgram must be generated"
    return p7_result.generation_result.program


def _full_checklist() -> NCReviewChecklist:
    return NCReviewChecklist(
        tool_numbers_verified=True,
        feeds_speeds_verified=True,
        depths_verified=True,
        wcs_offset_verified=True,
    )


def _partial_checklist() -> NCReviewChecklist:
    return NCReviewChecklist(
        tool_numbers_verified=True,
        feeds_speeds_verified=True,
        depths_verified=False,
        wcs_offset_verified=False,
    )


# ---------------------------------------------------------------------------
# NCReviewChecklist tests
# ---------------------------------------------------------------------------

class TestNCReviewChecklist:
    def test_all_checks_passed_when_all_true(self):
        cl = _full_checklist()
        assert cl.all_mandatory_checks_passed() is True

    def test_all_checks_failed_when_any_false(self):
        cl = _partial_checklist()
        assert cl.all_mandatory_checks_passed() is False

    def test_missing_checks_empty_when_all_true(self):
        cl = _full_checklist()
        assert cl.missing_checks() == []

    def test_missing_checks_lists_unchecked(self):
        cl = NCReviewChecklist(
            tool_numbers_verified=True,
            feeds_speeds_verified=False,
            depths_verified=False,
            wcs_offset_verified=True,
        )
        missing = cl.missing_checks()
        assert "feeds_speeds_verified" in missing
        assert "depths_verified" in missing
        assert "tool_numbers_verified" not in missing
        assert "wcs_offset_verified" not in missing

    def test_all_false_missing_has_four_items(self):
        cl = NCReviewChecklist()
        assert len(cl.missing_checks()) == 4

    def test_default_all_false(self):
        cl = NCReviewChecklist()
        assert cl.all_mandatory_checks_passed() is False


# ---------------------------------------------------------------------------
# record_nc_engineer_review status promotion tests
# ---------------------------------------------------------------------------

class TestNcReviewStatusPromotion:
    def test_validated_offline_when_all_checks_pass(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program,
            checklist=_full_checklist(),
            reviewer_notes="All checked. Tool=T1, RPM=5730, depth=25mm, WCS=G54.",
        )
        assert record.status == NCReviewStatus.VALIDATED_OFFLINE

    def test_engineer_reviewed_when_partial_checks(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program,
            checklist=_partial_checklist(),
            reviewer_notes="Depths not yet verified.",
        )
        assert record.status == NCReviewStatus.ENGINEER_REVIEWED

    def test_engineer_reviewed_when_no_checks(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program,
            checklist=NCReviewChecklist(),
            reviewer_notes="Initial review — no checks completed yet.",
        )
        assert record.status == NCReviewStatus.ENGINEER_REVIEWED

    def test_rejected_overrides_full_checklist(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program,
            checklist=_full_checklist(),
            reviewer_notes="Wrong tool number found.",
            rejected=True,
        )
        assert record.status == NCReviewStatus.REJECTED

    def test_rejected_overrides_partial_checklist(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program,
            checklist=_partial_checklist(),
            reviewer_notes="Feed rate out of range.",
            rejected=True,
        )
        assert record.status == NCReviewStatus.REJECTED


# ---------------------------------------------------------------------------
# NCReviewRecord safety invariant tests
# ---------------------------------------------------------------------------

class TestNCReviewRecordSafetyInvariants:
    def test_is_dispatchable_false_at_candidate(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=NCReviewChecklist(), reviewer_notes="")
        assert record.is_dispatchable is False

    def test_is_dispatchable_false_at_validated_offline(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        assert record.status == NCReviewStatus.VALIDATED_OFFLINE
        assert record.is_dispatchable is False

    def test_production_released_false_at_validated_offline(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        assert record.production_released is False

    def test_machine_ready_to_run_false_at_validated_offline(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        assert record.machine_ready_to_run is False

    def test_is_dispatchable_false_at_rejected(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=NCReviewChecklist(), reviewer_notes="Bad", rejected=True)
        assert record.is_dispatchable is False

    def test_production_released_false_at_rejected(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=NCReviewChecklist(), reviewer_notes="Bad", rejected=True)
        assert record.production_released is False

    def test_safety_invariants_cannot_be_overridden(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        record.is_dispatchable = True
        record.__post_init__()
        assert record.is_dispatchable is False

    def test_reviewed_at_is_set(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        assert record.reviewed_at != ""
        assert len(record.reviewed_at) > 10

    def test_nc_program_id_matches(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        assert record.nc_program_id == program.program_id

    def test_missing_at_review_empty_when_all_checked(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program, checklist=_full_checklist(), reviewer_notes="OK")
        assert record.missing_at_review == []

    def test_missing_at_review_lists_unchecked(self):
        program = _make_nc_program()
        record = record_nc_engineer_review(
            program,
            checklist=NCReviewChecklist(
                tool_numbers_verified=True,
                feeds_speeds_verified=False,
                depths_verified=True,
                wcs_offset_verified=False,
            ),
            reviewer_notes="Partial",
        )
        assert "feeds_speeds_verified" in record.missing_at_review
        assert "wcs_offset_verified" in record.missing_at_review
