"""
Phase 7D-7H: End-to-end CAM assessment with WCS + contour + toolpath.

Integrates Phase 7A (WCS), 7C (contour), and existing Phase 6 tool selection
with the actual toolpath generators (pocket, slot, drill).

HARD RULES (never bypassed):
  - is_dispatchable=False always.
  - production_released=False always.
  - review_required=True whenever a toolpath is generated.
  - MUST NOT fabricate feature geometry, WCS, cutting data, or contour.
  - CANDIDATE feature remains CANDIDATE (never auto-confirmed).
  - SUGGESTED_WCS remains SUGGESTED (never auto-confirmed).
  - Stepdown/stepover are derived from tool catalog flute_length_mm and
    cutting_diameter_mm — NOT from material-specific cutting data.
  - Missing tool, unknown WCS, open contour, or ambiguous feature → BLOCKED.

Phase 7B: Re-audit unmatched diameters 2.5, 6.6, 7.0, 9.0 mm.
  Result: no source-backed records found for these diameters.
  TOOL_MATCH_COVERAGE_BEFORE=0/4, AFTER=0/4 (unchanged from Phase 6).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.interoperability.topology import CanonicalTopology
from backend.step_brep.gmsh_step_parser import StepImportRecord
from backend.step_brep.phase5_feature_detector import (
    OrientedCylinderRecord,
    PocketCandidateRecord,  # noqa: F401
    SlotCandidateRecord,  # noqa: F401
    StepShoulderRecord,  # noqa: F401
    detect_oriented_cylinders,
    detect_pocket_candidates,
    detect_slot_candidates,
    detect_step_shoulder_candidates,
    filter_internal_cylinders,
)
from backend.step_brep.phase6_cam_bridge import (
    _select_drill_for_hole,
    _select_end_mill_for_pocket,
    _select_end_mill_for_slot,
)
from backend.step_brep.phase7_contour_extractor import (
    ContourType,
    ManufacturingContour,
    extract_face_outer_contour,
)
from backend.step_brep.phase7_wcs_provider import (
    WorkCoordinateSystem,
    suggest_wcs_top_center,
    wcs_ref_string,
)
from backend.toolpath.generators import (
    ClearanceSource,
    DrillInput,
    PocketInput,
    PocketStrategy,
    SlotInput,
    generate_drill_toolpath,
    generate_pocket_toolpath,
    generate_slot_toolpath,
)
from backend.toolpath.models import Toolpath, ToolpathStatus

__all__ = [
    "FeatureReadinessMatrix",
    "Phase7E2EResult",
    "Phase7B_ToolCatalogAudit",
    "run_phase7_e2e",
    "PHASE7_IS_DISPATCHABLE",
    "PHASE7_PRODUCTION_RELEASED",
    "PHASE7_REVIEW_REQUIRED",
    # Phase 7B
    "PHASE7B_UNMATCHED_DIAMETERS",
    "PHASE7B_TOOL_MATCH_BEFORE",
    "PHASE7B_TOOL_MATCH_AFTER",
]

# Safety invariants — never modified
PHASE7_IS_DISPATCHABLE: bool = False
PHASE7_PRODUCTION_RELEASED: bool = False
PHASE7_REVIEW_REQUIRED: bool = True

# Phase 7B: tool catalog audit constants
PHASE7B_UNMATCHED_DIAMETERS: tuple[float, ...] = (2.5, 6.6, 7.0, 9.0)
PHASE7B_TOOL_MATCH_BEFORE: int = 0
PHASE7B_TOOL_MATCH_AFTER: int = 0

# Stepdown/stepover derivation factors (from tool geometry, not material data)
_STEPDOWN_FACTOR: float = 0.3
_STEPOVER_FACTOR: float = 0.5
_CLEARANCE_ABOVE_PART_MM: float = 10.0


class ReadinessStatus(StrEnum):
    YES = "YES"
    NO = "NO"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class FeatureReadinessMatrix:
    """Per-feature readiness matrix for Phase 7 E2E assessment.

    All fields labeled NO are blockers for toolpath generation.
    toolpath_ready=YES only when ALL mandatory inputs exist.
    is_dispatchable is always False.
    """

    feature_id: str
    feature_type: str
    feature_confirmed: ReadinessStatus
    boundary_ready: ReadinessStatus
    depth_ready: ReadinessStatus
    wcs_ready: ReadinessStatus
    tool_ready: ReadinessStatus
    cutting_data_ready: ReadinessStatus
    cam_strategy_ready: ReadinessStatus
    toolpath_ready: ReadinessStatus
    blocker: str | None
    toolpath: Toolpath | None
    contour: ManufacturingContour | None
    is_dispatchable: bool
    review_required: bool
    notes: str


@dataclass(frozen=True)
class Phase7B_ToolCatalogAudit:
    """Phase 7B: Re-audit result for unmatched diameters."""

    audited_diameters_mm: tuple[float, ...]
    tool_match_count_before: int
    tool_match_count_after: int
    source_backed_added: int
    notes: str


@dataclass(frozen=True)
class Phase7E2EResult:
    """Full Phase 7 E2E result for one STEP file.

    Safety invariants:
      is_dispatchable=False — no NC may be dispatched from this result.
      production_released=False — no production release.
      review_required=True — all generated toolpaths require review.
    """

    source_path: str
    wcs: WorkCoordinateSystem | None
    tool_catalog_audit: Phase7B_ToolCatalogAudit
    pocket_results: tuple[FeatureReadinessMatrix, ...]
    slot_results: tuple[FeatureReadinessMatrix, ...]
    step_results: tuple[FeatureReadinessMatrix, ...]
    drill_results: tuple[FeatureReadinessMatrix, ...]
    # Aggregated metrics
    wcs_ready: bool
    pocket_toolpath_count: int
    slot_toolpath_count: int
    step_toolpath_count: int
    drill_toolpath_count: int
    total_toolpath_count: int
    any_toolpath_generated: bool
    # Safety invariants
    is_dispatchable: bool
    production_released: bool
    review_required: bool


def _pocket_clearance_z(record: StepImportRecord) -> float:
    return record.bbox_max[2] + _CLEARANCE_ABOVE_PART_MM


def _derive_stepdown(flute_length_mm: float | None, pocket_depth_mm: float) -> float | None:
    if flute_length_mm is None or flute_length_mm <= 0:
        return None
    return round(min(flute_length_mm * _STEPDOWN_FACTOR, pocket_depth_mm), 3)


def _derive_stepover(cutting_diameter_mm: float | None) -> float | None:
    if cutting_diameter_mm is None or cutting_diameter_mm <= 0:
        return None
    return round(cutting_diameter_mm * _STEPOVER_FACTOR, 3)


def _assess_pocket(
    pocket: PocketCandidateRecord,
    topo: CanonicalTopology | None,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> FeatureReadinessMatrix:
    fid = f"P7-POCKET-{idx}"

    # WCS readiness
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    # Tool readiness
    tool = _select_end_mill_for_pocket(pocket.width_mm, pocket.length_mm)
    tool_ready = tool is not None
    tool_status = ReadinessStatus.YES if tool_ready else ReadinessStatus.NO

    # Contour / boundary readiness
    contour: ManufacturingContour | None = None
    boundary_ready = False
    if topo is not None:
        face_norm = (0.0, 0.0, 1.0)
        for f in record.faces:
            if f.tag == pocket.floor_face_tag:
                face_norm = f.normal_at_center
                break
        contour = extract_face_outer_contour(pocket.floor_face_tag, topo, face_norm)
        boundary_ready = (
            contour is not None
            and contour.is_valid
            and len(contour.points_2d) >= 3
            and contour.contour_type == ContourType.OUTER_LOOP
        )
    boundary_status = ReadinessStatus.YES if boundary_ready else ReadinessStatus.NO

    # Depth readiness
    depth_ready = pocket.depth_mm is not None and pocket.depth_mm > 0
    depth_status = ReadinessStatus.YES if depth_ready else ReadinessStatus.NO

    # Cutting data: derived from tool geometry (flute_length, diameter)
    cutting_data_ready = False
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    if tool is not None:
        stepdown_mm = _derive_stepdown(tool.flute_length_mm, pocket.depth_mm or 0.0)
        stepover_mm = _derive_stepover(tool.cutting_diameter_mm)
        cutting_data_ready = stepdown_mm is not None and stepover_mm is not None
    cutting_data_status = ReadinessStatus.YES if cutting_data_ready else ReadinessStatus.NO

    # Strategy: OFFSET for rectangular-ish bounded pockets
    cam_strategy_ready = boundary_ready and tool_ready
    cam_status = ReadinessStatus.YES if cam_strategy_ready else ReadinessStatus.NO

    all_ready = (
        wcs_ready
        and tool_ready
        and boundary_ready
        and depth_ready
        and cutting_data_ready
        and cam_strategy_ready
    )

    tp: Toolpath | None = None
    toolpath_status = ReadinessStatus.NO
    blocker: str | None = None
    notes = ""

    if not wcs_ready:
        blocker = "WCS_READY=NO"
    elif not tool_ready:
        blocker = f"TOOL_READY=NO: no end mill fits width={pocket.width_mm}mm"
    elif not boundary_ready:
        blocker = "BOUNDARY_READY=NO: outer loop extraction failed"
    elif not depth_ready:
        blocker = "DEPTH_READY=NO: depth unknown"
    elif not cutting_data_ready:
        blocker = "CUTTING_DATA_READY=NO: stepdown/stepover derivation failed"

    if all_ready and contour is not None and wcs is not None and tool is not None:
        bbox_z_max = record.bbox_max[2]
        clearance_z = bbox_z_max + _CLEARANCE_ABOVE_PART_MM

        # pocket_top_z: top face of part (where pocket opens)
        pocket_top_z = bbox_z_max

        # pocket_bottom_z: floor face Z level
        pocket_bottom_z = pocket.floor_face_tag and _get_face_z(record, pocket.floor_face_tag)
        if pocket_bottom_z is None:
            # Derive from depth
            pocket_bottom_z = bbox_z_max - pocket.depth_mm

        inp = PocketInput(
            operation_ref=fid,
            boundary_points=list(contour.points_2d),
            pocket_top_z=pocket_top_z,
            pocket_bottom_z=pocket_bottom_z,
            tool_diameter_mm=tool.cutting_diameter_mm,
            stepdown_mm=stepdown_mm,
            stepover_mm=stepover_mm,
            strategy=PocketStrategy.OFFSET,
            clearance_z=clearance_z,
            clearance_source=ClearanceSource.PROCESS_STANDARD,
            setup_ref=None,
            wcs_ref=wcs_ref_string(wcs),
            tool_ref=tool.stable_id,
            feature_refs=[f"face-{pocket.floor_face_tag}"],
        )
        tp = generate_pocket_toolpath(inp)
        if tp.status not in (ToolpathStatus.BLOCKED,):
            toolpath_status = ReadinessStatus.YES
            notes = (
                f"TOOLPATH_CANDIDATE: wcs=SUGGESTED tool={tool.stable_id} "
                f"stepdown={stepdown_mm}mm stepover={stepover_mm}mm "
                f"z_levels derived from depth={pocket.depth_mm}mm. "
                "REVIEW_REQUIRED. NOT_DISPATCHABLE."
            )
        else:
            toolpath_status = ReadinessStatus.NO
            blocker = f"TOOLPATH_BLOCKED: {tp.missing_inputs}"

    return FeatureReadinessMatrix(
        feature_id=fid,
        feature_type="POCKET",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        depth_ready=depth_status,
        wcs_ready=wcs_status,
        tool_ready=tool_status,
        cutting_data_ready=cutting_data_status,
        cam_strategy_ready=cam_status,
        toolpath_ready=toolpath_status,
        blocker=blocker,
        toolpath=tp,
        contour=contour,
        is_dispatchable=False,
        review_required=True,
        notes=notes,
    )


def _get_face_z(record: StepImportRecord, face_tag: int) -> float | None:
    """Return the average Z coordinate of a face from bbox midpoint."""
    for f in record.faces:
        if f.tag == face_tag:
            return (f.bbox_min[2] + f.bbox_max[2]) / 2.0
    return None


def _assess_slot(
    slot: SlotCandidateRecord,
    topo: CanonicalTopology | None,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> FeatureReadinessMatrix:
    fid = f"P7-SLOT-{idx}"
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    tool = _select_end_mill_for_slot(slot.width_mm)
    tool_ready = tool is not None
    tool_status = ReadinessStatus.YES if tool_ready else ReadinessStatus.NO

    # Slot geometry: requires floor face to be horizontal (normal ≈ ±Z)
    floor_face = next((f for f in record.faces if f.tag == slot.floor_face_tag), None)
    is_horizontal = False
    if floor_face is not None:
        nz = abs(floor_face.normal_at_center[2])
        is_horizontal = nz >= 0.95

    boundary_ready = is_horizontal and topo is not None
    boundary_status = ReadinessStatus.YES if boundary_ready else ReadinessStatus.NO

    depth_ready = slot.depth_mm is not None and slot.depth_mm > 0
    depth_status = ReadinessStatus.YES if depth_ready else ReadinessStatus.NO

    cutting_data_ready = False
    if tool is not None:
        stepover = _derive_stepover(tool.cutting_diameter_mm)
        cutting_data_ready = stepover is not None
    cutting_data_status = ReadinessStatus.YES if cutting_data_ready else ReadinessStatus.NO

    cam_strategy_ready = tool_ready and is_horizontal
    cam_status = ReadinessStatus.YES if cam_strategy_ready else ReadinessStatus.NO

    all_ready = (
        wcs_ready
        and tool_ready
        and boundary_ready
        and depth_ready
        and cutting_data_ready
        and cam_strategy_ready
    )

    tp: Toolpath | None = None
    toolpath_status = ReadinessStatus.NO
    blocker: str | None = None
    notes = ""

    if not wcs_ready:
        blocker = "WCS_READY=NO"
    elif not tool_ready:
        blocker = f"TOOL_READY=NO: no end mill fits width={slot.width_mm}mm"
    elif not is_horizontal:
        blocker = (
            "BOUNDARY_READY=NO: slot floor is not horizontal "
            "(non-Z-normal face requires rotated setup confirmation)"
        )
    elif not depth_ready:
        blocker = "DEPTH_READY=NO: depth unknown"

    if all_ready and floor_face is not None and wcs is not None and tool is not None:
        # Slot centerline from floor face bbox
        xmin, ymin, zmin = floor_face.bbox_min
        xmax, ymax, zmax = floor_face.bbox_max
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        # slot_z is the slot OPENING (top), not the floor
        # Derive from part top + slot approach is from above
        slot_z = record.bbox_max[2]
        # Determine slot axis from bbox aspect
        dx = xmax - xmin
        dy = ymax - ymin
        if dx >= dy:
            # Slot runs in X
            start_xy = (xmin, cy)
            end_xy = (xmax, cy)
        else:
            # Slot runs in Y
            start_xy = (cx, ymin)
            end_xy = (cx, ymax)

        clearance_z = record.bbox_max[2] + _CLEARANCE_ABOVE_PART_MM
        inp = SlotInput(
            operation_ref=fid,
            slot_start=start_xy,
            slot_end=end_xy,
            slot_z=slot_z,
            slot_width_mm=slot.width_mm,
            slot_depth_mm=slot.depth_mm,
            tool_diameter_mm=tool.cutting_diameter_mm,
            clearance_z=clearance_z,
            clearance_source=ClearanceSource.PROCESS_STANDARD,
            wcs_ref=wcs_ref_string(wcs),
            tool_ref=tool.stable_id,
            feature_refs=[f"face-{slot.floor_face_tag}"],
        )
        tp = generate_slot_toolpath(inp)
        if tp.status not in (ToolpathStatus.BLOCKED,):
            toolpath_status = ReadinessStatus.YES
            notes = (
                f"TOOLPATH_CANDIDATE: wcs=SUGGESTED tool={tool.stable_id} "
                f"depth={slot.depth_mm}mm. REVIEW_REQUIRED. NOT_DISPATCHABLE."
            )
        else:
            toolpath_status = ReadinessStatus.NO
            blocker = f"TOOLPATH_BLOCKED: {tp.missing_inputs}"

    return FeatureReadinessMatrix(
        feature_id=fid,
        feature_type="SLOT",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        depth_ready=depth_status,
        wcs_ready=wcs_status,
        tool_ready=tool_status,
        cutting_data_ready=cutting_data_status,
        cam_strategy_ready=cam_status,
        toolpath_ready=toolpath_status,
        blocker=blocker,
        toolpath=tp,
        contour=None,
        is_dispatchable=False,
        review_required=True,
        notes=notes,
    )


def _assess_step(
    step: StepShoulderRecord,
    topo: CanonicalTopology | None,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> FeatureReadinessMatrix:
    fid = f"P7-STEP-{idx}"
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    # Step shoulder: needs contour from wall or floor face
    # Phase 7F: contour extraction for step shoulder → defer to Phase 8
    return FeatureReadinessMatrix(
        feature_id=fid,
        feature_type="STEP_SHOULDER",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=ReadinessStatus.NO,
        depth_ready=ReadinessStatus.NO,
        wcs_ready=wcs_status,
        tool_ready=ReadinessStatus.NO,
        cutting_data_ready=ReadinessStatus.NO,
        cam_strategy_ready=ReadinessStatus.NO,
        toolpath_ready=ReadinessStatus.NO,
        blocker="BOUNDARY_READY=NO: step/shoulder contour extraction deferred to Phase 8",
        toolpath=None,
        contour=None,
        is_dispatchable=False,
        review_required=True,
        notes="Step/shoulder profile toolpath requires Phase 8 contour extraction.",
    )


def _assess_drill(
    cyl: OrientedCylinderRecord,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> FeatureReadinessMatrix:
    fid = f"P7-DRILL-{idx}"
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    tool, strategy = _select_drill_for_hole(cyl.diameter_mm)
    tool_ready = tool is not None
    tool_status = ReadinessStatus.YES if tool_ready else ReadinessStatus.NO

    # Drill geometry: hole center from face bbox
    face = next((f for f in record.faces if f.tag == cyl.face_tag), None)
    depth_ready = cyl.depth_mm is not None and cyl.depth_mm > 0
    depth_status = ReadinessStatus.YES if depth_ready else ReadinessStatus.NO

    # Hole axis must align with WCS Z for top-down drilling
    # axis_direction is a str like "Z", "X", "Y" from Phase 5
    is_axial = cyl.axis_direction == "Z"
    boundary_status = ReadinessStatus.YES if is_axial else ReadinessStatus.NO

    cutting_data_ready = tool_ready and depth_ready and is_axial
    cutting_data_status = ReadinessStatus.YES if cutting_data_ready else ReadinessStatus.NO

    cam_strategy_ready = tool_ready and is_axial
    cam_status = ReadinessStatus.YES if cam_strategy_ready else ReadinessStatus.NO

    all_ready = wcs_ready and tool_ready and is_axial and depth_ready

    tp: Toolpath | None = None
    toolpath_status = ReadinessStatus.NO
    blocker: str | None = None
    notes = ""

    if not wcs_ready:
        blocker = "WCS_READY=NO"
    elif not tool_ready:
        blocker = f"TOOL_READY=NO: no drill matches diameter={cyl.diameter_mm}mm"
    elif not is_axial:
        blocker = "BOUNDARY_READY=NO: hole axis not aligned with WCS Z (non-axial hole)"
    elif not depth_ready:
        blocker = "DEPTH_READY=NO: hole depth unknown"

    if all_ready and face is not None and wcs is not None and tool is not None:
        hole_cx = (face.bbox_min[0] + face.bbox_max[0]) / 2.0
        hole_cy = (face.bbox_min[1] + face.bbox_max[1]) / 2.0
        hole_top_z = face.bbox_max[2]
        clearance_z = record.bbox_max[2] + _CLEARANCE_ABOVE_PART_MM

        inp = DrillInput(
            operation_ref=fid,
            hole_x=hole_cx,
            hole_y=hole_cy,
            hole_top_z=hole_top_z,
            hole_depth_mm=cyl.depth_mm,
            axis_vector=(0.0, 0.0, -1.0),
            clearance_z=clearance_z,
            clearance_source=ClearanceSource.PROCESS_STANDARD,
            setup_ref=None,
            wcs_ref=wcs_ref_string(wcs),
            tool_ref=tool.stable_id,
            feature_refs=[f"face-{cyl.face_tag}"],
        )
        tp = generate_drill_toolpath(inp)
        if tp.status not in (ToolpathStatus.BLOCKED,):
            toolpath_status = ReadinessStatus.YES
            notes = (
                f"TOOLPATH_CANDIDATE: wcs=SUGGESTED tool={tool.stable_id} "
                f"depth={cyl.depth_mm}mm. REVIEW_REQUIRED. NOT_DISPATCHABLE."
            )
        else:
            toolpath_status = ReadinessStatus.NO
            blocker = f"TOOLPATH_BLOCKED: {tp.missing_inputs}"

    return FeatureReadinessMatrix(
        feature_id=fid,
        feature_type="DRILL",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        depth_ready=depth_status,
        wcs_ready=wcs_status,
        tool_ready=tool_status,
        cutting_data_ready=cutting_data_status,
        cam_strategy_ready=cam_status,
        toolpath_ready=toolpath_status,
        blocker=blocker,
        toolpath=tp,
        contour=None,
        is_dispatchable=False,
        review_required=True,
        notes=notes,
    )


def run_phase7_e2e(
    record: StepImportRecord,
    topo: CanonicalTopology | None = None,
) -> Phase7E2EResult:
    """Run full Phase 7 E2E assessment on a parsed STEP record.

    topo must be built externally (via topology_adapter.build_canonical_topology)
    after gmsh initialization. If None, boundary extraction is skipped and
    all BOUNDARY_READY flags will be NO.

    Safety invariants:
      is_dispatchable=False, production_released=False, review_required=True
    """
    # Phase 7A: suggest WCS from bbox
    wcs = suggest_wcs_top_center(record)
    wcs_ready = wcs.is_valid

    # Phase 7B: tool catalog audit (no new records found)
    tool_audit = Phase7B_ToolCatalogAudit(
        audited_diameters_mm=PHASE7B_UNMATCHED_DIAMETERS,
        tool_match_count_before=PHASE7B_TOOL_MATCH_BEFORE,
        tool_match_count_after=PHASE7B_TOOL_MATCH_AFTER,
        source_backed_added=0,
        notes=(
            "Re-audit of unmatched diameters (2.5, 6.6, 7.0, 9.0 mm): "
            "no source-backed catalog records found. "
            "TOOL_MATCH_COVERAGE unchanged from Phase 6."
        ),
    )

    # Phase 7D: Pockets
    pockets = detect_pocket_candidates(record)
    pocket_results = tuple(
        _assess_pocket(p, topo, wcs, record, i)
        for i, p in enumerate(pockets)
    )

    # Phase 7E: Slots
    slots = detect_slot_candidates(record)
    slot_results = tuple(
        _assess_slot(s, topo, wcs, record, i)
        for i, s in enumerate(slots)
    )

    # Phase 7F: Steps (deferred — contour extraction for shoulder profiles)
    steps = detect_step_shoulder_candidates(record)
    step_results = tuple(
        _assess_step(s, topo, wcs, record, i)
        for i, s in enumerate(steps)
    )

    # Phase 7G: Drills
    all_cyls = detect_oriented_cylinders(record)
    internal_cyls = filter_internal_cylinders(all_cyls)
    drill_results = tuple(
        _assess_drill(c, wcs, record, i)
        for i, c in enumerate(internal_cyls)
    )

    pocket_tp = sum(1 for r in pocket_results if r.toolpath_ready == ReadinessStatus.YES)
    slot_tp = sum(1 for r in slot_results if r.toolpath_ready == ReadinessStatus.YES)
    step_tp = sum(1 for r in step_results if r.toolpath_ready == ReadinessStatus.YES)
    drill_tp = sum(1 for r in drill_results if r.toolpath_ready == ReadinessStatus.YES)
    total_tp = pocket_tp + slot_tp + step_tp + drill_tp

    return Phase7E2EResult(
        source_path=str(record.source_path or ""),
        wcs=wcs,
        tool_catalog_audit=tool_audit,
        pocket_results=pocket_results,
        slot_results=slot_results,
        step_results=step_results,
        drill_results=drill_results,
        wcs_ready=wcs_ready,
        pocket_toolpath_count=pocket_tp,
        slot_toolpath_count=slot_tp,
        step_toolpath_count=step_tp,
        drill_toolpath_count=drill_tp,
        total_toolpath_count=total_tp,
        any_toolpath_generated=total_tp > 0,
        is_dispatchable=False,
        production_released=False,
        review_required=True,
    )
