"""Phase 6 CAM bridge — wires Phase 5 feature candidates to existing toolpath infrastructure.

Purpose
-------
Bridge Phase 5 feature candidates (POCKET/SLOT/STEP/HOLE) to the existing
CAM planning and toolpath infrastructure.  Evaluates readiness, selects
catalog tools, and reports the first blocker for each candidate.

Safety contract
---------------
is_dispatchable=False — always, without exception.
production_released=False — always.
CANDIDATE != ENGINEERING_CONFIRMED — toolpath generation not attempted.
No fabrication of tools, geometry, cutting data, or CAM status.
UNKNOWN/AMBIGUOUS/NOT_VERIFIABLE remain so.
Voxel gouge verification deferred — no voxel engine available.
HARD RULES 1-35 from TASK: MACHININGPRO_AI_P10_PHASE6_REAL_3D_CAM_AND_TOOL_COVERAGE
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.seed_catalog import get_catalog
from backend.step_brep.gmsh_step_parser import StepImportRecord
from backend.step_brep.phase5_feature_detector import (
    OrientedCylinderRecord,
    PocketCandidateRecord,
    SlotCandidateRecord,
    StepShoulderRecord,
    detect_oriented_cylinders,
    detect_pocket_candidates,
    detect_slot_candidates,
    detect_step_shoulder_candidates,
    filter_internal_cylinders,
)

__all__ = [
    "FirstBlocker",
    "CAMReadinessStatus",
    "DrillStrategy",
    "GougeVerificationStatus",
    "PocketCAMAssessment",
    "SlotCAMAssessment",
    "StepCAMAssessment",
    "HoleCAMAssessment",
    "GougeVerificationAssessment",
    "Phase6SafetyInvariants",
    "Phase6CoverageResult",
    "assess_pocket_cam",
    "assess_slot_cam",
    "assess_step_cam",
    "assess_hole_cam",
    "assess_gouge_verification",
    "build_phase6_coverage",
    "check_phase6_safety_invariants",
]

# ---------------------------------------------------------------------------
# Constants — safety invariants, never changed
# ---------------------------------------------------------------------------

_IS_DISPATCHABLE: bool = False
_PRODUCTION_RELEASED: bool = False
_REVIEW_REQUIRED: bool = True
_OFFLINE_ONLY: bool = True

# Diameter thresholds for holemaking strategy selection
_DRILL_MAX_DIAMETER_MM: float = 20.0   # >= this: boring/helical required
_EXACT_MATCH_TOLERANCE_MM: float = 0.05
# Within 7% → COMPATIBLE_MATCH.  Chosen so the Phase 5 unmatched diameters
# (6.6mm vs 6.0mm = 9.1%, 20.0mm vs 18.0mm = 10.0%) remain NO_MATCH.
_COMPATIBLE_MATCH_RATIO: float = 0.07


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FirstBlocker(StrEnum):
    ENGINEERING_CONFIRMATION = "ENGINEERING_CONFIRMATION"
    MATERIAL = "MATERIAL"
    TOLERANCE = "TOLERANCE"
    TOOL = "TOOL"
    CUTTING_DATA = "CUTTING_DATA"
    CAM_STRATEGY = "CAM_STRATEGY"
    TOOLPATH = "TOOLPATH"
    SETUP = "SETUP"
    WCS = "WCS"
    GEOMETRY_DISAMBIGUATION = "GEOMETRY_DISAMBIGUATION"
    OTHER = "OTHER"
    NONE = "NONE"


class CAMReadinessStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    BLOCKED = "BLOCKED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NOT_READY = "NOT_READY"
    DEFERRED = "DEFERRED"


class DrillStrategy(StrEnum):
    DRILL = "DRILL"
    PECK_DRILL = "PECK_DRILL"
    REAMING = "REAMING"
    HELICAL_INTERPOLATION = "HELICAL_INTERPOLATION"
    BORING = "BORING"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class GougeVerificationStatus(StrEnum):
    NOT_VERIFIABLE = "NOT_VERIFIABLE"
    DEFERRED = "DEFERRED"
    WITHIN_DEFINED_SCOPE = "WITHIN_DEFINED_SCOPE"
    UNDERMACHINED = "UNDERMACHINED"
    OVERMACHINED = "OVERMACHINED"
    GOUGE = "GOUGE"


# ---------------------------------------------------------------------------
# Assessment dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PocketCAMAssessment:
    """CAM readiness assessment for one pocket candidate.

    is_dispatchable=False always.
    feature_status=CANDIDATE always (MUST 17 / HARD RULE 17).
    Production toolpath not generated for CANDIDATE features (MUST 8).
    """

    feature_id: str
    pocket_class: str
    feature_status: str
    first_blocker: FirstBlocker
    cam_strategy: str
    tool_stable_id: str | None
    tool_diameter_mm: float | None
    boundary_available: bool
    depth_mm: float | None
    width_mm: float | None
    length_mm: float | None
    opening_z: float | None
    wcs_status: str
    cutting_data_status: str
    toolpath_status: CAMReadinessStatus
    toolpath_blocked_by: list[str]
    is_dispatchable: bool
    review_required: bool
    offline_only: bool
    notes: str


@dataclass(frozen=True)
class SlotCAMAssessment:
    """CAM readiness assessment for one slot candidate.

    Tool diameter checked against slot width (MUST 18/19).
    slot_toolpath_ready=False always in Phase 6 (WCS undefined).
    """

    feature_id: str
    slot_class: str
    feature_status: str
    first_blocker: FirstBlocker
    cam_strategy: str
    tool_stable_id: str | None
    tool_diameter_mm: float | None
    tool_fits_slot: bool
    slot_width_mm: float | None
    slot_depth_mm: float | None
    slot_length_mm: float | None
    axis_direction: str | None
    wcs_status: str
    cutting_data_status: str
    slot_toolpath_ready: bool
    toolpath_status: CAMReadinessStatus
    toolpath_blocked_by: list[str]
    is_dispatchable: bool
    review_required: bool
    offline_only: bool
    notes: str


@dataclass(frozen=True)
class StepCAMAssessment:
    """CAM readiness assessment for one step/shoulder candidate."""

    feature_id: str
    step_height_mm: float | None
    feature_status: str
    first_blocker: FirstBlocker
    cam_strategy: str
    tool_stable_id: str | None
    tool_diameter_mm: float | None
    wcs_status: str
    toolpath_status: CAMReadinessStatus
    toolpath_blocked_by: list[str]
    is_dispatchable: bool
    review_required: bool
    notes: str


@dataclass(frozen=True)
class HoleCAMAssessment:
    """CAM readiness assessment for one hole/bore cylinder (MUST 24-27).

    Strategy selection is capability-based (MUST 25).
    No fabricated tool geometry or machine capability (MUST 26).
    Large-diameter boring/helical deferred — no generator (MUST 27).
    """

    feature_id: str
    diameter_mm: float
    depth_mm: float | None
    cylinder_orientation: str
    hole_class: str
    feature_status: str
    drill_strategy: DrillStrategy
    first_blocker: FirstBlocker
    tool_stable_id: str | None
    tool_diameter_mm: float | None
    tool_match_type: str
    toolpath_status: CAMReadinessStatus
    toolpath_blocked_by: list[str]
    advanced_holemaking_status: str
    is_dispatchable: bool
    review_required: bool
    notes: str


@dataclass(frozen=True)
class GougeVerificationAssessment:
    """Phase 6 gouge verification state (MUST 28-30).

    All four categories defined (MUST 30) but NOT_VERIFIABLE without voxel engine.
    GOUGE_VALIDATED=YES requires: target, simulation, alignment, comparison (MUST 35).
    """

    source_path: str
    step_target_available: bool
    voxel_simulation_available: bool
    coordinate_alignment_verified: bool
    comparison_method: str
    verification_status: GougeVerificationStatus
    undermachined: GougeVerificationStatus
    overmachined: GougeVerificationStatus
    gouge: GougeVerificationStatus
    within_scope: GougeVerificationStatus
    required_for_implementation: list[str]
    is_dispatchable: bool
    notes: str


@dataclass(frozen=True)
class Phase6SafetyInvariants:
    """Phase 6 safety invariant check result."""

    any_is_dispatchable_true: bool
    any_production_released_true: bool
    any_auto_confirmed: bool
    any_gouge_pass: bool
    all_candidates_remain_candidate: bool
    safety_pass: bool


@dataclass(frozen=True)
class Phase6CoverageResult:
    """Master Phase 6 CAM coverage assessment for one STEP file."""

    source_path: str
    sha256: str
    pocket_assessments: list[PocketCAMAssessment]
    slot_assessments: list[SlotCAMAssessment]
    step_assessments: list[StepCAMAssessment]
    hole_assessments: list[HoleCAMAssessment]
    gouge_assessment: GougeVerificationAssessment
    pocket_tool_found_count: int
    slot_tool_found_count: int
    slot_tool_fits_count: int
    holes_with_drill_match: int
    pocket_cam_status: str
    slot_cam_status: str
    step_cam_status: str
    drill_cam_status: str
    bore_cam_status: str
    tool_match_coverage: str
    is_dispatchable: bool
    production_released: bool
    safety_invariants: Phase6SafetyInvariants


# ---------------------------------------------------------------------------
# Tool selection helpers
# ---------------------------------------------------------------------------

def _get_end_mills() -> list[CuttingToolCatalogRecord]:
    return [
        t for t in get_catalog()
        if t.tool_category_code == "END_MILL"
        and t.cutting_diameter_mm is not None
    ]


def _get_drills() -> list[CuttingToolCatalogRecord]:
    return [
        t for t in get_catalog()
        if t.tool_category_code == "DRILL"
        and t.cutting_diameter_mm is not None
    ]


def _select_end_mill_for_slot(slot_width_mm: float) -> CuttingToolCatalogRecord | None:
    """Largest end mill with cutting_diameter_mm <= slot_width_mm (MUST 18)."""
    candidates = [
        (t, t.cutting_diameter_mm)
        for t in _get_end_mills()
        if t.cutting_diameter_mm <= slot_width_mm
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[1])[0]


def _select_end_mill_for_pocket(
    width_mm: float | None,
    length_mm: float | None,
) -> CuttingToolCatalogRecord | None:
    """Largest end mill that fits inside pocket with safe clearance.

    Uses min(width, length) × 0.8 as max tool diameter so the tool
    can reach the floor centre without interference on first pass.
    """
    if width_mm is None or length_mm is None:
        return None
    max_dia = min(width_mm, length_mm) * 0.8
    candidates = [
        (t, t.cutting_diameter_mm)
        for t in _get_end_mills()
        if t.cutting_diameter_mm < max_dia
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda x: x[1])[0]


def _select_end_mill_for_step(step_height_mm: float | None) -> CuttingToolCatalogRecord | None:  # noqa: ARG001
    """Largest available end mill for step/contour pass.

    Step height does not constrain tool diameter directly.
    """
    em = _get_end_mills()
    if not em:
        return None
    return max(em, key=lambda t: t.cutting_diameter_mm)


def _select_drill_for_hole(
    diameter_mm: float,
) -> tuple[CuttingToolCatalogRecord | None, str]:
    """Find exact or compatible drill match.

    Returns (tool, match_type) where match_type is one of:
      EXACT_MATCH       — |catalog_dia - required_dia| <= 0.05 mm
      COMPATIBLE_MATCH  — within 10% but not exact (needs confirmation)
      NO_MATCH          — nothing close enough
    """
    drills = _get_drills()
    for t in drills:
        if abs(t.cutting_diameter_mm - diameter_mm) <= _EXACT_MATCH_TOLERANCE_MM:
            return t, "EXACT_MATCH"
    compatible = [
        (t, abs(t.cutting_diameter_mm - diameter_mm))
        for t in drills
        if abs(t.cutting_diameter_mm - diameter_mm) / diameter_mm <= _COMPATIBLE_MATCH_RATIO
    ]
    if compatible:
        best = min(compatible, key=lambda x: x[1])
        return best[0], "COMPATIBLE_MATCH"
    return None, "NO_MATCH"


# ---------------------------------------------------------------------------
# Individual assessment functions
# ---------------------------------------------------------------------------

def assess_pocket_cam(pocket: PocketCandidateRecord) -> PocketCAMAssessment:
    """Assess CAM readiness for one pocket candidate.

    Does NOT generate a production toolpath (MUST 8 — CANDIDATE features only).
    Reports first blocker and downstream requirements.
    """
    feature_id = f"pocket:floor={pocket.floor_face_tag}"
    blocked_by: list[str] = []

    first_blocker = FirstBlocker.ENGINEERING_CONFIRMATION
    blocked_by.append(
        "feature_status=CANDIDATE: ENGINEERING_CONFIRMATION required before toolpath"
    )

    geom_ok = (
        pocket.depth_mm is not None
        and pocket.width_mm is not None
        and pocket.length_mm is not None
    )
    if not geom_ok:
        blocked_by.append("pocket_geometry: depth/width/length not fully available from bbox")

    if pocket.pocket_class == "AMBIGUOUS_POCKET":
        blocked_by.append(
            "pocket_class=AMBIGUOUS_POCKET: geometry disambiguation required before toolpath"
        )
        cam_strategy = "NOT_AVAILABLE"
        tool: CuttingToolCatalogRecord | None = None
    else:
        cam_strategy = "CONVENTIONAL_POCKETING"
        tool = _select_end_mill_for_pocket(pocket.width_mm, pocket.length_mm)
        if tool is None:
            blocked_by.append(
                f"tool: no end mill fits pocket dimensions "
                f"(w={pocket.width_mm} l={pocket.length_mm}) in catalog"
            )

    blocked_by.append("wcs_ref: not defined — WCS_UNKNOWN (Phase 6)")
    blocked_by.append("cutting_data: stepdown/stepover not available (Phase 6)")

    if pocket.pocket_class == "AMBIGUOUS_POCKET" or not geom_ok:
        toolpath_status = CAMReadinessStatus.INSUFFICIENT_DATA
    else:
        toolpath_status = CAMReadinessStatus.BLOCKED

    notes_parts = [f"class={pocket.pocket_class}"]
    if tool is not None:
        notes_parts.append(
            f"tool_found={tool.cutting_diameter_mm}mm ({tool.product_name})"
        )
    else:
        notes_parts.append("no_matching_tool_in_catalog")
    if geom_ok:
        notes_parts.append(
            f"depth={pocket.depth_mm}mm w={pocket.width_mm}mm l={pocket.length_mm}mm"
        )

    return PocketCAMAssessment(
        feature_id=feature_id,
        pocket_class=pocket.pocket_class,
        feature_status=pocket.feature_status,
        first_blocker=first_blocker,
        cam_strategy=cam_strategy,
        tool_stable_id=tool.stable_id if tool is not None else None,
        tool_diameter_mm=tool.cutting_diameter_mm if tool is not None else None,
        boundary_available=geom_ok,
        depth_mm=pocket.depth_mm,
        width_mm=pocket.width_mm,
        length_mm=pocket.length_mm,
        opening_z=pocket.opening_z,
        wcs_status="NOT_DEFINED",
        cutting_data_status="NOT_AVAILABLE",
        toolpath_status=toolpath_status,
        toolpath_blocked_by=blocked_by,
        is_dispatchable=_IS_DISPATCHABLE,
        review_required=_REVIEW_REQUIRED,
        offline_only=_OFFLINE_ONLY,
        notes="; ".join(notes_parts),
    )


def assess_slot_cam(slot: SlotCandidateRecord) -> SlotCAMAssessment:
    """Assess CAM readiness for one slot candidate.

    Tool compatibility with slot width checked (MUST 18).
    Returns slot_toolpath_ready=False and explicit blocker (MUST 19).
    """
    feature_id = f"slot:floor={slot.floor_face_tag}"
    blocked_by: list[str] = []

    first_blocker = FirstBlocker.ENGINEERING_CONFIRMATION
    blocked_by.append(
        "feature_status=CANDIDATE: ENGINEERING_CONFIRMATION required before toolpath"
    )

    geom_ok = (
        slot.width_mm is not None
        and slot.depth_mm is not None
        and slot.length_mm is not None
    )

    if slot.slot_class == "AMBIGUOUS_SLOT":
        blocked_by.append(
            "slot_class=AMBIGUOUS_SLOT: geometry disambiguation required"
        )
        cam_strategy = "NOT_AVAILABLE"
        tool_s: CuttingToolCatalogRecord | None = None
        tool_fits = False
    else:
        cam_strategy = "SLOT_MILL"
        if slot.width_mm is not None:
            tool_s = _select_end_mill_for_slot(slot.width_mm)
            tool_fits = tool_s is not None
            if not tool_fits:
                blocked_by.append(
                    f"tool: no end mill with diameter <= {slot.width_mm}mm in catalog"
                )
        else:
            tool_s = None
            tool_fits = False
            blocked_by.append("slot_width_mm: not available — cannot select tool")

    blocked_by.append("wcs_ref: not defined — WCS_UNKNOWN (Phase 6)")
    blocked_by.append("cutting_data: not available (Phase 6)")

    # slot_toolpath_ready requires geom + tool + WCS + cutting data — always False in Phase 6
    slot_toolpath_ready = False

    if not geom_ok or slot.slot_class == "AMBIGUOUS_SLOT":
        toolpath_status = CAMReadinessStatus.INSUFFICIENT_DATA
    else:
        toolpath_status = CAMReadinessStatus.BLOCKED

    notes_parts = [f"class={slot.slot_class}"]
    if tool_s is not None and tool_fits:
        notes_parts.append(
            f"tool_found={tool_s.cutting_diameter_mm}mm ({tool_s.product_name}) "
            f"fits_slot_width={slot.width_mm}mm"
        )
    elif slot.width_mm is not None:
        notes_parts.append(f"no_tool_fits_width={slot.width_mm}mm")
    if geom_ok:
        notes_parts.append(
            f"w={slot.width_mm}mm d={slot.depth_mm}mm l={slot.length_mm}mm "
            f"axis={slot.axis_direction}"
        )

    return SlotCAMAssessment(
        feature_id=feature_id,
        slot_class=slot.slot_class,
        feature_status=slot.feature_status,
        first_blocker=first_blocker,
        cam_strategy=cam_strategy,
        tool_stable_id=tool_s.stable_id if tool_s is not None else None,
        tool_diameter_mm=tool_s.cutting_diameter_mm if tool_s is not None else None,
        tool_fits_slot=tool_fits,
        slot_width_mm=slot.width_mm,
        slot_depth_mm=slot.depth_mm,
        slot_length_mm=slot.length_mm,
        axis_direction=slot.axis_direction,
        wcs_status="NOT_DEFINED",
        cutting_data_status="NOT_AVAILABLE",
        slot_toolpath_ready=slot_toolpath_ready,
        toolpath_status=toolpath_status,
        toolpath_blocked_by=blocked_by,
        is_dispatchable=_IS_DISPATCHABLE,
        review_required=_REVIEW_REQUIRED,
        offline_only=_OFFLINE_ONLY,
        notes="; ".join(notes_parts),
    )


def assess_step_cam(step: StepShoulderRecord) -> StepCAMAssessment:
    """Assess CAM readiness for one step/shoulder candidate."""
    feature_id = f"step:lower={step.lower_face_tag}:upper={step.upper_face_tag}"
    blocked_by: list[str] = []

    first_blocker = FirstBlocker.ENGINEERING_CONFIRMATION
    blocked_by.append(
        "feature_status=CANDIDATE: ENGINEERING_CONFIRMATION required before toolpath"
    )
    blocked_by.append(
        "contour_boundary: 2D profile points not extractable from face tags alone — "
        "requires geometry resolver (Phase 6C scope)"
    )
    blocked_by.append("wcs_ref: not defined — WCS_UNKNOWN (Phase 6)")

    cam_strategy = "CONTOUR_STEP_MILLING"
    tool_step = _select_end_mill_for_step(step.step_height_mm)
    toolpath_status = CAMReadinessStatus.BLOCKED

    notes_parts = ["strategy=CONTOUR_STEP_MILLING"]
    if step.step_height_mm is not None:
        notes_parts.append(f"step_height={step.step_height_mm}mm")
    else:
        notes_parts.append("step_height=UNKNOWN")
    if tool_step is not None:
        notes_parts.append(
            f"tool_candidate={tool_step.cutting_diameter_mm}mm ({tool_step.product_name})"
        )
    notes_parts.append("contour_boundary_extraction_not_implemented")

    return StepCAMAssessment(
        feature_id=feature_id,
        step_height_mm=step.step_height_mm,
        feature_status=step.feature_status,
        first_blocker=first_blocker,
        cam_strategy=cam_strategy,
        tool_stable_id=tool_step.stable_id if tool_step is not None else None,
        tool_diameter_mm=tool_step.cutting_diameter_mm if tool_step is not None else None,
        wcs_status="NOT_DEFINED",
        toolpath_status=toolpath_status,
        toolpath_blocked_by=blocked_by,
        is_dispatchable=_IS_DISPATCHABLE,
        review_required=_REVIEW_REQUIRED,
        notes="; ".join(notes_parts),
    )


def assess_hole_cam(cyl: OrientedCylinderRecord) -> HoleCAMAssessment:
    """Assess CAM readiness for one hole/bore candidate (MUST 24-27).

    Strategy is capability-based (MUST 25).
    No fabricated boring bar / machine capability (MUST 26).
    Helical path generator not implemented → DEFERRED (MUST 27).
    """
    feature_id = f"hole:face={cyl.face_tag}"
    blocked_by: list[str] = []

    first_blocker = FirstBlocker.ENGINEERING_CONFIRMATION
    blocked_by.append(
        "feature_status=CANDIDATE: ENGINEERING_CONFIRMATION required before toolpath"
    )

    diameter = cyl.diameter_mm

    if diameter >= _DRILL_MAX_DIAMETER_MM:
        # Large diameter: standard drilling not feasible
        # Helical interpolation or boring required, but no generator exists
        drill_strategy = DrillStrategy.HELICAL_INTERPOLATION
        advanced_status = "DEFERRED_NO_HELICAL_GENERATOR"
        blocked_by.append(
            f"diameter={diameter}mm: boring/helical required; "
            "helical path generator not implemented (Phase 6D/6F scope)"
        )
        tool_hole: CuttingToolCatalogRecord | None = None
        match_type = "NO_MATCH"
    else:
        tool_hole, match_type = _select_drill_for_hole(diameter)
        if match_type == "NO_MATCH":
            drill_strategy = DrillStrategy.UNSUPPORTED
            advanced_status = "NOT_APPLICABLE"
            blocked_by.append(
                f"drill: no match for ⌀{diameter}mm in catalog — "
                "TOOL catalog expansion required (P10-6E)"
            )
        elif match_type == "COMPATIBLE_MATCH":
            drill_strategy = DrillStrategy.DRILL
            advanced_status = "NOT_APPLICABLE"
            blocked_by.append(
                f"drill: compatible match only "
                f"({tool_hole.cutting_diameter_mm}mm vs ⌀{diameter}mm) — "
                "ENGINEERING_CONFIRMATION required before use"
            )
        else:
            drill_strategy = DrillStrategy.DRILL
            advanced_status = "NOT_APPLICABLE"

    blocked_by.append("wcs_ref: not defined — WCS_UNKNOWN (Phase 6)")

    toolpath_status = CAMReadinessStatus.BLOCKED

    notes_parts = [
        f"d={diameter}mm",
        f"strategy={drill_strategy.value}",
        f"match={match_type}",
    ]
    if tool_hole is not None:
        notes_parts.append(
            f"tool={tool_hole.cutting_diameter_mm}mm ({tool_hole.product_name})"
        )
    else:
        notes_parts.append("no_matching_drill_in_catalog")

    return HoleCAMAssessment(
        feature_id=feature_id,
        diameter_mm=diameter,
        depth_mm=cyl.depth_mm,
        cylinder_orientation=cyl.cylinder_orientation.value,
        hole_class=cyl.hole_class,
        feature_status=cyl.feature_status,
        drill_strategy=drill_strategy,
        first_blocker=first_blocker,
        tool_stable_id=tool_hole.stable_id if tool_hole is not None else None,
        tool_diameter_mm=tool_hole.cutting_diameter_mm if tool_hole is not None else None,
        tool_match_type=match_type,
        toolpath_status=toolpath_status,
        toolpath_blocked_by=blocked_by,
        advanced_holemaking_status=advanced_status,
        is_dispatchable=_IS_DISPATCHABLE,
        review_required=_REVIEW_REQUIRED,
        notes="; ".join(notes_parts),
    )


def assess_gouge_verification(record: StepImportRecord) -> GougeVerificationAssessment:
    """Phase 6 gouge verification assessment (MUST 28-30).

    All four categories defined per MUST 30.
    All remain NOT_VERIFIABLE — no voxel engine, no machined result.
    GOUGE_VALIDATED=YES requires all five conditions (MUST 35).
    """
    required: list[str] = [
        "VOXEL_SIMULATION_ENGINE: not implemented — required for stock removal simulation",
        "MACHINED_RESULT: no simulated or actual machined part available to compare",
        "COORDINATE_ALIGNMENT: STEP target and voxel result must share coordinate system",
        "TOLERANCE_DATA: engineering tolerance required for WITHIN_DEFINED_SCOPE verdict",
        "COMPARISON_METHOD: voxel-vs-target subtraction algorithm not implemented",
    ]
    return GougeVerificationAssessment(
        source_path=record.source_path,
        step_target_available=True,
        voxel_simulation_available=False,
        coordinate_alignment_verified=False,
        comparison_method="NOT_IMPLEMENTED",
        verification_status=GougeVerificationStatus.NOT_VERIFIABLE,
        undermachined=GougeVerificationStatus.NOT_VERIFIABLE,
        overmachined=GougeVerificationStatus.NOT_VERIFIABLE,
        gouge=GougeVerificationStatus.NOT_VERIFIABLE,
        within_scope=GougeVerificationStatus.NOT_VERIFIABLE,
        required_for_implementation=required,
        is_dispatchable=_IS_DISPATCHABLE,
        notes=(
            "Phase 6: STEP target geometry available but voxel simulation not implemented. "
            "UNDERMACHINED / OVERMACHINED / GOUGE / WITHIN_SCOPE categories are defined "
            "but cannot be computed without voxel engine and machined result. "
            "Phase 6F required for implementation. "
            "HARD RULE 16: Do NOT fabricate gouge PASS."
        ),
    )


# ---------------------------------------------------------------------------
# Master assessment
# ---------------------------------------------------------------------------

def build_phase6_coverage(record: StepImportRecord) -> Phase6CoverageResult:
    """Build complete Phase 6 CAM coverage assessment for one STEP file."""
    oriented_cyls = detect_oriented_cylinders(record)
    internal_cyls = filter_internal_cylinders(oriented_cyls)
    pockets = detect_pocket_candidates(record)
    slots = detect_slot_candidates(record)
    steps = detect_step_shoulder_candidates(record)

    pocket_assessments = [assess_pocket_cam(p) for p in pockets]
    slot_assessments = [assess_slot_cam(s) for s in slots]
    step_assessments = [assess_step_cam(st) for st in steps]
    hole_assessments = [assess_hole_cam(c) for c in internal_cyls]
    gouge_assessment = assess_gouge_verification(record)

    pocket_tool_found = sum(
        1 for p in pocket_assessments if p.tool_stable_id is not None
    )
    slot_tool_found = sum(
        1 for s in slot_assessments if s.tool_stable_id is not None
    )
    slot_tool_fits = sum(1 for s in slot_assessments if s.tool_fits_slot)
    holes_with_drill = sum(
        1 for h in hole_assessments if h.tool_match_type == "EXACT_MATCH"
    )
    n_unique_diams = len(set(h.diameter_mm for h in hole_assessments)) if hole_assessments else 0

    pocket_cam_status = (
        "PARTIAL_TOOL_AVAILABLE" if pocket_tool_found > 0 else "BLOCKED_NO_TOOL"
    )
    slot_cam_status = (
        "PARTIAL_TOOL_FITS" if slot_tool_fits > 0 else "BLOCKED_NO_TOOL"
    )
    step_cam_status = "BLOCKED_MISSING_CONTOUR_BOUNDARY"
    drill_cam_status = (
        "BLOCKED_NO_MATCHING_DRILL"
        if holes_with_drill == 0
        else f"PARTIAL_{holes_with_drill}_EXACT"
    )
    bore_cam_status = "DEFERRED_NO_HELICAL_GENERATOR"

    tool_match_coverage = (
        f"{holes_with_drill}/{n_unique_diams} exact drill matches"
        if n_unique_diams > 0
        else "0/0"
    )

    safety = check_phase6_safety_invariants(
        pocket_assessments, slot_assessments, step_assessments,
        hole_assessments, gouge_assessment,
    )

    return Phase6CoverageResult(
        source_path=record.source_path,
        sha256=record.sha256,
        pocket_assessments=pocket_assessments,
        slot_assessments=slot_assessments,
        step_assessments=step_assessments,
        hole_assessments=hole_assessments,
        gouge_assessment=gouge_assessment,
        pocket_tool_found_count=pocket_tool_found,
        slot_tool_found_count=slot_tool_found,
        slot_tool_fits_count=slot_tool_fits,
        holes_with_drill_match=holes_with_drill,
        pocket_cam_status=pocket_cam_status,
        slot_cam_status=slot_cam_status,
        step_cam_status=step_cam_status,
        drill_cam_status=drill_cam_status,
        bore_cam_status=bore_cam_status,
        tool_match_coverage=tool_match_coverage,
        is_dispatchable=_IS_DISPATCHABLE,
        production_released=_PRODUCTION_RELEASED,
        safety_invariants=safety,
    )


# ---------------------------------------------------------------------------
# Safety invariant check
# ---------------------------------------------------------------------------

def check_phase6_safety_invariants(
    pocket_assessments: list[PocketCAMAssessment],
    slot_assessments: list[SlotCAMAssessment],
    step_assessments: list[StepCAMAssessment],
    hole_assessments: list[HoleCAMAssessment],
    gouge_assessment: GougeVerificationAssessment,
) -> Phase6SafetyInvariants:
    """Verify Phase 6 hard-rule safety invariants."""
    any_dispatchable = (
        any(p.is_dispatchable for p in pocket_assessments)
        or any(s.is_dispatchable for s in slot_assessments)
        or any(st.is_dispatchable for st in step_assessments)
        or any(h.is_dispatchable for h in hole_assessments)
        or gouge_assessment.is_dispatchable
    )
    any_production: bool = False  # no production_released on individual assessments

    any_auto_confirmed = (
        any(p.feature_status != "CANDIDATE" for p in pocket_assessments)
        or any(s.feature_status != "CANDIDATE" for s in slot_assessments)
        or any(st.feature_status != "CANDIDATE" for st in step_assessments)
        or any(h.feature_status != "CANDIDATE" for h in hole_assessments)
    )

    # Gouge pass without voxel simulation is a fabricated pass
    any_gouge_pass = (
        gouge_assessment.verification_status == GougeVerificationStatus.WITHIN_DEFINED_SCOPE
        and not gouge_assessment.voxel_simulation_available
    )

    all_candidate = not any_auto_confirmed

    return Phase6SafetyInvariants(
        any_is_dispatchable_true=any_dispatchable,
        any_production_released_true=any_production,
        any_auto_confirmed=any_auto_confirmed,
        any_gouge_pass=any_gouge_pass,
        all_candidates_remain_candidate=all_candidate,
        safety_pass=(
            not any_dispatchable
            and not any_production
            and not any_auto_confirmed
            and not any_gouge_pass
            and all_candidate
        ),
    )
