"""
Level-15 Engineering Recommendations.

Proposals require human review.
is_automatic_action is always False.
is_applied is always False at creation.
"""

from __future__ import annotations

import uuid

from .enums import ClosedLoopProposalType, RecommendationType
from .models import ClosedLoopProposal, EngineeringRecommendation, RootCauseCandidate


def _uid() -> str:
    return str(uuid.uuid4())


def _direction_to_recommendation_type(
    direction: str,
) -> RecommendationType:
    mapping = {
        "REVIEW_CUTTING_DATA": RecommendationType.REVIEW_CUTTING_DATA,
        "REVIEW_TOOL_SELECTION": RecommendationType.REVIEW_TOOL_SELECTION,
        "REVIEW_TOOL_LIFE": RecommendationType.REVIEW_TOOL_LIFE,
        "REVIEW_MACHINE_ASSIGNMENT": RecommendationType.REVIEW_MACHINE_ASSIGNMENT,
        "REVIEW_SETUP_METHOD": RecommendationType.REVIEW_SETUP_METHOD,
        "REVIEW_FIXTURE": RecommendationType.REVIEW_FIXTURE,
        "REVIEW_NC_PROGRAM": RecommendationType.REVIEW_NC_PROGRAM,
        "REVIEW_MAINTENANCE": RecommendationType.REVIEW_MAINTENANCE,
        "REVIEW_QUALITY_PROCESS": RecommendationType.REVIEW_QUALITY_PROCESS,
    }
    return mapping.get(direction, RecommendationType.REVIEW_CUTTING_DATA)


def generate_recommendations(
    candidates: list[RootCauseCandidate],
) -> list[EngineeringRecommendation]:
    """
    Generate engineering recommendation proposals from root-cause candidates.

    All recommendations:
    - require human review (requires_review=True)
    - are NOT automatic actions (is_automatic_action=False)
    - are NOT applied (is_applied=False)
    """
    recommendations: list[EngineeringRecommendation] = []
    seen_directions: set[str] = set()

    for candidate in candidates:
        direction = candidate.suggested_direction
        if not direction or direction in seen_directions:
            continue
        seen_directions.add(direction)
        rec_type = _direction_to_recommendation_type(direction)
        recommendations.append(
            EngineeringRecommendation(
                recommendation_id=_uid(),
                recommendation_type=rec_type,
                candidate_ref=candidate.candidate_id,
                rationale="; ".join(candidate.evidence),
                requires_review=True,
                is_automatic_action=False,
                is_applied=False,
            )
        )

    return recommendations


def make_closed_loop_proposal(
    proposal_type: ClosedLoopProposalType,
    proposed_value: float | None = None,
    current_value: float | None = None,
    observation_ref: str | None = None,
    comparison_ref: str | None = None,
    rationale: str = "",
) -> ClosedLoopProposal:
    """
    Create a PROPOSED_ONLY closed-loop candidate.

    is_automatic_write is ALWAYS False.
    Does NOT write to Level-6 cutting data or Level-12 NC.
    """
    return ClosedLoopProposal(
        proposal_id=_uid(),
        proposal_type=proposal_type,
        observation_ref=observation_ref,
        comparison_ref=comparison_ref,
        proposed_value=proposed_value,
        current_value=current_value,
        rationale=rationale,
        is_proposed_only=True,
        is_automatic_write=False,
    )
