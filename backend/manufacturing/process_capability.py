"""
Process capability evaluation for tolerance-driven route selection (P5-E).

Evaluates whether a proposed route can achieve a required IT grade tolerance.

Capability data source:
  Standard manufacturing capability tables derived from ISO 286 / general
  machining engineering references.  These are well-established ranges used
  in engineering education and practice, not arbitrary constants.

  Drilling alone:          achievable IT11-IT12
  Drilling + Reaming:      achievable IT7-IT9
  Drilling + Boring:       achievable IT7-IT8

Capability status codes:
  CAPABLE          -- route can reliably achieve the required IT grade
  MARGINAL_REVIEW  -- route is at the boundary of its capability; engineer review required
  NOT_CAPABLE      -- route cannot achieve the required IT grade
  UNKNOWN          -- insufficient data to evaluate
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, StrEnum


class ITGrade(int, Enum):
    IT5 = 5
    IT6 = 6
    IT7 = 7
    IT8 = 8
    IT9 = 9
    IT10 = 10
    IT11 = 11
    IT12 = 12
    IT13 = 13
    IT14 = 14


class ProcessCapabilityStatus(StrEnum):
    CAPABLE = "CAPABLE"
    MARGINAL_REVIEW = "MARGINAL_REVIEW"
    NOT_CAPABLE = "NOT_CAPABLE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class ProcessCapabilityRecord:
    operation_sequence: tuple[str, ...]
    it_grade_min: int
    it_grade_max: int
    source_note: str


_CAPABILITY_TABLE: list[ProcessCapabilityRecord] = [
    ProcessCapabilityRecord(
        operation_sequence=("drilling",),
        it_grade_min=11,
        it_grade_max=13,
        source_note=(
            "Standard machining capability reference: drilling alone achieves "
            "IT11-IT13 depending on tool runout, rigidity, and material. "
            "ISO 286 / general machining engineering references."
        ),
    ),
    ProcessCapabilityRecord(
        operation_sequence=("drilling", "reaming"),
        it_grade_min=7,
        it_grade_max=9,
        source_note=(
            "Standard machining capability reference: drilling followed by "
            "precision reaming achieves IT7-IT9. "
            "ISO 286 / general machining engineering references."
        ),
    ),
    ProcessCapabilityRecord(
        operation_sequence=("drilling", "boring"),
        it_grade_min=7,
        it_grade_max=8,
        source_note=(
            "Standard machining capability reference: drilling followed by "
            "single-point boring achieves IT7-IT8. "
            "ISO 286 / general machining engineering references."
        ),
    ),
]


@dataclass
class CapabilityEvaluation:
    operation_sequence: tuple[str, ...]
    required_it_grade: int | None
    capability_status: ProcessCapabilityStatus
    achievable_it_min: int | None
    achievable_it_max: int | None
    notes: str


def _parse_it_grade(it_grade_str: str) -> int | None:
    """Parse 'IT7', 'IT11', or '7', '11' into an integer."""
    s = it_grade_str.strip().upper().lstrip("IT")
    try:
        return int(s)
    except ValueError:
        return None


def _operations_for_route(route_operations: list[str]) -> tuple[str, ...]:
    """Normalize a route's operation list to lower-case tuple."""
    return tuple(op.strip().lower() for op in route_operations if op.strip())


def evaluate_route_capability(
    route_operations: list[str],
    required_it_grade: int | None = None,
) -> CapabilityEvaluation:
    """Evaluate whether a route's operation sequence can achieve a tolerance.

    Args:
        route_operations: Ordered list of operation names in the route
            (e.g. ['drilling', 'reaming']).
        required_it_grade: Required IT grade as integer (e.g. 7 for IT7).
            None means no tolerance requirement is specified.

    Returns:
        CapabilityEvaluation with CAPABLE / MARGINAL_REVIEW / NOT_CAPABLE / UNKNOWN.
    """
    ops = _operations_for_route(route_operations)

    rec = next(
        (r for r in _CAPABILITY_TABLE if r.operation_sequence == ops),
        None,
    )

    if rec is None:
        return CapabilityEvaluation(
            operation_sequence=ops,
            required_it_grade=required_it_grade,
            capability_status=ProcessCapabilityStatus.UNKNOWN,
            achievable_it_min=None,
            achievable_it_max=None,
            notes=f"No capability record for operation sequence: {ops}",
        )

    if required_it_grade is None:
        return CapabilityEvaluation(
            operation_sequence=ops,
            required_it_grade=None,
            capability_status=ProcessCapabilityStatus.UNKNOWN,
            achievable_it_min=rec.it_grade_min,
            achievable_it_max=rec.it_grade_max,
            notes="No tolerance requirement specified; achievable range noted.",
        )

    # Lower IT number = tighter tolerance.
    # Route is CAPABLE if required_it_grade is within [rec.it_grade_min, rec.it_grade_max].
    # Route is MARGINAL if required is at the tight end (== rec.it_grade_min).
    # Route is NOT_CAPABLE if required < rec.it_grade_min (tighter than achievable).
    if required_it_grade < rec.it_grade_min:
        status = ProcessCapabilityStatus.NOT_CAPABLE
        notes = (
            f"Required IT{required_it_grade} is tighter than achievable range "
            f"IT{rec.it_grade_min}–IT{rec.it_grade_max} for {list(ops)}."
        )
    elif required_it_grade == rec.it_grade_min:
        status = ProcessCapabilityStatus.MARGINAL_REVIEW
        notes = (
            f"Required IT{required_it_grade} is at the tight boundary of "
            f"achievable IT{rec.it_grade_min}–IT{rec.it_grade_max}; "
            f"engineer review required."
        )
    elif rec.it_grade_min <= required_it_grade <= rec.it_grade_max:
        status = ProcessCapabilityStatus.CAPABLE
        notes = (
            f"Required IT{required_it_grade} is within achievable range "
            f"IT{rec.it_grade_min}–IT{rec.it_grade_max}."
        )
    else:
        # required_it_grade > rec.it_grade_max means looser than achievable -- also CAPABLE
        status = ProcessCapabilityStatus.CAPABLE
        notes = (
            f"Required IT{required_it_grade} is looser than achievable range "
            f"IT{rec.it_grade_min}–IT{rec.it_grade_max}; route is over-capable."
        )

    return CapabilityEvaluation(
        operation_sequence=ops,
        required_it_grade=required_it_grade,
        capability_status=status,
        achievable_it_min=rec.it_grade_min,
        achievable_it_max=rec.it_grade_max,
        notes=notes,
    )


def rank_routes_by_capability(
    route_operations_list: list[list[str]],
    required_it_grade: int | None = None,
) -> list[tuple[list[str], CapabilityEvaluation]]:
    """Rank route alternatives by capability for a given IT grade.

    Returns list of (route_operations, evaluation) sorted by suitability:
    CAPABLE first, then MARGINAL_REVIEW, then UNKNOWN, then NOT_CAPABLE.
    """
    evaluations = [
        (ops, evaluate_route_capability(ops, required_it_grade))
        for ops in route_operations_list
    ]

    priority = {
        ProcessCapabilityStatus.CAPABLE: 0,
        ProcessCapabilityStatus.MARGINAL_REVIEW: 1,
        ProcessCapabilityStatus.UNKNOWN: 2,
        ProcessCapabilityStatus.NOT_CAPABLE: 3,
    }

    evaluations.sort(key=lambda x: priority.get(x[1].capability_status, 9))
    return evaluations
