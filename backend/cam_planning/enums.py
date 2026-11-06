"""CAM planning enumerations for Level-9 Automatic CAM Planning.

Safety contract
---------------
NO_GCODE=YES             — this module never produces G-code.
NO_NC_CODE=YES           — this module never produces NC programs.
NO_FABRICATED_DATA=YES   — no synthetic coordinates, no assumed stock,
                           no assumed WCS, no assumed fixtures.
CANDIDATE_NOT_VERIFIED   — all outputs are candidates until human review.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = [
    "CAMJobStatus",
    "StockType",
    "StockSource",
    "WCSCandidateType",
    "SetupOrientation",
    "CAMOperationType",
    "CAMStrategyType",
    "OperationPhase",
    "EntryStrategy",
    "ExitStrategy",
    "FixtureType",
    "CAMPlanStatus",
    "ClearanceType",
    "ToolFamilyRequirement",
    "SimulationCheck",
    "TurningSequenceStep",
]


class CAMJobStatus(StrEnum):
    """Top-level lifecycle status of a CAM job."""

    DRAFT = "DRAFT"
    INCOMPLETE = "INCOMPLETE"
    READY_FOR_CAM_PLANNING = "READY_FOR_CAM_PLANNING"
    CAM_PLAN_CREATED = "CAM_PLAN_CREATED"
    SIMULATION_REQUIRED = "SIMULATION_REQUIRED"
    BLOCKED = "BLOCKED"


class StockType(StrEnum):
    """Classification of raw material stock form."""

    BAR = "BAR"
    BLOCK = "BLOCK"
    PLATE = "PLATE"
    CASTING = "CASTING"
    FORGING = "FORGING"
    NEAR_NET_SHAPE = "NEAR_NET_SHAPE"
    USER_DEFINED = "USER_DEFINED"
    UNKNOWN = "UNKNOWN"


class StockSource(StrEnum):
    """Traceability of stock dimension data.

    MISSING_VALUE_AS_ZERO=NO — absent stock dimensions must remain UNKNOWN.
    Do NOT infer stock size from finished-part bounding box.
    """

    USER_DEFINED = "USER_DEFINED"
    CAD_STOCK_MODEL = "CAD_STOCK_MODEL"
    VERIFIED_EXTERNAL_DATA = "VERIFIED_EXTERNAL_DATA"
    UNKNOWN = "UNKNOWN"


class WCSCandidateType(StrEnum):
    """Candidate work coordinate system origin / orientation choices.

    None of these is automatically selected as final.
    All remain WCS_CANDIDATE until validated.
    """

    TOP_CENTER = "TOP_CENTER"
    TOP_CORNER = "TOP_CORNER"
    PART_CENTER = "PART_CENTER"
    STOCK_CENTER = "STOCK_CENTER"
    FEATURE_REFERENCE = "FEATURE_REFERENCE"
    USER_DEFINED = "USER_DEFINED"


class SetupOrientation(StrEnum):
    """Machine access direction / table orientation for a setup.

    Uses standard machining axis conventions (+Z = spindle toward part).
    """

    PLUS_Z = "+Z"
    MINUS_Z = "-Z"
    PLUS_X = "+X"
    MINUS_X = "-X"
    PLUS_Y = "+Y"
    MINUS_Y = "-Y"
    USER_DEFINED = "USER_DEFINED"
    UNKNOWN = "UNKNOWN"


class CAMOperationType(StrEnum):
    """Candidate CAM operation taxonomy.

    Only generated when upstream evidence (Level 3–6) supports them.
    Candidate != verified toolpath.
    """

    FACE_MILL = "FACE_MILL"
    ADAPTIVE_ROUGH = "ADAPTIVE_ROUGH"
    POCKET_ROUGH = "POCKET_ROUGH"
    POCKET_FINISH = "POCKET_FINISH"
    CONTOUR_ROUGH = "CONTOUR_ROUGH"
    CONTOUR_FINISH = "CONTOUR_FINISH"
    SLOT_MILL = "SLOT_MILL"
    DRILL = "DRILL"
    PECK_DRILL = "PECK_DRILL"
    REAM = "REAM"
    BORE = "BORE"
    TAP = "TAP"
    THREAD_MILL = "THREAD_MILL"
    COUNTERBORE = "COUNTERBORE"
    COUNTERSINK = "COUNTERSINK"
    CHAMFER = "CHAMFER"
    BALL_END_FINISH = "BALL_END_FINISH"
    REST_MACHINING = "REST_MACHINING"
    TURN_ROUGH = "TURN_ROUGH"
    TURN_FINISH = "TURN_FINISH"
    FACE_TURN = "FACE_TURN"
    GROOVE = "GROOVE"
    PART_OFF = "PART_OFF"


class CAMStrategyType(StrEnum):
    """CAM toolpath strategy classification."""

    CONVENTIONAL_POCKETING = "CONVENTIONAL_POCKETING"
    ADAPTIVE_CLEARING = "ADAPTIVE_CLEARING"
    Z_LEVEL_FINISH = "Z_LEVEL_FINISH"
    PARALLEL_FINISH = "PARALLEL_FINISH"
    CONTOUR_FINISH_STRATEGY = "CONTOUR_FINISH_STRATEGY"
    DRILL_CYCLE = "DRILL_CYCLE"
    PECK_CYCLE = "PECK_CYCLE"
    BORE_CYCLE = "BORE_CYCLE"
    REAM_CYCLE = "REAM_CYCLE"


class OperationPhase(StrEnum):
    """Machining phase classification."""

    ROUGHING = "ROUGHING"
    SEMI_FINISH = "SEMI_FINISH"
    FINISH = "FINISH"


class EntryStrategy(StrEnum):
    """Required tool entry motion type.

    Coordinates are NOT generated here.
    """

    PLUNGE = "PLUNGE"
    RAMP = "RAMP"
    HELIX = "HELIX"
    LEAD_IN = "LEAD_IN"
    TANGENTIAL_ENTRY = "TANGENTIAL_ENTRY"
    UNKNOWN = "UNKNOWN"


class ExitStrategy(StrEnum):
    """Required tool exit motion type.

    Coordinates are NOT generated here.
    """

    LEAD_OUT = "LEAD_OUT"
    TANGENTIAL_EXIT = "TANGENTIAL_EXIT"
    RETRACT = "RETRACT"
    UNKNOWN = "UNKNOWN"


class FixtureType(StrEnum):
    """Generic workholding category.

    No fixture is claimed suitable without geometry/evidence.
    """

    VISE = "VISE"
    CHUCK = "CHUCK"
    COLLET = "COLLET"
    SOFT_JAW = "SOFT_JAW"
    FIXTURE_PLATE = "FIXTURE_PLATE"
    CUSTOM_FIXTURE = "CUSTOM_FIXTURE"
    MAGNETIC = "MAGNETIC"
    VACUUM = "VACUUM"
    UNKNOWN = "UNKNOWN"


class CAMPlanStatus(StrEnum):
    """Engineering completeness status of a CAM plan."""

    INCOMPLETE = "INCOMPLETE"
    CANDIDATE = "CANDIDATE"
    ENGINEERING_REVIEW_REQUIRED = "ENGINEERING_REVIEW_REQUIRED"
    READY_FOR_TOOLPATH_GENERATION = "READY_FOR_TOOLPATH_GENERATION"
    BLOCKED = "BLOCKED"


class ClearanceType(StrEnum):
    """Safety clearance concept type.

    Numeric values are NOT hard-coded; they require explicit sources.
    """

    SAFE_Z = "SAFE_Z"
    CLEARANCE_PLANE = "CLEARANCE_PLANE"
    RETRACT_PLANE = "RETRACT_PLANE"
    APPROACH_CLEARANCE = "APPROACH_CLEARANCE"


class ToolFamilyRequirement(StrEnum):
    """Generic tool family requirement.

    No commercial SKU is invented.
    Diameter is expressed as a range requirement, not a specific tool.
    """

    FACE_MILL_CUTTER = "FACE_MILL_CUTTER"
    SOLID_CARBIDE_END_MILL = "SOLID_CARBIDE_END_MILL"
    INDEXABLE_END_MILL = "INDEXABLE_END_MILL"
    DRILL_BIT = "DRILL_BIT"
    REAMER = "REAMER"
    BORING_BAR = "BORING_BAR"
    THREADING_TAP = "THREADING_TAP"
    THREAD_MILL_CUTTER = "THREAD_MILL_CUTTER"
    TURNING_INSERT = "TURNING_INSERT"
    GROOVING_INSERT = "GROOVING_INSERT"
    PARTING_INSERT = "PARTING_INSERT"
    UNKNOWN = "UNKNOWN"


class SimulationCheck(StrEnum):
    """Simulation verification requirement.

    All checks are REQUIRED; none is claimed as COMPLETE in Level 9.
    """

    TOOL_COLLISION = "TOOL_COLLISION"
    HOLDER_COLLISION = "HOLDER_COLLISION"
    FIXTURE_COLLISION = "FIXTURE_COLLISION"
    MACHINE_COLLISION = "MACHINE_COLLISION"
    TRAVEL_LIMITS = "TRAVEL_LIMITS"
    GOUGING = "GOUGING"
    REMAINING_STOCK = "REMAINING_STOCK"


class TurningSequenceStep(StrEnum):
    """Turning operation sequence classification."""

    FACE = "FACE"
    OD_ROUGH = "OD_ROUGH"
    ID_ROUGH = "ID_ROUGH"
    OD_FINISH = "OD_FINISH"
    ID_FINISH = "ID_FINISH"
    GROOVE = "GROOVE"
    THREAD = "THREAD"
    PART_OFF = "PART_OFF"
