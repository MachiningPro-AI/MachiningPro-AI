"""
Tool candidate selection for manufacturing features.

Evaluates the cutting tool catalog to find candidate tools for a confirmed
feature.  Selection is based on actual catalog records; no diameter guessing
that violates geometry is performed.

Tool match results:
  EXACT        -- tool cutting_diameter_mm == feature diameter_mm (within 0.005 mm)
  COMPATIBLE   -- tool can physically cut the feature but creates a different
                  final size (e.g. 5.0 mm drill on 4.891 mm feature); engineer
                  must verify fit tolerance
  NO_MATCH     -- no tool in the catalog covers this feature
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.cutting_tools.cutting_parameters import (
    CuttingDataReadiness,
    OperationCuttingData,
    get_cutting_data,
)
from backend.cutting_tools.seed_catalog import CuttingToolCatalogRecord, get_catalog


class ToolMatchStatus(StrEnum):
    EXACT = "EXACT"
    COMPATIBLE = "COMPATIBLE"
    NO_MATCH = "NO_MATCH"


_EXACT_TOLERANCE_MM = 0.005
_MAX_OVERSIZE_MM = 0.3


@dataclass
class ToolCandidate:
    tool: CuttingToolCatalogRecord
    match_status: ToolMatchStatus
    diameter_delta_mm: float
    cutting_data: OperationCuttingData | None
    cutting_data_ready: bool
    rejection_reason: str | None
    notes: str


@dataclass
class ToolSelectionResult:
    feature_diameter_mm: float
    feature_operation: str
    material_grade: str | None
    candidates: list[ToolCandidate]
    best_match: ToolCandidate | None
    tool_selection_ready: bool
    cutting_data_ready: bool
    machine_max_rpm: float | None


def _operation_for_route_type(route_type: str) -> str:
    mapping = {
        "drilling": "drilling",
        "reaming": "reaming",
        "boring": "boring",
        "turning": "turning",
        "milling": "milling",
        "grinding": "grinding",
    }
    lower = route_type.lower()
    for key, val in mapping.items():
        if key in lower:
            return val
    return lower


def select_tools(
    *,
    feature_diameter_mm: float,
    operation: str = "drilling",
    iso_material_groups: list[str] | None = None,
    material_grade: str | None = None,
    required_cutting_length_mm: float | None = None,
    machine_max_rpm: float | None = None,
) -> ToolSelectionResult:
    """Select tool candidates for a feature.

    Args:
        feature_diameter_mm: Confirmed feature hole/bore diameter in mm.
        operation: Machining operation (drilling, reaming, boring).
        iso_material_groups: ISO material group codes (P, M, K, N, S, H) the
            tool must be compatible with.  None = no material filter.
        material_grade: Material grade string for cutting data lookup.
        required_cutting_length_mm: Minimum cutting length needed.
        machine_max_rpm: Machine spindle limit for cutting data check.

    Returns:
        ToolSelectionResult with candidates ranked by match quality.
    """
    catalog = get_catalog()
    candidates: list[ToolCandidate] = []

    for tool in catalog:
        if operation not in [op.lower() for op in tool.supported_operations]:
            continue

        if iso_material_groups:
            if not any(g in (tool.iso_material_groups or []) for g in iso_material_groups):
                candidates.append(ToolCandidate(
                    tool=tool,
                    match_status=ToolMatchStatus.NO_MATCH,
                    diameter_delta_mm=0.0,
                    cutting_data=None,
                    cutting_data_ready=False,
                    rejection_reason="MATERIAL_INCOMPATIBLE",
                    notes=f"Tool does not support ISO group(s) {iso_material_groups}",
                ))
                continue

        tool_diam = tool.cutting_diameter_mm
        if tool_diam is None:
            continue

        delta = tool_diam - feature_diameter_mm

        if abs(delta) <= _EXACT_TOLERANCE_MM:
            match = ToolMatchStatus.EXACT
            rejection = None
            note = f"Exact diameter match: {tool_diam} mm"
        elif 0 < delta <= _MAX_OVERSIZE_MM:
            match = ToolMatchStatus.COMPATIBLE
            rejection = None
            note = (
                f"Tool diameter {tool_diam} mm is {delta:.3f} mm larger than "
                f"feature {feature_diameter_mm} mm — creates oversized hole; "
                f"engineer must verify fit tolerance."
            )
        else:
            if delta < 0:
                rejection_reason = "TOOL_TOO_SMALL"
                note = f"Tool {tool_diam} mm < feature {feature_diameter_mm} mm"
            else:
                rejection_reason = "TOOL_TOO_LARGE"
                note = (
                    f"Tool {tool_diam} mm is {delta:.3f} mm oversized "
                    f"(limit {_MAX_OVERSIZE_MM} mm)"
                )
            candidates.append(ToolCandidate(
                tool=tool,
                match_status=ToolMatchStatus.NO_MATCH,
                diameter_delta_mm=delta,
                cutting_data=None,
                cutting_data_ready=False,
                rejection_reason=rejection_reason,
                notes=note,
            ))
            continue

        if required_cutting_length_mm is not None:
            cl = tool.cutting_length_mm
            if cl is not None and cl < required_cutting_length_mm:
                candidates.append(ToolCandidate(
                    tool=tool,
                    match_status=ToolMatchStatus.NO_MATCH,
                    diameter_delta_mm=delta,
                    cutting_data=None,
                    cutting_data_ready=False,
                    rejection_reason="CUTTING_LENGTH_INSUFFICIENT",
                    notes=f"Tool cutting length {cl} mm < required {required_cutting_length_mm} mm",
                ))
                continue

        cutting_data: OperationCuttingData | None = None
        cutting_ready = False
        if material_grade and operation == "drilling":
            cutting_data = get_cutting_data(
                tool_family=tool.product_family or "",
                material_grade=material_grade,
                diameter_mm=tool_diam,
                operation=operation,
                machine_max_rpm=machine_max_rpm,
            )
            cutting_ready = cutting_data.readiness == CuttingDataReadiness.READY

        candidates.append(ToolCandidate(
            tool=tool,
            match_status=match,
            diameter_delta_mm=delta,
            cutting_data=cutting_data,
            cutting_data_ready=cutting_ready,
            rejection_reason=rejection,
            notes=note,
        ))

    viable = [c for c in candidates if c.match_status != ToolMatchStatus.NO_MATCH]
    viable.sort(key=lambda c: (
        0 if c.match_status == ToolMatchStatus.EXACT else 1,
        abs(c.diameter_delta_mm),
        0 if c.cutting_data_ready else 1,
    ))

    best = viable[0] if viable else None
    tool_ready = best is not None
    cutting_ready = any(c.cutting_data_ready for c in viable)

    return ToolSelectionResult(
        feature_diameter_mm=feature_diameter_mm,
        feature_operation=operation,
        material_grade=material_grade,
        candidates=viable,
        best_match=best,
        tool_selection_ready=tool_ready,
        cutting_data_ready=cutting_ready,
        machine_max_rpm=machine_max_rpm,
    )
