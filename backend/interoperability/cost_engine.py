"""Level 8 — Manufacturing Cost and RFQ Intelligence engine.

Derives CostIntelligenceResult from Level-7 CycleTimeIntelligenceResult
and optional financial inputs.  All calculations are deterministic and traceable.

HARD RULES:
  - Do NOT fabricate manufacturing cost.
  - Do NOT fabricate material price, machine hourly rate, labor rate.
  - Do NOT fabricate setup cost, tooling cost, inspection cost.
  - Do NOT fabricate scrap percentage, overhead, profit/margin.
  - Do NOT fabricate logistics cost or currency conversion.
  - UNKNOWN financial inputs MUST remain None — never become zero.
  - Manufacturing cost MUST remain separate from selling price.
  - Generic/reference rates MUST NOT be represented as actual company rates.
  - Quotation MUST NOT be presented as complete when required inputs missing.
  - No implied currency conversion without verified FX rate.
"""

from __future__ import annotations

import uuid

from backend.interoperability.cost_intelligence import (
    UNKNOWN_COST,
    CommercialInputs,
    CostDriver,
    CostDriverType,
    CostEvidence,
    CostFidelity,
    CostIntelligenceResult,
    CostModelStatus,
    CostReductionOpportunity,
    CostReductionOpportunityType,
    CostSourceType,
    ManufacturingCostResult,
    MarkupType,
    QuoteCandidate,
    QuoteCompleteness,
    QuoteFidelity,
    QuoteStatus,
    RfqModel,
    SellingPriceResult,
    WhatIfScenario,
)
from backend.interoperability.cycle_time_intelligence import (
    CycleTimeIntelligenceResult,
)


def _make_plan_id() -> str:
    return f"MCI-{uuid.uuid4().hex[:12].upper()}"


# ---------------------------------------------------------------------------
# Machine cost calculation
# ---------------------------------------------------------------------------


def calculate_machine_cost(
    machine_time_min: float | None,
    machine_rate: CostEvidence,
) -> CostEvidence:
    """machine_cost = machine_time_hours × machine_rate_per_hour.

    Returns UNKNOWN_COST when either input is missing.
    Does NOT invent a machine hourly rate.
    """
    if machine_time_min is None or machine_rate.is_unknown:
        warnings = []
        if machine_time_min is None:
            warnings.append("machine_time_min unknown — machine cost cannot be calculated")
        if machine_rate.is_unknown:
            warnings.append("machine_rate unknown — machine cost cannot be calculated")
        return CostEvidence(
            value=None,
            currency=machine_rate.currency,
            unit_basis="per_part",
            source_type=CostSourceType.UNKNOWN,
            evidence="MACHINE_COST=UNKNOWN: missing inputs",
            status="UNKNOWN",
            warnings=tuple(warnings),
        )

    machine_time_h = machine_time_min / 60.0
    cost_val = machine_time_h * machine_rate.value  # type: ignore[operator]
    formula = (
        f"machine_cost = {machine_time_min:.4f} min / 60 × {machine_rate.value} "
        f"{machine_rate.currency or ''}/{machine_rate.unit_basis or 'h'} "
        f"= {cost_val:.4f} {machine_rate.currency or ''}"
    )
    return CostEvidence(
        value=cost_val,
        currency=machine_rate.currency,
        unit_basis="per_part",
        source_type=CostSourceType.CALCULATED,
        source_name=machine_rate.source_name,
        evidence=formula,
        status="CALCULATED",
        warnings=(
            (f"machine_rate source: {machine_rate.source_type.value}",)
            if machine_rate.is_generic
            else ()
        ),
    )


# ---------------------------------------------------------------------------
# Labor cost calculation
# ---------------------------------------------------------------------------


def calculate_labor_cost(
    labor_hours: float | None,
    labor_rate: CostEvidence,
) -> CostEvidence:
    """labor_cost = labor_hours × labor_rate.

    Returns UNKNOWN_COST when either input is missing.
    Does NOT assume one operator per machine for the full cycle.
    """
    if labor_hours is None or labor_rate.is_unknown:
        return UNKNOWN_COST
    cost_val = labor_hours * labor_rate.value  # type: ignore[operator]
    formula = (
        f"labor_cost = {labor_hours:.4f} h × {labor_rate.value} "
        f"{labor_rate.currency or ''}/{labor_rate.unit_basis or 'h'} "
        f"= {cost_val:.4f} {labor_rate.currency or ''}"
    )
    return CostEvidence(
        value=cost_val,
        currency=labor_rate.currency,
        unit_basis="per_part",
        source_type=CostSourceType.CALCULATED,
        source_name=labor_rate.source_name,
        evidence=formula,
        status="CALCULATED",
        warnings=(
            (f"labor_rate source: {labor_rate.source_type.value}",)
            if labor_rate.is_generic
            else ()
        ),
    )


# ---------------------------------------------------------------------------
# Setup amortization
# ---------------------------------------------------------------------------


def calculate_setup_amortization(
    setup_cost_total: CostEvidence,
    quantity: int,
) -> CostEvidence:
    """setup_cost_per_part = setup_cost_total / quantity.

    Returns UNKNOWN_COST when setup_cost_total is unknown or quantity <= 0.
    """
    if setup_cost_total.is_unknown or quantity <= 0:
        return UNKNOWN_COST
    per_part = setup_cost_total.value / quantity  # type: ignore[operator]
    formula = (
        f"setup_per_part = {setup_cost_total.value} / {quantity} = {per_part:.4f} "
        f"{setup_cost_total.currency or ''}"
    )
    return CostEvidence(
        value=per_part,
        currency=setup_cost_total.currency,
        unit_basis="per_part",
        source_type=CostSourceType.CALCULATED,
        evidence=formula,
        status="CALCULATED",
    )


# ---------------------------------------------------------------------------
# Selling price calculation (commercial layer — strictly separate)
# ---------------------------------------------------------------------------


def calculate_selling_price(
    manufacturing_cost: float,
    currency: str | None,
    commercial_inputs: CommercialInputs,
) -> SellingPriceResult:
    """Calculate selling price — ONLY when manufacturing cost AND margin are known.

    selling_price = cost × (1 + markup)   [MARKUP mode]
    gross_margin = (price − cost) / price  [must equal gross_margin_pct/100]

    Manufacturing cost and selling price MUST remain separate.
    If commercial inputs are not supplied, selling_price remains UNKNOWN.
    """
    if not commercial_inputs.has_margin_input:
        return SellingPriceResult(
            selling_price=UNKNOWN_COST,
            warnings=("No margin/markup configured — SELLING_PRICE=UNKNOWN",),
        )

    if commercial_inputs.markup_pct is not None:
        markup = commercial_inputs.markup_pct / 100.0
        price = manufacturing_cost * (1.0 + markup)
        gm = (price - manufacturing_cost) / price if price > 0 else None
        formula = (
            f"selling_price = {manufacturing_cost:.4f} × (1 + {commercial_inputs.markup_pct}%)"
            f" = {price:.4f} {currency or ''}"
        )
        return SellingPriceResult(
            selling_price=CostEvidence(
                value=price,
                currency=currency,
                unit_basis="per_part",
                source_type=CostSourceType.CALCULATED,
                evidence=formula,
                status="CALCULATED",
            ),
            markup_applied=commercial_inputs.markup_pct,
            gross_margin_applied=round(gm * 100, 4) if gm is not None else None,
            markup_type=MarkupType.MARKUP,
            formula=formula,
        )

    if commercial_inputs.gross_margin_pct is not None:
        gm_frac = commercial_inputs.gross_margin_pct / 100.0
        if gm_frac >= 1.0:
            return SellingPriceResult(
                selling_price=UNKNOWN_COST,
                warnings=(
                    f"gross_margin_pct={commercial_inputs.gross_margin_pct} >= 100% is invalid",
                ),
            )
        price = manufacturing_cost / (1.0 - gm_frac)
        markup_equiv = price / manufacturing_cost - 1.0 if manufacturing_cost > 0 else None
        formula = (
            f"selling_price = {manufacturing_cost:.4f}"
            f" / (1 - {commercial_inputs.gross_margin_pct}%)"
            f" = {price:.4f} {currency or ''}"
        )
        return SellingPriceResult(
            selling_price=CostEvidence(
                value=price,
                currency=currency,
                unit_basis="per_part",
                source_type=CostSourceType.CALCULATED,
                evidence=formula,
                status="CALCULATED",
            ),
            gross_margin_applied=commercial_inputs.gross_margin_pct,
            markup_applied=round(markup_equiv * 100, 4) if markup_equiv is not None else None,
            markup_type=MarkupType.GROSS_MARGIN,
            formula=formula,
        )

    return SellingPriceResult(
        selling_price=UNKNOWN_COST,
        warnings=("No margin/markup configured",),
    )


# ---------------------------------------------------------------------------
# Scrap / yield application
# ---------------------------------------------------------------------------


def apply_scrap_yield(
    base_cost: float | None,
    yield_fraction: float | None,
    currency: str | None,
    base_evidence: str = "",
) -> CostEvidence:
    """Apply scrap/yield to a base cost.

    effective_cost = base_cost / yield_fraction
    Only valid when both inputs are present and 0 < yield_fraction <= 1.
    Does NOT assign default scrap percentages.
    """
    if base_cost is None or yield_fraction is None:
        return UNKNOWN_COST
    if not (0 < yield_fraction <= 1):
        return CostEvidence(
            value=None,
            source_type=CostSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=(f"yield_fraction={yield_fraction} is outside (0, 1] — invalid",),
        )
    effective = base_cost / yield_fraction
    formula = (
        f"effective_cost = {base_cost:.4f} / {yield_fraction:.4f} = {effective:.4f} "
        f"[{base_evidence}]"
    )
    return CostEvidence(
        value=effective,
        currency=currency,
        unit_basis="per_part",
        source_type=CostSourceType.CALCULATED,
        evidence=formula,
        status="CALCULATED",
    )


# ---------------------------------------------------------------------------
# Cost aggregation
# ---------------------------------------------------------------------------


def _aggregate_known_components(
    components: list[tuple[str, CostEvidence]],
    currency: str | None,
) -> tuple[float | None, list[str], list[str]]:
    """Sum known cost components.  Returns (total|None, known_names, unknown_names)."""
    total: float = 0.0
    known_names: list[str] = []
    unknown_names: list[str] = []
    has_any = False
    for name, ev in components:
        if ev.is_known:
            if ev.currency != currency and ev.currency is not None and currency is not None:
                unknown_names.append(f"{name}[CURRENCY_MISMATCH:{ev.currency}!={currency}]")
            else:
                total += ev.value  # type: ignore[operator]
                known_names.append(name)
                has_any = True
        else:
            unknown_names.append(name)
    return (total if has_any else None), known_names, unknown_names


# ---------------------------------------------------------------------------
# Cost driver analysis
# ---------------------------------------------------------------------------


def _derive_cost_drivers(
    result: ManufacturingCostResult,
) -> tuple[CostDriver, ...]:
    """Identify cost drivers from calculated values only.

    No arbitrary labels — only flagged when share > threshold.
    """
    if result.known_cost_subtotal is None or result.known_cost_subtotal <= 0:
        return ()

    total = result.known_cost_subtotal
    drivers: list[CostDriver] = []
    threshold = 0.30  # Flag if > 30% of known cost total

    checks: list[tuple[str, CostEvidence, CostDriverType]] = [
        ("machine_cost", result.machine_cost, CostDriverType.HIGH_MACHINE_TIME_COST),
        ("material_cost", result.material_cost, CostDriverType.HIGH_MATERIAL_COST),
        ("setup_cost", result.setup_cost, CostDriverType.HIGH_SETUP_COST),
        ("tooling_cost", result.tooling_cost, CostDriverType.HIGH_TOOLING_COST),
        ("inspection_cost", result.inspection_cost, CostDriverType.HIGH_INSPECTION_COST),
        ("subcontract_cost", result.subcontract_cost, CostDriverType.HIGH_SUBCONTRACT_COST),
        ("programming_cost", result.programming_cost, CostDriverType.HIGH_PROGRAMMING_COST),
        ("overhead_cost", result.overhead_cost, CostDriverType.HIGH_OVERHEAD_COST),
    ]
    for comp_name, evidence, driver_type in checks:
        if evidence.is_known:
            share = evidence.value / total  # type: ignore[operator]
            if share > threshold:
                drivers.append(
                    CostDriver(
                        driver_type=driver_type,
                        component_ref=comp_name,
                        share_pct=round(share * 100, 2),
                        description=(
                            f"{comp_name} = {evidence.value:.4f} "
                            f"({share * 100:.1f}% of known cost)"
                        ),
                        evidence=evidence.evidence,
                    )
                )
    # Sort by share descending
    drivers.sort(key=lambda d: d.share_pct or 0, reverse=True)
    return tuple(drivers)


# ---------------------------------------------------------------------------
# Cost reduction opportunities
# ---------------------------------------------------------------------------


def _derive_cost_reduction_opportunities(
    result: ManufacturingCostResult,
    drivers: tuple[CostDriver, ...],
) -> tuple[CostReductionOpportunity, ...]:
    """Identify cost reduction opportunity candidates.

    MUST NOT claim savings — only flag candidates.
    """
    opps: list[CostReductionOpportunity] = []

    # Setup amortization opportunity: setup cost known and quantity low
    if (
        result.setup_cost.is_known
        and result.quantity is not None
        and result.quantity < 25
    ):
        opps.append(CostReductionOpportunity(
            opportunity_type=CostReductionOpportunityType.SETUP_AMORTIZATION_OPPORTUNITY,
            description=(
                f"Setup cost amortization candidate: quantity={result.quantity}, "
                f"higher batch quantity would reduce per-part setup cost"
            ),
            affected_component="setup",
        ))

    # Machine time review: machine time is a top driver
    for d in drivers:
        if d.driver_type == CostDriverType.HIGH_MACHINE_TIME_COST:
            opps.append(CostReductionOpportunity(
                opportunity_type=CostReductionOpportunityType.MACHINE_TIME_REVIEW_CANDIDATE,
                description="Machine time is a high cost driver — cycle time review candidate",
                affected_component="machine_cost",
            ))
            break

    # Material utilization review
    for d in drivers:
        if d.driver_type == CostDriverType.HIGH_MATERIAL_COST:
            opps.append(CostReductionOpportunity(
                opportunity_type=CostReductionOpportunityType.MATERIAL_UTILIZATION_REVIEW,
                description=(
                    "Material cost is a high driver"
                    " — stock/near-net-shape review candidate"
                ),
                affected_component="material_cost",
            ))
            break

    # Subcontract review
    for d in drivers:
        if d.driver_type == CostDriverType.HIGH_SUBCONTRACT_COST:
            opps.append(CostReductionOpportunity(
                opportunity_type=CostReductionOpportunityType.SUBCONTRACT_REVIEW_CANDIDATE,
                description=(
                    "Subcontract cost is a high driver"
                    " — in-house/alternative review candidate"
                ),
                affected_component="subcontract_cost",
            ))
            break

    # Quantity break opportunity
    if result.setup_cost.is_known and result.quantity is not None:
        opps.append(CostReductionOpportunity(
            opportunity_type=CostReductionOpportunityType.QUANTITY_BREAK_OPPORTUNITY,
            description="Evaluate higher quantity breaks for setup amortization benefit",
            affected_component="setup",
        ))

    return tuple(opps)


# ---------------------------------------------------------------------------
# Quote completeness check
# ---------------------------------------------------------------------------


def check_quote_completeness(
    rfq: RfqModel,
    cost_result: ManufacturingCostResult,
    machine_rate: CostEvidence,
    cti: CycleTimeIntelligenceResult | None,
) -> QuoteCompleteness:
    """Evaluate quote completeness.  Returns list of missing inputs."""
    missing: list[str] = []

    quantity_known = rfq.has_quantity
    if not quantity_known:
        missing.append("QUANTITY_UNKNOWN")

    currency_known = rfq.has_currency
    if not currency_known:
        missing.append("CURRENCY_UNKNOWN")

    material_status_known = rfq.material is not None
    if not material_status_known:
        missing.append("MATERIAL_UNKNOWN")

    cycle_time_acceptable = (
        cti is not None
        and cti.has_any_known_time
    )
    if not cycle_time_acceptable:
        missing.append("CYCLE_TIME_INCOMPLETE")

    machine_rate_supplied = machine_rate.is_known
    if not machine_rate_supplied:
        missing.append("MACHINE_RATE_NOT_SUPPLIED")

    # Labor policy: at least some labor cost evidence or explicit acknowledgement
    labor_policy_known = cost_result.labor_cost.is_known
    if not labor_policy_known:
        missing.append("LABOR_POLICY_UNKNOWN")

    # Setup cost acknowledged (either known or explicitly noted as not applicable)
    setup_cost_acknowledged = (
        cost_result.setup_cost.is_known
        or "SETUP" in " ".join(cost_result.warnings)
    )
    if not setup_cost_acknowledged:
        missing.append("SETUP_COST_NOT_ACKNOWLEDGED")

    # Subcontract: if subcontract_cost is unknown, flag for review
    unknown_subcontract_reviewed = not cost_result.subcontract_cost.is_unknown or (
        "SUBCONTRACT" in " ".join(cost_result.warnings)
    )

    is_complete = len(missing) == 0

    return QuoteCompleteness(
        quantity_known=quantity_known,
        currency_known=currency_known,
        material_status_known=material_status_known,
        cycle_time_acceptable=cycle_time_acceptable,
        machine_rate_supplied=machine_rate_supplied,
        labor_policy_known=labor_policy_known,
        setup_cost_acknowledged=setup_cost_acknowledged,
        unknown_subcontract_reviewed=unknown_subcontract_reviewed,
        missing_inputs=tuple(missing),
        is_complete=is_complete,
    )


# ---------------------------------------------------------------------------
# Quote status derivation
# ---------------------------------------------------------------------------


def _derive_quote_status(
    completeness: QuoteCompleteness,
    cost_result: ManufacturingCostResult,
    commercial: CommercialInputs | None,
) -> QuoteStatus:
    """Derive quote status — MUST NOT auto-advance to READY_TO_QUOTE with open items."""
    if not completeness.quantity_known or not completeness.currency_known:
        return QuoteStatus.DRAFT
    if not completeness.cycle_time_acceptable or not completeness.machine_rate_supplied:
        return QuoteStatus.ENGINEERING_REVIEW_REQUIRED
    if cost_result.status == CostModelStatus.INSUFFICIENT_DATA:
        return QuoteStatus.ENGINEERING_REVIEW_REQUIRED
    if cost_result.status == CostModelStatus.PARTIAL:
        return QuoteStatus.COST_PARTIAL
    if commercial is None or not commercial.has_margin_input:
        return QuoteStatus.READY_FOR_COMMERCIAL_INPUT
    if completeness.is_complete:
        return QuoteStatus.READY_TO_QUOTE
    return QuoteStatus.COST_PARTIAL


# ---------------------------------------------------------------------------
# Cost fidelity derivation
# ---------------------------------------------------------------------------


def _derive_cost_fidelity(
    cost_result: ManufacturingCostResult,
    machine_rate: CostEvidence,
    cti: CycleTimeIntelligenceResult | None,
) -> CostFidelity:
    """Deterministic fidelity classification — no arbitrary percentages."""
    from backend.interoperability.cycle_time_intelligence import CycleTimeFidelity

    if cost_result.status == CostModelStatus.INSUFFICIENT_DATA:
        return CostFidelity.INSUFFICIENT
    if not cost_result.has_any_known_cost:
        return CostFidelity.INSUFFICIENT

    # Check cycle time fidelity
    ct_fidelity = (
        cti.part_cycle_time.cycle_time_fidelity
        if cti is not None
        else None
    )

    # Check if machine rate is company/verified rate
    machine_rate_quality = machine_rate.is_company_rate if machine_rate.is_known else False

    has_material = cost_result.material_cost.is_known
    has_machine = cost_result.machine_cost.is_known

    if (
        ct_fidelity is not None
        and ct_fidelity in (CycleTimeFidelity.HIGH, CycleTimeFidelity.MEDIUM)
        and machine_rate_quality
        and has_material
        and has_machine
    ):
        return CostFidelity.HIGH

    if has_machine or has_material:
        # Check if generic rates used
        if machine_rate.is_generic:
            return CostFidelity.LOW
        return CostFidelity.MEDIUM

    return CostFidelity.LOW


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------


def derive_cost_intelligence(
    cti: CycleTimeIntelligenceResult | None,
    machine_rate: CostEvidence | None = None,
    labor_rate: CostEvidence | None = None,
    setup_cost_total: CostEvidence | None = None,
    material_cost: CostEvidence | None = None,
    tooling_cost: CostEvidence | None = None,
    inspection_cost: CostEvidence | None = None,
    subcontract_cost: CostEvidence | None = None,
    overhead_cost: CostEvidence | None = None,
    programming_cost_total: CostEvidence | None = None,
    rfq: RfqModel | None = None,
    commercial_inputs: CommercialInputs | None = None,
    quantity_breaks: list[int] | None = None,
    currency: str | None = None,
) -> CostIntelligenceResult:
    """Derive manufacturing cost and RFQ intelligence from Level-7 output.

    All financial inputs are optional.  Missing inputs stay UNKNOWN — never zero.
    Does NOT fabricate any cost input.
    Returns a CostIntelligenceResult with full provenance and status.
    """
    plan_id = _make_plan_id()
    machine_rate_ev = machine_rate or UNKNOWN_COST
    labor_rate_ev = labor_rate or UNKNOWN_COST
    setup_cost_total_ev = setup_cost_total or UNKNOWN_COST
    material_cost_ev = material_cost or UNKNOWN_COST
    tooling_cost_ev = tooling_cost or UNKNOWN_COST
    inspection_cost_ev = inspection_cost or UNKNOWN_COST
    subcontract_cost_ev = subcontract_cost or UNKNOWN_COST
    overhead_cost_ev = overhead_cost or UNKNOWN_COST
    programming_cost_total_ev = programming_cost_total or UNKNOWN_COST

    warnings: list[str] = []
    evidence: list[str] = []

    # Derive machine time from Level-7 cycle time intelligence
    machine_time_min: float | None = None
    if cti is not None:
        pct = cti.part_cycle_time
        if pct.known_cutting_time_min is not None:
            machine_time_min = pct.known_cutting_time_min
            evidence.append(
                f"machine_time_min={machine_time_min:.4f} from Level-7 cycle time "
                f"(fidelity={pct.cycle_time_fidelity.value})"
            )
        else:
            warnings.append(
                "cycle_time known_cutting_time_min=UNKNOWN — machine cost cannot be calculated"
            )

    # Calculate machine cost
    machine_cost_ev = calculate_machine_cost(machine_time_min, machine_rate_ev)
    if machine_cost_ev.is_known:
        evidence.append(machine_cost_ev.evidence)
    if machine_cost_ev.warnings:
        warnings.extend(machine_cost_ev.warnings)

    # Calculate labor cost (using machine time as proxy for cutting labor hours)
    # NOTE: We do NOT assume one operator per machine for full cycle.
    # Labor hours must be supplied explicitly; machine time is NOT auto-used here.
    labor_cost_ev = UNKNOWN_COST
    if labor_rate_ev.is_known:
        warnings.append("LABOR_HOURS_NOT_SUPPLIED — cannot calculate labor cost from rate alone")

    # Setup amortization
    rfq_obj = rfq or RfqModel()
    quantity = rfq_obj.quantity
    setup_cost_per_part_ev = UNKNOWN_COST
    programming_cost_per_part_ev = UNKNOWN_COST
    if quantity is not None and quantity > 0:
        if setup_cost_total_ev.is_known:
            setup_cost_per_part_ev = calculate_setup_amortization(setup_cost_total_ev, quantity)
            evidence.append(setup_cost_per_part_ev.evidence)
        if programming_cost_total_ev.is_known:
            programming_cost_per_part_ev = calculate_setup_amortization(
                programming_cost_total_ev, quantity
            )
    setup_cost_ev = setup_cost_per_part_ev

    # Programming cost per part
    programming_cost_ev = programming_cost_per_part_ev

    # Determine currency from inputs
    resolved_currency = currency
    if resolved_currency is None:
        for ev in [machine_cost_ev, material_cost_ev, machine_rate_ev]:
            if ev.is_known and ev.currency:
                resolved_currency = ev.currency
                break

    # Aggregate known cost components
    all_components: list[tuple[str, CostEvidence]] = [
        ("material_cost", material_cost_ev),
        ("machine_cost", machine_cost_ev),
        ("labor_cost", labor_cost_ev),
        ("setup_cost", setup_cost_ev),
        ("programming_cost", programming_cost_ev),
        ("tooling_cost", tooling_cost_ev),
        ("consumables_cost", UNKNOWN_COST),
        ("inspection_cost", inspection_cost_ev),
        ("subcontract_cost", subcontract_cost_ev),
        ("scrap_effect", UNKNOWN_COST),
        ("rework_cost", UNKNOWN_COST),
        ("packaging_cost", UNKNOWN_COST),
        ("logistics_cost", UNKNOWN_COST),
        ("overhead_cost", overhead_cost_ev),
    ]

    known_total, known_names, unknown_names = _aggregate_known_components(
        all_components, resolved_currency
    )

    if known_names:
        evidence.append(
            f"known_cost_subtotal = sum({known_names})"
            f" = {known_total:.4f} {resolved_currency or ''}"
        )

    # Determine cost model status
    if known_total is None:
        cost_status = CostModelStatus.INSUFFICIENT_DATA
    elif unknown_names:
        cost_status = CostModelStatus.PARTIAL
    else:
        cost_status = CostModelStatus.COMPLETE

    # Build unit cost result
    unit_cost_result = ManufacturingCostResult(
        material_cost=material_cost_ev,
        machine_cost=machine_cost_ev,
        labor_cost=labor_cost_ev,
        setup_cost=setup_cost_ev,
        programming_cost=programming_cost_ev,
        tooling_cost=tooling_cost_ev,
        inspection_cost=inspection_cost_ev,
        subcontract_cost=subcontract_cost_ev,
        overhead_cost=overhead_cost_ev,
        known_cost_subtotal=known_total,
        known_cost_currency=resolved_currency,
        unknown_cost_components=tuple(unknown_names),
        quantity=quantity,
        setup_cost_per_part=setup_cost_per_part_ev,
        programming_cost_per_part=programming_cost_per_part_ev,
        status=cost_status,
        fidelity=_derive_cost_fidelity(
            ManufacturingCostResult(
                known_cost_subtotal=known_total,
                unknown_cost_components=tuple(unknown_names),
                status=cost_status,
                machine_cost=machine_cost_ev,
                material_cost=material_cost_ev,
            ),
            machine_rate_ev,
            cti,
        ),
        evidence=tuple(evidence),
        warnings=tuple(warnings),
    )

    # Quantity scenarios (what-if)
    q_scenarios: list[WhatIfScenario] = []
    for q in (quantity_breaks or []):
        if q <= 0:
            continue
        q_setup = calculate_setup_amortization(setup_cost_total_ev, q)
        q_prog = calculate_setup_amortization(programming_cost_total_ev, q)
        # Rebuild known components for this quantity
        q_components: list[tuple[str, CostEvidence]] = [
            ("material_cost", material_cost_ev),
            ("machine_cost", machine_cost_ev),
            ("labor_cost", labor_cost_ev),
            ("setup_cost", q_setup),
            ("programming_cost", q_prog),
            ("tooling_cost", tooling_cost_ev),
            ("inspection_cost", inspection_cost_ev),
            ("subcontract_cost", subcontract_cost_ev),
            ("overhead_cost", overhead_cost_ev),
        ]
        q_total, q_known, q_unknown = _aggregate_known_components(
            q_components, resolved_currency
        )
        q_status = (
            CostModelStatus.COMPLETE
            if not q_unknown
            else (
                CostModelStatus.PARTIAL
                if q_total is not None
                else CostModelStatus.INSUFFICIENT_DATA
            )
        )
        q_cost = ManufacturingCostResult(
            material_cost=material_cost_ev,
            machine_cost=machine_cost_ev,
            labor_cost=labor_cost_ev,
            setup_cost=q_setup,
            programming_cost=q_prog,
            tooling_cost=tooling_cost_ev,
            inspection_cost=inspection_cost_ev,
            subcontract_cost=subcontract_cost_ev,
            overhead_cost=overhead_cost_ev,
            known_cost_subtotal=q_total,
            known_cost_currency=resolved_currency,
            unknown_cost_components=tuple(q_unknown),
            quantity=q,
            setup_cost_per_part=q_setup,
            programming_cost_per_part=q_prog,
            status=q_status,
        )
        # Delta vs baseline
        delta: float | None = None
        if q_total is not None and known_total is not None:
            delta = q_total - known_total

        q_scenarios.append(WhatIfScenario(
            scenario_id=f"Q{q}",
            scenario_label=f"Quantity={q}",
            quantity=q,
            cost_result=q_cost,
            delta_vs_baseline=delta,
        ))

    # Cost drivers
    drivers = _derive_cost_drivers(unit_cost_result)

    # Cost reduction opportunities
    opps = _derive_cost_reduction_opportunities(unit_cost_result, drivers)

    # Selling price (commercial layer)
    selling_price_result = SellingPriceResult(
        selling_price=UNKNOWN_COST,
        warnings=("SELLING_PRICE=UNKNOWN: no commercial inputs provided",),
    )
    if commercial_inputs is not None and known_total is not None:
        selling_price_result = calculate_selling_price(
            known_total, resolved_currency, commercial_inputs
        )

    # Quote candidate
    completeness = check_quote_completeness(rfq_obj, unit_cost_result, machine_rate_ev, cti)
    quote_status = _derive_quote_status(completeness, unit_cost_result, commercial_inputs)
    quote_fidelity = QuoteFidelity(unit_cost_result.fidelity.value)

    quote_candidate = QuoteCandidate(
        rfq_ref=rfq_obj.rfq_id,
        quantity=quantity,
        manufacturing_cost=unit_cost_result,
        selling_price=selling_price_result,
        currency=resolved_currency,
        quote_status=quote_status,
        fidelity=quote_fidelity,
        completeness=completeness,
        engineering_warnings=tuple(warnings),
        commercial_warnings=selling_price_result.warnings,
        evidence=tuple(evidence),
    )

    # Overall status
    overall_status = cost_status
    overall_fidelity = unit_cost_result.fidelity
    missing_inputs_list = list(completeness.missing_inputs)

    return CostIntelligenceResult(
        plan_id=plan_id,
        recognition_basis=(
            "Level-7 cycle time intelligence"
            if cti is not None
            else "No cycle time intelligence available"
        ),
        unit_cost_result=unit_cost_result,
        quantity_scenarios=tuple(q_scenarios),
        rfq=rfq_obj,
        quote_candidate=quote_candidate,
        quote_completeness=completeness,
        cost_drivers=drivers,
        cost_reduction_opportunities=opps,
        status=overall_status,
        fidelity=overall_fidelity,
        has_any_known_cost=unit_cost_result.has_any_known_cost,
        missing_inputs=tuple(missing_inputs_list),
        warnings=tuple(warnings),
    )
