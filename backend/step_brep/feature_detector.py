"""
Hole candidate detection from STEP B-Rep (P10 Phase 3).

Detects HOLE_CANDIDATE features from cylindrical surfaces with circular boundaries.

Classification rules:
  - Cylindrical surface with 2 circular boundaries → THROUGH_HOLE_CANDIDATE
  - Cylindrical surface with 1 circular boundary → BLIND_HOLE_CANDIDATE
  - Diameter from cylindrical surface bbox (not fabricated)

Feature status: always CANDIDATE — never CONFIRMED in this phase.
Confirmation requires topology adjacency + depth verification.

HARD RULE: Feature counts and diameters come from real gmsh geometry.
           No fabricated hole depths unless from B-Rep floor detection.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.step_brep.gmsh_step_parser import StepImportRecord

__all__ = [
    "HoleCandidateRecord",
    "detect_hole_candidates",
]

_MIN_HOLE_DIAMETER_MM = 0.5
_MAX_HOLE_DIAMETER_MM = 500.0


@dataclass(frozen=True)
class HoleCandidateRecord:
    """A candidate hole feature extracted from a STEP B-Rep.

    feature_status is always CANDIDATE — confirmation requires topology adjacency.
    is_dispatchable is always False.
    """

    face_tag: int
    feature_status: str  # always "CANDIDATE"
    hole_class: str  # THROUGH_HOLE_CANDIDATE | BLIND_HOLE_CANDIDATE
    diameter_mm: float
    axis_direction: str | None  # X | Y | Z | None
    circular_boundary_count: int
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]

    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def depth_mm(self) -> float | None:
        """Estimated depth from bbox extent along axis. None if axis unknown."""
        if self.axis_direction is None:
            return None
        axis_extents = {
            "X": self.bbox_max[0] - self.bbox_min[0],
            "Y": self.bbox_max[1] - self.bbox_min[1],
            "Z": self.bbox_max[2] - self.bbox_min[2],
        }
        return axis_extents.get(self.axis_direction)


def detect_hole_candidates(record: StepImportRecord) -> list[HoleCandidateRecord]:
    """Detect hole candidates from a successfully parsed StepImportRecord.

    Returns an empty list if record.status != "PASS" or no cylindrical faces exist.
    All geometry values are from real B-Rep data in record.faces.

    HARD RULE: Never fabricate hole diameters or depths.
    """
    if record.status != "PASS":
        return []

    candidates: list[HoleCandidateRecord] = []

    for face in record.faces:
        if face.surface_class != "CYLINDRICAL":
            continue

        # We use boundary_curve_tags count as a proxy for hole classification

        # Get bbox dimensions to infer hole geometry
        xmin, ymin, zmin = face.bbox_min
        xmax, ymax, zmax = face.bbox_max
        dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin

        # Estimate diameter from cylindrical surface bbox
        # For a Z-axis cylinder: bbox is (d x d x depth), diameter = avg(dx, dy)
        # Determine which dimension is the axis (largest)
        extents = {"X": dx, "Y": dy, "Z": dz}
        sorted_axes = sorted(extents, key=lambda k: extents[k], reverse=True)
        axis = sorted_axes[0]
        lateral_extents = [extents[a] for a in sorted_axes[1:]]

        if len(lateral_extents) == 2:
            diameter = sum(lateral_extents) / 2.0
        else:
            diameter = lateral_extents[0] if lateral_extents else 0.0

        if diameter < _MIN_HOLE_DIAMETER_MM or diameter > _MAX_HOLE_DIAMETER_MM:
            continue

        # Through vs blind: through hole has 2 open circular boundaries
        # We use boundary curve count as a proxy; for a simple cylinder wall:
        #   2 curves (both circles) → through hole candidate
        #   1-2 curves with uncertain count → use boundary_curve_tags length
        n_boundary = len(face.boundary_curve_tags)
        if n_boundary >= 2:
            hole_class = "THROUGH_HOLE_CANDIDATE"
        else:
            hole_class = "BLIND_HOLE_CANDIDATE"

        candidates.append(HoleCandidateRecord(
            face_tag=face.tag,
            feature_status="CANDIDATE",
            hole_class=hole_class,
            diameter_mm=round(diameter, 4),
            axis_direction=axis,
            circular_boundary_count=n_boundary,
            bbox_min=face.bbox_min,
            bbox_max=face.bbox_max,
        ))

    return candidates
