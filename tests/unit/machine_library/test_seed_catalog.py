"""Tests for backend.machine_library.seed_catalog."""


from backend.machine_library.enums import MachineClass
from backend.machine_library.models import MachineCatalogRecord
from backend.machine_library.seed_catalog import (
    MACHINE_LIBRARY_RECORDS,
    seed_machine_library,
)
from backend.machine_library.validation import validate_machine_catalog_record

# ---------------------------------------------------------------------------
# Basic catalog integrity
# ---------------------------------------------------------------------------

class TestSeedCatalogBasics:
    def test_seed_returns_list(self):
        records = seed_machine_library()
        assert isinstance(records, list)

    def test_seed_returns_correct_type(self):
        records = seed_machine_library()
        assert all(isinstance(r, MachineCatalogRecord) for r in records)

    def test_seed_has_28_records(self):
        records = seed_machine_library()
        assert len(records) == 28

    def test_constant_and_function_agree(self):
        assert len(MACHINE_LIBRARY_RECORDS) == len(seed_machine_library())

    def test_seed_is_idempotent(self):
        a = seed_machine_library()
        b = seed_machine_library()
        ids_a = [r.stable_id for r in a]
        ids_b = [r.stable_id for r in b]
        assert ids_a == ids_b

    def test_seed_returns_fresh_copy(self):
        a = seed_machine_library()
        b = seed_machine_library()
        assert a is not b


# ---------------------------------------------------------------------------
# Stable ID uniqueness
# ---------------------------------------------------------------------------

class TestSeedCatalogIds:
    def test_all_stable_ids_unique(self):
        records = seed_machine_library()
        ids = [r.stable_id for r in records]
        assert len(ids) == len(set(ids))

    def test_all_stable_ids_non_empty(self):
        for r in seed_machine_library():
            assert r.stable_id.strip() != ""

    def test_all_ids_start_with_ml_prefix(self):
        for r in seed_machine_library():
            assert r.stable_id.startswith("ml-"), (
                f"stable_id {r.stable_id!r} does not start with 'ml-'"
            )


# ---------------------------------------------------------------------------
# All 12 MachineClass values represented
# ---------------------------------------------------------------------------

class TestSeedCatalogCoverage:
    def test_all_12_machine_classes_present(self):
        classes = {r.capability.machine_class for r in seed_machine_library()}
        for mc in MachineClass:
            assert mc in classes, f"MachineClass.{mc.name} not in seed catalog"

    def test_three_axis_vmc_has_at_least_2_records(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.THREE_AXIS_VMC]
        assert len(recs) >= 2

    def test_five_axis_vmc_has_at_least_2_records(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.FIVE_AXIS_VMC]
        assert len(recs) >= 2

    def test_cnc_lathe_has_at_least_2_records(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.CNC_LATHE]
        assert len(recs) >= 2

    def test_turn_mill_has_at_least_2_records(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.TURN_MILL]
        assert len(recs) >= 2

    def test_swiss_lathe_has_at_least_2_records(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.SWISS_LATHE]
        assert len(recs) >= 2

    def test_surface_grinder_present(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.SURFACE_GRINDER]
        assert len(recs) >= 1

    def test_cylindrical_grinder_present(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.CYLINDRICAL_GRINDER]
        assert len(recs) >= 1

    def test_wire_edm_present(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.WIRE_EDM]
        assert len(recs) >= 1

    def test_sinker_edm_present(self):
        recs = [r for r in seed_machine_library()
                if r.capability.machine_class is MachineClass.SINKER_EDM]
        assert len(recs) >= 1


# ---------------------------------------------------------------------------
# No fabricated data invariants
# ---------------------------------------------------------------------------

class TestNoFabricatedData:
    def test_all_records_have_manufacturer(self):
        for r in seed_machine_library():
            assert r.manufacturer.strip() != "", (
                f"{r.stable_id}: manufacturer is empty"
            )

    def test_all_records_have_model(self):
        for r in seed_machine_library():
            assert r.model.strip() != "", (
                f"{r.stable_id}: model is empty"
            )

    def test_no_zero_spindle_rpm(self):
        for r in seed_machine_library():
            if r.spindle.max_rpm is not None:
                assert r.spindle.max_rpm > 0, (
                    f"{r.stable_id}: spindle.max_rpm is 0"
                )

    def test_no_zero_spindle_power(self):
        for r in seed_machine_library():
            if r.spindle.power_kw is not None:
                assert r.spindle.power_kw > 0, (
                    f"{r.stable_id}: spindle.power_kw is 0"
                )

    def test_no_zero_travel(self):
        for r in seed_machine_library():
            e = r.envelope
            for attr in ("travel_x_mm", "travel_y_mm", "travel_z_mm"):
                val = getattr(e, attr)
                if val is not None:
                    assert val > 0, (
                        f"{r.stable_id}: envelope.{attr} is 0 or negative"
                    )

    def test_all_records_have_source_title(self):
        for r in seed_machine_library():
            assert r.source.source_title.strip() != "", (
                f"{r.stable_id}: source_title is empty"
            )

    def test_no_negative_magazine_capacity(self):
        for r in seed_machine_library():
            cap = r.capability.tool_magazine_capacity
            if cap is not None:
                assert cap > 0, (
                    f"{r.stable_id}: tool_magazine_capacity is non-positive"
                )


# ---------------------------------------------------------------------------
# Validation: all seed records pass
# ---------------------------------------------------------------------------

class TestSeedCatalogValidation:
    def test_all_seed_records_pass_validation(self):
        failures: list[str] = []
        for r in seed_machine_library():
            result = validate_machine_catalog_record(r)
            if not result.is_valid:
                failures.append(
                    f"{r.stable_id}: {result.errors}"
                )
        assert not failures, "Seed records failed validation:\n" + "\n".join(failures)

    def test_primary_capability_set_for_all_records(self):
        for r in seed_machine_library():
            assert r.capability.has_primary_capability, (
                f"{r.stable_id}: no primary capability declared"
            )


# ---------------------------------------------------------------------------
# Manufacturer coverage
# ---------------------------------------------------------------------------

class TestSeedCatalogManufacturers:
    def test_multiple_manufacturers_present(self):
        mfrs = {r.manufacturer for r in seed_machine_library()}
        assert len(mfrs) >= 10

    def test_haas_present(self):
        mfrs = {r.manufacturer for r in seed_machine_library()}
        assert "Haas Automation" in mfrs

    def test_dmg_mori_present(self):
        mfrs = {r.manufacturer for r in seed_machine_library()}
        assert "DMG MORI" in mfrs

    def test_grinder_manufacturer_present(self):
        grinder_mfrs = {
            r.manufacturer for r in seed_machine_library()
            if r.capability.machine_class in (
                MachineClass.SURFACE_GRINDER,
                MachineClass.CYLINDRICAL_GRINDER,
            )
        }
        assert len(grinder_mfrs) >= 2

    def test_edm_manufacturer_present(self):
        edm_mfrs = {
            r.manufacturer for r in seed_machine_library()
            if r.capability.machine_class in (
                MachineClass.WIRE_EDM,
                MachineClass.SINKER_EDM,
            )
        }
        assert len(edm_mfrs) >= 2
