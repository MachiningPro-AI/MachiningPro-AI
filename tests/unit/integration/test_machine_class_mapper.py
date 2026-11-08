"""Tests for the MachineClass cross-mapper (library ↔ scheduling)."""
import pytest

from backend.integration.machine_class_mapper import (
    MachineClassMapError,
    library_to_runtime,
    library_to_scheduling,
    runtime_to_library,
    scheduling_to_library,
)
from backend.machine_library.enums import MachineClass as LibraryMachineClass
from backend.scheduling.enums import MachineClass as SchedulingMachineClass


class TestLibraryToScheduling:
    """library_to_scheduling() / library_to_runtime()"""

    def test_three_axis_vmc(self):
        assert library_to_scheduling(LibraryMachineClass.THREE_AXIS_VMC) == SchedulingMachineClass.VMC_3AXIS

    def test_four_axis_vmc(self):
        assert library_to_scheduling(LibraryMachineClass.FOUR_AXIS_VMC) == SchedulingMachineClass.VMC_4AXIS

    def test_five_axis_vmc(self):
        assert library_to_scheduling(LibraryMachineClass.FIVE_AXIS_VMC) == SchedulingMachineClass.VMC_5AXIS

    def test_hmc(self):
        assert library_to_scheduling(LibraryMachineClass.HMC) == SchedulingMachineClass.HMC_3AXIS

    def test_cnc_lathe(self):
        assert library_to_scheduling(LibraryMachineClass.CNC_LATHE) == SchedulingMachineClass.LATHE_2AXIS

    def test_turn_mill(self):
        assert library_to_scheduling(LibraryMachineClass.TURN_MILL) == SchedulingMachineClass.TURN_MILL

    def test_swiss_lathe(self):
        assert library_to_scheduling(LibraryMachineClass.SWISS_LATHE) == SchedulingMachineClass.LATHE_LIVE_TOOL

    def test_drill_tap_center(self):
        assert library_to_scheduling(LibraryMachineClass.DRILL_TAP_CENTER) == SchedulingMachineClass.VMC_3AXIS

    def test_surface_grinder(self):
        assert library_to_scheduling(LibraryMachineClass.SURFACE_GRINDER) == SchedulingMachineClass.GRINDER

    def test_cylindrical_grinder(self):
        assert library_to_scheduling(LibraryMachineClass.CYLINDRICAL_GRINDER) == SchedulingMachineClass.GRINDER

    def test_wire_edm(self):
        assert library_to_scheduling(LibraryMachineClass.WIRE_EDM) == SchedulingMachineClass.WIRE_EDM

    def test_sinker_edm_fails_closed(self):
        with pytest.raises(MachineClassMapError):
            library_to_scheduling(LibraryMachineClass.SINKER_EDM)

    def test_sinker_edm_error_message_mentions_no_scheduling_lane(self):
        with pytest.raises(MachineClassMapError, match="no scheduling equivalent"):
            library_to_scheduling(LibraryMachineClass.SINKER_EDM)


class TestSchedulingToLibrary:
    """scheduling_to_library() / runtime_to_library()"""

    def test_vmc_3axis(self):
        assert scheduling_to_library(SchedulingMachineClass.VMC_3AXIS) == LibraryMachineClass.THREE_AXIS_VMC

    def test_vmc_4axis(self):
        assert scheduling_to_library(SchedulingMachineClass.VMC_4AXIS) == LibraryMachineClass.FOUR_AXIS_VMC

    def test_vmc_5axis(self):
        assert scheduling_to_library(SchedulingMachineClass.VMC_5AXIS) == LibraryMachineClass.FIVE_AXIS_VMC

    def test_hmc_3axis(self):
        assert scheduling_to_library(SchedulingMachineClass.HMC_3AXIS) == LibraryMachineClass.HMC

    def test_hmc_4axis(self):
        assert scheduling_to_library(SchedulingMachineClass.HMC_4AXIS) == LibraryMachineClass.HMC

    def test_lathe_2axis(self):
        assert scheduling_to_library(SchedulingMachineClass.LATHE_2AXIS) == LibraryMachineClass.CNC_LATHE

    def test_lathe_live_tool(self):
        assert scheduling_to_library(SchedulingMachineClass.LATHE_LIVE_TOOL) == LibraryMachineClass.CNC_LATHE

    def test_turn_mill(self):
        assert scheduling_to_library(SchedulingMachineClass.TURN_MILL) == LibraryMachineClass.TURN_MILL

    def test_wire_edm(self):
        assert scheduling_to_library(SchedulingMachineClass.WIRE_EDM) == LibraryMachineClass.WIRE_EDM

    def test_grinder_fails_closed_ambiguous(self):
        with pytest.raises(MachineClassMapError):
            scheduling_to_library(SchedulingMachineClass.GRINDER)

    def test_grinder_error_message_mentions_ambiguity(self):
        with pytest.raises(MachineClassMapError, match="ambiguous"):
            scheduling_to_library(SchedulingMachineClass.GRINDER)

    def test_unknown_fails_closed(self):
        with pytest.raises(MachineClassMapError):
            scheduling_to_library(SchedulingMachineClass.UNKNOWN)

    def test_unknown_error_message_mentions_sentinel(self):
        with pytest.raises(MachineClassMapError, match="sentinel"):
            scheduling_to_library(SchedulingMachineClass.UNKNOWN)


class TestAliases:
    """library_to_runtime and runtime_to_library are canonical aliases."""

    def test_library_to_runtime_is_alias(self):
        assert library_to_runtime is library_to_scheduling

    def test_runtime_to_library_is_alias(self):
        assert runtime_to_library is scheduling_to_library

    def test_library_to_runtime_works(self):
        assert library_to_runtime(LibraryMachineClass.THREE_AXIS_VMC) == SchedulingMachineClass.VMC_3AXIS

    def test_runtime_to_library_works(self):
        assert runtime_to_library(SchedulingMachineClass.VMC_3AXIS) == LibraryMachineClass.THREE_AXIS_VMC


class TestRoundTrips:
    """Symmetric pairs should round-trip without error."""

    @pytest.mark.parametrize("lib_cls", [
        LibraryMachineClass.THREE_AXIS_VMC,
        LibraryMachineClass.FOUR_AXIS_VMC,
        LibraryMachineClass.FIVE_AXIS_VMC,
        LibraryMachineClass.TURN_MILL,
        LibraryMachineClass.WIRE_EDM,
    ])
    def test_roundtrip_library_to_scheduling_back(self, lib_cls):
        sched = library_to_scheduling(lib_cls)
        back = scheduling_to_library(sched)
        assert back == lib_cls

    @pytest.mark.parametrize("sched_cls", [
        SchedulingMachineClass.VMC_3AXIS,
        SchedulingMachineClass.VMC_4AXIS,
        SchedulingMachineClass.VMC_5AXIS,
        SchedulingMachineClass.LATHE_2AXIS,
        SchedulingMachineClass.TURN_MILL,
        SchedulingMachineClass.WIRE_EDM,
    ])
    def test_roundtrip_scheduling_to_library_back(self, sched_cls):
        lib = scheduling_to_library(sched_cls)
        back = library_to_scheduling(lib)
        assert back == sched_cls


class TestNonRoundTripLossy:
    """Mappings that are intentionally lossy (many-to-one) must not round-trip."""

    def test_hmc_4axis_does_not_roundtrip(self):
        lib = scheduling_to_library(SchedulingMachineClass.HMC_4AXIS)
        back = library_to_scheduling(lib)
        assert back == SchedulingMachineClass.HMC_3AXIS  # lossy: 4-axis collapses to 3-axis

    def test_swiss_lathe_does_not_roundtrip_to_live_tool(self):
        sched = library_to_scheduling(LibraryMachineClass.SWISS_LATHE)
        back = scheduling_to_library(sched)
        assert back == LibraryMachineClass.CNC_LATHE  # lossy: LATHE_LIVE_TOOL → CNC_LATHE (not SWISS_LATHE)

    def test_drill_tap_center_does_not_roundtrip(self):
        sched = library_to_scheduling(LibraryMachineClass.DRILL_TAP_CENTER)
        back = scheduling_to_library(sched)
        assert back == LibraryMachineClass.THREE_AXIS_VMC  # lossy: collapses to 3-axis VMC


class TestTableCompleteness:
    """Every Library enum value is either mapped or explicitly fails closed."""

    def test_all_library_values_produce_a_result_or_map_error(self):
        for lib_cls in LibraryMachineClass:
            try:
                result = library_to_scheduling(lib_cls)
                assert isinstance(result, SchedulingMachineClass)
            except MachineClassMapError:
                pass  # explicitly unmappable — acceptable

    def test_all_scheduling_values_produce_a_result_or_map_error(self):
        for sched_cls in SchedulingMachineClass:
            try:
                result = scheduling_to_library(sched_cls)
                assert isinstance(result, LibraryMachineClass)
            except MachineClassMapError:
                pass  # explicitly unmappable — acceptable

    def test_exactly_one_library_value_raises(self):
        raises = [
            lib_cls for lib_cls in LibraryMachineClass
            if _raises(library_to_scheduling, lib_cls)
        ]
        assert raises == [LibraryMachineClass.SINKER_EDM], (
            f"Expected only SINKER_EDM to raise, got: {[c.value for c in raises]}"
        )

    def test_exactly_two_scheduling_values_raise(self):
        raises = [
            sc for sc in SchedulingMachineClass
            if _raises(scheduling_to_library, sc)
        ]
        assert set(raises) == {SchedulingMachineClass.GRINDER, SchedulingMachineClass.UNKNOWN}, (
            f"Expected GRINDER+UNKNOWN to raise, got: {[c.value for c in raises]}"
        )


def _raises(fn, arg) -> bool:
    """Return True if fn(arg) raises MachineClassMapError."""
    try:
        fn(arg)
        return False
    except MachineClassMapError:
        return True
