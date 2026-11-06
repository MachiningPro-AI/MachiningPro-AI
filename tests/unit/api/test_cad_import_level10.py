"""Level-10 Toolpath Generation Foundation — comprehensive test suite.

Covers:
- Geometry primitives (Point3D, Vector3D, Line/Arc/Helix/PolylineSegment)
- offset_polyline_2d, compute_z_levels, ramp_path
- VerificationContract invariants
- ClearancePlane, StepParameters
- PathMetrics and ToolpathCollection totals
- All 8 generators (drill, peck, profile, face_mill, pocket, slot, chamfer, turning)
- BLOCKED paths (missing clearance, WCS, tool diameter, stepdown/stepover, peck depth)
- ADAPTIVE_CANDIDATE → PARTIAL pocket
- Constraint validators (tool reach, machine envelope, radius offset)
- cycle_time bridge: EXACT vs APPROXIMATE path type, cycle_time_ready
- NO_FABRICATED_DATA audit
- Level-9 regression
- API endpoint tests (drill, profile, face-mill, pocket, slot, chamfer, turning)

SAFETY INVARIANTS CHECKED
--------------------------
NO_GCODE=YES             — no gcode field anywhere in responses
NO_FABRICATED_DATA=YES   — blocked generators must not invent coordinates
SIMULATION_REQUIRED=YES  — every Toolpath.simulation_required == True
VERIFIED_IS_FALSE=YES    — every Toolpath.is_verified == False
COLLISION_CHECK=NOT_PERFORMED  on every generated toolpath
"""

from __future__ import annotations

import math
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.toolpath.enums import (
    ClearanceSource,
    CompensationSide,
    MachineEnvelopeStatus,
    MotionType,
    PocketStrategy,
    ProfileSide,
    SegmentGeometryType,
    ToolpathFidelity,
    ToolpathStatus,
    ToolReachStatus,
    TurningMotionType,
    VerificationStatus,
)
from backend.toolpath.geometry import (
    ArcSegment,
    HelixSegment,
    LineSegment,
    Point3D,
    PolylineSegment,
    Vector3D,
    compute_z_levels,
    offset_polyline_2d,
    ramp_path,
)
from backend.toolpath.models import (
    ClearancePlane,
    PathMetrics,
    RemainingStock,
    StepParameters,
    Toolpath,
    ToolpathCollection,
    ToolpathSegment,
    VerificationContract,
    VisualizationData,
)
from backend.toolpath.generators import (
    ChamferInput,
    DrillInput,
    FaceMillInput,
    PeckDrillInput,
    PocketInput,
    ProfileInput,
    SlotInput,
    TurningInput,
    generate_chamfer_toolpath,
    generate_drill_toolpath,
    generate_face_mill_toolpath,
    generate_peck_drill_toolpath,
    generate_pocket_toolpath,
    generate_profile_toolpath,
    generate_slot_toolpath,
    generate_turning_toolpath,
)
from backend.toolpath.constraints import (
    MachineEnvelopeResult,
    ToolReachResult,
    check_machine_envelope,
    check_tool_reach,
    validate_tool_radius_offset,
)
from backend.toolpath.cycle_time import (
    PathLengthType,
    ToolpathCycleTimeInput,
    bridge_to_cycle_time,
    extract_cycle_time_input,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    import os
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "test")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "test")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret")
    return TestClient(app)


@pytest.fixture
def auth_headers(client: TestClient) -> dict:
    r = client.post("/api/login", json={"username": "test", "password": "test"})
    if r.status_code != 200:
        pytest.skip("Cannot authenticate")
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _auth(client: TestClient) -> dict:
    import os
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "test")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "test")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret")
    r = client.post("/api/login", json={"username": "test", "password": "test"})
    if r.status_code != 200:
        pytest.skip("Cannot authenticate")
    return {"Authorization": f"Bearer {r.json()['token']}"}


def _drill_params() -> dict:
    return dict(
        operation_ref="OP-DRILL-01",
        hole_x=25.0,
        hole_y=15.0,
        hole_top_z=0.0,
        hole_depth_mm=20.0,
        clearance_z=5.0,
        clearance_source="USER_SUPPLIED",
        wcs_ref="WCS-MAIN",
        setup_ref="SETUP-1",
        tool_ref="TOOL-HSS-10",
        feature_refs=["FEAT-HOLE-01"],
    )


# ---------------------------------------------------------------------------
# TestGeometryPrimitives
# ---------------------------------------------------------------------------

class TestGeometryPrimitives:
    def test_point3d_distance(self):
        a = Point3D(0, 0, 0)
        b = Point3D(3, 4, 0)
        assert abs(a.distance_to(b) - 5.0) < 1e-9

    def test_point3d_add_sub(self):
        a = Point3D(1, 2, 3)
        b = Point3D(4, 5, 6)
        assert a + b == Point3D(5, 7, 9)
        assert b - a == Point3D(3, 3, 3)

    def test_vector3d_magnitude(self):
        v = Vector3D(3, 4, 0)
        assert abs(v.magnitude - 5.0) < 1e-9

    def test_vector3d_normalize(self):
        v = Vector3D(0, 0, 10)
        n = v.normalize()
        assert abs(n.k - 1.0) < 1e-9
        assert abs(n.i) < 1e-9

    def test_vector3d_normalize_zero(self):
        v = Vector3D(0, 0, 0)
        n = v.normalize()
        assert n == Vector3D(0, 0, 0)

    def test_line_segment_length(self):
        from backend.toolpath.enums import CoordinateFrame
        seg = LineSegment(
            Point3D(0, 0, 0), Point3D(3, 4, 0), CoordinateFrame.WCS_COORDINATES
        )
        assert abs(seg.length - 5.0) < 1e-9

    def test_arc_segment_quarter_circle(self):
        from backend.toolpath.enums import CoordinateFrame
        arc = ArcSegment(
            start=Point3D(1, 0, 0),
            end=Point3D(0, 1, 0),
            center=Point3D(0, 0, 0),
            frame=CoordinateFrame.WCS_COORDINATES,
            clockwise=False,
        )
        expected = math.pi / 2.0 * 1.0  # radius=1, 90°
        assert abs(arc.length - expected) < 1e-6
        assert abs(arc.radius - 1.0) < 1e-9

    def test_helix_segment_length(self):
        from backend.toolpath.enums import CoordinateFrame
        helix = HelixSegment(
            center_xy=(0.0, 0.0),
            radius=5.0,
            start_z=0.0,
            end_z=-5.0,
            pitch=5.0,
            frame=CoordinateFrame.WCS_COORDINATES,
        )
        assert helix.axial_depth == 5.0
        # 1 turn → sqrt((1 * 2pi*5)^2 + 5^2)
        expected = math.sqrt((2 * math.pi * 5.0) ** 2 + 25.0)
        assert abs(helix.length - expected) < 1e-3

    def test_polyline_open_length(self):
        from backend.toolpath.enums import CoordinateFrame
        pts = (Point3D(0, 0, 0), Point3D(3, 0, 0), Point3D(3, 4, 0))
        poly = PolylineSegment(pts, CoordinateFrame.WCS_COORDINATES, closed=False)
        assert abs(poly.length - 7.0) < 1e-9

    def test_polyline_closed_length(self):
        from backend.toolpath.enums import CoordinateFrame
        pts = (Point3D(0, 0, 0), Point3D(10, 0, 0), Point3D(10, 10, 0), Point3D(0, 10, 0))
        poly = PolylineSegment(pts, CoordinateFrame.WCS_COORDINATES, closed=True)
        assert abs(poly.length - 40.0) < 1e-9

    def test_polyline_bounding_box(self):
        from backend.toolpath.enums import CoordinateFrame
        pts = (Point3D(-5, 2, 0), Point3D(10, -3, 5))
        poly = PolylineSegment(pts, CoordinateFrame.WCS_COORDINATES)
        bmin, bmax = poly.bounding_box
        assert bmin.x == -5
        assert bmax.x == 10


class TestGeometryHelpers:
    def test_offset_polyline_left(self):
        pts = [Point3D(0, 0, 0), Point3D(10, 0, 0)]
        result = offset_polyline_2d(pts, 2.0, "LEFT")
        assert len(result) == 2
        assert abs(result[0].y - 2.0) < 1e-9

    def test_offset_polyline_right(self):
        pts = [Point3D(0, 0, 0), Point3D(10, 0, 0)]
        result = offset_polyline_2d(pts, 2.0, "RIGHT")
        assert len(result) == 2
        assert abs(result[0].y - (-2.0)) < 1e-9

    def test_offset_polyline_too_few_points(self):
        result = offset_polyline_2d([Point3D(0, 0, 0)], 1.0)
        assert result == []

    def test_compute_z_levels_basic(self):
        levels = compute_z_levels(0.0, -10.0, 2.5)
        assert levels[0] < 0.0
        assert levels[-1] == -10.0
        assert len(levels) == 4

    def test_compute_z_levels_requires_positive_stepdown(self):
        with pytest.raises(ValueError):
            compute_z_levels(0.0, -5.0, 0)

    def test_ramp_path(self):
        from backend.toolpath.enums import CoordinateFrame
        seg = ramp_path(
            Point3D(0, 0, 0), (5.0, 0.0), start_z=0.0, end_z=-3.0,
            frame=CoordinateFrame.WCS_COORDINATES,
        )
        assert seg.start.z == 0.0
        assert seg.end.z == -3.0
        assert seg.end.x == 5.0


# ---------------------------------------------------------------------------
# TestVerificationContract
# ---------------------------------------------------------------------------

class TestVerificationContract:
    def test_all_checks_not_performed(self):
        vc = VerificationContract()
        assert vc.collision_check == VerificationStatus.NOT_PERFORMED
        assert vc.gouge_check == VerificationStatus.NOT_PERFORMED
        assert vc.fixture_check == VerificationStatus.NOT_PERFORMED
        assert vc.machine_collision_check == VerificationStatus.NOT_PERFORMED

    def test_note_present(self):
        vc = VerificationContract()
        assert "NOT_PERFORMED" in vc.note
        assert len(vc.note) > 10


class TestClearancePlaneAndStepParameters:
    def test_clearance_known_when_value_and_source(self):
        cp = ClearancePlane(value_mm=5.0, source=ClearanceSource.USER_SUPPLIED)
        assert cp.is_known is True

    def test_clearance_unknown_when_no_value(self):
        cp = ClearancePlane(value_mm=None, source=ClearanceSource.USER_SUPPLIED)
        assert cp.is_known is False

    def test_clearance_unknown_when_unknown_source(self):
        cp = ClearancePlane(value_mm=5.0, source=ClearanceSource.UNKNOWN)
        assert cp.is_known is False

    def test_step_parameters_known(self):
        sp = StepParameters(stepdown_mm=1.5, stepover_mm=3.0)
        assert sp.stepdown_known is True
        assert sp.stepover_known is True

    def test_step_parameters_unknown_when_none(self):
        sp = StepParameters()
        assert sp.stepdown_known is False
        assert sp.stepover_known is False

    def test_step_parameters_unknown_when_zero(self):
        sp = StepParameters(stepdown_mm=0.0)
        assert sp.stepdown_known is False


# ---------------------------------------------------------------------------
# TestToolpathInvariants
# ---------------------------------------------------------------------------

class TestToolpathInvariants:
    def test_is_verified_always_false(self):
        tp = Toolpath(toolpath_id="T001", operation_ref="OP-01")
        assert tp.is_verified is False

    def test_simulation_required_always_true(self):
        tp = Toolpath(toolpath_id="T002", operation_ref="OP-01")
        assert tp.simulation_required is True

    def test_toolpath_collection_simulation_required(self):
        tc = ToolpathCollection(collection_id="COL-01")
        assert tc.simulation_required is True

    def test_remaining_stock_placeholder(self):
        rs = RemainingStock()
        assert rs.remaining_stock_known is False
        assert "Level 11+" in rs.notes


class TestToolpathCollectionTotals:
    def test_recompute_totals(self):
        from backend.toolpath.enums import CoordinateFrame
        tp1 = Toolpath(
            toolpath_id="T1", operation_ref="OP-1",
            metrics=PathMetrics(cut_length_mm=10.0, link_or_rapid_length_mm=2.0,
                                total_length_mm=12.0),
        )
        tp2 = Toolpath(
            toolpath_id="T2", operation_ref="OP-2",
            metrics=PathMetrics(cut_length_mm=5.0, link_or_rapid_length_mm=1.0,
                                total_length_mm=6.0),
        )
        col = ToolpathCollection(collection_id="COL-1", toolpaths=[tp1, tp2])
        col.recompute_totals()
        assert abs(col.total_cut_length_mm - 15.0) < 1e-9
        assert abs(col.total_link_length_mm - 3.0) < 1e-9
        assert abs(col.total_path_length_mm - 18.0) < 1e-9


# ---------------------------------------------------------------------------
# TestDrillGenerator
# ---------------------------------------------------------------------------

class TestDrillGenerator:
    def _inp(self, **kw) -> DrillInput:
        base = dict(
            operation_ref="OP-DRILL",
            hole_x=0.0, hole_y=0.0, hole_top_z=0.0, hole_depth_mm=10.0,
            clearance_z=5.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1", setup_ref="S1", tool_ref="T1",
        )
        base.update(kw)
        return DrillInput(**base)

    def test_drill_generates_three_segments(self):
        tp = generate_drill_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert len(tp.segments) == 3

    def test_drill_segment_motions(self):
        tp = generate_drill_toolpath(self._inp())
        motions = [s.motion_type for s in tp.segments]
        assert MotionType.APPROACH in motions
        assert MotionType.PLUNGE in motions
        assert MotionType.RETRACT in motions

    def test_drill_metrics_computed(self):
        tp = generate_drill_toolpath(self._inp())
        assert tp.metrics.cut_length_mm > 0
        assert tp.metrics.total_length_mm > 0
        assert tp.metrics.segment_count == 3

    def test_drill_blocked_no_clearance(self):
        tp = generate_drill_toolpath(self._inp(clearance_z=None))
        assert tp.status == ToolpathStatus.BLOCKED
        assert tp.fidelity == ToolpathFidelity.BLOCKED
        assert len(tp.segments) == 0

    def test_drill_blocked_unknown_clearance_source(self):
        tp = generate_drill_toolpath(self._inp(clearance_source=ClearanceSource.UNKNOWN))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_drill_blocked_no_wcs(self):
        tp = generate_drill_toolpath(self._inp(wcs_ref=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_drill_verification_contract(self):
        tp = generate_drill_toolpath(self._inp())
        assert tp.verification.collision_check == VerificationStatus.NOT_PERFORMED
        assert tp.verification.gouge_check == VerificationStatus.NOT_PERFORMED

    def test_drill_no_gcode_in_output(self):
        tp = generate_drill_toolpath(self._inp())
        dump = tp.model_dump()
        assert "gcode" not in dump
        assert "nc_code" not in dump

    def test_drill_provenance_in_segments(self):
        tp = generate_drill_toolpath(self._inp())
        for seg in tp.segments:
            assert seg.wcs_ref == "WCS-1"
            assert seg.operation_ref == "OP-DRILL"


class TestPeckDrillGenerator:
    def _inp(self, **kw) -> PeckDrillInput:
        base = dict(
            operation_ref="OP-PECK",
            hole_x=0.0, hole_y=0.0, hole_top_z=0.0, hole_depth_mm=12.0,
            clearance_z=5.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1", peck_depth_mm=3.0,
        )
        base.update(kw)
        return PeckDrillInput(**base)

    def test_peck_drill_generates_multiple_pecks(self):
        tp = generate_peck_drill_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert len(tp.segments) > 3

    def test_peck_drill_blocked_no_peck_depth(self):
        tp = generate_peck_drill_toolpath(self._inp(peck_depth_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED
        assert any("peck_depth" in m for m in tp.missing_inputs)

    def test_peck_drill_blocked_zero_peck_depth(self):
        tp = generate_peck_drill_toolpath(self._inp(peck_depth_mm=0.0))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_peck_drill_metrics_gt_simple_drill(self):
        from backend.toolpath.generators import generate_drill_toolpath
        simple = generate_drill_toolpath(DrillInput(
            operation_ref="OP-DRILL", hole_x=0, hole_y=0, hole_top_z=0, hole_depth_mm=12,
            clearance_z=5, clearance_source=ClearanceSource.USER_SUPPLIED, wcs_ref="WCS",
        ))
        peck = generate_peck_drill_toolpath(self._inp())
        assert peck.metrics.retract_count >= simple.metrics.retract_count


# ---------------------------------------------------------------------------
# TestProfileGenerator
# ---------------------------------------------------------------------------

class TestProfileGenerator:
    def _inp(self, **kw) -> ProfileInput:
        base = dict(
            operation_ref="OP-PROFILE",
            contour_points=[(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)],
            contour_z=-5.0,
            tool_diameter_mm=10.0,
            profile_side=ProfileSide.OUTSIDE,
            compensation_side=CompensationSide.CENTERLINE,
            clearance_z=5.0,
            clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1",
        )
        base.update(kw)
        return ProfileInput(**base)

    def test_profile_generates_three_segments(self):
        tp = generate_profile_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert len(tp.segments) == 3

    def test_profile_blocked_no_wcs(self):
        tp = generate_profile_toolpath(self._inp(wcs_ref=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_profile_blocked_no_clearance(self):
        tp = generate_profile_toolpath(self._inp(clearance_z=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_profile_blocked_unknown_side(self):
        tp = generate_profile_toolpath(self._inp(profile_side=ProfileSide.UNKNOWN))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_profile_blocked_no_tool_diameter_for_offset(self):
        inp = self._inp(tool_diameter_mm=None, compensation_side=CompensationSide.LEFT_OFFSET)
        tp = generate_profile_toolpath(inp)
        assert tp.status == ToolpathStatus.BLOCKED

    def test_profile_contour_in_cut_segment(self):
        tp = generate_profile_toolpath(self._inp())
        cut_segs = [s for s in tp.segments if s.motion_type == MotionType.CUT]
        assert len(cut_segs) == 1
        assert len(cut_segs[0].polyline_points) >= 2


# ---------------------------------------------------------------------------
# TestFaceMillGenerator
# ---------------------------------------------------------------------------

class TestFaceMillGenerator:
    def _inp(self, **kw) -> FaceMillInput:
        base = dict(
            operation_ref="OP-FACE",
            region_x_min=0.0, region_x_max=50.0,
            region_y_min=0.0, region_y_max=30.0,
            face_z=0.0, tool_diameter_mm=25.0, stepover_mm=12.5,
            clearance_z=5.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1",
        )
        base.update(kw)
        return FaceMillInput(**base)

    def test_face_mill_generates_segments(self):
        tp = generate_face_mill_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert tp.metrics.segment_count > 2

    def test_face_mill_blocked_no_stepover(self):
        tp = generate_face_mill_toolpath(self._inp(stepover_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED
        assert any("stepover" in m for m in tp.missing_inputs)

    def test_face_mill_blocked_no_tool_diameter(self):
        tp = generate_face_mill_toolpath(self._inp(tool_diameter_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_face_mill_blocked_no_wcs(self):
        tp = generate_face_mill_toolpath(self._inp(wcs_ref=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_face_mill_cut_length_positive(self):
        tp = generate_face_mill_toolpath(self._inp())
        assert tp.metrics.cut_length_mm > 0


# ---------------------------------------------------------------------------
# TestPocketGenerator
# ---------------------------------------------------------------------------

class TestPocketGenerator:
    def _inp(self, **kw) -> PocketInput:
        base = dict(
            operation_ref="OP-POCKET",
            boundary_points=[(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (0.0, 20.0)],
            pocket_top_z=0.0, pocket_bottom_z=-10.0,
            tool_diameter_mm=8.0, stepdown_mm=2.5, stepover_mm=4.0,
            strategy=PocketStrategy.OFFSET,
            clearance_z=5.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1",
        )
        base.update(kw)
        return PocketInput(**base)

    def test_pocket_generates_segments(self):
        tp = generate_pocket_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert tp.metrics.depth_level_count >= 1

    def test_pocket_blocked_no_stepdown(self):
        tp = generate_pocket_toolpath(self._inp(stepdown_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED
        assert any("stepdown" in m for m in tp.missing_inputs)

    def test_pocket_blocked_no_stepover(self):
        tp = generate_pocket_toolpath(self._inp(stepover_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_pocket_blocked_no_wcs(self):
        tp = generate_pocket_toolpath(self._inp(wcs_ref=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_pocket_adaptive_candidate_returns_partial(self):
        tp = generate_pocket_toolpath(self._inp(strategy=PocketStrategy.ADAPTIVE_CANDIDATE))
        assert tp.status == ToolpathStatus.PARTIAL
        assert tp.fidelity == ToolpathFidelity.PARTIAL
        assert any("ADAPTIVE" in w for w in tp.warnings)

    def test_pocket_depth_levels_match_stepdown(self):
        tp = generate_pocket_toolpath(self._inp())
        expected_levels = len(compute_z_levels(0.0, -10.0, 2.5))
        assert tp.metrics.depth_level_count == expected_levels


# ---------------------------------------------------------------------------
# TestSlotGenerator
# ---------------------------------------------------------------------------

class TestSlotGenerator:
    def _inp(self, **kw) -> SlotInput:
        base = dict(
            operation_ref="OP-SLOT",
            slot_start=(0.0, 0.0), slot_end=(40.0, 0.0),
            slot_z=0.0, slot_width_mm=12.0, slot_depth_mm=5.0,
            tool_diameter_mm=10.0,
            clearance_z=5.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1",
        )
        base.update(kw)
        return SlotInput(**base)

    def test_slot_generates_four_segments(self):
        tp = generate_slot_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert len(tp.segments) == 4

    def test_slot_blocked_tool_too_large(self):
        tp = generate_slot_toolpath(self._inp(tool_diameter_mm=15.0))
        assert tp.status == ToolpathStatus.BLOCKED
        assert any("TOOL_TOO_LARGE" in w for w in tp.warnings)

    def test_slot_blocked_no_wcs(self):
        tp = generate_slot_toolpath(self._inp(wcs_ref=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_slot_blocked_no_slot_width(self):
        tp = generate_slot_toolpath(self._inp(slot_width_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED


# ---------------------------------------------------------------------------
# TestChamferGenerator
# ---------------------------------------------------------------------------

class TestChamferGenerator:
    def _inp(self, **kw) -> ChamferInput:
        base = dict(
            operation_ref="OP-CHAMFER",
            contour_points=[(0.0, 0.0), (20.0, 0.0), (20.0, 20.0), (0.0, 20.0)],
            contour_z=0.0, tool_diameter_mm=16.0, tool_angle_deg=45.0,
            chamfer_depth_mm=1.0,
            clearance_z=5.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-1",
        )
        base.update(kw)
        return ChamferInput(**base)

    def test_chamfer_generates_three_segments(self):
        tp = generate_chamfer_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert len(tp.segments) == 3

    def test_chamfer_blocked_no_tool_angle(self):
        tp = generate_chamfer_toolpath(self._inp(tool_angle_deg=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_chamfer_blocked_no_chamfer_depth(self):
        tp = generate_chamfer_toolpath(self._inp(chamfer_depth_mm=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_chamfer_cut_at_contact_z(self):
        tp = generate_chamfer_toolpath(self._inp())
        cut_segs = [s for s in tp.segments if s.motion_type == MotionType.CUT]
        assert len(cut_segs) == 1
        # contact_z = contour_z - chamfer_depth = 0.0 - 1.0 = -1.0
        assert cut_segs[0].start_point is not None
        assert abs(cut_segs[0].start_point[2] - (-1.0)) < 1e-9


# ---------------------------------------------------------------------------
# TestTurningGenerator
# ---------------------------------------------------------------------------

class TestTurningGenerator:
    def _inp(self, **kw) -> TurningInput:
        base = dict(
            operation_ref="OP-TURN",
            turning_motion_type=TurningMotionType.AXIAL_CUT,
            start_z=0.0, end_z=-50.0, start_x=20.0, end_x=20.0,
            clearance_x=25.0, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS-LATHE",
        )
        base.update(kw)
        return TurningInput(**base)

    def test_turning_generates_three_segments(self):
        tp = generate_turning_toolpath(self._inp())
        assert tp.status == ToolpathStatus.VERIFICATION_REQUIRED
        assert len(tp.segments) == 3

    def test_turning_xz_semantics_y_zero(self):
        tp = generate_turning_toolpath(self._inp())
        for seg in tp.segments:
            if seg.start_point:
                assert seg.start_point[1] == 0.0, "lathe XZ: y must be 0"
            if seg.end_point:
                assert seg.end_point[1] == 0.0

    def test_turning_warns_xz_semantics(self):
        tp = generate_turning_toolpath(self._inp())
        all_warnings = tp.warnings + [w for s in tp.segments for w in s.warnings]
        assert any("TURNING_XZ_SEMANTICS" in w for w in all_warnings)

    def test_turning_blocked_no_wcs(self):
        tp = generate_turning_toolpath(self._inp(wcs_ref=None))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_turning_blocked_no_clearance(self):
        tp = generate_turning_toolpath(self._inp(clearance_x=None))
        assert tp.status == ToolpathStatus.BLOCKED


# ---------------------------------------------------------------------------
# TestConstraintValidators
# ---------------------------------------------------------------------------

class TestConstraintValidators:
    def test_tool_reach_within(self):
        result = check_tool_reach(
            path_depth_mm=10.0, tool_reach_mm=20.0,
            flute_length_mm=None, holder_clearance_mm=None
        )
        assert result.status == ToolReachStatus.WITHIN_REACH

    def test_tool_reach_conflict(self):
        result = check_tool_reach(
            path_depth_mm=25.0, tool_reach_mm=20.0,
            flute_length_mm=None, holder_clearance_mm=None
        )
        assert result.status == ToolReachStatus.TOOL_REACH_CONFLICT
        assert "CONFLICT" in result.message

    def test_tool_reach_unknown_no_data(self):
        result = check_tool_reach(
            path_depth_mm=10.0, tool_reach_mm=None,
            flute_length_mm=None, holder_clearance_mm=None
        )
        assert result.status == ToolReachStatus.UNKNOWN

    def test_tool_reach_unknown_no_path_depth(self):
        result = check_tool_reach(
            path_depth_mm=None, tool_reach_mm=20.0,
            flute_length_mm=None, holder_clearance_mm=None
        )
        assert result.status == ToolReachStatus.UNKNOWN

    def test_machine_envelope_within(self):
        result = check_machine_envelope(
            bounding_box_min=(-5, -5, -5),
            bounding_box_max=(5, 5, 5),
            travel_x_mm=100.0, travel_y_mm=100.0, travel_z_mm=100.0,
        )
        assert result.status == MachineEnvelopeStatus.WITHIN_ENVELOPE

    def test_machine_envelope_conflict(self):
        result = check_machine_envelope(
            bounding_box_min=(0, 0, 0),
            bounding_box_max=(150, 10, 10),
            travel_x_mm=100.0, travel_y_mm=100.0, travel_z_mm=100.0,
        )
        assert result.status == MachineEnvelopeStatus.ENVELOPE_CONFLICT

    def test_machine_envelope_unknown_no_spec(self):
        result = check_machine_envelope(
            bounding_box_min=(0, 0, 0),
            bounding_box_max=(10, 10, 10),
            travel_x_mm=None, travel_y_mm=None, travel_z_mm=None,
        )
        assert result.status == MachineEnvelopeStatus.UNKNOWN

    def test_tool_radius_offset_valid(self):
        ok, msg = validate_tool_radius_offset(10.0, 5.0)
        assert ok is True
        assert "within" in msg.lower()

    def test_tool_radius_offset_exceeds(self):
        ok, msg = validate_tool_radius_offset(10.0, 6.0)
        assert ok is False
        assert "EXCEEDS" in msg

    def test_tool_radius_offset_unknown_diameter(self):
        ok, msg = validate_tool_radius_offset(None, 5.0)
        assert ok is False
        assert "UNKNOWN" in msg


# ---------------------------------------------------------------------------
# TestCycleTimeBridge
# ---------------------------------------------------------------------------

class TestCycleTimeBridge:
    def test_exact_path_produces_exact_type(self):
        metrics = PathMetrics(cut_length_mm=42.5, total_length_mm=55.0)
        inp = extract_cycle_time_input(
            operation_ref="OP-1", toolpath_id="TP-1",
            metrics=metrics, fidelity=ToolpathFidelity.EXACT_GENERATED,
        )
        assert inp.path_length_type == PathLengthType.EXACT_GENERATED_PATH

    def test_partial_fidelity_produces_approximate_type(self):
        metrics = PathMetrics(cut_length_mm=10.0, total_length_mm=12.0)
        inp = extract_cycle_time_input(
            operation_ref="OP-1", toolpath_id="TP-1",
            metrics=metrics, fidelity=ToolpathFidelity.PARTIAL,
        )
        assert inp.path_length_type == PathLengthType.APPROXIMATE_GEOMETRIC_PATH

    def test_blocked_fidelity_produces_unknown_type(self):
        metrics = PathMetrics(cut_length_mm=0.0, total_length_mm=0.0)
        inp = extract_cycle_time_input(
            operation_ref="OP-1", toolpath_id="TP-1",
            metrics=metrics, fidelity=ToolpathFidelity.BLOCKED,
        )
        assert inp.path_length_type == PathLengthType.UNKNOWN

    def test_bridge_cycle_time_ready_exact(self):
        metrics = PathMetrics(cut_length_mm=42.5, total_length_mm=55.0)
        inp = extract_cycle_time_input(
            operation_ref="OP-1", toolpath_id="TP-1",
            metrics=metrics, fidelity=ToolpathFidelity.EXACT_GENERATED,
        )
        bridge = bridge_to_cycle_time(inp)
        assert bridge.cycle_time_ready is True
        assert bridge.cut_path_mm == pytest.approx(42.5)

    def test_bridge_cycle_time_not_ready_unknown(self):
        metrics = PathMetrics(cut_length_mm=0.0, total_length_mm=0.0)
        inp = extract_cycle_time_input(
            operation_ref="OP-1", toolpath_id="TP-1",
            metrics=metrics, fidelity=ToolpathFidelity.BLOCKED,
        )
        bridge = bridge_to_cycle_time(inp)
        assert bridge.cycle_time_ready is False
        assert bridge.cut_path_mm is None

    def test_bridge_approximate_adds_limitation(self):
        metrics = PathMetrics(cut_length_mm=20.0, total_length_mm=25.0)
        inp = extract_cycle_time_input(
            operation_ref="OP-1", toolpath_id="TP-1",
            metrics=metrics, fidelity=ToolpathFidelity.PARTIAL,
        )
        bridge = bridge_to_cycle_time(inp)
        assert any("APPROXIMATE" in lim for lim in bridge.limitations)

    def test_exact_vs_approximate_labels_distinct(self):
        exact = PathLengthType.EXACT_GENERATED_PATH
        approx = PathLengthType.APPROXIMATE_GEOMETRIC_PATH
        assert exact != approx


# ---------------------------------------------------------------------------
# TestNoFabricatedData
# ---------------------------------------------------------------------------

class TestNoFabricatedData:
    def test_drill_blocked_does_not_invent_segments(self):
        tp = generate_drill_toolpath(DrillInput(
            operation_ref="OP", hole_x=0, hole_y=0, hole_top_z=0, hole_depth_mm=10,
            clearance_z=None,
        ))
        assert tp.status == ToolpathStatus.BLOCKED
        assert len(tp.segments) == 0

    def test_peck_blocked_no_coordinates_in_response(self):
        tp = generate_peck_drill_toolpath(PeckDrillInput(
            operation_ref="OP", hole_x=0, hole_y=0, hole_top_z=0, hole_depth_mm=10,
            clearance_z=5, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS", peck_depth_mm=None,
        ))
        assert tp.status == ToolpathStatus.BLOCKED
        assert len(tp.segments) == 0

    def test_pocket_no_stepdown_means_no_segments(self):
        tp = generate_pocket_toolpath(PocketInput(
            operation_ref="OP",
            boundary_points=[(0, 0), (10, 0), (10, 10), (0, 10)],
            pocket_top_z=0, pocket_bottom_z=-5,
            tool_diameter_mm=5, stepdown_mm=None, stepover_mm=2,
            clearance_z=5, clearance_source=ClearanceSource.USER_SUPPLIED,
            wcs_ref="WCS",
        ))
        assert tp.status == ToolpathStatus.BLOCKED

    def test_turning_no_clearance_means_no_segments(self):
        tp = generate_turning_toolpath(TurningInput(
            operation_ref="OP",
            turning_motion_type=TurningMotionType.FACE_CUT,
            start_z=0, end_z=-20, start_x=15, end_x=5,
            clearance_x=None, wcs_ref="WCS",
        ))
        assert tp.status == ToolpathStatus.BLOCKED
        assert len(tp.segments) == 0


# ---------------------------------------------------------------------------
# TestAPIEndpoints
# ---------------------------------------------------------------------------

class TestToolpathAPIDrill:
    def test_drill_unauthenticated_returns_401(self, client: TestClient):
        r = client.post("/api/toolpath/drill", json=_drill_params())
        assert r.status_code == 401

    def test_drill_authenticated_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        assert r.status_code == 200

    def test_drill_response_has_simulation_required(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        data = r.json()
        assert data["simulation_required"] is True

    def test_drill_response_is_verified_false(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        data = r.json()
        assert data["is_verified"] is False

    def test_drill_response_verification_checks_not_performed(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        vr = r.json()["verification_requirements"]
        assert vr["collision_check"] == "NOT_PERFORMED"
        assert vr["gouge_check"] == "NOT_PERFORMED"
        assert vr["fixture_check"] == "NOT_PERFORMED"
        assert vr["machine_collision_check"] == "NOT_PERFORMED"

    def test_drill_response_no_gcode_field(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        data = r.json()
        assert "gcode" not in data
        assert "nc_code" not in data
        assert "nc_program" not in data

    def test_drill_response_has_cycle_time_bridge(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        ct = r.json()["cycle_time_bridge"]
        assert "path_length_type" in ct
        assert ct["path_length_type"] in ("EXACT_GENERATED_PATH", "APPROXIMATE_GEOMETRIC_PATH", "UNKNOWN")

    def test_peck_drill_generates_more_segments(self, client: TestClient):
        headers = _auth(client)
        params = {**_drill_params(), "peck_depth_mm": 5.0}
        r = client.post("/api/toolpath/drill", json=params, headers=headers)
        data = r.json()
        assert len(data["toolpaths"]) > 3

    def test_drill_blocked_no_wcs_returns_blocked_status(self, client: TestClient):
        headers = _auth(client)
        params = {**_drill_params(), "wcs_ref": None}
        r = client.post("/api/toolpath/drill", json=params, headers=headers)
        data = r.json()
        assert data["status"] == "BLOCKED"


class TestToolpathAPIProfile:
    def _params(self):
        return dict(
            operation_ref="OP-PROFILE",
            contour_points=[[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
            contour_z=-5.0,
            tool_diameter_mm=10.0,
            profile_side="OUTSIDE",
            compensation_side="CENTERLINE",
            clearance_z=5.0,
            clearance_source="USER_SUPPLIED",
            wcs_ref="WCS-1",
        )

    def test_profile_authenticated_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/profile", json=self._params(), headers=headers)
        assert r.status_code == 200

    def test_profile_response_simulation_required(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/profile", json=self._params(), headers=headers)
        assert r.json()["simulation_required"] is True

    def test_profile_blocked_no_wcs(self, client: TestClient):
        headers = _auth(client)
        params = {**self._params(), "wcs_ref": None}
        r = client.post("/api/toolpath/profile", json=params, headers=headers)
        assert r.json()["status"] == "BLOCKED"


class TestToolpathAPIPocket:
    def _params(self):
        return dict(
            operation_ref="OP-POCKET",
            boundary_points=[[0.0, 0.0], [30.0, 0.0], [30.0, 20.0], [0.0, 20.0]],
            pocket_top_z=0.0, pocket_bottom_z=-10.0,
            tool_diameter_mm=8.0, stepdown_mm=2.5, stepover_mm=4.0,
            strategy="OFFSET",
            clearance_z=5.0, clearance_source="USER_SUPPLIED",
            wcs_ref="WCS-1",
        )

    def test_pocket_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/pocket", json=self._params(), headers=headers)
        assert r.status_code == 200

    def test_pocket_simulation_required(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/pocket", json=self._params(), headers=headers)
        assert r.json()["simulation_required"] is True

    def test_pocket_adaptive_returns_partial(self, client: TestClient):
        headers = _auth(client)
        params = {**self._params(), "strategy": "ADAPTIVE_CANDIDATE"}
        r = client.post("/api/toolpath/pocket", json=params, headers=headers)
        assert r.json()["status"] == "PARTIAL"


class TestToolpathAPISlot:
    def _params(self):
        return dict(
            operation_ref="OP-SLOT",
            slot_start=[0.0, 0.0], slot_end=[40.0, 0.0],
            slot_z=0.0, slot_width_mm=12.0, slot_depth_mm=5.0,
            tool_diameter_mm=10.0,
            clearance_z=5.0, clearance_source="USER_SUPPLIED",
            wcs_ref="WCS-1",
        )

    def test_slot_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/slot", json=self._params(), headers=headers)
        assert r.status_code == 200

    def test_slot_blocked_tool_too_large(self, client: TestClient):
        headers = _auth(client)
        params = {**self._params(), "tool_diameter_mm": 15.0}
        r = client.post("/api/toolpath/slot", json=params, headers=headers)
        assert r.json()["status"] == "BLOCKED"


class TestToolpathAPIChamfer:
    def _params(self):
        return dict(
            operation_ref="OP-CHAMFER",
            contour_points=[[0.0, 0.0], [20.0, 0.0], [20.0, 20.0], [0.0, 20.0]],
            contour_z=0.0, tool_diameter_mm=16.0, tool_angle_deg=45.0,
            chamfer_depth_mm=1.0, clearance_z=5.0, clearance_source="USER_SUPPLIED",
            wcs_ref="WCS-1",
        )

    def test_chamfer_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/chamfer", json=self._params(), headers=headers)
        assert r.status_code == 200

    def test_chamfer_blocked_no_angle(self, client: TestClient):
        headers = _auth(client)
        params = {**self._params(), "tool_angle_deg": None}
        r = client.post("/api/toolpath/chamfer", json=params, headers=headers)
        assert r.json()["status"] == "BLOCKED"


class TestToolpathAPIFaceMill:
    def _params(self):
        return dict(
            operation_ref="OP-FACE",
            region_x_min=0.0, region_x_max=50.0,
            region_y_min=0.0, region_y_max=30.0,
            face_z=0.0, tool_diameter_mm=25.0, stepover_mm=12.5,
            clearance_z=5.0, clearance_source="USER_SUPPLIED",
            wcs_ref="WCS-1",
        )

    def test_face_mill_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/face-mill", json=self._params(), headers=headers)
        assert r.status_code == 200

    def test_face_mill_blocked_no_stepover(self, client: TestClient):
        headers = _auth(client)
        params = {**self._params(), "stepover_mm": None}
        r = client.post("/api/toolpath/face-mill", json=params, headers=headers)
        assert r.json()["status"] == "BLOCKED"


class TestToolpathAPITurning:
    def _params(self):
        return dict(
            operation_ref="OP-TURN",
            turning_motion_type="AXIAL_CUT",
            start_z=0.0, end_z=-50.0, start_x=20.0, end_x=20.0,
            clearance_x=25.0, clearance_source="USER_SUPPLIED",
            wcs_ref="WCS-LATHE",
        )

    def test_turning_returns_200(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/turning", json=self._params(), headers=headers)
        assert r.status_code == 200

    def test_turning_blocked_no_clearance(self, client: TestClient):
        headers = _auth(client)
        params = {**self._params(), "clearance_x": None}
        r = client.post("/api/toolpath/turning", json=params, headers=headers)
        assert r.json()["status"] == "BLOCKED"


# ---------------------------------------------------------------------------
# TestLevel9Regression — ensure Level-9 still works
# ---------------------------------------------------------------------------

class TestLevel9Regression:
    def test_cam_plan_endpoint_still_works(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/cam/plan", json={
            "part_id": "L10-REGRESSION",
            "features": [{"feature_id": "F1", "feature_type": "HOLE", "is_confirmed": True}],
        }, headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert data["simulation_required"] is True

    def test_cam_plan_simulation_required_always_true(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/cam/plan", json={
            "part_id": "L10-REG-02",
            "features": [],
        }, headers=headers)
        assert r.status_code == 200
        assert r.json()["simulation_required"] is True

    def test_cam_plan_unauthenticated_returns_401(self, client: TestClient):
        r = client.post("/api/cam/plan", json={"part_id": "X"})
        assert r.status_code == 401


# ---------------------------------------------------------------------------
# TestInteroperability
# ---------------------------------------------------------------------------

class TestLevel10Interoperability:
    def test_drill_cycle_time_bridge_exact_path(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        ct = r.json()["cycle_time_bridge"]
        assert ct["path_length_type"] == "EXACT_GENERATED_PATH"
        assert ct["cut_path_mm"] is not None
        assert ct["cycle_time_ready"] is True

    def test_blocked_drill_cycle_time_bridge_unknown(self, client: TestClient):
        headers = _auth(client)
        params = {**_drill_params(), "wcs_ref": None}
        r = client.post("/api/toolpath/drill", json=params, headers=headers)
        ct = r.json()["cycle_time_bridge"]
        assert ct["path_length_type"] == "UNKNOWN"
        assert ct["cycle_time_ready"] is False

    def test_toolpath_metrics_cut_length_feeds_cycle_time(self, client: TestClient):
        headers = _auth(client)
        r = client.post("/api/toolpath/drill", json=_drill_params(), headers=headers)
        data = r.json()
        metrics = data["toolpath_metrics"]
        ct = data["cycle_time_bridge"]
        assert ct["cut_path_mm"] == pytest.approx(metrics["cut_length_mm"])
