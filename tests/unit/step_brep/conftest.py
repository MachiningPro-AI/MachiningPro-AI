"""
Session-scoped fixture: generate P10 benchmark STEP files if they don't exist.

Benchmark files are IN_HOUSE_BENCHMARK — not real external samples.
REAL_STEP_SAMPLE_COUNT remains 0 after this fixture runs.
"""

from __future__ import annotations

import pathlib

import pytest

from backend.step_brep.benchmark_generator import (
    IN_HOUSE_BENCHMARK_STEP_DIR,
    generate_all_benchmarks,
)

_STEP_DIR = IN_HOUSE_BENCHMARK_STEP_DIR


@pytest.fixture(scope="session")
def benchmark_step_dir() -> pathlib.Path:
    """Ensure benchmark STEP files exist; generate if missing."""
    s1 = _STEP_DIR / "P10_S1_drilled_block.step"
    s2 = _STEP_DIR / "P10_S2_pocket_slot.step"
    s3 = _STEP_DIR / "P10_S3_multi_feature.step"

    if not (s1.exists() and s2.exists() and s3.exists()):
        generate_all_benchmarks()

    return _STEP_DIR


@pytest.fixture(scope="session")
def p10_s1_step(benchmark_step_dir: pathlib.Path) -> pathlib.Path:
    return benchmark_step_dir / "P10_S1_drilled_block.step"


@pytest.fixture(scope="session")
def p10_s2_step(benchmark_step_dir: pathlib.Path) -> pathlib.Path:
    return benchmark_step_dir / "P10_S2_pocket_slot.step"


@pytest.fixture(scope="session")
def p10_s3_step(benchmark_step_dir: pathlib.Path) -> pathlib.Path:
    return benchmark_step_dir / "P10_S3_multi_feature.step"
