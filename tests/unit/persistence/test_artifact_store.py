"""Tests for ArtifactStore — durable CAD artifact storage and security."""
import pytest

from backend.persistence.artifact_store import (
    ArtifactStore,
    _valid_artifact_id,
)


class TestArtifactIdValidation:
    def test_valid_id(self):
        assert _valid_artifact_id("a" * 32) is True
        assert _valid_artifact_id("0123456789abcdef" * 2) is True

    def test_too_short(self):
        assert _valid_artifact_id("abc") is False

    def test_too_long(self):
        assert _valid_artifact_id("a" * 33) is False

    def test_uppercase_rejected(self):
        assert _valid_artifact_id("A" * 32) is False

    def test_path_traversal_rejected(self):
        assert _valid_artifact_id("../etc/passwd" + "a" * 19) is False
        assert _valid_artifact_id("../../" + "a" * 26) is False

    def test_slash_rejected(self):
        assert _valid_artifact_id("/" + "a" * 31) is False

    def test_backslash_rejected(self):
        assert _valid_artifact_id("\\" + "a" * 31) is False

    def test_empty_string(self):
        assert _valid_artifact_id("") is False


class TestArtifactStore:
    @pytest.fixture
    def store(self, tmp_path):
        return ArtifactStore(tmp_path / "artifacts")

    def test_store_dxf_file(self, store, tmp_path):
        content = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF\n"
        src = tmp_path / "part.dxf"
        src.write_bytes(content)
        ref = store.store(src, "part.dxf", ".dxf")
        assert len(ref.artifact_id) == 32
        assert all(c in "0123456789abcdef" for c in ref.artifact_id)
        assert ref.fmt == ".dxf"
        assert ref.size_bytes == len(content)
        assert ref.original_filename == "part.dxf"

    def test_stored_file_is_accessible(self, store, tmp_path):
        content = b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
        src = tmp_path / "part.stp"
        src.write_bytes(content)
        ref = store.store(src, "part.stp", ".stp")
        path = store.resolve(ref.artifact_id)
        assert path is not None
        assert path.exists()
        assert path.read_bytes() == content

    def test_content_addressed_deduplication(self, store, tmp_path):
        content = b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF\n"
        src1 = tmp_path / "copy1.dxf"
        src2 = tmp_path / "copy2.dxf"
        src1.write_bytes(content)
        src2.write_bytes(content)
        ref1 = store.store(src1, "copy1.dxf", ".dxf")
        ref2 = store.store(src2, "copy2.dxf", ".dxf")
        assert ref1.artifact_id == ref2.artifact_id  # same content → same ID

    def test_resolve_nonexistent_returns_none(self, store):
        fake_id = "a" * 32
        assert store.resolve(fake_id) is None

    def test_resolve_traversal_attempt_returns_none(self, store):
        assert store.resolve("../etc/passwd" + "a" * 19) is None
        assert store.resolve("") is None
        assert store.resolve("/absolute/path" + "a" * 18) is None

    def test_exists_true_after_store(self, store, tmp_path):
        src = tmp_path / "t.dxf"
        src.write_bytes(b"  0\nSECTION\n  0\nENDSEC\n  0\nEOF\n")
        ref = store.store(src, "t.dxf", ".dxf")
        assert store.exists(ref.artifact_id) is True

    def test_exists_false_for_unknown(self, store):
        assert store.exists("b" * 32) is False

    def test_is_healthy_true(self, store):
        assert store.is_healthy() is True

    def test_safe_name_has_no_original_filename(self, store, tmp_path):
        """safe_name must not contain path components from original_filename."""
        content = b"  0\nSECTION\n  0\nENDSEC\n  0\nEOF\n"
        src = tmp_path / "exploit.dxf"
        src.write_bytes(content)
        ref = store.store(src, "../../../etc/passwd.dxf", ".dxf")
        assert "/" not in ref.safe_name
        assert ".." not in ref.safe_name

    def test_different_content_different_id(self, store, tmp_path):
        src1 = tmp_path / "a.dxf"
        src2 = tmp_path / "b.dxf"
        src1.write_bytes(b"  0\nSECTION\n  0\nENDSEC\n  0\nEOF\n")
        src2.write_bytes(b"  0\nSECTION\n  0\nENDSEC\n  0\nEOF\nEXTRA\n")
        ref1 = store.store(src1, "a.dxf", ".dxf")
        ref2 = store.store(src2, "b.dxf", ".dxf")
        assert ref1.artifact_id != ref2.artifact_id
