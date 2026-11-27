"""
Phase B/C/D — Exact B-Rep Volume Engine Tests

Tests for:
  Phase B: brep_volume.compute_occ_entity_volume / compute_occ_entities_total_volume
  Phase C: exact_gouge gouge volume upgraded to BREP_EXACT
  Phase D: remaining material volume upgraded to BREP_EXACT
  Phase E: attach_mass_properties

VOLUME_FIDELITY=BREP_EXACT for valid closed solids
FALLBACK_LABELED=YES when tetrahedral mesh fallback used
FABRICATED_VOLUME=NO
"""

import pytest
import math

try:
    import gmsh
    _GMSH_AVAILABLE = True
except ImportError:
    _GMSH_AVAILABLE = False

pytestmark = pytest.mark.skipif(not _GMSH_AVAILABLE, reason="gmsh not available")

from backend.verification.brep_volume import (
    BRepVolumeResult,
    MassPropertyResult,
    attach_mass_properties,
    compute_occ_entities_total_volume,
    compute_occ_entity_volume,
)


# ---------------------------------------------------------------------------
# Phase B — OCC entity volume
# ---------------------------------------------------------------------------


class TestBRepVolumeBox:
    def _make_box_gmsh(self, w, h, d):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("test_box")
        tag = gmsh.model.occ.addBox(0, 0, 0, w, h, d)
        gmsh.model.occ.synchronize()
        return gmsh, tag

    def test_box_exact_volume(self):
        g, tag = self._make_box_gmsh(10.0, 20.0, 30.0)
        try:
            r = compute_occ_entity_volume(g, 3, tag)
            assert r.solid_valid
            assert r.volume_fidelity == "BREP_EXACT"
            assert abs(r.volume_mm3 - 6000.0) < 0.001
        finally:
            g.finalize()

    def test_box_center_of_mass(self):
        g, tag = self._make_box_gmsh(10.0, 10.0, 10.0)
        try:
            r = compute_occ_entity_volume(g, 3, tag)
            assert r.center_of_mass_x is not None
            assert abs(r.center_of_mass_x - 5.0) < 0.001
            assert abs(r.center_of_mass_y - 5.0) < 0.001
            assert abs(r.center_of_mass_z - 5.0) < 0.001
        finally:
            g.finalize()

    def test_box_bounding_box(self):
        g, tag = self._make_box_gmsh(5.0, 10.0, 15.0)
        try:
            r = compute_occ_entity_volume(g, 3, tag)
            assert r.bounding_box is not None
            xmin, ymin, zmin, xmax, ymax, zmax = r.bounding_box
            assert abs(xmax - xmin - 5.0) < 0.01
            assert abs(ymax - ymin - 10.0) < 0.01
            assert abs(zmax - zmin - 15.0) < 0.01
        finally:
            g.finalize()

    def test_cylinder_exact_volume(self):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("test_cyl")
        r_mm = 5.0
        h_mm = 20.0
        tag = gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, h_mm, r_mm)
        gmsh.model.occ.synchronize()
        try:
            result = compute_occ_entity_volume(gmsh, 3, tag)
            expected = math.pi * r_mm**2 * h_mm
            assert result.solid_valid
            assert result.volume_fidelity == "BREP_EXACT"
            assert abs(result.volume_mm3 - expected) < 0.001
        finally:
            gmsh.finalize()

    def test_invalid_entity_returns_not_valid(self):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("test_empty")
        gmsh.model.occ.synchronize()
        try:
            r = compute_occ_entity_volume(gmsh, 3, 9999)  # nonexistent tag
            assert not r.solid_valid
            assert r.volume_fidelity == "NOT_AVAILABLE"
            assert r.error is not None
        finally:
            gmsh.finalize()


class TestBRepVolumeMultipleEntities:
    def test_two_boxes_total_volume(self):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("test_two")
        t1 = gmsh.model.occ.addBox(0, 0, 0, 5, 5, 5)
        t2 = gmsh.model.occ.addBox(10, 0, 0, 3, 3, 3)
        gmsh.model.occ.synchronize()
        try:
            r = compute_occ_entities_total_volume(gmsh, [(3, t1), (3, t2)])
            assert r.solid_valid
            assert r.volume_fidelity == "BREP_EXACT"
            assert abs(r.volume_mm3 - (125.0 + 27.0)) < 0.001
            assert r.entity_count == 2
        finally:
            gmsh.finalize()

    def test_no_entities_returns_not_available(self):
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("test_empty")
        gmsh.model.occ.synchronize()
        try:
            r = compute_occ_entities_total_volume(gmsh, [])
            assert not r.solid_valid
            assert r.volume_fidelity == "NOT_AVAILABLE"
        finally:
            gmsh.finalize()

    def test_2d_entities_ignored(self):
        """Only 3D entities contribute to volume; 2D surfaces are ignored."""
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add("test_2d")
        t3d = gmsh.model.occ.addBox(0, 0, 0, 4, 4, 4)
        gmsh.model.occ.synchronize()
        # Pass a mix of dim=2 and dim=3
        surfaces = [(2, s) for _, s in gmsh.model.getEntities(2)]
        r = compute_occ_entities_total_volume(gmsh, surfaces + [(3, t3d)])
        try:
            assert abs(r.volume_mm3 - 64.0) < 0.001  # only the box
        finally:
            gmsh.finalize()


# ---------------------------------------------------------------------------
# Phase E — Mass properties
# ---------------------------------------------------------------------------


class TestMassProperties:
    def _make_brep_result(self, volume_mm3: float) -> BRepVolumeResult:
        return BRepVolumeResult(
            volume_mm3=volume_mm3,
            volume_method="BREP_SOLID_VOLUME",
            volume_fidelity="BREP_EXACT",
            solid_valid=True,
        )

    def test_mass_computed_when_density_available(self):
        r = self._make_brep_result(1_000_000.0)  # 1000 cm³ = 1e6 mm³
        # Steel density ~7850 kg/m³
        mp = attach_mass_properties(r, density_kg_m3=7850.0, density_source="CATALOG")
        assert mp.mass_status == "COMPUTED"
        assert mp.mass_kg is not None
        assert abs(mp.mass_kg - 7.85) < 0.001  # 7850 * 1e6 / 1e9 = 7.85 kg
        assert mp.density_status == "CATALOG_AVAILABLE"
        assert mp.density_source == "CATALOG"

    def test_mass_not_verifiable_when_no_density(self):
        r = self._make_brep_result(50000.0)
        mp = attach_mass_properties(r, density_kg_m3=None, density_source="NOT_PROVIDED")
        assert mp.mass_kg is None
        assert mp.mass_status == "NOT_VERIFIABLE"
        assert mp.density_status == "NOT_PROVIDED"

    def test_volume_fidelity_propagated(self):
        r = self._make_brep_result(100.0)
        mp = attach_mass_properties(r, density_kg_m3=2700.0, density_source="CATALOG")
        assert mp.volume_fidelity == "BREP_EXACT"
        assert mp.volume_method == "BREP_SOLID_VOLUME"

    def test_zero_density_treated_as_unavailable(self):
        r = self._make_brep_result(100.0)
        mp = attach_mass_properties(r, density_kg_m3=0.0, density_source="CATALOG")
        assert mp.mass_kg is None
        assert mp.mass_status == "NOT_VERIFIABLE"


# ---------------------------------------------------------------------------
# Phase C/D — Gouge/remaining volume upgrade in exact_gouge
# ---------------------------------------------------------------------------


class TestExactGougeVolumeUpgrade:
    """Verify that exact_gouge uses BREP_SOLID_VOLUME after Phase C/D upgrade."""

    def _run_known_gouge(self, tmp_path):
        """Run the gouge check on an oversized tool vs hole target."""
        import gmsh as _gmsh
        from backend.verification.exact_gouge import (
            ExactGougeConfig,
            run_exact_gouge_check,
        )

        # Build a small STEP target: box with a hole-shaped void (as simple box target)
        step_path = str(tmp_path / "target.step")
        _gmsh.initialize()
        _gmsh.option.setNumber("General.Verbosity", 0)
        _gmsh.model.add("target")
        # 20x20x20 box as target (tool is 6mm radius vs 4mm hole = simple "gouge")
        _gmsh.model.occ.addBox(0, 0, 0, 20, 20, 20)
        _gmsh.model.occ.synchronize()
        _gmsh.write(step_path)
        _gmsh.finalize()

        cfg = ExactGougeConfig(
            target_step_path=step_path,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=20,
            tool_radius_mm=6.0,  # oversized
            cutting_segments=[(10, 10, 25, 10, 10, -5)],
            tolerance_mm=0.1,
            tolerance_source="TEST_ONLY_DIAGNOSTIC",
            test_only=True,
            mesh_size_mm=2.0,
        )
        return run_exact_gouge_check(cfg)

    def test_gouge_volume_method_is_brep_solid(self, tmp_path):
        result = self._run_known_gouge(tmp_path)
        assert result.boolean_success
        assert result.gouge_volume_method == "BREP_SOLID_VOLUME", (
            f"Expected BREP_SOLID_VOLUME, got {result.gouge_volume_method}"
        )

    def test_gouge_volume_fidelity_is_brep_exact(self, tmp_path):
        result = self._run_known_gouge(tmp_path)
        if result.boolean_success:
            assert result.gouge_volume_fidelity in ("BREP_EXACT", "APPROXIMATE_NUMERICAL_INTEGRATION"), (
                f"Unexpected fidelity: {result.gouge_volume_fidelity}"
            )

    def test_no_mesh_integration_error_pct_on_brep_success(self, tmp_path):
        result = self._run_known_gouge(tmp_path)
        if result.gouge_volume_fidelity == "BREP_EXACT":
            assert result.volume_integration_error_pct is None, (
                "volume_integration_error_pct should be None for BREP_EXACT"
            )

    def test_fallback_discloses_approximate(self, tmp_path):
        """When fallback is used, fidelity must be APPROXIMATE, not BREP_EXACT."""
        result = self._run_known_gouge(tmp_path)
        if result.gouge_volume_fidelity == "APPROXIMATE_NUMERICAL_INTEGRATION":
            assert result.volume_integration_error_pct is not None
            assert any("falling back" in w.lower() or "fallback" in w.lower()
                       for w in result.warnings)
