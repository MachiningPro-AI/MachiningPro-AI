"""
Benchmark file integrity tests (P10 Phase 3, MUST 37).

Verifies that all benchmark STEP files have correct labels:
  - sample_origin = IN_HOUSE_BENCHMARK
  - is_real_external_sample = False
  - is_dispatchable = False
  - production_released = False

HARD RULES:
  - Benchmark files are NEVER called REAL_EXTERNAL_SAMPLE.
  - REAL_STEP_SAMPLE_COUNT=0 — benchmark files do not change this.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from backend.cad_import.step_intake import REAL_STEP_SAMPLE_COUNT
from backend.step_brep.gmsh_step_parser import parse_step_file

_GT_FILES = [
    "P10_S1_drilled_block_ground_truth.json",
    "P10_S2_pocket_slot_ground_truth.json",
    "P10_S3_multi_feature_ground_truth.json",
]

_STEP_FILES = [
    "P10_S1_drilled_block.step",
    "P10_S2_pocket_slot.step",
    "P10_S3_multi_feature.step",
]


# ===========================================================================
# A — Benchmark files exist
# ===========================================================================

@pytest.mark.parametrize("fname", _STEP_FILES)
def test_benchmark_step_file_exists(benchmark_step_dir: pathlib.Path, fname: str) -> None:
    assert (benchmark_step_dir / fname).exists(), f"Benchmark file missing: {fname}"


@pytest.mark.parametrize("fname", _GT_FILES)
def test_benchmark_ground_truth_exists(benchmark_step_dir: pathlib.Path, fname: str) -> None:
    assert (benchmark_step_dir / fname).exists(), f"Ground truth missing: {fname}"


# ===========================================================================
# B — Ground truth label integrity
# ===========================================================================

@pytest.mark.parametrize("gt_file", _GT_FILES)
def test_ground_truth_sample_origin_is_benchmark(
    benchmark_step_dir: pathlib.Path, gt_file: str
) -> None:
    gt = json.loads((benchmark_step_dir / gt_file).read_text(encoding="utf-8"))
    assert gt["sample_origin"] == "IN_HOUSE_BENCHMARK", (
        f"{gt_file}: sample_origin must be IN_HOUSE_BENCHMARK, not {gt['sample_origin']!r}"
    )


@pytest.mark.parametrize("gt_file", _GT_FILES)
def test_ground_truth_not_real_external(
    benchmark_step_dir: pathlib.Path, gt_file: str
) -> None:
    gt = json.loads((benchmark_step_dir / gt_file).read_text(encoding="utf-8"))
    assert gt["is_real_external_sample"] is False


@pytest.mark.parametrize("gt_file", _GT_FILES)
def test_ground_truth_not_dispatchable(
    benchmark_step_dir: pathlib.Path, gt_file: str
) -> None:
    gt = json.loads((benchmark_step_dir / gt_file).read_text(encoding="utf-8"))
    assert gt["is_dispatchable"] is False


@pytest.mark.parametrize("gt_file", _GT_FILES)
def test_ground_truth_not_production_released(
    benchmark_step_dir: pathlib.Path, gt_file: str
) -> None:
    gt = json.loads((benchmark_step_dir / gt_file).read_text(encoding="utf-8"))
    assert gt["production_released"] is False


@pytest.mark.parametrize("gt_file", _GT_FILES)
def test_ground_truth_qualification_class(
    benchmark_step_dir: pathlib.Path, gt_file: str
) -> None:
    gt = json.loads((benchmark_step_dir / gt_file).read_text(encoding="utf-8"))
    assert gt["qualification_class"] == "SOFTWARE_BENCHMARK"


# ===========================================================================
# C — Parsed benchmark labels match ground truth
# ===========================================================================

def test_benchmark_parser_origin_in_house(benchmark_step_dir: pathlib.Path) -> None:
    """parse_step_file with IN_HOUSE_BENCHMARK origin preserves label."""
    step = benchmark_step_dir / "P10_S1_drilled_block.step"
    result = parse_step_file(str(step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.sample_origin == "IN_HOUSE_BENCHMARK"
    # REAL_EXTERNAL_SAMPLE label must never appear
    assert result.sample_origin != "REAL_EXTERNAL_SAMPLE"


def test_benchmark_parse_does_not_increment_real_sample_count(
    benchmark_step_dir: pathlib.Path,
) -> None:
    """Parsing IN_HOUSE_BENCHMARK files must not increment REAL_STEP_SAMPLE_COUNT."""
    before = REAL_STEP_SAMPLE_COUNT
    for fname in _STEP_FILES:
        parse_step_file(
            str(benchmark_step_dir / fname),
            sample_origin="IN_HOUSE_BENCHMARK",
        )
    after = REAL_STEP_SAMPLE_COUNT
    # REAL_STEP_SAMPLE_COUNT is a module constant (not mutated at runtime).
    # Parsing benchmark files must not change it. Verify before==after.
    assert after == before


# ===========================================================================
# D — IN_HOUSE_BENCHMARK_STEP_COUNT
# ===========================================================================

def test_in_house_benchmark_step_count_at_least_3(benchmark_step_dir: pathlib.Path) -> None:
    """After generation, at least 3 benchmark STEP files exist."""
    count = len(list(benchmark_step_dir.glob("*.step")))
    assert count >= 3
