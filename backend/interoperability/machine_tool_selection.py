"""Level 5 — Machine and Tool Selection Intelligence engine.

Derives deterministic machine class requirements, machine candidates,
tool capability requirements, tool family candidates, holder requirements,
and compatibility results from a Level-4 ProcessIntelligenceResult.

HARD RULES (verbatim from task specification):
  - Do NOT fabricate machine recommendations.
  - Do NOT fabricate cutting-tool recommendations.
  - Do NOT invent machine specifications or tooling capabilities.
  - A process candidate does NOT automatically imply a valid machine/tool candidate.
  - Unknown data remains UNKNOWN.
"""

from __future__ import annotations

import uuid


def _uid(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:10]}"


def derive_machine_tool_intelligence(
    process_intelligence: object | None,
    geometry: object | None = None,
    material: object | None = None,
) -> object:
    """Derive machine and tool selection intelligence from Level-4 results.

    Parameters
    ----------
    process_intelligence:
        ProcessIntelligenceResult from Level-4, or None.
    geometry:
        CanonicalGeometry, used for dimensional context, or None.
    material:
        MaterialContext provided by the caller; None means unknown.

    Returns
    -------
    MachineToolIntelligenceResult
        Always returns a result; never raises.  Missing information is
        reflected in status and missing_inputs rather than fabricated.
    """
    from backend.interoperability.machine_tool_intelligence import (
        CuttingParameterRequirement,
        MachineToolIntelligenceResult,
        SelectionPlanStatus,
    )
    from backend.interoperability.process_intelligence import (
        PlanStatus,
        ProcessIntelligenceResult,
    )

    plan_id = _uid("L5PLAN-")

    if not isinstance(process_intelligence, ProcessIntelligenceResult):
        return MachineToolIntelligenceResult(
            plan_id=plan_id,
            status=SelectionPlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NONE",
            missing_inputs=(
                "No Level-4 process intelligence result available",
            ),
            warnings=("Machine/tool selection requires Level-4 process intelligence",),
        )

    pi = process_intelligence
    basis = pi.recognition_basis

    # Level-4 INSUFFICIENT_DATA → Level-5 also INSUFFICIENT_DATA
    if pi.status == PlanStatus.INSUFFICIENT_DATA:
        return MachineToolIntelligenceResult(
            plan_id=plan_id,
            status=SelectionPlanStatus.INSUFFICIENT_DATA,
            recognition_basis=basis,
            missing_inputs=tuple(pi.missing_inputs) + (
                "Level-4 process plan is INSUFFICIENT_DATA; "
                "machine/tool selection not possible",
            ),
            warnings=tuple(pi.warnings),
            source_process_candidate_count=len(pi.process_candidates),
            confirmed_process_count=pi.confirmed_feature_count,
        )

    missing: list[str] = list(pi.missing_inputs)
    warns: list[str] = list(pi.warnings)

    # ------------------------------------------------------------------
    # Phase 1: Machine capability requirements
    # ------------------------------------------------------------------
    mach_reqs = _derive_machine_capability_requirements(pi)

    # ------------------------------------------------------------------
    # Phase 2: Machine candidates
    # ------------------------------------------------------------------
    mach_candidates = _select_machine_candidates(mach_reqs, pi)

    # ------------------------------------------------------------------
    # Phase 3: Tool capability requirements
    # ------------------------------------------------------------------
    tool_reqs = _derive_tool_capability_requirements(pi)

    # ------------------------------------------------------------------
    # Phase 4: Tool candidates
    # ------------------------------------------------------------------
    tool_candidates = _select_tool_candidates(tool_reqs)

    # ------------------------------------------------------------------
    # Phase 5: Holder requirements
    # ------------------------------------------------------------------
    holder_reqs = _derive_holder_requirements(tool_reqs)

    # ------------------------------------------------------------------
    # Phase 6: Compatibility results
    # ------------------------------------------------------------------
    compat_results = _check_compatibility(tool_reqs, holder_reqs)

    # ------------------------------------------------------------------
    # Plan status
    # ------------------------------------------------------------------
    if not mach_candidates and not tool_candidates:
        status = SelectionPlanStatus.INSUFFICIENT_DATA
    elif all(
        mc.match_status == "UNKNOWN" for mc in mach_candidates
    ):
        status = SelectionPlanStatus.REQUIRES_INPUT
    elif pi.status == PlanStatus.CANDIDATE_PLAN:
        status = SelectionPlanStatus.CANDIDATE_PLAN
    elif pi.status == PlanStatus.COMPLETE:
        status = SelectionPlanStatus.COMPLETE
    else:
        status = SelectionPlanStatus.PARTIAL

    # Derivation-only warnings
    if basis == "2D_GEOMETRY_ONLY":
        warns.append(
            "Machine/tool requirements derived from 2D drawing candidates; "
            "3D geometry required for confirmed selection"
        )
    if basis == "GEOMETRY_ONLY":
        warns.append(
            "Machine/tool requirements derived from geometry candidates only; "
            "topology required for confirmed selection"
        )

    return MachineToolIntelligenceResult(
        plan_id=plan_id,
        status=status,
        recognition_basis=basis,
        machine_capability_requirements=tuple(mach_reqs),
        machine_candidates=tuple(mach_candidates),
        tool_capability_requirements=tuple(tool_reqs),
        tool_candidates=tuple(tool_candidates),
        holder_requirements=tuple(holder_reqs),
        compatibility_results=tuple(compat_results),
        cutting_parameter_requirements=CuttingParameterRequirement(),
        missing_inputs=tuple(missing),
        warnings=tuple(warns),
        source_process_candidate_count=len(pi.process_candidates),
        confirmed_process_count=pi.confirmed_feature_count,
    )


# ---------------------------------------------------------------------------
# Phase 1: Machine capability requirements
# ---------------------------------------------------------------------------


def _derive_machine_capability_requirements(pi: object) -> list:
    """Build machine capability requirements from the operation set."""
    from backend.interoperability.machine_tool_intelligence import (
        MachineCapabilityRequirement,
        MachineClassV5,
    )
    from backend.interoperability.process_intelligence import ProcessFamily

    ops = getattr(pi, "process_candidates", ())
    setups = getattr(pi, "setups", ())

    if not ops:
        return []

    # Determine which process families are present
    families = {op.process_family for op in ops}
    drilling = any(
        f in (ProcessFamily.DRILLING, ProcessFamily.CENTER_DRILLING,
              ProcessFamily.BORING, ProcessFamily.REAMING,
              ProcessFamily.TAPPING, ProcessFamily.COUNTERSINKING,
              ProcessFamily.COUNTERBORING)
        for f in families
    )
    milling = any(
        f in (ProcessFamily.MILLING, ProcessFamily.FACE_MILLING,
              ProcessFamily.PROFILE_MILLING, ProcessFamily.CHAMFERING)
        for f in families
    )
    turning = any(f == ProcessFamily.TURNING for f in families)
    grinding = any(f == ProcessFamily.GRINDING for f in families)
    edm = any(f == ProcessFamily.EDM for f in families)

    # Determine rotary axis count
    unique_dirs = {s.machining_direction for s in setups}
    rotary_axes = max(0, len(unique_dirs) - 1)

    # Select minimum machine class
    if edm:
        machine_class = MachineClassV5.WIRE_EDM
    elif grinding:
        machine_class = MachineClassV5.SURFACE_GRINDER
    elif turning and milling:
        machine_class = MachineClassV5.TURN_MILL
    elif turning:
        machine_class = MachineClassV5.CNC_LATHE
    elif rotary_axes >= 2:
        machine_class = MachineClassV5.FIVE_AXIS_VMC
    elif rotary_axes == 1:
        machine_class = MachineClassV5.FOUR_AXIS_VMC
    elif drilling or milling:
        machine_class = MachineClassV5.THREE_AXIS_VMC
    else:
        machine_class = MachineClassV5.UNKNOWN

    # Determine required axes
    required_axes = 3
    if rotary_axes >= 2:
        required_axes = 5
    elif rotary_axes == 1:
        required_axes = 4

    op_ids = tuple(op.operation_id for op in ops)
    evidence = (
        f"derived_from_{len(ops)}_operations_"
        f"{'drilling_' if drilling else ''}"
        f"{'milling_' if milling else ''}"
        f"{'turning_' if turning else ''}candidate"
    )

    req = MachineCapabilityRequirement(
        requirement_id=_uid("MCR-"),
        machine_class=machine_class,
        operation_refs=op_ids,
        required_axes=required_axes,
        required_rotary_axes=rotary_axes,
        turning_required=turning,
        milling_required=milling,
        drilling_required=drilling,
        grinding_required=grinding,
        edm_required=edm,
        evidence_notes=evidence,
        status="CANDIDATE",
    )
    return [req]


# ---------------------------------------------------------------------------
# Phase 2: Machine candidates
# ---------------------------------------------------------------------------


def _select_machine_candidates(mach_reqs: list, pi: object) -> list:
    """Derive generic machine class candidates from requirements."""
    from backend.interoperability.machine_tool_intelligence import (
        MachineCandidate,
        MachineClassV5,
        MatchStatus,
    )

    if not mach_reqs:
        return []

    req = mach_reqs[0]
    mc = req.machine_class
    candidates: list[MachineCandidate] = []

    # Primary candidate — the minimum class that satisfies the requirement
    primary_name = _machine_generic_name(mc)
    primary_rationale = _machine_rationale(req)

    candidates.append(
        MachineCandidate(
            machine_id=_uid("MC-"),
            machine_name=primary_name,
            machine_class=mc,
            match_status=MatchStatus.COMPATIBLE,
            matched_requirements=(req.requirement_id,),
            unknown_requirements=_unknown_req_labels(req),
            evidence_notes=req.evidence_notes,
            rationale=primary_rationale,
        )
    )

    # Alternative candidates — more-capable classes are always viable
    if mc == MachineClassV5.THREE_AXIS_VMC:
        # Drilling-only: add drill-tap-centre as lower-cost alternative
        if req.drilling_required and not req.milling_required:
            candidates.append(
                MachineCandidate(
                    machine_id=_uid("MC-"),
                    machine_name="Drill-and-Tap Centre (candidate — drilling only)",
                    machine_class=MachineClassV5.DRILL_TAP_CENTER,
                    match_status=MatchStatus.PARTIALLY_COMPATIBLE,
                    matched_requirements=(req.requirement_id,),
                    unknown_requirements=_unknown_req_labels(req),
                    warnings=(
                        "Drill-and-tap centre is suitable for drilling operations; "
                        "milling capability is limited — verify before selection",
                    ),
                    evidence_notes=req.evidence_notes,
                    rationale=(
                        "Alternative: drill-and-tap centre meets drilling requirement; "
                        "partially compatible because future milling needs are unconfirmed"
                    ),
                )
            )
        # 4-axis VMC as a more-capable alternative
        candidates.append(
            MachineCandidate(
                machine_id=_uid("MC-"),
                machine_name="4-Axis Vertical Machining Centre (candidate — exceeds requirement)",
                machine_class=MachineClassV5.FOUR_AXIS_VMC,
                match_status=MatchStatus.COMPATIBLE,
                matched_requirements=(req.requirement_id,),
                unknown_requirements=_unknown_req_labels(req),
                evidence_notes=req.evidence_notes,
                rationale=(
                    "Alternative: 4-axis VMC exceeds 3-axis requirement; "
                    "viable if multi-setup reduction is desirable"
                ),
            )
        )

    elif mc == MachineClassV5.FOUR_AXIS_VMC:
        candidates.append(
            MachineCandidate(
                machine_id=_uid("MC-"),
                machine_name="5-Axis Vertical Machining Centre (candidate — exceeds requirement)",
                machine_class=MachineClassV5.FIVE_AXIS_VMC,
                match_status=MatchStatus.COMPATIBLE,
                matched_requirements=(req.requirement_id,),
                unknown_requirements=_unknown_req_labels(req),
                evidence_notes=req.evidence_notes,
                rationale=(
                    "Alternative: 5-axis VMC exceeds 4-axis requirement; "
                    "viable for single-setup machining"
                ),
            )
        )

    elif mc == MachineClassV5.CNC_LATHE and req.milling_required:
        # Turning + milling → turn-mill is the better fit
        candidates.append(
            MachineCandidate(
                machine_id=_uid("MC-"),
                machine_name="Turn-Mill Centre (candidate — milling also required)",
                machine_class=MachineClassV5.TURN_MILL,
                match_status=MatchStatus.COMPATIBLE,
                matched_requirements=(req.requirement_id,),
                unknown_requirements=_unknown_req_labels(req),
                evidence_notes=req.evidence_notes,
                rationale="Turn-mill centre meets both turning and milling requirements",
            )
        )

    return candidates


def _machine_generic_name(machine_class: object) -> str:
    from backend.interoperability.machine_tool_intelligence import MachineClassV5

    _names: dict[str, str] = {
        MachineClassV5.THREE_AXIS_VMC: (
            "3-Axis Vertical Machining Centre (candidate)"
        ),
        MachineClassV5.FOUR_AXIS_VMC: (
            "4-Axis Vertical Machining Centre (candidate)"
        ),
        MachineClassV5.FIVE_AXIS_VMC: (
            "5-Axis Vertical Machining Centre (candidate)"
        ),
        MachineClassV5.HMC: "Horizontal Machining Centre (candidate)",
        MachineClassV5.CNC_LATHE: "CNC Lathe (candidate)",
        MachineClassV5.TURN_MILL: "Turn-Mill Centre (candidate)",
        MachineClassV5.SWISS_LATHE: "Swiss-Type Lathe (candidate)",
        MachineClassV5.DRILL_TAP_CENTER: "Drill-and-Tap Centre (candidate)",
        MachineClassV5.SURFACE_GRINDER: "Surface Grinder (candidate)",
        MachineClassV5.CYLINDRICAL_GRINDER: "Cylindrical Grinder (candidate)",
        MachineClassV5.WIRE_EDM: "Wire EDM (candidate)",
        MachineClassV5.SINKER_EDM: "Sinker EDM (candidate)",
        MachineClassV5.MANUAL_REVIEW: "Manual Review Required",
        MachineClassV5.UNKNOWN: "Machine class unknown — requires input",
    }
    return _names.get(str(machine_class), f"Machine class: {machine_class} (candidate)")


def _machine_rationale(req: object) -> str:
    parts: list[str] = []
    if getattr(req, "drilling_required", False):
        parts.append("drilling operations present")
    if getattr(req, "milling_required", False):
        parts.append("milling operations present")
    if getattr(req, "turning_required", False):
        parts.append("turning indicator active")
    if getattr(req, "grinding_required", False):
        parts.append("grinding operations present")
    if getattr(req, "edm_required", False):
        parts.append("EDM operations present")
    axes = getattr(req, "required_axes", 3)
    parts.append(f"minimum {axes} axes required")
    rotary = getattr(req, "required_rotary_axes", 0)
    if rotary > 0:
        parts.append(f"{rotary} rotary axis/axes required")
    return "; ".join(parts) if parts else "derived from operation set"


def _unknown_req_labels(req: object) -> tuple[str, ...]:
    """Labels for requirements that could not be evaluated (None fields)."""
    unknown: list[str] = []
    for attr in (
        "min_x_travel_mm", "min_y_travel_mm", "min_z_travel_mm",
        "min_spindle_speed_rpm", "min_spindle_power_kw", "min_spindle_torque_nm",
    ):
        if getattr(req, attr, None) is None:
            unknown.append(attr)
    return tuple(unknown)


# ---------------------------------------------------------------------------
# Phase 3: Tool capability requirements
# ---------------------------------------------------------------------------


def _derive_tool_capability_requirements(pi: object) -> list:
    """Map Level-4 tool requirements to Level-5 tool capability requirements."""
    from backend.interoperability.machine_tool_intelligence import (
        ToolCapabilityRequirement,
    )
    from backend.interoperability.process_intelligence import (
        ProcessStatus,
        RoughingOrFinishing,
    )

    l4_tool_reqs = getattr(pi, "tool_requirements", ())
    ops = getattr(pi, "process_candidates", ())
    op_map = {op.operation_id: op for op in ops}

    results: list[ToolCapabilityRequirement] = []

    for tr in l4_tool_reqs:
        op_id = getattr(tr, "operation_id", "")
        op = op_map.get(op_id)
        roughing = (
            getattr(op, "roughing_or_finishing", None) == RoughingOrFinishing.ROUGHING
            if op
            else False
        )
        finishing = (
            getattr(op, "roughing_or_finishing", None) == RoughingOrFinishing.FINISHING
            if op
            else False
        )
        op_status = getattr(op, "status", None)
        is_candidate = op_status != ProcessStatus.CONFIRMED_BY_RULE

        v5_family = _map_tool_family_to_v5(
            getattr(tr, "tool_family", None), roughing=roughing, finishing=finishing
        )

        feature_refs = tuple(getattr(op, "feature_ids", ())) if op else ()
        req_status = "CANDIDATE" if is_candidate else "CONFIRMED_BY_RULE"

        results.append(
            ToolCapabilityRequirement(
                requirement_id=_uid("TCR-"),
                tool_family=v5_family,
                operation_ref=op_id,
                feature_refs=feature_refs,
                min_diameter_mm=getattr(tr, "min_diameter_mm", None),
                max_diameter_mm=getattr(tr, "max_diameter_mm", None),
                min_reach_mm=getattr(tr, "required_reach_mm", None),
                access_direction=getattr(tr, "access_direction", None),
                basis=getattr(tr, "basis", ""),
                evidence_notes=getattr(tr, "evidence_notes", ""),
                status=req_status,
            )
        )

    return results


def _map_tool_family_to_v5(
    l4_family: object, roughing: bool = False, finishing: bool = False
) -> object:
    """Map a Level-4 ToolFamily value to its Level-5 ToolFamilyV5 equivalent."""
    from backend.interoperability.machine_tool_intelligence import ToolFamilyV5
    from backend.interoperability.process_intelligence import ToolFamily

    if l4_family is None:
        return ToolFamilyV5.UNKNOWN

    # Pass-through for families with 1:1 correspondence
    _direct: dict[str, str] = {
        ToolFamily.DRILL: ToolFamilyV5.DRILL,
        ToolFamily.CENTER_DRILL: ToolFamilyV5.CENTER_DRILL,
        ToolFamily.REAMER: ToolFamilyV5.REAMER,
        ToolFamily.BORING_BAR: ToolFamilyV5.BORING_BAR,
        ToolFamily.TAP: ToolFamilyV5.TAP,
        ToolFamily.THREAD_MILL: ToolFamilyV5.THREAD_MILL,
        ToolFamily.FACE_MILL: ToolFamilyV5.FACE_MILL,
        ToolFamily.CHAMFER_MILL: ToolFamilyV5.CHAMFER_MILL,
        ToolFamily.SLOT_MILL: ToolFamilyV5.SLOT_MILL,
        ToolFamily.TURNING_INSERT: ToolFamilyV5.TURNING_INSERT,
        ToolFamily.GROOVING_TOOL: ToolFamilyV5.GROOVING_TOOL,
        ToolFamily.BALL_NOSE_END_MILL: ToolFamilyV5.BALL_END_MILL,
    }
    s = str(l4_family)
    if s in _direct:
        return _direct[s]

    # END_MILL — finer distinction based on pass type
    if s == ToolFamily.END_MILL:
        if roughing:
            return ToolFamilyV5.ROUGHING_END_MILL
        if finishing:
            return ToolFamilyV5.FINISH_END_MILL
        return ToolFamilyV5.END_MILL

    return ToolFamilyV5.UNKNOWN


# ---------------------------------------------------------------------------
# Phase 4: Tool candidates
# ---------------------------------------------------------------------------


def _select_tool_candidates(tool_reqs: list) -> list:
    """Derive tool family candidates from tool capability requirements."""
    from backend.interoperability.machine_tool_intelligence import (
        MatchStatus,
        ToolCandidate,
        ToolFamilyV5,
    )

    candidates: list[ToolCandidate] = []

    for tr in tool_reqs:
        family = getattr(tr, "tool_family", ToolFamilyV5.UNKNOWN)
        op_ref = getattr(tr, "operation_ref", "")
        req_id = getattr(tr, "requirement_id", "")
        status_str = getattr(tr, "status", "CANDIDATE")

        # Unknown family → UNKNOWN match
        if str(family) == ToolFamilyV5.UNKNOWN:
            candidates.append(
                ToolCandidate(
                    candidate_id=_uid("TC-"),
                    tool_family=ToolFamilyV5.UNKNOWN,
                    operation_ref=op_ref,
                    match_status=MatchStatus.UNKNOWN,
                    unknown_requirements=(req_id,),
                    warnings=("Tool family could not be determined from operation evidence",),
                    rationale="Tool family unknown — additional operation evidence required",
                )
            )
            continue

        # Diameter unknown → PARTIALLY_COMPATIBLE (family known, size unknown)
        min_d = getattr(tr, "min_diameter_mm", None)
        max_d = getattr(tr, "max_diameter_mm", None)
        diameter_known = min_d is not None or max_d is not None

        if not diameter_known:
            match = MatchStatus.PARTIALLY_COMPATIBLE
            unknown_reqs: tuple[str, ...] = ("nominal_diameter_mm",)
            warns: tuple[str, ...] = (
                "Tool diameter not derivable from 2D or feature evidence; "
                "verify before tool selection",
            )
        else:
            match = MatchStatus.COMPATIBLE
            unknown_reqs = ()
            warns = ()

        # Preserve CANDIDATE status from L4
        final_status = "CANDIDATE" if status_str == "CANDIDATE" else status_str

        rationale = _tool_rationale(family, op_ref, final_status)

        candidates.append(
            ToolCandidate(
                candidate_id=_uid("TC-"),
                tool_family=family,
                operation_ref=op_ref,
                match_status=match,
                matched_requirements=(req_id,),
                unknown_requirements=unknown_reqs,
                warnings=warns,
                rationale=rationale,
            )
        )

    return candidates


def _tool_rationale(family: object, op_ref: str, status: str) -> str:
    return (
        f"{family} family selected from operation evidence "
        f"(operation: {op_ref}; confidence: {status})"
    )


# ---------------------------------------------------------------------------
# Phase 5: Holder requirements
# ---------------------------------------------------------------------------


def _derive_holder_requirements(tool_reqs: list) -> list:
    """Derive generic holder requirements from tool capability requirements."""
    from backend.interoperability.machine_tool_intelligence import (
        HolderRequirement,
        HolderType,
        ToolFamilyV5,
    )

    # Map tool family → preferred holder type (generic, not catalog-specific)
    _holder_map: dict[str, str] = {
        ToolFamilyV5.DRILL: HolderType.ER_COLLET,
        ToolFamilyV5.CENTER_DRILL: HolderType.ER_COLLET,
        ToolFamilyV5.SPOT_DRILL: HolderType.ER_COLLET,
        ToolFamilyV5.REAMER: HolderType.ER_COLLET,
        ToolFamilyV5.TAP: HolderType.TAPPING_CHUCK,
        ToolFamilyV5.THREAD_MILL: HolderType.ER_COLLET,
        ToolFamilyV5.END_MILL: HolderType.ER_COLLET,
        ToolFamilyV5.ROUGHING_END_MILL: HolderType.MILLING_CHUCK,
        ToolFamilyV5.FINISH_END_MILL: HolderType.ER_COLLET,
        ToolFamilyV5.BALL_END_MILL: HolderType.ER_COLLET,
        ToolFamilyV5.FACE_MILL: HolderType.MILLING_CHUCK,
        ToolFamilyV5.CHAMFER_MILL: HolderType.ER_COLLET,
        ToolFamilyV5.SLOT_MILL: HolderType.ER_COLLET,
        ToolFamilyV5.BORING_BAR: HolderType.BORING_HOLDER,
        ToolFamilyV5.TURNING_INSERT: HolderType.TURNING_TOOLHOLDER,
        ToolFamilyV5.GROOVING_TOOL: HolderType.TURNING_TOOLHOLDER,
        ToolFamilyV5.PARTING_TOOL: HolderType.TURNING_TOOLHOLDER,
    }

    results: list[HolderRequirement] = []

    for tr in tool_reqs:
        family = getattr(tr, "tool_family", ToolFamilyV5.UNKNOWN)
        op_ref = getattr(tr, "operation_ref", "")
        req_id = getattr(tr, "requirement_id", "")
        holder_type = _holder_map.get(str(family), HolderType.UNKNOWN)

        results.append(
            HolderRequirement(
                requirement_id=_uid("HR-"),
                holder_type=holder_type,
                operation_ref=op_ref,
                required_reach_mm=getattr(tr, "min_reach_mm", None),
                basis="tool_family_to_holder_mapping",
                evidence_notes=f"tool_req={req_id} family={family}",
            )
        )

    return results


# ---------------------------------------------------------------------------
# Phase 6: Compatibility checking
# ---------------------------------------------------------------------------


def _check_compatibility(tool_reqs: list, holder_reqs: list) -> list:
    """Run deterministic tool–holder compatibility checks."""
    from backend.interoperability.machine_tool_intelligence import (
        CompatibilityResult,
        HolderType,
        MatchStatus,
        ToolFamilyV5,
    )

    # Compatible combinations (family → holder types that work)
    _compatible: dict[str, set[str]] = {
        ToolFamilyV5.DRILL: {HolderType.ER_COLLET, HolderType.HYDRAULIC_CHUCK,
                              HolderType.SHRINK_FIT, HolderType.SIDE_LOCK},
        ToolFamilyV5.CENTER_DRILL: {HolderType.ER_COLLET},
        ToolFamilyV5.SPOT_DRILL: {HolderType.ER_COLLET},
        ToolFamilyV5.REAMER: {HolderType.ER_COLLET, HolderType.HYDRAULIC_CHUCK},
        ToolFamilyV5.TAP: {HolderType.TAPPING_CHUCK, HolderType.ER_COLLET},
        ToolFamilyV5.THREAD_MILL: {HolderType.ER_COLLET},
        ToolFamilyV5.END_MILL: {HolderType.ER_COLLET, HolderType.HYDRAULIC_CHUCK,
                                 HolderType.SHRINK_FIT, HolderType.MILLING_CHUCK},
        ToolFamilyV5.ROUGHING_END_MILL: {HolderType.MILLING_CHUCK, HolderType.SIDE_LOCK,
                                          HolderType.SHRINK_FIT},
        ToolFamilyV5.FINISH_END_MILL: {HolderType.ER_COLLET, HolderType.HYDRAULIC_CHUCK,
                                        HolderType.SHRINK_FIT},
        ToolFamilyV5.BALL_END_MILL: {HolderType.ER_COLLET, HolderType.HYDRAULIC_CHUCK,
                                      HolderType.SHRINK_FIT},
        ToolFamilyV5.FACE_MILL: {HolderType.MILLING_CHUCK, HolderType.SIDE_LOCK},
        ToolFamilyV5.CHAMFER_MILL: {HolderType.ER_COLLET},
        ToolFamilyV5.SLOT_MILL: {HolderType.ER_COLLET, HolderType.MILLING_CHUCK},
        ToolFamilyV5.BORING_BAR: {HolderType.BORING_HOLDER},
        ToolFamilyV5.TURNING_INSERT: {HolderType.TURNING_TOOLHOLDER},
        ToolFamilyV5.GROOVING_TOOL: {HolderType.TURNING_TOOLHOLDER},
        ToolFamilyV5.PARTING_TOOL: {HolderType.TURNING_TOOLHOLDER},
    }

    results: list[CompatibilityResult] = []

    for tr, hr in zip(tool_reqs, holder_reqs):  # noqa: B905
        family = str(getattr(tr, "tool_family", ""))
        holder = str(getattr(hr, "holder_type", ""))
        tr_id = getattr(tr, "requirement_id", "")
        hr_id = getattr(hr, "requirement_id", "")

        if holder == HolderType.UNKNOWN or family == ToolFamilyV5.UNKNOWN:
            match = MatchStatus.UNKNOWN
            matched: tuple[str, ...] = ()
            failed: tuple[str, ...] = ()
            unknown: tuple[str, ...] = ("tool_family_or_holder_type_unknown",)
        elif holder in _compatible.get(family, set()):
            match = MatchStatus.COMPATIBLE
            matched = ("tool_shank_to_holder_capacity", "operation_type")
            failed = ()
            # Reach unknown → partial caveat
            reach = getattr(tr, "min_reach_mm", None)
            unknown = ("required_reach_mm",) if reach is None else ()
            if unknown:
                match = MatchStatus.PARTIALLY_COMPATIBLE
        else:
            match = MatchStatus.INCOMPATIBLE
            matched = ()
            failed = ("holder_type_incompatible_with_tool_family",)
            unknown = ()

        results.append(
            CompatibilityResult(
                result_id=_uid("COMPAT-"),
                tool_requirement_id=tr_id,
                holder_requirement_id=hr_id,
                match_status=match,
                matched_constraints=matched,
                failed_constraints=failed,
                unknown_constraints=unknown,
                evidence_notes=f"tool={family} holder={holder}",
            )
        )

    return results
