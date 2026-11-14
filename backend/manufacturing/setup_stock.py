"""Setup and Stock Definition (P3-B).

Models and validation for workpiece stock geometry and machining setup.

Design invariants:
  - ALL dimension values must come from the engineer — never inferred or defaulted.
  - material_grade must reference a user-confirmed material — never fabricated.
  - No CNC dispatch, no automatic approval, no automatic adaptive correction.
  - Every resolved value carries USER_CONFIRMED provenance.

FABRICATED_STOCK_GEOMETRY=NO
FABRICATED_MATERIAL=NO
AUTO_CONFIRM=NO
CNC_DISPATCH=NO
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

__all__ = [
    "StockShape",
    "StockDefinition",
    "SetupDefinition",
    "SetupStockSession",
    "create_setup_stock_session",
    "validate_stock_dimensions",
]

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class StockShape(StrEnum):
    RECTANGULAR_BLOCK = "RECTANGULAR_BLOCK"
    ROUND_BAR = "ROUND_BAR"
    RING = "RING"
    PLATE = "PLATE"
    FORGING = "FORGING"


# ---------------------------------------------------------------------------
# Stock definition
# ---------------------------------------------------------------------------


@dataclass
class StockDefinition:
    """Workpiece stock geometry.  All dimensions in mm.

    Required dimensions by shape:
      RECTANGULAR_BLOCK : length_mm, width_mm, height_mm
      ROUND_BAR         : outer_diameter_mm, length_mm
      RING              : outer_diameter_mm, inner_diameter_mm, length_mm
      PLATE             : length_mm, width_mm, height_mm (height = thickness)
      FORGING           : length_mm, width_mm, height_mm (bounding box)

    material_grade must be a user-confirmed grade string — never an empty default.
    provenance is always USER_CONFIRMED.
    """

    stock_id: str
    shape: StockShape
    material_grade: str
    length_mm: float | None = None
    width_mm: float | None = None
    height_mm: float | None = None
    outer_diameter_mm: float | None = None
    inner_diameter_mm: float | None = None
    stock_notes: str | None = None
    confirmed_by: str = "engineer"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "stock_id": self.stock_id,
            "shape": str(self.shape),
            "material_grade": self.material_grade,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "outer_diameter_mm": self.outer_diameter_mm,
            "inner_diameter_mm": self.inner_diameter_mm,
            "stock_notes": self.stock_notes,
            "confirmed_by": self.confirmed_by,
            "provenance": "USER_CONFIRMED",
            "created_at": self.created_at.isoformat(),
        }


def validate_stock_dimensions(defn: StockDefinition) -> list[str]:
    """Return list of missing required dimension names for the given shape.

    Returns empty list when all required dimensions are present.
    """
    missing: list[str] = []
    if not defn.material_grade or not defn.material_grade.strip():
        missing.append("material_grade")

    shape = defn.shape
    if shape in (StockShape.RECTANGULAR_BLOCK, StockShape.PLATE, StockShape.FORGING):
        for dim in ("length_mm", "width_mm", "height_mm"):
            if getattr(defn, dim) is None:
                missing.append(dim)
    elif shape == StockShape.ROUND_BAR:
        for dim in ("outer_diameter_mm", "length_mm"):
            if getattr(defn, dim) is None:
                missing.append(dim)
    elif shape == StockShape.RING:
        for dim in ("outer_diameter_mm", "inner_diameter_mm", "length_mm"):
            if getattr(defn, dim) is None:
                missing.append(dim)
        # inner must be strictly less than outer
        if (
            defn.outer_diameter_mm is not None
            and defn.inner_diameter_mm is not None
            and defn.inner_diameter_mm >= defn.outer_diameter_mm
        ):
            missing.append("inner_diameter_mm:must_be_less_than_outer")

    for dim in ("length_mm", "width_mm", "height_mm", "outer_diameter_mm", "inner_diameter_mm"):
        v = getattr(defn, dim)
        if v is not None and v <= 0:
            missing.append(f"{dim}:must_be_positive")

    return missing


# ---------------------------------------------------------------------------
# Setup definition
# ---------------------------------------------------------------------------


@dataclass
class SetupDefinition:
    """Machining setup — datum assignment, orientation, fixture, and number of setups.

    datum_a/b/c are free-text descriptions provided by the engineer.
    n_setups must be ≥ 1.
    provenance is always USER_CONFIRMED.
    """

    setup_id: str
    n_setups: int = 1
    datum_a: str | None = None
    datum_b: str | None = None
    datum_c: str | None = None
    orientation: str | None = None
    fixture_note: str | None = None
    confirmed_by: str = "engineer"
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        return {
            "setup_id": self.setup_id,
            "n_setups": self.n_setups,
            "datum_a": self.datum_a,
            "datum_b": self.datum_b,
            "datum_c": self.datum_c,
            "orientation": self.orientation,
            "fixture_note": self.fixture_note,
            "confirmed_by": self.confirmed_by,
            "provenance": "USER_CONFIRMED",
            "created_at": self.created_at.isoformat(),
        }

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.n_setups < 1:
            errors.append("n_setups:must_be_at_least_1")
        return errors


# ---------------------------------------------------------------------------
# Session — links stock + setup to a cad_features session
# ---------------------------------------------------------------------------


@dataclass
class SetupStockSession:
    """Combines stock definition and setup definition for one CAD session."""

    session_id: str
    cad_session_id: str | None
    stock: StockDefinition | None
    setup: SetupDefinition | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def as_dict(self) -> dict[str, Any]:
        stock_errors = validate_stock_dimensions(self.stock) if self.stock else []
        setup_errors = self.setup.validate() if self.setup else []
        return {
            "session_id": self.session_id,
            "cad_session_id": self.cad_session_id,
            "stock": self.stock.as_dict() if self.stock else None,
            "setup": self.setup.as_dict() if self.setup else None,
            "stock_complete": self.stock is not None and len(stock_errors) == 0,
            "setup_complete": self.setup is not None and len(setup_errors) == 0,
            "stock_missing": stock_errors,
            "setup_errors": setup_errors,
            "cam_prerequisites_met": (
                self.stock is not None
                and len(stock_errors) == 0
                and self.setup is not None
                and len(setup_errors) == 0
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def create_setup_stock_session(cad_session_id: str | None = None) -> SetupStockSession:
    """Create a new, empty SetupStockSession."""
    return SetupStockSession(
        session_id=str(uuid.uuid4()),
        cad_session_id=cad_session_id,
        stock=None,
        setup=None,
    )
