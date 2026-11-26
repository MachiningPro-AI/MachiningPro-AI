"""Auto CAM cost estimation bridge — MACHININGPRO_AI_BETA3_COST_01.

Bridges AutoCamPlan cycle-time output + user-provided rates to the
existing manufacturing cost engine functions.

HARD RULES (verbatim from task spec):
  NO fabricated commercial rates.
  NO fabricated material prices.
  NO fabricated machine hourly rates.
  NO fabricated tool prices.
  UNKNOWN financial inputs must remain UNKNOWN / NOT_PROVIDED.
  Partial data produces PARTIAL_COST_ESTIMATE, not a fake total.
  Estimated machining time remains ESTIMATED.
  DUPLICATE_ENGINE_CREATED=NO — calls existing cost_engine functions.
  Cost analysis must not approve manufacturing.
  No CNC dispatch. No production release.
"""
from __future__ import annotations

from datetime import UTC, datetime

from backend.interoperability.cost_engine import (
    calculate_machine_cost,
    calculate_setup_amortization,
)
from backend.interoperability.cost_intelligence import (
    CostEvidence,
    CostSourceType,
)

from .models import (
    AutoCamCostEstimate,
    AutoCamCostInput,
    CostCategoryItem,
    CycleTimeResult,
    MachineResult,
)


def compute_autocam_cost(
    cycle_time: CycleTimeResult,
    machine: MachineResult,
    cost_input: AutoCamCostInput | None,
) -> AutoCamCostEstimate:
    """Compute cost estimate for an Auto CAM plan.

    Uses existing cost_engine functions — DUPLICATE_ENGINE_CREATED=NO.
    All missing inputs remain NOT_PROVIDED — never fabricated.
    Manufacturing approval status is NOT changed by this function.
    """
    if cost_input is None:
        return AutoCamCostEstimate(
            total_status="NOT_PROVIDED",
            cost_input_received=False,
            computed_at=datetime.now(UTC).isoformat(),
            warnings=[
                "No cost inputs provided. Submit via POST /api/autocam/{plan_id}/cost-input"
            ],
        )

    resolved_currency = (
        cost_input.currency
        or cost_input.machine_rate_currency
        or cost_input.material_cost_currency
    )
    warnings: list[str] = []

    # ── Machine cost ──────────────────────────────────────────────────────
    if cost_input.machine_hourly_rate is not None and cost_input.machine_hourly_rate > 0:
        rate_ev = CostEvidence(
            value=cost_input.machine_hourly_rate,
            currency=cost_input.machine_rate_currency or resolved_currency,
            unit_basis="per_hour",
            source_type=CostSourceType.USER_DEFINED,
            source_name="USER_PROVIDED",
            status="USER_PROVIDED",
            evidence=(
                f"user-supplied: {cost_input.machine_hourly_rate} "
                f"{cost_input.machine_rate_currency or resolved_currency or ''}/h"
            ),
        )
        machine_time_min: float | None = None
        ct_note = ""
        if cycle_time.cutting_time_s is not None:
            machine_time_min = cycle_time.cutting_time_s / 60.0
            ct_note = (
                f"cycle_time={cycle_time.cutting_time_s:.2f}s "
                f"(ESTIMATED—{cycle_time.status})"
            )
        else:
            warnings.append(
                "MACHINE_COST: cycle_time unknown — cannot calculate machine cost"
            )

        mc_ev = calculate_machine_cost(machine_time_min, rate_ev)
        machine_cost_item = CostCategoryItem(
            category="MACHINE_COST",
            value=mc_ev.value,
            currency=mc_ev.currency,
            source_type=mc_ev.source_type.value if mc_ev.is_known else "UNKNOWN",
            source_name="USER_PROVIDED",
            provenance=mc_ev.evidence or "UNKNOWN",
            status="CALCULATED" if mc_ev.is_known else "INSUFFICIENT_DATA",
            notes=ct_note or None,
            formula="machine_cost = (cycle_time_s / 3600) × machine_hourly_rate",
        )
    else:
        machine_cost_item = CostCategoryItem(
            category="MACHINE_COST",
            status="NOT_PROVIDED",
            notes="Provide machine_hourly_rate via POST /api/autocam/{plan_id}/cost-input",
        )
        warnings.append(
            "MACHINE_COST=NOT_PROVIDED: machine_hourly_rate not supplied"
        )

    # ── Material cost ─────────────────────────────────────────────────────
    if (
        cost_input.material_cost_total is not None
        and cost_input.material_cost_total >= 0
    ):
        material_cost_item = CostCategoryItem(
            category="MATERIAL_COST",
            value=cost_input.material_cost_total,
            currency=cost_input.material_cost_currency or resolved_currency,
            source_type="USER_DEFINED",
            source_name="USER_PROVIDED",
            provenance=(
                f"user-supplied: {cost_input.material_cost_total} "
                f"{cost_input.material_cost_currency or resolved_currency or ''}"
            ),
            status="USER_PROVIDED",
        )
    else:
        material_cost_item = CostCategoryItem(
            category="MATERIAL_COST",
            status="NOT_PROVIDED",
            notes=(
                "Provide material_cost_total via "
                "POST /api/autocam/{plan_id}/cost-input"
            ),
        )
        warnings.append(
            "MATERIAL_COST=NOT_PROVIDED: material_cost_total not supplied"
        )

    # ── Tool cost ─────────────────────────────────────────────────────────
    if (
        cost_input.tool_cost_total is not None
        and cost_input.tool_cost_total >= 0
    ):
        tool_cost_item = CostCategoryItem(
            category="TOOL_COST",
            value=cost_input.tool_cost_total,
            currency=cost_input.tool_cost_currency or resolved_currency,
            source_type="USER_DEFINED",
            source_name="USER_PROVIDED",
            provenance=(
                f"user-supplied: {cost_input.tool_cost_total} "
                f"{cost_input.tool_cost_currency or resolved_currency or ''}"
            ),
            status="USER_PROVIDED",
        )
    else:
        tool_cost_item = CostCategoryItem(
            category="TOOL_COST",
            status="NOT_PROVIDED",
            notes=(
                "Provide tool_cost_total via "
                "POST /api/autocam/{plan_id}/cost-input"
            ),
        )

    # ── Setup cost ────────────────────────────────────────────────────────
    if (
        cost_input.setup_cost_total is not None
        and cost_input.setup_cost_total >= 0
    ):
        quantity = cost_input.quantity
        setup_total_ev = CostEvidence(
            value=cost_input.setup_cost_total,
            currency=cost_input.setup_cost_currency or resolved_currency,
            unit_basis="total",
            source_type=CostSourceType.USER_DEFINED,
            status="USER_PROVIDED",
            evidence=f"user-supplied setup total: {cost_input.setup_cost_total}",
        )
        if quantity and quantity > 0:
            per_ev = calculate_setup_amortization(setup_total_ev, quantity)
            setup_cost_item = CostCategoryItem(
                category="SETUP_COST",
                value=per_ev.value,
                currency=per_ev.currency,
                source_type="CALCULATED",
                source_name="USER_PROVIDED",
                provenance=per_ev.evidence or "",
                status="CALCULATED",
                formula=(
                    f"setup_per_part = setup_total / quantity "
                    f"= {cost_input.setup_cost_total} / {quantity}"
                ),
            )
        else:
            setup_cost_item = CostCategoryItem(
                category="SETUP_COST",
                value=cost_input.setup_cost_total,
                currency=cost_input.setup_cost_currency or resolved_currency,
                source_type="USER_DEFINED",
                source_name="USER_PROVIDED",
                provenance="user-supplied setup total (quantity unknown — not amortized)",
                status="USER_PROVIDED",
                notes="Provide quantity to amortize per part",
            )
    else:
        setup_cost_item = CostCategoryItem(
            category="SETUP_COST",
            status="NOT_PROVIDED",
            notes=(
                "Provide setup_cost_total via "
                "POST /api/autocam/{plan_id}/cost-input"
            ),
        )

    # ── Labor cost ────────────────────────────────────────────────────────
    if (
        cost_input.labor_hours is not None
        and cost_input.labor_rate is not None
        and cost_input.labor_hours > 0
        and cost_input.labor_rate > 0
    ):
        labor_val = cost_input.labor_hours * cost_input.labor_rate
        labor_cost_item = CostCategoryItem(
            category="LABOR_COST",
            value=round(labor_val, 4),
            currency=cost_input.labor_rate_currency or resolved_currency,
            source_type="CALCULATED",
            source_name="USER_PROVIDED",
            provenance=(
                f"labor_cost = {cost_input.labor_hours}h × "
                f"{cost_input.labor_rate}/h = {labor_val:.4f}"
            ),
            status="CALCULATED",
            formula="labor_cost = labor_hours × labor_rate",
        )
    else:
        labor_cost_item = CostCategoryItem(
            category="LABOR_COST",
            status="NOT_PROVIDED",
            notes=(
                "Provide labor_hours + labor_rate via "
                "POST /api/autocam/{plan_id}/cost-input"
            ),
        )

    # ── Energy cost ───────────────────────────────────────────────────────
    if cost_input.energy_cost is not None and cost_input.energy_cost >= 0:
        energy_cost_item = CostCategoryItem(
            category="ENERGY_COST",
            value=cost_input.energy_cost,
            currency=cost_input.energy_cost_currency or resolved_currency,
            source_type="USER_DEFINED",
            source_name="USER_PROVIDED",
            provenance=f"user-supplied: {cost_input.energy_cost}",
            status="USER_PROVIDED",
        )
    else:
        energy_cost_item = CostCategoryItem(
            category="ENERGY_COST",
            status="NOT_PROVIDED",
        )

    # ── Overhead cost (% of known subtotal — applied after partial sum) ───
    # Placeholder; recalculated after partial sum below
    overhead_cost_item = CostCategoryItem(
        category="OVERHEAD_COST",
        status="NOT_PROVIDED",
        notes="Provide overhead_pct via POST /api/autocam/{plan_id}/cost-input",
    )

    # ── Other cost ────────────────────────────────────────────────────────
    other_cost_item = CostCategoryItem(
        category="OTHER_COST",
        status="NOT_PROVIDED",
    )

    # ── Aggregate known components (pre-overhead) ─────────────────────────
    pre_overhead = [
        machine_cost_item,
        material_cost_item,
        tool_cost_item,
        setup_cost_item,
        labor_cost_item,
        energy_cost_item,
        other_cost_item,
    ]
    known_pre = [item for item in pre_overhead if item.value is not None]

    # Currency mismatch check
    unique_currencies = {
        item.currency for item in known_pre if item.currency is not None
    }
    if len(unique_currencies) > 1:
        warnings.append(
            f"CURRENCY_MISMATCH: {sorted(unique_currencies)} — total aggregation blocked"
        )
        all_items = pre_overhead + [overhead_cost_item]
        return AutoCamCostEstimate(
            material_cost=material_cost_item,
            machine_cost=machine_cost_item,
            tool_cost=tool_cost_item,
            setup_cost=setup_cost_item,
            labor_cost=labor_cost_item,
            energy_cost=energy_cost_item,
            overhead_cost=overhead_cost_item,
            other_cost=other_cost_item,
            known_total=None,
            unknown_component_count=len(all_items) - len(known_pre),
            completeness_pct=0.0,
            total_status="CURRENCY_MISMATCH",
            currency=None,
            computed_at=datetime.now(UTC).isoformat(),
            cost_input_received=True,
            warnings=warnings,
        )

    subtotal = sum(item.value for item in known_pre)  # type: ignore[misc]

    # Apply overhead_pct to known subtotal (only if pct and subtotal both known)
    if (
        cost_input.overhead_pct is not None
        and cost_input.overhead_pct > 0
        and subtotal > 0
    ):
        oh_val = subtotal * (cost_input.overhead_pct / 100.0)
        overhead_cost_item = CostCategoryItem(
            category="OVERHEAD_COST",
            value=round(oh_val, 4),
            currency=resolved_currency,
            source_type="CALCULATED",
            source_name="USER_PROVIDED",
            provenance=(
                f"overhead = {subtotal:.4f} × {cost_input.overhead_pct}% "
                f"= {oh_val:.4f}"
            ),
            status="CALCULATED",
            formula=f"overhead_cost = known_subtotal × {cost_input.overhead_pct}%",
        )
        subtotal += oh_val

    all_items = [
        machine_cost_item,
        material_cost_item,
        tool_cost_item,
        setup_cost_item,
        labor_cost_item,
        energy_cost_item,
        overhead_cost_item,
        other_cost_item,
    ]
    known_all = [item for item in all_items if item.value is not None]
    unknown_count = len(all_items) - len(known_all)
    known_total = subtotal if known_all else None
    completeness_pct = round(len(known_all) / len(all_items) * 100, 1)

    if known_total is None:
        total_status = "INSUFFICIENT_DATA"
    elif unknown_count > 0:
        total_status = "PARTIAL_COST_ESTIMATE"
    else:
        total_status = "COMPLETE_COST_ESTIMATE"

    return AutoCamCostEstimate(
        material_cost=material_cost_item,
        machine_cost=machine_cost_item,
        tool_cost=tool_cost_item,
        setup_cost=setup_cost_item,
        labor_cost=labor_cost_item,
        energy_cost=energy_cost_item,
        overhead_cost=overhead_cost_item,
        other_cost=other_cost_item,
        known_total=round(known_total, 4) if known_total is not None else None,
        unknown_component_count=unknown_count,
        completeness_pct=completeness_pct,
        total_status=total_status,
        currency=resolved_currency,
        computed_at=datetime.now(UTC).isoformat(),
        cost_input_received=True,
        warnings=warnings,
    )
