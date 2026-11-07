"""
Level-13 Machine Scheduling and Job Assignment API.

Safe endpoints:
  POST /api/scheduling/evaluate-machines
  POST /api/scheduling/create-schedule-candidate
  POST /api/scheduling/evaluate-assignment
  POST /api/scheduling/apply-algorithm
  POST /api/scheduling/check-readiness
  GET  /api/scheduling/test-machines

NO dispatch endpoint.
NO send-NC endpoint.
NO start-machine endpoint.
NO controller-upload endpoint.
APPROVAL_REQUIRED=True always.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..scheduling import (
    MachineClass,
    MachineResource,
    ProductionJob,
    ResourceDataSource,
    SchedulingAlgorithm,
    SchedulingObjective,
    apply_scheduling_algorithm,
    check_production_readiness,
    evaluate_job_assignment,
    evaluate_machine_candidates,
)
from ..scheduling.models import (
    MachineRequirements,
    SchedulingObjectiveConfig,
)
from .auth import verify_token

router = APIRouter(prefix="/api/scheduling", tags=["scheduling"])


def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:  # noqa: B008
    """Bearer token auth; fails closed with 401."""
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class MachineRequest(BaseModel):
    machine_id: str
    machine_name: str
    machine_class: str = "UNKNOWN"
    axis_count: int | None = None
    x_travel_mm: float | None = None
    y_travel_mm: float | None = None
    z_travel_mm: float | None = None
    spindle_speed_max_rpm: float | None = None
    spindle_power_kw: float | None = None
    table_load_capacity_kg: float | None = None
    supports_turning: bool = False
    supports_milling: bool = True
    availability_status: str = "UNKNOWN"
    available_tool_ids: list[str] = Field(default_factory=list)
    installed_fixture_id: str | None = None
    supported_post_profile_ids: list[str] = Field(default_factory=list)
    source: str = "USER_DEFINED"


class JobRequest(BaseModel):
    job_id: str
    part_reference: str | None = None
    quantity: int = 1
    priority: str = "NORMAL"
    due_date: str | None = None
    toolpath_verified: bool = False
    nc_candidate_ref: str | None = None
    nc_candidate_status: str | None = None
    nc_candidate_stale: bool = False
    required_tools: list[str] = Field(default_factory=list)
    required_holders: list[str] = Field(default_factory=list)
    required_fixture: str | None = None
    estimated_cycle_time_min: float | None = None
    setup_time_min: float | None = None
    required_machine_class: str = "UNKNOWN"
    required_axis_count: int | None = None
    required_x_travel_mm: float | None = None
    required_y_travel_mm: float | None = None
    required_z_travel_mm: float | None = None
    required_spindle_speed_rpm: float | None = None
    requires_turning: bool = False
    requires_milling: bool = False
    required_post_profile_id: str | None = None
    max_workpiece_mass_kg: float | None = None
    process_plan_ref: str | None = None
    cam_plan_ref: str | None = None


class EvaluateMachinesRequest(BaseModel):
    job: JobRequest
    machines: list[MachineRequest]


class ScheduleCandidateRequest(BaseModel):
    job: JobRequest
    machine: MachineRequest
    queue_depth: int = 0
    algorithm: str = "FIFO"
    objective: str = "EARLIEST_COMPLETION"


class AssignmentRequest(BaseModel):
    job: JobRequest
    machine: MachineRequest
    queue_depth: int = 0


class AlgorithmRequest(BaseModel):
    jobs: list[JobRequest]
    machine_id: str
    algorithm: str = "FIFO"
    objective: str = "EARLIEST_COMPLETION"


class ReadinessRequest(BaseModel):
    job: JobRequest
    machine_eligible: bool = False
    schedule_slot_available: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_job(req: JobRequest) -> ProductionJob:
    from ..scheduling.enums import DueDateStatus, JobPriority
    machine_req = MachineRequirements(
        required_machine_class=MachineClass(req.required_machine_class),
        required_axis_count=req.required_axis_count,
        required_x_travel_mm=req.required_x_travel_mm,
        required_y_travel_mm=req.required_y_travel_mm,
        required_z_travel_mm=req.required_z_travel_mm,
        required_spindle_speed_rpm=req.required_spindle_speed_rpm,
        requires_turning=req.requires_turning,
        requires_milling=req.requires_milling,
        required_post_profile_id=req.required_post_profile_id,
        max_workpiece_mass_kg=req.max_workpiece_mass_kg,
    )
    return ProductionJob(
        job_id=req.job_id,
        part_reference=req.part_reference,
        quantity=req.quantity,
        priority=JobPriority(req.priority),
        due_date=req.due_date,
        due_date_status=DueDateStatus.KNOWN if req.due_date else DueDateStatus.UNKNOWN,
        toolpath_verified=req.toolpath_verified,
        nc_candidate_ref=req.nc_candidate_ref,
        nc_candidate_status=req.nc_candidate_status,
        nc_candidate_stale=req.nc_candidate_stale,
        machine_requirements=machine_req,
        required_tools=req.required_tools,
        required_holders=req.required_holders,
        required_fixture=req.required_fixture,
        estimated_cycle_time_min=req.estimated_cycle_time_min,
        setup_time_min=req.setup_time_min,
        process_plan_ref=req.process_plan_ref,
        cam_plan_ref=req.cam_plan_ref,
    )


def _build_machine(req: MachineRequest) -> MachineResource:
    from ..scheduling.enums import MachineAvailabilityStatus
    return MachineResource(
        machine_id=req.machine_id,
        machine_name=req.machine_name,
        machine_class=MachineClass(req.machine_class),
        source=ResourceDataSource(req.source),
        axis_count=req.axis_count,
        x_travel_mm=req.x_travel_mm,
        y_travel_mm=req.y_travel_mm,
        z_travel_mm=req.z_travel_mm,
        spindle_speed_max_rpm=req.spindle_speed_max_rpm,
        spindle_power_kw=req.spindle_power_kw,
        table_load_capacity_kg=req.table_load_capacity_kg,
        supports_turning=req.supports_turning,
        supports_milling=req.supports_milling,
        availability_status=MachineAvailabilityStatus(req.availability_status),
        available_tool_ids=req.available_tool_ids,
        installed_fixture_id=req.installed_fixture_id,
        supported_post_profile_ids=req.supported_post_profile_ids,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/evaluate-machines")
async def evaluate_machines(
    request: EvaluateMachinesRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Evaluate and rank machine candidates for a job."""
    job = _build_job(request.job)
    machines = [_build_machine(m) for m in request.machines]
    queue_depths = {m.machine_id: 0 for m in machines}
    reports = evaluate_machine_candidates(job, machines, queue_depths)
    return {
        "job_id": job.job_id,
        "candidates": [r.model_dump() for r in reports],
        "total_evaluated": len(reports),
        "eligible_count": sum(
            1 for r in reports
            if r.result in ("ELIGIBLE", "PARTIALLY_ELIGIBLE")
        ),
        "ineligible_count": sum(1 for r in reports if r.result == "INELIGIBLE"),
        "approval_required": True,
        "is_dispatch_order": False,
    }


@router.post("/create-schedule-candidate")
async def create_schedule(
    request: ScheduleCandidateRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Create a schedule candidate for a job on a specific machine."""
    from ..scheduling import create_schedule_candidate
    from ..scheduling.models import MachineQueue
    job = _build_job(request.job)
    machine = _build_machine(request.machine)
    queue = MachineQueue(machine_id=machine.machine_id) if request.queue_depth == 0 else None
    obj = SchedulingObjectiveConfig(
        algorithm=SchedulingAlgorithm(request.algorithm),
        objective=SchedulingObjective(request.objective),
    )
    candidate = create_schedule_candidate(job, machine, queue, obj)
    return {
        "schedule_candidate": candidate.model_dump(),
        "approval_required": True,
        "is_dispatch_order": False,
    }


@router.post("/evaluate-assignment")
async def evaluate_assignment(
    request: AssignmentRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Build a job assignment candidate with full rationale."""
    job = _build_job(request.job)
    machine = _build_machine(request.machine)
    candidate = evaluate_job_assignment(job, machine)
    return {
        "assignment_candidate": candidate.model_dump(),
        "approval_required": True,
        "is_dispatch_order": False,
    }


@router.post("/apply-algorithm")
async def apply_algorithm(
    request: AlgorithmRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Apply a scheduling algorithm to order jobs on a machine."""
    jobs = [_build_job(j) for j in request.jobs]
    result = apply_scheduling_algorithm(
        jobs,
        request.machine_id,
        SchedulingAlgorithm(request.algorithm),
        SchedulingObjective(request.objective),
    )
    return {
        "queue_result": result.model_dump(),
        "approval_required": True,
        "is_dispatch_order": False,
    }


@router.post("/check-readiness")
async def check_readiness(
    request: ReadinessRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Check production readiness for a job."""
    job = _build_job(request.job)
    readiness = check_production_readiness(
        job,
        machine_eligible=request.machine_eligible,
        schedule_slot_available=request.schedule_slot_available,
    )
    return {
        "readiness": readiness.model_dump(),
        "approval_required": True,
        "is_dispatch_order": False,
    }


@router.get("/test-machines")
async def get_test_machines(_auth: dict[str, Any] = Depends(_require_user)):  # noqa: B008
    """
    Return synthetic TEST_ONLY machine resources for controlled validation.

    These are clearly TEST_ONLY — not real production machine records.
    """
    return {
        "machines": [
            {
                "machine_id": "TEST_VMC_3AXIS_A",
                "machine_name": "Test VMC 3-Axis A",
                "machine_class": "VMC_3AXIS",
                "axis_count": 3,
                "x_travel_mm": 600.0,
                "y_travel_mm": 400.0,
                "z_travel_mm": 500.0,
                "spindle_speed_max_rpm": 12000.0,
                "supports_milling": True,
                "supports_turning": False,
                "source": "SYNTHETIC_TEST",
                "certification": "TEST_ONLY",
            },
            {
                "machine_id": "TEST_VMC_5AXIS_B",
                "machine_name": "Test VMC 5-Axis B",
                "machine_class": "VMC_5AXIS",
                "axis_count": 5,
                "x_travel_mm": 800.0,
                "y_travel_mm": 600.0,
                "z_travel_mm": 600.0,
                "spindle_speed_max_rpm": 18000.0,
                "supports_milling": True,
                "supports_turning": False,
                "source": "SYNTHETIC_TEST",
                "certification": "TEST_ONLY",
            },
            {
                "machine_id": "TEST_LATHE_C",
                "machine_name": "Test Lathe C",
                "machine_class": "LATHE_2AXIS",
                "axis_count": 2,
                "spindle_speed_max_rpm": 4000.0,
                "supports_milling": False,
                "supports_turning": True,
                "source": "SYNTHETIC_TEST",
                "certification": "TEST_ONLY",
            },
        ],
        "source": "SYNTHETIC_TEST",
        "certification": "TEST_ONLY",
        "note": "These are synthetic test resources only. Not real machine records.",
    }
