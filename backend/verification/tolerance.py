"""
Centralized tolerance policy for verification checks.

No magic epsilons — all tolerances are explicit and traceable.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class TolerancePolicy:
    linear_mm: float
    angular_deg: float
    collision_mm: float
    gouge_mm: float
    stock_voxel_mm: float
    max_path_segments: int
    max_voxel_cells: int
    max_simulation_iterations: int


DEFAULT_TOLERANCE = TolerancePolicy(
    linear_mm=0.001,
    angular_deg=0.01,
    collision_mm=0.0,
    gouge_mm=0.001,
    stock_voxel_mm=1.0,
    max_path_segments=50_000,
    max_voxel_cells=1_000_000,
    max_simulation_iterations=10_000,
)
