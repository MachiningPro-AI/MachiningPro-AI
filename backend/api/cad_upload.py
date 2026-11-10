"""CAD file upload endpoint.

Accepts DXF, IGES, and STEP files from authenticated users.
Returns a file_ref suitable for use as source_file_ref in CreateWorkflowRequest.

Safety invariants:
  PATH_TRAVERSAL_PROTECTION=YES
  UPLOAD_EXTENSION_ALLOWLIST=YES   (.dxf .igs .iges .stp .step)
  UPLOAD_SIZE_LIMIT=YES            (CAD_UPLOAD_MAX_BYTES env var, default 50 MB)
  CONTENT_HEADER_VALIDATION=YES
  NO_SERVER_PATH_IN_RESPONSE=YES
  TEMP_CLEANUP_ON_FAILURE=YES
"""
from __future__ import annotations

import os
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, UploadFile
from pydantic import BaseModel

from .auth import verify_token

router = APIRouter(prefix="/api/cad-upload", tags=["cad-upload"])

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".dxf", ".igs", ".iges", ".stp", ".step"})

MAX_UPLOAD_BYTES: int = int(os.getenv("CAD_UPLOAD_MAX_BYTES", str(50 * 1024 * 1024)))  # 50 MB

_UPLOAD_DIR = Path(tempfile.gettempdir()) / "machiningpro_uploads"


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
    """Return (safe_name, ext) from a raw filename.

    Strips directory components, sanitizes stem, preserves extension.
    """
    # Strip all directory components — never trust client path separators
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
    """DXF files start with group code 0 on the first line."""
    head = data[:20].decode("utf-8", errors="ignore").strip()
    return head.startswith("0") or head.startswith("  0")


def _validate_iges_header(data: bytes) -> bool:
    """IGES files have an 'S' (Start section) in fixed column 73 of the first record."""
    if len(data) < 80:
        return False
    try:
        first_line = data[:80].decode("ascii", errors="ignore")
        return first_line[72:73] == "S"
    except Exception:
        return False


def _validate_step_header(data: bytes) -> bool:
    """STEP/STP files begin with 'ISO-10303-21'."""
    return data[:20].lstrip().upper().startswith(b"ISO-10303-21")


def _validate_format(ext: str, data: bytes) -> bool:
    """Return True if the file header matches the declared extension."""
    if ext == ".dxf":
        return _validate_dxf_header(data)
    if ext in (".igs", ".iges"):
        return _validate_iges_header(data)
    if ext in (".stp", ".step"):
        return _validate_step_header(data)
    return False


def _ensure_upload_dir() -> Path:
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    return _UPLOAD_DIR


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
        raise HTTPException(
            422,
            detail=(
                f"Unsupported file format {ext!r}. "
                f"Allowed: {sorted(ALLOWED_EXTENSIONS)}"
            ),
        )

    # --- Read content (with size limit) ---
    dest_path: Path | None = None
    try:
        data = await file.read(MAX_UPLOAD_BYTES + 1)
    except Exception as exc:
        raise HTTPException(422, detail=f"Failed to read upload: {exc}") from exc

    if len(data) == 0:
        raise HTTPException(422, detail="Empty file — nothing to upload")

    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            413,
            detail=(
                f"File exceeds size limit of {MAX_UPLOAD_BYTES} bytes "
                f"({MAX_UPLOAD_BYTES // (1024 * 1024)} MB)"
            ),
        )

    # --- Format header validation ---
    if not _validate_format(ext, data):
        raise HTTPException(
            422,
            detail=f"File content does not match declared format {ext!r}",
        )

    # --- Persist to collision-safe path ---
    file_id = str(uuid.uuid4())
    collision_safe_name = f"{file_id}_{safe_name}"
    dest_path = _ensure_upload_dir() / collision_safe_name

    try:
        dest_path.write_bytes(data)
    except Exception as exc:
        if dest_path and dest_path.exists():
            dest_path.unlink(missing_ok=True)
        raise HTTPException(500, detail=f"Failed to store file: {exc}") from exc

    # file_ref is the opaque reference passed to Workflow; it resolves to the stored path
    # on the same server instance.  We deliberately do NOT return the absolute path.
    file_ref = collision_safe_name

    return UploadResponse(
        file_id=file_id,
        original_filename=raw_name,
        safe_name=safe_name,
        size_bytes=len(data),
        format=ext,
        upload_status="ACCEPTED",
        file_ref=file_ref,
    )


def resolve_file_ref(file_ref: str) -> str:
    """Convert a file_ref from the upload response to an absolute path for the workflow engine.

    Called by the workflow layer when source_file_ref looks like a collision-safe upload name.
    Returns the absolute path; raises ValueError if not found.
    """
    candidate = _ensure_upload_dir() / file_ref
    if not candidate.exists():
        raise ValueError(f"Uploaded file not found for ref {file_ref!r}")
    # Additional path-traversal guard: resolve must stay within upload dir
    try:
        candidate.resolve().relative_to(_UPLOAD_DIR.resolve())
    except ValueError as exc:
        raise ValueError(f"Path traversal detected for ref {file_ref!r}") from exc
    return str(candidate)
