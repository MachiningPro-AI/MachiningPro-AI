"""Level-17 CNC Job Planning & Machine Assignment API endpoints.

ASSIGNMENT_IS_PROPOSED_ONLY: All endpoints return PROPOSED recommendations only.
No endpoint dispatches jobs to real machines.
No endpoint automatically assigns a machine.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.auth import verify_token
from backend.job_planning import (
    AssignmentRecommendation,
    CamOperationRequirements,
    MachineCapabilityProfile,
    MaterialCompatibilityCheck,
    RankingObjective,
    SpindleMatchCheck,
    WorkloadEstimate,
    check_material_compatibility,
    check_spindle_requirements,
    estimate_workload,
    plan_job_assignment,
)
from backend.scheduling.enums import MachineClass

router = APIRouter(prefix="/api/job-planning", tags=["job-planning"])

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------


def _require_user(token: str = Depends(verify_token)):  # noqa: B008
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    return token


# ---------------------------------------------------------------------------
# Session-scoped stores (non-persistent, cleared on restart)
# ---------------------------------------------------------------------------

_recommendation_store: dict[str, AssignmentRecommendation] = {}
_profile_store: dict[str, MachineCapabilityProfile] = {}


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class PlanAssignmentRequest(BaseModel):
    requirements: CamOperationRequirements
    machines: list[MachineCapabilityProfile]
    queue_depths: dict[str, int] | None = None
    objective: RankingObjective = RankingObjective.CAPABILITY_FIT


class MaterialCompatibilityRequest(BaseModel):
    material: str | None = None
    machine_class: MachineClass = MachineClass.UNKNOWN


class SpindleMatchRequest(BaseModel):
    required_rpm: float | None = None
    machine_max_rpm: int | None = None


class WorkloadRequest(BaseModel):
    machine_id: str
    queue_depth: int | None = None
    estimated_cycle_time_min: float | None = None


class BatchPlanRequest(BaseModel):
    jobs: list[CamOperationRequirements]
    machines: list[MachineCapabilityProfile]
    queue_depths: dict[str, int] | None = None
    objective: RankingObjective = RankingObjective.CAPABILITY_FIT


class RegisterProfileRequest(BaseModel):
    profile: MachineCapabilityProfile


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/safety-constants")
async def get_safety_constants(_token: str = Depends(_require_user)):  # noqa: B008
    """Return Level-17 safety constants — all must be True."""
    from backend.job_planning import (
        ASSIGNMENT_IS_PROPOSED_ONLY,
        HUMAN_APPROVAL_MANDATORY,
        MISSING_DATA_FAILS_CLOSED,
        NO_AUTOMATIC_JOB_DISPATCH,
        NO_AUTOMATIC_MACHINE_ASSIGNMENT,
        NO_FABRICATED_CAPABILITY_DATA,
        UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
    )
    return {
        "NO_AUTOMATIC_MACHINE_ASSIGNMENT": NO_AUTOMATIC_MACHINE_ASSIGNMENT,
        "NO_AUTOMATIC_JOB_DISPATCH": NO_AUTOMATIC_JOB_DISPATCH,
        "NO_FABRICATED_CAPABILITY_DATA": NO_FABRICATED_CAPABILITY_DATA,
        "MISSING_DATA_FAILS_CLOSED": MISSING_DATA_FAILS_CLOSED,
        "ASSIGNMENT_IS_PROPOSED_ONLY": ASSIGNMENT_IS_PROPOSED_ONLY,
        "HUMAN_APPROVAL_MANDATORY": HUMAN_APPROVAL_MANDATORY,
        "UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE": UNKNOWN_CAPABILITY_IS_NOT_ELIGIBLE,
    }


@router.post("/assign", response_model=AssignmentRecommendation)
async def plan_assignment(
    req: PlanAssignmentRequest,
    _token: str = Depends(_require_user),  # noqa: B008
) -> AssignmentRecommendation:
    """
    Plan machine assignment for a job.

    Returns a PROPOSED recommendation — not a dispatch order.
    Human review mandatory before any real machine assignment.
    Missing capability data fails closed.
    """
    recommendation = plan_job_assignment(
        requirements=req.requirements,
        machines=req.machines,
        queue_depths=req.queue_depths,
        objective=req.objective,
    )
    _recommendation_store[recommendation.job_id] = recommendation
    return recommendation


@router.get("/recommendation/{job_id}", response_model=AssignmentRecommendation)
async def get_recommendation(
    job_id: str,
    _token: str = Depends(_require_user),  # noqa: B008
) -> AssignmentRecommendation:
    """Retrieve a stored assignment recommendation by job ID."""
    rec = _recommendation_store.get(job_id)
    if rec is None:
        raise HTTPException(status_code=404, detail=f"No recommendation for job {job_id!r}")
    return rec


@router.post("/material-compatibility", response_model=MaterialCompatibilityCheck)
async def check_material(
    req: MaterialCompatibilityRequest,
    _token: str = Depends(_require_user),  # noqa: B008
) -> MaterialCompatibilityCheck:
    """Check material compatibility with a machine class."""
    return check_material_compatibility(req.material, req.machine_class)


@router.post("/spindle-match", response_model=SpindleMatchCheck)
async def check_spindle(
    req: SpindleMatchRequest,
    _token: str = Depends(_require_user),  # noqa: B008
) -> SpindleMatchCheck:
    """Check spindle requirements against machine capability."""
    return check_spindle_requirements(req.required_rpm, req.machine_max_rpm)


@router.post("/workload", response_model=WorkloadEstimate)
async def estimate_machine_workload(
    req: WorkloadRequest,
    _token: str = Depends(_require_user),  # noqa: B008
) -> WorkloadEstimate:
    """Estimate workload status for a machine based on queue depth."""
    return estimate_workload(
        machine_id=req.machine_id,
        queue_depth=req.queue_depth,
        estimated_cycle_time_min=req.estimated_cycle_time_min,
    )


@router.post("/batch-assign")
async def batch_plan_assignment(
    req: BatchPlanRequest,
    _token: str = Depends(_require_user),  # noqa: B008
) -> dict:
    """Plan machine assignments for multiple jobs (batch).

    Returns PROPOSED recommendations for each job.
    No job is dispatched automatically.
    """
    results: list[AssignmentRecommendation] = []
    for job_req in req.jobs:
        rec = plan_job_assignment(
            requirements=job_req,
            machines=req.machines,
            queue_depths=req.queue_depths,
            objective=req.objective,
        )
        _recommendation_store[rec.job_id] = rec
        results.append(rec)
    return {
        "job_count": len(results),
        "recommendations": [r.model_dump() for r in results],
        "is_proposed_only": True,
        "is_automatic_dispatch": False,
        "review_required": True,
    }


@router.post("/profile/register")
async def register_profile(
    req: RegisterProfileRequest,
    _token: str = Depends(_require_user),  # noqa: B008
) -> dict:
    """Register a machine capability profile for use in planning."""
    _profile_store[req.profile.machine_id] = req.profile
    return {
        "machine_id": req.profile.machine_id,
        "registered": True,
        "is_fabricated_capability": req.profile.is_fabricated_capability,
    }


@router.get("/profiles")
async def list_profiles(
    _token: str = Depends(_require_user),  # noqa: B008
) -> dict:
    """List registered machine capability profiles."""
    return {
        "count": len(_profile_store),
        "machines": [p.model_dump() for p in _profile_store.values()],
    }


@router.get("/recommendations")
async def list_recommendations(
    _token: str = Depends(_require_user),  # noqa: B008
) -> dict:
    """List all stored assignment recommendations."""
    return {
        "count": len(_recommendation_store),
        "recommendations": [r.model_dump() for r in _recommendation_store.values()],
    }


# ---------------------------------------------------------------------------
# Explicitly NOT PRESENT — forbidden endpoints
# ---------------------------------------------------------------------------
# /auto-dispatch        — would dispatch a job to a machine without review
# /apply-assignment     — would commit an assignment without human approval
# /execute-on-machine   — would send commands to CNC
# /override-review      — would skip review_required gate
