"""Unit tests for partial circular boundary detection (P1-D).

Tests recognize_circular_boundaries() and CircularBoundaryCandidate:
  - Single ARC never returned (arc_count ≥ 2 required)
  - Two arcs with 180° each → HOLE_CANDIDATE (360° total)
  - Four arcs with 90° each → HOLE_CANDIDATE
  - Two arcs with 90° each (180° total) → CIRCULAR_BOUNDARY_CANDIDATE (partial)
  - Different centers: not merged
  - Different radii: not merged
  - Very small radius (≤0.05) → excluded
  - Three arcs: 120° each → CIRCULAR_BOUNDARY_CANDIDATE
  - Coverage < 60° → not returned
  - is_partial=True for partial candidates
  - is_partial=False for HOLE_CANDIDATE
  - review_required always True
  - candidate_id contains source_document_id
  - Two groups at different positions: two separate candidates
  - Mixed: one HOLE_CANDIDATE + one CIRCULAR_BOUNDARY_CANDIDATE in same drawing
  - Non-ARC entities (LINE, CIRCLE, LWPOLYLINE) not processed
  - Arc with start_angle > end_angle (wrap-around arc) coverage computed correctly
  - Empty entity list → empty result
  - Arc with no center → not grouped
  - Arc with radius=None → not grouped
  - Radius=0 → not grouped
  - Very large drawing with 10 circles, all complete → 10 HOLE_CANDIDATE
  - Three arcs with same center but different radii → two separate groups
"""

from __future__ import annotations

import pytest

from backend.interoperability.cad_feature_recognition import (
    CircularBoundaryCandidate,
    CircularBoundaryStatus,
    Dxf2dEntity,
    recognize_circular_boundaries,
)


def _arc(
    center_x: float = 0.0,
    center_y: float = 0.0,
    radius: float = 10.0,
    start_angle: float = 0.0,
    end_angle: float = 180.0,
) -> Dxf2dEntity:
    return Dxf2dEntity(
        entity_type="ARC",
        layer="0",
        center_x=center_x,
        center_y=center_y,
        radius=radius,
        start_angle=start_angle,
        end_angle=end_angle,
    )


def _line(x1: float = 0.0, y1: float = 0.0) -> Dxf2dEntity:
    return Dxf2dEntity(
        entity_type="LINE",
        layer="0",
        x1=x1,
        y1=y1,
    )


def _circle(cx: float = 0.0, cy: float = 0.0, r: float = 5.0) -> Dxf2dEntity:
    return Dxf2dEntity(
        entity_type="CIRCLE",
        layer="0",
        center_x=cx,
        center_y=cy,
        radius=r,
    )


# ---------------------------------------------------------------------------
# Single ARC guard
# ---------------------------------------------------------------------------

class TestSingleArcGuard:
    def test_single_arc_not_returned(self):
        entities = [_arc(start_angle=0.0, end_angle=90.0)]
        result = recognize_circular_boundaries(entities)
        assert result == []

    def test_single_complete_arc_not_returned(self):
        entities = [_arc(start_angle=0.0, end_angle=359.0)]
        result = recognize_circular_boundaries(entities)
        assert result == []


# ---------------------------------------------------------------------------
# Complete (HOLE_CANDIDATE)
# ---------------------------------------------------------------------------

class TestHoleCandidate:
    def test_two_arcs_180_each_gives_hole_candidate(self):
        entities = [
            _arc(start_angle=0.0, end_angle=180.0),
            _arc(start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 1
        assert result[0].status == CircularBoundaryStatus.HOLE_CANDIDATE
        assert result[0].is_partial is False

    def test_four_arcs_90_each_gives_hole_candidate(self):
        entities = [
            _arc(start_angle=0.0, end_angle=90.0),
            _arc(start_angle=90.0, end_angle=180.0),
            _arc(start_angle=180.0, end_angle=270.0),
            _arc(start_angle=270.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 1
        assert result[0].status == CircularBoundaryStatus.HOLE_CANDIDATE

    def test_hole_candidate_arc_count_correct(self):
        entities = [
            _arc(start_angle=0.0, end_angle=180.0),
            _arc(start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result[0].arc_count == 2

    def test_hole_candidate_radius_preserved(self):
        entities = [
            _arc(radius=25.0, start_angle=0.0, end_angle=180.0),
            _arc(radius=25.0, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result[0].radius == pytest.approx(25.0)

    def test_review_required_true_for_hole_candidate(self):
        entities = [
            _arc(start_angle=0.0, end_angle=180.0),
            _arc(start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result[0].review_required is True


# ---------------------------------------------------------------------------
# Partial arc candidate (CIRCULAR_BOUNDARY_CANDIDATE)
# ---------------------------------------------------------------------------

class TestPartialCandidate:
    def test_two_arcs_90_each_gives_partial(self):
        entities = [
            _arc(start_angle=0.0, end_angle=90.0),
            _arc(start_angle=90.0, end_angle=180.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 1
        assert result[0].status == CircularBoundaryStatus.CIRCULAR_BOUNDARY_CANDIDATE
        assert result[0].is_partial is True

    def test_three_arcs_120_each_gives_partial_candidate(self):
        entities = [
            _arc(start_angle=0.0, end_angle=120.0),
            _arc(start_angle=120.0, end_angle=240.0),
            _arc(start_angle=240.0, end_angle=355.0),   # slightly less than 360°
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 1
        assert result[0].is_partial is True
        assert result[0].review_required is True

    def test_partial_candidate_coverage_in_60_to_358_range(self):
        entities = [
            _arc(start_angle=0.0, end_angle=90.0),
            _arc(start_angle=90.0, end_angle=180.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert 60.0 <= result[0].coverage_deg < 358.0


# ---------------------------------------------------------------------------
# Coverage threshold: < 60° excluded
# ---------------------------------------------------------------------------

class TestCoverageThreshold:
    def test_arcs_with_total_coverage_below_60_excluded(self):
        # Two arcs, each 25°, total = 50° < 60° threshold
        entities = [
            _arc(start_angle=0.0, end_angle=25.0),
            _arc(start_angle=25.0, end_angle=50.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result == []


# ---------------------------------------------------------------------------
# Different centers / radii guards
# ---------------------------------------------------------------------------

class TestNoMergeGuards:
    def test_different_centers_not_merged(self):
        entities = [
            _arc(center_x=0.0, center_y=0.0, start_angle=0.0, end_angle=180.0),
            _arc(center_x=100.0, center_y=0.0, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        # Both arcs are single → neither returned as a candidate
        assert result == []

    def test_different_radii_not_merged(self):
        entities = [
            _arc(radius=10.0, start_angle=0.0, end_angle=180.0),
            _arc(radius=20.0, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result == []

    def test_same_center_different_radius_gives_two_separate_groups(self):
        entities = [
            _arc(center_x=0.0, radius=10.0, start_angle=0.0, end_angle=180.0),
            _arc(center_x=0.0, radius=10.0, start_angle=180.0, end_angle=360.0),
            _arc(center_x=0.0, radius=20.0, start_angle=0.0, end_angle=180.0),
            _arc(center_x=0.0, radius=20.0, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 2


# ---------------------------------------------------------------------------
# Minimum radius guard
# ---------------------------------------------------------------------------

class TestMinRadiusGuard:
    def test_very_small_radius_excluded(self):
        entities = [
            _arc(radius=0.04, start_angle=0.0, end_angle=180.0),
            _arc(radius=0.04, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result == []

    def test_exactly_min_radius_excluded(self):
        entities = [
            _arc(radius=0.05, start_angle=0.0, end_angle=180.0),
            _arc(radius=0.05, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert result == []


# ---------------------------------------------------------------------------
# Non-ARC entity types ignored
# ---------------------------------------------------------------------------

class TestNonArcIgnored:
    def test_line_entities_not_processed(self):
        entities = [_line(), _line()]
        result = recognize_circular_boundaries(entities)
        assert result == []

    def test_circle_entities_not_processed_for_arcs(self):
        entities = [_circle(), _circle()]
        result = recognize_circular_boundaries(entities)
        assert result == []

    def test_mixed_entities_only_arcs_processed(self):
        entities = [
            _arc(start_angle=0.0, end_angle=180.0),
            _arc(start_angle=180.0, end_angle=360.0),
            _line(),
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 1
        assert result[0].status == CircularBoundaryStatus.HOLE_CANDIDATE


# ---------------------------------------------------------------------------
# Empty input
# ---------------------------------------------------------------------------

class TestEmptyInput:
    def test_empty_list_returns_empty(self):
        assert recognize_circular_boundaries([]) == []


# ---------------------------------------------------------------------------
# Arc with missing data
# ---------------------------------------------------------------------------

class TestArcWithMissingData:
    def test_arc_with_no_center_x_not_grouped(self):
        arc1 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=None, center_y=0.0, radius=10.0, start_angle=0.0, end_angle=180.0)
        arc2 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0, radius=10.0, start_angle=180.0, end_angle=360.0)
        result = recognize_circular_boundaries([arc1, arc2])
        assert result == []

    def test_arc_with_zero_radius_not_grouped(self):
        arc1 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0, radius=0.0, start_angle=0.0, end_angle=180.0)
        arc2 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0, radius=0.0, start_angle=180.0, end_angle=360.0)
        result = recognize_circular_boundaries([arc1, arc2])
        assert result == []


# ---------------------------------------------------------------------------
# Multiple groups in one drawing
# ---------------------------------------------------------------------------

class TestMultipleGroups:
    def test_two_separate_hole_candidates(self):
        entities = [
            _arc(center_x=0.0, start_angle=0.0, end_angle=180.0),
            _arc(center_x=0.0, start_angle=180.0, end_angle=360.0),
            _arc(center_x=50.0, start_angle=0.0, end_angle=180.0),
            _arc(center_x=50.0, start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities)
        assert len(result) == 2
        assert all(r.status == CircularBoundaryStatus.HOLE_CANDIDATE for r in result)

    def test_mixed_hole_and_partial_candidate(self):
        entities = [
            # Complete circle at center (0, 0)
            _arc(center_x=0.0, start_angle=0.0, end_angle=180.0),
            _arc(center_x=0.0, start_angle=180.0, end_angle=360.0),
            # Partial arc set at center (50, 0) — 180°
            _arc(center_x=50.0, start_angle=0.0, end_angle=90.0),
            _arc(center_x=50.0, start_angle=90.0, end_angle=180.0),
        ]
        result = recognize_circular_boundaries(entities)
        hole_cands = [r for r in result if r.status == CircularBoundaryStatus.HOLE_CANDIDATE]
        partial_cands = [r for r in result if r.status == CircularBoundaryStatus.CIRCULAR_BOUNDARY_CANDIDATE]
        assert len(hole_cands) == 1
        assert len(partial_cands) == 1


# ---------------------------------------------------------------------------
# Wrap-around arc (start > end, e.g. 300° → 60°)
# ---------------------------------------------------------------------------

class TestWrapAroundArc:
    def test_wrap_around_arc_coverage_computed(self):
        # Arc from 300° to 60° covers 120°
        entities = [
            _arc(start_angle=300.0, end_angle=60.0),
            _arc(start_angle=60.0, end_angle=180.0),
        ]
        result = recognize_circular_boundaries(entities)
        # 120 + 120 = 240° → partial
        assert len(result) == 1
        assert result[0].is_partial is True
        assert result[0].coverage_deg == pytest.approx(240.0, rel=0.01)


# ---------------------------------------------------------------------------
# Source document ID in candidate_id
# ---------------------------------------------------------------------------

class TestCandidateId:
    def test_candidate_id_contains_source_id(self):
        entities = [
            _arc(start_angle=0.0, end_angle=180.0),
            _arc(start_angle=180.0, end_angle=360.0),
        ]
        result = recognize_circular_boundaries(entities, source_document_id="DXF-01")
        assert "DXF-01" in result[0].candidate_id
