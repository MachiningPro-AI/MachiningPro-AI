"""
Engineer cutting parameter confirmation gate (P6-C).

Transitions cutting data from MANUFACTURER_STARTING_VALUE to USER_CONFIRMED.
NC_CANDIDATE_REVIEW_READY=NO until this gate is passed.

HARD RULES:
  - No auto-confirmation.
  - Values must be within the manufacturer starting-value range.
  - Machine spindle and feed limits are re-checked after confirmation.
  - session_id is used for traceability only; never sent to external services.
  - MANUFACTURER_STARTING_VALUE never reaches NC review-ready without this gate.

FABRICATED_CUTTING_DATA=NO
AUTO_CONFIRMATION=NO
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from backend.cutting_tools.cutting_parameters import CuttingDataStatus

__all__ = [
    "ParameterConfirmationStatus",
    "MachineParameterCheckResult",
    "EngineerConfirmedCuttingParameters",
    "ParameterConfirmationResult",
    "confirm_cutting_parameters",
]


class ParameterConfirmationStatus(StrEnum):
    ENGINEER_CONFIRMED = "ENGINEER_CONFIRMED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INVALID_PARAMETERS = "INVALID_PARAMETERS"
    OUT_OF_MANUFACTURER_RANGE = "OUT_OF_MANUFACTURER_RANGE"


@dataclass
class MachineParameterCheckResult:
    """Machine limit compliance for confirmed cutting parameters."""

    rpm_within_limit: bool
    feed_within_limit: bool
    machine_max_rpm: float | None
    machine_max_feed_mm_min: float | None
    actual_rpm: float
    actual_feed_mm_min: float
    warnings: list[str] = field(default_factory=list)


@dataclass
class EngineerConfirmedCuttingParameters:
    """Cutting parameters explicitly confirmed by an engineer.

    status=USER_CONFIRMED means: an engineer has explicitly selected values
    from the MANUFACTURER_STARTING_VALUE range.

    This does NOT mean:
    - Tested in production
    - Certified for this specific workpiece
    - Approved for autonomous or unattended use
    - Production-ready

    OFFLINE_ONLY=YES  AUTO_APPROVE=NO  DISPATCH=NO
    """

    tool_family: str
    material_grade: str
    diameter_mm: float
    operation: str
    # Selected values (from manufacturer range, chosen by engineer)
    vc_mpm: float
    fn_mm: float
    # Recalculated from confirmed selection
    rpm_calculated: float
    feed_rate_mm_min: float
    # Machine compliance
    machine_check: MachineParameterCheckResult
    # Source provenance (from manufacturer starting value record)
    source: str
    source_url: str
    # Confirmation metadata
    session_id: str | None
    confirmed_at: str
    status: CuttingDataStatus = CuttingDataStatus.USER_CONFIRMED
    notes: str = ""


@dataclass
class ParameterConfirmationResult:
    """Result of engineer cutting parameter confirmation."""

    status: ParameterConfirmationStatus
    confirmed_params: EngineerConfirmedCuttingParameters | None
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def confirm_cutting_parameters(
    *,
    session_id: str | None,
    tool_family: str,
    material_grade: str,
    diameter_mm: float,
    operation: str,
    vc_mpm: float,
    fn_mm: float,
    # Manufacturer starting-value range (for validation)
    vc_min_mpm: float,
    vc_max_mpm: float,
    fn_min_mm: float,
    fn_max_mm: float,
    source: str,
    source_url: str,
    machine_max_rpm: float | None = None,
    machine_max_feed_mm_min: float | None = None,
) -> ParameterConfirmationResult:
    """Confirm engineer-selected cutting parameters and check against machine limits.

    Validates:
    1. vc_mpm and fn_mm are finite positive numbers.
    2. Values are within the manufacturer starting-value range (with epsilon tolerance).
    3. Recalculates RPM = (Vc × 1000) / (π × D) and feed = RPM × fn.
    4. Checks recalculated RPM and feed against machine limits.

    Returns ENGINEER_CONFIRMED when all checks pass,
    REVIEW_REQUIRED when machine limits are exceeded (confirmed params still returned),
    INVALID_PARAMETERS or OUT_OF_MANUFACTURER_RANGE when values are out of bounds.
    """
    blockers: list[str] = []
    warnings: list[str] = []

    # --- 1. Basic validity ---
    if not math.isfinite(vc_mpm) or vc_mpm <= 0.0:
        blockers.append(
            f"INVALID_VC: vc_mpm={vc_mpm!r} must be a finite positive number"
        )
    if not math.isfinite(fn_mm) or fn_mm <= 0.0:
        blockers.append(
            f"INVALID_FN: fn_mm={fn_mm!r} must be a finite positive number"
        )
    if not math.isfinite(diameter_mm) or diameter_mm <= 0.0:
        blockers.append(
            f"INVALID_DIAMETER: diameter_mm={diameter_mm!r} must be a finite positive number"
        )

    if blockers:
        return ParameterConfirmationResult(
            status=ParameterConfirmationStatus.INVALID_PARAMETERS,
            confirmed_params=None,
            blockers=blockers,
        )

    # --- 2. Within manufacturer starting-value range ---
    _EPS = 1e-9
    range_errors: list[str] = []
    if vc_mpm < vc_min_mpm - _EPS or vc_mpm > vc_max_mpm + _EPS:
        range_errors.append(
            f"OUT_OF_MANUFACTURER_RANGE: vc_mpm={vc_mpm:.4f} "
            f"outside [{vc_min_mpm:.4f}, {vc_max_mpm:.4f}] m/min"
        )
    if fn_mm < fn_min_mm - _EPS or fn_mm > fn_max_mm + _EPS:
        range_errors.append(
            f"OUT_OF_MANUFACTURER_RANGE: fn_mm={fn_mm:.5f} "
            f"outside [{fn_min_mm:.5f}, {fn_max_mm:.5f}] mm/rev"
        )

    if range_errors:
        return ParameterConfirmationResult(
            status=ParameterConfirmationStatus.OUT_OF_MANUFACTURER_RANGE,
            confirmed_params=None,
            blockers=range_errors,
        )

    # --- 3. Recalculate RPM and feed ---
    rpm = (vc_mpm * 1000.0) / (math.pi * diameter_mm)
    feed_mm_min = rpm * fn_mm

    # --- 4. Machine limit checks ---
    rpm_ok = True
    feed_ok = True
    machine_warnings: list[str] = []

    if machine_max_rpm is not None:
        if rpm > machine_max_rpm + _EPS:
            rpm_ok = False
            machine_warnings.append(
                f"RPM_LIMIT_EXCEEDED: calculated={rpm:.1f} > machine_max={machine_max_rpm}"
            )

    if machine_max_feed_mm_min is not None:
        if feed_mm_min > machine_max_feed_mm_min + _EPS:
            feed_ok = False
            machine_warnings.append(
                f"FEED_LIMIT_EXCEEDED: calculated={feed_mm_min:.1f} mm/min "
                f"> machine_max={machine_max_feed_mm_min}"
            )

    machine_check = MachineParameterCheckResult(
        rpm_within_limit=rpm_ok,
        feed_within_limit=feed_ok,
        machine_max_rpm=machine_max_rpm,
        machine_max_feed_mm_min=machine_max_feed_mm_min,
        actual_rpm=round(rpm, 2),
        actual_feed_mm_min=round(feed_mm_min, 3),
        warnings=machine_warnings,
    )

    confirmed = EngineerConfirmedCuttingParameters(
        tool_family=tool_family,
        material_grade=material_grade,
        diameter_mm=diameter_mm,
        operation=operation,
        vc_mpm=vc_mpm,
        fn_mm=fn_mm,
        rpm_calculated=round(rpm, 2),
        feed_rate_mm_min=round(feed_mm_min, 3),
        machine_check=machine_check,
        source=source,
        source_url=source_url,
        session_id=session_id,
        confirmed_at=datetime.now(UTC).isoformat(),
        status=CuttingDataStatus.USER_CONFIRMED,
    )

    if not rpm_ok or not feed_ok:
        return ParameterConfirmationResult(
            status=ParameterConfirmationStatus.REVIEW_REQUIRED,
            confirmed_params=confirmed,
            warnings=machine_warnings,
        )

    return ParameterConfirmationResult(
        status=ParameterConfirmationStatus.ENGINEER_CONFIRMED,
        confirmed_params=confirmed,
        warnings=warnings,
    )
