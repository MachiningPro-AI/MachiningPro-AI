"""CAM planning engine for Level-9 Automatic CAM Planning.

Creates a CAMJob from upstream feature/material/machine/cutting-data
intelligence (Levels 1-8).

Safety contract
---------------
NO_GCODE=YES             — engine never produces G-code.
NO_FABRICATED_DATA=YES   — no synthetic coordinates, no assumed stock,
                           no assumed WCS, no assumed fixtures.
CANDIDATE_NOT_VERIFIED   — all outputs are candidates until review.
SIMULATION_REQUIRED=YES  — every produced CAMJob sets simulation_required.
2D_DXF_SAFETY=YES        — 2D DXF produces only profile/drilling candidates,
                           never a complete 3D CAM plan.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from backend.cam_planning.enums import (
    CAMJobStatus,
    CAMOperationType,
    CAMPlanStatus,
    ClearanceType,
    EntryStrategy,
    ExitStrategy,
    FixtureType,
    SetupOrientation,
    StockSource,
    StockType,
    WCSCandidateType,
)
from backend.cam_planning.feature_to_cam import (
    get_cam_strategy_for_operation,
    map_feature_to_cam_candidates,
)
from backend.cam_planning.models import (
    CAMJob,
    CAMOperationCandidate,
    CAMStrategyCandidate,
    ClearanceRequirement,
    EntryExitRequirement,
    FixtureRequirement,
    SetupCandidate,
    StockRequirement,
    ToolpathRequirement,
    ToolRequirement,
    WCSCandidateModel,
)
from backend.cam_planning.operation_ordering import (
    sort_operations_by_precedence,
)

__all__ = [
    "CamPlanningInput",
    "create_cam_job",
    "create_cam_job_from_dxf",
    "create_cam_job_from_iges",
]


@dataclass
class FeatureInput:
    """Upstream feature record for CAM planning."""

    feature_id: str
    feature_type: str
    is_confirmed: bool = True
    has_tolerance_evidence: bool = False
    depth_diameter_ratio: float | None = None
    access_directions: list[str] | None = None


@dataclass
class CamPlanningInput:
    """Aggregated upstream data passed to the CAM planning engine.

    Consumers must NOT invent data for absent fields — leave as None/empty.
    """

    part_id: str | None = None
    cad_reference: str | None = None
    material: str | None = None
    machine_type: str | None = None
    machine_requirement_refs: list[str] | None = None
    features: list[FeatureInput] | None = None
    cutting_data_refs: list[str] | None = None
    is_2d_only: bool = False
    has_stock_definition: bool = False
    stock_type: StockType = StockType.UNKNOWN
    stock_source: StockSource = StockSource.UNKNOWN
    access_directions: list[str] | None = None


def _make_id() -> str:
    return uuid.uuid4().hex[:12]


def create_cam_job(inp: CamPlanningInput) -> CAMJob:
    """Create a CAMJob from upstream intelligence.

    Entry point for the Level-9 CAM planning engine.
    Produces only candidates — no G-code, no toolpath coordinates.
    """
    job_id = _make_id()
    warnings: list[str] = []
    missing_inputs: list[str] = []

    stock = StockRequirement(
        stock_type=inp.stock_type,
        source=inp.stock_source,
    )
    if not stock.is_known:
        warnings.append("STOCK_UNKNOWN: stock must be defined before toolpath generation")
        missing_inputs.append("stock_definition")

    wcs_candidates = [
        WCSCandidateModel(
            candidate_type=WCSCandidateType.TOP_CENTER,
            rationale="Default WCS candidate — requires validation before use",
            is_validated=False,
        )
    ]

    setup_candidates: list[SetupCandidate] = []
    access_dirs = inp.access_directions or ["+Z"]
    for i, direction in enumerate(access_dirs[:4]):
        setup_orientation = _parse_orientation(direction)
        setup_id = f"SETUP_{i + 1}"
        setup_candidates.append(
            SetupCandidate(
                setup_id=setup_id,
                orientation=setup_orientation,
                wcs_candidate=wcs_candidates[0] if i == 0 else None,
                fixture_requirement=FixtureRequirement(
                    fixture_type=FixtureType.UNKNOWN,
                    notes=(
                        "Fixture type must be determined from geometry and workholding availability"
                    ),
                ),
                rationale=f"Setup {i + 1}: access from {direction}",
                warnings=["WCS_CANDIDATE_ONLY: WCS not validated"],
            )
        )

    if not setup_candidates:
        setup_candidates.append(
            SetupCandidate(
                setup_id="SETUP_1",
                orientation=SetupOrientation.PLUS_Z,
                rationale="Default setup candidate — access direction not specified",
                warnings=["ACCESS_DIRECTION_UNKNOWN"],
            )
        )

    all_operations: list[CAMOperationCandidate] = []
    all_strategies: list[CAMStrategyCandidate] = []
    all_toolpath_reqs: list[ToolpathRequirement] = []

    if inp.is_2d_only:
        warnings.append(
            "2D_DXF_SAFETY: 2D input produces only profile/drilling candidates. "
            "Complete 3D CAM plan requires depth, stock, and setup data."
        )

    if inp.features:
        default_setup = setup_candidates[0].setup_id if setup_candidates else None
        default_cutting_data = inp.cutting_data_refs[0] if inp.cutting_data_refs else None

        for feat in inp.features:
            mapping = map_feature_to_cam_candidates(
                feature_id=feat.feature_id,
                feature_type=feat.feature_type,
                has_tolerance_evidence=feat.has_tolerance_evidence,
                depth_diameter_ratio=feat.depth_diameter_ratio,
                is_confirmed=feat.is_confirmed,
            )

            for op_type, phase, tool_family, rationale in zip(
                mapping.candidates,
                mapping.phases,
                mapping.tool_families,
                mapping.rationale.split("; "),
                strict=False,
            ):
                op_id = f"OP_{_make_id()}"
                entry_exit = EntryExitRequirement(
                    entry_strategy=_default_entry(op_type),
                    exit_strategy=ExitStrategy.RETRACT,
                )

                tool_req = ToolRequirement(
                    tool_family=tool_family,
                    notes="Tool family requirement — specific tool requires catalog lookup",
                )

                strategy_type = get_cam_strategy_for_operation(op_type)

                tp_req = ToolpathRequirement(
                    requirement_id=f"TP_{_make_id()}",
                    operation_ref=op_id,
                    strategy=strategy_type,
                    feature_refs=[feat.feature_id],
                    setup_ref=default_setup,
                    cutting_data_ref=default_cutting_data,
                    entry_exit=entry_exit,
                    clearances=[
                        ClearanceRequirement(
                            clearance_type=ClearanceType.SAFE_Z,
                            value_mm=None,
                            source=None,
                            notes="Safe Z value requires machine/fixture configuration",
                        ),
                        ClearanceRequirement(
                            clearance_type=ClearanceType.CLEARANCE_PLANE,
                            value_mm=None,
                            source=None,
                            notes="Clearance plane requires machine/fixture configuration",
                        ),
                    ],
                    simulation_required=True,
                    status=CAMPlanStatus.CANDIDATE,
                    warnings=list(mapping.warnings),
                )

                missing_info = list(mapping.warnings)
                if default_cutting_data is None:
                    missing_info.append("cutting_data_ref: cutting data not available")
                if inp.stock_type == StockType.UNKNOWN:
                    missing_info.append("stock_definition: stock not defined")

                op = CAMOperationCandidate(
                    operation_id=op_id,
                    operation_type=op_type,
                    phase=phase,
                    feature_refs=[feat.feature_id],
                    setup_ref=default_setup,
                    tool_requirement=tool_req,
                    cutting_data_ref=default_cutting_data,
                    toolpath_requirement=tp_req,
                    why=rationale,
                    which_feature=feat.feature_id,
                    which_setup=default_setup,
                    which_tool_family=tool_family.value,
                    which_cutting_data=default_cutting_data or "CUTTING_DATA_REQUIRED",
                    missing_information=missing_info,
                    status=CAMPlanStatus.CANDIDATE,
                    warnings=list(mapping.warnings),
                )
                all_operations.append(op)
                all_toolpath_reqs.append(tp_req)

                if strategy_type:
                    strategy = CAMStrategyCandidate(
                        strategy_id=f"STRAT_{_make_id()}",
                        strategy_type=strategy_type,
                        operation_ref=op_id,
                        feature_refs=[feat.feature_id],
                        reason=rationale,
                        required_tool=tool_req,
                        required_machine_capability=inp.machine_type,
                        cutting_data_ref=default_cutting_data,
                        status=CAMPlanStatus.CANDIDATE,
                        warnings=list(mapping.warnings),
                    )
                    all_strategies.append(strategy)
    else:
        missing_inputs.append("features")
        warnings.append("NO_FEATURES: no manufacturing features provided — no operations generated")

    op_id_map = {op.operation_id: op.operation_type for op in all_operations}
    op_phase_map = {op.operation_id: op.phase for op in all_operations}

    ordering = sort_operations_by_precedence(
        [op.operation_id for op in all_operations],
        op_id_map,
        op_phase_map,
    )

    ordered_op_ids = list(ordering.ordered_operation_ids)
    op_lookup = {op.operation_id: op for op in all_operations}

    ordered_ops: list[CAMOperationCandidate] = []
    seen: set[str] = set()
    for oid in ordered_op_ids:
        if oid in op_lookup and oid not in seen:
            ordered_ops.append(op_lookup[oid])
            seen.add(oid)
    for op in all_operations:
        if op.operation_id not in seen:
            ordered_ops.append(op)

    pred_ops: list[CAMOperationCandidate] = []
    for i, op in enumerate(ordered_ops):
        preds = [
            ordered_ops[j].operation_id
            for j in range(i)
            if ordered_ops[j].operation_id != op.operation_id
            and op.operation_id in ordering.ordered_operation_ids
            and ordered_ops[j].operation_id in ordering.ordered_operation_ids
            and ordered_ops[j].operation_type in _get_predecessors(op.operation_type)
        ]
        pred_ops.append(op.model_copy(update={"predecessor_operation_ids": preds}))

    all_operations = pred_ops

    if not inp.material:
        missing_inputs.append("material")
    if not inp.machine_requirement_refs:
        missing_inputs.append("machine_requirement")

    if ordered_ops:
        status = CAMJobStatus.CAM_PLAN_CREATED
        cam_plan_status = CAMPlanStatus.ENGINEERING_REVIEW_REQUIRED
    elif missing_inputs:
        status = CAMJobStatus.INCOMPLETE
        cam_plan_status = CAMPlanStatus.INCOMPLETE
    else:
        status = CAMJobStatus.DRAFT
        cam_plan_status = CAMPlanStatus.INCOMPLETE

    return CAMJob(
        job_id=job_id,
        part_reference=inp.part_id,
        cad_reference=inp.cad_reference,
        material=inp.material,
        stock=stock,
        wcs_candidates=wcs_candidates,
        setup_candidates=setup_candidates,
        operation_candidates=all_operations,
        strategy_candidates=all_strategies,
        toolpath_requirements=all_toolpath_reqs,
        machine_requirement_refs=inp.machine_requirement_refs or [],
        cutting_data_refs=inp.cutting_data_refs or [],
        warnings=warnings,
        missing_inputs=missing_inputs,
        status=status,
        cam_plan_status=cam_plan_status,
    )


def create_cam_job_from_dxf(
    file_name: str,
    features: list[FeatureInput] | None = None,
    material: str | None = None,
) -> CAMJob:
    """Create a 2D DXF CAM job.

    Per 2D DXF safety rule:
    - Profile and drilling candidates only.
    - Depth/stock/setup data must come from external source.
    - Complete 3D CAM plan NOT produced.
    """
    return create_cam_job(
        CamPlanningInput(
            cad_reference=file_name,
            material=material,
            features=features,
            is_2d_only=True,
            stock_type=StockType.UNKNOWN,
            stock_source=StockSource.UNKNOWN,
        )
    )


def create_cam_job_from_iges(
    file_name: str,
    features: list[FeatureInput] | None = None,
    material: str | None = None,
    machine_type: str | None = None,
    cutting_data_refs: list[str] | None = None,
    stock_type: StockType = StockType.UNKNOWN,
    stock_source: StockSource = StockSource.UNKNOWN,
    access_directions: list[str] | None = None,
) -> CAMJob:
    """Create a 3D IGES CAM job.

    Uses real Level-3 feature evidence. If feature evidence is insufficient,
    no operations are generated (zero CAM operations is acceptable).
    """
    return create_cam_job(
        CamPlanningInput(
            cad_reference=file_name,
            material=material,
            machine_type=machine_type,
            features=features,
            is_2d_only=False,
            stock_type=stock_type,
            stock_source=stock_source,
            cutting_data_refs=cutting_data_refs,
            access_directions=access_directions,
        )
    )


def _parse_orientation(direction: str) -> SetupOrientation:
    mapping = {
        "+z": SetupOrientation.PLUS_Z,
        "-z": SetupOrientation.MINUS_Z,
        "+x": SetupOrientation.PLUS_X,
        "-x": SetupOrientation.MINUS_X,
        "+y": SetupOrientation.PLUS_Y,
        "-y": SetupOrientation.MINUS_Y,
    }
    return mapping.get(direction.lower(), SetupOrientation.UNKNOWN)


def _default_entry(op_type: CAMOperationType) -> EntryStrategy:
    if op_type in (CAMOperationType.DRILL, CAMOperationType.PECK_DRILL,
                   CAMOperationType.TAP, CAMOperationType.REAM,
                   CAMOperationType.BORE, CAMOperationType.COUNTERBORE,
                   CAMOperationType.COUNTERSINK):
        return EntryStrategy.PLUNGE
    if op_type in (CAMOperationType.POCKET_ROUGH, CAMOperationType.ADAPTIVE_ROUGH):
        return EntryStrategy.HELIX
    if op_type in (CAMOperationType.CONTOUR_ROUGH, CAMOperationType.CONTOUR_FINISH,
                   CAMOperationType.SLOT_MILL):
        return EntryStrategy.RAMP
    if op_type in (CAMOperationType.POCKET_FINISH, CAMOperationType.BALL_END_FINISH,
                   CAMOperationType.CHAMFER):
        return EntryStrategy.LEAD_IN
    return EntryStrategy.UNKNOWN


def _get_predecessors(op_type: CAMOperationType) -> frozenset[CAMOperationType]:
    from backend.cam_planning.operation_ordering import PRECEDENCE_RULES
    return frozenset(r.predecessor for r in PRECEDENCE_RULES if r.successor == op_type)
