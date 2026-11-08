"""Assembly-level compatibility validation.

Reuses Phase 2 compatibility engine for tool-holder and insert-holder checks,
then adds assembly-geometry consistency checks.

Result precedence: FAIL > UNKNOWN > PASS.
Missing required dimensions produce UNKNOWN, never PASS.
Geometric consistency failure produces FAIL.
"""
from __future__ import annotations

from .assembly_models import (
    ToolAssemblyGeometry,
    ToolAssemblyRecord,
    ToolAssemblyValidationResult,
)
from .compatibility import (  # noqa: E402
    CompatibilityResult,
    CompatibilityStatus,
    check_insert_holder_compatibility,
    check_tool_holder_compatibility,
)

# ── Internal helpers ──────────────────────────────────────────────────────────

def _aggregate(
    failures: list[str],
    unknowns: list[str],
    passes: list[str],
) -> CompatibilityResult:
    if failures:
        note = (["(UNKNOWN checks also present: " + "; ".join(unknowns) + ")"]
                if unknowns else [])
        return CompatibilityResult(
            status=CompatibilityStatus.FAIL,
            reasons=failures + note,
        )
    if unknowns:
        return CompatibilityResult(status=CompatibilityStatus.UNKNOWN, reasons=unknowns)
    return CompatibilityResult(
        status=CompatibilityStatus.PASS,
        reasons=passes or ["Assembly geometry consistent"],
    )


# ── Geometry check ────────────────────────────────────────────────────────────

def check_assembly_geometry(record: ToolAssemblyRecord) -> CompatibilityResult:
    """Validate declared assembly geometry for self-consistency.

    Checks performed:
    1. tool_stick_out_mm > 0 when present.
    2. effective_reach_mm >= tool.cutting_length_mm when both present.
    3. tool_stick_out_mm <= gauge_length_mm when both present.
    4. overall_assembly_length_mm > 0 when present.
    5. assembly.shank_diameter_mm consistent with tool.shank_diameter_mm.
    6. assembly.spindle_interface consistent with holder.spindle_interface.
    7. coolant_enabled=True when tool requires through-coolant but holder
       does not support it → FAIL.
    """
    failures: list[str] = []
    unknowns: list[str] = []
    passes: list[str] = []

    g: ToolAssemblyGeometry = record.geometry
    tool = record.tool
    holder = record.holder

    # 1. Stick-out positivity
    if g.tool_stick_out_mm is not None:
        if g.tool_stick_out_mm <= 0:
            failures.append(
                f"tool_stick_out_mm={g.tool_stick_out_mm} is not positive"
            )
        else:
            passes.append(f"Stick-out {g.tool_stick_out_mm}mm > 0")

    # 2. Effective reach vs cutting length
    if g.effective_reach_mm is not None and tool.cutting_length_mm is not None:
        if g.effective_reach_mm < tool.cutting_length_mm:
            failures.append(
                f"effective_reach_mm={g.effective_reach_mm}mm < "
                f"tool.cutting_length_mm={tool.cutting_length_mm}mm"
            )
        else:
            passes.append(
                f"Effective reach {g.effective_reach_mm}mm ≥ "
                f"cutting length {tool.cutting_length_mm}mm"
            )
    elif g.effective_reach_mm is None and tool.cutting_length_mm is not None:
        unknowns.append(
            "geometry.effective_reach_mm is None — reach clearance unverified"
        )

    # 3. Stick-out ≤ gauge length
    if g.tool_stick_out_mm is not None and g.gauge_length_mm is not None:
        if g.tool_stick_out_mm > g.gauge_length_mm:
            failures.append(
                f"tool_stick_out_mm={g.tool_stick_out_mm}mm > "
                f"gauge_length_mm={g.gauge_length_mm}mm — impossible geometry"
            )
        else:
            passes.append(
                f"Stick-out {g.tool_stick_out_mm}mm ≤ gauge length "
                f"{g.gauge_length_mm}mm"
            )

    # 4. Overall assembly length positivity
    if g.overall_assembly_length_mm is not None:
        if g.overall_assembly_length_mm <= 0:
            failures.append(
                f"overall_assembly_length_mm={g.overall_assembly_length_mm} "
                "is not positive"
            )
        else:
            passes.append(
                f"Overall assembly length {g.overall_assembly_length_mm}mm > 0"
            )

    # 5. Shank diameter consistency: assembly vs tool
    if g.shank_diameter_mm is not None and tool.shank_diameter_mm is not None:
        if abs(g.shank_diameter_mm - tool.shank_diameter_mm) > 0.001:
            failures.append(
                f"assembly.shank_diameter_mm={g.shank_diameter_mm} ≠ "
                f"tool.shank_diameter_mm={tool.shank_diameter_mm} (contradictory)"
            )
        else:
            passes.append(
                f"Shank diameter {g.shank_diameter_mm}mm consistent with tool"
            )

    # 6. Spindle interface consistency: assembly vs holder
    if g.spindle_interface is not None and holder.spindle_interface is not None:
        if g.spindle_interface.lower() != holder.spindle_interface.lower():
            failures.append(
                f"assembly.spindle_interface={g.spindle_interface!r} ≠ "
                f"holder.spindle_interface={holder.spindle_interface!r} "
                "(contradictory)"
            )
        else:
            passes.append(
                f"Spindle interface {g.spindle_interface!r} consistent with holder"
            )

    # 7. Coolant: assembly enabled but holder incapable
    if g.coolant_enabled is True and holder.supports_coolant is False:
        failures.append(
            "assembly.coolant_enabled=True but holder.supports_coolant=False"
        )
    elif g.coolant_enabled is True and holder.supports_coolant is None:
        unknowns.append(
            "assembly.coolant_enabled=True but holder.supports_coolant is None"
        )

    if not failures and not unknowns and not passes:
        passes.append("No assembly geometry dimensions declared — unchecked")

    return _aggregate(failures, unknowns, passes)


# ── Assembly validation ───────────────────────────────────────────────────────

def validate_assembly(record: ToolAssemblyRecord) -> ToolAssemblyValidationResult:
    """Validate all aspects of a tool assembly.

    1. Tool-holder compatibility (Phase 2 engine).
    2. Insert-holder compatibility (Phase 2 engine, if insert present).
    3. Assembly geometry consistency.

    Overall status: FAIL if any check fails; UNKNOWN if any check is unknown
    and none fail; PASS only when all checks pass.
    """
    tool_holder = check_tool_holder_compatibility(record.tool, record.holder)

    insert_holder: CompatibilityResult | None = None
    if record.insert is not None:
        insert_holder = check_insert_holder_compatibility(
            record.insert, record.holder
        )

    geometry = check_assembly_geometry(record)

    all_checks = [tool_holder, geometry]
    if insert_holder is not None:
        all_checks.append(insert_holder)

    all_reasons: list[str] = []
    for chk in all_checks:
        all_reasons.extend(chk.reasons)

    has_fail = any(c.status == CompatibilityStatus.FAIL for c in all_checks)
    has_unknown = any(c.status == CompatibilityStatus.UNKNOWN for c in all_checks)

    if has_fail:
        overall = CompatibilityStatus.FAIL
    elif has_unknown:
        overall = CompatibilityStatus.UNKNOWN
    else:
        overall = CompatibilityStatus.PASS

    return ToolAssemblyValidationResult(
        overall_status=overall,
        tool_holder_check=tool_holder,
        insert_holder_check=insert_holder,
        geometry_check=geometry,
        all_reasons=all_reasons,
    )
