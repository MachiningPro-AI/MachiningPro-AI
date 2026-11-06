"""Level-10 Toolpath Generation — cycle-time bridge.

Feeds EXACT_GENERATED_PATH length from a Level-10 Toolpath back into the
Level-7 cycle-time model (backend.process_planning.cycle_time).

HARD RULES
----------
EXACT_GENERATED_PATH_DISTINCT=YES
    — ToolpathFidelity.EXACT_GENERATED always produces PathLengthType.EXACT_GENERATED_PATH.
APPROXIMATE_GEOMETRIC_PATH_DISTINCT=YES
    — APPROXIMATE or PARTIAL fidelity always produces PathLengthType.APPROXIMATE_GEOMETRIC_PATH.
PATH_LENGTH_LABEL_FIDELITY_MATCH=YES
    — the label MUST match the fidelity; never mislabel approximate as exact.
CYCLE_TIME_NOT_FABRICATED=YES
    — if path length is unknown / zero, return INSUFFICIENT_DATA, not a zero-time guess.
NO_GCODE=YES
    — no G-code is used or produced.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel

from backend.toolpath.enums import ToolpathFidelity
from backend.toolpath.models import PathMetrics


class PathLengthType(StrEnum):
    """Fidelity label for the path length fed to cycle-time calculation."""

    EXACT_GENERATED_PATH = "EXACT_GENERATED_PATH"
    APPROXIMATE_GEOMETRIC_PATH = "APPROXIMATE_GEOMETRIC_PATH"
    UNKNOWN = "UNKNOWN"


class ToolpathCycleTimeInput(BaseModel):
    """Inputs extracted from a Level-10 Toolpath for cycle-time use."""

    operation_ref: str
    toolpath_id: str
    cut_length_mm: float | None
    total_path_length_mm: float | None
    path_length_type: PathLengthType
    fidelity: str
    warnings: list[str] = []


class ToolpathCycleTimeBridge(BaseModel):
    """Result of bridging a Level-10 toolpath into the Level-7 cycle-time model.

    Does NOT compute actual cycle time — that requires feed_rate from Level-6
    cutting data intelligence.  This bridge provides the traceable path-length
    input for `StepCycleTime` computation.
    """

    operation_ref: str
    toolpath_id: str
    cut_path_mm: float | None
    total_path_mm: float | None
    path_length_type: PathLengthType
    path_length_source: str
    cycle_time_ready: bool
    missing_inputs: list[str] = []
    limitations: list[str] = []


_EXACT_NOTE = (
    "Path length derived from EXACT_GENERATED_PATH: "
    "computed from actual generated segment geometry by Level-10 toolpath engine."
)
_APPROX_NOTE = (
    "Path length derived from APPROXIMATE_GEOMETRIC_PATH: "
    "toolpath not fully generated (PARTIAL fidelity); "
    "length is an approximation, not an exact toolpath measurement."
)
_UNKNOWN_NOTE = (
    "Path length UNKNOWN: toolpath not generated (BLOCKED or NOT_GENERATED). "
    "Cannot feed path length to cycle-time model."
)


def extract_cycle_time_input(
    operation_ref: str,
    toolpath_id: str,
    metrics: PathMetrics,
    fidelity: ToolpathFidelity,
) -> ToolpathCycleTimeInput:
    """Extract path-length data from a Toolpath for cycle-time bridging.

    Maps ToolpathFidelity → PathLengthType. Never labels approximate as exact.
    """
    if fidelity == ToolpathFidelity.EXACT_GENERATED:
        path_type = PathLengthType.EXACT_GENERATED_PATH
    elif fidelity in (ToolpathFidelity.PARTIAL, ToolpathFidelity.APPROXIMATE):
        path_type = PathLengthType.APPROXIMATE_GEOMETRIC_PATH
    else:
        path_type = PathLengthType.UNKNOWN

    warnings = []
    if path_type == PathLengthType.APPROXIMATE_GEOMETRIC_PATH:
        warnings.append(
            "APPROXIMATE_PATH_LENGTH: fidelity is PARTIAL/APPROXIMATE; "
            "length is not from complete toolpath generation"
        )
    if path_type == PathLengthType.UNKNOWN:
        warnings.append("PATH_LENGTH_UNKNOWN: toolpath not generated")

    return ToolpathCycleTimeInput(
        operation_ref=operation_ref,
        toolpath_id=toolpath_id,
        cut_length_mm=metrics.cut_length_mm if metrics.cut_length_mm > 0 else None,
        total_path_length_mm=metrics.total_length_mm if metrics.total_length_mm > 0 else None,
        path_length_type=path_type,
        fidelity=str(fidelity),
        warnings=warnings,
    )


def bridge_to_cycle_time(inp: ToolpathCycleTimeInput) -> ToolpathCycleTimeBridge:
    """Produce a cycle-time bridge result from extracted toolpath path length.

    The bridge result is an input record for `StepCycleTime` calculation —
    it does NOT itself compute time (that requires feed rate from Level-6).

    Returns cycle_time_ready=False when path length unavailable.
    """
    missing: list[str] = []
    limitations: list[str] = []

    if inp.path_length_type == PathLengthType.UNKNOWN:
        return ToolpathCycleTimeBridge(
            operation_ref=inp.operation_ref,
            toolpath_id=inp.toolpath_id,
            cut_path_mm=None,
            total_path_mm=None,
            path_length_type=PathLengthType.UNKNOWN,
            path_length_source=_UNKNOWN_NOTE,
            cycle_time_ready=False,
            missing_inputs=["cut_path_mm: toolpath not generated"],
            limitations=["CYCLE_TIME_BLOCKED: toolpath must be generated first"],
        )

    if inp.cut_length_mm is None or inp.cut_length_mm <= 0:
        missing.append("cut_path_mm: cut path length is zero or unknown")

    if inp.path_length_type == PathLengthType.APPROXIMATE_GEOMETRIC_PATH:
        limitations.append(
            "APPROXIMATE_LENGTH: cycle time computed from approximate path, "
            "not exact toolpath — accuracy limited until toolpath is fully generated"
        )

    path_source = (
        _EXACT_NOTE
        if inp.path_length_type == PathLengthType.EXACT_GENERATED_PATH
        else _APPROX_NOTE
    )

    return ToolpathCycleTimeBridge(
        operation_ref=inp.operation_ref,
        toolpath_id=inp.toolpath_id,
        cut_path_mm=inp.cut_length_mm,
        total_path_mm=inp.total_path_length_mm,
        path_length_type=inp.path_length_type,
        path_length_source=path_source,
        cycle_time_ready=len(missing) == 0,
        missing_inputs=missing,
        limitations=limitations,
    )
