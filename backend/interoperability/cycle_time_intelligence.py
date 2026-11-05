"""Level 7 — Cycle Time and Manufacturing Performance Intelligence domain model.

Extends Level-6 cutting-data intelligence with deterministic cycle-time
derivation, time-component evidence, path-fidelity classification,
performance observations, and manufacturing-performance foundations.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate cycle time.
  - Do NOT fabricate toolpath length.
  - Do NOT fabricate machining distance.
  - Do NOT fabricate removal volume.
  - Do NOT fabricate setup time.
  - Do NOT fabricate tool-change time.
  - Do NOT fabricate loading/unloading time.
  - Do NOT fabricate inspection time.
  - Do NOT fabricate rapid rate or rapid distance.
  - Do NOT fabricate machine utilization.
  - Do NOT fabricate OEE.
  - Do NOT fabricate tool life.
  - UNKNOWN engineering data MUST remain UNKNOWN.
  - UNKNOWN values MUST NOT silently become zero.
  - CAD data alone MUST NEVER generate OEE.
  - Approximate geometric path MUST NOT be represented as exact CAM toolpath.
  - Do NOT claim exact cycle time when significant components are unknown.
  - Preserve Levels 1-6 backward compatibility.
"""

from __future__ import annotations

import dataclasses
import math
from enum import StrEnum

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class TimeEvidenceSourceType(StrEnum):
    """Source / derivation method for a time evidence record."""

    CALCULATED = "CALCULATED"
    GEOMETRY_DERIVED = "GEOMETRY_DERIVED"
    CUTTING_DATA_DERIVED = "CUTTING_DATA_DERIVED"
    MACHINE_DATA_DERIVED = "MACHINE_DATA_DERIVED"
    USER_DEFINED = "USER_DEFINED"
    OBSERVED = "OBSERVED"
    HISTORICAL_VALIDATED = "HISTORICAL_VALIDATED"
    PROCESS_STANDARD = "PROCESS_STANDARD"
    GENERIC_REFERENCE = "GENERIC_REFERENCE"
    UNKNOWN = "UNKNOWN"


class TimeComponentType(StrEnum):
    """Classification of an individual time component."""

    CUTTING_TIME = "CUTTING_TIME"
    RAPID_TIME = "RAPID_TIME"
    APPROACH_TIME = "APPROACH_TIME"
    RETRACT_TIME = "RETRACT_TIME"
    POSITIONING_TIME = "POSITIONING_TIME"
    TOOL_CHANGE_TIME = "TOOL_CHANGE_TIME"
    SETUP_TIME = "SETUP_TIME"
    LOAD_UNLOAD_TIME = "LOAD_UNLOAD_TIME"
    INSPECTION_TIME = "INSPECTION_TIME"
    DEBURR_TIME = "DEBURR_TIME"
    DWELL_TIME = "DWELL_TIME"
    SPINDLE_ACCEL_DECEL_TIME = "SPINDLE_ACCEL_DECEL_TIME"
    INDEXING_TIME = "INDEXING_TIME"
    ROTARY_POSITIONING_TIME = "ROTARY_POSITIONING_TIME"
    MANUAL_HANDLING_TIME = "MANUAL_HANDLING_TIME"
    OTHER_TIME = "OTHER_TIME"


class PathFidelity(StrEnum):
    """Fidelity of the path used to derive time estimates.

    EXACT_TOOLPATH: verified NC/CAM toolpath — highest fidelity.
    DERIVED_GEOMETRIC_PATH: path computed from geometric features.
    APPROXIMATE_PATH: path estimated from bounding dimensions.
    FEATURE_DIMENSION_BASED: path inferred from feature dimensions only.
    UNKNOWN: path not known.
    """

    EXACT_TOOLPATH = "EXACT_TOOLPATH"
    DERIVED_GEOMETRIC_PATH = "DERIVED_GEOMETRIC_PATH"
    APPROXIMATE_PATH = "APPROXIMATE_PATH"
    FEATURE_DIMENSION_BASED = "FEATURE_DIMENSION_BASED"
    UNKNOWN = "UNKNOWN"


class OperationTimeStatus(StrEnum):
    """Completeness status of an OperationTimeResult."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class CycleTimeFidelity(StrEnum):
    """Overall fidelity classification for a part cycle-time estimate.

    HIGH:
        Verified/exact path + verified cutting data + verified aux components.
    MEDIUM:
        Derived geometric path + verified cutting data + some auxiliary evidence.
    LOW:
        Generic-reference inputs or incomplete non-cutting times.
    INSUFFICIENT:
        Critical inputs missing — no meaningful estimate possible.
    """

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


class CycleTimePlanStatus(StrEnum):
    """Top-level plan status for the cycle time intelligence result."""

    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    REQUIRES_INPUT = "REQUIRES_INPUT"


class ToolChangeTimeSource(StrEnum):
    """Evidence source for tool-change time."""

    MACHINE_SPECIFIC_VERIFIED = "MACHINE_SPECIFIC_VERIFIED"
    OBSERVED = "OBSERVED"
    HISTORICAL_VALIDATED = "HISTORICAL_VALIDATED"
    USER_DEFINED = "USER_DEFINED"
    GENERIC_REFERENCE = "GENERIC_REFERENCE"
    UNKNOWN = "UNKNOWN"


class SetupTimeSource(StrEnum):
    """Evidence source for setup time."""

    USER_DEFINED = "USER_DEFINED"
    OBSERVED = "OBSERVED"
    HISTORICAL_VALIDATED = "HISTORICAL_VALIDATED"
    PROCESS_STANDARD = "PROCESS_STANDARD"
    GENERIC_REFERENCE = "GENERIC_REFERENCE"
    UNKNOWN = "UNKNOWN"


class PerformanceObservationType(StrEnum):
    """Classification of a manufacturing performance observation."""

    HIGH_CUTTING_TIME_SHARE = "HIGH_CUTTING_TIME_SHARE"
    HIGH_NON_CUTTING_TIME_SHARE = "HIGH_NON_CUTTING_TIME_SHARE"
    HIGH_TOOL_CHANGE_SHARE = "HIGH_TOOL_CHANGE_SHARE"
    MULTIPLE_TOOL_CHANGE_CANDIDATE = "MULTIPLE_TOOL_CHANGE_CANDIDATE"
    HIGH_REMOVAL_VOLUME_OPERATION = "HIGH_REMOVAL_VOLUME_OPERATION"
    CYCLE_TIME_INCOMPLETE = "CYCLE_TIME_INCOMPLETE"
    SETUP_TIME_UNKNOWN = "SETUP_TIME_UNKNOWN"
    TOOL_LIFE_DATA_MISSING = "TOOL_LIFE_DATA_MISSING"
    PATH_FIDELITY_LOW = "PATH_FIDELITY_LOW"


class OptimizationOpportunityType(StrEnum):
    """Classification of an optimization opportunity.

    MUST NOT calculate financial savings — only flag candidates.
    """

    CUTTING_DATA_REVIEW_CANDIDATE = "CUTTING_DATA_REVIEW_CANDIDATE"
    TOOL_CHANGE_REDUCTION_CANDIDATE = "TOOL_CHANGE_REDUCTION_CANDIDATE"
    SETUP_CONSOLIDATION_CANDIDATE = "SETUP_CONSOLIDATION_CANDIDATE"
    PATH_OPTIMIZATION_CANDIDATE = "PATH_OPTIMIZATION_CANDIDATE"


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TimeEvidence:
    """A single time evidence record with mandatory source traceability.

    None value means UNKNOWN — not zero, not estimated, not fabricated.
    Every non-None value MUST have an explicit source_type.
    """

    value: float | None = None
    unit: str = "min"
    source_type: TimeEvidenceSourceType = TimeEvidenceSourceType.UNKNOWN
    evidence: str = ""
    status: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.value is not None

    @property
    def is_unknown(self) -> bool:
        return self.value is None


UNKNOWN_TIME = TimeEvidence(
    value=None,
    unit="min",
    source_type=TimeEvidenceSourceType.UNKNOWN,
    evidence="",
    status="UNKNOWN",
    warnings=(),
)


@dataclasses.dataclass(frozen=True)
class ToolChangeTimeEvidence:
    """Evidence record for tool-change time.

    No evidence → value remains None — do not hard-code a default.
    """

    source: ToolChangeTimeSource = ToolChangeTimeSource.UNKNOWN
    value: float | None = None
    unit: str = "min"
    machine_ref: str = ""
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.value is not None


@dataclasses.dataclass(frozen=True)
class SetupTimeEvidence:
    """Evidence record for setup time.

    Number of setup candidates alone MUST NOT create a numeric setup time.
    """

    source: SetupTimeSource = SetupTimeSource.UNKNOWN
    value: float | None = None
    unit: str = "min"
    setup_ref: str = ""
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.value is not None


@dataclasses.dataclass(frozen=True)
class RemovalVolumeResult:
    """Removal volume for a simple geometric feature.

    Only computed from supported real geometry:
      - simple hole (cylindrical)
      - counterbore
      - simple pocket
      - simple slot
    Complex or unknown topology → value is None.
    """

    volume_mm3: float | None = None
    geometry_basis: str = ""
    formula: str = ""
    evidence_notes: str = ""
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.volume_mm3 is not None


@dataclasses.dataclass(frozen=True)
class MethodComparisonResult:
    """Comparison between path-based and MRR-based cycle time estimates.

    Both estimates must exist for a comparison to be meaningful.
    Do not silently average; expose both.
    """

    path_based_time_min: float | None = None
    mrr_based_time_min: float | None = None
    absolute_difference_min: float | None = None
    relative_difference: float | None = None
    has_discrepancy: bool = False
    discrepancy_threshold: float = 0.20
    status: str = "INSUFFICIENT_DATA"
    warnings: tuple[str, ...] = ()

    @property
    def both_known(self) -> bool:
        return (
            self.path_based_time_min is not None
            and self.mrr_based_time_min is not None
        )


@dataclasses.dataclass(frozen=True)
class OperationTimeResult:
    """Cycle-time components for a single machining operation.

    Unknown components remain UNKNOWN — never coerced to zero.
    """

    operation_ref: str
    operation_type: str
    cutting_time: TimeEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_TIME)
    rapid_time: TimeEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_TIME)
    positioning_time: TimeEvidence = dataclasses.field(default_factory=lambda: UNKNOWN_TIME)
    tool_change_time: ToolChangeTimeEvidence = dataclasses.field(
        default_factory=ToolChangeTimeEvidence
    )
    setup_component: SetupTimeEvidence = dataclasses.field(
        default_factory=SetupTimeEvidence
    )
    other_non_cutting_time: TimeEvidence = dataclasses.field(
        default_factory=lambda: UNKNOWN_TIME
    )
    path_based_time: TimeEvidence = dataclasses.field(
        default_factory=lambda: UNKNOWN_TIME
    )
    mrr_based_time: TimeEvidence = dataclasses.field(
        default_factory=lambda: UNKNOWN_TIME
    )
    method_comparison: MethodComparisonResult = dataclasses.field(
        default_factory=MethodComparisonResult
    )
    removal_volume: RemovalVolumeResult = dataclasses.field(
        default_factory=RemovalVolumeResult
    )
    path_fidelity: PathFidelity = PathFidelity.UNKNOWN
    known_time_min: float | None = None
    unknown_components: tuple[str, ...] = ()
    status: OperationTimeStatus = OperationTimeStatus.INSUFFICIENT_DATA
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def has_cutting_time(self) -> bool:
        return self.cutting_time.is_known or self.path_based_time.is_known


@dataclasses.dataclass(frozen=True)
class PartCycleTime:
    """Aggregated part cycle-time from all known operation times.

    When significant time components remain unknown:
    do NOT report exact TOTAL_CYCLE_TIME.
    """

    known_cutting_time_min: float | None = None
    known_non_cutting_time_min: float | None = None
    known_total_time_min: float | None = None
    unknown_components: tuple[str, ...] = ()
    cycle_time_status: OperationTimeStatus = OperationTimeStatus.INSUFFICIENT_DATA
    cycle_time_fidelity: CycleTimeFidelity = CycleTimeFidelity.INSUFFICIENT
    warnings: tuple[str, ...] = ()


@dataclasses.dataclass(frozen=True)
class BatchTimeResult:
    """Batch time foundation.

    batch_time = setup_time + quantity × recurring_part_time

    Only computed when all required inputs are known.
    """

    quantity: int | None = None
    setup_time: SetupTimeEvidence = dataclasses.field(
        default_factory=SetupTimeEvidence
    )
    recurring_part_time_min: float | None = None
    batch_time_min: float | None = None
    status: str = "INSUFFICIENT_DATA"
    warnings: tuple[str, ...] = ()

    @property
    def is_calculable(self) -> bool:
        return (
            self.quantity is not None
            and self.setup_time.is_known
            and self.recurring_part_time_min is not None
        )


@dataclasses.dataclass(frozen=True)
class ToolLifeConsumptionResult:
    """Tool-life consumption for one cutting operation.

    Only computed where validated tool life exists.
    tool_life_consumption = cutting_time / available_tool_life
    """

    operation_ref: str = ""
    cutting_time_min: float | None = None
    available_tool_life_min: float | None = None
    life_consumption_ratio: float | None = None
    parts_per_edge: float | None = None
    tool_changes_required: int | None = None
    tool_life_source: str = "UNKNOWN"
    status: str = "UNKNOWN"
    warnings: tuple[str, ...] = ()

    @property
    def is_known(self) -> bool:
        return self.life_consumption_ratio is not None


@dataclasses.dataclass(frozen=True)
class SpindleCuttingUtilization:
    """Spindle cutting utilization.

    spindle_cutting_utilization = cutting_time / known_cycle_time

    MUST be labelled SPINDLE_CUTTING_UTILIZATION — NOT OEE.
    """

    cutting_time_min: float | None = None
    known_cycle_time_min: float | None = None
    utilization: float | None = None
    label: str = "SPINDLE_CUTTING_UTILIZATION"
    status: str = "UNKNOWN"
    warnings: tuple[str, ...] = ()

    @property
    def is_calculable(self) -> bool:
        return (
            self.cutting_time_min is not None
            and self.known_cycle_time_min is not None
            and self.known_cycle_time_min > 0
        )


@dataclasses.dataclass(frozen=True)
class OEEFoundation:
    """OEE data-contract foundation.

    OEE requires Availability × Performance × Quality
    and REAL production observations.
    CAD data alone CANNOT provide OEE.

    Default: OEE_STATUS=INSUFFICIENT_PRODUCTION_DATA.
    """

    status: str = "INSUFFICIENT_PRODUCTION_DATA"
    availability: float | None = None
    performance: float | None = None
    quality: float | None = None
    oee: float | None = None
    notes: str = "CAD data alone is insufficient to compute OEE."


@dataclasses.dataclass(frozen=True)
class BottleneckFoundation:
    """Bottleneck identification from known operation times.

    Only compare known values.
    Unknown operations MUST NOT be treated as faster.
    """

    longest_known_operation_ref: str | None = None
    longest_known_time_min: float | None = None
    highest_cutting_time_op_ref: str | None = None
    highest_cutting_time_min: float | None = None
    highest_non_cutting_time_op_ref: str | None = None
    highest_non_cutting_time_min: float | None = None
    highest_tool_change_time_op_ref: str | None = None
    highest_tool_change_time_min: float | None = None
    status: str = "UNKNOWN"


@dataclasses.dataclass(frozen=True)
class PerformanceObservation:
    """A single evidence-based manufacturing performance observation."""

    observation_type: PerformanceObservationType
    description: str
    evidence: str = ""


@dataclasses.dataclass(frozen=True)
class OptimizationOpportunity:
    """A single optimization opportunity — candidate only, no guaranteed savings."""

    opportunity_type: OptimizationOpportunityType
    description: str
    evidence: str = ""


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class CycleTimeIntelligenceResult:
    """Top-level Level-7 result attached to a CanonicalDocument.

    All collections are immutable tuples.
    No field may be fabricated.
    Unknown values remain None — never coerced to zero.
    """

    plan_id: str
    status: CycleTimePlanStatus
    recognition_basis: str
    operation_time_results: tuple[OperationTimeResult, ...] = ()
    part_cycle_time: PartCycleTime = dataclasses.field(
        default_factory=PartCycleTime
    )
    batch_time_foundation: BatchTimeResult = dataclasses.field(
        default_factory=BatchTimeResult
    )
    tool_life_consumption_summary: tuple[ToolLifeConsumptionResult, ...] = ()
    spindle_cutting_utilization: SpindleCuttingUtilization = dataclasses.field(
        default_factory=SpindleCuttingUtilization
    )
    oee_foundation: OEEFoundation = dataclasses.field(
        default_factory=OEEFoundation
    )
    method_comparison: MethodComparisonResult = dataclasses.field(
        default_factory=MethodComparisonResult
    )
    bottleneck_foundation: BottleneckFoundation = dataclasses.field(
        default_factory=BottleneckFoundation
    )
    performance_observations: tuple[PerformanceObservation, ...] = ()
    optimization_opportunities: tuple[OptimizationOpportunity, ...] = ()
    fidelity: CycleTimeFidelity = CycleTimeFidelity.INSUFFICIENT
    missing_inputs: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    source_cdi_candidate_count: int = 0

    @property
    def has_any_known_time(self) -> bool:
        """True when at least one operation has a known cutting time."""
        return any(op.has_cutting_time for op in self.operation_time_results)

    @property
    def operation_count(self) -> int:
        return len(self.operation_time_results)

    @property
    def known_operation_count(self) -> int:
        return sum(
            1 for op in self.operation_time_results
            if op.status != OperationTimeStatus.INSUFFICIENT_DATA
        )


# ---------------------------------------------------------------------------
# Deterministic calculation utilities
# ---------------------------------------------------------------------------


def calculate_cutting_time(
    cutting_distance_mm: float | None,
    feed_rate_mm_per_min: float | None,
    source_type: TimeEvidenceSourceType = TimeEvidenceSourceType.CALCULATED,
    evidence_note: str = "",
) -> TimeEvidence:
    """time = cutting_distance / feed_rate  (both > 0 required).

    Returns TimeEvidence with value=None when any input is missing or invalid.
    UNKNOWN results MUST NOT be represented as zero.
    """
    warns: list[str] = []

    if cutting_distance_mm is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("cutting_distance_mm not provided",),
        )
    if feed_rate_mm_per_min is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("feed_rate_mm_per_min not provided",),
        )
    if cutting_distance_mm <= 0:
        warns.append(f"cutting_distance_mm must be > 0, got {cutting_distance_mm}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )
    if feed_rate_mm_per_min <= 0:
        warns.append(f"feed_rate_mm_per_min must be > 0, got {feed_rate_mm_per_min}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )

    value_min = cutting_distance_mm / feed_rate_mm_per_min
    return TimeEvidence(
        value=value_min,
        unit="min",
        source_type=source_type,
        evidence=evidence_note or (
            f"t = {cutting_distance_mm:.3f} mm / {feed_rate_mm_per_min:.3f} mm/min"
        ),
        status="CALCULATED",
        warnings=tuple(warns),
    )


def calculate_drilling_time(
    depth_mm: float | None,
    rpm: float | None,
    fn_mm_per_rev: float | None,
    source_type: TimeEvidenceSourceType = TimeEvidenceSourceType.CALCULATED,
    evidence_note: str = "",
) -> TimeEvidence:
    """drilling_time = depth / (rpm × fn).

    Do NOT fabricate drill-point allowance, peck parameters, or breakthrough.
    Returns TimeEvidence with value=None when any input is missing.
    """
    if depth_mm is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("depth_mm not provided",),
        )
    if rpm is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("rpm not provided",),
        )
    if fn_mm_per_rev is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("fn_mm_per_rev not provided",),
        )

    warns: list[str] = []
    if depth_mm <= 0:
        warns.append(f"depth_mm must be > 0, got {depth_mm}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )
    if rpm <= 0:
        warns.append(f"rpm must be > 0, got {rpm}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )
    if fn_mm_per_rev <= 0:
        warns.append(f"fn_mm_per_rev must be > 0, got {fn_mm_per_rev}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )

    feed_rate_mm_per_min = rpm * fn_mm_per_rev
    value_min = depth_mm / feed_rate_mm_per_min
    return TimeEvidence(
        value=value_min,
        unit="min",
        source_type=source_type,
        evidence=evidence_note or (
            f"t = {depth_mm:.3f} mm / ({rpm:.1f} rpm × {fn_mm_per_rev:.4f} mm/rev)"
        ),
        status="CALCULATED",
        warnings=tuple(warns),
    )


def calculate_mrr_based_time(
    removal_volume_mm3: float | None,
    mrr_mm3_per_min: float | None,
    source_type: TimeEvidenceSourceType = TimeEvidenceSourceType.CUTTING_DATA_DERIVED,
    evidence_note: str = "",
) -> TimeEvidence:
    """time = removal_volume / MRR.

    Returns TimeEvidence with value=None when any input is missing or invalid.
    """
    if removal_volume_mm3 is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("removal_volume_mm3 not provided",),
        )
    if mrr_mm3_per_min is None:
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=("mrr_mm3_per_min not provided",),
        )

    warns: list[str] = []
    if removal_volume_mm3 <= 0:
        warns.append(f"removal_volume_mm3 must be > 0, got {removal_volume_mm3}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )
    if mrr_mm3_per_min <= 0:
        warns.append(f"mrr_mm3_per_min must be > 0, got {mrr_mm3_per_min}")
        return TimeEvidence(
            source_type=TimeEvidenceSourceType.UNKNOWN,
            status="UNKNOWN",
            warnings=tuple(warns),
        )

    value_min = removal_volume_mm3 / mrr_mm3_per_min
    return TimeEvidence(
        value=value_min,
        unit="min",
        source_type=source_type,
        evidence=evidence_note or (
            f"t = {removal_volume_mm3:.3f} mm³ / {mrr_mm3_per_min:.3f} mm³/min"
        ),
        status="CALCULATED",
        warnings=tuple(warns),
    )


def calculate_cylindrical_removal_volume(
    diameter_mm: float | None,
    depth_mm: float | None,
) -> RemovalVolumeResult:
    """V = π/4 × D² × L  — cylindrical hole.

    Returns RemovalVolumeResult with volume_mm3=None when any input missing.
    """
    if diameter_mm is None or depth_mm is None:
        return RemovalVolumeResult(
            geometry_basis="cylindrical_hole",
            warnings=("diameter_mm or depth_mm not provided",),
        )
    if diameter_mm <= 0 or depth_mm <= 0:
        return RemovalVolumeResult(
            geometry_basis="cylindrical_hole",
            warnings=(f"Invalid dimensions: D={diameter_mm}, L={depth_mm}",),
        )
    vol = math.pi / 4.0 * diameter_mm ** 2 * depth_mm
    return RemovalVolumeResult(
        volume_mm3=vol,
        geometry_basis="cylindrical_hole",
        formula="V = π/4 × D² × L",
        evidence_notes=f"D={diameter_mm:.3f} mm, L={depth_mm:.3f} mm",
    )


def calculate_rectangular_pocket_volume(
    length_mm: float | None,
    width_mm: float | None,
    depth_mm: float | None,
) -> RemovalVolumeResult:
    """V = L × W × D  — rectangular pocket.

    Returns RemovalVolumeResult with volume_mm3=None when any input missing.
    """
    if length_mm is None or width_mm is None or depth_mm is None:
        return RemovalVolumeResult(
            geometry_basis="rectangular_pocket",
            warnings=("length_mm, width_mm, or depth_mm not provided",),
        )
    if length_mm <= 0 or width_mm <= 0 or depth_mm <= 0:
        return RemovalVolumeResult(
            geometry_basis="rectangular_pocket",
            warnings=(f"Invalid dimensions: L={length_mm}, W={width_mm}, D={depth_mm}",),
        )
    vol = length_mm * width_mm * depth_mm
    return RemovalVolumeResult(
        volume_mm3=vol,
        geometry_basis="rectangular_pocket",
        formula="V = L × W × D",
        evidence_notes=f"L={length_mm:.3f} mm, W={width_mm:.3f} mm, D={depth_mm:.3f} mm",
    )


def calculate_pass_count(
    total_depth_mm: float | None,
    ap_mm: float | None,
) -> tuple[int | None, float | None, tuple[str, ...]]:
    """passes = ceil(total_depth / ap); final_pass_depth = remainder.

    Returns (pass_count, final_pass_depth_mm, warnings).
    Returns (None, None, warnings) when total_depth or ap is None/invalid.
    """
    warns: list[str] = []
    if total_depth_mm is None:
        return (None, None, ("total_depth_mm not provided",))
    if ap_mm is None:
        return (None, None, ("ap_mm not provided",))
    if total_depth_mm <= 0:
        warns.append(f"total_depth_mm must be > 0, got {total_depth_mm}")
        return (None, None, tuple(warns))
    if ap_mm <= 0:
        warns.append(f"ap_mm must be > 0, got {ap_mm}")
        return (None, None, tuple(warns))

    n_passes = math.ceil(total_depth_mm / ap_mm)
    final_pass_depth = total_depth_mm - (n_passes - 1) * ap_mm
    return (n_passes, final_pass_depth, tuple(warns))


def calculate_tool_life_consumption(
    cutting_time_min: float | None,
    available_tool_life_min: float | None,
    operation_ref: str = "",
    tool_life_source: str = "UNKNOWN",
) -> ToolLifeConsumptionResult:
    """Compute tool-life consumption where validated tool life exists.

    tool_life_consumption = cutting_time / available_tool_life

    Returns ToolLifeConsumptionResult with None values when any input missing.
    No validated tool life → UNKNOWN.
    """
    if cutting_time_min is None or available_tool_life_min is None:
        return ToolLifeConsumptionResult(
            operation_ref=operation_ref,
            cutting_time_min=cutting_time_min,
            tool_life_source=tool_life_source,
            status="UNKNOWN",
            warnings=("cutting_time or available_tool_life not provided",),
        )
    if cutting_time_min <= 0:
        return ToolLifeConsumptionResult(
            operation_ref=operation_ref,
            cutting_time_min=cutting_time_min,
            tool_life_source=tool_life_source,
            status="UNKNOWN",
            warnings=(f"cutting_time_min must be > 0, got {cutting_time_min}",),
        )
    if available_tool_life_min <= 0:
        return ToolLifeConsumptionResult(
            operation_ref=operation_ref,
            cutting_time_min=cutting_time_min,
            tool_life_source=tool_life_source,
            status="UNKNOWN",
            warnings=(f"available_tool_life_min must be > 0, got {available_tool_life_min}",),
        )

    ratio = cutting_time_min / available_tool_life_min
    parts_per_edge = available_tool_life_min / cutting_time_min if cutting_time_min > 0 else None
    tool_changes = math.ceil(ratio)
    return ToolLifeConsumptionResult(
        operation_ref=operation_ref,
        cutting_time_min=cutting_time_min,
        available_tool_life_min=available_tool_life_min,
        life_consumption_ratio=ratio,
        parts_per_edge=parts_per_edge,
        tool_changes_required=tool_changes,
        tool_life_source=tool_life_source,
        status="CALCULATED",
    )


def calculate_spindle_utilization(
    cutting_time_min: float | None,
    known_cycle_time_min: float | None,
) -> SpindleCuttingUtilization:
    """spindle_cutting_utilization = cutting_time / known_cycle_time.

    MUST be labelled SPINDLE_CUTTING_UTILIZATION — NOT OEE.
    """
    if cutting_time_min is None or known_cycle_time_min is None:
        return SpindleCuttingUtilization(
            cutting_time_min=cutting_time_min,
            known_cycle_time_min=known_cycle_time_min,
            status="UNKNOWN",
            warnings=("cutting_time or known_cycle_time not provided",),
        )
    if known_cycle_time_min <= 0:
        return SpindleCuttingUtilization(
            cutting_time_min=cutting_time_min,
            known_cycle_time_min=known_cycle_time_min,
            status="UNKNOWN",
            warnings=(f"known_cycle_time_min must be > 0, got {known_cycle_time_min}",),
        )

    utilization = cutting_time_min / known_cycle_time_min
    return SpindleCuttingUtilization(
        cutting_time_min=cutting_time_min,
        known_cycle_time_min=known_cycle_time_min,
        utilization=utilization,
        label="SPINDLE_CUTTING_UTILIZATION",
        status="CALCULATED",
    )


def compare_time_methods(
    path_based_time_min: float | None,
    mrr_based_time_min: float | None,
    discrepancy_threshold: float = 0.20,
) -> MethodComparisonResult:
    """Compare path-based and MRR-based cycle time estimates.

    Flags TIME_ESTIMATE_DISCREPANCY when |relative_diff| > threshold.
    Do NOT automatically choose one; expose both.
    """
    if path_based_time_min is None or mrr_based_time_min is None:
        return MethodComparisonResult(
            path_based_time_min=path_based_time_min,
            mrr_based_time_min=mrr_based_time_min,
            status="INSUFFICIENT_DATA",
            discrepancy_threshold=discrepancy_threshold,
        )

    abs_diff = abs(path_based_time_min - mrr_based_time_min)
    ref = max(path_based_time_min, mrr_based_time_min)
    rel_diff = abs_diff / ref if ref > 0 else 0.0
    has_disc = rel_diff > discrepancy_threshold

    return MethodComparisonResult(
        path_based_time_min=path_based_time_min,
        mrr_based_time_min=mrr_based_time_min,
        absolute_difference_min=abs_diff,
        relative_difference=rel_diff,
        has_discrepancy=has_disc,
        discrepancy_threshold=discrepancy_threshold,
        status="TIME_ESTIMATE_DISCREPANCY" if has_disc else "CONSISTENT",
    )
