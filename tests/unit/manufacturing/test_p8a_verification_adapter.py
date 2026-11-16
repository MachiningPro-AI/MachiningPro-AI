"""
P8-A Tests: Verification adapter — OfflineNCCandidate → VerificationInput.

MUST 42: adapter, missing WCS, missing stock, missing holder, missing fixture,
         unknown tool geometry, provenance preservation.
"""

from __future__ import annotations

from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    P8VerificationInput,
    build_verification_input,
    nc_segments_to_verification_segments,
    run_p8_verification,
    stock_definition_to_stock_model,
)
from backend.verification.enums import FixtureSource, FixtureType

# ---------------------------------------------------------------------------
# Minimal candidate stub — mirrors OfflineNCCandidate fields used by adapter
# ---------------------------------------------------------------------------


class _Candidate:
    def __init__(
        self, feature_id="f001", tool_diameter_mm=5.0, nc_segments=None, toolpath_id="tp001"
    ):
        self.feature_id = feature_id
        self.tool_diameter_mm = tool_diameter_mm
        self.nc_segments = nc_segments or []
        self.toolpath_id = toolpath_id


def _make_seg_dict(
    sx=0.0, sy=0.0, sz=5.0, ex=0.0, ey=0.0, ez=-10.0,
    is_cutting=True, motion_type="FEED_LINEAR",
):
    return {
        "segment_id": "seg-001",
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "is_cutting": is_cutting,
        "motion_type": motion_type,
        "operation_id": "op-001",
        "tool_id": "tool-001",
        "feature_id": "f001",
    }


# ---------------------------------------------------------------------------
# nc_segments_to_verification_segments
# ---------------------------------------------------------------------------


class TestNcSegmentConversion:
    def test_valid_cutting_segment(self):
        segs = nc_segments_to_verification_segments([_make_seg_dict()])
        assert len(segs) == 1
        s = segs[0]
        assert s.is_cutting is True
        assert s.motion_type == "CUT"
        assert s.start_z == 5.0
        assert s.end_z == -10.0

    def test_valid_rapid_segment(self):
        segs = nc_segments_to_verification_segments([
            _make_seg_dict(is_cutting=False, motion_type="RAPID_LINEAR")
        ])
        assert len(segs) == 1
        assert segs[0].motion_type == "RAPID"
        assert segs[0].is_cutting is False

    def test_helix_segment(self):
        d = _make_seg_dict(motion_type="HELIX", is_cutting=True)
        segs = nc_segments_to_verification_segments([d])
        assert len(segs) == 1
        assert segs[0].motion_type == "CUT"

    def test_missing_coordinates_skipped(self):
        d = {"segment_id": "s1", "is_cutting": True, "motion_type": "FEED_LINEAR"}
        segs = nc_segments_to_verification_segments([d])
        assert segs == []

    def test_mixed_valid_invalid(self):
        good = _make_seg_dict()
        bad = {"segment_id": "s2", "is_cutting": False}
        segs = nc_segments_to_verification_segments([good, bad])
        assert len(segs) == 1

    def test_empty_input(self):
        assert nc_segments_to_verification_segments([]) == []

    def test_provenance_preserved(self):
        d = _make_seg_dict()
        d["tool_id"] = "my-tool"
        d["feature_id"] = "feat-99"
        segs = nc_segments_to_verification_segments([d])
        assert segs[0].tool_id == "my-tool"
        assert segs[0].feature_id == "feat-99"


# ---------------------------------------------------------------------------
# build_verification_input
# ---------------------------------------------------------------------------


class TestBuildVerificationInput:
    def test_valid_candidate_with_segments(self):
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand)
        assert isinstance(vi, P8VerificationInput)
        assert len(vi.segments) == 1
        assert vi.tool_diameter_mm == 5.0
        assert vi.tool_diameter_provenance == GeometryFieldProvenance.USER_CONFIRMED

    def test_missing_tool_diameter(self):
        cand = _Candidate(tool_diameter_mm=None, nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand)
        assert vi.tool_diameter_mm is None
        assert vi.tool_diameter_provenance == GeometryFieldProvenance.UNKNOWN
        assert any("TOOL_DIAMETER_UNKNOWN" in w for w in vi.provenance_notes or [])

    def test_no_segments(self):
        cand = _Candidate(nc_segments=[])
        vi = build_verification_input(candidate=cand)
        assert vi.segments == []

    def test_machine_travel_wired(self):
        machine = {"travel_x_mm": 762.0, "travel_y_mm": 406.0, "travel_z_mm": 508.0}
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, machine_record=machine)
        assert vi.machine_travel_x_mm == 762.0
        assert vi.machine_travel_y_mm == 406.0
        assert vi.machine_travel_z_mm == 508.0
        assert vi.machine_travel_provenance == GeometryFieldProvenance.KNOWN

    def test_machine_missing_travel(self):
        machine = {"travel_x_mm": None, "travel_y_mm": None, "travel_z_mm": None}
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, machine_record=machine)
        assert vi.machine_travel_x_mm is None
        assert vi.machine_travel_provenance == GeometryFieldProvenance.UNKNOWN

    def test_fixture_input_wired(self):
        fix = FixtureInput(
            fixture_id="vise-01",
            fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=-50.0, min_y_mm=-40.0, min_z_mm=-5.0,
            max_x_mm=50.0, max_y_mm=40.0, max_z_mm=0.0,
        )
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        assert len(vi.fixture_inputs) == 1
        assert vi.fixture_inputs[0].fixture_id == "vise-01"

    def test_no_fixture(self):
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand)
        assert vi.fixture_inputs == []

    def test_holder_always_unknown(self):
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand)
        assert vi.holder_diameter_mm is None
        assert vi.holder_diameter_provenance == GeometryFieldProvenance.UNKNOWN
        assert vi.holder_length_mm is None

    def test_part_bbox_always_unknown_from_dxf(self):
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand)
        assert vi.part_bbox_min is None
        assert vi.part_bbox_max is None
        assert vi.part_bbox_provenance == GeometryFieldProvenance.UNKNOWN

    def test_flute_length_from_tool_record(self):
        class _ToolRecord:
            stable_id = "sandvik-860-1-0500-026a1-pm"
            flute_length_mm = 20.0
            overall_length_mm = 74.0
            cutting_length_mm = 26.0

        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, tool_record=_ToolRecord())
        assert vi.tool_flute_length_mm == 20.0
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.KNOWN

    def test_flute_length_unknown_when_not_in_catalog(self):
        class _ToolRecord:
            stable_id = "sandvik-860-1-0800-040a1-pm"
            flute_length_mm = None
            overall_length_mm = 79.0
            cutting_length_mm = 28.0

        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, tool_record=_ToolRecord())
        assert vi.tool_flute_length_mm is None
        assert vi.tool_flute_length_provenance == GeometryFieldProvenance.UNKNOWN

    def test_verification_scope_no_geometry(self):
        cand = _Candidate(nc_segments=[])
        vi = build_verification_input(candidate=cand)
        assert "NO_GEOMETRY" in vi.verification_scope

    def test_verification_scope_with_segments_no_fixture(self):
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand)
        assert "CLEARANCE_CHECK_2_5D" in vi.verification_scope
        assert "TOOLPATH_WIRED" in vi.verification_scope

    def test_verification_scope_with_machine(self):
        machine = {"travel_x_mm": 762.0, "travel_y_mm": 406.0, "travel_z_mm": 508.0}
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, machine_record=machine)
        assert "STATIC_ENVELOPE_CHECK" in vi.verification_scope

    def test_verification_scope_with_fixture(self):
        fix = FixtureInput(
            fixture_id="f1", fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=-50.0, min_y_mm=-40.0, min_z_mm=-5.0,
            max_x_mm=50.0, max_y_mm=40.0, max_z_mm=0.0,
        )
        cand = _Candidate(nc_segments=[_make_seg_dict()])
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        assert "TOOL_COLLISION_CHECK" in vi.verification_scope


# ---------------------------------------------------------------------------
# stock_definition_to_stock_model
# ---------------------------------------------------------------------------


class TestStockDefinitionToStockModel:
    def test_rectangular_block(self):
        from backend.manufacturing.setup_stock import StockDefinition, StockShape
        stock = StockDefinition(
            stock_id="s1", shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45", length_mm=100.0, width_mm=80.0, height_mm=20.0
        )
        model = stock_definition_to_stock_model(stock)
        assert model is not None
        assert model.has_box_dims
        assert model.min_x_mm == -50.0
        assert model.max_x_mm == 50.0
        assert model.min_z_mm == -20.0
        assert model.max_z_mm == 0.0

    def test_round_bar(self):
        from backend.manufacturing.setup_stock import StockDefinition, StockShape
        stock = StockDefinition(
            stock_id="s2", shape=StockShape.ROUND_BAR,
            material_grade="C45", outer_diameter_mm=50.0, length_mm=100.0
        )
        model = stock_definition_to_stock_model(stock)
        assert model is not None
        assert model.has_cylinder_dims
        assert model.radius_mm == 25.0

    def test_incomplete_stock_returns_none(self):
        from backend.manufacturing.setup_stock import StockDefinition, StockShape
        stock = StockDefinition(
            stock_id="s3", shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45", length_mm=100.0
            # width_mm and height_mm missing
        )
        model = stock_definition_to_stock_model(stock)
        assert model is None

    def test_none_input_returns_none(self):
        assert stock_definition_to_stock_model(None) is None


# ---------------------------------------------------------------------------
# run_p8_verification
# ---------------------------------------------------------------------------


class TestRunP8Verification:
    def _make_input(self, segments=None, machine=None, fixtures=None, flute_len=None):
        from backend.manufacturing.verification_adapter import P8VerificationInput
        segs = segments if segments is not None else [
            *nc_segments_to_verification_segments([_make_seg_dict()])
        ]
        fix_list = fixtures or []
        machine_x = machine.get("travel_x_mm") if machine else None
        machine_y = machine.get("travel_y_mm") if machine else None
        machine_z = machine.get("travel_z_mm") if machine else None
        travel_prov = (
            GeometryFieldProvenance.KNOWN if machine_x else GeometryFieldProvenance.UNKNOWN
        )
        return P8VerificationInput(
            candidate_id="f001",
            feature_id="f001",
            toolpath_id="tp001",
            segments=segs,
            tool_diameter_mm=5.0,
            tool_diameter_provenance=GeometryFieldProvenance.USER_CONFIRMED,
            tool_flute_length_mm=flute_len,
            tool_flute_length_provenance=(
                GeometryFieldProvenance.KNOWN if flute_len else GeometryFieldProvenance.UNKNOWN
            ),
            tool_overall_length_mm=74.0,
            tool_overall_length_provenance=GeometryFieldProvenance.KNOWN,
            tool_cutting_length_mm=26.0,
            tool_cutting_length_provenance=GeometryFieldProvenance.KNOWN,
            holder_diameter_mm=None,
            holder_diameter_provenance=GeometryFieldProvenance.UNKNOWN,
            holder_length_mm=None,
            holder_length_provenance=GeometryFieldProvenance.UNKNOWN,
            stock_model=None,
            stock_provenance=GeometryFieldProvenance.UNKNOWN,
            fixture_inputs=fix_list,
            machine_travel_x_mm=machine_x,
            machine_travel_y_mm=machine_y,
            machine_travel_z_mm=machine_z,
            machine_travel_provenance=travel_prov,
            part_bbox_min=None,
            part_bbox_max=None,
            part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
            verification_scope="CLEARANCE_CHECK_2_5D",
        )

    def test_no_segments_returns_not_verifiable(self):
        vi = self._make_input(segments=[])
        result = run_p8_verification(vi)
        assert result.geometry_verification_ready is False
        assert result.tool_reach_validated == "NOT_VERIFIABLE"
        assert result.machine_envelope_validated == "NOT_VERIFIABLE"

    def test_is_dispatchable_always_false(self):
        vi = self._make_input()
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_production_released_always_false(self):
        vi = self._make_input()
        result = run_p8_verification(vi)
        assert result.production_released is False

    def test_tool_reach_insufficient_data_when_flute_unknown(self):
        vi = self._make_input(flute_len=None)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "INSUFFICIENT_DATA"

    def test_tool_reach_pass_when_depth_within_flute(self):
        # Segment depth = 10mm; flute_length = 20mm → PASS
        segs = nc_segments_to_verification_segments([_make_seg_dict(sz=5.0, ez=-5.0)])
        vi = self._make_input(segments=segs, flute_len=20.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "PASS"

    def test_tool_reach_fail_when_depth_exceeds_flute(self):
        # depth = 100mm (sz=5, ez=-95), flute = 20mm
        segs = nc_segments_to_verification_segments([_make_seg_dict(sz=5.0, ez=-95.0)])
        vi = self._make_input(segments=segs, flute_len=20.0)
        result = run_p8_verification(vi)
        assert result.tool_reach_validated == "FAIL"

    def test_no_fixture_collision_not_verifiable(self):
        vi = self._make_input(fixtures=[])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "NOT_VERIFIABLE"
        assert result.fixture_collision_validated == "NOT_VERIFIABLE"

    def test_holder_collision_not_verifiable_no_holder(self):
        vi = self._make_input()
        result = run_p8_verification(vi)
        assert result.holder_collision_validated == "NOT_VERIFIABLE"

    def test_gouge_not_verifiable_no_part_bbox(self):
        vi = self._make_input()
        result = run_p8_verification(vi)
        assert result.gouge_validated == "NOT_VERIFIABLE"

    def test_stock_not_verifiable_without_stock(self):
        vi = self._make_input()
        result = run_p8_verification(vi)
        assert result.stock_removal_validated == "NOT_VERIFIABLE"

    def test_machine_envelope_insufficient_data_no_travel(self):
        vi = self._make_input(machine=None)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "INSUFFICIENT_DATA"

    def test_machine_envelope_pass_inside_travel(self):
        # Segment coords: x=0, y=0, z within -50 to +5 mm; travel 762/406/508
        machine = {"travel_x_mm": 762.0, "travel_y_mm": 406.0, "travel_z_mm": 508.0}
        vi = self._make_input(machine=machine)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "PASS"

    def test_machine_envelope_fail_outside_travel(self):
        # Segment X = 1000 mm — well outside travel_x=762
        segs = nc_segments_to_verification_segments([
            _make_seg_dict(sx=1000.0, sy=0.0, sz=5.0, ex=1000.0, ey=0.0, ez=-10.0)
        ])
        machine = {"travel_x_mm": 762.0, "travel_y_mm": 406.0, "travel_z_mm": 508.0}
        vi = self._make_input(segments=segs, machine=machine)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "FAIL"

    def test_fixture_collision_pass_when_no_overlap(self):
        # Tool at x=0, fixture far away at x=200
        fix = FixtureInput(
            fixture_id="vise-01",
            fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=180.0, min_y_mm=-40.0, min_z_mm=-30.0,
            max_x_mm=220.0, max_y_mm=40.0, max_z_mm=0.0,
        )
        segs = nc_segments_to_verification_segments([_make_seg_dict()])
        vi = self._make_input(segments=segs, fixtures=[fix])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "PASS"

    def test_geometry_verification_ready_when_at_least_one_check_passes(self):
        machine = {"travel_x_mm": 762.0, "travel_y_mm": 406.0, "travel_z_mm": 508.0}
        vi = self._make_input(machine=machine)
        result = run_p8_verification(vi)
        assert result.geometry_verification_ready is True

    def test_simulation_result_attached(self):
        machine = {"travel_x_mm": 762.0, "travel_y_mm": 406.0, "travel_z_mm": 508.0}
        vi = self._make_input(machine=machine)
        result = run_p8_verification(vi)
        assert result.simulation_result is not None
