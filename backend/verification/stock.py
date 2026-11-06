"""
Stock and fixture geometry models for Level-11 verification.

Stock dimensions must be explicitly provided — never inferred from part bounding box.
Fixture geometry must be USER_DEFINED or VERIFIED_LIBRARY_RECORD — never fabricated.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from .enums import FixtureSource, FixtureType, StockFidelity, StockRemovalFidelity, StockShape
from .tolerance import DEFAULT_TOLERANCE, TolerancePolicy


class StockModel(BaseModel):
    shape: StockShape
    fidelity: StockFidelity = StockFidelity.UNKNOWN
    min_x_mm: float | None = None
    min_y_mm: float | None = None
    min_z_mm: float | None = None
    max_x_mm: float | None = None
    max_y_mm: float | None = None
    max_z_mm: float | None = None
    radius_mm: float | None = None
    height_mm: float | None = None
    center_x_mm: float | None = None
    center_y_mm: float | None = None
    bottom_z_mm: float | None = None

    @property
    def is_known(self) -> bool:
        return self.shape != StockShape.UNKNOWN

    @property
    def has_box_dims(self) -> bool:
        return all(
            v is not None
            for v in [
                self.min_x_mm,
                self.min_y_mm,
                self.min_z_mm,
                self.max_x_mm,
                self.max_y_mm,
                self.max_z_mm,
            ]
        )

    @property
    def has_cylinder_dims(self) -> bool:
        return all(
            v is not None
            for v in [
                self.radius_mm,
                self.height_mm,
                self.center_x_mm,
                self.center_y_mm,
                self.bottom_z_mm,
            ]
        )

    def volume_mm3(self) -> float | None:
        if self.shape == StockShape.BOX and self.has_box_dims:
            return (
                (self.max_x_mm - self.min_x_mm)
                * (self.max_y_mm - self.min_y_mm)
                * (self.max_z_mm - self.min_z_mm)
            )
        if self.shape == StockShape.CYLINDER and self.has_cylinder_dims:
            return math.pi * self.radius_mm**2 * self.height_mm
        return None

    def contains_point(self, x: float, y: float, z: float) -> bool:
        if self.shape == StockShape.BOX and self.has_box_dims:
            return (
                self.min_x_mm <= x <= self.max_x_mm
                and self.min_y_mm <= y <= self.max_y_mm
                and self.min_z_mm <= z <= self.max_z_mm
            )
        if self.shape == StockShape.CYLINDER and self.has_cylinder_dims:
            dist2 = (x - self.center_x_mm) ** 2 + (y - self.center_y_mm) ** 2
            return (
                dist2 <= self.radius_mm**2
                and self.bottom_z_mm <= z <= self.bottom_z_mm + self.height_mm
            )
        return True


class FixtureGeometry(BaseModel):
    fixture_id: str = Field(default="fixture_0")
    fixture_type: FixtureType
    source: FixtureSource
    min_x_mm: float
    min_y_mm: float
    min_z_mm: float
    max_x_mm: float
    max_y_mm: float
    max_z_mm: float

    @property
    def is_known(self) -> bool:
        return self.fixture_type != FixtureType.UNKNOWN


class VoxelGrid:
    """
    3D voxel grid for approximate stock-removal simulation.

    occupied[iz][iy][ix] = True means material still present.
    Fidelity is VOXEL_APPROXIMATE — never reported as EXACT_BOOLEAN.
    """

    def __init__(
        self,
        min_x: float,
        min_y: float,
        min_z: float,
        resolution: float,
        nx: int,
        ny: int,
        nz: int,
    ):
        self.min_x = min_x
        self.min_y = min_y
        self.min_z = min_z
        self.resolution = resolution
        self.nx = nx
        self.ny = ny
        self.nz = nz
        self.occupied: list = [
            [[True] * nx for _ in range(ny)] for _ in range(nz)
        ]
        self.fidelity = StockRemovalFidelity.VOXEL_APPROXIMATE
        self.iterations_used = 0
        self.resource_limit_hit = False

    @classmethod
    def from_stock(
        cls,
        stock: StockModel,
        tol: TolerancePolicy = DEFAULT_TOLERANCE,
    ) -> VoxelGrid | None:
        if stock.shape == StockShape.BOX and stock.has_box_dims:
            return cls._from_box(
                stock.min_x_mm,
                stock.min_y_mm,
                stock.min_z_mm,
                stock.max_x_mm,
                stock.max_y_mm,
                stock.max_z_mm,
                tol,
            )
        if stock.shape == StockShape.CYLINDER and stock.has_cylinder_dims:
            cx, cy = stock.center_x_mm, stock.center_y_mm
            r = stock.radius_mm
            bz = stock.bottom_z_mm
            h = stock.height_mm
            return cls._from_box(cx - r, cy - r, bz, cx + r, cy + r, bz + h, tol)
        return None

    @classmethod
    def _from_box(
        cls,
        min_x: float,
        min_y: float,
        min_z: float,
        max_x: float,
        max_y: float,
        max_z: float,
        tol: TolerancePolicy,
    ) -> VoxelGrid:
        resolution = tol.stock_voxel_mm
        nx = max(1, int(math.ceil((max_x - min_x) / resolution)))
        ny = max(1, int(math.ceil((max_y - min_y) / resolution)))
        nz = max(1, int(math.ceil((max_z - min_z) / resolution)))
        total = nx * ny * nz
        if total > tol.max_voxel_cells:
            factor = (total / tol.max_voxel_cells) ** (1.0 / 3.0)
            resolution = resolution * factor * 1.01
            nx = max(1, int(math.ceil((max_x - min_x) / resolution)))
            ny = max(1, int(math.ceil((max_y - min_y) / resolution)))
            nz = max(1, int(math.ceil((max_z - min_z) / resolution)))
        return cls(min_x, min_y, min_z, resolution, nx, ny, nz)

    def remove_path_segment(
        self,
        x1: float,
        y1: float,
        z1: float,
        x2: float,
        y2: float,
        z2: float,
        radius: float,
        tol: TolerancePolicy = DEFAULT_TOLERANCE,
    ) -> bool:
        """Remove swept cylinder along segment. Returns False if iteration limit hit."""
        x_lo = min(x1, x2) - radius
        x_hi = max(x1, x2) + radius
        y_lo = min(y1, y2) - radius
        y_hi = max(y1, y2) + radius
        z_lo = min(z1, z2) - radius
        z_hi = max(z1, z2) + radius

        ix_lo = max(0, int((x_lo - self.min_x) / self.resolution))
        ix_hi = min(self.nx - 1, int((x_hi - self.min_x) / self.resolution))
        iy_lo = max(0, int((y_lo - self.min_y) / self.resolution))
        iy_hi = min(self.ny - 1, int((y_hi - self.min_y) / self.resolution))
        iz_lo = max(0, int((z_lo - self.min_z) / self.resolution))
        iz_hi = min(self.nz - 1, int((z_hi - self.min_z) / self.resolution))

        dx = x2 - x1
        dy = y2 - y1
        dz = z2 - z1
        seg_len2 = dx * dx + dy * dy + dz * dz
        r2 = radius * radius

        for iz in range(iz_lo, iz_hi + 1):
            for iy in range(iy_lo, iy_hi + 1):
                for ix in range(ix_lo, ix_hi + 1):
                    if not self.occupied[iz][iy][ix]:
                        continue
                    self.iterations_used += 1
                    if self.iterations_used > tol.max_simulation_iterations:
                        self.resource_limit_hit = True
                        return False
                    vx = self.min_x + (ix + 0.5) * self.resolution
                    vy = self.min_y + (iy + 0.5) * self.resolution
                    vz = self.min_z + (iz + 0.5) * self.resolution
                    if seg_len2 < 1e-12:
                        dist2 = (vx - x1) ** 2 + (vy - y1) ** 2 + (vz - z1) ** 2
                    else:
                        t = ((vx - x1) * dx + (vy - y1) * dy + (vz - z1) * dz) / seg_len2
                        t = max(0.0, min(1.0, t))
                        px = x1 + t * dx
                        py = y1 + t * dy
                        pz = z1 + t * dz
                        dist2 = (vx - px) ** 2 + (vy - py) ** 2 + (vz - pz) ** 2
                    if dist2 <= r2:
                        self.occupied[iz][iy][ix] = False
        return True

    def count_remaining(self) -> int:
        total = 0
        for layer in self.occupied:
            for row in layer:
                total += sum(1 for v in row if v)
        return total

    def volume_remaining_mm3(self) -> float:
        return self.count_remaining() * (self.resolution**3)
