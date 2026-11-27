"""
MachiningPro AI — Level-11 Toolpath Verification and Simulation.

NO_GCODE=YES
NO_NC_CODE=YES
NO_FABRICATED_DATA=YES
FAIL_CLOSED=YES
UNKNOWN_IS_NOT_PASS=YES
SIMULATION_REQUIRED=TRUE
IS_VERIFIED_DERIVED=TRUE
"""

from .enums import (
    FixtureGeometrySource,
    FixtureSource,
    FixtureType,
    HolderGeometryFidelity,
    MachineEnvelopeStatus,
    SimulationStatus,
    StockFidelity,
    StockRemovalFidelity,
    StockShape,
    SweptVolumeStatus,
    VerificationCheckType,
    VerificationProfileEnum,
    VerificationSeverity,
    VerificationState,
    VerificationStatus,
)
from .models import (
    AxisLimitViolation,
    HolderGeometryRecord,
    MachineEnvelopeRecord,
    SimulationRequest,
    SimulationResult,
    VerificationIssue,
    VerificationResult,
    VerificationSegment,
    VerificationSummary,
    VisualizationData,
    WCSEnvelopeRecord,
)
from .profiles import PROFILE_MANDATORY_CHECKS, get_mandatory_checks
from .simulation import derive_verification_state, run_simulation
from .stock import FixtureGeometry, StockModel, VoxelGrid
from .swept_volume import AABB, SweptVolume, compute_swept_aabb, segment_cylinder_intersects_aabb
from .tolerance import DEFAULT_TOLERANCE, TolerancePolicy

__all__ = [
    "AxisLimitViolation",
    "FixtureGeometrySource",
    "FixtureSource",
    "FixtureType",
    "HolderGeometryFidelity",
    "HolderGeometryRecord",
    "MachineEnvelopeRecord",
    "MachineEnvelopeStatus",
    "SimulationStatus",
    "StockFidelity",
    "StockRemovalFidelity",
    "StockShape",
    "SweptVolumeStatus",
    "VerificationCheckType",
    "VerificationProfileEnum",
    "VerificationSeverity",
    "VerificationState",
    "VerificationStatus",
    "SimulationRequest",
    "SimulationResult",
    "VerificationIssue",
    "VerificationResult",
    "VerificationSegment",
    "VerificationSummary",
    "VisualizationData",
    "WCSEnvelopeRecord",
    "PROFILE_MANDATORY_CHECKS",
    "get_mandatory_checks",
    "derive_verification_state",
    "run_simulation",
    "FixtureGeometry",
    "StockModel",
    "VoxelGrid",
    "AABB",
    "SweptVolume",
    "compute_swept_aabb",
    "segment_cylinder_intersects_aabb",
    "DEFAULT_TOLERANCE",
    "TolerancePolicy",
]
