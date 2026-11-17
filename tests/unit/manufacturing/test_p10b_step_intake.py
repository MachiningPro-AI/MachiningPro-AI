"""
P10-B tests: STEP/B-Rep qualification intake.

Covers:
  - REAL_STEP_SAMPLE_COUNT=0 (always, cadquery not installed)
  - STEP_IMPORT_READY=False, BREP_TOPOLOGY_READY=False, FEATURE_EXTRACTION_READY=False
  - accept_step_file: extension check, missing file, empty file, deferred no parser
  - scan_step_samples: empty directory → empty result
  - scan_step_samples: directory doesn't exist → empty result
  - _3d_pipeline_readiness: all stages NOT_IMPLEMENTED or PARTIAL
  - 10 required sample classes (MUST 22 — via STEP_CAM_VERIFICATION doc)
"""

from __future__ import annotations

import os
import tempfile

import pytest

from backend.cad_import.step_intake import (
    BREP_TOPOLOGY_READY,
    FEATURE_EXTRACTION_READY,
    REAL_STEP_SAMPLE_COUNT,
    STEP_IMPORT_READY,
    StepIntakeRequest,
    StepIntakeStatus,
    _3d_pipeline_readiness,
    accept_step_file,
    scan_step_samples,
)


# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------


def test_real_step_sample_count_zero() -> None:
    assert REAL_STEP_SAMPLE_COUNT == 0


def test_step_import_ready_false() -> None:
    assert STEP_IMPORT_READY is False


def test_brep_topology_ready_false() -> None:
    assert BREP_TOPOLOGY_READY is False


def test_feature_extraction_ready_false() -> None:
    assert FEATURE_EXTRACTION_READY is False


# ---------------------------------------------------------------------------
# accept_step_file — extension check
# ---------------------------------------------------------------------------


def test_accept_wrong_extension() -> None:
    result = accept_step_file(StepIntakeRequest(file_path="part.dxf"))
    assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION
    assert result.is_qualified is False


def test_accept_wrong_extension_pdf() -> None:
    result = accept_step_file(StepIntakeRequest(file_path="part.pdf"))
    assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION


def test_accept_step_extension_valid() -> None:
    # .step extension is valid — should proceed past extension check
    result = accept_step_file(StepIntakeRequest(file_path="/nonexistent/part.step"))
    # Should NOT return REJECTED_WRONG_EXTENSION
    assert result.status != StepIntakeStatus.REJECTED_WRONG_EXTENSION


def test_accept_stp_extension_valid() -> None:
    result = accept_step_file(StepIntakeRequest(file_path="/nonexistent/part.stp"))
    assert result.status != StepIntakeStatus.REJECTED_WRONG_EXTENSION


def test_accept_p21_extension_valid() -> None:
    result = accept_step_file(StepIntakeRequest(file_path="/nonexistent/part.p21"))
    assert result.status != StepIntakeStatus.REJECTED_WRONG_EXTENSION


# ---------------------------------------------------------------------------
# accept_step_file — file not found
# ---------------------------------------------------------------------------


def test_accept_file_not_found() -> None:
    result = accept_step_file(
        StepIntakeRequest(file_path="/nonexistent/path/part.step")
    )
    assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND
    assert result.is_qualified is False


# ---------------------------------------------------------------------------
# accept_step_file — empty file
# ---------------------------------------------------------------------------


def test_accept_empty_file() -> None:
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
        empty_path = f.name
    try:
        result = accept_step_file(StepIntakeRequest(file_path=empty_path))
        assert result.status == StepIntakeStatus.REJECTED_EMPTY_FILE
        assert result.is_qualified is False
    finally:
        os.unlink(empty_path)


# ---------------------------------------------------------------------------
# accept_step_file — deferred (cadquery not installed)
# ---------------------------------------------------------------------------


def test_accept_valid_step_deferred_no_parser() -> None:
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
        f.write(b"ISO-10303-21;\nHEADER;ENDSEC;\nDATA;ENDSEC;\nEND-ISO-10303-21;\n")
        step_path = f.name
    try:
        result = accept_step_file(StepIntakeRequest(file_path=step_path))
        assert result.status == StepIntakeStatus.DEFERRED_NO_PARSER
        assert result.is_qualified is False
        assert result.part_bbox_min is None
        assert result.part_bbox_max is None
        assert result.provenance == "UNKNOWN"
    finally:
        os.unlink(step_path)


def test_accept_step_no_fabricated_bbox() -> None:
    """part_bbox must never be fabricated from non-STEP sources."""
    with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
        f.write(b"ISO-10303-21;\nHEADER;ENDSEC;\nDATA;ENDSEC;\nEND-ISO-10303-21;\n")
        step_path = f.name
    try:
        result = accept_step_file(StepIntakeRequest(file_path=step_path))
        assert result.part_bbox_min is None, (
            "part_bbox_min must be None when cadquery not installed (no fabrication)"
        )
        assert result.part_bbox_max is None, (
            "part_bbox_max must be None when cadquery not installed (no fabrication)"
        )
    finally:
        os.unlink(step_path)


# ---------------------------------------------------------------------------
# accept_step_file — file too large
# ---------------------------------------------------------------------------


def test_accept_file_too_large() -> None:
    with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
        f.write(b"x" * 1024)
        step_path = f.name
    try:
        result = accept_step_file(
            StepIntakeRequest(file_path=step_path, max_file_size_bytes=512)
        )
        assert result.status == StepIntakeStatus.REJECTED_FILE_TOO_LARGE
    finally:
        os.unlink(step_path)


# ---------------------------------------------------------------------------
# scan_step_samples — missing directory
# ---------------------------------------------------------------------------


def test_scan_missing_directory() -> None:
    results = scan_step_samples("/nonexistent/example_files")
    assert results == []


def test_scan_empty_directory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        results = scan_step_samples(tmpdir)
        assert results == []


def test_scan_no_step_files_in_directory() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create non-STEP files
        for name in ("part.dxf", "drawing.pdf", "readme.txt"):
            open(os.path.join(tmpdir, name), "w").close()
        results = scan_step_samples(tmpdir)
        assert results == []


def test_scan_step_files_returned() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        step_path = os.path.join(tmpdir, "part.step")
        with open(step_path, "wb") as f:
            f.write(b"ISO-10303-21;\nHEADER;ENDSEC;\nDATA;ENDSEC;\nEND-ISO-10303-21;\n")
        results = scan_step_samples(tmpdir)
        assert len(results) == 1
        assert results[0].status == StepIntakeStatus.DEFERRED_NO_PARSER


# ---------------------------------------------------------------------------
# _3d_pipeline_readiness
# ---------------------------------------------------------------------------


def test_3d_pipeline_readiness_structure() -> None:
    readiness = _3d_pipeline_readiness()
    assert isinstance(readiness, dict)
    assert "STEP_IMPORT" in readiness
    assert "BREP_TOPOLOGY" in readiness
    assert "FEATURE_EXTRACTION" in readiness


def test_3d_pipeline_step_import_not_implemented() -> None:
    readiness = _3d_pipeline_readiness()
    assert readiness["STEP_IMPORT"] == "NOT_IMPLEMENTED"


def test_3d_pipeline_brep_not_implemented() -> None:
    readiness = _3d_pipeline_readiness()
    assert readiness["BREP_TOPOLOGY"] == "NOT_IMPLEMENTED"


# ---------------------------------------------------------------------------
# örnek dosyalar scan: REAL_STEP_SAMPLE_COUNT=0
# ---------------------------------------------------------------------------


def test_example_files_directory_scan_zero() -> None:
    """Scan the designated STEP sample directory. Zero qualified files expected."""
    sample_dir = r"D:\makina_ogrenmesi\örnek dosyalar"
    results = scan_step_samples(sample_dir)
    qualified = [r for r in results if r.is_qualified]
    # REAL_STEP_SAMPLE_COUNT must be 0 (cadquery not installed; dir may not exist)
    assert len(qualified) == 0, (
        f"Expected 0 qualified STEP samples, got {len(qualified)}: "
        f"{[r.file_path for r in qualified]}"
    )
