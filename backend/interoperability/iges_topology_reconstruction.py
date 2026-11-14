"""IGES topology reconstruction from surface/curve inventory (P1-C).

Reconstructs surface-level topology from IGES files that contain surface and
boundary entities but no explicit B-Rep entities (types 186/502-514).

Specifically handles the common CATIA V5 IGES export pattern:
  - Type 108: Plane (planar surfaces)
  - Type 128: Rational B-Spline Surface (freeform surfaces)
  - Type 142: Curve on a Parametric Surface (boundary curves on surfaces)
  - Type 144: Trimmed Parametric Surface (surface + boundary reference)

HARD RULES:
  - HARD RULE 13: Do NOT convert open IGES surfaces into artificial solids.
  - HARD RULE 14: Do NOT manufacture artificial topology to make tests pass.
  - No fabricated vertices, edges, or loops from implicit geometry.
  - OPEN surface collection is acceptable and correct for these files.
  - Reconstruction is surface-group based; no fake B-Rep generated.
  - SURFACES_AVAILABLE=YES, CLOSED_BODY_AVAILABLE=NO for surface-only IGES.

Outputs:
  - IgesTopologyReconstructionResult: surface groups, adjacency, statistics
  - CanonicalTopology: empty B-Rep (no fabricated connectivity)
  - CanonicalTopology geometry reference preserved from original mapping

FABRICATED_TOPOLOGY=NO
FABRICATED_BODY=NO
FABRICATED_CLOSURE=NO
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum, unique
from types import MappingProxyType

from backend.interoperability.geometry import (
    CanonicalSurface,
    CanonicalSurfaceType,
)
from backend.interoperability.iges_mapping import IgesMappingResult
from backend.interoperability.topology import (
    BodyType,
    CanonicalTopology,
)

__all__ = [
    "SurfaceGroupType",
    "SurfaceGroup",
    "IgesReconstructionStatus",
    "IgesTopologyReconstructionResult",
    "reconstruct_iges_topology",
    "extract_iges_feature_candidates",
]

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

@unique
class SurfaceGroupType(StrEnum):
    PLANAR_ASSEMBLY    = "PLANAR_ASSEMBLY"      # Group of co-planar or near-parallel surfaces
    CYLINDRICAL_FAMILY = "CYLINDRICAL_FAMILY"   # Cylindrical surfaces with compatible axis
    FREEFORM_ASSEMBLY  = "FREEFORM_ASSEMBLY"    # B-spline / NURBS surfaces
    MIXED              = "MIXED"                # Mixed surface types


@unique
class IgesReconstructionStatus(StrEnum):
    SUCCESS             = "SUCCESS"
    PARTIAL             = "PARTIAL"              # Some surfaces grouped; others unclassified
    NO_SURFACES         = "NO_SURFACES"          # No surfaces in the mapped geometry
    NO_TOPOLOGY_ENTITIES= "NO_TOPOLOGY_ENTITIES" # Surfaces present; no B-Rep entities
    FAILED              = "FAILED"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SurfaceGroup:
    """A group of related surfaces in the reconstructed surface topology.

    Surface groups are derived from surface properties (type, normal direction,
    axis alignment) — NOT from fabricated B-Rep connectivity.

    surface_ids:    IDs of surfaces in this group (from canonical geometry)
    group_type:     Classification of the group
    normal_x/y/z:   For PLANAR_ASSEMBLY — approximate group normal (unit vector)
    axis_x/y/z:     For CYLINDRICAL_FAMILY — approximate common axis
    radius_mm:      For CYLINDRICAL_FAMILY — approximate radius (mm)
    source_note:    How this group was formed
    """

    group_id: str
    surface_ids: tuple[str, ...]
    group_type: SurfaceGroupType
    normal_x: float | None = None
    normal_y: float | None = None
    normal_z: float | None = None
    axis_x: float | None = None
    axis_y: float | None = None
    axis_z: float | None = None
    radius_mm: float | None = None
    source_note: str = ""

    @property
    def surface_count(self) -> int:
        return len(self.surface_ids)


@dataclass
class IgesTopologyReconstructionResult:
    """Result of IGES topology reconstruction.

    Provides surface-level topology (groups, adjacency counts) without
    fabricating B-Rep entities.

    HARD RULE: surfaces_available may be True while closed_body_available
    is False. This is the expected state for surface-sheet IGES models.
    """

    status: IgesReconstructionStatus = IgesReconstructionStatus.NO_SURFACES
    source_id: str = "iges-reconstruction"

    # Reconstruction statistics (from actual IGES entities)
    surface_count: int = 0
    curve_count: int = 0
    boundary_entity_count: int = 0    # Count of type 142/144 boundary entities
    loop_count: int = 0               # Approximated from trimmed surface structure
    shell_count: int = 0              # Connected surface groups
    body_count: int = 0               # Top-level body groups

    # Surface groups (planar, cylindrical, freeform)
    surface_groups: list[SurfaceGroup] = field(default_factory=list)

    # Topology state flags
    surfaces_available: bool = False
    closed_body_available: bool = False   # ALWAYS False for surface-only IGES
    topology_fabricated: bool = False     # ALWAYS False — no fabrication

    # Canonical topology (empty B-Rep; geometry reference preserved)
    canonical_topology: CanonicalTopology | None = None

    # Feature candidates inferred from surface groups (SURFACE_HEURISTIC method).
    # depth_mm is always None — cannot be determined from surface-only IGES.
    # topology_fabricated stays False; these are inference hints only.
    feature_candidates: list = field(default_factory=list)  # list[ManufacturingFeature]

    # Warnings and issues
    warnings: list[str] = field(default_factory=list)

    @property
    def planar_group_count(self) -> int:
        return sum(1 for g in self.surface_groups
                   if g.group_type == SurfaceGroupType.PLANAR_ASSEMBLY)

    @property
    def cylindrical_group_count(self) -> int:
        return sum(1 for g in self.surface_groups
                   if g.group_type == SurfaceGroupType.CYLINDRICAL_FAMILY)

    @property
    def freeform_group_count(self) -> int:
        return sum(1 for g in self.surface_groups
                   if g.group_type == SurfaceGroupType.FREEFORM_ASSEMBLY)


# ---------------------------------------------------------------------------
# Surface grouping helpers
# ---------------------------------------------------------------------------

_NORMAL_ANGLE_TOLERANCE = 15.0    # degrees — surfaces within this angle are "co-planar direction"
_AXIS_ANGLE_TOLERANCE   = 15.0    # degrees — cylindrical surfaces within this angle share axis
_RADIUS_RELATIVE_TOL    = 0.05    # relative — cylindrical surface radii within 5% are same

def _vec_len(x: float, y: float, z: float) -> float:
    return math.sqrt(x * x + y * y + z * z)


def _normalize_vec(x: float, y: float, z: float) -> tuple[float, float, float] | None:
    length = _vec_len(x, y, z)
    if length < 1e-12:
        return None
    return (x / length, y / length, z / length)


def _angle_between_vecs(
    v1: tuple[float, float, float],
    v2: tuple[float, float, float],
) -> float:
    """Return angle in degrees between two unit vectors (0–90, symmetric)."""
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    dot = max(-1.0, min(1.0, dot))
    angle_deg = math.degrees(math.acos(abs(dot)))
    return min(angle_deg, 180.0 - angle_deg)


def _surface_normal(surf: CanonicalSurface) -> tuple[float, float, float] | None:
    """Extract or approximate surface normal for PLANE type surfaces."""
    if surf.surface_type == CanonicalSurfaceType.PLANE and surf.normal is not None:
        try:
            nx = float(surf.normal.x.value)
            ny = float(surf.normal.y.value)
            nz = float(surf.normal.z.value)
        except (AttributeError, TypeError):
            return None
        return _normalize_vec(nx, ny, nz)
    return None


def _surface_axis(surf: CanonicalSurface) -> tuple[float, float, float] | None:
    """Extract surface axis for CYLINDER type surfaces."""
    if surf.surface_type == CanonicalSurfaceType.CYLINDER and surf.axis is not None:
        try:
            ax = float(surf.axis.x.value)
            ay = float(surf.axis.y.value)
            az = float(surf.axis.z.value)
        except (AttributeError, TypeError):
            return None
        return _normalize_vec(ax, ay, az)
    return None


def _surface_radius_mm(surf: CanonicalSurface) -> float | None:
    if surf.surface_type == CanonicalSurfaceType.CYLINDER and surf.radius is not None:
        try:
            return float(surf.radius.value)
        except (AttributeError, TypeError):
            return None
    return None


def _group_planar_surfaces(
    surfaces: list[CanonicalSurface],
) -> list[tuple[tuple[float, float, float], list[str]]]:
    """Group PLANE surfaces by normal direction proximity.

    Returns list of (representative_normal, [surface_ids]).
    Single-surface groups ARE included (a planar face by itself is still a group).
    """
    planar = [
        (s, _surface_normal(s)) for s in surfaces
        if s.surface_type == CanonicalSurfaceType.PLANE
    ]
    groups: list[tuple[tuple[float, float, float], list[str]]] = []

    for surf, normal in planar:
        if normal is None:
            # No normal available — create its own group
            groups.append(((0.0, 0.0, 1.0), [surf.surface_id]))
            continue
        matched = False
        for _i, (gn, gids) in enumerate(groups):
            angle = _angle_between_vecs(normal, gn)
            if angle <= _NORMAL_ANGLE_TOLERANCE:
                gids.append(surf.surface_id)
                matched = True
                break
        if not matched:
            groups.append((normal, [surf.surface_id]))
    return groups


def _group_cylindrical_surfaces(
    surfaces: list[CanonicalSurface],
) -> list[tuple[tuple[float, float, float], float | None, list[str]]]:
    """Group CYLINDER surfaces by axis proximity and approximate radius.

    Returns list of (representative_axis, radius_mm_or_none, [surface_ids]).
    """
    cylindrical = [
        (s, _surface_axis(s), _surface_radius_mm(s))
        for s in surfaces
        if s.surface_type == CanonicalSurfaceType.CYLINDER
    ]
    groups: list[tuple[tuple[float, float, float], float | None, list[str]]] = []

    for surf, axis, radius in cylindrical:
        axis = axis or (0.0, 0.0, 1.0)
        matched = False
        for _i, (ga, gr, gids) in enumerate(groups):
            angle = _angle_between_vecs(axis, ga)
            if angle > _AXIS_ANGLE_TOLERANCE:
                continue
            if radius is not None and gr is not None:
                if abs(radius - gr) / max(gr, 1e-6) > _RADIUS_RELATIVE_TOL:
                    continue
            gids.append(surf.surface_id)
            matched = True
            break
        if not matched:
            groups.append((axis, radius, [surf.surface_id]))
    return groups


# ---------------------------------------------------------------------------
# Main reconstruction function
# ---------------------------------------------------------------------------

def reconstruct_iges_topology(
    mapping_result: IgesMappingResult,
    source_id: str = "iges",
) -> IgesTopologyReconstructionResult:
    """Reconstruct surface-level topology from an IGES mapping result.

    Operates on the geometry extracted by map_iges_model(). Does NOT
    fabricate B-Rep vertices, edges, or loops.

    For IGES files with surfaces but no B-Rep entities:
      - Groups surfaces by normal/axis into SurfaceGroups
      - Counts boundary entities as a proxy for topological loops
      - Builds a CanonicalTopology with geometry reference but empty B-Rep
      - Reports SURFACES_AVAILABLE=YES, CLOSED_BODY_AVAILABLE=NO

    Args:
        mapping_result:  Result from iges_mapping.map_iges_model()
        source_id:       Identifier for logging/reporting

    Returns:
        IgesTopologyReconstructionResult with surface groups and statistics.
    """
    result = IgesTopologyReconstructionResult(source_id=source_id)

    # If mapping already produced B-Rep topology, report it and don't re-do
    if mapping_result.topology is not None:
        result.status = IgesReconstructionStatus.SUCCESS
        result.canonical_topology = mapping_result.topology
        result.surfaces_available = True
        topo = mapping_result.topology
        result.surface_count = len(topo.faces) if topo.faces else 0
        result.curve_count = 0
        result.loop_count = len(topo.loops) if topo.loops else 0
        result.shell_count = len(topo.shells) if topo.shells else 0
        result.body_count = len(topo.bodies) if topo.bodies else 0
        result.closed_body_available = any(
            getattr(b, "body_type", None) == BodyType.SOLID
            for b in topo.bodies
        )
        return result

    geom = mapping_result.geometry
    if geom is None or not geom.surfaces:
        result.status = IgesReconstructionStatus.NO_SURFACES
        result.warnings.append("NO_SURFACES: geometry contains no surfaces")
        return result

    result.surfaces_available = True
    result.closed_body_available = False   # Cannot be True for surface-only IGES

    surfaces_list = list(geom.surfaces)
    result.surface_count = len(surfaces_list)
    result.curve_count = len(geom.curves)

    # Count boundary entities (a proxy for loops)
    # Type 141 → entity_kind "IgesBoundary"
    # Type 142 → entity_kind "IgesCurveOnParametricSurface"
    _BOUNDARY_KINDS = {"IgesBoundary", "IgesCurveOnParametricSurface"}
    boundary_count = sum(
        1 for er in mapping_result.entity_refs
        if getattr(er, "entity_kind", "") in _BOUNDARY_KINDS
    )
    # Trimmed surfaces (type 144) have outer_boundary_relationship_id in metadata
    trimmed_count = sum(
        1 for s in surfaces_list
        if "outer_boundary_relationship_id" in (getattr(s, "metadata", None) or {})
    )
    result.boundary_entity_count = boundary_count + trimmed_count
    # Approximate loop count: each trimmed surface has at least one loop
    result.loop_count = max(boundary_count, trimmed_count)

    # Build surface groups
    surface_groups: list[SurfaceGroup] = []
    group_counter = 0

    # --- Planar surface groups ---
    for normal, sids in _group_planar_surfaces(surfaces_list):
        group_counter += 1
        surface_groups.append(SurfaceGroup(
            group_id=f"pg-{group_counter:04d}",
            surface_ids=tuple(sids),
            group_type=SurfaceGroupType.PLANAR_ASSEMBLY,
            normal_x=normal[0],
            normal_y=normal[1],
            normal_z=normal[2],
            source_note="grouped-by-normal-direction",
        ))

    # --- Cylindrical surface groups ---
    for axis, radius, sids in _group_cylindrical_surfaces(surfaces_list):
        group_counter += 1
        surface_groups.append(SurfaceGroup(
            group_id=f"cg-{group_counter:04d}",
            surface_ids=tuple(sids),
            group_type=SurfaceGroupType.CYLINDRICAL_FAMILY,
            axis_x=axis[0],
            axis_y=axis[1],
            axis_z=axis[2],
            radius_mm=radius,
            source_note="grouped-by-axis-direction",
        ))

    # --- Freeform surfaces (B-spline / NURBS) ---
    freeform_types = {
        CanonicalSurfaceType.BSPLINE,
        CanonicalSurfaceType.NURBS,
        CanonicalSurfaceType.REVOLUTION,
        CanonicalSurfaceType.EXTRUSION,
        CanonicalSurfaceType.OFFSET,
        CanonicalSurfaceType.UNKNOWN,
    }
    grouped_ids: set[str] = set()
    for g in surface_groups:
        grouped_ids.update(g.surface_ids)
    freeform_ids = [
        s.surface_id for s in surfaces_list
        if s.surface_id not in grouped_ids
        and s.surface_type in freeform_types
    ]
    if freeform_ids:
        group_counter += 1
        surface_groups.append(SurfaceGroup(
            group_id=f"ff-{group_counter:04d}",
            surface_ids=tuple(freeform_ids),
            group_type=SurfaceGroupType.FREEFORM_ASSEMBLY,
            source_note="ungrouped-freeform-surfaces",
        ))

    # --- Any remaining surfaces (UNKNOWN/OTHER types) ---
    all_grouped_ids: set[str] = set()
    for g in surface_groups:
        all_grouped_ids.update(g.surface_ids)
    remaining_ids = [s.surface_id for s in surfaces_list if s.surface_id not in all_grouped_ids]
    if remaining_ids:
        group_counter += 1
        surface_groups.append(SurfaceGroup(
            group_id=f"ux-{group_counter:04d}",
            surface_ids=tuple(remaining_ids),
            group_type=SurfaceGroupType.MIXED,
            source_note="unclassified-surface-type",
        ))

    result.surface_groups = surface_groups
    result.shell_count = len(surface_groups)
    result.body_count = 1 if surface_groups else 0

    # Build a CanonicalTopology with geometry reference but NO fabricated B-Rep.
    # Shells are built from the surface group surface_ids as a simplified topology.
    # Faces, loops, edges, vertices are NOT created (would require fabrication).
    #
    # We skip building full shells in CanonicalTopology because that would require
    # CanonicalFace → CanonicalLoop → CanonicalEdge → CanonicalVertex chain.
    # Reporting this as a topology with geometry only is honest per HARD RULE 14.
    canonical_topo = CanonicalTopology(
        topology_id=f"iges-reconstructed-{source_id}",
        vertices=(),
        edges=(),
        loops=(),
        faces=(),
        shells=(),
        bodies=(),
        geometry=geom,
        source_entity_ref=None,
        metadata=MappingProxyType({
            "reconstruction_method": "surface_grouping",
            "surface_count": str(result.surface_count),
            "shell_count": str(result.shell_count),
            "closed_body_available": "NO",
            "surfaces_available": "YES",
            "topology_fabricated": "NO",
        }),
    )
    result.canonical_topology = canonical_topo
    result.status = IgesReconstructionStatus.SUCCESS
    result.warnings.append(
        "TOPOLOGY_PARTIAL: surface-sheet topology only — "
        "no B-Rep vertices/edges/loops (not present in source IGES file)"
    )

    # Populate feature_candidates after result is otherwise complete
    result.feature_candidates = extract_iges_feature_candidates(result, source_id)

    return result


def reconstruct_topology_from_file(
    iges_bytes: bytes,
    source_id: str = "iges",
) -> IgesTopologyReconstructionResult:
    """Convenience wrapper: parse IGES, map, and reconstruct topology.

    Args:
        iges_bytes: Raw IGES file bytes.
        source_id:  Identifier for logging.

    Returns:
        IgesTopologyReconstructionResult.
    """
    from backend.interoperability.iges_mapping import map_iges_model
    from backend.interoperability.iges_parser import parse_iges_bytes

    model = parse_iges_bytes(iges_bytes)
    mapping = map_iges_model(model)
    return reconstruct_iges_topology(mapping, source_id=source_id)


def extract_iges_feature_candidates(
    recon: IgesTopologyReconstructionResult,
    source_document_id: str = "iges",
) -> list:
    """Infer manufacturing feature candidates from IGES surface groups.

    Produces CANDIDATE-only features using SURFACE_HEURISTIC method.
    These are inference hints — not confirmed engineering data.

    Rules:
      - CYLINDRICAL_FAMILY → PRECISION_BORE_CANDIDATE with radius/axis if known.
        depth_mm is always None (cannot be derived from surface-only IGES).
      - PLANAR_ASSEMBLY with ≥1 surface → PLANAR_FACE candidate.
      - topology_fabricated stays False.
      - closed_body_available stays False.
      - Every candidate has confidence=INFERRED and review_required=True.

    Returns list[ManufacturingFeature].
    """
    import uuid
    from decimal import Decimal
    from types import MappingProxyType

    from backend.domain.units import Quantity, Unit
    from backend.interoperability.cad_feature_recognition import (
        FeatureRecognitionConfidence,
        ManufacturingFeature,
        ManufacturingFeatureType,
        RecognitionMethod,
    )
    from backend.interoperability.geometry import (
        CanonicalSurfaceType,
        CanonicalVector3D,
    )

    def _qty(v: float) -> Quantity:
        return Quantity(value=Decimal(str(round(v, 4))), unit=Unit.MM)

    def _vec(x: float, y: float, z: float) -> CanonicalVector3D:
        return CanonicalVector3D(
            x=Quantity(value=Decimal(str(x)), unit=Unit.DIMENSIONLESS),
            y=Quantity(value=Decimal(str(y)), unit=Unit.DIMENSIONLESS),
            z=Quantity(value=Decimal(str(z)), unit=Unit.DIMENSIONLESS),
        )

    candidates: list[ManufacturingFeature] = []

    for group in recon.surface_groups:
        if group.group_type == SurfaceGroupType.CYLINDRICAL_FAMILY:
            radius = group.radius_mm
            diam: Decimal | None = (
                Decimal(str(round(radius * 2.0, 4))) if radius is not None else None
            )
            axis = None
            if (group.axis_x is not None
                    and group.axis_y is not None
                    and group.axis_z is not None):
                axis = _vec(group.axis_x, group.axis_y, group.axis_z)
            fid = f"feat-iges-bore-{uuid.uuid4().hex[:8]}"
            candidates.append(ManufacturingFeature(
                feature_id=fid,
                feature_type=ManufacturingFeatureType.PRECISION_BORE_CANDIDATE,
                source_body_id=source_document_id,
                source_face_ids=group.surface_ids,
                source_edge_ids=(),
                surface_type=CanonicalSurfaceType.CYLINDER,
                location=None,
                axis=axis,
                diameter_mm=diam,
                depth_mm=None,       # cannot be determined from surface-only IGES
                width_mm=None,
                length_mm=None,
                radius_mm=Decimal(str(round(radius, 4))) if radius is not None else None,
                angle_deg=None,
                bounding_box=None,
                recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
                confidence=FeatureRecognitionConfidence.INFERRED,
                pattern_id=None,
                confirmed_by=None,
                metadata=MappingProxyType({
                    "source": "IGES_SURFACE_GROUP",
                    "group_id": group.group_id,
                    "surface_count": str(group.surface_count),
                    "depth_unknown": "YES",
                    "review_required": "YES",
                }),
            ))

        elif group.group_type == SurfaceGroupType.PLANAR_ASSEMBLY:
            axis = None
            if (group.normal_x is not None
                    and group.normal_y is not None
                    and group.normal_z is not None):
                axis = _vec(group.normal_x, group.normal_y, group.normal_z)
            fid = f"feat-iges-face-{uuid.uuid4().hex[:8]}"
            candidates.append(ManufacturingFeature(
                feature_id=fid,
                feature_type=ManufacturingFeatureType.PLANAR_FACE,
                source_body_id=source_document_id,
                source_face_ids=group.surface_ids,
                source_edge_ids=(),
                surface_type=CanonicalSurfaceType.PLANE,
                location=None,
                axis=axis,
                diameter_mm=None,
                depth_mm=None,
                width_mm=None,
                length_mm=None,
                radius_mm=None,
                angle_deg=None,
                bounding_box=None,
                recognition_method=RecognitionMethod.SURFACE_HEURISTIC,
                confidence=FeatureRecognitionConfidence.INFERRED,
                pattern_id=None,
                confirmed_by=None,
                metadata=MappingProxyType({
                    "source": "IGES_SURFACE_GROUP",
                    "group_id": group.group_id,
                    "surface_count": str(group.surface_count),
                    "review_required": "YES",
                }),
            ))

    return candidates
