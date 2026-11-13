"""Title-block material designation extraction (P0).

Provides deterministic, pattern-based extraction of explicit material
designations from DXF drawing title-block MTEXT tokens.

HARD RULES:
  - Only classify as material if an explicit, recognized designation exists.
  - Do NOT treat arbitrary text, part numbers, or drawing numbers as material.
  - Do NOT infer material from context, ISO group, or generic description.
  - All extractions tagged source=TITLE_BLOCK.
  - FABRICATED_MATERIAL=NO.

Pattern coverage (European engineering drawing standards):
  - EN 10083 / DIN steels: 42CrMo4, C45, C40, 16MnCr5, 20MnCr5, Ck45
  - EN 10025 structural: S235JR, S355JR, S355J2, S275JR
  - EN 10027-2 numeric: 1.7225, 1.0503, 1.0038, 1.4301, 1.4404
  - Stainless: 304, 316L, X5CrNi18-10, 1.4301
  - Aluminum: EN AW-6082, AlSiMgMn, AlSi10Mg, AlZnMgCu1.5, 7075, 6061
  - Titanium: Ti-6Al-4V, Grade 5 (Ti)
  - ISO short-designation form: e.g. "MAT: 42CrMo4"
  - Turkish title-block labels: "MALZEME:", "MAMUL MAL:"
"""

from __future__ import annotations

import re
from typing import NamedTuple

from backend.interoperability.missing_data import (
    EngineeringField,
    EngineeringFieldSource,
    EngineeringFieldStatus,
)


# ---------------------------------------------------------------------------
# Known material aliases → canonical material library IDs
# ---------------------------------------------------------------------------

_MATERIAL_ALIASES: dict[str, str] = {
    # EN 10083 / DIN steels
    "42CrMo4":    "P-42CrMo4",
    "42crmo4":    "P-42CrMo4",
    "1.7225":     "P-42CrMo4",
    "C45":        "P-C45",
    "c45":        "P-C45",
    "Ck45":       "P-Ck45",
    "ck45":       "P-Ck45",
    "C40":        "P-C45",
    "c40":        "P-C45",
    "1.0503":     "P-C45",
    "1.1191":     "P-Ck45",
    "16MnCr5":    "P-16MnCr5",
    "16mncr5":    "P-16MnCr5",
    "20MnCr5":    "P-20MnCr5",
    "20mncr5":    "P-20MnCr5",
    # EN 10025 structural
    "S235JR":     "P-S235JR",
    "s235jr":     "P-S235JR",
    "1.0038":     "P-S235JR",
    "S355JR":     "P-S355JR",
    "s355jr":     "P-S355JR",
    "S355J2":     "P-S355J2",
    "s355j2":     "P-S355J2",
    "1.0577":     "P-S355JR",
    # Stainless
    "304":           "M-304",
    "X5CrNi18-10":   "M-304",
    "x5crni18-10":   "M-304",
    "1.4301":        "M-304",
    "316L":          "M-316L",
    "316l":          "M-316L",
    "X2CrNiMo17-12-2": "M-316L",
    "1.4404":        "M-316L",
    "17-4PH":        "M-17-4PH",
    "17-4ph":        "M-17-4PH",
    # Cast iron
    "GJL-250":    "K-GJL-250",
    "gjl-250":    "K-GJL-250",
    "EN-GJL-250": "K-GJL-250",
    "GJS-400":    "K-GJS-400",
    "gjs-400":    "K-GJS-400",
    "GG-25":      "K-GJL-250",
    "gg-25":      "K-GJL-250",
    # Aluminum
    "EN AW-6082": "N-6082-T6",
    "EN AW 6082": "N-6082-T6",
    "6082":       "N-6082-T6",
    "AlSiMgMn":   "N-6082-T6",
    "EN AW-6061": "N-6061-T6",
    "EN AW 6061": "N-6061-T6",
    "6061":       "N-6061-T6",
    "AlSi1MgMn":  "N-6061-T6",
    "EN AW-7075": "N-7075-T6",
    "7075":       "N-7075-T6",
    "AlZnMgCu1.5": "N-7075-T6",
    "AlSi10Mg":   "N-6082-T6",
    # Titanium
    "Ti-6Al-4V":  "S-Ti64",
    "Ti6Al4V":    "S-Ti64",
    "Grade 5":    "S-Ti64",
    "GRADE 5":    "S-Ti64",
    "3.7165":     "S-Ti64",
}


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------

class MaterialMatch(NamedTuple):
    raw_text: str
    designation: str
    library_id: str | None
    confidence: float


# Title-block label prefixes in various drawing standards
_TITLE_BLOCK_PREFIXES = re.compile(
    r"""
    (?:
        (?:MALZEME|MATERIAL|WERKSTOFF|MATIERE|MAT\.?)\s*[:：]\s*
        | (?:RAW\s*MATERIAL|MAMUL\s*MAL)\s*[:：]\s*
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Explicit EN/DIN/ISO designation patterns
_DESIGNATION_PATTERNS: list[re.Pattern[str]] = [
    # EN 10027-2 numeric: 1.0038, 1.7225, 1.4404, etc.
    re.compile(r"\b1\.[0-9]{4}\b"),
    # Structural steels: S235JR, S355J2+N, S275JR, etc.
    re.compile(r"\bS\d{3}J[0-9A-Z]{0,3}(?:\+[A-Z]+)?\b"),
    # Case-hardening / heat-treatable: 42CrMo4, 16MnCr5, 20MnCr5, C45, Ck45, C40
    re.compile(r"\b(?:42CrMo4|16MnCr5|20MnCr5|C45|C40|Ck45|C60)\b", re.IGNORECASE),
    # Stainless: X(n)Cr(Ni)(Mo)(n)(-n), 304, 316L, 17-4PH
    re.compile(r"\bX\d+Cr[A-Za-z0-9\-]+\b"),
    re.compile(r"\b3(?:04|16L?|21|47)\b"),
    re.compile(r"\b17-4PH\b", re.IGNORECASE),
    # Cast iron: EN-GJL-250, GJL-250, GG-25, GGG-40
    re.compile(r"\b(?:EN-?)?GJ[LS]-?\d{3}\b", re.IGNORECASE),
    re.compile(r"\bGG[GS]?-?\d{2,3}\b", re.IGNORECASE),
    # Aluminum: EN AW-6xxx, 6082, 7075, 6061, AlSi10Mg, AlSiMgMn, AlZn...
    re.compile(r"\bEN\s*AW[-\s]?[0-9]{4}(?:-[A-Z0-9]+)?\b", re.IGNORECASE),
    re.compile(r"\b(?:60[68][12]|7075|5083)\b"),
    re.compile(r"\bAl(?:Si|Zn|Cu|Mg)[A-Za-z0-9]+\b"),
    # Titanium: Ti-6Al-4V, Ti6Al4V, Grade 5
    re.compile(r"\bTi[-]?6Al[-]?4V\b", re.IGNORECASE),
    re.compile(r"\bGrade\s*5\b", re.IGNORECASE),
    re.compile(r"\b3\.7165\b"),
]


def _lookup_alias(text: str) -> str | None:
    """Case-insensitive alias lookup. Returns library_id or None."""
    # Try exact first
    if text in _MATERIAL_ALIASES:
        return _MATERIAL_ALIASES[text]
    # Try lowercase
    return _MATERIAL_ALIASES.get(text.lower())


def _match_designation_in_token(token: str) -> MaterialMatch | None:
    """Try to match a material designation in a single token string.

    Returns a MaterialMatch or None.
    """
    # Remove MTEXT format control codes residue (should already be stripped,
    # but defensive)
    cleaned = re.sub(r"\\[A-Za-z][^;]*;|{|}|\\U\+[0-9A-Fa-f]+", "", token).strip()

    if not cleaned:
        return None

    # 1. Title-block prefix → extract the material part after it
    prefix_match = _TITLE_BLOCK_PREFIXES.search(cleaned)
    if prefix_match:
        after_prefix = cleaned[prefix_match.end():].strip()
        # Try the text after the prefix against alias map or patterns
        result = _try_match(after_prefix)
        if result:
            return MaterialMatch(
                raw_text=cleaned,
                designation=result[0],
                library_id=result[1],
                confidence=0.90,
            )

    # 2. Try the full token
    result = _try_match(cleaned)
    if result:
        return MaterialMatch(
            raw_text=cleaned,
            designation=result[0],
            library_id=result[1],
            confidence=0.80,
        )

    return None


def _try_match(text: str) -> tuple[str, str | None] | None:
    """Try alias map first, then pattern matching.

    Returns (designation, library_id) or None.
    """
    # Alias exact match
    lib_id = _lookup_alias(text)
    if lib_id:
        return (text, lib_id)

    # Pattern match — try each pattern
    for pattern in _DESIGNATION_PATTERNS:
        m = pattern.search(text)
        if m:
            matched_text = m.group(0)
            lib_id = _lookup_alias(matched_text)
            return (matched_text, lib_id)

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_title_block_material(
    mtext_tokens: list[str],
) -> EngineeringField | None:
    """Extract material designation from DXF MTEXT title-block tokens.

    Scans all tokens for explicit material designations. Returns the
    best match or None if no material is found.

    Args:
        mtext_tokens: List of raw MTEXT token strings, already stripped of
                      AutoCAD format codes via strip_mtext_codes().

    Returns:
        EngineeringField with status=KNOWN, source=TITLE_BLOCK, or None.
    """
    best: MaterialMatch | None = None

    for token in mtext_tokens:
        match = _match_designation_in_token(token)
        if match and (best is None or match.confidence > best.confidence):
            best = match

    if best is None:
        return None

    ef = EngineeringField.known(
        field_name="material",
        value=best.designation,
        source=EngineeringFieldSource.TITLE_BLOCK,
        confidence=best.confidence,
    )
    # Set library resolution fields
    ef.library_resolved_id = best.library_id
    ef.library_resolved_designation = best.designation
    return ef
