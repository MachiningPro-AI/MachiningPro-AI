"""Tool holder catalog models.

No holder seed catalog is included; records must be sourced from real
manufacturer documentation.  This module defines the schema only.
"""
from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class HolderInterface(StrEnum):
    """Holder interface / chuck type."""

    ER_COLLET = "ER_COLLET"
    HYDRAULIC_CHUCK = "HYDRAULIC_CHUCK"
    SHRINK_FIT = "SHRINK_FIT"
    MILLING_CHUCK = "MILLING_CHUCK"
    SIDE_LOCK = "SIDE_LOCK"
    FACE_MILL_HOLDER = "FACE_MILL_HOLDER"
    BORING_HOLDER = "BORING_HOLDER"
    TAPPING_CHUCK = "TAPPING_CHUCK"
    TURNING_TOOLHOLDER = "TURNING_TOOLHOLDER"


class HolderCapacity(BaseModel):
    """Dimensional limits of the tool-receiving end of a holder."""

    min_shank_mm: float
    max_shank_mm: float
    max_tool_reach_mm: float | None = None
    gauge_length_mm: float | None = None
    max_runout_mm: float | None = None


class HolderSourceMetadata(BaseModel):
    """Provenance metadata for a tool holder record."""

    source_title: str
    source_authority: str
    evidence_status: str                  # MANUFACTURER_CATALOG or UNVERIFIED
    catalog_code: str | None = None
    source_note: str | None = None


class ToolHolderRecord(BaseModel):
    """A single tool holder catalog record."""

    stable_id: str
    manufacturer: str
    product_family: str | None = None
    product_name: str

    holder_type: HolderInterface
    spindle_interface: str | None = None   # machine-side: HSK-A63, BT40, CAT40, ISO 7:24

    capacity: HolderCapacity
    supports_coolant: bool | None = None
    coolant_through_spindle: bool | None = None

    # Insert pocket info — only relevant for TURNING_TOOLHOLDER, BORING_HOLDER, FACE_MILL_HOLDER
    insert_shape_code: str | None = None   # C, S, T, D …
    insert_ic_mm: float | None = None
    insert_hand: str | None = None         # R, L, N

    compatible_operations: list[str] = []

    provenance: HolderSourceMetadata
    missing_fields: list[str] = []
