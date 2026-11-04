"""Manufacturing process intelligence domain model (Level 4 — DFM and Process Intelligence).

Defines the deterministic, immutable data model for machining process
intelligence results derived from Level-3 manufacturing features.

Evidence semantics
------------------
Process recommendations are CANDIDATE unless deterministic rule evidence
makes them CONFIRMED_BY_RULE.  Missing material, tolerance, or dimensional
data always results in REQUIRES_INPUT rather than fabricated assumptions.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate manufacturing processes, machine selections, tool
    selections, feeds, speeds, cycle times or costs.
  - If required engineering information is unavailable, return
    UNKNOWN / INCOMPLETE / REQUIRES_INPUT.
  - Preserve Level-1, Level-2 and Level-3 backward compatibility.
"""

from __future__ import annotations

import dataclasses
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProcessFamily(StrEnum):
    """Broad machining process families."""

    MILLING = "MILLING"
    FACE_MILLING = "FACE_MILLING"
    PROFILE_MILLING = "PROFILE_MILLING"
    TURNING = "TURNING"
    DRILLING = "DRILLING"
    CENTER_DRILLING = "CENTER_DRILLING"
    BORING = "BORING"
    REAMING = "REAMING"
    TAPPING = "TAPPING"
    THREAD_MILLING = "THREAD_MILLING"
    COUNTERSINKING = "COUNTERSINKING"
    COUNTERBORING = "COUNTERBORING"
    CHAMFERING = "CHAMFERING"
    DEBURRING = "DEBURRING"
    GRINDING = "GRINDING"
    EDM = "EDM"
    INSPECTION = "INSPECTION"
    UNKNOWN = "UNKNOWN"


class ProcessStatus(StrEnum):
    """Confidence / evidence level for a process recommendation.

    CANDIDATE            Evidence is insufficient for a confirmed recommendation;
                         additional input or inspection is required.
    RECOMMENDED          Engineering heuristics support this process, but
                         deterministic proof is not available.
    CONFIRMED_BY_RULE    A deterministic manufacturing rule applied to confirmed
                         geometry/topology evidence justifies this process.
    REQUIRES_INPUT       The recommendation is blocked by missing information
                         (material, tolerance, depth, etc.).
    NOT_APPLICABLE       The process family does not apply to this feature.
    """

    CANDIDATE = "CANDIDATE"
    RECOMMENDED = "RECOMMENDED"
    CONFIRMED_BY_RULE = "CONFIRMED_BY_RULE"
    REQUIRES_INPUT = "REQUIRES_INPUT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class MachineClass(StrEnum):
    """Minimum machining centre class required by the operation set."""

    THREE_AXIS_VMC = "THREE_AXIS_VMC"
    FOUR_AXIS_VMC = "FOUR_AXIS_VMC"
    FIVE_AXIS_VMC = "FIVE_AXIS_VMC"
    CNC_LATHE = "CNC_LATHE"
    MILL_TURN = "MILL_TURN"
    HORIZONTAL_MACHINING_CENTER = "HORIZONTAL_MACHINING_CENTER"
    GRINDING_MACHINE = "GRINDING_MACHINE"
    EDM_MACHINE = "EDM_MACHINE"
    UNKNOWN = "UNKNOWN"


class ToolFamily(StrEnum):
    """Generic cutting-tool family.  No specific catalog model is implied."""

    FACE_MILL = "FACE_MILL"
    END_MILL = "END_MILL"
    BALL_NOSE_END_MILL = "BALL_NOSE_END_MILL"
    DRILL = "DRILL"
    CENTER_DRILL = "CENTER_DRILL"
    REAMER = "REAMER"
    BORING_BAR = "BORING_BAR"
    TAP = "TAP"
    THREAD_MILL = "THREAD_MILL"
    CHAMFER_MILL = "CHAMFER_MILL"
    SLOT_MILL = "SLOT_MILL"
    TURNING_INSERT = "TURNING_INSERT"
    GROOVING_TOOL = "GROOVING_TOOL"
    UNKNOWN = "UNKNOWN"


class DFMObservationType(StrEnum):
    """DFM observation categories that can be detected deterministically."""

    DEEP_HOLE = "DEEP_HOLE"
    HIGH_HOLE_LD_RATIO = "HIGH_HOLE_LD_RATIO"
    NARROW_SLOT = "NARROW_SLOT"
    DEEP_POCKET = "DEEP_POCKET"
    LONG_TOOL_REACH = "LONG_TOOL_REACH"
    MULTIPLE_MACHINING_DIRECTIONS = "MULTIPLE_MACHINING_DIRECTIONS"
    POTENTIAL_MULTI_SETUP = "POTENTIAL_MULTI_SETUP"
    SMALL_INTERNAL_RADIUS = "SMALL_INTERNAL_RADIUS"
    SHARP_INTERNAL_CORNER = "SHARP_INTERNAL_CORNER"
    THIN_WALL_CANDIDATE = "THIN_WALL_CANDIDATE"
    INACCESSIBLE_FEATURE_CANDIDATE = "INACCESSIBLE_FEATURE_CANDIDATE"


class DFMSeverity(StrEnum):
    """Manufacturability impact severity."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class AccessibilityStatus(StrEnum):
    """Feature accessibility from a given machining direction."""

    ACCESSIBLE = "ACCESSIBLE"
    POTENTIALLY_ACCESSIBLE = "POTENTIALLY_ACCESSIBLE"
    BLOCKED = "BLOCKED"
    UNKNOWN = "UNKNOWN"


class MaterialStatus(StrEnum):
    """Whether the part material was provided by the caller."""

    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"


class TurningIndicator(StrEnum):
    """Heuristic assessment of whether turning operations are warranted."""

    TURNING_NOT_INDICATED = "TURNING_NOT_INDICATED"
    TURNING_CANDIDATE = "TURNING_CANDIDATE"
    TURNING_STRONGLY_INDICATED = "TURNING_STRONGLY_INDICATED"


class RoughingOrFinishing(StrEnum):
    """Operation pass type."""

    ROUGHING = "ROUGHING"
    FINISHING = "FINISHING"
    COMBINED = "COMBINED"
    UNKNOWN = "UNKNOWN"


class PrecedenceType(StrEnum):
    """Strength of an operation precedence constraint."""

    ENGINEERING_REQUIRED = "ENGINEERING_REQUIRED"
    COMMON_PRACTICE = "COMMON_PRACTICE"
    SHOP_PREFERENCE = "SHOP_PREFERENCE"


class PlanStatus(StrEnum):
    """Overall quality of the produced process plan."""

    COMPLETE = "COMPLETE"
    CANDIDATE_PLAN = "CANDIDATE_PLAN"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REQUIRES_INPUT = "REQUIRES_INPUT"


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class DFMObservation:
    """A single deterministic DFM observation attached to one or more features."""

    observation_id: str
    observation_type: DFMObservationType
    severity: DFMSeverity
    affected_feature_ids: tuple[str, ...]
    engineering_rationale: str
    recommended_action: str
    measured_value: float | None = None
    threshold: float | None = None
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class MachineRequirement:
    """Minimum machine class required by the operation set."""

    requirement_id: str
    machine_class: MachineClass
    rotary_axes_required: int = 0
    min_x_travel_mm: float | None = None
    min_y_travel_mm: float | None = None
    min_z_travel_mm: float | None = None
    basis: str = ""
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class ToolRequirement:
    """Generic cutting-tool family requirement for one operation."""

    requirement_id: str
    tool_family: ToolFamily
    operation_id: str
    min_diameter_mm: float | None = None
    max_diameter_mm: float | None = None
    required_reach_mm: float | None = None
    required_cutting_length_mm: float | None = None
    access_direction: str | None = None
    basis: str = ""
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class SetupCandidate:
    """A candidate machining setup grouping features accessible from one direction."""

    setup_id: str
    machining_direction: str
    feature_ids: tuple[str, ...]
    accessibility: AccessibilityStatus = AccessibilityStatus.UNKNOWN
    orientation_label: str = ""
    notes: str = ""


@dataclasses.dataclass(frozen=True)
class ManufacturingOperation:
    """A candidate or confirmed machining operation derived from feature evidence."""

    operation_id: str
    process_family: ProcessFamily
    status: ProcessStatus
    feature_ids: tuple[str, ...]
    tool_family: ToolFamily
    roughing_or_finishing: RoughingOrFinishing = RoughingOrFinishing.UNKNOWN
    setup_id: str | None = None
    orientation: str | None = None
    precedes: tuple[str, ...] = ()
    follows: tuple[str, ...] = ()
    precedence_type: PrecedenceType = PrecedenceType.COMMON_PRACTICE
    rationale: str = ""
    warnings: tuple[str, ...] = ()
    evidence_notes: str = ""


@dataclasses.dataclass(frozen=True)
class MaterialContext:
    """Material context provided by the caller or inferred from the document."""

    material_name: str | None = None
    material_family: str | None = None
    hardness_hrc: float | None = None
    condition: str | None = None
    status: MaterialStatus = MaterialStatus.UNKNOWN


@dataclasses.dataclass(frozen=True)
class CuttingParameterStatus:
    """Cutting parameter availability for all operations.

    Per HARD RULE: feeds, speeds and depths are never fabricated.
    All are UNKNOWN / REQUIRES_INPUT until material and tool are specified.
    """

    cutting_speed_status: str = "REQUIRES_MATERIAL_INPUT"
    feed_per_tooth_status: str = "REQUIRES_MATERIAL_INPUT"
    depth_of_cut_status: str = "REQUIRES_MATERIAL_INPUT"
    estimated_cutting_speed_m_min: None = None
    estimated_feed_mm_tooth: None = None
    estimated_doc_mm: None = None
    source: str | None = None
    material_required: bool = True
    tool_material_required: bool = True


@dataclasses.dataclass(frozen=True)
class CycleTimeStatus:
    """Cycle time estimation availability.

    Per HARD RULE: cycle times are never fabricated.
    All are null until cutting parameters and machine are specified.
    """

    setup_time_status: str = "REQUIRES_CUTTING_PARAMETERS"
    machining_time_status: str = "REQUIRES_CUTTING_PARAMETERS"
    tool_change_time_status: str = "REQUIRES_CUTTING_PARAMETERS"
    inspection_time_status: str = "REQUIRES_CUTTING_PARAMETERS"
    estimated_total_minutes: None = None


@dataclasses.dataclass(frozen=True)
class ProcessIntelligenceResult:
    """Top-level Level-4 result attached to a CanonicalDocument.

    All collections are immutable tuples.  Counts and statuses are derived
    from the tuples; no field may be fabricated.
    """

    plan_id: str
    status: PlanStatus
    recognition_basis: str
    dfm_observations: tuple[DFMObservation, ...] = ()
    process_candidates: tuple[ManufacturingOperation, ...] = ()
    setups: tuple[SetupCandidate, ...] = ()
    machine_requirements: tuple[MachineRequirement, ...] = ()
    tool_requirements: tuple[ToolRequirement, ...] = ()
    operation_plan: tuple[ManufacturingOperation, ...] = ()
    material_context: MaterialContext = dataclasses.field(
        default_factory=MaterialContext
    )
    cutting_parameter_status: CuttingParameterStatus = dataclasses.field(
        default_factory=CuttingParameterStatus
    )
    cycle_time_status: CycleTimeStatus = dataclasses.field(
        default_factory=CycleTimeStatus
    )
    turning_indicator: TurningIndicator = TurningIndicator.TURNING_NOT_INDICATED
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_feature_count: int = 0
    confirmed_feature_count: int = 0

    # ------------------------------------------------------------------
    # Derived properties (no fabrication)
    # ------------------------------------------------------------------

    @property
    def drilling_candidate_count(self) -> int:
        return sum(
            1
            for op in self.process_candidates
            if op.process_family == ProcessFamily.DRILLING
        )

    @property
    def confirmed_operation_count(self) -> int:
        return sum(
            1
            for op in self.operation_plan
            if op.status == ProcessStatus.CONFIRMED_BY_RULE
        )

    @property
    def has_dfm_issues(self) -> bool:
        return any(
            obs.severity in (DFMSeverity.MEDIUM, DFMSeverity.HIGH)
            for obs in self.dfm_observations
        )

    @property
    def high_severity_dfm_count(self) -> int:
        return sum(
            1 for obs in self.dfm_observations if obs.severity == DFMSeverity.HIGH
        )
