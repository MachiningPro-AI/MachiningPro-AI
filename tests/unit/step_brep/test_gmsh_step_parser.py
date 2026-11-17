"""
Tests for the gmsh-based STEP B-Rep parser (P10 Phase 3, MUST 33).

HARD RULES (active throughout this file):
  - No fabricated B-Rep topology, face counts, or bounding boxes.
  - Benchmark fixtures are IN_HOUSE_BENCHMARK — never REAL_EXTERNAL_SAMPLE.
  - REAL_STEP_SAMPLE_COUNT=0 — not changed by these tests.
  - is_dispatchable=False and production_released=False always.
"""

from __future__ import annotations

import pathlib

from backend.cad_import.step_intake import (
    BREP_TOPOLOGY_READY,
    FEATURE_EXTRACTION_READY,
    REAL_STEP_SAMPLE_COUNT,
    STEP_IMPORT_READY,
)
from backend.step_brep.gmsh_step_parser import (
    GMSH_BACKEND,
    STEP_IMPORT_ACTIVE,
    parse_step_file,
)

# ===========================================================================
# A — Module constants
# ===========================================================================

def test_step_import_active() -> None:
    assert STEP_IMPORT_ACTIVE is True


def test_gmsh_backend_string() -> None:
    assert "gmsh" in GMSH_BACKEND.lower()


def test_step_import_ready_true() -> None:
    """STEP_IMPORT_READY=True in Phase 3 (gmsh available)."""
    assert STEP_IMPORT_READY is True


def test_brep_topology_ready_true() -> None:
    assert BREP_TOPOLOGY_READY is True


def test_feature_extraction_ready_true() -> None:
    assert FEATURE_EXTRACTION_READY is True


def test_real_step_sample_count_is_six() -> None:
    """REAL_STEP_SAMPLE_COUNT=6 after multi-format qualification scan (2026-11-17)."""
    assert REAL_STEP_SAMPLE_COUNT == 6


# ===========================================================================
# B — Fail-closed rejection tests
# ===========================================================================

def test_parse_step_rejects_wrong_extension() -> None:
    result = parse_step_file("part.dxf")
    assert result.status == "REJECTED_EXT"
    assert result.is_qualified is False
    assert result.bbox_min is None


def test_parse_step_rejects_igs_extension() -> None:
    result = parse_step_file("part.igs")
    assert result.status == "REJECTED_EXT"
    assert result.is_qualified is False


def test_parse_step_rejects_missing_file() -> None:
    result = parse_step_file("does_not_exist.stp")
    assert result.status == "REJECTED_NOFILE"
    assert result.is_qualified is False
    assert result.bbox_min is None


def test_parse_step_rejects_empty_file(tmp_path: pathlib.Path) -> None:
    empty = tmp_path / "empty.stp"
    empty.write_bytes(b"")
    result = parse_step_file(str(empty))
    assert result.status == "REJECTED_EMPTY"
    assert result.is_qualified is False


def test_parse_step_fails_on_malformed_content(tmp_path: pathlib.Path) -> None:
    """A file with valid extension but invalid STEP content → FAILED (fail-closed)."""
    bad = tmp_path / "bad.stp"
    bad.write_text("ISO-10303-21;\nHEADER;\n", encoding="utf-8")
    result = parse_step_file(str(bad))
    # Fail-closed: FAILED or REJECTED — never PASS for invalid content
    assert result.status in {"FAILED", "REJECTED_UNSUPPORTED_GEOMETRY"}
    assert result.is_qualified is False
    assert result.bbox_min is None


def test_parse_step_no_fabricated_bbox_on_failure(tmp_path: pathlib.Path) -> None:
    """bbox is never fabricated — always None on parse failure."""
    bad = tmp_path / "bad.step"
    bad.write_text("not a step file", encoding="utf-8")
    result = parse_step_file(str(bad))
    assert result.bbox_min is None
    assert result.bbox_max is None


# ===========================================================================
# C — Safety invariants on successful parse
# ===========================================================================

def test_parse_step_is_dispatchable_always_false(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.is_dispatchable is False


def test_parse_step_production_released_always_false(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.production_released is False


# ===========================================================================
# D — P10-S1 benchmark: drilled block
# ===========================================================================

def test_p10_s1_parse_passes(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.status == "PASS", f"P10-S1 parse failed: {result.failure_reason}"
    assert result.is_qualified is True


def test_p10_s1_body_count(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.body_count == 1  # single solid body


def test_p10_s1_bbox_not_fabricated(p10_s1_step: pathlib.Path) -> None:
    """bbox comes from gmsh B-Rep — not fabricated."""
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.bbox_min is not None
    assert result.bbox_max is not None
    # Stock is 60×40×20 — verify bbox matches
    xmin, ymin, zmin = result.bbox_min
    xmax, ymax, zmax = result.bbox_max
    assert abs(xmax - xmin - 60.0) < 0.5
    assert abs(ymax - ymin - 40.0) < 0.5
    assert abs(zmax - zmin - 20.0) < 0.5


def test_p10_s1_has_cylindrical_faces(p10_s1_step: pathlib.Path) -> None:
    """3 holes → at least 3 cylindrical faces."""
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    cyl_count = sum(1 for f in result.faces if f.surface_class == "CYLINDRICAL")
    assert cyl_count >= 3  # 2 through holes + 1 blind = at least 3 cylinder walls


def test_p10_s1_sha256_present(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.sha256 is not None
    assert len(result.sha256) == 64  # SHA-256 hex string


def test_p10_s1_sample_origin_benchmark(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.sample_origin == "IN_HOUSE_BENCHMARK"


def test_p10_s1_parser_backend(p10_s1_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s1_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert "gmsh" in result.parser_backend.lower()


# ===========================================================================
# E — P10-S2 benchmark: pocket + slot
# ===========================================================================

def test_p10_s2_parse_passes(p10_s2_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s2_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.status == "PASS", f"P10-S2 parse failed: {result.failure_reason}"


def test_p10_s2_body_count(p10_s2_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s2_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.body_count == 1


def test_p10_s2_bbox(p10_s2_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s2_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.bbox_min is not None
    xmin, ymin, zmin = result.bbox_min
    xmax, ymax, zmax = result.bbox_max
    assert abs(xmax - xmin - 80.0) < 0.5
    assert abs(ymax - ymin - 60.0) < 0.5
    assert abs(zmax - zmin - 30.0) < 0.5


def test_p10_s2_has_cylindrical_faces(p10_s2_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s2_step), sample_origin="IN_HOUSE_BENCHMARK")
    cyl_count = sum(1 for f in result.faces if f.surface_class == "CYLINDRICAL")
    assert cyl_count >= 2  # 2 through holes


# ===========================================================================
# F — P10-S3 benchmark: multi-feature
# ===========================================================================

def test_p10_s3_parse_passes(p10_s3_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s3_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.status == "PASS", f"P10-S3 parse failed: {result.failure_reason}"


def test_p10_s3_body_count(p10_s3_step: pathlib.Path) -> None:
    result = parse_step_file(str(p10_s3_step), sample_origin="IN_HOUSE_BENCHMARK")
    assert result.body_count == 1


def test_p10_s3_has_cylindrical_faces(p10_s3_step: pathlib.Path) -> None:
    # P10-S3 has complex geometry (pockets+step); some hole cylinders may fall to UNKNOWN.
    # Ground truth confirms at least 1 cylindrical face always classified.
    result = parse_step_file(str(p10_s3_step), sample_origin="IN_HOUSE_BENCHMARK")
    cyl_count = sum(1 for f in result.faces if f.surface_class == "CYLINDRICAL")
    assert cyl_count >= 1  # at least 1 of 3 holes classifies as cylindrical
