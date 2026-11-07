"""Level-18 Digital Twin — explainability engine.

Answers WHAT/WHY/WHICH for every scenario.
No fabricated explanations — only summarizes computed data.
"""

from __future__ import annotations

from .models import (
    ManufacturingTwinScenario,
    ScenarioComparison,
    SimulationResult,
    TwinRecommendation,
)


def explain_scenario(
    scenario: ManufacturingTwinScenario,
    result: SimulationResult,
) -> str:
    """Answer WHAT changed, WHY, WHICH source, WHICH constraint, KPI status."""
    lines: list[str] = [
        f"=== Scenario: {scenario.scenario_id} [{scenario.scenario_type}] ===",
        f"Status: {result.status}",
        f"Fidelity: {result.fidelity}",
    ]

    # WHAT changed
    if scenario.baseline_ref:
        lines.append(f"Based on baseline: {scenario.baseline_ref}")
        what_parts: list[str] = []
        if scenario.machine_ref:
            what_parts.append(f"machine={scenario.machine_ref!r}")
        if scenario.tool_refs:
            what_parts.append(f"tools={scenario.tool_refs}")
        if scenario.cutting_data:
            what_parts.append(f"cutting_data={scenario.cutting_data}")
        if scenario.quantity is not None:
            what_parts.append(f"quantity={scenario.quantity}")
        if what_parts:
            lines.append(f"Changed: {', '.join(what_parts)}")
    else:
        lines.append("This is the BASELINE scenario.")

    # WHICH source
    lines.append(f"Cycle time source: {result.kpi.cycle_time_source}")
    if result.kpi.cycle_time_min is not None:
        lines.append(f"Cycle time: {result.kpi.cycle_time_min:.2f} min")

    # WHICH constraint passed/failed
    failures = [c for c in result.constraint_results if not c.passed]
    passes = [c for c in result.constraint_results if c.passed]
    if failures:
        lines.append(f"Constraint failures ({len(failures)}):")
        for f in failures:
            lines.append(f"  FAIL {f.constraint_name}: {f.detail}")
    if passes:
        lines.append(f"Constraints passed: {', '.join(c.constraint_name for c in passes)}")

    # WHAT is unknown
    if result.kpi.unknowns:
        lines.append(f"Unknown KPIs: {', '.join(result.kpi.unknowns)}")

    # Warnings
    for w in result.warnings:
        lines.append(f"  WARNING: {w}")

    lines.append("[SIMULATION ONLY — human review required before any action]")
    return "\n".join(lines)


def explain_comparison(
    comparison: ScenarioComparison,
) -> str:
    """Explain what changed between baseline and scenario."""
    lines: list[str] = [
        f"=== Comparison: {comparison.comparison_id} vs baseline {comparison.baseline_id} ===",
    ]

    if not comparison.kpi_diffs and not comparison.unknown_diffs:
        lines.append("No KPI differences measurable (all values unknown).")
        return "\n".join(lines)

    for diff in comparison.kpi_diffs:
        if diff.absolute_diff is not None:
            direction = (
                "IMPROVED"
                if diff.improved
                else ("WORSENED" if diff.improved is False else "NO CHANGE")
            )
            pct = f" ({diff.relative_diff_pct:.1f}%)" if diff.relative_diff_pct is not None else ""
            lines.append(
                f"  {diff.kpi_name}: {diff.baseline_value:.3f} → "
                f"{diff.scenario_value:.3f}{pct} [{direction}]"
                if diff.baseline_value is not None and diff.scenario_value is not None
                else f"  {diff.kpi_name}: [{direction}]"
            )

    if comparison.trade_offs:
        lines.append("Trade-offs:")
        for t in comparison.trade_offs:
            lines.append(f"  {t}")

    if comparison.unknown_diffs:
        lines.append("Unknown differences (data missing):")
        for u in comparison.unknown_diffs:
            lines.append(f"  {u}")

    if comparison.constraint_delta:
        lines.append(f"Constraint changes: {comparison.constraint_delta}")

    return "\n".join(lines)


def explain_recommendation(
    recommendation: TwinRecommendation,
    all_results: list[SimulationResult],
) -> str:
    """Explain recommendation — why, fidelity, trade-offs, unknowns."""
    lines: list[str] = [
        f"=== Recommendation: {recommendation.recommendation_type} ===",
        f"Recommended scenario: {recommendation.scenario_id}",
        f"WHY: {recommendation.why}",
        f"Data fidelity: {recommendation.data_fidelity}",
    ]

    if recommendation.constraints_passed:
        lines.append(
            f"Constraints passed: {', '.join(recommendation.constraints_passed)}"
        )

    if recommendation.trade_offs:
        lines.append("Trade-offs:")
        for t in recommendation.trade_offs:
            lines.append(f"  {t}")

    if recommendation.unknowns:
        lines.append(f"Unknowns: {', '.join(recommendation.unknowns)}")

    lines.append(
        "\nIMPORTANT: This is a PROPOSED recommendation only. "
        "No scenario has been applied. Human engineering review mandatory before any change."
    )
    return "\n".join(lines)
