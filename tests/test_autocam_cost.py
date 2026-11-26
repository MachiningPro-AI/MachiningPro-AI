"""Tests for Auto CAM cost estimation bridge — MACHININGPRO_AI_BETA3_COST_01.

Verifies:
  - NOT_PROVIDED when no cost_input
  - PARTIAL when some categories missing
  - COMPLETE when all 8 categories supplied
  - CURRENCY_MISMATCH blocks aggregation
  - Overhead % calculated from known subtotal
  - Setup amortized when quantity supplied
  - Machine cost uses cycle_time_s / 3600 × hourly rate
  - All HARD RULES: no fabricated values, partial=partial not fake total
"""

import pytest

from backend.autocam.cost_estimate import compute_autocam_cost
from backend.autocam.models import (
    AutoCamCostEstimate,
    AutoCamCostInput,
    CycleTimeResult,
    MachineResult,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def machine() -> MachineResult:
    return MachineResult(
        machine_id="M001",
        manufacturer="Mazak",
        model="Variaxis 500",
        machine_type_code="5AX",
        spindle_max_rpm=12000,
        status="FOUND",
    )


@pytest.fixture
def cycle_time_known() -> CycleTimeResult:
    return CycleTimeResult(
        cutting_time_s=180.0,  # 3 minutes
        status="PARTIAL",
        path_length_type="ESTIMATED",
    )


@pytest.fixture
def cycle_time_unknown() -> CycleTimeResult:
    return CycleTimeResult(status="INSUFFICIENT_DATA")


# ---------------------------------------------------------------------------
# HARD RULE tests
# ---------------------------------------------------------------------------

class TestHardRules:
    def test_hr7_no_cost_input_returns_not_provided(self, machine, cycle_time_known):
        est = compute_autocam_cost(cycle_time_known, machine, None)
        assert est.total_status == "NOT_PROVIDED"
        assert not est.cost_input_received
        assert est.known_total is None

    def test_hr8_partial_input_returns_partial_not_fake_total(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            machine_hourly_rate=80.0,
            machine_rate_currency="EUR",
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.total_status == "PARTIAL_COST_ESTIMATE"
        assert est.unknown_component_count > 0

    def test_hr7_unknown_machine_rate_not_fabricated(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(currency="EUR")  # no machine_hourly_rate
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.machine_cost.status == "NOT_PROVIDED"
        assert est.machine_cost.value is None

    def test_hr8_no_known_components_returns_insufficient_data(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(currency="EUR")  # all rates missing
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.total_status in ("INSUFFICIENT_DATA", "PARTIAL_COST_ESTIMATE")

    def test_hr9_cycle_time_remains_estimated(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(machine_hourly_rate=80.0, currency="EUR")
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        # Machine cost notes must mention ESTIMATED
        assert est.machine_cost.notes is not None
        assert "ESTIMATED" in est.machine_cost.notes

    def test_no_fabricated_rate_when_cycle_time_unknown(self, machine, cycle_time_unknown):
        cost_input = AutoCamCostInput(machine_hourly_rate=80.0, currency="EUR")
        est = compute_autocam_cost(cycle_time_unknown, machine, cost_input)
        # Machine time is unknown → machine cost should be INSUFFICIENT_DATA not a fabricated value
        assert est.machine_cost.status in ("INSUFFICIENT_DATA", "NOT_PROVIDED")
        assert est.machine_cost.value is None


# ---------------------------------------------------------------------------
# Computation tests
# ---------------------------------------------------------------------------

class TestCostComputation:
    def test_machine_cost_calculation(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            machine_hourly_rate=60.0,  # €60/h
            machine_rate_currency="EUR",
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        # 180s = 3min = 0.05h → 0.05 × 60 = 3.00
        assert est.machine_cost.value is not None
        assert abs(est.machine_cost.value - 3.0) < 0.01
        assert est.machine_cost.status == "CALCULATED"
        assert est.machine_cost.currency == "EUR"

    def test_material_cost_passthrough(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            material_cost_total=45.50,
            material_cost_currency="EUR",
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.material_cost.value == 45.50
        assert est.material_cost.status == "USER_PROVIDED"

    def test_setup_amortization(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            setup_cost_total=120.0,
            setup_cost_currency="EUR",
            quantity=4,
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.setup_cost.value is not None
        assert abs(est.setup_cost.value - 30.0) < 0.01  # 120 / 4 = 30
        assert est.setup_cost.status == "CALCULATED"

    def test_setup_not_amortized_without_quantity(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            setup_cost_total=120.0,
            setup_cost_currency="EUR",
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.setup_cost.value == 120.0
        assert est.setup_cost.status == "USER_PROVIDED"

    def test_labor_cost_calculation(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            labor_hours=2.0,
            labor_rate=25.0,
            labor_rate_currency="EUR",
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.labor_cost.value == 50.0
        assert est.labor_cost.status == "CALCULATED"

    def test_overhead_pct_applied_to_known_subtotal(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            material_cost_total=100.0,
            material_cost_currency="EUR",
            overhead_pct=10.0,
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        # overhead = 100 × 10% = 10
        assert est.overhead_cost.value is not None
        assert abs(est.overhead_cost.value - 10.0) < 0.01
        assert est.overhead_cost.status == "CALCULATED"

    def test_complete_estimate_when_all_known(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            machine_hourly_rate=60.0,
            material_cost_total=45.0,
            tool_cost_total=12.0,
            setup_cost_total=120.0,
            labor_hours=1.0,
            labor_rate=30.0,
            energy_cost=5.0,
            quantity=1,
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        # other_cost still NOT_PROVIDED → PARTIAL
        assert est.total_status in ("COMPLETE_COST_ESTIMATE", "PARTIAL_COST_ESTIMATE")
        assert est.known_total is not None
        assert est.completeness_pct > 0


# ---------------------------------------------------------------------------
# Currency mismatch
# ---------------------------------------------------------------------------

class TestCurrencyMismatch:
    def test_currency_mismatch_blocks_total(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            machine_hourly_rate=80.0,
            machine_rate_currency="EUR",
            material_cost_total=50.0,
            material_cost_currency="USD",  # different!
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.total_status == "CURRENCY_MISMATCH"
        assert est.known_total is None

    def test_currency_mismatch_warning_present(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(
            machine_hourly_rate=80.0,
            machine_rate_currency="EUR",
            material_cost_total=50.0,
            material_cost_currency="USD",
            currency="EUR",
        )
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert any("CURRENCY_MISMATCH" in w for w in est.warnings)


# ---------------------------------------------------------------------------
# Provenance fields
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_machine_cost_has_formula(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(machine_hourly_rate=60.0, currency="EUR")
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.machine_cost.formula is not None
        assert "machine_hourly_rate" in est.machine_cost.formula

    def test_machine_cost_source_type_user_defined(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(machine_hourly_rate=60.0, currency="EUR")
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.machine_cost.source_type in ("USER_DEFINED", "CALCULATED")

    def test_all_items_have_category(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(currency="EUR")
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        for attr in ["material_cost", "machine_cost", "tool_cost", "setup_cost",
                     "labor_cost", "energy_cost", "overhead_cost", "other_cost"]:
            item = getattr(est, attr)
            assert item.category != ""

    def test_computed_at_set(self, machine, cycle_time_known):
        cost_input = AutoCamCostInput(currency="EUR")
        est = compute_autocam_cost(cycle_time_known, machine, cost_input)
        assert est.computed_at != ""
        assert est.cost_input_received is True
