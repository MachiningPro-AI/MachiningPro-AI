"""Tests for backend.machine_library.import_pipeline."""

import json

import pytest

from backend.machine_library.enums import MachineClass
from backend.machine_library.import_pipeline import (
    ImportPipelineResult,
    flat_dict_to_record,
    parse_csv_machines,
    parse_json_machines,
    run_ml_import_pipeline,
)
from backend.machine_library.models import MachineCatalogRecord

# ---------------------------------------------------------------------------
# Minimal valid flat dict
# ---------------------------------------------------------------------------

def _minimal_flat(
    stable_id: str = "flat-001",
    machine_class: str = "3_AXIS_VMC",
    axis_count: int = 3,
    milling: bool = True,
    drilling: bool = True,
) -> dict:
    return {
        "stable_id": stable_id,
        "manufacturer": "Test Mfr",
        "model": "Test Model",
        "machine_class": machine_class,
        "axis_count": axis_count,
        "turning_capable": False,
        "milling_capable": milling,
        "drilling_capable": drilling,
        "source_title": "Test Source",
        "evidence_grade": "MANUFACTURER_DATASHEET",
        "spindle_max_rpm": 10_000,
        "spindle_power_kw": 11.0,
        "travel_x_mm": 600.0,
        "travel_y_mm": 400.0,
        "travel_z_mm": 400.0,
    }


# ---------------------------------------------------------------------------
# flat_dict_to_record
# ---------------------------------------------------------------------------

class TestFlatDictToRecord:
    def test_minimal_valid(self):
        flat = _minimal_flat()
        record = flat_dict_to_record(flat)
        assert isinstance(record, MachineCatalogRecord)
        assert record.stable_id == "flat-001"
        assert record.machine_class is MachineClass.THREE_AXIS_VMC

    def test_machine_class_resolved(self):
        flat = _minimal_flat(machine_class="CNC_LATHE")
        record = flat_dict_to_record(flat)
        assert record.machine_class is MachineClass.CNC_LATHE

    def test_all_12_machine_classes_parseable(self):
        for mc in MachineClass:
            flat = _minimal_flat(machine_class=mc.value, stable_id=f"mc-{mc.value}")
            # Need to adjust capability for some machine classes
            if mc in (MachineClass.SURFACE_GRINDER, MachineClass.CYLINDRICAL_GRINDER):
                flat["milling_capable"] = False
                flat["drilling_capable"] = False
                flat["grinding_capable"] = True
            elif mc in (MachineClass.WIRE_EDM, MachineClass.SINKER_EDM):
                flat["milling_capable"] = False
                flat["drilling_capable"] = False
                flat["edm_capable"] = True
            record = flat_dict_to_record(flat)
            assert record.machine_class is mc

    def test_missing_stable_id_raises(self):
        flat = _minimal_flat()
        del flat["stable_id"]
        with pytest.raises(ValueError):
            flat_dict_to_record(flat)

    def test_missing_source_title_raises(self):
        flat = _minimal_flat()
        del flat["source_title"]
        with pytest.raises(ValueError):
            flat_dict_to_record(flat)

    def test_invalid_machine_class_raises(self):
        flat = _minimal_flat()
        flat["machine_class"] = "INVALID_CLASS"
        with pytest.raises(ValueError, match="unknown machine_class"):
            flat_dict_to_record(flat)

    def test_none_numeric_fields_stay_none(self):
        flat = _minimal_flat()
        flat["spindle_torque_nm"] = None
        flat["table_load_kg"] = None
        record = flat_dict_to_record(flat)
        assert record.spindle.torque_nm is None
        assert record.envelope.table_load_kg is None

    def test_string_coercion_int_fields(self):
        flat = _minimal_flat()
        flat["axis_count"] = "3"
        flat["spindle_max_rpm"] = "12000"
        flat["tool_magazine_capacity"] = "20"
        record = flat_dict_to_record(flat)
        assert record.capability.controlled_axes == 3
        assert record.spindle.max_rpm == 12_000
        assert record.capability.tool_magazine_capacity == 20

    def test_string_coercion_float_fields(self):
        flat = _minimal_flat()
        flat["spindle_power_kw"] = "22.4"
        flat["travel_x_mm"] = "762.0"
        record = flat_dict_to_record(flat)
        assert record.spindle.power_kw == 22.4
        assert record.envelope.travel_x_mm == 762.0

    def test_bool_coercion_string_true(self):
        flat = _minimal_flat()
        flat["flood_coolant"] = "true"
        flat["capable_tapping"] = "yes"
        record = flat_dict_to_record(flat)
        assert record.capability.flood_coolant is True
        assert record.capability.capable_tapping is True


# ---------------------------------------------------------------------------
# parse_csv_machines
# ---------------------------------------------------------------------------

class TestParseCsvMachines:
    def test_parse_minimal_csv(self):
        csv_text = (
            "stable_id,manufacturer,model,machine_class,axis_count,"
            "milling_capable,drilling_capable,source_title\r\n"
            "csv-001,Haas,VF-2 SS,3_AXIS_VMC,3,true,true,Haas Test\r\n"
        )
        records = parse_csv_machines(csv_text)
        assert len(records) == 1
        assert records[0]["stable_id"] == "csv-001"
        assert records[0]["machine_class"] == "3_AXIS_VMC"

    def test_empty_cell_becomes_none(self):
        csv_text = (
            "stable_id,manufacturer,model,machine_class,axis_count,"
            "milling_capable,drilling_capable,source_title,spindle_max_rpm\r\n"
            "csv-002,Haas,VF-2 SS,3_AXIS_VMC,3,true,true,Haas Test,\r\n"
        )
        records = parse_csv_machines(csv_text)
        assert records[0]["spindle_max_rpm"] is None

    def test_multiple_rows(self):
        csv_text = (
            "stable_id,manufacturer,model,machine_class,axis_count,"
            "milling_capable,drilling_capable,source_title\r\n"
            "row-01,M1,Mod1,3_AXIS_VMC,3,true,true,Source\r\n"
            "row-02,M2,Mod2,CNC_LATHE,2,false,true,Source\r\n"
        )
        records = parse_csv_machines(csv_text)
        assert len(records) == 2


# ---------------------------------------------------------------------------
# parse_json_machines
# ---------------------------------------------------------------------------

class TestParseJsonMachines:
    def test_parse_array(self):
        data = [_minimal_flat("json-01"), _minimal_flat("json-02")]
        records = parse_json_machines(json.dumps(data))
        assert len(records) == 2
        assert records[0]["stable_id"] == "json-01"

    def test_non_array_raises(self):
        with pytest.raises(ValueError, match="top-level array"):
            parse_json_machines(json.dumps({"key": "value"}))


# ---------------------------------------------------------------------------
# run_ml_import_pipeline
# ---------------------------------------------------------------------------

class TestRunMlImportPipeline:
    def test_accepts_valid_record(self):
        result = run_ml_import_pipeline([_minimal_flat("pipe-01")])
        assert isinstance(result, ImportPipelineResult)
        assert result.accepted == 1
        assert result.total_input == 1

    def test_rejects_duplicate_in_batch(self):
        flats = [_minimal_flat("dup-01"), _minimal_flat("dup-01")]
        result = run_ml_import_pipeline(flats)
        assert result.rejected_duplicate == 1
        assert result.accepted == 1

    def test_rejects_duplicate_vs_existing(self):
        result = run_ml_import_pipeline(
            [_minimal_flat("exist-01")],
            existing_ids=frozenset(["exist-01"]),
        )
        assert result.rejected_duplicate == 1
        assert result.accepted == 0

    def test_rejects_invalid_machine_class(self):
        flat = _minimal_flat()
        flat["machine_class"] = "BOGUS"
        result = run_ml_import_pipeline([flat])
        assert result.rejected_parse == 1

    def test_accepted_records_property(self):
        result = run_ml_import_pipeline([_minimal_flat("acc-01"), _minimal_flat("acc-02")])
        assert len(result.accepted_records) == 2

    def test_dry_run_default_true(self):
        result = run_ml_import_pipeline([_minimal_flat("dry-01")])
        assert result.dry_run is True

    def test_mixed_batch(self):
        flat_bad = _minimal_flat("bad-01")
        flat_bad["machine_class"] = "INVALID"
        flats = [_minimal_flat("good-01"), flat_bad, _minimal_flat("good-02")]
        result = run_ml_import_pipeline(flats)
        assert result.accepted == 2
        assert result.rejected_parse == 1

    def test_empty_input(self):
        result = run_ml_import_pipeline([])
        assert result.total_input == 0
        assert result.accepted == 0
