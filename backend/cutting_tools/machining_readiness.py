"""Machining Readiness assessment layer.

Evaluates whether a validated ToolAssemblyRecord is capable of performing a
specific machining operation under declared process conditions.

Design rules
------------
- FAIL takes precedence over UNKNOWN.
- Missing required information never produces PASS.
- Machine Library and Material Library are NOT imported; their relevant data
  is accepted as plain string/numeric fields in MachiningReadinessRequest.
  This keeps the Tool Library fully independent while providing clear
  integration points for future library wiring.
"""
from __future__ import annotations

from pydantic import BaseModel

from .assembly_compatibility import validate_assembly
from .assembly_models import ToolAssemblyRecord, ToolAssemblyValidationResult
from .compatibility import CompatibilityResult, CompatibilityStatus

# Operations supported across all 9 tool families
_SUPPORTED_OPERATIONS: frozenset[str] = frozenset({
    "drilling", "milling", "turning", "boring", "threading", "tapping",
    "reaming", "grooving", "grinding",
    "edm", "edm wire cutting", "edm sinker",
})


# ── Request and result models ─────────────────────────────────────────────────

class MachiningReadinessRequest(BaseModel):
    """Declared process conditions for a machining operation.

    Machine Library integration point
    ----------------------------------
    ``spindle_interface_required`` carries the machine spindle type as a plain
    string (e.g. ``"BT40"``, ``"HSK-A63"``).  Wire this from the Machine
    Library when available; leave None when the machine is unknown.

    Material Library integration point
    ------------------------------------
    ``workpiece_material_group`` carries the ISO 513 material group code
    (P / M / K / N / S / H) as a plain string.  Wire this from the Material
    Library when available; leave None when the material is unknown.
    """

    operation: str                                # drilling, milling, turning, …
    workpiece_material_group: str | None = None   # ISO 513: P/M/K/N/S/H
    required_cutting_diameter_mm: float | None = None
    required_reach_mm: float | None = None
    required_cutting_length_mm: float | None = None
    spindle_interface_required: str | None = None  # BT40, HSK-A63, etc.
    coolant_required: bool | None = None
    max_runout_mm: float | None = None


class OperationCompatibility(BaseModel):
    """Compatibility result for the requested operation against the assembly."""

    operation: str
    result: CompatibilityResult


class MachiningReadinessResult(BaseModel):
    """Final readiness verdict."""

    status: CompatibilityStatus
    reasons: list[str]


class ToolAssemblyCompatibility(BaseModel):
    """Full machining readiness assessment for one assembly + request pair."""

    assembly_stable_id: str
    request: MachiningReadinessRequest
    assembly_validation: ToolAssemblyValidationResult
    operation_check: OperationCompatibility
    material_check: CompatibilityResult
    dimension_check: CompatibilityResult
    machine_interface_check: CompatibilityResult
    coolant_check: CompatibilityResult
    runout_check: CompatibilityResult
    overall: MachiningReadinessResult


# ── Individual check helpers ──────────────────────────────────────────────────

def _r_pass(reasons: list[str]) -> CompatibilityResult:
    return CompatibilityResult(status=CompatibilityStatus.PASS, reasons=reasons)


def _r_fail(reasons: list[str]) -> CompatibilityResult:
    return CompatibilityResult(status=CompatibilityStatus.FAIL, reasons=reasons)


def _r_unknown(reasons: list[str]) -> CompatibilityResult:
    return CompatibilityResult(status=CompatibilityStatus.UNKNOWN, reasons=reasons)


def _check_operation(
    assembly: ToolAssemblyRecord, operation: str
) -> OperationCompatibility:
    op = operation.lower().strip()
    tool_ops = {o.lower() for o in assembly.tool.supported_operations}
    if op in tool_ops:
        result = _r_pass([f"Tool supports operation {op!r}"])
    else:
        result = _r_fail([
            f"Operation {op!r} not in tool supported_operations: {sorted(tool_ops)}"
        ])
    return OperationCompatibility(operation=op, result=result)


def _check_material(
    assembly: ToolAssemblyRecord, group: str | None
) -> CompatibilityResult:
    if group is None:
        return _r_unknown([
            "workpiece_material_group is None — material compatibility unverified "
            "(wire Material Library when available)"
        ])
    g = group.upper().strip()
    valid = {"P", "M", "K", "N", "S", "H"}
    if g not in valid:
        return _r_fail([f"workpiece_material_group {g!r} is not a valid ISO 513 code"])
    tool_groups = {m.upper() for m in assembly.tool.iso_material_groups}
    if g in tool_groups:
        return _r_pass([f"Tool supports workpiece material group {g!r}"])
    return _r_fail([
        f"Workpiece material group {g!r} not in tool iso_material_groups: "
        f"{sorted(tool_groups)}"
    ])


def _check_dimensions(
    assembly: ToolAssemblyRecord, request: MachiningReadinessRequest
) -> CompatibilityResult:
    failures: list[str] = []
    unknowns: list[str] = []
    passes: list[str] = []

    # Cutting diameter
    if request.required_cutting_diameter_mm is not None:
        actual = assembly.tool.cutting_diameter_mm
        if actual is None:
            unknowns.append(
                "tool.cutting_diameter_mm is None — cannot verify required "
                f"cutting diameter {request.required_cutting_diameter_mm}mm"
            )
        elif abs(actual - request.required_cutting_diameter_mm) > 0.001:
            failures.append(
                f"tool.cutting_diameter_mm={actual}mm ≠ required "
                f"{request.required_cutting_diameter_mm}mm"
            )
        else:
            passes.append(
                f"Cutting diameter {actual}mm matches required "
                f"{request.required_cutting_diameter_mm}mm"
            )

    # Required reach
    if request.required_reach_mm is not None:
        reach = assembly.geometry.effective_reach_mm
        if reach is None:
            unknowns.append(
                f"geometry.effective_reach_mm is None — cannot verify "
                f"required reach {request.required_reach_mm}mm"
            )
        elif reach < request.required_reach_mm:
            failures.append(
                f"assembly.geometry.effective_reach_mm={reach}mm < "
                f"required {request.required_reach_mm}mm"
            )
        else:
            passes.append(
                f"Effective reach {reach}mm ≥ required {request.required_reach_mm}mm"
            )

    # Required cutting length
    if request.required_cutting_length_mm is not None:
        cl = assembly.tool.cutting_length_mm
        if cl is None:
            unknowns.append(
                "tool.cutting_length_mm is None — cannot verify required "
                f"cutting length {request.required_cutting_length_mm}mm"
            )
        elif cl < request.required_cutting_length_mm:
            failures.append(
                f"tool.cutting_length_mm={cl}mm < required "
                f"{request.required_cutting_length_mm}mm"
            )
        else:
            passes.append(
                f"Cutting length {cl}mm ≥ required "
                f"{request.required_cutting_length_mm}mm"
            )

    if not failures and not unknowns and not passes:
        return _r_pass(["No dimension requirements specified"])

    if failures:
        note = (["(unknowns: " + "; ".join(unknowns) + ")"] if unknowns else [])
        return _r_fail(failures + note)
    if unknowns:
        return _r_unknown(unknowns)
    return _r_pass(passes)


def _check_machine_interface(
    assembly: ToolAssemblyRecord, required: str | None
) -> CompatibilityResult:
    if required is None:
        return _r_unknown([
            "spindle_interface_required is None — machine interface compatibility "
            "unverified (wire Machine Library when available)"
        ])
    actual = assembly.geometry.spindle_interface or assembly.holder.spindle_interface
    if actual is None:
        return _r_unknown([
            f"spindle_interface_required={required!r} but assembly has no declared "
            "spindle_interface"
        ])
    if actual.lower() != required.lower():
        return _r_fail([
            f"Assembly spindle interface {actual!r} ≠ required {required!r}"
        ])
    return _r_pass([f"Spindle interface {actual!r} matches requirement"])


def _check_coolant(
    assembly: ToolAssemblyRecord, required: bool | None
) -> CompatibilityResult:
    if required is None:
        return _r_pass(["No coolant requirement specified"])
    if required is False:
        return _r_pass(["Coolant not required by request"])
    # required is True
    enabled = assembly.geometry.coolant_enabled
    holder_capable = assembly.holder.supports_coolant
    if enabled is True:
        return _r_pass(["Coolant enabled in assembly geometry"])
    if enabled is False:
        return _r_fail(["Coolant required but assembly.geometry.coolant_enabled=False"])
    # enabled is None — check holder capability
    if holder_capable is False:
        return _r_fail(["Coolant required but holder.supports_coolant=False"])
    if holder_capable is None:
        return _r_unknown(["Coolant required but neither geometry nor holder confirm support"])
    return _r_pass(["Coolant required; holder reports support (geometry not declared)"])


def _check_runout(
    assembly: ToolAssemblyRecord, max_runout_mm: float | None
) -> CompatibilityResult:
    if max_runout_mm is None:
        return _r_pass(["No runout requirement specified"])
    holder_runout = assembly.holder.capacity.max_runout_mm
    if holder_runout is None:
        return _r_unknown([
            f"max_runout_mm required ≤ {max_runout_mm}mm but "
            "holder.capacity.max_runout_mm is None"
        ])
    if holder_runout > max_runout_mm:
        return _r_fail([
            f"Holder max runout {holder_runout}mm exceeds allowed {max_runout_mm}mm"
        ])
    return _r_pass([
        f"Holder max runout {holder_runout}mm ≤ required {max_runout_mm}mm"
    ])


# ── Public API ────────────────────────────────────────────────────────────────

def assess_machining_readiness(
    assembly: ToolAssemblyRecord,
    request: MachiningReadinessRequest,
) -> ToolAssemblyCompatibility:
    """Evaluate whether *assembly* can perform the operation in *request*.

    Steps
    -----
    1. Validate the assembly (tool-holder + geometry via assembly_compatibility).
    2. Check the requested operation is supported by the tool.
    3. Check workpiece material group compatibility.
    4. Check required dimensions (diameter, reach, cutting length).
    5. Check spindle interface.
    6. Check coolant requirement.
    7. Check runout limit.

    Overall status is the worst of all individual check statuses
    (FAIL > UNKNOWN > PASS).
    """
    assembly_validation: ToolAssemblyValidationResult = validate_assembly(assembly)
    operation_check = _check_operation(assembly, request.operation)
    material_check = _check_material(assembly, request.workpiece_material_group)
    dimension_check = _check_dimensions(assembly, request)
    machine_check = _check_machine_interface(assembly, request.spindle_interface_required)
    coolant_check = _check_coolant(assembly, request.coolant_required)
    runout_check = _check_runout(assembly, request.max_runout_mm)

    all_statuses = [
        assembly_validation.overall_status,
        operation_check.result.status,
        material_check.status,
        dimension_check.status,
        machine_check.status,
        coolant_check.status,
        runout_check.status,
    ]
    all_reasons: list[str] = [
        *assembly_validation.all_reasons,
        *operation_check.result.reasons,
        *material_check.reasons,
        *dimension_check.reasons,
        *machine_check.reasons,
        *coolant_check.reasons,
        *runout_check.reasons,
    ]

    has_fail = any(s == CompatibilityStatus.FAIL for s in all_statuses)
    has_unknown = any(s == CompatibilityStatus.UNKNOWN for s in all_statuses)

    if has_fail:
        overall_status = CompatibilityStatus.FAIL
    elif has_unknown:
        overall_status = CompatibilityStatus.UNKNOWN
    else:
        overall_status = CompatibilityStatus.PASS

    return ToolAssemblyCompatibility(
        assembly_stable_id=assembly.stable_id,
        request=request,
        assembly_validation=assembly_validation,
        operation_check=operation_check,
        material_check=material_check,
        dimension_check=dimension_check,
        machine_interface_check=machine_check,
        coolant_check=coolant_check,
        runout_check=runout_check,
        overall=MachiningReadinessResult(
            status=overall_status,
            reasons=all_reasons,
        ),
    )
