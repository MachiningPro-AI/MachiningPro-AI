"""
Level-15 Root-Cause Candidate Model.

Correlation-based evidence only.
Never claims causal proof.
Status always CANDIDATE or NOT_CONFIRMED.
is_confirmed and is_causal_proof are always False.
"""

from __future__ import annotations

import uuid

from .enums import RootCauseCandidateStatus
from .models import (
    AlarmAnalytics,
    PlannedActualComparison,
    RootCauseCandidate,
    ToolLifeFeedback,
)


def _uid() -> str:
    return str(uuid.uuid4())


def identify_root_cause_candidates(
    comparison: PlannedActualComparison | None = None,
    alarm_analytics: AlarmAnalytics | None = None,
    tool_feedback: ToolLifeFeedback | None = None,
) -> list[RootCauseCandidate]:
    """
    Identify correlation-based root-cause candidates.

    Does not claim causal proof.
    All candidates remain CANDIDATE / NOT_CONFIRMED.
    """
    candidates: list[RootCauseCandidate] = []

    if comparison is None and alarm_analytics is None and tool_feedback is None:
        return candidates

    # Cycle time increase + alarm spike
    if (
        comparison is not None
        and alarm_analytics is not None
        and comparison.cycle_time_relative_delta is not None
        and comparison.cycle_time_relative_delta > 0.1
        and alarm_analytics.total_alarm_count > 0
    ):
        candidates.append(
            RootCauseCandidate(
                candidate_id=_uid(),
                status=RootCauseCandidateStatus.CANDIDATE,
                observation_ref=comparison.observation_ref,
                comparison_ref=comparison.comparison_id,
                evidence=[
                    f"CYCLE_TIME_HIGH rel_delta={comparison.cycle_time_relative_delta:.2f}",
                    f"ALARM_COUNT={alarm_analytics.total_alarm_count}",
                ],
                correlated_deviations=["CYCLE_TIME_HIGH"],
                correlated_alarms=alarm_analytics.repeat_alarm_candidates,
                suggested_direction="REVIEW_MAINTENANCE",
                is_confirmed=False,
                is_causal_proof=False,
            )
        )

    # Cycle time increase + tool life shorter
    if (
        comparison is not None
        and tool_feedback is not None
        and comparison.cycle_time_relative_delta is not None
        and comparison.cycle_time_relative_delta > 0.1
        and tool_feedback.status.value == "TOOL_LIFE_SHORTER_THAN_EXPECTED"
    ):
        candidates.append(
            RootCauseCandidate(
                candidate_id=_uid(),
                status=RootCauseCandidateStatus.CANDIDATE,
                observation_ref=comparison.observation_ref,
                comparison_ref=comparison.comparison_id,
                evidence=[
                    f"CYCLE_TIME_HIGH rel_delta={comparison.cycle_time_relative_delta:.2f}",
                    f"TOOL_LIFE_SHORTER_THAN_EXPECTED tool={tool_feedback.tool_id}",
                ],
                correlated_deviations=["CYCLE_TIME_HIGH"],
                suggested_direction="REVIEW_TOOL_LIFE",
                is_confirmed=False,
                is_causal_proof=False,
            )
        )

    # Quality issue + specific tool
    if (
        comparison is not None
        and tool_feedback is not None
        and comparison.observed_program_hash
        and comparison.planned_nc_hash
        and comparison.observed_program_hash != comparison.planned_nc_hash
    ):
        candidates.append(
            RootCauseCandidate(
                candidate_id=_uid(),
                status=RootCauseCandidateStatus.CANDIDATE,
                observation_ref=comparison.observation_ref,
                comparison_ref=comparison.comparison_id,
                evidence=[
                    "PROGRAM_MISMATCH observed hash differs from planned",
                ],
                correlated_deviations=["PROGRAM_MISMATCH"],
                suggested_direction="REVIEW_NC_PROGRAM",
                is_confirmed=False,
                is_causal_proof=False,
            )
        )

    # Idle increase + repeated alarm
    if (
        alarm_analytics is not None
        and alarm_analytics.repeat_alarm_candidates
        and alarm_analytics.alarm_frequency_per_hour is not None
        and alarm_analytics.alarm_frequency_per_hour > 1.0
    ):
        candidates.append(
            RootCauseCandidate(
                candidate_id=_uid(),
                status=RootCauseCandidateStatus.CANDIDATE,
                evidence=[
                    f"ALARM_FREQUENCY_HIGH={alarm_analytics.alarm_frequency_per_hour:.2f}/hr",
                    f"REPEAT_ALARMS={alarm_analytics.repeat_alarm_candidates}",
                ],
                correlated_alarms=alarm_analytics.repeat_alarm_candidates,
                suggested_direction="REVIEW_MAINTENANCE",
                is_confirmed=False,
                is_causal_proof=False,
            )
        )

    return candidates
