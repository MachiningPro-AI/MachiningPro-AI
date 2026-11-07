"""
Level-14 Dispatch Audit Trail.

Creates immutable-style audit events for the dispatch lifecycle.
Events are append-only by design.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from .enums import DispatchAuditEventType
from .models import DispatchAuditEvent


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_audit_event(
    event_type: DispatchAuditEventType,
    actor: str,
    job_ref: str | None = None,
    machine_ref: str | None = None,
    package_ref: str | None = None,
    result: str = "UNKNOWN",
    reason: str = "",
    reference_hash: str | None = None,
) -> DispatchAuditEvent:
    return DispatchAuditEvent(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=_now(),
        actor=actor,
        job_ref=job_ref,
        machine_ref=machine_ref,
        package_ref=package_ref,
        result=result,
        reason=reason,
        reference_hash=reference_hash,
    )


def audit_package_created(
    package_ref: str,
    job_ref: str,
    machine_ref: str,
    actor: str,
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.PACKAGE_CREATED,
        actor=actor,
        job_ref=job_ref,
        machine_ref=machine_ref,
        package_ref=package_ref,
        result="CREATED",
    )


def audit_approval_requested(
    package_ref: str,
    actor: str,
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.APPROVAL_REQUESTED,
        actor=actor,
        package_ref=package_ref,
        result="PENDING",
    )


def audit_approval_granted(
    package_ref: str,
    actor: str,
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.APPROVAL_GRANTED_DRY_RUN,
        actor=actor,
        package_ref=package_ref,
        result="APPROVED_FOR_DRY_RUN",
    )


def audit_approval_rejected(
    package_ref: str,
    actor: str,
    reason: str = "",
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.APPROVAL_REJECTED,
        actor=actor,
        package_ref=package_ref,
        result="REJECTED",
        reason=reason,
    )


def audit_dry_run_started(
    package_ref: str,
    machine_ref: str,
    actor: str,
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.DRY_RUN_STARTED,
        actor=actor,
        machine_ref=machine_ref,
        package_ref=package_ref,
        result="STARTED",
    )


def audit_dry_run_passed(
    package_ref: str,
    machine_ref: str,
    actor: str,
    reference_hash: str | None = None,
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.DRY_RUN_PASSED,
        actor=actor,
        machine_ref=machine_ref,
        package_ref=package_ref,
        result="PASSED",
        reference_hash=reference_hash,
    )


def audit_dry_run_failed(
    package_ref: str,
    machine_ref: str,
    actor: str,
    reason: str = "",
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.DRY_RUN_FAILED,
        actor=actor,
        machine_ref=machine_ref,
        package_ref=package_ref,
        result="FAILED",
        reason=reason,
    )


def audit_package_stale(
    package_ref: str,
    actor: str,
    reason: str = "",
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.PACKAGE_STALE,
        actor=actor,
        package_ref=package_ref,
        result="STALE",
        reason=reason,
    )


def audit_machine_state_read(
    machine_ref: str,
    actor: str,
    result: str = "READ",
) -> DispatchAuditEvent:
    return create_audit_event(
        DispatchAuditEventType.MACHINE_STATE_READ,
        actor=actor,
        machine_ref=machine_ref,
        result=result,
    )
