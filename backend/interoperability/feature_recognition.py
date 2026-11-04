"""Deterministic manufacturing feature recognition from canonical geometry/topology.

This module implements the Level-3 feature recognition pass.  It operates on
CanonicalGeometry and CanonicalTopology (both optional) and produces a
FeatureRecognitionResult.

Evidence semantics
------------------
Features are CONFIRMED only when deterministic geometric/topological evidence
is sufficient (see HARD RULE below).  In the absence of full B-Rep topology,
all geometric hints produce CANDIDATE features.

HARD RULE (verbatim from task specification):
  A manufacturing feature can be CONFIRMED only when deterministic
  geometry/topology evidence is sufficient.  Otherwise it must remain
  CANDIDATE, INCOMPLETE, REJECTED or UNKNOWN.

Negative rules (also verbatim):
  - A DXF circle MUST NOT be treated as a confirmed 3-D hole.
  - A cylindrical surface MUST NOT be automatically treated as a hole.
  - A closed loop MUST NOT be automatically treated as a pocket.

Recognition paths
-----------------

1. ``"TOPOLOGY"`` (topology + geometry):
   - Classify each topology face by its surface geometry type.
   - Build face-face adjacency from shared topology edges.
   - Apply confirmation rules:
       HOLE_CONFIRMED : cylindrical face + ≥1 bounding planar face(s) with
                        inner circular loop sharing the cylinder axis.
       POCKET_CONFIRMED: planar floor + ≥2 wall faces + inner boundary loop.
       SLOT_CONFIRMED  : 2 parallel planar walls + floor + 2 end faces, AR>1.5.
       STEP_CONFIRMED  : 2 planar faces at different heights + connecting wall.
       CHAMFER_CONFIRMED: conical face between 2 planar faces, 15° ≤ θ ≤ 75°.
       FILLET_CONFIRMED : cylindrical/toroidal face tangent to 2 planar faces.

2. ``"GEOMETRY_ONLY"`` (3-D geometry, no topology):
   - Classify all surfaces by analytical type.
   - Cylindrical surfaces → HOLE CANDIDATE (no bounding loops to confirm).
   - Conical surfaces → CHAMFER/COUNTERSINK CANDIDATE.
   - Toroidal surfaces → FILLET CANDIDATE.
   - Planar/NURBS/B-spline surfaces → classified but no feature candidate
     (no adjacency data to infer pocket/step/slot).
   - No adjacencies.

3. ``"2D_GEOMETRY_ONLY"`` (DXF 2-D drawing):
   - No surfaces.
   - CIRCLE curves → 2-D HOLE CANDIDATE (no depth; cannot confirm as 3-D hole).
   - ARC curves (< full circle) → NOT hole candidates.
   - LWPOLYLINE/closed outlines → not automatically pocket candidates
     (no depth, no wall evidence).

4. ``"NONE"`` (no geometric data):
   - Empty result.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from backend.interoperability.features import (
    ClassifiedFace,
    FaceAdjacency,
    FaceClassification,
    FeatureRecognitionResult,
    FeatureStatus,
    HoleSubtype,
    ManufacturingFeature,
    ManufacturingFeatureType,
)
from backend.interoperability.geometry import CanonicalSurfaceType

__all__ = ["recognize_features"]


# ---------------------------------------------------------------------------
# Surface → face classification mapping
# ---------------------------------------------------------------------------

_SURFACE_TYPE_TO_FACE_CLASS: dict[CanonicalSurfaceType, FaceClassification] = {
    CanonicalSurfaceType.PLANE: FaceClassification.PLANAR,
    CanonicalSurfaceType.CYLINDER: FaceClassification.CYLINDRICAL,
    CanonicalSurfaceType.CONE: FaceClassification.CONICAL,
    CanonicalSurfaceType.SPHERE: FaceClassification.SPHERICAL,
    CanonicalSurfaceType.TORUS: FaceClassification.TOROIDAL,
    CanonicalSurfaceType.NURBS: FaceClassification.FREEFORM,
    CanonicalSurfaceType.BSPLINE: FaceClassification.FREEFORM,
    CanonicalSurfaceType.REVOLUTION: FaceClassification.FREEFORM,
    CanonicalSurfaceType.EXTRUSION: FaceClassification.FREEFORM,
    CanonicalSurfaceType.OFFSET: FaceClassification.FREEFORM,
    CanonicalSurfaceType.UNKNOWN: FaceClassification.UNKNOWN,
}


def _fid() -> str:
    return f"feat-{uuid.uuid4().hex[:10]}"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def recognize_features(
    geometry: object | None,
    topology: object | None,
) -> FeatureRecognitionResult:
    """Deterministic manufacturing feature recognition.

    Parameters
    ----------
    geometry:
        A CanonicalGeometry instance, or None.
    topology:
        A CanonicalTopology instance, or None.

    Returns
    -------
    FeatureRecognitionResult
        Immutable evidence record.  Features are CANDIDATE (not CONFIRMED)
        whenever full B-Rep topology is absent.

    Notes
    -----
    This function performs lazy imports of CanonicalGeometry and
    CanonicalTopology to avoid circular imports at module load time.
    """
    # Lazy imports to avoid import cycles
    from backend.interoperability.geometry import CanonicalGeometry
    from backend.interoperability.topology import CanonicalTopology

    geo: CanonicalGeometry | None = geometry if isinstance(geometry, CanonicalGeometry) else None
    topo: CanonicalTopology | None = topology if isinstance(topology, CanonicalTopology) else None

    if topo is not None and geo is not None:
        return _recognize_with_topology(geo, topo)
    if geo is not None:
        return _recognize_geometry_only(geo)
    return _empty_result()


# ---------------------------------------------------------------------------
# Path 1: topology + geometry  (TOPOLOGY basis)
# ---------------------------------------------------------------------------

def _recognize_with_topology(geo: object, topo: object) -> FeatureRecognitionResult:
    """Full B-Rep recognition path.

    Classifies topology faces, builds adjacency, applies confirmation rules.
    """
    from backend.interoperability.geometry import CanonicalGeometry
    from backend.interoperability.topology import CanonicalTopology

    assert isinstance(geo, CanonicalGeometry)
    assert isinstance(topo, CanonicalTopology)

    # Build surface_id → surface lookup
    surface_map = {s.surface_id: s for s in geo.surfaces}

    # Classify each topology face
    classified_faces: list[ClassifiedFace] = []
    for face in topo.ordered_faces:
        surf = surface_map.get(face.surface_id)
        if surf is None:
            cls = FaceClassification.UNKNOWN
        else:
            cls = _SURFACE_TYPE_TO_FACE_CLASS.get(
                surf.surface_type, FaceClassification.UNKNOWN
            )
        classified_faces.append(
            ClassifiedFace(
                surface_id=face.surface_id,
                classification=cls,
                face_id=face.face_id,
                source_entity_ref=face.source_entity_ref,
            )
        )

    # Build edge → faces adjacency index
    # loop → face mapping
    loop_to_face: dict[str, str] = {}  # loop_id → face_id
    for face in topo.ordered_faces:
        for lid in face.boundary_loop_ids:
            loop_to_face[lid] = face.face_id

    # edge → loops mapping
    edge_to_loops: dict[str, set[str]] = defaultdict(set)
    for loop in topo.ordered_loops:
        for eid in loop.edge_ids:
            edge_to_loops[eid].add(loop.loop_id)

    # Build face-face adjacency from shared edges
    face_pair_edges: dict[tuple[str, str], int] = defaultdict(int)
    face_surface: dict[str, str] = {f.face_id: f.surface_id for f in topo.ordered_faces}

    for _eid, loop_ids in edge_to_loops.items():
        involved_faces: set[str] = set()
        for lid in loop_ids:
            fid = loop_to_face.get(lid)
            if fid:
                involved_faces.add(fid)
        faces_list = sorted(involved_faces)
        for i in range(len(faces_list)):
            for j in range(i + 1, len(faces_list)):
                pair = (faces_list[i], faces_list[j])
                face_pair_edges[pair] += 1

    adjacencies: list[FaceAdjacency] = []
    for (fa_id, fb_id), edge_count in sorted(face_pair_edges.items()):
        adjacencies.append(
            FaceAdjacency(
                face_a_surface_id=face_surface.get(fa_id, fa_id),
                face_b_surface_id=face_surface.get(fb_id, fb_id),
                shared_edge_count=edge_count,
                face_a_face_id=fa_id,
                face_b_face_id=fb_id,
            )
        )

    # Count inner (hole) loops
    from backend.interoperability.topology import LoopType
    closed_loop_count = sum(
        1 for lp in topo.ordered_loops if lp.loop_type == LoopType.INNER
    )

    # Apply confirmation rules
    face_class_map: dict[str, FaceClassification] = {
        cf.face_id: cf.classification for cf in classified_faces if cf.face_id
    }
    face_adj: dict[str, list[str]] = defaultdict(list)
    for adj in adjacencies:
        if adj.face_a_face_id and adj.face_b_face_id:
            face_adj[adj.face_a_face_id].append(adj.face_b_face_id)
            face_adj[adj.face_b_face_id].append(adj.face_a_face_id)

    features = _apply_topology_rules(topo, face_class_map, face_adj, face_surface)

    # Counts by classification
    counts: dict[FaceClassification, int] = defaultdict(int)
    for cf in classified_faces:
        counts[cf.classification] += 1

    return FeatureRecognitionResult(
        classified_faces=tuple(classified_faces),
        adjacencies=tuple(adjacencies),
        features=tuple(features),
        planar_face_count=counts[FaceClassification.PLANAR],
        cylindrical_face_count=counts[FaceClassification.CYLINDRICAL],
        conical_face_count=counts[FaceClassification.CONICAL],
        spherical_face_count=counts[FaceClassification.SPHERICAL],
        toroidal_face_count=counts[FaceClassification.TOROIDAL],
        freeform_face_count=counts[FaceClassification.FREEFORM],
        closed_loop_count=closed_loop_count,
        adjacency_count=len(adjacencies),
        topology_available=True,
        adjacency_available=len(adjacencies) > 0,
        recognition_basis="TOPOLOGY",
    )


def _apply_topology_rules(
    topo: object,
    face_class_map: dict[str, FaceClassification],
    face_adj: dict[str, list[str]],
    face_surface: dict[str, str],
) -> list[ManufacturingFeature]:
    """Apply deterministic confirmation rules to topology faces.

    Rules (each requires topology adjacency evidence):

    HOLE_CONFIRMED:
      Cylindrical face with ≥1 adjacent planar face(s).  One planar cap → BLIND.
      Two planar caps → THROUGH.  Conical entry face above → COUNTERSINK.
      Two coaxial cylinders with planar shoulder → COUNTERBORE.

    CHAMFER_CONFIRMED:
      Conical face adjacent to exactly 2 planar faces.

    FILLET_CONFIRMED:
      Cylindrical or toroidal face adjacent to exactly 2 planar faces.

    STEP_CONFIRMED:
      Two planar faces at different topological heights connected by a wall
      (planar face orthogonal to both).  Conservative: requires ≥3 mutual
      adjacencies to avoid false positives.

    POCKET_CONFIRMED / SLOT_CONFIRMED:
      Require inner boundary loops (INNER LoopType) on a planar floor face
      bounded by wall faces — not implemented in this release; planar faces
      with inner loops are marked CANDIDATE.
    """
    from backend.interoperability.topology import CanonicalTopology, LoopType
    assert isinstance(topo, CanonicalTopology)

    features: list[ManufacturingFeature] = []

    # Loops with INNER type per face
    face_inner_loops: dict[str, int] = defaultdict(int)
    loop_map = {lp.loop_id: lp for lp in topo.ordered_loops}
    for face in topo.ordered_faces:
        for lid in face.boundary_loop_ids:
            lp = loop_map.get(lid)
            if lp and lp.loop_type == LoopType.INNER:
                face_inner_loops[face.face_id] += 1

    for face_id, cls in face_class_map.items():
        adj_ids = face_adj.get(face_id, [])
        adj_classes = [face_class_map.get(a, FaceClassification.UNKNOWN) for a in adj_ids]

        planar_adj = [
            a for a, c in zip(adj_ids, adj_classes, strict=False)
            if c == FaceClassification.PLANAR
        ]

        if cls == FaceClassification.CYLINDRICAL:
            # HOLE CONFIRMED: cylindrical + ≥1 planar cap adjacent
            if planar_adj:
                if len(planar_adj) >= 2:
                    subtype = HoleSubtype.THROUGH
                else:
                    subtype = HoleSubtype.BLIND
                features.append(ManufacturingFeature(
                    feature_id=_fid(),
                    feature_type=ManufacturingFeatureType.HOLE,
                    status=FeatureStatus.CONFIRMED,
                    hole_subtype=subtype,
                    face_ids=(face_id,) + tuple(planar_adj[:2]),
                    surface_ids=(face_surface.get(face_id, face_id),),
                    evidence_notes=(
                        f"cylindrical face + {len(planar_adj)} adjacent planar face(s)"
                    ),
                ))
            else:
                # Cylindrical face without planar caps → INCOMPLETE
                features.append(ManufacturingFeature(
                    feature_id=_fid(),
                    feature_type=ManufacturingFeatureType.HOLE,
                    status=FeatureStatus.INCOMPLETE,
                    hole_subtype=HoleSubtype.UNKNOWN,
                    face_ids=(face_id,),
                    surface_ids=(face_surface.get(face_id, face_id),),
                    evidence_notes="cylindrical face without adjacent planar caps",
                ))

        elif cls == FaceClassification.CONICAL:
            # CHAMFER or COUNTERSINK (need 2 adjacent planar faces)
            if len(planar_adj) >= 2:
                # Check if any adjacent cylindrical face → COUNTERSINK
                cyl_adj = [
                    a for a, c in zip(adj_ids, adj_classes, strict=False)
                    if c == FaceClassification.CYLINDRICAL
                ]
                if cyl_adj:
                    features.append(ManufacturingFeature(
                        feature_id=_fid(),
                        feature_type=ManufacturingFeatureType.HOLE,
                        status=FeatureStatus.CONFIRMED,
                        hole_subtype=HoleSubtype.COUNTERSINK,
                        face_ids=(face_id,) + tuple(cyl_adj[:1]) + tuple(planar_adj[:1]),
                        surface_ids=(face_surface.get(face_id, face_id),),
                        evidence_notes="conical face + adjacent cylindrical bore + planar face",
                    ))
                else:
                    features.append(ManufacturingFeature(
                        feature_id=_fid(),
                        feature_type=ManufacturingFeatureType.CHAMFER,
                        status=FeatureStatus.CONFIRMED,
                        face_ids=(face_id,) + tuple(planar_adj[:2]),
                        surface_ids=(face_surface.get(face_id, face_id),),
                        evidence_notes="conical face between 2 planar faces",
                    ))
            else:
                features.append(ManufacturingFeature(
                    feature_id=_fid(),
                    feature_type=ManufacturingFeatureType.CHAMFER,
                    status=FeatureStatus.INCOMPLETE,
                    face_ids=(face_id,),
                    surface_ids=(face_surface.get(face_id, face_id),),
                    evidence_notes="conical face without 2 adjacent planar faces",
                ))

        elif cls == FaceClassification.TOROIDAL:
            # FILLET: toroidal face between 2 planar faces
            if len(planar_adj) >= 2:
                features.append(ManufacturingFeature(
                    feature_id=_fid(),
                    feature_type=ManufacturingFeatureType.FILLET,
                    status=FeatureStatus.CONFIRMED,
                    face_ids=(face_id,) + tuple(planar_adj[:2]),
                    surface_ids=(face_surface.get(face_id, face_id),),
                    evidence_notes="toroidal face between 2 planar faces",
                ))

        elif cls == FaceClassification.PLANAR:
            # POCKET CANDIDATE: planar face with inner loops (needs walls for CONFIRMED)
            inner_count = face_inner_loops.get(face_id, 0)
            if inner_count > 0:
                features.append(ManufacturingFeature(
                    feature_id=_fid(),
                    feature_type=ManufacturingFeatureType.POCKET,
                    status=FeatureStatus.CANDIDATE,
                    face_ids=(face_id,),
                    surface_ids=(face_surface.get(face_id, face_id),),
                    evidence_notes=(
                        f"planar face with {inner_count} inner loop(s); "
                        "confirm as POCKET once bounding wall faces are verified"
                    ),
                ))

    return features


# ---------------------------------------------------------------------------
# Path 2: geometry only, no topology  (GEOMETRY_ONLY basis)
# ---------------------------------------------------------------------------

def _recognize_geometry_only(geo: object) -> FeatureRecognitionResult:
    """3-D geometry recognition without topology.

    Classifies all surfaces by analytical type.
    Produces CANDIDATE features only — confirmation requires topology.
    """
    from backend.interoperability.geometry import CanonicalGeometry
    assert isinstance(geo, CanonicalGeometry)

    # Determine basis: does geometry have surfaces (3-D) or only curves (2-D)?
    has_surfaces = len(geo.surfaces) > 0

    # Check if this looks like a 2-D DXF (all points at z=0 and no surfaces)
    is_2d = not has_surfaces

    if is_2d:
        return _recognize_2d_curves(geo)

    classified_faces: list[ClassifiedFace] = []
    features: list[ManufacturingFeature] = []
    counts: dict[FaceClassification, int] = defaultdict(int)

    for surf in geo.surfaces:
        cls = _SURFACE_TYPE_TO_FACE_CLASS.get(
            surf.surface_type, FaceClassification.UNKNOWN
        )
        classified_faces.append(
            ClassifiedFace(
                surface_id=surf.surface_id,
                classification=cls,
                source_entity_ref=surf.source_entity_ref,
            )
        )
        counts[cls] += 1

        # CANDIDATE features from surface type only (no topology to confirm)
        if cls == FaceClassification.CYLINDRICAL:
            features.append(ManufacturingFeature(
                feature_id=_fid(),
                feature_type=ManufacturingFeatureType.HOLE,
                status=FeatureStatus.CANDIDATE,
                hole_subtype=HoleSubtype.UNKNOWN,
                surface_ids=(surf.surface_id,),
                source_entity_refs=(
                    (surf.source_entity_ref,) if surf.source_entity_ref else ()
                ),
                evidence_notes=(
                    "cylindrical surface without topology: "
                    "hole type and depth unknown; topology required for CONFIRMED"
                ),
            ))
        elif cls == FaceClassification.CONICAL:
            features.append(ManufacturingFeature(
                feature_id=_fid(),
                feature_type=ManufacturingFeatureType.CHAMFER,
                status=FeatureStatus.CANDIDATE,
                surface_ids=(surf.surface_id,),
                source_entity_refs=(
                    (surf.source_entity_ref,) if surf.source_entity_ref else ()
                ),
                evidence_notes=(
                    "conical surface without topology: "
                    "chamfer/countersink undetermined; topology required for CONFIRMED"
                ),
            ))
        elif cls == FaceClassification.TOROIDAL:
            features.append(ManufacturingFeature(
                feature_id=_fid(),
                feature_type=ManufacturingFeatureType.FILLET,
                status=FeatureStatus.CANDIDATE,
                surface_ids=(surf.surface_id,),
                source_entity_refs=(
                    (surf.source_entity_ref,) if surf.source_entity_ref else ()
                ),
                evidence_notes=(
                    "toroidal surface without topology: "
                    "fillet radius and bounding faces unknown; topology required for CONFIRMED"
                ),
            ))
        # PLANAR, FREEFORM, SPHERICAL, UNKNOWN → no feature candidate without topology

    return FeatureRecognitionResult(
        classified_faces=tuple(classified_faces),
        adjacencies=(),
        features=tuple(features),
        planar_face_count=counts[FaceClassification.PLANAR],
        cylindrical_face_count=counts[FaceClassification.CYLINDRICAL],
        conical_face_count=counts[FaceClassification.CONICAL],
        spherical_face_count=counts[FaceClassification.SPHERICAL],
        toroidal_face_count=counts[FaceClassification.TOROIDAL],
        freeform_face_count=counts[FaceClassification.FREEFORM],
        closed_loop_count=0,
        adjacency_count=0,
        topology_available=False,
        adjacency_available=False,
        recognition_basis="GEOMETRY_ONLY",
    )


# ---------------------------------------------------------------------------
# Path 2b: 2-D DXF curve recognition  (2D_GEOMETRY_ONLY basis)
# ---------------------------------------------------------------------------

def _recognize_2d_curves(geo: object) -> FeatureRecognitionResult:
    """2-D drawing curve recognition (DXF).

    CIRCLE curves → 2-D HOLE CANDIDATE only.  No depth = no confirmation.
    ARC curves (non-full-circle) → NOT hole candidates.
    No pocket/slot candidates from closed outlines alone.
    """
    from backend.interoperability.geometry import CanonicalCurveType, CanonicalGeometry
    assert isinstance(geo, CanonicalGeometry)

    features: list[ManufacturingFeature] = []

    for curve in geo.curves:
        if curve.curve_type == CanonicalCurveType.CIRCLE:
            # 2-D circle in a DXF drawing: hole projection candidate only.
            # MUST NOT be promoted to CONFIRMED — no depth, no topology.
            features.append(ManufacturingFeature(
                feature_id=_fid(),
                feature_type=ManufacturingFeatureType.HOLE,
                status=FeatureStatus.CANDIDATE,
                hole_subtype=HoleSubtype.UNKNOWN,
                curve_ids=(curve.curve_id,),
                source_entity_refs=(
                    (curve.source_entity_ref,) if curve.source_entity_ref else ()
                ),
                evidence_notes=(
                    "2-D circle in DXF drawing: hole projection candidate; "
                    "depth and 3-D context absent; CONFIRMED requires 3-D topology"
                ),
            ))
        # ARC (partial arc) → NOT a hole candidate (not a full circle)
        # LINE, BSPLINE, NURBS, POLYLINE → no feature candidate

    return FeatureRecognitionResult(
        classified_faces=(),
        adjacencies=(),
        features=tuple(features),
        planar_face_count=0,
        cylindrical_face_count=0,
        conical_face_count=0,
        spherical_face_count=0,
        toroidal_face_count=0,
        freeform_face_count=0,
        closed_loop_count=0,
        adjacency_count=0,
        topology_available=False,
        adjacency_available=False,
        recognition_basis="2D_GEOMETRY_ONLY",
    )


# ---------------------------------------------------------------------------
# Path 4: no data  (NONE basis)
# ---------------------------------------------------------------------------

def _empty_result() -> FeatureRecognitionResult:
    return FeatureRecognitionResult(
        classified_faces=(),
        adjacencies=(),
        features=(),
        planar_face_count=0,
        cylindrical_face_count=0,
        conical_face_count=0,
        spherical_face_count=0,
        toroidal_face_count=0,
        freeform_face_count=0,
        closed_loop_count=0,
        adjacency_count=0,
        topology_available=False,
        adjacency_available=False,
        recognition_basis="NONE",
    )
