"""Level 8 — Manufacturing Cost and RFQ Intelligence domain model.

Extends Level-7 cycle-time intelligence with deterministic manufacturing
cost derivation, RFQ data model, quote candidate, and cost reduction
opportunity foundation.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate manufacturing cost.
  - Do NOT fabricate material price.
  - Do NOT fabricate machine hourly rate.
  - Do NOT fabricate labor rate.
  - Do NOT fabricate setup cost.
  - Do NOT fabricate tooling cost.
  - Do NOT fabricate inspection cost.
  - Do NOT fabricate subcontracting cost.
  - Do NOT fabricate scrap percentage.
  - Do NOT fabricate overhead.
  - Do NOT fabricate profit or commercial margin.
  - Do NOT fabricate logistics cost.
  - Do NOT fabricate currency conversion.
  - UNKNOWN financial inputs MUST remain UNKNOWN.
  - UNKNOWN cost components MUST NOT silently become zero.
  - Engineering manufacturing cost and commercial selling price MUST remain separate.
  - Quotation MUST NOT be presented as complete when required commercial inputs missing.
  - Every monetary value MUST preserve source, currency, unit basis, evidence, validity.
  - Generic/reference rates MUST NOT be represented as actual company rates.
  - Preserve Levels 1-7 backward compatibility.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum

__all__ = [
    # Source / provenance
    "CostSourceType",
    "CostEvidence",
    "UNKNOWN_COST",
    # Component taxonomy
    "CostComponentType",
    "CostComponent",
    # Cost model
    "CostModelStatus",
    "CostFidelity",
    "ManufacturingCostResult",
    # RFQ / quote
    "QuoteStatus",
    "QuoteFidelity",
    "RfqModel",
    "QuoteCandidate",
    "QuoteCompleteness",
    # Cost driver / reduction
    "CostDriverType",
    "CostDriver",
    "CostReductionOpportunityType",
    "CostReductionOpportunity",
    # What-if
    "WhatIfScenario",
    # Top-level result
    "CostIntelligenceResult",
]


# ---------------------------------------------------------------------------
# Cost source / provenance
# ---------------------------------------------------------------------------


class CostSourceType(StrEnum):
    """Classification of the evidence source for a cost input."""

    USER_DEFINED = "USER_DEFINED"
    COMPANY_RATE = "COMPANY_RATE"
    SUPPLIER_QUOTE = "SUPPLIER_QUOTE"
    PURCHASE_HISTORY = "PURCHASE_HISTORY"
    ERP_VERIFIED = "ERP_VERIFIED"
    OBSERVED = "OBSERVED"
    HISTORICAL_VALIDATED = "HISTORICAL_VALIDATED"
    MARKET_REFERENCE = "MARKET_REFERENCE"
    GENERIC_REFERENCE = "GENERIC_REFERENCE"
    CALCULATED = "CALCULATED"
    UNKNOWN = "UNKNOWN"


@dataclasses.dataclass(frozen=True)
class CostEvidence:
    """A single cost evidence record with mandatory provenance.

    None value means UNKNOWN — not zero, not estimated, not fabricated.
    Every non-None value MUST have an explicit source_type.
    Generic/reference rates MUST NOT be represented as actual company rates.
    """

    value: float | None = None
    currency: str | None = None
    unit_basis: str | None = None
    source_type: CostSourceType = CostSourceType.UNKNOWN
    source_name: str | None = None
    effective_date: str | None = None
    valid_from: str | None = None
    valid_to: str | None = None
    evidence: str = ""
    status: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @property
    def is_unknown(self) -> bool:
        return self.value is None

    @property
    def is_company_rate(self) -> bool:
        return self.source_type in (
            CostSourceType.COMPANY_RATE,
            CostSourceType.ERP_VERIFIED,
        )

    @property
    def is_generic(self) -> bool:
        return self.source_type in (
            CostSourceType.GENERIC_REFERENCE,
            CostSourceType.MARKET_REFERENCE,
        )


UNKNOWN_COST = CostEvidence(
    value=None,
    currency=None,
    unit_basis=None,
    source_type=CostSourceType.UNKNOWN,
    source_name=None,
    effective_date=None,
    evidence="",
    status="UNKNOWN",
    warnings=(),
)


# ---------------------------------------------------------------------------
# Cost component taxonomy
# ---------------------------------------------------------------------------


class CostComponentType(StrEnum):
    """Classification of an individual manufacturing cost component."""

    RAW_MATERIAL = "RAW_MATERIAL"
    MACHINE_TIME = "MACHINE_TIME"
    DIRECT_LABOR = "DIRECT_LABOR"
    SETUP = "SETUP"
    PROGRAMMING = "PROGRAMMING"
    TOOLING = "TOOLING"
    CONSUMABLES = "CONSUMABLES"
    WORKHOLDING = "WORKHOLDING"
    INSPECTION = "INSPECTION"
    QUALITY = "QUALITY"
    DEBURRING = "DEBURRING"
    HEAT_TREATMENT = "HEAT_TREATMENT"
    SURFACE_TREATMENT = "SURFACE_TREATMENT"
    GRINDING = "GRINDING"
    EDM = "EDM"
    SUBCONTRACTING = "SUBCONTRACTING"
    SCRAP = "SCRAP"
    REWORK_ALLOWANCE = "REWORK_ALLOWANCE"
    PACKAGING = "PACKAGING"
    LOGISTICS = "LOGISTICS"
    OVERHEAD = "OVERHEAD"
    OTHER = "OTHER"


@dataclasses.dataclass(frozen=True)
class CostComponent:
    """A single manufacturing cost component with full provenance.

    cost is UNKNOWN when financial input is missing — it MUST NOT become zero.
    formula describes the derivation path for explainability.
    """

    component_type: CostComponentType
    cost: CostEvidence
    formula: str = ""
    basis_description: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.cost.is_known

    @property
    def is_unknown(self) -> bool:
        return self.cost.is_unknown


# ---------------------------------------------------------------------------
# Material cost support
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MaterialCostInputs:
    """Inputs required for material cost calculation.

    All fields are optional/unknown by default — only filled when evidence exists.
    """

    material_grade: str | None = None
    stock_form: str | None = None
    stock_mass_kg: float | None = None
    finished_mass_kg: float | None = None
    stock_volume_mm3: float | None = None
    density_kg_mm3: float | None = None
    price_per_kg: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    price_per_length: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    stock_length_mm: float | None = None

    @property
    def has_mass_basis(self) -> bool:
        return self.stock_mass_kg is not None and self.price_per_kg.is_known

    @property
    def has_length_basis(self) -> bool:
        return self.stock_length_mm is not None and self.price_per_length.is_known

    @property
    def material_utilization(self) -> float | None:
        if self.finished_mass_kg is not None and self.stock_mass_kg is not None:
            if self.stock_mass_kg > 0:
                return self.finished_mass_kg / self.stock_mass_kg
        return None


# ---------------------------------------------------------------------------
# Tooling cost support
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ToolingCostEvidence:
    """Evidence for tooling cost per part.

    tool_purchase_cost: full tool cost
    insert_cost: cost per insert (for indexable tools)
    usable_edges: number of usable cutting edges per insert
    tool_life_min: total usable tool life in minutes
    tool_life_consumption_min: cutting time consumed per part in minutes
    """

    tool_ref: str = ""
    tool_purchase_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    insert_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    usable_edges: int | None = None
    tool_life_min: float | None = None
    tool_life_consumption_min: float | None = None

    @property
    def effective_edge_cost(self) -> CostEvidence:
        """Cost per cutting edge = insert_cost / usable_edges."""
        if self.insert_cost.is_known and self.usable_edges and self.usable_edges > 0:
            val = self.insert_cost.value / self.usable_edges  # type: ignore[operator]
            return CostEvidence(
                value=val,
                currency=self.insert_cost.currency,
                unit_basis="per_edge",
                source_type=CostSourceType.CALCULATED,
                evidence=f"insert_cost / usable_edges = "
                         f"{self.insert_cost.value} / {self.usable_edges}",
                status="CALCULATED",
            )
        return UNKNOWN_COST

    @property
    def tool_cost_per_part(self) -> CostEvidence:
        """Fraction of tool cost consumed per part."""
        # Try insert-based calculation
        edge_cost = self.effective_edge_cost
        if (
            edge_cost.is_known
            and self.tool_life_min is not None
            and self.tool_life_consumption_min is not None
            and self.tool_life_min > 0
        ):
            fraction = self.tool_life_consumption_min / self.tool_life_min
            val = fraction * edge_cost.value  # type: ignore[operator]
            return CostEvidence(
                value=val,
                currency=edge_cost.currency,
                unit_basis="per_part",
                source_type=CostSourceType.CALCULATED,
                evidence=(
                    f"fraction={self.tool_life_consumption_min:.4f}/{self.tool_life_min:.4f}"
                    f" × edge_cost={edge_cost.value}"
                ),
                status="CALCULATED",
            )
        # Try solid-tool calculation
        if (
            self.tool_purchase_cost.is_known
            and self.tool_life_min is not None
            and self.tool_life_consumption_min is not None
            and self.tool_life_min > 0
        ):
            fraction = self.tool_life_consumption_min / self.tool_life_min
            val = fraction * self.tool_purchase_cost.value  # type: ignore[operator]
            return CostEvidence(
                value=val,
                currency=self.tool_purchase_cost.currency,
                unit_basis="per_part",
                source_type=CostSourceType.CALCULATED,
                evidence=(
                    f"fraction={self.tool_life_consumption_min:.4f}/{self.tool_life_min:.4f}"
                    f" × purchase_cost={self.tool_purchase_cost.value}"
                ),
                status="CALCULATED",
            )
        return UNKNOWN_COST


# ---------------------------------------------------------------------------
# Manufacturing cost result
# ---------------------------------------------------------------------------


class CostModelStatus(StrEnum):
    """Completeness status of a manufacturing cost result."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICT = "CONFLICT"


class CostFidelity(StrEnum):
    """Fidelity classification for a manufacturing cost estimate.

    HIGH: validated cycle time + current material price + validated machine/labor rates
          + known tooling + known secondary process cost.
    MEDIUM: derived/estimated inputs — some components known.
    LOW: generic or incomplete rates.
    INSUFFICIENT: critical financial data absent.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


@dataclasses.dataclass(frozen=True)
class ManufacturingCostResult:
    """Deterministic manufacturing cost result — engineering cost only.

    All cost components are CostEvidence.  None/UNKNOWN values are preserved.
    known_cost_total is ONLY computed from known components.
    If significant components are UNKNOWN, status is PARTIAL — the known
    subtotal MUST NOT be labelled as 'total manufacturing cost'.
    """

    # Individual cost components
    material_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    machine_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    labor_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    setup_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    programming_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    tooling_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    consumables_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    inspection_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    subcontract_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    scrap_effect: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    rework_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    packaging_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    logistics_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    overhead_cost: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)

    # Aggregated
    known_cost_subtotal: float | None = None  # sum of known components only
    known_cost_currency: str | None = None
    unknown_cost_components: tuple[str, ...] = ()

    # Quantity context
    quantity: int | None = None
    setup_cost_per_part: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    programming_cost_per_part: CostEvidence = dataclasses.field(
        default_factory=lambda: UNKNOWN_COST
    )
    batch_fixed_cost: float | None = None
    batch_recurring_cost: float | None = None
    total_batch_cost: float | None = None

    # Status and fidelity
    status: CostModelStatus = CostModelStatus.INSUFFICIENT_DATA
    fidelity: CostFidelity = CostFidelity.INSUFFICIENT
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def has_any_known_cost(self) -> bool:
        return self.known_cost_subtotal is not None

    @property
    def all_components_known(self) -> bool:
        return len(self.unknown_cost_components) == 0


# ---------------------------------------------------------------------------
# Scrap / yield support
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class ScrapYieldModel:
    """Scrap and yield model — only used when input evidence exists.

    0 < yield_fraction <= 1 is validated.
    Default scrap percentages MUST NOT be assigned.
    """

    yield_fraction: float | None = None
    scrap_rate: float | None = None
    source: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.yield_fraction is not None

    def effective_cost_multiplier(self) -> float | None:
        """effective_cost = base_cost / yield — only when yield is known and valid."""
        if self.yield_fraction is not None and 0 < self.yield_fraction <= 1:
            return 1.0 / self.yield_fraction
        return None


# ---------------------------------------------------------------------------
# Commercial layer — strict separation from engineering cost
# ---------------------------------------------------------------------------


class MarkupType(StrEnum):
    """Markup vs. gross margin — these are NOT interchangeable."""

    MARKUP = "MARKUP"         # selling_price = cost × (1 + markup)
    GROSS_MARGIN = "GROSS_MARGIN"  # margin = (price − cost) / price


@dataclasses.dataclass(frozen=True)
class CommercialInputs:
    """Commercial inputs required for selling-price calculation.

    These are strictly separate from engineering manufacturing cost.
    If not supplied, selling_price MUST remain UNKNOWN.
    """

    markup_pct: float | None = None          # None = not provided
    gross_margin_pct: float | None = None    # None = not provided
    markup_type: MarkupType | None = None
    risk_contingency_pct: float | None = None
    sales_adjustment: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    source: CostSourceType = CostSourceType.UNKNOWN
    warnings: tuple[str, ...] = ()

    @property
    def has_margin_input(self) -> bool:
        return self.markup_pct is not None or self.gross_margin_pct is not None


@dataclasses.dataclass(frozen=True)
class SellingPriceResult:
    """Selling price — computed ONLY when manufacturing_cost and margin both known.

    Manufacturing cost and selling price MUST remain separate.
    """

    selling_price: CostEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_COST)
    markup_applied: float | None = None
    gross_margin_applied: float | None = None
    markup_type: MarkupType | None = None
    formula: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.selling_price.is_known


# ---------------------------------------------------------------------------
# Currency safety model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CurrencyConversion:
    """Currency conversion — only valid when FX rate is explicitly supplied.

    No implicit or fabricated FX rates allowed.
    """

    from_currency: str
    to_currency: str
    fx_rate: float | None = None
    fx_source: str | None = None
    effective_date: str | None = None
    warnings: tuple[str, ...] = ()

    @property
    def is_verified(self) -> bool:
        return (
            self.fx_rate is not None
            and self.fx_source is not None
            and self.effective_date is not None
        )


# ---------------------------------------------------------------------------
# RFQ model (vendor-neutral, original MachiningPro AI structure)
# ---------------------------------------------------------------------------


class RfqStatus(StrEnum):
    """Lifecycle status of an RFQ."""

    DRAFT = "DRAFT"
    ENGINEERING_REVIEW_REQUIRED = "ENGINEERING_REVIEW_REQUIRED"
    COST_PARTIAL = "COST_PARTIAL"
    READY_FOR_COMMERCIAL_INPUT = "READY_FOR_COMMERCIAL_INPUT"
    READY_TO_QUOTE = "READY_TO_QUOTE"
    QUOTED = "QUOTED"


@dataclasses.dataclass(frozen=True)
class RfqModel:
    """Vendor-neutral RFQ model — MachiningPro AI original structure.

    Does NOT copy Tofaş/Stellantis/OEM templates.
    Does NOT require customer-confidential fields.
    """

    rfq_id: str = ""
    customer_reference: str | None = None
    project_reference: str | None = None
    part_number: str | None = None
    part_name: str | None = None
    drawing_revision: str | None = None
    quantity: int | None = None
    annual_volume: int | None = None
    material: str | None = None
    delivery_target: str | None = None
    currency: str | None = None
    # File references to existing engineering import results
    cad_file_ref: str | None = None
    drawing_file_ref: str | None = None
    attachment_refs: tuple[str, ...] = ()
    # Technical requirements
    technical_requirements: tuple[str, ...] = ()
    notes: str | None = None
    # Status
    status: RfqStatus = RfqStatus.DRAFT
    warnings: tuple[str, ...] = ()

    @property
    def has_quantity(self) -> bool:
        return self.quantity is not None and self.quantity > 0

    @property
    def has_currency(self) -> bool:
        return self.currency is not None and len(self.currency) > 0


# ---------------------------------------------------------------------------
# Quote status and fidelity
# ---------------------------------------------------------------------------


class QuoteStatus(StrEnum):
    """Status of a quote candidate."""

    DRAFT = "DRAFT"
    ENGINEERING_REVIEW_REQUIRED = "ENGINEERING_REVIEW_REQUIRED"
    COST_PARTIAL = "COST_PARTIAL"
    READY_FOR_COMMERCIAL_INPUT = "READY_FOR_COMMERCIAL_INPUT"
    READY_TO_QUOTE = "READY_TO_QUOTE"
    QUOTED = "QUOTED"


class QuoteFidelity(StrEnum):
    """Fidelity classification for a quote.

    HIGH: validated cycle time + current material price + validated rates + known tooling.
    MEDIUM: some components derived/estimated.
    LOW: generic or incomplete rates.
    INSUFFICIENT: critical financial data absent.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


@dataclasses.dataclass(frozen=True)
class QuoteCompleteness:
    """Completeness check result for a quote.

    Lists mandatory inputs that are missing or unacknowledged.
    Quote MUST NOT move to READY_TO_QUOTE with open mandatory items.
    """

    quantity_known: bool = False
    currency_known: bool = False
    material_status_known: bool = False
    cycle_time_acceptable: bool = False
    machine_rate_supplied: bool = False
    labor_policy_known: bool = False
    setup_cost_acknowledged: bool = False
    unknown_subcontract_reviewed: bool = False
    missing_inputs: tuple[str, ...] = ()
    is_complete: bool = False


@dataclasses.dataclass(frozen=True)
class QuoteCandidate:
    """A quote candidate produced from engineering + (optional) commercial inputs.

    manufacturing_cost and selling_price are always kept separate.
    selling_price is UNKNOWN when margin not supplied.
    """

    rfq_ref: str = ""
    quantity: int | None = None
    manufacturing_cost: ManufacturingCostResult = dataclasses.field(
        default_factory=ManufacturingCostResult
    )
    selling_price: SellingPriceResult = dataclasses.field(
        default_factory=SellingPriceResult
    )
    currency: str | None = None
    quote_status: QuoteStatus = QuoteStatus.DRAFT
    fidelity: QuoteFidelity = QuoteFidelity.INSUFFICIENT
    completeness: QuoteCompleteness = dataclasses.field(default_factory=QuoteCompleteness)
    engineering_warnings: tuple[str, ...] = ()
    commercial_warnings: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Cost driver analysis
# ---------------------------------------------------------------------------


class CostDriverType(StrEnum):
    """Classification of a cost driver — derived from calculated values only."""

    HIGH_MACHINE_TIME_COST = "HIGH_MACHINE_TIME_COST"
    HIGH_MATERIAL_COST = "HIGH_MATERIAL_COST"
    HIGH_SETUP_COST = "HIGH_SETUP_COST"
    HIGH_TOOLING_COST = "HIGH_TOOLING_COST"
    HIGH_INSPECTION_COST = "HIGH_INSPECTION_COST"
    HIGH_SUBCONTRACT_COST = "HIGH_SUBCONTRACT_COST"
    LOW_MATERIAL_UTILIZATION = "LOW_MATERIAL_UTILIZATION"
    HIGH_PROGRAMMING_COST = "HIGH_PROGRAMMING_COST"
    HIGH_OVERHEAD_COST = "HIGH_OVERHEAD_COST"
    HIGH_SCRAP_EFFECT = "HIGH_SCRAP_EFFECT"


@dataclasses.dataclass(frozen=True)
class CostDriver:
    """A single identified cost driver — only from calculated values."""

    driver_type: CostDriverType
    component_ref: str
    share_pct: float | None = None  # % of known cost total — None if not calculable
    description: str = ""
    evidence: str = ""
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Cost reduction opportunities
# ---------------------------------------------------------------------------


class CostReductionOpportunityType(StrEnum):
    """Classification of a cost reduction opportunity — candidates only.

    MUST NOT claim savings unless alternate scenario is actually recalculated.
    """

    SETUP_AMORTIZATION_OPPORTUNITY = "SETUP_AMORTIZATION_OPPORTUNITY"
    MACHINE_TIME_REVIEW_CANDIDATE = "MACHINE_TIME_REVIEW_CANDIDATE"
    TOOL_LIFE_IMPROVEMENT_CANDIDATE = "TOOL_LIFE_IMPROVEMENT_CANDIDATE"
    MATERIAL_UTILIZATION_REVIEW = "MATERIAL_UTILIZATION_REVIEW"
    INSPECTION_SCOPE_REVIEW = "INSPECTION_SCOPE_REVIEW"
    PROCESS_CONSOLIDATION_CANDIDATE = "PROCESS_CONSOLIDATION_CANDIDATE"
    SUBCONTRACT_REVIEW_CANDIDATE = "SUBCONTRACT_REVIEW_CANDIDATE"
    QUANTITY_BREAK_OPPORTUNITY = "QUANTITY_BREAK_OPPORTUNITY"


@dataclasses.dataclass(frozen=True)
class CostReductionOpportunity:
    """A candidate cost reduction opportunity — no fabricated savings."""

    opportunity_type: CostReductionOpportunityType
    description: str = ""
    affected_component: str = ""
    candidate_only: bool = True  # Always True — no fabricated savings
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# What-if scenario support
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class WhatIfScenario:
    """A controlled what-if scenario — only recalculated values compared.

    Baseline is never altered silently.
    """

    scenario_id: str = ""
    scenario_label: str = ""
    quantity: int | None = None
    cost_result: ManufacturingCostResult = dataclasses.field(
        default_factory=ManufacturingCostResult
    )
    delta_vs_baseline: float | None = None  # None unless both scenarios have known cost
    warnings: tuple[str, ...] = ()


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CostIntelligenceResult:
    """Top-level Level-8 manufacturing cost and RFQ intelligence result.

    Derived from Level-7 CycleTimeIntelligenceResult plus optional financial inputs.
    """

    # Plan reference
    plan_id: str = ""
    recognition_basis: str = ""

    # Cost model
    unit_cost_result: ManufacturingCostResult = dataclasses.field(
        default_factory=ManufacturingCostResult
    )
    quantity_scenarios: tuple[WhatIfScenario, ...] = ()

    # RFQ and quote
    rfq: RfqModel = dataclasses.field(default_factory=RfqModel)
    quote_candidate: QuoteCandidate = dataclasses.field(default_factory=QuoteCandidate)
    quote_completeness: QuoteCompleteness = dataclasses.field(default_factory=QuoteCompleteness)

    # Analysis
    cost_drivers: tuple[CostDriver, ...] = ()
    cost_reduction_opportunities: tuple[CostReductionOpportunity, ...] = ()

    # Overall status
    status: CostModelStatus = CostModelStatus.INSUFFICIENT_DATA
    fidelity: CostFidelity = CostFidelity.INSUFFICIENT
    has_any_known_cost: bool = False
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def operation_count(self) -> int:
        return 0  # Reserved for future operation-level cost breakdown
