"""Tests for material_namespace adapter — MaterialCondition name collision.

Verifies:
- MachineConditionState is the StrEnum from machine_library
- MaterialConditionModel is the BaseModel from material_library
- They are distinct types (isinstance checks)
- machine_condition_to_str returns expected string values
- UNKNOWN is preserved, never promoted
"""
from enum import StrEnum

from pydantic import BaseModel

from backend.integration.material_namespace import (
    MachineConditionState,
    MaterialConditionModel,
    machine_condition_to_str,
)


class TestMachineConditionState:
    def test_is_str_enum(self):
        assert issubclass(MachineConditionState, StrEnum)

    def test_is_not_base_model(self):
        assert not issubclass(MachineConditionState, BaseModel)

    def test_values_present(self):
        values = {m.value for m in MachineConditionState}
        assert "ANNEALED" in values
        assert "QUENCHED_TEMPERED" in values
        assert "HARDENED" in values
        assert "UNKNOWN" in values

    def test_unknown_member_exists(self):
        assert MachineConditionState.UNKNOWN is not None

    def test_string_coercion(self):
        assert str(MachineConditionState.ANNEALED) == "ANNEALED"


class TestMaterialConditionModel:
    def test_is_base_model(self):
        assert issubclass(MaterialConditionModel, BaseModel)

    def test_is_not_str_enum(self):
        assert not issubclass(MaterialConditionModel, StrEnum)

    def test_has_condition_code(self):
        m = MaterialConditionModel(condition_code="ANNEALED", condition_label="Annealed")
        assert m.condition_code == "ANNEALED"

    def test_condition_label_stored(self):
        m = MaterialConditionModel(condition_code="HT", condition_label="Heat Treated")
        assert m.condition_label == "Heat Treated"


class TestTypesAreDistinct:
    def test_different_types(self):
        assert MachineConditionState is not MaterialConditionModel

    def test_machine_state_is_not_base_model_instance(self):
        assert not isinstance(MachineConditionState.ANNEALED, BaseModel)

    def test_model_is_not_str_enum_instance(self):
        m = MaterialConditionModel(condition_code="X", condition_label="Y")
        assert not isinstance(m, StrEnum)


class TestMachineConditionToStr:
    def test_annealed(self):
        assert machine_condition_to_str(MachineConditionState.ANNEALED) == "ANNEALED"

    def test_quenched_tempered(self):
        result = machine_condition_to_str(MachineConditionState.QUENCHED_TEMPERED)
        assert result == "QUENCHED_TEMPERED"

    def test_unknown_preserved(self):
        result = machine_condition_to_str(MachineConditionState.UNKNOWN)
        assert result == "UNKNOWN"

    def test_all_values_round_trip(self):
        for state in MachineConditionState:
            s = machine_condition_to_str(state)
            assert s == state.value
            assert s != ""
