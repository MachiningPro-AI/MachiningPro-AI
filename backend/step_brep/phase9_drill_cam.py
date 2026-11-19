"""
Phase 9C: Drill cycle assessment with explicit TOOL_CATALOG_GAP reporting.

Extends Phase 7/8 drill infrastructure to separate GEOMETRIC_TOOLPATH_READY
from PARAMETERIZED_CAM_READY (MUST 19).

generate_drill_toolpath does NOT require Vc/fn — it generates positions only
(APPROACH/PLUNGE/RETRACT segments).  Therefore:
  GEOMETRIC_TOOLPATH_READY = wcs_ready AND tool_ready AND depth_ready AND is_axial
  PARAMETERIZED_CAM_READY  = GEOMETRIC_TOOLPATH_READY AND Vc/fn known
                           = always False in Phase 9 (Vc/fn not in catalog scope)

SAFETY RULES (MUST 20–24):
  - BLIND hole depth from B-Rep evidence only; bbox-derived depth used here
    for THROUGH_HOLE_CANDIDATE only (bbox extent = through-depth; acceptable
    for THROUGH holes, NOT for BLIND holes per MUST 22).
  - is_dispatchable=False always.
  - production_released=False always.
  - CNC dispatch never occurs.
  - TOOL_CATALOG_GAP is documented per hole; no silent skip.

HARD INVARIANTS:
  IS_DISPATCHABLE=False
  PRODUCTION_RELEASED=False
  REVIEW_REQUIRED=True
  AUTO_CONFIRMATION=False
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import NamedTuple

from backend.step_brep.phase5_feature_detector import (
    CylinderOrientation,
    OrientedCylinderRecord,
)
from backend.step_brep.phase6_cam_bridge import _select_drill_for_hole
from backend.step_brep.phase7_wcs_provider import WorkCoordinateSystem, wcs_ref_string
from backend.toolpath.generators import (
    ClearanceSource,
    DrillInput,
    generate_drill_toolpath,
)
from backend.toolpath.models import Toolpath, ToolpathStatus

__all__ = [
    "DrillCycleAssessment",
    "DrillCycleResult",
    "assess_drill_cycle",
    "P9C_IS_DISPATCHABLE",
    "P9C_PRODUCTION_RELEASED",
    "P9C_AUTO_CONFIRMATION",
]

P9C_IS_DISPATCHABLE: bool = False
P9C_PRODUCTION_RELEASED: bool = False
P9C_AUTO_CONFIRMATION: bool = False


class _ToolMatch(NamedTuple):
    tool_id: str | None
    match_type: str  # EXACT_MATCH | COMPATIBLE_MATCH | NO_MATCH


@dataclass(frozen=True)
class DrillCycleAssessment:
    """CAM readiness for a single INTERNAL_CYLINDER drill candidate (MUST 19).

    Separates geometric readiness from parameterised CAM readiness:
      geometric_toolpath_ready: wcs + tool + depth + axial — no Vc/fn needed
      parameterized_cam_ready:  would additionally need Vc/fn — always False here

    is_dispatchable=False and production_released=False always.
    """

    feature_id: str
    face_tag: int
    diameter_mm: float
    hole_class: str         # THROUGH_HOLE_CANDIDATE | BLIND_HOLE_CANDIDATE | TRANSITION_RING
    axis_direction: str | None
    depth_mm: float | None
    # Tool
    tool_id: str | None
    tool_match_type: str    # EXACT_MATCH | COMPATIBLE_MATCH | NO_MATCH
    tool_catalog_gap: bool  # True when no matching tool found
    # Readiness dimensions
    wcs_ready: bool
    tool_ready: bool
    depth_ready: bool
    is_axial: bool          # axis_direction == "Z" for SUGGESTED WCS (top-center)
    # MUST 19 separation
    geometric_toolpath_ready: bool   # all geometric conditions: wcs+tool+depth+axial
    parameterized_cam_ready: bool    # always False — Vc/fn not in scope
    # Safety
    is_dispatchable: bool = field(default=P9C_IS_DISPATCHABLE)
    production_released: bool = field(default=P9C_PRODUCTION_RELEASED)
    blocker: str = ""
    toolpath: Toolpath | None = None


@dataclass
class DrillCycleResult:
    """Aggregate Phase 9C drill cycle result for all INTERNAL cylinders in a file."""

    assessments: list[DrillCycleAssessment] = field(default_factory=list)
    is_dispatchable: bool = P9C_IS_DISPATCHABLE
    production_released: bool = P9C_PRODUCTION_RELEASED

    @property
    def total_candidates(self) -> int:
        return len(self.assessments)

    @property
    def tool_matched_count(self) -> int:
        return sum(1 for a in self.assessments if not a.tool_catalog_gap)

    @property
    def tool_catalog_gap_count(self) -> int:
        return sum(1 for a in self.assessments if a.tool_catalog_gap)

    @property
    def geometric_toolpath_ready_count(self) -> int:
        return sum(1 for a in self.assessments if a.geometric_toolpath_ready)

    @property
    def parameterized_cam_ready_count(self) -> int:
        return 0  # always 0 in Phase 9

    @property
    def toolpath_count(self) -> int:
        return sum(1 for a in self.assessments if a.toolpath is not None)

    @property
    def unique_unmatched_diameters_mm(self) -> list[float]:
        seen: set[float] = set()
        result: list[float] = []
        for a in self.assessments:
            if a.tool_catalog_gap and a.diameter_mm not in seen:
                seen.add(a.diameter_mm)
                result.append(a.diameter_mm)
        return sorted(result)


_CLEARANCE_ABOVE_PART_MM: float = 10.0


def assess_drill_cycle(
    cyl: OrientedCylinderRecord,
    wcs: WorkCoordinateSystem | None,
    idx: int = 0,
) -> DrillCycleAssessment:
    """Assess drill cycle readiness for a single INTERNAL_CYLINDER candidate.

    Only INTERNAL_CYLINDER features are drillable (not EXTERNAL or AMBIGUOUS).
    BLIND_HOLE_CANDIDATE depth from bbox is accepted with REVIEW_REQUIRED flag;
    THROUGH_HOLE_CANDIDATE depth from bbox extent equals the through-hole depth.
    WCS top-center assumes Z-axis drilling only; non-Z axis features are BLOCKED.
    """
    feature_id = f"P9C-DRILL-{idx}-F{cyl.face_tag}"

    # Only INTERNAL cylinders are drill candidates
    if cyl.cylinder_orientation != CylinderOrientation.INTERNAL_CYLINDER:
        return DrillCycleAssessment(
            feature_id=feature_id,
            face_tag=cyl.face_tag,
            diameter_mm=cyl.diameter_mm,
            hole_class=cyl.hole_class,
            axis_direction=cyl.axis_direction,
            depth_mm=cyl.depth_mm,
            tool_id=None,
            tool_match_type="NOT_APPLICABLE",
            tool_catalog_gap=True,
            wcs_ready=False,
            tool_ready=False,
            depth_ready=False,
            is_axial=False,
            geometric_toolpath_ready=False,
            parameterized_cam_ready=False,
            blocker=f"NOT_INTERNAL_CYLINDER: orientation={cyl.cylinder_orientation.value}",
        )

    wcs_ready = wcs is not None and wcs.is_valid

    # Tool selection
    tool, match_type = _select_drill_for_hole(cyl.diameter_mm)
    tool_id = tool.stable_id if tool is not None else None
    tool_ready = tool is not None
    tool_catalog_gap = not tool_ready

    # Depth: bbox-derived
    # THROUGH_HOLE: bbox extent = hole depth through part → acceptable
    # BLIND_HOLE: bbox extent overestimates → flag but keep (REVIEW_REQUIRED per MUST 22)
    depth_ready = cyl.depth_mm is not None and cyl.depth_mm > 0.0

    # Axial: SUGGESTED WCS uses world-Z; only Z-axis holes can be drilled without setup rotation
    is_axial = cyl.axis_direction == "Z"

    geometric_toolpath_ready = wcs_ready and tool_ready and depth_ready and is_axial
    parameterized_cam_ready = False  # MUST 19: Vc/fn not in scope

    toolpath: Toolpath | None = None
    blocker: str = ""

    if not wcs_ready:
        blocker = "WCS_READY=NO: wcs is None or invalid"
    elif not is_axial:
        blocker = (
            f"IS_AXIAL=NO: axis_direction={cyl.axis_direction!r} "
            "(Z required for SUGGESTED WCS)"
        )
    elif tool_catalog_gap:
        blocker = (
            f"TOOL_CATALOG_GAP: no drill for diameter={cyl.diameter_mm}mm "
            f"(match_type={match_type})"
        )
    elif not depth_ready:
        blocker = "DEPTH_READY=NO: depth_mm not available"
    else:
        # All geometric conditions met; attempt toolpath generation
        assert wcs is not None  # narrowing
        assert cyl.depth_mm is not None
        hole_x = (cyl.bbox_min[0] + cyl.bbox_max[0]) / 2.0
        hole_y = (cyl.bbox_min[1] + cyl.bbox_max[1]) / 2.0
        hole_top_z = cyl.bbox_max[2]

        clearance_z = (
            wcs.clearance_z_mm
            if wcs.clearance_z_mm is not None
            else hole_top_z + _CLEARANCE_ABOVE_PART_MM
        )
        inp = DrillInput(
            operation_ref=feature_id,
            hole_x=hole_x,
            hole_y=hole_y,
            hole_top_z=hole_top_z,
            hole_depth_mm=cyl.depth_mm,
            axis_vector=(0.0, 0.0, -1.0),
            clearance_z=clearance_z,
            clearance_source=ClearanceSource.PROCESS_STANDARD,
            wcs_ref=wcs_ref_string(wcs),
            tool_ref=tool_id,
            feature_refs=[feature_id],
        )
        try:
            tp = generate_drill_toolpath(inp)
        except Exception as exc:
            blocker = f"TOOLPATH_GENERATION_FAILED: {exc}"
        else:
            if tp.status == ToolpathStatus.BLOCKED:
                blocker = f"TOOLPATH_BLOCKED: {tp.missing_inputs}"
            else:
                toolpath = tp
                blocker = "REVIEW_REQUIRED: geometric drill cycle generated; NOT_DISPATCHABLE"

    return DrillCycleAssessment(
        feature_id=feature_id,
        face_tag=cyl.face_tag,
        diameter_mm=cyl.diameter_mm,
        hole_class=cyl.hole_class,
        axis_direction=cyl.axis_direction,
        depth_mm=cyl.depth_mm,
        tool_id=tool_id,
        tool_match_type=match_type,
        tool_catalog_gap=tool_catalog_gap,
        wcs_ready=wcs_ready,
        tool_ready=tool_ready,
        depth_ready=depth_ready,
        is_axial=is_axial,
        geometric_toolpath_ready=geometric_toolpath_ready,
        parameterized_cam_ready=parameterized_cam_ready,
        toolpath=toolpath,
        blocker=blocker,
    )
