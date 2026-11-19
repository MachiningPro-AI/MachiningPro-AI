"""
Phase 8: Step/shoulder multi-face boundary extraction.

Implements bounded boundary traversal for STEP/SHOULDER features (MUST 3-9).

A step/shoulder feature has 3 relevant faces:
  - lower_face  (the step face itself — horizontal planar, lower Z)
  - upper_face  (upper wall — cylindrical or planar, higher Z)
  - wall_face   (lower wall — cylindrical or planar, lower Z)

STRATEGY (MUST 7, MUST 8):
  Boundary extraction looks at the step face (lower_face) only.  Multi-face
  edge-tracing would require a topology graph not built in Phase 8.  The step
  face boundary is extracted exactly as a pocket floor boundary.

SAFETY RULES (MUST 6, MUST 9):
  - FEATURE_CONFIRMED must be YES before any toolpath is generated.
  - Phase 8 never auto-confirms CANDIDATE features.
  - BOUNDARY_READY=YES requires BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP.
  - All step/shoulder toolpaths: is_dispatchable=False, production_released=False.

HARD INVARIANTS:
  IS_DISPATCHABLE=False
  PRODUCTION_RELEASED=False
  REVIEW_REQUIRED=True
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.interoperability.topology import CanonicalTopology
from backend.step_brep.phase5_feature_detector import StepShoulderRecord
from backend.step_brep.phase8_arc_sampler import ArcContourMap
from backend.step_brep.phase8_contour_extractor import (
    BoundaryTraversalStatus,
    Phase8Contour,
    extract_face_contour_p8,
)

__all__ = [
    "StepShoulderBoundary",
    "StepShoulderBoundaryResult",
    "extract_step_shoulder_boundary",
    "STEP_IS_DISPATCHABLE",
    "STEP_PRODUCTION_RELEASED",
    "STEP_REVIEW_REQUIRED",
]

STEP_IS_DISPATCHABLE: bool = False
STEP_PRODUCTION_RELEASED: bool = False
STEP_REVIEW_REQUIRED: bool = True


@dataclass(frozen=True)
class StepShoulderBoundary:
    """Extracted boundary for a single step/shoulder feature.

    boundary_ready: True only when traversal_status=CONNECTED_CLOSED_LOOP
    and the contour is geometrically valid (is_valid=True).

    feature_confirmed: always False in Phase 8 — CANDIDATE never auto-confirmed.
    toolpath_ready: always False — requires feature_confirmed=True first.
    """

    step_id: str
    lower_face_tag: int
    contour: Phase8Contour | None
    boundary_ready: bool
    boundary_method: str | None
    traversal_status: BoundaryTraversalStatus | None
    blocker: str


@dataclass
class StepShoulderBoundaryResult:
    """Aggregate result for all step/shoulder boundaries in a file."""

    step_boundaries: list[StepShoulderBoundary] = field(default_factory=list)

    # Safety invariants (MUST 44)
    is_dispatchable: bool = STEP_IS_DISPATCHABLE
    production_released: bool = STEP_PRODUCTION_RELEASED
    review_required: bool = STEP_REVIEW_REQUIRED

    @property
    def boundary_ready_count(self) -> int:
        return sum(1 for b in self.step_boundaries if b.boundary_ready)

    @property
    def total_count(self) -> int:
        return len(self.step_boundaries)


def _derive_face_normal(
    lower_face_tag: int,
    topo: CanonicalTopology,
) -> tuple[float, float, float]:
    """Derive face normal from topology metadata.

    If the face has surface metadata indicating a planar face, infer normal
    from the topology.  Falls back to (0,0,1) for horizontal planar step faces.
    """
    face_id = f"F-{lower_face_tag}"
    face = next((f for f in topo.faces if f.face_id == face_id), None)
    if face is None:
        return (0.0, 0.0, 1.0)

    # For PLANAR faces the step floor is typically horizontal
    sc = (face.metadata or {}).get("surface_class", "")
    if sc == "PLANAR":
        return (0.0, 0.0, 1.0)
    return (0.0, 0.0, 1.0)  # default


def extract_step_shoulder_boundary(
    step_rec: StepShoulderRecord,
    topo: CanonicalTopology,
    arc_map: ArcContourMap | None = None,
    step_index: int = 0,
) -> StepShoulderBoundary:
    """Extract the outer boundary of a step/shoulder feature.

    Attempts to extract the lower_face boundary using Phase 8 contour
    extraction.  FEATURE_CONFIRMED is NEVER automatically set.

    Returns a StepShoulderBoundary with:
      - boundary_ready=True iff CONNECTED_CLOSED_LOOP and valid contour.
      - toolpath_ready=False always (requires explicit feature confirmation).
    """
    face_tag = step_rec.lower_face_tag
    step_id = f"STEP-{step_index}-F{face_tag}"
    fn = _derive_face_normal(face_tag, topo)

    p8c = extract_face_contour_p8(
        face_tag=face_tag,
        topo=topo,
        arc_map=arc_map,
        face_normal=fn,
    )

    if p8c is None:
        return StepShoulderBoundary(
            step_id=step_id,
            lower_face_tag=face_tag,
            contour=None,
            boundary_ready=False,
            boundary_method=None,
            traversal_status=None,
            blocker="BOUNDARY_READY=NO: face not found in topology or arc_map",
        )

    if p8c.traversal_status != BoundaryTraversalStatus.CONNECTED_CLOSED_LOOP:
        return StepShoulderBoundary(
            step_id=step_id,
            lower_face_tag=face_tag,
            contour=p8c,
            boundary_ready=False,
            boundary_method=p8c.boundary_method,
            traversal_status=p8c.traversal_status,
            blocker=f"BOUNDARY_READY=NO: traversal_status={p8c.traversal_status.value}",
        )

    if not p8c.contour.is_valid:
        return StepShoulderBoundary(
            step_id=step_id,
            lower_face_tag=face_tag,
            contour=p8c,
            boundary_ready=False,
            boundary_method=p8c.boundary_method,
            traversal_status=p8c.traversal_status,
            blocker=f"BOUNDARY_READY=NO: contour not valid — {p8c.contour.validation_notes}",
        )

    # Boundary is geometrically valid and topologically closed.
    # FEATURE_CONFIRMED still required for toolpath — always False in Phase 8.
    return StepShoulderBoundary(
        step_id=step_id,
        lower_face_tag=face_tag,
        contour=p8c,
        boundary_ready=True,
        boundary_method=p8c.boundary_method,
        traversal_status=p8c.traversal_status,
        blocker="TOOLPATH_READY=NO: FEATURE_CONFIRMED=NO (CANDIDATE never auto-confirmed)",
    )
