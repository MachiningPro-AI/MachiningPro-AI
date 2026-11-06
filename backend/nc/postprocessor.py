"""
Level-12 Postprocessor Requirement and Profile models.

PostProcessorProfile is data/configuration driven.
Controller-specific syntax lives ONLY in profile data, not scattered through code.

GENERIC_ISO_TEST profile:
- TEST_ONLY
- NOT_MACHINE_CERTIFIED
- NOT_DISPATCHABLE
- Not Fanuc, not Siemens, not Haas, not Heidenhain
- Uses generic ISO 6983-style test codes for controlled validation only

NO_FABRICATED_MACHINE_PROFILES=YES
NO_CNC_DISPATCH=YES
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .enums import (
    ArcMode,
    AxisConfiguration,
    MachineClass,
    NCCoordinateMode,
    NCMotionType,
    NCUnitMode,
    PostCertificationStatus,
)


class PostProcessorRequirement(BaseModel):
    """
    Machine/controller requirements that a postprocessor must satisfy.
    Unknown fields remain UNKNOWN — never fabricated.
    """

    controller_family: str = "UNKNOWN"
    machine_class: MachineClass = MachineClass.UNKNOWN
    axis_configuration: AxisConfiguration = AxisConfiguration.UNKNOWN
    linear_axes: list[str] = Field(default_factory=list)
    rotary_axes: list[str] = Field(default_factory=list)
    units: NCUnitMode = NCUnitMode.UNKNOWN
    coordinate_modes: list[NCCoordinateMode] = Field(default_factory=list)
    supported_motion_types: list[NCMotionType] = Field(default_factory=list)
    tool_change_semantics: str = "UNKNOWN"
    spindle_semantics: str = "UNKNOWN"
    coolant_semantics: str = "UNKNOWN"
    work_offset_semantics: str = "UNKNOWN"
    arc_format: ArcMode | None = None
    comment_format: str = "UNKNOWN"
    program_number_format: str = "UNKNOWN"
    maximum_line_length: int | None = None
    numeric_precision: int | None = None


class NumericFormat(BaseModel):
    decimal_places: int = 3
    leading_zero: bool = True
    trailing_zero: bool = False
    sign_always: bool = False


class BlockNumberConfig(BaseModel):
    enabled: bool = False
    start: int = 10
    increment: int = 10


class PostProcessorProfile(BaseModel):
    """
    Data-driven postprocessor profile.

    All controller-specific syntax lives here.
    Runtime code reads profile data — never hard-codes controller syntax.
    """

    profile_id: str
    profile_name: str
    dialect: str
    certification_status: PostCertificationStatus
    not_machine_certified: bool
    not_dispatchable: bool
    provenance: str

    # supported codes — explicit, never assumed
    supported_motion_codes: dict[str, str] = Field(default_factory=dict)
    unit_commands: dict[str, str] = Field(default_factory=dict)
    plane_commands: dict[str, str] = Field(default_factory=dict)
    coordinate_mode_commands: dict[str, str] = Field(default_factory=dict)
    feed_mode_commands: dict[str, str] = Field(default_factory=dict)
    spindle_commands: dict[str, str] = Field(default_factory=dict)
    coolant_commands: dict[str, str] = Field(default_factory=dict)
    program_end_commands: list[str] = Field(default_factory=list)

    # optional tool change pattern
    tool_change_pattern: str | None = None
    # arc mode supported
    arc_modes: list[ArcMode] = Field(default_factory=list)

    # program structure
    program_start_comment: str = ""
    program_end_comment: str = ""

    # numeric formatting
    numeric_format: NumericFormat = Field(default_factory=NumericFormat)
    block_numbers: BlockNumberConfig = Field(default_factory=BlockNumberConfig)
    maximum_line_length: int | None = None

    # motion types supported by this profile
    supported_motion_types: list[NCMotionType] = Field(default_factory=list)
    supported_coordinate_modes: list[NCCoordinateMode] = Field(default_factory=list)
    supported_unit_modes: list[NCUnitMode] = Field(default_factory=list)
    default_coordinate_mode: NCCoordinateMode = NCCoordinateMode.ABSOLUTE
    default_unit_mode: NCUnitMode = NCUnitMode.MM
    requires_unit_declaration: bool = True
    requires_plane_declaration: bool = True
    requires_coordinate_mode_declaration: bool = True

    # cutter compensation: left as computer-compensated by default
    default_cutter_comp: str = "COMPUTER_COMPENSATED"

    # safety banners included in every generated program
    safety_banner_lines: list[str] = Field(
        default_factory=lambda: [
            "OFFLINE VALIDATION REQUIRED",
            "MACHINE-SPECIFIC REVIEW REQUIRED",
            "DO NOT RUN ON MACHINE WITHOUT APPROVAL",
        ]
    )


# ---------------------------------------------------------------------------
# GENERIC_ISO_TEST profile
#
# Explicitly TEST_ONLY / NOT_MACHINE_CERTIFIED / NOT_DISPATCHABLE.
# Uses generic ISO 6983-style test codes for controlled validation only.
# NOT compatible with any real machine without independent verification.
# ---------------------------------------------------------------------------

GENERIC_ISO_TEST = PostProcessorProfile(
    profile_id="GENERIC_ISO_TEST_v1",
    profile_name="Generic ISO Test Profile",
    dialect="GENERIC_ISO_TEST",
    certification_status=PostCertificationStatus.TEST_ONLY,
    not_machine_certified=True,
    not_dispatchable=True,
    provenance=(
        "TEST_ONLY: Generic ISO 6983-style codes for offline validation. "
        "NOT certified for any machine. NOT compatible with Fanuc, Siemens, "
        "Haas, Heidenhain or any other controller without independent verification."
    ),
    # Motion codes — generic ISO 6983 test mapping
    supported_motion_codes={
        "RAPID_LINEAR": "G0",
        "FEED_LINEAR": "G1",
        "ARC_CW": "G2",
        "ARC_CCW": "G3",
    },
    unit_commands={"MM": "G21", "INCH": "G20"},
    plane_commands={"XY": "G17", "XZ": "G18", "YZ": "G19"},
    coordinate_mode_commands={"ABSOLUTE": "G90", "INCREMENTAL": "G91"},
    feed_mode_commands={"FEED_PER_MINUTE": "G94", "FEED_PER_REV": "G95"},
    # Spindle/coolant — TEST_ONLY generic codes
    spindle_commands={"CW": "M3", "CCW": "M4", "OFF": "M5"},
    coolant_commands={"FLOOD": "M8", "OFF": "M9"},
    program_end_commands=["M30"],
    tool_change_pattern="T{tool_number}M6",
    arc_modes=[ArcMode.CENTER_OFFSET, ArcMode.RADIUS],
    program_start_comment="( TEST-ONLY GENERIC ISO PROGRAM - NOT FOR MACHINE USE )",
    program_end_comment="( END OF TEST PROGRAM )",
    numeric_format=NumericFormat(decimal_places=3, leading_zero=True, trailing_zero=False),
    block_numbers=BlockNumberConfig(enabled=False),
    maximum_line_length=255,
    supported_motion_types=[
        NCMotionType.RAPID_LINEAR,
        NCMotionType.FEED_LINEAR,
        NCMotionType.ARC_CW,
        NCMotionType.ARC_CCW,
    ],
    supported_coordinate_modes=[NCCoordinateMode.ABSOLUTE, NCCoordinateMode.INCREMENTAL],
    supported_unit_modes=[NCUnitMode.MM, NCUnitMode.INCH],
    default_coordinate_mode=NCCoordinateMode.ABSOLUTE,
    default_unit_mode=NCUnitMode.MM,
    requires_unit_declaration=True,
    requires_plane_declaration=True,
    requires_coordinate_mode_declaration=True,
    safety_banner_lines=[
        "( OFFLINE VALIDATION REQUIRED )",
        "( MACHINE-SPECIFIC REVIEW REQUIRED )",
        "( DO NOT RUN ON MACHINE WITHOUT APPROVAL )",
        "( PROFILE: GENERIC_ISO_TEST - TEST_ONLY - NOT_DISPATCHABLE )",
    ],
)

# Registry of available profiles — only TEST_ONLY profiles at Level 12
PROFILE_REGISTRY: dict[str, PostProcessorProfile] = {
    GENERIC_ISO_TEST.profile_id: GENERIC_ISO_TEST,
}


def get_profile(profile_id: str) -> PostProcessorProfile | None:
    return PROFILE_REGISTRY.get(profile_id)
