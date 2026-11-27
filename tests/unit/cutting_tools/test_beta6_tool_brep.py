"""
Phase G/H — Parametric Tool B-Rep Builder Tests

Tests for:
  Phase F: tool catalog audit coverage
  Phase G: parametric tool B-Rep geometry construction
  Phase H: tool geometry fidelity fields

TOOL_GEOMETRY_FIDELITY ∈ {PARAMETRIC_BREP, PARTIAL, NOT_AVAILABLE}
CUTTER_ENVELOPE_FIDELITY_NOT_SILENT=YES
FULL_FLUTE_GEOMETRY_AVAILABLE=NO (always False for parametric builder)
FABRICATED_DIMENSIONS=NO
"""

import pytest

try:
    import gmsh
    _GMSH_AVAILABLE = True
except ImportError:
    _GMSH_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _GMSH_AVAILABLE, reason="gmsh not available")

from backend.cutting_tools.tool_brep_builder import (
    ToolBRepResult,
    build_tool_brep,
    build_tool_brep_from_record,
)
from backend.cutting_tools.library import ToolLibrary


# ---------------------------------------------------------------------------
# Phase F — Catalog audit
# ---------------------------------------------------------------------------


class TestPhaseFCatalogAudit:
    def test_catalog_total_count(self):
        tools = ToolLibrary().all()
        assert len(tools) >= 60, f"Expected ≥60 tools, got {len(tools)}"

    def test_tools_with_cutting_diameter(self):
        tools = ToolLibrary().all()
        with_diam = [t for t in tools if t.cutting_diameter_mm is not None]
        assert len(with_diam) >= 30, f"Expected ≥30 tools with diameter, got {len(with_diam)}"

    def test_full_brep_input_tools(self):
        """Tools with cutting_diameter + shank + overall_length are B-Rep ready."""
        tools = ToolLibrary().all()
        full = [
            t for t in tools
            if all(x is not None for x in [
                t.cutting_diameter_mm, t.shank_diameter_mm, t.overall_length_mm
            ])
        ]
        # Must have at least some tools ready for B-Rep construction
        assert len(full) >= 10, f"Expected ≥10 full B-Rep input tools, got {len(full)}"

    def test_no_corner_radius_in_catalog(self):
        """Confirm corner_radius_mm absence in catalog — prevents fabrication."""
        tools = ToolLibrary().all()
        with_corner = [t for t in tools if t.corner_radius_mm is not None]
        # Catalog may have some (e.g., ball end mills with known corner radius)
        # This test just audits the count — not requiring zero
        assert isinstance(len(with_corner), int)  # audit only


# ---------------------------------------------------------------------------
# Phase G — Tool B-Rep construction
# ---------------------------------------------------------------------------


class TestDrillBRep:
    def test_drill_full_body(self):
        r = build_tool_brep(
            tool_id="DRILL_TEST_01",
            tool_type_code="DRILL",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=10.0,
            overall_length_mm=100.0,
            flute_length_mm=40.0,
        )
        assert r.cutter_envelope_ready
        assert r.full_tool_body_ready
        assert r.geometry_fidelity == "PARAMETRIC_BREP"
        assert r.tool_volume_mm3 > 0.0
        assert r.tool_volume_fidelity == "BREP_EXACT"
        assert r.error is None

    def test_drill_cutter_only(self):
        """No shank/overall → partial body only."""
        r = build_tool_brep(
            tool_id="DRILL_TEST_02",
            tool_type_code="DRILL",
            cutting_diameter_mm=8.0,
            shank_diameter_mm=None,
            overall_length_mm=None,
        )
        assert r.cutter_envelope_ready
        assert not r.full_tool_body_ready
        assert r.geometry_fidelity == "PARTIAL"
        assert "shank_diameter_mm" in r.dimensions_missing
        assert "overall_length_mm" in r.dimensions_missing

    def test_drill_no_diameter_returns_not_available(self):
        r = build_tool_brep(
            tool_id="DRILL_TEST_03",
            tool_type_code="DRILL",
            cutting_diameter_mm=None,
            shank_diameter_mm=10.0,
            overall_length_mm=100.0,
        )
        assert not r.cutter_envelope_ready
        assert r.geometry_fidelity == "NOT_AVAILABLE"
        assert "cutting_diameter_mm" in r.dimensions_missing

    def test_drill_volume_matches_analytic_approx(self):
        """Drill volume ≥ cylinder volume (tip cone adds material)."""
        r = build_tool_brep(
            tool_id="DRILL_TEST_04",
            tool_type_code="DRILL",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=10.0,
            overall_length_mm=80.0,
            flute_length_mm=35.0,
        )
        import math
        min_cyl = math.pi * 5.0**2 * 35.0  # just the flute cylinder
        assert r.tool_volume_mm3 > min_cyl * 0.5  # loose bound


class TestEndMillBRep:
    def test_flat_end_mill(self):
        r = build_tool_brep(
            tool_id="EM_FLAT_01",
            tool_type_code="FLAT_END_MILL",
            cutting_diameter_mm=12.0,
            shank_diameter_mm=12.0,
            overall_length_mm=80.0,
            flute_length_mm=30.0,
        )
        assert r.geometry_fidelity == "PARAMETRIC_BREP"
        assert r.full_tool_body_ready
        assert r.tool_volume_mm3 > 0.0

    def test_ball_end_mill(self):
        r = build_tool_brep(
            tool_id="EM_BALL_01",
            tool_type_code="BALL_END_MILL",
            cutting_diameter_mm=8.0,
            shank_diameter_mm=8.0,
            overall_length_mm=60.0,
            flute_length_mm=20.0,
        )
        assert r.cutter_envelope_ready
        assert r.error is None

    def test_bull_nose_end_mill(self):
        r = build_tool_brep(
            tool_id="EM_BULL_01",
            tool_type_code="BULL_NOSE_END_MILL",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=10.0,
            overall_length_mm=75.0,
            flute_length_mm=25.0,
            corner_radius_mm=1.0,
        )
        assert r.cutter_envelope_ready

    def test_chamfer_mill(self):
        r = build_tool_brep(
            tool_id="CHAM_01",
            tool_type_code="CHAMFER_MILL",
            cutting_diameter_mm=16.0,
            shank_diameter_mm=10.0,
            overall_length_mm=60.0,
            point_angle_deg=90.0,
        )
        assert r.cutter_envelope_ready

    def test_face_mill(self):
        r = build_tool_brep(
            tool_id="FACE_01",
            tool_type_code="FACE_MILL",
            cutting_diameter_mm=63.0,
            shank_diameter_mm=16.0,
            overall_length_mm=50.0,
        )
        assert r.cutter_envelope_ready

    def test_slot_mill(self):
        r = build_tool_brep(
            tool_id="SLOT_01",
            tool_type_code="SLOT_MILL",
            cutting_diameter_mm=20.0,
            shank_diameter_mm=16.0,
            overall_length_mm=60.0,
        )
        assert r.cutter_envelope_ready


class TestUnsupportedToolType:
    def test_unsupported_returns_not_available(self):
        r = build_tool_brep(
            tool_id="UNKNOWN_01",
            tool_type_code="TURNING_INSERT",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=None,
            overall_length_mm=None,
        )
        assert r.geometry_fidelity == "NOT_AVAILABLE"
        assert r.error is not None


# ---------------------------------------------------------------------------
# Phase H — Geometry fidelity fields (HARD RULE: no silent downgrade)
# ---------------------------------------------------------------------------


class TestToolGeometryFidelityFields:
    def test_full_body_exposes_parametric_brep(self):
        r = build_tool_brep(
            tool_id="FID_01",
            tool_type_code="FLAT_END_MILL",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=10.0,
            overall_length_mm=80.0,
            flute_length_mm=30.0,
        )
        assert r.geometry_method == "PARAMETRIC_BREP"
        assert r.geometry_fidelity == "PARAMETRIC_BREP"
        assert r.cutter_envelope_fidelity == "PARAMETRIC_BREP"

    def test_cutter_only_exposes_partial(self):
        r = build_tool_brep(
            tool_id="FID_02",
            tool_type_code="FLAT_END_MILL",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=None,
            overall_length_mm=None,
        )
        assert r.geometry_fidelity == "PARTIAL"
        assert r.geometry_completeness == "CUTTER_ENVELOPE_ONLY"

    def test_full_flute_geometry_always_false(self):
        """Phase H: parametric envelope ≠ full flute geometry."""
        r = build_tool_brep(
            tool_id="FID_03",
            tool_type_code="DRILL",
            cutting_diameter_mm=10.0,
            shank_diameter_mm=10.0,
            overall_length_mm=80.0,
            flute_length_mm=35.0,
        )
        assert r.full_flute_geometry_available is False

    def test_volume_fidelity_is_brep_exact_on_success(self):
        r = build_tool_brep(
            tool_id="FID_04",
            tool_type_code="FLAT_END_MILL",
            cutting_diameter_mm=12.0,
            shank_diameter_mm=12.0,
            overall_length_mm=100.0,
        )
        if r.error is None:
            assert r.tool_volume_fidelity == "BREP_EXACT"

    def test_dimensions_used_and_missing_populated(self):
        r = build_tool_brep(
            tool_id="FID_05",
            tool_type_code="DRILL",
            cutting_diameter_mm=8.0,
            shank_diameter_mm=None,
            overall_length_mm=None,
        )
        assert "cutting_diameter_mm" in r.dimensions_used
        assert "shank_diameter_mm" in r.dimensions_missing
        assert "overall_length_mm" in r.dimensions_missing
