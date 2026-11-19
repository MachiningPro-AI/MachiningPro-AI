"""
Phase 8: Extended E2E CAM assessment with Phase 8 improvements.

Extends Phase 7 E2E with:
  - Circular outer-loop extraction (topology_adapter Fix 1 — planar circular faces)
  - 2-arc closed-face support (arc_contour_map — BOUNDARY_METHOD=APPROXIMATED)
  - BoundaryTraversalStatus classification for all features
  - Step/shoulder boundary extraction via Phase 8 step shoulder module
  - Disconnected boundary detection (PM face 117 — stays BLOCKED)

Phase 8 improvement summary over Phase 7:
  - pocket outer-loop extraction: FB (face 7) and SK (face 3) may succeed
    after topology_adapter Fix 1 (circular OUTER loops).
  - PM face 109 (2-arc pocket): may succeed via arc_contour_map.
  - PM face 117: DISCONNECTED boundary → BLOCKED correctly.
  - Step/shoulder: BOUNDARY_READY may be YES for some faces, but
    TOOLPATH_READY remains NO (FEATURE_CONFIRMED=NO always).

HARD SAFETY INVARIANTS (never bypassed):
  IS_DISPATCHABLE=False
  PRODUCTION_RELEASED=False
  REAL_MACHINE_WRITE=False
  AUTO_CNC_DISPATCH=False
  AUTO_APPROVAL=False
  AUTOMATIC_ADAPTATION=False
  FEATURE_CONFIRMED: always CANDIDATE (never auto-confirmed)
  WCS_PROVENANCE: always SUGGESTED (never auto-promoted)
  BOUNDARY_METHOD=APPROXIMATED: flagged, never silently exact
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
from backend.step_brep.phase7_cam_e2e import (
    _CLEARANCE_ABOVE_PART_MM,
    _derive_stepdown,
    _derive_stepover,
    _get_face_z,
)
from backend.step_brep.phase7_contour_extractor import (
    ContourType,
    ManufacturingContour,
)
from backend.step_brep.phase7_wcs_provider import (
    WorkCoordinateSystem,
    suggest_wcs_top_center,
    wcs_ref_string,
)
from backend.step_brep.phase8_arc_sampler import ArcContourMap
from backend.step_brep.phase8_contour_extractor import (
    BoundaryTraversalStatus,
    Phase8Contour,
    extract_face_contour_p8,
)
from backend.step_brep.phase8_step_shoulder_boundary import (
    StepShoulderBoundary,
    StepShoulderBoundaryResult,
    extract_step_shoulder_boundary,
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
    "Phase8FeatureMatrix",
    "Phase8E2EResult",
    "run_phase8_e2e",
    "PHASE8_IS_DISPATCHABLE",
    "PHASE8_PRODUCTION_RELEASED",
    "PHASE8_REVIEW_REQUIRED",
    "PHASE8_REAL_MACHINE_WRITE",
    "PHASE8_AUTO_CNC_DISPATCH",
    "PHASE8_AUTO_APPROVAL",
    "PHASE8_AUTOMATIC_ADAPTATION",
]

PHASE8_IS_DISPATCHABLE: bool = False
PHASE8_PRODUCTION_RELEASED: bool = False
PHASE8_REVIEW_REQUIRED: bool = True
PHASE8_REAL_MACHINE_WRITE: bool = False
PHASE8_AUTO_CNC_DISPATCH: bool = False
PHASE8_AUTO_APPROVAL: bool = False
PHASE8_AUTOMATIC_ADAPTATION: bool = False


class ReadinessStatus(StrEnum):
    YES = "YES"
    NO = "NO"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass(frozen=True)
class Phase8FeatureMatrix:
    """Per-feature readiness matrix with Phase 8 boundary traversal info.

    boundary_method: 'EXACT' or 'APPROXIMATED' — always set when boundary_ready=YES.
    traversal_status: BoundaryTraversalStatus value for the extracted boundary.
    is_dispatchable: always False.
    """

    feature_id: str
    feature_type: str
    feature_confirmed: ReadinessStatus
    boundary_ready: ReadinessStatus
    boundary_method: str | None
    traversal_status: BoundaryTraversalStatus | None
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
class Phase8E2EResult:
    """Full Phase 8 E2E result for one STEP file.

    Extends Phase 7 result with arc_map support and step/shoulder boundaries.

    Safety invariants: all HARD constants are False/True as documented above.
    arc_map_faces_used: face tags for which arc_map was used (APPROXIMATED).
    """

    source_path: str
    wcs: WorkCoordinateSystem | None
    pocket_results: tuple[Phase8FeatureMatrix, ...]
    slot_results: tuple[Phase8FeatureMatrix, ...]
    step_results: tuple[Phase8FeatureMatrix, ...]
    step_shoulder_boundaries: StepShoulderBoundaryResult
    drill_results: tuple[Phase8FeatureMatrix, ...]
    # Aggregated metrics
    wcs_ready: bool
    pocket_toolpath_count: int
    slot_toolpath_count: int
    step_toolpath_count: int
    drill_toolpath_count: int
    total_toolpath_count: int
    any_toolpath_generated: bool
    # Phase 8 specific
    arc_map_faces_used: tuple[int, ...]
    step_boundary_ready_count: int
    # Safety invariants
    is_dispatchable: bool
    production_released: bool
    review_required: bool
    real_machine_write: bool
    auto_cnc_dispatch: bool
    auto_approval: bool
    automatic_adaptation: bool


def _assess_pocket_p8(
    pocket: PocketCandidateRecord,
    topo: CanonicalTopology | None,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
    arc_map: ArcContourMap | None = None,
) -> tuple[Phase8FeatureMatrix, bool]:
    """Assess a pocket candidate with Phase 8 contour extraction.

    Returns (matrix, arc_map_used) where arc_map_used=True if boundary
    was extracted via arc_map (APPROXIMATED).
    """
    fid = f"P8-POCKET-{idx}"
    arc_map_used = False

    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    tool = _select_end_mill_for_pocket(pocket.width_mm, pocket.length_mm)
    tool_ready = tool is not None
    tool_status = ReadinessStatus.YES if tool_ready else ReadinessStatus.NO

    # Phase 8 contour extraction
    p8c: Phase8Contour | None = None
    contour: ManufacturingContour | None = None
    boundary_ready = False
    boundary_method: str | None = None
    traversal_status: BoundaryTraversalStatus | None = None

    if topo is not None:
        face_norm = (0.0, 0.0, 1.0)
        for f in record.faces:
            if f.tag == pocket.floor_face_tag:
                face_norm = f.normal_at_center
                break
        p8c = extract_face_contour_p8(
            face_tag=pocket.floor_face_tag,
            topo=topo,
            arc_map=arc_map,
            face_normal=face_norm,
        )
        if p8c is not None:
            contour = p8c.contour
            traversal_status = p8c.traversal_status
            boundary_method = p8c.boundary_method
            if p8c.boundary_method == "APPROXIMATED":
                arc_map_used = True
            boundary_ready = (
                p8c.traversal_status == BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP
                and contour.is_valid
                and len(contour.points_2d) >= 3
                and contour.contour_type == ContourType.OUTER_LOOP
            )

    boundary_status = ReadinessStatus.YES if boundary_ready else ReadinessStatus.NO

    depth_ready = pocket.depth_mm is not None and pocket.depth_mm > 0
    depth_status = ReadinessStatus.YES if depth_ready else ReadinessStatus.NO

    cutting_data_ready = False
    stepdown_mm: float | None = None
    stepover_mm: float | None = None
    if tool is not None:
        stepdown_mm = _derive_stepdown(tool.flute_length_mm, pocket.depth_mm or 0.0)
        stepover_mm = _derive_stepover(tool.cutting_diameter_mm)
        cutting_data_ready = stepdown_mm is not None and stepover_mm is not None
    cutting_data_status = ReadinessStatus.YES if cutting_data_ready else ReadinessStatus.NO

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
        trav = traversal_status.value if traversal_status else "NOT_EXTRACTED"
        blocker = f"BOUNDARY_READY=NO: traversal_status={trav}"
    elif not depth_ready:
        blocker = "DEPTH_READY=NO: depth unknown"
    elif not cutting_data_ready:
        blocker = "CUTTING_DATA_READY=NO: stepdown/stepover derivation failed"

    if all_ready and contour is not None and wcs is not None and tool is not None:
        bbox_z_max = record.bbox_max[2]
        clearance_z = bbox_z_max + _CLEARANCE_ABOVE_PART_MM
        pocket_top_z = bbox_z_max
        pocket_bottom_z = _get_face_z(record, pocket.floor_face_tag)
        if pocket_bottom_z is None:
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
        bm_note = f" boundary_method={boundary_method}" if boundary_method else ""
        if tp.status not in (ToolpathStatus.BLOCKED,):
            toolpath_status = ReadinessStatus.YES
            notes = (
                f"TOOLPATH_CANDIDATE: wcs=SUGGESTED tool={tool.stable_id} "
                f"stepdown={stepdown_mm}mm stepover={stepover_mm}mm{bm_note}. "
                "REVIEW_REQUIRED. NOT_DISPATCHABLE."
            )
        else:
            toolpath_status = ReadinessStatus.NO
            blocker = f"TOOLPATH_BLOCKED: {tp.missing_inputs}"

    return Phase8FeatureMatrix(
        feature_id=fid,
        feature_type="POCKET",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        boundary_method=boundary_method,
        traversal_status=traversal_status,
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
    ), arc_map_used


def _assess_slot_p8(
    slot: SlotCandidateRecord,
    topo: CanonicalTopology | None,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> Phase8FeatureMatrix:
    """Assess a slot candidate — same as Phase 7 (slot contour unchanged)."""
    fid = f"P8-SLOT-{idx}"
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    tool = _select_end_mill_for_slot(slot.width_mm)
    tool_ready = tool is not None
    tool_status = ReadinessStatus.YES if tool_ready else ReadinessStatus.NO

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
        xmin, ymin, zmin = floor_face.bbox_min
        xmax, ymax, zmax = floor_face.bbox_max
        cx = (xmin + xmax) / 2.0
        cy = (ymin + ymax) / 2.0
        slot_z = record.bbox_max[2]
        dx = xmax - xmin
        dy = ymax - ymin
        if dx >= dy:
            start_xy = (xmin, cy)
            end_xy = (xmax, cy)
        else:
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

    return Phase8FeatureMatrix(
        feature_id=fid,
        feature_type="SLOT",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        boundary_method="EXACT" if boundary_ready else None,
        traversal_status=BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP if boundary_ready else None,
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


def _assess_step_p8(
    step: StepShoulderRecord,
    boundary: StepShoulderBoundary,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> Phase8FeatureMatrix:
    """Assess a step/shoulder candidate with Phase 8 boundary extraction.

    TOOLPATH_READY=NO always: FEATURE_CONFIRMED is never auto-set.
    """
    fid = f"P8-STEP-{idx}"
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    boundary_ready = boundary.boundary_ready
    boundary_status = ReadinessStatus.YES if boundary_ready else ReadinessStatus.NO

    return Phase8FeatureMatrix(
        feature_id=fid,
        feature_type="STEP_SHOULDER",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        boundary_method=boundary.boundary_method,
        traversal_status=boundary.traversal_status,
        depth_ready=ReadinessStatus.NO,
        wcs_ready=wcs_status,
        tool_ready=ReadinessStatus.NO,
        cutting_data_ready=ReadinessStatus.NO,
        cam_strategy_ready=ReadinessStatus.NO,
        toolpath_ready=ReadinessStatus.NO,
        blocker=boundary.blocker,
        toolpath=None,
        contour=boundary.contour.contour if boundary.contour else None,
        is_dispatchable=False,
        review_required=True,
        notes=(
            "Step/shoulder BOUNDARY_READY improved in Phase 8. "
            "TOOLPATH_READY=NO: requires FEATURE_CONFIRMED=YES (never auto-confirmed)."
        ),
    )


def _assess_drill_p8(
    cyl: OrientedCylinderRecord,
    wcs: WorkCoordinateSystem | None,
    record: StepImportRecord,
    idx: int,
) -> Phase8FeatureMatrix:
    """Assess a drill candidate — same as Phase 7 (no new drill catalog records)."""
    fid = f"P8-DRILL-{idx}"
    wcs_ready = wcs is not None and wcs.is_valid
    wcs_status = ReadinessStatus.YES if wcs_ready else ReadinessStatus.NO

    tool, strategy = _select_drill_for_hole(cyl.diameter_mm)
    tool_ready = tool is not None
    tool_status = ReadinessStatus.YES if tool_ready else ReadinessStatus.NO

    face = next((f for f in record.faces if f.tag == cyl.face_tag), None)
    depth_ready = cyl.depth_mm is not None and cyl.depth_mm > 0
    depth_status = ReadinessStatus.YES if depth_ready else ReadinessStatus.NO

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

    return Phase8FeatureMatrix(
        feature_id=fid,
        feature_type="DRILL",
        feature_confirmed=ReadinessStatus.NO,
        boundary_ready=boundary_status,
        boundary_method="EXACT" if is_axial else None,
        traversal_status=BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP if is_axial else None,
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


def run_phase8_e2e(
    record: StepImportRecord,
    topo: CanonicalTopology | None = None,
    arc_map: ArcContourMap | None = None,
) -> Phase8E2EResult:
    """Run full Phase 8 E2E assessment on a parsed STEP record.

    topo: canonical topology built via topology_adapter (after gmsh Fix 1).
    arc_map: arc-contour map built via build_arc_contour_map() while gmsh active.

    Both are optional — absent means boundary extraction is limited.

    Safety invariants:
      is_dispatchable=False, production_released=False, review_required=True,
      real_machine_write=False, auto_cnc_dispatch=False, auto_approval=False,
      automatic_adaptation=False.
    """
    wcs = suggest_wcs_top_center(record)
    wcs_ready = wcs.is_valid

    # Pockets
    arc_faces_used: list[int] = []
    pockets = detect_pocket_candidates(record)
    pocket_results_list: list[Phase8FeatureMatrix] = []
    for i, p in enumerate(pockets):
        m, used = _assess_pocket_p8(p, topo, wcs, record, i, arc_map)
        pocket_results_list.append(m)
        if used:
            arc_faces_used.append(p.floor_face_tag)
    pocket_results = tuple(pocket_results_list)

    # Slots (same as Phase 7)
    slots = detect_slot_candidates(record)
    slot_results = tuple(
        _assess_slot_p8(s, topo, wcs, record, i)
        for i, s in enumerate(slots)
    )

    # Steps (Phase 8: attempt boundary extraction)
    steps = detect_step_shoulder_candidates(record)
    ssb_result = StepShoulderBoundaryResult()
    step_matrices: list[Phase8FeatureMatrix] = []
    for i, s in enumerate(steps):
        boundary = extract_step_shoulder_boundary(s, topo or CanonicalTopology(
            topology_id="empty", faces=(), loops=(), edges=(), vertices=(),
        ), arc_map, step_index=i)
        ssb_result.step_boundaries.append(boundary)
        step_matrices.append(_assess_step_p8(s, boundary, wcs, record, i))
    step_results = tuple(step_matrices)

    # Drills (same as Phase 7 — no new catalog records)
    all_cyls = detect_oriented_cylinders(record)
    internal_cyls = filter_internal_cylinders(all_cyls)
    drill_results = tuple(
        _assess_drill_p8(c, wcs, record, i)
        for i, c in enumerate(internal_cyls)
    )

    pocket_tp = sum(1 for r in pocket_results if r.toolpath_ready == ReadinessStatus.YES)
    slot_tp = sum(1 for r in slot_results if r.toolpath_ready == ReadinessStatus.YES)
    step_tp = sum(1 for r in step_results if r.toolpath_ready == ReadinessStatus.YES)
    drill_tp = sum(1 for r in drill_results if r.toolpath_ready == ReadinessStatus.YES)
    total_tp = pocket_tp + slot_tp + step_tp + drill_tp

    return Phase8E2EResult(
        source_path=str(record.source_path or ""),
        wcs=wcs,
        pocket_results=pocket_results,
        slot_results=slot_results,
        step_results=step_results,
        step_shoulder_boundaries=ssb_result,
        drill_results=drill_results,
        wcs_ready=wcs_ready,
        pocket_toolpath_count=pocket_tp,
        slot_toolpath_count=slot_tp,
        step_toolpath_count=step_tp,
        drill_toolpath_count=drill_tp,
        total_toolpath_count=total_tp,
        any_toolpath_generated=total_tp > 0,
        arc_map_faces_used=tuple(arc_faces_used),
        step_boundary_ready_count=ssb_result.boundary_ready_count,
        is_dispatchable=False,
        production_released=False,
        review_required=True,
        real_machine_write=False,
        auto_cnc_dispatch=False,
        auto_approval=False,
        automatic_adaptation=False,
    )
