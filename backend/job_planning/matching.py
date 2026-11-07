"""Level-17 capability matching — match CAM operation requirements to machine capabilities.

MISSING_DATA_FAILS_CLOSED=YES
UNKNOWN != COMPATIBLE
"""

from __future__ import annotations

from ..scheduling.enums import MachineClass
from .enums import CapabilityMatchLevel, MaterialCompatibilityResult, SpindleMatchResult
from .models import (
    CamOperationRequirements,
    CapabilityCheckResult,
    MachineCapabilityProfile,
    MaterialCompatibilityCheck,
    SpindleMatchCheck,
)

# ---------------------------------------------------------------------------
# Material → machine class compatibility table (conservative — not exhaustive)
# UNKNOWN material → UNKNOWN result (fail-closed)
# ---------------------------------------------------------------------------

_MATERIAL_CLASS_COMPATIBLE: dict[str, set[MachineClass]] = {
    "AL_6082_T6": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "AL_7075_T6": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "SS_304": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "SS_316L": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "ST_42CRMO4": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "ST_C45": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "CAST_IRON_GG25": {
        MachineClass.VMC_3AXIS, MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_3AXIS, MachineClass.HMC_4AXIS,
        MachineClass.LATHE_2AXIS, MachineClass.LATHE_LIVE_TOOL, MachineClass.TURN_MILL,
    },
    "TITANIUM_TI6AL4V": {
        MachineClass.VMC_4AXIS, MachineClass.VMC_5AXIS,
        MachineClass.HMC_4AXIS,
        MachineClass.TURN_MILL,
    },
}

# Materials NOT suitable for grinders in standard machining context
_GRINDER_INCOMPATIBLE_MATERIALS: set[str] = set()

# High-spindle-speed materials require TSC (through-spindle coolant) to be recommended
_TSC_PREFERRED_MATERIALS: set[str] = {"TITANIUM_TI6AL4V", "SS_316L"}


def check_material_compatibility(
    material: str | None,
    machine_class: MachineClass,
) -> MaterialCompatibilityCheck:
    """Check whether a material is compatible with a machine class.

    UNKNOWN material → UNKNOWN (fail-closed, not assumed compatible).
    UNKNOWN machine class → UNKNOWN.
    Material not in table → UNKNOWN (conservative).
    """
    if material is None:
        return MaterialCompatibilityCheck(
            material=material,
            machine_class=machine_class,
            result=MaterialCompatibilityResult.UNKNOWN,
            reason="Material not specified — cannot assess compatibility",
        )
    if machine_class == MachineClass.UNKNOWN:
        return MaterialCompatibilityCheck(
            material=material,
            machine_class=machine_class,
            result=MaterialCompatibilityResult.UNKNOWN,
            reason="Machine class UNKNOWN — cannot assess compatibility",
        )

    compatible_classes = _MATERIAL_CLASS_COMPATIBLE.get(material)
    if compatible_classes is None:
        return MaterialCompatibilityCheck(
            material=material,
            machine_class=machine_class,
            result=MaterialCompatibilityResult.UNKNOWN,
            reason=f"Material '{material}' not in compatibility table — unknown",
        )
    if machine_class in compatible_classes:
        return MaterialCompatibilityCheck(
            material=material,
            machine_class=machine_class,
            result=MaterialCompatibilityResult.COMPATIBLE,
            reason=f"{material} is compatible with {machine_class}",
        )
    return MaterialCompatibilityCheck(
        material=material,
        machine_class=machine_class,
        result=MaterialCompatibilityResult.INCOMPATIBLE,
        reason=f"{material} is not in the compatible set for {machine_class}",
    )


# Spindle utilization thresholds
_SPINDLE_AT_LIMIT_PCT = 95.0
_SPINDLE_HIGH_UTIL_PCT = 85.0


def check_spindle_requirements(
    required_rpm: float | None,
    machine_max_rpm: int | None,
) -> SpindleMatchCheck:
    """Check whether a machine's spindle can satisfy the required RPM.

    UNKNOWN machine RPM → UNKNOWN (fail-closed).
    No requirement → WITHIN_RANGE (no constraint to violate).
    """
    if required_rpm is None:
        return SpindleMatchCheck(
            required_rpm=None,
            machine_max_rpm=machine_max_rpm,
            result=SpindleMatchResult.WITHIN_RANGE,
            utilization_pct=None,
        )
    if machine_max_rpm is None:
        return SpindleMatchCheck(
            required_rpm=required_rpm,
            machine_max_rpm=None,
            result=SpindleMatchResult.UNKNOWN,
            utilization_pct=None,
        )
    if machine_max_rpm <= 0:
        return SpindleMatchCheck(
            required_rpm=required_rpm,
            machine_max_rpm=machine_max_rpm,
            result=SpindleMatchResult.UNDER_SPEC,
            utilization_pct=None,
        )

    util_pct = (required_rpm / machine_max_rpm) * 100.0

    if required_rpm > machine_max_rpm:
        return SpindleMatchCheck(
            required_rpm=required_rpm,
            machine_max_rpm=machine_max_rpm,
            result=SpindleMatchResult.OVER_LIMIT,
            utilization_pct=util_pct,
        )
    if util_pct >= _SPINDLE_AT_LIMIT_PCT:
        return SpindleMatchCheck(
            required_rpm=required_rpm,
            machine_max_rpm=machine_max_rpm,
            result=SpindleMatchResult.AT_LIMIT,
            utilization_pct=util_pct,
        )
    return SpindleMatchCheck(
        required_rpm=required_rpm,
        machine_max_rpm=machine_max_rpm,
        result=SpindleMatchResult.WITHIN_RANGE,
        utilization_pct=util_pct,
    )


def check_process_capabilities(
    requirements: CamOperationRequirements,
    profile: MachineCapabilityProfile,
) -> list[CapabilityCheckResult]:
    """Check all process capability requirements against a machine capability profile."""
    results: list[CapabilityCheckResult] = []

    # Turning capability
    if "TURNING" in requirements.operations or "FINISH_TURNING" in requirements.operations:
        if not profile.turning_capable:
            results.append(CapabilityCheckResult(
                check_name="turning_capability",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires turning but machine is not turning-capable",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="turning_capability",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine supports turning",
            ))

    # Milling capability
    if any(op in requirements.operations for op in (
        "MILLING", "ROUGHING_MILLING", "FINISH_MILLING", "FACE_MILLING",
        "POCKET_MILLING", "CONTOUR_MILLING",
    )):
        if not profile.milling_capable:
            results.append(CapabilityCheckResult(
                check_name="milling_capability",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires milling but machine is not milling-capable",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="milling_capability",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine supports milling",
            ))

    # Drilling
    if any(op in requirements.operations for op in ("DRILLING", "DEEP_DRILLING")):
        if not profile.drilling_capable:
            results.append(CapabilityCheckResult(
                check_name="drilling_capability",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires drilling but machine is not drilling-capable",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="drilling_capability",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine supports drilling",
            ))

    # Tapping
    if requirements.requires_tapping:
        if profile.capable_tapping is None:
            results.append(CapabilityCheckResult(
                check_name="tapping_capability",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="Tapping capability unknown for this machine",
            ))
        elif not profile.capable_tapping:
            results.append(CapabilityCheckResult(
                check_name="tapping_capability",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires tapping but machine does not support it",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="tapping_capability",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine supports tapping",
            ))

    # Boring
    if requirements.requires_boring:
        if profile.capable_boring is None:
            results.append(CapabilityCheckResult(
                check_name="boring_capability",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="Boring capability unknown for this machine",
            ))
        elif not profile.capable_boring:
            results.append(CapabilityCheckResult(
                check_name="boring_capability",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires boring but machine does not support it",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="boring_capability",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine supports boring",
            ))

    # Live tooling
    if requirements.requires_live_tooling:
        if not profile.has_live_tooling:
            results.append(CapabilityCheckResult(
                check_name="live_tooling",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires live tooling but machine does not have it",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="live_tooling",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine has live tooling",
            ))

    # Through-spindle coolant
    if requirements.requires_through_spindle_coolant:
        if profile.through_spindle_coolant is None:
            results.append(CapabilityCheckResult(
                check_name="through_spindle_coolant",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="Through-spindle coolant capability unknown",
            ))
        elif not profile.through_spindle_coolant:
            results.append(CapabilityCheckResult(
                check_name="through_spindle_coolant",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail="Job requires TSC but machine does not have it",
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="through_spindle_coolant",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail="Machine has through-spindle coolant",
            ))

    # Axis count
    if requirements.required_axis_count is not None:
        if profile.axis_count is None:
            results.append(CapabilityCheckResult(
                check_name="axis_count",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="Machine axis count unknown",
            ))
        elif profile.axis_count < requirements.required_axis_count:
            results.append(CapabilityCheckResult(
                check_name="axis_count",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail=(
                    f"Required {requirements.required_axis_count} axes, "
                    f"machine has {profile.axis_count}"
                ),
            ))
        elif profile.axis_count > requirements.required_axis_count:
            results.append(CapabilityCheckResult(
                check_name="axis_count",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail=(
                    f"Machine has {profile.axis_count} axes "
                    f"(required {requirements.required_axis_count}) — surplus axes"
                ),
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="axis_count",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail=f"Axis count matches: {profile.axis_count}",
            ))

    # Work envelope — X
    if requirements.required_x_travel_mm is not None:
        if profile.travel_x_mm is None:
            results.append(CapabilityCheckResult(
                check_name="x_travel",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="X travel unknown",
            ))
        elif profile.travel_x_mm < requirements.required_x_travel_mm:
            results.append(CapabilityCheckResult(
                check_name="x_travel",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail=(
                    f"X travel {profile.travel_x_mm}mm < "
                    f"required {requirements.required_x_travel_mm}mm"
                ),
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="x_travel",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail=f"X travel {profile.travel_x_mm}mm sufficient",
            ))

    # Work envelope — Y
    if requirements.required_y_travel_mm is not None:
        if profile.travel_y_mm is None:
            results.append(CapabilityCheckResult(
                check_name="y_travel",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="Y travel unknown",
            ))
        elif profile.travel_y_mm < requirements.required_y_travel_mm:
            results.append(CapabilityCheckResult(
                check_name="y_travel",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail=(
                    f"Y travel {profile.travel_y_mm}mm < "
                    f"required {requirements.required_y_travel_mm}mm"
                ),
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="y_travel",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail=f"Y travel {profile.travel_y_mm}mm sufficient",
            ))

    # Work envelope — Z
    if requirements.required_z_travel_mm is not None:
        if profile.travel_z_mm is None:
            results.append(CapabilityCheckResult(
                check_name="z_travel",
                match_level=CapabilityMatchLevel.UNKNOWN,
                detail="Z travel unknown",
            ))
        elif profile.travel_z_mm < requirements.required_z_travel_mm:
            results.append(CapabilityCheckResult(
                check_name="z_travel",
                match_level=CapabilityMatchLevel.NO_MATCH,
                detail=(
                    f"Z travel {profile.travel_z_mm}mm < "
                    f"required {requirements.required_z_travel_mm}mm"
                ),
            ))
        else:
            results.append(CapabilityCheckResult(
                check_name="z_travel",
                match_level=CapabilityMatchLevel.FULL_MATCH,
                detail=f"Z travel {profile.travel_z_mm}mm sufficient",
            ))

    return results
