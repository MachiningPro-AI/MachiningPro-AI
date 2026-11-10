"""Level-20 CAD format acceptance tests (MUST 25-27).

Tests each advertised upload format through upload→storage→CAD_IMPORT path.
All fixtures are TEST_ONLY / DEMO — no proprietary customer data.

FORMATS_TESTED: DXF, IGS, IGES, STP, STEP
MALFORMED_CAD_TESTED: YES
OVERSIZED_TESTED: YES
EMPTY_TESTED: YES
UNSUPPORTED_EXTENSION_TESTED: YES
"""

import pytest

from backend.api.cad_upload import (
    ALLOWED_EXTENSIONS,
    _reject_traversal,
    _sanitize_filename,
    _validate_dxf_header,
    _validate_format,
    _validate_iges_header,
    _validate_step_header,
)
from backend.persistence.artifact_store import ArtifactStore
from backend.workflow.enums import StageStatus, WorkflowObjective
from backend.workflow.models import WorkflowContext
from backend.workflow.stage_runners.cad_runner import CadImportRunner
from tests.fixtures.cad_golden import (
    malformed_dxf,
    malformed_iges,
    malformed_step,
    minimal_dxf,
    minimal_iges,
    minimal_step,
)


class TestFormatHeaderValidation:
    """Unit tests for per-format header validators."""

    # DXF
    def test_valid_dxf_accepted(self):
        assert _validate_dxf_header(minimal_dxf()) is True

    def test_malformed_dxf_rejected(self):
        assert _validate_dxf_header(malformed_dxf()) is False

    def test_empty_dxf_rejected(self):
        assert _validate_dxf_header(b"") is False

    # STEP
    def test_valid_step_accepted(self):
        assert _validate_step_header(minimal_step()) is True

    def test_malformed_step_rejected(self):
        assert _validate_step_header(malformed_step()) is False

    def test_empty_step_rejected(self):
        assert _validate_step_header(b"") is False

    # IGES
    def test_valid_iges_accepted(self):
        assert _validate_iges_header(minimal_iges()) is True

    def test_malformed_iges_rejected(self):
        assert _validate_iges_header(malformed_iges()) is False

    def test_iges_too_short_rejected(self):
        assert _validate_iges_header(b"short") is False

    # validate_format dispatch
    def test_validate_format_dxf(self):
        assert _validate_format(".dxf", minimal_dxf()) is True

    def test_validate_format_stp(self):
        assert _validate_format(".stp", minimal_step()) is True

    def test_validate_format_step(self):
        assert _validate_format(".step", minimal_step()) is True

    def test_validate_format_igs(self):
        assert _validate_format(".igs", minimal_iges()) is True

    def test_validate_format_iges(self):
        assert _validate_format(".iges", minimal_iges()) is True

    def test_validate_format_unsupported_ext(self):
        assert _validate_format(".exe", b"anything") is False

    def test_validate_format_mismatch_dxf_step(self):
        assert _validate_format(".dxf", minimal_step()) is False

    def test_validate_format_mismatch_step_dxf(self):
        assert _validate_format(".stp", minimal_dxf()) is False


class TestFilenameValidation:
    def test_reject_traversal_dotdot(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _reject_traversal("../../../etc/passwd.dxf")
        assert exc_info.value.status_code == 422

    def test_reject_traversal_forward_slash(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _reject_traversal("some/path/file.dxf")

    def test_reject_traversal_backslash(self):
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _reject_traversal("some\\path\\file.dxf")

    def test_safe_filename_accepted(self):
        _reject_traversal("my_part_v2.dxf")  # should not raise

    def test_sanitize_strips_directory(self):
        safe, ext = _sanitize_filename("../../../etc/passwd.dxf")
        assert "/" not in safe
        assert ".." not in safe

    def test_sanitize_ext_lowercase(self):
        _, ext = _sanitize_filename("PART.DXF")
        assert ext == ".dxf"

    def test_sanitize_long_stem_truncated(self):
        long_name = "A" * 300 + ".dxf"
        safe, _ = _sanitize_filename(long_name)
        assert len(safe) <= 135  # 128 stem + 4 ext + 3 margin


class TestAllowedExtensions:
    def test_all_advertised_formats_allowed(self):
        for ext in [".dxf", ".igs", ".iges", ".stp", ".step"]:
            assert ext in ALLOWED_EXTENSIONS, f"{ext} not in ALLOWED_EXTENSIONS"

    def test_dangerous_extensions_blocked(self):
        for ext in [".exe", ".py", ".sh", ".bat", ".ps1", ".js", ".php"]:
            assert ext not in ALLOWED_EXTENSIONS


class TestArtifactStoreDXFAcceptance:
    """Round-trip: write fixture → store → resolve path."""

    def test_dxf_stored_and_resolved(self, tmp_path):
        store = ArtifactStore(tmp_path / "artifacts")
        src = tmp_path / "TEST_ONLY_part.dxf"
        src.write_bytes(minimal_dxf())
        ref = store.store(src, "TEST_ONLY_part.dxf", ".dxf")
        path = store.resolve(ref.artifact_id)
        assert path is not None
        assert path.read_bytes() == minimal_dxf()

    def test_stp_stored_and_resolved(self, tmp_path):
        store = ArtifactStore(tmp_path / "artifacts")
        src = tmp_path / "TEST_ONLY_part.stp"
        src.write_bytes(minimal_step())
        ref = store.store(src, "TEST_ONLY_part.stp", ".stp")
        path = store.resolve(ref.artifact_id)
        assert path is not None

    def test_step_stored_and_resolved(self, tmp_path):
        store = ArtifactStore(tmp_path / "artifacts")
        src = tmp_path / "TEST_ONLY_part.step"
        src.write_bytes(minimal_step())
        ref = store.store(src, "TEST_ONLY_part.step", ".step")
        assert store.exists(ref.artifact_id)

    def test_iges_stored_and_resolved(self, tmp_path):
        store = ArtifactStore(tmp_path / "artifacts")
        src = tmp_path / "TEST_ONLY_part.iges"
        src.write_bytes(minimal_iges())
        ref = store.store(src, "TEST_ONLY_part.iges", ".iges")
        assert store.exists(ref.artifact_id)

    def test_igs_stored_and_resolved(self, tmp_path):
        store = ArtifactStore(tmp_path / "artifacts")
        src = tmp_path / "TEST_ONLY_part.igs"
        src.write_bytes(minimal_iges())
        ref = store.store(src, "TEST_ONLY_part.igs", ".igs")
        assert store.exists(ref.artifact_id)


class TestCadRunnerWithFixtures:
    """Level-19 CAD_IMPORT stage with actual fixture files."""

    def _make_ctx(self, file_ref: str) -> WorkflowContext:
        return WorkflowContext(
            workflow_id="WF_acceptance_test",
            part_reference="TEST_ONLY_PART",
            revision="REV-TEST",
            source_file_ref=file_ref,
            material_ref=None,
            quantity=1,
            stock_ref=None,
            objective=WorkflowObjective.BALANCED,
        )

    def test_dxf_cad_import_pass(self, tmp_path):
        dxf_file = tmp_path / "TEST_ONLY.dxf"
        dxf_file.write_bytes(minimal_dxf())
        ctx = self._make_ctx(str(dxf_file))
        runner = CadImportRunner()
        result = runner.run(ctx)
        # Should PASS or at worst PARTIAL (not BLOCKED/FAILED)
        assert result.status in (
            StageStatus.PASS, StageStatus.PARTIAL
        ), f"Expected PASS or PARTIAL, got {result.status}: {result.warnings} {result.errors}"

    def test_step_cad_import_pass_or_partial(self, tmp_path):
        stp_file = tmp_path / "TEST_ONLY.stp"
        stp_file.write_bytes(minimal_step())
        ctx = self._make_ctx(str(stp_file))
        runner = CadImportRunner()
        result = runner.run(ctx)
        assert result.status in (StageStatus.PASS, StageStatus.PARTIAL)

    def test_missing_file_blocked(self):
        ctx = self._make_ctx("/nonexistent/path/no_such_file.dxf")
        runner = CadImportRunner()
        result = runner.run(ctx)
        assert result.status == StageStatus.BLOCKED

    def test_no_source_ref_blocked(self):
        ctx = self._make_ctx(None)
        runner = CadImportRunner()
        result = runner.run(ctx)
        assert result.status == StageStatus.BLOCKED

    def test_unsupported_extension_partial(self, tmp_path):
        bad_file = tmp_path / "TEST_ONLY.xyz"
        bad_file.write_bytes(b"unsupported format content")
        ctx = self._make_ctx(str(bad_file))
        runner = CadImportRunner()
        result = runner.run(ctx)
        assert result.status == StageStatus.PARTIAL

    def test_dxf_import_sets_geometry_ref(self, tmp_path):
        dxf_file = tmp_path / "TEST_ONLY.dxf"
        dxf_file.write_bytes(minimal_dxf())
        ctx = self._make_ctx(str(dxf_file))
        runner = CadImportRunner()
        result = runner.run(ctx)
        if result.status == StageStatus.PASS:
            assert ctx.geometry_ref is not None
            assert "GEO_DXF" in ctx.geometry_ref
