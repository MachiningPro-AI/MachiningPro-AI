"""P6-B NC bridge adapter tests (MUST 47 — toolpath adapter)."""

from __future__ import annotations

import pytest

from backend.manufacturing.nc_bridge import segment_to_nc_input, toolpath_to_nc_segments
from backend.toolpath.enums import (
    ClearanceSource,
    CoordinateFrame,
    MotionType,
    SegmentGeometryType,
    ToolpathStatus,
)
from backend.toolpath.generators import DrillInput, generate_drill_toolpath
from backend.toolpath.models import ToolpathSegment


def _make_seg(
    motion: MotionType = MotionType.PLUNGE,
    start=(0.0, 0.0, 5.0),
    end=(0.0, 0.0, -20.0),
    tool_ref: str | None = "tool-001",
    setup_ref: str | None = "setup-1",
    feature_refs: list[str] | None = None,
) -> ToolpathSegment:
    return ToolpathSegment(
        segment_id="testseg",
        operation_ref="op-drill-01",
        motion_type=motion,
        geometry_type=SegmentGeometryType.LINE,
        frame=CoordinateFrame.WCS_COORDINATES,
        start_point=start,
        end_point=end,
        setup_ref=setup_ref,
        wcs_ref="W1",
        tool_ref=tool_ref,
        feature_refs=feature_refs or ["feat-1"],
        status=ToolpathStatus.GENERATED,
    )


class TestSegmentToNcInput:
    def test_plunge_becomes_feed_linear(self):
        seg = _make_seg(motion=MotionType.PLUNGE)
        out = segment_to_nc_input(seg)
        assert out["motion_type"] == "FEED_LINEAR"
        assert out["is_cutting"] is True

    def test_approach_becomes_rapid_linear(self):
        seg = _make_seg(motion=MotionType.APPROACH)
        out = segment_to_nc_input(seg)
        assert out["motion_type"] == "RAPID_LINEAR"
        assert out["is_cutting"] is False

    def test_retract_becomes_rapid_linear(self):
        seg = _make_seg(motion=MotionType.RETRACT)
        out = segment_to_nc_input(seg)
        assert out["motion_type"] == "RAPID_LINEAR"
        assert out["is_cutting"] is False

    def test_helix_becomes_helix(self):
        seg = _make_seg(motion=MotionType.HELIX)
        out = segment_to_nc_input(seg)
        assert out["motion_type"] == "HELIX"
        assert out["is_cutting"] is True

    def test_coordinates_preserved(self):
        seg = _make_seg(start=(1.0, 2.0, 5.0), end=(1.0, 2.0, -20.0))
        out = segment_to_nc_input(seg)
        assert out["start_x"] == pytest.approx(1.0)
        assert out["start_y"] == pytest.approx(2.0)
        assert out["start_z"] == pytest.approx(5.0)
        assert out["end_z"] == pytest.approx(-20.0)

    def test_tool_ref_preserved(self):
        seg = _make_seg(tool_ref="sandvik-860-5mm")
        out = segment_to_nc_input(seg)
        assert out["tool_id"] == "sandvik-860-5mm"

    def test_feature_ref_preserved(self):
        seg = _make_seg(feature_refs=["feat-xyz"])
        out = segment_to_nc_input(seg)
        assert out["feature_id"] == "feat-xyz"

    def test_no_tool_ref_omitted(self):
        seg = _make_seg(tool_ref=None)
        out = segment_to_nc_input(seg)
        assert "tool_id" not in out


class TestToolpathToNcSegments:
    def _make_drill_toolpath(self):
        inp = DrillInput(
            operation_ref="op-drill-01",
            hole_x=10.0,
            hole_y=20.0,
            hole_top_z=0.0,
            hole_depth_mm=25.0,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            wcs_ref="W1",
            tool_ref="tool-5mm",
            feature_refs=["feat-001"],
        )
        return generate_drill_toolpath(inp)

    def test_valid_drilling_produces_segments(self):
        tp = self._make_drill_toolpath()
        # Drill generator returns VERIFICATION_REQUIRED (offline safety intent)
        assert tp.status in (ToolpathStatus.GENERATED, ToolpathStatus.VERIFICATION_REQUIRED)
        segs = toolpath_to_nc_segments(tp)
        assert len(segs) == tp.metrics.segment_count

    def test_segment_motions_mapped(self):
        tp = self._make_drill_toolpath()
        segs = toolpath_to_nc_segments(tp)
        motion_types = {s["motion_type"] for s in segs}
        assert "RAPID_LINEAR" in motion_types  # approach + retract
        assert "FEED_LINEAR" in motion_types   # plunge

    def test_blocked_toolpath_produces_empty_segments(self):
        # Missing wcs_ref → BLOCKED
        inp = DrillInput(
            operation_ref="op-no-wcs",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=10.0,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_DEFINED,
            wcs_ref=None,  # BLOCKED
        )
        tp = generate_drill_toolpath(inp)
        assert tp.status == ToolpathStatus.BLOCKED
        segs = toolpath_to_nc_segments(tp)
        assert segs == []

    def test_missing_clearance_blocked(self):
        inp = DrillInput(
            operation_ref="op-no-clear",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=10.0,
            clearance_z=None,
            clearance_source=ClearanceSource.UNKNOWN,
            wcs_ref="W1",
        )
        tp = generate_drill_toolpath(inp)
        assert tp.status == ToolpathStatus.BLOCKED
