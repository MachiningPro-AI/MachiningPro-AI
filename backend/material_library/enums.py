"""Enumerations for the Material Library domain package.

Design constraints
------------------
FABRICATED_MATERIAL_PROPERTY=NO
MISSING_VALUE_AS_NONE=YES
UNKNOWN_TREATED_AS_KNOWN=NO
ISO_GROUP_GATES_MACHINE_VERDICT=NO
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "MaterialISOGroup",
    "MaterialSubGroup",
    "MaterialFamily",
    "EvidenceGrade",
    "DataConfidence",
    "MaterialCatalogStatus",
    "HardnessScale",
]


class MaterialISOGroup(StrEnum):
    """ISO 513 chip-forming material groups.

    Aligned with backend.machine_library.material_context.MaterialISOGroup.
    """

    P = "P"       # Steels (carbon, alloy, structural, cast)
    M = "M"       # Stainless steel (austenitic, ferritic, duplex)
    K = "K"       # Cast iron (grey, nodular, vermicular, malleable)
    N = "N"       # Non-ferrous (aluminium, copper, brass, bronze)
    S = "S"       # Superalloys and titanium
    H = "H"       # Hardened materials (> ~45 HRC)
    UNKNOWN = "UNKNOWN"


class MaterialSubGroup(StrEnum):
    """ISO 513 sub-group classification."""

    P_STEEL = "P_STEEL"
    M_STAINLESS = "M_STAINLESS"
    K_CAST_IRON = "K_CAST_IRON"
    N_ALUMINUM = "N_ALUMINUM"
    N_COPPER = "N_COPPER"
    S_TITANIUM = "S_TITANIUM"
    S_NICKEL_HRSA = "S_NICKEL_HRSA"
    H_HARDENED = "H_HARDENED"
    UNKNOWN = "UNKNOWN"


class MaterialFamily(StrEnum):
    """Broad material family classification (non-ISO, for browsing)."""

    STEEL = "steel"
    STAINLESS_STEEL = "stainless_steel"
    CAST_IRON = "cast_iron"
    ALUMINUM = "aluminum"
    COPPER_ALLOY = "copper_alloy"
    TITANIUM = "titanium"
    NICKEL_ALLOY = "nickel_alloy"
    OTHER = "other"
    UNKNOWN = "UNKNOWN"


class EvidenceGrade(StrEnum):
    """Provenance of a data point — mirrors Machine Library EvidenceGrade.

    Use the most conservative grade that accurately describes the source.
    Never promote ESTIMATED data to LITERATURE_REFERENCE.
    """

    MANUFACTURER_DATASHEET = "MANUFACTURER_DATASHEET"
    DISTRIBUTOR_SPEC_SHEET = "DISTRIBUTOR_SPEC_SHEET"
    LITERATURE_REFERENCE = "LITERATURE_REFERENCE"
    INTERNAL_MEASURED = "INTERNAL_MEASURED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"


class DataConfidence(StrEnum):
    """Field-level data confidence (aligns with existing backend/materials vocabulary)."""

    VERIFIED_STANDARD = "VERIFIED_STANDARD"   # Traceable to published standard
    GENERAL_INDUSTRY = "GENERAL_INDUSTRY"     # Widely accepted but not from one standard
    REFERENCE_ONLY = "REFERENCE_ONLY"         # Synthesis / general envelope, not OEM
    UNKNOWN = "UNKNOWN"


class MaterialCatalogStatus(StrEnum):
    """Lifecycle status of a catalog record."""

    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    DEPRECATED = "DEPRECATED"


class HardnessScale(StrEnum):
    """Hardness measurement scale — no silent conversion between scales."""

    HB = "HB"
    HRC = "HRC"
    HRB = "HRB"
    HV = "HV"
