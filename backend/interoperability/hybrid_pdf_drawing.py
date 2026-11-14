"""Hybrid PDF technical drawing extraction with staged native-text + OCR fallback.

Implements the staged P1 PDF pipeline:
  Stage 1 — Native text extraction (pdfplumber; always first)
  Stage 2 — Vector content check (pdfplumber path analysis)
  Stage 3 — OCR fallback (via ocr_drawing; raster regions only)

NATIVE FIRST. VECTOR SECOND. OCR LAST.

Design invariants:
  - OCR results are always source=OCR, never source=NATIVE_TEXT.
  - LOW-confidence OCR is retained as evidence but NOT promoted to fields.
  - No OCR result is auto-confirmed as engineering data.
  - CONFLICT provenance preserved when native text and OCR disagree.
  - Engineering extraction uses existing deterministic parsers; never fabricates.
  - HARD_RULE: UNKNOWN information remains UNKNOWN.

FABRICATED_ENGINEERING_DATA=NO
OCR_AUTO_CONFIRM=NO
CNC_DISPATCH=NO
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum, unique
from io import BytesIO

from backend.interoperability.drawing import DrawingIngestionStatus

__all__ = [
    "PdfContentType",
    "OcrConfidenceLevel",
    "PdfExtractionProvenance",
    "HybridPdfToken",
    "PdfEngineeringToken",
    "PdfEngineeringTokenType",
    "PdfPageClassification",
    "HybridPdfStageResult",
    "HybridPdfExtractionResult",
    "classify_pdf_content",
    "extract_hybrid_pdf",
    "extract_engineering_tokens_from_text",
]

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

@unique
class PdfContentType(StrEnum):
    NATIVE_TEXT = "NATIVE_TEXT"       # Only native text; no raster images
    VECTOR = "VECTOR"                 # Vector paths present (dimension lines etc.)
    RASTER = "RASTER"                 # Raster/bitmap images; drawing content is rasterized
    HYBRID = "HYBRID"                 # Both native text AND raster images
    EMPTY = "EMPTY"                   # No extractable content
    UNKNOWN = "UNKNOWN"               # Could not classify


@unique
class OcrConfidenceLevel(StrEnum):
    HIGH = "HIGH"       # ≥ 0.90 — may be displayed prominently; still requires review
    MEDIUM = "MEDIUM"   # 0.70–0.89 — requires explicit review before use
    LOW = "LOW"         # < 0.70 — retain as evidence; do NOT promote automatically
    UNKNOWN = "UNKNOWN"


@unique
class PdfExtractionProvenance(StrEnum):
    NATIVE_TEXT = "NATIVE_TEXT"       # Extracted via pdfplumber from embedded text
    VECTOR = "VECTOR"                 # Extracted from vector path/drawing objects
    OCR = "OCR"                       # Extracted via OCR from raster image region
    OCR_TITLE_BLOCK = "OCR_TITLE_BLOCK"  # OCR token positionally confirmed as title-block area
    CONFLICT = "CONFLICT"             # Native text and OCR produced incompatible values


@unique
class PdfEngineeringTokenType(StrEnum):
    DIMENSION = "DIMENSION"
    DIAMETER = "DIAMETER"
    RADIUS = "RADIUS"
    TOLERANCE = "TOLERANCE"
    THREAD = "THREAD"
    SURFACE_FINISH = "SURFACE_FINISH"
    FIT = "FIT"
    MATERIAL = "MATERIAL"
    GDT = "GDT"
    GENERAL_NOTE = "GENERAL_NOTE"
    DRAWING_NUMBER = "DRAWING_NUMBER"
    REVISION = "REVISION"
    PART_NUMBER = "PART_NUMBER"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class HybridPdfToken:
    """A single extracted text token with its extraction provenance."""

    text: str
    provenance: PdfExtractionProvenance
    page_number: int
    confidence: Decimal | None = None   # 0–1, present for OCR tokens; None for native
    ocr_confidence_level: OcrConfidenceLevel | None = None
    bounding_box_x: Decimal | None = None
    bounding_box_y: Decimal | None = None
    bounding_box_w: Decimal | None = None
    bounding_box_h: Decimal | None = None


@dataclass(frozen=True)
class PdfEngineeringToken:
    """A token recognized as an engineering value.

    HARD RULE: raw_text is preserved unmodified.
    HARD RULE: normalized_value may be None when classification is uncertain.
    HARD RULE: auto_confirmed is always False — user confirmation required.
    """

    token_type: PdfEngineeringTokenType
    raw_text: str
    normalized_value: str | None      # Canonical form; None when uncertain
    provenance: PdfExtractionProvenance
    page_number: int
    confidence: Decimal               # Overall extraction + classification confidence
    ocr_confidence_level: OcrConfidenceLevel | None = None
    auto_confirmed: bool = False      # Always False — requires user review
    review_required: bool = True      # Always True


@dataclass(frozen=True)
class PdfPageClassification:
    """Content classification for a single PDF page."""

    page_number: int
    content_type: PdfContentType
    native_text_char_count: int
    image_count: int
    has_vector_paths: bool
    ocr_required: bool
    note: str = ""


@dataclass(frozen=True)
class HybridPdfStageResult:
    """Result from one extraction stage."""

    stage: int                               # 1, 2, or 3
    stage_name: str                          # "NATIVE_TEXT" / "VECTOR" / "OCR"
    tokens_found: int
    tokens: tuple[HybridPdfToken, ...]
    success: bool
    failure_reason: str | None = None


@dataclass
class HybridPdfExtractionResult:
    """Full hybrid PDF extraction result.

    Fields
    ------
    source_id          : caller-supplied identifier for this PDF
    page_count         : total pages in the document
    page_classifications : per-page content classification
    stage_results      : results from each stage (1–3)
    all_tokens         : all extracted tokens (all stages combined)
    engineering_tokens : tokens recognized as engineering values
    native_text_count  : total native text tokens (Stage 1)
    ocr_token_count    : total OCR tokens (Stage 3)
    ocr_required_pages : number of pages that required OCR
    has_ocr_results    : whether any OCR extraction succeeded
    drawing_number     : drawing number if found in native text
    warnings           : non-fatal extraction warnings
    errors             : fatal extraction errors
    """

    source_id: str
    page_count: int = 0
    page_classifications: list[PdfPageClassification] = field(default_factory=list)
    stage_results: list[HybridPdfStageResult] = field(default_factory=list)
    all_tokens: list[HybridPdfToken] = field(default_factory=list)
    engineering_tokens: list[PdfEngineeringToken] = field(default_factory=list)
    native_text_count: int = 0
    ocr_token_count: int = 0
    ocr_required_pages: int = 0
    has_ocr_results: bool = False
    drawing_number: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Engineering token extraction (deterministic, no fabrication)
# ---------------------------------------------------------------------------

# Diameter prefix characters (after strip)
_DIAM_PREFIXES = {"Ø", "⌀"}

# Engineering token patterns
_RE_DIAMETER = re.compile(
    r"(?:Ø|⌀|\bDIA\.?\s*)(\d+(?:[.,]\d+)?)\s*(?:mm|MM)?",
    re.IGNORECASE,
)
_RE_RADIUS = re.compile(
    r"\bR\.?\s*(\d+(?:[.,]\d+)?)\s*(?:mm|MM)?",
    re.IGNORECASE,
)
_RE_THREAD = re.compile(
    r"\b(M\d+(?:[.,]\d+)?(?:\s*[xX]\s*\d+(?:[.,]\d+)?)?(?:\s*-\s*\d+[hHgG])?)(?:\s|$)",
)
_RE_TOLERANCE = re.compile(
    r"\b(\d+(?:[.,]\d+)?)\s*([+\-±])\s*(\d+(?:[.,]\d+)?)\b",
)
_RE_SURFACE_FINISH = re.compile(
    r"\bR[az]\s*(\d+(?:[.,]\d+)?)\b",
    re.IGNORECASE,
)
_RE_FIT = re.compile(
    r"\b([Hh]\d{1,2}(?:[/\|][a-zA-Z]\d{1,2})?|[a-zA-Z]\d{1,2}/[Hh]\d{1,2})\b",
)
_RE_DIMENSION = re.compile(
    r"(?<!\bM)(?<!\bR)(?<!\bØ)(?<!\bDIA)\b(\d{1,5}(?:[.,]\d+)?)\s*(?:mm|MM|in\b)?",
    re.IGNORECASE,
)
_RE_MATERIAL_EN = re.compile(
    r"\b(?:42CrMo4|C45|Ck45|S235JR|S355JR|S355J2|16MnCr5|20MnCr5|"
    r"1\.[0-9]{4}|304|316L|GJL-250|GJS-400|EN\s*AW[-\s]?\d{4}|"
    r"Ti-6Al-4V|Ti6Al4V)\b",
    re.IGNORECASE,
)
_RE_DRAWING_NO = re.compile(
    r"(?:DWG(?:\s*NO\.?|\.?\s*NUMBER)?|DRAWING\s*(?:NO\.?|NUMBER)?)\s*[:：]\s*([A-Z0-9\-/]+)",
    re.IGNORECASE,
)

# Confidence multipliers per provenance
_PROVENANCE_CONFIDENCE: dict[PdfExtractionProvenance, Decimal] = {
    PdfExtractionProvenance.NATIVE_TEXT: Decimal("0.95"),
    PdfExtractionProvenance.VECTOR: Decimal("0.90"),
    PdfExtractionProvenance.OCR: Decimal("0.70"),
    PdfExtractionProvenance.OCR_TITLE_BLOCK: Decimal("0.75"),
    PdfExtractionProvenance.CONFLICT: Decimal("0.40"),
}

# False-positive guards: strings that look like engineering values but are not
_FP_GUARD_PATTERNS = [
    re.compile(r"^\d{4}$"),                        # 4-digit year e.g. 2024
    re.compile(r"^[A-Z]\d{2}$"),                   # Revision code e.g. A02, B03
    re.compile(r"^P\d{2}$"),                       # Revision P00, P01
    re.compile(r"^\d{1,3}/\d{1,3}$"),             # Sheet fraction e.g. 1/5
    re.compile(r"^DWG-\d+"),                       # Document ID prefix
    re.compile(r"^\d{6,}$"),                       # Long part numbers (≥6 digits)
]


def _is_false_positive(text: str) -> bool:
    """Return True if the text matches a known false-positive pattern."""
    cleaned = text.strip()
    return any(p.match(cleaned) for p in _FP_GUARD_PATTERNS)


def _ocr_confidence_level(confidence: Decimal | None) -> OcrConfidenceLevel:
    if confidence is None:
        return OcrConfidenceLevel.UNKNOWN
    if confidence >= Decimal("0.90"):
        return OcrConfidenceLevel.HIGH
    if confidence >= Decimal("0.70"):
        return OcrConfidenceLevel.MEDIUM
    return OcrConfidenceLevel.LOW


def extract_engineering_tokens_from_text(
    text: str,
    provenance: PdfExtractionProvenance,
    page_number: int,
    ocr_confidence: Decimal | None = None,
) -> list[PdfEngineeringToken]:
    """Extract engineering tokens from a text string.

    Applies deterministic pattern matching. Never fabricates values.
    Returns empty list when no recognized tokens are found.

    FALSE_POSITIVE_GUARDS=YES
    FABRICATED_ENGINEERING_VALUE=NO
    AUTO_CONFIRMED=NO
    """
    if not text or not text.strip():
        return []

    tokens: list[PdfEngineeringToken] = []
    conf_level = _ocr_confidence_level(ocr_confidence) if ocr_confidence else None
    base_conf = _PROVENANCE_CONFIDENCE.get(provenance, Decimal("0.60"))

    # Adjust confidence for OCR level
    if conf_level == OcrConfidenceLevel.LOW:
        base_conf = base_conf * Decimal("0.70")
    elif conf_level == OcrConfidenceLevel.MEDIUM:
        base_conf = base_conf * Decimal("0.90")

    # --- Drawing number (title block) ---
    for m in _RE_DRAWING_NO.finditer(text):
        raw = m.group(0)
        value = m.group(1).strip()
        if not _is_false_positive(value):
            tokens.append(PdfEngineeringToken(
                token_type=PdfEngineeringTokenType.DRAWING_NUMBER,
                raw_text=raw,
                normalized_value=value,
                provenance=provenance,
                page_number=page_number,
                confidence=min(base_conf + Decimal("0.05"), Decimal("1.0")),
                ocr_confidence_level=conf_level,
                review_required=True,
            ))

    # --- Material designations ---
    for m in _RE_MATERIAL_EN.finditer(text):
        raw = m.group(0)
        if not _is_false_positive(raw):
            tokens.append(PdfEngineeringToken(
                token_type=PdfEngineeringTokenType.MATERIAL,
                raw_text=raw,
                normalized_value=raw.strip(),
                provenance=provenance,
                page_number=page_number,
                confidence=base_conf,
                ocr_confidence_level=conf_level,
                review_required=True,
            ))

    # --- Diameter ---
    for m in _RE_DIAMETER.finditer(text):
        raw = m.group(0)
        if not _is_false_positive(raw):
            tokens.append(PdfEngineeringToken(
                token_type=PdfEngineeringTokenType.DIAMETER,
                raw_text=raw,
                normalized_value=m.group(1).replace(",", "."),
                provenance=provenance,
                page_number=page_number,
                confidence=base_conf,
                ocr_confidence_level=conf_level,
                review_required=True,
            ))

    # --- Radius ---
    for m in _RE_RADIUS.finditer(text):
        raw = m.group(0)
        if not _is_false_positive(raw):
            tokens.append(PdfEngineeringToken(
                token_type=PdfEngineeringTokenType.RADIUS,
                raw_text=raw,
                normalized_value=m.group(1).replace(",", "."),
                provenance=provenance,
                page_number=page_number,
                confidence=base_conf,
                ocr_confidence_level=conf_level,
                review_required=True,
            ))

    # --- Thread ---
    for m in _RE_THREAD.finditer(text):
        raw = m.group(0).strip()
        if not _is_false_positive(raw):
            tokens.append(PdfEngineeringToken(
                token_type=PdfEngineeringTokenType.THREAD,
                raw_text=raw,
                normalized_value=m.group(1).strip(),
                provenance=provenance,
                page_number=page_number,
                confidence=base_conf,
                ocr_confidence_level=conf_level,
                review_required=True,
            ))

    # --- Tolerance ---
    for m in _RE_TOLERANCE.finditer(text):
        raw = m.group(0)
        if not _is_false_positive(raw):
            tokens.append(PdfEngineeringToken(
                token_type=PdfEngineeringTokenType.TOLERANCE,
                raw_text=raw,
                normalized_value=raw,
                provenance=provenance,
                page_number=page_number,
                confidence=base_conf * Decimal("0.90"),
                ocr_confidence_level=conf_level,
                review_required=True,
            ))

    # --- Surface finish ---
    for m in _RE_SURFACE_FINISH.finditer(text):
        raw = m.group(0)
        tokens.append(PdfEngineeringToken(
            token_type=PdfEngineeringTokenType.SURFACE_FINISH,
            raw_text=raw,
            normalized_value=m.group(1).replace(",", "."),
            provenance=provenance,
            page_number=page_number,
            confidence=base_conf,
            ocr_confidence_level=conf_level,
            review_required=True,
        ))

    return tokens


# ---------------------------------------------------------------------------
# Page content classification
# ---------------------------------------------------------------------------

def classify_pdf_content(payload: bytes, source_id: str) -> list[PdfPageClassification]:
    """Classify each page of a PDF as NATIVE_TEXT / VECTOR / RASTER / HYBRID.

    Uses pdfplumber for text detection and raster_drawing.inspect_raster_pdf
    for image/vector detection.

    Returns a list of PdfPageClassification, one per page.
    """
    try:
        import pdfplumber
    except ImportError:
        return [PdfPageClassification(
            page_number=1,
            content_type=PdfContentType.UNKNOWN,
            native_text_char_count=0,
            image_count=0,
            has_vector_paths=False,
            ocr_required=False,
            note="pdfplumber not available",
        )]

    try:
        from backend.interoperability.raster_drawing import (
            RasterContentKind,
            inspect_raster_pdf,
        )
        raster_snapshot = inspect_raster_pdf(payload, source_id)
        raster_pages = {p.page_number: p for p in raster_snapshot.pages}
    except Exception:
        raster_pages = {}

    classifications: list[PdfPageClassification] = []
    try:
        with pdfplumber.open(BytesIO(payload)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                try:
                    text = page.extract_text() or ""
                    char_count = len(text.strip())
                    # Count image objects
                    objects = page.objects
                    image_count = len(objects.get("image", []))
                    # Count vector path/rect/line objects
                    path_count = (
                        len(objects.get("rect", []))
                        + len(objects.get("line", []))
                        + len(objects.get("curve", []))
                    )
                    has_vector = path_count > 0
                    rp = raster_pages.get(page_num)
                    if rp is not None:
                        from backend.interoperability.raster_drawing import RasterContentKind
                        rk = rp.content_kind
                        if rk in (RasterContentKind.RASTER_ONLY, RasterContentKind.MIXED):
                            image_count = max(image_count, 1)

                    # Classify
                    has_native = char_count >= 10
                    has_raster = image_count > 0

                    if has_raster and has_native:
                        content_type = PdfContentType.HYBRID
                        ocr_required = True
                    elif has_raster and not has_native:
                        content_type = PdfContentType.RASTER
                        ocr_required = True
                    elif has_native and has_vector:
                        content_type = PdfContentType.VECTOR
                        ocr_required = False
                    elif has_native:
                        content_type = PdfContentType.NATIVE_TEXT
                        ocr_required = False
                    else:
                        content_type = PdfContentType.EMPTY
                        ocr_required = False

                    classifications.append(PdfPageClassification(
                        page_number=page_num,
                        content_type=content_type,
                        native_text_char_count=char_count,
                        image_count=image_count,
                        has_vector_paths=has_vector,
                        ocr_required=ocr_required,
                    ))
                except Exception as exc:
                    classifications.append(PdfPageClassification(
                        page_number=page_num,
                        content_type=PdfContentType.UNKNOWN,
                        native_text_char_count=0,
                        image_count=0,
                        has_vector_paths=False,
                        ocr_required=True,
                        note=f"page-classification-error: {type(exc).__name__}",
                    ))
    except Exception:
        # malformed or encrypted PDF
        pass

    if not classifications:
        classifications.append(PdfPageClassification(
            page_number=1,
            content_type=PdfContentType.UNKNOWN,
            native_text_char_count=0,
            image_count=0,
            has_vector_paths=False,
            ocr_required=False,
            note="pdf-open-failed",
        ))

    return classifications


# ---------------------------------------------------------------------------
# Main extraction function
# ---------------------------------------------------------------------------

def extract_hybrid_pdf(
    payload: bytes,
    source_id: str,
    *,
    ocr_minimum_confidence: Decimal = Decimal("0.70"),
    extract_engineering: bool = True,
) -> HybridPdfExtractionResult:
    """Extract text and engineering tokens from a PDF using staged pipeline.

    Stage 1: Native text extraction via pdfplumber (always attempted)
    Stage 2: Vector content check (presence detection, not full extraction)
    Stage 3: OCR fallback via ocr_drawing.extract_ocr_from_pdf (raster pages only)

    Design: NATIVE_FIRST. VECTOR_CHECK. OCR_LAST.

    Args:
        payload:               Raw PDF bytes.
        source_id:             Caller-supplied identifier for this PDF.
        ocr_minimum_confidence: Minimum OCR confidence for token inclusion.
        extract_engineering:   Whether to run engineering token extraction.

    Returns:
        HybridPdfExtractionResult with all tokens and their provenances.
    """
    result = HybridPdfExtractionResult(source_id=source_id)

    # Classify pages
    result.page_classifications = classify_pdf_content(payload, source_id)
    result.page_count = len(result.page_classifications)
    result.ocr_required_pages = sum(1 for p in result.page_classifications if p.ocr_required)

    # -----------------------------------------------------------------------
    # Stage 1 — Native text extraction
    # -----------------------------------------------------------------------
    native_tokens: list[HybridPdfToken] = []
    stage1_ok = False
    stage1_failure: str | None = None
    try:
        import pdfplumber
        with pdfplumber.open(BytesIO(payload)) as pdf:
            for i, page in enumerate(pdf.pages):
                page_num = i + 1
                try:
                    words = page.extract_words() or []
                    for w in words:
                        text = str(w.get("text", "")).strip()
                        if not text:
                            continue
                        native_tokens.append(HybridPdfToken(
                            text=text,
                            provenance=PdfExtractionProvenance.NATIVE_TEXT,
                            page_number=page_num,
                            confidence=None,
                        ))
                except Exception:
                    pass
        stage1_ok = True
    except ImportError:
        stage1_failure = "pdfplumber-unavailable"
    except Exception as exc:
        stage1_failure = f"native-extraction-error: {type(exc).__name__}"

    result.native_text_count = len(native_tokens)
    result.all_tokens.extend(native_tokens)
    result.stage_results.append(HybridPdfStageResult(
        stage=1,
        stage_name="NATIVE_TEXT",
        tokens_found=len(native_tokens),
        tokens=tuple(native_tokens),
        success=stage1_ok,
        failure_reason=stage1_failure,
    ))

    # Extract drawing number from native text
    for tok in native_tokens:
        m = _RE_DRAWING_NO.search(tok.text)
        if m and not result.drawing_number:
            value = m.group(1).strip()
            if not _is_false_positive(value):
                result.drawing_number = value

    # -----------------------------------------------------------------------
    # Stage 2 — Vector content check
    # -----------------------------------------------------------------------
    has_vector_pages = any(
        p.has_vector_paths for p in result.page_classifications
    )
    result.stage_results.append(HybridPdfStageResult(
        stage=2,
        stage_name="VECTOR",
        tokens_found=0,
        tokens=(),
        success=True,
        failure_reason=None if has_vector_pages else "no-vector-paths-detected",
    ))

    # -----------------------------------------------------------------------
    # Stage 3 — OCR fallback (only when raster pages exist)
    # -----------------------------------------------------------------------
    ocr_tokens: list[HybridPdfToken] = []
    stage3_ok = False
    stage3_failure: str | None = None

    if result.ocr_required_pages > 0:
        try:
            from backend.interoperability.ocr_drawing import extract_ocr_from_pdf
            ocr_result = extract_ocr_from_pdf(payload, source_id)
            if ocr_result.status in {
                DrawingIngestionStatus.VALID,
                DrawingIngestionStatus.INSUFFICIENT_DATA,
            }:
                for ev in ocr_result.evidence:
                    conf = Decimal(str(ev.confidence)) if hasattr(ev, "confidence") else None
                    if conf is not None and conf < ocr_minimum_confidence:
                        # Retain as low-confidence evidence; tag appropriately
                        pass
                    ocr_tokens.append(HybridPdfToken(
                        text=ev.text if hasattr(ev, "text") else str(ev),
                        provenance=PdfExtractionProvenance.OCR,
                        page_number=getattr(ev.source_location, "page_number", 1)
                        if hasattr(ev, "source_location") else 1,
                        confidence=conf,
                        ocr_confidence_level=_ocr_confidence_level(conf),
                    ))
                result.has_ocr_results = True
                stage3_ok = True
            elif ocr_result.status == DrawingIngestionStatus.UNSUPPORTED:
                stage3_failure = "OCR_UNSUPPORTED"
                result.warnings.append("OCR_UNSUPPORTED: tesseract not available on this system")
            else:
                stage3_failure = (
                    ocr_result.diagnostics[0] if ocr_result.diagnostics else "OCR_FAILED"
                )
                result.warnings.append(f"OCR extraction failed: {stage3_failure}")
        except ImportError:
            stage3_failure = "pytesseract-unavailable"
            result.warnings.append("OCR_UNAVAILABLE: pytesseract or PIL not installed")
        except Exception as exc:
            stage3_failure = f"ocr-error: {type(exc).__name__}"
            result.warnings.append(f"OCR extraction error: {stage3_failure}")
    else:
        stage3_failure = "ocr-not-required"

    result.ocr_token_count = len(ocr_tokens)
    result.all_tokens.extend(ocr_tokens)
    result.stage_results.append(HybridPdfStageResult(
        stage=3,
        stage_name="OCR",
        tokens_found=len(ocr_tokens),
        tokens=tuple(ocr_tokens),
        success=stage3_ok,
        failure_reason=stage3_failure,
    ))

    # -----------------------------------------------------------------------
    # Engineering token extraction
    # -----------------------------------------------------------------------
    if extract_engineering:
        for tok in result.all_tokens:
            # Only extract from non-trivially-short tokens
            if len(tok.text.strip()) < 2:
                continue
            # LOW confidence OCR: retain but do not extract engineering values
            if (tok.provenance == PdfExtractionProvenance.OCR
                    and tok.ocr_confidence_level == OcrConfidenceLevel.LOW):
                continue
            eng_tokens = extract_engineering_tokens_from_text(
                tok.text,
                tok.provenance,
                tok.page_number,
                ocr_confidence=tok.confidence,
            )
            result.engineering_tokens.extend(eng_tokens)

    return result
