"""
P7-C: Engineer NC review gate — CANDIDATE → VALIDATED_OFFLINE.

An engineer examines a generated NCProgram and confirms each mandatory checklist
item.  Only when all items are confirmed is the status promoted to VALIDATED_OFFLINE.

HARD RULES:
  - NEVER auto-validate an NC candidate (Hard Rule 10).
  - Engineer review is mandatory for VALIDATED_OFFLINE (Hard Rule 11).
  - is_dispatchable=False even after VALIDATED_OFFLINE.
  - production_released=False even after VALIDATED_OFFLINE.
  - machine_ready_to_run=False even after VALIDATED_OFFLINE.
  - Partial checklist → ENGINEER_REVIEWED (not VALIDATED_OFFLINE).
  - Explicit rejection → REJECTED.

Mandatory checklist items:
  - tool_numbers_verified: tool numbers match physical tool register
  - feeds_speeds_verified: Vc/fn within confirmed range
  - depths_verified: programmed Z depths match feature geometry
  - wcs_offset_verified: work offset matches machine setup sheet

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE  AUTO_VALIDATE=NEVER
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from backend.nc import NCProgram

__all__ = [
    "NCReviewStatus",
    "NCReviewChecklist",
    "NCReviewRecord",
    "record_nc_engineer_review",
]


class NCReviewStatus(StrEnum):
    CANDIDATE = "CANDIDATE"
    ENGINEER_REVIEWED = "ENGINEER_REVIEWED"
    VALIDATED_OFFLINE = "VALIDATED_OFFLINE"
    REJECTED = "REJECTED"


@dataclass
class NCReviewChecklist:
    """Mandatory checklist for engineer NC review.

    All four items must be True to promote to VALIDATED_OFFLINE.
    Partial confirmation → ENGINEER_REVIEWED only.
    """

    tool_numbers_verified: bool = False
    feeds_speeds_verified: bool = False
    depths_verified: bool = False
    wcs_offset_verified: bool = False

    def all_mandatory_checks_passed(self) -> bool:
        return (
            self.tool_numbers_verified
            and self.feeds_speeds_verified
            and self.depths_verified
            and self.wcs_offset_verified
        )

    def missing_checks(self) -> list[str]:
        """Return names of unchecked mandatory items."""
        missing = []
        if not self.tool_numbers_verified:
            missing.append("tool_numbers_verified")
        if not self.feeds_speeds_verified:
            missing.append("feeds_speeds_verified")
        if not self.depths_verified:
            missing.append("depths_verified")
        if not self.wcs_offset_verified:
            missing.append("wcs_offset_verified")
        return missing


@dataclass
class NCReviewRecord:
    """Record of an engineer's review of one NCProgram.

    Safety invariants (enforced in __post_init__):
      is_dispatchable=False — always, even at VALIDATED_OFFLINE
      production_released=False — always
      machine_ready_to_run=False — always

    VALIDATED_OFFLINE means: an engineer has reviewed all mandatory checklist
    items for offline engineering purposes.  It does NOT mean:
    - Tested on a real machine
    - Certified for production use
    - Approved for autonomous or unattended operation
    - Compatible with any specific controller
    """

    nc_program_id: str
    status: NCReviewStatus
    checklist: NCReviewChecklist
    reviewer_notes: str
    reviewed_at: str
    missing_at_review: list[str]
    # Safety invariants
    is_dispatchable: bool = False
    production_released: bool = False
    machine_ready_to_run: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)
        object.__setattr__(self, "machine_ready_to_run", False)


def record_nc_engineer_review(
    nc_program: NCProgram,
    *,
    checklist: NCReviewChecklist,
    reviewer_notes: str,
    rejected: bool = False,
) -> NCReviewRecord:
    """Record an engineer's review of a generated NCProgram.

    Status progression:
    - rejected=True → REJECTED (regardless of checklist)
    - all mandatory checks passed → VALIDATED_OFFLINE
    - partial checks → ENGINEER_REVIEWED
    - no checks → ENGINEER_REVIEWED

    is_dispatchable=False and production_released=False in every case.

    Parameters
    ----------
    nc_program:
        The NCProgram being reviewed.
    checklist:
        Mandatory review checklist items (all must be True for VALIDATED_OFFLINE).
    reviewer_notes:
        Free-text notes from the reviewing engineer.
    rejected:
        If True, marks the program REJECTED regardless of checklist state.
    """
    reviewed_at = datetime.now(UTC).isoformat()
    missing = checklist.missing_checks()

    if rejected:
        status = NCReviewStatus.REJECTED
    elif checklist.all_mandatory_checks_passed():
        status = NCReviewStatus.VALIDATED_OFFLINE
    else:
        status = NCReviewStatus.ENGINEER_REVIEWED

    return NCReviewRecord(
        nc_program_id=nc_program.program_id,
        status=status,
        checklist=checklist,
        reviewer_notes=reviewer_notes,
        reviewed_at=reviewed_at,
        missing_at_review=missing,
    )
