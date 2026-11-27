"""
Tool Assembly Geometry Operations (Phase K)

Computes canonical assembly geometry from cutter + holder + stickout.

TOOL_ASSEMBLY_READY gate: requires tool_id, holder_id, and tool_stickout_mm.

Reuses existing persistence architecture (ToolAssemblyRecord, ToolAssemblyGeometry)
from assembly_models.py — no duplicate persistence engine created.

ASSEMBLY_GEOMETRY_FIDELITY ∈ {PARAMETRIC_BREP, SIMPLIFIED, PARTIAL, NOT_AVAILABLE}

Fidelity is the MINIMUM of tool_geometry_fidelity and holder_geometry_fidelity.
A PASS or PARTIAL assembly with NOT_AVAILABLE tool geometry → NOT_AVAILABLE fidelity.

FABRICATED_GEOMETRY=NO — missing dims reported as NOT_AVAILABLE.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

_FIDELITY_RANK = {
    "PARAMETRIC_BREP": 4,
    "CATALOG_BREP": 4,
    "PARTIAL": 3,
    "SIMPLIFIED": 2,
    "NOT_AVAILABLE": 0,
}


@dataclass
class AssemblyGeometryResult:
    """Computed geometry for a cutter + holder + stickout assembly.

    TOOL_ASSEMBLY_READY=YES when tool_id, holder_id and tool_stickout are set
    and at least gauge_length is known.
    """

    tool_id: str = ""
    holder_id: str = ""

    # Input dimensions
    tool_stickout_mm: float | None = None
    gauge_length_mm: float | None = None   # from holder

    # Computed assembly dimensions
    assembly_length_mm: float | None = None          # gauge_length + stickout
    assembly_max_diameter_mm: float | None = None    # max of tool cutter diam / holder body diam
    effective_reach_mm: float | None = None          # stickout (how far tool protrudes)

    # Fidelity
    assembly_geometry_fidelity: str = "NOT_AVAILABLE"
    tool_geometry_fidelity: str = "NOT_AVAILABLE"
    holder_geometry_fidelity: str = "NOT_AVAILABLE"

    # Gate
    tool_assembly_ready: bool = False
    missing_requirements: list[str] = field(default_factory=list)

    provenance: str = "CATALOG_PARAMETRIC"
    warnings: list[str] = field(default_factory=list)


def compute_assembly_geometry(
    tool_id: str,
    holder_id: str,
    tool_stickout_mm: float | None,
    gauge_length_mm: float | None,
    tool_cutting_diameter_mm: float | None,
    holder_body_diameter_mm: float | None,
    tool_geometry_fidelity: str = "NOT_AVAILABLE",
    holder_geometry_fidelity: str = "NOT_AVAILABLE",
) -> AssemblyGeometryResult:
    """Compute assembly geometry from components.

    Does NOT fabricate any dimensions. Reports missing values explicitly.
    TOOL_ASSEMBLY_READY=YES only when tool_id, holder_id, and stickout are all present.
    """
    result = AssemblyGeometryResult(
        tool_id=tool_id,
        holder_id=holder_id,
        tool_stickout_mm=tool_stickout_mm,
        gauge_length_mm=gauge_length_mm,
        tool_geometry_fidelity=tool_geometry_fidelity,
        holder_geometry_fidelity=holder_geometry_fidelity,
    )

    # Check gate requirements
    missing = []
    if not tool_id:
        missing.append("tool_id")
    if not holder_id:
        missing.append("holder_id")
    if tool_stickout_mm is None:
        missing.append("tool_stickout_mm")

    result.missing_requirements = missing
    if missing:
        result.tool_assembly_ready = False
        result.assembly_geometry_fidelity = "NOT_AVAILABLE"
        return result

    result.effective_reach_mm = tool_stickout_mm

    # Assembly length = gauge_length + stickout
    if gauge_length_mm is not None:
        result.assembly_length_mm = gauge_length_mm + tool_stickout_mm
    else:
        result.warnings.append(
            "gauge_length_mm unavailable — assembly_length_mm not computable"
        )

    # Max diameter: largest of tool cutter or holder body
    candidates = [
        d for d in [tool_cutting_diameter_mm, holder_body_diameter_mm]
        if d is not None
    ]
    if candidates:
        result.assembly_max_diameter_mm = max(candidates)
    else:
        result.warnings.append(
            "No diameter data available — assembly_max_diameter_mm not computable"
        )

    # Fidelity = minimum of tool and holder fidelity
    t_rank = _FIDELITY_RANK.get(tool_geometry_fidelity, 0)
    h_rank = _FIDELITY_RANK.get(holder_geometry_fidelity, 0)
    min_rank = min(t_rank, h_rank)
    result.assembly_geometry_fidelity = _rank_to_fidelity(min_rank)

    result.tool_assembly_ready = True
    return result


def _rank_to_fidelity(rank: int) -> str:
    for name, r in _FIDELITY_RANK.items():
        if r == rank:
            return name
    return "NOT_AVAILABLE"
