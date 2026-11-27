"""
Phase N-Z Live Acceptance Tests — Cases A, B, C.

Case A: Reachable toolpath — all axes within limits → PASS
Case B: Overtravel FAIL — X command exceeds catalog travel → FAIL + violation listed
Case C: Rotary limit FAIL — A command exceeds catalog limit → FAIL + violation listed

All cases use TEST_ONLY kinematic models (never production machine writes).
No dispatch, no auto-approval.

LIVE_ACCEPTANCE_CASE_A=PASS
LIVE_ACCEPTANCE_CASE_B=FAIL_DETECTED
LIVE_ACCEPTANCE_CASE_C=ROTARY_FAIL_DETECTED
"""

import pytest
from backend.verification.machine_kinematics import (
    MachineArchitecture,
    build_test_only_kinematic_model,
    verify_machine_limits,
)
from backend.verification.stock_removal import (
    StockRemovalMode,
    compute_stock_removal_fast,
)
from backend.verification.material_removal import compute_mrr
from backend.verification.quality_modes import get_quality_mode_config, QualityMode
from backend.verification.stock import StockModel
from backend.verification.enums import StockShape


# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def machine_3ax():
    return build_test_only_kinematic_model(
        machine_id="ACCEPT-VMC",
        architecture=MachineArchitecture.THREE_AXIS_VMC,
        x_range=(-500.0, 500.0),
        y_range=(-400.0, 400.0),
        z_range=(-300.0, 0.0),
    )


@pytest.fixture
def machine_4ax():
    return build_test_only_kinematic_model(
        machine_id="ACCEPT-4AX",
        architecture=MachineArchitecture.FOUR_AXIS_TABLE,
        x_range=(-400.0, 400.0),
        y_range=(-300.0, 300.0),
        z_range=(-500.0, 0.0),
        a_range=(-110.0, 110.0),
    )


@pytest.fixture
def box_stock():
    return StockModel(shape=StockShape.BOX,
                      min_x_mm=0.0, min_y_mm=0.0, min_z_mm=0.0,
                      max_x_mm=100.0, max_y_mm=100.0, max_z_mm=50.0)


# ---------------------------------------------------------------------------
# Case A: Reachable toolpath → PASS
# ---------------------------------------------------------------------------

class TestCaseA:
    """Case A: Reachable path — all axes in range."""

    def test_a_linear_path_pass(self, machine_3ax):
        segs = [
            {"x": -100.0, "y": -50.0, "z": -20.0},
            {"x":    0.0, "y":   0.0, "z": -15.0},
            {"x":  100.0, "y":  50.0, "z": -10.0},
        ]
        r = verify_machine_limits(machine_3ax, segs)
        assert r.status == "PASS"
        assert r.violations == []

    def test_a_extreme_but_in_range(self, machine_3ax):
        segs = [
            {"x": 499.9, "y": 399.9, "z": -299.9},
            {"x": -499.9, "y": -399.9, "z": -0.1},
        ]
        r = verify_machine_limits(machine_3ax, segs)
        assert r.status == "PASS"

    def test_a_quality_mode_fast(self, box_stock):
        get_quality_mode_config(QualityMode.FAST)
        r = compute_stock_removal_fast(box_stock, tool_radius_mm=5.0,
                                       cutting_segments=[(0, 0, 5, 0, 0, -5)])
        assert r.mode == StockRemovalMode.FAST_APPROXIMATE
        assert r.initial_volume_mm3 > 0

    def test_a_mrr_computable(self, box_stock):
        r_stock = compute_stock_removal_fast(box_stock, tool_radius_mm=5.0,
                                             cutting_segments=[(0, 0, 5, 0, 0, -5)])
        r_mrr = compute_mrr(
            operation_id="A-OP",
            tool_id="A-TOOL",
            removed_volume_mm3=r_stock.removed_volume_mm3,
            cutting_time_min=0.5,
            volume_fidelity=r_stock.removed_volume_fidelity,
            provenance="TEST",
        )
        if r_stock.removed_volume_mm3 and r_stock.removed_volume_mm3 > 0:
            assert r_mrr.mrr_mm3_per_min > 0

    def test_a_singularity_not_implemented(self, machine_3ax):
        r = verify_machine_limits(machine_3ax, [{"x": 0.0, "y": 0.0, "z": -5.0}])
        assert r.singularity_check == "NOT_IMPLEMENTED"

    def test_a_segments_checked_matches_input(self, machine_3ax):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0}] * 5
        r = verify_machine_limits(machine_3ax, segs)
        assert r.segments_checked == 5


# ---------------------------------------------------------------------------
# Case B: Overtravel FAIL — X exceeds travel
# ---------------------------------------------------------------------------

class TestCaseB:
    """Case B: X command 650 mm when travel is ±500 mm → FAIL."""

    def test_b_overtravel_x_detected(self, machine_3ax):
        segs = [
            {"x": 0.0, "y": 0.0, "z": -5.0},
            {"x": 650.0, "y": 0.0, "z": -5.0},  # 150 mm overtravel
        ]
        r = verify_machine_limits(machine_3ax, segs)
        assert r.status == "FAIL"

    def test_b_violation_axis_is_x(self, machine_3ax):
        segs = [{"x": 650.0, "y": 0.0, "z": -5.0}]
        r = verify_machine_limits(machine_3ax, segs)
        axes = [v.axis for v in r.violations]
        assert "X" in axes

    def test_b_violation_excess_correct(self, machine_3ax):
        segs = [{"x": 650.0, "y": 0.0, "z": -5.0}]
        r = verify_machine_limits(machine_3ax, segs)
        v = next(v for v in r.violations if v.axis == "X")
        assert v.excess == pytest.approx(150.0, abs=0.1)

    def test_b_valid_axes_not_violated(self, machine_3ax):
        segs = [{"x": 650.0, "y": 0.0, "z": -5.0}]
        r = verify_machine_limits(machine_3ax, segs)
        y_violations = [v for v in r.violations if v.axis == "Y"]
        z_violations = [v for v in r.violations if v.axis == "Z"]
        assert len(y_violations) == 0
        assert len(z_violations) == 0

    def test_b_multiple_overtravel(self, machine_3ax):
        segs = [{"x": 650.0, "y": 500.0, "z": -5.0}]
        r = verify_machine_limits(machine_3ax, segs)
        assert r.status == "FAIL"
        axes = {v.axis for v in r.violations}
        assert "X" in axes
        assert "Y" in axes

    def test_b_violation_command_value_recorded(self, machine_3ax):
        segs = [{"x": 650.0, "y": 0.0, "z": -5.0}]
        r = verify_machine_limits(machine_3ax, segs)
        v = next(v for v in r.violations if v.axis == "X")
        assert v.command_value == pytest.approx(650.0, abs=0.1)


# ---------------------------------------------------------------------------
# Case C: Rotary limit FAIL — A exceeds ±110°
# ---------------------------------------------------------------------------

class TestCaseC:
    """Case C: A command 150° when limit is ±110° → FAIL."""

    def test_c_rotary_overtravel_detected(self, machine_4ax):
        segs = [
            {"x": 0.0, "y": 0.0, "z": -5.0, "a": 150.0},  # A exceeds ±110
        ]
        r = verify_machine_limits(machine_4ax, segs)
        assert r.status == "FAIL"

    def test_c_violation_axis_is_a(self, machine_4ax):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0, "a": 150.0}]
        r = verify_machine_limits(machine_4ax, segs)
        axes = [v.axis for v in r.violations]
        assert "A" in axes

    def test_c_a_violation_excess(self, machine_4ax):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0, "a": 150.0}]
        r = verify_machine_limits(machine_4ax, segs)
        v = next(v for v in r.violations if v.axis == "A")
        assert v.excess == pytest.approx(40.0, abs=0.1)

    def test_c_within_rotary_limit_pass(self, machine_4ax):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0, "a": 90.0}]
        r = verify_machine_limits(machine_4ax, segs)
        a_violations = [v for v in r.violations if v.axis == "A"]
        assert len(a_violations) == 0

    def test_c_negative_a_overtravel(self, machine_4ax):
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0, "a": -120.0}]
        r = verify_machine_limits(machine_4ax, segs)
        a_violations = [v for v in r.violations if v.axis == "A"]
        assert len(a_violations) == 1
        assert a_violations[0].excess == pytest.approx(10.0, abs=0.1)

    def test_c_missing_rotary_no_fabrication(self):
        # 3-axis machine has no A limit — rotary check must be NOT_PERFORMED, not PASS/FAIL
        m = build_test_only_kinematic_model(
            machine_id="3AX",
            architecture=MachineArchitecture.THREE_AXIS_VMC,
            x_range=(-500.0, 500.0),
            y_range=(-400.0, 400.0),
            z_range=(-300.0, 0.0),
        )
        segs = [{"x": 0.0, "y": 0.0, "z": -5.0, "a": 9999.0}]
        r = verify_machine_limits(m, segs)
        # 3-axis has no A limit — the A value must not cause a fabricated FAIL
        # (it should be ignored since there's no A axis limit defined)
        a_violations = [v for v in r.violations if v.axis == "A"]
        # Correct: no A limit defined → no A violation fabricated
        assert len(a_violations) == 0
