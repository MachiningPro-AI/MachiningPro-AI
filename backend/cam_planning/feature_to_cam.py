"""Feature-to-CAM operation mapping for Level-9 Automatic CAM Planning.

Maps manufacturing features (from Level-3 recognition) to candidate
CAM operations.  Returns candidates only — not verified operations.

Safety contract
---------------
CANDIDATE_NOT_VERIFIED   — circle != CAM drill automatically.
CANDIDATE_HOLE_NOT_DRILL — a candidate hole is not a confirmed drilling op.
NO_FABRICATED_MAPPING    — no operation is generated without feature evidence.
TOLERANCE_REQUIRED       — REAM/BORE only produced when tolerance exists.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.cam_planning.enums import (
    CAMOperationType,
    CAMStrategyType,
    OperationPhase,
    ToolFamilyRequirement,
)

__all__ = [
    "FeatureMappingResult",
    "map_feature_to_cam_candidates",
    "get_cam_strategy_for_operation",
    "FEATURE_TO_CAM_MAP",
]


@dataclass(frozen=True)
class FeatureMappingResult:
    """Result of mapping a feature to candidate CAM operations."""

    feature_id: str
    feature_type: str
    candidates: tuple[CAMOperationType, ...]
    phases: tuple[OperationPhase, ...]
    tool_families: tuple[ToolFamilyRequirement, ...]
    rationale: str
    requires_tolerance_evidence: bool = False
    requires_depth_evidence: bool = False
    warnings: tuple[str, ...] = ()


_FM = ToolFamilyRequirement
_SC = _FM.SOLID_CARBIDE_END_MILL

FEATURE_TO_CAM_MAP: dict[
    str, list[tuple[CAMOperationType, OperationPhase, ToolFamilyRequirement, str]]
] = {
    "hole": [
        (CAMOperationType.DRILL, OperationPhase.ROUGHING, _FM.DRILL_BIT,
         "Confirmed hole → DRILL candidate"),
    ],
    "deep_hole": [
        (CAMOperationType.PECK_DRILL, OperationPhase.ROUGHING, _FM.DRILL_BIT,
         "Deep hole → PECK_DRILL for chip evacuation"),
    ],
    "tight_tolerance_hole": [
        (CAMOperationType.DRILL, OperationPhase.ROUGHING, _FM.DRILL_BIT,
         "Tight-tolerance hole → DRILL + finishing candidate"),
        (CAMOperationType.REAM, OperationPhase.FINISH, _FM.REAMER,
         "Tight-tolerance hole → REAM candidate (requires tolerance evidence)"),
        (CAMOperationType.BORE, OperationPhase.FINISH, _FM.BORING_BAR,
         "Tight-tolerance hole → BORE candidate (requires tolerance evidence)"),
    ],
    "pocket": [
        (CAMOperationType.POCKET_ROUGH, OperationPhase.ROUGHING, _SC,
         "Pocket → POCKET_ROUGH candidate"),
        (CAMOperationType.POCKET_FINISH, OperationPhase.FINISH, _SC,
         "Pocket → POCKET_FINISH candidate where surface requirement justifies"),
    ],
    "slot": [
        (CAMOperationType.SLOT_MILL, OperationPhase.ROUGHING, _SC,
         "Slot → SLOT_MILL candidate"),
    ],
    "chamfer": [
        (CAMOperationType.CHAMFER, OperationPhase.FINISH, _SC,
         "Chamfer feature → CHAMFER candidate"),
    ],
    "planar_face": [
        (CAMOperationType.FACE_MILL, OperationPhase.ROUGHING, _FM.FACE_MILL_CUTTER,
         "Planar face → FACE_MILL candidate"),
    ],
    "thread": [
        (CAMOperationType.TAP, OperationPhase.FINISH, _FM.THREADING_TAP,
         "Thread feature → TAP candidate"),
        (CAMOperationType.THREAD_MILL, OperationPhase.FINISH, _FM.THREAD_MILL_CUTTER,
         "Thread feature → THREAD_MILL alternative candidate"),
    ],
    "groove": [
        (CAMOperationType.GROOVE, OperationPhase.ROUGHING, _FM.GROOVING_INSERT,
         "Groove → GROOVE turning candidate"),
    ],
    "cylindrical_surface": [
        (CAMOperationType.TURN_ROUGH, OperationPhase.ROUGHING, _FM.TURNING_INSERT,
         "Cylindrical surface → TURN_ROUGH candidate"),
        (CAMOperationType.TURN_FINISH, OperationPhase.FINISH, _FM.TURNING_INSERT,
         "Cylindrical surface → TURN_FINISH where finish requirement justifies"),
    ],
    "freeform_surface": [
        (CAMOperationType.CONTOUR_ROUGH, OperationPhase.ROUGHING, _SC,
         "Freeform surface → CONTOUR_ROUGH candidate"),
        (CAMOperationType.BALL_END_FINISH, OperationPhase.FINISH, _SC,
         "Freeform surface → BALL_END_FINISH where surface requirement exists"),
    ],
}

_TOLERANCE_REQUIRED_OPS = frozenset({
    CAMOperationType.REAM,
    CAMOperationType.BORE,
})

_DEEP_HOLE_DEPTH_RATIO = 5.0


def map_feature_to_cam_candidates(
    feature_id: str,
    feature_type: str,
    has_tolerance_evidence: bool = False,
    depth_diameter_ratio: float | None = None,
    is_confirmed: bool = True,
) -> FeatureMappingResult:
    """Map a feature to candidate CAM operations.

    Rules:
    - circle != CAM drill operation automatically (is_confirmed must be True)
    - candidate hole != confirmed drilling automatically
    - REAM/BORE only if has_tolerance_evidence
    - deep hole (depth/dia > 5) → PECK_DRILL instead of DRILL
    - unknown feature_type → empty candidates with warning
    """
    if not is_confirmed:
        return FeatureMappingResult(
            feature_id=feature_id,
            feature_type=feature_type,
            candidates=(),
            phases=(),
            tool_families=(),
            rationale="Feature is not confirmed — no CAM operations generated",
            warnings=("CANDIDATE_NOT_CONFIRMED: feature must be confirmed before CAM mapping",),
        )

    effective_type = feature_type.lower()

    if effective_type == "hole" and depth_diameter_ratio is not None:
        if depth_diameter_ratio > _DEEP_HOLE_DEPTH_RATIO:
            effective_type = "deep_hole"

    if effective_type not in FEATURE_TO_CAM_MAP:
        return FeatureMappingResult(
            feature_id=feature_id,
            feature_type=feature_type,
            candidates=(),
            phases=(),
            tool_families=(),
            rationale=f"Feature type {feature_type!r} has no defined CAM mapping",
            warnings=(f"UNKNOWN_FEATURE_TYPE: {feature_type!r}",),
        )

    raw_candidates = FEATURE_TO_CAM_MAP[effective_type]
    filtered: list[tuple[CAMOperationType, OperationPhase, ToolFamilyRequirement, str]] = []
    warnings: list[str] = []

    for op, phase, tool_family, rationale in raw_candidates:
        if op in _TOLERANCE_REQUIRED_OPS and not has_tolerance_evidence:
            warnings.append(
                f"{op.value}: tolerance evidence required but not present — "
                "operation suppressed until tolerance data is available"
            )
            continue
        filtered.append((op, phase, tool_family, rationale))

    candidates = tuple(op for op, _, _, _ in filtered)
    phases = tuple(ph for _, ph, _, _ in filtered)
    tool_families = tuple(tf for _, _, tf, _ in filtered)
    rationale_parts = [r for _, _, _, r in filtered]
    rationale = "; ".join(rationale_parts) if rationale_parts else "No applicable operations"

    return FeatureMappingResult(
        feature_id=feature_id,
        feature_type=feature_type,
        candidates=candidates,
        phases=phases,
        tool_families=tool_families,
        rationale=rationale,
        requires_tolerance_evidence=effective_type == "tight_tolerance_hole",
        requires_depth_evidence=effective_type in ("hole", "deep_hole"),
        warnings=tuple(warnings),
    )


_STRATEGY_MAP: dict[CAMOperationType, CAMStrategyType] = {
    CAMOperationType.FACE_MILL: CAMStrategyType.CONVENTIONAL_POCKETING,
    CAMOperationType.ADAPTIVE_ROUGH: CAMStrategyType.ADAPTIVE_CLEARING,
    CAMOperationType.POCKET_ROUGH: CAMStrategyType.CONVENTIONAL_POCKETING,
    CAMOperationType.POCKET_FINISH: CAMStrategyType.CONTOUR_FINISH_STRATEGY,
    CAMOperationType.CONTOUR_ROUGH: CAMStrategyType.ADAPTIVE_CLEARING,
    CAMOperationType.CONTOUR_FINISH: CAMStrategyType.CONTOUR_FINISH_STRATEGY,
    CAMOperationType.BALL_END_FINISH: CAMStrategyType.PARALLEL_FINISH,
    CAMOperationType.SLOT_MILL: CAMStrategyType.CONVENTIONAL_POCKETING,
    CAMOperationType.DRILL: CAMStrategyType.DRILL_CYCLE,
    CAMOperationType.PECK_DRILL: CAMStrategyType.PECK_CYCLE,
    CAMOperationType.REAM: CAMStrategyType.REAM_CYCLE,
    CAMOperationType.BORE: CAMStrategyType.BORE_CYCLE,
    CAMOperationType.TAP: CAMStrategyType.DRILL_CYCLE,
    CAMOperationType.THREAD_MILL: CAMStrategyType.CONTOUR_FINISH_STRATEGY,
    CAMOperationType.CHAMFER: CAMStrategyType.CONTOUR_FINISH_STRATEGY,
    CAMOperationType.COUNTERBORE: CAMStrategyType.DRILL_CYCLE,
    CAMOperationType.COUNTERSINK: CAMStrategyType.DRILL_CYCLE,
    CAMOperationType.TURN_ROUGH: CAMStrategyType.CONVENTIONAL_POCKETING,
    CAMOperationType.TURN_FINISH: CAMStrategyType.Z_LEVEL_FINISH,
    CAMOperationType.FACE_TURN: CAMStrategyType.Z_LEVEL_FINISH,
    CAMOperationType.GROOVE: CAMStrategyType.DRILL_CYCLE,
    CAMOperationType.PART_OFF: CAMStrategyType.DRILL_CYCLE,
    CAMOperationType.REST_MACHINING: CAMStrategyType.PARALLEL_FINISH,
}


def get_cam_strategy_for_operation(op: CAMOperationType) -> CAMStrategyType | None:
    """Return the default strategy candidate for a given operation type."""
    return _STRATEGY_MAP.get(op)
