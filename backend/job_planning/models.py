"""Level-17 CNC Job Planning & Machine Assignment — data models.

ASSIGNMENT_IS_PROPOSED_ONLY=YES
NO_AUTOMATIC_MACHINE_DISPATCH=YES
MISSING_DATA_FAILS_CLOSED=YES
NO_FABRICATED_CAPABILITY=YES
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from ..scheduling.enums import MachineClass
from .enums import (
    AssignmentStatus,
    CapabilityMatchLevel,
    MaterialCompatibilityResult,
    PlanningBlockReason,
    RankingObjective,
    SpindleMatchResult,
    WorkloadStatus,
)


class CamOperationRequirements(BaseModel):
    """Requirements derived from validated CAM operations — inputs to job planning."""

    job_id: str
    part_reference: str | None = None
    material: str | None = None
    operations: list[str] = Field(default_factory=list)
    required_machine_class: MachineClass = MachineClass.UNKNOWN
    required_axis_count: int | None = None
    required_spindle_rpm: float | None = None
    required_spindle_power_kw: float | None = None
    required_x_travel_mm: float | None = None
    required_y_travel_mm: float | None = None
    required_z_travel_mm: float | None = None
    workpiece_mass_kg: float | None = None
    requires_through_spindle_coolant: bool = False
    requires_live_tooling: bool = False
    requires_tapping: bool = False
    requires_boring: bool = False
    estimated_cycle_time_min: float | None = None
    data_source: str = "CAM_PLAN"
    is_fabricated_requirements: bool = False


class MachineCapabilityProfile(BaseModel):
    """Machine capability — built from catalog or resource data, never fabricated."""

    machine_id: str
    machine_class: MachineClass = MachineClass.UNKNOWN
    axis_count: int | None = None
    spindle_max_rpm: int | None = None
    spindle_power_kw: float | None = None
    travel_x_mm: float | None = None
    travel_y_mm: float | None = None
    travel_z_mm: float | None = None
    table_load_kg: float | None = None
    turning_capable: bool = False
    milling_capable: bool = False
    drilling_capable: bool = False
    through_spindle_coolant: bool | None = None
    has_live_tooling: bool = False
    capable_tapping: bool | None = None
    capable_boring: bool | None = None
    tool_magazine_capacity: int | None = None
    is_fabricated_capability: bool = False


class CapabilityCheckResult(BaseModel):
    """Result of a single capability check."""

    check_name: str
    match_level: CapabilityMatchLevel
    detail: str = ""


class MaterialCompatibilityCheck(BaseModel):
    """Result of material compatibility check against a machine class."""

    material: str | None
    machine_class: MachineClass
    result: MaterialCompatibilityResult
    reason: str = ""


class SpindleMatchCheck(BaseModel):
    """Result of spindle requirement match against machine capability."""

    required_rpm: float | None
    machine_max_rpm: int | None
    result: SpindleMatchResult
    utilization_pct: float | None = None


class WorkloadEstimate(BaseModel):
    """Estimated workload for a machine — never fabricated."""

    machine_id: str
    queue_depth: int = 0
    estimated_cycle_time_min: float | None = None
    workload_status: WorkloadStatus = WorkloadStatus.UNKNOWN
    is_fabricated: bool = False


class AssignmentCandidate(BaseModel):
    """
    Single machine assignment candidate.

    PROPOSED ONLY — never automatically dispatched.
    Human review mandatory before any real machine assignment.
    """

    machine_id: str
    rank: int
    capability_score: float
    material_compatibility: MaterialCompatibilityResult
    spindle_match: SpindleMatchResult
    workload_status: WorkloadStatus
    capability_checks: list[CapabilityCheckResult] = Field(default_factory=list)
    workload_estimate: WorkloadEstimate
    incompatibility_reasons: list[str] = Field(default_factory=list)
    soft_preference_score: float = 0.0
    overall_score: float
    explanation: str = ""
    is_proposed_only: bool = True
    is_automatic_dispatch: bool = False


class AssignmentRecommendation(BaseModel):
    """
    Ranked assignment recommendation — PROPOSED ONLY.

    is_proposed_only and is_automatic_dispatch are always True/False respectively.
    review_required is always True.
    Human approval mandatory before any real machine dispatch.
    """

    job_id: str
    status: AssignmentStatus = AssignmentStatus.PROPOSED
    candidates: list[AssignmentCandidate] = Field(default_factory=list)
    best_candidate_id: str | None = None
    planning_warnings: list[str] = Field(default_factory=list)
    blocking_reasons: list[PlanningBlockReason] = Field(default_factory=list)
    is_proposed_only: bool = True
    is_automatic_dispatch: bool = False
    review_required: bool = True
    is_fabricated_data: bool = False
    explanation: str = ""
    ranking_objective: RankingObjective = RankingObjective.CAPABILITY_FIT
