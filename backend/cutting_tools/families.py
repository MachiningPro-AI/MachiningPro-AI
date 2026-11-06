"""Tool family definitions — higher-level groupings over catalog category codes.

Nine production families are supported:
  DRILLING, MILLING, TURNING, BORING, THREADING, REAMING, GROOVING, GRINDING, EDM.

Each family maps to one or more tool_category_code values used in the catalog.
"""

from __future__ import annotations

from enum import StrEnum


class ToolFamily(StrEnum):
    """Coarse manufacturing process family for a cutting / erosion tool."""

    DRILLING = "DRILLING"
    MILLING = "MILLING"
    TURNING = "TURNING"
    BORING = "BORING"
    THREADING = "THREADING"   # taps + thread mills
    REAMING = "REAMING"
    GROOVING = "GROOVING"
    GRINDING = "GRINDING"
    EDM = "EDM"               # wire EDM wire and sinker electrodes


# Maps each family to the catalog tool_category_code values it covers.
FAMILY_TO_CATEGORY_CODES: dict[ToolFamily, frozenset[str]] = {
    ToolFamily.DRILLING:  frozenset({"DRILL"}),
    ToolFamily.MILLING:   frozenset({"END_MILL", "FACE_MILL_INSERT", "FACE_MILL_BODY"}),
    ToolFamily.TURNING:   frozenset({"TURNING_INSERT"}),
    ToolFamily.BORING:    frozenset({"BORING_BAR"}),
    ToolFamily.THREADING: frozenset({"TAP", "THREAD_MILL"}),
    ToolFamily.REAMING:   frozenset({"REAMER"}),
    ToolFamily.GROOVING:  frozenset({"GROOVING_INSERT"}),
    ToolFamily.GRINDING:  frozenset({"GRINDING_WHEEL"}),
    ToolFamily.EDM:       frozenset({"EDM_WIRE", "EDM_ELECTRODE"}),
}

# Reverse lookup: category code → family (built once at import time).
CATEGORY_CODE_TO_FAMILY: dict[str, ToolFamily] = {
    code: family
    for family, codes in FAMILY_TO_CATEGORY_CODES.items()
    for code in codes
}


def family_for_category_code(code: str) -> ToolFamily | None:
    """Return the ToolFamily for a tool_category_code, or None if unmapped."""
    return CATEGORY_CODE_TO_FAMILY.get(code)


def category_codes_for_family(family: ToolFamily) -> frozenset[str]:
    """Return the category codes that belong to a given family."""
    return FAMILY_TO_CATEGORY_CODES[family]
