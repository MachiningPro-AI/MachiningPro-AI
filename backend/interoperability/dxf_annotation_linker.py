"""DXF annotation → manufacturing feature spatial linking (P1-B).

Links parsed DXF drawing annotations (DIMENSION, MTEXT, TEXT, ATTRIB)
to recognized manufacturing feature candidates using:
  1. DIMENSION_GEOMETRY  — dimension definition points on or near a feature
  2. SPATIAL_NEAREST     — text insertion point closest to a compatible feature
  3. LEADER_ASSOCIATION  — leader arrow endpoint near a feature boundary

HARD RULES:
  - Every link is CANDIDATE only — never auto-confirmed.
  - CONFLICT when two annotations target the same feature with incompatible data.
  - AMBIGUOUS when one annotation spatially resolves to >1 comparable candidate.
  - UNRESOLVED when no spatial evidence supports any link.
  - Black-box or semantic-text-only linking is PROHIBITED.
  - FABRICATED_LINK=NO — only evidence-supported associations are returned.

The module uses the existing backend.interoperability.association engine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique

from backend.interoperability.association import (
    AnnotationAssociation,
    AnnotationType,
    AssociationState,
    BoundingBox2D,
    FeatureType,
    associate_annotation,
)
from backend.interoperability.cad_feature_recognition import ManufacturingFeature

__all__ = [
    "DxfAnnotation",
    "DxfAnnotationSource",
    "DxfAnnotationLinkMethod",
    "DxfAnnotationLinkStatus",
    "DxfAnnotationLink",
    "DxfAnnotationLinkResult",
    "link_dxf_annotations",
    "dxf_feature_bbox",
]

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

@unique
class DxfAnnotationSource(StrEnum):
    DIMENSION = "DIMENSION"       # DXF DIMENSION entity
    MTEXT = "MTEXT"               # DXF MTEXT entity (multi-line text)
    TEXT = "TEXT"                 # DXF TEXT entity (single-line text)
    ATTRIB = "ATTRIB"             # DXF ATTRIB entity (attribute text)
    LEADER = "LEADER"             # DXF LEADER / MULTILEADER entity


@unique
class DxfAnnotationLinkMethod(StrEnum):
    DIMENSION_GEOMETRY  = "DIMENSION_GEOMETRY"   # Dimension def points bracket a feature
    SPATIAL_NEAREST     = "SPATIAL_NEAREST"      # Insertion point nearest compatible feature
    LEADER_ASSOCIATION  = "LEADER_ASSOCIATION"   # Leader arrow endpoint near feature boundary
    DIRECT_REFERENCE    = "DIRECT_REFERENCE"     # Entity handle reference in annotation


@unique
class DxfAnnotationLinkStatus(StrEnum):
    LINKED      = "LINKED"       # Single unambiguous spatial link
    AMBIGUOUS   = "AMBIGUOUS"    # Multiple candidate features; review required
    CONFLICT    = "CONFLICT"     # Two annotations disagree for the same feature
    UNRESOLVED  = "UNRESOLVED"   # No spatial evidence found


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DxfAnnotation:
    """A parsed DXF annotation with spatial context.

    Coordinates are in drawing units (mm assumed only when file header confirms).
    """

    annotation_id: str
    source: DxfAnnotationSource
    annotation_type: AnnotationType       # From association module
    text: str                             # Raw extracted text
    subtype: str | None = None            # e.g. "DIAMETRAL", "LINEAR", "RADIAL"

    # Spatial context (at least one must be provided for spatial linking)
    insertion_x: float | None = None     # Text insertion / annotation origin point
    insertion_y: float | None = None
    defpoint1_x: float | None = None     # Dimension definition point 1 (DXF: DEFPOINT)
    defpoint1_y: float | None = None
    defpoint2_x: float | None = None     # Dimension definition point 2
    defpoint2_y: float | None = None
    leader_x: float | None = None        # Leader arrow endpoint
    leader_y: float | None = None

    layer: str = "0"
    handle: str | None = None            # DXF entity handle for direct references

    @property
    def has_spatial_context(self) -> bool:
        return any([
            self.insertion_x is not None,
            self.defpoint1_x is not None,
            self.leader_x is not None,
        ])


@dataclass(frozen=True)
class DxfAnnotationLink:
    """A spatial link between a DXF annotation and a manufacturing feature.

    Every link is CANDIDATE only — user confirmation required before use.
    """

    annotation_id: str
    feature_id: str
    annotation_type: AnnotationType
    link_method: DxfAnnotationLinkMethod
    status: DxfAnnotationLinkStatus
    confidence: Decimal                  # 0–1; combined spatial + semantic score
    source: str = "DXF_SPATIAL_ANALYSIS"
    annotation_text: str = ""
    feature_type: FeatureType = FeatureType.UNKNOWN
    review_required: bool = True         # Always True — never auto-confirmed
    conflict_note: str | None = None     # Populated when status=CONFLICT
    candidate_count: int = 1             # Number of competing candidates


@dataclass
class DxfAnnotationLinkResult:
    """Full result of DXF annotation–feature linking.

    Fields
    ------
    linked          : annotations with a single unambiguous feature match
    ambiguous       : annotations with multiple comparable candidates
    conflicts       : annotation pairs that disagree on the same feature
    unresolved      : annotations with no spatial evidence
    total_annotations : total input annotations attempted
    total_features    : total input features attempted
    warnings          : non-fatal linking issues
    """

    linked: list[DxfAnnotationLink] = field(default_factory=list)
    ambiguous: list[DxfAnnotationLink] = field(default_factory=list)
    conflicts: list[DxfAnnotationLink] = field(default_factory=list)
    unresolved: list[DxfAnnotationLink] = field(default_factory=list)
    total_annotations: int = 0
    total_features: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def linked_count(self) -> int:
        return len(self.linked)

    @property
    def ambiguous_count(self) -> int:
        return len(self.ambiguous)

    @property
    def conflict_count(self) -> int:
        return len(self.conflicts)

    @property
    def unresolved_count(self) -> int:
        return len(self.unresolved)


# ---------------------------------------------------------------------------
# Spatial helpers
# ---------------------------------------------------------------------------

def dxf_feature_bbox(feature: ManufacturingFeature) -> BoundingBox2D | None:
    """Build a 2D bounding box for a manufacturing feature from its location.

    For 2D DXF features (circles), uses center ± radius. Returns None when
    insufficient spatial data is available.
    """
    if feature.location is None:
        return None
    try:
        cx = float(feature.location.x.value)
        cy = float(feature.location.y.value)
    except (AttributeError, TypeError, ValueError):
        return None

    if feature.radius_mm is not None:
        r = float(feature.radius_mm)
        return BoundingBox2D(
            x=Decimal(str(cx - r)),
            y=Decimal(str(cy - r)),
            width=Decimal(str(r * 2.0)),
            height=Decimal(str(r * 2.0)),
        )
    if feature.diameter_mm is not None:
        r = float(feature.diameter_mm) / 2.0
        return BoundingBox2D(
            x=Decimal(str(cx - r)),
            y=Decimal(str(cy - r)),
            width=Decimal(str(r * 2.0)),
            height=Decimal(str(r * 2.0)),
        )
    # Point feature with unknown extent — use 1×1 bounding box at center
    return BoundingBox2D(
        x=Decimal(str(cx - 0.5)),
        y=Decimal(str(cy - 0.5)),
        width=Decimal("1.0"),
        height=Decimal("1.0"),
    )


def _annotation_bbox(annotation: DxfAnnotation) -> BoundingBox2D | None:
    """Build bounding box for an annotation's primary position.

    Priority: defpoint1 (most accurate for DIMENSION), then insertion, then leader.
    """
    # DIMENSION: use midpoint of defpoints if both available
    if (annotation.defpoint1_x is not None and annotation.defpoint1_y is not None
            and annotation.defpoint2_x is not None and annotation.defpoint2_y is not None):
        mx = (annotation.defpoint1_x + annotation.defpoint2_x) / 2.0
        my = (annotation.defpoint1_y + annotation.defpoint2_y) / 2.0
        # Width spans the two defpoints
        w = abs(annotation.defpoint2_x - annotation.defpoint1_x) + 1.0
        h = abs(annotation.defpoint2_y - annotation.defpoint1_y) + 1.0
        return BoundingBox2D(
            x=Decimal(str(mx - w / 2.0)),
            y=Decimal(str(my - h / 2.0)),
            width=Decimal(str(w)),
            height=Decimal(str(h)),
        )
    # Insertion point
    if annotation.insertion_x is not None and annotation.insertion_y is not None:
        return BoundingBox2D(
            x=Decimal(str(annotation.insertion_x - 0.5)),
            y=Decimal(str(annotation.insertion_y - 0.5)),
            width=Decimal("1.0"),
            height=Decimal("1.0"),
        )
    # Leader endpoint
    if annotation.leader_x is not None and annotation.leader_y is not None:
        return BoundingBox2D(
            x=Decimal(str(annotation.leader_x - 0.5)),
            y=Decimal(str(annotation.leader_y - 0.5)),
            width=Decimal("1.0"),
            height=Decimal("1.0"),
        )
    return None


def _pick_link_method(annotation: DxfAnnotation) -> DxfAnnotationLinkMethod:
    """Choose the most informative link method based on available spatial data."""
    if annotation.handle is not None:
        return DxfAnnotationLinkMethod.DIRECT_REFERENCE
    if (annotation.defpoint1_x is not None and annotation.defpoint2_x is not None):
        return DxfAnnotationLinkMethod.DIMENSION_GEOMETRY
    if annotation.leader_x is not None:
        return DxfAnnotationLinkMethod.LEADER_ASSOCIATION
    return DxfAnnotationLinkMethod.SPATIAL_NEAREST


# ---------------------------------------------------------------------------
# Conflict detection
# ---------------------------------------------------------------------------

def _detect_conflicts(
    links: list[tuple[DxfAnnotation, AnnotationAssociation]],
    feature_bboxes: dict[str, tuple[BoundingBox2D, FeatureType]],
) -> list[DxfAnnotationLink]:
    """Detect CONFLICT when two annotations both auto-match the same feature.

    A conflict arises when:
    - Two annotations both have AUTO_MATCHED state
    - Both point to the same feature_id
    - Their texts are incompatible (e.g. two different diameters for one hole)
    """
    conflicts: list[DxfAnnotationLink] = []
    # Build feature → list of AUTO_MATCHED annotations
    feature_to_annotations: dict[str, list[DxfAnnotation]] = {}
    for ann, assoc in links:
        if (assoc.state == AssociationState.AUTO_MATCHED
                and assoc.confirmed_feature_id is not None):
            fid = assoc.confirmed_feature_id
            feature_to_annotations.setdefault(fid, []).append(ann)

    for fid, anns in feature_to_annotations.items():
        if len(anns) < 2:
            continue
        # Multiple annotations matched the same feature — check for text conflict
        # (different texts imply different values — flag as CONFLICT)
        texts = {a.text.strip() for a in anns}
        if len(texts) > 1:
            # Flag ALL annotations for this feature as CONFLICT
            for ann in anns:
                bbox = feature_bboxes.get(fid, (None, FeatureType.UNKNOWN))
                conflicts.append(DxfAnnotationLink(
                    annotation_id=ann.annotation_id,
                    feature_id=fid,
                    annotation_type=ann.annotation_type,
                    link_method=_pick_link_method(ann),
                    status=DxfAnnotationLinkStatus.CONFLICT,
                    confidence=Decimal("0.30"),
                    annotation_text=ann.text,
                    feature_type=bbox[1],
                    review_required=True,
                    conflict_note=(
                        f"Multiple annotations conflict for feature {fid}: "
                        + ", ".join(repr(t) for t in sorted(texts))
                    ),
                    candidate_count=len(anns),
                ))

    return conflicts


# ---------------------------------------------------------------------------
# Main linking function
# ---------------------------------------------------------------------------

def link_dxf_annotations(
    annotations: list[DxfAnnotation],
    features: list[ManufacturingFeature],
    *,
    max_proximity_mm: float = 50.0,
) -> DxfAnnotationLinkResult:
    """Link DXF annotations to manufacturing feature candidates.

    Args:
        annotations:       Parsed DXF annotations (DIMENSION, MTEXT, TEXT, ATTRIB).
        features:          Recognized manufacturing features (from recognize_dxf_features).
        max_proximity_mm:  Maximum distance (mm) for spatial nearest-neighbor matching.

    Returns:
        DxfAnnotationLinkResult with categorized links.

    FABRICATED_LINK=NO
    BLACK_BOX_ASSUMPTION=NO
    AUTO_CONFIRMED=NO
    """
    result = DxfAnnotationLinkResult(
        total_annotations=len(annotations),
        total_features=len(features),
    )

    if not features:
        result.warnings.append("NO_FEATURES: no manufacturing features to link annotations to")
        for ann in annotations:
            result.unresolved.append(DxfAnnotationLink(
                annotation_id=ann.annotation_id,
                feature_id="",
                annotation_type=ann.annotation_type,
                link_method=DxfAnnotationLinkMethod.SPATIAL_NEAREST,
                status=DxfAnnotationLinkStatus.UNRESOLVED,
                confidence=Decimal("0"),
                annotation_text=ann.text,
            ))
        return result

    # Build feature bounding boxes
    feature_bboxes: dict[str, tuple[BoundingBox2D, FeatureType]] = {}
    for feat in features:
        bbox = dxf_feature_bbox(feat)
        if bbox is not None:
            feature_bboxes[feat.feature_id] = (bbox, FeatureType.HOLE)

    if not feature_bboxes:
        result.warnings.append("NO_FEATURE_GEOMETRY: features have no spatial data")

    max_prox = Decimal(str(max_proximity_mm))

    # Associate each annotation
    raw_links: list[tuple[DxfAnnotation, AnnotationAssociation]] = []
    for ann in annotations:
        if not ann.has_spatial_context:
            result.unresolved.append(DxfAnnotationLink(
                annotation_id=ann.annotation_id,
                feature_id="",
                annotation_type=ann.annotation_type,
                link_method=DxfAnnotationLinkMethod.SPATIAL_NEAREST,
                status=DxfAnnotationLinkStatus.UNRESOLVED,
                confidence=Decimal("0"),
                annotation_text=ann.text,
            ))
            continue

        ann_bbox = _annotation_bbox(ann)
        assoc = associate_annotation(
            annotation_id=ann.annotation_id,
            annotation_type=ann.annotation_type,
            annotation_bbox=ann_bbox,
            annotation_subtype=ann.subtype,
            feature_bboxes=feature_bboxes,
            max_proximity_pts=max_prox,
        )
        raw_links.append((ann, assoc))

    # Detect conflicts (before converting to links)
    conflicts = _detect_conflicts(raw_links, feature_bboxes)
    conflict_annotation_ids = {c.annotation_id for c in conflicts}
    result.conflicts.extend(conflicts)

    # Convert associations to links
    for ann, assoc in raw_links:
        if ann.annotation_id in conflict_annotation_ids:
            continue  # Already handled as conflict

        link_method = _pick_link_method(ann)
        feat_type = FeatureType.UNKNOWN

        if assoc.state == AssociationState.UNRESOLVED:
            result.unresolved.append(DxfAnnotationLink(
                annotation_id=ann.annotation_id,
                feature_id="",
                annotation_type=ann.annotation_type,
                link_method=link_method,
                status=DxfAnnotationLinkStatus.UNRESOLVED,
                confidence=Decimal("0"),
                annotation_text=ann.text,
            ))

        elif assoc.state == AssociationState.MULTIPLE_CANDIDATES:
            best_cand = assoc.candidates[0] if assoc.candidates else None
            feat_id = best_cand.feature_id if best_cand else ""
            if best_cand and feat_id in feature_bboxes:
                feat_type = feature_bboxes[feat_id][1]
            result.ambiguous.append(DxfAnnotationLink(
                annotation_id=ann.annotation_id,
                feature_id=feat_id,
                annotation_type=ann.annotation_type,
                link_method=link_method,
                status=DxfAnnotationLinkStatus.AMBIGUOUS,
                confidence=best_cand.combined_score if best_cand else Decimal("0"),
                annotation_text=ann.text,
                feature_type=feat_type,
                candidate_count=len(assoc.candidates),
            ))

        elif assoc.state == AssociationState.AUTO_MATCHED:
            feat_id = assoc.confirmed_feature_id or ""
            if feat_id in feature_bboxes:
                feat_type = feature_bboxes[feat_id][1]
            best_cand = assoc.candidates[0] if assoc.candidates else None
            result.linked.append(DxfAnnotationLink(
                annotation_id=ann.annotation_id,
                feature_id=feat_id,
                annotation_type=ann.annotation_type,
                link_method=link_method,
                status=DxfAnnotationLinkStatus.LINKED,
                confidence=best_cand.combined_score if best_cand else Decimal("0.60"),
                annotation_text=ann.text,
                feature_type=feat_type,
                candidate_count=1,
            ))

    return result
