"""Level 5 — Machine and Tool Selection Intelligence domain model.

Extends Level-4 process intelligence with deterministic machine class
selection, tool family selection, holder requirements, and compatibility
checking.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate machine recommendations.
  - Do NOT fabricate cutting-tool recommendations.
  - Do NOT invent machine specifications or tooling capabilities.
  - Do NOT recommend a specific commercial machine/tool unless verified data exists.
  - Generic capability matching MUST work even when no vendor database exists.
  - Machine selection and tool selection must be explainable and traceable.
  - A process candidate does NOT automatically imply a valid machine/tool candidate.
  - Preserve Levels 1-4 backward compatibility.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MatchStatus(StrEnum):
    """Compatibility match status for a machine or tool candidate."""

    COMPATIBLE = "COMPATIBLE"
    PARTIALLY_COMPATIBLE = "PARTIALLY_COMPATIBLE"
    INCOMPATIBLE = "INCOMPATIBLE"
    UNKNOWN = "UNKNOWN"


class MachineClassV5(StrEnum):
    """Extended generic machine class taxonomy (Level 5).

    Superset of Level-4 MachineClass — includes all Level-4 values and
    additional classes.  No commercial brand is implied by any value.
    """

    THREE_AXIS_VMC = "THREE_AXIS_VMC"
    FOUR_AXIS_VMC = "FOUR_AXIS_VMC"
    FIVE_AXIS_VMC = "FIVE_AXIS_VMC"
    HMC = "HMC"
    CNC_LATHE = "CNC_LATHE"
    TURN_MILL = "TURN_MILL"
    SWISS_LATHE = "SWISS_LATHE"
    DRILL_TAP_CENTER = "DRILL_TAP_CENTER"
    SURFACE_GRINDER = "SURFACE_GRINDER"
    CYLINDRICAL_GRINDER = "CYLINDRICAL_GRINDER"
    WIRE_EDM = "WIRE_EDM"
    SINKER_EDM = "SINKER_EDM"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    UNKNOWN = "UNKNOWN"


class ToolFamilyV5(StrEnum):
    """Extended generic tool-family taxonomy (Level 5).

    Superset of Level-4 ToolFamily with finer distinctions for roughing /
    finishing passes and additional tool types.  No specific catalog model
    or brand is implied.
    """

    DRILL = "DRILL"
    CENTER_DRILL = "CENTER_DRILL"
    SPOT_DRILL = "SPOT_DRILL"
    END_MILL = "END_MILL"
    ROUGHING_END_MILL = "ROUGHING_END_MILL"
    FINISH_END_MILL = "FINISH_END_MILL"
    BALL_END_MILL = "BALL_END_MILL"
    FACE_MILL = "FACE_MILL"
    CHAMFER_MILL = "CHAMFER_MILL"
    SLOT_MILL = "SLOT_MILL"
    REAMER = "REAMER"
    BORING_BAR = "BORING_BAR"
    TAP = "TAP"
    THREAD_MILL = "THREAD_MILL"
    TURNING_INSERT = "TURNING_INSERT"
    GROOVING_TOOL = "GROOVING_TOOL"
    PARTING_TOOL = "PARTING_TOOL"
    GRINDING_WHEEL = "GRINDING_WHEEL"
    EDM_ELECTRODE = "EDM_ELECTRODE"
    UNKNOWN = "UNKNOWN"


class HolderType(StrEnum):
    """Generic toolholder / workholding type.  No specific SKU is implied."""

    ER_COLLET = "ER_COLLET"
    HYDRAULIC_CHUCK = "HYDRAULIC_CHUCK"
    SHRINK_FIT = "SHRINK_FIT"
    MILLING_CHUCK = "MILLING_CHUCK"
    SIDE_LOCK = "SIDE_LOCK"
    BORING_HOLDER = "BORING_HOLDER"
    TAPPING_CHUCK = "TAPPING_CHUCK"
    TURNING_TOOLHOLDER = "TURNING_TOOLHOLDER"
    UNKNOWN = "UNKNOWN"


class MaterialGroup(StrEnum):
    """ISO material workpiece group.  Used when material is known."""

    P_STEEL = "P_STEEL"
    M_STAINLESS = "M_STAINLESS"
    K_CAST_IRON = "K_CAST_IRON"
    N_NON_FERROUS = "N_NON_FERROUS"
    S_SUPERALLOY = "S_SUPERALLOY"
    H_HARDENED = "H_HARDENED"
    UNKNOWN = "UNKNOWN"


class CuttingParameterRequirementStatus(StrEnum):
    """Status of a cutting parameter requirement."""

    UNKNOWN = "UNKNOWN"
    RANGE_REQUIRED = "RANGE_REQUIRED"
    CATALOG_DATA_REQUIRED = "CATALOG_DATA_REQUIRED"
    RULE_BASED_RANGE = "RULE_BASED_RANGE"


class SelectionPlanStatus(StrEnum):
    """Overall quality of the Level-5 machine and tool selection plan."""

    COMPLETE = "COMPLETE"
    CANDIDATE_PLAN = "CANDIDATE_PLAN"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REQUIRES_INPUT = "REQUIRES_INPUT"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class MachineCapabilityRequirement:
    """Full machine capability requirement derived from the operation set.

    All numeric specs default to None when not derivable from evidence.
    None != 0 and None != compatible.
    """

    requirement_id: str
    machine_class: MachineClassV5
    operation_refs: tuple[str, ...] = ()
    required_axes: int = 3
    required_rotary_axes: int = 0
    required_orientation: str | None = None
    min_x_travel_mm: float | None = None
    min_y_travel_mm: float | None = None
    min_z_travel_mm: float | None = None
    min_work_envelope_mm: float | None = None
    min_spindle_speed_rpm: float | None = None
    min_spindle_power_kw: float | None = None
    min_spindle_torque_nm: float | None = None
    turning_required: bool = False
    milling_required: bool = False
    drilling_required: bool = False
    grinding_required: bool = False
    edm_required: bool = False
    coolant_required: bool = False
    through_spindle_coolant_required: bool = False
    accuracy_requirement: str | None = None
    workholding_requirement: str | None = None
    warnings: tuple[str, ...] = ()
    evidence_notes: str = ""
    status: str = "CANDIDATE"


@dataclasses.dataclass(frozen=True)
class MachineCandidate:
    """A candidate generic machine class for the operation set.

    machine_name is a generic descriptive label — NOT a commercial model.
    No brand, model number or pricing is implied.
    compatibility_score is None unless deterministically computable from
    explicit requirement satisfaction counts.
    """

    machine_id: str
    machine_name: str
    machine_class: MachineClassV5
    match_status: MatchStatus
    matched_requirements: tuple[str, ...] = ()
    failed_requirements: tuple[str, ...] = ()
    unknown_requirements: tuple[str, ...] = ()
    compatibility_score: float | None = None
    warnings: tuple[str, ...] = ()
    evidence_notes: str = ""
    rationale: str = ""


@dataclasses.dataclass(frozen=True)
class ToolCapabilityRequirement:
    """Detailed tool capability requirement for one operation.

    All dimensional fields default to None when not derivable from evidence.
    """

    requirement_id: str
    tool_family: ToolFamilyV5
    operation_ref: str
    feature_refs: tuple[str, ...] = ()
    nominal_diameter_mm: float | None = None
    min_diameter_mm: float | None = None
    max_diameter_mm: float | None = None
    min_flute_length_mm: float | None = None
    min_reach_mm: float | None = None
    max_tool_diameter_mm: float | None = None
    corner_radius_mm: float | None = None
    tool_angle_deg: float | None = None
    material_group: MaterialGroup = MaterialGroup.UNKNOWN
    coolant_required: bool = False
    access_direction: str | None = None
    basis: str = ""
    evidence_notes: str = ""
    status: str = "CANDIDATE"


@dataclasses.dataclass(frozen=True)
class ToolCandidate:
    """A candidate tool family for one operation.

    No specific catalog tool, brand or catalog number is selected.
    """

    candidate_id: str
    tool_family: ToolFamilyV5
    operation_ref: str
    match_status: MatchStatus
    matched_requirements: tuple[str, ...] = ()
    failed_requirements: tuple[str, ...] = ()
    unknown_requirements: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    evidence_notes: str = ""
    rationale: str = ""


@dataclasses.dataclass(frozen=True)
class HolderRequirement:
    """Generic toolholder requirement for one operation.

    No specific SKU, vendor or catalog item is implied.
    All dimensional constraints default to None when not derivable.
    """

    requirement_id: str
    holder_type: HolderType
    operation_ref: str
    tool_interface: str | None = None
    required_reach_mm: float | None = None
    max_holder_diameter_mm: float | None = None
    runout_requirement_mm: float | None = None
    rigidity_requirement: str | None = None
    clearance_requirement: str | None = None
    coolant_required: bool = False
    basis: str = ""
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class CompatibilityResult:
    """Deterministic tool–holder compatibility check result."""

    result_id: str
    tool_requirement_id: str
    holder_requirement_id: str
    match_status: MatchStatus
    matched_constraints: tuple[str, ...] = ()
    failed_constraints: tuple[str, ...] = ()
    unknown_constraints: tuple[str, ...] = ()
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class CuttingParameterRequirement:
    """Foundation for cutting parameter requirements.

    Per HARD RULE: feeds, speeds and depths are NEVER fabricated.
    All remain UNKNOWN / RANGE_REQUIRED until material and tool are specified.
    """

    cutting_speed_status: CuttingParameterRequirementStatus = (
        CuttingParameterRequirementStatus.UNKNOWN
    )
    feed_per_tooth_status: CuttingParameterRequirementStatus = (
        CuttingParameterRequirementStatus.UNKNOWN
    )
    feed_per_rev_status: CuttingParameterRequirementStatus = (
        CuttingParameterRequirementStatus.UNKNOWN
    )
    depth_of_cut_status: CuttingParameterRequirementStatus = (
        CuttingParameterRequirementStatus.UNKNOWN
    )
    material_group_required: bool = True
    tool_material_required: bool = True


@dataclasses.dataclass(frozen=True)
class MachineToolIntelligenceResult:
    """Top-level Level-5 result attached to a CanonicalDocument.

    All collections are immutable tuples.  Counts and statuses are derived
    from the tuples; no field may be fabricated.
    """

    plan_id: str
    status: SelectionPlanStatus
    recognition_basis: str
    machine_capability_requirements: tuple[MachineCapabilityRequirement, ...] = ()
    machine_candidates: tuple[MachineCandidate, ...] = ()
    tool_capability_requirements: tuple[ToolCapabilityRequirement, ...] = ()
    tool_candidates: tuple[ToolCandidate, ...] = ()
    holder_requirements: tuple[HolderRequirement, ...] = ()
    compatibility_results: tuple[CompatibilityResult, ...] = ()
    cutting_parameter_requirements: CuttingParameterRequirement = dataclasses.field(
        default_factory=CuttingParameterRequirement
    )
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_process_candidate_count: int = 0
    confirmed_process_count: int = 0

    # ------------------------------------------------------------------
    # Derived properties (no fabrication)
    # ------------------------------------------------------------------

    @property
    def compatible_machine_count(self) -> int:
        return sum(
            1
            for mc in self.machine_candidates
            if mc.match_status == MatchStatus.COMPATIBLE
        )

    @property
    def compatible_tool_count(self) -> int:
        return sum(
            1
            for tc in self.tool_candidates
            if tc.match_status == MatchStatus.COMPATIBLE
        )

    @property
    def has_unknown_requirements(self) -> bool:
        return any(
            mc.unknown_requirements for mc in self.machine_candidates
        ) or any(
            tc.unknown_requirements for tc in self.tool_candidates
        )

    @property
    def drilling_tool_candidate_count(self) -> int:
        return sum(
            1
            for tc in self.tool_candidates
            if tc.tool_family in (ToolFamilyV5.DRILL, ToolFamilyV5.CENTER_DRILL)
        )
