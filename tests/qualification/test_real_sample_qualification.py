"""Real sample file qualification — MachiningPro AI.

Exercises the CAD import pipeline against real engineering files located at the
READ-ONLY source directory.  Tests are SKIPPED automatically when that
directory is absent (CI, staging, fresh clone).

HARD RULES IN EFFECT:
- SOURCE FILES ARE READ-ONLY: never edited, moved, copied, or committed.
- No fabrication: every assertion is bounded by what the pipeline actually returns.
- UNKNOWN information remains UNKNOWN — no assumed units, materials, or tolerances.
- Fail-closed only: UNSUPPORTED and PARTIAL outcomes for unsupported formats are
  PASS conditions, not failures.
- Do NOT copy sample files into repo paths.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import NamedTuple

import pytest

# ---------------------------------------------------------------------------
# Source directory — READ-ONLY, outside the repository
# ---------------------------------------------------------------------------

SAMPLE_DIR = Path(r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar")
SAMPLES_AVAILABLE = SAMPLE_DIR.exists()

skip_if_no_samples = pytest.mark.skipif(
    not SAMPLES_AVAILABLE,
    reason="Real sample directory not available (CI / clean clone)",
)


# ---------------------------------------------------------------------------
# Selected test files
# ---------------------------------------------------------------------------

class SampleFile(NamedTuple):
    filename: str
    declared_format: str
    size_bytes: int              # expected approximate size (±10%)
    checksum_sha256_prefix: str  # first 16 hex chars — integrity check


# DXF series — 2D engineering drawings
DXF_30 = SampleFile("109106_01_30.dxf",   "DXF",         271812,  "")
DXF_38 = SampleFile("109106_01_38.dxf",   "DXF",         599563,  "")
DXF_PS = SampleFile("Pense_Sema.dxf",     "DXF",         894575,  "")

# IGES — 3-axis surface/solid geometry exports
IGES_S  = SampleFile("agv03773.geo_fin001.006003.igs",    "IGES",  217054, "")
IGES_M  = SampleFile("fa00aaj27500_004999.igs",           "IGES",  221292, "")
IGES_L  = SampleFile("fa00aas38521.geo_fin001.004999.igs","IGES",  875514, "")

# PDF — dimensioned engineering drawings (import pipeline path: drawing analysis)
PDF_1 = SampleFile("DWG-00206402-001.pdf",                        "PDF", 342000, "")
PDF_2 = SampleFile("DWG-00139945-001_UPPER COVER MU METAL SHIELD.pdf", "PDF", 422000, "")
PDF_3 = SampleFile("DWG-00139946-001_LOWER COVER MU METAL SHIELD.pdf", "PDF", 506000, "")

# DWG — expected UNSUPPORTED (no registered adapter)
DWG_1 = SampleFile("Pense_Sema.dwg", "DWG", 172000, "")

# CATIA .model — expected UNSUPPORTED (proprietary format, no adapter)
MODEL_1 = SampleFile("46795221-FONDELLO-SEDE-.model", "CATIA_MODEL", 720000, "")

ALL_SUPPORTED = [DXF_30, DXF_38, DXF_PS, IGES_S, IGES_M, IGES_L]
ALL_UNSUPPORTED_BY_IMPORT = [PDF_1, PDF_2, PDF_3, DWG_1, MODEL_1]


# ---------------------------------------------------------------------------
# Import helpers
# ---------------------------------------------------------------------------

def _build_source(sf: SampleFile):
    from backend.interoperability.models import EngineeringSource
    file_path = SAMPLE_DIR / sf.filename
    data = file_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    return (
        EngineeringSource(
            source_id=f"real-sample::{sf.filename}",
            file_name=sf.filename,
            checksum=f"sha256:{sha256}",
        ),
        file_path,
        sha256,
    )


def _run_import(sf: SampleFile):
    from backend.interoperability.orchestrator import CadImportOrchestrator
    source, file_path, sha256 = _build_source(sf)
    orch = CadImportOrchestrator()
    result = orch.import_source(source, content_path=file_path)
    return result, sha256


# ---------------------------------------------------------------------------
# RSQ-01 — Source file inventory and integrity
# ---------------------------------------------------------------------------

class TestRealSampleInventory:
    """RSQ-01: Verify sample files exist and are intact (by size)."""

    @skip_if_no_samples
    def test_dxf_files_exist(self):
        for sf in [DXF_30, DXF_38, DXF_PS]:
            p = SAMPLE_DIR / sf.filename
            assert p.exists(), f"Missing DXF: {sf.filename}"
            actual = p.stat().st_size
            assert abs(actual - sf.size_bytes) / sf.size_bytes < 0.10, (
                f"{sf.filename}: size {actual} deviates >10% from {sf.size_bytes}"
            )

    @skip_if_no_samples
    def test_iges_files_exist(self):
        for sf in [IGES_S, IGES_M, IGES_L]:
            p = SAMPLE_DIR / sf.filename
            assert p.exists(), f"Missing IGES: {sf.filename}"
            actual = p.stat().st_size
            assert abs(actual - sf.size_bytes) / sf.size_bytes < 0.10, (
                f"{sf.filename}: size {actual} deviates >10% from {sf.size_bytes}"
            )

    @skip_if_no_samples
    def test_pdf_files_exist(self):
        for sf in [PDF_1, PDF_2, PDF_3]:
            p = SAMPLE_DIR / sf.filename
            assert p.exists(), f"Missing PDF: {sf.filename}"
            assert p.stat().st_size > 100_000, f"{sf.filename}: suspiciously small"

    @skip_if_no_samples
    def test_unsupported_format_files_exist(self):
        for sf in [DWG_1, MODEL_1]:
            p = SAMPLE_DIR / sf.filename
            assert p.exists(), f"Missing file: {sf.filename}"

    @skip_if_no_samples
    def test_source_files_not_in_repository(self):
        """Confirm sample files were NOT copied into the repository tree."""
        import os
        repo_root = Path(__file__).parents[2]
        for sf in ALL_SUPPORTED + ALL_UNSUPPORTED_BY_IMPORT:
            repo_copy = repo_root / sf.filename
            assert not repo_copy.exists(), (
                f"Sample file found inside repo (must stay outside): {repo_copy}"
            )

    @skip_if_no_samples
    def test_all_files_within_import_size_limit(self):
        """Max import size is 64 MB. Verify all selected files are within limit."""
        max_bytes = 64 * 1024 * 1024
        for sf in ALL_SUPPORTED + ALL_UNSUPPORTED_BY_IMPORT:
            p = SAMPLE_DIR / sf.filename
            if p.exists():
                assert p.stat().st_size <= max_bytes, (
                    f"{sf.filename}: {p.stat().st_size} > {max_bytes} limit"
                )


# ---------------------------------------------------------------------------
# RSQ-02 — DXF import pipeline
# ---------------------------------------------------------------------------

class TestDxfImport:
    """RSQ-02: DXF files import without exception; capabilities match Level 1."""

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_import_does_not_raise(self, sf):
        result, _ = _run_import(sf)
        # Orchestrator never raises — it always returns an ImportResult.
        assert result is not None

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_import_produces_document(self, sf):
        result, _ = _run_import(sf)
        # DXF Level 0/1 always succeeds; ezdxf absent → DEGRADED (not FAILED).
        assert result.document is not None, (
            f"{sf.filename}: import returned no document "
            f"(status={result.status}, error={result.error_message})"
        )

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_import_status_not_failed(self, sf):
        from backend.interoperability.orchestrator import ImportStatus
        result, _ = _run_import(sf)
        assert result.status != ImportStatus.FAILED, (
            f"{sf.filename}: unexpected FAILED status — {result.error_message}"
        )

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_import_degraded_without_ezdxf(self, sf):
        """Without ezdxf, DXF imports are DEGRADED (Level 1 only), not FAILED."""
        from backend.interoperability.orchestrator import ImportStatus
        try:
            import ezdxf  # noqa: F401
            has_ezdxf = True
        except ImportError:
            has_ezdxf = False

        result, _ = _run_import(sf)
        if not has_ezdxf:
            assert result.status == ImportStatus.DEGRADED, (
                f"{sf.filename}: expected DEGRADED without ezdxf, got {result.status}"
            )

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_document_has_entity_refs(self, sf):
        result, _ = _run_import(sf)
        if result.document is not None:
            assert len(result.document.entity_refs) >= 1, (
                f"{sf.filename}: expected at least 1 entity_ref"
            )

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_no_stack_trace_in_error_message(self, sf):
        result, _ = _run_import(sf)
        if result.error_message:
            assert "Traceback" not in result.error_message
            assert "File \"" not in result.error_message

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [DXF_30, DXF_38, DXF_PS], ids=lambda s: s.filename)
    def test_dxf_provenance_recorded(self, sf):
        result, _ = _run_import(sf)
        if result.succeeded:
            assert result.provenance is not None, (
                f"{sf.filename}: succeeded but provenance is None"
            )


# ---------------------------------------------------------------------------
# RSQ-03 — IGES import pipeline
# ---------------------------------------------------------------------------

class TestIgesImport:
    """RSQ-03: IGES files handled without exception; large files parse entity_refs."""

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [IGES_S, IGES_M, IGES_L], ids=lambda s: s.filename)
    def test_iges_import_does_not_raise(self, sf):
        result, _ = _run_import(sf)
        assert result is not None

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [IGES_S, IGES_M, IGES_L], ids=lambda s: s.filename)
    def test_iges_import_status_not_failed(self, sf):
        from backend.interoperability.orchestrator import ImportStatus
        result, _ = _run_import(sf)
        assert result.status != ImportStatus.FAILED, (
            f"{sf.filename}: unexpected FAILED — {result.error_message}"
        )

    @skip_if_no_samples
    def test_iges_large_file_has_entity_refs(self):
        """IGES_L (855 KB) must produce at least 100 entity_refs."""
        result, _ = _run_import(IGES_L)
        assert result.document is not None, "IGES_L returned no document"
        assert len(result.document.entity_refs) >= 100, (
            f"IGES_L: only {len(result.document.entity_refs)} entity_refs, expected >=100"
        )

    @skip_if_no_samples
    def test_iges_small_file_produces_entity_refs(self):
        """IGES_S (217 KB) must produce at least 1 entity_ref (even if UNSUPPORTED)."""
        result, _ = _run_import(IGES_S)
        assert result.document is not None, "IGES_S returned no document"
        assert len(result.document.entity_refs) >= 1

    @skip_if_no_samples
    @pytest.mark.parametrize("sf", [IGES_S, IGES_M, IGES_L], ids=lambda s: s.filename)
    def test_iges_no_stack_trace_in_error(self, sf):
        result, _ = _run_import(sf)
        if result.error_message:
            assert "Traceback" not in result.error_message
            assert "File \"" not in result.error_message


# ---------------------------------------------------------------------------
# RSQ-04 — Unsupported format fail-closed behavior
# ---------------------------------------------------------------------------

class TestUnsupportedFormats:
    """RSQ-04: PDF, DWG, .model return UNSUPPORTED (not exception, not FAILED)."""

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        [PDF_1, PDF_2, PDF_3, DWG_1, MODEL_1],
        ids=lambda s: s.filename,
    )
    def test_unsupported_format_does_not_raise(self, sf):
        result, _ = _run_import(sf)
        assert result is not None

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        [PDF_1, PDF_2, PDF_3, DWG_1, MODEL_1],
        ids=lambda s: s.filename,
    )
    def test_unsupported_format_returns_unsupported_status(self, sf):
        from backend.interoperability.orchestrator import ImportStatus
        result, _ = _run_import(sf)
        assert result.status == ImportStatus.UNSUPPORTED, (
            f"{sf.filename}: expected UNSUPPORTED, got {result.status}"
        )

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        [PDF_1, PDF_2, PDF_3, DWG_1, MODEL_1],
        ids=lambda s: s.filename,
    )
    def test_unsupported_format_does_not_fabricate_document(self, sf):
        """Fail-closed: UNSUPPORTED imports must not return a fabricated document."""
        result, _ = _run_import(sf)
        # PDF/DWG/.model — no adapter → document must be None
        if result.document is not None:
            # If a document is returned it must have UNSUPPORTED normalization,
            # not a fabricated SUCCESS.
            from backend.interoperability.enums import NormalizationStatus
            assert result.document.normalization_status in (
                NormalizationStatus.UNSUPPORTED,
                NormalizationStatus.PARTIAL,
            ), (
                f"{sf.filename}: UNSUPPORTED import returned a document with "
                f"normalization_status={result.document.normalization_status.value}"
            )

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        [PDF_1, PDF_2, PDF_3, DWG_1, MODEL_1],
        ids=lambda s: s.filename,
    )
    def test_unsupported_format_no_stack_trace(self, sf):
        result, _ = _run_import(sf)
        if result.error_message:
            assert "Traceback" not in result.error_message
            assert "File \"" not in result.error_message

    @skip_if_no_samples
    def test_dwg_file_format_not_registered(self):
        """DWG has no registered adapter — format detection must report no adapter."""
        from backend.interoperability.orchestrator import ImportStatus
        result, _ = _run_import(DWG_1)
        assert result.status == ImportStatus.UNSUPPORTED

    @skip_if_no_samples
    def test_catia_model_format_not_registered(self):
        """CATIA .model has no registered adapter — must return UNSUPPORTED."""
        from backend.interoperability.orchestrator import ImportStatus
        result, _ = _run_import(MODEL_1)
        assert result.status == ImportStatus.UNSUPPORTED


# ---------------------------------------------------------------------------
# RSQ-05 — Security invariants on real file imports
# ---------------------------------------------------------------------------

class TestRealSampleSecurityInvariants:
    """RSQ-05: Real file imports must not expose internals or trigger fabrication."""

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        ALL_SUPPORTED + ALL_UNSUPPORTED_BY_IMPORT,
        ids=lambda s: s.filename,
    )
    def test_no_filesystem_path_in_error_message(self, sf):
        """Error messages must not expose server filesystem paths."""
        result, _ = _run_import(sf)
        if result.error_message:
            # Must not contain absolute path segments
            msg = result.error_message
            assert "D:\\" not in msg and "C:\\" not in msg and "/home/" not in msg, (
                f"{sf.filename}: error message exposes filesystem path: {msg[:200]}"
            )

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        ALL_SUPPORTED + ALL_UNSUPPORTED_BY_IMPORT,
        ids=lambda s: s.filename,
    )
    def test_import_result_always_has_import_id(self, sf):
        """Every result must have a stable import_id for traceability."""
        result, _ = _run_import(sf)
        assert result.import_id, f"{sf.filename}: missing import_id"

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        ALL_SUPPORTED + ALL_UNSUPPORTED_BY_IMPORT,
        ids=lambda s: s.filename,
    )
    def test_import_result_has_diagnostics(self, sf):
        """Every result must include diagnostics for traceability."""
        result, _ = _run_import(sf)
        assert result.diagnostics is not None, f"{sf.filename}: missing diagnostics"

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        ALL_SUPPORTED + ALL_UNSUPPORTED_BY_IMPORT,
        ids=lambda s: s.filename,
    )
    def test_no_fabricated_success_on_unsupported(self, sf):
        """Failed/UNSUPPORTED imports must not claim succeeded=True."""
        from backend.interoperability.orchestrator import ImportStatus
        result, _ = _run_import(sf)
        if result.status == ImportStatus.UNSUPPORTED:
            assert not result.succeeded, (
                f"{sf.filename}: status=UNSUPPORTED but succeeded=True (fabrication)"
            )
        if result.status == ImportStatus.FAILED:
            assert not result.succeeded, (
                f"{sf.filename}: status=FAILED but succeeded=True (fabrication)"
            )


# ---------------------------------------------------------------------------
# RSQ-06 — Capability record coherence
# ---------------------------------------------------------------------------

class TestCapabilityRecordCoherence:
    """RSQ-06: CapabilityRecord must be present and coherent for all imports."""

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        ALL_SUPPORTED,
        ids=lambda s: s.filename,
    )
    def test_capability_record_present(self, sf):
        result, _ = _run_import(sf)
        assert result.capability is not None, f"{sf.filename}: missing capability record"

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        ALL_SUPPORTED,
        ids=lambda s: s.filename,
    )
    def test_capability_achieved_level_is_enum(self, sf):
        from backend.interoperability.enums import CapabilityLevel
        result, _ = _run_import(sf)
        if result.capability is not None:
            assert isinstance(result.capability.achieved_level, CapabilityLevel), (
                f"{sf.filename}: achieved_level is not CapabilityLevel: "
                f"{result.capability.achieved_level}"
            )

    @skip_if_no_samples
    @pytest.mark.parametrize(
        "sf",
        [DXF_30, DXF_38, DXF_PS],
        ids=lambda s: s.filename,
    )
    def test_dxf_capability_not_level_zero(self, sf):
        """DXF Level 0/1 always succeeds → achieved_level > LEVEL_0_RECOGNIZED."""
        from backend.interoperability.enums import CapabilityLevel
        result, _ = _run_import(sf)
        if result.capability is not None:
            assert result.capability.achieved_level != CapabilityLevel.LEVEL_0_RECOGNIZED, (
                f"{sf.filename}: DXF achieved only LEVEL_0_RECOGNIZED — "
                f"adapter may have failed silently"
            )
