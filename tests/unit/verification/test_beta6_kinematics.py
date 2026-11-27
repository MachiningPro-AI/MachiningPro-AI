"""Phases R/S/T — Kinematic model, axis solution, limit verification tests."""

import pytest
from backend.verification.machine_kinematics import (
    MachineArchitecture,
    AxisLimit,
    MachineKinematicModel,
    MachineLimitVerificationResult,
    AxisSolutionResult,
    build_kinematic_model_from_catalog,
    build_test_only_kinematic_model,
    solve_axis_positions_3axis,
    verify_machine_limits,
)


# ---------------------------------------------------------------------------
# Phase R — Kinematic model building
# ---------------------------------------------------------------------------

class TestBuildTestOnlyModel:
    def test_returns_model(self):
        m = build_test_only_kinematic_model(
            machine_id="TEST-VMC",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )
        assert isinstance(m, MachineKinematicModel)

    def test_test_only_flag_set(self):
        m = build_test_only_kinematic_model(
            machine_id="TEST-VMC",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )
        assert m.test_only is True

    def test_source_is_test_only(self):
        m = build_test_only_kinematic_model(
            machine_id="TEST-VMC",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )
        assert m.source == "TEST_ONLY"

    def test_linear_axes_populated(self):
        m = build_test_only_kinematic_model(
            machine_id="TEST-VMC",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )
        lm = m.axis_limit_map()
        assert "X" in lm
        assert "Y" in lm
        assert "Z" in lm
        assert lm["X"] == (-500.0, 500.0)
        assert lm["Z"] == (-300.0, 0.0)

    def test_rotary_axes_optional(self):
        m = build_test_only_kinematic_model(
            machine_id="TEST-5AX",
            architecture=MachineArchitecture.FIVE_AXIS_TABLE_TABLE,
            x_range=(-400.0, 400.0),
            y_range=(-300.0, 300.0),
            z_range=(-500.0, 0.0),
            a_range=(-110.0, 110.0),
            b_range=(-360.0, 360.0),
        )
        lm = m.axis_limit_map()
        assert "A" in lm
        assert lm["A"] == (-110.0, 110.0)

    def test_3axis_no_rotary(self):
        m = build_test_only_kinematic_model(
            machine_id="TEST-3AX",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )
        lm = m.axis_limit_map()
        assert "A" not in lm
        assert "B" not in lm
        assert "C" not in lm


class TestBuildFromCatalog:
    def _make_envelope(self, x=600.0, y=500.0, z=450.0,
                       min_angle=None, max_angle=None):
        from types import SimpleNamespace
        return SimpleNamespace(
            travel_x_mm=x, travel_y_mm=y, travel_z_mm=z,
            min_angle_deg=min_angle, max_angle_deg=max_angle,
        )

    def test_3axis_vmc_builds(self):
        m = build_kinematic_model_from_catalog(
            machine_id="CAT-VMC",
            machine_class_value="3_AXIS_VMC",
            envelope=self._make_envelope(),
            source="CATALOG",
        )
        assert isinstance(m, MachineKinematicModel)
        assert m.test_only is False

    def test_linear_axes_from_travel(self):
        m = build_kinematic_model_from_catalog(
            machine_id="CAT-VMC",
            machine_class_value="3_AXIS_VMC",
            envelope=self._make_envelope(x=762.0, y=508.0, z=508.0),
            source="CATALOG",
        )
        lm = m.axis_limit_map()
        assert "X" in lm
        assert lm["X"][1] - lm["X"][0] == pytest.approx(762.0, rel=1e-3)

    def test_no_fabricated_rotary_limits(self):
        m = build_kinematic_model_from_catalog(
            machine_id="CAT-5AX",
            machine_class_value="5_AXIS_VMC",
            envelope=self._make_envelope(),
            source="CATALOG",
        )
        lm = m.axis_limit_map()
        # rotary limits must NOT be invented
        for axis in ("A", "B", "C"):
            if axis in lm:
                pytest.fail(f"Rotary axis {axis} fabricated without catalog data")

    def test_hmc_architecture_mapped(self):
        m = build_kinematic_model_from_catalog(
            machine_id="CAT-HMC",
            machine_class_value="HMC",
            envelope=self._make_envelope(),
            source="CATALOG",
        )
        assert m.architecture == MachineArchitecture.THREE_AXIS_HMC


# ---------------------------------------------------------------------------
# Phase S — Axis solution
# ---------------------------------------------------------------------------

class TestSolveAxisPositions:
    def test_pass_status(self):
        r = solve_axis_positions_3axis(x_mm=10.0, y_mm=20.0, z_mm=-5.0)
        assert r.status == "PASS"

    def test_xyz_passthrough(self):
        r = solve_axis_positions_3axis(x_mm=12.5, y_mm=33.0, z_mm=-8.0)
        assert r.x_mm == pytest.approx(12.5)
        assert r.y_mm == pytest.approx(33.0)
        assert r.z_mm == pytest.approx(-8.0)

    def test_rotary_none_for_3axis(self):
        r = solve_axis_positions_3axis(x_mm=0.0, y_mm=0.0, z_mm=0.0)
        # 3-axis solution: rotary axes not solved → None (not fabricated)
        assert r.a_deg is None
        assert r.b_deg is None
        assert r.c_deg is None

    def test_method_documented(self):
        r = solve_axis_positions_3axis(x_mm=0.0, y_mm=0.0, z_mm=0.0)
        assert r.kinematic_method is not None and len(r.kinematic_method) > 0

    def test_pose_id_returned(self):
        r = solve_axis_positions_3axis(x_mm=0.0, y_mm=0.0, z_mm=0.0, pose_id="P1")
        assert r.pose_id == "P1"


# ---------------------------------------------------------------------------
# Phase T — Machine limit verification
# ---------------------------------------------------------------------------

class TestVerifyMachineLimits:
    def _model(self):
        return build_test_only_kinematic_model(
            machine_id="TEST",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )

    def test_all_within_limits_pass(self):
        segs = [
            {"x": 0.0, "y": 0.0, "z": -10.0},
            {"x": 100.0, "y": 50.0, "z": -20.0},
        ]
        r = verify_machine_limits(self._model(), segs)
        assert isinstance(r, MachineLimitVerificationResult)
        assert r.status == "PASS"
        assert r.violations == []

    def test_overtravel_detected(self):
        segs = [
            {"x": 600.0, "y": 0.0, "z": -10.0},  # X overtravel
        ]
        r = verify_machine_limits(self._model(), segs)
        assert r.status == "FAIL"
        assert any(v.axis == "X" for v in r.violations)

    def test_violation_has_excess(self):
        segs = [{"x": 600.0, "y": 0.0, "z": -10.0}]
        r = verify_machine_limits(self._model(), segs)
        v = next(v for v in r.violations if v.axis == "X")
        assert v.excess > 0.0

    def test_singularity_not_implemented(self):
        r = verify_machine_limits(self._model(), [{"x": 0.0, "y": 0.0, "z": -10.0}])
        assert r.singularity_check == "NOT_IMPLEMENTED"

    def test_empty_segments_pass(self):
        r = verify_machine_limits(self._model(), [])
        assert r.status == "PASS"
        assert r.segments_checked == 0

    def test_no_limits_model_not_verifiable(self):
        from dataclasses import replace
        m = self._model()
        # Remove all axis limits
        from backend.verification.machine_kinematics import MachineKinematicModel
        m2 = MachineKinematicModel(
            machine_id="NO-LIMITS",
            architecture=MachineArchitecture.UNKNOWN,
            axis_count=3,
            axis_limits=[],
            home_position={},
            test_only=True,
            source="TEST_ONLY",
            provenance="test",
        )
        r = verify_machine_limits(m2, [{"x": 9999.0, "y": 9999.0, "z": 9999.0}])
        assert r.status in ("NOT_PERFORMED", "NOT_VERIFIABLE")

    def test_axes_checked_count(self):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0}]
        r = verify_machine_limits(self._model(), segs)
        assert len(r.axes_checked) >= 3

    def test_multiple_violations(self):
        segs = [{"x": 600.0, "y": 500.0, "z": 100.0}]  # X+Y+Z overtravel
        r = verify_machine_limits(self._model(), segs)
        assert r.status == "FAIL"
        assert len(r.violations) >= 2

    def test_provenance_set(self):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0}]
        r = verify_machine_limits(self._model(), segs, operation_id="OP-01")
        assert r.provenance is not None
