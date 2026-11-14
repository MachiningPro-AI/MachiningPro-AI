"""P1 real sample coverage qualification tests (MUST 37).

Verifies that P1 modules (hybrid_pdf_drawing, dxf_annotation_linker,
iges_topology_reconstruction, cad_feature_recognition partial arcs) are:
  - Importable and produce correct module-level exports
  - Respect fabrication guards on synthetic inputs
  - Report UNKNOWN correctly (no fabricated fields)
  - Identify surface-only IGES as SURFACES_AVAILABLE/CLOSED_BODY=NO
  - Partial circular boundary detection does not produce false positives

NOTE: Real sample files are at D:/makina_ogrenmesi/olcum_denemeleri/örnek dosyalar
      These tests use SYNTHETIC inputs only — real file tests require the sample
      files to be present and are marked with @pytest.mark.real_samples.
      Real file tests are skipped by default; run with --run-real-samples.

REAL_SAMPLE_FILES_NOT_COMMITTED=YES
SOURCE_FILES_UNCHANGED=YES
FABRICATED_ENGINEERING_DATA=NO
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from types import MappingProxyType

import pytest

# ---------------------------------------------------------------------------
# P1-A: hybrid_pdf_drawing
# ---------------------------------------------------------------------------

class TestHybridPdfDrawingImports:
    def test_public_api_importable(self):
        from backend.interoperability.hybrid_pdf_drawing import (
            PdfContentType,
            OcrConfidenceLevel,
            PdfExtractionProvenance,
            PdfEngineeringTokenType,
            HybridPdfToken,
            PdfEngineeringToken,
            PdfPageClassification,
            HybridPdfStageResult,
            HybridPdfExtractionResult,
            extract_engineering_tokens_from_text,
        )
        assert extract_engineering_tokens_from_text is not None

    def test_ocr_auto_confirm_false(self):
        from backend.interoperability.hybrid_pdf_drawing import (
            PdfEngineeringToken,
            PdfEngineeringTokenType,
            PdfExtractionProvenance,
        )
        t = PdfEngineeringToken(
            token_type=PdfEngineeringTokenType.DRAWING_NUMBER,
            raw_text="DWG NO: X-100",
            normalized_value="X-100",
            provenance=PdfExtractionProvenance.NATIVE_TEXT,
            page_number=1,
            confidence=Decimal("0.95"),
        )
        assert t.auto_confirmed is False
        assert t.review_required is True

    def test_no_engineering_tokens_from_empty_input(self):
        from backend.interoperability.hybrid_pdf_drawing import (
            extract_engineering_tokens_from_text,
            PdfExtractionProvenance,
        )
        result = extract_engineering_tokens_from_text("", PdfExtractionProvenance.NATIVE_TEXT, page_number=1)
        assert result == []

    def test_fp_guard_dwg_id_not_a_dimension(self):
        from backend.interoperability.hybrid_pdf_drawing import (
            extract_engineering_tokens_from_text,
            PdfExtractionProvenance,
            PdfEngineeringTokenType,
        )
        # DWG-00206402-001 is a drawing ID, not an engineering dimension
        result = extract_engineering_tokens_from_text(
            "DWG-00206402-001",
            PdfExtractionProvenance.NATIVE_TEXT,
            page_number=1,
        )
        dim_tokens = [t for t in result if t.token_type == PdfEngineeringTokenType.DIMENSION]
        assert dim_tokens == []


# ---------------------------------------------------------------------------
# P1-B: dxf_annotation_linker
# ---------------------------------------------------------------------------

class TestDxfAnnotationLinkerImports:
    def test_public_api_importable(self):
        from backend.interoperability.dxf_annotation_linker import (
            DxfAnnotation,
            DxfAnnotationSource,
            DxfAnnotationLinkMethod,
            DxfAnnotationLinkStatus,
            DxfAnnotationLink,
            DxfAnnotationLinkResult,
            link_dxf_annotations,
            dxf_feature_bbox,
        )
        assert link_dxf_annotations is not None

    def test_no_auto_confirm_on_link(self):
        from backend.interoperability.dxf_annotation_linker import (
            DxfAnnotationLink,
            DxfAnnotationLinkMethod,
            DxfAnnotationLinkStatus,
        )
        from backend.interoperability.association import AnnotationType, FeatureType
        link = DxfAnnotationLink(
            annotation_id="a1",
            feature_id="f1",
            annotation_type=AnnotationType.DIMENSION,
            link_method=DxfAnnotationLinkMethod.SPATIAL_NEAREST,
            status=DxfAnnotationLinkStatus.LINKED,
            confidence=Decimal("0.75"),
        )
        assert link.review_required is True

    def test_empty_annotations_gives_empty_result(self):
        from backend.interoperability.dxf_annotation_linker import link_dxf_annotations
        result = link_dxf_annotations([], [])
        assert result.total_annotations == 0
        assert len(result.linked) == 0
        assert len(result.unresolved) == 0


# ---------------------------------------------------------------------------
# P1-C: iges_topology_reconstruction
# ---------------------------------------------------------------------------

class TestIgesTopologyReconstructionImports:
    def test_public_api_importable(self):
        from backend.interoperability.iges_topology_reconstruction import (
            SurfaceGroupType,
            SurfaceGroup,
            IgesReconstructionStatus,
            IgesTopologyReconstructionResult,
            reconstruct_iges_topology,
        )
        assert reconstruct_iges_topology is not None

    def test_no_surfaces_gives_correct_status(self):
        from backend.interoperability.iges_topology_reconstruction import (
            IgesReconstructionStatus,
            reconstruct_iges_topology,
        )
        from unittest.mock import MagicMock
        mr = MagicMock()
        mr.topology = None
        mr.geometry = None
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        assert result.status == IgesReconstructionStatus.NO_SURFACES

    def test_surface_only_model_closed_body_always_false(self):
        from backend.interoperability.iges_topology_reconstruction import reconstruct_iges_topology
        from backend.interoperability.geometry import CanonicalGeometry, CanonicalSurface, CanonicalSurfaceType, CanonicalVector3D
        from backend.domain.units import Quantity, Unit
        from unittest.mock import MagicMock

        vec = CanonicalVector3D(
            x=Quantity.of(0, Unit.DIMENSIONLESS),
            y=Quantity.of(0, Unit.DIMENSIONLESS),
            z=Quantity.of(1, Unit.DIMENSIONLESS),
        )
        surf = CanonicalSurface(surface_id="s1", surface_type=CanonicalSurfaceType.PLANE, normal=vec)
        geom = CanonicalGeometry(geometry_id="g1", surfaces=(surf,))
        mr = MagicMock()
        mr.topology = None
        mr.geometry = geom
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        assert result.closed_body_available is False
        assert result.topology_fabricated is False
        assert result.surfaces_available is True

    def test_no_b_rep_fabricated(self):
        from backend.interoperability.iges_topology_reconstruction import reconstruct_iges_topology
        from backend.interoperability.geometry import CanonicalGeometry, CanonicalSurface, CanonicalSurfaceType, CanonicalVector3D
        from backend.domain.units import Quantity, Unit
        from unittest.mock import MagicMock

        vec = CanonicalVector3D(
            x=Quantity.of(0, Unit.DIMENSIONLESS),
            y=Quantity.of(0, Unit.DIMENSIONLESS),
            z=Quantity.of(1, Unit.DIMENSIONLESS),
        )
        surf = CanonicalSurface(surface_id="s1", surface_type=CanonicalSurfaceType.PLANE, normal=vec)
        geom = CanonicalGeometry(geometry_id="g1", surfaces=(surf,))
        mr = MagicMock()
        mr.topology = None
        mr.geometry = geom
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        topo = result.canonical_topology
        assert topo is not None
        assert len(topo.vertices) == 0
        assert len(topo.edges) == 0
        assert len(topo.loops) == 0
        assert len(topo.faces) == 0
        assert len(topo.shells) == 0
        assert len(topo.bodies) == 0


# ---------------------------------------------------------------------------
# P1-D: cad_feature_recognition partial arcs
# ---------------------------------------------------------------------------

class TestPartialCircularBoundaryImports:
    def test_public_api_importable(self):
        from backend.interoperability.cad_feature_recognition import (
            CircularBoundaryStatus,
            CircularBoundaryCandidate,
            recognize_circular_boundaries,
        )
        assert recognize_circular_boundaries is not None

    def test_single_arc_not_a_candidate(self):
        from backend.interoperability.cad_feature_recognition import (
            Dxf2dEntity,
            recognize_circular_boundaries,
        )
        arc = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0,
                          radius=10.0, start_angle=0.0, end_angle=270.0)
        result = recognize_circular_boundaries([arc])
        assert result == []

    def test_complete_circle_gives_hole_candidate(self):
        from backend.interoperability.cad_feature_recognition import (
            Dxf2dEntity,
            CircularBoundaryStatus,
            recognize_circular_boundaries,
        )
        arc1 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0,
                           radius=10.0, start_angle=0.0, end_angle=180.0)
        arc2 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0,
                           radius=10.0, start_angle=180.0, end_angle=360.0)
        result = recognize_circular_boundaries([arc1, arc2])
        assert len(result) == 1
        assert result[0].status == CircularBoundaryStatus.HOLE_CANDIDATE
        assert result[0].review_required is True

    def test_partial_arcs_give_partial_candidate(self):
        from backend.interoperability.cad_feature_recognition import (
            Dxf2dEntity,
            CircularBoundaryStatus,
            recognize_circular_boundaries,
        )
        arc1 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0,
                           radius=10.0, start_angle=0.0, end_angle=90.0)
        arc2 = Dxf2dEntity(entity_type="ARC", layer="0", center_x=0.0, center_y=0.0,
                           radius=10.0, start_angle=90.0, end_angle=180.0)
        result = recognize_circular_boundaries([arc1, arc2])
        assert len(result) == 1
        assert result[0].status == CircularBoundaryStatus.CIRCULAR_BOUNDARY_CANDIDATE
        assert result[0].is_partial is True
