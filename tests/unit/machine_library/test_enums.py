"""Tests for backend.machine_library.enums."""

import pytest

from backend.machine_library.enums import (
    AxisType,
    EvidenceGrade,
    MachineCatalogStatus,
    MachineClass,
)

# ---------------------------------------------------------------------------
# MachineClass — all 12 required values
# ---------------------------------------------------------------------------

class TestMachineClass:
    def test_three_axis_vmc_value(self):
        assert MachineClass.THREE_AXIS_VMC.value == "3_AXIS_VMC"

    def test_four_axis_vmc_value(self):
        assert MachineClass.FOUR_AXIS_VMC.value == "4_AXIS_VMC"

    def test_five_axis_vmc_value(self):
        assert MachineClass.FIVE_AXIS_VMC.value == "5_AXIS_VMC"

    def test_hmc_value(self):
        assert MachineClass.HMC.value == "HMC"

    def test_cnc_lathe_value(self):
        assert MachineClass.CNC_LATHE.value == "CNC_LATHE"

    def test_turn_mill_value(self):
        assert MachineClass.TURN_MILL.value == "TURN_MILL"

    def test_swiss_lathe_value(self):
        assert MachineClass.SWISS_LATHE.value == "SWISS_LATHE"

    def test_drill_tap_center_value(self):
        assert MachineClass.DRILL_TAP_CENTER.value == "DRILL_TAP_CENTER"

    def test_surface_grinder_value(self):
        assert MachineClass.SURFACE_GRINDER.value == "SURFACE_GRINDER"

    def test_cylindrical_grinder_value(self):
        assert MachineClass.CYLINDRICAL_GRINDER.value == "CYLINDRICAL_GRINDER"

    def test_wire_edm_value(self):
        assert MachineClass.WIRE_EDM.value == "WIRE_EDM"

    def test_sinker_edm_value(self):
        assert MachineClass.SINKER_EDM.value == "SINKER_EDM"

    def test_all_12_classes_present(self):
        values = {mc.value for mc in MachineClass}
        expected = {
            "3_AXIS_VMC", "4_AXIS_VMC", "5_AXIS_VMC", "HMC",
            "CNC_LATHE", "TURN_MILL", "SWISS_LATHE", "DRILL_TAP_CENTER",
            "SURFACE_GRINDER", "CYLINDRICAL_GRINDER", "WIRE_EDM", "SINKER_EDM",
        }
        assert values == expected

    def test_count_exactly_12(self):
        assert len(MachineClass) == 12

    def test_str_enum_serializes_to_value(self):
        assert str(MachineClass.HMC) == "HMC"
        assert str(MachineClass.THREE_AXIS_VMC) == "3_AXIS_VMC"

    def test_lookup_by_value(self):
        assert MachineClass("3_AXIS_VMC") is MachineClass.THREE_AXIS_VMC
        assert MachineClass("SINKER_EDM") is MachineClass.SINKER_EDM

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            MachineClass("NONEXISTENT")


# ---------------------------------------------------------------------------
# MachineCatalogStatus
# ---------------------------------------------------------------------------

class TestMachineCatalogStatus:
    def test_active(self):
        assert MachineCatalogStatus.ACTIVE.value == "ACTIVE"

    def test_discontinued(self):
        assert MachineCatalogStatus.DISCONTINUED.value == "DISCONTINUED"

    def test_prototype(self):
        assert MachineCatalogStatus.PROTOTYPE.value == "PROTOTYPE"

    def test_unknown(self):
        assert MachineCatalogStatus.UNKNOWN.value == "UNKNOWN"

    def test_count(self):
        assert len(MachineCatalogStatus) == 4


# ---------------------------------------------------------------------------
# AxisType
# ---------------------------------------------------------------------------

class TestAxisType:
    def test_linear(self):
        assert AxisType.LINEAR.value == "LINEAR"

    def test_rotary(self):
        assert AxisType.ROTARY.value == "ROTARY"


# ---------------------------------------------------------------------------
# EvidenceGrade
# ---------------------------------------------------------------------------

class TestEvidenceGrade:
    def test_manufacturer_datasheet(self):
        assert EvidenceGrade.MANUFACTURER_DATASHEET.value == "MANUFACTURER_DATASHEET"

    def test_estimated(self):
        assert EvidenceGrade.ESTIMATED.value == "ESTIMATED"

    def test_unknown(self):
        assert EvidenceGrade.UNKNOWN.value == "UNKNOWN"
