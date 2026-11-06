"""CAM planning Pydantic models for Level-9 Automatic CAM Planning.

Safety contract
---------------
NO_GCODE=YES             — no G-code strings anywhere in this module.
NO_FABRICATED_DATA=YES   — all numeric fields are Optional; None means UNKNOWN.
MISSING_VALUE_AS_ZERO=NO — absent values are None, never 0.
CANDIDATE_NOT_VERIFIED   — all outputs are candidates until human review.
SIMULATION_REQUIRED=YES  — every CAMJob declares simulation is required.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.cam_planning.enums import (
    CAMJobStatus,
    CAMOperationType,
    CAMPlanStatus,
    CAMStrategyType,
    ClearanceType,
    EntryStrategy,
    ExitStrategy,
    FixtureType,
    OperationPhase,
    SetupOrientation,
    SimulationCheck,
    StockSource,
    StockType,
    ToolFamilyRequirement,
    TurningSequenceStep,
    WCSCandidateType,
)

__all__ = [
    "StockRequirement",
    "WCSCandidateModel",
    "SetupCandidate",
    "ToolRequirement",
    "HolderRequirement",
    "StepParameter",
    "EntryExitRequirement",
    "ClearanceRequirement",
    "ToolpathRequirement",
    "CAMOperationCandidate",
    "CAMStrategyCandidate",
    "FixtureRequirement",
    "SimulationRequirement",
    "CAMJob",
]


class StockRequirement(BaseModel):
    """Raw material stock definition.

    Dimensions must come from USER_DEFINED, CAD_STOCK_MODEL, or
    VERIFIED_EXTERNAL_DATA.  Do NOT infer from finished-part bounding box.
    """

    stock_type: StockType = StockType.UNKNOWN
    source: StockSource = StockSource.UNKNOWN
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    diameter_mm: float | None = None
    allowance_mm: float | None = None
    notes: str | None = None

    @property
    def is_known(self) -> bool:
        return self.source != StockSource.UNKNOWN and self.stock_type != StockType.UNKNOWN


class WCSCandidateModel(BaseModel):
    """Work coordinate system candidate.

    Not automatically selected as final — returns WCS_CANDIDATE
    until validated by engineer.
    """

    candidate_type: WCSCandidateType
    feature_ref: str | None = None
    datum_ref: str | None = None
    rationale: str | None = None
    is_validated: bool = False


class SetupCandidate(BaseModel):
    """A candidate machining setup (orientation + accessible features).

    Derived from Level-4 access directions and Level-5 machine requirements.
    Minimum number of setups is NOT claimed unless proven.
    """

    setup_id: str
    orientation: SetupOrientation
    accessible_feature_refs: list[str] = Field(default_factory=list)
    wcs_candidate: WCSCandidateModel | None = None
    fixture_requirement: FixtureRequirement | None = None
    rationale: str | None = None
    warnings: list[str] = Field(default_factory=list)


class ToolRequirement(BaseModel):
    """Generic tool family requirement.

    No commercial tool SKU is invented.
    Diameter is a range requirement, not a specific tool.
    """

    tool_family: ToolFamilyRequirement = ToolFamilyRequirement.UNKNOWN
    min_diameter_mm: float | None = None
    max_diameter_mm: float | None = None
    min_reach_mm: float | None = None
    tool_ref: str | None = None
    notes: str | None = None


class HolderRequirement(BaseModel):
    """Holder requirement placeholder.

    Compatibility with Tool/Holder Library NOT assumed without validation.
    """

    min_reach_mm: float | None = None
    clearance_mm: float | None = None
    interface: str | None = None
    rigidity_note: str | None = None
    notes: str | None = None


class StepParameter(BaseModel):
    """Step-down / step-over parameter requirement.

    Only from validated cutting data or explicit user input.
    No defaults.
    """

    ap_mm: float | None = None
    ae_mm: float | None = None
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    source: str | None = None


class EntryExitRequirement(BaseModel):
    """Entry and exit motion type requirements.

    Coordinates are NOT generated here.
    """

    entry_strategy: EntryStrategy = EntryStrategy.UNKNOWN
    exit_strategy: ExitStrategy = ExitStrategy.UNKNOWN
    entry_notes: str | None = None
    exit_notes: str | None = None


class ClearanceRequirement(BaseModel):
    """Safety clearance requirement.

    Numeric values require USER_DEFINED, MACHINE_CONFIGURATION,
    FIXTURE_CONFIGURATION, or VERIFIED_RULE.
    Hard-coded values (5 mm, 10 mm, etc.) are forbidden.
    """

    clearance_type: ClearanceType
    value_mm: float | None = None
    source: str | None = None
    notes: str | None = None


class ToolpathRequirement(BaseModel):
    """Neutral toolpath requirement specification.

    Accumulates all requirements for a future toolpath generator.
    No coordinates are generated here.
    """

    requirement_id: str
    operation_ref: str
    strategy: CAMStrategyType | None = None
    feature_refs: list[str] = Field(default_factory=list)
    tool_ref: str | None = None
    holder_ref: str | None = None
    setup_ref: str | None = None
    wcs_ref: str | None = None
    cutting_data_ref: str | None = None
    entry_exit: EntryExitRequirement | None = None
    step_parameters: StepParameter | None = None
    clearances: list[ClearanceRequirement] = Field(default_factory=list)
    simulation_required: bool = True
    status: CAMPlanStatus = CAMPlanStatus.INCOMPLETE
    warnings: list[str] = Field(default_factory=list)


class CAMOperationCandidate(BaseModel):
    """A candidate CAM operation with full explainability.

    WHY it exists, WHICH feature drives it, WHICH setup accesses it,
    WHICH tool family is needed, WHICH cutting data is linked,
    WHICH information is missing — all stated explicitly.

    Candidate != verified toolpath.
    """

    operation_id: str
    operation_type: CAMOperationType
    phase: OperationPhase
    feature_refs: list[str] = Field(default_factory=list)
    setup_ref: str | None = None
    tool_requirement: ToolRequirement | None = None
    holder_requirement: HolderRequirement | None = None
    cutting_data_ref: str | None = None
    toolpath_requirement: ToolpathRequirement | None = None

    why: str
    which_feature: str
    which_setup: str | None = None
    which_tool_family: str | None = None
    which_cutting_data: str | None = None
    missing_information: list[str] = Field(default_factory=list)

    status: CAMPlanStatus = CAMPlanStatus.CANDIDATE
    warnings: list[str] = Field(default_factory=list)
    predecessor_operation_ids: list[str] = Field(default_factory=list)


class CAMStrategyCandidate(BaseModel):
    """A candidate CAM strategy with rationale and requirements.

    Each strategy must state: reason, feature_refs, required_tool,
    required_machine_capability, cutting_data_ref, status, warnings.
    """

    strategy_id: str
    strategy_type: CAMStrategyType
    operation_ref: str
    feature_refs: list[str] = Field(default_factory=list)
    reason: str
    required_tool: ToolRequirement | None = None
    required_machine_capability: str | None = None
    cutting_data_ref: str | None = None
    status: CAMPlanStatus = CAMPlanStatus.CANDIDATE
    warnings: list[str] = Field(default_factory=list)


class FixtureRequirement(BaseModel):
    """Generic workholding requirement derived from geometry/evidence.

    No fixture is claimed suitable without geometry/evidence.
    COLLISION_FREE is NOT claimed here.
    """

    fixture_type: FixtureType = FixtureType.UNKNOWN
    min_clamping_force_n: float | None = None
    clearance_required_mm: float | None = None
    access_directions: list[str] = Field(default_factory=list)
    notes: str | None = None
    is_validated: bool = False


class SimulationRequirement(BaseModel):
    """Simulation requirement declaration.

    SIMULATION_REQUIRED=YES on every CAM plan.
    None of the checks are claimed COMPLETE in Level 9.
    """

    simulation_required: bool = True
    required_checks: list[SimulationCheck] = Field(
        default_factory=lambda: list(SimulationCheck)
    )
    notes: str = (
        "Simulation is required before any toolpath is used for machining. "
        "Level 9 does not perform or verify simulation."
    )


class CAMJob(BaseModel):
    """Top-level CAM job container.

    Aggregates all candidates, requirements, and status for a CAM planning
    session.  Does NOT contain G-code, NC code, or toolpath coordinates.

    Safety invariants:
    - NO_GCODE=YES
    - FABRICATED_STOCK=NO
    - FABRICATED_WCS=NO
    - FABRICATED_TOOLPATH=NO
    - SIMULATION_REQUIRED=YES (always set on creation)
    """

    job_id: str
    part_reference: str | None = None
    cad_reference: str | None = None
    material: str | None = None

    stock: StockRequirement = Field(default_factory=StockRequirement)
    wcs_candidates: list[WCSCandidateModel] = Field(default_factory=list)
    setup_candidates: list[SetupCandidate] = Field(default_factory=list)
    operation_candidates: list[CAMOperationCandidate] = Field(default_factory=list)
    strategy_candidates: list[CAMStrategyCandidate] = Field(default_factory=list)
    toolpath_requirements: list[ToolpathRequirement] = Field(default_factory=list)
    fixture_requirements: list[FixtureRequirement] = Field(default_factory=list)
    simulation_requirement: SimulationRequirement = Field(
        default_factory=SimulationRequirement
    )

    tool_requirements: list[ToolRequirement] = Field(default_factory=list)
    cutting_data_refs: list[str] = Field(default_factory=list)
    machine_requirement_refs: list[str] = Field(default_factory=list)
    turning_sequence: list[TurningSequenceStep] = Field(default_factory=list)

    warnings: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    status: CAMJobStatus = CAMJobStatus.DRAFT
    cam_plan_status: CAMPlanStatus = CAMPlanStatus.INCOMPLETE

    @property
    def operation_count(self) -> int:
        return len(self.operation_candidates)

    @property
    def has_operations(self) -> bool:
        return bool(self.operation_candidates)

    @property
    def simulation_required(self) -> bool:
        return self.simulation_requirement.simulation_required

    @property
    def setup_count(self) -> int:
        return len(self.setup_candidates)
