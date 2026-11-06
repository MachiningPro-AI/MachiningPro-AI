"""ISO 1832 insert taxonomy models.

No manufacturer grades or specifications are fabricated here.
All grade/coating fields are None unless sourced from a real catalog record.
"""
from __future__ import annotations

from pydantic import BaseModel


class InsertDesignation(BaseModel):
    """Parsed fields from an ISO 1832 insert designation string."""

    raw: str
    shape_code: str
    shape_description: str
    clearance_code: str
    clearance_deg: float | None
    tolerance_code: str
    type_code: str
    type_description: str
    size_code: str
    ic_mm: float | None
    thickness_code: str
    thickness_mm: float | None
    nose_radius_code: str | None
    nose_radius_mm: float | None
    cutting_direction_code: str | None
    manufacturer_specific: str | None
    parse_warnings: list[str]


class InsertGeometry(BaseModel):
    """Physical geometry of an ISO indexable insert."""

    shape_code: str
    clearance_angle_deg: float | None = None
    tolerance_class: str | None = None
    ic_mm: float | None = None
    thickness_mm: float | None = None
    nose_radius_mm: float | None = None
    edge_length_mm: float | None = None
    cutting_direction: str | None = None  # R, L, N


class InsertGrade(BaseModel):
    """Substrate, coating and grade metadata for an indexable insert."""

    substrate_material_code: str | None = None  # CARBIDE, CERMET, CERAMIC, CBN, PCD
    substrate_grade: str | None = None           # manufacturer grade code
    coating: str | None = None
    coating_type: str | None = None              # CVD, PVD, UNCOATED
    hardness_hv: int | None = None


class InsertSourceMetadata(BaseModel):
    """Provenance metadata for an insert record."""

    source_title: str
    source_authority: str
    evidence_status: str                  # MANUFACTURER_CATALOG or UNVERIFIED
    catalog_code: str | None = None
    source_note: str | None = None


class InsertRecord(BaseModel):
    """A single ISO indexable insert record with parsed designation."""

    stable_id: str
    manufacturer: str
    product_family: str | None = None
    product_name: str

    designation: InsertDesignation
    geometry: InsertGeometry
    grade: InsertGrade
    provenance: InsertSourceMetadata

    iso_material_groups: list[str]       # P / M / K / N / S / H
    supported_operations: list[str]
    missing_fields: list[str] = []
