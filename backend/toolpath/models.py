"""Level-10 Toolpath Generation — domain models.

Safety contract
---------------
NO_GCODE=YES
NO_FABRICATED_DATA=YES
COLLISION_CHECK=NOT_PERFORMED
GOUGE_CHECK=NOT_PERFORMED
FIXTURE_CHECK=NOT_PERFORMED
MACHINE_COLLISION_CHECK=NOT_PERFORMED
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from backend.toolpath.enums import (
    ClearanceSource,
    CompensationSide,
    CoordinateFrame,
    EntryType,
    ExitType,
    LinkStatus,
    MachineEnvelopeStatus,
    MotionType,
    SegmentGeometryType,
    ToolpathFidelity,
    ToolpathStatus,
    ToolReachStatus,
    VerificationStatus,
)


class VerificationContract(BaseModel):
    """Every generated toolpath must declare all checks NOT_PERFORMED."""

    collision_check: VerificationStatus = VerificationStatus.NOT_PERFORMED
    gouge_check: VerificationStatus = VerificationStatus.NOT_PERFORMED
    fixture_check: VerificationStatus = VerificationStatus.NOT_PERFORMED
    machine_collision_check: VerificationStatus = VerificationStatus.NOT_PERFORMED
    note: str = (
        "Level 10 generates toolpath geometry only. "
        "All collision, gouge and fixture checks are NOT_PERFORMED. "
        "Simulation and verification required before execution."
    )


class ClearancePlane(BaseModel):
    """Clearance / safe-Z value with mandatory source traceability."""

    value_mm: float | None = None
    source: ClearanceSource = ClearanceSource.UNKNOWN
    notes: str | None = None

    @property
    def is_known(self) -> bool:
        return self.value_mm is not None and self.source != ClearanceSource.UNKNOWN


class StepParameters(BaseModel):
    """Step-down / step-over parameters — no defaults."""

    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    stepdown_source: str | None = None
    stepover_source: str | None = None

    @property
    def stepdown_known(self) -> bool:
        return self.stepdown_mm is not None and self.stepdown_mm > 0

    @property
    def stepover_known(self) -> bool:
        return self.stepover_mm is not None and self.stepover_mm > 0


class ToolpathSegment(BaseModel):
    """Single toolpath motion segment."""

    segment_id: str
    operation_ref: str
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)
    strategy: str | None = None
    motion_type: MotionType
    geometry_type: SegmentGeometryType
    frame: CoordinateFrame
    start_point: tuple[float, float, float] | None = None
    end_point: tuple[float, float, float] | None = None
    arc_center: tuple[float, float, float] | None = None
    arc_clockwise: bool = False
    helix_radius: float | None = None
    helix_pitch: float | None = None
    polyline_points: list[tuple[float, float, float]] = Field(default_factory=list)
    computed_length_mm: float | None = None
    status: ToolpathStatus = ToolpathStatus.NOT_GENERATED
    source_evidence: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class PathMetrics(BaseModel):
    """Computed path quality metrics — no estimates, only computed values."""

    cut_length_mm: float = 0.0
    link_or_rapid_length_mm: float = 0.0
    total_length_mm: float = 0.0
    segment_count: int = 0
    retract_count: int = 0
    depth_level_count: int = 0
    max_depth_mm: float | None = None
    bounding_box_min: tuple[float, float, float] | None = None
    bounding_box_max: tuple[float, float, float] | None = None
    is_exact: bool = False


class VisualizationData(BaseModel):
    """Frontend-safe geometry for path visualization (no G-code required)."""

    polyline_points: list[tuple[float, float, float]] = Field(default_factory=list)
    arcs: list[dict[str, Any]] = Field(default_factory=list)
    motion_types: list[str] = Field(default_factory=list)
    operation_groups: dict[str, list[int]] = Field(default_factory=dict)
    tool_groups: dict[str, list[int]] = Field(default_factory=dict)
    setup_groups: dict[str, list[int]] = Field(default_factory=dict)
    frame: CoordinateFrame = CoordinateFrame.WCS_COORDINATES


class RemainingStock(BaseModel):
    """Foundation for remaining-stock tracking — no voxel simulation."""

    initial_stock_ref: str | None = None
    removed_region_refs: list[str] = Field(default_factory=list)
    remaining_stock_known: bool = False
    notes: str = (
        "Remaining stock tracking is a foundation placeholder. "
        "Full stock simulation requires geometric verification (Level 11+)."
    )


class Toolpath(BaseModel):
    """Top-level toolpath container for a single CAM operation."""

    toolpath_id: str
    operation_ref: str
    cam_job_ref: str | None = None
    setup_ref: str | None = None
    wcs_ref: str | None = None
    tool_ref: str | None = None
    feature_refs: list[str] = Field(default_factory=list)
    frame: CoordinateFrame = CoordinateFrame.WCS_COORDINATES
    segments: list[ToolpathSegment] = Field(default_factory=list)
    entry_type: EntryType = EntryType.ENTRY_STRATEGY_REQUIRED
    exit_type: ExitType = ExitType.UNKNOWN
    link_status: LinkStatus = LinkStatus.VERIFICATION_REQUIRED
    clearance: ClearancePlane = Field(default_factory=ClearancePlane)
    step_parameters: StepParameters = Field(default_factory=StepParameters)
    compensation_side: CompensationSide = CompensationSide.CENTERLINE
    metrics: PathMetrics = Field(default_factory=PathMetrics)
    visualization: VisualizationData = Field(default_factory=VisualizationData)
    verification: VerificationContract = Field(default_factory=VerificationContract)
    fidelity: ToolpathFidelity = ToolpathFidelity.NOT_GENERATED
    status: ToolpathStatus = ToolpathStatus.NOT_GENERATED
    tool_reach_status: ToolReachStatus = ToolReachStatus.UNKNOWN
    machine_envelope_status: MachineEnvelopeStatus = MachineEnvelopeStatus.UNKNOWN
    remaining_stock: RemainingStock = Field(default_factory=RemainingStock)
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)

    @property
    def has_segments(self) -> bool:
        return len(self.segments) > 0

    @property
    def is_verified(self) -> bool:
        return False  # Level 10 never claims verified

    @property
    def simulation_required(self) -> bool:
        return True


class ToolpathCollection(BaseModel):
    """All toolpaths for a CAM job."""

    collection_id: str
    cam_job_ref: str | None = None
    toolpaths: list[Toolpath] = Field(default_factory=list)
    total_cut_length_mm: float = 0.0
    total_link_length_mm: float = 0.0
    total_path_length_mm: float = 0.0
    simulation_required: bool = True
    verification: VerificationContract = Field(default_factory=VerificationContract)
    warnings: list[str] = Field(default_factory=list)

    def recompute_totals(self) -> None:
        self.total_cut_length_mm = sum(tp.metrics.cut_length_mm for tp in self.toolpaths)
        self.total_link_length_mm = sum(
            tp.metrics.link_or_rapid_length_mm for tp in self.toolpaths
        )
        self.total_path_length_mm = sum(tp.metrics.total_length_mm for tp in self.toolpaths)
