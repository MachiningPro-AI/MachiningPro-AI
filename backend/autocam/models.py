"""Auto CAM data models.

Safety contract — hardcoded, immutable:
  AUTO_CAM_CAN_DISPATCH_CNC=NO
  AUTO_CAM_CAN_RELEASE_PRODUCTION=NO
  AUTO_CAM_CAN_AUTO_APPROVE=NO
  REAL_MACHINE_WRITE_FOUND=NO
  AUTO_CAM_FEATURE_CONFIRMATION_CHANGED=NO
  AUTO_CAM_WCS_CONFIRMATION_CHANGED=NO
  AUTO_CAM_PRODUCTION_RELEASE_CHANGED=NO
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import AutoCamPlanStatus, AutoCamStage, BlockerCode, StageStatus

# ---------------------------------------------------------------------------
# Safety invariants — module-level constants, never overridden by API input
# ---------------------------------------------------------------------------

_SAFETY_INVARIANTS: dict[str, Any] = {
    "AUTO_CAM_CAN_DISPATCH_CNC": False,
    "AUTO_CAM_CAN_RELEASE_PRODUCTION": False,
    "AUTO_CAM_CAN_AUTO_APPROVE": False,
    "REAL_MACHINE_WRITE_FOUND": False,
    "AUTO_CAM_FEATURE_CONFIRMATION_CHANGED": False,
    "AUTO_CAM_WCS_CONFIRMATION_CHANGED": False,
    "AUTO_CAM_PRODUCTION_RELEASE_CHANGED": False,
    "DISPATCH_GATE": "ALWAYS_BLOCKED",
    "SIMULATION_REQUIRED": True,
    "CANDIDATE_ONLY": True,
    "ENGINEER_REVIEW_REQUIRED": True,
}


# ---------------------------------------------------------------------------
# Input models
# ---------------------------------------------------------------------------

class StockBbox(BaseModel):
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float

    @property
    def length_mm(self) -> float:
        return abs(self.max_x - self.min_x)

    @property
    def width_mm(self) -> float:
        return abs(self.max_y - self.min_y)

    @property
    def height_mm(self) -> float:
        return abs(self.max_z - self.min_z)


class AutoCamFeatureInput(BaseModel):
    feature_id: str
    feature_type: str  # HOLE, POCKET, SLOT, PLANAR_FACE, STEP_SHOULDER
    center_x: float | None = None
    center_y: float | None = None
    center_z_top: float | None = None
    depth_mm: float | None = None
    diameter_mm: float | None = None
    width_mm: float | None = None
    length_mm: float | None = None
    clearance_z: float | None = None
    boundary_points: list[list[float]] | None = None


class AutoCamCostInput(BaseModel):
    """Commercial inputs supplied by the user for Auto CAM cost estimation.

    All fields optional — missing inputs remain NOT_PROVIDED.
    Every supplied value is labeled USER_PROVIDED with provenance.
    """

    machine_hourly_rate: float | None = None
    machine_rate_currency: str | None = None

    material_cost_total: float | None = None
    material_cost_currency: str | None = None

    tool_cost_total: float | None = None
    tool_cost_currency: str | None = None

    setup_cost_total: float | None = None
    setup_cost_currency: str | None = None

    labor_hours: float | None = None
    labor_rate: float | None = None
    labor_rate_currency: str | None = None

    energy_cost: float | None = None
    energy_cost_currency: str | None = None

    overhead_pct: float | None = None

    quantity: int | None = None
    currency: str | None = None

    submitted_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )


class CostCategoryItem(BaseModel):
    """One line item in the cost estimate with full provenance."""

    category: str
    value: float | None = None
    currency: str | None = None
    source_type: str = "UNKNOWN"
    source_name: str | None = None
    provenance: str = "NOT_PROVIDED"
    status: str = "NOT_PROVIDED"
    notes: str | None = None
    formula: str | None = None


class AutoCamCostEstimate(BaseModel):
    """Full Auto CAM cost estimate with per-category provenance.

    TOTAL_STATUS allowed values:
      COMPLETE_COST_ESTIMATE      — all 8 categories known
      PARTIAL_COST_ESTIMATE       — ≥1 known, some unknown
      INSUFFICIENT_DATA           — no cost components known
      NOT_PROVIDED                — no cost_input submitted yet
      CURRENCY_MISMATCH           — mixed currencies, sum blocked
    """

    material_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="MATERIAL_COST")
    )
    machine_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="MACHINE_COST")
    )
    tool_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="TOOL_COST")
    )
    setup_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="SETUP_COST")
    )
    labor_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="LABOR_COST")
    )
    energy_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="ENERGY_COST")
    )
    overhead_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="OVERHEAD_COST")
    )
    other_cost: CostCategoryItem = Field(
        default_factory=lambda: CostCategoryItem(category="OTHER_COST")
    )

    known_total: float | None = None
    unknown_component_count: int = 0
    completeness_pct: float = 0.0
    total_status: str = "NOT_PROVIDED"
    currency: str | None = None

    computed_at: str = ""
    cost_input_received: bool = False
    warnings: list[str] = Field(default_factory=list)


class AutoCamRequest(BaseModel):
    """Input to the Auto CAM orchestration pipeline.

    Safety contract is enforced by the orchestrator — no field in this
    model can override the safety invariants.

    Fail-closed: missing stock_bbox → STAGE S02 BLOCKED.
    """

    file_ref: str = Field(..., min_length=1, max_length=256)
    features: list[AutoCamFeatureInput] = Field(default_factory=list)
    stock_bbox: StockBbox | None = None
    material_grade: str | None = Field(default=None, max_length=64)
    machine_type_preference: str | None = Field(default=None, max_length=32)
    wcs_ref: str = Field(default="WCS_PART_ORIGIN", max_length=64)
    setup_ref: str = Field(default="SETUP_01", max_length=32)

    # Cost inputs — optional user-provided commercial rates
    cost_input: AutoCamCostInput | None = None

    # Safety fields — read-only; orchestrator enforces these
    is_dispatchable: bool = Field(default=False, frozen=True)
    production_released: bool = Field(default=False, frozen=True)


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

class AutoCamBlocker(BaseModel):
    code: BlockerCode
    stage: AutoCamStage
    message: str
    missing_input: str | None = None


class AutoCamWarning(BaseModel):
    stage: AutoCamStage
    message: str
    severity: str = "ADVISORY"


class ToolResult(BaseModel):
    tool_id: str | None = None
    tool_type: str | None = None
    tool_diameter_mm: float | None = None
    cutting_length_mm: float | None = None
    tool_status: str = "INSUFFICIENT_DATA"
    provenance: str = "CATALOG"


class CuttingParamResult(BaseModel):
    vc_m_per_min: float | None = None
    rpm: float | None = None
    feed_mm_per_min: float | None = None
    fz_mm: float | None = None
    doc_mm: float | None = None
    woc_mm: float | None = None
    status: str = "NOT_AVAILABLE"
    provenance: str = "NOT_AVAILABLE"


class OperationResult(BaseModel):
    operation_ref: str
    feature_id: str
    feature_type: str
    operation_type: str
    cam_strategy: str
    tool: ToolResult
    cutting_params: CuttingParamResult
    toolpath_status: str = "NOT_PERFORMED"
    toolpath_id: str | None = None
    segment_count: int = 0
    point_count: int = 0
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    simulation_required: bool = True


class ToolpathGroupFE(BaseModel):
    motion_type: str
    points: list[float]
    operation_ref: str


class CycleTimeResult(BaseModel):
    total_known_s: float | None = None
    cutting_time_s: float | None = None
    rapid_time_s: float | None = None
    status: str = "INSUFFICIENT_DATA"
    path_length_type: str = "UNKNOWN"


class VerificationSummaryResult(BaseModel):
    state: str = "UNVERIFIED"
    checks_performed: int = 0
    checks_passed: int = 0
    checks_failed: int = 0
    checks_not_performed: int = 0
    stock_removal_fidelity: str = "NOT_PERFORMED"
    collision_check: str = "NOT_PERFORMED"
    gouge_check: str = "NOT_VERIFIABLE"
    # Phase D: separate exact vs conservative gouge — GOUGE_EXACT always NOT_VERIFIABLE (KL-07)
    gouge_exact: str = "NOT_VERIFIABLE"
    gouge_conservative: str = "NOT_PERFORMED"
    # Phase G: explicit holder collision sub-checks
    holder_collision_check: str = "NOT_PERFORMED"
    holder_part_collision: str = "NOT_PERFORMED"
    holder_stock_collision: str = "NOT_PERFORMED"
    holder_fixture_collision: str = "NOT_PERFORMED"
    # Phase I: explicit fixture collision sub-checks
    fixture_collision_check: str = "NOT_PERFORMED"
    tool_fixture_collision: str = "NOT_PERFORMED"
    part_fixture_interference: str = "NOT_PERFORMED"
    tool_reach_check: str = "NOT_PERFORMED"
    machine_envelope_check: str = "NOT_PERFORMED"
    axis_limit_check: str = "NOT_PERFORMED"
    # Phase J/K: machine + WCS envelope data
    machine_id: str | None = None
    machine_limit_source: str = "CATALOG"
    wcs_ref: str = "WCS_PART_ORIGIN"
    # Phase N: individual check provenance (for the results panel)
    check_details: dict[str, dict[str, Any]] = Field(default_factory=dict)
    issues: list[dict[str, Any]] = Field(default_factory=list)
    # Phase Q: safety invariants
    verification_can_auto_approve: bool = False
    verification_can_release_production: bool = False
    verification_can_dispatch_cnc: bool = False


class MachineResult(BaseModel):
    machine_id: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    machine_type_code: str | None = None
    spindle_max_rpm: int | None = None
    # Phase J: machine travel limits for envelope verification
    x_travel_mm: float | None = None
    y_travel_mm: float | None = None
    z_travel_mm: float | None = None
    machine_limit_source: str = "CATALOG"
    status: str = "INSUFFICIENT_DATA"


class AutoCamStageResult(BaseModel):
    stage: AutoCamStage
    status: StageStatus
    duration_ms: float = 0.0
    outputs: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)


class AutoCamPlan(BaseModel):
    """Auto CAM orchestration result.

    Safety invariants are ALWAYS present and ALWAYS set to safe values.
    No API input can change them.
    """

    plan_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:16])
    file_ref: str
    plan_status: AutoCamPlanStatus
    stages: list[AutoCamStageResult]
    operations: list[OperationResult] = Field(default_factory=list)
    toolpath_groups: list[ToolpathGroupFE] = Field(default_factory=list)
    machine: MachineResult = Field(default_factory=MachineResult)
    cycle_time: CycleTimeResult = Field(default_factory=CycleTimeResult)
    verification: VerificationSummaryResult = Field(
        default_factory=VerificationSummaryResult
    )
    blockers: list[AutoCamBlocker] = Field(default_factory=list)
    warnings: list[AutoCamWarning] = Field(default_factory=list)
    cost_estimate_status: str = "NOT_IMPLEMENTED"
    report_status: str = "NOT_PERFORMED"
    created_at: str = ""

    # Safety invariants — always present, always safe
    safety: dict[str, Any] = Field(default_factory=lambda: dict(_SAFETY_INVARIANTS))

    # Cost estimate — computed after cost_input submitted
    cost_estimate: AutoCamCostEstimate | None = None

    @property
    def is_blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def stage_count_pass(self) -> int:
        return sum(1 for s in self.stages if s.status == StageStatus.PASS)
