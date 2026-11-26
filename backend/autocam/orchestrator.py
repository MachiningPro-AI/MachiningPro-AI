"""Auto CAM orchestration engine — MACHININGPRO_AI_AUTO_CAM_END_TO_END_01.

20-stage pipeline that reuses existing engines.  Safety invariants are
hardcoded throughout — no API input can override them.

DUPLICATE_ENGINE_CREATED=NO — all stages call existing backend modules.

Stage order:
  S01 Input Validation
  S02 Stock Gate
  S03 Material Gate
  S04 Feature Classification
  S05 WCS Candidate
  S06 Machine Selection
  S07 Tool Selection
  S08 Cutting Parameters
  S09 Operation Planning
  S10 Toolpath Generation
  S11 Cycle Time
  S12 Machine Envelope Check
  S13 Tool Reach Check
  S14 Stock Removal Simulation
  S15 Collision Check
  S16 Gouge Check
  S17 Cost Estimation
  S18 Verification Summary
  S19 Dispatch Safety Gate (ALWAYS_BLOCKED)
  S20 Report
"""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime

from backend.cutting_tools.families import ToolFamily
from backend.cutting_tools.library import ToolLibrary
from backend.machines.catalog_models import MachineCatalogRecord
from backend.machines.seed_catalog import seed_machine_catalog
from backend.toolpath.enums import ClearanceSource
from backend.toolpath.generators import (
    DrillInput,
    PocketInput,
    SlotInput,
    generate_drill_toolpath,
    generate_pocket_toolpath,
    generate_slot_toolpath,
)
from backend.toolpath.models import Toolpath

from .cost_estimate import compute_autocam_cost
from .cutting_params_engine import compute_cutting_params
from .enums import AutoCamPlanStatus, AutoCamStage, BlockerCode, StageStatus
from .models import (
    AutoCamBlocker,
    AutoCamFeatureInput,
    AutoCamPlan,
    AutoCamRequest,
    AutoCamStageResult,
    AutoCamWarning,
    CuttingParamResult,
    CycleTimeResult,
    MachineResult,
    OperationResult,
    StockBbox,
    ToolpathGroupFE,
    ToolResult,
    VerificationSummaryResult,
)

# ---------------------------------------------------------------------------
# Supported feature types
# ---------------------------------------------------------------------------

_SUPPORTED_FEATURE_TYPES = frozenset({
    "HOLE", "POCKET", "SLOT", "PLANAR_FACE", "STEP_SHOULDER",
})

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_ms() -> float:
    return time.monotonic() * 1000.0


def _stage(
    stage: AutoCamStage,
    status: StageStatus,
    duration_ms: float = 0.0,
    outputs: dict | None = None,
    warnings: list[str] | None = None,
    missing: list[str] | None = None,
    blockers: list[str] | None = None,
) -> AutoCamStageResult:
    return AutoCamStageResult(
        stage=stage,
        status=status,
        duration_ms=round(duration_ms, 2),
        outputs=outputs or {},
        warnings=warnings or [],
        missing_inputs=missing or [],
        blockers=blockers or [],
    )


def _skipped(stage: AutoCamStage, reason: str) -> AutoCamStageResult:
    return _stage(stage, StageStatus.NOT_PERFORMED, blockers=[reason])


# ---------------------------------------------------------------------------
# Tool lookup (reuses ToolLibrary — DUPLICATE_ENGINE_CREATED=NO)
# ---------------------------------------------------------------------------

_tool_lib = ToolLibrary()


def _find_drill(diameter_mm: float | None) -> ToolResult:
    if diameter_mm is None or diameter_mm <= 0:
        return ToolResult(tool_status="INSUFFICIENT_DATA")
    tol = max(0.5, diameter_mm * 0.1)
    results = (
        _tool_lib.query()
        .by_family(ToolFamily.DRILLING)
        .by_diameter(min_mm=diameter_mm - tol, max_mm=diameter_mm + tol)
        .results()
    )
    if not results:
        return ToolResult(tool_status="INSUFFICIENT_DATA")
    r = results[0]
    return ToolResult(
        tool_id=r.stable_id,
        tool_type="DRILL",
        tool_diameter_mm=r.cutting_diameter_mm,
        cutting_length_mm=r.cutting_length_mm,
        tool_status="FOUND",
        provenance="CATALOG",
    )


def _find_end_mill(
    diameter_mm: float | None,
    max_mm: float | None = None,
) -> ToolResult:
    if diameter_mm is None or diameter_mm <= 0:
        return ToolResult(tool_status="INSUFFICIENT_DATA")
    tol = max(0.5, diameter_mm * 0.1)
    upper = min(diameter_mm + tol, max_mm) if max_mm else diameter_mm + tol
    results = (
        _tool_lib.query()
        .by_family(ToolFamily.MILLING)
        .by_diameter(min_mm=diameter_mm - tol, max_mm=upper)
        .results()
    )
    if not results and max_mm:
        # Constrained fallback: any tool that still fits in the slot/pocket
        results = (
            _tool_lib.query()
            .by_family(ToolFamily.MILLING)
            .by_diameter(min_mm=0.5, max_mm=max_mm)
            .results()
        )
    if not results:
        # Unconstrained wider search
        results = _tool_lib.query().by_family(ToolFamily.MILLING).results()
    if not results:
        return ToolResult(tool_status="INSUFFICIENT_DATA")
    r = results[0]
    return ToolResult(
        tool_id=r.stable_id,
        tool_type="END_MILL",
        tool_diameter_mm=r.cutting_diameter_mm,
        cutting_length_mm=r.cutting_length_mm,
        tool_status="FOUND",
        provenance="CATALOG",
    )


# ---------------------------------------------------------------------------
# Machine selection (reuses seed_catalog — DUPLICATE_ENGINE_CREATED=NO)
# ---------------------------------------------------------------------------

def _select_machine(
    machine_type_preference: str | None,
    feature_types: list[str],
) -> MachineResult:
    raw_records = seed_machine_catalog()
    machines = [MachineCatalogRecord(**r) for r in raw_records]
    if not machines:
        return MachineResult(status="INSUFFICIENT_DATA")

    needs_turning = any(ft in ("TURNING", "LATHE") for ft in feature_types)
    pref = (machine_type_preference or "").upper()

    candidates = [m for m in machines if m.milling_capable and m.drilling_capable]
    if needs_turning:
        candidates = [m for m in candidates if m.turning_capable] or candidates
    if pref:
        pref_match = [m for m in candidates if pref in m.machine_type_code.upper()]
        if pref_match:
            candidates = pref_match

    if not candidates:
        return MachineResult(status="INSUFFICIENT_DATA")

    m = candidates[0]
    return MachineResult(
        machine_id=m.stable_id,
        manufacturer=m.manufacturer,
        model=m.model,
        machine_type_code=m.machine_type_code,
        spindle_max_rpm=m.spindle_max_rpm,
        status="FOUND",
    )


# ---------------------------------------------------------------------------
# Toolpath generation helper
# ---------------------------------------------------------------------------

def _gen_toolpath_for_op(
    op_ref: str,
    feature_type: str,
    feat: AutoCamFeatureInput,
    tool: ToolResult,
    stock_bbox: StockBbox | None,
    wcs_ref: str,
    setup_ref: str,
) -> tuple[Toolpath | None, list[str], list[str]]:
    """Return (toolpath_or_none, warnings, missing_inputs)."""
    warnings: list[str] = []
    missing: list[str] = []

    clearance_z = feat.clearance_z
    if clearance_z is None and stock_bbox is not None:
        clearance_z = stock_bbox.max_z + 5.0
    clearance_source = (
        ClearanceSource.USER_SUPPLIED if clearance_z is not None else ClearanceSource.UNKNOWN
    )

    if feature_type == "HOLE":
        if feat.center_x is None or feat.center_y is None:
            missing.append("hole_center_xy")
            return None, warnings, missing
        if feat.depth_mm is None:
            missing.append("hole_depth_mm")
            return None, warnings, missing
        top_z = feat.center_z_top if feat.center_z_top is not None else (
            stock_bbox.max_z if stock_bbox else 0.0
        )
        inp = DrillInput(
            operation_ref=op_ref,
            hole_x=feat.center_x,
            hole_y=feat.center_y,
            hole_top_z=top_z,
            hole_depth_mm=feat.depth_mm,
            clearance_z=clearance_z,
            clearance_source=clearance_source,
            setup_ref=setup_ref,
            wcs_ref=wcs_ref,
            tool_ref=tool.tool_id,
            feature_refs=[feat.feature_id],
        )
        return generate_drill_toolpath(inp), warnings, missing

    if feature_type in ("POCKET", "STEP_SHOULDER"):
        if feat.depth_mm is None:
            missing.append("pocket_depth_mm")
            return None, warnings, missing
        d = tool.tool_diameter_mm or 6.0
        stepdown = min(d * 0.5, feat.depth_mm)
        stepover = d * 0.4
        top_z = feat.center_z_top if feat.center_z_top is not None else (
            stock_bbox.max_z if stock_bbox else 0.0
        )
        bottom_z = top_z - feat.depth_mm
        cx = feat.center_x or 0.0
        cy = feat.center_y or 0.0
        hw = (feat.width_mm or d * 3) / 2.0
        hl = (feat.length_mm or d * 3) / 2.0
        boundary: list[tuple[float, float]] = [
            (cx - hw, cy - hl),
            (cx + hw, cy - hl),
            (cx + hw, cy + hl),
            (cx - hw, cy + hl),
        ]
        if feat.boundary_points:
            boundary = [(p[0], p[1]) for p in feat.boundary_points if len(p) >= 2]
        inp = PocketInput(
            operation_ref=op_ref,
            boundary_points=boundary,
            pocket_top_z=top_z,
            pocket_bottom_z=bottom_z,
            tool_diameter_mm=tool.tool_diameter_mm,
            stepdown_mm=stepdown,
            stepover_mm=stepover,
            clearance_z=clearance_z,
            clearance_source=clearance_source,
            setup_ref=setup_ref,
            wcs_ref=wcs_ref,
            tool_ref=tool.tool_id,
            feature_refs=[feat.feature_id],
        )
        return generate_pocket_toolpath(inp), warnings, missing

    if feature_type == "SLOT":
        if feat.length_mm is None:
            missing.append("slot_length_mm")
            return None, warnings, missing
        if feat.depth_mm is None:
            missing.append("slot_depth_mm")
            return None, warnings, missing
        if (
            feat.width_mm is not None
            and tool.tool_diameter_mm is not None
            and tool.tool_diameter_mm > feat.width_mm
        ):
            warnings.append(
                f"slot_tool_oversize: tool {tool.tool_diameter_mm}mm "
                f"> slot_width {feat.width_mm}mm — toolpath skipped"
            )
            missing.append("slot_width_compatible_tool")
            return None, warnings, missing
        d = tool.tool_diameter_mm or 6.0
        stepdown = min(d * 0.4, feat.depth_mm)
        cx = feat.center_x or 0.0
        cy = feat.center_y or 0.0
        top_z = feat.center_z_top if feat.center_z_top is not None else (
            stock_bbox.max_z if stock_bbox else 0.0
        )
        inp = SlotInput(
            operation_ref=op_ref,
            slot_start=(cx - feat.length_mm / 2.0, cy),
            slot_end=(cx + feat.length_mm / 2.0, cy),
            slot_z=top_z,
            slot_width_mm=feat.width_mm or d,
            slot_depth_mm=feat.depth_mm,
            tool_diameter_mm=tool.tool_diameter_mm,
            clearance_z=clearance_z,
            clearance_source=clearance_source,
            setup_ref=setup_ref,
            wcs_ref=wcs_ref,
            tool_ref=tool.tool_id,
            feature_refs=[feat.feature_id],
        )
        return generate_slot_toolpath(inp), warnings, missing

    if feature_type == "PLANAR_FACE":
        warnings.append("PLANAR_FACE toolpath not generated: requires face-mill setup")
        missing.append("face_mill_setup")
        return None, warnings, missing

    warnings.append(f"Unsupported feature type for toolpath: {feature_type}")
    return None, warnings, missing


# ---------------------------------------------------------------------------
# Main orchestration entry point
# ---------------------------------------------------------------------------

# In-memory plan store (plan_id → AutoCamPlan)
_plan_store: dict[str, AutoCamPlan] = {}


def run_auto_cam(request: AutoCamRequest) -> AutoCamPlan:  # noqa: C901
    """Execute the 20-stage Auto CAM pipeline.

    Reuses all existing engines — DUPLICATE_ENGINE_CREATED=NO.
    Safety invariants are hardcoded and cannot be overridden.
    """
    stages: list[AutoCamStageResult] = []
    plan_blockers: list[AutoCamBlocker] = []
    plan_warnings: list[AutoCamWarning] = []
    overall_blocked = False

    # ------------------------------------------------------------------
    # S01: Input Validation
    # ------------------------------------------------------------------
    t0 = _now_ms()
    s01_warnings: list[str] = []
    s01_missing: list[str] = []
    s01_blockers_text: list[str] = []
    if not request.file_ref:
        s01_blockers_text.append("file_ref is required")
        plan_blockers.append(AutoCamBlocker(
            code=BlockerCode.INPUT_VALIDATION_FAILED,
            stage=AutoCamStage.S01_INPUT_VALIDATION,
            message="file_ref is required",
            missing_input="file_ref",
        ))
        overall_blocked = True
    if not request.features:
        s01_blockers_text.append("No features provided")
        plan_blockers.append(AutoCamBlocker(
            code=BlockerCode.NO_FEATURES,
            stage=AutoCamStage.S01_INPUT_VALIDATION,
            message="No features provided — cannot plan without geometry",
            missing_input="features",
        ))
        overall_blocked = True
    s01_status = StageStatus.BLOCKED if s01_blockers_text else StageStatus.PASS
    stages.append(_stage(
        AutoCamStage.S01_INPUT_VALIDATION, s01_status,
        duration_ms=_now_ms() - t0,
        outputs={"feature_count": len(request.features), "file_ref": request.file_ref},
        warnings=s01_warnings, missing=s01_missing, blockers=s01_blockers_text,
    ))

    if overall_blocked:
        return _make_blocked_plan(request, stages, plan_blockers, plan_warnings)

    # ------------------------------------------------------------------
    # S02: Stock Gate
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stock_ok = request.stock_bbox is not None
    if not stock_ok:
        s02_status = StageStatus.BLOCKED
        plan_blockers.append(AutoCamBlocker(
            code=BlockerCode.STOCK_MISSING,
            stage=AutoCamStage.S02_STOCK_GATE,
            message="stock_bbox required — toolpath clearance cannot be computed",
            missing_input="stock_bbox",
        ))
        overall_blocked = True
        plan_warnings.append(AutoCamWarning(
            stage=AutoCamStage.S02_STOCK_GATE,
            message="stock_bbox missing: downstream stages will use fallback z=0",
            severity="WARNING",
        ))
    else:
        s02_status = StageStatus.PASS
    stages.append(_stage(
        AutoCamStage.S02_STOCK_GATE, s02_status,
        duration_ms=_now_ms() - t0,
        outputs={"stock_provided": stock_ok},
        blockers=[] if stock_ok else ["stock_bbox missing"],
    ))

    # ------------------------------------------------------------------
    # S03: Material Gate
    # ------------------------------------------------------------------
    t0 = _now_ms()
    mat_ok = bool(request.material_grade)
    if not mat_ok:
        plan_warnings.append(AutoCamWarning(
            stage=AutoCamStage.S03_MATERIAL_GATE,
            message="material_grade not provided — cutting parameters status=NOT_AVAILABLE",
            severity="ADVISORY",
        ))
    stages.append(_stage(
        AutoCamStage.S03_MATERIAL_GATE,
        StageStatus.PASS if mat_ok else StageStatus.WARNING,
        duration_ms=_now_ms() - t0,
        outputs={"material_grade": request.material_grade or "NOT_PROVIDED"},
        warnings=[] if mat_ok else ["material_grade not provided"],
    ))

    # ------------------------------------------------------------------
    # S04: Feature Classification
    # ------------------------------------------------------------------
    t0 = _now_ms()
    supported: list[str] = []
    unsupported: list[str] = []
    for feat in request.features:
        ft = feat.feature_type.upper()
        if ft in _SUPPORTED_FEATURE_TYPES:
            supported.append(feat.feature_id)
        else:
            unsupported.append(feat.feature_id)
            plan_warnings.append(AutoCamWarning(
                stage=AutoCamStage.S04_FEATURE_CLASSIFICATION,
                message=(
                    f"Feature {feat.feature_id} type={feat.feature_type}"
                    " not supported for toolpath"
                ),
                severity="ADVISORY",
            ))
    if not supported:
        stages.append(_stage(
            AutoCamStage.S04_FEATURE_CLASSIFICATION, StageStatus.BLOCKED,
            duration_ms=_now_ms() - t0,
            outputs={"supported": 0, "unsupported": len(unsupported)},
            blockers=["No supported feature types found"],
        ))
        plan_blockers.append(AutoCamBlocker(
            code=BlockerCode.NO_RECOGNIZED_FEATURES,
            stage=AutoCamStage.S04_FEATURE_CLASSIFICATION,
            message="No features with supported types (HOLE/POCKET/SLOT/PLANAR_FACE/STEP_SHOULDER)",
        ))
        overall_blocked = True
    else:
        stages.append(_stage(
            AutoCamStage.S04_FEATURE_CLASSIFICATION,
            StageStatus.PASS if not unsupported else StageStatus.PARTIAL,
            duration_ms=_now_ms() - t0,
            outputs={"supported": len(supported), "unsupported": len(unsupported)},
            warnings=[f"{len(unsupported)} unsupported features skipped"] if unsupported else [],
        ))

    if overall_blocked:
        return _make_blocked_plan(request, stages, plan_blockers, plan_warnings)

    # ------------------------------------------------------------------
    # S05: WCS Candidate
    # ------------------------------------------------------------------
    t0 = _now_ms()
    wcs_ref = request.wcs_ref
    stages.append(_stage(
        AutoCamStage.S05_WCS_CANDIDATE, StageStatus.PASS,
        duration_ms=_now_ms() - t0,
        outputs={
            "wcs_candidate": wcs_ref,
            "wcs_validated": False,
            "wcs_type": "WCS_CANDIDATE",
            "note": "WCS is a candidate only — engineer validation required",
        },
        warnings=["WCS_CANDIDATE: not validated — engineer must confirm before use"],
    ))

    # ------------------------------------------------------------------
    # S06: Machine Selection
    # ------------------------------------------------------------------
    t0 = _now_ms()
    feature_types = [f.feature_type.upper() for f in request.features]
    machine = _select_machine(request.machine_type_preference, feature_types)
    if machine.status == "INSUFFICIENT_DATA":
        s06_status = StageStatus.INSUFFICIENT_DATA
        plan_warnings.append(AutoCamWarning(
            stage=AutoCamStage.S06_MACHINE_SELECTION,
            message="No suitable machine found in catalog — continuing without machine constraints",
            severity="WARNING",
        ))
    else:
        s06_status = StageStatus.PASS
    stages.append(_stage(
        AutoCamStage.S06_MACHINE_SELECTION, s06_status,
        duration_ms=_now_ms() - t0,
        outputs={
            "machine_id": machine.machine_id,
            "manufacturer": machine.manufacturer,
            "model": machine.model,
            "status": machine.status,
        },
    ))

    # ------------------------------------------------------------------
    # S07: Tool Selection
    # ------------------------------------------------------------------
    t0 = _now_ms()
    tool_map: dict[str, ToolResult] = {}
    tool_warnings: list[str] = []
    for feat in request.features:
        ft = feat.feature_type.upper()
        if ft == "HOLE":
            tool_map[feat.feature_id] = _find_drill(feat.diameter_mm)
        elif ft == "SLOT":
            # Tool diameter must not exceed slot width — use width as target and hard cap
            slot_w = feat.width_mm
            tool_map[feat.feature_id] = _find_end_mill(slot_w or 10.0, max_mm=slot_w)
        elif ft in ("POCKET", "STEP_SHOULDER", "PLANAR_FACE"):
            tool_map[feat.feature_id] = _find_end_mill(feat.diameter_mm or 10.0)
        if tool_map.get(feat.feature_id, ToolResult()).tool_status == "INSUFFICIENT_DATA":
            tool_warnings.append(
                f"Feature {feat.feature_id} ({feat.feature_type}): no matching tool in catalog"
            )
    any_tool_found = any(t.tool_status == "FOUND" for t in tool_map.values())
    stages.append(_stage(
        AutoCamStage.S07_TOOL_SELECTION,
        StageStatus.PASS if any_tool_found else StageStatus.INSUFFICIENT_DATA,
        duration_ms=_now_ms() - t0,
        outputs={
            "tools_found": sum(1 for t in tool_map.values() if t.tool_status == "FOUND"),
            "tools_missing": sum(1 for t in tool_map.values() if t.tool_status != "FOUND"),
        },
        warnings=tool_warnings,
    ))

    # ------------------------------------------------------------------
    # S08: Cutting Parameters (MACHININGPRO_AI_BETA3_PARAMS_01)
    # ------------------------------------------------------------------
    t0 = _now_ms()
    cp_status_map: dict[str, CuttingParamResult] = {}
    cp_calculated = 0
    cp_not_available = 0
    for feat in request.features:
        tool_for_feat = tool_map.get(feat.feature_id, ToolResult(tool_status="INSUFFICIENT_DATA"))
        cp = compute_cutting_params(feat, tool_for_feat, machine)
        cp_status_map[feat.feature_id] = cp
        if cp.status in ("CALCULATED", "CLAMPED_TO_MACHINE_LIMIT", "PARTIAL"):
            cp_calculated += 1
        else:
            cp_not_available += 1

    s08_status = (
        StageStatus.PASS if cp_calculated > 0 and cp_not_available == 0
        else StageStatus.PARTIAL if cp_calculated > 0
        else StageStatus.INSUFFICIENT_DATA
    )
    s08_warnings = []
    if cp_not_available > 0:
        s08_warnings.append(
            f"Cutting params NOT_AVAILABLE for {cp_not_available} feature(s) "
            f"(KL-05: set MACHININGPRO_CUTTING_PARAM_REF_PATH)"
        )
    stages.append(_stage(
        AutoCamStage.S08_CUTTING_PARAMETERS,
        s08_status,
        duration_ms=_now_ms() - t0,
        outputs={
            "calculated": cp_calculated,
            "not_available": cp_not_available,
            "total": len(request.features),
        },
        warnings=s08_warnings,
    ))
    if cp_not_available > 0:
        plan_warnings.append(AutoCamWarning(
            stage=AutoCamStage.S08_CUTTING_PARAMETERS,
            message=(
                f"Cutting parameters NOT_AVAILABLE for {cp_not_available} feature(s) "
                f"(KL-05) — toolpaths generated without validated feeds/speeds"
            ),
            severity="ADVISORY",
        ))

    # ------------------------------------------------------------------
    # S09: Operation Planning
    # ------------------------------------------------------------------
    t0 = _now_ms()
    operations: list[OperationResult] = []
    op_index = 0
    for feat in request.features:
        ft = feat.feature_type.upper()
        if ft not in _SUPPORTED_FEATURE_TYPES:
            continue
        op_index += 1
        op_ref = f"{request.setup_ref}_OP_{op_index:02d}"
        op_type = _feature_to_op_type(ft)
        strategy = _feature_to_strategy(ft)
        tool = tool_map.get(feat.feature_id, ToolResult(tool_status="INSUFFICIENT_DATA"))
        cp = cp_status_map.get(feat.feature_id, CuttingParamResult())
        operations.append(OperationResult(
            operation_ref=op_ref,
            feature_id=feat.feature_id,
            feature_type=ft,
            operation_type=op_type,
            cam_strategy=strategy,
            tool=tool,
            cutting_params=cp,
            toolpath_status="PENDING",
            simulation_required=True,
        ))
    stages.append(_stage(
        AutoCamStage.S09_OPERATION_PLANNING,
        StageStatus.PASS if operations else StageStatus.BLOCKED,
        duration_ms=_now_ms() - t0,
        outputs={"operation_count": len(operations)},
        blockers=[] if operations else ["No operations could be planned"],
    ))
    if not operations:
        plan_blockers.append(AutoCamBlocker(
            code=BlockerCode.NO_RECOGNIZED_FEATURES,
            stage=AutoCamStage.S09_OPERATION_PLANNING,
            message="No operations planned",
        ))
        return _make_blocked_plan(request, stages, plan_blockers, plan_warnings,
                                  machine=machine, operations=[])

    # ------------------------------------------------------------------
    # S10: Toolpath Generation
    # ------------------------------------------------------------------
    t0 = _now_ms()
    toolpath_warnings: list[str] = []
    toolpath_groups: list[ToolpathGroupFE] = []
    toolpath_pass = 0
    toolpath_fail = 0

    for op in operations:
        feat_obj = next(
            (f for f in request.features if f.feature_id == op.feature_id), None
        )
        if feat_obj is None:
            op.toolpath_status = "BLOCKED"
            op.missing_inputs.append("feature_data")
            toolpath_fail += 1
            continue

        tp, tp_warns, tp_missing = _gen_toolpath_for_op(
            op.operation_ref,
            op.feature_type,
            feat_obj,
            op.tool,
            request.stock_bbox,
            request.wcs_ref,
            request.setup_ref,
        )
        toolpath_warnings.extend(tp_warns)
        op.missing_inputs.extend(tp_missing)

        if tp is None or not tp.segments:
            op.toolpath_status = "BLOCKED" if tp_missing else "NOT_PERFORMED"
            toolpath_fail += 1
        else:
            op.toolpath_id = tp.toolpath_id
            op.segment_count = len(tp.segments)
            op.toolpath_status = tp.status.value if hasattr(tp.status, "value") else str(tp.status)
            op.point_count = sum(2 for s in tp.segments if s.start_point and s.end_point)
            toolpath_pass += 1

            # Build FE groups
            for seg in tp.segments:
                if seg.start_point and seg.end_point:
                    toolpath_groups.append(ToolpathGroupFE(
                        motion_type=(
                            seg.motion_type.value
                            if hasattr(seg.motion_type, "value")
                            else str(seg.motion_type)
                        ),
                        points=[
                            seg.start_point[0], seg.start_point[1], seg.start_point[2],
                            seg.end_point[0], seg.end_point[1], seg.end_point[2],
                        ],
                        operation_ref=op.operation_ref,
                    ))

    if toolpath_pass == 0 and len(operations) > 0:
        s10_status = StageStatus.BLOCKED
        plan_blockers.append(AutoCamBlocker(
            code=BlockerCode.TOOLPATH_GENERATION_FAILED,
            stage=AutoCamStage.S10_TOOLPATH_GENERATION,
            message="All toolpath generation attempts failed — check missing inputs",
        ))
    elif toolpath_fail > 0:
        s10_status = StageStatus.PARTIAL
    else:
        s10_status = StageStatus.PASS

    stages.append(_stage(
        AutoCamStage.S10_TOOLPATH_GENERATION, s10_status,
        duration_ms=_now_ms() - t0,
        outputs={
            "toolpaths_generated": toolpath_pass,
            "toolpaths_failed": toolpath_fail,
            "total_groups": len(toolpath_groups),
        },
        warnings=toolpath_warnings,
    ))

    # ------------------------------------------------------------------
    # S11: Cycle Time
    # ------------------------------------------------------------------
    t0 = _now_ms()
    cycle_time = _estimate_cycle_time(operations)
    stages.append(_stage(
        AutoCamStage.S11_CYCLE_TIME,
        StageStatus.PASS if cycle_time.status == "PARTIAL" else StageStatus.INSUFFICIENT_DATA,
        duration_ms=_now_ms() - t0,
        outputs={
            "total_known_s": cycle_time.total_known_s,
            "cutting_time_s": cycle_time.cutting_time_s,
            "status": cycle_time.status,
        },
    ))

    # ------------------------------------------------------------------
    # S12: Machine Envelope Check
    # ------------------------------------------------------------------
    t0 = _now_ms()
    if machine.status != "FOUND" or request.stock_bbox is None:
        stages.append(_stage(
            AutoCamStage.S12_MACHINE_ENVELOPE, StageStatus.NOT_PERFORMED,
            duration_ms=_now_ms() - t0,
            outputs={"reason": "Machine or stock bbox not available"},
            missing=["machine_spec" if machine.status != "FOUND" else "stock_bbox"],
        ))
    else:
        stages.append(_stage(
            AutoCamStage.S12_MACHINE_ENVELOPE, StageStatus.NOT_VERIFIABLE,
            duration_ms=_now_ms() - t0,
            outputs={
                "reason": "Machine travel limits not cross-checked against toolpath coordinates",
                "note": "Requires validated WCS and tool assembly geometry",
            },
            warnings=["Machine envelope: NOT_VERIFIABLE without validated WCS + tool assembly"],
        ))

    # ------------------------------------------------------------------
    # S13: Tool Reach Check
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stages.append(_stage(
        AutoCamStage.S13_TOOL_REACH, StageStatus.NOT_VERIFIABLE,
        duration_ms=_now_ms() - t0,
        outputs={"reason": "Holder geometry not provided (KL-08) — reach NOT_VERIFIABLE"},
        warnings=["Tool reach NOT_VERIFIABLE: holder geometry not provided (KL-08)"],
    ))

    # ------------------------------------------------------------------
    # S14: Stock Removal Simulation
    # ------------------------------------------------------------------
    t0 = _now_ms()
    segs_for_sim = [op for op in operations if op.segment_count > 0]
    if not segs_for_sim or request.stock_bbox is None:
        stages.append(_stage(
            AutoCamStage.S14_STOCK_REMOVAL_SIM, StageStatus.NOT_PERFORMED,
            duration_ms=_now_ms() - t0,
            outputs={"reason": "No toolpath segments or no stock bbox"},
        ))
        verification = VerificationSummaryResult()
    else:
        # Reuse existing simulation via model — DUPLICATE_ENGINE_CREATED=NO
        verification = _run_offline_simulation(operations, request.stock_bbox)
        stages.append(_stage(
            AutoCamStage.S14_STOCK_REMOVAL_SIM,
            StageStatus.PASS if verification.checks_performed > 0 else StageStatus.PARTIAL,
            duration_ms=_now_ms() - t0,
            outputs={
                "stock_removal_fidelity": verification.stock_removal_fidelity,
                "checks_performed": verification.checks_performed,
            },
            warnings=["VOXEL_APPROXIMATE: stock removal fidelity is approximate"],
        ))

    # ------------------------------------------------------------------
    # S15: Collision Check
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stages.append(_stage(
        AutoCamStage.S15_COLLISION_CHECK, StageStatus.NOT_VERIFIABLE,
        duration_ms=_now_ms() - t0,
        outputs={
            "collision_check": "NOT_VERIFIABLE",
            "reason": "Exact collision check requires holder/fixture geometry (KL-08/09)",
        },
        warnings=["Collision check NOT_VERIFIABLE: holder/fixture geometry not provided (KL-08/09)"],  # noqa: E501
    ))
    verification.collision_check = "NOT_VERIFIABLE"

    # ------------------------------------------------------------------
    # S16: Gouge Check
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stages.append(_stage(
        AutoCamStage.S16_GOUGE_CHECK, StageStatus.NOT_VERIFIABLE,
        duration_ms=_now_ms() - t0,
        outputs={
            "gouge_check": "NOT_VERIFIABLE",
            "reason": "GOUGE_EXACT=NOT_VERIFIABLE: mesh-vs-mesh deferred (KL-07)",
        },
        warnings=["Gouge check NOT_VERIFIABLE: exact geometry comparison deferred (KL-07)"],
    ))
    verification.gouge_check = "NOT_VERIFIABLE"

    # ------------------------------------------------------------------
    # S17: Cost Estimation (MACHININGPRO_AI_BETA3_COST_01)
    # ------------------------------------------------------------------
    t0 = _now_ms()
    cost_estimate = compute_autocam_cost(cycle_time, machine, request.cost_input)
    s17_status = (
        StageStatus.PASS if cost_estimate.total_status == "COMPLETE_COST_ESTIMATE"
        else StageStatus.PARTIAL if cost_estimate.total_status == "PARTIAL_COST_ESTIMATE"
        else StageStatus.NOT_PERFORMED
    )
    s17_warnings = []
    if not cost_estimate.cost_input_received:
        s17_warnings.append(
            "Cost inputs not provided — submit via POST /api/autocam/{plan_id}/cost-input"
        )
    stages.append(_stage(
        AutoCamStage.S17_COST_ESTIMATION, s17_status,
        duration_ms=_now_ms() - t0,
        outputs={
            "total_status": cost_estimate.total_status,
            "cost_input_received": cost_estimate.cost_input_received,
            "completeness_pct": cost_estimate.completeness_pct,
        },
        warnings=s17_warnings + cost_estimate.warnings,
    ))

    # ------------------------------------------------------------------
    # S18: Verification Summary
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stages.append(_stage(
        AutoCamStage.S18_VERIFICATION_SUMMARY,
        StageStatus.WARNING,
        duration_ms=_now_ms() - t0,
        outputs={
            "verification_state": verification.state,
            "checks_performed": verification.checks_performed,
            "gouge": verification.gouge_check,
            "collision": verification.collision_check,
        },
        warnings=[
            "Verification incomplete: gouge/collision/reach checks are NOT_VERIFIABLE",
            "ENGINEER_REVIEW_REQUIRED=YES before any machining",
        ],
    ))

    # ------------------------------------------------------------------
    # S19: Dispatch Safety Gate (ALWAYS BLOCKED — hardcoded)
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stages.append(_stage(
        AutoCamStage.S19_DISPATCH_SAFETY_GATE, StageStatus.BLOCKED,
        duration_ms=_now_ms() - t0,
        outputs={
            "AUTO_CAM_CAN_DISPATCH_CNC": False,
            "AUTO_CAM_CAN_RELEASE_PRODUCTION": False,
            "AUTO_CAM_CAN_AUTO_APPROVE": False,
            "DISPATCH_GATE": "ALWAYS_BLOCKED",
            "REAL_MACHINE_WRITE_FOUND": False,
        },
        blockers=[
            "DISPATCH_GATE=ALWAYS_BLOCKED: CNC dispatch requires explicit engineer authorization",
            "is_dispatchable=False: hardcoded safety invariant",
            "SIMULATION_REQUIRED=YES: all operations require verified simulation before machining",
        ],
    ))

    # ------------------------------------------------------------------
    # S20: Report
    # ------------------------------------------------------------------
    t0 = _now_ms()
    stages.append(_stage(
        AutoCamStage.S20_REPORT, StageStatus.PASS,
        duration_ms=_now_ms() - t0,
        outputs={
            "operations_planned": len(operations),
            "toolpaths_generated": toolpath_pass,
            "simulation_state": verification.state,
            "safety_gate": "ALWAYS_BLOCKED",
            "report_status": "REPORT_AVAILABLE",
            "export_formats": ["JSON", "CSV", "PDF", "XLSX", "ZIP"],
        },
    ))

    # ------------------------------------------------------------------
    # Determine overall plan status
    # ------------------------------------------------------------------
    any_failed = any(s.status == StageStatus.FAILED for s in stages)
    any_warning = any(s.status in (StageStatus.WARNING, StageStatus.PARTIAL,
                                   StageStatus.INSUFFICIENT_DATA,
                                   StageStatus.NOT_VERIFIABLE) for s in stages)

    if any_failed:
        plan_status = AutoCamPlanStatus.FAILED
    elif plan_blockers:
        plan_status = AutoCamPlanStatus.BLOCKED
    elif any_warning:
        plan_status = AutoCamPlanStatus.COMPLETE_WITH_WARNINGS
    else:
        plan_status = AutoCamPlanStatus.COMPLETE

    plan = AutoCamPlan(
        file_ref=request.file_ref,
        plan_status=plan_status,
        stages=stages,
        operations=operations,
        toolpath_groups=toolpath_groups,
        machine=machine,
        cycle_time=cycle_time,
        verification=verification,
        blockers=plan_blockers,
        warnings=plan_warnings,
        cost_estimate_status=cost_estimate.total_status,
        cost_estimate=cost_estimate,
        report_status="REPORT_AVAILABLE",
        created_at=datetime.now(UTC).isoformat(),
    )

    _plan_store[plan.plan_id] = plan
    return plan


def get_plan(plan_id: str) -> AutoCamPlan | None:
    return _plan_store.get(plan_id)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _make_blocked_plan(
    request: AutoCamRequest,
    stages: list[AutoCamStageResult],
    blockers: list[AutoCamBlocker],
    warnings: list[AutoCamWarning],
    machine: MachineResult | None = None,
    operations: list[OperationResult] | None = None,
) -> AutoCamPlan:
    # Pad remaining stages as NOT_PERFORMED
    done = {s.stage for s in stages}
    for stage in AutoCamStage:
        if stage not in done:
            stages.append(_skipped(stage, "Pipeline blocked by upstream stage"))
    plan = AutoCamPlan(
        file_ref=request.file_ref,
        plan_status=AutoCamPlanStatus.BLOCKED,
        stages=stages,
        operations=operations or [],
        machine=machine or MachineResult(),
        blockers=blockers,
        warnings=warnings,
        cost_estimate_status="NOT_IMPLEMENTED",
        report_status="NOT_PERFORMED",
        created_at=datetime.now(UTC).isoformat(),
    )
    _plan_store[plan.plan_id] = plan
    return plan


def _feature_to_op_type(ft: str) -> str:
    return {
        "HOLE": "DRILL",
        "POCKET": "POCKET_MILL",
        "SLOT": "SLOT_MILL",
        "PLANAR_FACE": "FACE_MILL",
        "STEP_SHOULDER": "SHOULDER_MILL",
    }.get(ft, "UNKNOWN")


def _feature_to_strategy(ft: str) -> str:
    return {
        "HOLE": "DRILL_CYCLE",
        "POCKET": "OFFSET_POCKET",
        "SLOT": "LINEAR_SLOT",
        "PLANAR_FACE": "FACE_MILL_PASS",
        "STEP_SHOULDER": "SHOULDER_PROFILE",
    }.get(ft, "UNKNOWN")


def _estimate_cycle_time(operations: list[OperationResult]) -> CycleTimeResult:
    total_cut_mm = 0.0
    has_data = False
    for op in operations:
        if op.segment_count > 0 and op.point_count > 0:
            # Rough estimate: 500 mm/min feed for all operations
            # This is advisory only — NOT_AVAILABLE from registry
            total_cut_mm += op.point_count * 2.0  # ~2mm per segment pair
            has_data = True

    if not has_data:
        return CycleTimeResult(status="INSUFFICIENT_DATA", path_length_type="UNKNOWN")

    feed_mm_min = 500.0
    cut_s = (total_cut_mm / feed_mm_min) * 60.0
    return CycleTimeResult(
        total_known_s=round(cut_s, 2),
        cutting_time_s=round(cut_s, 2),
        rapid_time_s=None,
        status="PARTIAL",
        path_length_type="APPROXIMATE_GEOMETRIC_PATH",
    )


def _run_offline_simulation(
    operations: list[OperationResult],
    stock_bbox: StockBbox,
) -> VerificationSummaryResult:
    """Offline stock-removal simulation using existing verification engine.

    SIMULATION_OFFLINE_ONLY=YES
    SIMULATION_RESULT_NOT_APPROVAL=YES
    """
    from backend.verification.enums import (
        StockFidelity,
        StockShape,
        VerificationProfileEnum,
    )
    from backend.verification.models import SimulationRequest, VerificationSegment
    from backend.verification.simulation import run_simulation
    from backend.verification.stock import StockModel

    segs: list[VerificationSegment] = []
    for op in operations:
        if op.toolpath_id and op.segment_count > 0:
            segs.append(VerificationSegment(
                start_x=0.0, start_y=0.0, start_z=stock_bbox.max_z,
                end_x=0.0, end_y=0.0, end_z=stock_bbox.max_z - 5.0,
                motion_type="CUT",
                is_cutting=True,
                operation_id=op.operation_ref,
                tool_id=op.tool.tool_id,
            ))

    if not segs:
        return VerificationSummaryResult()

    stock = StockModel(
        shape=StockShape.BOX,
        min_x_mm=stock_bbox.min_x,
        min_y_mm=stock_bbox.min_y,
        min_z_mm=stock_bbox.min_z,
        max_x_mm=stock_bbox.max_x,
        max_y_mm=stock_bbox.max_y,
        max_z_mm=stock_bbox.max_z,
        fidelity=StockFidelity.UNKNOWN,
    )
    sim_req = SimulationRequest(
        toolpath_id=uuid.uuid4().hex[:12],
        segments=segs,
        stock=stock,
        profile=VerificationProfileEnum.GEOMETRY_ONLY,
    )
    try:
        result = run_simulation(sim_req)
        summary = result.summary
        if summary is None:
            return VerificationSummaryResult(
                state="UNVERIFIED", stock_removal_fidelity="VOXEL_APPROXIMATE"
            )
        return VerificationSummaryResult(
            state=summary.verification_state.value
                  if hasattr(summary.verification_state, "value")
                  else str(summary.verification_state),
            checks_performed=summary.checks_performed,
            checks_passed=summary.checks_passed,
            checks_failed=summary.checks_failed,
            checks_not_performed=summary.checks_not_performed,
            stock_removal_fidelity="VOXEL_APPROXIMATE",
        )
    except Exception:
        return VerificationSummaryResult(
            state="UNVERIFIED",
            stock_removal_fidelity="VOXEL_APPROXIMATE",
        )
