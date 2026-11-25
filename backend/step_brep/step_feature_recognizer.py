"""
STEP feature recognition via gmsh OCC topology (Phase A).

Uses StepFaceSummary data already extracted by parse_step_file — no pythonocc-core needed.

HARD RULES:
  - No fabricated feature IDs; all IDs are deterministic from tag+type.
  - diameter_mm and depth_mm come from real bbox dimensions only.
  - confidence=GEOMETRY_RULE (never EXACT_BREP without full topology).
  - provenance label GMSH_OCC_TOPOLOGY is always set in warnings.
  - is_dispatchable=False, production_released=False always (inherited from parser).
  - recognize_features_from_bytes returns None on any failure (fail-closed).
"""

from __future__ import annotations

import os
import tempfile
from types import MappingProxyType

PROVENANCE = "GMSH_OCC_TOPOLOGY"
_RECOGNITION_VERSION = "1.0.0-gmsh"
_HOLE_NORMAL_TOL = 0.15     # face with |nz| > 0.85 is a horizontal (top/bottom) face
_CYL_ASPECT_TOL = 0.08      # dx and dy must match within 8% to be a vertical cylinder


def _approx_equal(a: float, b: float, rel_tol: float = _CYL_ASPECT_TOL) -> bool:
    denom = max(abs(a), abs(b), 1e-10)
    return abs(a - b) / denom < rel_tol


def recognize_features(
    record: object,
) -> object | None:
    """Return ManufacturingFeatureRecognitionResult from a StepImportRecord, or None.

    Recognizes:
      HOLE        — CYLINDRICAL face, circular boundary, dx≈dy (vertical cylinder)
      PLANAR_FACE — PLANAR face, |normal_z| > 0.85 (horizontal)
    """
    try:
        from decimal import Decimal

        from backend.domain.units import Quantity, Unit
        from backend.interoperability.cad_feature_recognition import (
            FeatureRecognitionConfidence,
            ManufacturingFeature,
            ManufacturingFeatureRecognitionResult,
            ManufacturingFeatureType,
            RecognitionMethod,
        )
        from backend.interoperability.geometry import BoundingBox3D

        def _qty(v: float) -> Quantity:
            return Quantity(value=Decimal(str(round(v, 4))), unit=Unit.MM)

        def _pt(x: float, y: float, z: float):  # type: ignore[no-untyped-def]
            from backend.interoperability.geometry import CanonicalPoint3D
            return CanonicalPoint3D(x=_qty(x), y=_qty(y), z=_qty(z))

        def _vec(x: float, y: float, z: float):  # type: ignore[no-untyped-def]
            from backend.domain.units import Quantity, Unit
            from backend.interoperability.geometry import CanonicalVector3D
            return CanonicalVector3D(
                x=Quantity(value=Decimal(str(round(x, 6))), unit=Unit.DIMENSIONLESS),
                y=Quantity(value=Decimal(str(round(y, 6))), unit=Unit.DIMENSIONLESS),
                z=Quantity(value=Decimal(str(round(z, 6))), unit=Unit.DIMENSIONLESS),
            )

        faces = getattr(record, "faces", [])
        if not faces:
            return None

        doc_id = getattr(record, "sha256", None) or "step-gmsh"
        if doc_id:
            doc_id = doc_id[:16]

        features: list[ManufacturingFeature] = []

        for face in faces:
            tag: int = face.tag
            surface_class: str = face.surface_class
            bbox_min: tuple[float, float, float] = face.bbox_min
            bbox_max: tuple[float, float, float] = face.bbox_max
            normal: tuple[float, float, float] = face.normal_at_center
            has_circular: bool = face.has_circular_boundary

            xmin, ymin, zmin = bbox_min
            xmax, ymax, zmax = bbox_max
            dx = xmax - xmin
            dy = ymax - ymin
            dz = zmax - zmin

            fid = f"step-gmsh-{tag}"

            if (
                surface_class == "CYLINDRICAL"
                and has_circular
                and dx > 1e-4
                and dy > 1e-4
                and _approx_equal(dx, dy)
            ):
                # Vertical cylinder → HOLE candidate
                cx = (xmin + xmax) / 2.0
                cy = (ymin + ymax) / 2.0
                diam = (dx + dy) / 2.0
                from backend.interoperability.geometry import CanonicalSurfaceType
                features.append(ManufacturingFeature(
                    feature_id=fid,
                    feature_type=ManufacturingFeatureType.HOLE,
                    source_body_id="gmsh-body-0",
                    source_face_ids=(f"occ-face-{tag}",),
                    source_edge_ids=tuple(
                        f"occ-edge-{t}" for t in face.boundary_curve_tags
                    ),
                    surface_type=CanonicalSurfaceType.CYLINDER,
                    location=_pt(cx, cy, zmax),
                    axis=_vec(0.0, 0.0, -1.0),
                    diameter_mm=Decimal(str(round(diam, 4))),
                    depth_mm=Decimal(str(round(dz, 4))),
                    width_mm=None,
                    length_mm=None,
                    radius_mm=Decimal(str(round(diam / 2.0, 4))),
                    angle_deg=None,
                    bounding_box=BoundingBox3D(
                        min_point=_pt(xmin, ymin, zmin),
                        max_point=_pt(xmax, ymax, zmax),
                    ),
                    recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
                    confidence=FeatureRecognitionConfidence.GEOMETRY_RULE,
                    pattern_id=None,
                    confirmed_by=None,
                    metadata=MappingProxyType({"provenance": PROVENANCE, "occ_tag": tag}),
                ))

            elif surface_class == "PLANAR" and abs(normal[2]) > (1.0 - _HOLE_NORMAL_TOL):
                # Horizontal planar face
                from backend.interoperability.geometry import CanonicalSurfaceType
                cx = (xmin + xmax) / 2.0
                cy = (ymin + ymax) / 2.0
                cz = (zmin + zmax) / 2.0
                features.append(ManufacturingFeature(
                    feature_id=fid,
                    feature_type=ManufacturingFeatureType.PLANAR_FACE,
                    source_body_id="gmsh-body-0",
                    source_face_ids=(f"occ-face-{tag}",),
                    source_edge_ids=tuple(
                        f"occ-edge-{t}" for t in face.boundary_curve_tags
                    ),
                    surface_type=CanonicalSurfaceType.PLANE,
                    location=_pt(cx, cy, cz),
                    axis=_vec(normal[0], normal[1], normal[2]),
                    diameter_mm=None,
                    depth_mm=None,
                    width_mm=Decimal(str(round(dy, 4))),
                    length_mm=Decimal(str(round(dx, 4))),
                    radius_mm=None,
                    angle_deg=None,
                    bounding_box=BoundingBox3D(
                        min_point=_pt(xmin, ymin, zmin),
                        max_point=_pt(xmax, ymax, zmax),
                    ),
                    recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
                    confidence=FeatureRecognitionConfidence.GEOMETRY_RULE,
                    pattern_id=None,
                    confirmed_by=None,
                    metadata=MappingProxyType({"provenance": PROVENANCE, "occ_tag": tag}),
                ))

        return ManufacturingFeatureRecognitionResult(
            source_document_id=doc_id,
            recognition_version=_RECOGNITION_VERSION,
            features=list(features),
            patterns=[],
            accessibility={},
            tool_reach={},
            warnings=[
                f"GMSH_OCC_TOPOLOGY: {len(features)} features recognized from STEP surface "
                "topology — review required; GEOMETRY_RULE confidence, not EXACT_BREP",
            ],
            face_count=len(faces),
            body_count=max(getattr(record, "body_count", 0), 0),
        )
    except Exception:
        return None


def recognize_features_from_bytes(
    content_bytes: bytes,
    file_name: str,
) -> object | None:
    """Write content_bytes to a temp file, parse with gmsh, return feature result or None."""
    ext = os.path.splitext(file_name)[1].lower() or ".step"
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        with open(tmp_path, "wb") as f:
            f.write(content_bytes)
        from backend.step_brep.gmsh_step_parser import parse_step_file
        record = parse_step_file(tmp_path)
        if not record.is_qualified:
            return None
        return recognize_features(record)
    except Exception:
        return None
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
