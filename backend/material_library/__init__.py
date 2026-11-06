"""Material Library — isolated domain package for the MachiningPro AI material catalog.

Provides structured data models, a deterministic registry, ISO-based classification,
machinability profiles, tool compatibility matrices, and cutting reference envelopes
for 19 seed material grades across ISO groups P, M, K, N, and S.

Design constraints
------------------
FABRICATED_MATERIAL_PROPERTY=NO
MISSING_VALUE_AS_NONE=YES
CUTTING_ENVELOPE_IS_NOT_OEM_SPEC=YES
REFERENCE_ONLY_CUTTING_DATA=YES
FAIL_CLOSED=YES
DUPLICATE_STABLE_ID_RAISES=YES
ISO_GROUP_GATES_MACHINE_VERDICT=NO

ISO groups supported
--------------------
  P — Steel (carbon, alloy, structural)
  M — Stainless steel (austenitic, ferritic, duplex, PH)
  K — Cast iron (grey, nodular)
  N — Non-ferrous (aluminium alloys, copper alloys)
  S — Superalloys and titanium (S_TITANIUM / S_NICKEL_HRSA)
  H — Hardened (catalog expansion ready; no seed records yet)
"""

from backend.material_library.enums import (
    DataConfidence,
    EvidenceGrade,
    HardnessScale,
    MaterialCatalogStatus,
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)
from backend.material_library.models import (
    MachinabilityProfile,
    MaterialCatalogRecord,
    MaterialCondition,
    MaterialCuttingRef,
    MaterialDesignation,
    MaterialHardnessEntry,
    MaterialProperty,
    MaterialSourceMetadata,
    MaterialToolCompatEntry,
)
from backend.material_library.registry import MaterialCatalogError, MaterialCatalogRegistry
from backend.material_library.validation import (
    MaterialValidationIssue,
    MaterialValidationResult,
    validate_material_catalog_record,
)

__all__ = [
    # Enums
    "DataConfidence",
    "EvidenceGrade",
    "HardnessScale",
    "MaterialCatalogStatus",
    "MaterialFamily",
    "MaterialISOGroup",
    "MaterialSubGroup",
    # Models
    "MachinabilityProfile",
    "MaterialCatalogRecord",
    "MaterialCondition",
    "MaterialCuttingRef",
    "MaterialDesignation",
    "MaterialHardnessEntry",
    "MaterialProperty",
    "MaterialSourceMetadata",
    "MaterialToolCompatEntry",
    # Registry
    "MaterialCatalogError",
    "MaterialCatalogRegistry",
    # Validation
    "MaterialValidationIssue",
    "MaterialValidationResult",
    "validate_material_catalog_record",
]
