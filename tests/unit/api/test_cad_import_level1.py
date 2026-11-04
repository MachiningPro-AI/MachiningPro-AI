"""CAD_IMPORT_LEVEL_1 regression tests.

Covers:
  DXF: valid, malformed, unsupported entities, large file, wrong HTTP method,
       entity count, bounds extraction, units extraction
  IGES: valid, malformed, empty sections, directory parsing, parameter parsing,
        entity type distribution, unsupported entities, bounds, units,
        production-style file

All tests are pure-Python, no ezdxf, no cloud, no paid API.
"""

from __future__ import annotations

import io
from pathlib import Path

from backend.api.engineering_import import (
    _detect_format_id,
)
from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR, DxfTokenAdapter
from backend.interoperability.adapters.iges import IGES_DESCRIPTOR, IgesTokenAdapter
from backend.interoperability.enums import CapabilityLevel, NormalizationStatus
from backend.interoperability.models import EngineeringSource
from tests.unit.interoperability.iges_fixtures import EntitySpec, make_iges

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _dxf_source(name: str = "test.dxf") -> EngineeringSource:
    return EngineeringSource(
        source_id=f"test::{name}",
        source_format_id="DXF",
        file_name=name,
    )


def _iges_source(name: str = "test.iges") -> EngineeringSource:
    return EngineeringSource(
        source_id=f"test::{name}",
        source_format_id="IGES",
        file_name=name,
    )


def _ingest_dxf(text: str, tmp_path: Path, name: str = "test.dxf"):
    p = tmp_path / name
    # Write as binary to preserve \r\n on Windows (text mode would double \r)
    p.write_bytes(text.encode("utf-8"))
    return DxfTokenAdapter().ingest_file(_dxf_source(name), DXF_DESCRIPTOR, p)


def _ingest_iges(content: bytes, tmp_path: Path, name: str = "test.iges"):
    p = tmp_path / name
    p.write_bytes(content)
    return IgesTokenAdapter().ingest_file(_iges_source(name), IGES_DESCRIPTOR, p)


# ---------------------------------------------------------------------------
# DXF — valid file with engineering geometry
# ---------------------------------------------------------------------------

_VALID_DXF = (
    "  0\nSECTION\n"
    "  2\nHEADER\n"
    "  9\n$ACADVER\n"
    "  1\nAC1015\n"
    "  9\n$INSUNITS\n"
    " 70\n4\n"   # Millimeters
    "  9\n$EXTMIN\n"
    " 10\n-10.0\n"
    " 20\n-5.0\n"
    "  9\n$EXTMAX\n"
    " 10\n150.0\n"
    " 20\n75.0\n"
    "  0\nENDSEC\n"
    "  0\nSECTION\n"
    "  2\nENTITIES\n"
    "  0\nLINE\n  8\n0\n 10\n0.0\n 20\n0.0\n 11\n100.0\n 21\n0.0\n"
    "  0\nLINE\n  8\n0\n 10\n100.0\n 20\n0.0\n 11\n100.0\n 21\n50.0\n"
    "  0\nCIRCLE\n  8\nHOLES\n 10\n50.0\n 20\n25.0\n 40\n12.5\n"
    "  0\nARC\n  8\nHOLES\n 10\n80.0\n 20\n25.0\n 40\n10.0\n"
    "  0\nTEXT\n  8\nANNOTATIONS\n  1\nTITLE\n"
    "  0\nMTEXT\n  8\nANNOTATIONS\n  1\nNOTES\n"
    "  0\nINSERT\n  2\nBOLT\n  8\nFASTENERS\n"
    "  0\nENDSEC\n"
    "  0\nEOF\n"
)


class TestDxfValid:
    def test_capability_level_1(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_1_PARSED,
            CapabilityLevel.LEVEL_2_GEOMETRY,
            CapabilityLevel.LEVEL_3_ENGINEERING_SEMANTICS,
        )

    def test_entity_count(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header.metadata["entity_line"] == 2
        assert header.metadata["entity_circle"] == 1
        assert header.metadata["entity_arc"] == 1
        assert header.metadata["entity_text"] == 1
        assert header.metadata["entity_mtext"] == 1
        assert header.metadata["entity_insert"] == 1

    def test_dxf_version(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header.metadata["dxf_version"] == "AC1015"

    def test_units_extraction(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header.metadata["units"] == "Millimeters"

    def test_bounds_extraction(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        # Bounds come from entity coordinates, not just $EXTMIN/$EXTMAX
        assert "xmin" in header.metadata
        assert "xmax" in header.metadata
        assert "ymin" in header.metadata
        assert "ymax" in header.metadata
        assert header.metadata["xmin"] <= 0.0
        assert header.metadata["xmax"] >= 100.0

    def test_layers_extraction(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        layers = str(header.metadata.get("layers", ""))
        assert "HOLES" in layers
        assert "ANNOTATIONS" in layers

    def test_layer_count(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header.metadata["layer_count"] >= 3  # 0, HOLES, ANNOTATIONS, FASTENERS

    def test_no_unsupported_for_common_entities(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        unsupported = str(header.metadata.get("unsupported_entities", ""))
        assert unsupported == "" or unsupported == "None"

    def test_normalization_status_success(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        # Without ezdxf Level 2 reports UNSUPPORTED; Level 1 is SUCCESS
        assert doc.normalization_status in (
            NormalizationStatus.SUCCESS,
            NormalizationStatus.UNSUPPORTED,
            NormalizationStatus.PARTIAL,
        )


# ---------------------------------------------------------------------------
# DXF — malformed file (no group codes)
# ---------------------------------------------------------------------------

class TestDxfMalformed:
    def test_fails_closed_on_random_bytes(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.dxf"
        p.write_bytes(b"\xff\xfe\x00\x01\x00\x02binary garbage")
        doc = DxfTokenAdapter().ingest_file(_dxf_source("bad.dxf"), DXF_DESCRIPTOR, p)
        assert doc.capability_level == CapabilityLevel.LEVEL_0_RECOGNIZED

    def test_fails_closed_on_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.dxf"
        p.write_text("", encoding="utf-8")
        doc = DxfTokenAdapter().ingest_file(_dxf_source("empty.dxf"), DXF_DESCRIPTOR, p)
        assert doc.capability_level == CapabilityLevel.LEVEL_0_RECOGNIZED
        assert doc.normalization_status == NormalizationStatus.FAILED

    def test_partial_dxf_still_parsed(self, tmp_path: Path) -> None:
        # Has valid group codes but no ENTITIES section
        text = "  0\nSECTION\n  2\nHEADER\n  9\n$ACADVER\n  1\nAC1009\n  0\nENDSEC\n"
        doc = _ingest_dxf(text, tmp_path, "partial.dxf")
        assert doc.capability_level == CapabilityLevel.LEVEL_1_PARSED

    def test_wrong_http_method_endpoint_exists(self) -> None:
        """DXF endpoint is POST /api/import — a GET would return 405.
        Verify the endpoint registration is correct."""
        from fastapi.testclient import TestClient

        from backend.api.app import app
        from backend.api.engineering_import import require_user

        # Confirm POST /api/import returns 422 (no file) not 405 (wrong method)
        app.dependency_overrides[require_user] = lambda: {"sub": "test"}
        try:
            client = TestClient(app, raise_server_exceptions=False)
            resp = client.post("/api/import")
            # 422 = Unprocessable Entity (missing required 'file' field) — NOT 405
            assert resp.status_code in (400, 422), (
                f"Expected 422 not 405 on POST /api/import; got {resp.status_code}"
            )
        finally:
            app.dependency_overrides.pop(require_user, None)


# ---------------------------------------------------------------------------
# DXF — unsupported entity types
# ---------------------------------------------------------------------------

class TestDxfUnsupportedEntities:
    def test_unknown_entity_logged_as_unsupported(self, tmp_path: Path) -> None:
        text = (
            "  0\nSECTION\n  2\nENTITIES\n"
            "  0\nOLDPROPRIETARYENT\n  8\n0\n"
            "  0\nENDSEC\n  0\nEOF\n"
        )
        doc = _ingest_dxf(text, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        unsupported = str(header.metadata.get("unsupported_entities", ""))
        assert "OLDPROPRIETARYENT" in unsupported

    def test_known_geometry_entities_not_flagged_unsupported(self, tmp_path: Path) -> None:
        text = (
            "  0\nSECTION\n  2\nENTITIES\n"
            "  0\nSPLINE\n  8\n0\n"
            "  0\nELLIPSE\n  8\n0\n"
            "  0\nLWPOLYLINE\n  8\n0\n"
            "  0\nENDSEC\n  0\nEOF\n"
        )
        doc = _ingest_dxf(text, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        unsupported = str(header.metadata.get("unsupported_entities", ""))
        assert "SPLINE" not in unsupported
        assert "ELLIPSE" not in unsupported
        assert "LWPOLYLINE" not in unsupported


# ---------------------------------------------------------------------------
# DXF — large file
# ---------------------------------------------------------------------------

class TestDxfLargeFile:
    def test_large_dxf_entity_count_accurate(self, tmp_path: Path) -> None:
        # 5000 LINE entities — use \n so Windows text mode is irrelevant
        lines = ["  0\nSECTION\n  2\nENTITIES\n"]
        for i in range(5000):
            lines.append(
                f"  0\nLINE\n  8\n0\n"
                f" 10\n{i * 1.0}\n 20\n0.0\n"
                f" 11\n{i * 1.0 + 1.0}\n 21\n1.0\n"
            )
        lines.append("  0\nENDSEC\n  0\nEOF\n")
        doc = _ingest_dxf("".join(lines), tmp_path, "large.dxf")
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_1_PARSED,
            CapabilityLevel.LEVEL_2_GEOMETRY,
        )
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header.metadata["entity_line"] == 5000


# ---------------------------------------------------------------------------
# DXF — API endpoint response model check
# ---------------------------------------------------------------------------

class TestDxfApiResponse:
    def test_api_response_includes_common_cad_fields(self, tmp_path: Path) -> None:
        """Simulate the engineering_import endpoint processing of a DXF file."""
        from backend.api.engineering_import import (
            _get_registry,
            _minimal_descriptor,
        )

        data = _VALID_DXF.encode("utf-8")
        filename = "drawing.dxf"
        format_id, family_str = _detect_format_id(data[:512], filename)
        assert format_id == "DXF"

        registry = _get_registry()
        source = EngineeringSource(
            source_id=f"test::{filename}",
            source_format_id=format_id,
            file_name=filename,
        )
        descriptor = _minimal_descriptor(format_id, family_str)
        adapters = registry.find_by_format(format_id)
        assert adapters, "DXF must be in the default registry"

        p = tmp_path / filename
        p.write_text(_VALID_DXF, encoding="utf-8")
        doc = adapters[0].ingest_file(source, descriptor, p)
        assert doc.capability_level in (
            CapabilityLevel.LEVEL_1_PARSED,
            CapabilityLevel.LEVEL_2_GEOMETRY,
            CapabilityLevel.LEVEL_3_ENGINEERING_SEMANTICS,
        )

    def test_units_millimeters_in_dxf_header(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert header.metadata.get("units") == "Millimeters"

    def test_bounds_populated_from_entity_coords(self, tmp_path: Path) -> None:
        doc = _ingest_dxf(_VALID_DXF, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "DxfHeader")
        assert float(header.metadata["xmax"]) >= 100.0
        assert float(header.metadata["ymax"]) >= 50.0


# ---------------------------------------------------------------------------
# IGES — valid minimal file
# ---------------------------------------------------------------------------

_MINIMAL_IGES_LINE = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
    )
)

_IGES_MULTI_ENTITY = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="L1"),
        EntitySpec(110, "110,0.0,0.0,0.0,0.0,100.0,0.0;", label="L2"),
        EntitySpec(100, "100,0.0,0.0,0.0,50.0,0.0,360.0;", label="ARC"),
        EntitySpec(116, "116,10.0,10.0,10.0;", label="PT"),
        EntitySpec(314, "314,255,0,0;", label="RED"),
    )
)


class TestIgesValid:
    def test_capability_level_1_minimum(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_MINIMAL_IGES_LINE, tmp_path)
        assert doc.capability_level >= CapabilityLevel.LEVEL_1_PARSED

    def test_entity_count(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_MINIMAL_IGES_LINE, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert header.metadata["entity_count"] == 1

    def test_entity_type_distribution(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        # Entity type keys are entity_<name_snake_case>
        assert header.metadata["entity_line"] == 2
        assert header.metadata["entity_circular_arc"] == 1
        assert header.metadata["entity_point"] == 1
        assert header.metadata["entity_color_definition"] == 1

    def test_units_in_header(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_MINIMAL_IGES_LINE, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        # unit_name from global section — should be a string
        unit = header.metadata.get("source_unit")
        assert unit is not None
        assert isinstance(unit, str)

    def test_metadata_values_are_json_scalar(self, tmp_path: Path) -> None:
        """All header metadata values must be JSON-safe scalars (no Decimal/dict/list)."""
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        for k, v in header.metadata.items():
            assert isinstance(v, (str, int, float, bool, type(None))), (
                f"Metadata key {k!r} has non-scalar type {type(v).__name__}"
            )

    def test_iges_version_reported(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_MINIMAL_IGES_LINE, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        # iges_version should be int or None (from global section)
        v = header.metadata.get("iges_version")
        assert v is None or isinstance(v, int)


# ---------------------------------------------------------------------------
# IGES — malformed / empty sections
# ---------------------------------------------------------------------------

class TestIgesMalformed:
    def test_empty_fails_closed(self, tmp_path: Path) -> None:
        p = tmp_path / "empty.iges"
        p.write_bytes(b"")
        doc = IgesTokenAdapter().ingest_file(_iges_source("empty.iges"), IGES_DESCRIPTOR, p)
        assert doc.normalization_status == NormalizationStatus.FAILED

    def test_random_bytes_fails_closed(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.iges"
        p.write_bytes(bytes(range(256)) * 10)
        doc = IgesTokenAdapter().ingest_file(_iges_source("bad.iges"), IGES_DESCRIPTOR, p)
        assert doc.capability_level == CapabilityLevel.LEVEL_0_RECOGNIZED

    def test_map_iges_model_exception_preserved_at_level_1(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """If map_iges_model raises, capability must stay at LEVEL_1 not fall to LEVEL_0."""
        import backend.interoperability.adapters.iges as iges_mod

        def _boom(model):
            raise RuntimeError("simulated mapping failure")

        monkeypatch.setattr(iges_mod, "map_iges_model", _boom)
        doc = _ingest_iges(_MINIMAL_IGES_LINE, tmp_path)
        # Must be LEVEL_1 (mark_parsed was called before map_iges_model)
        assert doc.capability_level == CapabilityLevel.LEVEL_1_PARSED
        # normalization status = PARTIAL (not FAILED from outer except)
        assert doc.normalization_status in (
            NormalizationStatus.PARTIAL,
            NormalizationStatus.SUCCESS,
        )


# ---------------------------------------------------------------------------
# IGES — directory entry and parameter data parsing
# ---------------------------------------------------------------------------

class TestIgesDirectoryParsing:
    def test_entity_directory_entries_present(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        # entity_refs should include at least the header + mapped entity refs
        assert len(doc.entity_refs) >= 1

    def test_section_counts_in_metadata(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        counts = header.metadata.get("section_counts")
        assert counts is not None
        # section_counts is serialized as a string representation of a dict
        assert isinstance(counts, str)

    def test_multiple_entity_types_distributed(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert header.metadata["entity_count"] == 5


# ---------------------------------------------------------------------------
# IGES — unsupported entity tracking
# ---------------------------------------------------------------------------

class TestIgesUnsupportedEntities:
    def test_unknown_iges_entity_type_flagged(self, tmp_path: Path) -> None:
        # Entity type 999 is not in the standard — should appear in unsupported list
        iges_with_unknown = make_iges(
            entities=(
                EntitySpec(110, "110,0.0,0.0,0.0,1.0,0.0,0.0;", label="LINE"),
                EntitySpec(999, "999,0.0;", label="UNKNOWN"),
            )
        )
        doc = _ingest_iges(iges_with_unknown, tmp_path, "unknown_ent.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        unsupported = str(header.metadata.get("unsupported_entity_types", ""))
        assert "type_999" in unsupported

    def test_known_entity_not_in_unsupported(self, tmp_path: Path) -> None:
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        unsupported = str(header.metadata.get("unsupported_entity_types", ""))
        # Types 110, 100, 116, 314 are all in _IGES_ENTITY_NAMES
        assert "type_110" not in unsupported
        assert "type_100" not in unsupported


# ---------------------------------------------------------------------------
# IGES — production-style: large multi-entity file
# ---------------------------------------------------------------------------

class TestIgesProductionStyle:
    def test_production_style_iges_parsed_at_level_1(self, tmp_path: Path) -> None:
        """Simulate a production IGES with many entity types."""
        entities = (
            # Mix of B-spline curves/surfaces, arcs, lines, points, trimmed surfaces
            EntitySpec(
                126,
                "126,1,1,1,0,1,0,0.0,1.0,1.0,0.0,0.0,0.0,1.0,1.0,0.0,0.0,0.0,1.0,1.0;",
                label="BSP1",
            ),
            EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="L1"),
            EntitySpec(110, "110,100.0,0.0,0.0,100.0,100.0,0.0;", label="L2"),
            EntitySpec(100, "100,0.0,50.0,0.0,50.0,0.0,360.0;", label="ARC1"),
            EntitySpec(116, "116,0.0,0.0,0.0;", label="PT1"),
            EntitySpec(314, "314,128,128,128;", label="GRAY"),
        )
        large_iges = make_iges(entities=entities)
        doc = _ingest_iges(large_iges, tmp_path, "production.iges")
        assert doc.capability_level >= CapabilityLevel.LEVEL_1_PARSED
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert header.metadata["entity_count"] == len(entities)

    def test_map_failure_does_not_discard_global_section_metadata(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Even when geometry mapping fails, global section metadata must survive."""
        import backend.interoperability.adapters.iges as iges_mod

        def _boom(model):
            raise RuntimeError("mapping crash")

        monkeypatch.setattr(iges_mod, "map_iges_model", _boom)
        doc = _ingest_iges(_IGES_MULTI_ENTITY, tmp_path)
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        # global section metadata must be present
        assert "source_unit" in header.metadata
        assert "entity_count" in header.metadata
        assert header.metadata["entity_count"] == 5


# ---------------------------------------------------------------------------
# Common CAD response model — via API endpoint helpers
# ---------------------------------------------------------------------------

def _make_api_client():
    """Create TestClient with auth dependency overridden."""
    from fastapi.testclient import TestClient

    from backend.api.app import app
    from backend.api.engineering_import import require_user

    app.dependency_overrides[require_user] = lambda: {"sub": "test"}
    client = TestClient(app)
    return client, app, require_user


class TestCommonCadResponseModel:
    def test_dxf_response_has_all_level1_fields(self, tmp_path: Path) -> None:
        """Validate the API endpoint produces all common CAD response fields."""
        client, app, require_user = _make_api_client()
        try:
            data = _VALID_DXF.encode("utf-8")
            resp = client.post(
                "/api/import",
                files={"file": ("drawing.dxf", io.BytesIO(data), "application/octet-stream")},
            )
        finally:
            app.dependency_overrides.pop(require_user, None)

        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        body = resp.json()

        # Legacy fields
        assert "file_name" in body
        assert "format_id" in body
        assert body["format_id"] == "DXF"
        assert "import_status" in body
        assert "capability_level" in body
        assert "entity_count" in body

        # CAD Level-1 common fields
        assert "status" in body
        assert "format" in body
        assert "source_file_name" in body
        assert "file_size_bytes" in body
        assert "entity_types" in body
        assert "unsupported_entities" in body
        assert "warnings" in body
        assert "errors" in body

        # Field type checks
        assert isinstance(body["entity_types"], dict)
        assert isinstance(body["unsupported_entities"], list)
        assert isinstance(body["warnings"], list)
        assert isinstance(body["errors"], list)

        # Units must be set (millimeters DXF)
        assert body.get("units") == "Millimeters"

        # Entity types populated
        assert body["entity_types"].get("Line", 0) >= 2

        # Bounds populated from entity coordinates
        assert body["bounds"] is not None
        assert body["bounds"]["xmax"] >= 100.0

    def test_iges_response_capability_at_least_level_1(self, tmp_path: Path) -> None:
        client, app, require_user = _make_api_client()
        try:
            resp = client.post(
                "/api/import",
                files={"file": (
                    "model.iges", io.BytesIO(_MINIMAL_IGES_LINE), "application/octet-stream",
                )},
            )
        finally:
            app.dependency_overrides.pop(require_user, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["format_id"] == "IGES"
        # After our fix, IGES parse should reach LEVEL_1 minimum
        assert body["capability_level"] != "LEVEL_0_RECOGNIZED", (
            "IGES parse succeeded but capability is stuck at LEVEL_0"
        )

    def test_file_size_bytes_accurate(self, tmp_path: Path) -> None:
        client, app, require_user = _make_api_client()
        try:
            data = _VALID_DXF.encode("utf-8")
            resp = client.post(
                "/api/import",
                files={"file": ("drawing.dxf", io.BytesIO(data), "application/octet-stream")},
            )
        finally:
            app.dependency_overrides.pop(require_user, None)

        assert resp.status_code == 200
        body = resp.json()
        assert body["file_size_bytes"] == len(data)
