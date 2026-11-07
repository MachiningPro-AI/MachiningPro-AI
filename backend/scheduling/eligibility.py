"""
Level-13 Machine Eligibility — deterministic hard-constraint checking.

INELIGIBLE machines are never ranked.
UNKNOWN capability != eligible.
Compatibility and availability are separate checks.
"""

from __future__ import annotations

from .enums import EligibilityFailReason, MachineEligibilityResult
from .models import (
    EligibilityCheckResult,
    EligibilityReport,
    MachineRequirements,
    MachineResource,
    ProductionJob,
)


def _check(
    name: str,
    passed: bool,
    fail_reason: EligibilityFailReason | None = None,
    detail: str = "",
) -> EligibilityCheckResult:
    return EligibilityCheckResult(
        check_name=name,
        passed=passed,
        fail_reason=fail_reason if not passed else None,
        detail=detail,
    )


def check_machine_eligibility(
    job: ProductionJob,
    machine: MachineResource,
) -> EligibilityReport:
    """
    Run all hard-constraint eligibility checks for a job against a machine.

    Returns EligibilityReport with result ELIGIBLE / PARTIALLY_ELIGIBLE /
    INELIGIBLE / UNKNOWN.

    Hard failures immediately mark INELIGIBLE.
    Unknown required data marks UNKNOWN or PARTIALLY_ELIGIBLE.
    """
    req: MachineRequirements = job.machine_requirements
    checks: list[EligibilityCheckResult] = []
    hard_failures: list[EligibilityFailReason] = []
    unknowns: list[str] = []
    soft_score = 0.0

    # --- machine class ---
    from .enums import MachineClass
    if req.required_machine_class != MachineClass.UNKNOWN:
        if machine.machine_class == MachineClass.UNKNOWN:
            unknowns.append("machine_class")
            checks.append(_check(
                "machine_class",
                False,
                EligibilityFailReason.UNKNOWN,
                "Machine class unknown — cannot verify compatibility",
            ))
        elif machine.machine_class != req.required_machine_class:
            # Allow TURN_MILL to satisfy LATHE requirements
            compatible = _class_compatible(machine.machine_class, req.required_machine_class)
            if not compatible:
                hard_failures.append(EligibilityFailReason.MACHINE_CLASS_MISMATCH)
            checks.append(_check(
                "machine_class",
                compatible,
                EligibilityFailReason.MACHINE_CLASS_MISMATCH if not compatible else None,
                f"Required {req.required_machine_class}, machine is {machine.machine_class}",
            ))
        else:
            checks.append(_check("machine_class", True, detail="Class matches"))
    # else: no specific class required — skip

    # --- axis count ---
    if req.required_axis_count is not None:
        if machine.axis_count is None:
            unknowns.append("axis_count")
            checks.append(_check(
                "axis_count",
                False,
                EligibilityFailReason.UNKNOWN,
                "Machine axis count unknown",
            ))
        elif machine.axis_count < req.required_axis_count:
            hard_failures.append(EligibilityFailReason.AXIS_COUNT_INSUFFICIENT)
            checks.append(_check(
                "axis_count",
                False,
                EligibilityFailReason.AXIS_COUNT_INSUFFICIENT,
                f"Required {req.required_axis_count} axes, machine has {machine.axis_count}",
            ))
        else:
            checks.append(_check("axis_count", True, detail="Axis count sufficient"))
            if machine.axis_count > req.required_axis_count:
                soft_score += 0.5  # bonus axes available

    # --- work envelope ---
    if req.required_x_travel_mm is not None:
        if machine.x_travel_mm is None:
            unknowns.append("x_travel_mm")
            checks.append(_check(
                "x_travel",
                False,
                EligibilityFailReason.UNKNOWN,
                "X travel unknown",
            ))
        elif machine.x_travel_mm < req.required_x_travel_mm:
            hard_failures.append(EligibilityFailReason.WORK_ENVELOPE_TOO_SMALL)
            checks.append(_check(
                "x_travel",
                False,
                EligibilityFailReason.WORK_ENVELOPE_TOO_SMALL,
                f"X travel {machine.x_travel_mm}mm < required {req.required_x_travel_mm}mm",
            ))
        else:
            checks.append(_check("x_travel", True))

    if req.required_y_travel_mm is not None:
        if machine.y_travel_mm is None:
            unknowns.append("y_travel_mm")
            checks.append(_check(
                "y_travel", False, EligibilityFailReason.UNKNOWN, "Y travel unknown"
            ))
        elif machine.y_travel_mm < req.required_y_travel_mm:
            hard_failures.append(EligibilityFailReason.WORK_ENVELOPE_TOO_SMALL)
            checks.append(_check(
                "y_travel",
                False,
                EligibilityFailReason.WORK_ENVELOPE_TOO_SMALL,
                f"Y travel {machine.y_travel_mm}mm < required {req.required_y_travel_mm}mm",
            ))
        else:
            checks.append(_check("y_travel", True))

    if req.required_z_travel_mm is not None:
        if machine.z_travel_mm is None:
            unknowns.append("z_travel_mm")
            checks.append(_check(
                "z_travel", False, EligibilityFailReason.UNKNOWN, "Z travel unknown"
            ))
        elif machine.z_travel_mm < req.required_z_travel_mm:
            hard_failures.append(EligibilityFailReason.WORK_ENVELOPE_TOO_SMALL)
            checks.append(_check(
                "z_travel",
                False,
                EligibilityFailReason.WORK_ENVELOPE_TOO_SMALL,
                f"Z travel {machine.z_travel_mm}mm < required {req.required_z_travel_mm}mm",
            ))
        else:
            checks.append(_check("z_travel", True))

    # --- spindle speed ---
    if req.required_spindle_speed_rpm is not None:
        if machine.spindle_speed_max_rpm is None:
            unknowns.append("spindle_speed_max_rpm")
            checks.append(_check(
                "spindle_speed",
                False,
                EligibilityFailReason.UNKNOWN,
                "Spindle speed capability unknown",
            ))
        elif machine.spindle_speed_max_rpm < req.required_spindle_speed_rpm:
            hard_failures.append(EligibilityFailReason.SPINDLE_SPEED_INSUFFICIENT)
            checks.append(_check(
                "spindle_speed",
                False,
                EligibilityFailReason.SPINDLE_SPEED_INSUFFICIENT,
                f"Max RPM {machine.spindle_speed_max_rpm}"
                f" < required {req.required_spindle_speed_rpm}",
            ))
        else:
            checks.append(_check("spindle_speed", True))

    # --- turning / milling capability ---
    if req.requires_turning and not machine.supports_turning:
        hard_failures.append(EligibilityFailReason.TURNING_CAPABILITY_MISSING)
        checks.append(_check(
            "turning_capability",
            False,
            EligibilityFailReason.TURNING_CAPABILITY_MISSING,
            "Job requires turning but machine does not support it",
        ))

    if req.requires_milling and not machine.supports_milling:
        hard_failures.append(EligibilityFailReason.MILLING_CAPABILITY_MISSING)
        checks.append(_check(
            "milling_capability",
            False,
            EligibilityFailReason.MILLING_CAPABILITY_MISSING,
            "Job requires milling but machine does not support it",
        ))

    # --- load capacity ---
    if req.max_workpiece_mass_kg is not None:
        if machine.table_load_capacity_kg is None and machine.chuck_capacity_mm is None:
            unknowns.append("load_capacity")
            checks.append(_check(
                "load_capacity",
                False,
                EligibilityFailReason.UNKNOWN,
                "Machine load capacity unknown",
            ))
        elif (
            machine.table_load_capacity_kg is not None
            and machine.table_load_capacity_kg < req.max_workpiece_mass_kg
        ):
            hard_failures.append(EligibilityFailReason.LOAD_CAPACITY_EXCEEDED)
            checks.append(_check(
                "load_capacity",
                False,
                EligibilityFailReason.LOAD_CAPACITY_EXCEEDED,
                f"Table capacity {machine.table_load_capacity_kg}kg"
                f" < workpiece {req.max_workpiece_mass_kg}kg",
            ))
        else:
            checks.append(_check("load_capacity", True))

    # --- post profile / controller ---
    if req.required_post_profile_id:
        if not machine.supported_post_profile_ids:
            unknowns.append("post_profile")
            checks.append(_check(
                "post_profile",
                False,
                EligibilityFailReason.UNKNOWN,
                "Machine post-profile support unknown",
            ))
        elif req.required_post_profile_id not in machine.supported_post_profile_ids:
            hard_failures.append(EligibilityFailReason.POST_PROFILE_INCOMPATIBLE)
            checks.append(_check(
                "post_profile",
                False,
                EligibilityFailReason.POST_PROFILE_INCOMPATIBLE,
                f"Post profile {req.required_post_profile_id} not in machine supported list",
            ))
        else:
            checks.append(_check("post_profile", True))
            soft_score += 1.0  # exact post profile match

    # --- soft: short queue ---
    # (scored in scheduler, not here — but noted)

    # --- determine overall result ---
    if hard_failures:
        result = MachineEligibilityResult.INELIGIBLE
    elif unknowns:
        # Has unknowns but no hard failures
        result = (
            MachineEligibilityResult.PARTIALLY_ELIGIBLE if checks
            else MachineEligibilityResult.UNKNOWN
        )
    elif not checks:
        # No requirements specified — machine is generically eligible
        result = MachineEligibilityResult.ELIGIBLE
    else:
        all_pass = all(c.passed for c in checks)
        result = (
            MachineEligibilityResult.ELIGIBLE if all_pass
            else MachineEligibilityResult.PARTIALLY_ELIGIBLE
        )

    return EligibilityReport(
        machine_id=machine.machine_id,
        result=result,
        checks=checks,
        hard_constraint_failures=hard_failures,
        soft_preference_score=soft_score,
        unknown_data_fields=unknowns,
        warnings=req.warnings[:],
    )


def _class_compatible(machine_class: str, required_class: str) -> bool:
    """TURN_MILL can satisfy lathe requirements; check sub-class compatibility."""
    from .enums import MachineClass
    if machine_class == required_class:
        return True
    # TURN_MILL satisfies LATHE requirements
    if required_class in (MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL):
        return machine_class == MachineClass.TURN_MILL
    # VMC_5AXIS satisfies VMC_3AXIS / VMC_4AXIS requirements
    if required_class in (MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS):
        return machine_class == MachineClass.VMC_5AXIS
    if required_class == MachineClass.VMC_4AXIS:
        return machine_class == MachineClass.VMC_5AXIS
    return False


def rank_eligible_machines(
    reports: list[EligibilityReport],
    queue_depths: dict[str, int] | None = None,
) -> list[EligibilityReport]:
    """
    Return eligible machines ranked by soft preference score.

    INELIGIBLE machines are excluded from the ranked list.
    Unknown queue depth is treated as a neutral score (0).
    """
    from .enums import MachineEligibilityResult
    eligible = [
        r for r in reports
        if r.result in (
            MachineEligibilityResult.ELIGIBLE,
            MachineEligibilityResult.PARTIALLY_ELIGIBLE,
        )
    ]

    def rank_key(report: EligibilityReport) -> tuple[float, float]:
        queue_penalty = 0.0
        if queue_depths:
            depth = queue_depths.get(report.machine_id, 0)
            queue_penalty = -float(depth) * 0.1
        # ELIGIBLE ranks above PARTIALLY_ELIGIBLE
        eligibility_bonus = (
            1.0 if report.result == MachineEligibilityResult.ELIGIBLE else 0.0
        )
        return (eligibility_bonus + report.soft_preference_score + queue_penalty,)

    return sorted(eligible, key=lambda r: rank_key(r)[0], reverse=True)
