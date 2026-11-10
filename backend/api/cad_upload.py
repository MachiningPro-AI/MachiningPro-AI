"""CAD file upload endpoint.

Accepts DXF, IGES, and STEP files from authenticated users.
Returns a file_ref suitable for use as source_file_ref in CreateWorkflowRequest.

Safety invariants:
  PATH_TRAVERSAL_PROTECTION=YES
  UPLOAD_EXTENSION_ALLOWLIST=YES   (.dxf .igs .iges .stp .step)
  UPLOAD_SIZE_LIMIT=YES            (CAD_UPLOAD_MAX_BYTES env var, default 50 MB)
  CONTENT_HEADER_VALIDATION=YES
  NO_SERVER_PATH_IN_RESPONSE=YES
  DURABLE_STORAGE=YES              (ArtifactStore, Level 20)

Level-20: files are persisted in ArtifactStore (not OS temp dir).
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from pydantic import BaseModel

from ..observability import metrics
from ..persistence import ArtifactStoreError, get_artifact_store
from .auth import verify_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/cad-upload", tags=["cad-upload"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".dxf", ".igs", ".iges", ".stp", ".step"})

MAX_UPLOAD_BYTES: int = int(os.getenv("CAD_UPLOAD_MAX_BYTES", str(50 * 1024 * 1024)))  # 50 MB

# Demo mode: tighter upload limit
_DEMO_MODE = os.getenv("MACHININGPRO_DEMO_MODE", "0").strip() in ("1", "true", "yes")
if _DEMO_MODE:
    MAX_UPLOAD_BYTES = min(MAX_UPLOAD_BYTES, 5 * 1024 * 1024)  # 5 MB cap in demo


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:  # noqa: B008
    """Bearer token auth; fails closed with 401."""
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        metrics.increment(metrics.AUTH_FAILED)
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


# ---------------------------------------------------------------------------
# Response model
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    file_id: str
    original_filename: str
    safe_name: str
    size_bytes: int
    format: str
    upload_status: str
    file_ref: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9_\-]")


def _sanitize_filename(raw: str) -> tuple[str, str]:
    """Return (safe_name, ext) from a raw filename."""
    name = Path(raw).name
    stem = Path(name).stem
    ext = Path(name).suffix.lower()
    safe_stem = _SAFE_STEM_RE.sub("_", stem)[:128] or "cad_file"
    return f"{safe_stem}{ext}", ext


def _reject_traversal(raw: str) -> None:
    """Raise 422 if the raw filename contains path-traversal patterns."""
    if any(c in raw for c in ("..", "/", "\\")):
        raise HTTPException(422, detail="Invalid filename: path traversal not permitted")


def _validate_dxf_header(data: bytes) -> bool:
    head = data[:20].decode("utf-8", errors="ignore").strip()
    return head.startswith("0") or head.startswith("  0")


def _validate_iges_header(data: bytes) -> bool:
    if len(data) < 80:
        return False
    try:
        first_line = data[:80].decode("ascii", errors="ignore")
        return first_line[72:73] == "S"
    except Exception:  # noqa: BLE001
        return False


def _validate_step_header(data: bytes) -> bool:
    return data[:20].lstrip().upper().startswith(b"ISO-10303-21")


def _validate_format(ext: str, data: bytes) -> bool:
    if ext == ".dxf":
        return _validate_dxf_header(data)
    if ext in (".igs", ".iges"):
        return _validate_iges_header(data)
    if ext in (".stp", ".step"):
        return _validate_step_header(data)
    return False


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("", response_model=UploadResponse, status_code=200)
async def upload_cad_file(
    file: UploadFile,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> UploadResponse:
    """Upload a CAD file. Returns a file_ref for use in workflow creation."""

    # --- Filename safety ---
    raw_name = file.filename or ""
    _reject_traversal(raw_name)
    safe_name, ext = _sanitize_filename(raw_name)

    if ext not in ALLOWED_EXTENSIONS:
        metrics.increment(metrics.UPLOAD_REJECTED)
        raise HTTPException(
            422,
            detail=(
                f"Unsupported file format {ext!r}. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )

    # --- Read content (with size limit) ---
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
    except Exception as exc:
        metrics.increment(metrics.UPLOAD_REJECTED)
        raise HTTPException(422, detail=f"Failed to read upload: {exc}") from exc

    if len(data) == 0:
        metrics.increment(metrics.UPLOAD_REJECTED)
        raise HTTPException(422, detail="Empty file — nothing to upload")

    if len(data) > MAX_UPLOAD_BYTES:
        metrics.increment(metrics.UPLOAD_OVERSIZED)
        raise HTTPException(
            413,
            detail=(
                f"File exceeds size limit of {MAX_UPLOAD_BYTES} bytes "
                f"({MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
            ),
        )

    # --- Format header validation ---
    if not _validate_format(ext, data):
        metrics.increment(metrics.UPLOAD_REJECTED)
        raise HTTPException(
            422,
            detail=f"File content does not match declared format {ext!r}",
        )

    # --- Store via ArtifactStore (durable, not OS temp) ---
    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(data)
            tmp_path = Path(tmp.name)

        artifact_store = get_artifact_store()
        artifact_ref = artifact_store.store(tmp_path, raw_name, ext)

    except ArtifactStoreError as exc:
        logger.error("ArtifactStore unavailable during upload: %s", exc)
        metrics.increment(metrics.UPLOAD_REJECTED)
        raise HTTPException(503, detail="Storage unavailable — try again shortly") from exc
    except Exception as exc:
        metrics.increment(metrics.UPLOAD_REJECTED)
        raise HTTPException(500, detail=f"Failed to store file: {exc}") from exc
    finally:
        if tmp_path and tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    metrics.increment(metrics.UPLOAD_ACCEPTED)
    logger.info(
        "CAD upload accepted artifact_id=%s format=%s size=%d",
        artifact_ref.artifact_id,
        ext,
        artifact_ref.size_bytes,
    )

    return UploadResponse(
        file_id=artifact_ref.artifact_id,
        original_filename=raw_name,
        safe_name=artifact_ref.safe_name,
        size_bytes=artifact_ref.size_bytes,
        format=ext,
        upload_status="ACCEPTED",
        file_ref=artifact_ref.artifact_id,  # opaque 32-char hex ID
    )


def resolve_file_ref(file_ref: str) -> str:
    """Convert a file_ref from the upload response to an absolute path.

    Returns the absolute path; raises ValueError if not found or invalid.
    PATH_TRAVERSAL_PROTECTION=YES — only hex artifact IDs accepted.
    """
    artifact_store = get_artifact_store()
    path = artifact_store.resolve(file_ref)
    if path is None:
        raise ValueError(f"Uploaded file not found for ref {file_ref!r}")
    return str(path)
