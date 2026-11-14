"""P2 qualification tests — real-file readiness defect fixes.

Covers:
  DEF-P1A-001 — C45 allowlist: C45 must NOT be suppressed by revision-code FP guard
  DEF-P1A-001 — Allowlist members (C15, C22, C35, C60, C80) also pass through
  DEF-P1A-001 — Non-allowlisted revision-code-shaped tokens (A02, K1) remain suppressed
  DEF-P1A-002 — PYTESSERACT_AVAILABLE is a module-level bool (False when not installed)
  DEF-RSQ-001 — Unsupported format error message includes format name, not empty string
  DEF-RSQ-001 — _ext_from_source extracts extension from file_name
  DEF-RSQ-001 — _ext_from_source extracts extension from source_id when file_name absent
  DEF-RSQ-003 — Revision codes (P00, A02, K1) suppressed as fit tokens
  DEF-RSQ-003 — Valid fit token H7 still detected
  DEF-RSQ-003 — Valid fit token g6 still detected
  P2-B — extract_iges_feature_candidates: cylindrical group → PRECISION_BORE_CANDIDATE
  P2-B — extract_iges_feature_candidates: planar group → PLANAR_FACE
  P2-B — PRECISION_BORE_CANDIDATE depth_mm is always None
  P2-B — PRECISION_BORE_CANDIDATE confidence is INFERRED
  P2-B — feature_candidates populated on reconstruct_iges_topology result
  P2-B — topology_fabricated stays False after feature extraction
  P2-B — closed_body_available stays False after feature extraction
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# DEF-P1A-001 / DEF-P1A-002 — hybrid_pdf_drawing
# ---------------------------------------------------------------------------

from backend.interoperability.hybrid_pdf_drawing import (
    PYTESSERACT_AVAILABLE,
    PdfEngineeringTokenType,
    PdfExtractionProvenance,
    _is_false_positive,
    extract_engineering_tokens_from_text,
)


class TestDefP1A001Allowlist:
    def test_c45_not_filtered(self):
        assert _is_false_positive("C45") is False

    def test_c15_not_filtered(self):
        assert _is_false_positive("C15") is False

    def test_c22_not_filtered(self):
        assert _is_false_positive("C22") is False

    def test_c35_not_filtered(self):
        assert _is_false_positive("C35") is False

    def test_c60_not_filtered(self):
        assert _is_false_positive("C60") is False

    def test_c80_not_filtered(self):
        assert _is_false_positive("C80") is False

    def test_ck45_not_filtered(self):
        assert _is_false_positive("Ck45") is False

    def test_cm45_not_filtered(self):
        assert _is_false_positive("Cm45") is False

    def test_a02_still_filtered(self):
        # A02 matches ^[A-Z]\d{2}$ FP guard — must remain True
        assert _is_false_positive("A02") is True

    def test_p00_still_filtered(self):
        # P00 matches ^P\d{2}$ FP guard — must remain True
        assert _is_false_positive("P00") is True

    def test_b03_still_filtered(self):
        # B03 matches ^[A-Z]\d{2}$ FP guard — must remain True
        assert _is_false_positive("B03") is True

    def test_c45_produces_material_token(self):
        tokens = extract_engineering_tokens_from_text(
            "C45", PdfExtractionProvenance.NATIVE_TEXT, page_number=1
        )
        mat = [t for t in tokens if t.token_type == PdfEngineeringTokenType.MATERIAL]
        assert len(mat) == 1
        assert mat[0].normalized_value == "C45"


class TestDefP1A002PytesseractFlag:
    def test_pytesseract_available_is_bool(self):
        assert isinstance(PYTESSERACT_AVAILABLE, bool)

    def test_pytesseract_available_accessible(self):
        # Flag must exist at module level — import already exercised above
        from backend.interoperability.hybrid_pdf_drawing import PYTESSERACT_AVAILABLE as flag
        assert flag is not None


# ---------------------------------------------------------------------------
# DEF-RSQ-001 — orchestrator unsupported-format error message
# ---------------------------------------------------------------------------

from backend.interoperability.enums import CapabilityLevel
from backend.interoperability.models import EngineeringSource
from backend.interoperability.orchestrator import CadImportOrchestrator, FormatDetectionResult


def _make_source(source_id: str, file_name: str | None = None) -> MagicMock:
    src = MagicMock()
    src.source_id = source_id
    src.file_name = file_name
    return src


def _make_detection(format_id: str = "DWG") -> MagicMock:
    det = MagicMock(spec=FormatDetectionResult)
    det.format_id = format_id
    det.confidence = 0.95
    return det


class TestDefRSQ001UnsupportedFormatMessage:
    def test_ext_from_source_uses_file_name(self):
        src = _make_source("some-id", file_name="part.DWG")
        ext = CadImportOrchestrator._ext_from_source(src)
        assert ext == "DWG"

    def test_ext_from_source_uses_source_id_fallback(self):
        src = _make_source("drawing.pdf")
        src.file_name = None
        ext = CadImportOrchestrator._ext_from_source(src)
        assert ext == "PDF"

    def test_ext_from_source_no_extension_returns_empty(self):
        src = _make_source("nodothere")
        src.file_name = None
        ext = CadImportOrchestrator._ext_from_source(src)
        assert ext == ""

    def test_unsupported_result_notes_include_format(self):
        orc = CadImportOrchestrator()
        src = _make_source("drawing.dwg", file_name="drawing.dwg")
        result = orc._build_unsupported_result(
            source=src,
            detection=_make_detection("DWG"),
            candidate_ids=(),
            format_id="DWG",
            requested_level=CapabilityLevel.LEVEL_2_GEOMETRY,
        )
        # error_message must reference the format name, not be blank or 'UNKNOWN'
        assert result.error_message is not None
        assert "DWG" in result.error_message


# ---------------------------------------------------------------------------
# DEF-RSQ-003 — semantic_extraction revision-code suppression
# ---------------------------------------------------------------------------

from backend.interoperability.semantic_extraction import (
    DetectionSourceType,
    NormalizedDetectionType,
    run_token_extraction,
)


class TestDefRSQ003RevisionCodeSuppression:
    def test_p00_not_detected_as_fit(self):
        detections = run_token_extraction(["P00"], DetectionSourceType.VECTOR_PDF)
        fit_detections = [d for d in detections if d.normalized_type == NormalizedDetectionType.FIT]
        assert fit_detections == []

    def test_a02_not_detected_as_fit(self):
        detections = run_token_extraction(["A02"], DetectionSourceType.VECTOR_PDF)
        fit_detections = [d for d in detections if d.normalized_type == NormalizedDetectionType.FIT]
        assert fit_detections == []

    def test_k1_not_detected_as_fit(self):
        detections = run_token_extraction(["K1"], DetectionSourceType.VECTOR_PDF)
        fit_detections = [d for d in detections if d.normalized_type == NormalizedDetectionType.FIT]
        assert fit_detections == []

    def test_h7_still_detected_as_fit(self):
        detections = run_token_extraction(["H7"], DetectionSourceType.VECTOR_PDF)
        fit_detections = [d for d in detections if d.normalized_type == NormalizedDetectionType.FIT]
        assert len(fit_detections) >= 1

    def test_h7_g6_compound_still_detected_as_fit(self):
        # Compound fit notation must still be detected (not suppressed by revision-code guard)
        detections = run_token_extraction(["H7/g6"], DetectionSourceType.VECTOR_PDF)
        fit_detections = [d for d in detections if d.normalized_type == NormalizedDetectionType.FIT]
        assert len(fit_detections) >= 1


# ---------------------------------------------------------------------------
# P2-B — IGES feature candidates
# ---------------------------------------------------------------------------

from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import (
    CanonicalGeometry,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
)
from backend.interoperability.iges_topology_reconstruction import (
    IgesTopologyReconstructionResult,
    IgesReconstructionStatus,
    SurfaceGroup,
    SurfaceGroupType,
    extract_iges_feature_candidates,
    reconstruct_iges_topology,
)
from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeatureType,
    RecognitionMethod,
)


def _qty(v: float) -> Quantity:
    return Quantity.of(v, Unit.MM)


def _vec3(x: float, y: float, z: float) -> CanonicalVector3D:
    return CanonicalVector3D(
        x=Quantity.of(x, Unit.DIMENSIONLESS),
        y=Quantity.of(y, Unit.DIMENSIONLESS),
        z=Quantity.of(z, Unit.DIMENSIONLESS),
    )


def _make_cyl_group(gid: str, radius: float) -> SurfaceGroup:
    return SurfaceGroup(
        group_id=gid,
        group_type=SurfaceGroupType.CYLINDRICAL_FAMILY,
        surface_ids=(f"{gid}-s1",),
        axis_x=0.0, axis_y=0.0, axis_z=1.0,
        radius_mm=radius,
    )


def _make_planar_group(gid: str) -> SurfaceGroup:
    return SurfaceGroup(
        group_id=gid,
        group_type=SurfaceGroupType.PLANAR_ASSEMBLY,
        surface_ids=(f"{gid}-s1", f"{gid}-s2"),
        normal_x=0.0, normal_y=0.0, normal_z=1.0,
    )


def _make_recon_result(groups: list[SurfaceGroup]) -> IgesTopologyReconstructionResult:
    return IgesTopologyReconstructionResult(
        status=IgesReconstructionStatus.SUCCESS,
        surface_groups=groups,
        surface_count=sum(g.surface_count for g in groups),
    )


class TestP2BIgesFeatureCandidates:
    def test_cylindrical_group_produces_precision_bore_candidate(self):
        recon = _make_recon_result([_make_cyl_group("g1", 12.5)])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        assert len(candidates) == 1
        assert candidates[0].feature_type == ManufacturingFeatureType.PRECISION_BORE_CANDIDATE

    def test_planar_group_produces_planar_face(self):
        recon = _make_recon_result([_make_planar_group("g2")])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        assert len(candidates) == 1
        assert candidates[0].feature_type == ManufacturingFeatureType.PLANAR_FACE

    def test_bore_candidate_depth_is_none(self):
        recon = _make_recon_result([_make_cyl_group("g3", 8.0)])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        assert candidates[0].depth_mm is None

    def test_bore_candidate_confidence_is_inferred(self):
        recon = _make_recon_result([_make_cyl_group("g4", 5.0)])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        assert candidates[0].confidence == FeatureRecognitionConfidence.INFERRED

    def test_bore_candidate_recognition_method_is_surface_heuristic(self):
        recon = _make_recon_result([_make_cyl_group("g5", 6.5)])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        assert candidates[0].recognition_method == RecognitionMethod.SURFACE_HEURISTIC

    def test_bore_candidate_diameter_derived_from_radius(self):
        recon = _make_recon_result([_make_cyl_group("g6", 10.0)])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        c = candidates[0]
        assert c.diameter_mm is not None
        assert float(c.diameter_mm) == pytest.approx(20.0)

    def test_mixed_groups_produce_multiple_candidates(self):
        recon = _make_recon_result([
            _make_cyl_group("g7", 7.5),
            _make_planar_group("g8"),
        ])
        candidates = extract_iges_feature_candidates(recon, "test-iges")
        assert len(candidates) == 2

    def test_topology_fabricated_stays_false(self):
        recon = _make_recon_result([_make_cyl_group("g9", 4.0)])
        assert recon.topology_fabricated is False
        extract_iges_feature_candidates(recon, "test-iges")
        assert recon.topology_fabricated is False

    def test_closed_body_available_stays_false(self):
        recon = _make_recon_result([_make_cyl_group("g10", 4.0)])
        assert recon.closed_body_available is False
        extract_iges_feature_candidates(recon, "test-iges")
        assert recon.closed_body_available is False

    def test_feature_candidates_populated_by_reconstruct(self):
        from unittest.mock import MagicMock
        surf = CanonicalSurface(
            surface_id="s1",
            surface_type=CanonicalSurfaceType.CYLINDER,
            axis=_vec3(0, 0, 1),
            radius=_qty(5.0),
        )
        geom = CanonicalGeometry(geometry_id="g", surfaces=(surf,), curves=())
        mr = MagicMock()
        mr.topology = None
        mr.geometry = geom
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr, source_id="test")
        assert isinstance(result.feature_candidates, list)
        # At least one candidate from the cylinder surface
        assert len(result.feature_candidates) >= 1
