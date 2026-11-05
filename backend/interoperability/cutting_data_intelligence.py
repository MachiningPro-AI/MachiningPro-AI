"""Level 6 — Cutting Data and Catalog Intelligence domain model.

Extends Level-5 machine/tool selection with deterministic cutting-data
requirement derivation, explicit units, source provenance, RPM/feed/MRR
foundations, tool-life evidence, and a vendor-neutral catalog record model.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate cutting speeds.
  - Do NOT fabricate feeds.
  - Do NOT fabricate depth or width of cut.
  - Do NOT fabricate tool-life values.
  - Do NOT invent commercial catalog data.
  - Do NOT present generic reference ranges as vendor-certified data.
  - Every cutting-data recommendation MUST preserve source/provenance.
  - Unknown material/tool/process information MUST remain UNKNOWN.
  - Preserve Levels 1-5 backward compatibility.
"""

from __future__ import annotations

import dataclasses
import math
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CuttingDataSourceType(StrEnum):
    """Provenance of a cutting-data record.

    Lower values → higher authority in the precedence order:
      1 VERIFIED_VENDOR_CATALOG
      2 VERIFIED_STANDARD
      3 VERIFIED_INTERNAL_DATA
      4 ENGINEERING_RULE
      5 GENERIC_REFERENCE_RANGE
      6 USER_DEFINED
      7 UNKNOWN
    """

    VERIFIED_VENDOR_CATALOG = "VERIFIED_VENDOR_CATALOG"
    VERIFIED_STANDARD = "VERIFIED_STANDARD"
    VERIFIED_INTERNAL_DATA = "VERIFIED_INTERNAL_DATA"
    ENGINEERING_RULE = "ENGINEERING_RULE"
    GENERIC_REFERENCE_RANGE = "GENERIC_REFERENCE_RANGE"
    USER_DEFINED = "USER_DEFINED"
    UNKNOWN = "UNKNOWN"


# Precedence: lower number = higher authority.
SOURCE_PRECEDENCE: dict[str, int] = {
    CuttingDataSourceType.VERIFIED_VENDOR_CATALOG: 1,
    CuttingDataSourceType.VERIFIED_STANDARD: 2,
    CuttingDataSourceType.VERIFIED_INTERNAL_DATA: 3,
    CuttingDataSourceType.ENGINEERING_RULE: 4,
    CuttingDataSourceType.GENERIC_REFERENCE_RANGE: 5,
    CuttingDataSourceType.USER_DEFINED: 6,
    CuttingDataSourceType.UNKNOWN: 7,
}


class CuttingSpeedUnit(StrEnum):
    M_PER_MIN = "m/min"
    SFM = "SFM"


class FeedUnit(StrEnum):
    MM_PER_TOOTH = "mm/tooth"
    MM_PER_REV = "mm/rev"
    MM_PER_MIN = "mm/min"


class LengthUnit(StrEnum):
    MM = "mm"


class SpindleUnit(StrEnum):
    RPM = "rpm"


class MRRUnit(StrEnum):
    MM3_PER_MIN = "mm3/min"
    CM3_PER_MIN = "cm3/min"


class OperationContext(StrEnum):
    """Semantic machining operation for cutting-data lookup."""

    FACE_MILLING = "FACE_MILLING"
    ROUGH_MILLING = "ROUGH_MILLING"
    FINISH_MILLING = "FINISH_MILLING"
    POCKET_MILLING = "POCKET_MILLING"
    SLOT_MILLING = "SLOT_MILLING"
    CONTOUR_MILLING = "CONTOUR_MILLING"
    DRILLING = "DRILLING"
    PECK_DRILLING = "PECK_DRILLING"
    CENTER_DRILLING = "CENTER_DRILLING"
    REAMING = "REAMING"
    BORING = "BORING"
    TAPPING = "TAPPING"
    THREAD_MILLING = "THREAD_MILLING"
    TURNING = "TURNING"
    FACING = "FACING"
    GROOVING = "GROOVING"
    PARTING = "PARTING"
    CHAMFERING = "CHAMFERING"
    UNKNOWN = "UNKNOWN"


class ToolMaterialClass(StrEnum):
    """Generic tool-material class — no specific grade or brand implied."""

    HSS = "HSS"
    HSS_E = "HSS_E"
    SOLID_CARBIDE = "SOLID_CARBIDE"
    CARBIDE_INSERT = "CARBIDE_INSERT"
    CERAMIC = "CERAMIC"
    CBN = "CBN"
    PCD = "PCD"
    UNKNOWN = "UNKNOWN"


class CoatingClass(StrEnum):
    """Generic coating class — no specific product or brand implied."""

    UNCOATED = "UNCOATED"
    TiN = "TiN"
    TiCN = "TiCN"
    TiAlN = "TiAlN"
    AlTiN = "AlTiN"
    AlCrN = "AlCrN"
    DLC = "DLC"
    DIAMOND = "DIAMOND"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class CoolantMode(StrEnum):
    DRY = "DRY"
    FLOOD = "FLOOD"
    MQL = "MQL"
    THROUGH_TOOL = "THROUGH_TOOL"
    AIR = "AIR"
    UNKNOWN = "UNKNOWN"


class CuttingDataStatus(StrEnum):
    VERIFIED = "VERIFIED"
    RULE_BASED = "RULE_BASED"
    GENERIC_REFERENCE = "GENERIC_REFERENCE"
    USER_DEFINED = "USER_DEFINED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    CONFLICT = "CONFLICT"
    UNKNOWN = "UNKNOWN"


class MachineConstraintStatus(StrEnum):
    WITHIN_MACHINE_LIMITS = "WITHIN_MACHINE_LIMITS"
    CONSTRAINED_BY_MACHINE = "CONSTRAINED_BY_MACHINE"
    OUTSIDE_MACHINE_LIMITS = "OUTSIDE_MACHINE_LIMITS"
    UNKNOWN = "UNKNOWN"


class ToolLifeSourceType(StrEnum):
    TAYLOR_EQUATION = "TAYLOR_EQUATION"
    OBSERVED_TOOL_LIFE = "OBSERVED_TOOL_LIFE"
    CATALOG_TOOL_LIFE_RANGE = "CATALOG_TOOL_LIFE_RANGE"
    EMPIRICAL_INTERNAL_MODEL = "EMPIRICAL_INTERNAL_MODEL"
    UNKNOWN = "UNKNOWN"


class CatalogLicenseStatus(StrEnum):
    OPEN = "OPEN"
    RESTRICTED = "RESTRICTED"
    PROPRIETARY = "PROPRIETARY"
    USER_SUPPLIED = "USER_SUPPLIED"
    UNKNOWN = "UNKNOWN"


class MaterialCondition(StrEnum):
    ANNEALED = "ANNEALED"
    NORMALIZED = "NORMALIZED"
    QUENCHED_TEMPERED = "QUENCHED_TEMPERED"
    HARDENED = "HARDENED"
    UNKNOWN = "UNKNOWN"


class HardnessUnit(StrEnum):
    HRC = "HRC"
    HRB = "HRB"
    HV = "HV"
    HB = "HB"
    UNKNOWN = "UNKNOWN"


class CuttingDataPlanStatus(StrEnum):
    COMPLETE = "COMPLETE"
    CANDIDATE_PLAN = "CANDIDATE_PLAN"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REQUIRES_INPUT = "REQUIRES_INPUT"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RangeValue:
    """An explicit-unit numerical range (min / nominal / max).

    None means unknown — not zero, not zero-width, not fabricated.
    """

    min_val: float | None = None
    nominal_val: float | None = None
    max_val: float | None = None
    unit: str = ""

    @property
    def is_known(self) -> bool:
        return self.min_val is not None or self.nominal_val is not None


# ---------------------------------------------------------------------------
# Provenance and material
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CuttingDataProvenance:
    """Mandatory provenance record for every cutting-data record.

    Every result that carries numerical cutting data MUST have a provenance
    record so the engineer can trace the origin and assess reliability.
    """

    source_type: CuttingDataSourceType = CuttingDataSourceType.UNKNOWN
    source_name: str = ""
    source_document: str = ""
    source_version: str = ""
    source_date: str = ""
    material_scope: str = ""
    tool_scope: str = ""
    operation_scope: str = ""
    validity_notes: str = ""
    confidence: str = ""
    license_status: CatalogLicenseStatus = CatalogLicenseStatus.UNKNOWN


@dataclasses.dataclass(frozen=True)
class MaterialRecord:
    """Deterministic material record.

    All optional fields remain None when not derivable from evidence.
    Unknown grade MUST remain UNKNOWN — do not invent it.
    """

    material_group: str = "UNKNOWN"
    material_grade: str | None = None
    condition: MaterialCondition = MaterialCondition.UNKNOWN
    hardness: float | None = None
    hardness_unit: HardnessUnit = HardnessUnit.UNKNOWN
    tensile_strength_mpa: float | None = None
    machinability_class: str | None = None
    evidence_notes: str = ""


# ---------------------------------------------------------------------------
# Cutting data record
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CuttingDataRecord:
    """A single cutting-data record with explicit units and mandatory provenance.

    All dimensional fields carry RangeValue with explicit unit strings.
    Missing values are None, never fabricated.
    """

    record_id: str
    material_group: str
    material_grade: str | None
    operation_type: OperationContext
    tool_family: str
    tool_material: ToolMaterialClass
    coating: CoatingClass
    diameter_min_mm: float | None
    diameter_max_mm: float | None
    vc_range: RangeValue
    fz_range: RangeValue
    fn_range: RangeValue
    ap_range: RangeValue
    ae_range: RangeValue
    coolant_mode: CoolantMode
    source: CuttingDataProvenance
    warnings: tuple[str, ...] = ()
    status: CuttingDataStatus = CuttingDataStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Calculation results
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class RPMResult:
    """Result of the spindle-speed calculation.

    n = (1000 × Vc) / (π × D)   [Vc in m/min, D in mm, n in rpm]

    All fields None when inputs are unavailable or invalid.
    formula documents the applied equation.
    """

    n_min: float | None = None
    n_nominal: float | None = None
    n_max: float | None = None
    unit: SpindleUnit = SpindleUnit.RPM
    formula: str = "n = (1000 × Vc) / (π × D)"
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_calculable(self) -> bool:
        return self.n_nominal is not None


@dataclasses.dataclass(frozen=True)
class FeedRateResult:
    """Result of the feed-rate calculation.

    Milling:  Vf = n × z × fz   [mm/min]
    Turning:  Vf = n × fn        [mm/min]

    All fields None when inputs are unavailable.
    """

    vf_min: float | None = None
    vf_nominal: float | None = None
    vf_max: float | None = None
    unit: FeedUnit = FeedUnit.MM_PER_MIN
    formula: str = ""
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_calculable(self) -> bool:
        return self.vf_nominal is not None


@dataclasses.dataclass(frozen=True)
class MRRResult:
    """Material Removal Rate foundation.

    Milling:  MRR = ae × ap × Vf   [mm³/min]
    Drilling: uses separate documented formulation.

    All fields None when inputs are unavailable.
    """

    mrr_min: float | None = None
    mrr_nominal: float | None = None
    mrr_max: float | None = None
    unit: MRRUnit = MRRUnit.MM3_PER_MIN
    formula: str = ""
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_calculable(self) -> bool:
        return self.mrr_nominal is not None


@dataclasses.dataclass(frozen=True)
class MachineConstraintResult:
    """Result of checking a computed value against a machine limit."""

    status: MachineConstraintStatus = MachineConstraintStatus.UNKNOWN
    applied_constraint: str = ""
    constrained_field: str = ""
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class ToolLifeEvidence:
    """Tool-life evidence record.

    Taylor's equation: V × T^n = C

    If C or n are absent, TOOL_LIFE=UNKNOWN — do not fabricate constants.
    All numerical fields are None when unknown.
    """

    source_type: ToolLifeSourceType = ToolLifeSourceType.UNKNOWN
    taylor_v: float | None = None
    taylor_t: float | None = None
    taylor_n_exp: float | None = None
    taylor_c: float | None = None
    observed_life_min: float | None = None
    observed_life_max: float | None = None
    catalog_life_min: float | None = None
    catalog_life_max: float | None = None
    life_unit: str = "min"
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def taylor_calculable(self) -> bool:
        """True only when ALL Taylor coefficients are present."""
        return (
            self.taylor_n_exp is not None
            and self.taylor_c is not None
            and self.taylor_v is not None
        )

    def compute_taylor_life(self) -> float | None:
        """T = (C / V)^(1/n) — None when any coefficient is missing."""
        if not self.taylor_calculable:
            return None
        if self.taylor_v is None or self.taylor_v <= 0:
            return None
        exp = self.taylor_n_exp
        if exp is None or exp <= 0:
            return None
        return (self.taylor_c / self.taylor_v) ** (1.0 / exp)  # type: ignore[operator]


# ---------------------------------------------------------------------------
# Catalog model
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CatalogRecord:
    """Vendor-neutral catalog record foundation.

    DO NOT populate with fabricated or unverified commercial data.
    manufacturer and catalog_name must be supplied by a verified, licensed source.
    """

    record_id: str
    manufacturer: str
    catalog_name: str
    product_family: str
    tool_family: str
    material_groups: tuple[str, ...] = ()
    diameter_min_mm: float | None = None
    diameter_max_mm: float | None = None
    geometry_description: str = ""
    grade: str = ""
    coating: CoatingClass = CoatingClass.UNKNOWN
    recommended_parameters: CuttingDataRecord | None = None
    source_document: str = ""
    source_version: str = ""
    license_status: CatalogLicenseStatus = CatalogLicenseStatus.UNKNOWN
    redistribution_permission: bool = False
    usage_restrictions: str = ""


# ---------------------------------------------------------------------------
# Cutting data candidate
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CuttingDataCandidate:
    """A single candidate cutting-data result for one operation/tool/material.

    Numerical fields are explicitly typed.  Missing data is None.
    source documents exactly where the range came from.
    """

    candidate_id: str
    material_record: MaterialRecord
    operation: OperationContext
    tool_family: str
    machine_requirement_ref: str = ""
    tool_requirement_ref: str = ""
    vc_range: RangeValue = dataclasses.field(default_factory=RangeValue)
    feed_range: RangeValue = dataclasses.field(default_factory=RangeValue)
    ap_range: RangeValue = dataclasses.field(default_factory=RangeValue)
    ae_range: RangeValue = dataclasses.field(default_factory=RangeValue)
    rpm_result: RPMResult = dataclasses.field(default_factory=RPMResult)
    feed_rate_result: FeedRateResult = dataclasses.field(default_factory=FeedRateResult)
    mrr_result: MRRResult = dataclasses.field(default_factory=MRRResult)
    machine_constraint: MachineConstraintResult = dataclasses.field(
        default_factory=MachineConstraintResult
    )
    coolant: CoolantMode = CoolantMode.UNKNOWN
    source: CuttingDataProvenance = dataclasses.field(
        default_factory=CuttingDataProvenance
    )
    status: CuttingDataStatus = CuttingDataStatus.UNKNOWN
    warnings: tuple[str, ...] = ()
    evidence_notes: str = ""


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CuttingDataIntelligenceResult:
    """Top-level Level-6 result attached to a CanonicalDocument.

    All collections are immutable tuples.
    No field may be fabricated.
    """

    plan_id: str
    status: CuttingDataPlanStatus
    recognition_basis: str
    material_record: MaterialRecord = dataclasses.field(
        default_factory=MaterialRecord
    )
    cutting_data_candidates: tuple[CuttingDataCandidate, ...] = ()
    catalog_matches: tuple[CatalogRecord, ...] = ()
    tool_life_evidence: tuple[ToolLifeEvidence, ...] = ()
    machine_constraint_results: tuple[MachineConstraintResult, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_mti_candidate_count: int = 0

    @property
    def candidate_count(self) -> int:
        return len(self.cutting_data_candidates)

    @property
    def has_cutting_data(self) -> bool:
        """True when at least one candidate carries a usable range."""
        return any(
            c.status in (
                CuttingDataStatus.VERIFIED,
                CuttingDataStatus.RULE_BASED,
                CuttingDataStatus.GENERIC_REFERENCE,
                CuttingDataStatus.USER_DEFINED,
            )
            for c in self.cutting_data_candidates
        )

    @property
    def has_verified_candidates(self) -> bool:
        return any(
            c.status == CuttingDataStatus.VERIFIED
            for c in self.cutting_data_candidates
        )


# ---------------------------------------------------------------------------
# RPM calculation utility (pure, no side effects)
# ---------------------------------------------------------------------------


def calculate_rpm(
    vc_m_per_min: float | None,
    diameter_mm: float | None,
) -> RPMResult:
    """Compute spindle speed using  n = (1000 × Vc) / (π × D).

    Parameters
    ----------
    vc_m_per_min:
        Cutting speed in m/min.  None → UNKNOWN result.
    diameter_mm:
        Tool/workpiece diameter in mm.  None or ≤ 0 → UNKNOWN result.

    Returns
    -------
    RPMResult with all None fields when inputs are unavailable or invalid.
    """
    warns: list[str] = []

    if vc_m_per_min is None:
        return RPMResult(
            warnings=("cutting speed (Vc) unknown — RPM cannot be calculated",),
            evidence_notes="Vc is None",
        )
    if diameter_mm is None:
        return RPMResult(
            warnings=("tool/workpiece diameter unknown — RPM cannot be calculated",),
            evidence_notes="D is None",
        )
    if diameter_mm <= 0:
        return RPMResult(
            warnings=(f"diameter must be > 0, got {diameter_mm} mm",),
            evidence_notes=f"D={diameter_mm} invalid",
        )
    if vc_m_per_min <= 0:
        warns.append(f"Vc must be > 0, got {vc_m_per_min} m/min")
        return RPMResult(warnings=tuple(warns), evidence_notes=f"Vc={vc_m_per_min} invalid")

    n = (1000.0 * vc_m_per_min) / (math.pi * diameter_mm)
    notes = f"n = (1000 × {vc_m_per_min}) / (π × {diameter_mm}) = {n:.2f} rpm"
    return RPMResult(
        n_nominal=round(n, 2),
        unit=SpindleUnit.RPM,
        formula="n = (1000 × Vc) / (π × D)",
        evidence_notes=notes,
    )


def calculate_milling_feed_rate(
    rpm: float | None,
    number_of_teeth: int | None,
    fz_mm_per_tooth: float | None,
) -> FeedRateResult:
    """Compute table feed using  Vf = n × z × fz.

    Parameters
    ----------
    rpm:
        Spindle speed in rpm.  None → UNKNOWN.
    number_of_teeth:
        Number of flutes/teeth.  None → UNKNOWN (do not fabricate).
    fz_mm_per_tooth:
        Feed per tooth in mm/tooth.  None → UNKNOWN.
    """
    if rpm is None:
        return FeedRateResult(
            warnings=("RPM unknown — milling feed rate cannot be calculated",),
            formula="Vf = n × z × fz",
        )
    if number_of_teeth is None:
        return FeedRateResult(
            warnings=(
                "number_of_teeth unknown — milling feed rate cannot be calculated; "
                "do not fabricate tooth count",
            ),
            formula="Vf = n × z × fz",
        )
    if fz_mm_per_tooth is None:
        return FeedRateResult(
            warnings=("fz unknown — milling feed rate cannot be calculated",),
            formula="Vf = n × z × fz",
        )
    if rpm <= 0 or number_of_teeth <= 0 or fz_mm_per_tooth <= 0:
        return FeedRateResult(
            warnings=("invalid input — all values must be > 0",),
            formula="Vf = n × z × fz",
        )

    vf = rpm * number_of_teeth * fz_mm_per_tooth
    notes = (
        f"Vf = {rpm:.2f} × {number_of_teeth} × {fz_mm_per_tooth} = {vf:.3f} mm/min"
    )
    return FeedRateResult(
        vf_nominal=round(vf, 3),
        unit=FeedUnit.MM_PER_MIN,
        formula="Vf = n × z × fz",
        evidence_notes=notes,
    )


def calculate_turning_feed_rate(
    rpm: float | None,
    fn_mm_per_rev: float | None,
) -> FeedRateResult:
    """Compute feed rate using  Vf = n × fn.

    Parameters
    ----------
    rpm:
        Spindle speed in rpm.
    fn_mm_per_rev:
        Feed per revolution in mm/rev.
    """
    if rpm is None:
        return FeedRateResult(
            warnings=("RPM unknown — turning feed rate cannot be calculated",),
            formula="Vf = n × fn",
        )
    if fn_mm_per_rev is None:
        return FeedRateResult(
            warnings=("fn unknown — turning feed rate cannot be calculated",),
            formula="Vf = n × fn",
        )
    if rpm <= 0 or fn_mm_per_rev <= 0:
        return FeedRateResult(
            warnings=("invalid input — all values must be > 0",),
            formula="Vf = n × fn",
        )

    vf = rpm * fn_mm_per_rev
    notes = f"Vf = {rpm:.2f} × {fn_mm_per_rev} = {vf:.3f} mm/min"
    return FeedRateResult(
        vf_nominal=round(vf, 3),
        unit=FeedUnit.MM_PER_MIN,
        formula="Vf = n × fn",
        evidence_notes=notes,
    )


def calculate_milling_mrr(
    ae_mm: float | None,
    ap_mm: float | None,
    vf_mm_per_min: float | None,
) -> MRRResult:
    """Compute MRR using  MRR = ae × ap × Vf.

    All inputs must be known and > 0.
    """
    if ae_mm is None or ap_mm is None or vf_mm_per_min is None:
        return MRRResult(
            warnings=("ae, ap, or Vf unknown — MRR cannot be calculated",),
            formula="MRR = ae × ap × Vf",
        )
    if ae_mm <= 0 or ap_mm <= 0 or vf_mm_per_min <= 0:
        return MRRResult(
            warnings=("invalid input — ae, ap, Vf must all be > 0",),
            formula="MRR = ae × ap × Vf",
        )

    mrr = ae_mm * ap_mm * vf_mm_per_min
    notes = f"MRR = {ae_mm} × {ap_mm} × {vf_mm_per_min:.3f} = {mrr:.2f} mm³/min"
    return MRRResult(
        mrr_nominal=round(mrr, 2),
        unit=MRRUnit.MM3_PER_MIN,
        formula="MRR = ae × ap × Vf",
        evidence_notes=notes,
    )
