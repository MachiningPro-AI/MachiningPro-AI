"""P8 Safety Tests (MUST 47, MUST 50).

Required:
  is_dispatchable=False
  production_released=False
  real_machine_write=False
  auto_dispatch=False
  auto_approval=False
"""

from __future__ import annotations

from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    P8VerificationInput,
    P8VerificationResult,
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


def _make_vi(with_machine=False, with_fixture=False, with_flute=False):
    segs = nc_segments_to_verification_segments([_make_seg()])
    machine_x = 762.0 if with_machine else None
    machine_y = 406.0 if with_machine else None
    machine_z = 508.0 if with_machine else None
    fixtures = []
    if with_fixture:
        fixtures.append(FixtureInput(
            fixture_id="vise-01", fixture_type=FixtureType.VISE_JAWS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
            min_x_mm=100.0, min_y_mm=-40.0, min_z_mm=-5.0,
            max_x_mm=200.0, max_y_mm=40.0, max_z_mm=0.0,
        ))
    return P8VerificationInput(
        candidate_id="f001", feature_id="f001", toolpath_id="tp001",
        segments=segs,
        tool_diameter_mm=5.0,
        tool_diameter_provenance=GeometryFieldProvenance.USER_CONFIRMED,
        tool_flute_length_mm=20.0 if with_flute else None,
        tool_flute_length_provenance=(
            GeometryFieldProvenance.KNOWN if with_flute else GeometryFieldProvenance.UNKNOWN
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
        fixture_inputs=fixtures,
        machine_travel_x_mm=machine_x,
        machine_travel_y_mm=machine_y,
        machine_travel_z_mm=machine_z,
        machine_travel_provenance=(
            GeometryFieldProvenance.KNOWN if with_machine else GeometryFieldProvenance.UNKNOWN
        ),
        part_bbox_min=None, part_bbox_max=None,
        part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
        verification_scope="TEST",
    )


class TestP8SafetyInvariants:
    def test_is_dispatchable_false_minimal(self):
        vi = _make_vi()
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_is_dispatchable_false_with_machine(self):
        vi = _make_vi(with_machine=True)
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_is_dispatchable_false_with_fixture(self):
        vi = _make_vi(with_machine=True, with_fixture=True)
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_is_dispatchable_false_all_checks_pass(self):
        vi = _make_vi(with_machine=True, with_fixture=True, with_flute=True)
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_production_released_false_minimal(self):
        vi = _make_vi()
        result = run_p8_verification(vi)
        assert result.production_released is False

    def test_production_released_false_with_machine(self):
        vi = _make_vi(with_machine=True, with_fixture=True, with_flute=True)
        result = run_p8_verification(vi)
        assert result.production_released is False

    def test_post_init_enforces_dispatchable(self):
        """__post_init__ must override any attempt to set is_dispatchable=True."""
        vi = _make_vi()
        result = run_p8_verification(vi)
        # Attempt to override — must be rejected
        try:
            object.__setattr__(result, "is_dispatchable", True)
        except Exception:
            pass
        # Confirm the enforced value: even if setattr worked, the model design forbids True
        # We test this via the dataclass post_init
        result2 = P8VerificationResult(
            candidate_id="f001", feature_id="f001", toolpath_id=None,
            verification_scope="TEST",
            geometry_verification_ready=False,
            tool_reach_validated="NOT_VERIFIABLE",
            machine_envelope_validated="NOT_VERIFIABLE",
            tool_collision_validated="NOT_VERIFIABLE",
            holder_collision_validated="NOT_VERIFIABLE",
            fixture_collision_validated="NOT_VERIFIABLE",
            stock_removal_validated="NOT_VERIFIABLE",
            gouge_validated="NOT_VERIFIABLE",
            simulation_result=None,
            tool_diameter_provenance=GeometryFieldProvenance.UNKNOWN,
            tool_flute_length_provenance=GeometryFieldProvenance.UNKNOWN,
            machine_travel_provenance=GeometryFieldProvenance.UNKNOWN,
            fixture_count=0,
            part_bbox_provenance=GeometryFieldProvenance.UNKNOWN,
            stock_provenance=GeometryFieldProvenance.UNKNOWN,
            is_dispatchable=True,  # attempt to set True
            production_released=True,  # attempt to set True
        )
        # post_init must reset both to False
        assert result2.is_dispatchable is False
        assert result2.production_released is False

    def test_no_real_machine_write_in_adapter_module(self):
        """Grep: no is_real_machine_write=True in verification_adapter.py."""
        import pathlib
        src = pathlib.Path(
            "D:/makina_ogrenmesi/MachiningPro_AI_NEXT/backend/manufacturing/verification_adapter.py"
        ).read_text()
        assert "is_real_machine_write=True" not in src
        assert "is_real_machine_write = True" not in src

    def test_no_auto_dispatch_in_adapter_module(self):
        import pathlib
        src = pathlib.Path(
            "D:/makina_ogrenmesi/MachiningPro_AI_NEXT/backend/manufacturing/verification_adapter.py"
        ).read_text()
        assert "auto_dispatch=True" not in src
        assert "auto_dispatch = True" not in src

    def test_no_auto_approval_in_adapter_module(self):
        import pathlib
        src = pathlib.Path(
            "D:/makina_ogrenmesi/MachiningPro_AI_NEXT/backend/manufacturing/verification_adapter.py"
        ).read_text()
        assert "auto_approval=True" not in src
        assert "auto_approval = True" not in src

    def test_no_production_released_true_in_adapter_module(self):
        import pathlib
        src = pathlib.Path(
            "D:/makina_ogrenmesi/MachiningPro_AI_NEXT/backend/manufacturing/verification_adapter.py"
        ).read_text()
        assert "production_released=True" not in src
        assert "production_released = True" not in src

    def test_no_is_dispatchable_true_in_adapter_module(self):
        import pathlib
        src = pathlib.Path(
            "D:/makina_ogrenmesi/MachiningPro_AI_NEXT/backend/manufacturing/verification_adapter.py"
        ).read_text()
        assert "is_dispatchable=True" not in src
        assert "is_dispatchable = True" not in src

    def test_verified_state_does_not_set_dispatchable(self):
        """VERIFIED verification state must NOT imply dispatchable."""
        vi = _make_vi(with_machine=True, with_flute=True)
        result = run_p8_verification(vi)
        # Even if envelope check passes → dispatchable stays False
        assert result.is_dispatchable is False

    def test_build_verification_input_candidate_no_nc_candidate_review_ready_bypass(self):
        """build_verification_input does not set any nc_candidate_review_ready flag."""
        cand = type("Cand", (), {
            "feature_id": "f001",
            "tool_diameter_mm": 5.0,
            "nc_segments": [_make_seg()],
            "toolpath_id": "tp001",
        })()
        vi = build_verification_input(candidate=cand)
        # P8VerificationInput has no nc_candidate_review_ready attribute
        assert not hasattr(vi, "nc_candidate_review_ready")
