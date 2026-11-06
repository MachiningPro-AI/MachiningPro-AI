"""Level-10 Toolpath Generation — enumerations.

Safety contract
---------------
NO_GCODE=YES             — this module never produces G-code.
NO_FABRICATED_DATA=YES   — no synthetic coordinates, no assumed clearance,
                           no assumed stepdown/stepover, no assumed WCS.
COLLISION_CHECK=NOT_PERFORMED  — until Level 11.
GOUGE_CHECK=NOT_PERFORMED      — until Level 11.
"""

from __future__ import annotations

from enum import StrEnum


class ToolpathStatus(StrEnum):
    NOT_GENERATED = "NOT_GENERATED"
    PARTIAL = "PARTIAL"
    GENERATED = "GENERATED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    BLOCKED = "BLOCKED"


class MotionType(StrEnum):
    CUT = "CUT"
    RAPID = "RAPID"
    APPROACH = "APPROACH"
    RETRACT = "RETRACT"
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    LINK = "LINK"
    PLUNGE = "PLUNGE"
    RAMP = "RAMP"
    HELIX = "HELIX"
    DWELL = "DWELL"
    ARC = "ARC"


class CoordinateFrame(StrEnum):
    PART_COORDINATES = "PART_COORDINATES"
    SETUP_COORDINATES = "SETUP_COORDINATES"
    WCS_COORDINATES = "WCS_COORDINATES"
    MCS_COORDINATES = "MCS_COORDINATES"
    LATHE_XZ = "LATHE_XZ"
    UNKNOWN_FRAME = "UNKNOWN_FRAME"


class SegmentGeometryType(StrEnum):
    LINE = "LINE"
    ARC = "ARC"
    HELIX = "HELIX"
    POLYLINE = "POLYLINE"
    POINT = "POINT"


class ProfileSide(StrEnum):
    INSIDE = "INSIDE"
    OUTSIDE = "OUTSIDE"
    ON_CONTOUR = "ON_CONTOUR"
    UNKNOWN = "UNKNOWN"


class CompensationSide(StrEnum):
    CENTERLINE = "CENTERLINE"
    LEFT_OFFSET = "LEFT_OFFSET"
    RIGHT_OFFSET = "RIGHT_OFFSET"
    UNKNOWN = "UNKNOWN"


class CornerType(StrEnum):
    SHARP = "SHARP"
    ARC_TRANSITION = "ARC_TRANSITION"
    TANGENT_TRANSITION = "TANGENT_TRANSITION"


class DepthStrategy(StrEnum):
    SINGLE_DEPTH = "SINGLE_DEPTH"
    MULTI_DEPTH = "MULTI_DEPTH"
    UNKNOWN = "UNKNOWN"


class PocketStrategy(StrEnum):
    OFFSET = "OFFSET"
    ZIGZAG = "ZIGZAG"
    SPIRAL = "SPIRAL"
    ADAPTIVE_CANDIDATE = "ADAPTIVE_CANDIDATE"
    UNKNOWN = "UNKNOWN"


class EntryType(StrEnum):
    PLUNGE = "PLUNGE"
    LINEAR_RAMP = "LINEAR_RAMP"
    HELIX = "HELIX"
    TANGENTIAL_ENTRY = "TANGENTIAL_ENTRY"
    ENTRY_STRATEGY_REQUIRED = "ENTRY_STRATEGY_REQUIRED"


class ExitType(StrEnum):
    DIRECT_RETRACT = "DIRECT_RETRACT"
    LEAD_OUT = "LEAD_OUT"
    TANGENTIAL_EXIT = "TANGENTIAL_EXIT"
    UNKNOWN = "UNKNOWN"


class LinkStatus(StrEnum):
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    BLOCKED = "BLOCKED"


class ClearanceSource(StrEnum):
    USER_DEFINED = "USER_DEFINED"
    USER_SUPPLIED = "USER_SUPPLIED"
    FIXTURE_CONFIGURATION = "FIXTURE_CONFIGURATION"
    MACHINE_CONFIGURATION = "MACHINE_CONFIGURATION"
    PROCESS_STANDARD = "PROCESS_STANDARD"
    UNKNOWN = "UNKNOWN"


class ToolpathFidelity(StrEnum):
    NOT_GENERATED = "NOT_GENERATED"
    EXACT_GENERATED = "EXACT_GENERATED"
    APPROXIMATE = "APPROXIMATE"
    DERIVED = "DERIVED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


class TurningMotionType(StrEnum):
    AXIAL_CUT = "AXIAL_CUT"
    RADIAL_CUT = "RADIAL_CUT"
    PROFILE_CUT = "PROFILE_CUT"
    FACE_CUT = "FACE_CUT"
    GROOVE_CUT = "GROOVE_CUT"


class VerificationStatus(StrEnum):
    NOT_PERFORMED = "NOT_PERFORMED"


class MachineEnvelopeStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    WITHIN_ENVELOPE = "WITHIN_ENVELOPE"
    ENVELOPE_CONFLICT = "ENVELOPE_CONFLICT"


class ToolReachStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    WITHIN_REACH = "WITHIN_REACH"
    TOOL_REACH_CONFLICT = "TOOL_REACH_CONFLICT"
