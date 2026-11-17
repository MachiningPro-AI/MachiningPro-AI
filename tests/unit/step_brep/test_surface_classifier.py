"""
Tests for PLANAR/CYLINDRICAL/UNKNOWN surface classification (P10 Phase 3, MUST 35).

HARD RULES:
  - Classification based on actual gmsh geometry — not fabricated.
  - UNKNOWN remains UNKNOWN when classification is uncertain.
"""

from __future__ import annotations

import gmsh  # type: ignore[import]
import pytest

from backend.step_brep.surface_classifier import (
    SurfaceClass,
    classify_surface,
    estimate_cylinder_axis,
    estimate_cylinder_diameter,
    is_circular_curve,
)


# Single module-level gmsh session. Individual fixtures call gmsh.model.add() with
# unique names; they never call gmsh.initialize()/finalize() themselves.
@pytest.fixture(scope="module", autouse=True)
def _gmsh_session():
    gmsh.initialize(["-v", "0"])
    yield
    try:
        gmsh.finalize()
    except Exception:
        pass


# ===========================================================================
# A — Classify planar faces on a box
# ===========================================================================

@pytest.fixture(scope="module")
def box_surfaces() -> list[int]:
    """Surface tags from a simple 10×20×5 box."""
    gmsh.model.add("box_cls")
    gmsh.model.occ.addBox(0, 0, 0, 10, 20, 5)
    gmsh.model.occ.synchronize()
    return [s[1] for s in gmsh.model.getEntities(2)]


def test_box_surfaces_all_planar(box_surfaces: list[int]) -> None:
    """All 6 faces of a box should be classified PLANAR."""
    for stag in box_surfaces:
        cls = classify_surface(stag)
        assert cls == SurfaceClass.PLANAR, (
            f"Surface {stag} expected PLANAR, got {cls}"
        )


# ===========================================================================
# B — Classify cylindrical face on a bare cylinder
# ===========================================================================

@pytest.fixture(scope="module")
def cylinder_surfaces() -> list[int]:
    """Surface tags from a Z-axis cylinder Ø10, height 20."""
    gmsh.model.add("cyl_cls")
    gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, 20, 5)
    gmsh.model.occ.synchronize()
    return [s[1] for s in gmsh.model.getEntities(2)]


def test_cylinder_has_cylindrical_surface(cylinder_surfaces: list[int]) -> None:
    """A standalone cylinder has at least 1 CYLINDRICAL lateral face."""
    cyl_count = sum(1 for s in cylinder_surfaces if classify_surface(s) == SurfaceClass.CYLINDRICAL)
    assert cyl_count >= 1


def test_cylinder_caps_are_planar(cylinder_surfaces: list[int]) -> None:
    """Top and bottom caps of a cylinder are PLANAR."""
    planar = [s for s in cylinder_surfaces if classify_surface(s) == SurfaceClass.PLANAR]
    assert len(planar) >= 2


# ===========================================================================
# C — is_circular_curve on a cylinder
# ===========================================================================

@pytest.fixture(scope="module")
def cylinder_curves() -> list[int]:
    """Curve tags from a Z-axis cylinder Ø20, height 30."""
    gmsh.model.add("cyl_crv")
    gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, 30, 10)
    gmsh.model.occ.synchronize()
    return [c[1] for c in gmsh.model.getEntities(1)]


def test_cylinder_has_circular_curves(cylinder_curves: list[int]) -> None:
    """A Z-axis cylinder Ø20 has circular boundary curves."""
    circ_count = sum(1 for c in cylinder_curves if is_circular_curve(c)[0])
    assert circ_count >= 2  # top circle + bottom circle


def test_circular_curve_diameter_reasonable(cylinder_curves: list[int]) -> None:
    """Detected circle diameter ≈ 20mm (Ø20 cylinder)."""
    for ctag in cylinder_curves:
        is_circ, diam = is_circular_curve(ctag)
        if is_circ:
            assert 18.0 <= diam <= 22.0, f"Unexpected diameter {diam} for curve {ctag}"


# ===========================================================================
# D — Cylinder axis and diameter estimation
# ===========================================================================

def test_cylinder_axis_z_on_z_cylinder() -> None:
    """Z-axis cylinder → estimated axis = 'Z'."""
    gmsh.model.add("axz")
    gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, 25, 8)
    gmsh.model.occ.synchronize()
    surfs = [s[1] for s in gmsh.model.getEntities(2)]
    cyl_surf = next((s for s in surfs if classify_surface(s) == SurfaceClass.CYLINDRICAL), None)
    if cyl_surf is not None:
        axis = estimate_cylinder_axis(cyl_surf)
        assert axis == "Z"


def test_cylinder_diameter_z_on_z_cylinder() -> None:
    """Diameter of a Ø10 Z-axis cylinder (height=40) ≈ 10mm.

    Height 40 / diameter 10 = ratio 4.0 > 1.5 → axis detection succeeds.
    """
    gmsh.model.add("diam10")
    gmsh.model.occ.addCylinder(0, 0, 0, 0, 0, 40, 5)  # radius=5 → diameter=10
    gmsh.model.occ.synchronize()
    surfs = [s[1] for s in gmsh.model.getEntities(2)]
    cyl_surf = next((s for s in surfs if classify_surface(s) == SurfaceClass.CYLINDRICAL), None)
    if cyl_surf is not None:
        diam = estimate_cylinder_diameter(cyl_surf)
        assert diam is not None
        assert 8.0 <= diam <= 12.0, f"Unexpected diameter: {diam}"


# ===========================================================================
# E — SurfaceClass enum values
# ===========================================================================

def test_surface_class_planar_value() -> None:
    assert SurfaceClass.PLANAR == "PLANAR"


def test_surface_class_cylindrical_value() -> None:
    assert SurfaceClass.CYLINDRICAL == "CYLINDRICAL"


def test_surface_class_unknown_value() -> None:
    assert SurfaceClass.UNKNOWN == "UNKNOWN"
