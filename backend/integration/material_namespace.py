"""Resolve the MaterialCondition name collision between Machine Library and Material Library.

NAME COLLISION
--------------
Both libraries define a type named ``MaterialCondition``, but they are
completely different things:

  machine_library.material_context.MaterialCondition
      A StrEnum describing the heat-treatment state of the workpiece for
      machine-capability evaluation (ANNEALED, QUENCHED_TEMPERED, …).
      Used as an enum selector in MaterialMachiningContext.

  material_library.models.MaterialCondition
      A Pydantic BaseModel describing a full condition variant record for a
      material catalog entry — condition_code, condition_label, hardness range,
      tensile properties, machinability rating, and cutting reference.

These types serve orthogonal purposes and must never be confused. This module
re-exports both under unambiguous aliases and provides a bridge helper.

Usage
-----
    from backend.integration.material_namespace import (
        MachineConditionState,    # StrEnum — use in MaterialMachiningContext
        MaterialConditionModel,   # BaseModel — use in MaterialCatalogRecord
    )

Design constraints:
  CIRCULAR_DEPENDENCY=NO (libraries never import from integration)
  SILENT_TYPE_COERCION=NO
"""

from __future__ import annotations

from backend.machine_library.material_context import (
    MaterialCondition as _MachineConditionState,
)
from backend.material_library.models import (
    MaterialCondition as _MaterialConditionModel,
)

# Unambiguous alias for the StrEnum from machine_library
MachineConditionState = _MachineConditionState

# Unambiguous alias for the BaseModel from material_library
MaterialConditionModel = _MaterialConditionModel


def machine_condition_to_str(state: MachineConditionState) -> str:
    """Return the string value of a MachineConditionState enum member.

    Useful when constructing a MaterialConditionModel.condition_code from a
    machine-library planning context.  Returns the enum's value directly —
    no UNKNOWN-to-PASS promotion occurs here.
    """
    return str(state.value)


__all__ = [
    "MachineConditionState",
    "MaterialConditionModel",
    "machine_condition_to_str",
]
