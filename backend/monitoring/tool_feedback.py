"""
Level-15 Tool-Life Feedback.

Compares predicted tool life vs observed usage.
PROPOSED_ONLY — no tool-offset write, no automatic action.
"""

from __future__ import annotations

import uuid

from .enums import DataQuality, ObservationSource, ToolLifeStatus
from .models import ActualToolUsage, ToolLifeFeedback


def _uid() -> str:
    return str(uuid.uuid4())


def make_tool_usage(
    tool_id: str,
    cutting_time: float | None = None,
    spindle_time: float | None = None,
    parts_produced: int | None = None,
    tool_change_count: int | None = None,
    observed_life: float | None = None,
    machine_id: str | None = None,
    job_id: str | None = None,
    source: ObservationSource = ObservationSource.SIMULATED_CONTROLLER,
) -> ActualToolUsage:
    """Create an observed tool usage record."""
    warnings: list[str] = []
    if cutting_time is None and spindle_time is None:
        warnings.append("NO_TOOL_TELEMETRY_AVAILABLE")
    return ActualToolUsage(
        tool_usage_id=_uid(),
        tool_id=tool_id,
        machine_id=machine_id,
        job_id=job_id,
        cutting_time=cutting_time,
        spindle_time=spindle_time,
        parts_produced=parts_produced,
        tool_change_count=tool_change_count,
        observed_life=observed_life,
        source=source,
        data_quality=DataQuality.RAW if cutting_time is not None else DataQuality.UNKNOWN,
        warnings=warnings,
    )


def compute_tool_life_feedback(
    tool_id: str,
    predicted_life: float | None,
    actual_usage: ActualToolUsage,
    tolerance_ratio: float = 0.1,
) -> ToolLifeFeedback:
    """
    Compare predicted vs observed tool life.

    Returns INSUFFICIENT_DATA when either side is missing.
    is_automatic_action is always False.
    """
    observed = actual_usage.observed_life or actual_usage.cutting_time

    if predicted_life is None or observed is None:
        return ToolLifeFeedback(
            feedback_id=_uid(),
            tool_id=tool_id,
            predicted_life=predicted_life,
            observed_life=observed,
            status=ToolLifeStatus.INSUFFICIENT_DATA,
            data_quality=DataQuality.UNKNOWN,
            is_automatic_action=False,
        )

    if predicted_life <= 0:
        return ToolLifeFeedback(
            feedback_id=_uid(),
            tool_id=tool_id,
            predicted_life=predicted_life,
            observed_life=observed,
            status=ToolLifeStatus.INSUFFICIENT_DATA,
            data_quality=DataQuality.INVALID,
            is_automatic_action=False,
        )

    rel_delta = (observed - predicted_life) / predicted_life

    if rel_delta < -tolerance_ratio:
        status = ToolLifeStatus.TOOL_LIFE_SHORTER_THAN_EXPECTED
    elif rel_delta > tolerance_ratio:
        status = ToolLifeStatus.TOOL_LIFE_LONGER_THAN_EXPECTED
    else:
        status = ToolLifeStatus.TOOL_LIFE_WITHIN_POLICY

    return ToolLifeFeedback(
        feedback_id=_uid(),
        tool_id=tool_id,
        predicted_life=predicted_life,
        observed_life=observed,
        status=status,
        relative_delta=rel_delta,
        data_quality=DataQuality.RAW,
        is_automatic_action=False,
    )
