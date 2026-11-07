"""
Level-14 Shop Floor Integration and Safe Dispatch Foundation API.

Allowed endpoints:
  POST /api/dispatch/create-package
  POST /api/dispatch/validate-package
  POST /api/dispatch/request-approval
  POST /api/dispatch/approve-dry-run
  POST /api/dispatch/reject-package
  POST /api/dispatch/run-dry-run
  GET  /api/dispatch/machine-state/{machine_id}
  GET  /api/dispatch/audit-events

Forbidden endpoints (NOT implemented):
  send-to-machine
  upload-program
  start-machine
  stop-machine
  write-offset

NO_REAL_MACHINE_WRITE=YES
NO_AUTO_DISPATCH=YES
APPROVAL_REQUIRED=YES
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from ..dispatch import (
    APPROVAL_REQUIRED,
    IS_DISPATCH_ORDER,
    ApprovalStatus,
    DispatchApproval,
    DispatchPackage,
    DispatchPackageStatus,
    DispatchPolicy,
    SimulatedCNCController,
    SimulatedMachineState,
    audit_approval_granted,
    audit_approval_rejected,
    audit_approval_requested,
    audit_dry_run_failed,
    audit_dry_run_passed,
    audit_dry_run_started,
    audit_machine_state_read,
    audit_package_created,
    check_dispatch_readiness,
    run_simulated_transfer,
)
from .auth import verify_token

router = APIRouter(prefix="/api/dispatch", tags=["dispatch"])


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _require_user(
    authorization: str | None = Header(default=None),  # noqa: B008
) -> dict[str, Any]:
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


class CreatePackageRequest(BaseModel):
    job_ref: str
    assignment_ref: str
    machine_ref: str
    nc_candidate_ref: str | None = None
    nc_hash: str | None = None
    post_profile_ref: str | None = None
    tool_list: list[str] = Field(default_factory=list)
    holder_list: list[str] = Field(default_factory=list)
    fixture_ref: str | None = None
    setup_ref: str | None = None
    work_offset_ref: str | None = None
    verification_ref: str | None = None
    schedule_ref: str | None = None


class ApprovalRequest(BaseModel):
    package_id: str
    approved_by: str
    comments: str = ""


class RejectRequest(BaseModel):
    package_id: str
    rejected_by: str
    reason: str = ""


class DryRunRequest(BaseModel):
    package_id: str
    job_ref: str
    assignment_ref: str
    machine_ref: str
    nc_candidate_ref: str | None = None
    nc_hash: str | None = None
    post_profile_ref: str | None = None
    tool_list: list[str] = Field(default_factory=list)
    fixture_ref: str | None = None
    verification_ref: str | None = None
    approval_id: str | None = None
    approved_by: str | None = None
    simulated_machine_state: str = "IDLE"


class ValidatePackageRequest(BaseModel):
    package_id: str
    job_ref: str
    assignment_ref: str
    machine_ref: str
    nc_candidate_ref: str | None = None
    nc_hash: str | None = None
    tool_list: list[str] = Field(default_factory=list)
    fixture_ref: str | None = None
    verification_ref: str | None = None
    current_nc_hash: str | None = None
    current_assignment_ref: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/create-package")
async def create_package(
    request: CreatePackageRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Create a new dispatch package (DRAFT status). No machine write."""
    package_id = str(uuid.uuid4())
    package = DispatchPackage(
        package_id=package_id,
        job_ref=request.job_ref,
        assignment_ref=request.assignment_ref,
        machine_ref=request.machine_ref,
        nc_candidate_ref=request.nc_candidate_ref,
        nc_hash=request.nc_hash,
        post_profile_ref=request.post_profile_ref,
        tool_list=request.tool_list,
        holder_list=request.holder_list,
        fixture_ref=request.fixture_ref,
        setup_ref=request.setup_ref,
        work_offset_ref=request.work_offset_ref,
        verification_ref=request.verification_ref,
        schedule_ref=request.schedule_ref,
        created_at=_now(),
        status=DispatchPackageStatus.DRAFT,
    )
    actor = _auth.get("sub", "api_user")
    event = audit_package_created(
        package_ref=package_id,
        job_ref=request.job_ref,
        machine_ref=request.machine_ref,
        actor=actor,
    )
    return {
        "package": package.model_dump(),
        "audit_event": event.model_dump(),
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }


@router.post("/validate-package")
async def validate_package(
    request: ValidatePackageRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Validate package integrity and readiness (no machine write)."""
    package = DispatchPackage(
        package_id=request.package_id,
        job_ref=request.job_ref,
        assignment_ref=request.assignment_ref,
        machine_ref=request.machine_ref,
        nc_candidate_ref=request.nc_candidate_ref,
        nc_hash=request.nc_hash,
        tool_list=request.tool_list,
        fixture_ref=request.fixture_ref,
        verification_ref=request.verification_ref,
        created_at=_now(),
    )
    readiness = check_dispatch_readiness(
        package=package,
        policy=DispatchPolicy(
            require_human_approval=False,
        ),
        current_nc_hash=request.current_nc_hash,
        current_assignment_ref=request.current_assignment_ref,
    )
    return {
        "package_id": request.package_id,
        "readiness": readiness.model_dump(),
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }


@router.post("/request-approval")
async def request_approval(
    request: ApprovalRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Request human approval for dry-run. No machine write."""
    approval_id = str(uuid.uuid4())
    approval = DispatchApproval(
        approval_id=approval_id,
        package_ref=request.package_id,
        approved_by=request.approved_by,
        scope="DRY_RUN_ONLY",
        status=ApprovalStatus.PENDING,
        comments=request.comments,
        is_automatic=False,
        is_execution_approval=False,
    )
    actor = _auth.get("sub", "api_user")
    event = audit_approval_requested(package_ref=request.package_id, actor=actor)
    return {
        "approval": approval.model_dump(),
        "audit_event": event.model_dump(),
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }


@router.post("/approve-dry-run")
async def approve_dry_run(
    request: ApprovalRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Approve a package for dry-run only. No execution approval."""
    approval_id = str(uuid.uuid4())
    approval = DispatchApproval(
        approval_id=approval_id,
        package_ref=request.package_id,
        approved_by=request.approved_by,
        approved_at=_now(),
        scope="DRY_RUN_ONLY",
        status=ApprovalStatus.APPROVED_FOR_DRY_RUN,
        comments=request.comments,
        is_automatic=False,
        is_execution_approval=False,
    )
    actor = _auth.get("sub", "api_user")
    event = audit_approval_granted(package_ref=request.package_id, actor=actor)
    return {
        "approval": approval.model_dump(),
        "audit_event": event.model_dump(),
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }


@router.post("/reject-package")
async def reject_package(
    request: RejectRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Reject a dispatch package. No machine write."""
    actor = _auth.get("sub", "api_user")
    event = audit_approval_rejected(
        package_ref=request.package_id,
        actor=actor,
        reason=request.reason,
    )
    return {
        "package_id": request.package_id,
        "status": "REJECTED",
        "audit_event": event.model_dump(),
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }


@router.post("/run-dry-run")
async def execute_dry_run(
    request: DryRunRequest,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """
    Execute a simulated dry-run against a synthetic test controller.
    NO real machine is contacted. NO real transfer occurs.
    """
    package = DispatchPackage(
        package_id=request.package_id,
        job_ref=request.job_ref,
        assignment_ref=request.assignment_ref,
        machine_ref=request.machine_ref,
        nc_candidate_ref=request.nc_candidate_ref,
        nc_hash=request.nc_hash,
        post_profile_ref=request.post_profile_ref,
        tool_list=request.tool_list,
        fixture_ref=request.fixture_ref,
        verification_ref=request.verification_ref,
        created_at=_now(),
    )

    approval: DispatchApproval | None = None
    if request.approval_id and request.approved_by:
        approval = DispatchApproval(
            approval_id=request.approval_id,
            package_ref=request.package_id,
            approved_by=request.approved_by,
            approved_at=_now(),
            scope="DRY_RUN_ONLY",
            status=ApprovalStatus.APPROVED_FOR_DRY_RUN,
            is_automatic=False,
            is_execution_approval=False,
        )

    try:
        sim_state = SimulatedMachineState(request.simulated_machine_state)
    except ValueError:
        sim_state = SimulatedMachineState.IDLE

    controller = SimulatedCNCController(
        machine_id=request.machine_ref,
        initial_state=sim_state,
    )
    controller.connect_read_only()

    actor = _auth.get("sub", "api_user")
    start_event = audit_dry_run_started(
        package_ref=request.package_id,
        machine_ref=request.machine_ref,
        actor=actor,
    )

    result = run_simulated_transfer(package, controller, approval)

    if result.status.value == "PASSED":
        end_event = audit_dry_run_passed(
            package_ref=request.package_id,
            machine_ref=request.machine_ref,
            actor=actor,
            reference_hash=request.nc_hash,
        )
    else:
        end_event = audit_dry_run_failed(
            package_ref=request.package_id,
            machine_ref=request.machine_ref,
            actor=actor,
            reason=", ".join(f.value for f in result.failures),
        )

    return {
        "dry_run_result": result.model_dump(),
        "start_event": start_event.model_dump(),
        "end_event": end_event.model_dump(),
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
        "is_real_transfer": False,
    }


@router.get("/machine-state/{machine_id}")
async def get_machine_state(
    machine_id: str,
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """
    Return a synthetic TEST_ONLY machine state snapshot.
    Read-only. No real machine is contacted.
    """
    controller = SimulatedCNCController(machine_id=machine_id)
    controller.connect_read_only()
    state = controller.get_machine_state(machine_id)
    actor = _auth.get("sub", "api_user")
    event = audit_machine_state_read(machine_ref=machine_id, actor=actor)
    return {
        "machine_state": state.model_dump(),
        "audit_event": event.model_dump(),
        "source": "SYNTHETIC_TEST",
        "certification": "TEST_ONLY",
        "is_real_machine_read": False,
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }


@router.get("/audit-events")
async def get_audit_events(
    _auth: dict[str, Any] = Depends(_require_user),  # noqa: B008
):
    """Return available audit event types (schema documentation)."""
    from ..dispatch.enums import DispatchAuditEventType
    return {
        "audit_event_types": [e.value for e in DispatchAuditEventType],
        "approval_required": APPROVAL_REQUIRED,
        "is_dispatch_order": IS_DISPATCH_ORDER,
    }
