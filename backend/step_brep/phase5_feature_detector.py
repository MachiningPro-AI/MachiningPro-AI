"""
P10 Phase 5 — Real 3D feature coverage (MUST 4–20, 26–30).

Implements:
  - Improved cylinder axis / diameter computation (fixes Phase 3 bbox heuristic)
  - Cylinder orientation: INTERNAL_CYLINDER / EXTERNAL_CYLINDER / AMBIGUOUS_CYLINDER
  - Face adjacency from shared boundary_curve_tags (no live gmsh session needed)
  - Pocket candidate detection (horizontal floor + adjacent wall faces)
  - Slot candidate detection (planar floor + 2 parallel side walls)
  - Step / shoulder detection (two horizontal faces at different heights via wall)
  - Gouge comparator framework (NOT_IMPLEMENTED; infrastructure documented for Phase 6F)

HARD RULES:
  - feature_status is always CANDIDATE — never CONFIRMED.
  - is_dispatchable is always False.
  - production_released is always False.
  - No fabricated pocket depth, slot width, or bore classification.
  - AMBIGUOUS remains AMBIGUOUS.
  - UNKNOWN remains UNKNOWN.
  - NOT_VERIFIABLE remains NOT_VERIFIABLE.
  - OD_AS_BORE_FALSE_POSITIVE_COUNT=0 for controlled negative geometries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.step_brep.gmsh_step_parser import StepFaceSummary, StepImportRecord

__all__ = [
    "CylinderOrientation",
    "OrientedCylinderRecord",
    "PocketCandidateRecord",
    "SlotCandidateRecord",
    "StepShoulderRecord",
    "GougeComparatorResult",
    "build_face_adjacency",
    "compute_cylinder_params",
    "classify_cylinder_orientation",
    "detect_oriented_cylinders",
    "detect_pocket_candidates",
    "detect_slot_candidates",
    "detect_step_shoulder_candidates",
    "build_gouge_comparator_result",
    "GOUGE_COMPARATOR_IMPLEMENTED",
]

_FLAT_THRESHOLD = 1e-4   # bbox extent considered "zero" for planar detection
_AXIS_RATIO_TOL = 0.15   # 15% tolerance for two extents to be "equal" (cylindrical axis)
_PARALLEL_NORMAL_TOL = 0.1   # normal dot product tolerance for "parallel" faces
_MIN_HOLE_DIAMETER_MM = 0.5
_MAX_HOLE_DIAMETER_MM = 500.0

GOUGE_COMPARATOR_IMPLEMENTED: bool = False


# ===========================================================================
# Enumerations
# ===========================================================================


class CylinderOrientation(StrEnum):
    INTERNAL_CYLINDER = "INTERNAL_CYLINDER"   # bore / through-hole candidate
    EXTERNAL_CYLINDER = "EXTERNAL_CYLINDER"   # OD / shaft / boss
    AMBIGUOUS_CYLINDER = "AMBIGUOUS_CYLINDER"  # cannot determine without topology


# ===========================================================================
# Data classes
# ===========================================================================


@dataclass(frozen=True)
class OrientedCylinderRecord:
    """Cylindrical face with Phase 5 orientation and improved geometry.

    feature_status=CANDIDATE always.  is_dispatchable=False always.
    cylinder_orientation may be INTERNAL/EXTERNAL/AMBIGUOUS.
    """

    face_tag: int
    feature_status: str           # always "CANDIDATE"
    hole_class: str               # THROUGH_HOLE_CANDIDATE | BLIND_HOLE_CANDIDATE | TRANSITION_RING
    cylinder_orientation: CylinderOrientation
    diameter_mm: float            # from improved axis detection
    axis_direction: str | None    # "X" | "Y" | "Z" | None
    depth_mm: float | None        # bbox extent along axis; None if axis unknown
    circular_boundary_count: int
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    orientation_evidence: str     # human-readable evidence for the classification

    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def production_released(self) -> bool:
        return False


@dataclass(frozen=True)
class PocketCandidateRecord:
    """Bounded pocket candidate from face topology.

    Requires: horizontal floor face + ≥2 adjacent wall faces.
    feature_status=CANDIDATE always.  is_dispatchable=False always.
    Dimensions are from bbox evidence only; UNKNOWN when not computable.
    """

    floor_face_tag: int
    wall_face_tags: tuple[int, ...]
    pocket_class: str    # RECTANGULAR_POCKET_CANDIDATE | GENERAL_POCKET_CANDIDATE | AMBIGUOUS
    feature_status: str  # always "CANDIDATE"
    depth_mm: float | None          # from part top Z minus floor Z; None if axis ambiguous
    width_mm: float | None          # from floor bbox; None if not computable
    length_mm: float | None         # from floor bbox; None if not computable
    opening_z: float | None         # Z position of the pocket opening (top of walls)
    evidence: str

    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def production_released(self) -> bool:
        return False


@dataclass(frozen=True)
class SlotCandidateRecord:
    """Bounded slot candidate from face topology.

    Requires: planar floor face + 2 parallel planar side walls connected to floor.
    feature_status=CANDIDATE always.  is_dispatchable=False always.
    """

    floor_face_tag: int
    side_wall_tags: tuple[int, int]   # exactly 2 parallel walls
    end_face_tags: tuple[int, ...]    # 0 (open), 1, or 2 end faces
    slot_class: str     # OPEN_SLOT_CANDIDATE | CLOSED_SLOT_CANDIDATE | AMBIGUOUS_SLOT
    feature_status: str # always "CANDIDATE"
    width_mm: float | None      # distance between walls; None if not computable
    depth_mm: float | None      # floor to opening; None if not computable
    length_mm: float | None     # slot length from floor bbox; None if not computable
    axis_direction: str | None  # direction slot runs along ("X"|"Y"|"Z"|None)
    evidence: str

    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def production_released(self) -> bool:
        return False


@dataclass(frozen=True)
class StepShoulderRecord:
    """Bounded step/shoulder candidate from face topology.

    Requires: two horizontal planar faces at different Z heights, connected through
    a vertical wall face.
    feature_status=CANDIDATE always.
    """

    lower_face_tag: int
    upper_face_tag: int
    wall_face_tag: int
    step_height_mm: float | None   # upper Z - lower Z; None if axis ambiguous
    feature_status: str            # always "CANDIDATE"
    evidence: str

    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def production_released(self) -> bool:
        return False


@dataclass(frozen=True)
class GougeComparatorResult:
    """Gouge comparison result placeholder.

    GOUGE_COMPARATOR_IMPLEMENTED=False.
    All results are NOT_VERIFIABLE pending voxel simulation infrastructure.

    Required inputs for a future implementation (Phase 6F):
      - STEP target geometry (available: StepImportRecord)
      - Voxel simulation result (NOT available: no voxel engine)
      - Coordinate system alignment (NOT available)
      - Tolerance definition (NOT available)
    """

    source_path: str
    result: str                     # always "NOT_VERIFIABLE" in Phase 5
    comparator_implemented: bool    # always False
    step_target_available: bool
    voxel_result_available: bool    # always False
    coordinate_alignment: str       # always "NOT_VERIFIED"
    voxel_size_mm: float | None     # None — no voxel model
    comparison_method: str          # "NOT_IMPLEMENTED"
    estimated_geometric_error_bound: float | None  # None
    notes: str

    @property
    def gouge_validated(self) -> str:
        return "NOT_VERIFIABLE"

    @property
    def is_dispatchable(self) -> bool:
        return False


# ===========================================================================
# Face adjacency (from boundary_curve_tags — no gmsh required)
# ===========================================================================


def build_face_adjacency(faces: list[StepFaceSummary]) -> dict[int, frozenset[int]]:
    """Build face-to-adjacent-faces map from shared boundary curve tags.

    Two faces are adjacent if they share at least one boundary edge tag.
    Returns dict: face_tag → frozenset of adjacent face_tags.

    Uses only StepImportRecord.faces[].boundary_curve_tags — no live gmsh session needed.
    """
    edge_to_faces: dict[int, list[int]] = {}
    for face in faces:
        for etag in face.boundary_curve_tags:
            edge_to_faces.setdefault(etag, []).append(face.tag)

    adj: dict[int, set[int]] = {f.tag: set() for f in faces}
    for _edge_tag, face_tags in edge_to_faces.items():
        for ft in face_tags:
            for ft2 in face_tags:
                if ft2 != ft:
                    adj[ft].add(ft2)

    return {k: frozenset(v) for k, v in adj.items()}


# ===========================================================================
# Improved cylinder axis + diameter computation
# ===========================================================================


def compute_cylinder_params(
    face: StepFaceSummary,
) -> tuple[str | None, float | None, float | None]:
    """Return (axis_direction, diameter_mm, depth_mm) from cylindrical face bbox.

    Phase 5 improvement: uses the axis where the other two extents are MOST EQUAL
    (the cylinder has equal radial extents in both directions perpendicular to its axis).
    This fixes the Phase 3 "largest extent = axis" heuristic that failed for short cylinders
    (e.g., disks, flange faces) where diameter > height.

    Returns (None, None, None) if geometry is degenerate.
    """
    dx = face.bbox_max[0] - face.bbox_min[0]
    dy = face.bbox_max[1] - face.bbox_min[1]
    dz = face.bbox_max[2] - face.bbox_min[2]
    extents = {"X": dx, "Y": dy, "Z": dz}

    best_axis: str | None = None
    best_ratio = float("inf")
    for axis_cand in ("X", "Y", "Z"):
        others = [extents[a] for a in ("X", "Y", "Z") if a != axis_cand]
        m1, m2 = max(others), min(others)
        if m2 < _FLAT_THRESHOLD:
            continue  # degenerate
        ratio = m1 / m2
        if ratio < best_ratio:
            best_ratio = ratio
            best_axis = axis_cand

    if best_axis is None:
        return None, None, None

    others = [extents[a] for a in ("X", "Y", "Z") if a != best_axis]
    diameter = sum(others) / 2.0
    depth = extents[best_axis]

    if diameter < _MIN_HOLE_DIAMETER_MM:
        return best_axis, None, depth

    return best_axis, round(diameter, 4), round(depth, 4)


# ===========================================================================
# Cylinder orientation classification
# ===========================================================================


def classify_cylinder_orientation(
    face: StepFaceSummary,
    record: StepImportRecord,
) -> tuple[CylinderOrientation, str]:
    """Classify a cylindrical face as INTERNAL, EXTERNAL, or AMBIGUOUS.

    Evidence sources (all from StepFaceSummary / StepImportRecord — no live gmsh):

    1. DIAMETER_TO_PART_RATIO:
       If diameter >= 0.85 × min(part_lateral_extent) → likely EXTERNAL (OD spans part).
       If diameter < 0.5 × min(part_lateral_extent) AND face NOT concentric → INTERNAL.

    2. FACE_CENTER_OFFSET:
       If the face bbox center is significantly offset from the part's XY center:
         this face is NOT concentric with the part → likely a HOLE (INTERNAL).
       If face center ≈ part center in XY → concentric, cannot determine (AMBIGUOUS).

    3. ASPECT_RATIO:
       depth/diameter < 0.3 → SHORT_CYLINDER (transition ring, flange OD step)
         → EXTERNAL or AMBIGUOUS (not a hole).

    Returns (CylinderOrientation, evidence_string).
    AMBIGUOUS is the fail-safe for cases we cannot resolve geometrically.
    """
    if record.bbox_min is None or record.bbox_max is None:
        return CylinderOrientation.AMBIGUOUS_CYLINDER, "PART_BBOX_UNAVAILABLE"

    axis, diameter_mm, depth_mm = compute_cylinder_params(face)

    if diameter_mm is None:
        return CylinderOrientation.AMBIGUOUS_CYLINDER, "DIAMETER_DEGENERATE"

    # Part extents
    part_dx = record.bbox_max[0] - record.bbox_min[0]
    part_dy = record.bbox_max[1] - record.bbox_min[1]
    part_dz = record.bbox_max[2] - record.bbox_min[2]

    # Part and face centers
    part_cx = (record.bbox_min[0] + record.bbox_max[0]) / 2.0
    part_cy = (record.bbox_min[1] + record.bbox_max[1]) / 2.0
    face_cx = (face.bbox_min[0] + face.bbox_max[0]) / 2.0
    face_cy = (face.bbox_min[1] + face.bbox_max[1]) / 2.0

    # Lateral part size (excluding axis direction)
    if axis == "Z":
        min_part_lateral = min(part_dx, part_dy)
    elif axis == "X":
        min_part_lateral = min(part_dy, part_dz)
    elif axis == "Y":
        min_part_lateral = min(part_dx, part_dz)
    else:
        min_part_lateral = min(part_dx, part_dy)

    if min_part_lateral < _FLAT_THRESHOLD:
        return CylinderOrientation.AMBIGUOUS_CYLINDER, "PART_LATERAL_DEGENERATE"

    diameter_ratio = diameter_mm / min_part_lateral

    # Offset of face center from part center (XY plane)
    offset_xy = ((face_cx - part_cx) ** 2 + (face_cy - part_cy) ** 2) ** 0.5
    offset_ratio = offset_xy / (min_part_lateral / 2.0)

    # Aspect ratio
    if depth_mm is not None and depth_mm > _FLAT_THRESHOLD:
        aspect = depth_mm / diameter_mm
    else:
        aspect = 0.0

    evidence_parts = [
        f"dia_ratio={diameter_ratio:.3f}",
        f"offset_ratio={offset_ratio:.3f}",
        f"aspect={aspect:.3f}",
    ]

    # --- Classification rules ---

    # Rule 1: Diameter spans >=85% of part → EXTERNAL (OD or flange)
    if diameter_ratio >= 0.85:
        evidence_parts.append("RULE=DIAMETER_SPANS_PART→EXTERNAL")
        return CylinderOrientation.EXTERNAL_CYLINDER, " ".join(evidence_parts)

    # Rule 2: Short cylinder (aspect < 0.3) → transition ring, likely EXTERNAL step
    if aspect < 0.3 and aspect > 0:
        evidence_parts.append("RULE=SHORT_CYLINDER→EXTERNAL_TRANSITION")
        return CylinderOrientation.EXTERNAL_CYLINDER, " ".join(evidence_parts)

    # Rule 3: Face center is significantly offset from part center
    # (face is NOT concentric with the part → it's a hole somewhere in the part)
    if offset_ratio > 0.3 and diameter_ratio < 0.5:
        evidence_parts.append("RULE=OFFSET_AND_SMALL→INTERNAL")
        return CylinderOrientation.INTERNAL_CYLINDER, " ".join(evidence_parts)

    # Rule 4: Small diameter, NOT offset → concentric small bore (INTERNAL candidate)
    # Only when diameter is clearly smaller than part (< 60%)
    if diameter_ratio < 0.5 and offset_ratio <= 0.3:
        evidence_parts.append("RULE=SMALL_CONCENTRIC→INTERNAL_CANDIDATE")
        return CylinderOrientation.INTERNAL_CYLINDER, " ".join(evidence_parts)

    # Default: AMBIGUOUS — cannot determine without topology adjacency
    evidence_parts.append("RULE=AMBIGUOUS_CANNOT_DETERMINE")
    return CylinderOrientation.AMBIGUOUS_CYLINDER, " ".join(evidence_parts)


# ===========================================================================
# Oriented cylinder detection (Phase 5 replacement for Phase 3 hole candidates)
# ===========================================================================


def detect_oriented_cylinders(record: StepImportRecord) -> list[OrientedCylinderRecord]:
    """Detect and orient all cylindrical faces in a STEP B-Rep.

    Replaces Phase 3 detect_hole_candidates with orientation-aware classification.
    All results are CANDIDATE — no auto-confirmation.
    EXTERNAL_CYLINDER entries must NOT be treated as holes (MUST 7).

    HARD RULE: OD_AS_BORE_FALSE_POSITIVE_COUNT=0 for well-structured parts.
    """
    if record.status != "PASS":
        return []

    results: list[OrientedCylinderRecord] = []

    for face in record.faces:
        if face.surface_class != "CYLINDRICAL":
            continue

        axis, diameter_mm, depth_mm = compute_cylinder_params(face)

        if diameter_mm is None:
            continue
        if diameter_mm < _MIN_HOLE_DIAMETER_MM or diameter_mm > _MAX_HOLE_DIAMETER_MM:
            continue

        orientation, evidence = classify_cylinder_orientation(face, record)

        # Hole class: use depth relative to diameter
        n_boundary = len(face.boundary_curve_tags)
        if depth_mm is not None and diameter_mm > _FLAT_THRESHOLD:
            aspect = depth_mm / diameter_mm
        else:
            aspect = 0.0

        if aspect < 0.3 and aspect > 0:
            hole_class = "TRANSITION_RING"
        elif n_boundary >= 2:
            hole_class = "THROUGH_HOLE_CANDIDATE"
        else:
            hole_class = "BLIND_HOLE_CANDIDATE"

        results.append(OrientedCylinderRecord(
            face_tag=face.tag,
            feature_status="CANDIDATE",
            hole_class=hole_class,
            cylinder_orientation=orientation,
            diameter_mm=diameter_mm,
            axis_direction=axis,
            depth_mm=depth_mm,
            circular_boundary_count=n_boundary,
            bbox_min=face.bbox_min,
            bbox_max=face.bbox_max,
            orientation_evidence=evidence,
        ))

    return results


def filter_internal_cylinders(
    cylinders: list[OrientedCylinderRecord],
) -> list[OrientedCylinderRecord]:
    """Return only INTERNAL_CYLINDER entries (true hole/bore candidates).

    HARD RULE: EXTERNAL_CYLINDER and AMBIGUOUS_CYLINDER are excluded from
    holemaking feature candidates. Only INTERNAL_CYLINDER feeds the drill/bore path.
    """
    return [c for c in cylinders if c.cylinder_orientation == CylinderOrientation.INTERNAL_CYLINDER]


# ===========================================================================
# Pocket detection
# ===========================================================================


def _face_by_tag(faces: list[StepFaceSummary]) -> dict[int, StepFaceSummary]:
    return {f.tag: f for f in faces}


def _planar_normal_axis(face: StepFaceSummary) -> str | None:
    """Return 'X', 'Y', or 'Z' for the normal axis of a PLANAR face from bbox.

    For a PLANAR face, one bbox extent is essentially zero (the flat dimension).
    That flat dimension corresponds to the normal direction.
    Returns None if face is not axis-aligned planar.
    """
    dx = face.bbox_max[0] - face.bbox_min[0]
    dy = face.bbox_max[1] - face.bbox_min[1]
    dz = face.bbox_max[2] - face.bbox_min[2]
    _FLAT = _FLAT_THRESHOLD
    if dz < _FLAT:
        return "Z"
    if dy < _FLAT:
        return "Y"
    if dx < _FLAT:
        return "X"
    return None


def _face_center(face: StepFaceSummary) -> tuple[float, float, float]:
    return (
        (face.bbox_min[0] + face.bbox_max[0]) / 2.0,
        (face.bbox_min[1] + face.bbox_max[1]) / 2.0,
        (face.bbox_min[2] + face.bbox_max[2]) / 2.0,
    )


def detect_pocket_candidates(record: StepImportRecord) -> list[PocketCandidateRecord]:
    """Detect bounded pocket candidates from STEP B-Rep face topology.

    A pocket candidate requires:
      - A horizontal PLANAR floor face (Z-normal, dz ≈ 0)
      - The floor Z is BELOW the part's top surface (inside the part)
      - ≥ 2 adjacent wall faces (non-horizontal planar or UNKNOWN)
      - The floor is NOT on the bottom external surface of the part

    Does NOT recognize pocket from a single planar face (HARD RULE 12).
    Pocket class:
      RECTANGULAR_POCKET_CANDIDATE: ≥ 3 flat axis-aligned wall faces
      GENERAL_POCKET_CANDIDATE: mix of walls/curved faces
      AMBIGUOUS_POCKET: 2 adjacent wall faces only

    All results are CANDIDATE. Depth from part top Z - floor Z (bbox evidence).
    Width/length from floor bbox lateral extents.
    """
    if record.status != "PASS" or record.bbox_min is None or record.bbox_max is None:
        return []

    adj = build_face_adjacency(record.faces)
    face_map = _face_by_tag(record.faces)

    part_top_z = record.bbox_max[2]
    part_bot_z = record.bbox_min[2]
    _TOP_TOL = max((part_top_z - part_bot_z) * 0.05, 0.5)   # 5% of height

    candidates: list[PocketCandidateRecord] = []

    for face in record.faces:
        if face.surface_class != "PLANAR":
            continue
        if _planar_normal_axis(face) != "Z":
            continue

        fcx, fcy, fcz = _face_center(face)

        # Floor must be below the part top (not the top external surface)
        if fcz >= part_top_z - _TOP_TOL:
            continue

        # Floor must be above the part bottom (not the bottom external surface)
        if fcz <= part_bot_z + _TOP_TOL:
            continue

        # Collect adjacent wall faces
        adj_tags = adj.get(face.tag, frozenset())
        wall_tags: list[int] = []
        for atag in adj_tags:
            aface = face_map.get(atag)
            if aface is None:
                continue
            anorm_axis = _planar_normal_axis(aface)
            if anorm_axis in ("X", "Y"):
                wall_tags.append(atag)
            elif aface.surface_class == "UNKNOWN":
                wall_tags.append(atag)
            elif aface.surface_class == "CYLINDRICAL":
                wall_tags.append(atag)

        # Require ≥ 2 adjacent walls
        if len(wall_tags) < 2:
            continue

        # Classify pocket type
        flat_walls = [
            t for t in wall_tags
            if face_map[t].surface_class == "PLANAR"
            and _planar_normal_axis(face_map[t]) in ("X", "Y")
        ]
        if len(flat_walls) >= 3:
            pocket_class = "RECTANGULAR_POCKET_CANDIDATE"
        elif len(flat_walls) >= 1:
            pocket_class = "GENERAL_POCKET_CANDIDATE"
        else:
            pocket_class = "AMBIGUOUS_POCKET"

        # Pocket depth: part top Z - floor Z
        depth = round(part_top_z - fcz, 4)

        # Width and length from floor bbox lateral extents
        fdx = face.bbox_max[0] - face.bbox_min[0]
        fdy = face.bbox_max[1] - face.bbox_min[1]
        _lat_ok = fdx > _FLAT_THRESHOLD and fdy > _FLAT_THRESHOLD
        width_mm = round(min(fdx, fdy), 4) if _lat_ok else None
        length_mm = round(max(fdx, fdy), 4) if _lat_ok else None

        candidates.append(PocketCandidateRecord(
            floor_face_tag=face.tag,
            wall_face_tags=tuple(sorted(wall_tags)),
            pocket_class=pocket_class,
            feature_status="CANDIDATE",
            depth_mm=depth if depth > 0 else None,
            width_mm=width_mm,
            length_mm=length_mm,
            opening_z=round(part_top_z, 4),
            evidence=(
                f"floor_z={fcz:.2f} part_top_z={part_top_z:.2f} "
                f"adjacent_walls={len(wall_tags)} flat_walls={len(flat_walls)}"
            ),
        ))

    return candidates


# ===========================================================================
# Slot detection
# ===========================================================================


def detect_slot_candidates(record: StepImportRecord) -> list[SlotCandidateRecord]:
    """Detect bounded slot candidates from STEP B-Rep face topology.

    A slot candidate requires:
      - A planar floor face (normal in any axis — the slot can run along any direction)
      - Exactly 2 adjacent planar wall faces with PARALLEL normals (opposite sides of slot)
      - Width: distance between parallel walls (from their bbox positions)
      - Length: extent of the floor face along the slot direction
      - Open/closed ends determined by whether end faces are present

    Does NOT recognize slot from 2 parallel faces alone (HARD RULE 13).
    All results are CANDIDATE.
    """
    if record.status != "PASS":
        return []

    adj = build_face_adjacency(record.faces)
    face_map = _face_by_tag(record.faces)

    seen_floors: set[int] = set()
    candidates: list[SlotCandidateRecord] = []

    p_min = record.bbox_min
    p_max = record.bbox_max

    for face in record.faces:
        if face.surface_class != "PLANAR":
            continue
        if face.tag in seen_floors:
            continue

        floor_norm_axis = _planar_normal_axis(face)
        if floor_norm_axis is None:
            continue

        # Outer-surface filter: slot floor must be RECESSED from the part boundary.
        # A face AT the outer surface (outer wall/top/bottom) is NOT a slot floor.
        # Threshold: 3% of part extent in the floor-normal direction, min 0.5mm.
        if p_min is not None and p_max is not None:
            if floor_norm_axis == "Z":
                fc = (face.bbox_min[2] + face.bbox_max[2]) / 2.0
                dext = p_max[2] - p_min[2]
                _tol = max(dext * 0.03, 0.5)
                if fc >= p_max[2] - _tol or fc <= p_min[2] + _tol:
                    continue
            elif floor_norm_axis == "X":
                fc = (face.bbox_min[0] + face.bbox_max[0]) / 2.0
                dext = p_max[0] - p_min[0]
                _tol = max(dext * 0.03, 0.5)
                if fc >= p_max[0] - _tol or fc <= p_min[0] + _tol:
                    continue
            elif floor_norm_axis == "Y":
                fc = (face.bbox_min[1] + face.bbox_max[1]) / 2.0
                dext = p_max[1] - p_min[1]
                _tol = max(dext * 0.03, 0.5)
                if fc >= p_max[1] - _tol or fc <= p_min[1] + _tol:
                    continue

        # Find adjacent planar wall faces (normal perpendicular to floor normal)
        adj_tags = adj.get(face.tag, frozenset())
        planar_walls: list[StepFaceSummary] = []
        for atag in adj_tags:
            aface = face_map.get(atag)
            if aface is None or aface.surface_class != "PLANAR":
                continue
            anorm_axis = _planar_normal_axis(aface)
            if anorm_axis is None or anorm_axis == floor_norm_axis:
                continue
            planar_walls.append(aface)

        if len(planar_walls) < 2:
            continue

        # Look for exactly 2 walls with the SAME normal axis (parallel/antiparallel)
        axis_groups: dict[str, list[StepFaceSummary]] = {}
        for w in planar_walls:
            ax = _planar_normal_axis(w)
            if ax:
                axis_groups.setdefault(ax, []).append(w)

        pair_axis: str | None = None
        pair_walls: list[StepFaceSummary] = []
        for ax, ws in axis_groups.items():
            if len(ws) >= 2:
                pair_axis = ax
                pair_walls = ws[:2]
                break

        if pair_axis is None or len(pair_walls) < 2:
            continue

        seen_floors.add(face.tag)

        # Measure width (distance between parallel walls along their normal axis)
        w0, w1 = pair_walls
        if pair_axis == "X":
            c0 = (w0.bbox_min[0] + w0.bbox_max[0]) / 2.0
            c1 = (w1.bbox_min[0] + w1.bbox_max[0]) / 2.0
        elif pair_axis == "Y":
            c0 = (w0.bbox_min[1] + w0.bbox_max[1]) / 2.0
            c1 = (w1.bbox_min[1] + w1.bbox_max[1]) / 2.0
        else:
            c0 = (w0.bbox_min[2] + w0.bbox_max[2]) / 2.0
            c1 = (w1.bbox_min[2] + w1.bbox_max[2]) / 2.0
        width_mm = round(abs(c1 - c0), 4)

        # Depth: floor normal extent matches the floor's flat dimension's depth
        # = distance from floor to part surface
        if floor_norm_axis == "X":
            floor_pos = (face.bbox_min[0] + face.bbox_max[0]) / 2.0
            if record.bbox_max is not None:
                depth_mm = round(record.bbox_max[0] - floor_pos, 4)
            else:
                depth_mm = None
        elif floor_norm_axis == "Y":
            floor_pos = (face.bbox_min[1] + face.bbox_max[1]) / 2.0
            if record.bbox_max is not None:
                depth_mm = round(record.bbox_max[1] - abs(floor_pos), 4)
            else:
                depth_mm = None
        else:  # Z
            floor_pos = (face.bbox_min[2] + face.bbox_max[2]) / 2.0
            if record.bbox_max is not None:
                depth_mm = round(record.bbox_max[2] - floor_pos, 4)
            else:
                depth_mm = None

        # Slot runs along the axis perpendicular to both floor normal and wall normal
        all_axes = {"X", "Y", "Z"}
        slot_axis_set = all_axes - {floor_norm_axis, pair_axis}
        slot_axis = next(iter(slot_axis_set)) if len(slot_axis_set) == 1 else None

        # Length from floor bbox along slot axis
        if slot_axis == "X":
            length_mm = round(face.bbox_max[0] - face.bbox_min[0], 4)
        elif slot_axis == "Y":
            length_mm = round(face.bbox_max[1] - face.bbox_min[1], 4)
        elif slot_axis == "Z":
            length_mm = round(face.bbox_max[2] - face.bbox_min[2], 4)
        else:
            length_mm = None

        # Detect end faces (walls perpendicular to slot axis)
        end_face_tags: list[int] = []
        if slot_axis:
            for atag in adj_tags:
                aface = face_map.get(atag)
                if aface is None or aface.surface_class != "PLANAR":
                    continue
                anorm = _planar_normal_axis(aface)
                if anorm == slot_axis:
                    end_face_tags.append(atag)

        slot_class = (
            "CLOSED_SLOT_CANDIDATE" if len(end_face_tags) >= 2
            else "OPEN_SLOT_CANDIDATE" if len(end_face_tags) == 0
            else "AMBIGUOUS_SLOT"
        )

        candidates.append(SlotCandidateRecord(
            floor_face_tag=face.tag,
            side_wall_tags=(w0.tag, w1.tag),
            end_face_tags=tuple(sorted(end_face_tags)),
            slot_class=slot_class,
            feature_status="CANDIDATE",
            width_mm=width_mm if width_mm > _FLAT_THRESHOLD else None,
            depth_mm=depth_mm if (depth_mm and depth_mm > 0) else None,
            length_mm=length_mm if (length_mm and length_mm > _FLAT_THRESHOLD) else None,
            axis_direction=slot_axis,
            evidence=(
                f"floor_norm={floor_norm_axis} wall_norm={pair_axis} "
                f"slot_axis={slot_axis} end_faces={len(end_face_tags)}"
            ),
        ))

    return candidates


# ===========================================================================
# Step / shoulder detection
# ===========================================================================


def detect_step_shoulder_candidates(
    record: StepImportRecord,
) -> list[StepShoulderRecord]:
    """Detect step/shoulder candidates from face topology.

    A step shoulder is a horizontal PLANAR face (Z-normal) that:
      - Is adjacent to ≥2 non-planar faces (cylindrical/unknown on BOTH sides)
      - Is NOT a plain end cap (which has only 1 non-planar neighbor)

    This model covers machined shaft shoulders and boss steps where the step
    face sits between two cylindrical sections at different diameters.
    For faces adjacent to only 1 cylinder, they are end caps, not shoulders.

    The step height is estimated from the Z extent between the step face and
    the adjacent cylinder centers. All results are CANDIDATE.

    Only Z-axis steps are detected in Phase 5.
    """
    if record.status != "PASS":
        return []

    adj = build_face_adjacency(record.faces)
    face_map = _face_by_tag(record.faces)

    candidates: list[StepShoulderRecord] = []

    for face in record.faces:
        if face.surface_class != "PLANAR" or _planar_normal_axis(face) != "Z":
            continue

        face_z = (face.bbox_min[2] + face.bbox_max[2]) / 2.0
        adj_tags = adj.get(face.tag, frozenset())

        # Count non-planar neighbors (cylinders / unknown shaft sections)
        non_planar_nbrs = [
            face_map[t] for t in adj_tags
            if t in face_map
            and face_map[t].surface_class in ("CYLINDRICAL", "UNKNOWN")
        ]
        # Require ≥2 non-planar neighbors: face is BETWEEN two shaft sections
        if len(non_planar_nbrs) < 2:
            continue

        # Pick the two non-planar neighbors as "lower" and "upper" wall faces
        nbr_z = [(f.tag, (f.bbox_min[2] + f.bbox_max[2]) / 2.0) for f in non_planar_nbrs]
        nbr_z.sort(key=lambda x: x[1])
        lower_wall_tag = nbr_z[0][0]
        upper_wall_tag = nbr_z[-1][0]

        # Step height: separation between the adjacent cylinder Z-centers
        lower_z = nbr_z[0][1]
        upper_z = nbr_z[-1][1]
        step_h = round(abs(upper_z - lower_z), 4) if abs(upper_z - lower_z) > 0.1 else None

        # Use the lower wall as the representative wall_face_tag
        wall_tag = lower_wall_tag

        candidates.append(StepShoulderRecord(
            lower_face_tag=face.tag,
            upper_face_tag=upper_wall_tag,
            wall_face_tag=wall_tag,
            step_height_mm=step_h,
            feature_status="CANDIDATE",
            evidence=(
                f"step_face={face.tag} face_z={face_z:.2f} "
                f"lower_wall={lower_wall_tag}(z={lower_z:.1f}) "
                f"upper_wall={upper_wall_tag}(z={upper_z:.1f}) "
                f"non_planar_nbrs={len(non_planar_nbrs)}"
            ),
        ))

    return candidates


# ===========================================================================
# Gouge comparator (NOT_IMPLEMENTED — Phase 6F)
# ===========================================================================


def build_gouge_comparator_result(record: StepImportRecord) -> GougeComparatorResult:
    """Build a gouge comparator result.

    GOUGE_COMPARATOR_IMPLEMENTED=False.
    All results are NOT_VERIFIABLE pending voxel simulation infrastructure.

    Required for future implementation (Phase 6F):
      - Voxel simulation engine (stock removal simulation)
      - Coordinate system alignment between STEP target and voxel model
      - Tolerance data from engineering drawing annotation

    HARD RULE: Never return gouge_validated=PASS without all conditions met:
      - target geometry available
      - voxel simulation ran
      - coordinate systems aligned
      - comparison executed
      - result within explicitly defined verification scope
    """
    has_target = record.status == "PASS" and record.bbox_min is not None

    return GougeComparatorResult(
        source_path=record.source_path,
        result="NOT_VERIFIABLE",
        comparator_implemented=False,
        step_target_available=has_target,
        voxel_result_available=False,
        coordinate_alignment="NOT_VERIFIED",
        voxel_size_mm=None,
        comparison_method="NOT_IMPLEMENTED",
        estimated_geometric_error_bound=None,
        notes=(
            "Phase 5: STEP target geometry available but voxel simulation not implemented. "
            "Voxel-to-B-Rep comparator deferred to Phase 6F. "
            "GOUGE_VALIDATED=NOT_VERIFIABLE until: voxel engine runs, "
            "coordinate alignment verified, comparison executed."
        ),
    )
