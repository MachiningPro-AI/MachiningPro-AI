"""Machine interface normalization and tool-holder compatibility models.

Provides canonical forms for spindle and tool-holder interface designations.
Normalisation is best-effort only: unrecognised strings are preserved with
UNVERIFIED status and never silently discarded, guessed, or assumed compatible.

Design rules
------------
MISSING_INTERFACE_AS_COMPATIBLE=NO
GUESSED_INTERFACE=NO
UNKNOWN_TREATED_AS_COMPATIBLE=NO
FAIL_CLOSED=YES
NO_SPINDLE_AS_COMPATIBLE=NO
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

__all__ = [
    "InterfaceFamily",
    "InterfaceVerificationStatus",
    "CompatibilityVerdict",
    "NormalizedMachineInterface",
    "InterfaceCompatibilityResult",
    "normalize_interface_string",
    "check_interface_compatibility",
]


class InterfaceFamily(StrEnum):
    """Spindle / tool-holder interface family.

    NO_SPINDLE: non-rotating machines (EDMs) or no published taper interface.
    LATHE_CHUCK: chuck-based workholding spindle (not a tool taper).
    COLLET: collet-based tool or workholding interface.
    UNKNOWN: interface present but family unrecognised or not provided.
    """

    CAT = "CAT"
    BT = "BT"
    HSK = "HSK"
    SK = "SK"               # DIN 69871 / ISO 7388-1
    CAPTO = "CAPTO"         # Sandvik Coromant Capto
    KM = "KM"               # Kennametal KM
    VDI = "VDI"             # VDI turret (lathes)
    LATHE_CHUCK = "LATHE_CHUCK"
    COLLET = "COLLET"
    NO_SPINDLE = "NO_SPINDLE"
    UNKNOWN = "UNKNOWN"


class InterfaceVerificationStatus(StrEnum):
    """Evidence quality for a normalised interface record."""

    MANUFACTURER_CONFIRMED = "MANUFACTURER_CONFIRMED"
    INFERRED = "INFERRED"
    UNVERIFIED = "UNVERIFIED"
    UNKNOWN = "UNKNOWN"


class CompatibilityVerdict(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class NormalizedMachineInterface:
    """Canonical form of a spindle or tool-holder interface designation."""

    family: InterfaceFamily
    designation: str                    # Canonical form, e.g. "CAT-40"
    raw_input: str                      # Original string before normalisation
    verification_status: InterfaceVerificationStatus
    source_note: str = ""

    @property
    def is_known(self) -> bool:
        return self.family not in (InterfaceFamily.UNKNOWN, InterfaceFamily.NO_SPINDLE)

    @property
    def is_verified(self) -> bool:
        return self.verification_status in (
            InterfaceVerificationStatus.MANUFACTURER_CONFIRMED,
            InterfaceVerificationStatus.INFERRED,
        )


@dataclass(frozen=True)
class InterfaceCompatibilityResult:
    """Result of comparing machine spindle vs tool-holder interface."""

    verdict: CompatibilityVerdict
    machine_interface: NormalizedMachineInterface
    tool_interface: NormalizedMachineInterface
    reason: str


# ---------------------------------------------------------------------------
# Normalisation table — (compiled pattern, family, canonical or empty-string)
# When canonical is empty the pattern must supply group(0) for the designation.
# Applied in order; first match wins.
# ---------------------------------------------------------------------------

@dataclass
class _Rule:
    pattern: re.Pattern[str]
    family: InterfaceFamily
    canonical: str  # fixed canonical; "" means derive from uppercased raw


_RULES: list[_Rule] = []


def _add(pattern: str, family: InterfaceFamily, canonical: str = "") -> None:
    _RULES.append(_Rule(re.compile(pattern, re.IGNORECASE), family, canonical))


# CAT (ANSI/ASME B5.50)
_add(r"^cat[-\s]?50$",  InterfaceFamily.CAT, "CAT-50")
_add(r"^cat[-\s]?45$",  InterfaceFamily.CAT, "CAT-45")
_add(r"^cat[-\s]?40$",  InterfaceFamily.CAT, "CAT-40")
_add(r"^cat[-\s]?30$",  InterfaceFamily.CAT, "CAT-30")

# BT (JIS B 6339)
_add(r"^bt[-\s]?50$",   InterfaceFamily.BT, "BT-50")
_add(r"^bt[-\s]?40$",   InterfaceFamily.BT, "BT-40")
_add(r"^bt[-\s]?30$",   InterfaceFamily.BT, "BT-30")

# HSK (DIN 69893 / ISO 12164)
_add(r"^hsk[-\s]?a[-\s]?100$", InterfaceFamily.HSK, "HSK-A100")
_add(r"^hsk[-\s]?a[-\s]?80$",  InterfaceFamily.HSK, "HSK-A80")
_add(r"^hsk[-\s]?a[-\s]?63$",  InterfaceFamily.HSK, "HSK-A63")
_add(r"^hsk[-\s]?a[-\s]?50$",  InterfaceFamily.HSK, "HSK-A50")
_add(r"^hsk[-\s]?e[-\s]?40$",  InterfaceFamily.HSK, "HSK-E40")
_add(r"^hsk[-\s]?e[-\s]?25$",  InterfaceFamily.HSK, "HSK-E25")
_add(r"^hsk[-\s]?f[-\s]?63$",  InterfaceFamily.HSK, "HSK-F63")
_add(r"^hsk[-\s]?f[-\s]?50$",  InterfaceFamily.HSK, "HSK-F50")

# SK (DIN 69871 / ISO 7388-1) — also "ISO-40", "ISO40"
_add(r"^(sk|iso)[-\s]?50$",    InterfaceFamily.SK, "SK-50")
_add(r"^(sk|iso)[-\s]?40$",    InterfaceFamily.SK, "SK-40")
_add(r"^(sk|iso)[-\s]?30$",    InterfaceFamily.SK, "SK-30")

# Capto (Sandvik Coromant)
_add(r"^(capto[-\s]?)?c[-\s]?10$", InterfaceFamily.CAPTO, "C10")
_add(r"^(capto[-\s]?)?c[-\s]?8$",  InterfaceFamily.CAPTO, "C8")
_add(r"^(capto[-\s]?)?c[-\s]?6$",  InterfaceFamily.CAPTO, "C6")
_add(r"^(capto[-\s]?)?c[-\s]?5$",  InterfaceFamily.CAPTO, "C5")
_add(r"^(capto[-\s]?)?c[-\s]?4$",  InterfaceFamily.CAPTO, "C4")

# KM (Kennametal)
_add(r"^km[-\s]?\d+$", InterfaceFamily.KM)

# VDI turret (DIN 69880) — dynamic canonical
_add(r"^vdi[-\s]?\d+$", InterfaceFamily.VDI)

# Lathe chuck / collet
_add(r"^lathe[-_\s]?chuck$",   InterfaceFamily.LATHE_CHUCK, "LATHE_CHUCK")
_add(r"^chuck$",               InterfaceFamily.LATHE_CHUCK, "LATHE_CHUCK")
_add(r"^collet$",              InterfaceFamily.COLLET, "COLLET")
_add(r"^er[-\s]?\d+$",         InterfaceFamily.COLLET)   # ER16, ER32, etc.

# No spindle / non-rotating machines
_add(
    r"^(no[-_\s]?spindle|n/a|none|edm|wire[-_\s]?edm|sinker[-_\s]?edm)$",
    InterfaceFamily.NO_SPINDLE,
    "NO_SPINDLE",
)


def normalize_interface_string(
    raw: str | None,
    *,
    source_note: str = "",
    verification_status: InterfaceVerificationStatus = (
        InterfaceVerificationStatus.MANUFACTURER_CONFIRMED
    ),
) -> NormalizedMachineInterface:
    """Return NormalizedMachineInterface from a raw interface string.

    None / blank input returns UNKNOWN family.
    Unrecognised strings are preserved with UNVERIFIED status.
    The caller-supplied verification_status applies only when a rule matches.
    """
    if raw is None or not raw.strip():
        return NormalizedMachineInterface(
            family=InterfaceFamily.UNKNOWN,
            designation="UNKNOWN",
            raw_input=raw or "",
            verification_status=InterfaceVerificationStatus.UNKNOWN,
            source_note=source_note,
        )

    stripped = raw.strip()
    for rule in _RULES:
        if rule.pattern.match(stripped):
            canonical = rule.canonical if rule.canonical else stripped.upper()
            return NormalizedMachineInterface(
                family=rule.family,
                designation=canonical,
                raw_input=stripped,
                verification_status=verification_status,
                source_note=source_note,
            )

    # No rule matched — preserve raw with UNVERIFIED
    return NormalizedMachineInterface(
        family=InterfaceFamily.UNKNOWN,
        designation=stripped,
        raw_input=stripped,
        verification_status=InterfaceVerificationStatus.UNVERIFIED,
        source_note=source_note,
    )


def check_interface_compatibility(
    machine_interface: NormalizedMachineInterface,
    tool_interface: NormalizedMachineInterface,
) -> InterfaceCompatibilityResult:
    """Return PASS, FAIL, or UNKNOWN for machine spindle vs tool-holder.

    Rules (fail-closed — ties resolve to UNKNOWN, not PASS):
    - NO_SPINDLE on either side → FAIL.
    - Either UNKNOWN family → UNKNOWN (never PASS).
    - Different families → FAIL.
    - Same family, same canonical designation → PASS.
    - Same family, different designation (size mismatch) → FAIL.
    """
    mi = machine_interface
    ti = tool_interface

    if (
        mi.family is InterfaceFamily.NO_SPINDLE
        or ti.family is InterfaceFamily.NO_SPINDLE
    ):
        return InterfaceCompatibilityResult(
            verdict=CompatibilityVerdict.FAIL,
            machine_interface=mi,
            tool_interface=ti,
            reason="NO_SPINDLE interface cannot accept a tool holder",
        )

    if (
        mi.family is InterfaceFamily.UNKNOWN
        or ti.family is InterfaceFamily.UNKNOWN
    ):
        return InterfaceCompatibilityResult(
            verdict=CompatibilityVerdict.UNKNOWN,
            machine_interface=mi,
            tool_interface=ti,
            reason="UNKNOWN interface — cannot determine compatibility",
        )

    if mi.family is not ti.family:
        return InterfaceCompatibilityResult(
            verdict=CompatibilityVerdict.FAIL,
            machine_interface=mi,
            tool_interface=ti,
            reason=f"Interface family mismatch: {mi.family} vs {ti.family}",
        )

    if mi.designation == ti.designation:
        return InterfaceCompatibilityResult(
            verdict=CompatibilityVerdict.PASS,
            machine_interface=mi,
            tool_interface=ti,
            reason=f"Compatible: {mi.designation}",
        )

    return InterfaceCompatibilityResult(
        verdict=CompatibilityVerdict.FAIL,
        machine_interface=mi,
        tool_interface=ti,
        reason=(
            f"Interface size mismatch: machine={mi.designation}, "
            f"tool={ti.designation}"
        ),
    )
