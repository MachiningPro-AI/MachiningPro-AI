"""Machine Library — isolated domain package for CNC machine catalog.

Provides structured domain models, a registry, validation rules,
and an import pipeline for the MachiningPro AI machine catalog.

Supports all 12 machine classes:
  3_AXIS_VMC, 4_AXIS_VMC, 5_AXIS_VMC, HMC,
  CNC_LATHE, TURN_MILL, SWISS_LATHE, DRILL_TAP_CENTER,
  SURFACE_GRINDER, CYLINDRICAL_GRINDER, WIRE_EDM, SINKER_EDM

Design constraints
------------------
MISSING_VALUE_AS_ZERO=NO
SYNTHETIC_SPECIFICATIONS_ADDED=NO
FABRICATED_MACHINE_SPEC=NO
FAIL_CLOSED=YES
"""

from backend.machine_library.enums import (
    AxisType,
    EvidenceGrade,
    MachineCatalogStatus,
    MachineClass,
)
from backend.machine_library.models import (
    MachineAxisSpecification,
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)
from backend.machine_library.registry import MachineCatalogError, MachineCatalogRegistry
from backend.machine_library.validation import (
    MachineCatalogValidationResult,
    validate_machine_catalog_record,
)

__all__ = [
    # Enums
    "AxisType",
    "EvidenceGrade",
    "MachineCatalogStatus",
    "MachineClass",
    # Models
    "MachineAxisSpecification",
    "MachineCapability",
    "MachineCatalogRecord",
    "MachineEnvelope",
    "MachineSourceMetadata",
    "MachineSpindleSpecification",
    # Registry
    "MachineCatalogError",
    "MachineCatalogRegistry",
    # Validation
    "MachineCatalogValidationResult",
    "validate_machine_catalog_record",
]
