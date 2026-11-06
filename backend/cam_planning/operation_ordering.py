"""Deterministic CAM operation ordering rules for Level-9.

Implements precedence rules for a topological sort of candidate operations.
Does NOT claim globally optimal sequence.

Precedence rules implemented
----------------------------
R-OP-01  FACE_MILL / FACE_TURN before datum-dependent operations
R-OP-02  ROUGHING before SEMI_FINISH before FINISH
R-OP-03  DRILL before REAM
R-OP-04  DRILL / PECK_DRILL before TAP
R-OP-05  DRILL before BORE
R-OP-06  POCKET_ROUGH before POCKET_FINISH
R-OP-07  CONTOUR_ROUGH before CONTOUR_FINISH / BALL_END_FINISH
R-OP-08  Main machining before CHAMFER / deburr
R-OP-09  ADAPTIVE_ROUGH before REST_MACHINING
R-OP-10  TURN_ROUGH before TURN_FINISH
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.cam_planning.enums import CAMOperationType, OperationPhase

__all__ = [
    "PrecedenceRule",
    "PRECEDENCE_RULES",
    "compute_phase_order",
    "sort_operations_by_precedence",
    "OperationOrderResult",
]


@dataclass(frozen=True)
class PrecedenceRule:
    """A single precedence constraint: predecessor must run before successor."""

    rule_id: str
    predecessor: CAMOperationType
    successor: CAMOperationType
    rationale: str


PRECEDENCE_RULES: tuple[PrecedenceRule, ...] = (
    PrecedenceRule("R-OP-01a", CAMOperationType.FACE_MILL, CAMOperationType.POCKET_ROUGH,
                   "Face datum surface before datum-dependent pocketing"),
    PrecedenceRule("R-OP-01b", CAMOperationType.FACE_MILL, CAMOperationType.DRILL,
                   "Face datum surface before datum-dependent drilling"),
    PrecedenceRule("R-OP-01c", CAMOperationType.FACE_MILL, CAMOperationType.CONTOUR_ROUGH,
                   "Face datum surface before contour operations"),
    PrecedenceRule("R-OP-01d", CAMOperationType.FACE_TURN, CAMOperationType.TURN_ROUGH,
                   "Face turn before OD/ID roughing"),
    PrecedenceRule("R-OP-03", CAMOperationType.DRILL, CAMOperationType.REAM,
                   "Drill before ream"),
    PrecedenceRule("R-OP-04a", CAMOperationType.DRILL, CAMOperationType.TAP,
                   "Drill before tap"),
    PrecedenceRule("R-OP-04b", CAMOperationType.PECK_DRILL, CAMOperationType.TAP,
                   "Peck drill before tap"),
    PrecedenceRule("R-OP-05", CAMOperationType.DRILL, CAMOperationType.BORE,
                   "Drill before bore"),
    PrecedenceRule("R-OP-06", CAMOperationType.POCKET_ROUGH, CAMOperationType.POCKET_FINISH,
                   "Rough pocket before finish pocket"),
    PrecedenceRule("R-OP-07a", CAMOperationType.CONTOUR_ROUGH, CAMOperationType.CONTOUR_FINISH,
                   "Contour rough before contour finish"),
    PrecedenceRule("R-OP-07b", CAMOperationType.CONTOUR_ROUGH, CAMOperationType.BALL_END_FINISH,
                   "Contour rough before ball-end finish"),
    PrecedenceRule("R-OP-08a", CAMOperationType.POCKET_ROUGH, CAMOperationType.CHAMFER,
                   "Main machining before chamfer"),
    PrecedenceRule("R-OP-08b", CAMOperationType.CONTOUR_ROUGH, CAMOperationType.CHAMFER,
                   "Contour rough before chamfer"),
    PrecedenceRule("R-OP-08c", CAMOperationType.SLOT_MILL, CAMOperationType.CHAMFER,
                   "Slot milling before chamfer"),
    PrecedenceRule("R-OP-09", CAMOperationType.ADAPTIVE_ROUGH, CAMOperationType.REST_MACHINING,
                   "Adaptive roughing before rest machining"),
    PrecedenceRule("R-OP-10", CAMOperationType.TURN_ROUGH, CAMOperationType.TURN_FINISH,
                   "Turn rough before turn finish"),
)

_PHASE_ORDER: dict[OperationPhase, int] = {
    OperationPhase.ROUGHING: 0,
    OperationPhase.SEMI_FINISH: 1,
    OperationPhase.FINISH: 2,
}


def compute_phase_order(phase: OperationPhase) -> int:
    """Return numeric ordering for phase (lower = earlier)."""
    return _PHASE_ORDER.get(phase, 1)


@dataclass(frozen=True)
class OperationOrderResult:
    """Result of ordering candidate operations."""

    ordered_operation_ids: tuple[str, ...]
    applied_rules: tuple[str, ...]
    warnings: tuple[str, ...]


def sort_operations_by_precedence(
    operation_ids: list[str],
    operation_types: dict[str, CAMOperationType],
    operation_phases: dict[str, OperationPhase],
) -> OperationOrderResult:
    """Sort candidate operations by precedence rules.

    Uses a stable topological sort:
    1. Apply explicit precedence rules from PRECEDENCE_RULES.
    2. Within same phase, preserve input order (stable sort).
    3. Phase order: ROUGHING < SEMI_FINISH < FINISH.

    Does NOT claim globally optimal sequence.

    Args:
        operation_ids:    List of operation IDs to sort.
        operation_types:  Map from operation ID to CAMOperationType.
        operation_phases: Map from operation ID to OperationPhase.

    Returns:
        OperationOrderResult with sorted IDs and applied rules.
    """
    if not operation_ids:
        return OperationOrderResult(
            ordered_operation_ids=(),
            applied_rules=(),
            warnings=(),
        )

    type_to_ids: dict[CAMOperationType, list[str]] = {}
    for oid in operation_ids:
        op_type = operation_types.get(oid)
        if op_type:
            type_to_ids.setdefault(op_type, []).append(oid)

    predecessors: dict[str, set[str]] = {oid: set() for oid in operation_ids}
    applied_rules: list[str] = []

    for rule in PRECEDENCE_RULES:
        pred_ids = type_to_ids.get(rule.predecessor, [])
        succ_ids = type_to_ids.get(rule.successor, [])
        if pred_ids and succ_ids:
            for pid in pred_ids:
                for sid in succ_ids:
                    if pid != sid:
                        predecessors[sid].add(pid)
            applied_rules.append(rule.rule_id)

    remaining = list(operation_ids)
    ordered: list[str] = []
    warnings: list[str] = []
    max_iterations = len(operation_ids) * len(operation_ids) + 1
    iterations = 0

    while remaining:
        iterations += 1
        if iterations > max_iterations:
            warnings.append(
                "CYCLE_DETECTED: precedence graph has a cycle; remaining operations appended"
            )
            ordered.extend(remaining)
            break

        ready = [
            oid for oid in remaining
            if all(pred not in remaining for pred in predecessors.get(oid, set()))
        ]

        if not ready:
            warnings.append("PARTIAL_ORDER: no progress possible; appending remaining by phase")
            remaining.sort(key=lambda oid: (
                compute_phase_order(operation_phases.get(oid, OperationPhase.ROUGHING)),
                operation_ids.index(oid),
            ))
            ordered.extend(remaining)
            break

        ready.sort(key=lambda oid: (
            compute_phase_order(operation_phases.get(oid, OperationPhase.ROUGHING)),
            operation_ids.index(oid),
        ))

        for oid in ready:
            ordered.append(oid)
            remaining.remove(oid)

    return OperationOrderResult(
        ordered_operation_ids=tuple(ordered),
        applied_rules=tuple(applied_rules),
        warnings=tuple(warnings),
    )
