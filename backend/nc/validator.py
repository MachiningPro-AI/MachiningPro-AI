"""
Level-12 NC Offline Syntax and Semantic Validator.

Validates generated NCProgram IR blocks for syntax and semantic correctness.
All validation is OFFLINE — no machine connection required or performed.

NO_CNC_DISPATCH=YES  OFFLINE_ONLY=YES
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .enums import (
    NCCoordinateMode,
    NCMotionType,
    NCProgramStatus,
    NCUnitMode,
)
from .ir import NCProgram
from .postprocessor import PostProcessorProfile


@dataclass
class ValidationIssue:
    severity: str  # ERROR, WARNING, INFO
    code: str
    message: str
    block_id: str | None = None
    element_index: int | None = None


@dataclass
class ValidationResult:
    status: NCProgramStatus
    syntax_issues: list[ValidationIssue] = field(default_factory=list)
    semantic_issues: list[ValidationIssue] = field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0

    @property
    def is_valid(self) -> bool:
        return self.error_count == 0

    @property
    def all_issues(self) -> list[ValidationIssue]:
        return self.syntax_issues + self.semantic_issues


# ---------------------------------------------------------------------------
# Syntax validation
# ---------------------------------------------------------------------------


def _syntax_validate(program: NCProgram, profile: PostProcessorProfile) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    for block in program.blocks:
        for idx, elem in enumerate(block.elements):
            kind = elem.get("kind", "")
            data = elem.get("data", {})

            if kind == "motion":
                mt_str = data.get("motion_type", "")
                try:
                    mt = NCMotionType(mt_str)
                except ValueError:
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            code="SYN_UNSUPPORTED_MOTION",
                            message=f"Unknown motion type: {mt_str!r}",
                            block_id=block.block_id,
                            element_index=idx,
                        )
                    )
                    continue

                # Check motion type is in profile
                if mt not in profile.supported_motion_types and mt not in (
                    NCMotionType.RAPID_LINEAR,
                    NCMotionType.FEED_LINEAR,
                    NCMotionType.ARC_CW,
                    NCMotionType.ARC_CCW,
                ):
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            code="SYN_UNSUPPORTED_MOTION_TYPE",
                            message=f"Motion type {mt_str} not in profile supported list",
                            block_id=block.block_id,
                            element_index=idx,
                        )
                    )

                # Feed move missing feed
                if mt in (NCMotionType.FEED_LINEAR, NCMotionType.ARC_CW, NCMotionType.ARC_CCW):
                    if not data.get("feed_mmpm"):
                        issues.append(
                            ValidationIssue(
                                severity="ERROR",
                                code="SYN_MISSING_FEED",
                                message=f"Feed move {mt_str} has no feed rate",
                                block_id=block.block_id,
                                element_index=idx,
                            )
                        )

                # Arc syntax
                if mt in (NCMotionType.ARC_CW, NCMotionType.ARC_CCW):
                    arc_mode = data.get("arc_mode")
                    has_ijk = any(
                        data.get(k) is not None for k in ("arc_i", "arc_j", "arc_k")
                    )
                    has_r = data.get("arc_radius") is not None
                    if not arc_mode:
                        issues.append(
                            ValidationIssue(
                                severity="ERROR",
                                code="SYN_ARC_NO_MODE",
                                message="Arc motion has no arc_mode specified",
                                block_id=block.block_id,
                                element_index=idx,
                            )
                        )
                    elif arc_mode == "CENTER_OFFSET" and not has_ijk:
                        issues.append(
                            ValidationIssue(
                                severity="ERROR",
                                code="SYN_ARC_MISSING_IJK",
                                message="CENTER_OFFSET arc has no I/J/K values",
                                block_id=block.block_id,
                                element_index=idx,
                            )
                        )
                    elif arc_mode == "RADIUS" and not has_r:
                        issues.append(
                            ValidationIssue(
                                severity="ERROR",
                                code="SYN_ARC_MISSING_RADIUS",
                                message="RADIUS arc has no arc_radius value",
                                block_id=block.block_id,
                                element_index=idx,
                            )
                        )

                # End coordinates present
                if data.get("end_x") is None and data.get("end_y") is None:
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            code="SYN_MISSING_COORDS",
                            message=f"Motion {mt_str} has no end coordinates",
                            block_id=block.block_id,
                            element_index=idx,
                        )
                    )

                # Line length check
                if profile.maximum_line_length:
                    # Approximate text length
                    text_len = len(str(data))
                    if text_len > profile.maximum_line_length:
                        issues.append(
                            ValidationIssue(
                                severity="WARNING",
                                code="SYN_LINE_TOO_LONG",
                                message=(
                                    f"Block may exceed maximum line length "
                                    f"({text_len} > {profile.maximum_line_length})"
                                ),
                                block_id=block.block_id,
                                element_index=idx,
                            )
                        )

            elif kind == "tool_change":
                tool_number = data.get("tool_number")
                tool_id = data.get("tool_id", "")
                if tool_number is None:
                    issues.append(
                        ValidationIssue(
                            severity="ERROR",
                            code="SYN_MISSING_TOOL_NUMBER",
                            message=f"Tool change for {tool_id!r} has no tool number",
                            block_id=block.block_id,
                            element_index=idx,
                        )
                    )

    return issues


# ---------------------------------------------------------------------------
# Semantic validation
# ---------------------------------------------------------------------------


def _semantic_validate(
    program: NCProgram, profile: PostProcessorProfile
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    # Units declared
    if program.unit_mode == NCUnitMode.UNKNOWN:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                code="SEM_UNKNOWN_UNITS",
                message="Program unit mode is UNKNOWN — cannot generate safe output",
            )
        )

    # Coordinate mode declared
    if program.coordinate_mode == NCCoordinateMode.UNKNOWN:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                code="SEM_UNKNOWN_COORD_MODE",
                message="Program coordinate mode is UNKNOWN",
            )
        )

    # Units in supported modes
    if program.unit_mode not in profile.supported_unit_modes:
        if program.unit_mode != NCUnitMode.UNKNOWN:
            issues.append(
                ValidationIssue(
                    severity="ERROR",
                    code="SEM_UNSUPPORTED_UNIT",
                    message=(
                        f"Unit mode {program.unit_mode} not supported by profile "
                        f"{profile.profile_id}"
                    ),
                )
            )

    # Coordinate mode in supported modes
    if (
        program.coordinate_mode not in profile.supported_coordinate_modes
        and program.coordinate_mode != NCCoordinateMode.UNKNOWN
    ):
        issues.append(
            ValidationIssue(
                severity="ERROR",
                code="SEM_UNSUPPORTED_COORD_MODE",
                message=(
                    f"Coordinate mode {program.coordinate_mode} not supported by profile "
                    f"{profile.profile_id}"
                ),
            )
        )

    # Verification requirement
    if not program.toolpath_id:
        issues.append(
            ValidationIssue(
                severity="WARNING",
                code="SEM_NO_TOOLPATH_REF",
                message="Program has no toolpath reference",
            )
        )

    # Program end exists
    has_end = any(
        elem.get("kind") == "program_end"
        for block in program.blocks
        for elem in block.elements
    )
    if not has_end:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                code="SEM_NO_PROGRAM_END",
                message="Program has no program-end command",
            )
        )

    # Offline / dispatchable check
    if program.is_dispatchable:
        issues.append(
            ValidationIssue(
                severity="ERROR",
                code="SEM_DISPATCHABLE_FLAG",
                message="Program is_dispatchable=True — this is not permitted at Level 12",
            )
        )

    # Duplicate motion codes check (basic)
    seen_feed_modes: set[str] = set()
    seen_unit_decls: set[str] = set()
    for block in program.blocks:
        for elem in block.elements:
            if elem.get("kind") == "unit_decl":
                um = elem.get("data", {}).get("unit_mode", "")
                if um in seen_unit_decls:
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            code="SEM_DUPLICATE_UNIT_DECL",
                            message=f"Duplicate unit declaration: {um}",
                            block_id=block.block_id,
                        )
                    )
                seen_unit_decls.add(um)
            if elem.get("kind") == "feed_cmd":
                fm = elem.get("data", {}).get("feed_mode", "")
                if fm in seen_feed_modes:
                    issues.append(
                        ValidationIssue(
                            severity="WARNING",
                            code="SEM_DUPLICATE_FEED_MODE",
                            message=f"Duplicate feed mode declaration: {fm}",
                            block_id=block.block_id,
                        )
                    )
                seen_feed_modes.add(fm)

    return issues


# ---------------------------------------------------------------------------
# Combined validator
# ---------------------------------------------------------------------------


def validate_nc_program(
    program: NCProgram, profile: PostProcessorProfile
) -> ValidationResult:
    """
    Run offline syntax and semantic validation on a generated NCProgram.

    Returns ValidationResult with VALIDATED_OFFLINE on success,
    REJECTED on errors, REVIEW_REQUIRED on warnings only.
    """
    syntax_issues = _syntax_validate(program, profile)
    semantic_issues = _semantic_validate(program, profile)

    all_issues = syntax_issues + semantic_issues
    error_count = sum(1 for i in all_issues if i.severity == "ERROR")
    warning_count = sum(1 for i in all_issues if i.severity == "WARNING")

    if error_count > 0:
        status = NCProgramStatus.REJECTED
    elif warning_count > 0:
        status = NCProgramStatus.REVIEW_REQUIRED
    else:
        status = NCProgramStatus.VALIDATED_OFFLINE

    return ValidationResult(
        status=status,
        syntax_issues=syntax_issues,
        semantic_issues=semantic_issues,
        error_count=error_count,
        warning_count=warning_count,
    )
