"""Tests for backend.machine_library.models."""


from backend.machine_library.enums import (
    AxisType,
    EvidenceGrade,
    MachineCatalogStatus,
    MachineClass,
)
from backend.machine_library.models import (
    MachineAxisSpecification,
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_cap(machine_class: MachineClass = MachineClass.THREE_AXIS_VMC) -> MachineCapability:
    return MachineCapability(
        machine_class=machine_class,
        controlled_axes=3,
        milling_capable=True,
        drilling_capable=True,
    )


def _minimal_spindle() -> MachineSpindleSpecification:
    return MachineSpindleSpecification(max_rpm=10_000, power_kw=11.0)


def _minimal_envelope() -> MachineEnvelope:
    return MachineEnvelope(travel_x_mm=600.0, travel_y_mm=400.0, travel_z_mm=400.0)


def _minimal_source() -> MachineSourceMetadata:
    return MachineSourceMetadata(source_title="Test Source")


def _minimal_record(stable_id: str = "test-001") -> MachineCatalogRecord:
    return MachineCatalogRecord(
        stable_id=stable_id,
        manufacturer="Test Mfr",
        model="Test Model",
        capability=_minimal_cap(),
        spindle=_minimal_spindle(),
        envelope=_minimal_envelope(),
        source=_minimal_source(),
    )


# ---------------------------------------------------------------------------
# MachineAxisSpecification
# ---------------------------------------------------------------------------

class TestMachineAxisSpecification:
    def test_linear_axis_construction(self):
        ax = MachineAxisSpecification(
            axis_label="X",
            axis_type=AxisType.LINEAR,
            travel_mm=600.0,
        )
        assert ax.axis_label == "X"
        assert ax.axis_type is AxisType.LINEAR
        assert ax.travel_mm == 600.0

    def test_rotary_axis_construction(self):
        ax = MachineAxisSpecification(
            axis_label="B",
            axis_type=AxisType.ROTARY,
            min_angle_deg=-110.0,
            max_angle_deg=110.0,
        )
        assert ax.axis_type is AxisType.ROTARY
        assert ax.min_angle_deg == -110.0
        assert ax.max_angle_deg == 110.0

    def test_optional_fields_default_none(self):
        ax = MachineAxisSpecification(axis_label="A", axis_type=AxisType.ROTARY)
        assert ax.travel_mm is None
        assert ax.min_angle_deg is None
        assert ax.max_angle_deg is None
        assert ax.positioning_accuracy_um is None


# ---------------------------------------------------------------------------
# MachineSpindleSpecification
# ---------------------------------------------------------------------------

class TestMachineSpindleSpecification:
    def test_full_construction(self):
        s = MachineSpindleSpecification(
            min_rpm=100,
            max_rpm=12_000,
            power_kw=22.4,
            power_continuous_kw=18.5,
            torque_nm=140.0,
            interface="CAT-40",
        )
        assert s.max_rpm == 12_000
        assert s.power_kw == 22.4
        assert s.interface == "CAT-40"

    def test_all_fields_optional(self):
        s = MachineSpindleSpecification()
        assert s.max_rpm is None
        assert s.power_kw is None
        assert s.interface is None
        assert s.interfaces_supported == []

    def test_interfaces_supported_list(self):
        s = MachineSpindleSpecification(
            interfaces_supported=["CAT-40", "BT-40"]
        )
        assert len(s.interfaces_supported) == 2


# ---------------------------------------------------------------------------
# MachineEnvelope
# ---------------------------------------------------------------------------

class TestMachineEnvelope:
    def test_prismatic_envelope(self):
        e = MachineEnvelope(
            travel_x_mm=762.0,
            travel_y_mm=406.0,
            travel_z_mm=508.0,
            table_load_kg=680.0,
        )
        assert e.travel_x_mm == 762.0
        assert e.table_load_kg == 680.0

    def test_turning_envelope(self):
        e = MachineEnvelope(
            max_turning_diameter_mm=381.0,
            max_turning_length_mm=549.0,
            bar_capacity_mm=65.0,
        )
        assert e.bar_capacity_mm == 65.0

    def test_rotary_axes_default_empty(self):
        e = MachineEnvelope()
        assert e.rotary_axes == []

    def test_rotary_axes_populated(self):
        ax_b = MachineAxisSpecification(
            axis_label="B", axis_type=AxisType.ROTARY
        )
        e = MachineEnvelope(rotary_axes=[ax_b])
        assert len(e.rotary_axes) == 1

    def test_all_optional_default_none(self):
        e = MachineEnvelope()
        assert e.travel_x_mm is None
        assert e.table_load_kg is None
        assert e.bar_capacity_mm is None


# ---------------------------------------------------------------------------
# MachineCapability
# ---------------------------------------------------------------------------

class TestMachineCapability:
    def test_has_primary_capability_milling(self):
        cap = MachineCapability(
            machine_class=MachineClass.THREE_AXIS_VMC,
            controlled_axes=3,
            milling_capable=True,
        )
        assert cap.has_primary_capability is True

    def test_has_primary_capability_turning(self):
        cap = MachineCapability(
            machine_class=MachineClass.CNC_LATHE,
            controlled_axes=2,
            turning_capable=True,
        )
        assert cap.has_primary_capability is True

    def test_has_primary_capability_grinding(self):
        cap = MachineCapability(
            machine_class=MachineClass.SURFACE_GRINDER,
            controlled_axes=3,
            grinding_capable=True,
        )
        assert cap.has_primary_capability is True

    def test_has_primary_capability_edm(self):
        cap = MachineCapability(
            machine_class=MachineClass.WIRE_EDM,
            controlled_axes=5,
            edm_capable=True,
        )
        assert cap.has_primary_capability is True

    def test_no_primary_capability(self):
        cap = MachineCapability(
            machine_class=MachineClass.THREE_AXIS_VMC,
            controlled_axes=3,
        )
        assert cap.has_primary_capability is False

    def test_defaults(self):
        cap = MachineCapability(
            machine_class=MachineClass.HMC,
            controlled_axes=4,
            milling_capable=True,
        )
        assert cap.has_subspindle is False
        assert cap.has_pallet_changer is False
        assert cap.flood_coolant is True
        assert cap.supported_processes == []


# ---------------------------------------------------------------------------
# MachineSourceMetadata
# ---------------------------------------------------------------------------

class TestMachineSourceMetadata:
    def test_construction(self):
        s = MachineSourceMetadata(
            source_title="Haas Automation (haas.com)",
            source_note="From public spec sheet",
        )
        assert s.source_title == "Haas Automation (haas.com)"
        assert s.evidence_grade is EvidenceGrade.MANUFACTURER_DATASHEET

    def test_optional_fields_none(self):
        s = MachineSourceMetadata(source_title="Test")
        assert s.source_url is None
        assert s.source_note is None
        assert s.verified_date is None


# ---------------------------------------------------------------------------
# MachineCatalogRecord
# ---------------------------------------------------------------------------

class TestMachineCatalogRecord:
    def test_minimal_construction(self):
        r = _minimal_record()
        assert r.stable_id == "test-001"
        assert r.manufacturer == "Test Mfr"
        assert r.catalog_status is MachineCatalogStatus.ACTIVE

    def test_machine_class_property(self):
        r = _minimal_record()
        assert r.machine_class is MachineClass.THREE_AXIS_VMC

    def test_missing_fields_no_spindle_rpm(self):
        r = MachineCatalogRecord(
            stable_id="missing-001",
            manufacturer="Mfr",
            model="Model",
            capability=_minimal_cap(),
            spindle=MachineSpindleSpecification(),   # all None
            envelope=_minimal_envelope(),
            source=_minimal_source(),
        )
        mf = r.missing_fields
        assert "spindle.max_rpm" in mf
        assert "spindle.power_kw" in mf

    def test_missing_fields_complete_spindle(self):
        r = MachineCatalogRecord(
            stable_id="full-001",
            manufacturer="Mfr",
            model="Model",
            capability=_minimal_cap(),
            spindle=MachineSpindleSpecification(
                min_rpm=100, max_rpm=10_000, power_kw=11.0,
                torque_nm=100.0, interface="CAT-40",
            ),
            envelope=MachineEnvelope(
                travel_x_mm=600.0,
                travel_y_mm=400.0,
                travel_z_mm=400.0,
                table_load_kg=500.0,
            ),
            source=_minimal_source(),
        )
        mf = r.missing_fields
        assert "spindle.max_rpm" not in mf
        assert "spindle.power_kw" not in mf

    def test_year_discontinued_optional(self):
        r = _minimal_record()
        assert r.year_introduced is None
        assert r.year_discontinued is None

    def test_country_of_origin_optional(self):
        r = _minimal_record()
        assert r.country_of_origin is None

    def test_lathe_record_construction(self):
        r = MachineCatalogRecord(
            stable_id="lathe-001",
            manufacturer="Haas",
            model="ST-20",
            capability=MachineCapability(
                machine_class=MachineClass.CNC_LATHE,
                controlled_axes=2,
                turning_capable=True,
                drilling_capable=True,
            ),
            spindle=MachineSpindleSpecification(max_rpm=4_000, power_kw=22.4),
            envelope=MachineEnvelope(
                max_turning_diameter_mm=381.0,
                max_turning_length_mm=549.0,
                bar_capacity_mm=65.0,
            ),
            source=MachineSourceMetadata(source_title="Haas"),
        )
        assert r.machine_class is MachineClass.CNC_LATHE
        assert r.envelope.bar_capacity_mm == 65.0
