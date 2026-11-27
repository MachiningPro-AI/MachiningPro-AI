"""
Phase O — Material Removal Per Operation
Phase P — Material Removal Rate

For each CAM operation:
  OPERATION_ID, TOOL_ID, INITIAL_VOLUME, REMOVED_VOLUME, REMAINING_VOLUME,
  REMOVAL_PERCENT, METHOD, FIDELITY, PROVENANCE

MRR = REMOVED_VOLUME / CUTTING_TIME (never derived from fabricated values)

Fail-closed contract:
  Missing volume or time → NOT_AVAILABLE
  No fabricated MRR values
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class OperationRemovalResult:
    operation_id: str = ""
    tool_id: str = ""
    initial_volume_mm3: float | None = None
    removed_volume_mm3: float | None = None
    remaining_volume_mm3: float | None = None
    removal_percent: float | None = None
    method: str = "NOT_AVAILABLE"
    fidelity: str = "NOT_AVAILABLE"
    provenance: str = "CATALOG_PARAMETRIC"
    status: str = "NOT_AVAILABLE"
    warnings: list[str] = field(default_factory=list)


@dataclass
class MRRResult:
    operation_id: str = ""
    tool_id: str = ""
    mrr_mm3_per_min: float | None = None
    mrr_unit: str = "mm³/min"
    mrr_method: str = "NOT_AVAILABLE"
    mrr_provenance: str = "NOT_AVAILABLE"
    mrr_status: str = "NOT_AVAILABLE"
    removed_volume_mm3: float | None = None
    cutting_time_min: float | None = None
    warnings: list[str] = field(default_factory=list)


def compute_operation_removal(
    operation_id: str,
    tool_id: str,
    initial_volume_mm3: float | None,
    remaining_volume_after_mm3: float | None,
    volume_method: str,
    volume_fidelity: str,
    provenance: str = "CATALOG_PARAMETRIC",
) -> OperationRemovalResult:
    """Compute per-operation material removal from before/after volumes.

    Both volumes must come from the same method (BREP_EXACT or VOXEL_APPROXIMATE).
    Never mix fidelity levels without disclosure.
    """
    r = OperationRemovalResult(
        operation_id=operation_id,
        tool_id=tool_id,
        initial_volume_mm3=initial_volume_mm3,
        remaining_volume_mm3=remaining_volume_after_mm3,
        method=volume_method,
        fidelity=volume_fidelity,
        provenance=provenance,
    )

    if initial_volume_mm3 is None:
        r.status = "NOT_AVAILABLE"
        r.warnings.append("initial_volume_mm3 not provided")
        return r

    if remaining_volume_after_mm3 is None:
        r.status = "NOT_AVAILABLE"
        r.warnings.append("remaining_volume_mm3 not provided")
        return r

    removed = initial_volume_mm3 - remaining_volume_after_mm3
    r.removed_volume_mm3 = max(0.0, removed)  # clamp negative (rounding)
    if removed < -1e-3:
        r.warnings.append(
            f"remaining ({remaining_volume_after_mm3:.3f}) > initial ({initial_volume_mm3:.3f}); "
            "possible volume measurement inconsistency"
        )

    if initial_volume_mm3 > 0:
        r.removal_percent = 100.0 * r.removed_volume_mm3 / initial_volume_mm3
    else:
        r.removal_percent = 0.0

    r.status = "COMPUTED"
    return r


def compute_mrr(
    operation_id: str,
    tool_id: str,
    removed_volume_mm3: float | None,
    cutting_time_min: float | None,
    volume_fidelity: str,
    provenance: str = "CATALOG_PARAMETRIC",
) -> MRRResult:
    """MRR = removed_volume_mm3 / cutting_time_min.

    Never derives MRR from fabricated values.
    Both inputs must be legitimately measured.
    """
    r = MRRResult(
        operation_id=operation_id,
        tool_id=tool_id,
        removed_volume_mm3=removed_volume_mm3,
        cutting_time_min=cutting_time_min,
        mrr_unit="mm³/min",
        mrr_provenance=provenance,
    )

    if removed_volume_mm3 is None:
        r.mrr_status = "NOT_AVAILABLE"
        r.mrr_method = "NOT_AVAILABLE"
        r.warnings.append("removed_volume_mm3 not available")
        return r

    if cutting_time_min is None:
        r.mrr_status = "NOT_AVAILABLE"
        r.mrr_method = "NOT_AVAILABLE"
        r.warnings.append("cutting_time_min not available; MRR cannot be computed")
        return r

    if cutting_time_min <= 0:
        r.mrr_status = "NOT_AVAILABLE"
        r.mrr_method = "NOT_AVAILABLE"
        r.warnings.append(f"cutting_time_min={cutting_time_min} ≤ 0; MRR undefined")
        return r

    r.mrr_mm3_per_min = removed_volume_mm3 / cutting_time_min
    r.mrr_method = f"REMOVED_VOLUME_/{volume_fidelity}_OVER_CUTTING_TIME"
    r.mrr_status = "COMPUTED"
    return r
