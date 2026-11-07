"""Level-18 Digital Twin — scenario candidate generator.

Generates candidates ONLY from validated alternatives.
No random engineering values invented.
Combinatorial explosion prevented by TwinSearchLimits.
"""

from __future__ import annotations

from .enums import ScenarioType
from .models import ManufacturingTwinScenario, TwinSearchLimits

_DEFAULT_VC_CANDIDATES = [0.85, 1.0, 1.10]  # relative multipliers from baseline


def _copy_scenario(
    baseline: ManufacturingTwinScenario,
    scenario_id: str,
    scenario_type: ScenarioType,
    **overrides,
) -> ManufacturingTwinScenario:
    """Create a new scenario based on the baseline with specific overrides.

    Baseline is NOT mutated — a fresh object is returned.
    """
    base_dict = baseline.model_dump()
    base_dict.update(overrides)
    base_dict["scenario_id"] = scenario_id
    base_dict["scenario_type"] = scenario_type
    base_dict["baseline_ref"] = baseline.scenario_id
    base_dict["is_simulation_only"] = True
    base_dict["is_production_plan"] = False
    base_dict["baseline_mutation_allowed"] = False
    base_dict["review_required"] = True
    return ManufacturingTwinScenario(**base_dict)


def generate_machine_alternatives(
    baseline: ManufacturingTwinScenario,
    machine_refs: list[str],
    limits: TwinSearchLimits | None = None,
) -> list[ManufacturingTwinScenario]:
    """Generate machine alternative scenarios.

    Only machines explicitly provided are used — none invented.
    """
    lim = limits or TwinSearchLimits()
    capped = machine_refs[: lim.max_machines]
    scenarios = []
    for idx, machine_ref in enumerate(capped, start=1):
        s = _copy_scenario(
            baseline,
            scenario_id=f"{baseline.scenario_id}_MACH_ALT_{idx:02d}",
            scenario_type=ScenarioType.MACHINE_ALTERNATIVE,
            machine_ref=machine_ref,
        )
        scenarios.append(s)
    return scenarios


def generate_tool_alternatives(
    baseline: ManufacturingTwinScenario,
    tool_ref_sets: list[list[str]],
    limits: TwinSearchLimits | None = None,
) -> list[ManufacturingTwinScenario]:
    """Generate tool alternative scenarios.

    Only tool sets explicitly provided are used — no fabricated SKUs.
    """
    lim = limits or TwinSearchLimits()
    capped = tool_ref_sets[: lim.max_tools]
    scenarios = []
    for idx, tool_refs in enumerate(capped, start=1):
        s = _copy_scenario(
            baseline,
            scenario_id=f"{baseline.scenario_id}_TOOL_ALT_{idx:02d}",
            scenario_type=ScenarioType.TOOL_ALTERNATIVE,
            tool_refs=tool_refs,
        )
        scenarios.append(s)
    return scenarios


def generate_cutting_data_alternatives(
    baseline: ManufacturingTwinScenario,
    candidate_cutting_data: list[dict],
    limits: TwinSearchLimits | None = None,
) -> list[ManufacturingTwinScenario]:
    """Generate cutting parameter alternative scenarios.

    Every candidate must remain inside verified bounds — validation in constraints.
    No random values invented.
    """
    lim = limits or TwinSearchLimits()
    capped = candidate_cutting_data[: lim.max_parameter_candidates]
    scenarios = []
    for idx, cutting_data in enumerate(capped, start=1):
        s = _copy_scenario(
            baseline,
            scenario_id=f"{baseline.scenario_id}_CDALT_{idx:02d}",
            scenario_type=ScenarioType.CUTTING_DATA_ALTERNATIVE,
            cutting_data=cutting_data,
        )
        scenarios.append(s)
    return scenarios


def generate_quantity_alternatives(
    baseline: ManufacturingTwinScenario,
    quantities: list[int],
    limits: TwinSearchLimits | None = None,
) -> list[ManufacturingTwinScenario]:
    """Generate quantity/batch size alternative scenarios."""
    lim = limits or TwinSearchLimits()
    capped = quantities[: lim.max_parameter_candidates]
    scenarios = []
    for idx, quantity in enumerate(capped, start=1):
        s = _copy_scenario(
            baseline,
            scenario_id=f"{baseline.scenario_id}_QTY_{idx:02d}",
            scenario_type=ScenarioType.QUANTITY_ALTERNATIVE,
            quantity=quantity,
            batch_size=quantity,
        )
        scenarios.append(s)
    return scenarios


def generate_schedule_alternatives(
    baseline: ManufacturingTwinScenario,
    schedule_refs: list[str],
    limits: TwinSearchLimits | None = None,
) -> list[ManufacturingTwinScenario]:
    """Generate scheduling alternative scenarios."""
    lim = limits or TwinSearchLimits()
    capped = schedule_refs[: lim.max_machines]
    scenarios = []
    for idx, schedule_ref in enumerate(capped, start=1):
        s = _copy_scenario(
            baseline,
            scenario_id=f"{baseline.scenario_id}_SCHED_{idx:02d}",
            scenario_type=ScenarioType.SCHEDULE_ALTERNATIVE,
            schedule_ref=schedule_ref,
        )
        scenarios.append(s)
    return scenarios
