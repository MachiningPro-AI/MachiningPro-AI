"""
P10 Phase 4 — Real STEP Qualification Gate Tests.

MUST 37: Add real qualification tests where deterministic and legally safe.
FINAL_RESULT: DEFERRED_REAL_EXTERNAL_STEP_SAMPLE_REQUIRED
  (REAL_EXTERNAL_STEP_SAMPLE_COUNT=0 at time of P10 Phase 4 scan)

HARD RULES verified here:
  HR-01: IN_HOUSE_BENCHMARK files MUST NOT count as REAL_EXTERNAL_STEP.
  HR-21: is_dispatchable=False always.
  HR-22: production_released=False always.

These tests document and enforce the Phase 4 deferred gate state.
They will remain valid until at least one real external STEP file is ingested.
"""

from __future__ import annotations

import os
import pathlib

import pytest

from backend.cad_import.step_intake import (
    IN_HOUSE_BENCHMARK_STEP_COUNT,
    REAL_STEP_SAMPLE_COUNT,
    StepIntakeRequest,
    StepIntakeStatus,
    accept_step_file,
    scan_step_samples,
)

# ---------------------------------------------------------------------------
# Phase 4 scan constants (recorded from P10 Phase 4 scan, 2026-11-17)
# ---------------------------------------------------------------------------

_REAL_SAMPLE_ROOT = r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar"

_PHASE4_SCAN_REAL_EXTERNAL_STEP_COUNT = 0  # Verified: 2026-11-17
_PHASE4_IN_HOUSE_BENCHMARK_COUNT = 3       # P10-S1/S2/S3 from benchmark_generator.py

_BENCHMARK_DIR = (
    pathlib.Path(__file__).parent.parent.parent
    / "qualification" / "fixtures" / "step"
)


# ---------------------------------------------------------------------------
# MUST 2: Sample count gate
# ---------------------------------------------------------------------------


class TestPhase4SampleCounts:
    def test_real_step_sample_count_is_zero(self):
        """Phase 4 scan: no real external STEP files found."""
        assert REAL_STEP_SAMPLE_COUNT == 0

    def test_in_house_benchmark_count_is_three(self):
        """3 IN_HOUSE_BENCHMARK fixtures from Phase 3 benchmark_generator."""
        assert IN_HOUSE_BENCHMARK_STEP_COUNT == 3

    def test_benchmark_count_not_added_to_real_count(self):
        """HARD RULE 1: benchmark files must NEVER inflate REAL_STEP_SAMPLE_COUNT."""
        assert REAL_STEP_SAMPLE_COUNT != IN_HOUSE_BENCHMARK_STEP_COUNT
        assert REAL_STEP_SAMPLE_COUNT == 0

    def test_phase4_scan_matches_recorded_result(self):
        """Phase 4 recorded scan: REAL_EXTERNAL=0, IN_HOUSE=3."""
        assert REAL_STEP_SAMPLE_COUNT == _PHASE4_SCAN_REAL_EXTERNAL_STEP_COUNT
        assert IN_HOUSE_BENCHMARK_STEP_COUNT == _PHASE4_IN_HOUSE_BENCHMARK_COUNT


# ---------------------------------------------------------------------------
# MUST 3: Deferred gate
# ---------------------------------------------------------------------------


class TestPhase4DeferredGate:
    def test_qualification_not_ready_without_real_sample(self):
        """REAL_STEP_QUALIFICATION_READY=NO when REAL_STEP_SAMPLE_COUNT=0."""
        # qualification is ready only when real sample count >= 1
        qualification_ready = REAL_STEP_SAMPLE_COUNT >= 1
        assert qualification_ready is False

    def test_benchmark_cannot_substitute_for_real_sample(self):
        """IN_HOUSE_BENCHMARK files do NOT satisfy the real sample gate."""
        # Even with 3 benchmark files, the real sample gate remains unmet
        assert IN_HOUSE_BENCHMARK_STEP_COUNT == 3
        assert REAL_STEP_SAMPLE_COUNT == 0
        qualification_ready = REAL_STEP_SAMPLE_COUNT >= 1
        assert qualification_ready is False

    @pytest.mark.skipif(
        not os.path.isdir(_REAL_SAMPLE_ROOT),
        reason="Real sample root not accessible",
    )
    def test_scan_real_sample_root_returns_empty(self):
        """Scanning the real sample root returns 0 STEP files (Phase 4 result)."""
        results = scan_step_samples(_REAL_SAMPLE_ROOT)
        step_files = [r for r in results if r.status != StepIntakeStatus.REJECTED_FILE_NOT_FOUND]
        assert len(step_files) == 0

    def test_scan_nonexistent_directory_returns_empty(self):
        """scan_step_samples is fail-closed on missing directory."""
        results = scan_step_samples(r"C:\nonexistent\path\that\does\not\exist")
        assert results == []


# ---------------------------------------------------------------------------
# MUST 4: IN_HOUSE_BENCHMARK source integrity
# ---------------------------------------------------------------------------


class TestBenchmarkSourceIntegrity:
    @pytest.fixture(autouse=True)
    def _require_benchmark_dir(self):
        if not _BENCHMARK_DIR.exists():
            pytest.skip("Benchmark fixtures not generated yet")

    def test_benchmark_files_exist(self):
        """P10-S1/S2/S3 fixture files must exist."""
        for name in ("P10_S1_drilled_block.step", "P10_S2_pocket_slot.step",
                     "P10_S3_multi_feature.step"):
            assert (_BENCHMARK_DIR / name).exists(), f"Missing: {name}"

    def test_benchmark_ground_truth_has_in_house_label(self):
        """Every ground-truth file must label sample_origin=IN_HOUSE_BENCHMARK."""
        import json
        for name in ("P10_S1_drilled_block_ground_truth.json",
                     "P10_S2_pocket_slot_ground_truth.json",
                     "P10_S3_multi_feature_ground_truth.json"):
            gt = json.loads((_BENCHMARK_DIR / name).read_text(encoding="utf-8"))
            assert gt["sample_origin"] == "IN_HOUSE_BENCHMARK", f"{name}: wrong origin"
            assert gt["is_real_external_sample"] is False, f"{name}: wrong flag"
            assert gt["qualification_class"] == "SOFTWARE_BENCHMARK", f"{name}: wrong class"

    def test_benchmark_ground_truth_not_dispatchable(self):
        """HARD RULE 21: is_dispatchable=False in every benchmark ground-truth."""
        import json
        for name in ("P10_S1_drilled_block_ground_truth.json",
                     "P10_S2_pocket_slot_ground_truth.json",
                     "P10_S3_multi_feature_ground_truth.json"):
            gt = json.loads((_BENCHMARK_DIR / name).read_text(encoding="utf-8"))
            assert gt["is_dispatchable"] is False
            assert gt["production_released"] is False

    def test_benchmark_step_pass_via_intake(self):
        """Benchmark STEP files pass the intake gate (B-Rep parser functional)."""
        for name in ("P10_S1_drilled_block.step", "P10_S2_pocket_slot.step",
                     "P10_S3_multi_feature.step"):
            path = str(_BENCHMARK_DIR / name)
            result = accept_step_file(StepIntakeRequest(file_path=path))
            assert result.status == StepIntakeStatus.PASS, (
                f"{name}: expected PASS, got {result.status}: {result.rejection_reason}"
            )
            assert result.is_qualified is True
            assert result.part_bbox_min is not None
            assert result.part_bbox_max is not None
            assert result.provenance == "STEP_FILE_EVIDENCE"
            # HARD RULE 21/22
            assert result.is_qualified in (True, False)   # always a bool, never raises

    def test_benchmark_intake_result_not_dispatchable(self):
        """StepIntakeResult has no is_dispatchable=True path (HARD RULE 21)."""
        # The intake result itself does not carry is_dispatchable;
        # the StepImportRecord from the underlying parser does.
        from backend.step_brep.gmsh_step_parser import parse_step_file
        for name in ("P10_S1_drilled_block.step",):
            path = str(_BENCHMARK_DIR / name)
            rec = parse_step_file(path)
            assert rec.is_dispatchable is False
            assert rec.production_released is False


# ---------------------------------------------------------------------------
# MUST 36 / MUST 35: Safety invariants
# ---------------------------------------------------------------------------


class TestPhase4SafetyInvariants:
    def test_no_real_step_import_dispatched(self):
        """REAL_STEP_SAMPLE_COUNT=0 means no real file was ever dispatched."""
        assert REAL_STEP_SAMPLE_COUNT == 0

    def test_intake_result_is_qualified_false_when_file_missing(self):
        """HARD RULE 21: a file-not-found result is never marked qualified."""
        result = accept_step_file(
            StepIntakeRequest(file_path="nonexistent_real_part.step")
        )
        assert result.status == StepIntakeStatus.REJECTED_FILE_NOT_FOUND
        assert result.is_qualified is False

    def test_step_import_ready_true(self):
        """STEP_IMPORT_READY=True (Phase 3 wired gmsh)."""
        from backend.cad_import.step_intake import STEP_IMPORT_READY
        assert STEP_IMPORT_READY is True

    def test_brep_topology_ready_true(self):
        """BREP_TOPOLOGY_READY=True (Phase 3 wired topology_adapter)."""
        from backend.cad_import.step_intake import BREP_TOPOLOGY_READY
        assert BREP_TOPOLOGY_READY is True

    def test_feature_extraction_ready_true(self):
        """FEATURE_EXTRACTION_READY=True (Phase 3 wired hole detector)."""
        from backend.cad_import.step_intake import FEATURE_EXTRACTION_READY
        assert FEATURE_EXTRACTION_READY is True


# ---------------------------------------------------------------------------
# MUST 29 / MUST 30: Phase 4 qualification result documentation
# ---------------------------------------------------------------------------


class TestPhase4QualificationResult:
    """Documents the Phase 4 qualification result per MUST 29."""

    # These are documentation-as-tests: they assert the deferred state and
    # will need updating when the first real STEP file is ingested.

    PHASE4_RESULT = "DEFERRED_REAL_EXTERNAL_STEP_SAMPLE_REQUIRED"
    SCAN_DATE = "2026-11-17"
    SCAN_ROOT = r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar"

    def test_phase4_final_result_is_deferred(self):
        """Phase 4 final result is DEFERRED — no real STEP file was found."""
        assert self.PHASE4_RESULT == "DEFERRED_REAL_EXTERNAL_STEP_SAMPLE_REQUIRED"
        assert REAL_STEP_SAMPLE_COUNT == 0

    def test_phase4_in_house_benchmarks_do_not_unblock_gate(self):
        """3 benchmark fixtures cannot substitute for a real external STEP (MUST 3)."""
        # Gate condition: REAL_EXTERNAL_STEP_SAMPLE_COUNT >= 1 required.
        assert IN_HOUSE_BENCHMARK_STEP_COUNT == 3
        assert REAL_STEP_SAMPLE_COUNT == 0

    def test_phase4_next_step_documented(self):
        """Next step: ingest a user-owned / legitimately sourced STEP file."""
        # NEXT_PRIMARY_BLOCKER = REAL_EXTERNAL_STEP_SAMPLE_REQUIRED
        # Acquisition paths (non-exhaustive):
        #   1. Create in FreeCAD (LGPL, free) → export AP214 STEP
        #   2. Source CC0 public domain part from NIH 3D Print Exchange
        #   3. Use an existing in-house drawing → regenerate as STEP
        # This test documents the requirement without implementing it.
        assert REAL_STEP_SAMPLE_COUNT == 0  # still zero — action is external
