"""Level-18 Digital Twin — scenario comparison engine.

Compare scenario A/B/N against baseline.
Absolute differences, relative differences, trade-offs, unknown diffs.
No fabricated comparisons — unknown values remain unknown.
"""

from __future__ import annotations

from .enums import KPIKey
from .models import KPIDiff, ScenarioComparison, ScenarioKPI, SimulationResult

# KPI configurations: (attr_name, lower_is_better)
_KPI_CONFIG: list[tuple[str, str, bool]] = [
    (KPIKey.CYCLE_TIME, "cycle_time_min", True),
    (KPIKey.SETUP_TIME, "setup_time_min", True),
    (KPIKey.BATCH_TIME, "batch_time_min", True),
    (KPIKey.THROUGHPUT, "throughput_per_hour", False),
    (KPIKey.MANUFACTURING_COST, "manufacturing_cost", True),
    (KPIKey.TOOL_LIFE, "tool_life_min", False),
    (KPIKey.TOOL_CONSUMPTION, "tool_consumption", True),
    (KPIKey.ENERGY, "energy_kwh", True),
    (KPIKey.MACHINE_LOAD, "machine_load_pct", True),
    (KPIKey.LATENESS, "lateness_min", True),
    (KPIKey.MATERIAL_UTILIZATION, "material_utilization_pct", False),
]


def _diff(
    kpi_key: str,
    kpi_attr: str,
    baseline_kpi: ScenarioKPI,
    scenario_kpi: ScenarioKPI,
    lower_is_better: bool,
) -> KPIDiff | None:
    """Compute KPI diff — returns None if both values are None."""
    bv: float | None = getattr(baseline_kpi, kpi_attr, None)
    sv: float | None = getattr(scenario_kpi, kpi_attr, None)
    if bv is None and sv is None:
        return None
    abs_diff: float | None = None
    rel_diff: float | None = None
    improved: bool | None = None
    if bv is not None and sv is not None:
        abs_diff = sv - bv
        if bv != 0:
            rel_diff = (abs_diff / abs(bv)) * 100.0
        # improvement: lower_is_better means negative abs_diff = better
        if abs_diff < 0:
            improved = lower_is_better
        elif abs_diff > 0:
            improved = not lower_is_better
        else:
            improved = None  # no change
    return KPIDiff(
        kpi_name=kpi_key,
        baseline_value=bv,
        scenario_value=sv,
        absolute_diff=abs_diff,
        relative_diff_pct=rel_diff,
        improved=improved,
    )


def _generate_trade_offs(diffs: list[KPIDiff]) -> list[str]:
    """Generate human-readable trade-off descriptions."""
    improved = [d for d in diffs if d.improved is True and d.absolute_diff is not None]
    worsened = [d for d in diffs if d.improved is False and d.absolute_diff is not None]

    trade_offs: list[str] = []
    for imp in improved:
        trade_offs.append(
            f"{imp.kpi_name} improved by "
            f"{abs(imp.absolute_diff or 0):.2f} "
            f"({imp.relative_diff_pct:.1f}%)"
            if imp.relative_diff_pct is not None
            else f"{imp.kpi_name} improved by {abs(imp.absolute_diff or 0):.2f}"
        )
    for wor in worsened:
        trade_offs.append(
            f"{wor.kpi_name} worsened by "
            f"{abs(wor.absolute_diff or 0):.2f} "
            f"({abs(wor.relative_diff_pct or 0):.1f}%)"
            if wor.relative_diff_pct is not None
            else f"{wor.kpi_name} worsened by {abs(wor.absolute_diff or 0):.2f}"
        )
    return trade_offs


def compare_scenarios(
    baseline: SimulationResult,
    scenario: SimulationResult,
) -> ScenarioComparison:
    """
    Compare a scenario SimulationResult against the baseline.

    Returns absolute/relative diffs, trade-offs, and unknown diffs.
    Unknown values remain unknown — not assumed zero.
    """
    diffs: list[KPIDiff] = []
    unknown_diffs: list[str] = []

    for kpi_key, kpi_attr, lower_is_better in _KPI_CONFIG:
        bv = getattr(baseline.kpi, kpi_attr, None)
        sv = getattr(scenario.kpi, kpi_attr, None)
        if bv is None or sv is None:
            # At least one value unknown — record as unknown diff
            if bv is not None or sv is not None:
                unknown_diffs.append(
                    f"{kpi_key}: baseline={'known' if bv is not None else 'UNKNOWN'}, "
                    f"scenario={'known' if sv is not None else 'UNKNOWN'}"
                )
            continue
        d = _diff(kpi_key, kpi_attr, baseline.kpi, scenario.kpi, lower_is_better)
        if d is not None:
            diffs.append(d)

    trade_offs = _generate_trade_offs(diffs)

    # Constraint delta
    b_failures = set(str(f) for f in baseline.hard_constraint_failures)
    s_failures = set(str(f) for f in scenario.hard_constraint_failures)
    new_failures = s_failures - b_failures
    resolved = b_failures - s_failures
    constraint_delta_parts: list[str] = []
    if new_failures:
        constraint_delta_parts.append(f"NEW failures: {', '.join(new_failures)}")
    if resolved:
        constraint_delta_parts.append(f"Resolved: {', '.join(resolved)}")
    constraint_delta = "; ".join(constraint_delta_parts)

    return ScenarioComparison(
        baseline_id=baseline.scenario_id,
        comparison_id=scenario.scenario_id,
        kpi_diffs=diffs,
        trade_offs=trade_offs,
        unknown_diffs=unknown_diffs,
        constraint_delta=constraint_delta,
        is_fabricated=False,
    )
