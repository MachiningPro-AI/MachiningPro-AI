"""
Phase 9: E2E CAM assessment extending Phase 8 with:
  - Phase 9B: Multi-face shoulder boundary extraction (phase9_shoulder_cam)
  - Phase 9C: Drill cycle assessment with explicit TOOL_CATALOG_GAP reporting
              and MUST 19 geometric/parameterised separation (phase9_drill_cam)

HARD SAFETY INVARIANTS (never bypassed):
  IS_DISPATCHABLE=False
  PRODUCTION_RELEASED=False
  REAL_MACHINE_WRITE=False
  AUTO_CNC_DISPATCH=False
  AUTO_APPROVAL=False
  AUTOMATIC_ADAPTATION=False
  FEATURE_CONFIRMED: always CANDIDATE (never auto-confirmed)
  WCS_PROVENANCE: always SUGGESTED (never auto-promoted)
  P9B_TOOLPATH_READY=False (FEATURE_CONFIRMED=NO always)
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.interoperability.topology import CanonicalTopology
from backend.step_brep.gmsh_step_parser import StepImportRecord
from backend.step_brep.phase5_feature_detector import (
    CylinderOrientation,
    detect_oriented_cylinders,
    detect_step_shoulder_candidates,
)
from backend.step_brep.phase7_wcs_provider import suggest_wcs_top_center
from backend.step_brep.phase8_arc_sampler import ArcContourMap
from backend.step_brep.phase8_cam_e2e import (
    Phase8E2EResult,
    run_phase8_e2e,
)
from backend.step_brep.phase9_drill_cam import (
    DrillCycleResult,
    assess_drill_cycle,
)
from backend.step_brep.phase9_shoulder_cam import (
    ShoulderCAMResult,
    assess_shoulder_cam,
)

__all__ = [
    "Phase9E2EResult",
    "run_phase9_e2e",
    "PHASE9_IS_DISPATCHABLE",
    "PHASE9_PRODUCTION_RELEASED",
    "PHASE9_REVIEW_REQUIRED",
    "PHASE9_REAL_MACHINE_WRITE",
    "PHASE9_AUTO_CNC_DISPATCH",
    "PHASE9_AUTO_APPROVAL",
    "PHASE9_AUTOMATIC_ADAPTATION",
    "PHASE9_P9B_TOOLPATH_READY",
]

PHASE9_IS_DISPATCHABLE: bool = False
PHASE9_PRODUCTION_RELEASED: bool = False
PHASE9_REVIEW_REQUIRED: bool = True
PHASE9_REAL_MACHINE_WRITE: bool = False
PHASE9_AUTO_CNC_DISPATCH: bool = False
PHASE9_AUTO_APPROVAL: bool = False
PHASE9_AUTOMATIC_ADAPTATION: bool = False
PHASE9_P9B_TOOLPATH_READY: bool = False   # re-exported from phase9_shoulder_cam


@dataclass(frozen=True)
class Phase9E2EResult:
    """Full Phase 9 E2E result for one STEP file.

    Wraps Phase8E2EResult and adds Phase 9B (shoulder CAM) and Phase 9C (drill).

    Safety invariants: all HARD constants are False/True as documented above.
    """

    source_path: str
    # Phase 8 baseline
    p8_result: Phase8E2EResult
    # Phase 9B — multi-face shoulder boundary + CAM assessment
    shoulder_cam: ShoulderCAMResult
    # Phase 9C — drill cycle assessment with TOOL_CATALOG_GAP reporting
    drill_cycle: DrillCycleResult
    # Aggregate metrics
    wcs_ready: bool
    # Phase 8 (inherited)
    p8_pocket_toolpath_count: int
    p8_slot_toolpath_count: int
    p8_step_toolpath_count: int
    p8_drill_toolpath_count: int
    p8_total_toolpath_count: int
    # Phase 9B (all 0 — FEATURE_CONFIRMED gate)
    p9b_shoulder_total: int
    p9b_shoulder_boundary_valid: int
    p9b_shoulder_depth_ready: int
    p9b_shoulder_cam_ready: int
    p9b_shoulder_toolpath_count: int   # always 0
    # Phase 9C
    p9c_drill_total: int
    p9c_drill_tool_matched: int
    p9c_drill_catalog_gap: int
    p9c_drill_geometric_tp_ready: int
    p9c_drill_parameterized_cam_ready: int   # always 0
    p9c_drill_toolpath_count: int
    # Combined total
    total_toolpath_count: int
    any_toolpath_generated: bool
    # Safety invariants
    is_dispatchable: bool
    production_released: bool
    review_required: bool
    real_machine_write: bool
    auto_cnc_dispatch: bool
    auto_approval: bool
    automatic_adaptation: bool


def _run_shoulder_cam(
    record: StepImportRecord,
    topo: CanonicalTopology | None,
) -> ShoulderCAMResult:
    """Run Phase 9B shoulder CAM assessment for all step/shoulder features."""
    result = ShoulderCAMResult()
    if topo is None:
        return result

    shoulders = detect_step_shoulder_candidates(record)
    for i, s in enumerate(shoulders):
        assessment = assess_shoulder_cam(s, topo, idx=i)
        result.assessments.append(assessment)
    return result


def _run_drill_cycle(
    record: StepImportRecord,
) -> DrillCycleResult:
    """Run Phase 9C drill cycle assessment for all INTERNAL_CYLINDER candidates."""
    result = DrillCycleResult()
    wcs = suggest_wcs_top_center(record)
    wcs_obj = wcs if wcs.is_valid else None

    all_cyls = detect_oriented_cylinders(record)
    idx = 0
    for cyl in all_cyls:
        if cyl.cylinder_orientation != CylinderOrientation.INTERNAL_CYLINDER:
            continue
        assessment = assess_drill_cycle(cyl, wcs_obj, idx=idx)
        result.assessments.append(assessment)
        idx += 1
    return result


def run_phase9_e2e(
    record: StepImportRecord,
    topo: CanonicalTopology | None = None,
    arc_map: ArcContourMap | None = None,
) -> Phase9E2EResult:
    """Run full Phase 9 E2E assessment on a parsed STEP record.

    Runs Phase 8 E2E first, then adds Phase 9B (shoulder) and Phase 9C (drill).

    topo: canonical topology built via topology_adapter.
    arc_map: arc-contour map built while gmsh is active.

    Safety invariants:
      is_dispatchable=False, production_released=False, review_required=True,
      real_machine_write=False, auto_cnc_dispatch=False, auto_approval=False,
      automatic_adaptation=False.
    """
    # Phase 8 baseline
    p8 = run_phase8_e2e(record, topo, arc_map)

    # Phase 9B
    shoulder_cam = _run_shoulder_cam(record, topo)

    # Phase 9C
    drill_cycle = _run_drill_cycle(record)

    # Aggregate: Phase 9C is the authoritative drill source.
    # Exclude p8.drill_toolpath_count to avoid double-counting:
    # Phase 8 also runs _assess_drill_p8 and may generate drill TPs for the
    # same holes that Phase 9C processes.  Total = p8 non-drill + p9c drill.
    p8_non_drill_tp = (
        p8.pocket_toolpath_count
        + p8.slot_toolpath_count
        + p8.step_toolpath_count
    )
    total_tp = p8_non_drill_tp + drill_cycle.toolpath_count
    # (shoulder toolpath always 0)

    return Phase9E2EResult(
        source_path=str(record.source_path or ""),
        p8_result=p8,
        shoulder_cam=shoulder_cam,
        drill_cycle=drill_cycle,
        wcs_ready=p8.wcs_ready,
        p8_pocket_toolpath_count=p8.pocket_toolpath_count,
        p8_slot_toolpath_count=p8.slot_toolpath_count,
        p8_step_toolpath_count=p8.step_toolpath_count,
        p8_drill_toolpath_count=p8.drill_toolpath_count,
        p8_total_toolpath_count=p8.total_toolpath_count,
        p9b_shoulder_total=shoulder_cam.total_count,
        p9b_shoulder_boundary_valid=shoulder_cam.boundary_valid_count,
        p9b_shoulder_depth_ready=shoulder_cam.depth_ready_count,
        p9b_shoulder_cam_ready=shoulder_cam.cam_ready_count,
        p9b_shoulder_toolpath_count=0,
        p9c_drill_total=drill_cycle.total_candidates,
        p9c_drill_tool_matched=drill_cycle.tool_matched_count,
        p9c_drill_catalog_gap=drill_cycle.tool_catalog_gap_count,
        p9c_drill_geometric_tp_ready=drill_cycle.geometric_toolpath_ready_count,
        p9c_drill_parameterized_cam_ready=0,
        p9c_drill_toolpath_count=drill_cycle.toolpath_count,
        total_toolpath_count=total_tp,
        any_toolpath_generated=(total_tp > 0),
        is_dispatchable=PHASE9_IS_DISPATCHABLE,
        production_released=PHASE9_PRODUCTION_RELEASED,
        review_required=PHASE9_REVIEW_REQUIRED,
        real_machine_write=PHASE9_REAL_MACHINE_WRITE,
        auto_cnc_dispatch=PHASE9_AUTO_CNC_DISPATCH,
        auto_approval=PHASE9_AUTO_APPROVAL,
        automatic_adaptation=PHASE9_AUTOMATIC_ADAPTATION,
    )
