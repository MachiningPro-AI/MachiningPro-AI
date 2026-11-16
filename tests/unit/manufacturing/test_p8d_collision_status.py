"""P8-D Tests: Collision / clearance status (MUST 46)."""

from __future__ import annotations

from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    P8VerificationInput,
    nc_segments_to_verification_segments,
    run_p8_verification,
)
from backend.verification.enums import FixtureSource, FixtureType


def _seg(sx=0.0, sy=0.0, sz=5.0, ex=0.0, ey=0.0, ez=-10.0, is_cutting=True):
    return {
        "segment_id": "s1",
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "is_cutting": is_cutting,
        "motion_type": "FEED_LINEAR" if is_cutting else "RAPID_LINEAR",
        "operation_id": "op1",
    }


def _fix(x_offset=100.0):
    return FixtureInput(
        fixture_id="vise-01", fixture_type=FixtureType.VISE_JAWS,
        source=FixtureSource.USER_DEFINED,
        provenance=GeometryFieldProvenance.USER_CONFIRMED,
        min_x_mm=x_offset - 10, min_y_mm=-40.0, min_z_mm=-5.0,
        max_x_mm=x_offset + 10, max_y_mm=40.0, max_z_mm=0.0,
    )


def _make_vi(segs, fixtures=None, holder_diam=None):
    return P8VerificationInput(
        candidate_id="f001", feature_id="f001", toolpath_id="tp001",
        segments=segs,
        tool_diameter_mm=5.0,
        tool_diameter_provenance=GeometryFieldProvenance.USER_CONFIRMED,
        tool_flute_length_mm=None,
        tool_flute_length_provenance=GeometryFieldProvenance.UNKNOWN,
        tool_overall_length_mm=50.0,
        tool_overall_length_provenance=GeometryFieldProvenance.KNOWN,
        tool_cutting_length_mm=None,
        tool_cutting_length_provenance=GeometryFieldProvenance.UNKNOWN,
        holder_diameter_mm=holder_diam,
        holder_diameter_provenance=(
            GeometryFieldProvenance.USER_CONFIRMED if holder_diam
            else GeometryFieldProvenance.UNKNOWN
        ),
        holder_length_mm=50.0 if holder_diam else None,
        holder_length_provenance=(
            GeometryFieldProvenance.USER_CONFIRMED if holder_diam
            else GeometryFieldProvenance.UNKNOWN
        ),
        stock_model=None,
        stock_provenance=GeometryFieldProvenance.UNKNOWN,
        fixture_inputs=fixtures or [],
        machine_travel_x_mm=None,
        machine_travel_y_mm=None,
        machine_travel_z_mm=None,
        machine_travel_provenance=GeometryFieldProvenance.UNKNOWN,
        part_bbox_min=None, part_bbox_max=None,
        part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
        verification_scope="TEST",
    )


class TestCollisionStatus:
    def test_verifiable_pass_no_fixture_overlap(self):
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs, fixtures=[_fix(x_offset=200.0)])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "PASS"

    def test_verifiable_fail_fixture_overlaps_path(self):
        # Fixture centered on tool path (x=0)
        fix = FixtureInput(
            fixture_id="block", fixture_type=FixtureType.CLAMPS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=-3.0, min_y_mm=-3.0, min_z_mm=-15.0,
            max_x_mm=3.0, max_y_mm=3.0, max_z_mm=10.0,
        )
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs, fixtures=[fix])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "FAIL"

    def test_not_verifiable_due_to_absent_holder(self):
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs, fixtures=[_fix()], holder_diam=None)
        result = run_p8_verification(vi)
        assert result.holder_collision_validated == "NOT_VERIFIABLE"

    def test_not_verifiable_due_to_absent_fixture(self):
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs, fixtures=[])
        result = run_p8_verification(vi)
        assert result.fixture_collision_validated == "NOT_VERIFIABLE"
        assert result.tool_collision_validated == "NOT_VERIFIABLE"

    def test_not_verifiable_due_to_absent_3d_geometry(self):
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs)
        result = run_p8_verification(vi)
        assert result.gouge_validated == "NOT_VERIFIABLE"

    def test_collision_statuses_independent_of_each_other(self):
        # fixture present → tool_collision checkable, but holder still NOT_VERIFIABLE
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs, fixtures=[_fix(x_offset=200.0)], holder_diam=None)
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "PASS"
        assert result.holder_collision_validated == "NOT_VERIFIABLE"
        # These two are genuinely independent
        assert result.tool_collision_validated != result.holder_collision_validated

    def test_geometry_check_pass_not_equal_to_collision_validated(self):
        """GEOMETRY_CHECK_PASS != COLLISION_VALIDATED (MUST 21 / MUST 38)."""
        # machine envelope PASS ≠ collision validated
        segs = nc_segments_to_verification_segments([_seg()])
        vi = _make_vi(segs, fixtures=[])
        result = run_p8_verification(vi)
        # Collision stays NOT_VERIFIABLE; machine_envelope returns INSUFFICIENT without travel
        assert result.tool_collision_validated == "NOT_VERIFIABLE"
        assert result.fixture_collision_validated == "NOT_VERIFIABLE"
