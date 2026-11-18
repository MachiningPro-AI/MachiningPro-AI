"""
Phase 7A: Canonical WCS model with provenance tracking.

HARD RULES (never bypassed):
  - Bounding-box-derived WCS is always SUGGESTED, never USER_CONFIRMED.
  - SUGGESTED_WCS may not be used to dispatch NC. is_dispatchable=False always.
  - Required transition: SUGGESTED → USER_CONFIRMED (explicit, never automatic).
  - WCS validity checks: right-handed, orthogonal, finite values, valid transform.
  - MUST NOT fabricate WCS, datum, stock, or fixture geometry.

MUST 25: canonical WCS model with provenance.
MUST 26: derive SUGGESTED_WCS from STEP bbox (TOP_CENTER) only.
MUST 27: validate WCS before use in toolpath generation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from backend.cam_planning.enums import WCSCandidateType
from backend.step_brep.gmsh_step_parser import StepImportRecord

__all__ = [
    "WCSProvenance",
    "WorkCoordinateSystem",
    "suggest_wcs_top_center",
    "validate_wcs",
    "wcs_ref_string",
    "WCS_SAFETY_IS_DISPATCHABLE",
    "WCS_SAFETY_PRODUCTION_RELEASED",
    "WCS_SAFETY_REVIEW_REQUIRED",
]

# Safety invariants — never modified
WCS_SAFETY_IS_DISPATCHABLE: bool = False
WCS_SAFETY_PRODUCTION_RELEASED: bool = False
WCS_SAFETY_REVIEW_REQUIRED: bool = True

_ORTHOGONALITY_TOLERANCE: float = 1e-9
_UNIT_VECTOR_TOLERANCE: float = 1e-9
_CLEARANCE_ABOVE_PART_MM: float = 10.0


class WCSProvenance(StrEnum):
    """Provenance level for a WorkCoordinateSystem.

    Only USER_CONFIRMED may be used for production.
    SUGGESTED is the maximum provenance for bbox-derived WCS.
    """

    FILE_EVIDENCE = "FILE_EVIDENCE"
    SETUP_DEFINITION = "SETUP_DEFINITION"
    USER_CONFIRMED = "USER_CONFIRMED"
    SUGGESTED = "SUGGESTED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class WorkCoordinateSystem:
    """Canonical WCS representation for Phase 7+.

    All geometry is in millimetres (world-frame). The axes define a
    machine-frame orientation: Z_axis points *from* the part *toward* the
    spindle (i.e. the tool approach direction is -Z_axis).

    Fields
    ------
    wcs_id          Session-local identifier.
    origin_mm       WCS origin in world-frame mm.
    x_axis          Unit vector for the X axis.
    y_axis          Unit vector for the Y axis.
    z_axis          Unit vector for the Z axis (tool approach direction reversed).
    provenance      How this WCS was established.
    candidate_type  Geometric category of the candidate origin location.
    is_right_handed True when det([x,y,z])>0.
    is_orthogonal   True when all dot-products ≈ 0.
    is_valid        True when right-handed AND orthogonal AND all values finite.
    source_path     STEP file this WCS was derived from.
    clearance_z_mm  Recommended safe retract height in world-frame Z (mm).
    notes           Human-readable explanation of provenance choice.
    """

    wcs_id: str
    origin_mm: tuple[float, float, float]
    x_axis: tuple[float, float, float]
    y_axis: tuple[float, float, float]
    z_axis: tuple[float, float, float]
    provenance: WCSProvenance
    candidate_type: WCSCandidateType
    is_right_handed: bool
    is_orthogonal: bool
    is_valid: bool
    source_path: str
    clearance_z_mm: float | None
    notes: str


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(
    a: tuple[float, float, float], b: tuple[float, float, float]
) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _norm(v: tuple[float, float, float]) -> float:
    return math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)


def _unit(v: tuple[float, float, float]) -> tuple[float, float, float]:
    n = _norm(v)
    if n < 1e-15:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


def validate_wcs(wcs: WorkCoordinateSystem) -> bool:
    """Return True when WCS axes are right-handed, orthogonal, and finite.

    Does NOT modify the WCS — validation is read-only.
    """
    ax, ay, az = wcs.x_axis, wcs.y_axis, wcs.z_axis
    for v in (ax, ay, az):
        if any(not math.isfinite(c) for c in v):
            return False
    if any(not math.isfinite(c) for c in wcs.origin_mm):
        return False
    # Orthogonality
    if abs(_dot(ax, ay)) > _ORTHOGONALITY_TOLERANCE:
        return False
    if abs(_dot(ay, az)) > _ORTHOGONALITY_TOLERANCE:
        return False
    if abs(_dot(ax, az)) > _ORTHOGONALITY_TOLERANCE:
        return False
    # Right-handedness: x × y should equal z
    xc = _cross(ax, ay)
    det = _dot(xc, az)
    if det <= 0:
        return False
    return True


def _build_wcs(
    *,
    wcs_id: str,
    origin: tuple[float, float, float],
    x_axis: tuple[float, float, float],
    y_axis: tuple[float, float, float],
    z_axis: tuple[float, float, float],
    provenance: WCSProvenance,
    candidate_type: WCSCandidateType,
    source_path: str,
    clearance_z: float | None,
    notes: str,
) -> WorkCoordinateSystem:
    all_finite = all(math.isfinite(c) for c in (*origin, *x_axis, *y_axis, *z_axis))
    if not all_finite:
        return WorkCoordinateSystem(
            wcs_id=wcs_id,
            origin_mm=origin,
            x_axis=x_axis,
            y_axis=y_axis,
            z_axis=z_axis,
            provenance=provenance,
            candidate_type=candidate_type,
            is_right_handed=False,
            is_orthogonal=False,
            is_valid=False,
            source_path=source_path,
            clearance_z_mm=clearance_z,
            notes=notes + " [INVALID: non-finite values]",
        )
    xy_dot = abs(_dot(x_axis, y_axis))
    yz_dot = abs(_dot(y_axis, z_axis))
    xz_dot = abs(_dot(x_axis, z_axis))
    is_orthogonal = (
        xy_dot <= _ORTHOGONALITY_TOLERANCE
        and yz_dot <= _ORTHOGONALITY_TOLERANCE
        and xz_dot <= _ORTHOGONALITY_TOLERANCE
    )
    xc = _cross(x_axis, y_axis)
    is_right_handed = _dot(xc, z_axis) > 0
    is_valid = is_orthogonal and is_right_handed
    return WorkCoordinateSystem(
        wcs_id=wcs_id,
        origin_mm=origin,
        x_axis=x_axis,
        y_axis=y_axis,
        z_axis=z_axis,
        provenance=provenance,
        candidate_type=candidate_type,
        is_right_handed=is_right_handed,
        is_orthogonal=is_orthogonal,
        is_valid=is_valid,
        source_path=source_path,
        clearance_z_mm=clearance_z,
        notes=notes,
    )


def suggest_wcs_top_center(record: StepImportRecord) -> WorkCoordinateSystem:
    """Derive a SUGGESTED WCS from the STEP bounding box TOP_CENTER.

    Origin = geometric center of the top (maximum Z) face.
    X = world +X, Y = world +Y, Z = world +Z.
    Tool approaches from above in the -Z direction (Z points toward spindle).

    HARD RULE: This WCS is always SUGGESTED, never USER_CONFIRMED.
    Bbox-derived WCS may only be SUGGESTED. Requires explicit
    SUGGESTED → USER_CONFIRMED transition before production use.
    is_dispatchable is always False.
    """
    xmin, ymin, zmin = record.bbox_min
    xmax, ymax, zmax = record.bbox_max
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    origin = (cx, cy, zmax)
    # Standard orientation: X right, Y forward, Z up (right-handed)
    x_axis = (1.0, 0.0, 0.0)
    y_axis = (0.0, 1.0, 0.0)
    z_axis = (0.0, 0.0, 1.0)
    clearance_z = zmax + _CLEARANCE_ABOVE_PART_MM
    sha_prefix = record.sha256[:8] if record.sha256 else "unknown"
    return _build_wcs(
        wcs_id=f"SUGGESTED_WCS_TOP_CENTER_{sha_prefix}",
        origin=origin,
        x_axis=x_axis,
        y_axis=y_axis,
        z_axis=z_axis,
        provenance=WCSProvenance.SUGGESTED,
        candidate_type=WCSCandidateType.TOP_CENTER,
        source_path=str(record.source_path or ""),
        clearance_z=clearance_z,
        notes=(
            "SUGGESTED_WCS derived from STEP bounding box TOP_CENTER. "
            "Never auto-confirmed. Requires explicit USER_CONFIRMED transition "
            "before production or dispatch use. is_dispatchable=False."
        ),
    )


def wcs_ref_string(wcs: WorkCoordinateSystem) -> str:
    """Return a canonical wcs_ref string for use in toolpath inputs.

    Format: '<PROVENANCE>:WCS:<wcs_id>'
    Example: 'SUGGESTED:WCS:SUGGESTED_WCS_TOP_CENTER_abc12345'
    """
    return f"{wcs.provenance.value}:WCS:{wcs.wcs_id}"
