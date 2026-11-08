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

L = LibraryMachineClass
S = SchedulingMachineClass


class TestLibraryToScheduling:
    """library_to_scheduling() / library_to_runtime()"""

    def test_three_axis_vmc(self):
        assert library_to_scheduling(L.THREE_AXIS_VMC) == S.VMC_3AXIS

    def test_four_axis_vmc(self):
        assert library_to_scheduling(L.FOUR_AXIS_VMC) == S.VMC_4AXIS

    def test_five_axis_vmc(self):
        assert library_to_scheduling(L.FIVE_AXIS_VMC) == S.VMC_5AXIS

    def test_hmc(self):
        assert library_to_scheduling(L.HMC) == S.HMC_3AXIS

    def test_cnc_lathe(self):
        assert library_to_scheduling(L.CNC_LATHE) == S.LATHE_2AXIS

    def test_turn_mill(self):
        assert library_to_scheduling(L.TURN_MILL) == S.TURN_MILL

    def test_swiss_lathe(self):
        assert library_to_scheduling(L.SWISS_LATHE) == S.LATHE_LIVE_TOOL

    def test_drill_tap_center(self):
        assert library_to_scheduling(L.DRILL_TAP_CENTER) == S.VMC_3AXIS

    def test_surface_grinder(self):
        assert library_to_scheduling(L.SURFACE_GRINDER) == S.GRINDER

    def test_cylindrical_grinder(self):
        assert library_to_scheduling(L.CYLINDRICAL_GRINDER) == S.GRINDER

    def test_wire_edm(self):
        assert library_to_scheduling(L.WIRE_EDM) == S.WIRE_EDM

    def test_sinker_edm_fails_closed(self):
        with pytest.raises(MachineClassMapError):
            library_to_scheduling(L.SINKER_EDM)

    def test_sinker_edm_error_message_mentions_no_scheduling_lane(self):
        with pytest.raises(MachineClassMapError, match="no scheduling equivalent"):
            library_to_scheduling(L.SINKER_EDM)


class TestSchedulingToLibrary:
    """scheduling_to_library() / runtime_to_library()"""

    def test_vmc_3axis(self):
        assert scheduling_to_library(S.VMC_3AXIS) == L.THREE_AXIS_VMC

    def test_vmc_4axis(self):
        assert scheduling_to_library(S.VMC_4AXIS) == L.FOUR_AXIS_VMC

    def test_vmc_5axis(self):
        assert scheduling_to_library(S.VMC_5AXIS) == L.FIVE_AXIS_VMC

    def test_hmc_3axis(self):
        assert scheduling_to_library(S.HMC_3AXIS) == L.HMC

    def test_hmc_4axis(self):
        assert scheduling_to_library(S.HMC_4AXIS) == L.HMC

    def test_lathe_2axis(self):
        assert scheduling_to_library(S.LATHE_2AXIS) == L.CNC_LATHE

    def test_lathe_live_tool(self):
        assert scheduling_to_library(S.LATHE_LIVE_TOOL) == L.CNC_LATHE

    def test_turn_mill(self):
        assert scheduling_to_library(S.TURN_MILL) == L.TURN_MILL

    def test_wire_edm(self):
        assert scheduling_to_library(S.WIRE_EDM) == L.WIRE_EDM

    def test_grinder_fails_closed_ambiguous(self):
        with pytest.raises(MachineClassMapError):
            scheduling_to_library(S.GRINDER)

    def test_grinder_error_message_mentions_ambiguity(self):
        with pytest.raises(MachineClassMapError, match="ambiguous"):
            scheduling_to_library(S.GRINDER)

    def test_unknown_fails_closed(self):
        with pytest.raises(MachineClassMapError):
            scheduling_to_library(S.UNKNOWN)

    def test_unknown_error_message_mentions_sentinel(self):
        with pytest.raises(MachineClassMapError, match="sentinel"):
            scheduling_to_library(S.UNKNOWN)


class TestAliases:
    """library_to_runtime and runtime_to_library are canonical aliases."""

    def test_library_to_runtime_is_alias(self):
        assert library_to_runtime is library_to_scheduling

    def test_runtime_to_library_is_alias(self):
        assert runtime_to_library is scheduling_to_library

    def test_library_to_runtime_works(self):
        assert library_to_runtime(L.THREE_AXIS_VMC) == S.VMC_3AXIS

    def test_runtime_to_library_works(self):
        assert runtime_to_library(S.VMC_3AXIS) == L.THREE_AXIS_VMC


class TestRoundTrips:
    """Symmetric pairs should round-trip without error."""

    @pytest.mark.parametrize("lib_cls", [
        L.THREE_AXIS_VMC,
        L.FOUR_AXIS_VMC,
        L.FIVE_AXIS_VMC,
        L.TURN_MILL,
        L.WIRE_EDM,
    ])
    def test_roundtrip_library_to_scheduling_back(self, lib_cls):
        sched = library_to_scheduling(lib_cls)
        back = scheduling_to_library(sched)
        assert back == lib_cls

    @pytest.mark.parametrize("sched_cls", [
        S.VMC_3AXIS,
        S.VMC_4AXIS,
        S.VMC_5AXIS,
        S.LATHE_2AXIS,
        S.TURN_MILL,
        S.WIRE_EDM,
    ])
    def test_roundtrip_scheduling_to_library_back(self, sched_cls):
        lib = scheduling_to_library(sched_cls)
        back = library_to_scheduling(lib)
        assert back == sched_cls


class TestNonRoundTripLossy:
    """Mappings that are intentionally lossy (many-to-one) must not round-trip."""

    def test_hmc_4axis_does_not_roundtrip(self):
        lib = scheduling_to_library(S.HMC_4AXIS)
        back = library_to_scheduling(lib)
        # lossy: 4-axis collapses to 3-axis
        assert back == S.HMC_3AXIS

    def test_swiss_lathe_does_not_roundtrip_to_live_tool(self):
        sched = library_to_scheduling(L.SWISS_LATHE)
        back = scheduling_to_library(sched)
        # lossy: LATHE_LIVE_TOOL maps back to CNC_LATHE, not SWISS_LATHE
        assert back == L.CNC_LATHE

    def test_drill_tap_center_does_not_roundtrip(self):
        sched = library_to_scheduling(L.DRILL_TAP_CENTER)
        back = scheduling_to_library(sched)
        # lossy: collapses to 3-axis VMC
        assert back == L.THREE_AXIS_VMC


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
        raises = [c for c in LibraryMachineClass if _raises(library_to_scheduling, c)]
        assert raises == [L.SINKER_EDM], (
            f"Expected only SINKER_EDM to raise, got: {[c.value for c in raises]}"
        )

    def test_exactly_two_scheduling_values_raise(self):
        raises = [c for c in SchedulingMachineClass if _raises(scheduling_to_library, c)]
        assert set(raises) == {S.GRINDER, S.UNKNOWN}, (
            f"Expected GRINDER+UNKNOWN to raise, got: {[c.value for c in raises]}"
        )


def _raises(fn, arg) -> bool:
    """Return True if fn(arg) raises MachineClassMapError."""
    try:
        fn(arg)
        return False
    except MachineClassMapError:
        return True
