"""Integration adapters — bridge layer between Machine, Material, and Tool Libraries.

This package must NOT be imported by any individual library module.
Dependency direction: integration → libraries (never the reverse).

Adapter modules:
  material_namespace  — resolve MaterialCondition name collision
  spindle_adapter     — normalize holder spindle_interface strings
  result_mapping      — unify PASS/FAIL/UNKNOWN across library types
  machine_adapter     — MC-1: opt-in Machine Library pipeline bridge
  material_adapter    — MC-2: opt-in Material Library pipeline bridge
  tool_adapter        — MC-3: opt-in Tool Library selection-engine bridge

Design constraints:
  CIRCULAR_DEPENDENCY=NO
  UNKNOWN_AS_PASS=NO
  CAT40_EQ_BT40=NO (not verified equivalent)
  FABRICATED_SPEC=NO
  LEGACY_PIPELINE_UNCHANGED=YES (opt-in only; backend.machines/materials untouched)
"""

from .machine_adapter import (
    MachineLookupResult,
    MachineLookupStatus,
    MachinePipelineAdapter,
)
from .material_adapter import (
    MaterialLookupResult,
    MaterialLookupStatus,
    MaterialPipelineAdapter,
)
from .material_namespace import MachineConditionState, MaterialConditionModel
from .result_mapping import IntegrationVerdict, combine_verdicts
from .spindle_adapter import (
    check_holder_machine_spindle_compatibility,
    normalize_holder_spindle_interface,
)
from .tool_adapter import ToolPipelineAdapter, ToolPipelineRequest, ToolPipelineResult

__all__ = [
    "MachineConditionState",
    "MaterialConditionModel",
    "IntegrationVerdict",
    "combine_verdicts",
    "normalize_holder_spindle_interface",
    "check_holder_machine_spindle_compatibility",
    "MachineLookupResult",
    "MachineLookupStatus",
    "MachinePipelineAdapter",
    "MaterialLookupResult",
    "MaterialLookupStatus",
    "MaterialPipelineAdapter",
    "ToolPipelineAdapter",
    "ToolPipelineRequest",
    "ToolPipelineResult",
]
