"""
P7-B: Multi-hole batch sequencing for a single sample.

Groups confirmed drilling features by tool assignment and returns a PROPOSED
sequence for engineer review.

HARD RULES:
  - NEVER auto-confirm a hole sequence.
  - NEVER auto-assign tool numbers.
  - NEVER hide COMPATIBLE tool dimensional risk.
  - engineer_confirmed is ALWAYS False until an explicit confirm call.
  - is_dispatchable is ALWAYS False.
  - production_released is ALWAYS False.
  - sequence_status=PROPOSED until engineer_confirmed=True.

Sequence ordering policy:
  - Groups are ordered: EXACT tool matches before COMPATIBLE.
  - Holes within a group are in insertion order (not path-optimized).
  - Path optimization is an engineering responsibility — this module proposes;
    engineer confirms.

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE  NO_AUTO_SEQUENCE=YES
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum

__all__ = [
    "BatchSequenceStatus",
    "HoleEntry",
    "ToolGroup",
    "BatchSequenceProposal",
    "group_features_by_tool",
]


class BatchSequenceStatus(StrEnum):
    PROPOSED = "PROPOSED"
    ENGINEER_CONFIRMED = "ENGINEER_CONFIRMED"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"


@dataclass
class HoleEntry:
    """One drilling feature in a batch sequence.

    tool_number is None when not yet assigned by engineer (TOOL_NUMBER_REQUIRED).
    """

    feature_id: str
    hole_x: float
    hole_y: float
    depth_mm: float
    feature_diameter_mm: float
    tool_id: str
    tool_match_status: str           # EXACT / COMPATIBLE / NO_MATCH
    tool_diameter_mm: float
    tool_number: int | None = None   # None = TOOL_NUMBER_REQUIRED
    warnings: list[str] = field(default_factory=list)


@dataclass
class ToolGroup:
    """One tool's holes within a batch sequence proposal.

    sequence_proposed=True always at creation.
    engineer_confirmed=False until explicit review call.
    """

    group_id: str
    tool_id: str
    tool_match_status: str
    holes: list[HoleEntry] = field(default_factory=list)
    proposed_tool_number: int | None = None   # engineer must verify / assign
    sequence_proposed: bool = True
    engineer_confirmed: bool = False          # always False at creation

    def __post_init__(self) -> None:
        object.__setattr__(self, "sequence_proposed", True)
        object.__setattr__(self, "engineer_confirmed", False)


@dataclass
class BatchSequenceProposal:
    """Proposed multi-tool, multi-hole drilling sequence for one sample.

    Safety invariants (enforced in __post_init__):
      engineer_confirmed=False — always at creation
      is_dispatchable=False — always
      production_released=False — always
    """

    sample_id: str
    groups: list[ToolGroup]
    total_holes: int
    total_tools: int
    compatible_hole_count: int        # holes with COMPATIBLE tool match
    no_match_hole_count: int          # holes with no tool — these block their group
    sequence_status: str = BatchSequenceStatus.PROPOSED
    engineer_confirmed: bool = False
    is_dispatchable: bool = False
    production_released: bool = False
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "engineer_confirmed", False)
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)
        if self.no_match_hole_count > 0:
            object.__setattr__(self, "sequence_status", BatchSequenceStatus.INCOMPLETE)


def group_features_by_tool(
    sample_id: str,
    hole_entries: list[HoleEntry],
) -> BatchSequenceProposal:
    """Group hole entries by tool, returning a PROPOSED batch sequence.

    Ordering policy:
    - EXACT tool-match groups come before COMPATIBLE tool-match groups.
    - Within match class, groups appear in first-seen order of their tool_id.
    - Holes within a group are in insertion order.
    - NO_MATCH holes are collected into a separate blocked group at the end.

    Parameters
    ----------
    sample_id:
        Identifier of the sample (e.g. DXF-01).
    hole_entries:
        List of HoleEntry objects, each with tool_id and tool_match_status.
        May contain NO_MATCH entries (blocked from NC generation).
    """
    exact_groups: dict[str, ToolGroup] = {}
    compatible_groups: dict[str, ToolGroup] = {}
    no_match_group_holes: list[HoleEntry] = []
    warnings: list[str] = []

    proposed_tool_number = 1

    for entry in hole_entries:
        if entry.tool_match_status == "NO_MATCH":
            no_match_group_holes.append(entry)
            warnings.append(
                f"NO_MATCH: feature={entry.feature_id} dia={entry.feature_diameter_mm}mm "
                "has no compatible tool — excluded from NC candidate"
            )
            continue

        if entry.tool_match_status == "COMPATIBLE":
            if entry.tool_id not in compatible_groups:
                compatible_groups[entry.tool_id] = ToolGroup(
                    group_id=str(uuid.uuid4())[:12],
                    tool_id=entry.tool_id,
                    tool_match_status="COMPATIBLE",
                    proposed_tool_number=None,  # engineer assigns
                )
                warnings.append(
                    f"COMPATIBLE_MATCH: tool={entry.tool_id} dia={entry.tool_diameter_mm}mm "
                    "used for COMPATIBLE features — engineer must verify fit tolerance"
                )
            compatible_groups[entry.tool_id].holes.append(entry)
        else:
            # EXACT
            if entry.tool_id not in exact_groups:
                exact_groups[entry.tool_id] = ToolGroup(
                    group_id=str(uuid.uuid4())[:12],
                    tool_id=entry.tool_id,
                    tool_match_status="EXACT",
                    proposed_tool_number=None,  # engineer assigns
                )
            exact_groups[entry.tool_id].holes.append(entry)

    # Build ordered group list: EXACT first, then COMPATIBLE
    ordered_groups: list[ToolGroup] = []
    for g in exact_groups.values():
        g.proposed_tool_number = proposed_tool_number
        ordered_groups.append(g)
        proposed_tool_number += 1
    for g in compatible_groups.values():
        g.proposed_tool_number = proposed_tool_number
        ordered_groups.append(g)
        proposed_tool_number += 1

    # NO_MATCH group (blocked — still tracked for transparency)
    if no_match_group_holes:
        no_match_group = ToolGroup(
            group_id=str(uuid.uuid4())[:12],
            tool_id="NO_MATCH",
            tool_match_status="NO_MATCH",
            holes=no_match_group_holes,
        )
        ordered_groups.append(no_match_group)
        warnings.append(
            f"SEQUENCE_INCOMPLETE: {len(no_match_group_holes)} hole(s) have no matching "
            "tool — engineer must source tools or defer those features"
        )

    compatible_count = sum(
        len(g.holes) for g in ordered_groups if g.tool_match_status == "COMPATIBLE"
    )
    no_match_count = len(no_match_group_holes)

    return BatchSequenceProposal(
        sample_id=sample_id,
        groups=ordered_groups,
        total_holes=len(hole_entries),
        total_tools=len(exact_groups) + len(compatible_groups),
        compatible_hole_count=compatible_count,
        no_match_hole_count=no_match_count,
        warnings=warnings,
    )
