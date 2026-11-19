"""
Wire gmsh STEP topology into existing CanonicalTopology (Stage 4B).

MUST 12: Wire STEP B-Rep output into existing topology.py.
MUST 13: Preserve stable provenance between STEP entity → body → face → feature.
MUST 14: Session-local IDs only — no persistent cross-revision topology IDs.

Design constraints:
  - geometry=None: curve_id and surface_id are descriptive strings, not validated.
  - Circular curves (full circles, no vertices) are split into 4 quarter-arc edges
    with 4 synthetic vertices to satisfy CanonicalLoop's ≥3 edge requirement.
  - CanonicalEdge requires distinct start/end vertices; seam edges (connecting
    the start points of two circles) are excluded from loop construction.
  - All entity IDs are session-local: "V-{tag}", "E-{tag}", "F-{tag}", etc.

HARD RULE: No topology is fabricated. All positions come from gmsh.getBoundingBox().
"""

from __future__ import annotations

import threading
from decimal import Decimal

import gmsh  # type: ignore[import]

from backend.domain.units import Quantity, Unit
from backend.interoperability.geometry import BoundingBox3D, CanonicalPoint3D
from backend.interoperability.topology import (
    BodyType,
    CanonicalBody,
    CanonicalEdge,
    CanonicalFace,
    CanonicalLoop,
    CanonicalShell,
    CanonicalTopology,
    CanonicalVertex,
    LoopType,
    Orientation,
    ShellClosure,
)
from backend.step_brep.surface_classifier import SurfaceClass

__all__ = ["build_canonical_topology"]

_gmsh_lock = threading.Lock()
_QMM = Unit.MM


def _qty(val: float) -> Quantity:
    return Quantity(value=Decimal(str(round(val, 6))), unit=_QMM)


def _point(x: float, y: float, z: float, src: str | None = None) -> CanonicalPoint3D:
    return CanonicalPoint3D(
        x=_qty(x), y=_qty(y), z=_qty(z),
        source_entity_ref=src,
    )


def _bbox3d(xmin: float, ymin: float, zmin: float,
            xmax: float, ymax: float, zmax: float) -> BoundingBox3D:
    return BoundingBox3D(
        min_point=_point(xmin, ymin, zmin),
        max_point=_point(xmax, ymax, zmax),
    )


def build_canonical_topology(
    topology_id: str,
    step_path: str | None = None,
) -> CanonicalTopology:
    """Build CanonicalTopology from the currently active gmsh model.

    gmsh must already be initialized and synchronized (call after importShapes +
    occ.synchronize).  This function does NOT call gmsh.initialize() or finalize().

    Returns a valid CanonicalTopology with geometry=None.
    """
    all_vertices: list[CanonicalVertex] = []
    all_edges: list[CanonicalEdge] = []
    all_loops: list[CanonicalLoop] = []
    all_faces: list[CanonicalFace] = []
    all_shells: list[CanonicalShell] = []
    all_bodies: list[CanonicalBody] = []

    # --- Pass 1: vertices (0D entities) ---
    gmsh_v_to_id: dict[int, str] = {}
    for _d, vtag in gmsh.model.getEntities(0):
        vid = f"V-{vtag}"
        xmin, ymin, zmin, _, _, _ = gmsh.model.getBoundingBox(0, vtag)
        pt = _point(xmin, ymin, zmin, src=f"gmsh:v:{vtag}")
        cv = CanonicalVertex(vertex_id=vid, point=pt, source_entity_ref=f"gmsh:v:{vtag}")
        all_vertices.append(cv)
        gmsh_v_to_id[vtag] = vid

    # --- Pass 2: edges (1D entities) ---
    # Map gmsh curve tag → list[edge_id] (1 for linear, 4 for full circle)
    curve_to_edge_ids: dict[int, list[str]] = {}

    for _d, ctag in gmsh.model.getEntities(1):
        bounds = gmsh.model.getBoundary([(1, ctag)], oriented=False)

        if len(bounds) == 2:
            # Linear edge with two distinct endpoints
            v1, v2 = bounds[0][1], bounds[1][1]
            if v1 == v2:
                # Degenerate seam — skip
                curve_to_edge_ids[ctag] = []
                continue
            if v1 not in gmsh_v_to_id or v2 not in gmsh_v_to_id:
                curve_to_edge_ids[ctag] = []
                continue
            eid = f"E-{ctag}"
            edge = CanonicalEdge(
                edge_id=eid,
                start_vertex_id=gmsh_v_to_id[v1],
                end_vertex_id=gmsh_v_to_id[v2],
                curve_id=f"CRV-LINE-{ctag}",
                orientation=Orientation.FORWARD,
                source_entity_ref=f"gmsh:c:{ctag}",
            )
            all_edges.append(edge)
            curve_to_edge_ids[ctag] = [eid]

        elif len(bounds) == 0:
            # Full circle — split into 4 quarter arcs
            xmin, ymin, zmin, xmax, ymax, zmax = gmsh.model.getBoundingBox(1, ctag)
            dx, dy, dz = xmax - xmin, ymax - ymin, zmax - zmin
            _FLAT = 1e-4

            # Determine circle plane and compute centre + radius
            if dz < _FLAT:  # XY plane
                cx, cy, cz = (xmin + xmax) / 2, (ymin + ymax) / 2, zmin
                r = (dx + dy) / 4
                pts = [
                    (cx + r, cy, cz), (cx, cy + r, cz),
                    (cx - r, cy, cz), (cx, cy - r, cz),
                ]
            elif dy < _FLAT:  # XZ plane
                cx, cy, cz = (xmin + xmax) / 2, ymin, (zmin + zmax) / 2
                r = (dx + dz) / 4
                pts = [
                    (cx + r, cy, cz), (cx, cy, cz + r),
                    (cx - r, cy, cz), (cx, cy, cz - r),
                ]
            else:  # YZ plane
                cx, cy, cz = xmin, (ymin + ymax) / 2, (zmin + zmax) / 2
                r = (dy + dz) / 4
                pts = [
                    (cx, cy + r, cz), (cx, cy, cz + r),
                    (cx, cy - r, cz), (cx, cy, cz - r),
                ]

            # Create 4 synthetic vertices
            syn_vids: list[str] = []
            for i, (px, py, pz) in enumerate(pts):
                syn_id = f"SV-C{ctag}-Q{i}"
                pt = _point(px, py, pz, src=f"gmsh:c:{ctag}:syn{i}")
                sv = CanonicalVertex(
                    vertex_id=syn_id, point=pt, source_entity_ref=f"gmsh:c:{ctag}:syn{i}"
                )
                all_vertices.append(sv)
                syn_vids.append(syn_id)

            # Create 4 quarter-arc edges
            arc_ids: list[str] = []
            for i in range(4):
                arc_eid = f"ARC-C{ctag}-Q{i}"
                arc = CanonicalEdge(
                    edge_id=arc_eid,
                    start_vertex_id=syn_vids[i],
                    end_vertex_id=syn_vids[(i + 1) % 4],
                    curve_id=f"CRV-ARC-C{ctag}-Q{i}",
                    orientation=Orientation.FORWARD,
                    source_entity_ref=f"gmsh:c:{ctag}:arc{i}",
                )
                all_edges.append(arc)
                arc_ids.append(arc_eid)

            curve_to_edge_ids[ctag] = arc_ids

        else:
            # Unusual: not 0 or 2 boundary vertices — skip for safety
            curve_to_edge_ids[ctag] = []

    # --- Pass 3: loops and faces (2D entities) ---
    for _d, stag in gmsh.model.getEntities(2):
        s_bounds = gmsh.model.getBoundary([(2, stag)], oriented=False)
        bound_ctags = [b[1] for b in s_bounds]

        # Classify each boundary curve
        circ_ctags = [ct for ct in bound_ctags if len(curve_to_edge_ids.get(ct, [])) == 4]
        line_ctags = [ct for ct in bound_ctags if len(curve_to_edge_ids.get(ct, [])) == 1]

        # Determine surface class
        xmin_s, ymin_s, zmin_s, xmax_s, ymax_s, zmax_s = gmsh.model.getBoundingBox(2, stag)
        dx_s = xmax_s - xmin_s
        dy_s = ymax_s - ymin_s
        dz_s = zmax_s - zmin_s
        _FLAT = 1e-6

        if dx_s < _FLAT or dy_s < _FLAT or dz_s < _FLAT:
            surf_class = SurfaceClass.PLANAR
        elif circ_ctags and not line_ctags:
            surf_class = SurfaceClass.CYLINDRICAL
        else:
            surf_class = SurfaceClass.UNKNOWN

        loop_ids: list[str] = []

        # Outer rectangular loop from linear curves (need ≥3 for CanonicalLoop)
        if len(line_ctags) >= 3:
            outer_eids: list[str] = []
            for ct in line_ctags:
                outer_eids.extend(curve_to_edge_ids[ct])
            if len(outer_eids) >= 3:
                loop_id = f"LOOP-S{stag}-OUTER"
                loop = CanonicalLoop(
                    loop_id=loop_id,
                    edge_ids=tuple(outer_eids),
                    loop_type=LoopType.OUTER,
                    source_entity_ref=f"gmsh:s:{stag}:outer",
                )
                all_loops.append(loop)
                loop_ids.append(loop_id)

        # Circular boundary loops — classify OUTER vs INNER for planar circular faces.
        # For PLANAR faces with no linear edges (e.g. circular disk or annular face),
        # the largest circle is the OUTER boundary; smaller ones are inner holes.
        # For non-planar faces or faces with linear edges, circles are INNER (default).
        if surf_class == SurfaceClass.PLANAR and not line_ctags and circ_ctags:
            # Sort circles by bounding-box area descending; largest = outer
            def _circ_bb_area(ct: int) -> float:
                x0, y0, z0, x1, y1, z1 = gmsh.model.getBoundingBox(1, ct)
                return (x1 - x0) * (y1 - y0)
            sorted_circ = sorted(circ_ctags, key=_circ_bb_area, reverse=True)
            for i, ct in enumerate(sorted_circ):
                arc_eids = curve_to_edge_ids[ct]
                if len(arc_eids) >= 3:
                    ctype = LoopType.OUTER if i == 0 else LoopType.INNER
                    loop_id = f"LOOP-S{stag}-C{ct}"
                    loop = CanonicalLoop(
                        loop_id=loop_id,
                        edge_ids=tuple(arc_eids),
                        loop_type=ctype,
                        source_entity_ref=f"gmsh:s:{stag}:c{ct}",
                    )
                    all_loops.append(loop)
                    loop_ids.append(loop_id)
        else:
            circ_loop_type = LoopType.INNER if line_ctags else LoopType.UNKNOWN
            for ct in circ_ctags:
                arc_eids = curve_to_edge_ids[ct]
                if len(arc_eids) >= 3:
                    loop_id = f"LOOP-S{stag}-C{ct}"
                    loop = CanonicalLoop(
                        loop_id=loop_id,
                        edge_ids=tuple(arc_eids),
                        loop_type=circ_loop_type,
                        source_entity_ref=f"gmsh:s:{stag}:c{ct}",
                    )
                    all_loops.append(loop)
                    loop_ids.append(loop_id)

        if not loop_ids:
            # No valid loops could be built — skip this face
            continue

        face = CanonicalFace(
            face_id=f"F-{stag}",
            surface_id=f"SURF-{surf_class.value}-{stag}",
            boundary_loop_ids=tuple(loop_ids),
            orientation=Orientation.UNKNOWN,
            source_entity_ref=f"gmsh:s:{stag}",
            metadata={"surface_class": surf_class.value},
        )
        all_faces.append(face)

    # --- Pass 4: shells and bodies (3D entities) ---
    face_id_set = {f.face_id for f in all_faces}

    for _d, vtag in gmsh.model.getEntities(3):
        v_bounds = gmsh.model.getBoundary([(3, vtag)], oriented=False)
        face_tags = [abs(b[1]) for b in v_bounds]
        face_ids = [f"F-{ft}" for ft in face_tags if f"F-{ft}" in face_id_set]

        if not face_ids:
            continue

        xmin_v, ymin_v, zmin_v, xmax_v, ymax_v, zmax_v = gmsh.model.getBoundingBox(3, vtag)
        body_bbox = _bbox3d(xmin_v, ymin_v, zmin_v, xmax_v, ymax_v, zmax_v)

        shell_id = f"SHELL-{vtag}"
        shell = CanonicalShell(
            shell_id=shell_id,
            face_ids=tuple(face_ids),
            closure=ShellClosure.CLOSED,
            is_oriented=True,
            source_entity_ref=f"gmsh:vol:{vtag}",
        )
        all_shells.append(shell)

        body = CanonicalBody(
            body_id=f"BODY-{vtag}",
            body_type=BodyType.SOLID,
            shell_ids=(shell_id,),
            bounding_box=body_bbox,
            source_entity_ref=f"gmsh:vol:{vtag}",
        )
        all_bodies.append(body)

    return CanonicalTopology(
        topology_id=topology_id,
        vertices=tuple(all_vertices),
        edges=tuple(all_edges),
        loops=tuple(all_loops),
        faces=tuple(all_faces),
        shells=tuple(all_shells),
        bodies=tuple(all_bodies),
        geometry=None,
    )
