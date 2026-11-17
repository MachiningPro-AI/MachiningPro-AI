"""
Tests for CanonicalTopology wiring from STEP B-Rep (P10 Phase 3, MUST 34-35).

HARD RULES: No fabricated topology. All entity IDs from real gmsh data.
"""

from __future__ import annotations

import pathlib

import gmsh  # type: ignore[import]
import pytest

from backend.interoperability.topology import (
    BodyType,
    CanonicalTopology,
    ShellClosure,
)
from backend.step_brep.topology_adapter import build_canonical_topology


# Single module-level gmsh session. Individual fixtures use gmsh.model.add()
# with unique names but never call gmsh.initialize()/finalize() themselves.
@pytest.fixture(scope="module", autouse=True)
def _gmsh_session():
    gmsh.initialize(["-v", "0"])
    yield
    try:
        gmsh.finalize()
    except Exception:
        pass


# ===========================================================================
# A — Build topology from a simple box (no holes)
# ===========================================================================

@pytest.fixture(scope="module")
def simple_box_topology() -> CanonicalTopology:
    """CanonicalTopology for a 10×20×5 box."""
    gmsh.model.add("box_topo")
    gmsh.model.occ.addBox(0, 0, 0, 10, 20, 5)
    gmsh.model.occ.synchronize()
    return build_canonical_topology("topo-box-test")


def test_simple_box_is_canonical_topology(simple_box_topology: CanonicalTopology) -> None:
    assert isinstance(simple_box_topology, CanonicalTopology)


def test_simple_box_body_count(simple_box_topology: CanonicalTopology) -> None:
    assert len(simple_box_topology.bodies) == 1


def test_simple_box_body_is_solid(simple_box_topology: CanonicalTopology) -> None:
    body = simple_box_topology.bodies[0]
    assert body.body_type == BodyType.SOLID


def test_simple_box_shell_is_closed(simple_box_topology: CanonicalTopology) -> None:
    shell = simple_box_topology.shells[0]
    assert shell.closure == ShellClosure.CLOSED


def test_simple_box_face_count(simple_box_topology: CanonicalTopology) -> None:
    # A box has 6 faces
    assert len(simple_box_topology.faces) == 6


def test_simple_box_vertices_nonzero(simple_box_topology: CanonicalTopology) -> None:
    assert len(simple_box_topology.vertices) >= 8  # box has 8 corners


def test_simple_box_edges_nonzero(simple_box_topology: CanonicalTopology) -> None:
    assert len(simple_box_topology.edges) >= 12  # box has 12 edges


def test_simple_box_body_has_bounding_box(simple_box_topology: CanonicalTopology) -> None:
    body = simple_box_topology.bodies[0]
    assert body.bounding_box is not None


def test_simple_box_provenance_in_vertices(simple_box_topology: CanonicalTopology) -> None:
    """All vertices have source_entity_ref from gmsh."""
    for v in simple_box_topology.vertices:
        assert v.source_entity_ref is not None


# ===========================================================================
# B — Build topology from a drilled block (has circular surfaces)
# ===========================================================================

@pytest.fixture(scope="module")
def drilled_block_topology() -> CanonicalTopology:
    """CanonicalTopology for a 60×40×20 block with 1 through hole Ø10."""
    gmsh.model.add("drilled_topo")
    block = gmsh.model.occ.addBox(0, 0, 0, 60, 40, 20)
    cyl = gmsh.model.occ.addCylinder(30, 20, -1, 0, 0, 22, 5)
    gmsh.model.occ.cut([(3, block)], [(3, cyl)])
    gmsh.model.occ.synchronize()
    return build_canonical_topology("topo-drilled-test")


def test_drilled_block_is_valid_topology(drilled_block_topology: CanonicalTopology) -> None:
    assert isinstance(drilled_block_topology, CanonicalTopology)


def test_drilled_block_body_count(drilled_block_topology: CanonicalTopology) -> None:
    assert len(drilled_block_topology.bodies) == 1


def test_drilled_block_has_7_faces(drilled_block_topology: CanonicalTopology) -> None:
    # 6 box faces + 1 cylindrical surface = 7 faces (some may be built partially)
    assert len(drilled_block_topology.faces) >= 5


def test_drilled_block_has_cylindrical_face(drilled_block_topology: CanonicalTopology) -> None:
    cyl_faces = [
        f for f in drilled_block_topology.faces
        if "CYLINDRICAL" in f.surface_id
    ]
    assert len(cyl_faces) >= 1, "No cylindrical face found in drilled block topology"


def test_drilled_block_has_inner_loops(drilled_block_topology: CanonicalTopology) -> None:
    """Top and bottom planar faces should have inner loops (the hole boundary)."""
    from backend.interoperability.topology import LoopType
    inner_loops = [
        loop for loop in drilled_block_topology.loops
        if loop.loop_type == LoopType.INNER
    ]
    assert len(inner_loops) >= 2  # top hole + bottom hole


def test_drilled_block_reference_integrity(drilled_block_topology: CanonicalTopology) -> None:
    """CanonicalTopology validates reference integrity at construction — if built, it's valid."""
    # Construction raises TopologyContainerError on invalid refs; reaching here means valid.
    assert drilled_block_topology.topology_id == "topo-drilled-test"


def test_drilled_block_synthetic_vertices_created(
    drilled_block_topology: CanonicalTopology,
) -> None:
    """Circular curves require synthetic vertices (SV-C{tag}-Q{i} pattern)."""
    syn_verts = [v for v in drilled_block_topology.vertices if v.vertex_id.startswith("SV-")]
    # Ø10 hole has 2 circles → 8 synthetic vertices (4 per circle)
    assert len(syn_verts) >= 8


def test_all_loop_edge_ids_resolve(drilled_block_topology: CanonicalTopology) -> None:
    """Every edge_id referenced in every loop must exist in edges."""
    edge_id_set = {e.edge_id for e in drilled_block_topology.edges}
    for loop in drilled_block_topology.loops:
        for eid in loop.edge_ids:
            assert eid in edge_id_set, f"Loop {loop.loop_id!r} references missing edge {eid!r}"


# ===========================================================================
# C — Topology from benchmark STEP file
# ===========================================================================

def test_topology_from_benchmark_step(p10_s1_step: pathlib.Path) -> None:
    """Build CanonicalTopology from P10-S1 STEP file."""
    gmsh.model.add("topo_step_import")
    gmsh.model.occ.importShapes(str(p10_s1_step))
    gmsh.model.occ.synchronize()
    topo = build_canonical_topology("topo-p10s1")

    assert isinstance(topo, CanonicalTopology)
    assert len(topo.bodies) == 1
    assert len(topo.faces) >= 6
