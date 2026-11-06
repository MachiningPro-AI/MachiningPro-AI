"""
Level-12 NC Postprocessor and Safe G-code module.

Architecture
------------
VerifiedToolpath → NCGenerationInput → NCProgram (IR) → PostProcessorProfile
→ NCCandidate (offline text) → NCGenerationManifest

Safety invariants
-----------------
NO_GCODE_DISPATCH=YES
NO_CNC_CONNECTION=YES
NO_FABRICATED_MACHINE_DATA=YES
OFFLINE_ONLY=YES
is_dispatchable=False (always)
VERIFIED toolpath required for NC generation
"""

from .enums import (
    ArcMode,
    AxisConfiguration,
    MachineClass,
    NCCoolantMode,
    NCCoordinateMode,
    NCCutterCompMode,
    NCFeedMode,
    NCGenerationBlockReason,
    NCMotionType,
    NCPlane,
    NCProgramStatus,
    NCSpindleDirection,
    NCStaleReason,
    NCUnitMode,
    PostCertificationStatus,
    WorkOffsetRef,
)
from .generator import (
    NCGenerationInput,
    NCGenerationResult,
    compute_program_hash,
    generate_nc,
    is_program_stale,
)
from .ir import (
    NCBlock,
    NCComment,
    NCCoolantCommand,
    NCCoordinateModeDeclaration,
    NCFeedCommand,
    NCMotion,
    NCPlaneDeclaration,
    NCProgram,
    NCSourceTrace,
    NCSpindleCommand,
    NCToolChange,
    NCUnitDeclaration,
    NCWorkOffsetDeclaration,
)
from .manifest import (
    NCGenerationManifest,
    build_manifest,
    check_manifest_staleness,
    serialize_blocks_for_hash,
)
from .postprocessor import (
    GENERIC_ISO_TEST,
    PROFILE_REGISTRY,
    BlockNumberConfig,
    NumericFormat,
    PostProcessorProfile,
    PostProcessorRequirement,
    get_profile,
)
from .validator import (
    ValidationIssue,
    ValidationResult,
    validate_nc_program,
)

__all__ = [
    # enums
    "ArcMode",
    "AxisConfiguration",
    "MachineClass",
    "NCCoordinateMode",
    "NCCoolantMode",
    "NCCutterCompMode",
    "NCFeedMode",
    "NCGenerationBlockReason",
    "NCMotionType",
    "NCPlane",
    "NCProgramStatus",
    "NCSpindleDirection",
    "NCStaleReason",
    "NCUnitMode",
    "PostCertificationStatus",
    "WorkOffsetRef",
    # ir
    "NCBlock",
    "NCComment",
    "NCCoolantCommand",
    "NCCoordinateModeDeclaration",
    "NCFeedCommand",
    "NCMotion",
    "NCPlaneDeclaration",
    "NCProgram",
    "NCSourceTrace",
    "NCSpindleCommand",
    "NCToolChange",
    "NCUnitDeclaration",
    "NCWorkOffsetDeclaration",
    # postprocessor
    "GENERIC_ISO_TEST",
    "PROFILE_REGISTRY",
    "BlockNumberConfig",
    "NumericFormat",
    "PostProcessorProfile",
    "PostProcessorRequirement",
    "get_profile",
    # generator
    "NCGenerationInput",
    "NCGenerationResult",
    "compute_program_hash",
    "generate_nc",
    "is_program_stale",
    # validator
    "ValidationIssue",
    "ValidationResult",
    "validate_nc_program",
    # manifest
    "NCGenerationManifest",
    "build_manifest",
    "check_manifest_staleness",
    "serialize_blocks_for_hash",
]

# Safety contract constants for external audit
NO_GCODE_DISPATCH: str = "YES"
NO_CNC_CONNECTION: str = "YES"
NO_FABRICATED_MACHINE_DATA: str = "YES"
OFFLINE_ONLY: str = "YES"
IS_DISPATCHABLE: bool = False
VERIFIED_TOOLPATH_REQUIRED: str = "YES"
