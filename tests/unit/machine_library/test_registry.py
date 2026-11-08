"""Tests for backend.machine_library.registry."""

import pytest

from backend.machine_library.enums import MachineClass
from backend.machine_library.models import (
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)
from backend.machine_library.registry import MachineCatalogError, MachineCatalogRegistry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_record(
    stable_id: str,
    machine_class: MachineClass = MachineClass.THREE_AXIS_VMC,
    manufacturer: str = "Test Mfr",
) -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id=stable_id,
        manufacturer=manufacturer,
        model="Model",
        capability=MachineCapability(
            machine_class=machine_class,
            controlled_axes=3,
            milling_capable=True,
        ),
        spindle=MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0),
        envelope=MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0),
        source=MachineSourceMetadata(source_title="Test"),
    )


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class TestMachineCatalogRegistryRegistration:
    def test_register_returns_record(self):
        reg = MachineCatalogRegistry()
        r = _make_record("r-001")
        returned = reg.register(r)
        assert returned is r

    def test_register_stores_record(self):
        reg = MachineCatalogRegistry()
        r = _make_record("r-002")
        reg.register(r)
        assert reg.has("r-002")

    def test_duplicate_stable_id_raises(self):
        reg = MachineCatalogRegistry()
        reg.register(_make_record("dup-01"))
        with pytest.raises(MachineCatalogError, match="already registered"):
            reg.register(_make_record("dup-01"))

    def test_register_non_record_raises_type_error(self):
        reg = MachineCatalogRegistry()
        with pytest.raises(TypeError):
            reg.register("not-a-record")  # type: ignore[arg-type]

    def test_len_increases_on_register(self):
        reg = MachineCatalogRegistry()
        assert len(reg) == 0
        reg.register(_make_record("r-001"))
        assert len(reg) == 1
        reg.register(_make_record("r-002"))
        assert len(reg) == 2


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------

class TestMachineCatalogRegistryLookup:
    def test_get_registered(self):
        reg = MachineCatalogRegistry()
        r = _make_record("get-01")
        reg.register(r)
        assert reg.get("get-01") is r

    def test_get_missing_raises(self):
        reg = MachineCatalogRegistry()
        with pytest.raises(MachineCatalogError, match="no record"):
            reg.get("not-here")

    def test_has_true(self):
        reg = MachineCatalogRegistry()
        reg.register(_make_record("h-01"))
        assert reg.has("h-01") is True

    def test_has_false(self):
        reg = MachineCatalogRegistry()
        assert reg.has("absent") is False

    def test_contains_operator(self):
        reg = MachineCatalogRegistry()
        reg.register(_make_record("c-01"))
        assert "c-01" in reg
        assert "absent" not in reg


# ---------------------------------------------------------------------------
# Collection queries
# ---------------------------------------------------------------------------

class TestMachineCatalogRegistryQueries:
    def setup_method(self):
        self.reg = MachineCatalogRegistry()
        self.reg.register(_make_record("vmc-01", MachineClass.THREE_AXIS_VMC, "Haas"))
        self.reg.register(_make_record("vmc-02", MachineClass.THREE_AXIS_VMC, "DMG MORI"))
        self.reg.register(_make_record("lathe-01", MachineClass.CNC_LATHE, "Haas"))
        self.reg.register(_make_record("edm-01", MachineClass.WIRE_EDM, "Fanuc"))

    def test_find_by_class_returns_matching(self):
        result = self.reg.find_by_class(MachineClass.THREE_AXIS_VMC)
        assert len(result) == 2

    def test_find_by_class_empty_for_absent_class(self):
        result = self.reg.find_by_class(MachineClass.SWISS_LATHE)
        assert result == ()

    def test_find_by_class_sorted_by_stable_id(self):
        result = self.reg.find_by_class(MachineClass.THREE_AXIS_VMC)
        ids = [r.stable_id for r in result]
        assert ids == sorted(ids)

    def test_find_by_manufacturer_case_insensitive(self):
        haas_records = self.reg.find_by_manufacturer("haas")
        assert len(haas_records) == 2

    def test_find_by_manufacturer_no_match(self):
        result = self.reg.find_by_manufacturer("Mazak")
        assert result == ()

    def test_all_returns_all_sorted(self):
        all_records = self.reg.all()
        assert len(all_records) == 4
        ids = [r.stable_id for r in all_records]
        assert ids == sorted(ids)

    def test_stable_ids_registration_order(self):
        ids = self.reg.stable_ids()
        assert "vmc-01" in ids
        assert "lathe-01" in ids

    def test_classes_present(self):
        classes = self.reg.classes_present()
        assert MachineClass.THREE_AXIS_VMC in classes
        assert MachineClass.CNC_LATHE in classes
        assert MachineClass.WIRE_EDM in classes
        assert MachineClass.SWISS_LATHE not in classes

    def test_manufacturer_names_sorted(self):
        names = self.reg.manufacturer_names()
        assert names == tuple(sorted(names))
        assert "Haas" in names
        assert "Fanuc" in names

    def test_find_capable_milling(self):
        result = self.reg.find_capable(milling=True)
        assert len(result) >= 2


# ---------------------------------------------------------------------------
# Empty registry
# ---------------------------------------------------------------------------

class TestEmptyRegistry:
    def test_empty_all(self):
        reg = MachineCatalogRegistry()
        assert reg.all() == ()

    def test_empty_classes_present(self):
        reg = MachineCatalogRegistry()
        assert reg.classes_present() == frozenset()

    def test_empty_manufacturer_names(self):
        reg = MachineCatalogRegistry()
        assert reg.manufacturer_names() == ()
