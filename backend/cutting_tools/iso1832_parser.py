"""ISO 1832 indexable insert designation parser.

ISO 1832 character positions (after stripping spaces):
  1   : Insert shape          (1 char, alpha)
  2   : Clearance angle       (1 char, alpha)
  3   : Tolerance class       (1 char, alpha)
  4   : Insert type           (1 char, alpha)
  5–6 : Insert size           (2 chars, digit, IC in mm)
  7–8 : Thickness             (2 chars, mixed)
  9–10: Nose radius           (2 chars, digit, optional)
  11  : Cutting direction     (1 char, R/L/N, optional)
  ... : Manufacturer suffix   (follows a hyphen delimiter)

Unknown or unsupported positions are recorded in ``parse_warnings`` and
decoded fields are set to ``None``; a ``ValueError`` is raised only for
structurally invalid input (fewer than 8 characters after normalization).
"""
from __future__ import annotations

from .insert_models import InsertDesignation

# ── Shape (position 1) ────────────────────────────────────────────────────────

_SHAPE_CODES: dict[str, str] = {
    "A": "Parallelogram 85°",
    "B": "Parallelogram 82°",
    "C": "Rhombic 80°",
    "D": "Rhombic 55°",
    "E": "Rhombic 75°",
    "H": "Hexagonal",
    "K": "Parallelogram 55°",
    "L": "Rectangular",
    "M": "Rhombic 86°",
    "O": "Octagonal",
    "P": "Pentagonal",
    "R": "Round",
    "S": "Square 90°",
    "T": "Trigon / Equilateral Triangle 60°",
    "V": "Rhombic 35°",
    "W": "Trigon 80°",
}

# ── Clearance angle (position 2) ──────────────────────────────────────────────

_CLEARANCE_DEG: dict[str, float] = {
    "A": 3.0,
    "B": 5.0,
    "C": 7.0,
    "D": 15.0,
    "E": 20.0,
    "F": 25.0,
    "G": 30.0,
    "N": 0.0,
    "O": 11.0,
    "P": 11.0,
}

# ── Insert type (position 4) ──────────────────────────────────────────────────

_TYPE_CODES: dict[str, str] = {
    "A": "With hole, 20° countersink (one side), no chipbreaker",
    "B": "With hole, 20° countersink (both sides), no chipbreaker",
    "C": "Without hole, without chipbreaker",
    "F": "With hole, 20° countersink (one side), one-side chipbreaker",
    "G": "With hole, 20° countersink (both sides), both-side chipbreaker",
    "H": "Without hole, with chipbreaker",
    "M": "With hole, 20° countersink (one side), no chipbreaker (truncated)",
    "N": "Without hole, without chipbreaker (plain)",
    "Q": "With hole (cylindrical), without chipbreaker",
    "R": "Without hole, one-side chipbreaker",
    "S": "With hole, 90° countersink (one side), without chipbreaker",
    "T": "With hole, 90° countersink (one side), one-side chipbreaker",
    "W": "With hole, 90° countersink (both sides), without chipbreaker",
    "X": "Manufacturer specific",
    "Z": "Manufacturer specific (variant)",
}

# ── Thickness codes (position 7–8) ───────────────────────────────────────────
# Inch-origin codes (most common for CNMG/SNMG/TNMG family):

_THICKNESS_MM: dict[str, float] = {
    "01": 1.59,
    "02": 2.38,
    "03": 3.18,
    "04": 4.76,
    "05": 5.56,
    "06": 6.35,
    "07": 7.94,
    "08": 9.52,
    # Metric codes:
    "T1": 1.5,
    "T2": 2.0,
    "T3": 2.5,
    "T4": 3.0,
    "T5": 3.5,
    "T6": 4.0,
    "T7": 4.5,
    "T8": 5.0,
}


def parse_iso1832(designation: str) -> InsertDesignation:
    """Parse an ISO 1832 insert designation into an ``InsertDesignation`` object.

    Whitespace within the alphanumeric core is stripped before parsing so that
    ``"CNMG 120408"`` and ``"CNMG120408"`` are equivalent.  A hyphen separates
    the ISO core from any manufacturer-specific suffix (e.g. ``"-MF4"``).

    Raises:
        ValueError: if the core is fewer than 8 characters after normalization.

    Returns an ``InsertDesignation`` with ``parse_warnings`` populated for any
    unrecognized position codes; decoded numeric fields are ``None`` for unknown
    codes rather than fabricated values.
    """
    stripped = designation.strip()

    # Split manufacturer suffix on the first hyphen
    if "-" in stripped:
        iso_part, _, mfr_suffix = stripped.partition("-")
        manufacturer_specific: str | None = mfr_suffix.strip() or None
    else:
        iso_part = stripped
        manufacturer_specific = None

    # Remove embedded spaces from the ISO core
    core = iso_part.replace(" ", "")

    if len(core) < 8:
        raise ValueError(
            f"ISO 1832 designation too short: {designation!r} "
            f"({len(core)} characters after normalization, minimum 8 required)"
        )

    warnings: list[str] = []

    # Fixed positions
    shape_code = core[0].upper()
    clearance_code = core[1].upper()
    tolerance_code = core[2].upper()
    type_code = core[3].upper()
    size_code = core[4:6]
    thickness_code = core[6:8]

    # Decode shape
    shape_description = _SHAPE_CODES.get(shape_code)
    if shape_description is None:
        shape_description = f"UNKNOWN({shape_code!r})"
        warnings.append(f"Unrecognized shape code {shape_code!r}")

    # Decode clearance angle
    clearance_deg = _CLEARANCE_DEG.get(clearance_code)
    if clearance_deg is None:
        warnings.append(f"Unrecognized clearance angle code {clearance_code!r}")

    # Decode IC / insert size (first two digits are IC in mm)
    ic_mm: float | None
    try:
        ic_mm = float(size_code)
    except ValueError:
        ic_mm = None
        warnings.append(f"Cannot decode IC from size code {size_code!r}")

    # Decode thickness
    thickness_mm: float | None = _THICKNESS_MM.get(thickness_code)
    if thickness_mm is None:
        try:
            thickness_mm = float(thickness_code)
        except ValueError:
            pass
    if thickness_mm is None:
        warnings.append(f"Cannot decode thickness from code {thickness_code!r}")

    # Decode type description
    type_description = _TYPE_CODES.get(type_code, f"UNKNOWN({type_code!r})")
    if type_description.startswith("UNKNOWN"):
        warnings.append(f"Unrecognized insert type code {type_code!r}")

    # Optional nose radius (positions 9–10)
    nose_radius_code: str | None = None
    nose_radius_mm: float | None = None
    cutting_direction_code: str | None = None

    tail = core[8:]

    if len(tail) >= 2:
        candidate = tail[:2]
        try:
            nr_val = float(candidate) / 10.0  # nose radius in tenths of mm
            nose_radius_code = candidate
            nose_radius_mm = nr_val
            tail = tail[2:]
        except ValueError:
            warnings.append(f"Cannot decode nose radius from {candidate!r}")

    # Optional cutting direction (R / L / N)
    if tail and tail[0].upper() in ("R", "L", "N"):
        cutting_direction_code = tail[0].upper()
        tail = tail[1:]

    # Anything left before the hyphen suffix is treated as manufacturer-specific
    if tail:
        manufacturer_specific = (
            tail if manufacturer_specific is None else tail + "-" + manufacturer_specific
        )

    return InsertDesignation(
        raw=designation,
        shape_code=shape_code,
        shape_description=shape_description,
        clearance_code=clearance_code,
        clearance_deg=clearance_deg,
        tolerance_code=tolerance_code,
        type_code=type_code,
        type_description=type_description,
        size_code=size_code,
        ic_mm=ic_mm,
        thickness_code=thickness_code,
        thickness_mm=thickness_mm,
        nose_radius_code=nose_radius_code,
        nose_radius_mm=nose_radius_mm,
        cutting_direction_code=cutting_direction_code,
        manufacturer_specific=manufacturer_specific,
        parse_warnings=warnings,
    )
