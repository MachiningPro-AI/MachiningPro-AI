"""
P8-B Tests: Tool reach validation.

MUST 43: known sufficient cutting length, insufficient cutting length,
         unknown flute length, known overall length, unknown stickout,
         depth > tool capability.
"""

from __future__ import annotations

from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    P8VerificationInput,
    nc_segments_to_verification_segments,
    run_p8_verification,
)


def _make_seg(sz, ez, is_cutting=True):
    return {
        "segment_id": "s1",
        "start_x": 0.0, "start_y": 0.0, "start_z": sz,
        "end_x": 0.0, "end_y": 0.0, "end_z": ez,
        "is_cutting": is_cutting,
        "motion_type": "FEED_LINEAR" if is_cutting else "RAPID_LINEAR",
        "operation_id": "op1",
    }


def _make_vi(segs, flute_len=None, overall_len=None, cut_len=None):
    return P8VerificationInput(
        candidate_id="f001",
        feature_id="f001",
        toolpath_id="tp001",
        segments=segs,
        tool_diameter_mm=5.0,
        tool_diameter_provenance=GeometryFieldProvenance.USER_CONFIRMED,
        tool_flute_length_mm=flute_len,
        tool_flute_length_provenance=(
            GeometryFieldProvenance.KNOWN if flute_len is not None
            else GeometryFieldProvenance.UNKNOWN
        ),
        tool_overall_length_mm=overall_len,
        tool_overall_length_provenance=(
            GeometryFieldProvenance.KNOWN if overall_len is not None
            else GeometryFieldProvenance.UNKNOWN
        ),
        tool_cutting_length_mm=cut_len,
        tool_cutting_length_provenance=(
            GeometryFieldProvenance.KNOWN if cut_len is not None
            else GeometryFieldProvenance.UNKNOWN
        ),
        holder_diameter_mm=None,
        holder_diameter_provenance=GeometryFieldProvenance.UNKNOWN,
        holder_length_mm=None,
        holder_length_provenance=GeometryFieldProvenance.UNKNOWN,
        stock_model=None,
        stock_provenance=GeometryFieldProvenance.UNKNOWN,
        fixture_inputs=[],
        machine_travel_x_mm=None,
        machine_travel_y_mm=None,
        machine_travel_z_mm=None,
        machine_travel_provenance=GeometryFieldProvenance.UNKNOWN,
        part_bbox_min=None,
        part_bbox_max=None,
        part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
        verification_scope="CLEARANCE_CHECK_2_5D",
    )


class TestToolReach:
    def test_known_sufficient_flute_length(self):
        # depth = 15mm (sz=5, ez=-10); flute = 30mm → PASS
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -10.0)])
        vi = _make_vi(segs, flute_len=30.0, overall_len=74.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "PASS"

    def test_insufficient_flute_exceeds_depth(self):
        # depth = 50mm (sz=5, ez=-45); flute = 20mm → FAIL
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -45.0)])
        vi = _make_vi(segs, flute_len=20.0, overall_len=74.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "FAIL"

    def test_unknown_flute_returns_insufficient_data(self):
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -10.0)])
        vi = _make_vi(segs, flute_len=None, overall_len=74.0, cut_len=26.0)
        result = run_p8_verification(vi)
        # flute unknown → INSUFFICIENT_DATA (not PASS, not NOT_VERIFIABLE)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"

    def test_overall_length_known_does_not_substitute_for_flute(self):
        # overall_length alone does not unlock tool_reach check
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -10.0)])
        vi = _make_vi(segs, flute_len=None, overall_len=74.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"

    def test_exact_boundary_depth_equals_flute(self):
        # depth = 20mm; flute = 20mm; with tolerance this should PASS (tolerance is 0.01)
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -15.0)])
        vi = _make_vi(segs, flute_len=20.0, overall_len=74.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "PASS"

    def test_no_cutting_segments_always_pass_reach(self):
        # Only rapid segments — no depth to check
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -10.0, is_cutting=False)])
        vi = _make_vi(segs, flute_len=5.0, overall_len=74.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "PASS"

    def test_no_flute_no_overall_fully_unknown(self):
        segs = nc_segments_to_verification_segments([_make_seg(5.0, -10.0)])
        vi = _make_vi(segs, flute_len=None, overall_len=None, cut_len=None)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"

    def test_p8b_audit_18_drills_flute_length_p9a(self):
        """P9-A update: 9/18 drills now have flute_length_mm (all Sandvik 860-1)."""
        from backend.cutting_tools.seed_catalog import get_catalog
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        drills_with_flute = [d for d in drills if d.flute_length_mm is not None]
        sandvik_860_with_flute = [
            d for d in drills_with_flute if d.stable_id.startswith("sandvik-860-1-")
        ]
        # P9-A: all 9 Sandvik 860-1 drills now have flute_length_mm populated
        assert len(sandvik_860_with_flute) == 9, (
            f"Expected 9 Sandvik 860-1 drills with flute_length_mm, "
            f"got {len(sandvik_860_with_flute)}"
        )

    def test_p8b_audit_cutting_length_partial(self):
        """Confirm cutting_length_mm is partial — not a substitute for flute_length."""
        from backend.cutting_tools.seed_catalog import get_catalog
        drills = [t for t in get_catalog() if t.tool_category_code == "DRILL"]
        drills_with_cut = [d for d in drills if d.cutting_length_mm is not None]
        # Should be partial (between 0 and all 18)
        assert 0 < len(drills_with_cut) < len(drills), (
            "Expected partial cutting_length_mm coverage"
        )

    def test_p8b_sandvik_860_has_cutting_length(self):
        """Sandvik 860-1 primary drills have cutting_length from P7."""
        from backend.cutting_tools.seed_catalog import get_catalog
        sandvik_860 = [
            t for t in get_catalog()
            if t.stable_id.startswith("sandvik-860-1") and t.cutting_length_mm is not None
        ]
        assert len(sandvik_860) >= 7, (
            "Expected at least 7 Sandvik 860-1 drills with cutting_length_mm"
        )
