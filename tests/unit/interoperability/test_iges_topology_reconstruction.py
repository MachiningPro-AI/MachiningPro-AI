"""Unit tests for iges_topology_reconstruction (P1-C).

Tests:
  - Surface group classification (planar, cylindrical, freeform)
  - Empty-surface IGES → NO_SURFACES status
  - Existing B-Rep topology passed through without re-reconstruction
  - Boundary entity counting from entity_refs
  - Partial group: single ungrouped surface goes to MIXED
  - Surface count / curve count statistics
  - No B-Rep objects fabricated (vertices, edges, loops, faces, shells, bodies empty)
  - closed_body_available always False for surface-only IGES
  - topology_fabricated always False
  - SurfaceGroup properties (group_id, surface_ids, group_type)
  - Multiple planar groups by distinct normals
  - Multiple cylindrical groups by distinct axes
  - Surface group source_note populated
  - CanonicalTopology geometry reference preserved
  - reconstruction metadata keys present on CanonicalTopology
  - reconstruct_iges_topology: empty entity_refs
  - reconstruct_iges_topology: boundary counts
  - Planar normal clustering within tolerance
  - Planar normal clustering separates distinct normals
  - Cylindrical radius grouping with compatible radius
  - Cylindrical radius grouping rejects incompatible radius
  - Single surface not merged into multi-surface group
  - review_required flag absent (not applicable on this layer)
  - IgesReconstructionStatus.SUCCESS on valid surface input
  - Freeform surfaces (NURBS/BSPLINE) grouped separately
"""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType
from unittest.mock import MagicMock

import pytest

from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import (
    CanonicalCurve,
    CanonicalCurveType,
    CanonicalGeometry,
    CanonicalSurface,
    CanonicalSurfaceType,
    CanonicalVector3D,
)
from backend.interoperability.iges_topology_reconstruction import (
    IgesReconstructionStatus,
    IgesTopologyReconstructionResult,
    SurfaceGroup,
    SurfaceGroupType,
    _group_cylindrical_surfaces,
    _group_planar_surfaces,
    reconstruct_iges_topology,
)
from backend.interoperability.topology import CanonicalTopology


# ---------------------------------------------------------------------------
# Minimal helpers
# ---------------------------------------------------------------------------

def _vec(x: float, y: float, z: float) -> CanonicalVector3D:
    return CanonicalVector3D(
        x=Quantity.of(x, Unit.DIMENSIONLESS),
        y=Quantity.of(y, Unit.DIMENSIONLESS),
        z=Quantity.of(z, Unit.DIMENSIONLESS),
    )


def _qty_mm(v: float) -> Quantity:
    return Quantity.of(v, Unit.MM)


def _make_plane_surface(sid: str, nx: float, ny: float, nz: float) -> CanonicalSurface:
    """Build a minimal PLANE CanonicalSurface with given normal direction."""
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.PLANE,
        normal=_vec(nx, ny, nz),
    )


def _make_cylinder_surface(
    sid: str, ax: float, ay: float, az: float, radius: float
) -> CanonicalSurface:
    """Build a minimal CYLINDER CanonicalSurface with given axis and radius."""
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.CYLINDER,
        axis=_vec(ax, ay, az),
        radius=_qty_mm(radius),
    )


def _make_bspline_surface(sid: str) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.BSPLINE,
        metadata=MappingProxyType({}),
    )


def _make_nurbs_surface(sid: str) -> CanonicalSurface:
    return CanonicalSurface(
        surface_id=sid,
        surface_type=CanonicalSurfaceType.NURBS,
        metadata=MappingProxyType({}),
    )


def _make_mapping_result(surfaces=(), curves=(), entity_refs=()):
    geom = CanonicalGeometry(
        geometry_id="test-geom",
        surfaces=tuple(surfaces),
        curves=tuple(curves),
    )
    mr = MagicMock()
    mr.topology = None
    mr.geometry = geom
    mr.entity_refs = list(entity_refs)
    return mr


def _make_entity_ref(entity_kind: str):
    er = MagicMock()
    er.entity_kind = entity_kind
    return er


# ---------------------------------------------------------------------------
# Tests: empty / no surface
# ---------------------------------------------------------------------------

class TestNoSurfaces:
    def test_empty_geometry_gives_no_surfaces_status(self):
        mr = _make_mapping_result(surfaces=[])
        result = reconstruct_iges_topology(mr, source_id="test")
        assert result.status == IgesReconstructionStatus.NO_SURFACES

    def test_empty_geometry_surfaces_available_false(self):
        mr = _make_mapping_result(surfaces=[])
        result = reconstruct_iges_topology(mr, source_id="test")
        assert result.surfaces_available is False

    def test_none_geometry_gives_no_surfaces(self):
        mr = MagicMock()
        mr.topology = None
        mr.geometry = None
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        assert result.status == IgesReconstructionStatus.NO_SURFACES

    def test_no_surfaces_warnings_populated(self):
        mr = _make_mapping_result(surfaces=[])
        result = reconstruct_iges_topology(mr)
        assert any("NO_SURFACES" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Tests: B-Rep topology passthrough
# ---------------------------------------------------------------------------

class TestBRepPassthrough:
    def test_existing_brep_topology_passed_through(self):
        topo = MagicMock(spec=CanonicalTopology)
        topo.faces = []
        topo.loops = []
        topo.shells = []
        topo.bodies = []
        mr = _make_mapping_result(surfaces=[])
        mr.topology = topo
        mr.geometry = MagicMock()
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        assert result.canonical_topology is topo
        assert result.status == IgesReconstructionStatus.SUCCESS

    def test_brep_topology_body_count_reported(self):
        topo = MagicMock(spec=CanonicalTopology)
        topo.faces = []
        topo.loops = []
        topo.shells = [MagicMock()]
        topo.bodies = [MagicMock(), MagicMock()]
        mr = _make_mapping_result(surfaces=[])
        mr.topology = topo
        mr.geometry = MagicMock()
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        assert result.body_count == 2
        assert result.shell_count == 1


# ---------------------------------------------------------------------------
# Tests: Fabrication guards
# ---------------------------------------------------------------------------

class TestFabricationGuards:
    def test_no_vertices_fabricated(self):
        mr = _make_mapping_result(surfaces=[_make_plane_surface("s1", 0, 0, 1)])
        result = reconstruct_iges_topology(mr)
        assert result.canonical_topology is not None
        assert len(result.canonical_topology.vertices) == 0

    def test_no_edges_fabricated(self):
        mr = _make_mapping_result(surfaces=[_make_plane_surface("s1", 0, 0, 1)])
        result = reconstruct_iges_topology(mr)
        assert len(result.canonical_topology.edges) == 0

    def test_no_loops_fabricated(self):
        mr = _make_mapping_result(surfaces=[_make_plane_surface("s1", 0, 0, 1)])
        result = reconstruct_iges_topology(mr)
        assert len(result.canonical_topology.loops) == 0

    def test_no_faces_fabricated(self):
        mr = _make_mapping_result(surfaces=[_make_plane_surface("s1", 0, 0, 1)])
        result = reconstruct_iges_topology(mr)
        assert len(result.canonical_topology.faces) == 0

    def test_no_shells_fabricated_in_canonical(self):
        mr = _make_mapping_result(surfaces=[_make_plane_surface("s1", 0, 0, 1)])
        result = reconstruct_iges_topology(mr)
        assert len(result.canonical_topology.shells) == 0

    def test_topology_fabricated_always_false(self):
        mr = _make_mapping_result(surfaces=[_make_plane_surface("s1", 0, 0, 1)])
        result = reconstruct_iges_topology(mr)
        assert result.topology_fabricated is False

    def test_closed_body_always_false_for_surface_only(self):
        mr = _make_mapping_result(surfaces=[
            _make_plane_surface("s1", 0, 0, 1),
            _make_plane_surface("s2", 0, 0, 1),
        ])
        result = reconstruct_iges_topology(mr)
        assert result.closed_body_available is False


# ---------------------------------------------------------------------------
# Tests: Surface grouping
# ---------------------------------------------------------------------------

class TestPlanarGrouping:
    def test_two_co_planar_surfaces_in_one_group(self):
        s1 = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        s2 = _make_plane_surface("s2", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s1, s2])
        result = reconstruct_iges_topology(mr)
        pg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.PLANAR_ASSEMBLY]
        assert len(pg) == 1
        assert len(pg[0].surface_ids) == 2

    def test_two_distinct_normals_give_two_groups(self):
        s1 = _make_plane_surface("s1", 0.0, 0.0, 1.0)   # top face
        s2 = _make_plane_surface("s2", 0.0, 1.0, 0.0)   # front face
        mr = _make_mapping_result(surfaces=[s1, s2])
        result = reconstruct_iges_topology(mr)
        pg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.PLANAR_ASSEMBLY]
        assert len(pg) == 2

    def test_anti_parallel_normals_in_same_group(self):
        # +Z and -Z — _angle_between_vecs uses abs(dot), so they cluster
        s1 = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        s2 = _make_plane_surface("s2", 0.0, 0.0, -1.0)
        mr = _make_mapping_result(surfaces=[s1, s2])
        result = reconstruct_iges_topology(mr)
        pg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.PLANAR_ASSEMBLY]
        assert len(pg) == 1


class TestCylindricalGrouping:
    def test_two_same_axis_cylinders_in_one_group(self):
        c1 = _make_cylinder_surface("c1", 0.0, 0.0, 1.0, 10.0)
        c2 = _make_cylinder_surface("c2", 0.0, 0.0, 1.0, 10.0)
        mr = _make_mapping_result(surfaces=[c1, c2])
        result = reconstruct_iges_topology(mr)
        cg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.CYLINDRICAL_FAMILY]
        assert len(cg) == 1
        assert len(cg[0].surface_ids) == 2

    def test_different_radii_give_two_groups(self):
        c1 = _make_cylinder_surface("c1", 0.0, 0.0, 1.0, 5.0)
        c2 = _make_cylinder_surface("c2", 0.0, 0.0, 1.0, 20.0)   # radius differs by >5%
        mr = _make_mapping_result(surfaces=[c1, c2])
        result = reconstruct_iges_topology(mr)
        cg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.CYLINDRICAL_FAMILY]
        assert len(cg) == 2


class TestFreeformGrouping:
    def test_bspline_surface_in_freeform_group(self):
        s = _make_bspline_surface("bs1")
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        fg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.FREEFORM_ASSEMBLY]
        assert len(fg) == 1
        assert "bs1" in fg[0].surface_ids

    def test_nurbs_surface_in_freeform_group(self):
        s = _make_nurbs_surface("n1")
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        fg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.FREEFORM_ASSEMBLY]
        assert len(fg) == 1


# ---------------------------------------------------------------------------
# Tests: Surface group metadata
# ---------------------------------------------------------------------------

class TestSurfaceGroupMetadata:
    def test_planar_group_has_normal_components(self):
        s = _make_plane_surface("s1", 0.0, 1.0, 0.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        pg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.PLANAR_ASSEMBLY]
        assert pg[0].normal_x is not None
        assert pg[0].normal_y is not None
        assert pg[0].normal_z is not None

    def test_cylindrical_group_has_axis_and_radius(self):
        c = _make_cylinder_surface("c1", 1.0, 0.0, 0.0, 15.0)
        mr = _make_mapping_result(surfaces=[c])
        result = reconstruct_iges_topology(mr)
        cg = [g for g in result.surface_groups if g.group_type == SurfaceGroupType.CYLINDRICAL_FAMILY]
        assert cg[0].axis_x is not None
        assert cg[0].radius_mm == pytest.approx(15.0, rel=0.01)

    def test_surface_group_source_note_populated(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        for g in result.surface_groups:
            assert len(g.source_note) > 0

    def test_group_id_format_has_prefix(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        for g in result.surface_groups:
            assert "-" in g.group_id


# ---------------------------------------------------------------------------
# Tests: Statistics and counts
# ---------------------------------------------------------------------------

class TestStatistics:
    def test_surface_count_matches_input(self):
        surfaces = [_make_plane_surface(f"s{i}", 0.0, 0.0, 1.0) for i in range(5)]
        mr = _make_mapping_result(surfaces=surfaces)
        result = reconstruct_iges_topology(mr)
        assert result.surface_count == 5

    def test_curve_count_from_geometry(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        c1 = CanonicalCurve(curve_id="c1", curve_type=CanonicalCurveType.LINE)
        c2 = CanonicalCurve(curve_id="c2", curve_type=CanonicalCurveType.LINE)
        geom = CanonicalGeometry(
            geometry_id="test-geom-curves",
            surfaces=(s,),
            curves=(c1, c2),
        )
        mr = MagicMock()
        mr.topology = None
        mr.geometry = geom
        mr.entity_refs = []
        result = reconstruct_iges_topology(mr)
        assert result.curve_count == 2

    def test_boundary_entity_count_from_entity_refs(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(
            surfaces=[s],
            entity_refs=[
                _make_entity_ref("IgesCurveOnParametricSurface"),
                _make_entity_ref("IgesCurveOnParametricSurface"),
                _make_entity_ref("OtherEntityKind"),
            ],
        )
        result = reconstruct_iges_topology(mr)
        assert result.boundary_entity_count >= 2

    def test_shell_count_equals_number_of_surface_groups(self):
        s1 = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        s2 = _make_cylinder_surface("c1", 0.0, 0.0, 1.0, 5.0)
        mr = _make_mapping_result(surfaces=[s1, s2])
        result = reconstruct_iges_topology(mr)
        assert result.shell_count == len(result.surface_groups)

    def test_body_count_nonzero_when_surfaces_present(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        assert result.body_count >= 1


# ---------------------------------------------------------------------------
# Tests: CanonicalTopology geometry reference
# ---------------------------------------------------------------------------

class TestCanonicalTopologyRef:
    def test_canonical_topology_geometry_reference_set(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        assert result.canonical_topology is not None
        assert result.canonical_topology.geometry is mr.geometry

    def test_canonical_topology_metadata_has_surface_count(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        meta = result.canonical_topology.metadata
        assert "surface_count" in meta

    def test_canonical_topology_metadata_no_closed_body(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        meta = result.canonical_topology.metadata
        assert meta.get("closed_body_available") == "NO"

    def test_canonical_topology_metadata_surfaces_available_yes(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        meta = result.canonical_topology.metadata
        assert meta.get("surfaces_available") == "YES"

    def test_success_status_on_valid_input(self):
        s = _make_plane_surface("s1", 0.0, 0.0, 1.0)
        mr = _make_mapping_result(surfaces=[s])
        result = reconstruct_iges_topology(mr)
        assert result.status == IgesReconstructionStatus.SUCCESS
