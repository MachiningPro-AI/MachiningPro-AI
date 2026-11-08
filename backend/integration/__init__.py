"""Integration adapters — bridge layer between Machine, Material, and Tool Libraries.

This package must NOT be imported by any individual library module.
Dependency direction: integration → libraries (never the reverse).

Adapter modules:
  material_namespace      — resolve MaterialCondition name collision
  spindle_adapter         — normalize holder spindle_interface strings
  result_mapping          — unify PASS/FAIL/UNKNOWN across library types
  machine_adapter         — MC-1: opt-in Machine Library pipeline bridge
  material_adapter        — MC-2: opt-in Material Library pipeline bridge
  tool_adapter            — MC-3: opt-in Tool Library selection-engine bridge
  compatibility_wiring    — MC-4/MC-5: spindle normalization + IntegrationVerdict wiring
  material_resolution     — MC-6: material name → ISO group for operation planning
  machine_class_mapper    — explicit, fail-closed MachineClass cross-mapper (library ↔ scheduling)

Design constraints:
  CIRCULAR_DEPENDENCY=NO
  UNKNOWN_AS_PASS=NO
  CAT40_EQ_BT40=NO (not verified equivalent)
  FABRICATED_SPEC=NO
  LEGACY_PIPELINE_UNCHANGED=YES (opt-in only; backend.machines/materials untouched)
"""

from .compatibility_wiring import (
    EnhancedCompatibilityResult,
    SpindleCheckDetail,
    enhanced_evaluate,
)
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
from .material_resolution import (
    MaterialResolutionResult,
    resolve_iso_group_for_selection,
    resolve_material_for_selection,
)
from .result_mapping import IntegrationVerdict, combine_verdicts
from .spindle_adapter import (
    check_holder_machine_spindle_compatibility,
    normalize_holder_spindle_interface,
)
from .tool_adapter import ToolPipelineAdapter, ToolPipelineRequest, ToolPipelineResult
from .machine_class_mapper import (
    MachineClassMapError,
    library_to_runtime,
    library_to_scheduling,
    runtime_to_library,
    scheduling_to_library,
)

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
    "SpindleCheckDetail",
    "EnhancedCompatibilityResult",
    "enhanced_evaluate",
    "MaterialResolutionResult",
    "resolve_material_for_selection",
    "resolve_iso_group_for_selection",
    "MachineClassMapError",
    "library_to_scheduling",
    "scheduling_to_library",
    "library_to_runtime",
    "runtime_to_library",
]
