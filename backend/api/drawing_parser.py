"""Drawing Parser API — EPIC_04C Phase 2.

7 endpoints for semantic extraction sessions:
  POST /api/drawing-parser/analyze
  GET  /api/drawing-parser/{session_id}/detections
  GET  /api/drawing-parser/{session_id}/requirements
  POST /api/drawing-parser/{session_id}/detections/{detection_id}/confirm
  POST /api/drawing-parser/{session_id}/detections/{detection_id}/edit
  POST /api/drawing-parser/{session_id}/detections/{detection_id}/reject
  POST /api/drawing-parser/{session_id}/detections/{detection_id}/associate

Security: file size enforced, allowed types enforced, no path traversal.
Privacy: drawing bytes never logged, sessions are in-memory only.

FABRICATED_DIMENSION=NO
FABRICATED_TOLERANCE=NO
FABRICATED_FIT=NO
FABRICATED_GDT=NO
UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO
"""

from __future__ import annotations

import base64
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.interoperability.semantic_extraction import (
    AssociationState,
    DetectionSourceType,
    ExtractionSession,
    FeatureType,
    NormalizedDetection,
    ParserConfidence,
    ReviewState,
    create_session,
    run_token_extraction,
)

router = APIRouter(prefix="/api/drawing-parser", tags=["drawing-parser"])

# In-memory session store (process-scoped, temporary by design)
# Drawing bytes are NEVER stored — only extracted detections.
_SESSIONS: dict[str, ExtractionSession] = {}

# Security limits
_MAX_FILE_BYTES = 64 * 1024 * 1024  # 64 MB
_ALLOWED_EXTENSIONS = frozenset({
    "pdf", "png", "jpg", "jpeg", "tiff", "tif", "bmp", "dxf", "step", "stp", "iges", "igs",
})
_ALLOWED_MIME_TYPES = frozenset({
    "application/pdf", "image/png", "image/jpeg", "image/tiff", "image/bmp",
    "image/vnd.dxf", "application/dxf",
    "application/step", "model/step",
    "text/plain",  # DXF / IGES are ASCII
})

DISCLAIMER = "Results are REFERENCE_ONLY. Engineer review required before manufacturing use."


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    source_id: str = Field(..., min_length=1, max_length=256)
    file_name: str = Field(..., min_length=1, max_length=256)
    content_b64: str = Field(..., description="Base64-encoded file content")
    title_block_unit: str | None = None
    drawing_standard: str | None = None
    material_raw: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("file_name")
    @classmethod
    def _sanitize_file_name(cls, v: str) -> str:
        import pathlib
        name = pathlib.PurePosixPath(v).name
        if not name:
            raise ValueError("file_name must be a plain filename, not a path")
        return name

    @field_validator("content_b64")
    @classmethod
    def _validate_content_b64(cls, v: str) -> str:
        try:
            decoded = base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("content_b64 must be valid base64") from exc
        if len(decoded) > _MAX_FILE_BYTES:
            raise ValueError(
                f"File exceeds maximum allowed size ({_MAX_FILE_BYTES // (1024*1024)} MB)"
            )
        return v


class AnalyzeResponse(BaseModel):
    session_id: str
    source_id: str
    status: str
    detection_count: int
    review_required_count: int
    detected_unit: str | None
    ocr_available: bool
    warnings: list[str]
    disclaimer: str


class DetectionOut(BaseModel):
    detection_id: str
    page: int | None
    source_type: str
    normalized_type: str
    normalized_value: str | None
    unit: str | None
    raw_text: str | None
    confidence: float
    confidence_method: str
    review_state: str
    review_required: bool
    association_state: str
    association_feature_id: str | None
    association_feature_type: str
    subtype: str | None
    ambiguities: list[dict[str, Any]]


class DetectionsResponse(BaseModel):
    session_id: str
    detections: list[DetectionOut]
    total: int
    review_required_count: int
    confirmed_count: int
    disclaimer: str


class RequirementsResponse(BaseModel):
    session_id: str
    source_id: str
    detected_unit: str | None
    material_status: str | None
    material_matched_id: str | None
    general_tolerance_standard: str | None
    general_tolerance_linear_mm: float | None
    confirmed_detections: list[DetectionOut]
    unconfirmed_review_required: int
    disclaimer: str


class ConfirmRequest(BaseModel):
    confirmed_value: str | None = None
    confirmed_unit: str | None = None
    confirmed_feature_id: str | None = None


class EditRequest(BaseModel):
    new_value: str = Field(..., min_length=1, max_length=512)
    new_unit: str | None = None


class AssociateRequest(BaseModel):
    feature_id: str = Field(..., min_length=1, max_length=256)
    feature_type: str | None = None


class ActionResponse(BaseModel):
    detection_id: str
    review_state: str
    message: str
    disclaimer: str


# ---------------------------------------------------------------------------
# DXF annotation extraction
# ---------------------------------------------------------------------------

# DXF $INSUNITS code → drawing unit string (None = UNKNOWN, do not assume)
_DXF_INSUNITS_UNIT_MAP: dict[int, str] = {
    1: "inch",   # Inches
    2: "inch",   # Feet (imperial context)
    4: "mm",     # Millimeters
    5: "mm",     # Centimeters (mm drawing context)
    6: "mm",     # Meters (mm drawing context)
    # 0 = Unitless → not in map → returns None (UNKNOWN)
}

_MTEXT_FORMAT_RE = re.compile(
    r'\\[A-Za-z][^;]{0,40};'   # \fFont|...;  \H2.0;  \W1.0;
    r'|\\[PplLouOwW~\{\}n]'    # single-char codes
    r'|\{\\[^}]*\}'            # {\\...} format groups
)


def _extract_dxf_annotations(content_bytes: bytes) -> tuple[list[str], str | None]:
    """Extract text tokens and unit declaration from DXF bytes.

    Returns (text_tokens, drawing_unit) where drawing_unit is "mm", "inch",
    or None (UNKNOWN — $INSUNITS=0/absent; never silently assumed).

    Extracts: TEXT (gc=1), MTEXT (gc=1,3), ATTRIB/ATTDEF (gc=1),
    DIMENSION custom text (gc=1, excluding auto "<>").
    Raw bytes NEVER stored. Only text tokens returned.

    DXF_ANNOTATION_EXTRACTION=YES
    SILENT_MM_ASSUMPTION=NO
    """
    _TEXT_ENTITIES = frozenset({"TEXT", "MTEXT", "ATTRIB", "ATTDEF", "DIMENSION"})

    text_tokens: list[str] = []
    drawing_unit: str | None = None

    try:
        text = content_bytes.decode("latin-1", errors="replace")
    except Exception:
        return [], None

    lines = text.splitlines()
    n = len(lines)
    i = 0
    in_header = False
    in_entities = False
    insunits_pending = False
    current_entity: str | None = None

    while i < n - 1:
        try:
            gc_raw = lines[i].strip()
            value = lines[i + 1].strip()
        except IndexError:
            break
        i += 2

        try:
            gc = int(gc_raw)
        except ValueError:
            continue

        if gc == 0 and value == "SECTION":
            current_entity = None
            if i < n - 1 and lines[i].strip() == "2":
                sname = lines[i + 1].strip().upper()
                in_header = sname == "HEADER"
                in_entities = sname in ("ENTITIES", "BLOCKS")
                i += 2
        elif gc == 0 and value in ("ENDSEC", "EOF"):
            current_entity = None
            in_header = False
            in_entities = False
        elif gc == 9 and value == "$INSUNITS" and in_header:
            insunits_pending = True
        elif gc == 70 and insunits_pending:
            insunits_pending = False
            try:
                drawing_unit = _DXF_INSUNITS_UNIT_MAP.get(int(value))
            except ValueError:
                pass
        elif gc == 0 and in_entities:
            current_entity = value if value in _TEXT_ENTITIES else None
        elif current_entity in _TEXT_ENTITIES and gc in (1, 3):
            tok = value
            if current_entity == "DIMENSION" and tok == "<>":
                continue  # auto-measured value, no semantic text
            # Strip MTEXT formatting codes
            tok = _MTEXT_FORMAT_RE.sub(" ", tok)
            tok = tok.replace("{", " ").replace("}", " ")
            tok = " ".join(tok.split())
            if tok:
                text_tokens.append(tok)

    return text_tokens, drawing_unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extension_ok(file_name: str) -> bool:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    return ext in _ALLOWED_EXTENSIONS


def _detection_to_out(d: NormalizedDetection) -> DetectionOut:
    return DetectionOut(
        detection_id=d.detection_id,
        page=d.page,
        source_type=d.source_type.value,
        normalized_type=d.normalized_type.value,
        normalized_value=d.normalized_value,
        unit=d.unit,
        raw_text=d.raw_text,
        confidence=float(d.confidence),
        confidence_method=d.confidence_method.value,
        review_state=d.review_state.value,
        review_required=d.review_required,
        association_state=d.association_state.value,
        association_feature_id=d.association_feature_id,
        association_feature_type=d.association_feature_type.value,
        subtype=d.subtype,
        ambiguities=[
            {"kind": a.kind.value, "description": a.description}
            for a in d.ambiguities
        ],
    )


def _get_session(session_id: str) -> ExtractionSession:
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")
    return session


def _get_detection(session: ExtractionSession, detection_id: str) -> NormalizedDetection:
    for d in session.detections:
        if d.detection_id == detection_id:
            return d
    raise HTTPException(status_code=404, detail=f"Detection not found: {detection_id}")


def _infer_source_format(file_name: str) -> str:
    ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
    _MAP = {
        "pdf": "PDF", "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG",
        "tiff": "TIFF", "tif": "TIFF", "bmp": "BMP",
        "dxf": "DXF", "step": "STEP", "stp": "STEP",
        "iges": "IGES", "igs": "IGES",
    }
    return _MAP.get(ext, "UNKNOWN")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_drawing(req: AnalyzeRequest) -> AnalyzeResponse:
    """Analyze a drawing and create an extraction session.

    Drawing bytes are decoded, validated, and processed.
    Content is NEVER logged or persisted beyond this session.
    """
    # Security: extension check
    if not _extension_ok(req.file_name):
        raise HTTPException(
            status_code=422,
            detail=f"File type not allowed: {req.file_name}",
        )

    # Decode content (already validated by Pydantic)
    try:
        content = base64.b64decode(req.content_b64, validate=True)
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Invalid base64 content") from exc

    # Security: size gate (belt-and-suspenders after Pydantic validator)
    if len(content) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File exceeds maximum size of {_MAX_FILE_BYTES // (1024*1024)} MB",
        )

    source_format = _infer_source_format(req.file_name)

    # Create extraction session — bytes NOT stored in session
    session = create_session(
        source_id=req.source_id,
        source_format=source_format,
        title_block_unit=req.title_block_unit,
        notes=req.notes,
        drawing_standard=req.drawing_standard,
        material_raw=req.material_raw,
        general_tolerance_texts=req.notes,
    )

    # For DXF files: extract text tokens and unit directly from the DXF bytes
    if source_format == "DXF":
        dxf_tokens, dxf_unit = _extract_dxf_annotations(content)
        # Merge DXF-extracted tokens with any notes provided
        all_tokens = dxf_tokens + (req.notes or [])
        if all_tokens:
            token_detections = run_token_extraction(
                all_tokens,
                source_type=DetectionSourceType.DXF,
                page=1,
            )
            session.detections.extend(token_detections)
        # Apply DXF unit if session has no declared unit yet
        if dxf_unit is not None and session.detected_unit is None:
            session.detected_unit = dxf_unit
            # Remove UNIT_NOT_DECLARED warning since we now have a unit
            session.extraction_warnings = [
                w for w in session.extraction_warnings
                if w != "UNIT_NOT_DECLARED"
            ]
        elif dxf_unit is None and not dxf_tokens and not req.notes:
            # No annotations and no unit — be explicit
            if "NO_ANNOTATIONS_FOUND" not in session.extraction_warnings:
                session.extraction_warnings.append("NO_ANNOTATIONS_FOUND")
    else:
        # Non-DXF: run token extraction on note texts
        if req.notes:
            token_detections = run_token_extraction(
                req.notes,
                source_type=DetectionSourceType.VECTOR_PDF,
                page=1,
            )
            session.detections.extend(token_detections)

    _SESSIONS[session.session_id] = session

    status = "PARTIAL" if session.extraction_warnings else "VALID"

    return AnalyzeResponse(
        session_id=session.session_id,
        source_id=session.source_id,
        status=status,
        detection_count=len(session.detections),
        review_required_count=session.review_required_count,
        detected_unit=session.detected_unit,
        ocr_available=session.ocr_available,
        warnings=session.extraction_warnings,
        disclaimer=DISCLAIMER,
    )


@router.get("/{session_id}/detections", response_model=DetectionsResponse)
async def get_detections(session_id: str) -> DetectionsResponse:
    """Return all extracted detections for a session."""
    session = _get_session(session_id)
    return DetectionsResponse(
        session_id=session_id,
        detections=[_detection_to_out(d) for d in session.detections],
        total=len(session.detections),
        review_required_count=session.review_required_count,
        confirmed_count=session.confirmed_count,
        disclaimer=DISCLAIMER,
    )


@router.get("/{session_id}/requirements", response_model=RequirementsResponse)
async def get_requirements(session_id: str) -> RequirementsResponse:
    """Return confirmed requirements ready for Drawing-to-Process handoff.

    Unconfirmed REVIEW_REQUIRED items are excluded from this response.
    They must be confirmed before being used in process planning.
    UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO
    """
    session = _get_session(session_id)
    confirmed = [d for d in session.detections if d.review_state == ReviewState.CONFIRMED]

    mat = session.material_outcome
    gen_tol = session.general_tolerance

    return RequirementsResponse(
        session_id=session_id,
        source_id=session.source_id,
        detected_unit=session.detected_unit,
        material_status=mat.status.value if mat else None,
        material_matched_id=mat.matched_id if mat else None,
        general_tolerance_standard=gen_tol.standard if gen_tol else None,
        general_tolerance_linear_mm=(
            float(gen_tol.linear_tolerance_mm)
            if gen_tol and gen_tol.linear_tolerance_mm
            else None
        ),
        confirmed_detections=[_detection_to_out(d) for d in confirmed],
        unconfirmed_review_required=session.review_required_count,
        disclaimer=DISCLAIMER,
    )


@router.post(
    "/{session_id}/detections/{detection_id}/confirm",
    response_model=ActionResponse,
)
async def confirm_detection(
    session_id: str,
    detection_id: str,
    req: ConfirmRequest,
) -> ActionResponse:
    """Engineer confirms a detection.

    Optionally override the value, unit, or feature association.
    UNCERTAIN_EXTRACTION_AUTO_APPROVED=NO — only engineer action confirms.
    """
    session = _get_session(session_id)
    detection = _get_detection(session, detection_id)

    detection.review_state = ReviewState.CONFIRMED
    detection.confidence_method = ParserConfidence.USER_CONFIRMED
    from decimal import Decimal
    detection.confidence = Decimal("1.00")

    if req.confirmed_value is not None:
        detection.normalized_value = req.confirmed_value
    if req.confirmed_unit is not None:
        detection.unit = req.confirmed_unit
    if req.confirmed_feature_id is not None:
        detection.association_feature_id = req.confirmed_feature_id
        detection.association_state = AssociationState.USER_MATCHED

    return ActionResponse(
        detection_id=detection_id,
        review_state=ReviewState.CONFIRMED.value,
        message="Detection confirmed by engineer",
        disclaimer=DISCLAIMER,
    )


@router.post(
    "/{session_id}/detections/{detection_id}/edit",
    response_model=ActionResponse,
)
async def edit_detection(
    session_id: str,
    detection_id: str,
    req: EditRequest,
) -> ActionResponse:
    """Engineer edits a detection value — resets to PENDING for re-review."""
    session = _get_session(session_id)
    detection = _get_detection(session, detection_id)

    detection.normalized_value = req.new_value
    if req.new_unit is not None:
        detection.unit = req.new_unit
    detection.review_state = ReviewState.EDITED
    detection.confidence_method = ParserConfidence.USER_CONFIRMED
    from decimal import Decimal
    detection.confidence = Decimal("1.00")

    return ActionResponse(
        detection_id=detection_id,
        review_state=ReviewState.EDITED.value,
        message="Detection edited by engineer; re-confirm to use in planning",
        disclaimer=DISCLAIMER,
    )


@router.post(
    "/{session_id}/detections/{detection_id}/reject",
    response_model=ActionResponse,
)
async def reject_detection(
    session_id: str,
    detection_id: str,
) -> ActionResponse:
    """Engineer rejects a detection — excluded from requirements."""
    session = _get_session(session_id)
    detection = _get_detection(session, detection_id)

    detection.review_state = ReviewState.REJECTED

    return ActionResponse(
        detection_id=detection_id,
        review_state=ReviewState.REJECTED.value,
        message="Detection rejected by engineer",
        disclaimer=DISCLAIMER,
    )


@router.post(
    "/{session_id}/detections/{detection_id}/associate",
    response_model=ActionResponse,
)
async def associate_detection(
    session_id: str,
    detection_id: str,
    req: AssociateRequest,
) -> ActionResponse:
    """Engineer assigns a feature association to a detection."""
    session = _get_session(session_id)
    detection = _get_detection(session, detection_id)

    detection.association_feature_id = req.feature_id
    detection.association_state = AssociationState.USER_MATCHED

    if req.feature_type:
        try:
            detection.association_feature_type = FeatureType(req.feature_type)
        except ValueError:
            pass  # keep existing

    return ActionResponse(
        detection_id=detection_id,
        review_state=detection.review_state.value,
        message=f"Detection associated with feature: {req.feature_id}",
        disclaimer=DISCLAIMER,
    )
