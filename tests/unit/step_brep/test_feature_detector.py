"""
Tests for hole candidate detection from STEP B-Rep (P10 Phase 3, MUST 36).

HARD RULES:
  - Hole candidates are CANDIDATE only — never CONFIRMED in Phase 3.
  - is_dispatchable=False always.
  - Diameter from real B-Rep geometry — not fabricated.
"""

from __future__ import annotations

import pathlib

import pytest

from backend.step_brep.feature_detector import (
    HoleCandidateRecord,
    detect_hole_candidates,
)
from backend.step_brep.gmsh_step_parser import StepImportRecord, parse_step_file


# ===========================================================================
# A — detect_hole_candidates on failed record
# ===========================================================================

def test_detect_holes_empty_on_failed_record() -> None:
    """detect_hole_candidates returns [] when status != PASS."""
    bad_record = StepImportRecord(
        status="FAILED",
        source_path="bad.stp",
        sha256=None,
        file_size_bytes=None,
        parser_backend="gmsh",
        sample_origin="UNKNOWN_EXTERNAL",
        body_count=0,
        volume_count=0,
        surface_count=0,
        edge_count=0,
        vertex_count=0,
        bbox_min=None,
        bbox_max=None,
    )
    result = detect_hole_candidates(bad_record)
    assert result == []


# ===========================================================================
# B — P10-S1: drilled block (2 through holes + 1 blind)
# ===========================================================================

@pytest.fixture(scope="module")
def p10_s1_record(p10_s1_step: pathlib.Path) -> StepImportRecord:
    return parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")


def test_p10_s1_hole_candidates_found(p10_s1_record: StepImportRecord) -> None:
    holes = detect_hole_candidates(p10_s1_record)
    assert len(holes) >= 1  # at least 1 hole candidate found


def test_p10_s1_all_holes_are_candidate(p10_s1_record: StepImportRecord) -> None:
    holes = detect_hole_candidates(p10_s1_record)
    for h in holes:
        assert h.feature_status == "CANDIDATE"


def test_p10_s1_all_holes_not_dispatchable(p10_s1_record: StepImportRecord) -> None:
    holes = detect_hole_candidates(p10_s1_record)
    for h in holes:
        assert h.is_dispatchable is False


def test_p10_s1_hole_diameters_reasonable(p10_s1_record: StepImportRecord) -> None:
    """All detected hole diameters are within the expected design range."""
    holes = detect_hole_candidates(p10_s1_record)
    for h in holes:
        # Design calls for Ø6, Ø8, Ø10 — allow some tolerance
        assert 4.0 <= h.diameter_mm <= 15.0, f"Unexpected diameter: {h.diameter_mm}"


def test_p10_s1_hole_has_axis_direction(p10_s1_record: StepImportRecord) -> None:
    holes = detect_hole_candidates(p10_s1_record)
    for h in holes:
        assert h.axis_direction in {"X", "Y", "Z"}


# ===========================================================================
# C — P10-S3: multi-feature (3 through holes)
# ===========================================================================

@pytest.fixture(scope="module")
def p10_s3_record(p10_s3_step: pathlib.Path) -> StepImportRecord:
    return parse_step_file(str(p10_s3_step), sample_origin="IN_HOUSE_BENCHMARK")


def test_p10_s3_hole_candidates_at_least_1(p10_s3_record: StepImportRecord) -> None:
    # P10-S3 has complex geometry; only cylindrical faces (not UNKNOWN) produce candidates.
    # Ground truth: 1 cylindrical classified → at least 1 hole candidate.
    holes = detect_hole_candidates(p10_s3_record)
    assert len(holes) >= 1  # at least 1 hole candidate from cylindrical faces


def test_p10_s3_hole_candidates_all_candidate_status(p10_s3_record: StepImportRecord) -> None:
    holes = detect_hole_candidates(p10_s3_record)
    for h in holes:
        assert h.feature_status == "CANDIDATE"


# ===========================================================================
# D — HoleCandidateRecord invariants
# ===========================================================================

def test_hole_candidate_record_is_dispatchable_false() -> None:
    record = HoleCandidateRecord(
        face_tag=7,
        feature_status="CANDIDATE",
        hole_class="THROUGH_HOLE_CANDIDATE",
        diameter_mm=10.0,
        axis_direction="Z",
        circular_boundary_count=2,
        bbox_min=(25.0, 15.0, -1.0),
        bbox_max=(35.0, 25.0, 21.0),
    )
    assert record.is_dispatchable is False


def test_hole_candidate_record_depth_from_bbox() -> None:
    record = HoleCandidateRecord(
        face_tag=7,
        feature_status="CANDIDATE",
        hole_class="THROUGH_HOLE_CANDIDATE",
        diameter_mm=10.0,
        axis_direction="Z",
        circular_boundary_count=2,
        bbox_min=(0.0, 0.0, 0.0),
        bbox_max=(10.0, 10.0, 20.0),
    )
    # Depth along Z axis = 20 mm
    assert record.depth_mm is not None
    assert abs(record.depth_mm - 20.0) < 0.1
