"""
P10-G tests: Stock / simulation production workflow.

Covers:
  - count_rapid_feed_segments: RAPID_LINEAR/FEED_LINEAR/HELIX counts
  - SIMULATION_METHOD=VOXEL_APPROXIMATION constant
  - ProductionSimulationResult safety invariants (is_dispatchable=False, production_released=False)
  - run_production_simulation: no candidate → simulation_ran=False
  - run_production_simulation: segments + stock → simulation_ran=True
  - Separate result fields: stock_removal_validated, gouge_validated, collision_scope_validated
  - gouge=NOT_VERIFIABLE when no STEP (always current state)
  - RAPID_SEGMENTS_CHECKED=YES, FEED_SEGMENTS_CHECKED=YES
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.manufacturing.production_simulation import (
    SIMULATION_METHOD,
    ProductionSimulationInput,
    ProductionSimulationResult,
    count_rapid_feed_segments,
    run_production_simulation,
)
from backend.manufacturing.verification_adapter import GeometryFieldProvenance


# ---------------------------------------------------------------------------
# SIMULATION_METHOD constant
# ---------------------------------------------------------------------------


def test_simulation_method_is_voxel_approximation() -> None:
    assert SIMULATION_METHOD == "VOXEL_APPROXIMATION"


# ---------------------------------------------------------------------------
# count_rapid_feed_segments
# ---------------------------------------------------------------------------


def test_count_rapid_only() -> None:
    segs = [{"motion_type": "RAPID_LINEAR"}] * 3
    r, f = count_rapid_feed_segments(segs)
    assert r == 3
    assert f == 0


def test_count_feed_only() -> None:
    segs = [{"motion_type": "FEED_LINEAR"}, {"motion_type": "HELIX"}]
    r, f = count_rapid_feed_segments(segs)
    assert r == 0
    assert f == 2


def test_count_mixed_segments() -> None:
    segs = [
        {"motion_type": "RAPID_LINEAR"},
        {"motion_type": "FEED_LINEAR"},
        {"motion_type": "HELIX"},
        {"motion_type": "RAPID_LINEAR"},
    ]
    r, f = count_rapid_feed_segments(segs)
    assert r == 2
    assert f == 2


def test_count_unknown_motion_type_counts_as_feed() -> None:
    segs = [{"motion_type": "UNKNOWN_TYPE"}]
    r, f = count_rapid_feed_segments(segs)
    assert r == 0
    assert f == 1


def test_count_empty_segments() -> None:
    r, f = count_rapid_feed_segments([])
    assert r == 0
    assert f == 0


def test_count_missing_motion_type_defaults_to_feed() -> None:
    segs = [{}]
    r, f = count_rapid_feed_segments(segs)
    assert r == 0
    assert f == 1


# ---------------------------------------------------------------------------
# ProductionSimulationResult safety invariants
# ---------------------------------------------------------------------------


def test_simulation_result_safety_invariants() -> None:
    result = ProductionSimulationResult(candidate_id="cand-001")
    assert result.is_dispatchable is False
    assert result.production_released is False


def test_simulation_result_method_always_voxel() -> None:
    result = ProductionSimulationResult(candidate_id="cand-001")
    assert result.simulation_method == "VOXEL_APPROXIMATION"


def test_simulation_result_cannot_set_dispatchable() -> None:
    result = ProductionSimulationResult(candidate_id="cand-001")
    object.__setattr__(result, "is_dispatchable", True)
    result.__post_init__()
    assert result.is_dispatchable is False


# ---------------------------------------------------------------------------
# run_production_simulation: no segments → simulation_ran=False
# ---------------------------------------------------------------------------


def _make_candidate_no_segs() -> SimpleNamespace:
    return SimpleNamespace(
        feature_id="feat-no-segs",
        candidate_id="cand-no-segs",
        toolpath_id=None,
        nc_segments=[],
    )


def _make_candidate_with_segs() -> SimpleNamespace:
    return SimpleNamespace(
        feature_id="feat-001",
        candidate_id="cand-001",
        toolpath_id=None,
        nc_segments=[
            {
                "start_x": 0.0, "start_y": 0.0, "start_z": 10.0,
                "end_x": 0.0, "end_y": 0.0, "end_z": 2.0,
                "motion_type": "RAPID_LINEAR",
                "is_cutting": False,
                "segment_id": "s1",
            },
            {
                "start_x": 0.0, "start_y": 0.0, "start_z": 2.0,
                "end_x": 0.0, "end_y": 0.0, "end_z": -5.0,
                "motion_type": "FEED_LINEAR",
                "is_cutting": True,
                "segment_id": "s2",
            },
        ],
    )


def test_run_no_segments_simulation_not_ran() -> None:
    sim_input = ProductionSimulationInput(candidate=_make_candidate_no_segs())
    result = run_production_simulation(sim_input)
    assert result.simulation_ran is False
    assert result.is_dispatchable is False
    assert result.production_released is False


def test_run_no_segments_safety_invariants() -> None:
    sim_input = ProductionSimulationInput(candidate=_make_candidate_no_segs())
    result = run_production_simulation(sim_input)
    assert result.is_dispatchable is False
    assert result.production_released is False
    assert result.simulation_method == "VOXEL_APPROXIMATION"


# ---------------------------------------------------------------------------
# run_production_simulation: with segments
# ---------------------------------------------------------------------------


def _make_stock_def() -> SimpleNamespace:
    return SimpleNamespace(
        stock_id="stock-001",
        shape="RECTANGULAR_BLOCK",
        material_grade="1.0038",
        length_mm=100.0,
        width_mm=80.0,
        height_mm=30.0,
        outer_diameter_mm=None,
        inner_diameter_mm=None,
        stock_notes="",
        confirmed_by="test",
        created_at="2026-11-17",
    )


def test_run_with_segments_separate_results() -> None:
    candidate = _make_candidate_with_segs()
    stock_def = _make_stock_def()
    sim_input = ProductionSimulationInput(
        candidate=candidate,
        stock_def=stock_def,
    )
    result = run_production_simulation(sim_input)
    # Separate result fields exist
    assert hasattr(result, "stock_removal_validated")
    assert hasattr(result, "gouge_validated")
    assert hasattr(result, "collision_scope_validated")
    # Safety invariants always
    assert result.is_dispatchable is False
    assert result.production_released is False


def test_run_gouge_always_not_verifiable_without_step() -> None:
    candidate = _make_candidate_with_segs()
    sim_input = ProductionSimulationInput(candidate=candidate)
    result = run_production_simulation(sim_input)
    assert result.gouge_validated == "NOT_VERIFIABLE"
    # Warning about STEP required
    assert any("GOUGE" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# RAPID_SEGMENTS_CHECKED and FEED_SEGMENTS_CHECKED
# ---------------------------------------------------------------------------


def test_rapid_feed_segments_checked_when_segs_present() -> None:
    candidate = _make_candidate_with_segs()
    sim_input = ProductionSimulationInput(candidate=candidate)
    result = run_production_simulation(sim_input)
    assert result.rapid_segment_count == 1
    assert result.feed_segment_count == 1
    assert result.rapid_segments_checked is True
    assert result.feed_segments_checked is True


def test_rapid_feed_segments_not_checked_when_empty() -> None:
    candidate = _make_candidate_no_segs()
    sim_input = ProductionSimulationInput(candidate=candidate)
    result = run_production_simulation(sim_input)
    assert result.rapid_segment_count == 0
    assert result.feed_segment_count == 0
    assert result.rapid_segments_checked is False
    assert result.feed_segments_checked is False


# ---------------------------------------------------------------------------
# Collision scope: NOT_VERIFIABLE when no fixtures/holder
# ---------------------------------------------------------------------------


def test_collision_scope_not_verifiable_without_fixtures() -> None:
    candidate = _make_candidate_with_segs()
    sim_input = ProductionSimulationInput(candidate=candidate, fixture_inputs=[])
    result = run_production_simulation(sim_input)
    assert result.collision_scope_validated in {"NOT_VERIFIABLE", "PARTIAL"}


# ---------------------------------------------------------------------------
# SIMULATION_METHOD_CONFIRMED in warnings
# ---------------------------------------------------------------------------


def test_simulation_method_confirmed_in_warnings() -> None:
    candidate = _make_candidate_with_segs()
    sim_input = ProductionSimulationInput(candidate=candidate)
    result = run_production_simulation(sim_input)
    assert any("VOXEL_APPROXIMATION" in w for w in result.warnings)
