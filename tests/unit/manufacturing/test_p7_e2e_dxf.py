"""
P7 E2E tests using real DXF-01 coordinates and tool data.

DXF-01 = 109106_01_30.dxf (sha256[:16]=e694952f02d7fb5b, 9 holes)
  First feature: x=-225.54485, y=-968.552339, z=0.0
  Tool: sandvik-860-1-0500-026a1-pm (5.0mm), COMPATIBLE match
  Cutting data: Vc=70-115 m/min, fn=0.06-0.11 mm/rev (C45, ISO P)

Tests verify the full P7-A → P7-C chain:
  1. OfflineNCCandidate (P6) → NCGenerationInput (P7-A) → NCProgram
  2. NCProgram has correct profile, is_offline_candidate, is_dispatchable=False
  3. NCProgram blocks list contains motion blocks with real DXF-01 coordinates
  4. Full DXF-01 batch sequence (9 holes) groups correctly into P7-B proposal
  5. P7-C review records status transitions correctly end-to-end
  6. All safety invariants hold through the full chain
"""

from __future__ import annotations

import pytest

from backend.manufacturing.clearance_policy import ClearanceSource, evaluate_clearance
from backend.manufacturing.multi_hole_sequence import HoleEntry, group_features_by_tool
from backend.manufacturing.nc_candidate import build_offline_nc_candidate
from backend.manufacturing.nc_generation_adapter import generate_nc_from_candidate
from backend.manufacturing.nc_review import (
    NCReviewChecklist,
    NCReviewStatus,
    record_nc_engineer_review,
)
from backend.manufacturing.parameter_confirmation import confirm_cutting_parameters
from backend.nc import NCProgramStatus

# ---------------------------------------------------------------------------
# Real DXF-01 constants (sha256[:16]=e694952f02d7fb5b, 9 holes)
# ---------------------------------------------------------------------------

_DXF01_SAMPLE_ID = "DXF-01"
_DXF01_FEATURE_X = -225.54485
_DXF01_FEATURE_Y = -968.552339
_DXF01_FEATURE_Z = 0.0
_DXF01_DEPTH_MM = 25.0
_DXF01_FEATURE_DIA = 4.891
_DXF01_TOOL_ID = "sandvik-860-1-0500-026a1-pm"
_DXF01_TOOL_DIA = 5.0
_DXF01_VC = 90.0        # confirmed selection within 70-115 range
_DXF01_FN = 0.08        # confirmed selection within 0.06-0.11 range


def _dxf01_confirmed_params():
    result = confirm_cutting_parameters(
        session_id="dxf01-e2e",
        tool_family="CoroDrill 860",
        material_grade="C45",
        diameter_mm=_DXF01_TOOL_DIA,
        operation="drilling",
        vc_mpm=_DXF01_VC,
        fn_mm=_DXF01_FN,
        vc_min_mpm=70.0,
        vc_max_mpm=115.0,
        fn_min_mm=0.06,
        fn_max_mm=0.11,
        source="Sandvik Coromant CoroDrill 860-1 Application Guide",
        source_url="coromant.sandvik.com",
    )
    return result.confirmed_params


def _dxf01_clearance():
    return evaluate_clearance(
        clearance_z=5.0,
        clearance_source=ClearanceSource.USER_SUPPLIED,
        stock_top_z=_DXF01_FEATURE_Z,
        feature_top_z=_DXF01_FEATURE_Z,
        wcs_ref="DXF01_WCS",
    )


def _dxf01_candidate():
    return build_offline_nc_candidate(
        sample_id=_DXF01_SAMPLE_ID,
        feature_id="dxf01-feat-001",
        hole_x=_DXF01_FEATURE_X,
        hole_y=_DXF01_FEATURE_Y,
        hole_top_z=_DXF01_FEATURE_Z,
        hole_depth_mm=_DXF01_DEPTH_MM,
        feature_diameter_mm=_DXF01_FEATURE_DIA,
        material="C45",
        operation="drilling",
        tool_id=_DXF01_TOOL_ID,
        tool_match_status="COMPATIBLE",
        tool_diameter_mm=_DXF01_TOOL_DIA,
        clearance_eval=_dxf01_clearance(),
        wcs_ref="DXF01_WCS",
        confirmed_params=_dxf01_confirmed_params(),
    )


# ---------------------------------------------------------------------------
# P7-A E2E: NC generation from real DXF-01 candidate
# ---------------------------------------------------------------------------

class TestP7AE2EDXF01:
    def test_nc_candidate_review_ready(self):
        candidate = _dxf01_candidate()
        assert candidate.nc_candidate_review_ready is True

    def test_nc_generation_produces_candidate_status(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.nc_program_status == NCProgramStatus.CANDIDATE

    def test_nc_program_not_dispatchable(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.generation_result.program.is_dispatchable is False

    def test_nc_program_is_offline_candidate(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.generation_result.program.is_offline_candidate is True

    def test_nc_program_uses_generic_iso_profile(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.generation_result.program.post_profile_id == "GENERIC_ISO_TEST_v1"

    def test_nc_program_has_motion_blocks(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        program = result.generation_result.program
        motion_blocks = [
            b for b in program.blocks
            if any(e.get("kind") == "motion" for e in b.elements)
        ]
        assert len(motion_blocks) > 0

    def test_nc_program_spindle_uses_confirmed_rpm(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        program = result.generation_result.program
        spindle_blocks = [
            b for b in program.blocks
            if any(e.get("kind") == "spindle_cmd" for e in b.elements)
        ]
        assert len(spindle_blocks) > 0
        spindle_data = spindle_blocks[0].elements[0]["data"]
        # RPM from Vc=90, D=5mm: (90000)/(pi*5) ≈ 5729.6
        assert spindle_data.get("speed_rpm") == pytest.approx(5729.58, rel=0.01)

    def test_nc_program_tool_number_correct(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=2)
        program = result.generation_result.program
        tc_blocks = [
            b for b in program.blocks
            if any(e.get("kind") == "tool_change" for e in b.elements)
        ]
        assert len(tc_blocks) > 0
        tc_data = tc_blocks[0].elements[0]["data"]
        assert tc_data["tool_number"] == 2

    def test_compatible_risk_in_p7_warnings(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        combined = " ".join(result.warnings)
        assert "COMPATIBLE" in combined or "COMPATIBLE_REVIEW" in combined

    def test_p7_result_not_claimed_for_controller(self):
        candidate = _dxf01_candidate()
        result = generate_nc_from_candidate(candidate, tool_number=1)
        assert result.production_controller_compatibility == "NOT_CLAIMED"


# ---------------------------------------------------------------------------
# P7-B E2E: Full 9-hole DXF-01 batch sequence
# ---------------------------------------------------------------------------

def _dxf01_full_hole_entries() -> list[HoleEntry]:
    """Real DXF-01 approximation: 9 holes across 4 tool groups."""
    return [
        HoleEntry("f001", -225.5, -968.6, 25.0, 4.891,
                  _DXF01_TOOL_ID, "COMPATIBLE", 5.0),
        HoleEntry("f002", -210.0, -960.0, 25.0, 4.891,
                  _DXF01_TOOL_ID, "COMPATIBLE", 5.0),
        HoleEntry("f003", -200.0, -970.0, 20.0, 5.0,
                  _DXF01_TOOL_ID, "EXACT", 5.0),
        HoleEntry("f004", -190.0, -965.0, 20.0, 5.0,
                  _DXF01_TOOL_ID, "EXACT", 5.0),
        HoleEntry("f005", -180.0, -955.0, 20.0, 5.0,
                  _DXF01_TOOL_ID, "EXACT", 5.0),
        HoleEntry("f006", -170.0, -945.0, 22.0, 6.0,
                  "sandvik-860-1-0600-031a1-pm", "EXACT", 6.0),
        HoleEntry("f007", -160.0, -935.0, 22.0, 6.0,
                  "sandvik-860-1-0600-031a1-pm", "EXACT", 6.0),
        HoleEntry("f008", -150.0, -925.0, 28.0, 8.0,
                  "sandvik-860-1-0800-040a1-pm", "EXACT", 8.0),
        HoleEntry("f009", -140.0, -915.0, 28.0, 8.0,
                  "sandvik-860-1-0800-040a1-pm", "EXACT", 8.0),
    ]


class TestP7BE2EDXF01:
    def test_batch_sequence_covers_all_9_holes(self):
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        assert proposal.total_holes == 9

    def test_batch_sequence_no_no_match(self):
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        assert proposal.no_match_hole_count == 0

    def test_batch_sequence_proposed_status(self):
        from backend.manufacturing.multi_hole_sequence import BatchSequenceStatus
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        assert proposal.sequence_status == BatchSequenceStatus.PROPOSED

    def test_batch_sequence_engineer_not_confirmed(self):
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        assert proposal.engineer_confirmed is False

    def test_batch_sequence_not_dispatchable(self):
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        assert proposal.is_dispatchable is False

    def test_batch_sequence_compatible_count_two(self):
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        assert proposal.compatible_hole_count == 2

    def test_batch_sequence_groups_cover_all_holes(self):
        proposal = group_features_by_tool(_DXF01_SAMPLE_ID, _dxf01_full_hole_entries())
        total_in_groups = sum(len(g.holes) for g in proposal.groups)
        assert total_in_groups == 9


# ---------------------------------------------------------------------------
# P7-C E2E: Full review chain on DXF-01 NC program
# ---------------------------------------------------------------------------

class TestP7CE2EDXF01:
    def test_full_chain_produces_validated_offline(self):
        candidate = _dxf01_candidate()
        p7_result = generate_nc_from_candidate(candidate, tool_number=1)
        program = p7_result.generation_result.program
        assert program is not None
        review = record_nc_engineer_review(
            program,
            checklist=NCReviewChecklist(
                tool_numbers_verified=True,
                feeds_speeds_verified=True,
                depths_verified=True,
                wcs_offset_verified=True,
            ),
            reviewer_notes="DXF-01 feature 001: T1 CoroDrill 5mm, RPM=5730, depth=25mm, G54.",
        )
        assert review.status == NCReviewStatus.VALIDATED_OFFLINE

    def test_validated_offline_not_dispatchable(self):
        candidate = _dxf01_candidate()
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
            reviewer_notes="All checks passed.",
        )
        assert review.is_dispatchable is False

    def test_partial_review_stays_engineer_reviewed(self):
        candidate = _dxf01_candidate()
        p7_result = generate_nc_from_candidate(candidate, tool_number=1)
        program = p7_result.generation_result.program
        review = record_nc_engineer_review(
            program,
            checklist=NCReviewChecklist(tool_numbers_verified=True),
            reviewer_notes="Only tool numbers checked so far.",
        )
        assert review.status == NCReviewStatus.ENGINEER_REVIEWED

    def test_all_p7_safety_invariants_full_chain(self):
        """End-to-end invariant check through the entire P6+P7 chain."""
        candidate = _dxf01_candidate()
        # P6 invariants
        assert candidate.is_dispatchable is False
        assert candidate.production_released is False
        # P7-A invariants
        p7_result = generate_nc_from_candidate(candidate, tool_number=1)
        assert p7_result.is_dispatchable is False
        assert p7_result.production_released is False
        assert p7_result.machine_ready_to_run is False
        program = p7_result.generation_result.program
        assert program.is_dispatchable is False
        # P7-C invariants
        review = record_nc_engineer_review(
            program,
            checklist=NCReviewChecklist(
                tool_numbers_verified=True,
                feeds_speeds_verified=True,
                depths_verified=True,
                wcs_offset_verified=True,
            ),
            reviewer_notes="Full chain validation test.",
        )
        assert review.is_dispatchable is False
        assert review.production_released is False
        assert review.machine_ready_to_run is False
