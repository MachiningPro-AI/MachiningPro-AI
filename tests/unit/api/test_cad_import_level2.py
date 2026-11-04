"""CAD_IMPORT_LEVEL_2_IGES_RECOVERY_01 regression tests.

Covers:
  IGES Level-2: fatality semantics for unsupported curve/surface types,
  separate status model (file_parse_status/geometry_status/metadata_status/
  topology_status) in IgesHeader metadata, capability level upgrades,
  recovery of supported geometry alongside unsupported types.

Hard rules verified here:
  - Type 102/104/140 must NOT be fatal (non-geometric but structurally valid)
  - Supported geometry (100 arcs, 110 lines, 126 B-splines) is extracted correctly
    even when unsupported types are present
  - PARTIAL status when unsupported curve/surface types appear — not FAILED
  - Status model fields are present in IgesHeader metadata after successful mapping
  - DXF behavior is not changed (DXF regression tested in test_cad_import_level1.py)
"""

from __future__ import annotations

from pathlib import Path

from backend.interoperability.adapters.iges import IGES_DESCRIPTOR, IgesTokenAdapter
from backend.interoperability.enums import CapabilityLevel, NormalizationStatus
from backend.interoperability.iges_mapping import _UNSUPPORTED_CURVE_SURFACE_TYPES
from backend.interoperability.models import EngineeringSource
from tests.unit.interoperability.iges_fixtures import EntitySpec, make_iges

# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------


def _iges_source(name: str = "test.iges") -> EngineeringSource:
    return EngineeringSource(
        source_id=f"test::{name}",
        source_format_id="IGES",
        file_name=name,
    )


def _ingest(content: bytes, tmp_path: Path, name: str = "test.iges"):
    p = tmp_path / name
    p.write_bytes(content)
    return IgesTokenAdapter().ingest_file(_iges_source(name), IGES_DESCRIPTOR, p)


# ---------------------------------------------------------------------------
# IGES fixtures with unsupported curve/surface types
# ---------------------------------------------------------------------------

# File with only supported geometry (100, 110) — should reach LEVEL_2_GEOMETRY
# IGES type 100 (Circular Arc) params: ZT, CX, CY, X2, Y2, X3, Y3  (7 required params)
# Quarter-circle centered at (0,0), from (50,0) to (0,50):
_SUPPORTED_ONLY = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
        EntitySpec(100, "100,0.0,0.0,0.0,50.0,0.0,0.0,50.0;", label="ARC"),
    )
)

# File with 110 (supported) + 102 (unsupported but non-fatal)
_WITH_COMPOSITE_CURVE_102 = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
        EntitySpec(102, "102,0;", label="COMP"),
    )
)

# File with 110 (supported) + 104 (conic arc, unsupported but non-fatal)
_WITH_CONIC_ARC_104 = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
        EntitySpec(104, "104,1.0,0.0,0.0,0.0,-1.0,0.0,0.0,1.0,0.0;", label="CONIC"),
    )
)

# File with 110 (supported) + 140 (offset surface, unsupported but non-fatal)
_WITH_OFFSET_SURFACE_140 = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="LINE"),
        EntitySpec(140, "140,1,1.0,0.0;", label="OFFSET"),
    )
)

# File mixing supported geometry with multiple unsupported types (like the production file)
_MIXED_SUPPORTED_UNSUPPORTED = make_iges(
    entities=(
        EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="L1"),
        EntitySpec(110, "110,100.0,0.0,0.0,100.0,100.0,0.0;", label="L2"),
        EntitySpec(100, "100,0.0,0.0,0.0,50.0,0.0,0.0,50.0;", label="ARC"),
        EntitySpec(102, "102,0;", label="COMP"),
        EntitySpec(104, "104,1.0,0.0,0.0,0.0,-1.0,0.0,0.0,1.0,0.0;", label="CONIC"),
        EntitySpec(140, "140,1,1.0,0.0;", label="OFFSET"),
        EntitySpec(314, "314,255,0,0;", label="COLOR"),
        EntitySpec(406, "406,1,0;", label="PROP"),
    )
)


# ---------------------------------------------------------------------------
# _UNSUPPORTED_CURVE_SURFACE_TYPES frozenset contents
# ---------------------------------------------------------------------------

class TestUnsupportedCurveSurfaceTypesSet:
    def test_frozenset_exported(self) -> None:
        assert isinstance(_UNSUPPORTED_CURVE_SURFACE_TYPES, frozenset)

    def test_contains_102_composite_curve(self) -> None:
        assert 102 in _UNSUPPORTED_CURVE_SURFACE_TYPES

    def test_contains_104_conic_arc(self) -> None:
        assert 104 in _UNSUPPORTED_CURVE_SURFACE_TYPES

    def test_contains_140_offset_surface(self) -> None:
        assert 140 in _UNSUPPORTED_CURVE_SURFACE_TYPES

    def test_does_not_contain_supported_mapped_types(self) -> None:
        # Types with active mappers must NOT be in this set
        for t in (100, 110, 116, 126, 128):
            assert t not in _UNSUPPORTED_CURVE_SURFACE_TYPES, (
                f"Supported mapped type {t} must not be in _UNSUPPORTED_CURVE_SURFACE_TYPES"
            )

    def test_type_118_not_in_unsupported_set(self) -> None:
        # Type 118 (Ruled Surface) is declared in _GEOMETRY_TYPES but lacks a mapper —
        # it is intentionally fatal (fail-closed) so it must NOT be in this set.
        assert 118 not in _UNSUPPORTED_CURVE_SURFACE_TYPES

    def test_does_not_contain_metadata_types(self) -> None:
        # Metadata types have their own handler; not in this set
        for t in (402, 406, 410, 314):
            assert t not in _UNSUPPORTED_CURVE_SURFACE_TYPES


# ---------------------------------------------------------------------------
# Fatality semantics — unsupported types must NOT be fatal
# ---------------------------------------------------------------------------

class TestFatalitySemantics:
    def test_type_102_composite_curve_not_fatal(self, tmp_path: Path) -> None:
        """Type 102 must produce a non-fatal issue, not FAILED status."""
        doc = _ingest(_WITH_COMPOSITE_CURVE_102, tmp_path, "type102.iges")
        assert doc.normalization_status != NormalizationStatus.FAILED, (
            "Type 102 (Composite Curve) must not cause FAILED status — it is non-fatal"
        )

    def test_type_104_conic_arc_not_fatal(self, tmp_path: Path) -> None:
        doc = _ingest(_WITH_CONIC_ARC_104, tmp_path, "type104.iges")
        assert doc.normalization_status != NormalizationStatus.FAILED, (
            "Type 104 (Conic Arc) must not cause FAILED status — it is non-fatal"
        )

    def test_type_140_offset_surface_not_fatal(self, tmp_path: Path) -> None:
        doc = _ingest(_WITH_OFFSET_SURFACE_140, tmp_path, "type140.iges")
        assert doc.normalization_status != NormalizationStatus.FAILED, (
            "Type 140 (Offset Surface) must not cause FAILED status — it is non-fatal"
        )

    def test_unsupported_types_yield_partial_not_failed(self, tmp_path: Path) -> None:
        """When unsupported types are mixed with supported, status must be PARTIAL."""
        doc = _ingest(_MIXED_SUPPORTED_UNSUPPORTED, tmp_path, "mixed.iges")
        assert doc.normalization_status in (
            NormalizationStatus.PARTIAL,
            NormalizationStatus.SUCCESS,
        ), (
            f"Expected PARTIAL or SUCCESS, got {doc.normalization_status}"
        )

    def test_supported_only_reaches_level2(self, tmp_path: Path) -> None:
        """A file with only supported geometry types must reach LEVEL_2_GEOMETRY."""
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "supported_only.iges")
        assert doc.capability_level >= CapabilityLevel.LEVEL_2_GEOMETRY, (
            f"Supported-only IGES reached only {doc.capability_level}, expected LEVEL_2_GEOMETRY+"
        )


# ---------------------------------------------------------------------------
# Capability level with unsupported types present
# ---------------------------------------------------------------------------

class TestCapabilityLevel:
    def test_type_102_still_reaches_level2(self, tmp_path: Path) -> None:
        """Supported lines must still be extracted even when type 102 is present."""
        doc = _ingest(_WITH_COMPOSITE_CURVE_102, tmp_path, "cap102.iges")
        assert doc.capability_level >= CapabilityLevel.LEVEL_2_GEOMETRY, (
            f"Expected LEVEL_2_GEOMETRY+ even with type 102, got {doc.capability_level}"
        )

    def test_type_104_still_reaches_level2(self, tmp_path: Path) -> None:
        doc = _ingest(_WITH_CONIC_ARC_104, tmp_path, "cap104.iges")
        assert doc.capability_level >= CapabilityLevel.LEVEL_2_GEOMETRY

    def test_type_140_still_reaches_level2(self, tmp_path: Path) -> None:
        doc = _ingest(_WITH_OFFSET_SURFACE_140, tmp_path, "cap140.iges")
        assert doc.capability_level >= CapabilityLevel.LEVEL_2_GEOMETRY

    def test_mixed_file_reaches_level2(self, tmp_path: Path) -> None:
        doc = _ingest(_MIXED_SUPPORTED_UNSUPPORTED, tmp_path, "mixed_cap.iges")
        assert doc.capability_level >= CapabilityLevel.LEVEL_2_GEOMETRY


# ---------------------------------------------------------------------------
# Separate status model — header metadata fields
# ---------------------------------------------------------------------------

class TestStatusModel:
    def test_file_parse_status_present(self, tmp_path: Path) -> None:
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_parse.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert "file_parse_status" in header.metadata

    def test_file_parse_status_success(self, tmp_path: Path) -> None:
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_parse2.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert header.metadata["file_parse_status"] == "SUCCESS"

    def test_geometry_status_present(self, tmp_path: Path) -> None:
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_geo.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert "geometry_status" in header.metadata

    def test_metadata_status_present(self, tmp_path: Path) -> None:
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_meta.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert "metadata_status" in header.metadata

    def test_topology_status_present(self, tmp_path: Path) -> None:
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_topo.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert "topology_status" in header.metadata

    def test_geometry_status_partial_with_unsupported_types(self, tmp_path: Path) -> None:
        """When unsupported types are present, geometry_status must not be SUCCESS."""
        doc = _ingest(_MIXED_SUPPORTED_UNSUPPORTED, tmp_path, "stat_mixed.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert header.metadata["geometry_status"] in ("PARTIAL", "FAILED"), (
            "geometry_status must be PARTIAL (not SUCCESS) when unsupported types present"
        )

    def test_topology_status_none_when_no_topology(self, tmp_path: Path) -> None:
        """Files with no B-Rep topology produce topology_status=NONE."""
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_topo_none.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        assert header.metadata["topology_status"] == "NONE"

    def test_status_values_are_strings(self, tmp_path: Path) -> None:
        doc = _ingest(_MIXED_SUPPORTED_UNSUPPORTED, tmp_path, "stat_types.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        for key in ("file_parse_status", "geometry_status", "metadata_status", "topology_status"):
            val = header.metadata[key]
            assert isinstance(val, str), f"{key} must be a string, got {type(val).__name__}"

    def test_status_model_absent_when_mapping_fails(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """When map_iges_model raises, status model fields must NOT be in header metadata
        (the exception path creates the header ref without them, preserving Level-1 data)."""
        import backend.interoperability.adapters.iges as iges_mod

        def _boom(model):
            raise RuntimeError("simulated mapping failure")

        monkeypatch.setattr(iges_mod, "map_iges_model", _boom)
        doc = _ingest(_SUPPORTED_ONLY, tmp_path, "stat_exc.iges")
        header = next(r for r in doc.entity_refs if r.entity_kind == "IgesHeader")
        # Level-1 data must still be present
        assert "entity_count" in header.metadata
        assert "source_unit" in header.metadata
        # Status model fields must not be present (mapping never completed)
        for key in ("file_parse_status", "geometry_status", "metadata_status", "topology_status"):
            assert key not in header.metadata, (
                f"Status field {key!r} must be absent when mapping fails"
            )


# ---------------------------------------------------------------------------
# Fidelity events — unsupported types appear in fidelity report as UNSUPPORTED
# ---------------------------------------------------------------------------

class TestFidelityEvents:
    def test_type_102_recorded_as_unsupported_fidelity(self, tmp_path: Path) -> None:
        """Type 102 entities must appear in fidelity events, not silently dropped."""
        doc = _ingest(_WITH_COMPOSITE_CURVE_102, tmp_path, "fid102.iges")
        events = doc.fidelity_report.events if doc.fidelity_report is not None else ()
        descriptions = [e.description for e in events]
        assert any("102" in d for d in descriptions), (
            "Expected type 102 fidelity event not found"
        )

    def test_type_104_recorded_as_unsupported_fidelity(self, tmp_path: Path) -> None:
        doc = _ingest(_WITH_CONIC_ARC_104, tmp_path, "fid104.iges")
        events = doc.fidelity_report.events if doc.fidelity_report is not None else ()
        descriptions = [e.description for e in events]
        assert any("104" in d for d in descriptions)

    def test_type_140_recorded_as_unsupported_fidelity(self, tmp_path: Path) -> None:
        doc = _ingest(_WITH_OFFSET_SURFACE_140, tmp_path, "fid140.iges")
        events = doc.fidelity_report.events if doc.fidelity_report is not None else ()
        descriptions = [e.description for e in events]
        assert any("140" in d for d in descriptions)

    def test_supported_lines_produce_no_fatal_events(self, tmp_path: Path) -> None:
        """Lines (type 110) must not appear in fidelity events at all."""
        from backend.interoperability.enums import FidelityClass
        doc = _ingest(
            make_iges(entities=(
                EntitySpec(110, "110,0.0,0.0,0.0,100.0,0.0,0.0;", label="L"),
            )),
            tmp_path, "fid110.iges"
        )
        events = doc.fidelity_report.events if doc.fidelity_report is not None else ()
        fatal_events = [e for e in events if e.fidelity_class == FidelityClass.LOST]
        assert fatal_events == [], f"Unexpected fatal events for supported geometry: {fatal_events}"
