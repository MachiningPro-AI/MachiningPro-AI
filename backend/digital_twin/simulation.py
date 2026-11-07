"""Level-18 Digital Twin — deterministic scenario evaluator.

Input: ManufacturingTwinScenario
Output: SimulationResult (KPIs + constraints + status)

SIMULATION / DECISION SUPPORT only.
No automatic application of results.
No fabricated KPI values.
"""

from __future__ import annotations

from .constraints import determine_fidelity, evaluate_constraints
from .enums import (
    CycleTimeSource,
    EnergyStatus,
    ErrorType,
    ScenarioStatus,
)
from .models import (
    ManufacturingTwinScenario,
    ScenarioKPI,
    SimulationResult,
)

_EVALUATOR_VERSION = "18.0"


def _compute_cycle_time(
    scenario: ManufacturingTwinScenario,
) -> tuple[float | None, CycleTimeSource, list[str]]:
    """Return (cycle_time_min, source, unknowns)."""
    unknowns: list[str] = []

    if scenario.estimated_cycle_time_min is not None:
        return (
            scenario.estimated_cycle_time_min,
            CycleTimeSource.SIMULATED,
            unknowns,
        )

    unknowns.append("cycle_time_min")
    return None, CycleTimeSource.UNKNOWN, unknowns


def _compute_batch_time(
    cycle_time_min: float | None,
    setup_time_min: float | None,
    batch_size: int | None,
    quantity: int | None,
) -> tuple[float | None, list[str]]:
    """Return (batch_time_min, unknowns).

    batch_time = setup_time + cycle_time * batch_size
    """
    unknowns: list[str] = []
    n = batch_size or quantity
    if cycle_time_min is None:
        unknowns.append("batch_time_min (cycle_time unknown)")
        return None, unknowns
    if n is None:
        unknowns.append("batch_time_min (quantity unknown)")
        return None, unknowns
    setup = setup_time_min or 0.0
    if setup_time_min is None:
        unknowns.append("setup_time_min")
    return setup + cycle_time_min * n, unknowns


def _compute_throughput(
    batch_time_min: float | None,
    batch_size: int | None,
) -> tuple[float | None, list[str]]:
    """Return (throughput_per_hour, unknowns)."""
    unknowns: list[str] = []
    if batch_time_min is None or batch_size is None or batch_size <= 0:
        unknowns.append("throughput_per_hour")
        return None, unknowns
    if batch_time_min <= 0:
        unknowns.append("throughput_per_hour (batch_time <= 0)")
        return None, unknowns
    return (batch_size / batch_time_min) * 60.0, unknowns


def _compute_energy(
    cycle_time_min: float | None,
    setup_time_min: float | None,
    idle_power_kw: float | None,
    cutting_power_kw: float | None,
) -> tuple[float | None, EnergyStatus]:
    """Return (energy_kwh, status).

    Only calculates when both power values and time are present.
    No generic kWh fabrication.
    """
    if cutting_power_kw is None or idle_power_kw is None:
        return None, EnergyStatus.INSUFFICIENT_DATA
    if cycle_time_min is None:
        return None, EnergyStatus.INSUFFICIENT_DATA

    setup_h = (setup_time_min or 0.0) / 60.0
    cycle_h = cycle_time_min / 60.0
    energy = idle_power_kw * setup_h + cutting_power_kw * cycle_h
    return energy, EnergyStatus.CALCULATED


def simulate_scenario(
    scenario: ManufacturingTwinScenario,
) -> SimulationResult:
    """
    Evaluate a ManufacturingTwinScenario and return a SimulationResult.

    Same input + same evaluator version = same deterministic result.
    is_simulation_only=True, is_production_plan=False always.
    """
    # Constraint evaluation
    constraint_results, hard_failures, warnings = evaluate_constraints(scenario)
    errors: list[ErrorType] = []

    # If hard constraints fail → INVALID scenario; KPIs still computed for comparison
    if hard_failures:
        status = ScenarioStatus.INVALID
    elif scenario.status in (ScenarioStatus.DRAFT, ScenarioStatus.INCOMPLETE):
        status = ScenarioStatus.INCOMPLETE
    else:
        status = ScenarioStatus.SIMULATED

    # Fidelity
    fidelity = determine_fidelity(scenario)

    unknowns: list[str] = []

    # Cycle time
    cycle_time, ct_source, ct_unknowns = _compute_cycle_time(scenario)
    unknowns.extend(ct_unknowns)

    # Setup time
    setup_time = scenario.estimated_setup_time_min

    # Batch time
    batch_time, bt_unknowns = _compute_batch_time(
        cycle_time, setup_time, scenario.batch_size, scenario.quantity
    )
    unknowns.extend(bt_unknowns)

    # Throughput
    throughput, tp_unknowns = _compute_throughput(
        batch_time, scenario.batch_size or scenario.quantity
    )
    unknowns.extend(tp_unknowns)

    # Energy
    energy_kwh, energy_status = _compute_energy(
        cycle_time,
        setup_time,
        scenario.machine_idle_power_kw,
        scenario.machine_cutting_power_kw,
    )

    # Missing data errors
    if cycle_time is None:
        errors.append(ErrorType.MISSING_CYCLE_DATA)
    if scenario.machine_ref is None:
        errors.append(ErrorType.MISSING_MACHINE_DATA)
        warnings.append("machine_ref not set — machine KPIs unavailable")
    if hard_failures:
        errors.append(ErrorType.CONSTRAINT_FAILURE)

    kpi = ScenarioKPI(
        cycle_time_min=cycle_time,
        cycle_time_source=ct_source,
        setup_time_min=setup_time,
        batch_time_min=batch_time,
        throughput_per_hour=throughput,
        manufacturing_cost=None,  # requires L8 cost engine — not invoked here by default
        cost_currency=None,
        energy_kwh=energy_kwh,
        energy_status=energy_status,
        fidelity=fidelity,
        unknowns=list(set(unknowns)),
        is_fabricated=False,
    )

    return SimulationResult(
        scenario_id=scenario.scenario_id,
        status=status,
        kpi=kpi,
        constraint_results=constraint_results,
        hard_constraint_failures=hard_failures,
        fidelity=fidelity,
        warnings=warnings,
        errors=errors,
        is_simulation_only=True,
        is_production_plan=False,
    )
