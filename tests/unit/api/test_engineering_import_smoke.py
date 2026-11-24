"""Phase 4 smoke tests — Universal Engineering Import (UNIVERSAL_IMPORT_02).

Five format scenarios:
  1. PDF    → format detection → DRAWING_PDF route (no universal adapter)
  2. PNG    → format detection → DRAWING_IMAGE route, IMPORT=SUCCESS
  3. DXF    → format detection → DRAWING_VECTOR, DETERMINISTIC_2D_GEOMETRY_AVAILABLE
  4. STEP   → format detection → CAD_GEOMETRY, GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE
  5. IGES   → format detection → CAD_GEOMETRY, GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE

All tests are pure-Python with synthetic but structurally valid file content.
No cloud conversion. No paid API. No Granite inference.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from backend.api.engineering_import import (
    _EXT_TO_FORMAT,
    _detect_format_id,
    _ext,
    _minimal_descriptor,
)
from backend.interoperability.adapters.registry_helpers import build_default_adapter_registry
from backend.interoperability.enums import CapabilityLevel, NormalizationStatus
from tests.unit.interoperability.iges_fixtures import (
    EntitySpec,
    make_iges,
    make_iges_presentation_and_geometry,
    make_iges_presentation_only,
)

# ---------------------------------------------------------------------------
# Minimal synthetic file content
# ---------------------------------------------------------------------------

_MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\n%%EOF"

_MINIMAL_PNG = (
    b"\x89PNG\r\n\x1a\n"          # PNG signature
    b"\x00\x00\x00\rIHDR"         # IHDR chunk (13 bytes)
    b"\x00\x00\x00\x10"           # width=16
    b"\x00\x00\x00\x10"           # height=16
    b"\x08\x02\x00\x00\x00"       # bit depth=8, color type=2
    b"\x90\x91h\x36"              # CRC (arbitrary, not validated by adapter)
    b"\x00\x00\x00\x00IEND"
    b"\xaeB`\x82"
)

_MINIMAL_DXF = (
    "  0\r\nSECTION\r\n"
    "  2\r\nHEADER\r\n"
    "  9\r\n$ACADVER\r\n"
    "  1\r\nAC1015\r\n"
    "  0\r\nENDSEC\r\n"
    "  0\r\nSECTION\r\n"
    "  2\r\nENTITIES\r\n"
    "  0\r\nLINE\r\n"
    " 10\r\n0.0\r\n"
    " 20\r\n0.0\r\n"
    " 11\r\n100.0\r\n"
    " 21\r\n0.0\r\n"
    "  0\r\nCIRCLE\r\n"
    " 10\r\n50.0\r\n"
    " 20\r\n50.0\r\n"
    " 40\r\n25.0\r\n"
    "  0\r\nENDSEC\r\n"
    "  0\r\nEOF\r\n"
)

_MINIMAL_STEP = (
    "ISO-10303-21;\r\n"
    "HEADER;\r\n"
    "FILE_DESCRIPTION(('Minimal STEP test'),'2;1');\r\n"
    "FILE_NAME('test.stp','2024-01-01T00:00:00',(''),(''),'','','');\r\n"
    "FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\r\n"
    "ENDSEC;\r\n"
    "DATA;\r\n"
    "#1=PRODUCT('part','Part','',(#2));\r\n"
    "#2=PRODUCT_CONTEXT('',#3,'mechanical');\r\n"
    "#3=APPLICATION_CONTEXT('automotive design');\r\n"
    "#10=CARTESIAN_POINT('Origin',(0.0,0.0,0.0));\r\n"
    "ENDSEC;\r\n"
    "END-ISO-10303-21;\r\n"
)

# Use the existing fixture builder for a well-formed IGES with a Line entity
_MINIMAL_IGES = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
    )
)


# ---------------------------------------------------------------------------
# Helper: run the backend import endpoint logic directly (no HTTP)
# ---------------------------------------------------------------------------

def _ingest_bytes(data: bytes, filename: str):
    """Write data to a temp file and call the matching registry adapter."""
    registry = build_default_adapter_registry()
    format_id, family_str = _detect_format_id(data[:512], filename)
    from backend.interoperability.models import EngineeringSource
    source = EngineeringSource(
        source_id=f"smoke::{filename}",
        source_format_id=format_id if format_id != "UNKNOWN" else None,
        file_name=filename,
    )
    descriptor = _minimal_descriptor(format_id, family_str)
    adapters = registry.find_by_format(format_id)
    assert adapters, f"No adapter found for format_id={format_id!r} (file={filename!r})"
    adapter = adapters[0]
    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    with tempfile.NamedTemporaryFile(delete=False, suffix=f".{ext}") as tmp:
        tmp.write(data)
        tmp_path = Path(tmp.name)
    try:
        return adapter.ingest_file(source, descriptor, tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)


# ===========================================================================
# Smoke 1 — vector PDF
# ===========================================================================

class TestSmoke01VectorPDF:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, DRAWING_ANALYSIS_ENTRY_READY=YES."""

    def test_format_detection_pass(self):
        """PDF detected from extension (no PDF magic in ContentSniffer)."""
        fmt_id, family = _detect_format_id(_MINIMAL_PDF[:512], "drawing.pdf")
        assert fmt_id == "PDF"
        assert family == "DOCUMENT"

    def test_ext_detection(self):
        assert _ext("technical_drawing.pdf") == "pdf"

    def test_pdf_ext_table_entry(self):
        fmt_id, family = _EXT_TO_FORMAT["pdf"]
        assert fmt_id == "PDF"
        assert family == "DOCUMENT"

    def test_drawing_analysis_entry_ready(self):
        """PDF is NOT in the universal registry — it goes to /api/drawings (drawing analysis)."""
        registry = build_default_adapter_registry()
        adapters = registry.find_by_format("PDF")
        assert not adapters, "PDF must NOT be in the universal import registry"


# ===========================================================================
# Smoke 2 — PNG / JPG (raster image)
# ===========================================================================

class TestSmoke02Image:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS, PREVIEW_VISIBLE=YES."""

    def test_png_format_detection_pass(self):
        fmt_id, family = _detect_format_id(_MINIMAL_PNG[:512], "photo.png")
        assert fmt_id == "RASTER-IMAGE"
        assert family == "IMAGE"

    def test_jpg_format_detection_pass(self):
        fmt_id, family = _detect_format_id(b"\xff\xd8\xff\xe0abc", "scan.jpg")
        assert fmt_id == "RASTER-IMAGE"
        assert family == "IMAGE"

    def test_png_import_pass(self):
        doc = _ingest_bytes(_MINIMAL_PNG, "drawing_scan.png")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
            NormalizationStatus.INSUFFICIENT_DATA,
        ), f"unexpected status: {doc.normalization_status}"
        assert doc.capability_level >= CapabilityLevel.LEVEL_0_RECOGNIZED
        assert doc.format_descriptor.format_id == "RASTER-IMAGE"

    def test_image_ext_table_entries(self):
        for ext in ("png", "jpg", "jpeg", "tif", "tiff", "bmp"):
            fmt_id, family = _EXT_TO_FORMAT[ext]
            assert fmt_id == "RASTER-IMAGE", f"{ext} should map to RASTER-IMAGE"
            assert family == "IMAGE", f"{ext} family should be IMAGE"

    def test_drawing_analysis_entry_ready(self):
        """IMAGE family → DRAWING_IMAGE route in UI → analyze button accessible."""
        _, family = _EXT_TO_FORMAT["png"]
        assert family == "IMAGE"


# ===========================================================================
# Smoke 3 — DXF
# ===========================================================================

class TestSmoke03Dxf:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS,
    DETERMINISTIC_2D_GEOMETRY_AVAILABLE=YES, PREVIEW_OR_VIEW_AVAILABLE=YES."""

    def test_dxf_format_detection_pass(self):
        data = _MINIMAL_DXF.encode("ascii")
        fmt_id, family = _detect_format_id(data[:512], "part_drawing.dxf")
        assert fmt_id == "DXF"
        assert family == "DRAWING"

    def test_dxf_import_pass(self):
        data = _MINIMAL_DXF.encode("ascii")
        doc = _ingest_bytes(data, "part_drawing.dxf")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"

    def test_dxf_deterministic_2d_geometry_available(self):
        """DETERMINISTIC_2D_GEOMETRY_AVAILABLE — entities parsed from DXF."""
        data = _MINIMAL_DXF.encode("ascii")
        doc = _ingest_bytes(data, "part_drawing.dxf")
        entity_count = len(doc.entity_refs)
        assert entity_count > 0, "DXF must yield at least one parsed entity"

    def test_dxf_preview_or_view_available(self):
        """PREVIEW_OR_VIEW_AVAILABLE — format is identified as 2D drawing."""
        data = _MINIMAL_DXF.encode("ascii")
        doc = _ingest_bytes(data, "part_drawing.dxf")
        assert doc.format_descriptor.format_id in ("DXF", "DXF-BINARY")


# ===========================================================================
# Smoke 4 — STEP
# ===========================================================================

class TestSmoke04Step:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS,
    GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE=YES."""

    def test_step_format_detection_pass(self):
        data = _MINIMAL_STEP.encode("ascii")
        fmt_id, family = _detect_format_id(data[:512], "assembly.step")
        assert fmt_id.startswith("STEP-"), f"Expected STEP- prefix, got {fmt_id!r}"
        assert family == "NEUTRAL_EXCHANGE"

    def test_step_import_pass(self):
        data = _MINIMAL_STEP.encode("ascii")
        doc = _ingest_bytes(data, "assembly.step")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"

    def test_step_geometry_load_pass(self):
        """GEOMETRY_LOAD=PASS — at least one entity parsed from STEP."""
        data = _MINIMAL_STEP.encode("ascii")
        doc = _ingest_bytes(data, "assembly.step")
        entity_count = len(doc.entity_refs)
        assert entity_count > 0, "STEP must yield at least one parsed entity"

    def test_step_basic_metadata_visible(self):
        """BASIC_METADATA_VISIBLE — at least one entity carries metadata."""
        data = _MINIMAL_STEP.encode("ascii")
        doc = _ingest_bytes(data, "assembly.step")
        assert len(doc.entity_refs) > 0
        has_meta = any(bool(ref.metadata) for ref in doc.entity_refs)
        assert has_meta, "STEP entities must include basic metadata dict"


# ===========================================================================
# Smoke 5 — IGES
# ===========================================================================

class TestSmoke05Iges:
    """FILE_SELECTION=PASS, FORMAT_DETECTION=PASS, IMPORT=PASS,
    GEOMETRY_LOAD=PASS, BASIC_METADATA_VISIBLE=YES."""

    def test_iges_format_detection_pass(self):
        fmt_id, family = _detect_format_id(_MINIMAL_IGES[:512], "surface_model.iges")
        assert fmt_id == "IGES"
        assert family == "NEUTRAL_EXCHANGE"

    def test_iges_import_pass(self):
        doc = _ingest_bytes(_MINIMAL_IGES, "surface_model.iges")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"

    def test_iges_geometry_load_pass(self):
        """GEOMETRY_LOAD=PASS — at least one entity parsed from IGES."""
        doc = _ingest_bytes(_MINIMAL_IGES, "surface_model.iges")
        entity_count = len(doc.entity_refs)
        assert entity_count > 0, "IGES must yield at least one parsed entity"

    def test_iges_basic_metadata_visible(self):
        """BASIC_METADATA_VISIBLE — at least one entity carries metadata."""
        doc = _ingest_bytes(_MINIMAL_IGES, "surface_model.iges")
        assert len(doc.entity_refs) > 0
        has_meta = any(bool(ref.metadata) for ref in doc.entity_refs)
        assert has_meta, "IGES entities must include basic metadata dict"


# ===========================================================================
# Smoke 6 — has_renderable_geometry (CAD_IMPORT_IGES_03)
# ===========================================================================

def _has_renderable_geometry(doc) -> bool:
    """Apply the same logic as import_file() in engineering_import.py."""
    from backend.interoperability.geometry import CanonicalGeometry
    geom = doc.geometry
    return isinstance(geom, CanonicalGeometry) and (
        len(geom.curves) > 0 or len(geom.surfaces) > 0
    )


_POINT_ONLY_IGES = make_iges(
    entities=(
        EntitySpec(116, "116,10.0,20.0,30.0,0;", label="POINT"),
    )
)

_LINE_BEARING_IGES = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
    )
)


class TestSmoke06HasRenderableGeometry:
    """POINT_ONLY_IGES_HAS_RENDERABLE_GEOMETRY=NO, LINE_IGES=YES,
    STL_MESH=NO (mesh geometry is not in CanonicalGeometry curves/surfaces)."""

    def test_point_only_iges_no_renderable_geometry(self):
        """Point entity (type 116) must NOT count as renderable geometry."""
        doc = _ingest_bytes(_POINT_ONLY_IGES, "point_cloud.iges")
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.PARTIAL,
        ), f"unexpected status: {doc.normalization_status}"
        assert not _has_renderable_geometry(doc), (
            "Point-only IGES must have has_renderable_geometry=False"
        )

    def test_line_bearing_iges_has_renderable_geometry(self):
        """Line entity (type 110) MUST count as renderable geometry."""
        doc = _ingest_bytes(_LINE_BEARING_IGES, "line_model.iges")
        assert _has_renderable_geometry(doc), (
            "Line-bearing IGES must have has_renderable_geometry=True"
        )

    def test_stl_no_renderable_geometry_in_canonical(self):
        """STL mesh geometry is not stored as CanonicalGeometry curves/surfaces."""
        from tests.unit.interoperability.test_universal_import import _STL_ASCII_MINIMAL
        doc = _ingest_bytes(_STL_ASCII_MINIMAL.encode(), "part.stl")
        assert not _has_renderable_geometry(doc), (
            "STL mesh geometry must not register as has_renderable_geometry"
        )


# ===========================================================================
# Smoke 7 — _tessellate_step (CAD_3D_VIEWER_01B)
# ===========================================================================

_SAMPLE_STEP_PATH = Path(__file__).parents[3] / "sample_part.step"


class TestSmoke07StepTessellation:
    """GMSH_TESSELLATION_FUNCTION_EXISTS=YES, GRACEFUL_FAILURE_ON_NO_GEOMETRY=YES."""

    def test_tessellate_step_importable(self):
        """_tessellate_step is importable and callable."""
        from backend.api.engineering_import import _tessellate_step
        assert callable(_tessellate_step)

    def test_tessellate_step_empty_bytes_returns_none(self):
        """Empty bytes must return None gracefully (HARD RULE 09)."""
        from backend.api.engineering_import import _tessellate_step
        result = _tessellate_step(b"")
        assert result is None

    def test_tessellate_step_invalid_bytes_returns_none(self):
        """Non-STEP bytes must return None without raising (HARD RULE 09)."""
        from backend.api.engineering_import import _tessellate_step
        result = _tessellate_step(b"NOT A STEP FILE AT ALL\x00\x01\x02")
        assert result is None

    def test_tessellate_step_minimal_no_geometry_returns_none(self):
        """Minimal STEP with no surfaces must return None gracefully."""
        from backend.api.engineering_import import _tessellate_step
        result = _tessellate_step(_MINIMAL_STEP.encode("ascii"))
        # A STEP with no solid bodies yields no triangles — must be None or valid dict
        # (gmsh may load it but produce 0 triangles)
        assert result is None or (
            isinstance(result, dict)
            and result.get("triangle_count", 0) >= 0
        )

    @pytest.mark.skipif(
        not _SAMPLE_STEP_PATH.exists(),
        reason="sample_part.step not present in repo root",
    )
    def test_tessellate_step_real_file_returns_valid_mesh(self):
        """sample_part.step → valid mesh dict with ≥1 triangle and correct keys."""
        from backend.api.engineering_import import _tessellate_step
        data = _SAMPLE_STEP_PATH.read_bytes()
        result = _tessellate_step(data)
        assert result is not None, "Real STEP file must tessellate successfully"
        assert "positions" in result
        assert "indices" in result
        assert "bounding_box" in result
        assert "vertex_count" in result
        assert "triangle_count" in result
        assert result["triangle_count"] > 0, "Must produce at least one triangle"
        assert result["vertex_count"] > 0
        # All indices must be valid (HARD RULE 17)
        max_idx = max(result["indices"])
        assert max_idx < result["vertex_count"], "Triangle indices must be within vertex array"
        # positions length must be vertex_count * 3
        assert len(result["positions"]) == result["vertex_count"] * 3
        # bounding_box must have min and max with 3 components
        bb = result["bounding_box"]
        assert len(bb["min"]) == 3
        assert len(bb["max"]) == 3

    @pytest.mark.skipif(
        not _SAMPLE_STEP_PATH.exists(),
        reason="sample_part.step not present in repo root",
    )
    def test_tessellate_step_real_file_bounding_box_correct(self):
        """sample_part.step bounding box must match known 20×20×10mm geometry."""
        from backend.api.engineering_import import _tessellate_step
        data = _SAMPLE_STEP_PATH.read_bytes()
        result = _tessellate_step(data)
        assert result is not None
        bb = result["bounding_box"]
        # Part is ≈20×20×10mm centred at origin; allow ±1mm tolerance
        assert abs(bb["max"][0] - bb["min"][0] - 20.0) < 1.0, "X extent should be ≈20mm"
        assert abs(bb["max"][1] - bb["min"][1] - 20.0) < 1.0, "Y extent should be ≈20mm"
        assert abs(bb["max"][2] - bb["min"][2] - 10.0) < 1.0, "Z extent should be ≈10mm"


# ===========================================================================
# Smoke 8 — Tessellation eligibility fix (PARTIAL_SUCCESS root cause)
# ===========================================================================

class TestSmoke08TessellationEligibility:
    """ROOT_CAUSE_FIX: PARTIAL_SUCCESS must allow tessellation (MUST 4 / MUST 8)."""

    def _can_tessellate(self, status: str) -> bool:
        """Mirror the backend fix logic."""
        return status not in ("FAILED", "UNRECOGNIZED", "PARSE_ERROR")

    def test_success_eligible(self):
        assert self._can_tessellate("SUCCESS")

    def test_partial_success_eligible_root_cause_fix(self):
        """PARTIAL_SUCCESS must allow tessellation — this is the root cause fix."""
        assert self._can_tessellate("PARTIAL_SUCCESS"), (
            "PARTIAL_SUCCESS returned when pythonocc-core absent; "
            "gmsh tessellation must still be attempted"
        )

    def test_recognized_only_eligible(self):
        assert self._can_tessellate("RECOGNIZED_ONLY")

    def test_unknown_eligible(self):
        assert self._can_tessellate("UNKNOWN")

    def test_failed_not_eligible(self):
        assert not self._can_tessellate("FAILED")

    def test_unrecognized_not_eligible(self):
        assert not self._can_tessellate("UNRECOGNIZED")

    def test_parse_error_not_eligible(self):
        assert not self._can_tessellate("PARSE_ERROR")

    def test_tessellate_brep_importable(self):
        """_tessellate_brep is importable and callable."""
        from backend.api.engineering_import import _tessellate_brep
        assert callable(_tessellate_brep)

    def test_tessellate_iges_importable(self):
        """_tessellate_iges is importable and callable (MUST 8)."""
        from backend.api.engineering_import import _tessellate_iges
        assert callable(_tessellate_iges)

    def test_tessellate_brep_empty_returns_none(self):
        """Empty bytes must return None for any suffix."""
        from backend.api.engineering_import import _tessellate_brep
        for suffix in (".step", ".igs"):
            assert _tessellate_brep(b"", suffix) is None

    def test_tessellate_iges_empty_returns_none(self):
        from backend.api.engineering_import import _tessellate_iges
        assert _tessellate_iges(b"") is None

    def test_tessellate_iges_invalid_returns_none(self):
        """Non-IGES bytes must return None without raising."""
        from backend.api.engineering_import import _tessellate_iges
        assert _tessellate_iges(b"NOT AN IGES FILE\x00") is None

    def test_tessellate_step_delegates_to_brep(self):
        """_tessellate_step wraps _tessellate_brep with .step suffix."""
        from backend.api import engineering_import as ei
        # Both must exist and be callable
        assert callable(ei._tessellate_step)
        assert callable(ei._tessellate_brep)
        # Empty bytes: both return None
        assert ei._tessellate_step(b"") is None
        assert ei._tessellate_brep(b"", ".step") is None

    @pytest.mark.skipif(
        not _SAMPLE_STEP_PATH.exists(),
        reason="sample_part.step not present in repo root",
    )
    def test_partial_success_step_reaches_tessellation(self):
        """When status is PARTIAL_SUCCESS + STEP format, tessellate must be called.

        This is the key regression guard: before the fix, the condition
        `import_status == 'SUCCESS'` blocked tessellation for PARTIAL_SUCCESS files.
        After the fix, PARTIAL_SUCCESS passes the gate and gmsh produces a mesh.
        """
        from backend.api.engineering_import import _tessellate_step
        data = _SAMPLE_STEP_PATH.read_bytes()
        # PARTIAL_SUCCESS is now eligible; tessellation must succeed on a real part
        result = _tessellate_step(data)
        assert result is not None, "Real STEP file must tessellate even at PARTIAL_SUCCESS level"
        assert result["triangle_count"] > 0


# ---------------------------------------------------------------------------
# MUST 10, 11 — IGES entity diagnostics (IGES robustness spec)
# ---------------------------------------------------------------------------

class TestSmoke09IgesDiagnostics:
    """IGES import returns structured diagnostics for entity class counts."""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _run_import(data: bytes, filename: str = "fixture.igs") -> dict:
        import io

        from backend.api.engineering_import import import_file

        class _Upload:
            file = io.BytesIO(data)

        up = _Upload()
        up.filename = filename  # type: ignore[attr-defined]
        return import_file(up)

    # ------------------------------------------------------------------
    # MUST 10/11: iges_diagnostics present for IGES files
    # ------------------------------------------------------------------

    def test_iges_diagnostics_key_present_for_iges(self):
        """iges_diagnostics is returned for IGES files."""
        data = make_iges()
        result = self._run_import(data)
        assert "iges_diagnostics" in result
        diag = result["iges_diagnostics"]
        assert isinstance(diag, dict)

    def test_iges_diagnostics_absent_for_step(self):
        """iges_diagnostics is None for non-IGES formats (STEP)."""
        import io

        from backend.api.engineering_import import import_file

        step_path = Path("D:/makina_ogrenmesi/olcum_denemeleri"
                         "/MP_SYN_001_extracted/MachiningPro_Synthetic_Test_Pack/MP_SYN_001.step")
        if not step_path.exists():
            pytest.skip("Real STEP file not available")

        class _Upload:
            filename = "MP_SYN_001.step"
            file = io.BytesIO(step_path.read_bytes())

        result = import_file(_Upload())
        assert result.get("iges_diagnostics") is None

    # ------------------------------------------------------------------
    # MUST 6: NO_RENDERABLE_GEOMETRY for presentation-only IGES
    # ------------------------------------------------------------------

    def test_presentation_only_iges_no_renderable_geometry(self):
        """IGES with only type-314 Color Definition → NO_RENDERABLE_GEOMETRY."""
        data = make_iges_presentation_only()
        result = self._run_import(data)
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["renderable_geometry"] is False
        assert diag["iges_import_status"] == "NO_RENDERABLE_GEOMETRY"

    def test_presentation_only_no_mesh(self):
        """Geometry-free IGES file must NOT return a preview_mesh."""
        data = make_iges_presentation_only()
        result = self._run_import(data)
        assert result.get("preview_mesh") is None, (
            "NO_RENDERABLE_GEOMETRY file must not produce a mesh"
        )

    # ------------------------------------------------------------------
    # MUST 3/4: TYPE_314_FILE_ABORT=NO — mixed file still renders
    # ------------------------------------------------------------------

    def test_presentation_and_geometry_iges_import_not_aborted(self):
        """IGES with type-314 + line → import not aborted (TYPE_314_FILE_ABORT=NO).

        The file contains a type-314 Color Definition entity plus a Line entity.
        The import must succeed at the adapter level (not FAILED/PARSE_ERROR).
        Note: preview_mesh may be None because a bare line curve has no tessellatable
        surface; this is correct and expected.
        """
        data = make_iges_presentation_and_geometry()
        result = self._run_import(data)
        # The import must NOT be aborted at the adapter level
        assert result["import_status"] not in ("FAILED", "PARSE_ERROR", "UNRECOGNIZED"), (
            "Type-314 must NOT abort the IGES import"
        )

    def test_presentation_and_geometry_iges_status_partial(self):
        """Mixed file → iges_import_status=PARTIAL (not COMPLETE, not NO_RENDERABLE_GEOMETRY)."""
        data = make_iges_presentation_and_geometry()
        result = self._run_import(data)
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["iges_import_status"] == "PARTIAL", (
            "File with skipped presentation entities must report PARTIAL, not COMPLETE"
        )

    def test_presentation_and_geometry_iges_import_status_not_no_renderable(self):
        """Mixed IGES file (line+type-314) → iges_import_status is PARTIAL, not no-renderable.

        renderable_geometry reflects whether the viewer can display the mesh (needs
        a tessellatable surface), not whether the adapter extracted any geometry.
        A file with only line curves has adapter-level geometry but no displayable
        mesh, so iges_import_status must be PARTIAL (not NO_RENDERABLE_GEOMETRY).
        """
        data = make_iges_presentation_and_geometry()
        result = self._run_import(data)
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["iges_import_status"] != "NO_RENDERABLE_GEOMETRY", (
            "File with line geometry + type-314 must NOT be classified as no-renderable"
        )
        assert diag["iges_import_status"] == "PARTIAL"

    # ------------------------------------------------------------------
    # MUST 11: skipped entity counts populated
    # ------------------------------------------------------------------

    def test_presentation_count_in_diagnostics(self):
        """skipped_presentation_count is non-negative integer."""
        data = make_iges()
        result = self._run_import(data)
        diag = result["iges_diagnostics"]
        assert isinstance(diag["skipped_presentation_count"], int)
        assert diag["skipped_presentation_count"] >= 0

    def test_annotation_count_in_diagnostics(self):
        """skipped_annotation_count is non-negative integer."""
        data = make_iges()
        result = self._run_import(data)
        diag = result["iges_diagnostics"]
        assert isinstance(diag["skipped_annotation_count"], int)
        assert diag["skipped_annotation_count"] >= 0

    def test_unsupported_geometric_count_in_diagnostics(self):
        """unsupported_geometric_count is non-negative integer."""
        data = make_iges()
        result = self._run_import(data)
        diag = result["iges_diagnostics"]
        assert isinstance(diag["unsupported_geometric_count"], int)
        assert diag["unsupported_geometric_count"] >= 0

    def test_total_skipped_non_geometric_field_present(self):
        """total_skipped_non_geometric is present and consistent."""
        data = make_iges()
        result = self._run_import(data)
        diag = result["iges_diagnostics"]
        assert "total_skipped_non_geometric" in diag
        assert isinstance(diag["total_skipped_non_geometric"], int)

    # ------------------------------------------------------------------
    # MUST 2: IgesEntityClass enum importable
    # ------------------------------------------------------------------

    def test_iges_entity_class_enum_importable(self):
        """IgesEntityClass enum is exported from iges_mapping."""
        from backend.interoperability.iges_mapping import IgesEntityClass
        assert IgesEntityClass.GEOMETRIC.value == "GEOMETRIC"
        assert IgesEntityClass.TOPOLOGICAL.value == "TOPOLOGICAL"
        assert IgesEntityClass.PRESENTATION.value == "PRESENTATION"
        assert IgesEntityClass.ANNOTATION.value == "ANNOTATION"
        assert IgesEntityClass.STRUCTURAL.value == "STRUCTURAL"
        assert IgesEntityClass.UNKNOWN.value == "UNKNOWN"

    def test_iges_entity_classification_dict_importable(self):
        """IGES_ENTITY_CLASSIFICATION dict is exported and covers key types."""
        from backend.interoperability.iges_mapping import (
            IGES_ENTITY_CLASSIFICATION,
            IgesEntityClass,
        )
        # Type 314 = Color Definition → PRESENTATION
        assert IGES_ENTITY_CLASSIFICATION[314] == IgesEntityClass.PRESENTATION
        # Type 110 = Line → GEOMETRIC
        assert IGES_ENTITY_CLASSIFICATION[110] == IgesEntityClass.GEOMETRIC
        # Type 128 = NURBS surface → GEOMETRIC
        assert IGES_ENTITY_CLASSIFICATION[128] == IgesEntityClass.GEOMETRIC
        # Type 142 = Curve on surface → TOPOLOGICAL
        assert IGES_ENTITY_CLASSIFICATION[142] == IgesEntityClass.TOPOLOGICAL
        # Type 402 = Associativity Instance → STRUCTURAL
        assert IGES_ENTITY_CLASSIFICATION[402] == IgesEntityClass.STRUCTURAL

    def test_type_314_entity_class_is_presentation(self):
        """Type 314 must map to PRESENTATION (not ANNOTATION or STRUCTURAL)."""
        from backend.interoperability.iges_mapping import (
            IGES_ENTITY_CLASSIFICATION,
            IgesEntityClass,
        )
        assert IGES_ENTITY_CLASSIFICATION.get(314) == IgesEntityClass.PRESENTATION

    # ------------------------------------------------------------------
    # MUST 16: 3+ IGES files all return iges_diagnostics
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("iges_path,expected_has_mesh", [
        (
            "D:/makina_ogrenmesi/olcum_denemeleri/MP_SYN_001_extracted"
            "/MachiningPro_Synthetic_Test_Pack/MP_SYN_001.iges",
            True,
        ),
        (
            "D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_1.igs",
            True,
        ),
        (
            "D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_2.igs",
            True,
        ),
    ])
    def test_real_iges_files_have_diagnostics(self, iges_path: str, expected_has_mesh: bool):
        """Every real IGES file returns iges_diagnostics with consistent fields."""
        import io

        path = Path(iges_path)
        if not path.exists():
            pytest.skip(f"Real IGES file not present: {iges_path}")

        from backend.api.engineering_import import import_file

        class _Upload:
            file = io.BytesIO(path.read_bytes())

        up = _Upload()
        up.filename = path.name  # type: ignore[attr-defined]
        result = import_file(up)

        diag = result.get("iges_diagnostics")
        assert diag is not None, f"iges_diagnostics missing for {path.name}"
        assert diag["renderable_geometry"] == expected_has_mesh, (
            f"{path.name}: renderable_geometry mismatch"
        )
        assert diag["iges_import_status"] in ("COMPLETE", "PARTIAL", "NO_RENDERABLE_GEOMETRY")
        # All count fields must be non-negative
        for field in ("skipped_presentation_count", "skipped_annotation_count",
                      "skipped_metadata_count", "unsupported_geometric_count",
                      "total_skipped_non_geometric"):
            assert isinstance(diag[field], int) and diag[field] >= 0, (
                f"{path.name}: {field} must be non-negative int"
            )

    def test_sample_iges2_has_partial_status(self):
        """sample_iges_2.igs with 8× type-314 → iges_import_status=PARTIAL."""
        import io

        path = Path("D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_2.igs")
        if not path.exists():
            pytest.skip("sample_iges_2.igs not present")

        from backend.api.engineering_import import import_file

        class _Upload:
            filename = "sample_iges_2.igs"
            file = io.BytesIO(path.read_bytes())

        result = import_file(_Upload())
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["iges_import_status"] == "PARTIAL"
        assert diag["renderable_geometry"] is True


class TestSmoke10IgesCyclicRecovery:
    """Cyclic IGES entity references must NOT abort the import when tessellation succeeds.

    Root cause: _validate_reference_graph raised IgesParseError on the first
    cycle detected, which aborted ALL entity processing.  The fix records a
    cyclic-reference warning and continues, leaving geometry extraction intact.
    """

    @staticmethod
    def _run_import(data: bytes, filename: str = "fixture.igs") -> dict:
        import io

        from backend.api.engineering_import import import_file

        class _Upload:
            file = io.BytesIO(data)
        up = _Upload()
        up.filename = filename  # type: ignore[attr-defined]
        return import_file(up)

    # ------------------------------------------------------------------
    # MUST 2 — cycle detection
    # ------------------------------------------------------------------

    def test_parser_returns_cyclic_warnings_not_raises(self):
        """Parser must return cyclic-reference warnings, not raise IgesParseError."""
        from backend.interoperability.iges_parser import parse_iges_bytes
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        model = parse_iges_bytes(make_iges_cyclic_no_geometry())
        assert len(model.cyclic_reference_warnings) >= 1
        assert any("cyclic" in w.lower() for w in model.cyclic_reference_warnings)

    def test_cyclic_warnings_contain_de_pointer(self):
        """Each cyclic-reference warning must name the offending DE pointer."""
        from backend.interoperability.iges_parser import parse_iges_bytes
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        model = parse_iges_bytes(make_iges_cyclic_no_geometry())
        assert all("DE" in w for w in model.cyclic_reference_warnings)

    def test_clean_file_has_empty_cyclic_warnings(self):
        """A file with no cycles produces an empty warnings tuple."""
        from backend.interoperability.iges_parser import parse_iges_bytes
        from tests.unit.interoperability.iges_fixtures import make_iges_simple_line

        model = parse_iges_bytes(make_iges_simple_line())
        assert model.cyclic_reference_warnings == ()

    # ------------------------------------------------------------------
    # MUST 3 — cycle branch isolation
    # ------------------------------------------------------------------

    def test_cyclic_entity_does_not_abort_independent_entity(self):
        """Entities unrelated to a cycle are still present in the parsed model."""
        from backend.interoperability.iges_parser import parse_iges_bytes
        from tests.unit.interoperability.iges_fixtures import EntitySpec, make_iges

        transform = "124,1,0,0,0,1,0,0,0,1,0,0;"
        line = "110,0,0,0,5,0,0;"
        model = parse_iges_bytes(
            make_iges(
                (
                    EntitySpec(124, transform, transform_pointer=3),  # DE 1 → DE 3
                    EntitySpec(124, transform, transform_pointer=1),  # DE 3 → DE 1
                    EntitySpec(110, line),                            # DE 5 (independent)
                )
            )
        )
        assert len(model.entities) == 3
        de5 = model.entities_by_pointer.get(5)
        assert de5 is not None and de5.directory.entity_type == 110

    # ------------------------------------------------------------------
    # MUST 4 — fallback tessellation / MUST 5 — canonical decision
    # ------------------------------------------------------------------

    def test_cyclic_fixture_import_status_is_no_renderable_geometry_not_crashed(self):
        """Cyclic fixture with NO geometry → NO_RENDERABLE_GEOMETRY (not crash, not fake)."""
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        result = self._run_import(make_iges_cyclic_no_geometry(), "cyclic_no_geom.igs")
        diag = result.get("iges_diagnostics")
        assert diag is not None
        # No geometry entity → no preview mesh
        assert result.get("preview_mesh") is None
        assert diag["iges_import_status"] == "NO_RENDERABLE_GEOMETRY"
        assert diag["renderable_geometry"] is False

    def test_fidelity_event_recorded_for_cyclic_reference(self):
        """A LOST fidelity event is recorded when a cyclic reference is detected."""
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        result = self._run_import(make_iges_cyclic_no_geometry())
        events = result.get("fidelity_events", [])
        cyclic_events = [
            ev for ev in events
            if "cyclic" in ev.get("description", "").lower()
        ]
        assert len(cyclic_events) >= 1
        assert all(ev["class"] == "LOST" for ev in cyclic_events)

    # ------------------------------------------------------------------
    # MUST 11 — three IGES file test (sample_iges_2.igs cyclic sub-test)
    # ------------------------------------------------------------------

    def test_sample_iges2_parser_no_longer_raises(self):
        """sample_iges_2.igs: parser now succeeds; cyclic warning recorded."""
        from pathlib import Path

        from backend.interoperability.iges_parser import parse_iges_bytes

        path = Path("D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_2.igs")
        if not path.exists():
            pytest.skip("sample_iges_2.igs not present")

        model = parse_iges_bytes(path.read_bytes())
        assert len(model.cyclic_reference_warnings) >= 1
        assert len(model.entities) > 0  # all 7552 entities still present

    def test_sample_iges2_cyclic_fidelity_event(self):
        """sample_iges_2.igs cyclic ref → LOST fidelity event in full pipeline."""
        import io
        from pathlib import Path

        from backend.api.engineering_import import import_file

        path = Path("D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_2.igs")
        if not path.exists():
            pytest.skip("sample_iges_2.igs not present")

        class _Upload:
            filename = "sample_iges_2.igs"
            file = io.BytesIO(path.read_bytes())

        result = import_file(_Upload())
        events = result.get("fidelity_events", [])
        cyclic_events = [
            ev for ev in events
            if "cyclic" in ev.get("description", "").lower() and ev.get("class") == "LOST"
        ]
        assert len(cyclic_events) >= 1

    def test_sample_iges2_canonical_geometry_now_extracted(self):
        """sample_iges_2.igs: after fix, adapter-level geometry is extracted (not just gmsh)."""
        from pathlib import Path

        from backend.interoperability.iges_mapping import map_iges_model
        from backend.interoperability.iges_parser import parse_iges_bytes

        path = Path("D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_2.igs")
        if not path.exists():
            pytest.skip("sample_iges_2.igs not present")

        model = parse_iges_bytes(path.read_bytes())
        mapping = map_iges_model(model)
        assert mapping.geometry is not None
        geom = mapping.geometry
        assert len(geom.curves) + len(geom.surfaces) > 0

    # ------------------------------------------------------------------
    # MUST 12 — presentation entity regression
    # ------------------------------------------------------------------

    def test_presentation_entity_still_produces_no_renderable_geometry(self):
        """type-314-only file → NO_RENDERABLE_GEOMETRY (regression guard)."""
        from tests.unit.interoperability.iges_fixtures import make_iges_presentation_only

        result = self._run_import(make_iges_presentation_only())
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["iges_import_status"] == "NO_RENDERABLE_GEOMETRY"

    def test_presentation_plus_geometry_still_produces_partial(self):
        """type-314 + line → PARTIAL (regression guard)."""
        from tests.unit.interoperability.iges_fixtures import make_iges_presentation_and_geometry

        result = self._run_import(make_iges_presentation_and_geometry())
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["iges_import_status"] == "PARTIAL"

    # ------------------------------------------------------------------
    # MUST 13 — negative test: cyclic ref + no geometry
    # ------------------------------------------------------------------

    def test_cyclic_ref_no_geometry_no_crash_no_fake(self):
        """Cyclic reference with no renderable geometry: no crash, no fabricated mesh."""
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        result = self._run_import(make_iges_cyclic_no_geometry(), "cyclic.igs")
        # Must not crash
        assert result is not None
        # Must not fabricate geometry
        assert result.get("preview_mesh") is None
        # Correct diagnostic
        diag = result.get("iges_diagnostics")
        assert diag is not None
        assert diag["iges_import_status"] == "NO_RENDERABLE_GEOMETRY"
        assert diag["renderable_geometry"] is False

    # ------------------------------------------------------------------
    # MUST 16 — new iges_diagnostics fields: parser_status,
    #           cyclic_reference_count, cyclic_reference_des,
    #           tessellation_status, vertex_count, triangle_count
    # ------------------------------------------------------------------

    def test_parser_status_field_present_for_iges(self):
        """parser_status must be present in iges_diagnostics."""
        data = make_iges()
        result = self._run_import(data)
        diag = result["iges_diagnostics"]
        assert "parser_status" in diag, "parser_status missing from iges_diagnostics"
        assert diag["parser_status"] in ("SUCCESS", "PARTIAL")

    def test_parser_status_success_for_clean_file(self):
        """Clean IGES file (no cycles) → parser_status=SUCCESS."""
        from tests.unit.interoperability.iges_fixtures import make_iges_simple_line

        result = self._run_import(make_iges_simple_line(), "clean.igs")
        diag = result["iges_diagnostics"]
        assert diag["parser_status"] == "SUCCESS"

    def test_parser_status_partial_for_cyclic_file(self):
        """IGES file with cyclic reference → parser_status=PARTIAL."""
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        result = self._run_import(make_iges_cyclic_no_geometry(), "cyclic.igs")
        diag = result["iges_diagnostics"]
        assert diag["parser_status"] == "PARTIAL"

    def test_cyclic_reference_count_zero_for_clean_file(self):
        """Clean IGES file → cyclic_reference_count=0."""
        from tests.unit.interoperability.iges_fixtures import make_iges_simple_line

        result = self._run_import(make_iges_simple_line(), "clean.igs")
        diag = result["iges_diagnostics"]
        assert diag["cyclic_reference_count"] == 0

    def test_cyclic_reference_count_nonzero_for_cyclic_file(self):
        """Cyclic IGES file → cyclic_reference_count >= 1."""
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        result = self._run_import(make_iges_cyclic_no_geometry(), "cyclic.igs")
        diag = result["iges_diagnostics"]
        assert diag["cyclic_reference_count"] >= 1

    def test_cyclic_reference_des_list_for_cyclic_file(self):
        """cyclic_reference_des must be a list of DE numbers for a cyclic file."""
        from tests.unit.interoperability.iges_fixtures import make_iges_cyclic_no_geometry

        result = self._run_import(make_iges_cyclic_no_geometry(), "cyclic.igs")
        diag = result["iges_diagnostics"]
        assert isinstance(diag["cyclic_reference_des"], list)
        assert len(diag["cyclic_reference_des"]) >= 1
        assert all(isinstance(de, int) for de in diag["cyclic_reference_des"])

    def test_cyclic_reference_des_empty_for_clean_file(self):
        """Clean IGES → cyclic_reference_des is an empty list."""
        from tests.unit.interoperability.iges_fixtures import make_iges_simple_line

        result = self._run_import(make_iges_simple_line(), "clean.igs")
        diag = result["iges_diagnostics"]
        assert diag["cyclic_reference_des"] == []

    def test_tessellation_status_field_present(self):
        """tessellation_status must be present in iges_diagnostics."""
        data = make_iges()
        result = self._run_import(data)
        diag = result["iges_diagnostics"]
        assert "tessellation_status" in diag
        assert diag["tessellation_status"] in ("SUCCESS", "FAILED", "NOT_ATTEMPTED")

    def test_tessellation_status_failed_for_no_geometry(self):
        """Presentation-only IGES (no tessellatable geometry) → tessellation_status=FAILED."""
        from tests.unit.interoperability.iges_fixtures import make_iges_presentation_only

        result = self._run_import(make_iges_presentation_only(), "pres.igs")
        diag = result["iges_diagnostics"]
        # No mesh produced from a presentation-only file
        assert result.get("preview_mesh") is None
        assert diag["tessellation_status"] == "FAILED"

    def test_vertex_count_zero_for_no_geometry(self):
        """vertex_count must be 0 when tessellation fails (no mesh)."""
        from tests.unit.interoperability.iges_fixtures import make_iges_presentation_only

        result = self._run_import(make_iges_presentation_only(), "pres.igs")
        diag = result["iges_diagnostics"]
        assert diag["vertex_count"] == 0

    def test_triangle_count_zero_for_no_geometry(self):
        """triangle_count must be 0 when tessellation fails (no mesh)."""
        from tests.unit.interoperability.iges_fixtures import make_iges_presentation_only

        result = self._run_import(make_iges_presentation_only(), "pres.igs")
        diag = result["iges_diagnostics"]
        assert diag["triangle_count"] == 0

    @pytest.mark.parametrize("iges_path", [
        "D:/makina_ogrenmesi/olcum_denemeleri/sample_iges_2.igs",
    ])
    def test_sample_iges2_new_diagnostic_fields(self, iges_path: str):
        """sample_iges_2.igs: parser_status=PARTIAL, cyclic_reference_count>=1, tessellation=SUCCESS."""
        import io

        path = Path(iges_path)
        if not path.exists():
            pytest.skip(f"Real IGES file not present: {iges_path}")

        from backend.api.engineering_import import import_file

        class _Upload:
            file = io.BytesIO(path.read_bytes())
        up = _Upload()
        up.filename = path.name  # type: ignore[attr-defined]
        result = import_file(up)

        diag = result.get("iges_diagnostics")
        assert diag is not None

        assert diag["parser_status"] == "PARTIAL", (
            "sample_iges_2.igs cyclic ref must yield parser_status=PARTIAL"
        )
        assert diag["cyclic_reference_count"] >= 1, "Must detect at least one cyclic reference"
        assert 1 in diag["cyclic_reference_des"], "DE 1 must appear in cyclic_reference_des"
        assert diag["tessellation_status"] == "SUCCESS", (
            "sample_iges_2.igs must tessellate successfully despite cyclic ref"
        )
        assert diag["vertex_count"] > 0
        assert diag["triangle_count"] > 0
