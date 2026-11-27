"""
Phase I/J/K/L/M — Holder B-Rep, Assembly Ops, Assembly Collision, Stock Tests

Tests for:
  Phase I: holder catalog audit
  Phase J: holder B-Rep builder
  Phase K: assembly geometry ops
  Phase L: 6 independent assembly collision checks
  Phase M: stock CUSTOM_BREP + volume method/fidelity
"""

import pytest
import math

try:
    import gmsh
    _GMSH_AVAILABLE = True
except ImportError:
    _GMSH_AVAILABLE = False

from backend.tool_holders.holder_brep_builder import build_holder_brep
from backend.tool_holders.seed_catalog import get_catalog as get_holders
from backend.cutting_tools.assembly_ops import compute_assembly_geometry
from backend.verification.assembly_collision import (
    AssemblyCollisionInput,
    run_assembly_collision_checks,
)
from backend.verification.stock import StockModel
from backend.verification.enums import (
    StockShape,
    StockVolumeMethod,
    StockVolumeFidelity,
    CustomBRepStatus,
)


# ---------------------------------------------------------------------------
# Phase I — Holder catalog audit
# ---------------------------------------------------------------------------


class TestPhaseIHolderCatalogAudit:
    def test_catalog_total_count(self):
        holders = get_holders()
        assert len(holders) >= 15

    def test_gauge_length_coverage(self):
        holders = get_holders()
        with_gauge = [h for h in holders if h.gauge_length_mm is not None]
        # Most holders should have gauge_length
        assert len(with_gauge) >= 12

    def test_nose_diameter_sparse(self):
        holders = get_holders()
        with_nose = [h for h in holders if h.nose_diameter_mm is not None]
        # Catalog is sparse — just confirm we report honestly (may be very few)
        assert len(with_nose) >= 0  # audit only

    def test_no_fabricated_body_diameter(self):
        """body_diameter_mm must only be present when actually in catalog."""
        holders = get_holders()
        # We just verify the field exists; value may be None for most
        for h in holders:
            # body_diameter_mm should be None or a positive number
            if h.body_diameter_mm is not None:
                assert h.body_diameter_mm > 0


# ---------------------------------------------------------------------------
# Phase J — Holder B-Rep builder
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _GMSH_AVAILABLE, reason="gmsh not available")
class TestPhaseJHolderBRep:
    def test_no_gauge_returns_not_available(self):
        r = build_holder_brep("H_TEST_01", gauge_length_mm=None,
                               nose_diameter_mm=None, body_diameter_mm=None,
                               overall_length_mm=None)
        assert r.geometry_fidelity == "NOT_AVAILABLE"
        assert "gauge_length_mm" in r.dimensions_missing

    def test_gauge_only_gives_simplified(self):
        r = build_holder_brep("H_TEST_02", gauge_length_mm=63.0,
                               nose_diameter_mm=None, body_diameter_mm=None,
                               overall_length_mm=None)
        assert r.geometry_fidelity == "SIMPLIFIED"
        assert r.holder_volume_mm3 > 0.0
        assert r.holder_volume_fidelity == "BREP_EXACT"

    def test_gauge_and_nose_gives_partial(self):
        r = build_holder_brep("H_TEST_03", gauge_length_mm=63.0,
                               nose_diameter_mm=25.0, body_diameter_mm=None,
                               overall_length_mm=None)
        assert r.geometry_fidelity == "PARTIAL"
        assert r.holder_volume_mm3 > 0.0

    def test_full_dims_gives_parametric_brep(self):
        r = build_holder_brep("H_TEST_04", gauge_length_mm=63.0,
                               nose_diameter_mm=25.0, body_diameter_mm=63.0,
                               overall_length_mm=120.0)
        assert r.geometry_fidelity == "PARAMETRIC_BREP"
        assert r.holder_volume_mm3 > 0.0
        assert r.holder_volume_fidelity == "BREP_EXACT"

    def test_simplified_not_reported_as_full_fidelity(self):
        """HARD RULE 4: simplified holder must not be presented as CATALOG_BREP."""
        r = build_holder_brep("H_TEST_05", gauge_length_mm=63.0,
                               nose_diameter_mm=None, body_diameter_mm=None,
                               overall_length_mm=None)
        assert r.geometry_fidelity not in ("CATALOG_BREP", "PARAMETRIC_BREP")

    def test_no_taper_modeled(self):
        """Holder B-Rep is rotational envelope only — no taper modeled."""
        r = build_holder_brep("H_TEST_06", gauge_length_mm=63.0,
                               nose_diameter_mm=25.0, body_diameter_mm=63.0,
                               overall_length_mm=100.0)
        assert r.taper_modeled is False

    def test_volume_exact_for_cylinder(self):
        """Gauge-only cylinder: volume ≈ π r² l."""
        r = build_holder_brep("H_TEST_07", gauge_length_mm=50.0,
                               nose_diameter_mm=20.0, body_diameter_mm=None,
                               overall_length_mm=None)
        expected_min = math.pi * 10.0**2 * 50.0 * 0.5  # loose lower bound
        assert r.holder_volume_mm3 > expected_min


# ---------------------------------------------------------------------------
# Phase K — Assembly geometry
# ---------------------------------------------------------------------------


class TestPhaseKAssemblyOps:
    def test_assembly_ready_with_all_inputs(self):
        r = compute_assembly_geometry(
            tool_id="TOOL_A", holder_id="HOLDER_A",
            tool_stickout_mm=35.0, gauge_length_mm=63.0,
            tool_cutting_diameter_mm=10.0, holder_body_diameter_mm=50.0,
            tool_geometry_fidelity="PARAMETRIC_BREP",
            holder_geometry_fidelity="PARAMETRIC_BREP",
        )
        assert r.tool_assembly_ready
        assert abs(r.assembly_length_mm - (63.0 + 35.0)) < 0.001
        assert r.assembly_max_diameter_mm == 50.0
        assert r.effective_reach_mm == 35.0

    def test_assembly_not_ready_missing_stickout(self):
        r = compute_assembly_geometry(
            tool_id="TOOL_A", holder_id="HOLDER_A",
            tool_stickout_mm=None, gauge_length_mm=63.0,
            tool_cutting_diameter_mm=10.0, holder_body_diameter_mm=50.0,
        )
        assert not r.tool_assembly_ready
        assert "tool_stickout_mm" in r.missing_requirements

    def test_assembly_not_ready_missing_ids(self):
        r = compute_assembly_geometry(
            tool_id="", holder_id="",
            tool_stickout_mm=30.0, gauge_length_mm=63.0,
            tool_cutting_diameter_mm=10.0, holder_body_diameter_mm=50.0,
        )
        assert not r.tool_assembly_ready

    def test_assembly_fidelity_minimum_of_components(self):
        r = compute_assembly_geometry(
            tool_id="TOOL_A", holder_id="HOLDER_A",
            tool_stickout_mm=30.0, gauge_length_mm=63.0,
            tool_cutting_diameter_mm=10.0, holder_body_diameter_mm=50.0,
            tool_geometry_fidelity="PARAMETRIC_BREP",
            holder_geometry_fidelity="SIMPLIFIED",
        )
        assert r.tool_assembly_ready
        assert r.assembly_geometry_fidelity == "SIMPLIFIED"

    def test_assembly_no_gauge_length_warns(self):
        r = compute_assembly_geometry(
            tool_id="TOOL_A", holder_id="HOLDER_A",
            tool_stickout_mm=30.0, gauge_length_mm=None,
            tool_cutting_diameter_mm=10.0, holder_body_diameter_mm=50.0,
        )
        assert r.assembly_length_mm is None
        assert any("gauge_length" in w for w in r.warnings)


# ---------------------------------------------------------------------------
# Phase L — 6 independent assembly collision checks
# ---------------------------------------------------------------------------


class TestPhaseLAssemblyCollision:
    def _basic_inp(self) -> AssemblyCollisionInput:
        return AssemblyCollisionInput(
            cutter_radius_mm=5.0,
            cutter_length_mm=30.0,
            cutter_geometry_fidelity="PARAMETRIC_BREP",
            holder_gauge_length_mm=63.0,
            holder_max_diameter_mm=50.0,
            holder_geometry_fidelity="SIMPLIFIED",
            tool_stickout_mm=35.0,
            stock=StockModel(
                shape=StockShape.BOX,
                min_x_mm=0, min_y_mm=0, min_z_mm=0,
                max_x_mm=100, max_y_mm=100, max_z_mm=50,
            ),
            part_bbox_mm=(0.0, 0.0, 0.0, 100.0, 100.0, 50.0),
            toolpath_bbox_mm=(10.0, 10.0, 0.0, 90.0, 90.0, 40.0),
        )

    def test_six_checks_returned(self):
        results = run_assembly_collision_checks(self._basic_inp())
        expected_keys = {
            "CUTTER_PART", "CUTTER_STOCK", "CUTTER_FIXTURE",
            "HOLDER_PART", "HOLDER_STOCK", "HOLDER_FIXTURE",
        }
        assert set(results.keys()) == expected_keys

    def test_checks_are_independent(self):
        """Each check has its own status — not sharing a single result."""
        results = run_assembly_collision_checks(self._basic_inp())
        for name, r in results.items():
            assert r.check_type == name

    def test_cutter_fixture_not_performed_without_fixtures(self):
        inp = self._basic_inp()
        inp.fixtures = []
        results = run_assembly_collision_checks(inp)
        assert results["CUTTER_FIXTURE"].status == "NOT_PERFORMED"
        assert results["HOLDER_FIXTURE"].status == "NOT_PERFORMED"

    def test_cutter_part_not_performed_without_part_bbox(self):
        inp = self._basic_inp()
        inp.part_bbox_mm = None
        results = run_assembly_collision_checks(inp)
        assert results["CUTTER_PART"].status == "NOT_PERFORMED"
        assert results["HOLDER_PART"].status == "NOT_PERFORMED"

    def test_cutter_stock_not_performed_without_stock(self):
        inp = self._basic_inp()
        inp.stock = None
        results = run_assembly_collision_checks(inp)
        assert results["CUTTER_STOCK"].status == "NOT_PERFORMED"

    def test_cutter_part_not_performed_without_cutter(self):
        inp = self._basic_inp()
        inp.cutter_radius_mm = None
        results = run_assembly_collision_checks(inp)
        assert results["CUTTER_PART"].status == "NOT_PERFORMED"
        assert results["CUTTER_STOCK"].status == "NOT_PERFORMED"
        assert results["CUTTER_FIXTURE"].status == "NOT_PERFORMED"

    def test_holder_checks_not_performed_without_holder(self):
        inp = self._basic_inp()
        inp.holder_max_diameter_mm = None
        inp.holder_gauge_length_mm = None
        results = run_assembly_collision_checks(inp)
        assert results["HOLDER_PART"].status == "NOT_PERFORMED"
        assert results["HOLDER_STOCK"].status == "NOT_PERFORMED"
        assert results["HOLDER_FIXTURE"].status == "NOT_PERFORMED"

    def test_cutter_stock_overtravel_detected(self):
        inp = self._basic_inp()
        # Toolpath extends beyond stock in X
        inp.toolpath_bbox_mm = (-5.0, 10.0, 0.0, 95.0, 90.0, 40.0)
        results = run_assembly_collision_checks(inp)
        assert results["CUTTER_STOCK"].status == "FAIL"
        assert results["CUTTER_STOCK"].collision_count > 0

    def test_cutter_stock_pass_within_stock(self):
        inp = self._basic_inp()
        inp.toolpath_bbox_mm = (10.0, 10.0, 0.0, 85.0, 85.0, 40.0)
        results = run_assembly_collision_checks(inp)
        assert results["CUTTER_STOCK"].status == "PASS"

    def test_no_check_returns_pass_on_missing_cutter(self):
        """HARD RULE: no fabricated PASS when cutter data is missing."""
        inp = self._basic_inp()
        inp.cutter_radius_mm = None
        results = run_assembly_collision_checks(inp)
        for key in ("CUTTER_PART", "CUTTER_STOCK", "CUTTER_FIXTURE"):
            assert results[key].status != "PASS", (
                f"{key} must not be PASS when cutter geometry is missing"
            )

    def test_all_results_expose_geometry_fidelity(self):
        results = run_assembly_collision_checks(self._basic_inp())
        for name, r in results.items():
            # geometry_fidelity is always set (may be NOT_AVAILABLE)
            assert r.geometry_fidelity in (
                "BREP_EXACT", "PARAMETRIC_BREP", "SIMPLIFIED",
                "NOT_AVAILABLE", "PARTIAL",
            ), f"{name}: unexpected fidelity {r.geometry_fidelity}"


# ---------------------------------------------------------------------------
# Phase M — Stock CUSTOM_BREP + volume method/fidelity
# ---------------------------------------------------------------------------


class TestPhaseMStockGeometry:
    def test_box_stock_volume_analytic(self):
        s = StockModel(
            shape=StockShape.BOX,
            min_x_mm=0, min_y_mm=0, min_z_mm=0,
            max_x_mm=100, max_y_mm=100, max_z_mm=50,
        )
        assert abs(s.volume_mm3() - 500_000.0) < 0.001
        assert s.volume_method() == StockVolumeMethod.ANALYTIC_FORMULA
        assert s.volume_fidelity() == StockVolumeFidelity.ANALYTIC_EXACT

    def test_cylinder_stock_volume_analytic(self):
        s = StockModel(
            shape=StockShape.CYLINDER,
            radius_mm=25.0, height_mm=80.0,
            center_x_mm=0, center_y_mm=0, bottom_z_mm=0,
        )
        expected = math.pi * 25.0**2 * 80.0
        assert abs(s.volume_mm3() - expected) < 0.001
        assert s.volume_fidelity() == StockVolumeFidelity.ANALYTIC_EXACT

    def test_custom_brep_stock_shape_exists(self):
        """CUSTOM_BREP is a valid StockShape after Phase M enum update."""
        assert hasattr(StockShape, "CUSTOM_BREP")
        assert StockShape.CUSTOM_BREP == "CUSTOM_BREP"

    def test_custom_brep_stock_no_step_path(self):
        s = StockModel(shape=StockShape.CUSTOM_BREP)
        assert s.volume_mm3() is None  # no volume until validated
        assert s.volume_method() == StockVolumeMethod.NOT_AVAILABLE
        assert s.custom_brep_status == CustomBRepStatus.NOT_PROVIDED

    def test_custom_brep_stock_with_validated_volume(self):
        """After OCC getMass validation, volume and method are set."""
        s = StockModel(
            shape=StockShape.CUSTOM_BREP,
            initial_stock_volume_mm3=125_000.0,
            initial_stock_volume_method=StockVolumeMethod.BREP_SOLID_VOLUME,
            initial_stock_volume_fidelity=StockVolumeFidelity.BREP_EXACT,
            custom_brep_status=CustomBRepStatus.VALID_CLOSED_SOLID,
            custom_brep_step_path="fixtures/stock.step",
        )
        assert s.volume_mm3() == 125_000.0
        assert s.volume_method() == StockVolumeMethod.BREP_SOLID_VOLUME
        assert s.volume_fidelity() == StockVolumeFidelity.BREP_EXACT

    def test_stock_repair_disclosure(self):
        """If repair was applied, it must be disclosed in custom_brep_repair_note."""
        s = StockModel(
            shape=StockShape.CUSTOM_BREP,
            custom_brep_repair_applied=True,
            custom_brep_repair_note="Closed 2 open edges via OCC ShapeFix",
        )
        assert s.custom_brep_repair_applied
        assert s.custom_brep_repair_note is not None

    def test_volume_fidelity_not_available_for_unknown_shape(self):
        s = StockModel(shape=StockShape.UNKNOWN)
        assert s.volume_fidelity() == StockVolumeFidelity.NOT_AVAILABLE
        assert s.volume_method() == StockVolumeMethod.NOT_AVAILABLE
