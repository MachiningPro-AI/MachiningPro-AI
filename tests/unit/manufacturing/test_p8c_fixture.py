"""P8-C Tests: Fixture geometry input model (MUST 44)."""

from __future__ import annotations

from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    P8VerificationInput,
    build_verification_input,
    nc_segments_to_verification_segments,
    run_p8_verification,
)
from backend.verification.enums import FixtureSource, FixtureType


def _make_seg():
    return {
        "segment_id": "s1",
        "start_x": 0.0, "start_y": 0.0, "start_z": 5.0,
        "end_x": 0.0, "end_y": 0.0, "end_z": -10.0,
        "is_cutting": True, "motion_type": "FEED_LINEAR", "operation_id": "op1",
    }


def _make_vi_with_fix(fixtures, machine=None):
    segs = nc_segments_to_verification_segments([_make_seg()])
    machine_x = machine.get("travel_x_mm") if machine else None
    machine_y = machine.get("travel_y_mm") if machine else None
    machine_z = machine.get("travel_z_mm") if machine else None
    return P8VerificationInput(
        candidate_id="f001", feature_id="f001", toolpath_id="tp001",
        segments=segs,
        tool_diameter_mm=5.0,
        tool_diameter_provenance=GeometryFieldProvenance.USER_CONFIRMED,
        tool_flute_length_mm=None,
        tool_flute_length_provenance=GeometryFieldProvenance.UNKNOWN,
        tool_overall_length_mm=None,
        tool_overall_length_provenance=GeometryFieldProvenance.UNKNOWN,
        tool_cutting_length_mm=None,
        tool_cutting_length_provenance=GeometryFieldProvenance.UNKNOWN,
        holder_diameter_mm=None,
        holder_diameter_provenance=GeometryFieldProvenance.UNKNOWN,
        holder_length_mm=None,
        holder_length_provenance=GeometryFieldProvenance.UNKNOWN,
        stock_model=None,
        stock_provenance=GeometryFieldProvenance.UNKNOWN,
        fixture_inputs=fixtures,
        machine_travel_x_mm=machine_x,
        machine_travel_y_mm=machine_y,
        machine_travel_z_mm=machine_z,
        machine_travel_provenance=(
            GeometryFieldProvenance.KNOWN if machine_x else GeometryFieldProvenance.UNKNOWN
        ),
        part_bbox_min=None, part_bbox_max=None,
        part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
        verification_scope="TEST",
    )


class TestFixtureModel:
    def test_fixture_absent_returns_not_verifiable(self):
        vi = _make_vi_with_fix(fixtures=[])
        result = run_p8_verification(vi)
        assert result.fixture_collision_validated == "NOT_VERIFIABLE"
        assert result.tool_collision_validated == "NOT_VERIFIABLE"

    def test_valid_box_fixture_wired(self):
        fix = FixtureInput(
            fixture_id="vise-01", fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=100.0, min_y_mm=-40.0, min_z_mm=-5.0,
            max_x_mm=200.0, max_y_mm=40.0, max_z_mm=0.0,
        )
        vi = _make_vi_with_fix(fixtures=[fix])
        result = run_p8_verification(vi)
        # Tool at x=0, fixture at x=100-200 — no overlap → PASS
        assert result.tool_collision_validated == "PASS"
        assert result.fixture_count == 1

    def test_fixture_collision_detected(self):
        # Fixture exactly around the tool path
        fix = FixtureInput(
            fixture_id="vise-01", fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=-1.0, min_y_mm=-1.0, min_z_mm=-15.0,
            max_x_mm=1.0, max_y_mm=1.0, max_z_mm=10.0,
        )
        vi = _make_vi_with_fix(fixtures=[fix])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "FAIL"

    def test_unknown_provenance_fixture_excluded(self):
        # Fixture with UNKNOWN provenance should not contribute trustworthy geometry
        fix = FixtureInput(
            fixture_id="unknown-fix", fixture_type=FixtureType.UNKNOWN,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.UNKNOWN,
            min_x_mm=-1.0, min_y_mm=-1.0, min_z_mm=-15.0,
            max_x_mm=1.0, max_y_mm=1.0, max_z_mm=10.0,
        )
        vi = _make_vi_with_fix(fixtures=[fix])
        result = run_p8_verification(vi)
        # UNKNOWN provenance fixture not trusted → NOT_VERIFIABLE
        assert result.tool_collision_validated == "NOT_VERIFIABLE"
        assert result.fixture_count == 0

    def test_fixture_is_trustworthy_property(self):
        confirmed = FixtureInput(
            fixture_id="f1", fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=0.0, min_y_mm=0.0, min_z_mm=0.0,
            max_x_mm=10.0, max_y_mm=10.0, max_z_mm=10.0,
        )
        unknown = FixtureInput(
            fixture_id="f2", fixture_type=FixtureType.UNKNOWN,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.UNKNOWN,
            min_x_mm=0.0, min_y_mm=0.0, min_z_mm=0.0,
            max_x_mm=10.0, max_y_mm=10.0, max_z_mm=10.0,
        )
        assert confirmed.is_trustworthy is True
        assert unknown.is_trustworthy is False

    def test_to_fixture_geometry_conversion(self):
        from backend.verification.stock import FixtureGeometry
        fix = FixtureInput(
            fixture_id="vise-01", fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=-50.0, min_y_mm=-40.0, min_z_mm=-5.0,
            max_x_mm=50.0, max_y_mm=40.0, max_z_mm=0.0,
        )
        fg = fix.to_fixture_geometry()
        assert isinstance(fg, FixtureGeometry)
        assert fg.fixture_id == "vise-01"
        assert fg.min_x_mm == -50.0
        assert fg.max_z_mm == 0.0

    def test_keep_out_region_valid_box_fixture(self):
        # Clamps modeled as box fixture — valid keep-out region
        fix = FixtureInput(
            fixture_id="clamp-01", fixture_type=FixtureType.CLAMPS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=80.0, min_y_mm=-10.0, min_z_mm=-20.0,
            max_x_mm=120.0, max_y_mm=10.0, max_z_mm=0.0,
        )
        vi = _make_vi_with_fix(fixtures=[fix])
        result = run_p8_verification(vi)
        # Tool at x=0, clamp at x=80-120 → no collision
        assert result.tool_collision_validated == "PASS"

    def test_no_invented_fixture_coordinates(self):
        """Fixture with explicit zeros is valid; must not be auto-populated."""
        cand_class = type("Cand", (), {
            "feature_id": "f001",
            "tool_diameter_mm": 5.0,
            "nc_segments": [_make_seg()],
            "toolpath_id": "tp001",
        })()
        vi = build_verification_input(candidate=cand_class)
        # No fixtures should be auto-populated
        assert vi.fixture_inputs == []
