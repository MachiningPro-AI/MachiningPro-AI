"""Enumerations for the Machine Library domain.

Canonical string values match industry convention.
MachineClass values intentionally include numeric prefixes
(e.g. "3_AXIS_VMC") — Python attribute names differ from values.
"""

from __future__ import annotations

from enum import StrEnum


class MachineClass(StrEnum):
    """Supported CNC machine classes in the Machine Library."""

    THREE_AXIS_VMC = "3_AXIS_VMC"
    FOUR_AXIS_VMC = "4_AXIS_VMC"
    FIVE_AXIS_VMC = "5_AXIS_VMC"
    HMC = "HMC"
    CNC_LATHE = "CNC_LATHE"
    TURN_MILL = "TURN_MILL"
    SWISS_LATHE = "SWISS_LATHE"
    DRILL_TAP_CENTER = "DRILL_TAP_CENTER"
    SURFACE_GRINDER = "SURFACE_GRINDER"
    CYLINDRICAL_GRINDER = "CYLINDRICAL_GRINDER"
    WIRE_EDM = "WIRE_EDM"
    SINKER_EDM = "SINKER_EDM"


class MachineCatalogStatus(StrEnum):
    """Lifecycle status of a machine catalog entry."""

    ACTIVE = "ACTIVE"
    DISCONTINUED = "DISCONTINUED"
    PROTOTYPE = "PROTOTYPE"
    UNKNOWN = "UNKNOWN"


class AxisType(StrEnum):
    """Classification of a CNC axis."""

    LINEAR = "LINEAR"
    ROTARY = "ROTARY"


class EvidenceGrade(StrEnum):
    """Evidence quality tier for machine specifications.

    MANUFACTURER_DATASHEET is the highest credible grade for
    catalog entries.  ESTIMATED must never override a measured value.
    """

    MANUFACTURER_DATASHEET = "MANUFACTURER_DATASHEET"
    DISTRIBUTOR_SPEC_SHEET = "DISTRIBUTOR_SPEC_SHEET"
    LITERATURE_REFERENCE = "LITERATURE_REFERENCE"
    INTERNAL_MEASURED = "INTERNAL_MEASURED"
    ESTIMATED = "ESTIMATED"
    UNKNOWN = "UNKNOWN"
