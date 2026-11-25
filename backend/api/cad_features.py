"""CAD Feature Recognition API — EPIC_04D Phase 2.

8 endpoints under /api/cad-features/:
  POST /analyze                           — upload CAD + trigger feature recognition
  GET  /{session_id}                      — session metadata
  GET  /{session_id}/features             — feature list (filterable)
  GET  /{session_id}/patterns             — feature patterns
  GET  /{session_id}/fusion               — drawing/CAD fusion result
  POST /{session_id}/features/{fid}/confirm         — confirm a feature
  POST /{session_id}/features/{fid}/reject           — reject a feature
  POST /{session_id}/associate-drawing    — manually link requirement → feature

Security:
  File size limit: 64 MB
  Extension whitelist: .stp .step .iges .igs .stl .obj .3mf .dxf
  Filename sanitization: path separators stripped
  Raw CAD bytes NEVER stored in session

FABRICATED_FEATURE=NO
CUSTOMER_CAD_COMMITTED=NO
"""

from __future__ import annotations

import base64
import hashlib
import pathlib
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from backend.interoperability.association import AnnotationType
from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeatureRecognitionResult,
    ManufacturingFeatureType,
    recognize_manufacturing_features,
)
from backend.interoperability.cad_fusion import (
    FusionResult,
    fuse_cad_with_drawing,
)

router = APIRouter(prefix="/api/cad-features", tags=["cad-features"])

# ---- Security limits ----
_MAX_FILE_BYTES = 64 * 1024 * 1024  # 64 MB
_ALLOWED_EXTENSIONS = frozenset({
    "stp", "step", "iges", "igs", "stl", "obj", "3mf", "dxf"
})

_RECOGNITION_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Session store (in-memory, no raw bytes)
# ---------------------------------------------------------------------------

@dataclass
class CadFeatureSession:
    session_id: str
    file_name: str
    format_id: str
    file_fingerprint: str  # SHA-256 of uploaded bytes
    entity_count: int
    unit: str
    recognition_result: ManufacturingFeatureRecognitionResult
    fusion_result: FusionResult | None
    drawing_session_id: str | None
    rejected_feature_ids: set[str]
    confirmed_feature_ids: set[str]
    created_at: datetime
    annotation_link_result: object | None = None  # DxfAnnotationLinkResult | None
    # P6 state — per-feature confirmed cutting params, clearance, NC candidates
    # P6 per-feature state maps (feature_id → result object)
    p6_confirmed_params: dict = field(default_factory=dict)
    p6_clearance_state: dict = field(default_factory=dict)
    p6_toolpath_cache: dict = field(default_factory=dict)
    p6_nc_candidates: dict = field(default_factory=dict)


_SESSIONS: dict[str, CadFeatureSession] = {}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AnalyzeRequest(BaseModel):
    file_name: str = Field(..., min_length=1, max_length=256)
    content_b64: str = Field(..., description="Base64-encoded CAD file bytes")
    source_id: str | None = Field(default=None, max_length=256)
    drawing_session_id: str | None = None

    @field_validator("file_name")
    @classmethod
    def _sanitize_filename(cls, v: str) -> str:
        name = pathlib.PurePosixPath(v).name
        if not name:
            raise ValueError("file_name must not be a directory path")
        return name

    @field_validator("content_b64")
    @classmethod
    def _validate_b64(cls, v: str) -> str:
        try:
            decoded = base64.b64decode(v, validate=True)
        except Exception as exc:
            raise ValueError("content_b64 must be valid base64") from exc
        if len(decoded) > _MAX_FILE_BYTES:
            mb = _MAX_FILE_BYTES // (1024 * 1024)
            raise ValueError(f"File exceeds maximum allowed size ({mb} MB)")
        return v


class ConfirmRequest(BaseModel):
    user_id: str = Field(default="engineer")


class RejectRequest(BaseModel):
    user_id: str = Field(default="engineer")
    reason: str | None = None


class FeatureDimensionConfirmRequest(BaseModel):
    """Engineer-supplied dimension confirmation (P3-A).

    HARD RULES:
      - depth_mm MUST be positive when supplied.
      - width_mm MUST be positive when supplied.
      - feature_type_override must be a valid ManufacturingFeatureType string.
      - Values are tagged USER_CONFIRMED — never reported as file-extracted data.
    """

    user_id: str = Field(default="engineer")
    feature_type_override: str | None = None
    depth_mm: float | None = None
    width_mm: float | None = None
    review_notes: str | None = Field(default=None, max_length=500)

    @field_validator("depth_mm")
    @classmethod
    def _depth_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("depth_mm must be positive")
        return v

    @field_validator("width_mm")
    @classmethod
    def _width_positive(cls, v: float | None) -> float | None:
        if v is not None and v <= 0:
            raise ValueError("width_mm must be positive")
        return v

    @field_validator("feature_type_override")
    @classmethod
    def _valid_type(cls, v: str | None) -> str | None:
        if v is not None:
            try:
                ManufacturingFeatureType(v)
            except ValueError as exc:
                raise ValueError(f"Unknown ManufacturingFeatureType: {v!r}") from exc
        return v


class AssociateDrawingRequest(BaseModel):
    requirement_id: str = Field(..., min_length=1)
    feature_id: str = Field(..., min_length=1)
    user_id: str = Field(default="engineer")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _detect_format(file_name: str) -> str:
    ext = pathlib.Path(file_name).suffix.lstrip(".").lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=f"File extension '.{ext}' is not supported. "
                   f"Allowed: {sorted(_ALLOWED_EXTENSIONS)}",
        )
    if ext in ("stp", "step"):
        return "STEP"
    if ext in ("iges", "igs"):
        return "IGES"
    if ext == "dxf":
        return "DXF"
    if ext == "stl":
        return "STL"
    if ext == "obj":
        return "OBJ"
    if ext == "3mf":
        return "3MF"
    return ext.upper()


def _get_session(session_id: str) -> CadFeatureSession:
    sess = _SESSIONS.get(session_id)
    if sess is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess


def _try_parse_iges_or_step(
    content_bytes: bytes, format_id: str, file_name: str
) -> ManufacturingFeatureRecognitionResult | None:
    """Attempt to parse IGES/STEP and run feature recognition."""
    if format_id == "IGES":
        try:
            from backend.interoperability.iges_mapping import map_iges_model
            from backend.interoperability.iges_parser import parse_iges_bytes
            from backend.interoperability.iges_topology_reconstruction import (
                reconstruct_iges_topology,
            )
            iges_model = parse_iges_bytes(content_bytes)
            mapping = map_iges_model(iges_model)
            doc_id = hashlib.sha256(content_bytes[:256]).hexdigest()[:16]
            if mapping.topology and mapping.geometry:
                return recognize_manufacturing_features(
                    mapping.topology, mapping.geometry, doc_id
                )
            # No B-Rep topology: use surface-group reconstruction to produce
            # PRECISION_BORE_CANDIDATE and PLANAR_FACE hints (SURFACE_HEURISTIC).
            recon = reconstruct_iges_topology(mapping, source_id=doc_id)
            if recon.feature_candidates:
                return ManufacturingFeatureRecognitionResult(
                    source_document_id=doc_id,
                    recognition_version=_RECOGNITION_VERSION,
                    features=tuple(recon.feature_candidates),
                    patterns=[],
                    accessibility={},
                    tool_reach={},
                    warnings=[
                        "IGES_SURFACE_HEURISTIC: features inferred from surface groups — "
                        "review required before use",
                        *recon.warnings,
                    ],
                    face_count=recon.surface_count,
                    body_count=max(recon.body_count, 0),
                )
        except Exception:
            pass

    if format_id == "STEP":
        # Phase A: gmsh OCC topology recognition (no pythonocc-core needed)
        try:
            from backend.step_brep.step_feature_recognizer import (
                recognize_features_from_bytes as _step_gmsh,
            )
            result = _step_gmsh(content_bytes, file_name)
            if result is not None:
                return result
        except Exception:
            pass

        # Fallback: attempt via pythonocc-core if available
        try:
            from backend.interoperability.adapters.step import StepTokenAdapter

            # Level 2 requires pythonocc-core; gracefully fails if absent
            adapter = StepTokenAdapter()
            adapter.ingest(content_bytes, pathlib.Path(file_name))
        except Exception:
            pass

    return None


def _run_feature_recognition_for_format(
    content_bytes: bytes,
    format_id: str,
    file_name: str,
) -> tuple[ManufacturingFeatureRecognitionResult, dict]:
    """Run format-specific feature recognition. Always returns (result, metadata).

    metadata keys (DXF only): entity_counts, geometry_entity_count,
    annotation_entity_count, block_insert_support.
    """
    from backend.interoperability.cad_feature_recognition import (
        ManufacturingFeatureRecognitionResult,
    )

    result = _try_parse_iges_or_step(content_bytes, format_id, file_name)
    if result is not None:
        return result, {}

    if format_id == "DXF":
        try:
            from backend.interoperability.cad_feature_recognition import (
                recognize_dxf_features,
            )
            from backend.interoperability.dxf_annotation_linker import (
                link_dxf_annotations,
            )
            entities, entity_counts = _parse_dxf_2d(content_bytes)
            feats = recognize_dxf_features(entities)
            annotations = _parse_dxf_annotations(content_bytes)
            annotation_link_result = link_dxf_annotations(annotations, feats)
            doc_id = hashlib.sha256(content_bytes[:256]).hexdigest()[:16]
            geom_count = sum(
                v for k, v in entity_counts.items()
                if k in _GEOMETRY_ENTITY_TYPES_CF
            )
            ann_count = sum(
                v for k, v in entity_counts.items()
                if k in _ANNOTATION_ENTITY_TYPES_CF
            )
            warnings = ["DXF 2D: depth unknown; all holes are candidates only"]
            if not feats and geom_count == 0:
                warnings.append("NO_GEOMETRY_ENTITIES_FOUND")
            dxf_meta = {
                "entity_counts": entity_counts,
                "geometry_entity_count": geom_count,
                "annotation_entity_count": ann_count,
                "block_insert_support": "DEFERRED",
                "annotation_link_result": annotation_link_result,
            }
            return ManufacturingFeatureRecognitionResult(
                source_document_id=doc_id,
                recognition_version=_RECOGNITION_VERSION,
                features=feats,
                patterns=[],
                accessibility={},
                tool_reach={},
                warnings=warnings,
                face_count=0,
                body_count=0,
            ), dxf_meta
        except Exception:
            pass

    # Fallback: empty result with warning
    doc_id = hashlib.sha256(content_bytes[:256]).hexdigest()[:16]
    return ManufacturingFeatureRecognitionResult(
        source_document_id=doc_id,
        recognition_version=_RECOGNITION_VERSION,
        features=[],
        patterns=[],
        accessibility={},
        tool_reach={},
        warnings=[
            f"{format_id}: feature recognition not available "
            "(IGES Level 2 B-Rep required; STEP needs pythonocc-core)"
        ],
        face_count=0,
        body_count=0,
    ), {}


_HISTOGRAM_ENTITY_TYPES = frozenset({
    "CIRCLE", "ARC", "LINE", "LWPOLYLINE", "POLYLINE",
    "ELLIPSE", "SPLINE", "INSERT", "BLOCK",
    "DIMENSION", "TEXT", "MTEXT",
})
_ANNOTATION_ENTITY_TYPES_CF = frozenset({
    "DIMENSION", "TEXT", "MTEXT", "LEADER", "MLEADER", "ATTDEF", "ATTRIB",
})
_GEOMETRY_ENTITY_TYPES_CF = frozenset({
    "CIRCLE", "ARC", "LINE", "LWPOLYLINE", "POLYLINE",
    "ELLIPSE", "SPLINE", "INSERT", "BLOCK",
})


def _parse_dxf_2d(content_bytes: bytes) -> tuple[list, dict]:
    """Extract 2D geometry entities from DXF bytes (pure Python).

    Returns (entities, entity_counts).
    entities: list[Dxf2dEntity] — CIRCLE, ARC, LWPOLYLINE, POLYLINE, ELLIPSE
    entity_counts: {entity_type: count} for histogram diagnostics

    BLOCK_INSERT_GEOMETRY_SUPPORT=DEFERRED — blocks are counted but not resolved.
    FABRICATED_GEOMETRY=NO
    """
    from backend.interoperability.cad_feature_recognition import Dxf2dEntity
    entities: list = []
    entity_counts: dict[str, int] = {}

    try:
        text = content_bytes.decode("latin-1", errors="replace")
        lines = text.splitlines()
        n = len(lines)
        i = 0
        in_entities = False

        while i < n - 1:
            code = lines[i].strip()
            val = lines[i + 1].strip() if i + 1 < n else ""
            i += 2

            if code == "0" and val == "SECTION":
                if i < n - 1 and lines[i].strip() == "2":
                    sname = lines[i + 1].strip().upper()
                    in_entities = sname in ("ENTITIES", "BLOCKS")
                    i += 2
                continue
            if code == "0" and val in ("ENDSEC", "EOF"):
                in_entities = False
                continue

            if code != "0" or not in_entities:
                continue

            etype = val.upper()
            if etype in _HISTOGRAM_ENTITY_TYPES:
                entity_counts[etype] = entity_counts.get(etype, 0) + 1

            if etype == "CIRCLE":
                cx = cy = r = 0.0
                layer = "0"
                while i < n - 1:
                    c2 = lines[i].strip()
                    v2 = lines[i + 1].strip() if i + 1 < n else ""
                    if c2 == "0":
                        break
                    i += 2
                    if c2 == "8":
                        layer = v2
                    elif c2 == "10":
                        try:
                            cx = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "20":
                        try:
                            cy = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "40":
                        try:
                            r = float(v2)
                        except ValueError:
                            pass
                if r > 0.0:
                    entities.append(Dxf2dEntity(
                        entity_type="CIRCLE", layer=layer,
                        center_x=cx, center_y=cy, radius=r,
                    ))

            elif etype == "ARC":
                cx = cy = r = sa = se = 0.0
                layer = "0"
                while i < n - 1:
                    c2 = lines[i].strip()
                    v2 = lines[i + 1].strip() if i + 1 < n else ""
                    if c2 == "0":
                        break
                    i += 2
                    if c2 == "8":
                        layer = v2
                    elif c2 == "10":
                        try:
                            cx = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "20":
                        try:
                            cy = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "40":
                        try:
                            r = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "50":
                        try:
                            sa = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "51":
                        try:
                            se = float(v2)
                        except ValueError:
                            pass
                if r > 0.0:
                    entities.append(Dxf2dEntity(
                        entity_type="ARC", layer=layer,
                        center_x=cx, center_y=cy, radius=r,
                        start_angle=sa, end_angle=se,
                    ))

            elif etype in ("LWPOLYLINE", "POLYLINE"):
                layer = "0"
                closed = False
                verts: list[tuple[float, float]] = []
                cur_x: float | None = None
                cur_y: float | None = None
                while i < n - 1:
                    c2 = lines[i].strip()
                    v2 = lines[i + 1].strip() if i + 1 < n else ""
                    if c2 == "0":
                        break
                    i += 2
                    if c2 == "8":
                        layer = v2
                    elif c2 == "70":
                        try:
                            closed = bool(int(v2) & 1)
                        except ValueError:
                            pass
                    elif c2 == "10":
                        if cur_x is not None and cur_y is not None:
                            verts.append((cur_x, cur_y))
                        try:
                            cur_x = float(v2)
                        except ValueError:
                            cur_x = None
                        cur_y = None
                    elif c2 == "20":
                        try:
                            cur_y = float(v2)
                        except ValueError:
                            pass
                if cur_x is not None and cur_y is not None:
                    verts.append((cur_x, cur_y))
                if verts:
                    entities.append(Dxf2dEntity(
                        entity_type=etype, layer=layer,
                        closed=closed, vertices=tuple(verts),
                    ))

            elif etype == "ELLIPSE":
                cx = cy = mx = my = 0.0
                ratio = 1.0
                layer = "0"
                while i < n - 1:
                    c2 = lines[i].strip()
                    v2 = lines[i + 1].strip() if i + 1 < n else ""
                    if c2 == "0":
                        break
                    i += 2
                    if c2 == "8":
                        layer = v2
                    elif c2 == "10":
                        try:
                            cx = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "20":
                        try:
                            cy = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "11":
                        try:
                            mx = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "21":
                        try:
                            my = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "40":
                        try:
                            ratio = float(v2)
                        except ValueError:
                            pass
                entities.append(Dxf2dEntity(
                    entity_type="ELLIPSE", layer=layer,
                    center_x=cx, center_y=cy,
                    major_x=mx, major_y=my, ratio=ratio,
                ))

    except Exception:
        pass

    return entities, entity_counts


def _parse_dxf_annotations(content_bytes: bytes) -> list:
    """Extract annotation entities with spatial coordinates from DXF bytes.

    Returns list[DxfAnnotation] for DIMENSION, TEXT, MTEXT entities.
    Only entities with at least one spatial coordinate are included.

    FABRICATED_ANNOTATION=NO
    """
    from backend.interoperability.dxf_annotation_linker import (
        DxfAnnotation,
        DxfAnnotationSource,
    )

    annotations: list[DxfAnnotation] = []
    ann_counter = 0

    try:
        text = content_bytes.decode("latin-1", errors="replace")
        lines = text.splitlines()
        n = len(lines)
        i = 0
        in_entities = False

        while i < n - 1:
            code = lines[i].strip()
            val = lines[i + 1].strip() if i + 1 < n else ""
            i += 2

            if code == "0" and val == "SECTION":
                if i < n - 1 and lines[i].strip() == "2":
                    sname = lines[i + 1].strip().upper()
                    in_entities = sname in ("ENTITIES", "BLOCKS")
                    i += 2
                continue
            if code == "0" and val in ("ENDSEC", "EOF"):
                in_entities = False
                continue
            if code != "0" or not in_entities:
                continue

            etype = val.upper()

            if etype == "DIMENSION":
                ann_text = ""
                handle = None
                layer = "0"
                ix = iy = None     # text midpoint (code 11/21)
                dp1x = dp1y = None  # definition point 1 (code 10/20)
                dp2x = dp2y = None  # definition point 2 (code 13/23)
                dim_type = 0
                while i < n - 1:
                    c2 = lines[i].strip()
                    v2 = lines[i + 1].strip() if i + 1 < n else ""
                    if c2 == "0":
                        break
                    i += 2
                    if c2 == "1":
                        ann_text = v2
                    elif c2 == "5":
                        handle = v2
                    elif c2 == "8":
                        layer = v2
                    elif c2 == "10":
                        try:
                            dp1x = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "20":
                        try:
                            dp1y = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "11":
                        try:
                            ix = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "21":
                        try:
                            iy = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "13":
                        try:
                            dp2x = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "23":
                        try:
                            dp2y = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "70":
                        try:
                            dim_type = int(v2) & 0x0F
                        except ValueError:
                            pass
                if dp1x is None and ix is None:
                    continue
                subtype = {0: "LINEAR", 1: "ALIGNED", 2: "ANGULAR", 3: "DIAMETRAL",
                           4: "RADIAL", 5: "ANGULAR3P", 6: "ORDINATE"}.get(dim_type, "LINEAR")
                ann_counter += 1
                annotations.append(DxfAnnotation(
                    annotation_id=f"ANN-{ann_counter:04d}",
                    source=DxfAnnotationSource.DIMENSION,
                    annotation_type=AnnotationType.DIMENSION,
                    text=ann_text,
                    subtype=subtype,
                    insertion_x=ix, insertion_y=iy,
                    defpoint1_x=dp1x, defpoint1_y=dp1y,
                    defpoint2_x=dp2x, defpoint2_y=dp2y,
                    layer=layer, handle=handle,
                ))

            elif etype in ("TEXT", "MTEXT"):
                ann_text = ""
                handle = None
                layer = "0"
                ix = iy = None
                while i < n - 1:
                    c2 = lines[i].strip()
                    v2 = lines[i + 1].strip() if i + 1 < n else ""
                    if c2 == "0":
                        break
                    i += 2
                    if c2 == "1":
                        ann_text = v2
                    elif c2 == "3":
                        ann_text = ann_text + v2  # MTEXT continuation
                    elif c2 == "5":
                        handle = v2
                    elif c2 == "8":
                        layer = v2
                    elif c2 == "10":
                        try:
                            ix = float(v2)
                        except ValueError:
                            pass
                    elif c2 == "20":
                        try:
                            iy = float(v2)
                        except ValueError:
                            pass
                if not ann_text.strip() or ix is None:
                    continue
                src = DxfAnnotationSource.MTEXT if etype == "MTEXT" else DxfAnnotationSource.TEXT
                ann_type = _classify_annotation_text(ann_text)
                ann_counter += 1
                annotations.append(DxfAnnotation(
                    annotation_id=f"ANN-{ann_counter:04d}",
                    source=src,
                    annotation_type=ann_type,
                    text=ann_text,
                    insertion_x=ix, insertion_y=iy,
                    layer=layer, handle=handle,
                ))

    except Exception:
        pass

    return annotations


def _classify_annotation_text(text: str) -> AnnotationType:
    """Classify annotation text to AnnotationType using existing parsers."""
    from backend.interoperability.fit_drawing import FitParseStatus, parse_fit_token
    from backend.interoperability.surface_finish_drawing import parse_surface_finish_token
    from backend.interoperability.thread_drawing import parse_thread_token

    t = text.strip()
    if not t:
        return AnnotationType.GENERAL_NOTE
    if parse_surface_finish_token(t) is not None:
        return AnnotationType.SURFACE_FINISH
    if parse_thread_token(t) is not None:
        return AnnotationType.THREAD
    status, _ = parse_fit_token(t)
    if status == FitParseStatus.PARSED:
        return AnnotationType.FIT
    return AnnotationType.GENERAL_NOTE


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze", summary="Upload CAD file and run feature recognition")
async def analyze_cad(req: AnalyzeRequest) -> dict:
    """Upload a CAD file and run deterministic feature recognition.

    Supported formats: IGES (full B-Rep), STEP (if pythonocc-core available), DXF (2D circles).
    Raw bytes are NEVER stored in the session.

    Returns session_id for subsequent feature/fusion queries.
    """
    content_bytes = base64.b64decode(req.content_b64)
    file_name = req.file_name
    format_id = _detect_format(file_name)

    fingerprint = hashlib.sha256(content_bytes).hexdigest()[:32]

    recognition_result, format_meta = _run_feature_recognition_for_format(
        content_bytes, format_id, file_name
    )

    # Drawing fusion (if drawing session provided)
    fusion_result: FusionResult | None = None
    if req.drawing_session_id:
        from backend.api.drawing_parser import _SESSIONS as _DRAWING_SESSIONS
        drawing_session = _DRAWING_SESSIONS.get(req.drawing_session_id)
        session_id_for_fusion = str(uuid.uuid4())
        fusion_result = fuse_cad_with_drawing(
            recognition_result,
            drawing_session,
            session_id_for_fusion,
        )

    ann_link = format_meta.get("annotation_link_result") if format_meta else None
    session_id = str(uuid.uuid4())
    sess = CadFeatureSession(
        session_id=session_id,
        file_name=file_name,
        format_id=format_id,
        file_fingerprint=fingerprint,
        entity_count=recognition_result.face_count,
        unit="MM",
        recognition_result=recognition_result,
        fusion_result=fusion_result,
        drawing_session_id=req.drawing_session_id,
        rejected_feature_ids=set(),
        confirmed_feature_ids=set(),
        created_at=datetime.now(UTC),
        annotation_link_result=ann_link,
    )
    _SESSIONS[session_id] = sess

    response: dict = {
        "session_id": session_id,
        "source_id": req.source_id or "",
        "status": "ANALYZED",
        "format_id": format_id,
        "file_name": file_name,
        "feature_count": recognition_result.feature_count,
        "pattern_count": recognition_result.pattern_count,
        "face_count": recognition_result.face_count,
        "body_count": recognition_result.body_count,
        "warnings": recognition_result.warnings,
        "fusion_available": fusion_result is not None,
        "disclaimer": "REFERENCE_ONLY — engineer review required",
    }
    if format_meta:
        response["entity_counts"] = format_meta.get("entity_counts", {})
        response["geometry_entity_count"] = format_meta.get("geometry_entity_count", 0)
        response["annotation_entity_count"] = format_meta.get("annotation_entity_count", 0)
        response["block_insert_support"] = format_meta.get("block_insert_support", "N/A")
        if ann_link is not None:
            response["annotation_links"] = {
                "linked": ann_link.linked_count,
                "ambiguous": ann_link.ambiguous_count,
                "conflicts": ann_link.conflict_count,
                "unresolved": ann_link.unresolved_count,
                "total_annotations": ann_link.total_annotations,
                "review_required": True,
            }
    return response


@router.get("/{session_id}", summary="Get session metadata")
async def get_session(session_id: str) -> dict:
    sess = _get_session(session_id)
    return {
        "session_id": sess.session_id,
        "file_name": sess.file_name,
        "format_id": sess.format_id,
        "entity_count": sess.entity_count,
        "unit": sess.unit,
        "feature_count": sess.recognition_result.feature_count,
        "pattern_count": sess.recognition_result.pattern_count,
        "warnings": sess.recognition_result.warnings,
        "drawing_session_id": sess.drawing_session_id,
        "created_at": sess.created_at.isoformat(),
    }


@router.get("/{session_id}/features", summary="List recognized features")
async def get_features(
    session_id: str,
    feature_type: str | None = None,
    confidence: str | None = None,
    unlinked_only: bool = False,
) -> dict:
    """Return recognized manufacturing features.

    Optional filters:
    - feature_type: filter by ManufacturingFeatureType
    - confidence: filter by FeatureRecognitionConfidence
    - unlinked_only: only features with no drawing requirement link
    """
    sess = _get_session(session_id)
    features = sess.recognition_result.features

    # Apply filters
    if feature_type:
        try:
            ft = ManufacturingFeatureType(feature_type)
            features = [f for f in features if f.feature_type == ft]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown feature_type: {feature_type}",
            ) from exc

    if confidence:
        try:
            conf = FeatureRecognitionConfidence(confidence)
            features = [f for f in features if f.confidence == conf]
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"Unknown confidence: {confidence}",
            ) from exc

    if unlinked_only and sess.fusion_result:
        linked_ids = {
            lnk.feature_id for lnk in sess.fusion_result.feature_links
        }
        features = [f for f in features if f.feature_id not in linked_ids]

    # Exclude rejected
    features = [
        f for f in features
        if f.feature_id not in sess.rejected_feature_ids
    ]

    return {
        "session_id": session_id,
        "total": len(features),
        "features": [f.as_dict() for f in features],
    }


@router.get("/{session_id}/patterns", summary="List detected feature patterns")
async def get_patterns(session_id: str) -> dict:
    sess = _get_session(session_id)
    return {
        "session_id": session_id,
        "total": sess.recognition_result.pattern_count,
        "patterns": [p.as_dict() for p in sess.recognition_result.patterns],
    }


@router.get("/{session_id}/fusion", summary="Get drawing/CAD fusion result")
async def get_fusion(session_id: str) -> dict:
    sess = _get_session(session_id)
    if sess.fusion_result is None:
        return {
            "session_id": session_id,
            "fusion_available": False,
            "message": "No drawing session linked. Provide drawing_session_id in /analyze.",
        }
    return sess.fusion_result.as_dict()


@router.post(
    "/{session_id}/features/{feature_id}/confirm",
    summary="Engineer confirms a feature",
)
async def confirm_feature(
    session_id: str,
    feature_id: str,
    body: ConfirmRequest,
) -> dict:
    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    confirmed = feature.confirm(body.user_id)
    # Replace in list
    idx = next(
        i for i, f in enumerate(sess.recognition_result.features)
        if f.feature_id == feature_id
    )
    sess.recognition_result.features[idx] = confirmed
    sess.confirmed_feature_ids.add(feature_id)

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "status": "CONFIRMED",
        "message": f"Feature confirmed by {body.user_id}",
        "confirmed": True,
        "confidence": str(confirmed.confidence),
        "user_id": body.user_id,
    }


@router.post(
    "/{session_id}/features/{feature_id}/confirm-with-dimension",
    summary="Engineer confirms feature with explicit dimension data (P3-A)",
)
async def confirm_feature_with_dimension(
    session_id: str,
    feature_id: str,
    body: FeatureDimensionConfirmRequest,
) -> dict:
    """Confirm a feature and supply engineer-measured dimension values.

    Use this when depth_mm or feature_type must be explicitly provided by the
    engineer — for example, 2D DXF hole candidates (depth not in drawing) or
    IGES bore candidates (depth not recoverable from surface-only topology).

    HARD RULES:
      - depth_mm and width_mm values come from the engineer, never inferred.
      - Returned values are tagged dimension_provenance=USER_CONFIRMED.
      - This endpoint does NOT trigger CNC dispatch or automatic downstream action.
    """
    from decimal import Decimal as _Dec

    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    type_override = (
        ManufacturingFeatureType(body.feature_type_override)
        if body.feature_type_override
        else None
    )
    depth = _Dec(str(body.depth_mm)) if body.depth_mm is not None else None
    width = _Dec(str(body.width_mm)) if body.width_mm is not None else None

    confirmed = feature.confirm_with_dimensions(
        body.user_id,
        feature_type_override=type_override,
        depth_mm=depth,
        width_mm=width,
        review_notes=body.review_notes,
    )

    idx = next(
        i for i, f in enumerate(sess.recognition_result.features)
        if f.feature_id == feature_id
    )
    sess.recognition_result.features[idx] = confirmed
    sess.confirmed_feature_ids.add(feature_id)

    # P4-A: bridge confirmed feature to route generator
    from backend.manufacturing.confirmed_feature_route import bridge_confirmed_feature_to_route
    route_bridge = bridge_confirmed_feature_to_route(confirmed)

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "status": "CONFIRMED_WITH_DIMENSION",
        "user_id": body.user_id,
        "confidence": str(confirmed.confidence),
        "feature_type": str(confirmed.feature_type),
        "depth_mm": float(confirmed.depth_mm) if confirmed.depth_mm is not None else None,
        "width_mm": float(confirmed.width_mm) if confirmed.width_mm is not None else None,
        "type_changed": type_override is not None and type_override != feature.feature_type,
        "depth_supplied": body.depth_mm is not None,
        "width_supplied": body.width_mm is not None,
        "dimension_provenance": "USER_CONFIRMED",
        "review_notes": body.review_notes,
        "feature": confirmed.as_dict(),
        "route_generation": route_bridge.as_dict(),
        "disclaimer": "USER_CONFIRMED: dimension values supplied by engineer — not inferred",
    }


@router.post(
    "/{session_id}/features/{feature_id}/reject",
    summary="Engineer rejects a feature",
)
async def reject_feature(
    session_id: str,
    feature_id: str,
    body: RejectRequest,
) -> dict:
    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    sess.rejected_feature_ids.add(feature_id)
    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "status": "REJECTED",
        "message": "Feature rejected",
        "rejected": True,
        "reason": body.reason,
    }


@router.get(
    "/{session_id}/features/{feature_id}/machine-candidates",
    summary="Return machine candidates for a confirmed feature (P5-B)",
)
async def get_machine_candidates(
    session_id: str,
    feature_id: str,
    operation: str | None = None,
    stock_x_mm: float | None = None,
    stock_y_mm: float | None = None,
    stock_z_mm: float | None = None,
    material_grade: str | None = None,
    required_rpm_max: float | None = None,
) -> dict:
    """Find machine candidates for a confirmed feature.

    Uses the machine library registry with actual capability data.
    Unknown capability does NOT become a pass.

    HARD RULES:
      - No machine write, no NC dispatch.
      - Selection uses actual machine library records only.
      - CAPABILITY_UNKNOWN != PASS.
    """
    from backend.manufacturing.machine_selection import select_machines

    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    _op = operation or "drilling"
    result = select_machines(
        operation=_op,
        stock_x_mm=stock_x_mm,
        stock_y_mm=stock_y_mm,
        stock_z_mm=stock_z_mm,
        required_rpm_max=required_rpm_max,
    )

    candidates_out = []
    for c in result.passing_candidates:
        candidates_out.append({
            "stable_id": c.machine.stable_id,
            "manufacturer": c.machine.manufacturer,
            "model": c.machine.model,
            "overall_status": c.overall_status.value,
            "checks": [
                {"check": ch.check_name, "status": ch.status.value, "detail": ch.detail}
                for ch in c.checks
            ],
        })

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "operation": _op,
        "machine_selection_ready": result.machine_selection_ready,
        "candidate_count": len(result.passing_candidates),
        "candidates": candidates_out,
        "notes": result.notes,
        "disclaimer": "OFFLINE_ONLY=YES. No machine write. No CNC dispatch.",
    }


@router.get(
    "/{session_id}/features/{feature_id}/tool-candidates",
    summary="Return tool candidates for a confirmed feature (P5-A/C)",
)
async def get_tool_candidates(
    session_id: str,
    feature_id: str,
    operation: str | None = None,
    material_grade: str | None = None,
    required_cutting_length_mm: float | None = None,
    machine_max_rpm: float | None = None,
) -> dict:
    """Find tool candidates for a confirmed feature.

    Uses the cutting tool catalog with actual geometry data.
    Reports EXACT / COMPATIBLE / NO_MATCH per tool.

    HARD RULES:
      - No nearest-diameter guess that violates geometry.
      - Cutting data from manufacturer starting values only (with provenance).
      - No automatic tool selection -- engineer must confirm.
    """
    from backend.cutting_tools.cutting_parameters import CuttingDataReadiness
    from backend.manufacturing.tool_selection import select_tools

    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    diameter_mm = feature.diameter_mm
    if diameter_mm is None:
        raise HTTPException(
            status_code=422,
            detail=f"Feature {feature_id!r} has no diameter_mm — confirm with dimension first",
        )

    _op = operation or "drilling"
    result = select_tools(
        feature_diameter_mm=float(diameter_mm),
        operation=_op,
        material_grade=material_grade,
        required_cutting_length_mm=required_cutting_length_mm,
        machine_max_rpm=machine_max_rpm,
    )

    candidates_out = []
    for c in result.candidates:
        entry: dict = {
            "stable_id": c.tool.stable_id,
            "manufacturer": c.tool.manufacturer,
            "product_name": c.tool.product_name,
            "cutting_diameter_mm": c.tool.cutting_diameter_mm,
            "match_status": c.match_status.value,
            "diameter_delta_mm": round(c.diameter_delta_mm, 4),
            "cutting_data_ready": c.cutting_data_ready,
            "rejection_reason": c.rejection_reason,
            "notes": c.notes,
        }
        if c.cutting_data and c.cutting_data.readiness == CuttingDataReadiness.READY:
            cd = c.cutting_data
            entry["cutting_data"] = {
                "vc_min_mpm": cd.vc_min_mpm,
                "vc_max_mpm": cd.vc_max_mpm,
                "fn_min_mm": cd.fn_min_mm,
                "fn_max_mm": cd.fn_max_mm,
                "rpm_min": cd.rpm_min,
                "rpm_max": cd.rpm_max,
                "feed_rate_min_mm_min": cd.feed_rate_min_mm_min,
                "feed_rate_max_mm_min": cd.feed_rate_max_mm_min,
                "machine_limit_status": cd.machine_limit_status.value,
                "source": cd.source,
                "source_url": cd.source_url,
                "status": cd.status.value,
            }
        candidates_out.append(entry)

    best = None
    if result.best_match:
        best = result.best_match.tool.stable_id

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "feature_diameter_mm": float(diameter_mm),
        "operation": _op,
        "tool_selection_ready": result.tool_selection_ready,
        "cutting_data_ready": result.cutting_data_ready,
        "candidate_count": len(result.candidates),
        "candidates": candidates_out,
        "best_match_stable_id": best,
        "disclaimer": (
            "OFFLINE_ONLY=YES. No auto-approval. "
            "COMPATIBLE tools create oversized holes — engineer must verify fit tolerance."
        ),
    }


@router.post(
    "/{session_id}/associate-drawing",
    summary="Manually associate a drawing requirement with a CAD feature",
)
async def associate_drawing(
    session_id: str,
    body: AssociateDrawingRequest,
) -> dict:
    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features
         if f.feature_id == body.feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {body.feature_id!r} not found")

    if sess.fusion_result is None:
        # Create a minimal fusion result to hold the manual link
        from backend.interoperability.cad_fusion import (
            FusionCompleteness,
            FusionResult,
        )
        sess.fusion_result = FusionResult(
            fusion_id=str(uuid.uuid4()),
            cad_session_id=session_id,
            drawing_session_id=None,
            feature_links=[],
            ambiguities=[],
            drawing_only_req_ids=[],
            cad_only_feature_ids=[],
            completeness=FusionCompleteness.PARTIAL,
            review_events=[],
            created_at=datetime.now(UTC),
        )

    sess.fusion_result.reassign_link(
        body.requirement_id, body.feature_id, body.user_id
    )
    return {
        "session_id": session_id,
        "requirement_id": body.requirement_id,
        "feature_id": body.feature_id,
        "status": "USER_MATCHED",
        "user_id": body.user_id,
    }


# ---------------------------------------------------------------------------
# P6 endpoints: cutting parameter confirmation, toolpath candidate, readiness
# ---------------------------------------------------------------------------


class ConfirmCuttingParametersRequest(BaseModel):
    """Engineer-confirmed cutting parameter selection (P6-C)."""

    tool_id: str
    tool_family: str
    material_grade: str
    diameter_mm: float
    operation: str = "drilling"
    vc_mpm: float
    fn_mm: float
    vc_min_mpm: float
    vc_max_mpm: float
    fn_min_mm: float
    fn_max_mm: float
    source: str
    source_url: str
    machine_max_rpm: float | None = None
    machine_max_feed_mm_min: float | None = None


class BuildToolpathCandidateRequest(BaseModel):
    """Inputs to build a drilling toolpath candidate (P6-D)."""

    tool_id: str
    tool_match_status: str
    tool_diameter_mm: float
    machine_id: str | None = None
    route_id: str | None = None
    clearance_z: float
    clearance_source: str = "USER_DEFINED"
    wcs_ref: str
    hole_x: float | None = None
    hole_y: float | None = None
    hole_top_z: float | None = None
    stock_top_z: float | None = None


@router.post(
    "/{session_id}/features/{feature_id}/confirm-cutting-parameters",
    summary="Engineer confirms cutting parameters from manufacturer range (P6-C)",
)
async def confirm_cutting_parameters_endpoint(
    session_id: str,
    feature_id: str,
    body: ConfirmCuttingParametersRequest,
) -> dict:
    """Transition cutting data from MANUFACTURER_STARTING_VALUE to USER_CONFIRMED.

    NC_CANDIDATE_REVIEW_READY=NO until this gate is passed.

    HARD RULES:
      - No auto-confirmation.
      - Values must be within the manufacturer starting-value range.
      - Machine limits are re-checked after confirmation.
      - is_dispatchable is never set to True.
    """
    from backend.manufacturing.parameter_confirmation import (
        ParameterConfirmationStatus,
        confirm_cutting_parameters,
    )

    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    result = confirm_cutting_parameters(
        session_id=session_id,
        tool_family=body.tool_family,
        material_grade=body.material_grade,
        diameter_mm=body.diameter_mm,
        operation=body.operation,
        vc_mpm=body.vc_mpm,
        fn_mm=body.fn_mm,
        vc_min_mpm=body.vc_min_mpm,
        vc_max_mpm=body.vc_max_mpm,
        fn_min_mm=body.fn_min_mm,
        fn_max_mm=body.fn_max_mm,
        source=body.source,
        source_url=body.source_url,
        machine_max_rpm=body.machine_max_rpm,
        machine_max_feed_mm_min=body.machine_max_feed_mm_min,
    )

    if result.confirmed_params is not None:
        sess.p6_confirmed_params[feature_id] = result.confirmed_params

    confirmed_out: dict | None = None
    if result.confirmed_params is not None:
        cp = result.confirmed_params
        confirmed_out = {
            "tool_family": cp.tool_family,
            "material_grade": cp.material_grade,
            "diameter_mm": cp.diameter_mm,
            "operation": cp.operation,
            "vc_mpm": cp.vc_mpm,
            "fn_mm": cp.fn_mm,
            "rpm_calculated": cp.rpm_calculated,
            "feed_rate_mm_min": cp.feed_rate_mm_min,
            "status": cp.status.value,
            "source": cp.source,
            "source_url": cp.source_url,
            "confirmed_at": cp.confirmed_at,
            "machine_check": {
                "rpm_within_limit": cp.machine_check.rpm_within_limit,
                "feed_within_limit": cp.machine_check.feed_within_limit,
                "actual_rpm": cp.machine_check.actual_rpm,
                "actual_feed_mm_min": cp.machine_check.actual_feed_mm_min,
                "warnings": cp.machine_check.warnings,
            },
        }

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "status": result.status.value,
        "nc_candidate_review_ready": (
            result.status == ParameterConfirmationStatus.ENGINEER_CONFIRMED
        ),
        "confirmed_params": confirmed_out,
        "blockers": result.blockers,
        "warnings": result.warnings,
        "disclaimer": (
            "OFFLINE_ONLY=YES. ENGINEER_CONFIRMED means the engineer selected "
            "these values from the manufacturer range — NOT production-tested or "
            "certified. Engineer sign-off required before production use."
        ),
        "is_dispatchable": False,
    }


@router.post(
    "/{session_id}/features/{feature_id}/build-toolpath-candidate",
    summary="Build a drilling toolpath candidate and offline NC candidate (P6-D)",
)
async def build_toolpath_candidate_endpoint(
    session_id: str,
    feature_id: str,
    body: BuildToolpathCandidateRequest,
) -> dict:
    """Build a drilling toolpath candidate and an offline NC candidate.

    Uses the confirmed feature's location, depth, and engineer-confirmed cutting
    parameters.  The NC candidate is OFFLINE ONLY and NOT dispatchable.

    HARD RULES:
      - is_dispatchable=False always.
      - production_released=False always.
      - COMPATIBLE match risk preserved in every output.
      - NC_CANDIDATE_REVIEW_READY=NO if cutting parameters not ENGINEER_CONFIRMED.
    """
    from backend.api.setup_stock import _SESSIONS as _SETUP_SESSIONS  # noqa: PLC0415
    from backend.manufacturing.clearance_policy import evaluate_clearance
    from backend.manufacturing.nc_candidate import build_offline_nc_candidate
    from backend.toolpath.enums import ClearanceSource

    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    # Hole location: use feature.location if not overridden
    loc = getattr(feature, "location", None)
    hole_x = body.hole_x if body.hole_x is not None else (
        (loc["x_mm"] if isinstance(loc, dict) else getattr(loc, "x_mm", 0.0))
        if loc is not None else 0.0
    )
    hole_y = body.hole_y if body.hole_y is not None else (
        (loc["y_mm"] if isinstance(loc, dict) else getattr(loc, "y_mm", 0.0))
        if loc is not None else 0.0
    )
    hole_top_z = body.hole_top_z if body.hole_top_z is not None else (
        (loc["z_mm"] if isinstance(loc, dict) else getattr(loc, "z_mm", 0.0))
        if loc is not None else 0.0
    )

    depth_mm = float(feature.depth_mm) if feature.depth_mm is not None else None
    if depth_mm is None:
        raise HTTPException(
            status_code=422,
            detail=f"Feature {feature_id!r} has no depth_mm — confirm with dimension first",
        )

    diameter_mm = float(feature.diameter_mm) if feature.diameter_mm is not None else None
    if diameter_mm is None:
        raise HTTPException(
            status_code=422,
            detail=f"Feature {feature_id!r} has no diameter_mm — confirm with dimension first",
        )

    # Clearance source
    try:
        cs = ClearanceSource(body.clearance_source)
    except ValueError:
        cs = ClearanceSource.USER_DEFINED

    clearance_eval = evaluate_clearance(
        clearance_z=body.clearance_z,
        clearance_source=cs,
        stock_top_z=body.stock_top_z,
        feature_top_z=hole_top_z,
        wcs_ref=body.wcs_ref,
    )
    sess.p6_clearance_state[feature_id] = clearance_eval

    # Retrieve confirmed cutting params (may be None)
    confirmed_params = sess.p6_confirmed_params.get(feature_id)
    cutting_confirmed = (
        confirmed_params is not None
        and confirmed_params.status.value == "USER_CONFIRMED"
    )

    # Build NC candidate
    material = "UNKNOWN"
    # Try to find material from setup session (best-effort)
    setup_sess = _SETUP_SESSIONS.get(session_id)
    if setup_sess is not None and setup_sess.stock is not None:
        material = setup_sess.stock.material_grade or "UNKNOWN"

    nc = build_offline_nc_candidate(
        sample_id=sess.file_name,
        feature_id=feature_id,
        hole_x=hole_x,
        hole_y=hole_y,
        hole_top_z=hole_top_z,
        hole_depth_mm=depth_mm,
        feature_diameter_mm=diameter_mm,
        material=material,
        operation="drilling",
        tool_id=body.tool_id,
        tool_match_status=body.tool_match_status,
        tool_diameter_mm=body.tool_diameter_mm,
        clearance_eval=clearance_eval,
        wcs_ref=body.wcs_ref,
        confirmed_params=confirmed_params,
        route_id=body.route_id,
        machine_id=body.machine_id,
    )
    sess.p6_nc_candidates[feature_id] = nc

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "sample_id": nc.sample_id,
        "toolpath_status": nc.toolpath_status,
        "toolpath_summary": nc.toolpath_summary,
        "nc_candidate_ready": bool(nc.nc_segments),
        "nc_candidate_review_ready": nc.nc_candidate_review_ready,
        "segment_count": len(nc.nc_segments),
        "tool_id": nc.tool_id,
        "tool_match_status": nc.tool_match_status,
        "tool_risk_warning": nc.tool_risk_warning,
        "dimensional_conformance": nc.dimensional_conformance,
        "cutting_params_confirmed": cutting_confirmed,
        "clearance_z_mm": nc.clearance_z_mm,
        "wcs_ref": nc.wcs_ref,
        "review_status": nc.review_status,
        "warnings": nc.warnings,
        "provenance": nc.provenance,
        "offline_only": nc.offline_only,
        "is_dispatchable": nc.is_dispatchable,
        "production_released": nc.production_released,
        "engineer_review_required": nc.engineer_review_required,
        "postprocessor_status": nc.postprocessor_status,
        "production_controller_compatibility": nc.production_controller_compatibility,
        "label_en": nc.label_en,
        "label_tr": nc.label_tr,
    }


@router.get(
    "/{session_id}/features/{feature_id}/p6-readiness",
    summary="Return P6 five-level CAM→NC readiness for a feature",
)
async def get_p6_readiness(
    session_id: str,
    feature_id: str,
    machine_id: str | None = None,
    tool_id: str | None = None,
    tool_match_status: str | None = None,
) -> dict:
    """Return the full five-level P6 readiness for a confirmed feature.

    Levels:
      CAM_READY                 ← cam_gate.py (unchanged semantics)
      PARAMETERIZED_CAM_READY   ← machine + tool + ENGINEER_CONFIRMED params + WCS
      TOOLPATH_READY            ← parameterized + clearance + toolpath generated
      NC_CANDIDATE_READY        ← segments translated
      NC_CANDIDATE_REVIEW_READY ← all engineer gates complete

    None of these levels imply DISPATCHABLE or PRODUCTION_RELEASED.
    """
    from backend.api.setup_stock import _SESSIONS as _SETUP_SESSIONS  # noqa: PLC0415
    from backend.manufacturing.cam_gate import check_cam_prerequisites
    from backend.manufacturing.nc_candidate import evaluate_p6_readiness
    from backend.manufacturing.parameter_confirmation import ParameterConfirmationStatus

    sess = _get_session(session_id)
    feature = next(
        (f for f in sess.recognition_result.features if f.feature_id == feature_id),
        None,
    )
    if feature is None:
        raise HTTPException(status_code=404, detail=f"Feature {feature_id!r} not found")

    # CAM prerequisite check
    setup_sess = _SETUP_SESSIONS.get(session_id)
    cam_state = check_cam_prerequisites(feature, setup_sess)

    confirmed_params = sess.p6_confirmed_params.get(feature_id)
    clearance_eval = sess.p6_clearance_state.get(feature_id)
    nc_candidate = sess.p6_nc_candidates.get(feature_id)

    param_status: ParameterConfirmationStatus | None = None
    if confirmed_params is not None:
        param_status = ParameterConfirmationStatus.ENGINEER_CONFIRMED

    wcs_ref = nc_candidate.wcs_ref if nc_candidate is not None else None

    report = evaluate_p6_readiness(
        feature_id=feature_id,
        cam_ready=cam_state.cam_ready,
        cam_ready_blocker=cam_state.first_blocker,
        machine_id=machine_id,
        tool_id=tool_id,
        tool_match_status=tool_match_status,
        confirmed_params=confirmed_params,
        param_confirmation_status=param_status,
        wcs_ref=wcs_ref,
        clearance_eval=clearance_eval,
        nc_candidate=nc_candidate,
    )

    return {
        "session_id": session_id,
        "feature_id": feature_id,
        "cam_ready": report.cam_ready,
        "parameterized_cam_ready": report.parameterized_cam_ready,
        "toolpath_ready": report.toolpath_ready,
        "nc_candidate_ready": report.nc_candidate_ready,
        "nc_candidate_review_ready": report.nc_candidate_review_ready,
        "blockers": {
            "cam": report.cam_ready_blocker,
            "parameterized_cam": report.parameterized_cam_ready_blocker,
            "toolpath": report.toolpath_ready_blocker,
            "nc_candidate": report.nc_candidate_ready_blocker,
            "nc_review": report.nc_candidate_review_ready_blocker,
        },
        "tool_match_status": report.tool_match_status,
        "cutting_params_status": report.cutting_params_status,
        "clearance_status": report.clearance_status,
        "is_dispatchable": report.is_dispatchable,
        "production_released": report.production_released,
        "machine_ready_to_run": report.machine_ready_to_run,
        "disclaimer": (
            "OFFLINE_ONLY=YES. No level implies DISPATCHABLE or PRODUCTION_RELEASED. "
            "Engineer sign-off required before production use."
        ),
    }
