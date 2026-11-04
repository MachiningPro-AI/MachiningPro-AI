"""Manufacturing feature evidence model for the interoperability layer (Level 3).

Defines the deterministic, immutable data model for manufacturing feature
recognition results.  Adapters that perform feature recognition populate
FeatureRecognitionResult and attach it to the CanonicalDocument.

Evidence-based classification
------------------------------
Features progress through evidence states.  A feature MUST NOT reach
CONFIRMED without sufficient geometric/topological evidence:

  CANDIDATE   -- geometric hint present (e.g. a cylindrical surface, a 2-D
                 circle), but topology / depth / bounding evidence is absent.
                 A DXF circle is at most a CANDIDATE — it has no depth.
                 A lone cylindrical surface is at most a CANDIDATE — it
                 has no bounding loops or confirmed axis orientation.

  CONFIRMED   -- deterministic evidence from geometry AND topology:
                 cylindrical face + bounding planar caps + inner loop
                 sharing the same axis → HOLE CONFIRMED.  Rules for each
                 feature type are enumerated in feature_recognition.py.

  INCOMPLETE  -- some evidence gathered but required elements are absent
                 (e.g. cylinder found, but no bounding planar faces).

  REJECTED    -- initially a candidate, but contradicting evidence found
                 (e.g. cylinder flagged as hole candidate, but no open end).

  UNKNOWN     -- insufficient data to classify.

Non-goals
---------
* No feature evaluation or machining simulation.
* No DFM rule application (this is the evidence layer only).
* No inference of manufacturing operations, tools, or parameters.
* No topology construction (see topology.py for that).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType

from backend.domain.base import entity_as_dict, optional_non_empty_str, require_non_empty_str
from backend.domain.exceptions import ValidationError

__all__ = [
    "ClassifiedFace",
    "FaceAdjacency",
    "FaceClassification",
    "FeatureRecognitionResult",
    "FeatureStatus",
    "HoleSubtype",
    "ManufacturingFeature",
    "ManufacturingFeatureType",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class FeatureStatus(StrEnum):
    """Evidence state of a manufacturing feature classification.

    CANDIDATE and INCOMPLETE must never be promoted to CONFIRMED without
    deterministic geometric/topological proof.
    """

    CANDIDATE = "CANDIDATE"
    """Geometric hint present; topology/depth/bounding evidence absent."""

    CONFIRMED = "CONFIRMED"
    """Deterministic evidence from geometry AND topology is sufficient."""

    INCOMPLETE = "INCOMPLETE"
    """Partial evidence; required elements (e.g. bounding faces) absent."""

    REJECTED = "REJECTED"
    """Initially a candidate but contradicting evidence found."""

    UNKNOWN = "UNKNOWN"
    """Insufficient data to classify."""


class ManufacturingFeatureType(StrEnum):
    """Classification of a recognized manufacturing feature."""

    HOLE = "HOLE"
    POCKET = "POCKET"
    SLOT = "SLOT"
    STEP = "STEP"
    CHAMFER = "CHAMFER"
    FILLET = "FILLET"
    UNKNOWN = "UNKNOWN"


class HoleSubtype(StrEnum):
    """Sub-classification of a HOLE feature.

    Requires deterministic topology evidence for any value other than UNKNOWN.
    """

    THROUGH = "THROUGH"
    """Cylinder bounded by planar faces on both ends."""

    BLIND = "BLIND"
    """Cylinder bounded by a planar face on one end only."""

    COUNTERBORE = "COUNTERBORE"
    """Two concentric cylindrical steps with a planar shoulder."""

    COUNTERSINK = "COUNTERSINK"
    """Conical entry face above a cylindrical bore; matching axis."""

    UNKNOWN = "UNKNOWN"
    """Hole type could not be determined from available evidence."""


class FaceClassification(StrEnum):
    """Topological face classification by underlying surface type."""

    PLANAR = "PLANAR"
    CYLINDRICAL = "CYLINDRICAL"
    CONICAL = "CONICAL"
    SPHERICAL = "SPHERICAL"
    TOROIDAL = "TOROIDAL"
    FREEFORM = "FREEFORM"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Face classification record
# ---------------------------------------------------------------------------

def _empty_proxy() -> MappingProxyType:
    return MappingProxyType({})


@dataclass(frozen=True, slots=True)
class ClassifiedFace:
    """A surface from CanonicalGeometry classified by its analytical type.

    surface_id references a CanonicalSurface.surface_id.
    When topology is available, face_id references a CanonicalFace.face_id.
    """

    surface_id: str
    classification: FaceClassification
    face_id: str | None = None
    source_entity_ref: str | None = None
    metadata: MappingProxyType = field(default_factory=_empty_proxy)

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "surface_id", require_non_empty_str(self.surface_id, "surface_id"))
        if not isinstance(self.classification, FaceClassification):
            raise ValidationError("classification must be a FaceClassification")
        if self.face_id is not None:
            _set(self, "face_id", require_non_empty_str(self.face_id, "face_id"))
        _set(
            self,
            "source_entity_ref",
            optional_non_empty_str(self.source_entity_ref, "source_entity_ref"),
        )
        _set(self, "metadata", MappingProxyType(dict(self.metadata or {})))

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Face adjacency record
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FaceAdjacency:
    """A face-to-face adjacency relationship derived from topology.

    Requires CanonicalTopology to be present; adjacencies cannot be computed
    from geometry alone.  face_a_surface_id and face_b_surface_id reference
    CanonicalSurface.surface_id values.
    """

    face_a_surface_id: str
    face_b_surface_id: str
    shared_edge_count: int
    face_a_face_id: str | None = None
    face_b_face_id: str | None = None

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(
            self,
            "face_a_surface_id",
            require_non_empty_str(self.face_a_surface_id, "face_a_surface_id"),
        )
        _set(
            self,
            "face_b_surface_id",
            require_non_empty_str(self.face_b_surface_id, "face_b_surface_id"),
        )
        if (
            isinstance(self.shared_edge_count, bool)
            or not isinstance(self.shared_edge_count, int)
            or self.shared_edge_count < 0
        ):
            raise ValidationError("shared_edge_count must be a non-negative integer")
        if self.face_a_face_id is not None:
            _set(
                self,
                "face_a_face_id",
                require_non_empty_str(self.face_a_face_id, "face_a_face_id"),
            )
        if self.face_b_face_id is not None:
            _set(
                self,
                "face_b_face_id",
                require_non_empty_str(self.face_b_face_id, "face_b_face_id"),
            )

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Manufacturing feature evidence record
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class ManufacturingFeature:
    """Evidence record for a single recognized (or candidate) manufacturing feature.

    surface_ids reference CanonicalGeometry surfaces.
    face_ids reference CanonicalTopology faces (empty when topology absent).
    curve_ids reference CanonicalGeometry curves (e.g. 2-D circle → hole candidate).
    source_entity_refs provide format-level traceability.

    Status rules
    ------------
    CONFIRMED requires both a valid feature_type AND sufficient evidence
    in surface_ids / face_ids / curve_ids as governed by the recognition
    rules in feature_recognition.py.  Callers must not create CONFIRMED
    features without that evidence chain.
    """

    feature_id: str
    feature_type: ManufacturingFeatureType
    status: FeatureStatus
    hole_subtype: HoleSubtype | None = None
    surface_ids: tuple[str, ...] = ()
    face_ids: tuple[str, ...] = ()
    curve_ids: tuple[str, ...] = ()
    source_entity_refs: tuple[str, ...] = ()
    evidence_notes: str = ""

    def __post_init__(self) -> None:
        _set = object.__setattr__
        _set(self, "feature_id", require_non_empty_str(self.feature_id, "feature_id"))
        if not isinstance(self.feature_type, ManufacturingFeatureType):
            raise ValidationError("feature_type must be a ManufacturingFeatureType")
        if not isinstance(self.status, FeatureStatus):
            raise ValidationError("status must be a FeatureStatus")
        if self.hole_subtype is not None and not isinstance(self.hole_subtype, HoleSubtype):
            raise ValidationError("hole_subtype must be a HoleSubtype or None")
        for attr in ("surface_ids", "face_ids", "curve_ids", "source_entity_refs"):
            vals = tuple(getattr(self, attr))
            for i, v in enumerate(vals):
                if not isinstance(v, str) or not v.strip():
                    raise ValidationError(f"{attr}[{i}] must be a non-empty string")
            _set(self, attr, vals)
        if not isinstance(self.evidence_notes, str):
            raise ValidationError("evidence_notes must be a string")

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)


# ---------------------------------------------------------------------------
# Feature recognition result container
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class FeatureRecognitionResult:
    """Immutable container for one adapter's manufacturing feature recognition pass.

    Counts
    ------
    *_face_count fields count ClassifiedFace entries by FaceClassification.
    closed_loop_count counts inner loops from CanonicalTopology (0 when topology absent).
    adjacency_count == len(adjacencies).

    Basis
    -----
    recognition_basis describes what data was available:
      "TOPOLOGY"          full B-Rep topology + geometry
      "GEOMETRY_ONLY"     3-D geometry present, topology absent
      "2D_GEOMETRY_ONLY"  2-D drawing geometry (DXF), no 3-D surfaces
      "NONE"              no geometric data
    """

    classified_faces: tuple[ClassifiedFace, ...]
    adjacencies: tuple[FaceAdjacency, ...]
    features: tuple[ManufacturingFeature, ...]

    planar_face_count: int = 0
    cylindrical_face_count: int = 0
    conical_face_count: int = 0
    spherical_face_count: int = 0
    toroidal_face_count: int = 0
    freeform_face_count: int = 0

    closed_loop_count: int = 0
    adjacency_count: int = 0

    topology_available: bool = False
    adjacency_available: bool = False
    recognition_basis: str = "NONE"

    def __post_init__(self) -> None:
        _set = object.__setattr__
        for attr, expected in (
            ("classified_faces", ClassifiedFace),
            ("adjacencies", FaceAdjacency),
            ("features", ManufacturingFeature),
        ):
            items = tuple(getattr(self, attr))
            for i, item in enumerate(items):
                if not isinstance(item, expected):
                    raise ValidationError(
                        f"{attr}[{i}] must be a {expected.__name__}"
                    )
            _set(self, attr, items)
        for count_attr in (
            "planar_face_count", "cylindrical_face_count", "conical_face_count",
            "spherical_face_count", "toroidal_face_count", "freeform_face_count",
            "closed_loop_count", "adjacency_count",
        ):
            v = getattr(self, count_attr)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise ValidationError(f"{count_attr} must be a non-negative integer")
        if not isinstance(self.topology_available, bool):
            raise ValidationError("topology_available must be bool")
        if not isinstance(self.adjacency_available, bool):
            raise ValidationError("adjacency_available must be bool")
        if not isinstance(self.recognition_basis, str):
            raise ValidationError("recognition_basis must be a string")

    # ------------------------------------------------------------------
    # Derived counts — by feature type and status
    # ------------------------------------------------------------------

    def _count(
        self,
        feature_type: ManufacturingFeatureType,
        status: FeatureStatus | None = None,
        hole_subtype: HoleSubtype | None = None,
    ) -> int:
        result = 0
        for f in self.features:
            if f.feature_type != feature_type:
                continue
            if status is not None and f.status != status:
                continue
            if hole_subtype is not None and f.hole_subtype != hole_subtype:
                continue
            result += 1
        return result

    @property
    def hole_candidates(self) -> int:
        return self._count(ManufacturingFeatureType.HOLE, FeatureStatus.CANDIDATE)

    @property
    def confirmed_holes(self) -> int:
        return self._count(ManufacturingFeatureType.HOLE, FeatureStatus.CONFIRMED)

    @property
    def through_holes(self) -> int:
        return self._count(
            ManufacturingFeatureType.HOLE,
            FeatureStatus.CONFIRMED,
            HoleSubtype.THROUGH,
        )

    @property
    def blind_holes(self) -> int:
        return self._count(
            ManufacturingFeatureType.HOLE,
            FeatureStatus.CONFIRMED,
            HoleSubtype.BLIND,
        )

    @property
    def counterbores(self) -> int:
        return self._count(
            ManufacturingFeatureType.HOLE,
            FeatureStatus.CONFIRMED,
            HoleSubtype.COUNTERBORE,
        )

    @property
    def countersinks(self) -> int:
        return self._count(
            ManufacturingFeatureType.HOLE,
            FeatureStatus.CONFIRMED,
            HoleSubtype.COUNTERSINK,
        )

    @property
    def pocket_candidates(self) -> int:
        return self._count(ManufacturingFeatureType.POCKET, FeatureStatus.CANDIDATE)

    @property
    def confirmed_pockets(self) -> int:
        return self._count(ManufacturingFeatureType.POCKET, FeatureStatus.CONFIRMED)

    @property
    def slot_candidates(self) -> int:
        return self._count(ManufacturingFeatureType.SLOT, FeatureStatus.CANDIDATE)

    @property
    def confirmed_slots(self) -> int:
        return self._count(ManufacturingFeatureType.SLOT, FeatureStatus.CONFIRMED)

    @property
    def steps(self) -> int:
        return self._count(ManufacturingFeatureType.STEP, FeatureStatus.CONFIRMED)

    @property
    def chamfers(self) -> int:
        return self._count(ManufacturingFeatureType.CHAMFER, FeatureStatus.CONFIRMED)

    @property
    def fillets(self) -> int:
        return self._count(ManufacturingFeatureType.FILLET, FeatureStatus.CONFIRMED)

    def as_dict(self) -> dict[str, object]:
        return entity_as_dict(self)
