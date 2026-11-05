"""Level 7 — Cycle Time and Manufacturing Performance Intelligence engine.

Derives CycleTimeIntelligenceResult from Level-6 CuttingDataIntelligenceResult
and optional geometry input.  All calculations are deterministic and traceable.

HARD RULES:
  - Do NOT fabricate cycle time, toolpath length, machining distance.
  - Do NOT fabricate setup time, tool-change time, rapid time.
  - Do NOT fabricate removal volume or MRR.
  - Do NOT fabricate machine utilization or OEE.
  - UNKNOWN values MUST remain None — never become zero.
  - CAD data alone MUST NOT produce OEE.
  - Approximate path MUST NOT be represented as exact toolpath.
"""

from __future__ import annotations

import uuid

from backend.interoperability.cutting_data_intelligence import (
    CuttingDataCandidate,
    CuttingDataIntelligenceResult,
)
from backend.interoperability.cycle_time_intelligence import (
    UNKNOWN_TIME,
    BatchTimeResult,
    BottleneckFoundation,
    CycleTimeFidelity,
    CycleTimeIntelligenceResult,
    CycleTimePlanStatus,
    OEEFoundation,
    OperationTimeResult,
    OperationTimeStatus,
    OptimizationOpportunity,
    OptimizationOpportunityType,
    PartCycleTime,
    PerformanceObservation,
    PerformanceObservationType,
    RemovalVolumeResult,
    SetupTimeEvidence,
    SetupTimeSource,
    SpindleCuttingUtilization,
    TimeEvidenceSourceType,
    ToolChangeTimeEvidence,
    ToolChangeTimeSource,
    ToolLifeConsumptionResult,
    calculate_drilling_time,
    calculate_mrr_based_time,
    calculate_spindle_utilization,
    calculate_tool_life_consumption,
    compare_time_methods,
)


def _make_plan_id() -> str:
    return f"CTI-{uuid.uuid4().hex[:12].upper()}"


def _get_hole_depth(geometry: object | None) -> float | None:
    """Extract the best available hole-depth estimate from canonical geometry.

    For 2-D DXF geometry the depth dimension is NOT available from the drawing
    alone — circles represent hole projections but carry no axial information.
    Returns None when depth cannot be reliably derived.
    """
    if geometry is None:
        return None
    try:
        from backend.interoperability.geometry import CanonicalGeometry
        if not isinstance(geometry, CanonicalGeometry):
            return None
        bbox = geometry.bounding_box
        if bbox is None:
            return None
        # 2-D DXF: z-extent is 0 — no depth information available.
        z_size = (
            bbox.max_z - bbox.min_z
            if (bbox.max_z is not None and bbox.min_z is not None)
            else 0.0
        )
        if z_size <= 0.001:
            return None
        return float(z_size)
    except Exception:
        return None


def _get_representative_diameter(candidate: CuttingDataCandidate) -> float | None:
    """Return the nominal diameter from the cutting data record if available."""
    if candidate.rpm_result.is_calculable:
        return None  # We already have rpm — no need to back-derive diameter
    return None


def _build_operation_time(
    candidate: CuttingDataCandidate,
    geometry: object | None,
    op_index: int,
) -> OperationTimeResult:
    """Build OperationTimeResult for one cutting data candidate.

    Attempts:
    1. Drilling time from depth + rpm + fn (when available).
    2. MRR-based time from removal volume + MRR (when geometry supports it).
    3. Path-based cutting time (requires cutting distance — not available from
       pure 2-D DXF/IGES geometry → UNKNOWN for real production files).

    Unknown components remain UNKNOWN — never coerced to zero.
    """
    op_ref = f"OP-{op_index + 1:02d}-{candidate.operation.value}"
    op_type = candidate.operation.value
    warns: list[str] = []
    unknown_comps: list[str] = []

    # --- Feed rate from Level 6 ---
    rpm_nominal: float | None = candidate.rpm_result.n_nominal

    # --- Determine cutting time ---
    cutting_time = UNKNOWN_TIME
    path_based_time = UNKNOWN_TIME
    mrr_based_time = UNKNOWN_TIME
    path_fidelity = None
    removal_volume = RemovalVolumeResult(geometry_basis="")

    op_value = candidate.operation.value

    is_drilling = op_value in ("DRILLING", "PECK_DRILLING", "CENTER_DRILLING",
                               "REAMING", "BORING", "TAPPING")
    is_milling = op_value in ("FACE_MILLING", "ROUGH_MILLING", "FINISH_MILLING",
                               "POCKET_MILLING", "SLOT_MILLING", "CONTOUR_MILLING",
                               "CHAMFERING", "THREAD_MILLING")
    is_turning = op_value in ("TURNING", "FACING", "GROOVING", "PARTING")

    if is_drilling:
        hole_depth = _get_hole_depth(geometry)
        # fn from the feed_range (if available)
        fn_mm_per_rev = candidate.feed_range.nominal_val if candidate.feed_range.is_known else None

        if hole_depth is not None and rpm_nominal is not None and fn_mm_per_rev is not None:
            cutting_time = calculate_drilling_time(
                depth_mm=hole_depth,
                rpm=rpm_nominal,
                fn_mm_per_rev=fn_mm_per_rev,
                source_type=TimeEvidenceSourceType.GEOMETRY_DERIVED,
                evidence_note=(
                    "depth from geometry bbox, fn from L6 candidate"
                    f" {candidate.candidate_id}"
                ),
            )
            path_fidelity = "DERIVED_GEOMETRIC_PATH"

            # Also try removal volume + MRR for cylindrical hole
            if candidate.rpm_result.is_calculable:
                # We have RPM but need diameter — L6 candidate has no diameter stored
                # Removal volume requires diameter → UNKNOWN
                removal_volume = RemovalVolumeResult(
                    geometry_basis="cylindrical_hole",
                    warnings=("tool_diameter not available from candidate record",),
                )
        else:
            unknown_comps.append(TimeEvidenceSourceType.GEOMETRY_DERIVED.value)
            if hole_depth is None:
                unknown_comps.append("HOLE_DEPTH")
            if rpm_nominal is None:
                unknown_comps.append("RPM")
            if fn_mm_per_rev is None:
                unknown_comps.append("FEED_PER_REV")
            path_fidelity = "UNKNOWN"

        # MRR-based time for drilling — need removal volume
        if candidate.mrr_result.is_calculable and removal_volume.is_known:
            mrr_based_time = calculate_mrr_based_time(
                removal_volume_mm3=removal_volume.volume_mm3,
                mrr_mm3_per_min=candidate.mrr_result.mrr_nominal,
                source_type=TimeEvidenceSourceType.CUTTING_DATA_DERIVED,
                evidence_note=f"MRR from L6 candidate {candidate.candidate_id}",
            )

    elif is_milling or is_turning:
        # For milling/turning, cutting distance requires CAM toolpath or feature geometry.
        # 2-D CAD (DXF/IGES) does NOT provide verified cutting distance.
        # Feature perimeter ≠ exact toolpath → label UNKNOWN or FEATURE_DIMENSION_BASED.
        unknown_comps.append("CUTTING_DISTANCE")
        path_fidelity = "UNKNOWN"
        warns.append(
            "Cutting distance not derivable from 2-D CAD geometry — cutting time UNKNOWN."
        )

        # MRR-based estimate if removal volume geometry is known
        if candidate.mrr_result.is_calculable and removal_volume.is_known:
            mrr_based_time = calculate_mrr_based_time(
                removal_volume_mm3=removal_volume.volume_mm3,
                mrr_mm3_per_min=candidate.mrr_result.mrr_nominal,
                source_type=TimeEvidenceSourceType.CUTTING_DATA_DERIVED,
                evidence_note=f"MRR from L6 candidate {candidate.candidate_id}",
            )
        else:
            unknown_comps.append("REMOVAL_VOLUME")

    else:
        unknown_comps.append("CUTTING_DISTANCE")
        path_fidelity = "UNKNOWN"

    # --- Tool change time: UNKNOWN unless evidence provided ---
    tool_change_time = ToolChangeTimeEvidence(
        source=ToolChangeTimeSource.UNKNOWN,
        evidence_notes="No machine-specific or observed tool-change data provided.",
    )
    unknown_comps.append("TOOL_CHANGE_TIME")

    # --- Rapid / positioning time: UNKNOWN unless rapid rate and distance known ---
    rapid_time = UNKNOWN_TIME
    positioning_time = UNKNOWN_TIME
    unknown_comps.append("RAPID_TIME")
    unknown_comps.append("POSITIONING_TIME")

    # --- Setup component: UNKNOWN unless evidence provided ---
    setup_component = SetupTimeEvidence(
        source=SetupTimeSource.UNKNOWN,
        evidence_notes="Setup time not derivable from CAD geometry alone.",
    )
    unknown_comps.append("SETUP_TIME")

    # --- Determine known_time and status ---
    known_times: list[float] = []
    if cutting_time.is_known and cutting_time.value is not None:
        known_times.append(cutting_time.value)
    elif path_based_time.is_known and path_based_time.value is not None:
        known_times.append(path_based_time.value)

    known_time_total = sum(known_times) if known_times else None

    if known_time_total is not None:
        status = OperationTimeStatus.PARTIAL
    else:
        status = OperationTimeStatus.INSUFFICIENT_DATA

    # Method comparison
    method_comp = compare_time_methods(
        path_based_time_min=cutting_time.value if cutting_time.is_known else path_based_time.value,
        mrr_based_time_min=mrr_based_time.value if mrr_based_time.is_known else None,
    )

    from backend.interoperability.cycle_time_intelligence import PathFidelity
    pf_map = {
        "EXACT_TOOLPATH": PathFidelity.EXACT_TOOLPATH,
        "DERIVED_GEOMETRIC_PATH": PathFidelity.DERIVED_GEOMETRIC_PATH,
        "APPROXIMATE_PATH": PathFidelity.APPROXIMATE_PATH,
        "FEATURE_DIMENSION_BASED": PathFidelity.FEATURE_DIMENSION_BASED,
        "UNKNOWN": PathFidelity.UNKNOWN,
        None: PathFidelity.UNKNOWN,
    }
    path_fidelity_enum = pf_map.get(path_fidelity, PathFidelity.UNKNOWN)

    return OperationTimeResult(
        operation_ref=op_ref,
        operation_type=op_type,
        cutting_time=cutting_time,
        rapid_time=rapid_time,
        positioning_time=positioning_time,
        tool_change_time=tool_change_time,
        setup_component=setup_component,
        other_non_cutting_time=UNKNOWN_TIME,
        path_based_time=path_based_time,
        mrr_based_time=mrr_based_time,
        method_comparison=method_comp,
        removal_volume=removal_volume,
        path_fidelity=path_fidelity_enum,
        known_time_min=known_time_total,
        unknown_components=tuple(dict.fromkeys(unknown_comps)),
        status=status,
        evidence=(f"L6 candidate {candidate.candidate_id}",),
        warnings=tuple(warns),
    )


def _build_part_cycle_time(
    operations: tuple[OperationTimeResult, ...],
) -> PartCycleTime:
    """Aggregate operation times into a PartCycleTime.

    When significant components remain unknown:
    do NOT report exact total cycle time.
    """
    known_cutting: list[float] = []
    all_unknown: list[str] = []

    for op in operations:
        t = op.cutting_time.value
        if t is not None:
            known_cutting.append(t)
        elif op.path_based_time.value is not None:
            known_cutting.append(op.path_based_time.value)
        for uc in op.unknown_components:
            if uc not in all_unknown:
                all_unknown.append(uc)

    total_known_cutting = sum(known_cutting) if known_cutting else None

    has_unknown_critical = bool(all_unknown)

    # Non-cutting: tool change, setup, rapid — all UNKNOWN for CAD-only input
    known_non_cutting = None

    # Total: only if no significant unknowns
    if total_known_cutting is not None and not has_unknown_critical:
        known_total = total_known_cutting
        status = OperationTimeStatus.PARTIAL
    elif total_known_cutting is not None:
        known_total = None  # don't present as final
        status = OperationTimeStatus.PARTIAL
    else:
        known_total = None
        status = OperationTimeStatus.INSUFFICIENT_DATA

    # Fidelity
    if not operations:
        fidelity = CycleTimeFidelity.INSUFFICIENT
    elif status == OperationTimeStatus.INSUFFICIENT_DATA:
        fidelity = CycleTimeFidelity.INSUFFICIENT
    elif has_unknown_critical:
        fidelity = CycleTimeFidelity.LOW
    else:
        fidelity = CycleTimeFidelity.MEDIUM

    return PartCycleTime(
        known_cutting_time_min=total_known_cutting,
        known_non_cutting_time_min=known_non_cutting,
        known_total_time_min=known_total,
        unknown_components=tuple(dict.fromkeys(all_unknown)),
        cycle_time_status=status,
        cycle_time_fidelity=fidelity,
    )


def _build_bottleneck(
    operations: tuple[OperationTimeResult, ...],
) -> BottleneckFoundation:
    """Identify bottleneck from known operation times only."""
    if not operations:
        return BottleneckFoundation(status="NO_OPERATIONS")

    known_ops = [
        op for op in operations
        if op.known_time_min is not None
    ]
    if not known_ops:
        return BottleneckFoundation(status="ALL_UNKNOWN")

    longest = max(known_ops, key=lambda op: op.known_time_min or 0.0)
    highest_cut = max(
        (op for op in known_ops if op.cutting_time.is_known),
        key=lambda op: op.cutting_time.value or 0.0,
        default=None,
    )

    return BottleneckFoundation(
        longest_known_operation_ref=longest.operation_ref,
        longest_known_time_min=longest.known_time_min,
        highest_cutting_time_op_ref=highest_cut.operation_ref if highest_cut else None,
        highest_cutting_time_min=highest_cut.cutting_time.value if highest_cut else None,
        status="IDENTIFIED",
    )


def _build_observations(
    operations: tuple[OperationTimeResult, ...],
    part_cycle: PartCycleTime,
) -> tuple[PerformanceObservation, ...]:
    """Generate evidence-based performance observations."""
    obs: list[PerformanceObservation] = []

    if part_cycle.cycle_time_status == OperationTimeStatus.INSUFFICIENT_DATA:
        obs.append(PerformanceObservation(
            observation_type=PerformanceObservationType.CYCLE_TIME_INCOMPLETE,
            description="Cycle time could not be fully computed from available CAD data.",
            evidence="Cutting distance / depth not derivable from 2-D geometry alone.",
        ))

    if any("SETUP_TIME" in op.unknown_components for op in operations):
        obs.append(PerformanceObservation(
            observation_type=PerformanceObservationType.SETUP_TIME_UNKNOWN,
            description="Setup time is UNKNOWN — no setup evidence provided.",
            evidence="Number of setup candidates alone does not create setup time.",
        ))

    for op in operations:
        from backend.interoperability.cycle_time_intelligence import PathFidelity
        if op.path_fidelity in (PathFidelity.UNKNOWN, PathFidelity.APPROXIMATE_PATH):
            obs.append(PerformanceObservation(
                observation_type=PerformanceObservationType.PATH_FIDELITY_LOW,
                description=f"Path fidelity LOW for operation {op.operation_ref}.",
                evidence=f"path_fidelity={op.path_fidelity.value}",
            ))
            break

    # Check for multiple tool changes
    if len(operations) > 2:
        obs.append(PerformanceObservation(
            observation_type=PerformanceObservationType.MULTIPLE_TOOL_CHANGE_CANDIDATE,
            description=f"{len(operations)} operations detected — multiple tool changes likely.",
            evidence=f"operation_count={len(operations)}",
        ))

    return tuple(obs)


def _build_optimization_opportunities(
    operations: tuple[OperationTimeResult, ...],
) -> tuple[OptimizationOpportunity, ...]:
    """Flag optimization opportunities — candidates only, no guaranteed savings."""
    opps: list[OptimizationOpportunity] = []

    if operations:
        opps.append(OptimizationOpportunity(
            opportunity_type=OptimizationOpportunityType.CUTTING_DATA_REVIEW_CANDIDATE,
            description=(
                "Cutting data candidates from generic reference ranges —"
                " vendor-verified data may improve cycle time."
            ),
            evidence="source_type=GENERIC_REFERENCE_RANGE",
        ))

    if len(operations) > 1:
        opps.append(OptimizationOpportunity(
            opportunity_type=OptimizationOpportunityType.TOOL_CHANGE_REDUCTION_CANDIDATE,
            description="Multiple operations detected — review tool-change strategy.",
            evidence=f"operation_count={len(operations)}",
        ))

    return tuple(opps)


def _compute_plan_fidelity(
    operations: tuple[OperationTimeResult, ...],
    part_cycle: PartCycleTime,
    has_verified_cutting_data: bool,
) -> CycleTimeFidelity:
    """Determine plan-level cycle time fidelity.

    HIGH: exact path + verified cutting data + verified aux components.
    MEDIUM: derived geometric path + verified cutting data + some aux evidence.
    LOW: generic-reference inputs or incomplete non-cutting times.
    INSUFFICIENT: critical inputs missing.
    """
    if not operations or part_cycle.cycle_time_status == OperationTimeStatus.INSUFFICIENT_DATA:
        return CycleTimeFidelity.INSUFFICIENT

    from backend.interoperability.cycle_time_intelligence import PathFidelity
    any_exact = any(op.path_fidelity == PathFidelity.EXACT_TOOLPATH for op in operations)
    any_derived = any(op.path_fidelity == PathFidelity.DERIVED_GEOMETRIC_PATH for op in operations)

    if any_exact and has_verified_cutting_data:
        return CycleTimeFidelity.HIGH
    elif any_derived and has_verified_cutting_data:
        return CycleTimeFidelity.MEDIUM
    elif part_cycle.cycle_time_status == OperationTimeStatus.PARTIAL:
        return CycleTimeFidelity.LOW
    else:
        return CycleTimeFidelity.INSUFFICIENT


def derive_cycle_time_intelligence(
    cdi_result: CuttingDataIntelligenceResult | None,
    geometry: object | None = None,
) -> CycleTimeIntelligenceResult:
    """Derive CycleTimeIntelligenceResult from Level-6 cutting data.

    Parameters
    ----------
    cdi_result:
        Level-6 CuttingDataIntelligenceResult.  None → INSUFFICIENT_DATA.
    geometry:
        CanonicalGeometry from Level-2 (optional).  None → no geometry-derived
        times are computed.

    Returns
    -------
    CycleTimeIntelligenceResult with status PARTIAL or INSUFFICIENT_DATA.
    Status COMPLETE requires all major time components to be known.
    """
    plan_id = _make_plan_id()

    if cdi_result is None:
        return CycleTimeIntelligenceResult(
            plan_id=plan_id,
            status=CycleTimePlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NO_CUTTING_DATA",
            missing_inputs=("cdi_result",),
            warnings=("No Level-6 cutting data result provided.",),
        )

    candidates = cdi_result.cutting_data_candidates
    if not candidates:
        return CycleTimeIntelligenceResult(
            plan_id=plan_id,
            status=CycleTimePlanStatus.INSUFFICIENT_DATA,
            recognition_basis="NO_CUTTING_DATA_CANDIDATES",
            source_cdi_candidate_count=0,
            missing_inputs=("cutting_data_candidates",),
            warnings=("No cutting data candidates from Level 6.",),
        )

    # Build per-operation time results
    operations = tuple(
        _build_operation_time(candidate, geometry, i)
        for i, candidate in enumerate(candidates)
    )

    part_cycle = _build_part_cycle_time(operations)

    # Tool-life consumption — only where validated tool life exists
    # Level-6 candidates do not carry validated tool-life by default
    tool_life_summary: tuple[ToolLifeConsumptionResult, ...] = ()
    for op in operations:
        if op.cutting_time.is_known and op.cutting_time.value is not None:
            # Look for tool-life evidence in cdi_result
            if cdi_result.tool_life_evidence:
                for tle in cdi_result.tool_life_evidence:
                    tl_min = tle.compute_taylor_life()
                    if tl_min is not None:
                        consumption = calculate_tool_life_consumption(
                            cutting_time_min=op.cutting_time.value,
                            available_tool_life_min=tl_min,
                            operation_ref=op.operation_ref,
                            tool_life_source=tle.source_type.value,
                        )
                        tool_life_summary = (*tool_life_summary, consumption)
            else:
                # No validated tool-life data
                tool_life_summary = (
                    *tool_life_summary,
                    ToolLifeConsumptionResult(
                        operation_ref=op.operation_ref,
                        cutting_time_min=op.cutting_time.value,
                        status="UNKNOWN",
                        warnings=("No validated tool-life data available.",),
                    ),
                )

    # Spindle utilization (only where cycle time is sufficiently complete)
    spindle_util = SpindleCuttingUtilization(status="UNKNOWN")
    if (
        part_cycle.known_cutting_time_min is not None
        and part_cycle.known_total_time_min is not None
    ):
        spindle_util = calculate_spindle_utilization(
            cutting_time_min=part_cycle.known_cutting_time_min,
            known_cycle_time_min=part_cycle.known_total_time_min,
        )
    elif part_cycle.known_cutting_time_min is not None:
        spindle_util = SpindleCuttingUtilization(
            cutting_time_min=part_cycle.known_cutting_time_min,
            status="UNKNOWN",
            warnings=("known_cycle_time incomplete — total cycle time not available.",),
        )

    # OEE — always INSUFFICIENT_PRODUCTION_DATA for CAD-only input
    oee = OEEFoundation(
        status="INSUFFICIENT_PRODUCTION_DATA",
        notes="CAD data alone is insufficient to compute OEE.",
    )

    # Batch time foundation (all UNKNOWN for CAD-only input)
    batch_time = BatchTimeResult(
        status="INSUFFICIENT_DATA",
        warnings=("Batch time requires setup_time and quantity — not available from CAD.",),
    )

    # Bottleneck analysis
    bottleneck = _build_bottleneck(operations)

    # Overall method comparison (aggregate)
    all_path_times = [
        op.cutting_time.value for op in operations
        if op.cutting_time.is_known and op.cutting_time.value is not None
    ]
    all_mrr_times = [
        op.mrr_based_time.value for op in operations
        if op.mrr_based_time.is_known and op.mrr_based_time.value is not None
    ]
    agg_path = sum(all_path_times) if all_path_times else None
    agg_mrr = sum(all_mrr_times) if all_mrr_times else None
    method_comp = compare_time_methods(agg_path, agg_mrr)

    # Performance observations
    observations = _build_observations(operations, part_cycle)

    # Optimization opportunities
    opt_opps = _build_optimization_opportunities(operations)

    # Fidelity
    fidelity = _compute_plan_fidelity(
        operations=operations,
        part_cycle=part_cycle,
        has_verified_cutting_data=cdi_result.has_verified_candidates,
    )

    # Plan status
    if part_cycle.cycle_time_status == OperationTimeStatus.PARTIAL:
        plan_status = CycleTimePlanStatus.PARTIAL
    else:
        plan_status = CycleTimePlanStatus.INSUFFICIENT_DATA

    # Missing inputs
    missing: list[str] = []
    if not geometry:
        missing.append("GEOMETRY")
    missing.extend([
        "CUTTING_DISTANCE",
        "TOOL_CHANGE_TIME",
        "SETUP_TIME",
        "RAPID_TIME",
        "LOAD_UNLOAD_TIME",
        "INSPECTION_TIME",
    ])

    return CycleTimeIntelligenceResult(
        plan_id=plan_id,
        status=plan_status,
        recognition_basis=f"L6:{cdi_result.recognition_basis}",
        operation_time_results=operations,
        part_cycle_time=part_cycle,
        batch_time_foundation=batch_time,
        tool_life_consumption_summary=tool_life_summary,
        spindle_cutting_utilization=spindle_util,
        oee_foundation=oee,
        method_comparison=method_comp,
        bottleneck_foundation=bottleneck,
        performance_observations=observations,
        optimization_opportunities=opt_opps,
        fidelity=fidelity,
        missing_inputs=tuple(missing),
        warnings=(),
        source_cdi_candidate_count=len(candidates),
    )
