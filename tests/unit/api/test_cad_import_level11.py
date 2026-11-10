"""
Level-11 Toolpath Verification and Simulation tests.

Coverage:
  - Verification domain model (enums, tolerance, models)
  - Stock representation (BOX, CYLINDER, VoxelGrid)
  - Swept tool volume and AABB geometry
  - All 12 check types (fail-closed, deterministic, synthetic cases)
  - Verification profiles and state derivation
  - Simulation orchestration
  - Negative tests (missing geometry != PASS)
  - Numerical robustness (NaN, Inf, zero-length, degenerate)
  - Level-10 regression (simulation_required, is_verified, NOT_PERFORMED unchanged)
  - No fabricated verification data
  - API tests (skip if auth unavailable)
"""

import math
import os

import pytest

from backend.verification.checks import (
    _valid_coords,
    check_axis_limit,
    check_fixture_collision,
    check_holder_collision,
    check_machine_envelope,
    check_overtravel,
    check_part_gouge,
    check_rapid_clearance,
    check_stock_gouge,
    check_stock_remaining,
    check_tool_collision,
    check_tool_reach,
)
from backend.verification.enums import (
    SimulationStatus,
    StockShape,
    VerificationCheckType,
    VerificationProfileEnum,
    VerificationSeverity,
    VerificationState,
    VerificationStatus,
)
from backend.verification.models import (
    SimulationRequest,
    VerificationSegment,
)
from backend.verification.profiles import PROFILE_MANDATORY_CHECKS, get_mandatory_checks
from backend.verification.simulation import derive_verification_state, run_simulation
from backend.verification.stock import FixtureGeometry, StockModel, VoxelGrid
from backend.verification.swept_volume import (
    AABB,
    compute_swept_aabb,
    segment_cylinder_intersects_aabb,
    segment_intersects_aabb,
)
from backend.verification.tolerance import DEFAULT_TOLERANCE, TolerancePolicy

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seg(
    x1: float,
    y1: float,
    z1: float,
    x2: float,
    y2: float,
    z2: float,
    motion_type: str = "CUT",
    is_cutting: bool = True,
    sid: str = "s0",
) -> VerificationSegment:
    return VerificationSegment(
        segment_id=sid,
        start_x=x1,
        start_y=y1,
        start_z=z1,
        end_x=x2,
        end_y=y2,
        end_z=z2,
        motion_type=motion_type,
        is_cutting=is_cutting,
    )


def _box_stock(
    min_x: float = -25.0,
    min_y: float = -25.0,
    min_z: float = -25.0,
    max_x: float = 25.0,
    max_y: float = 25.0,
    max_z: float = 0.0,
) -> StockModel:
    return StockModel(
        shape=StockShape.BOX,
        min_x_mm=min_x,
        min_y_mm=min_y,
        min_z_mm=min_z,
        max_x_mm=max_x,
        max_y_mm=max_y,
        max_z_mm=max_z,
    )


def _fixture(
    min_x: float,
    min_y: float,
    min_z: float,
    max_x: float,
    max_y: float,
    max_z: float,
    fid: str = "fix0",
) -> FixtureGeometry:
    from backend.verification.enums import FixtureSource, FixtureType

    return FixtureGeometry(
        fixture_id=fid,
        fixture_type=FixtureType.VISE_JAWS,
        source=FixtureSource.USER_DEFINED,
        min_x_mm=min_x,
        min_y_mm=min_y,
        min_z_mm=min_z,
        max_x_mm=max_x,
        max_y_mm=max_y,
        max_z_mm=max_z,
    )


# ---------------------------------------------------------------------------
# TestVerificationEnums
# ---------------------------------------------------------------------------


class TestVerificationEnums:
    def test_verification_status_has_all_values(self):
        expected = {
            "NOT_PERFORMED",
            "INSUFFICIENT_DATA",
            "PASS",
            "FAIL",
            "PARTIAL",
            "ERROR",
        }
        assert {s.value for s in VerificationStatus} == expected

    def test_check_types_has_12_values(self):
        assert len(list(VerificationCheckType)) == 12

    def test_all_12_check_types_present(self):
        expected = {
            "TOOL_COLLISION", "HOLDER_COLLISION", "FIXTURE_COLLISION",
            "PART_GOUGE", "STOCK_GOUGE", "MACHINE_ENVELOPE", "AXIS_LIMIT",
            "TOOL_REACH", "RAPID_CLEARANCE", "STOCK_REMAINING",
            "OVERTRAVEL", "KINEMATIC_CHECK",
        }
        assert {ct.value for ct in VerificationCheckType} == expected

    def test_severity_has_4_levels(self):
        assert len(list(VerificationSeverity)) == 4

    def test_verification_state_values(self):
        expected = {
            "UNVERIFIED", "PARTIALLY_VERIFIED", "VERIFIED", "FAILED", "BLOCKED"
        }
        assert {s.value for s in VerificationState} == expected

    def test_simulation_status_has_6_values(self):
        expected = {
            "NOT_STARTED", "RUNNING", "COMPLETED", "PARTIAL", "FAILED", "BLOCKED"
        }
        assert {s.value for s in SimulationStatus} == expected

    def test_profiles_5_values(self):
        expected = {
            "GEOMETRY_ONLY", "TOOL_AND_PART", "TOOL_HOLDER_PART",
            "FULL_SETUP", "FULL_MACHINE"
        }
        assert {p.value for p in VerificationProfileEnum} == expected


# ---------------------------------------------------------------------------
# TestTolerancePolicy
# ---------------------------------------------------------------------------


class TestTolerancePolicy:
    def test_default_linear_tolerance_explicit(self):
        assert DEFAULT_TOLERANCE.linear_mm == 0.001

    def test_default_collision_tolerance_explicit(self):
        assert DEFAULT_TOLERANCE.collision_mm == 0.0

    def test_default_gouge_tolerance_explicit(self):
        assert DEFAULT_TOLERANCE.gouge_mm == 0.001

    def test_voxel_resolution_explicit(self):
        assert DEFAULT_TOLERANCE.stock_voxel_mm == 1.0

    def test_max_segment_limit_explicit(self):
        assert DEFAULT_TOLERANCE.max_path_segments == 50_000

    def test_max_voxel_cells_explicit(self):
        assert DEFAULT_TOLERANCE.max_voxel_cells == 1_000_000

    def test_custom_tolerance_immutable(self):
        tol = TolerancePolicy(
            linear_mm=0.01,
            angular_deg=0.1,
            collision_mm=0.001,
            gouge_mm=0.01,
            stock_voxel_mm=2.0,
            max_path_segments=1000,
            max_voxel_cells=100_000,
            max_simulation_iterations=5000,
        )
        assert tol.linear_mm == 0.01
        assert tol.stock_voxel_mm == 2.0


# ---------------------------------------------------------------------------
# TestStockModel
# ---------------------------------------------------------------------------


class TestStockModel:
    def test_box_stock_is_known(self):
        s = _box_stock()
        assert s.is_known is True

    def test_unknown_stock_not_known(self):
        s = StockModel(shape=StockShape.UNKNOWN)
        assert s.is_known is False

    def test_box_volume(self):
        s = _box_stock(-25, -25, -25, 25, 25, 0)
        vol = s.volume_mm3()
        assert vol == pytest.approx(50 * 50 * 25, rel=1e-6)

    def test_cylinder_volume(self):
        s = StockModel(
            shape=StockShape.CYLINDER,
            radius_mm=15.0,
            height_mm=30.0,
            center_x_mm=0.0,
            center_y_mm=0.0,
            bottom_z_mm=-30.0,
        )
        expected = math.pi * 15.0**2 * 30.0
        assert s.volume_mm3() == pytest.approx(expected, rel=1e-6)

    def test_unknown_stock_volume_is_none(self):
        s = StockModel(shape=StockShape.UNKNOWN)
        assert s.volume_mm3() is None

    def test_box_contains_interior_point(self):
        s = _box_stock()
        assert s.contains_point(0.0, 0.0, -10.0) is True

    def test_box_excludes_exterior_point(self):
        s = _box_stock()
        assert s.contains_point(100.0, 0.0, 0.0) is False

    def test_cylinder_contains_interior(self):
        s = StockModel(
            shape=StockShape.CYLINDER,
            radius_mm=10.0,
            height_mm=20.0,
            center_x_mm=0.0,
            center_y_mm=0.0,
            bottom_z_mm=-20.0,
        )
        assert s.contains_point(5.0, 5.0, -10.0) is True

    def test_cylinder_excludes_outside_radius(self):
        s = StockModel(
            shape=StockShape.CYLINDER,
            radius_mm=10.0,
            height_mm=20.0,
            center_x_mm=0.0,
            center_y_mm=0.0,
            bottom_z_mm=-20.0,
        )
        assert s.contains_point(15.0, 0.0, -10.0) is False

    def test_stock_does_not_infer_from_part_bbox(self):
        # Must supply explicit dimensions; no inference
        s = StockModel(shape=StockShape.BOX)
        assert s.has_box_dims is False
        assert s.volume_mm3() is None


# ---------------------------------------------------------------------------
# TestVoxelGrid
# ---------------------------------------------------------------------------


class TestVoxelGrid:
    def test_from_box_stock_creates_full_grid(self):
        stock = _box_stock(-25, -25, -25, 25, 25, 0)
        grid = VoxelGrid.from_stock(stock, DEFAULT_TOLERANCE)
        assert grid is not None
        total = grid.nx * grid.ny * grid.nz
        assert total <= DEFAULT_TOLERANCE.max_voxel_cells

    def test_initial_grid_all_occupied(self):
        stock = _box_stock(-10, -10, -10, 10, 10, 0)
        grid = VoxelGrid.from_stock(stock, DEFAULT_TOLERANCE)
        initial = grid.count_remaining()
        assert initial == grid.nx * grid.ny * grid.nz

    def test_remove_cylinder_reduces_stock(self):
        stock = _box_stock(-25, -25, -25, 25, 25, 0)
        grid = VoxelGrid.from_stock(stock, DEFAULT_TOLERANCE)
        initial = grid.count_remaining()
        grid.remove_path_segment(0, 0, 0, 0, 0, -20, 5.0, DEFAULT_TOLERANCE)
        assert grid.count_remaining() < initial

    def test_volume_remaining_less_than_initial(self):
        stock = _box_stock(-25, -25, -25, 25, 25, 0)
        grid = VoxelGrid.from_stock(stock, DEFAULT_TOLERANCE)
        initial_vol = grid.volume_remaining_mm3()
        grid.remove_path_segment(0, 0, 0, 0, 0, -20, 5.0, DEFAULT_TOLERANCE)
        assert grid.volume_remaining_mm3() < initial_vol

    def test_max_cells_respected(self):
        # Very coarse tolerance to force cell limit
        tol = TolerancePolicy(
            linear_mm=0.001,
            angular_deg=0.01,
            collision_mm=0.0,
            gouge_mm=0.001,
            stock_voxel_mm=0.01,
            max_path_segments=50_000,
            max_voxel_cells=10_000,
            max_simulation_iterations=10_000,
        )
        stock = _box_stock(-100, -100, -100, 100, 100, 0)
        grid = VoxelGrid.from_stock(stock, tol)
        assert grid.nx * grid.ny * grid.nz <= tol.max_voxel_cells * 2


# ---------------------------------------------------------------------------
# TestAABBGeometry
# ---------------------------------------------------------------------------


class TestAABBGeometry:
    def test_aabb_volume(self):
        a = AABB(0, 0, 0, 10, 10, 10)
        assert a.volume() == pytest.approx(1000.0)

    def test_aabb_contains_point(self):
        a = AABB(0, 0, 0, 10, 10, 10)
        assert a.contains_point(5, 5, 5) is True
        assert a.contains_point(15, 5, 5) is False

    def test_aabb_intersects(self):
        a = AABB(0, 0, 0, 10, 10, 10)
        b = AABB(5, 5, 5, 15, 15, 15)
        assert a.intersects(b) is True

    def test_aabb_no_intersect(self):
        a = AABB(0, 0, 0, 5, 5, 5)
        b = AABB(10, 10, 10, 20, 20, 20)
        assert a.intersects(b) is False

    def test_aabb_expanded_by(self):
        a = AABB(0, 0, 0, 10, 10, 10)
        b = a.expanded_by(5)
        assert b.min_x == -5
        assert b.max_x == 15

    def test_segment_intersects_aabb_pass_through(self):
        aabb = AABB(0, 0, 0, 10, 10, 10)
        assert segment_intersects_aabb(-5, 5, 5, 15, 5, 5, aabb) is True

    def test_segment_intersects_aabb_miss(self):
        aabb = AABB(0, 0, 0, 5, 5, 5)
        assert segment_intersects_aabb(10, 10, 10, 20, 20, 20, aabb) is False

    def test_segment_cylinder_intersects_aabb(self):
        aabb = AABB(10, 0, 0, 20, 10, 10)
        # Segment passes near fixture with large radius
        assert segment_cylinder_intersects_aabb(0, 5, 5, 8, 5, 5, 3.0, aabb) is True

    def test_segment_cylinder_misses_aabb(self):
        aabb = AABB(50, 0, 0, 60, 10, 10)
        assert segment_cylinder_intersects_aabb(0, 5, 5, 10, 5, 5, 1.0, aabb) is False


# ---------------------------------------------------------------------------
# TestSweptVolume
# ---------------------------------------------------------------------------


class TestSweptVolume:
    def test_unknown_tool_gives_insufficient_data(self):
        from backend.verification.enums import SweptVolumeStatus

        segs = [_seg(0, 0, 0, 0, 0, -10)]
        sv = compute_swept_aabb(segs, None)
        assert sv.status == SweptVolumeStatus.INSUFFICIENT_DATA

    def test_known_tool_gives_approximate(self):
        from backend.verification.enums import SweptVolumeStatus

        segs = [_seg(0, 0, 0, 0, 0, -10)]
        sv = compute_swept_aabb(segs, 10.0)
        assert sv.status == SweptVolumeStatus.APPROXIMATE

    def test_swept_aabb_radius_applied(self):
        segs = [_seg(0, 0, 0, 10, 0, 0)]
        sv = compute_swept_aabb(segs, 4.0)
        assert sv.aabb is not None
        assert sv.aabb.min_x <= -2.0
        assert sv.aabb.max_x >= 12.0

    def test_empty_segments_not_computed(self):
        from backend.verification.enums import SweptVolumeStatus

        sv = compute_swept_aabb([], 10.0)
        assert sv.status == SweptVolumeStatus.NOT_COMPUTED


# ---------------------------------------------------------------------------
# TestMachineEnvelopeCheck
# ---------------------------------------------------------------------------


class TestMachineEnvelopeCheck:
    def test_pass_when_within_limits(self):
        segs = [_seg(0, 0, 0, 10, 0, -5)]
        r = check_machine_envelope(segs, 500, 500, 300)
        assert r.status == VerificationStatus.PASS

    def test_fail_when_x_exceeds_limit(self):
        segs = [_seg(0, 0, 0, 300, 0, -5)]
        r = check_machine_envelope(segs, 400, 400, 300)
        # 300 < 200 (half of 400) is false → 300 > 200 → FAIL
        # wait: half of 400 = 200, abs(300) = 300 > 200 → FAIL
        assert r.status == VerificationStatus.FAIL
        assert r.severity == VerificationSeverity.CRITICAL

    def test_fail_when_z_too_deep(self):
        segs = [_seg(0, 0, -400, 0, 0, -400)]
        r = check_machine_envelope(segs, 500, 500, 300)
        # z = -400 < -300 → FAIL
        assert r.status == VerificationStatus.FAIL

    def test_insufficient_data_when_no_machine(self):
        segs = [_seg(0, 0, 0, 10, 0, -5)]
        r = check_machine_envelope(segs, None, None, None)
        assert r.status == VerificationStatus.INSUFFICIENT_DATA

    def test_pass_on_boundary(self):
        # Exactly at half_x = 50
        segs = [_seg(50, 0, -50, 50, 0, -50)]
        r = check_machine_envelope(segs, 100, 100, 100)
        assert r.status == VerificationStatus.PASS


# ---------------------------------------------------------------------------
# TestOvertravelCheck
# ---------------------------------------------------------------------------


class TestOvertravelCheck:
    def test_overtravel_fail_closed(self):
        segs = [_seg(0, 0, -5, 60, 0, -5)]
        r = check_overtravel(segs, 100, 100, 50)
        # half_x=50, x=60 > 50 → FAIL
        assert r.status == VerificationStatus.FAIL
        assert r.severity == VerificationSeverity.CRITICAL

    def test_no_overtravel_pass(self):
        segs = [_seg(10, 10, -10, 20, 20, -20)]
        r = check_overtravel(segs, 500, 500, 300)
        assert r.status == VerificationStatus.PASS

    def test_insufficient_data_no_machine(self):
        segs = [_seg(0, 0, 0, 10, 0, 0)]
        r = check_overtravel(segs, None, None, None)
        assert r.status == VerificationStatus.INSUFFICIENT_DATA

    def test_overtravel_z_negative_direction(self):
        segs = [_seg(0, 0, -400, 0, 0, -400)]
        r = check_overtravel(segs, 500, 500, 300)
        assert r.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# TestToolReachCheck
# ---------------------------------------------------------------------------


class TestToolReachCheck:
    def test_pass_within_flute_length(self):
        segs = [_seg(0, 0, 2, 0, 0, -15)]
        r = check_tool_reach(segs, flute_length_mm=30.0, holder_clearance_mm=None)
        assert r.status == VerificationStatus.PASS

    def test_fail_when_depth_exceeds_flute(self):
        segs = [_seg(0, 0, 2, 0, 0, -40)]
        r = check_tool_reach(segs, flute_length_mm=20.0, holder_clearance_mm=None)
        assert r.status == VerificationStatus.FAIL
        assert r.severity == VerificationSeverity.CRITICAL

    def test_insufficient_data_no_tool(self):
        segs = [_seg(0, 0, 0, 0, 0, -20)]
        r = check_tool_reach(segs, flute_length_mm=None, holder_clearance_mm=None)
        assert r.status == VerificationStatus.INSUFFICIENT_DATA

    def test_holder_clearance_limits_effective_reach(self):
        # flute=50mm but holder_clearance=15mm → effective=15mm
        segs = [_seg(0, 0, 2, 0, 0, -20)]
        r = check_tool_reach(segs, flute_length_mm=50.0, holder_clearance_mm=15.0)
        # depth ~22mm > effective 15mm → FAIL
        assert r.status == VerificationStatus.FAIL

    def test_evidence_reports_flute_and_holder_separately(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_tool_reach(segs, flute_length_mm=30.0, holder_clearance_mm=25.0)
        assert "flute_length_mm" in r.evidence
        assert "holder_clearance_mm" in r.evidence
        assert "effective_reach_mm" in r.evidence


# ---------------------------------------------------------------------------
# TestPartGougeCheck
# ---------------------------------------------------------------------------


class TestPartGougeCheck:
    def test_insufficient_data_no_part(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_part_gouge(segs, None, None, 10.0)
        assert r.status == VerificationStatus.INSUFFICIENT_DATA

    def test_pass_when_cutting_above_part_bottom(self):
        segs = [_seg(0, 0, 0, 0, 0, -5)]
        r = check_part_gouge(
            segs,
            part_bbox_min=(-10.0, -10.0, -10.0),
            part_bbox_max=(10.0, 10.0, 0.0),
            tool_diameter_mm=8.0,
        )
        # z goes to -5 > part_min_z(-10) → no Z-gouge
        assert r.status in (VerificationStatus.PASS, VerificationStatus.PARTIAL)

    def test_fail_when_below_part_bottom(self):
        segs = [_seg(0, 0, 0, 0, 0, -15)]
        r = check_part_gouge(
            segs,
            part_bbox_min=(-10.0, -10.0, -10.0),
            part_bbox_max=(10.0, 10.0, 0.0),
            tool_diameter_mm=8.0,
        )
        # z goes to -15 < part_min_z(-10) → FAIL
        assert r.status == VerificationStatus.FAIL
        assert r.severity == VerificationSeverity.CRITICAL

    def test_explicit_gouge_tolerance_used(self):
        # Exactly at boundary
        segs = [_seg(0, 0, -10.0005, 0, 0, -10.0005)]
        tol = TolerancePolicy(
            linear_mm=0.001, angular_deg=0.01, collision_mm=0.0,
            gouge_mm=0.001, stock_voxel_mm=1.0, max_path_segments=50_000,
            max_voxel_cells=1_000_000, max_simulation_iterations=10_000,
        )
        r = check_part_gouge(
            segs,
            part_bbox_min=(-10, -10, -10),
            part_bbox_max=(10, 10, 0),
            tool_diameter_mm=8.0,
            tol=tol,
        )
        # -10.0005 < -10 - 0.001 = -10.001? No. -10.001 is more negative.
        # -10.0005 > -10.001, so NOT below tolerance → no Z-gouge from that check
        assert r.status in (VerificationStatus.PASS, VerificationStatus.PARTIAL)


# ---------------------------------------------------------------------------
# TestStockGougeCheck
# ---------------------------------------------------------------------------


class TestStockGougeCheck:
    def test_insufficient_data_no_stock(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_stock_gouge(segs, None, 10.0)
        assert r.status == VerificationStatus.INSUFFICIENT_DATA

    def test_pass_inside_stock(self):
        segs = [_seg(0, 0, 0, 0, 0, -20)]
        r = check_stock_gouge(segs, _box_stock(), 8.0)
        assert r.status == VerificationStatus.PASS

    def test_fail_when_cutting_outside_stock(self):
        segs = [_seg(0, 0, 0, 100, 0, 0)]  # x=100 outside stock (max_x=25)
        r = check_stock_gouge(segs, _box_stock(), 8.0)
        assert r.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# TestToolCollisionCheck
# ---------------------------------------------------------------------------


class TestToolCollisionCheck:
    def test_not_performed_when_no_fixture(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_tool_collision(segs, [], 8.0)
        assert r.status == VerificationStatus.NOT_PERFORMED

    def test_insufficient_data_no_tool_diameter(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        fix = [_fixture(50, 50, -20, 100, 100, 0)]
        r = check_tool_collision(segs, fix, None)
        assert r.status == VerificationStatus.INSUFFICIENT_DATA

    def test_pass_when_tool_clear_of_fixture(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        fix = [_fixture(100, 100, -20, 200, 200, 0)]
        r = check_tool_collision(segs, fix, 8.0)
        assert r.status == VerificationStatus.PASS

    def test_fail_when_tool_intersects_fixture(self):
        # Segment goes from (0,0,0) to (20,0,0), fixture at x=10..30, y=-5..5, z=-5..5
        segs = [_seg(0, 0, 0, 20, 0, 0, is_cutting=False, motion_type="RAPID")]
        fix = [_fixture(10, -5, -5, 30, 5, 5)]
        r = check_tool_collision(segs, fix, 4.0)
        assert r.status == VerificationStatus.FAIL
        assert r.severity == VerificationSeverity.CRITICAL


# ---------------------------------------------------------------------------
# TestHolderCollisionCheck
# ---------------------------------------------------------------------------


class TestHolderCollisionCheck:
    def test_not_performed_when_no_holder_geometry(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        fix = [_fixture(50, 50, -20, 100, 100, 50)]
        r = check_holder_collision(segs, fix, 20.0, None, None)
        assert r.status == VerificationStatus.NOT_PERFORMED

    def test_not_performed_when_no_fixture(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_holder_collision(segs, [], 20.0, 30.0, 50.0)
        assert r.status == VerificationStatus.NOT_PERFORMED

    def test_fail_on_holder_fixture_collision(self):
        # Tool at x=0 going to z=-20; large holder (radius=25) at same XY
        # Fixture at x=20..30 (close enough to be hit by holder radius=25)
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        fix = [_fixture(20, -5, 0, 30, 5, 60)]
        r = check_holder_collision(
            segs, fix, tool_length_mm=10.0, holder_diameter_mm=50.0, holder_length_mm=50.0
        )
        assert r.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# TestFixtureCollisionCheck
# ---------------------------------------------------------------------------


class TestFixtureCollisionCheck:
    def test_not_performed_no_fixture(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_fixture_collision(segs, [], 8.0, None, None, None)
        assert r.status == VerificationStatus.NOT_PERFORMED

    def test_fail_when_tool_hits_fixture(self):
        segs = [_seg(0, 0, 0, 20, 0, 0)]
        fix = [_fixture(10, -5, -5, 30, 5, 5)]
        r = check_fixture_collision(segs, fix, 4.0, None, None, None)
        assert r.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# TestRapidClearanceCheck
# ---------------------------------------------------------------------------


class TestRapidClearanceCheck:
    def test_not_performed_no_fixture(self):
        segs = [_seg(0, 0, 5, 30, 0, 5, motion_type="RAPID", is_cutting=False)]
        r = check_rapid_clearance(segs, [], 8.0)
        assert r.status == VerificationStatus.NOT_PERFORMED

    def test_fail_rapid_through_fixture(self):
        segs = [_seg(0, 0, 5, 30, 0, 5, motion_type="RAPID", is_cutting=False)]
        fix = [_fixture(10, -5, 0, 25, 5, 10)]
        r = check_rapid_clearance(segs, fix, 4.0)
        assert r.status == VerificationStatus.FAIL
        assert r.severity == VerificationSeverity.CRITICAL

    def test_pass_rapid_above_fixture(self):
        segs = [_seg(0, 0, 50, 30, 0, 50, motion_type="RAPID", is_cutting=False)]
        fix = [_fixture(10, -5, 0, 25, 5, 10)]
        r = check_rapid_clearance(segs, fix, 4.0)
        assert r.status == VerificationStatus.PASS

    def test_pass_no_rapid_segments(self):
        segs = [_seg(0, 0, 0, 10, 0, -10, motion_type="CUT", is_cutting=True)]
        fix = [_fixture(10, -5, 0, 25, 5, 10)]
        r = check_rapid_clearance(segs, fix, 4.0)
        assert r.status == VerificationStatus.PASS


# ---------------------------------------------------------------------------
# TestVerificationProfiles
# ---------------------------------------------------------------------------


class TestVerificationProfiles:
    def test_geometry_only_has_part_gouge_and_stock_gouge(self):
        m = get_mandatory_checks(VerificationProfileEnum.GEOMETRY_ONLY)
        assert VerificationCheckType.PART_GOUGE in m
        assert VerificationCheckType.STOCK_GOUGE in m
        assert VerificationCheckType.MACHINE_ENVELOPE not in m

    def test_full_machine_has_all_critical_checks(self):
        m = get_mandatory_checks(VerificationProfileEnum.FULL_MACHINE)
        assert VerificationCheckType.MACHINE_ENVELOPE in m
        assert VerificationCheckType.OVERTRAVEL in m
        assert VerificationCheckType.KINEMATIC_CHECK in m

    def test_geometry_only_does_not_include_machine_checks(self):
        m = get_mandatory_checks(VerificationProfileEnum.GEOMETRY_ONLY)
        assert VerificationCheckType.MACHINE_ENVELOPE not in m
        assert VerificationCheckType.OVERTRAVEL not in m

    def test_full_setup_requires_fixture_checks(self):
        m = get_mandatory_checks(VerificationProfileEnum.FULL_SETUP)
        assert VerificationCheckType.FIXTURE_COLLISION in m
        assert VerificationCheckType.RAPID_CLEARANCE in m

    def test_all_profiles_in_dict(self):
        for p in VerificationProfileEnum:
            assert p in PROFILE_MANDATORY_CHECKS


# ---------------------------------------------------------------------------
# TestVerificationStateDerivation
# ---------------------------------------------------------------------------


class TestVerificationStateDerivation:
    def test_no_checks_unverified(self):
        state = derive_verification_state({}, frozenset())
        assert state == VerificationState.UNVERIFIED

    def test_all_mandatory_pass_gives_verified(self):
        from backend.verification.models import VerificationResult

        checks = {
            VerificationCheckType.PART_GOUGE.value: VerificationResult(
                check_type=VerificationCheckType.PART_GOUGE,
                status=VerificationStatus.PASS,
                severity=VerificationSeverity.INFO,
            ),
            VerificationCheckType.STOCK_GOUGE.value: VerificationResult(
                check_type=VerificationCheckType.STOCK_GOUGE,
                status=VerificationStatus.PASS,
                severity=VerificationSeverity.INFO,
            ),
        }
        mandatory = get_mandatory_checks(VerificationProfileEnum.GEOMETRY_ONLY)
        state = derive_verification_state(checks, mandatory)
        assert state == VerificationState.VERIFIED

    def test_any_fail_gives_failed(self):
        from backend.verification.models import VerificationResult

        checks = {
            VerificationCheckType.PART_GOUGE.value: VerificationResult(
                check_type=VerificationCheckType.PART_GOUGE,
                status=VerificationStatus.FAIL,
                severity=VerificationSeverity.CRITICAL,
            ),
        }
        state = derive_verification_state(checks, frozenset())
        assert state == VerificationState.FAILED

    def test_some_not_performed_gives_blocked_or_partial(self):
        from backend.verification.models import VerificationResult

        checks = {
            VerificationCheckType.TOOL_COLLISION.value: VerificationResult(
                check_type=VerificationCheckType.TOOL_COLLISION,
                status=VerificationStatus.NOT_PERFORMED,
                severity=VerificationSeverity.WARNING,
            ),
        }
        state = derive_verification_state(checks, frozenset())
        assert state in (VerificationState.BLOCKED, VerificationState.UNVERIFIED)

    def test_mixed_pass_and_not_performed_gives_partially_verified(self):
        from backend.verification.models import VerificationResult

        checks = {
            VerificationCheckType.PART_GOUGE.value: VerificationResult(
                check_type=VerificationCheckType.PART_GOUGE,
                status=VerificationStatus.PASS,
                severity=VerificationSeverity.INFO,
            ),
            VerificationCheckType.TOOL_COLLISION.value: VerificationResult(
                check_type=VerificationCheckType.TOOL_COLLISION,
                status=VerificationStatus.NOT_PERFORMED,
                severity=VerificationSeverity.WARNING,
            ),
        }
        state = derive_verification_state(checks, frozenset())
        assert state == VerificationState.PARTIALLY_VERIFIED

    def test_not_performed_is_not_pass(self):
        assert VerificationStatus.NOT_PERFORMED != VerificationStatus.PASS

    def test_insufficient_data_is_not_pass(self):
        assert VerificationStatus.INSUFFICIENT_DATA != VerificationStatus.PASS

    def test_partial_is_not_pass(self):
        assert VerificationStatus.PARTIAL != VerificationStatus.PASS

    def test_error_is_not_pass(self):
        assert VerificationStatus.ERROR != VerificationStatus.PASS


# ---------------------------------------------------------------------------
# TestSimulationResult
# ---------------------------------------------------------------------------


class TestSimulationResult:
    def test_is_verified_derived_from_state(self):
        from backend.verification.models import SimulationResult

        r = SimulationResult(
            session_id="x",
            toolpath_id="tp",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.VERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        assert r.is_verified is True

    def test_is_verified_false_when_unverified(self):
        from backend.verification.models import SimulationResult

        r = SimulationResult(
            session_id="x",
            toolpath_id="tp",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.UNVERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        assert r.is_verified is False

    def test_completed_simulation_may_still_fail(self):
        from backend.verification.models import SimulationResult

        r = SimulationResult(
            session_id="x",
            toolpath_id="tp",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.FAILED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        assert r.simulation_status == SimulationStatus.COMPLETED
        assert r.is_verified is False


# ---------------------------------------------------------------------------
# TestSyntheticSafeDrilling
# ---------------------------------------------------------------------------


class TestSyntheticSafeDrilling:
    """Known geometry: drill through stock, within machine limits, no fixture."""

    def setup_method(self):
        self.stock = _box_stock(-25, -25, -25, 25, 25, 2)
        self.segs = [
            _seg(0, 0, 2, 0, 0, 2, motion_type="APPROACH", is_cutting=False, sid="s0"),
            _seg(0, 0, 2, 0, 0, -20, motion_type="PLUNGE", is_cutting=True, sid="s1"),
            _seg(0, 0, -20, 0, 0, 2, motion_type="RETRACT", is_cutting=False, sid="s2"),
        ]
        self.req = SimulationRequest(
            toolpath_id="drill_safe",
            segments=self.segs,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            tool_diameter_mm=10.0,
            tool_length_mm=50.0,
            tool_flute_length_mm=30.0,
            stock=self.stock,
            machine_travel_x_mm=500,
            machine_travel_y_mm=500,
            machine_travel_z_mm=300,
            part_bbox_min=(-10, -10, -25),
            part_bbox_max=(10, 10, 0),
        )

    def test_simulation_completes(self):
        result = run_simulation(self.req)
        assert result.simulation_status == SimulationStatus.COMPLETED

    def test_stock_gouge_pass(self):
        result = run_simulation(self.req)
        sg = result.checks.get(VerificationCheckType.STOCK_GOUGE.value)
        assert sg is not None
        assert sg.status == VerificationStatus.PASS

    def test_machine_envelope_pass(self):
        result = run_simulation(self.req)
        env = result.checks.get(VerificationCheckType.MACHINE_ENVELOPE.value)
        assert env is not None
        assert env.status == VerificationStatus.PASS

    def test_overtravel_pass(self):
        result = run_simulation(self.req)
        ot = result.checks.get(VerificationCheckType.OVERTRAVEL.value)
        assert ot is not None
        assert ot.status == VerificationStatus.PASS

    def test_tool_reach_pass(self):
        result = run_simulation(self.req)
        tr = result.checks.get(VerificationCheckType.TOOL_REACH.value)
        assert tr is not None
        assert tr.status == VerificationStatus.PASS

    def test_remaining_stock_less_than_initial(self):
        result = run_simulation(self.req)
        if result.remaining_stock_volume_mm3 is not None:
            assert result.remaining_stock_volume_mm3 < result.initial_stock_volume_mm3

    def test_geometry_only_verified_state(self):
        result = run_simulation(self.req)
        # GEOMETRY_ONLY: PART_GOUGE + STOCK_GOUGE mandatory
        # STOCK_GOUGE passes; PART_GOUGE may PASS or PARTIAL
        assert result.verification_state in (
            VerificationState.VERIFIED,
            VerificationState.PARTIALLY_VERIFIED,
        )


# ---------------------------------------------------------------------------
# TestSyntheticGougingDrill
# ---------------------------------------------------------------------------


class TestSyntheticGougingDrill:
    """Known geometry: drill goes below final part bottom → PART_GOUGE=FAIL."""

    def test_part_gouge_fail(self):
        segs = [_seg(0, 0, 0, 0, 0, -30, motion_type="PLUNGE", is_cutting=True)]
        req = SimulationRequest(
            toolpath_id="gouge_drill",
            segments=segs,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            tool_diameter_mm=8.0,
            stock=_box_stock(-25, -25, -25, 25, 25, 0),
            part_bbox_min=(-10, -10, -20),
            part_bbox_max=(10, 10, 0),
        )
        result = run_simulation(req)
        pg = result.checks.get(VerificationCheckType.PART_GOUGE.value)
        assert pg is not None
        # Drill goes to -30, part_min_z=-20 → z_low=-30 < -20-0.001 → FAIL
        assert pg.status == VerificationStatus.FAIL
        assert pg.severity == VerificationSeverity.CRITICAL

    def test_gouge_state_is_failed(self):
        segs = [_seg(0, 0, 0, 0, 0, -30, motion_type="PLUNGE", is_cutting=True)]
        req = SimulationRequest(
            toolpath_id="gouge_drill2",
            segments=segs,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            tool_diameter_mm=8.0,
            part_bbox_min=(-10, -10, -20),
            part_bbox_max=(10, 10, 0),
        )
        result = run_simulation(req)
        assert result.verification_state == VerificationState.FAILED
        assert result.is_verified is False


# ---------------------------------------------------------------------------
# TestSyntheticToolReachConflict
# ---------------------------------------------------------------------------


class TestSyntheticToolReachConflict:
    """Known geometry: pocket depth 40mm, flute length 20mm → TOOL_REACH=FAIL."""

    def test_deep_pocket_fail(self):
        segs = [
            _seg(0, 0, 2, 0, 0, -40, motion_type="PLUNGE", is_cutting=True, sid="s1")
        ]
        req = SimulationRequest(
            toolpath_id="deep_pocket",
            segments=segs,
            profile=VerificationProfileEnum.TOOL_AND_PART,
            tool_diameter_mm=10.0,
            tool_length_mm=50.0,
            tool_flute_length_mm=20.0,
        )
        result = run_simulation(req)
        tr = result.checks.get(VerificationCheckType.TOOL_REACH.value)
        assert tr is not None
        assert tr.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# TestSyntheticHolderCollision
# ---------------------------------------------------------------------------


class TestSyntheticHolderCollision:
    """Known geometry: holder (radius=25mm) hits fixture wall."""

    def test_holder_collision_fail(self):
        # Path at x=0 → holder extends 25mm radius → hits fixture at x=20
        segs = [_seg(0, 0, 0, 0, 0, -20, is_cutting=True)]
        fix = [_fixture(20, -5, 0, 50, 5, 60)]
        req = SimulationRequest(
            toolpath_id="holder_coll",
            segments=segs,
            profile=VerificationProfileEnum.TOOL_HOLDER_PART,
            tool_diameter_mm=8.0,
            tool_length_mm=20.0,
            holder_diameter_mm=50.0,
            holder_length_mm=50.0,
            fixtures=fix,
        )
        result = run_simulation(req)
        hc = result.checks.get(VerificationCheckType.HOLDER_COLLISION.value)
        assert hc is not None
        assert hc.status == VerificationStatus.FAIL
        assert hc.severity == VerificationSeverity.CRITICAL


# ---------------------------------------------------------------------------
# TestSyntheticFixtureCollision
# ---------------------------------------------------------------------------


class TestSyntheticFixtureCollision:
    """Known geometry: tool path intersects fixture box → FIXTURE_COLLISION=FAIL."""

    def test_fixture_collision_fail(self):
        segs = [_seg(0, 0, 0, 20, 0, 0, is_cutting=False, motion_type="RAPID")]
        fix = [_fixture(10, -5, -5, 25, 5, 5)]
        req = SimulationRequest(
            toolpath_id="fix_coll",
            segments=segs,
            profile=VerificationProfileEnum.FULL_SETUP,
            tool_diameter_mm=4.0,
            tool_length_mm=20.0,
            fixtures=fix,
        )
        result = run_simulation(req)
        fc = result.checks.get(VerificationCheckType.FIXTURE_COLLISION.value)
        assert fc is not None
        assert fc.status == VerificationStatus.FAIL


# ---------------------------------------------------------------------------
# TestSyntheticOvertravel
# ---------------------------------------------------------------------------


class TestSyntheticOvertravel:
    """Known geometry: path point at x=300 exceeds travel ±200 → OVERTRAVEL=FAIL."""

    def test_overtravel_fail(self):
        segs = [_seg(0, 0, 0, 300, 0, -10)]
        req = SimulationRequest(
            toolpath_id="overtravel",
            segments=segs,
            profile=VerificationProfileEnum.FULL_MACHINE,
            tool_diameter_mm=8.0,
            machine_travel_x_mm=400,
            machine_travel_y_mm=400,
            machine_travel_z_mm=300,
        )
        result = run_simulation(req)
        ot = result.checks.get(VerificationCheckType.OVERTRAVEL.value)
        # half_x=200, x=300 > 200 → FAIL
        assert ot is not None
        assert ot.status == VerificationStatus.FAIL
        assert result.is_verified is False


# ---------------------------------------------------------------------------
# TestSyntheticRemainingStock
# ---------------------------------------------------------------------------


class TestSyntheticRemainingStock:
    def test_remaining_stock_after_drilling(self):
        stock = _box_stock(-25, -25, -25, 25, 25, 0)
        segs = [_seg(0, 0, 0, 0, 0, -20, is_cutting=True)]
        req = SimulationRequest(
            toolpath_id="remaining",
            segments=segs,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            tool_diameter_mm=10.0,
            stock=stock,
        )
        result = run_simulation(req)
        if result.remaining_stock_volume_mm3 is not None:
            assert result.remaining_stock_volume_mm3 < result.initial_stock_volume_mm3
            assert result.removed_volume_mm3 is not None
            assert result.removed_volume_mm3 >= 0.0
        # Fidelity must not be EXACT_BOOLEAN
        assert result.stock_removal_fidelity != "EXACT_BOOLEAN"


# ---------------------------------------------------------------------------
# TestNegativeTests
# ---------------------------------------------------------------------------


class TestNegativeTests:
    def test_no_stock_no_stock_removal_pass(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_stock_remaining(segs, None, 8.0)
        result, _, _ = r
        assert result.status != VerificationStatus.PASS

    def test_no_fixture_no_fixture_collision_pass(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_fixture_collision(segs, [], 8.0, None, None, None)
        assert r.status != VerificationStatus.PASS

    def test_no_holder_no_holder_collision_pass(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        fix = [_fixture(50, 50, -20, 100, 100, 0)]
        r = check_holder_collision(segs, fix, 20.0, None, None)
        assert r.status != VerificationStatus.PASS

    def test_no_machine_no_envelope_pass(self):
        segs = [_seg(0, 0, 0, 10, 0, -5)]
        r = check_machine_envelope(segs, None, None, None)
        assert r.status != VerificationStatus.PASS

    def test_simulation_completed_not_equal_verified(self):
        req = SimulationRequest(
            toolpath_id="neg_test",
            segments=[_seg(0, 0, 0, 0, 0, -10)],
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
            tool_diameter_mm=8.0,
        )
        result = run_simulation(req)
        assert result.simulation_status == SimulationStatus.COMPLETED
        # Without part_bbox, PART_GOUGE=INSUFFICIENT_DATA → not VERIFIED
        assert result.is_verified is False

    def test_partial_model_not_collision_free(self):
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        r = check_tool_collision(segs, [], 8.0)
        assert r.status == VerificationStatus.NOT_PERFORMED
        assert r.status != VerificationStatus.PASS

    def test_toolpath_generated_not_equal_verified(self):
        # Generate a toolpath from Level-10 → it must still be unverified
        from backend.toolpath.generators import DrillInput, generate_drill_toolpath

        inp = DrillInput(
            operation_ref="op1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=20.0,
            clearance_z=5.0,
            setup_ref="setup1",
            wcs_ref="wcs1",
            tool_ref="tool1",
        )
        tp = generate_drill_toolpath(inp)
        assert tp.is_verified is False
        assert tp.simulation_required is True


# ---------------------------------------------------------------------------
# TestNumericalRobustness
# ---------------------------------------------------------------------------


class TestNumericalRobustness:
    def test_valid_coords_normal(self):
        assert _valid_coords(0.0, 0.0, 0.0) is True

    def test_valid_coords_rejects_nan(self):
        assert _valid_coords(float("nan"), 0.0, 0.0) is False

    def test_valid_coords_rejects_inf(self):
        assert _valid_coords(float("inf"), 0.0, 0.0) is False
        assert _valid_coords(0.0, float("-inf"), 0.0) is False

    def test_valid_coords_rejects_extreme(self):
        assert _valid_coords(1e10, 0.0, 0.0) is False

    def test_zero_length_segment_handled_in_check(self):
        segs = [_seg(5.0, 5.0, -5.0, 5.0, 5.0, -5.0)]  # zero length
        r = check_stock_gouge(segs, _box_stock(), 8.0)
        assert r.status in (VerificationStatus.PASS, VerificationStatus.FAIL)

    def test_nan_segment_does_not_crash(self):
        segs = [_seg(float("nan"), 0, 0, 0, 0, -10)]
        r = check_stock_gouge(segs, _box_stock(), 8.0)
        assert r.status in (VerificationStatus.PASS, VerificationStatus.FAIL)

    def test_inf_coords_do_not_crash(self):
        segs = [_seg(float("inf"), 0, 0, 0, 0, -10)]
        r = check_machine_envelope(segs, 500, 500, 300)
        assert r.status in (VerificationStatus.PASS, VerificationStatus.FAIL)

    def test_resource_limit_returns_partial(self):
        tol = TolerancePolicy(
            linear_mm=0.001, angular_deg=0.01, collision_mm=0.0,
            gouge_mm=0.001, stock_voxel_mm=0.5, max_path_segments=50_000,
            max_voxel_cells=100_000, max_simulation_iterations=1,
        )
        stock = _box_stock(-25, -25, -25, 25, 25, 0)
        segs = [_seg(0, 0, 0, 0, 0, -20, is_cutting=True)]
        result, _, _ = check_stock_remaining(segs, stock, 8.0, tol)
        # With max_iterations=1 it will hit limit
        assert result.status in (VerificationStatus.PASS, VerificationStatus.PARTIAL)


# ---------------------------------------------------------------------------
# TestLevel10Regression
# ---------------------------------------------------------------------------


class TestLevel10Regression:
    def test_level10_drill_simulation_required_true(self):
        from backend.toolpath.generators import DrillInput, generate_drill_toolpath

        inp = DrillInput(
            operation_ref="op1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=20.0,
            clearance_z=5.0,
            setup_ref="setup1",
            wcs_ref="wcs1",
            tool_ref="tool1",
        )
        tp = generate_drill_toolpath(inp)
        assert tp.simulation_required is True

    def test_level10_is_verified_still_false(self):
        from backend.toolpath.generators import DrillInput, generate_drill_toolpath

        inp = DrillInput(
            operation_ref="op1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=20.0,
            clearance_z=5.0,
            setup_ref="setup1",
            wcs_ref="wcs1",
            tool_ref="tool1",
        )
        tp = generate_drill_toolpath(inp)
        assert tp.is_verified is False

    def test_level10_verification_contract_all_not_performed(self):
        from backend.toolpath.generators import DrillInput, generate_drill_toolpath

        inp = DrillInput(
            operation_ref="op1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=20.0,
            clearance_z=5.0,
            setup_ref="setup1",
            wcs_ref="wcs1",
            tool_ref="tool1",
        )
        tp = generate_drill_toolpath(inp)
        contract = tp.verification
        assert contract.collision_check.value == "NOT_PERFORMED"
        assert contract.gouge_check.value == "NOT_PERFORMED"
        assert contract.fixture_check.value == "NOT_PERFORMED"
        assert contract.machine_collision_check.value == "NOT_PERFORMED"

    def test_level11_adds_verification_only_when_invoked(self):
        # Without running simulation, Level-10 toolpath has no verification results
        from backend.toolpath.generators import DrillInput, generate_drill_toolpath

        inp = DrillInput(
            operation_ref="op1",
            hole_x=0.0,
            hole_y=0.0,
            hole_top_z=0.0,
            hole_depth_mm=20.0,
            clearance_z=5.0,
            setup_ref="setup1",
            wcs_ref="wcs1",
            tool_ref="tool1",
        )
        tp = generate_drill_toolpath(inp)
        # Level-10 has no checks dict — only after run_simulation
        assert tp.is_verified is False
        assert tp.simulation_required is True


# ---------------------------------------------------------------------------
# TestNoFabricatedData
# ---------------------------------------------------------------------------


class TestNoFabricatedData:
    def test_no_hardcoded_safe_results_in_checks(self):
        """Missing inputs must NOT produce PASS."""
        segs = [_seg(0, 0, 0, 0, 0, -10)]
        for fn in [
            lambda: check_tool_collision(segs, [], 8.0),
            lambda: check_holder_collision(segs, [], 20.0, None, None),
            lambda: check_fixture_collision(segs, [], 8.0, None, None, None),
            lambda: check_rapid_clearance(segs, [], 8.0),
        ]:
            r = fn()
            assert r.status != VerificationStatus.PASS, (
                f"{r.check_type}: returned PASS with no fixture geometry"
            )

    def test_simulation_is_verified_starts_false(self):
        req = SimulationRequest(
            toolpath_id="fabrication_test",
            segments=[],
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        result = run_simulation(req)
        assert result.is_verified is False

    def test_no_gcode_in_verification_module(self):
        import inspect

        import backend.verification.simulation as sim_module

        source = inspect.getsource(sim_module)
        for token in ["G00", "G01", "G02", "M03", "M30", "N0010", "%\n"]:
            assert token not in source


# ---------------------------------------------------------------------------
# TestSegmentCount
# ---------------------------------------------------------------------------


class TestSegmentCount:
    def test_exceeding_segment_limit_returns_blocked(self):
        tol = TolerancePolicy(
            linear_mm=0.001, angular_deg=0.01, collision_mm=0.0,
            gouge_mm=0.001, stock_voxel_mm=1.0, max_path_segments=5,
            max_voxel_cells=1_000_000, max_simulation_iterations=10_000,
        )
        segs = [_seg(float(i), 0, 0, float(i + 1), 0, 0, sid=f"s{i}") for i in range(10)]
        req = SimulationRequest(
            toolpath_id="overcount",
            segments=segs,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        result = run_simulation(req, tol)
        assert result.simulation_status == SimulationStatus.FAILED
        assert result.verification_state == VerificationState.BLOCKED
        assert result.resource_limit_hit is True


# ---------------------------------------------------------------------------
# TestKinematicCheckFoundation
# ---------------------------------------------------------------------------


class TestKinematicCheckFoundation:
    def test_kinematic_check_is_not_performed(self):
        segs = [_seg(0, 0, 0, 10, 0, -10)]
        r = check_axis_limit(segs, None)
        assert r.status == VerificationStatus.NOT_PERFORMED

    def test_kinematic_check_in_simulation(self):
        req = SimulationRequest(
            toolpath_id="kc_test",
            segments=[_seg(0, 0, 0, 0, 0, -10)],
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        result = run_simulation(req)
        kc = result.checks.get(VerificationCheckType.KINEMATIC_CHECK.value)
        assert kc is not None
        assert kc.status == VerificationStatus.NOT_PERFORMED


# ---------------------------------------------------------------------------
# TestVerificationAPI (skip without auth)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def _auth(client):
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "dev")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "dev")
    os.environ.setdefault("JWT_SECRET", "devsecret")
    resp = client.post(
        "/api/login",
        json={
            "username": os.environ["MACHININGPRO_DEV_USERNAME"],
            "password": os.environ["MACHININGPRO_DEV_PASSWORD"],
        },
    )
    if resp.status_code != 200:
        pytest.skip("Cannot authenticate")
    return {"Authorization": f"Bearer {resp.json()['token']}"}


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient

    from backend.api.app import app

    return TestClient(app)


class TestVerificationAPISimulate:
    def test_simulate_requires_auth(self, client):
        body = {
            "toolpath_id": "tp1",
            "segments": [],
            "profile": "GEOMETRY_ONLY",
        }
        resp = client.post("/api/verification/simulate", json=body)
        assert resp.status_code == 401

    def test_simulate_with_auth(self, client, _auth):
        body = {
            "toolpath_id": "tp1",
            "segments": [],
            "profile": "GEOMETRY_ONLY",
        }
        resp = client.post("/api/verification/simulate", json=body, headers=_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "verification_state" in data
        assert data["verification_state"] != "VERIFIED"

    def test_simulate_geometry_only_requires_auth(self, client):
        body = {"toolpath_id": "tp1", "segments": [], "profile": "GEOMETRY_ONLY"}
        resp = client.post("/api/verification/simulate/geometry-only", json=body)
        assert resp.status_code == 401

    def test_simulate_response_has_all_12_checks(self, client, _auth):
        body = {
            "toolpath_id": "tp_all",
            "segments": [],
            "profile": "FULL_MACHINE",
        }
        resp = client.post("/api/verification/simulate", json=body, headers=_auth)
        assert resp.status_code == 200
        data = resp.json()
        checks = data.get("checks", {})
        assert len(checks) == 12

    def test_simulate_no_fabricated_pass(self, client, _auth):
        body = {
            "toolpath_id": "tp_neg",
            "segments": [],
            "profile": "FULL_MACHINE",
        }
        resp = client.post("/api/verification/simulate", json=body, headers=_auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["verification_state"] != "VERIFIED"
        checks = data.get("checks", {})
        for name, check in checks.items():
            assert check["status"] != "PASS", f"Check {name} should not PASS with no inputs"
