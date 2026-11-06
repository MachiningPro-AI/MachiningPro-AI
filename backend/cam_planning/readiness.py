"""CAM plan readiness checker for Level-9.

Evaluates whether a CAMJob has sufficient information to proceed to
toolpath generation.

READY_FOR_TOOLPATH_GENERATION requires:
  - stock known (type and source not UNKNOWN)
  - machine capability requirement stated
  - at least one setup candidate defined
  - WCS candidate defined for each setup
  - at least one operation candidate defined
  - no critical unresolved geometry issues
  - cutting data reference present for each operation (or status known)
  - tool requirement stated for each operation
  - no BLOCKED status anywhere

SIMULATION_REQUIRED stays YES regardless of readiness.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.cam_planning.enums import CAMJobStatus, CAMPlanStatus
from backend.cam_planning.models import CAMJob

__all__ = [
    "ReadinessResult",
    "check_cam_readiness",
]


@dataclass(frozen=True)
class ReadinessResult:
    """Outcome of a CAM plan readiness check."""

    is_ready: bool
    cam_plan_status: CAMPlanStatus
    job_status: CAMJobStatus
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    missing_inputs: tuple[str, ...]


def check_cam_readiness(job: CAMJob) -> ReadinessResult:
    """Evaluate whether a CAMJob is ready for toolpath generation.

    Returns READY_FOR_TOOLPATH_GENERATION only when all mandatory
    information is present and consistent.

    Fail-closed: missing or UNKNOWN data → not ready.
    """
    blockers: list[str] = []
    warnings: list[str] = []
    missing_inputs: list[str] = []

    if not job.stock.is_known:
        blockers.append("STOCK_UNKNOWN: stock type or source is UNKNOWN")
        missing_inputs.append("stock_type")
        missing_inputs.append("stock_source")

    if not job.setup_candidates:
        blockers.append("NO_SETUP_CANDIDATES: at least one setup candidate required")
        missing_inputs.append("setup_candidates")

    if not job.operation_candidates:
        blockers.append("NO_OPERATIONS: at least one operation candidate required")
        missing_inputs.append("operation_candidates")

    for setup in job.setup_candidates:
        if setup.wcs_candidate is None:
            blockers.append(
                f"WCS_UNDEFINED: setup {setup.setup_id!r} has no WCS candidate"
            )
            missing_inputs.append(f"wcs_candidate[{setup.setup_id}]")
        elif not setup.wcs_candidate.is_validated:
            warnings.append(
                f"WCS_NOT_VALIDATED: setup {setup.setup_id!r} WCS is a candidate only"
            )

    has_blocked_ops = False
    for op in job.operation_candidates:
        if op.status == CAMPlanStatus.BLOCKED:
            blockers.append(
                f"OPERATION_BLOCKED: {op.operation_id!r} ({op.operation_type.value})"
            )
            has_blocked_ops = True

        if op.tool_requirement is None:
            warnings.append(
                f"NO_TOOL_REQUIREMENT: {op.operation_id!r} has no tool requirement"
            )
            missing_inputs.append(f"tool_requirement[{op.operation_id}]")

        if op.cutting_data_ref is None:
            warnings.append(
                f"CUTTING_DATA_REQUIRED: {op.operation_id!r} has no cutting data ref"
            )
            missing_inputs.append(f"cutting_data_ref[{op.operation_id}]")

        if op.setup_ref is None:
            warnings.append(
                f"NO_SETUP_REF: {op.operation_id!r} has no setup reference"
            )

    for tr in job.toolpath_requirements:
        if tr.wcs_ref is None:
            warnings.append(
                f"NO_WCS_REF: toolpath requirement {tr.requirement_id!r} has no WCS ref"
            )
        if tr.cutting_data_ref is None:
            warnings.append(
                f"CUTTING_DATA_REQUIRED: toolpath requirement {tr.requirement_id!r}"
            )

    if job.wcs_candidates and not any(c.is_validated for c in job.wcs_candidates):
        warnings.append("ALL_WCS_UNVALIDATED: no WCS candidate has been validated")

    is_ready = not blockers and not has_blocked_ops

    if is_ready:
        cam_plan_status = CAMPlanStatus.READY_FOR_TOOLPATH_GENERATION
        job_status = CAMJobStatus.SIMULATION_REQUIRED
    elif blockers:
        if has_blocked_ops:
            cam_plan_status = CAMPlanStatus.BLOCKED
            job_status = CAMJobStatus.BLOCKED
        else:
            cam_plan_status = CAMPlanStatus.INCOMPLETE
            job_status = CAMJobStatus.INCOMPLETE
    else:
        cam_plan_status = CAMPlanStatus.ENGINEERING_REVIEW_REQUIRED
        job_status = CAMJobStatus.CAM_PLAN_CREATED

    return ReadinessResult(
        is_ready=is_ready,
        cam_plan_status=cam_plan_status,
        job_status=job_status,
        blockers=tuple(blockers),
        warnings=tuple(warnings),
        missing_inputs=tuple(set(missing_inputs)),
    )
