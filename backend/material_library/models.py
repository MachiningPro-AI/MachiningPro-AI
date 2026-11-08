"""Pydantic data models for the Material Library domain package.

FABRICATED_MATERIAL_PROPERTY=NO
MISSING_VALUE_AS_NONE=YES
CUTTING_ENVELOPE_IS_NOT_OEM_SPEC=YES
REFERENCE_ONLY_CUTTING_DATA=YES
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.material_library.enums import (
    DataConfidence,
    EvidenceGrade,
    HardnessScale,
    MaterialCatalogStatus,
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)

__all__ = [
    "MaterialHardnessEntry",
    "MaterialCondition",
    "MaterialDesignation",
    "MaterialProperty",
    "MachinabilityProfile",
    "MaterialToolCompatEntry",
    "MaterialCuttingRef",
    "MaterialSourceMetadata",
    "MaterialCatalogRecord",
]


class MaterialHardnessEntry(BaseModel):
    """A single hardness measurement — explicit scale, no silent conversion."""

    scale: HardnessScale
    value_min: float
    value_max: float
    confidence: DataConfidence = DataConfidence.VERIFIED_STANDARD
    source: str


class MaterialCondition(BaseModel):
    """Heat-treatment or delivery condition with condition-specific properties."""

    condition_code: str
    condition_label: str
    hardness: list[MaterialHardnessEntry] = []
    tensile_strength_mpa: float | None = None
    yield_strength_mpa: float | None = None
    elongation_pct: float | None = None
    confidence: DataConfidence = DataConfidence.VERIFIED_STANDARD
    source: str = ""


class MaterialDesignation(BaseModel):
    """Standard-system designations and known aliases for a material."""

    werkstoff_nr: str | None = None
    standard_en: str | None = None
    standard_din: str | None = None
    standard_aisi: str | None = None
    standard_uns: str | None = None
    aliases: list[str] = []


class MaterialProperty(BaseModel):
    """Bulk physical properties that are condition-independent.

    All fields are optional — None means the value is unknown, not zero.
    MISSING_VALUE_AS_NONE=YES  MISSING_VALUE_AS_ZERO=NO
    """

    density_kg_m3: float | None = None
    elastic_modulus_gpa: float | None = None
    thermal_conductivity_w_mk: float | None = None
    specific_heat_j_kgk: float | None = None
    thermal_expansion_um_mk: float | None = None
    melting_point_deg_c: float | None = None


class MachinabilityProfile(BaseModel):
    """Qualitative machinability metadata.

    All ratings are from the Programlar Sandvik synthesis (REFERENCE_ONLY).
    None means no data was found — it does not mean the value is LOW or zero.
    """

    chip_formation: str | None = None
    work_hardening: str | None = None
    bue_tendency: str | None = None
    abrasiveness: str | None = None
    thermal_load: str | None = None
    cutting_force: str | None = None
    tool_wear_rate: str | None = None
    coolant_guidance: str | None = None
    notes: str | None = None
    evidence_status: DataConfidence = DataConfidence.REFERENCE_ONLY
    source: str = "Programlar Sandvik synthesis"


class MaterialToolCompatEntry(BaseModel):
    """Tool-material compatibility rating (REFERENCE_ONLY Programlar matrix).

    Ratings: RECOMMENDED / ACCEPTABLE / CONDITIONAL / NOT_RECOMMENDED.
    CONDITIONAL requires condition_notes explaining when it applies.
    """

    tool_material: str
    rating: str
    condition_notes: str | None = None
    evidence_status: DataConfidence = DataConfidence.REFERENCE_ONLY
    source: str = "Programlar Sandvik synthesis"


class MaterialCuttingRef(BaseModel):
    """General-industry cutting parameter reference envelope.

    These are NOT OEM catalog values and must NEVER be presented as
    production parameters or quoted to customers.
    CUTTING_ENVELOPE_IS_NOT_OEM_SPEC=YES
    """

    operation: str
    tool_material: str
    vc_min_m_min: float | None = None
    vc_max_m_min: float | None = None
    fn_min_mm_rev: float | None = None
    fn_max_mm_rev: float | None = None
    fz_min_mm_tooth: float | None = None
    fz_max_mm_tooth: float | None = None
    ap_min_mm: float | None = None
    ap_max_mm: float | None = None
    evidence_status: DataConfidence = DataConfidence.REFERENCE_ONLY
    source: str = "Programlar general industry envelope"


class MaterialSourceMetadata(BaseModel):
    """Evidence provenance for a MaterialCatalogRecord."""

    data_confidence: DataConfidence = DataConfidence.VERIFIED_STANDARD
    source_document: str = ""
    evidence_grade: EvidenceGrade = EvidenceGrade.LITERATURE_REFERENCE
    notes: str | None = None


class MaterialCatalogRecord(BaseModel):
    """Canonical material record in the Material Library catalog.

    Design invariants:
    - stable_id is immutable once committed.
    - All optional numeric fields are None when unknown (never 0.0).
    - Cutting references are REFERENCE_ONLY and must not be used as OEM data.
    - ISO group and sub-group must be declared; UNKNOWN is allowed for new drafts.
    """

    # --- Identity ---
    stable_id: str
    designation: str

    # --- ISO classification ---
    iso_group: MaterialISOGroup
    iso_subgroup: MaterialSubGroup
    material_family: MaterialFamily

    # --- Standard designations and aliases ---
    designation_detail: MaterialDesignation = Field(
        default_factory=MaterialDesignation
    )

    # --- Bulk physical properties ---
    properties: MaterialProperty = Field(default_factory=MaterialProperty)

    # --- Condition-dependent properties ---
    conditions: list[MaterialCondition] = []

    # --- Machinability ---
    machinability: MachinabilityProfile | None = None

    # --- Tool compatibility ---
    tool_compatibility: list[MaterialToolCompatEntry] = []

    # --- Cutting reference envelopes ---
    cutting_references: list[MaterialCuttingRef] = []

    # --- Provenance ---
    source_metadata: MaterialSourceMetadata = Field(
        default_factory=MaterialSourceMetadata
    )

    # --- Lifecycle ---
    status: MaterialCatalogStatus = MaterialCatalogStatus.ACTIVE
