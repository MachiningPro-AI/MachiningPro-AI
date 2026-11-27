"""
Phase Y — Quality Modes

FAST:
  - voxel stock removal (FAST_APPROXIMATE)
  - simplified geometry allowed
  - clearly labeled approximate

BALANCED:
  - higher tessellation
  - tool-holder assembly collision
  - intermediate fidelity

HIGH_FIDELITY:
  - B-Rep Boolean where supported (BREP_BOOLEAN)
  - exact B-Rep volumes (BREP_EXACT)
  - highest legitimate geometry fidelity

Every simulation/verification result exposes QUALITY_MODE.
No claim that equal accuracy exists between modes.

FAST_MODE_READY=YES
BALANCED_MODE_READY=YES
HIGH_FIDELITY_MODE_READY=YES
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class QualityMode(StrEnum):
    FAST = "FAST"
    BALANCED = "BALANCED"
    HIGH_FIDELITY = "HIGH_FIDELITY"


@dataclass(frozen=True)
class QualityModeConfig:
    mode: QualityMode

    # Stock removal
    stock_removal_method: str           # FAST_APPROXIMATE or BREP_BOOLEAN
    stock_removal_fidelity: str

    # Geometry
    tool_geometry_fidelity: str         # min acceptable
    holder_geometry_fidelity: str

    # Collision
    assembly_collision_enabled: bool
    machine_collision_enabled: bool

    # Volume
    volume_method: str                  # BREP_SOLID_VOLUME or VOXEL_APPROXIMATE
    volume_fidelity: str

    # Description for UI / reporting
    description: str


QUALITY_MODE_FAST = QualityModeConfig(
    mode=QualityMode.FAST,
    stock_removal_method="FAST_APPROXIMATE",
    stock_removal_fidelity="APPROXIMATE_VOXEL",
    tool_geometry_fidelity="SIMPLIFIED",
    holder_geometry_fidelity="SIMPLIFIED",
    assembly_collision_enabled=False,
    machine_collision_enabled=False,
    volume_method="VOXEL_APPROXIMATE",
    volume_fidelity="APPROXIMATE_VOXEL",
    description="Voxel approximation. Fast preview. NOT exact.",
)

QUALITY_MODE_BALANCED = QualityModeConfig(
    mode=QualityMode.BALANCED,
    stock_removal_method="FAST_APPROXIMATE",
    stock_removal_fidelity="APPROXIMATE_VOXEL",
    tool_geometry_fidelity="PARTIAL",
    holder_geometry_fidelity="SIMPLIFIED",
    assembly_collision_enabled=True,
    machine_collision_enabled=False,
    volume_method="VOXEL_APPROXIMATE",
    volume_fidelity="APPROXIMATE_VOXEL",
    description="Higher tessellation + assembly collision. Approximate volumes.",
)

QUALITY_MODE_HIGH_FIDELITY = QualityModeConfig(
    mode=QualityMode.HIGH_FIDELITY,
    stock_removal_method="BREP_BOOLEAN",
    stock_removal_fidelity="BREP_EXACT",
    tool_geometry_fidelity="PARAMETRIC_BREP",
    holder_geometry_fidelity="PARAMETRIC_BREP",
    assembly_collision_enabled=True,
    machine_collision_enabled=True,
    volume_method="BREP_SOLID_VOLUME",
    volume_fidelity="BREP_EXACT",
    description="B-Rep Boolean + exact volumes. Highest fidelity. Slower.",
)


_MODE_MAP: dict[QualityMode, QualityModeConfig] = {
    QualityMode.FAST: QUALITY_MODE_FAST,
    QualityMode.BALANCED: QUALITY_MODE_BALANCED,
    QualityMode.HIGH_FIDELITY: QUALITY_MODE_HIGH_FIDELITY,
}


def get_quality_mode_config(mode: QualityMode | str) -> QualityModeConfig:
    if isinstance(mode, str):
        mode = QualityMode(mode)
    return _MODE_MAP[mode]


def annotate_result_with_quality_mode(result: dict, mode: QualityMode | str) -> dict:
    """Add QUALITY_MODE field to any result dict."""
    cfg = get_quality_mode_config(mode)
    result["QUALITY_MODE"] = cfg.mode.value
    result["QUALITY_MODE_DESCRIPTION"] = cfg.description
    return result
