"""Spindle interface adapter — bridge between Machine Library and Tool Library.

PROBLEM
-------
The Machine Library normalizes spindle interface strings via
``normalize_interface_string()`` into ``NormalizedMachineInterface`` objects
with structured ``InterfaceFamily`` and canonical designation fields.

The Tool Library's ``ToolHolderRecord.spindle_interface`` is a raw ``str | None``
field (e.g. "BT40", "HSK-A63", "CAT 40"). No normalization occurs within the
Tool Library.

This adapter connects the two by normalizing a holder's raw spindle_interface
string using the Machine Library's normalization rules, then delegating
compatibility checking to the Machine Library's ``check_interface_compatibility()``.

CAT40 ≠ BT40
------------
CAT-40 (ANSI/ASME B5.50) and BT-40 (JIS B 6339) have the same 7:24 taper
angle and nominally the same gauge-line diameter but differ in pull-stud
geometry, V-flange geometry, and drawbar thread.  Interchangeability has NOT
been verified.  This adapter treats them as DIFFERENT interface families;
``check_interface_compatibility()`` returns FAIL for cross-family comparisons.

Design constraints:
  MISSING_INTERFACE_AS_COMPATIBLE=NO
  CAT40_EQ_BT40=NO
  UNKNOWN_AS_PASS=NO
  FAIL_CLOSED=YES
"""

from __future__ import annotations

from backend.machine_library.interfaces import (
    InterfaceCompatibilityResult,
    InterfaceVerificationStatus,
    NormalizedMachineInterface,
    check_interface_compatibility,
    normalize_interface_string,
)

__all__ = [
    "normalize_holder_spindle_interface",
    "check_holder_machine_spindle_compatibility",
]


def normalize_holder_spindle_interface(
    raw: str | None,
    *,
    source_note: str = "tool-library holder record",
) -> NormalizedMachineInterface:
    """Normalize a ToolHolderRecord.spindle_interface string.

    None or blank → UNKNOWN family (never PASS).
    Unrecognized strings → preserved raw with UNVERIFIED status.
    """
    return normalize_interface_string(
        raw,
        source_note=source_note,
        verification_status=InterfaceVerificationStatus.INFERRED,
    )


def check_holder_machine_spindle_compatibility(
    holder_spindle_raw: str | None,
    machine_spindle_raw: str | None,
) -> InterfaceCompatibilityResult:
    """Check whether a holder's spindle interface is compatible with a machine's.

    Both raw strings are normalized independently before comparison.
    Returns PASS, FAIL, or UNKNOWN — never guesses or promotes UNKNOWN to PASS.

    CAT-40 and BT-40 are treated as incompatible (different families) because
    their pull-stud and drawbar geometries differ and equivalence is unverified.
    """
    holder_norm = normalize_holder_spindle_interface(holder_spindle_raw)
    machine_norm = normalize_interface_string(
        machine_spindle_raw,
        source_note="machine-library machine record",
        verification_status=InterfaceVerificationStatus.MANUFACTURER_CONFIRMED,
    )
    return check_interface_compatibility(machine_norm, holder_norm)
