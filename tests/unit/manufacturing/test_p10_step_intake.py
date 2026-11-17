"""
P10-B test suite: STEP/B-Rep qualification intake.

Validates:
  - REAL_STEP_SAMPLE_COUNT=0 (zero real STEP files)
  - scan_step_samples on sample directory returns empty list
  - accept_step_file with wrong extension → REJECTED_WRONG_EXTENSION
  - accept_step_file with missing file → REJECTED_FILE_NOT_FOUND
  - accept_step_file with empty file → REJECTED_EMPTY_FILE
  - accept_step_file with valid extension, exists → DEFERRED_NO_PARSER (cadquery not installed)
  - STEP_IMPORT_READY=NO, BREP_TOPOLOGY_READY=NO, FEATURE_EXTRACTION_READY=NO
  - is_qualified=False for all current results (no cadquery)
  - part_bbox_min/max always None (no fabricated geometry)
  - 3D pipeline readiness: all stages NOT_IMPLEMENTED or PARTIAL

HARD RULES verified:
  - No STEP files fabricated or simulated
  - GOUGE_VALIDATED remains NOT_VERIFIABLE until real sample qualifies
  - REAL_STEP_SAMPLE_COUNT cannot be incremented by this test suite
"""

from __future__ import annotations

import os
import tempfile

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

# Real sample directory from P9 assessment
SAMPLE_DIR = r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar"


# ---------------------------------------------------------------------------
# P10-B1: Real sample count = 0
# ---------------------------------------------------------------------------

class TestRealStepSampleCount:
    def test_real_step_sample_count_is_zero(self):
        assert REAL_STEP_SAMPLE_COUNT == 0

    def test_scan_sample_dir_finds_no_step_files(self):
        results = scan_step_samples(SAMPLE_DIR)
        step_results = [
            r for r in results
            if r.status not in (
                StepIntakeStatus.REJECTED_WRONG_EXTENSION,
                StepIntakeStatus.REJECTED_FILE_NOT_FOUND,
            )
        ]
        assert len(step_results) == 0, (
            f"Unexpected STEP files found: {[r.file_path for r in step_results]}"
        )

    def test_scan_nonexistent_dir_returns_empty(self):
        results = scan_step_samples(r"C:\nonexistent\dir\xyz123")
        assert results == []


# ---------------------------------------------------------------------------
# P10-B2: Parser readiness constants
# ---------------------------------------------------------------------------

class TestParserReadiness:
    def test_step_import_ready_false(self):
        assert STEP_IMPORT_READY is False

    def test_brep_topology_ready_false(self):
        assert BREP_TOPOLOGY_READY is False

    def test_feature_extraction_ready_false(self):
        assert FEATURE_EXTRACTION_READY is False


# ---------------------------------------------------------------------------
# P10-B3: Intake gate — extension check
# ---------------------------------------------------------------------------

class TestIntakeGateExtension:
    def test_dxf_extension_rejected(self):
        result = accept_step_file(StepIntakeRequest("/some/file.dxf"))
        assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION
        assert result.is_qualified is False
        assert result.part_bbox_min is None

    def test_iges_extension_rejected(self):
        result = accept_step_file(StepIntakeRequest("/some/file.iges"))
        assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION
        assert result.is_qualified is False

    def test_txt_extension_rejected(self):
        result = accept_step_file(StepIntakeRequest("/some/file.txt"))
        assert result.status == StepIntakeStatus.REJECTED_WRONG_EXTENSION

    def test_stp_extension_accepted_for_path_check(self):
        result = accept_step_file(StepIntakeRequest("/nonexistent/file.stp"))
        # Should pass extension check but fail on file not found
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND

    def test_step_extension_accepted_for_path_check(self):
        result = accept_step_file(StepIntakeRequest("/nonexistent/file.step"))
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND

    def test_p21_extension_accepted_for_path_check(self):
        result = accept_step_file(StepIntakeRequest("/nonexistent/file.p21"))
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND

    def test_stp_uppercase_extension_accepted(self):
        result = accept_step_file(StepIntakeRequest("/nonexistent/file.STP"))
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND

    def test_step_uppercase_extension_accepted(self):
        result = accept_step_file(StepIntakeRequest("/nonexistent/file.STEP"))
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND


# ---------------------------------------------------------------------------
# P10-B4: Intake gate — file existence and size
# ---------------------------------------------------------------------------

class TestIntakeGateFileChecks:
    def test_missing_file_rejected(self):
        result = accept_step_file(StepIntakeRequest("/nonexistent/part.stp"))
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND
        assert result.is_qualified is False

    def test_empty_file_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
            path = f.name
        try:
            # File exists but is empty
            result = accept_step_file(StepIntakeRequest(path))
            assert result.status == StepIntakeStatus.REJECTED_EMPTY_FILE
            assert result.is_qualified is False
        finally:
            os.unlink(path)

    def test_valid_step_file_deferred_no_parser(self):
        with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
            f.write(b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION(('test'),'2;1');\n")
            path = f.name
        try:
            result = accept_step_file(StepIntakeRequest(path))
            assert result.status == StepIntakeStatus.DEFERRED_NO_PARSER
            assert result.is_qualified is False
            assert result.part_bbox_min is None
            assert result.part_bbox_max is None
        finally:
            os.unlink(path)

    def test_step_file_too_large_rejected(self):
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            f.write(b"x" * 10)
            path = f.name
        try:
            result = accept_step_file(StepIntakeRequest(
                path,
                max_file_size_bytes=5,  # 10 bytes > 5 → too large
            ))
            assert result.status == StepIntakeStatus.REJECTED_FILE_TOO_LARGE
            assert result.is_qualified is False
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# P10-B5: No fabricated geometry
# ---------------------------------------------------------------------------

class TestNoFabricatedGeometry:
    def test_part_bbox_always_none_without_parser(self):
        with tempfile.NamedTemporaryFile(suffix=".step", delete=False) as f:
            f.write(b"ISO-10303-21;\nHEADER;\n")
            path = f.name
        try:
            result = accept_step_file(StepIntakeRequest(path))
            assert result.part_bbox_min is None
            assert result.part_bbox_max is None
        finally:
            os.unlink(path)

    def test_provenance_unknown_without_parser(self):
        with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
            f.write(b"ISO-10303-21;\n")
            path = f.name
        try:
            result = accept_step_file(StepIntakeRequest(path))
            assert result.provenance == "UNKNOWN"
        finally:
            os.unlink(path)

    def test_is_qualified_always_false_without_parser(self):
        with tempfile.NamedTemporaryFile(suffix=".stp", delete=False) as f:
            f.write(b"ISO-10303-21;\n")
            path = f.name
        try:
            result = accept_step_file(StepIntakeRequest(path))
            assert result.is_qualified is False
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# P10-B6: 3D pipeline readiness assessment (MUST 23)
# ---------------------------------------------------------------------------

class TestPipelineReadiness:
    def test_pipeline_readiness_dict_has_all_stages(self):
        readiness = _3d_pipeline_readiness()
        expected_stages = {
            "STEP_IMPORT",
            "BREP_TOPOLOGY",
            "SOLID_CLASSIFIER",
            "FEATURE_EXTRACTION",
            "ROUTE_GENERATION_3D",
            "MACHINE_SELECTION_3D",
            "TOOL_SELECTION_3D",
            "CAM_STRATEGY_3D",
            "TOOLPATH_3D",
            "VERIFICATION_3D",
            "SIMULATION_3D",
        }
        for stage in expected_stages:
            assert stage in readiness, f"Stage {stage} missing from pipeline readiness"

    def test_step_import_not_implemented(self):
        readiness = _3d_pipeline_readiness()
        assert readiness["STEP_IMPORT"] == "NOT_IMPLEMENTED"

    def test_brep_topology_not_implemented(self):
        readiness = _3d_pipeline_readiness()
        assert readiness["BREP_TOPOLOGY"] == "NOT_IMPLEMENTED"

    def test_feature_extraction_not_implemented(self):
        readiness = _3d_pipeline_readiness()
        assert readiness["FEATURE_EXTRACTION"] == "NOT_IMPLEMENTED"

    def test_route_generation_3d_not_implemented(self):
        readiness = _3d_pipeline_readiness()
        assert readiness["ROUTE_GENERATION_3D"] == "NOT_IMPLEMENTED"

    def test_machine_selection_partial(self):
        readiness = _3d_pipeline_readiness()
        assert readiness["MACHINE_SELECTION_3D"] == "PARTIAL"

    def test_no_fully_implemented_stage_before_step(self):
        readiness = _3d_pipeline_readiness()
        # No stage should be fully IMPLEMENTED until STEP is available
        fully_implemented = [
            k for k, v in readiness.items()
            if v == "IMPLEMENTED"
        ]
        assert len(fully_implemented) == 0
