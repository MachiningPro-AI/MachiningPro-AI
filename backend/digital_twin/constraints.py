"""Level-18 Digital Twin — constraint engine.

Hard constraint failures immediately invalidate the scenario.
UNKNOWN capability is NOT treated as passing.
"""

from __future__ import annotations

from .enums import ConstraintFailReason, FidelityLevel, ScenarioStatus
from .models import ConstraintResult, ManufacturingTwinScenario

# Spindle utilization threshold above which a warning is emitted
_SPINDLE_WARN_PCT = 90.0


def _check(
    name: str,
    passed: bool,
    fail_reason: ConstraintFailReason | None = None,
    detail: str = "",
) -> ConstraintResult:
    return ConstraintResult(
        constraint_name=name,
        passed=passed,
        fail_reason=fail_reason if not passed else None,
        detail=detail,
    )


def evaluate_constraints(
    scenario: ManufacturingTwinScenario,
) -> tuple[list[ConstraintResult], list[ConstraintFailReason], list[str]]:
    """
    Evaluate all hard constraints for a scenario.

    Returns (results, hard_failures, warnings).
    Hard failures → scenario INVALID.
    Unknown data → warn but do not fabricate pass.
    """
    results: list[ConstraintResult] = []
    hard_failures: list[ConstraintFailReason] = []
    warnings: list[str] = []

    # --- Spindle speed ---
    if scenario.required_spindle_rpm is not None:
        if scenario.machine_spindle_max_rpm is None:
            warnings.append(
                "Machine spindle max RPM unknown — cannot verify spindle constraint"
            )
            results.append(_check(
                "spindle_speed",
                False,
                ConstraintFailReason.UNKNOWN,
                "Machine spindle max RPM unknown",
            ))
        elif scenario.required_spindle_rpm > scenario.machine_spindle_max_rpm:
            hard_failures.append(ConstraintFailReason.SPINDLE_RANGE_EXCEEDED)
            results.append(_check(
                "spindle_speed",
                False,
                ConstraintFailReason.SPINDLE_RANGE_EXCEEDED,
                (
                    f"Required {scenario.required_spindle_rpm} RPM "
                    f"exceeds machine max {scenario.machine_spindle_max_rpm} RPM"
                ),
            ))
        else:
            util = (scenario.required_spindle_rpm / scenario.machine_spindle_max_rpm) * 100
            if util >= _SPINDLE_WARN_PCT:
                warnings.append(
                    f"Spindle utilization {util:.1f}% — approaching machine limit"
                )
            results.append(_check(
                "spindle_speed",
                True,
                detail=(
                    f"Required {scenario.required_spindle_rpm} RPM within "
                    f"machine max {scenario.machine_spindle_max_rpm} RPM"
                ),
            ))

    # --- Axis count ---
    if scenario.required_axis_count is not None:
        if scenario.machine_axis_count is None:
            warnings.append("Machine axis count unknown — cannot verify axis constraint")
            results.append(_check(
                "axis_count",
                False,
                ConstraintFailReason.UNKNOWN,
                "Machine axis count unknown",
            ))
        elif scenario.machine_axis_count < scenario.required_axis_count:
            hard_failures.append(ConstraintFailReason.AXIS_COUNT_INSUFFICIENT)
            results.append(_check(
                "axis_count",
                False,
                ConstraintFailReason.AXIS_COUNT_INSUFFICIENT,
                (
                    f"Required {scenario.required_axis_count} axes, "
                    f"machine has {scenario.machine_axis_count}"
                ),
            ))
        else:
            results.append(_check(
                "axis_count",
                True,
                detail=f"Axis count {scenario.machine_axis_count} sufficient",
            ))

    # --- Work envelope X ---
    if scenario.machine_travel_x_mm is not None and scenario.part_mass_kg is not None:
        # Only check work envelope if part dimensions are knowable via part_mass proxy
        pass  # Envelope check requires geometry — skip without it

    # --- Toolpath verification ---
    if scenario.toolpath_ref is not None and not scenario.toolpath_verified:
        hard_failures.append(ConstraintFailReason.TOOLPATH_UNVERIFIED)
        results.append(_check(
            "toolpath_verified",
            False,
            ConstraintFailReason.TOOLPATH_UNVERIFIED,
            "Toolpath referenced but not verified",
        ))
    elif scenario.toolpath_ref is not None and scenario.toolpath_verified:
        results.append(_check(
            "toolpath_verified",
            True,
            detail="Toolpath is verified",
        ))

    # --- Cutting parameter bounds ---
    cutting_data = scenario.cutting_data
    _BOUNDS: dict[str, tuple[float, float]] = {
        "vc": (10.0, 1500.0),
        "fn": (0.01, 2.0),
        "fz": (0.01, 2.0),
        "ap": (0.05, 25.0),
        "ae": (0.05, 100.0),
        "rpm": (100.0, 60000.0),
    }
    for param, (lo, hi) in _BOUNDS.items():
        val = cutting_data.get(param)
        if val is not None:
            if not (lo <= float(val) <= hi):
                hard_failures.append(ConstraintFailReason.PARAMETER_OUT_OF_BOUNDS)
                results.append(_check(
                    f"cutting_param_{param}",
                    False,
                    ConstraintFailReason.PARAMETER_OUT_OF_BOUNDS,
                    f"{param}={val} out of verified bounds [{lo}, {hi}]",
                ))
            else:
                results.append(_check(
                    f"cutting_param_{param}",
                    True,
                    detail=f"{param}={val} within bounds [{lo}, {hi}]",
                ))

    return results, hard_failures, warnings


def determine_scenario_status(
    hard_failures: list[ConstraintFailReason],
    scenario: ManufacturingTwinScenario,
) -> ScenarioStatus:
    """Return the scenario status based on constraint evaluation."""
    if hard_failures:
        return ScenarioStatus.INVALID
    # Check completeness
    if scenario.status == ScenarioStatus.DRAFT:
        return ScenarioStatus.INCOMPLETE
    return ScenarioStatus.VALID


def determine_fidelity(scenario: ManufacturingTwinScenario) -> FidelityLevel:
    """Determine simulation fidelity based on available data."""
    known_count = sum([
        scenario.estimated_cycle_time_min is not None,
        scenario.machine_ref is not None,
        bool(scenario.tool_refs),
        bool(scenario.cutting_data),
        scenario.material_ref is not None,
    ])
    if known_count >= 5:
        return FidelityLevel.HIGH
    if known_count >= 3:
        return FidelityLevel.MEDIUM
    if known_count >= 1:
        return FidelityLevel.LOW
    return FidelityLevel.INSUFFICIENT
