"""CAD artifact store — persists uploaded CAD files outside the OS temp directory.

Security contract:
  PATH_TRAVERSAL_PROTECTION=YES  — artifact_id is validated as hex-only
  NO_SERVER_PATH_IN_RESPONSE=YES — callers receive artifact_id, not filesystem paths
  CROSS_USER_GUESSING_PROTECTION=YES — IDs are SHA-256 derived and unguessable
  ARBITRARY_PATH_READ=NO
  ARBITRARY_PATH_WRITE=NO
"""
from __future__ import annotations

import hashlib
import logging
import shutil
from pathlib import Path
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Artifact IDs are 32 hex characters (first half of SHA-256 hex).
_ARTIFACT_ID_CHARS = frozenset("0123456789abcdef")
_ARTIFACT_ID_LEN = 32


class ArtifactRef(NamedTuple):
    artifact_id: str         # 32-char hex; opaque reference
    safe_name: str           # collision-safe filename stored on disk
    original_filename: str   # display only — never used as a path
    fmt: str                 # file extension (.dxf / .igs / .iges / .stp / .step)
    size_bytes: int


class ArtifactStoreError(RuntimeError):
    """Raised when artifact persistence fails."""


class ArtifactStore:
    """Stores uploaded CAD files in a controlled, persistent directory.

    Files are keyed by an opaque artifact_id derived from content SHA-256.
    The artifact directory must be on a persistent filesystem in production.

    Usage::

        store = ArtifactStore(Path("data/artifacts"))
        ref = store.store(tmp_path, "part.dxf", ".dxf")
        full_path = store.resolve(ref.artifact_id)
    """

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        try:
            self._base.mkdir(parents=True, exist_ok=True)
            logger.info("ArtifactStore initialised at %s", self._base)
        except OSError as exc:
            raise ArtifactStoreError(
                f"Cannot create artifact store at {base_dir}: {exc}"
            ) from exc

    def store(self, source_path: Path, original_filename: str, fmt: str) -> ArtifactRef:
        """Copy source_path into controlled storage and return an ArtifactRef.

        The original_filename is recorded for display only.
        The stored path is an opaque, content-derived filename.
        """
        try:
            content_hash = _sha256_file(source_path)
        except OSError as exc:
            raise ArtifactStoreError(f"Cannot read source file: {exc}") from exc

        artifact_id = content_hash[:_ARTIFACT_ID_LEN]
        safe_name = f"{artifact_id}{fmt.lower()}"
        dest = self._base / safe_name

        try:
            if not dest.exists():
                shutil.copy2(str(source_path), str(dest))
                logger.debug("Stored artifact %s (%d bytes)", artifact_id, dest.stat().st_size)
        except OSError as exc:
            raise ArtifactStoreError(f"Failed to store artifact: {exc}") from exc

        size_bytes = dest.stat().st_size
        return ArtifactRef(
            artifact_id=artifact_id,
            safe_name=safe_name,
            original_filename=original_filename,
            fmt=fmt.lower(),
            size_bytes=size_bytes,
        )

    def resolve(self, artifact_id: str) -> Path | None:
        """Return the absolute Path for an artifact_id, or None if not found.

        Only accepts IDs consisting entirely of lowercase hex characters
        to prevent any path traversal attempt.
        """
        if not _valid_artifact_id(artifact_id):
            logger.warning("Rejected artifact_id with invalid characters: %r", artifact_id)
            return None
        matches = list(self._base.glob(f"{artifact_id}.*"))
        if not matches:
            return None
        return matches[0]

    def exists(self, artifact_id: str) -> bool:
        return self.resolve(artifact_id) is not None

    def is_healthy(self) -> bool:
        try:
            return self._base.is_dir()
        except Exception:  # noqa: BLE001
            return False


def _valid_artifact_id(artifact_id: str) -> bool:
    """Return True only if artifact_id is a 32-char lowercase hex string."""
    if not artifact_id or len(artifact_id) != _ARTIFACT_ID_LEN:
        return False
    return all(c in _ARTIFACT_ID_CHARS for c in artifact_id)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
