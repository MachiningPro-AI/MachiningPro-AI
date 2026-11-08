"""MachineClass cross-mapper: machine_library ↔ scheduling.

Translates between backend.machine_library.enums.MachineClass (library namespace,
e.g. '3_AXIS_VMC') and backend.scheduling.enums.MachineClass (runtime namespace,
e.g. 'VMC_3AXIS') using explicit lookup tables only.

Design constraints:
  EXPLICIT_ONLY=YES          — no string heuristics, no replace/startswith/contains
  FAIL_CLOSED=YES            — unknown or ambiguous input raises MachineClassMapError
  FABRICATED_MAPPING=NO      — every entry is backed by documented machine taxonomy
  SINKER_EDM_UNMAPPABLE=YES  — no scheduling equivalent; raises on attempt
  GRINDER_AMBIGUOUS=YES      — GRINDER→library is ambiguous; raises on attempt
  LIBRARY_UNCHANGED=YES      — mapper never modifies library or scheduling enums
"""
from __future__ import annotations

from backend.machine_library.enums import MachineClass as _LibraryMachineClass
from backend.scheduling.enums import MachineClass as _SchedulingMachineClass

__all__ = [
    "MachineClassMapError",
    "library_to_scheduling",
    "scheduling_to_library",
    "library_to_runtime",
    "runtime_to_library",
]


class MachineClassMapError(ValueError):
    """Raised when a MachineClass value cannot be unambiguously mapped."""


# ---------------------------------------------------------------------------
# Explicit lookup tables — maintained manually; no dynamic generation.
# Comments document WHY each mapping is chosen, not just WHAT it is.
# ---------------------------------------------------------------------------

# Library → Scheduling
# - HMC: library has one generic HMC value; scheduling distinguishes 3-axis vs
#   4-axis.  Library HMC records are predominantly 3-axis (all 28 seed records
#   that carry MachineClass.HMC have 3-axis spindle geometry), so HMC_3AXIS is
#   the correct conservative mapping.  Callers that need HMC_4AXIS must resolve
#   via stable_id lookup in MachinePipelineAdapter and check axis count directly.
# - SWISS_LATHE → LATHE_LIVE_TOOL: Swiss lathes have live tooling by definition.
# - DRILL_TAP_CENTER → VMC_3AXIS: drill/tap centers share the same 3-axis
#   scheduling path; they differ only in spindle speed range, not job routing.
# - SURFACE_GRINDER / CYLINDRICAL_GRINDER → GRINDER: scheduling uses one
#   generic GRINDER class; the sub-type distinction lives in the library record.
# - SINKER_EDM: scheduling has no SINKER_EDM lane; raises MachineClassMapError.
_LIBRARY_TO_SCHEDULING: dict[_LibraryMachineClass, _SchedulingMachineClass] = {
    _LibraryMachineClass.THREE_AXIS_VMC:    _SchedulingMachineClass.VMC_3AXIS,
    _LibraryMachineClass.FOUR_AXIS_VMC:     _SchedulingMachineClass.VMC_4AXIS,
    _LibraryMachineClass.FIVE_AXIS_VMC:     _SchedulingMachineClass.VMC_5AXIS,
    _LibraryMachineClass.HMC:               _SchedulingMachineClass.HMC_3AXIS,
    _LibraryMachineClass.CNC_LATHE:         _SchedulingMachineClass.LATHE_2AXIS,
    _LibraryMachineClass.TURN_MILL:         _SchedulingMachineClass.TURN_MILL,
    _LibraryMachineClass.SWISS_LATHE:       _SchedulingMachineClass.LATHE_LIVE_TOOL,
    _LibraryMachineClass.DRILL_TAP_CENTER:  _SchedulingMachineClass.VMC_3AXIS,
    _LibraryMachineClass.SURFACE_GRINDER:   _SchedulingMachineClass.GRINDER,
    _LibraryMachineClass.CYLINDRICAL_GRINDER: _SchedulingMachineClass.GRINDER,
    _LibraryMachineClass.WIRE_EDM:          _SchedulingMachineClass.WIRE_EDM,
    # _LibraryMachineClass.SINKER_EDM: intentionally absent — no scheduling lane
}

# Scheduling → Library
# - HMC_3AXIS / HMC_4AXIS both map to HMC: library has one generic HMC value.
# - LATHE_LIVE_TOOL → CNC_LATHE: live-tool lathes are catalogued as CNC_LATHE in
#   the library (Swiss-specific identity is a stable_id attribute, not a class).
# - GRINDER is ambiguous (surface vs cylindrical); raises MachineClassMapError.
# - UNKNOWN: scheduling's sentinel value; never maps to a library class.
_SCHEDULING_TO_LIBRARY: dict[_SchedulingMachineClass, _LibraryMachineClass] = {
    _SchedulingMachineClass.VMC_3AXIS:      _LibraryMachineClass.THREE_AXIS_VMC,
    _SchedulingMachineClass.VMC_4AXIS:      _LibraryMachineClass.FOUR_AXIS_VMC,
    _SchedulingMachineClass.VMC_5AXIS:      _LibraryMachineClass.FIVE_AXIS_VMC,
    _SchedulingMachineClass.HMC_3AXIS:      _LibraryMachineClass.HMC,
    _SchedulingMachineClass.HMC_4AXIS:      _LibraryMachineClass.HMC,
    _SchedulingMachineClass.LATHE_2AXIS:    _LibraryMachineClass.CNC_LATHE,
    _SchedulingMachineClass.LATHE_LIVE_TOOL: _LibraryMachineClass.CNC_LATHE,
    _SchedulingMachineClass.TURN_MILL:      _LibraryMachineClass.TURN_MILL,
    _SchedulingMachineClass.WIRE_EDM:       _LibraryMachineClass.WIRE_EDM,
    # _SchedulingMachineClass.GRINDER:  absent — ambiguous (surface vs cylindrical)
    # _SchedulingMachineClass.UNKNOWN:  absent — sentinel, never a library class
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def library_to_scheduling(
    lib_class: _LibraryMachineClass,
) -> _SchedulingMachineClass:
    """Map a library MachineClass to its scheduling equivalent.

    Raises MachineClassMapError when no unambiguous scheduling lane exists
    (currently: SINKER_EDM has no scheduling equivalent).
    """
    result = _LIBRARY_TO_SCHEDULING.get(lib_class)
    if result is None:
        raise MachineClassMapError(
            f"Library MachineClass {lib_class.value!r} has no scheduling equivalent. "
            "Cannot map SINKER_EDM to a scheduling lane — caller must handle this "
            "machine class explicitly."
        )
    return result


def scheduling_to_library(
    sched_class: _SchedulingMachineClass,
) -> _LibraryMachineClass:
    """Map a scheduling MachineClass to its library equivalent.

    Raises MachineClassMapError for ambiguous or unmappable values:
      - GRINDER: could be SURFACE_GRINDER or CYLINDRICAL_GRINDER
      - UNKNOWN: sentinel value, not a physical machine class
    """
    result = _SCHEDULING_TO_LIBRARY.get(sched_class)
    if result is None:
        if sched_class is _SchedulingMachineClass.GRINDER:
            raise MachineClassMapError(
                "Scheduling MachineClass 'GRINDER' is ambiguous: library distinguishes "
                "SURFACE_GRINDER from CYLINDRICAL_GRINDER. "
                "Resolve via MachinePipelineAdapter.lookup() and inspect the record."
            )
        raise MachineClassMapError(
            f"Scheduling MachineClass {sched_class.value!r} cannot be mapped to a "
            "library class. UNKNOWN is a sentinel and has no library equivalent."
        )
    return result


# Canonical aliases matching the task spec names
library_to_runtime = library_to_scheduling
runtime_to_library = scheduling_to_library
