"""
Machine candidate selection for manufacturing routes.

Evaluates the machine library to find candidate machines for a proposed
manufacturing route.  Filtering uses actual known data from the machine
library; unknown capability does NOT become a pass.

Filtering criteria (in order):
  1. Operation compatibility (drilling_capable, boring_capable, etc.)
  2. Work envelope vs stock dimensions (when stock provided)
  3. Spindle RPM limit vs required cutting RPM (when cutting data provided)
  4. Additional process-specific limits where modeled

Machine candidate status codes:
  OPERATION_COMPATIBLE   -- passes operation capability check
  WORK_ENVELOPE_PASS     -- stock fits within machine envelope
  SPINDLE_LIMIT_PASS     -- required RPM within machine spindle range
  OPERATION_INCOMPATIBLE -- machine cannot perform this operation
  WORK_ENVELOPE_FAIL     -- stock too large for machine
  SPINDLE_LIMIT_EXCEEDED -- required RPM exceeds machine maximum
  CAPABILITY_UNKNOWN     -- relevant capability not modeled
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.machine_library.models import MachineCatalogRecord
from backend.machine_library.registry import MachineCatalogRegistry
from backend.machine_library.seed_catalog import seed_machine_library


class MachineCandidateStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


@dataclass
class MachineFilterResult:
    check_name: str
    status: MachineCandidateStatus
    detail: str


@dataclass
class MachineCandidate:
    machine: MachineCatalogRecord
    overall_status: MachineCandidateStatus
    checks: list[MachineFilterResult]
    rejection_reason: str | None


@dataclass
class MachineSelectionResult:
    operation: str
    candidates: list[MachineCandidate]
    passing_candidates: list[MachineCandidate]
    machine_selection_ready: bool
    notes: str


_OPERATION_TO_FLAG: dict[str, str] = {
    "drilling": "drilling_capable",
    "boring": "capable_boring",
    "reaming": "capable_reaming",
    "turning": "turning_capable",
    "milling": "milling_capable",
    "grinding": "grinding_capable",
    "tapping": "capable_tapping",
    "threading": "capable_threading",
}


def _get_registry() -> MachineCatalogRegistry:
    reg = MachineCatalogRegistry()
    for record in seed_machine_library():
        reg.register(record)
    return reg


def select_machines(
    *,
    operation: str,
    stock_x_mm: float | None = None,
    stock_y_mm: float | None = None,
    stock_z_mm: float | None = None,
    required_rpm_max: float | None = None,
    iso_material_group: str | None = None,
) -> MachineSelectionResult:
    """Select machine candidates for a manufacturing operation.

    Args:
        operation: Machining operation name (e.g. 'drilling').
        stock_x_mm / stock_y_mm / stock_z_mm: Stock envelope in mm.
        required_rpm_max: Maximum RPM required by cutting data.
        iso_material_group: ISO material group for filtering (future use).

    Returns:
        MachineSelectionResult with candidates and pass/fail per check.
    """
    reg = _get_registry()
    all_machines = reg.all()
    candidates: list[MachineCandidate] = []

    op_flag = _OPERATION_TO_FLAG.get(operation.lower())

    for machine in all_machines:
        checks: list[MachineFilterResult] = []
        overall = MachineCandidateStatus.PASS
        rejection: str | None = None

        # -- Check 1: operation capability -----------------------------------
        if op_flag is None:
            checks.append(MachineFilterResult(
                check_name="OPERATION_COMPATIBLE",
                status=MachineCandidateStatus.REVIEW_REQUIRED,
                detail=f"Operation '{operation}' not modeled in filter logic",
            ))
            overall = MachineCandidateStatus.REVIEW_REQUIRED
        else:
            cap_value = getattr(machine.capability, op_flag, None)
            if cap_value is True:
                checks.append(MachineFilterResult(
                    check_name="OPERATION_COMPATIBLE",
                    status=MachineCandidateStatus.PASS,
                    detail=f"{op_flag}=True",
                ))
            elif cap_value is False:
                checks.append(MachineFilterResult(
                    check_name="OPERATION_COMPATIBLE",
                    status=MachineCandidateStatus.FAIL,
                    detail=f"{op_flag}=False",
                ))
                overall = MachineCandidateStatus.FAIL
                rejection = "OPERATION_INCOMPATIBLE"
            else:
                checks.append(MachineFilterResult(
                    check_name="OPERATION_COMPATIBLE",
                    status=MachineCandidateStatus.REVIEW_REQUIRED,
                    detail=f"{op_flag}=None (not modeled)",
                ))
                if overall == MachineCandidateStatus.PASS:
                    overall = MachineCandidateStatus.REVIEW_REQUIRED

        # -- Check 2: work envelope ------------------------------------------
        if stock_x_mm is not None or stock_y_mm is not None or stock_z_mm is not None:
            env = machine.envelope
            envelope_ok = True
            envelope_detail_parts = []

            if stock_x_mm is not None and env.travel_x_mm is not None:
                if stock_x_mm > env.travel_x_mm:
                    envelope_ok = False
                    envelope_detail_parts.append(
                        f"X: stock {stock_x_mm} mm > travel {env.travel_x_mm} mm"
                    )
            if stock_y_mm is not None and env.travel_y_mm is not None:
                if stock_y_mm > env.travel_y_mm:
                    envelope_ok = False
                    envelope_detail_parts.append(
                        f"Y: stock {stock_y_mm} mm > travel {env.travel_y_mm} mm"
                    )
            if stock_z_mm is not None and env.travel_z_mm is not None:
                if stock_z_mm > env.travel_z_mm:
                    envelope_ok = False
                    envelope_detail_parts.append(
                        f"Z: stock {stock_z_mm} mm > travel {env.travel_z_mm} mm"
                    )

            if envelope_ok:
                checks.append(MachineFilterResult(
                    check_name="WORK_ENVELOPE_PASS",
                    status=MachineCandidateStatus.PASS,
                    detail="Stock fits within machine travel",
                ))
            else:
                detail = (
                    "; ".join(envelope_detail_parts)
                    if envelope_detail_parts
                    else "Envelope data insufficient"
                )
                checks.append(MachineFilterResult(
                    check_name="WORK_ENVELOPE_PASS",
                    status=MachineCandidateStatus.FAIL,
                    detail=detail,
                ))
                if overall != MachineCandidateStatus.FAIL:
                    overall = MachineCandidateStatus.FAIL
                    rejection = rejection or "WORK_ENVELOPE_FAIL"

        # -- Check 3: spindle RPM limit --------------------------------------
        if required_rpm_max is not None:
            spindle_max = machine.spindle.max_rpm if machine.spindle else None
            if spindle_max is None:
                checks.append(MachineFilterResult(
                    check_name="SPINDLE_LIMIT_PASS",
                    status=MachineCandidateStatus.REVIEW_REQUIRED,
                    detail="Machine spindle max_rpm not modeled",
                ))
                if overall == MachineCandidateStatus.PASS:
                    overall = MachineCandidateStatus.REVIEW_REQUIRED
            elif required_rpm_max <= spindle_max:
                checks.append(MachineFilterResult(
                    check_name="SPINDLE_LIMIT_PASS",
                    status=MachineCandidateStatus.PASS,
                    detail=f"Required {required_rpm_max:.0f} rpm <= machine {spindle_max:.0f} rpm",
                ))
            else:
                checks.append(MachineFilterResult(
                    check_name="SPINDLE_LIMIT_PASS",
                    status=MachineCandidateStatus.FAIL,
                    detail=f"Required {required_rpm_max:.0f} rpm > machine {spindle_max:.0f} rpm",
                ))
                if overall != MachineCandidateStatus.FAIL:
                    overall = MachineCandidateStatus.FAIL
                    rejection = rejection or "SPINDLE_LIMIT_EXCEEDED"

        candidates.append(MachineCandidate(
            machine=machine,
            overall_status=overall,
            checks=checks,
            rejection_reason=rejection,
        ))

    passing = [c for c in candidates if c.overall_status == MachineCandidateStatus.PASS]
    passing.sort(key=lambda c: c.machine.stable_id)

    return MachineSelectionResult(
        operation=operation,
        candidates=candidates,
        passing_candidates=passing,
        machine_selection_ready=len(passing) > 0,
        notes=(
            f"{len(passing)} machine(s) pass all checks out of "
            f"{len(candidates)} evaluated."
        ),
    )
