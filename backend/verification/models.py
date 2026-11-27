"""
Level-11 verification data models.

is_verified is a derived property — TRUE only when state = VERIFIED.
Every issue is traceable to toolpath/segment/tool/setup/feature.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field

from .enums import (
    HolderGeometryFidelity,
    MachineEnvelopeStatus,
    SimulationStatus,
    StockRemovalFidelity,
    VerificationCheckType,
    VerificationProfileEnum,
    VerificationSeverity,
    VerificationState,
    VerificationStatus,
)
from .stock import FixtureGeometry, StockModel


class HolderGeometryRecord(BaseModel):
    """Phase F — Holder geometry for verification.

    HOLDER_GEOMETRY_ENGINE=SIMPLIFIED_CYLINDER_WITH_GAUGE_LENGTH.
    All fields come from user-provided catalog records; nothing fabricated.
    Missing fields → NOT_PERFORMED/INSUFFICIENT_DATA (never PASS).
    """

    holder_id: str | None = None
    interface: str | None = None          # e.g. HSK-A63, ISO 30, BT40
    gauge_length_mm: float | None = None
    max_diameter_mm: float | None = None
    profile: str | None = None            # e.g. STRAIGHT, TAPER, MODULAR
    source: str = "CATALOG"
    provenance: str = "USER_SELECTED"
    fidelity: HolderGeometryFidelity = HolderGeometryFidelity.SIMPLIFIED
    # Legacy / derived fields kept for backward compat
    holder_type: str | None = None
    max_tool_reach_mm: float | None = None
    shank_diameter_mm: float | None = None


class MachineEnvelopeRecord(BaseModel):
    """Phase J — Machine envelope data for verification.

    MACHINE_LIMIT_SOURCE must be CATALOG or USER_DEFINED; never fabricated.
    Missing axis data → NOT_VERIFIABLE (never PASS).
    """

    machine_id: str | None = None
    machine_limit_source: str = "CATALOG"
    x_travel_mm: float | None = None
    y_travel_mm: float | None = None
    z_travel_mm: float | None = None
    a_axis_limit_deg: tuple[float, float] | None = None
    b_axis_limit_deg: tuple[float, float] | None = None
    c_axis_limit_deg: tuple[float, float] | None = None
    spindle_max_rpm: int | None = None
    max_feed_mm_per_min: float | None = None
    max_tool_length_mm: float | None = None
    machine_envelope_status: MachineEnvelopeStatus = MachineEnvelopeStatus.INSUFFICIENT_DATA


class WCSEnvelopeRecord(BaseModel):
    """Phase K — WCS and envelope extents for verification.

    Part, stock, toolpath, and machine extents must all be accounted for.
    WCS offsets shift the coordinate frame before machine envelope check.
    """

    wcs_offset_x_mm: float = 0.0
    wcs_offset_y_mm: float = 0.0
    wcs_offset_z_mm: float = 0.0
    wcs_ref: str = "WCS_PART_ORIGIN"
    part_extents_mm: dict[str, float] | None = None   # min/max XYZ
    stock_extents_mm: dict[str, float] | None = None
    toolpath_extents_mm: dict[str, float] | None = None
    machine_extents_mm: dict[str, float] | None = None


class AxisLimitViolation(BaseModel):
    """Phase L — Detailed axis limit violation record."""

    axis: str
    command_position: float
    limit_min: float
    limit_max: float
    excess_mm: float
    operation_id: str | None = None
    toolpath_segment: str | None = None


class VerificationSegment(BaseModel):
    segment_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    start_x: float
    start_y: float
    start_z: float
    end_x: float
    end_y: float
    end_z: float
    motion_type: str
    is_cutting: bool
    operation_id: str | None = None
    tool_id: str | None = None
    setup_id: str | None = None
    feature_id: str | None = None


class VerificationIssue(BaseModel):
    issue_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    check_type: VerificationCheckType
    severity: VerificationSeverity
    message: str
    toolpath_id: str | None = None
    operation_id: str | None = None
    segment_id: str | None = None
    tool_id: str | None = None
    setup_id: str | None = None
    feature_id: str | None = None
    geometry_refs: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    check_type: VerificationCheckType
    status: VerificationStatus
    severity: VerificationSeverity
    toolpath_refs: list[str] = Field(default_factory=list)
    segment_refs: list[str] = Field(default_factory=list)
    geometry_refs: list[str] = Field(default_factory=list)
    evidence: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    issues: list[VerificationIssue] = Field(default_factory=list)


class VerificationSummary(BaseModel):
    verification_state: VerificationState
    profile: VerificationProfileEnum
    checks_performed: int
    checks_passed: int
    checks_failed: int
    checks_not_performed: int
    checks_insufficient_data: int
    critical_issues: int
    error_issues: int
    warning_issues: int
    info_issues: int

    @property
    def is_verified(self) -> bool:
        return self.verification_state == VerificationState.VERIFIED


class VisualizationData(BaseModel):
    cutting_points: list[list[float]] = Field(default_factory=list)
    rapid_points: list[list[float]] = Field(default_factory=list)
    stock_bbox: dict[str, float] | None = None
    part_bbox: dict[str, float] | None = None
    fixture_bboxes: list[dict[str, float]] = Field(default_factory=list)
    collision_points: list[list[float]] = Field(default_factory=list)
    gouge_points: list[list[float]] = Field(default_factory=list)
    holder_collision_points: list[list[float]] = Field(default_factory=list)
    holder_bboxes: list[dict[str, float]] = Field(default_factory=list)
    toolpath_extents: dict[str, float] | None = None
    remaining_stock_note: str | None = None
    # Phase M toggle metadata — which layers have data
    has_tool_layer: bool = False
    has_holder_layer: bool = False
    has_fixture_layer: bool = False
    has_collision_layer: bool = False
    has_gouge_layer: bool = False


class SimulationRequest(BaseModel):
    toolpath_id: str
    segments: list[VerificationSegment] = Field(default_factory=list)
    profile: VerificationProfileEnum = VerificationProfileEnum.GEOMETRY_ONLY
    tool_diameter_mm: float | None = None
    tool_length_mm: float | None = None
    tool_flute_length_mm: float | None = None
    # Simplified holder geometry (floats) — kept for backward compat
    holder_diameter_mm: float | None = None
    holder_length_mm: float | None = None
    # Rich holder geometry record (Phase F) — takes precedence over simple floats
    holder_geometry: HolderGeometryRecord | None = None
    stock: StockModel | None = None
    fixtures: list[FixtureGeometry] = Field(default_factory=list)
    machine_travel_x_mm: float | None = None
    machine_travel_y_mm: float | None = None
    machine_travel_z_mm: float | None = None
    machine_id: str | None = None
    # Phase J: rich machine envelope record (takes precedence over travel_* floats)
    machine_envelope: MachineEnvelopeRecord | None = None
    # Explicit per-axis limits dict e.g. {"X": (-300.0, 300.0), "Y": (-250.0, 250.0)}
    # Takes precedence over machine_travel_* when present
    axis_limits: dict[str, tuple[float, float]] | None = None
    part_bbox_min: tuple[float, float, float] | None = None
    part_bbox_max: tuple[float, float, float] | None = None
    wcs_offset_x_mm: float = 0.0
    wcs_offset_y_mm: float = 0.0
    wcs_offset_z_mm: float = 0.0
    # Phase K: rich WCS + envelope record
    wcs_envelope: WCSEnvelopeRecord | None = None


class SimulationResult(BaseModel):
    session_id: str
    toolpath_id: str
    simulation_status: SimulationStatus
    verification_state: VerificationState
    profile: VerificationProfileEnum
    checks: dict[str, VerificationResult] = Field(default_factory=dict)
    issues: list[VerificationIssue] = Field(default_factory=list)
    summary: VerificationSummary | None = None
    initial_stock_volume_mm3: float | None = None
    remaining_stock_volume_mm3: float | None = None
    removed_volume_mm3: float | None = None
    stock_removal_fidelity: StockRemovalFidelity = StockRemovalFidelity.UNKNOWN
    visualization: VisualizationData = Field(default_factory=VisualizationData)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    resource_limit_hit: bool = False
    # Phase K: WCS envelope applied during verification
    wcs_envelope: WCSEnvelopeRecord | None = None
    # Phase J: machine envelope record used
    machine_envelope: MachineEnvelopeRecord | None = None
    # Phase L: axis limit violations (structured)
    axis_limit_violations: list[AxisLimitViolation] = Field(default_factory=list)

    @property
    def is_verified(self) -> bool:
        return self.verification_state == VerificationState.VERIFIED
