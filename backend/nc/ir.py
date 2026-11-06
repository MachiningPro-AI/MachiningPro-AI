"""
Level-12 Controller-Neutral NC Intermediate Representation.

The IR describes WHAT operations the toolpath requires.
Controller-specific output belongs exclusively to PostProcessorProfile.

NO_GCODE_DISPATCH=YES  NO_CNC_CONNECTION=YES  OFFLINE_ONLY=YES
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .enums import (
    ArcMode,
    NCCoolantMode,
    NCCoordinateMode,
    NCCutterCompMode,
    NCFeedMode,
    NCMotionType,
    NCPlane,
    NCSpindleDirection,
    NCUnitMode,
    WorkOffsetRef,
)


class NCSourceTrace(BaseModel):
    """Traceability back to the originating toolpath element."""

    toolpath_id: str | None = None
    segment_id: str | None = None
    operation_id: str | None = None
    setup_id: str | None = None
    tool_id: str | None = None
    feature_id: str | None = None


class NCMotion(BaseModel):
    """Controller-neutral motion element: type + coordinates + feed."""

    motion_type: NCMotionType
    end_x: float | None = None
    end_y: float | None = None
    end_z: float | None = None
    # arc center offsets (CENTER_OFFSET mode)
    arc_i: float | None = None
    arc_j: float | None = None
    arc_k: float | None = None
    # arc radius (RADIUS mode)
    arc_radius: float | None = None
    arc_mode: ArcMode | None = None
    arc_plane: NCPlane | None = None
    # feed
    feed_mmpm: float | None = None
    source: NCSourceTrace = Field(default_factory=NCSourceTrace)


class NCToolChange(BaseModel):
    """Tool change element — tool_number=None means TOOL_NUMBER_REQUIRED."""

    tool_id: str
    tool_number: int | None = None
    description: str | None = None
    source: NCSourceTrace = Field(default_factory=NCSourceTrace)


class NCSpindleCommand(BaseModel):
    """Spindle on/off/speed — speed_rpm=None means no RPM available."""

    speed_rpm: float | None = None
    direction: NCSpindleDirection = NCSpindleDirection.OFF
    source_operation_id: str | None = None


class NCFeedCommand(BaseModel):
    feed_value: float
    feed_mode: NCFeedMode = NCFeedMode.FEED_PER_MINUTE


class NCCoolantCommand(BaseModel):
    coolant_mode: NCCoolantMode


class NCWorkOffsetDeclaration(BaseModel):
    offset_ref: WorkOffsetRef = WorkOffsetRef.UNKNOWN
    description: str | None = None


class NCPlaneDeclaration(BaseModel):
    plane: NCPlane


class NCUnitDeclaration(BaseModel):
    unit_mode: NCUnitMode


class NCCoordinateModeDeclaration(BaseModel):
    coord_mode: NCCoordinateMode


class NCCutterCompDeclaration(BaseModel):
    comp_mode: NCCutterCompMode


class NCComment(BaseModel):
    text: str


class NCDrillCycle(BaseModel):
    """Generic drill cycle — post profile maps to controller cycle or expands."""

    cycle_type: str  # SIMPLE_DRILL_CYCLE or PECK_DRILL_CYCLE
    hole_x: float | None = None
    hole_y: float | None = None
    clearance_z: float | None = None
    hole_top_z: float | None = None
    hole_depth_mm: float | None = None
    peck_depth_mm: float | None = None
    feed_mmpm: float | None = None
    source: NCSourceTrace = Field(default_factory=NCSourceTrace)


class NCBlock(BaseModel):
    """
    One logical NC block in the IR.

    elements is a list of NC element dicts — each element carries a 'kind' key
    identifying its type. We use dict[str, Any] to avoid complex union serialization.
    """

    block_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    elements: list[dict[str, Any]] = Field(default_factory=list)
    sequence_number: int | None = None
    comment: str | None = None
    source: NCSourceTrace = Field(default_factory=NCSourceTrace)


class NCProgram(BaseModel):
    """
    Top-level controller-neutral NC program.

    is_dispatchable is always False at Level 12.
    Controller-specific text is derived by applying a PostProcessorProfile.
    """

    program_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    program_number: str  # test/generic identifier — NOT a real machine program number
    unit_mode: NCUnitMode
    coordinate_mode: NCCoordinateMode
    blocks: list[NCBlock] = Field(default_factory=list)
    toolpath_id: str | None = None
    verification_session_id: str | None = None
    post_profile_id: str
    # hashes for stale detection
    source_toolpath_hash: str = ""
    source_verification_hash: str = ""
    # safety invariants
    is_offline_candidate: bool = True
    is_dispatchable: bool = False  # invariant — always False at Level 12
    safety_warnings: list[str] = Field(
        default_factory=lambda: [
            "OFFLINE VALIDATION REQUIRED",
            "MACHINE-SPECIFIC REVIEW REQUIRED",
            "DO NOT RUN ON MACHINE WITHOUT APPROVAL",
        ]
    )
    generation_warnings: list[str] = Field(default_factory=list)
    block_count: int = 0

    def model_post_init(self, __context: Any) -> None:
        self.block_count = len(self.blocks)
