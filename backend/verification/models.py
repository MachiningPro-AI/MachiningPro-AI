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
    SimulationStatus,
    StockRemovalFidelity,
    VerificationCheckType,
    VerificationProfileEnum,
    VerificationSeverity,
    VerificationState,
    VerificationStatus,
)
from .stock import FixtureGeometry, StockModel


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
    remaining_stock_note: str | None = None


class SimulationRequest(BaseModel):
    toolpath_id: str
    segments: list[VerificationSegment] = Field(default_factory=list)
    profile: VerificationProfileEnum = VerificationProfileEnum.GEOMETRY_ONLY
    tool_diameter_mm: float | None = None
    tool_length_mm: float | None = None
    tool_flute_length_mm: float | None = None
    holder_diameter_mm: float | None = None
    holder_length_mm: float | None = None
    stock: StockModel | None = None
    fixtures: list[FixtureGeometry] = Field(default_factory=list)
    machine_travel_x_mm: float | None = None
    machine_travel_y_mm: float | None = None
    machine_travel_z_mm: float | None = None
    part_bbox_min: tuple[float, float, float] | None = None
    part_bbox_max: tuple[float, float, float] | None = None


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

    @property
    def is_verified(self) -> bool:
        return self.verification_state == VerificationState.VERIFIED
