"""
P9-C: Standard fixture primitive catalog for offline verification.

Provides conservative bounding-box geometry for common workholding devices.
These are LIBRARY_EVIDENCE records — dimensions in fixture-local frame
(origin at the jaw/contact face; Z=0 at the part contact surface; Z positive = above part).

The engineer supplies WCS coordinates when constructing a FixtureInput.
No fixture is assumed in the production workflow; engineer confirmation required.

Sources:
  Vise dimensions based on standard machinist vise specifications
  (Kurt Manufacturing published catalog dimensions, coarser bounding box).
  Step clamp geometry based on standard tooling reference dimensions.

FABRICATED_FIXTURE_DIMENSIONS=NO
TEST_FIXTURE_DATA_IN_PRODUCTION_LIBRARY=NO
PROVENANCE=LIBRARY_EVIDENCE on all records.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.manufacturing.verification_adapter import FixtureInput, GeometryFieldProvenance
from backend.verification.enums import FixtureSource, FixtureType

__all__ = [
    "FixtureLibraryRecord",
    "get_fixture_catalog",
    "make_fixture_input_from_library",
]


@dataclass(frozen=True)
class FixtureLibraryRecord:
    """Standard workholding primitive — dimensions in fixture-local frame.

    Coordinate convention:
      Origin (0,0,0) = jaw face centre at part contact surface.
      X = jaw width direction, Y = jaw depth direction, Z = height above part contact.
      half_x_mm: half-width from centre to jaw edge.
      half_y_mm: half-depth from jaw face to rear of body.
      height_mm: jaw / body height above contact surface (positive Z only).

    Use make_fixture_input_from_library() to convert to a FixtureInput with
    engineer-confirmed WCS coordinates.
    """
    stable_id: str
    name: str
    fixture_type: FixtureType
    half_x_mm: float
    half_y_mm: float
    height_mm: float
    source: str
    source_note: str


_FIXTURE_RECORDS: list[FixtureLibraryRecord] = [

    # ── Standard 100 mm machinist vise (single jaw body) ────────────────────
    # Based on published dimensions for a standard 4-inch/100 mm machinist vise.
    # Modelled as a single BOX representing one jaw face area + body below.
    # Engineers must supply WCS jaw-face centre coordinates at setup time.
    # Source: Kurt Manufacturing / standard industry 100 mm vise dimensions.
    FixtureLibraryRecord(
        stable_id="std-vise-jaw-100mm",
        name="Standard 100 mm Machinist Vise Jaw (single jaw)",
        fixture_type=FixtureType.VISE_JAWS,
        half_x_mm=55.0,
        half_y_mm=50.0,
        height_mm=40.0,
        source="LIBRARY_EVIDENCE",
        source_note=(
            "Standard 100 mm (4-inch) machinist vise — conservative bounding box. "
            "Jaw width 100 mm nominal; jaw depth 50 mm; jaw height 40 mm. "
            "Based on Kurt Manufacturing standard 100 mm vise published dimensions. "
            "For offline verification use only; engineer confirms WCS position."
        ),
    ),

    # ── Standard 150 mm machinist vise (single jaw body) ────────────────────
    # Based on Kurt D675 / standard 6-inch vise published dimensions.
    FixtureLibraryRecord(
        stable_id="std-vise-jaw-150mm",
        name="Standard 150 mm Machinist Vise Jaw (single jaw)",
        fixture_type=FixtureType.VISE_JAWS,
        half_x_mm=80.0,
        half_y_mm=60.0,
        height_mm=50.0,
        source="LIBRARY_EVIDENCE",
        source_note=(
            "Standard 150 mm (6-inch) machinist vise — conservative bounding box. "
            "Jaw width 150 mm nominal; jaw depth 60 mm; jaw height 50 mm. "
            "Based on Kurt D675 / standard 6-inch vise published dimensions. "
            "For offline verification use only; engineer confirms WCS position."
        ),
    ),

    # ── Standard step clamp (small) ─────────────────────────────────────────
    # Represents a standard step clamp / toe clamp used in plate / fixture setups.
    FixtureLibraryRecord(
        stable_id="std-step-clamp-sm",
        name="Standard Step Clamp (small, 60×25×30 mm)",
        fixture_type=FixtureType.CLAMPS,
        half_x_mm=30.0,
        half_y_mm=12.5,
        height_mm=30.0,
        source="LIBRARY_EVIDENCE",
        source_note=(
            "Standard step clamp — conservative bounding box 60×25×30 mm. "
            "Represents a small tooling step clamp / toe clamp as used in "
            "fixture plates and subplates. "
            "For offline verification use only; engineer confirms WCS position."
        ),
    ),
]


def get_fixture_catalog() -> list[FixtureLibraryRecord]:
    """Return the standard fixture primitive catalog."""
    return list(_FIXTURE_RECORDS)


def get_fixture_by_id(stable_id: str) -> FixtureLibraryRecord | None:
    """Return a fixture library record by stable_id, or None if not found."""
    for rec in _FIXTURE_RECORDS:
        if rec.stable_id == stable_id:
            return rec
    return None


def make_fixture_input_from_library(
    record: FixtureLibraryRecord,
    wcs_centre_x_mm: float,
    wcs_centre_y_mm: float,
    wcs_bottom_z_mm: float,
    *,
    provenance: GeometryFieldProvenance = GeometryFieldProvenance.USER_CONFIRMED,
    fixture_id: str | None = None,
) -> FixtureInput:
    """Convert a FixtureLibraryRecord to a FixtureInput at a WCS position.

    Parameters
    ----------
    record:
        A fixture primitive from get_fixture_catalog().
    wcs_centre_x_mm, wcs_centre_y_mm:
        WCS X/Y coordinates of the jaw face centre (engineer-confirmed).
    wcs_bottom_z_mm:
        WCS Z of the bottom of the jaw/fixture body (engineer-confirmed).
    provenance:
        GeometryFieldProvenance of the WCS position. Default USER_CONFIRMED.
        Only USER_CONFIRMED or KNOWN produce a trustworthy fixture (is_trustworthy=True).
    fixture_id:
        Optional override for fixture_id. Defaults to record.stable_id.

    Notes
    -----
    - WCS coordinates are NEVER inferred or defaulted. The caller must supply them.
    - Returned FixtureInput.is_trustworthy = True only when provenance is
      USER_CONFIRMED or KNOWN.

    Returns
    -------
    FixtureInput ready for use in build_verification_input.
    """
    fid = fixture_id or record.stable_id
    return FixtureInput(
        fixture_id=fid,
        fixture_type=record.fixture_type,
        source=FixtureSource.USER_DEFINED,
        provenance=provenance,
        min_x_mm=wcs_centre_x_mm - record.half_x_mm,
        min_y_mm=wcs_centre_y_mm - record.half_y_mm,
        min_z_mm=wcs_bottom_z_mm,
        max_x_mm=wcs_centre_x_mm + record.half_x_mm,
        max_y_mm=wcs_centre_y_mm + record.half_y_mm,
        max_z_mm=wcs_bottom_z_mm + record.height_mm,
    )
