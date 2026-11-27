"""
Level-11 verification enumeration types.

NO_GCODE=YES  NO_NC_CODE=YES  NO_FABRICATED_DATA=YES
FAIL_CLOSED=YES  UNKNOWN_IS_NOT_PASS=YES
"""

from enum import StrEnum


class VerificationStatus(StrEnum):
    NOT_PERFORMED = "NOT_PERFORMED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    # NOT_VERIFIABLE: check is conceptually applicable but the required engine/data
    # is not available — never treated as PASS, never treated as FAIL.
    # Example: GOUGE_EXACT requires mesh-vs-mesh engine not installed.
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    PASS = "PASS"
    FAIL = "FAIL"
    PARTIAL = "PARTIAL"
    ERROR = "ERROR"


class VerificationCheckType(StrEnum):
    TOOL_COLLISION = "TOOL_COLLISION"
    HOLDER_COLLISION = "HOLDER_COLLISION"
    # Explicit sub-checks for holder collision (Phase G)
    HOLDER_PART_COLLISION = "HOLDER_PART_COLLISION"
    HOLDER_STOCK_COLLISION = "HOLDER_STOCK_COLLISION"
    HOLDER_FIXTURE_COLLISION = "HOLDER_FIXTURE_COLLISION"
    FIXTURE_COLLISION = "FIXTURE_COLLISION"
    # Explicit sub-checks for fixture collision (Phase I)
    TOOL_FIXTURE_COLLISION = "TOOL_FIXTURE_COLLISION"
    PART_FIXTURE_INTERFERENCE = "PART_FIXTURE_INTERFERENCE"
    # PART_GOUGE: conservative bounding-box check — never returns PASS,
    # returns PARTIAL (no overlap found) or FAIL (critical violation).
    PART_GOUGE = "PART_GOUGE"
    # GOUGE_EXACT: exact mesh-vs-mesh comparison — always NOT_VERIFIABLE
    # until a mesh intersection engine is available (KL-07).
    GOUGE_EXACT = "GOUGE_EXACT"
    # GOUGE_CONSERVATIVE: alias for PART_GOUGE bbox check in explicit separation contexts
    GOUGE_CONSERVATIVE = "GOUGE_CONSERVATIVE"
    STOCK_GOUGE = "STOCK_GOUGE"
    MACHINE_ENVELOPE = "MACHINE_ENVELOPE"
    AXIS_LIMIT = "AXIS_LIMIT"
    TOOL_REACH = "TOOL_REACH"
    RAPID_CLEARANCE = "RAPID_CLEARANCE"
    STOCK_REMAINING = "STOCK_REMAINING"
    OVERTRAVEL = "OVERTRAVEL"
    KINEMATIC_CHECK = "KINEMATIC_CHECK"


class VerificationSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class VerificationState(StrEnum):
    UNVERIFIED = "UNVERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class StockShape(StrEnum):
    BOX = "BOX"
    CYLINDER = "CYLINDER"
    USER_DEFINED_MESH = "USER_DEFINED_MESH"
    NEAR_NET_MESH = "NEAR_NET_MESH"
    UNKNOWN = "UNKNOWN"


class StockFidelity(StrEnum):
    EXACT_MESH = "EXACT_MESH"
    ANALYTIC_PRIMITIVE = "ANALYTIC_PRIMITIVE"
    DISCRETIZED_APPROXIMATION = "DISCRETIZED_APPROXIMATION"
    UNKNOWN = "UNKNOWN"


class StockRemovalFidelity(StrEnum):
    EXACT_BOOLEAN = "EXACT_BOOLEAN"
    ANALYTIC = "ANALYTIC"
    VOXEL_APPROXIMATE = "VOXEL_APPROXIMATE"
    UNKNOWN = "UNKNOWN"


class SimulationStatus(StrEnum):
    NOT_STARTED = "NOT_STARTED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class VerificationProfileEnum(StrEnum):
    GEOMETRY_ONLY = "GEOMETRY_ONLY"
    TOOL_AND_PART = "TOOL_AND_PART"
    TOOL_HOLDER_PART = "TOOL_HOLDER_PART"
    FULL_SETUP = "FULL_SETUP"
    FULL_MACHINE = "FULL_MACHINE"


class FixtureType(StrEnum):
    VISE_JAWS = "VISE_JAWS"
    CHUCK = "CHUCK"
    SOFT_JAWS = "SOFT_JAWS"
    FIXTURE_PLATE = "FIXTURE_PLATE"
    CUSTOM_FIXTURE_MESH = "CUSTOM_FIXTURE_MESH"
    CLAMPS = "CLAMPS"
    UNKNOWN = "UNKNOWN"


class FixtureSource(StrEnum):
    USER_DEFINED = "USER_DEFINED"
    VERIFIED_LIBRARY_RECORD = "VERIFIED_LIBRARY_RECORD"
    IMPORTED_GEOMETRY = "IMPORTED_GEOMETRY"


class SweptVolumeStatus(StrEnum):
    COMPUTED = "COMPUTED"
    APPROXIMATE = "APPROXIMATE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_COMPUTED = "NOT_COMPUTED"


class HolderGeometryFidelity(StrEnum):
    """Phase F fidelity levels for holder geometry used in collision checks."""
    CATALOG_GEOMETRY = "CATALOG_GEOMETRY"
    PARAMETRIC_APPROXIMATION = "PARAMETRIC_APPROXIMATION"
    SIMPLIFIED = "SIMPLIFIED"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class FixtureGeometrySource(StrEnum):
    """Phase H fixture model sources."""
    STEP = "STEP"
    IGES = "IGES"
    STL = "STL"
    PROJECT_ARTIFACT = "PROJECT_ARTIFACT"
    USER_DEFINED_BBOX = "USER_DEFINED_BBOX"
    NOT_PROVIDED = "NOT_PROVIDED"


class MachineEnvelopeStatus(StrEnum):
    """Phase J machine envelope verification status."""
    PASS = "PASS"
    FAIL = "FAIL"
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ExactGougeMethod(StrEnum):
    """Method used for exact gouge / overcut verification."""
    BREP_BOOLEAN_OCC = "BREP_BOOLEAN_OCC"       # gmsh OCC Boolean B-Rep (beta.5)
    MESH_BOOLEAN = "MESH_BOOLEAN"               # mesh Boolean fallback
    HIGH_RESOLUTION_VOXEL = "HIGH_RESOLUTION_VOXEL"  # voxel approx (not exact)
    NOT_AVAILABLE = "NOT_AVAILABLE"             # engine missing


class TargetGeometryFidelity(StrEnum):
    """Fidelity of the target geometry used in exact gouge check."""
    BREP_EXACT = "BREP_EXACT"                   # from STEP/B-Rep via OCC
    TESSELLATED_HIGH_FIDELITY = "TESSELLATED_HIGH_FIDELITY"  # fine mesh
    TESSELLATED_APPROXIMATE = "TESSELLATED_APPROXIMATE"      # coarse mesh
    NOT_AVAILABLE = "NOT_AVAILABLE"


class MachinedResultMethod(StrEnum):
    """How the machined-result geometry was derived."""
    BOOLEAN_BREP = "BOOLEAN_BREP"               # stock B-Rep cut by swept tool
    MESH_BOOLEAN = "MESH_BOOLEAN"
    HIGH_RESOLUTION_VOXEL = "HIGH_RESOLUTION_VOXEL"
    NOT_COMPUTED = "NOT_COMPUTED"


class ToolGeometryFidelity(StrEnum):
    """Fidelity of tool geometry used in swept-volume construction."""
    CATALOG_GEOMETRY = "CATALOG_GEOMETRY"       # full profile from catalog
    PARAMETRIC = "PARAMETRIC"                   # diameter + corner radius known
    SIMPLIFIED = "SIMPLIFIED"                   # cylinder only
    NOT_AVAILABLE = "NOT_AVAILABLE"
