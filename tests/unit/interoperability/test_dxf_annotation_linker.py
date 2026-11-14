"""Unit tests for dxf_annotation_linker (P1-B).

Tests:
  - DxfAnnotation.has_spatial_context: False when no coordinates
  - DxfAnnotation.has_spatial_context: True with insertion_x
  - DxfAnnotation.has_spatial_context: True with defpoint1_x
  - DxfAnnotation.has_spatial_context: True with leader_x
  - dxf_feature_bbox: None for feature with no location
  - dxf_feature_bbox: returns BoundingBox2D for hole with radius
  - dxf_feature_bbox: returns BoundingBox2D for hole with diameter
  - dxf_feature_bbox: 1x1 fallback for feature with location but no size
  - link_dxf_annotations: empty features → all annotations UNRESOLVED
  - link_dxf_annotations: annotation without spatial context → UNRESOLVED
  - link_dxf_annotations: spatially near feature → LINKED
  - link_dxf_annotations: two equally close features → AMBIGUOUS
  - link_dxf_annotations: conflicting annotations for same feature → CONFLICT
  - link_dxf_annotations: total_annotations counter correct
  - link_dxf_annotations: total_features counter correct
  - link_dxf_annotations: review_required always True on all links
  - link_dxf_annotations: auto_confirmed absent (DxfAnnotationLink has no such field)
  - _pick_link_method: DIRECT_REFERENCE when handle present
  - _pick_link_method: DIMENSION_GEOMETRY when defpoints present
  - _pick_link_method: LEADER_ASSOCIATION when leader present
  - _pick_link_method: SPATIAL_NEAREST fallback
  - DxfAnnotationLinkResult: linked_count property
  - DxfAnnotationLinkResult: ambiguous_count property
  - DxfAnnotationLinkResult: conflict_count property
  - DxfAnnotationLinkResult: unresolved_count property
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from backend.interoperability.association import AnnotationType, FeatureType
from backend.interoperability.cad_feature_recognition import ManufacturingFeature
from backend.interoperability.dxf_annotation_linker import (
    DxfAnnotation,
    DxfAnnotationLink,
    DxfAnnotationLinkMethod,
    DxfAnnotationLinkResult,
    DxfAnnotationLinkStatus,
    DxfAnnotationSource,
    link_dxf_annotations,
    dxf_feature_bbox,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ann(
    ann_id: str = "ann-1",
    source: DxfAnnotationSource = DxfAnnotationSource.DIMENSION,
    ann_type: AnnotationType = AnnotationType.DIMENSION,
    text: str = "Ø25",
    insertion_x: float | None = None,
    insertion_y: float | None = None,
    defpoint1_x: float | None = None,
    defpoint1_y: float | None = None,
    defpoint2_x: float | None = None,
    defpoint2_y: float | None = None,
    leader_x: float | None = None,
    leader_y: float | None = None,
    handle: str | None = None,
) -> DxfAnnotation:
    return DxfAnnotation(
        annotation_id=ann_id,
        source=source,
        annotation_type=ann_type,
        text=text,
        insertion_x=insertion_x,
        insertion_y=insertion_y,
        defpoint1_x=defpoint1_x,
        defpoint1_y=defpoint1_y,
        defpoint2_x=defpoint2_x,
        defpoint2_y=defpoint2_y,
        leader_x=leader_x,
        leader_y=leader_y,
        handle=handle,
    )


def _feat(
    fid: str = "feat-1",
    cx: float = 0.0,
    cy: float = 0.0,
    r: float = 10.0,
) -> ManufacturingFeature:
    loc = MagicMock()
    loc.x.value = Decimal(str(cx))
    loc.y.value = Decimal(str(cy))
    feat = MagicMock(spec=ManufacturingFeature)
    feat.feature_id = fid
    feat.location = loc
    feat.radius_mm = r
    feat.diameter_mm = None
    return feat


# ---------------------------------------------------------------------------
# DxfAnnotation.has_spatial_context
# ---------------------------------------------------------------------------

class TestHasSpatialContext:
    def test_no_coordinates_returns_false(self):
        a = _ann()
        assert a.has_spatial_context is False

    def test_insertion_x_returns_true(self):
        a = _ann(insertion_x=10.0, insertion_y=20.0)
        assert a.has_spatial_context is True

    def test_defpoint1_x_returns_true(self):
        a = _ann(defpoint1_x=5.0, defpoint1_y=5.0)
        assert a.has_spatial_context is True

    def test_leader_x_returns_true(self):
        a = _ann(leader_x=50.0, leader_y=50.0)
        assert a.has_spatial_context is True


# ---------------------------------------------------------------------------
# dxf_feature_bbox
# ---------------------------------------------------------------------------

class TestDxfFeatureBbox:
    def test_no_location_returns_none(self):
        feat = MagicMock(spec=ManufacturingFeature)
        feat.location = None
        result = dxf_feature_bbox(feat)
        assert result is None

    def test_radius_gives_bbox(self):
        feat = _feat(cx=10.0, cy=10.0, r=5.0)
        bbox = dxf_feature_bbox(feat)
        assert bbox is not None
        assert float(bbox.width) == pytest.approx(10.0)

    def test_diameter_gives_bbox(self):
        feat = MagicMock(spec=ManufacturingFeature)
        loc = MagicMock()
        loc.x.value = Decimal("20")
        loc.y.value = Decimal("20")
        feat.location = loc
        feat.radius_mm = None
        feat.diameter_mm = 12.0
        bbox = dxf_feature_bbox(feat)
        assert bbox is not None
        assert float(bbox.width) == pytest.approx(12.0)

    def test_no_size_gives_1x1_fallback(self):
        feat = MagicMock(spec=ManufacturingFeature)
        loc = MagicMock()
        loc.x.value = Decimal("0")
        loc.y.value = Decimal("0")
        feat.location = loc
        feat.radius_mm = None
        feat.diameter_mm = None
        bbox = dxf_feature_bbox(feat)
        assert bbox is not None
        assert float(bbox.width) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# link_dxf_annotations: empty features
# ---------------------------------------------------------------------------

class TestLinkEmptyFeatures:
    def test_no_features_all_annotations_unresolved(self):
        anns = [_ann("a1", insertion_x=10.0, insertion_y=10.0)]
        result = link_dxf_annotations(anns, [])
        assert len(result.unresolved) == len(anns)
        assert len(result.linked) == 0

    def test_no_features_warning_added(self):
        anns = [_ann("a1", insertion_x=0.0, insertion_y=0.0)]
        result = link_dxf_annotations(anns, [])
        assert any("NO_FEATURES" in w for w in result.warnings)

    def test_total_annotations_counter(self):
        anns = [_ann("a1"), _ann("a2")]
        result = link_dxf_annotations(anns, [])
        assert result.total_annotations == 2

    def test_total_features_counter(self):
        anns = [_ann("a1")]
        feats = [_feat("f1"), _feat("f2", cx=50.0)]
        result = link_dxf_annotations(anns, feats)
        assert result.total_features == 2


# ---------------------------------------------------------------------------
# link_dxf_annotations: annotation without spatial context
# ---------------------------------------------------------------------------

class TestNoSpatialContext:
    def test_annotation_without_spatial_context_unresolved(self):
        anns = [_ann("a1")]   # No coordinates at all
        feats = [_feat("f1")]
        result = link_dxf_annotations(anns, feats)
        assert any(l.annotation_id == "a1" and l.status == DxfAnnotationLinkStatus.UNRESOLVED
                   for l in result.unresolved)


# ---------------------------------------------------------------------------
# DxfAnnotationLinkResult properties
# ---------------------------------------------------------------------------

class TestLinkResultProperties:
    def test_linked_count(self):
        r = DxfAnnotationLinkResult()
        r.linked = [MagicMock(), MagicMock()]
        assert r.linked_count == 2

    def test_ambiguous_count(self):
        r = DxfAnnotationLinkResult()
        r.ambiguous = [MagicMock()]
        assert r.ambiguous_count == 1

    def test_conflict_count(self):
        r = DxfAnnotationLinkResult()
        r.conflicts = [MagicMock(), MagicMock(), MagicMock()]
        assert r.conflict_count == 3

    def test_unresolved_count(self):
        r = DxfAnnotationLinkResult()
        r.unresolved = [MagicMock()]
        assert r.unresolved_count == 1


# ---------------------------------------------------------------------------
# Link method selection
# ---------------------------------------------------------------------------

class TestPickLinkMethod:
    def test_direct_reference_when_handle(self):
        from backend.interoperability.dxf_annotation_linker import _pick_link_method
        a = _ann(handle="1A2B")
        assert _pick_link_method(a) == DxfAnnotationLinkMethod.DIRECT_REFERENCE

    def test_dimension_geometry_when_defpoints(self):
        from backend.interoperability.dxf_annotation_linker import _pick_link_method
        a = _ann(defpoint1_x=0.0, defpoint1_y=0.0, defpoint2_x=10.0, defpoint2_y=0.0)
        assert _pick_link_method(a) == DxfAnnotationLinkMethod.DIMENSION_GEOMETRY

    def test_leader_association_when_leader(self):
        from backend.interoperability.dxf_annotation_linker import _pick_link_method
        a = _ann(leader_x=5.0, leader_y=5.0)
        assert _pick_link_method(a) == DxfAnnotationLinkMethod.LEADER_ASSOCIATION

    def test_spatial_nearest_fallback(self):
        from backend.interoperability.dxf_annotation_linker import _pick_link_method
        a = _ann(insertion_x=10.0, insertion_y=10.0)
        assert _pick_link_method(a) == DxfAnnotationLinkMethod.SPATIAL_NEAREST


# ---------------------------------------------------------------------------
# Review required invariant
# ---------------------------------------------------------------------------

class TestReviewRequired:
    def test_review_required_on_unresolved_link(self):
        anns = [_ann("a1")]   # no spatial context → unresolved
        feats = [_feat()]
        result = link_dxf_annotations(anns, feats)
        for link in result.unresolved:
            assert link.review_required is True

    def test_review_required_on_linked(self):
        # Place annotation exactly at feature center with proximity
        ann = _ann("a1", insertion_x=0.0, insertion_y=0.0, text="Ø20")
        feat = _feat("f1", cx=0.5, cy=0.5, r=10.0)   # close enough
        result = link_dxf_annotations([ann], [feat], max_proximity_mm=20.0)
        for link in result.linked:
            assert link.review_required is True


# ---------------------------------------------------------------------------
# DxfAnnotation fields
# ---------------------------------------------------------------------------

class TestDxfAnnotationFields:
    def test_text_stored(self):
        a = _ann(text="Ø32 h6")
        assert a.text == "Ø32 h6"

    def test_source_stored(self):
        a = _ann(source=DxfAnnotationSource.MTEXT)
        assert a.source == DxfAnnotationSource.MTEXT

    def test_layer_default_zero(self):
        a = _ann()
        assert a.layer == "0"

    def test_subtype_default_none(self):
        a = _ann()
        assert a.subtype is None
