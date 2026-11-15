"""
Clearance height policy for manufacturing toolpath generation (P6-A).

Uses the existing ClearancePlane / ClearanceSource from backend.toolpath —
no duplicate semantics are created.

Priority order:
  1. Explicit CAD/setup evidence  → ClearanceSource.FIXTURE_CONFIGURATION
  2. Engineer-confirmed setup value → ClearanceSource.USER_DEFINED
  3. Approved proposed value        → ClearanceSource.USER_SUPPLIED (requires confirmation)

HARD RULES:
  - TOOLPATH_READY=NO with CLEARANCE_Z_REQUIRED when clearance is unknown.
  - WCS must be named before clearance can be validated.
  - Clearance must be finite, positive relative to feature top.
  - FIXTURE_COLLISION_VALIDATED=NO always (no fixture geometry available).
  - HOLDER_COLLISION_VALIDATED=NO always (no holder geometry available).
  - STOCK_REMOVAL_VALIDATED=NO always (no stock simulation available).
  - Never fabricate or assume a default clearance height.

TOOLPATH_ENGINE_FOUND=YES  (backend.toolpath.generators.generate_drill_toolpath)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import StrEnum

from backend.toolpath.enums import ClearanceSource
from backend.toolpath.models import ClearancePlane

__all__ = [
    "ClearanceEvaluationStatus",
    "ClearanceEvaluationResult",
    "evaluate_clearance",
]


class ClearanceEvaluationStatus(StrEnum):
    TOOLPATH_READY = "TOOLPATH_READY"
    WCS_UNKNOWN = "WCS_UNKNOWN"
    CLEARANCE_Z_REQUIRED = "CLEARANCE_Z_REQUIRED"
    INVALID_CLEARANCE = "INVALID_CLEARANCE"
    CLEARANCE_BELOW_STOCK = "CLEARANCE_BELOW_STOCK"
    CLEARANCE_BELOW_MACHINING_REGION = "CLEARANCE_BELOW_MACHINING_REGION"


@dataclass(frozen=True)
class ClearanceEvaluationResult:
    """Result of evaluating whether clearance Z is valid for toolpath generation.

    toolpath_ready=True only when:
    - wcs_ref is defined
    - clearance_z is a finite number from a known source
    - clearance_z is above the machining region (feature_top_z)
    - clearance_z is above stock_top_z (when known)

    Collision safety is NEVER claimed:
    - FIXTURE_COLLISION_VALIDATED=NO
    - HOLDER_COLLISION_VALIDATED=NO
    - STOCK_REMOVAL_VALIDATED=NO
    """

    toolpath_ready: bool
    status: ClearanceEvaluationStatus
    clearance_plane: ClearancePlane
    blocker: str | None
    validation_notes: list[str] = field(default_factory=list)

    # Collision / simulation state — always NOT validated
    fixture_collision_validated: bool = False
    holder_collision_validated: bool = False
    stock_removal_validated: bool = False


def evaluate_clearance(
    *,
    clearance_z: float | None,
    clearance_source: ClearanceSource,
    stock_top_z: float | None,
    feature_top_z: float,
    wcs_ref: str | None,
) -> ClearanceEvaluationResult:
    """Evaluate the clearance Z height for toolpath generation.

    Parameters
    ----------
    clearance_z:
        The proposed retract / safe-Z value in WCS coordinates. None means unknown.
    clearance_source:
        Traceability source for the clearance value.
    stock_top_z:
        Top surface of the stock in WCS coordinates. None if unknown.
    feature_top_z:
        Z coordinate of the feature's entry surface (hole top). Used as lower bound.
    wcs_ref:
        Named WCS reference. Must be defined before clearance can be validated.

    Returns
    -------
    ClearanceEvaluationResult with toolpath_ready=True only when all checks pass.
    """
    _base_notes = [
        "FIXTURE_COLLISION_VALIDATED=NO: fixture geometry not available",
        "HOLDER_COLLISION_VALIDATED=NO: holder geometry not available",
        "STOCK_REMOVAL_VALIDATED=NO: stock simulation not performed",
    ]

    if wcs_ref is None:
        return ClearanceEvaluationResult(
            toolpath_ready=False,
            status=ClearanceEvaluationStatus.WCS_UNKNOWN,
            clearance_plane=ClearancePlane(value_mm=None, source=ClearanceSource.UNKNOWN),
            blocker="WCS_UNKNOWN: wcs_ref must be defined before clearance can be evaluated",
            validation_notes=[
                "WCS reference is not set — engineer must define the WCS for this setup",
            ],
        )

    if clearance_z is None or clearance_source == ClearanceSource.UNKNOWN:
        return ClearanceEvaluationResult(
            toolpath_ready=False,
            status=ClearanceEvaluationStatus.CLEARANCE_Z_REQUIRED,
            clearance_plane=ClearancePlane(value_mm=None, source=ClearanceSource.UNKNOWN),
            blocker="CLEARANCE_Z_REQUIRED: safe Z retract height not supplied",
            validation_notes=[
                "Clearance Z is not set.",
                "Engineer must supply via confirmed setup value (ClearanceSource.USER_DEFINED) "
                "or explicit override (ClearanceSource.USER_SUPPLIED).",
            ],
        )

    if not math.isfinite(clearance_z):
        return ClearanceEvaluationResult(
            toolpath_ready=False,
            status=ClearanceEvaluationStatus.INVALID_CLEARANCE,
            clearance_plane=ClearancePlane(value_mm=None, source=clearance_source),
            blocker=f"INVALID_CLEARANCE: clearance_z={clearance_z!r} is not a finite number",
            validation_notes=[f"clearance_z={clearance_z!r} is not finite"],
        )

    notes: list[str] = []

    if stock_top_z is not None and clearance_z < stock_top_z:
        return ClearanceEvaluationResult(
            toolpath_ready=False,
            status=ClearanceEvaluationStatus.CLEARANCE_BELOW_STOCK,
            clearance_plane=ClearancePlane(value_mm=clearance_z, source=clearance_source),
            blocker=(
                f"CLEARANCE_BELOW_STOCK: clearance_z={clearance_z:.4f} "
                f"is below stock_top_z={stock_top_z:.4f}"
            ),
            validation_notes=[
                f"Clearance ({clearance_z:.4f}) must be above stock top ({stock_top_z:.4f})"
            ],
        )

    if clearance_z <= feature_top_z:
        return ClearanceEvaluationResult(
            toolpath_ready=False,
            status=ClearanceEvaluationStatus.CLEARANCE_BELOW_MACHINING_REGION,
            clearance_plane=ClearancePlane(value_mm=clearance_z, source=clearance_source),
            blocker=(
                f"CLEARANCE_BELOW_MACHINING_REGION: clearance_z={clearance_z:.4f} "
                f"is below feature_top_z={feature_top_z:.4f}"
            ),
            validation_notes=[
                f"Clearance ({clearance_z:.4f}) must be above feature top Z ({feature_top_z:.4f})"
            ],
        )

    notes.extend(_base_notes)
    clearance_plane = ClearancePlane(
        value_mm=clearance_z,
        source=clearance_source,
        notes="; ".join(notes),
    )

    return ClearanceEvaluationResult(
        toolpath_ready=True,
        status=ClearanceEvaluationStatus.TOOLPATH_READY,
        clearance_plane=clearance_plane,
        blocker=None,
        validation_notes=notes,
    )
