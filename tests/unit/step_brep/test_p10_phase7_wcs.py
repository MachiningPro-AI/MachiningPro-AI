"""
Tests for Phase 7A: WCS derivation and provenance (phase7_wcs_provider.py).

Covers MUST 25–27: canonical WCS model, SUGGESTED_WCS from bbox, validation.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.cam_planning.enums import WCSCandidateType
from backend.step_brep.phase7_wcs_provider import (
    WCS_SAFETY_IS_DISPATCHABLE,
    WCS_SAFETY_PRODUCTION_RELEASED,
    WCS_SAFETY_REVIEW_REQUIRED,
    WCSProvenance,
    WorkCoordinateSystem,
    suggest_wcs_top_center,
    validate_wcs,
    wcs_ref_string,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(bbox_min=(0.0, 0.0, 0.0), bbox_max=(100.0, 80.0, 30.0), sha="abcd1234ef567890"):
    rec = MagicMock()
    rec.bbox_min = bbox_min
    rec.bbox_max = bbox_max
    rec.sha256 = sha
    rec.source_path = "/fake/part.step"
    return rec


def _make_wcs(
    origin=(0.0, 0.0, 30.0),
    x_axis=(1.0, 0.0, 0.0),
    y_axis=(0.0, 1.0, 0.0),
    z_axis=(0.0, 0.0, 1.0),
    provenance=WCSProvenance.SUGGESTED,
    candidate_type=WCSCandidateType.TOP_CENTER,
):
    return WorkCoordinateSystem(
        wcs_id="test-wcs",
        origin_mm=origin,
        x_axis=x_axis,
        y_axis=y_axis,
        z_axis=z_axis,
        provenance=provenance,
        candidate_type=candidate_type,
        is_right_handed=True,
        is_orthogonal=True,
        is_valid=True,
        source_path="/fake/part.step",
        clearance_z_mm=40.0,
        notes="test WCS",
    )


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestWCSSafetyInvariants:
    def test_is_dispatchable_always_false(self):
        assert WCS_SAFETY_IS_DISPATCHABLE is False

    def test_production_released_always_false(self):
        assert WCS_SAFETY_PRODUCTION_RELEASED is False

    def test_review_required_always_true(self):
        assert WCS_SAFETY_REVIEW_REQUIRED is True


# ---------------------------------------------------------------------------
# WCSProvenance enum
# ---------------------------------------------------------------------------

class TestWCSProvenance:
    def test_has_file_evidence(self):
        assert WCSProvenance.FILE_EVIDENCE == "FILE_EVIDENCE"

    def test_has_setup_definition(self):
        assert WCSProvenance.SETUP_DEFINITION == "SETUP_DEFINITION"

    def test_has_user_confirmed(self):
        assert WCSProvenance.USER_CONFIRMED == "USER_CONFIRMED"

    def test_has_suggested(self):
        assert WCSProvenance.SUGGESTED == "SUGGESTED"

    def test_has_unknown(self):
        assert WCSProvenance.UNKNOWN == "UNKNOWN"

    def test_all_five_values(self):
        assert len(WCSProvenance) == 5


# ---------------------------------------------------------------------------
# suggest_wcs_top_center
# ---------------------------------------------------------------------------

class TestSuggestWCSTopCenter:
    def test_provenance_is_suggested(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.provenance == WCSProvenance.SUGGESTED

    def test_candidate_type_is_top_center(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.candidate_type == WCSCandidateType.TOP_CENTER

    def test_origin_at_top_face_center(self):
        rec = _make_record(bbox_min=(0, 0, 0), bbox_max=(100, 80, 30))
        wcs = suggest_wcs_top_center(rec)
        assert abs(wcs.origin_mm[0] - 50.0) < 1e-6
        assert abs(wcs.origin_mm[1] - 40.0) < 1e-6
        assert abs(wcs.origin_mm[2] - 30.0) < 1e-6

    def test_origin_z_matches_bbox_max_z(self):
        rec = _make_record(bbox_max=(40.0, 30.0, 15.0))
        wcs = suggest_wcs_top_center(rec)
        assert abs(wcs.origin_mm[2] - 15.0) < 1e-6

    def test_axes_are_world_aligned(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.x_axis == (1.0, 0.0, 0.0)
        assert wcs.y_axis == (0.0, 1.0, 0.0)
        assert wcs.z_axis == (0.0, 0.0, 1.0)

    def test_is_valid_true(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.is_valid is True

    def test_is_right_handed_true(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.is_right_handed is True

    def test_is_orthogonal_true(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.is_orthogonal is True

    def test_clearance_z_above_part(self):
        rec = _make_record(bbox_max=(100.0, 80.0, 30.0))
        wcs = suggest_wcs_top_center(rec)
        # clearance = bbox_max_z + 10
        assert wcs.clearance_z_mm is not None
        assert wcs.clearance_z_mm > 30.0

    def test_wcs_id_contains_sha_prefix(self):
        rec = _make_record(sha="deadbeef12345678")
        wcs = suggest_wcs_top_center(rec)
        assert "deadbeef" in wcs.wcs_id

    def test_notes_state_suggested_never_confirmed(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert "SUGGESTED" in wcs.notes
        assert "never" in wcs.notes.lower() or "not" in wcs.notes.lower()

    def test_non_zero_origin_part(self):
        # Asymmetric bbox
        rec = _make_record(bbox_min=(-40, -30, -15), bbox_max=(40, 30, 15))
        wcs = suggest_wcs_top_center(rec)
        assert abs(wcs.origin_mm[0]) < 1e-6
        assert abs(wcs.origin_mm[1]) < 1e-6
        assert abs(wcs.origin_mm[2] - 15.0) < 1e-6

    def test_provenance_is_never_user_confirmed(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.provenance != WCSProvenance.USER_CONFIRMED

    def test_provenance_is_never_file_evidence(self):
        wcs = suggest_wcs_top_center(_make_record())
        assert wcs.provenance != WCSProvenance.FILE_EVIDENCE


# ---------------------------------------------------------------------------
# validate_wcs
# ---------------------------------------------------------------------------

class TestValidateWCS:
    def test_valid_standard_wcs(self):
        wcs = _make_wcs()
        assert validate_wcs(wcs) is True

    def test_non_right_handed_fails(self):
        # Flip Y → left-handed
        wcs = _make_wcs(y_axis=(0.0, -1.0, 0.0))
        assert validate_wcs(wcs) is False

    def test_non_orthogonal_xy_fails(self):
        # X and Y share a component
        wcs = _make_wcs(x_axis=(1.0, 0.1, 0.0), y_axis=(0.0, 1.0, 0.0))
        assert validate_wcs(wcs) is False

    def test_zero_z_axis_fails(self):
        wcs = _make_wcs(z_axis=(0.0, 0.0, 0.0))
        assert validate_wcs(wcs) is False

    def test_nan_in_origin_fails(self):
        wcs = _make_wcs(origin=(float("nan"), 0.0, 30.0))
        assert validate_wcs(wcs) is False

    def test_inf_in_axis_fails(self):
        wcs = _make_wcs(x_axis=(float("inf"), 0.0, 0.0))
        assert validate_wcs(wcs) is False

    def test_swapped_x_and_z_fails_right_hand(self):
        # (0,0,1)×(0,1,0) = (-1,0,0) which dotted with (1,0,0) = -1 → not right-handed
        wcs = _make_wcs(x_axis=(0.0, 0.0, 1.0), z_axis=(1.0, 0.0, 0.0))
        assert validate_wcs(wcs) is False


# ---------------------------------------------------------------------------
# wcs_ref_string
# ---------------------------------------------------------------------------

class TestWCSRefString:
    def test_format_contains_provenance(self):
        wcs = _make_wcs(provenance=WCSProvenance.SUGGESTED)
        ref = wcs_ref_string(wcs)
        assert "SUGGESTED" in ref

    def test_format_contains_wcs_literal(self):
        wcs = _make_wcs()
        ref = wcs_ref_string(wcs)
        assert "WCS" in ref

    def test_format_contains_wcs_id(self):
        wcs = _make_wcs()
        ref = wcs_ref_string(wcs)
        assert wcs.wcs_id in ref

    def test_ref_is_string(self):
        wcs = _make_wcs()
        assert isinstance(wcs_ref_string(wcs), str)

    def test_user_confirmed_provenance_in_ref(self):
        wcs = _make_wcs(provenance=WCSProvenance.USER_CONFIRMED)
        ref = wcs_ref_string(wcs)
        assert "USER_CONFIRMED" in ref
