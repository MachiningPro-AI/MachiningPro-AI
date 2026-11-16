"""P8-E Tests: Machine envelope validation (MUST 45)."""

from __future__ import annotations

from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    P8VerificationInput,
    build_verification_input,
    nc_segments_to_verification_segments,
    run_p8_verification,
)


def _seg(sx, sy, sz, ex, ey, ez, is_cutting=False):
    return {
        "segment_id": "s1",
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "is_cutting": is_cutting,
        "motion_type": "FEED_LINEAR" if is_cutting else "RAPID_LINEAR",
        "operation_id": "op1",
    }


def _make_vi(segs, travel_x=None, travel_y=None, travel_z=None):
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
        fixture_inputs=[],
        machine_travel_x_mm=travel_x,
        machine_travel_y_mm=travel_y,
        machine_travel_z_mm=travel_z,
        machine_travel_provenance=(
            GeometryFieldProvenance.KNOWN if travel_x is not None
            else GeometryFieldProvenance.UNKNOWN
        ),
        part_bbox_min=None, part_bbox_max=None,
        part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
        verification_scope="TEST",
    )


class TestMachineEnvelope:
    def test_inside_x_y_z_range(self):
        segs = nc_segments_to_verification_segments([_seg(0, 0, 5, 0, 0, -10)])
        vi = _make_vi(segs, travel_x=762.0, travel_y=406.0, travel_z=508.0)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "PASS"

    def test_x_overflow(self):
        segs = nc_segments_to_verification_segments([_seg(500, 0, 5, 500, 0, -10)])
        vi = _make_vi(segs, travel_x=200.0, travel_y=406.0, travel_z=508.0)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "FAIL"

    def test_y_overflow(self):
        segs = nc_segments_to_verification_segments([_seg(0, 300, 5, 0, 300, -10)])
        vi = _make_vi(segs, travel_x=762.0, travel_y=200.0, travel_z=508.0)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "FAIL"

    def test_z_overflow(self):
        # travel_z=50 means z limit is -50; going to z=-100 fails
        segs = nc_segments_to_verification_segments([_seg(0, 0, 5, 0, 0, -100)])
        vi = _make_vi(segs, travel_x=762.0, travel_y=406.0, travel_z=50.0)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "FAIL"

    def test_unknown_axis_travel_returns_insufficient_data(self):
        segs = nc_segments_to_verification_segments([_seg(0, 0, 5, 0, 0, -10)])
        vi = _make_vi(segs, travel_x=None, travel_y=None, travel_z=None)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "INSUFFICIENT_DATA"

    def test_boundary_condition_at_exact_limit(self):
        # half_x = 381mm; point at x=381 is exactly at limit — should pass
        segs = nc_segments_to_verification_segments([_seg(381, 0, 5, 381, 0, -10)])
        vi = _make_vi(segs, travel_x=762.0, travel_y=406.0, travel_z=508.0)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "PASS"

    def test_static_selection_pass_does_not_imply_envelope_pass(self):
        """Machine selection PASS (capacity check) is NOT envelope validation."""
        # Build a candidate with machine_id but no travel extracted
        cand = type("Cand", (), {
            "feature_id": "f001",
            "tool_diameter_mm": 5.0,
            "nc_segments": [_seg(0, 0, 5, 0, 0, -10)],
            "toolpath_id": "tp001",
        })()
        machine_no_travel = {"stable_id": "haas-vf-2ss", "travel_x_mm": None}
        vi = build_verification_input(candidate=cand, machine_record=machine_no_travel)
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "INSUFFICIENT_DATA"

    def test_p8e_haas_vf2ss_has_travel(self):
        """Confirm haas-vf-2ss has travel data in machine catalog."""
        from backend.machines.seed_catalog import seed_machine_catalog
        machines = seed_machine_catalog()
        haas = next((m for m in machines if m.get("stable_id") == "haas-vf-2ss"), None)
        assert haas is not None
        assert haas["travel_x_mm"] == 762.0
        assert haas["travel_y_mm"] == 406.0
        assert haas["travel_z_mm"] == 508.0

    def test_p8e_dxf01_path_inside_vf2ss_envelope(self):
        """DXF-01 hole coordinates are well inside a Haas VF-2SS travel envelope."""
        # DXF-01 holes are ~40x40mm spread; Haas travel 762x406x508mm
        from backend.machines.seed_catalog import seed_machine_catalog
        machines = seed_machine_catalog()
        haas = next(m for m in machines if m.get("stable_id") == "haas-vf-2ss")
        segs = nc_segments_to_verification_segments([
            _seg(20, 15, 5, 20, 15, -10),
            _seg(-20, -15, 5, -20, -15, -10),
        ])
        vi = _make_vi(
            segs,
            travel_x=haas["travel_x_mm"],
            travel_y=haas["travel_y_mm"],
            travel_z=haas["travel_z_mm"],
        )
        result = run_p8_verification(vi)
        assert result.machine_envelope_validated == "PASS"
