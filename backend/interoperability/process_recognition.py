"""Level-4 manufacturing process intelligence — deterministic feature-to-process mapping.

Derives DFM observations, operation candidates, setup candidates, machine-class
requirements and tool-family requirements from Level-3 FeatureRecognitionResult.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate manufacturing processes, machine selections, tool
    selections, feeds, speeds, cycle times or costs.
  - Preserve feature confidence: CANDIDATE features produce CANDIDATE
    operations; CONFIRMED_BY_RULE requires topology-confirmed features.
  - If required engineering information is unavailable, return
    UNKNOWN / INCOMPLETE / REQUIRES_INPUT.

DFM threshold constants (documented here — single source of truth):
  DEEP_HOLE_LD_INFO   = 5.0   L/D ratio at which a hole first attracts INFO
  DEEP_HOLE_LD_LOW    = 10.0  L/D at which severity escalates to LOW
  DEEP_HOLE_LD_MEDIUM = 20.0  L/D at which severity escalates to MEDIUM
"""

from __future__ import annotations

import uuid

# ---------------------------------------------------------------------------
# DFM thresholds — single source of truth
# ---------------------------------------------------------------------------

_DEEP_HOLE_LD_INFO: float = 5.0
_DEEP_HOLE_LD_LOW: float = 10.0
_DEEP_HOLE_LD_MEDIUM: float = 20.0


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def recognize_process_intelligence(
    features: object | None,
    geometry: object | None,
    topology: object | None,
    material: object | None = None,
) -> object:
    """Derive process intelligence from Level-3 feature recognition results.

    Parameters
    ----------
    features:
        FeatureRecognitionResult from Level-3, or None.
    geometry:
        CanonicalGeometry, used for dimensional DFM checks, or None.
    topology:
        CanonicalTopology, available when B-Rep was parsed, or None.
    material:
        MaterialContext provided by the caller; None means unknown.

    Returns
    -------
    ProcessIntelligenceResult
        Always returns a result; never raises.  Missing information is
        reflected in status and missing_inputs rather than fabricated.
    """
    from backend.interoperability.features import FeatureRecognitionResult
    from backend.interoperability.process_intelligence import (
        CuttingParameterStatus,
        CycleTimeStatus,
        ManufacturingOperation,
        MaterialContext,
        PlanStatus,
        ProcessIntelligenceResult,
        ProcessStatus,
        ToolRequirement,
    )

    plan_id = _uid("PLAN-")

    if not isinstance(features, FeatureRecognitionResult):
        return ProcessIntelligenceResult(
            plan_id=plan_id,
            status=PlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NONE",
            missing_inputs=(
                "No Level-3 feature recognition result available",
                "Material unknown",
            ),
            warnings=("Process planning requires Level-3 feature recognition",),
        )

    mat_ctx = material if isinstance(material, MaterialContext) else MaterialContext()

    all_ops: list[ManufacturingOperation] = []
    all_tool_reqs: list[ToolRequirement] = []
    all_dfm: list = []
    missing: list[str] = []
    warns: list[str] = []

    # Shared preamble — always require material for cutting parameters
    if mat_ctx.status.value == "UNKNOWN":
        missing.append("Material specification required for cutting parameters")

    basis = features.recognition_basis

    # ------------------------------------------------------------------
    # Map confirmed features → CONFIRMED_BY_RULE operations
    # ------------------------------------------------------------------

    for feat in features.features:
        from backend.interoperability.features import (
            FeatureStatus,
            ManufacturingFeatureType,
        )

        if feat.status not in (FeatureStatus.CONFIRMED, FeatureStatus.CANDIDATE):
            continue

        is_confirmed = feat.status == FeatureStatus.CONFIRMED
        op_status = ProcessStatus.CONFIRMED_BY_RULE if is_confirmed else ProcessStatus.CANDIDATE

        ftype = feat.feature_type
        fid = feat.feature_id

        if ftype == ManufacturingFeatureType.HOLE:
            ops, tool_reqs, dfm_obs = _map_hole(
                feat, op_status, geometry, fid, mat_ctx
            )
            all_ops.extend(ops)
            all_tool_reqs.extend(tool_reqs)
            all_dfm.extend(dfm_obs)

        elif ftype == ManufacturingFeatureType.POCKET:
            ops, tool_reqs = _map_pocket(feat, op_status, fid)
            all_ops.extend(ops)
            all_tool_reqs.extend(tool_reqs)

        elif ftype == ManufacturingFeatureType.SLOT:
            ops, tool_reqs = _map_slot(feat, op_status, fid)
            all_ops.extend(ops)
            all_tool_reqs.extend(tool_reqs)

        elif ftype == ManufacturingFeatureType.STEP:
            ops, tool_reqs = _map_step(feat, op_status, fid)
            all_ops.extend(ops)
            all_tool_reqs.extend(tool_reqs)

        elif ftype == ManufacturingFeatureType.CHAMFER:
            ops, tool_reqs = _map_chamfer(feat, op_status, fid)
            all_ops.extend(ops)
            all_tool_reqs.extend(tool_reqs)

        elif ftype == ManufacturingFeatureType.FILLET:
            ops, tool_reqs = _map_fillet(feat, op_status, fid)
            all_ops.extend(ops)
            all_tool_reqs.extend(tool_reqs)

    # ------------------------------------------------------------------
    # Setup candidates
    # ------------------------------------------------------------------
    setups = _build_setups(features, all_ops)

    # Assign setups to operations
    if setups:
        setup_id = setups[0].setup_id
        all_ops = [
            ManufacturingOperation(
                operation_id=op.operation_id,
                process_family=op.process_family,
                status=op.status,
                feature_ids=op.feature_ids,
                tool_family=op.tool_family,
                roughing_or_finishing=op.roughing_or_finishing,
                setup_id=setup_id,
                orientation=op.orientation,
                precedes=op.precedes,
                follows=op.follows,
                precedence_type=op.precedence_type,
                rationale=op.rationale,
                warnings=op.warnings,
                evidence_notes=op.evidence_notes,
            )
            for op in all_ops
        ]

    # ------------------------------------------------------------------
    # Machine class requirements
    # ------------------------------------------------------------------
    machine_reqs = _derive_machine_requirements(all_ops, setups)

    # ------------------------------------------------------------------
    # Operation sequence (ordered plan)
    # ------------------------------------------------------------------
    operation_plan = _sequence_operations(all_ops)

    # ------------------------------------------------------------------
    # Additional missing inputs
    # ------------------------------------------------------------------
    if not features.features:
        missing.append(
            "No manufacturing features available; "
            "topology required for detailed process planning"
        )
    else:
        has_hole_no_depth = any(
            True
            for feat in features.features
            if _is_hole_without_depth(feat)
        )
        if has_hole_no_depth:
            missing.append("Hole depth required for L/D DFM analysis and tool reach specification")

    if features.recognition_basis == "2D_GEOMETRY_ONLY":
        missing.append("3D context required; current input is 2D drawing projection only")
        warns.append(
            "Process candidates derived from 2D DXF projection; "
            "depth and 3D geometry required for confirmed process plan"
        )

    if features.recognition_basis == "GEOMETRY_ONLY":
        missing.append("B-Rep topology required for feature confirmation and process confirmation")
        warns.append(
            "Process candidates derived from surface geometry only; "
            "topology required for CONFIRMED_BY_RULE recommendations"
        )

    if features.recognition_basis == "NONE":
        warns.append("No geometry or topology; process plan is empty")

    # ------------------------------------------------------------------
    # Turning indicator
    # ------------------------------------------------------------------
    turning_indicator = _assess_turning(features, geometry)

    # ------------------------------------------------------------------
    # Plan status
    # ------------------------------------------------------------------
    confirmed_count = sum(
        1 for f in features.features
        if hasattr(f, "status") and str(f.status) == "CONFIRMED"
    )

    if not features.features:
        plan_status = PlanStatus.INSUFFICIENT_DATA
    elif all(op.status == ProcessStatus.CANDIDATE for op in operation_plan):
        plan_status = PlanStatus.CANDIDATE_PLAN
    elif any(op.status == ProcessStatus.CONFIRMED_BY_RULE for op in operation_plan):
        plan_status = PlanStatus.COMPLETE if confirmed_count > 0 else PlanStatus.PARTIAL
    else:
        plan_status = PlanStatus.PARTIAL

    return ProcessIntelligenceResult(
        plan_id=plan_id,
        status=plan_status,
        recognition_basis=basis,
        dfm_observations=tuple(all_dfm),
        process_candidates=tuple(all_ops),
        setups=tuple(setups),
        machine_requirements=tuple(machine_reqs),
        tool_requirements=tuple(all_tool_reqs),
        operation_plan=tuple(operation_plan),
        material_context=mat_ctx,
        cutting_parameter_status=CuttingParameterStatus(),
        cycle_time_status=CycleTimeStatus(),
        turning_indicator=turning_indicator,
        missing_inputs=tuple(missing),
        warnings=tuple(warns),
        source_feature_count=len(features.features),
        confirmed_feature_count=confirmed_count,
    )


# ---------------------------------------------------------------------------
# Feature-to-process mapping helpers
# ---------------------------------------------------------------------------


def _map_hole(
    feat: object,
    op_status: object,
    geometry: object | None,
    fid: str,
    mat_ctx: object,
) -> tuple[list, list, list]:
    """Map a hole feature (any subtype) to drilling operations."""
    from backend.interoperability.features import HoleSubtype
    from backend.interoperability.process_intelligence import (
        DFMObservation,
        ManufacturingOperation,
        PrecedenceType,
        ProcessFamily,
        RoughingOrFinishing,
        ToolFamily,
        ToolRequirement,
    )

    ops: list[ManufacturingOperation] = []
    tool_reqs: list[ToolRequirement] = []
    dfm_obs: list[DFMObservation] = []

    subtype = getattr(feat, "hole_subtype", HoleSubtype.UNKNOWN)
    curve_ids = getattr(feat, "curve_ids", ())
    source_curve_id = curve_ids[0] if curve_ids else None

    # Diameter from geometry when available
    diameter_mm: float | None = None
    if source_curve_id is not None and geometry is not None:
        try:
            from backend.interoperability.geometry import CanonicalGeometry

            if isinstance(geometry, CanonicalGeometry) and geometry.has_curve(source_curve_id):
                curve = geometry.get_curve(source_curve_id)
                if curve.radius is not None:
                    diameter_mm = float(curve.radius.value) * 2.0
        except Exception:  # noqa: BLE001
            pass

    # Center drill (always precedes drilling — engineering required)
    cd_id = _uid("OP-CD-")
    drill_id = _uid("OP-DR-")

    cd_op = ManufacturingOperation(
        operation_id=cd_id,
        process_family=ProcessFamily.CENTER_DRILLING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.CENTER_DRILL,
        roughing_or_finishing=RoughingOrFinishing.COMBINED,
        precedes=(drill_id,),
        follows=(),
        precedence_type=PrecedenceType.ENGINEERING_REQUIRED,
        rationale="Center drilling required before drilling to ensure positional accuracy",
        evidence_notes=f"feature_id={fid}",
    )

    drill_rationale = _hole_rationale(subtype, op_status)
    drill_op = ManufacturingOperation(
        operation_id=drill_id,
        process_family=_hole_process(subtype),
        status=op_status,
        feature_ids=(fid,),
        tool_family=_hole_tool(subtype),
        roughing_or_finishing=RoughingOrFinishing.COMBINED,
        precedes=(),
        follows=(cd_id,),
        precedence_type=PrecedenceType.ENGINEERING_REQUIRED,
        rationale=drill_rationale,
        evidence_notes=f"feature_id={fid}",
    )

    ops.extend([cd_op, drill_op])

    # Tool requirements
    tool_reqs.append(
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.CENTER_DRILL,
            operation_id=cd_id,
            basis="center_drill_before_hole_drilling",
            evidence_notes=f"feature_id={fid}",
        )
    )
    tool_reqs.append(
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=_hole_tool(subtype),
            operation_id=drill_id,
            min_diameter_mm=diameter_mm,
            max_diameter_mm=diameter_mm,
            basis="feature_to_process_mapping",
            evidence_notes=f"feature_id={fid}",
        )
    )

    # DFM: counterbore and countersink add extra operations
    if subtype == HoleSubtype.COUNTERBORE:
        cb_id = _uid("OP-CB-")
        cb_op = ManufacturingOperation(
            operation_id=cb_id,
            process_family=ProcessFamily.COUNTERBORING,
            status=op_status,
            feature_ids=(fid,),
            tool_family=ToolFamily.END_MILL,
            roughing_or_finishing=RoughingOrFinishing.COMBINED,
            follows=(drill_id,),
            precedence_type=PrecedenceType.ENGINEERING_REQUIRED,
            rationale="Counterboring requires pilot hole drilled first",
            evidence_notes=f"feature_id={fid}",
        )
        ops.append(cb_op)
        tool_reqs.append(
            ToolRequirement(
                requirement_id=_uid("TR-"),
                tool_family=ToolFamily.END_MILL,
                operation_id=cb_id,
                basis="counterbore_after_pilot_drill",
                evidence_notes=f"feature_id={fid}",
            )
        )

    elif subtype == HoleSubtype.COUNTERSINK:
        cs_id = _uid("OP-CS-")
        cs_op = ManufacturingOperation(
            operation_id=cs_id,
            process_family=ProcessFamily.COUNTERSINKING,
            status=op_status,
            feature_ids=(fid,),
            tool_family=ToolFamily.CHAMFER_MILL,
            roughing_or_finishing=RoughingOrFinishing.COMBINED,
            follows=(drill_id,),
            precedence_type=PrecedenceType.ENGINEERING_REQUIRED,
            rationale="Countersinking requires pilot hole drilled first",
            evidence_notes=f"feature_id={fid}",
        )
        ops.append(cs_op)
        tool_reqs.append(
            ToolRequirement(
                requirement_id=_uid("TR-"),
                tool_family=ToolFamily.CHAMFER_MILL,
                operation_id=cs_id,
                basis="countersink_after_pilot_drill",
                evidence_notes=f"feature_id={fid}",
            )
        )

    return ops, tool_reqs, dfm_obs


def _hole_process(subtype: object) -> object:
    from backend.interoperability.features import HoleSubtype
    from backend.interoperability.process_intelligence import ProcessFamily

    if subtype == HoleSubtype.COUNTERBORE:
        return ProcessFamily.DRILLING
    if subtype == HoleSubtype.COUNTERSINK:
        return ProcessFamily.DRILLING
    return ProcessFamily.DRILLING


def _hole_tool(subtype: object) -> object:
    from backend.interoperability.features import HoleSubtype
    from backend.interoperability.process_intelligence import ToolFamily

    if subtype in (HoleSubtype.COUNTERBORE, HoleSubtype.COUNTERSINK):
        return ToolFamily.DRILL
    return ToolFamily.DRILL


def _hole_rationale(subtype: object, status: object) -> str:
    from backend.interoperability.features import HoleSubtype
    from backend.interoperability.process_intelligence import ProcessStatus

    basis = (
        "topology B-Rep evidence"
        if status == ProcessStatus.CONFIRMED_BY_RULE
        else "2D/geometry candidate"
    )
    if subtype == HoleSubtype.THROUGH:
        return f"Through-hole drilling ({basis})"
    if subtype == HoleSubtype.BLIND:
        return f"Blind-hole drilling ({basis})"
    if subtype == HoleSubtype.COUNTERBORE:
        return f"Counterbore pilot-hole drilling ({basis})"
    if subtype == HoleSubtype.COUNTERSINK:
        return f"Countersink pilot-hole drilling ({basis})"
    return f"Hole drilling ({basis})"


def _map_pocket(feat: object, op_status: object, fid: str) -> tuple[list, list]:
    from backend.interoperability.process_intelligence import (
        ManufacturingOperation,
        PrecedenceType,
        ProcessFamily,
        RoughingOrFinishing,
        ToolFamily,
        ToolRequirement,
    )

    rough_id = _uid("OP-MR-")
    finish_id = _uid("OP-MF-")

    rough_op = ManufacturingOperation(
        operation_id=rough_id,
        process_family=ProcessFamily.MILLING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.END_MILL,
        roughing_or_finishing=RoughingOrFinishing.ROUGHING,
        precedes=(finish_id,),
        precedence_type=PrecedenceType.COMMON_PRACTICE,
        rationale="Pocket roughing before finishing",
        evidence_notes=f"feature_id={fid}",
    )
    finish_op = ManufacturingOperation(
        operation_id=finish_id,
        process_family=ProcessFamily.MILLING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.END_MILL,
        roughing_or_finishing=RoughingOrFinishing.FINISHING,
        follows=(rough_id,),
        precedence_type=PrecedenceType.COMMON_PRACTICE,
        rationale="Pocket finishing after roughing",
        evidence_notes=f"feature_id={fid}",
    )

    tool_reqs = [
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.END_MILL,
            operation_id=rough_id,
            basis="pocket_milling",
            evidence_notes=f"feature_id={fid}",
        ),
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.END_MILL,
            operation_id=finish_id,
            basis="pocket_milling_finish",
            evidence_notes=f"feature_id={fid}",
        ),
    ]
    return [rough_op, finish_op], tool_reqs


def _map_slot(feat: object, op_status: object, fid: str) -> tuple[list, list]:
    from backend.interoperability.process_intelligence import (
        ManufacturingOperation,
        ProcessFamily,
        RoughingOrFinishing,
        ToolFamily,
        ToolRequirement,
    )

    op_id = _uid("OP-SL-")
    op = ManufacturingOperation(
        operation_id=op_id,
        process_family=ProcessFamily.MILLING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.SLOT_MILL,
        roughing_or_finishing=RoughingOrFinishing.COMBINED,
        rationale="Slot milling",
        evidence_notes=f"feature_id={fid}",
    )
    tool_reqs = [
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.SLOT_MILL,
            operation_id=op_id,
            basis="slot_milling",
            evidence_notes=f"feature_id={fid}",
        )
    ]
    return [op], tool_reqs


def _map_step(feat: object, op_status: object, fid: str) -> tuple[list, list]:
    from backend.interoperability.process_intelligence import (
        ManufacturingOperation,
        ProcessFamily,
        RoughingOrFinishing,
        ToolFamily,
        ToolRequirement,
    )

    op_id = _uid("OP-ST-")
    op = ManufacturingOperation(
        operation_id=op_id,
        process_family=ProcessFamily.MILLING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.END_MILL,
        roughing_or_finishing=RoughingOrFinishing.COMBINED,
        rationale="Step milling (shoulder/face)",
        evidence_notes=f"feature_id={fid}",
    )
    tool_reqs = [
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.END_MILL,
            operation_id=op_id,
            basis="step_milling",
            evidence_notes=f"feature_id={fid}",
        )
    ]
    return [op], tool_reqs


def _map_chamfer(feat: object, op_status: object, fid: str) -> tuple[list, list]:
    from backend.interoperability.process_intelligence import (
        ManufacturingOperation,
        ProcessFamily,
        RoughingOrFinishing,
        ToolFamily,
        ToolRequirement,
    )

    op_id = _uid("OP-CH-")
    op = ManufacturingOperation(
        operation_id=op_id,
        process_family=ProcessFamily.CHAMFERING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.CHAMFER_MILL,
        roughing_or_finishing=RoughingOrFinishing.COMBINED,
        rationale="Chamfer milling",
        evidence_notes=f"feature_id={fid}",
    )
    tool_reqs = [
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.CHAMFER_MILL,
            operation_id=op_id,
            basis="chamfer_milling",
            evidence_notes=f"feature_id={fid}",
        )
    ]
    return [op], tool_reqs


def _map_fillet(feat: object, op_status: object, fid: str) -> tuple[list, list]:
    from backend.interoperability.process_intelligence import (
        ManufacturingOperation,
        ProcessFamily,
        RoughingOrFinishing,
        ToolFamily,
        ToolRequirement,
    )

    op_id = _uid("OP-FL-")
    op = ManufacturingOperation(
        operation_id=op_id,
        process_family=ProcessFamily.PROFILE_MILLING,
        status=op_status,
        feature_ids=(fid,),
        tool_family=ToolFamily.BALL_NOSE_END_MILL,
        roughing_or_finishing=RoughingOrFinishing.FINISHING,
        rationale="Fillet profile milling (ball-nose end mill)",
        evidence_notes=f"feature_id={fid}",
    )
    tool_reqs = [
        ToolRequirement(
            requirement_id=_uid("TR-"),
            tool_family=ToolFamily.BALL_NOSE_END_MILL,
            operation_id=op_id,
            basis="fillet_profile_milling",
            evidence_notes=f"feature_id={fid}",
        )
    ]
    return [op], tool_reqs


# ---------------------------------------------------------------------------
# Setup candidate builder
# ---------------------------------------------------------------------------


def _build_setups(features: object, ops: list) -> list:
    from backend.interoperability.process_intelligence import (
        AccessibilityStatus,
        SetupCandidate,
    )

    if not ops:
        return []

    all_fids: list[str] = []
    for op in ops:
        all_fids.extend(op.feature_ids)
    unique_fids = list(dict.fromkeys(all_fids))

    basis = getattr(features, "recognition_basis", "NONE")

    if basis == "2D_GEOMETRY_ONLY":
        direction = "+Z"
        notes = "Setup direction assumed +Z; derived from 2D DXF drawing plane"
        accessibility = AccessibilityStatus.POTENTIALLY_ACCESSIBLE
    elif basis == "TOPOLOGY":
        direction = "+Z"
        notes = "Setup direction inferred from confirmed feature orientation"
        accessibility = AccessibilityStatus.ACCESSIBLE
    else:
        direction = "+Z"
        notes = "Setup direction assumed +Z; topology required for verified orientation"
        accessibility = AccessibilityStatus.UNKNOWN

    return [
        SetupCandidate(
            setup_id=_uid("SETUP-"),
            machining_direction=direction,
            feature_ids=tuple(unique_fids),
            accessibility=accessibility,
            orientation_label=f"OP10-{direction}",
            notes=notes,
        )
    ]


# ---------------------------------------------------------------------------
# Machine class derivation
# ---------------------------------------------------------------------------


def _derive_machine_requirements(ops: list, setups: list) -> list:
    from backend.interoperability.process_intelligence import (
        MachineClass,
        MachineRequirement,
    )

    if not ops:
        return []

    unique_directions = {s.machining_direction for s in setups}
    rotary_axes = 0
    if len(unique_directions) > 1:
        rotary_axes = 1

    machine_class = MachineClass.THREE_AXIS_VMC
    if rotary_axes > 0:
        machine_class = MachineClass.FOUR_AXIS_VMC

    basis_note = (
        "drilling_and_milling_operations_candidate"
        if any(
            op.process_family.value in ("DRILLING", "MILLING", "CENTER_DRILLING")
            for op in ops
        )
        else "generic_milling"
    )

    return [
        MachineRequirement(
            requirement_id=_uid("MCH-"),
            machine_class=machine_class,
            rotary_axes_required=rotary_axes,
            basis=basis_note,
            evidence_notes=f"derived_from_{len(ops)}_operations",
        )
    ]


# ---------------------------------------------------------------------------
# Operation sequencing
# ---------------------------------------------------------------------------


def _sequence_operations(ops: list) -> list:
    """Topological sort of operations by follows/precedes relationships."""
    if not ops:
        return []

    op_map = {op.operation_id: op for op in ops}
    # Build in-degree from follows constraints
    in_degree: dict[str, int] = {op.operation_id: 0 for op in ops}
    dependents: dict[str, list[str]] = {op.operation_id: [] for op in ops}

    for op in ops:
        for pred_id in op.follows:
            if pred_id in in_degree:
                in_degree[op.operation_id] += 1
                dependents[pred_id].append(op.operation_id)

    queue = [
        op_map[oid] for oid, deg in sorted(in_degree.items()) if deg == 0
    ]
    result: list = []
    visited: set[str] = set()

    while queue:
        op = queue.pop(0)
        if op.operation_id in visited:
            continue
        visited.add(op.operation_id)
        result.append(op)
        for dep_id in dependents[op.operation_id]:
            in_degree[dep_id] -= 1
            if in_degree[dep_id] == 0:
                queue.append(op_map[dep_id])

    # Append any operations not reachable by follows (no ordering constraint)
    for op in ops:
        if op.operation_id not in visited:
            result.append(op)

    return result


# ---------------------------------------------------------------------------
# DFM helpers
# ---------------------------------------------------------------------------


def _is_hole_without_depth(feat: object) -> bool:
    from backend.interoperability.features import ManufacturingFeatureType

    if getattr(feat, "feature_type", None) != ManufacturingFeatureType.HOLE:
        return False
    surface_ids = getattr(feat, "surface_ids", ())
    curve_ids = getattr(feat, "curve_ids", ())
    # 2D DXF hole from curve only (no surface) → no depth
    return len(surface_ids) == 0 and len(curve_ids) > 0


# ---------------------------------------------------------------------------
# Turning indicator
# ---------------------------------------------------------------------------


def _assess_turning(features: object, geometry: object | None) -> object:
    from backend.interoperability.process_intelligence import TurningIndicator

    if geometry is not None:
        from backend.interoperability.geometry import CanonicalGeometry, CanonicalSurfaceType

        if isinstance(geometry, CanonicalGeometry):
            cylinder_count = sum(
                1
                for s in geometry.surfaces
                if s.surface_type == CanonicalSurfaceType.CYLINDER
            )
            surface_count = len(geometry.surfaces)
            if surface_count > 0 and cylinder_count / surface_count > 0.6:
                return TurningIndicator.TURNING_STRONGLY_INDICATED
            if cylinder_count > 0:
                return TurningIndicator.TURNING_CANDIDATE

    return TurningIndicator.TURNING_NOT_INDICATED
