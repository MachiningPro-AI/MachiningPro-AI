"""MC-3: Tool Library selection-engine pipeline adapter.

Opt-in bridge between backend.cutting_tools.selection_engine and the
production-planning pipeline.  The legacy compatibility engine
(backend.compatibility.engine) is NOT modified; its _TOOLS catalog
(47 tools from seed_catalog Phase 1) remains the default.

Only callers that explicitly instantiate ToolPipelineAdapter receive
selection-engine behaviour.

Design constraints:
  LEGACY_PIPELINE_UNCHANGED=YES     — engine._TOOLS / seed_catalog untouched
  OPT_IN_ONLY=YES                    — no automatic activation
  FAIL_EXCLUDED_FROM_RECOMMENDED=YES — FAIL candidates never in recommended
  UNKNOWN_PRESERVED_AS_DIAGNOSTIC=YES — UNKNOWN in uncertain, not silently dropped
  DETERMINISTIC_RANKING=YES          — score descending, stable_id ascending
  FABRICATED_SPEC=NO
  UNKNOWN_AS_PASS=NO
"""
from __future__ import annotations

from dataclasses import dataclass, field

from backend.cutting_tools.catalog_models import CuttingToolCatalogRecord
from backend.cutting_tools.library import ToolLibrary
from backend.cutting_tools.selection_engine import (
    ToolSelectionCandidate,
    ToolSelectionEngine,
    ToolSelectionRequest,
    ToolSelectionResult,
)

__all__ = [
    "ToolPipelineRequest",
    "ToolPipelineResult",
    "ToolPipelineAdapter",
]


@dataclass
class ToolPipelineRequest:
    """Operation-planning requirements for tool selection.

    ``iso_material_group``: set from Material Library adapter (opt-in) or leave None.
    ``spindle_interface``:  set from Machine Library adapter (opt-in) or leave None.
    Missing fields are treated as UNKNOWN — they never produce PASS automatically.
    """

    operation: str
    required_diameter_mm: float | None = None
    machining_depth_mm: float | None = None
    required_reach_mm: float | None = None
    required_cutting_length_mm: float | None = None
    iso_material_group: str | None = None    # from MaterialPipelineAdapter.resolve()
    spindle_interface: str | None = None     # from MachinePipelineAdapter.normalize_spindle()


@dataclass
class ToolPipelineResult:
    """Selection result with PASS / UNKNOWN / FAIL separated.

    ``recommended``: PASS candidates ranked deterministically (score desc, id asc).
    ``uncertain``:   UNKNOWN candidates, preserved for diagnostics.
    ``rejected``:    FAIL candidates, diagnostic only — never recommended.
    """

    recommended: list[ToolSelectionCandidate] = field(default_factory=list)
    uncertain: list[ToolSelectionCandidate] = field(default_factory=list)
    rejected: list[ToolSelectionCandidate] = field(default_factory=list)
    total_evaluated: int = 0
    note: str | None = None


class ToolPipelineAdapter:
    """Opt-in adapter: connects ToolSelectionEngine to pipeline operation requests.

    FAIL and UNKNOWN candidates are excluded from confirmed recommendations.
    UNKNOWN candidates are preserved in ``uncertain`` for diagnostic use.
    Rankings are deterministic: score descending, stable_id ascending.

    The legacy compatibility engine uses seed_catalog Phase 1 (47 tools) directly
    and is unaffected by this adapter.
    """

    def __init__(
        self, records: list[CuttingToolCatalogRecord] | None = None
    ) -> None:
        if records is None:
            records = ToolLibrary().all()
        self._engine = ToolSelectionEngine(records)

    def select(self, request: ToolPipelineRequest) -> ToolPipelineResult:
        """Run tool selection for *request*; return separated PASS/UNKNOWN/FAIL lists."""
        sel_req = ToolSelectionRequest(
            operation=request.operation,
            required_diameter_mm=request.required_diameter_mm,
            machining_depth_mm=request.machining_depth_mm,
            required_reach_mm=request.required_reach_mm,
            required_cutting_length_mm=request.required_cutting_length_mm,
            iso_material_group=request.iso_material_group,
            spindle_interface=request.spindle_interface,
        )
        result: ToolSelectionResult = self._engine.select(sel_req)
        return ToolPipelineResult(
            recommended=result.recommended,
            uncertain=result.uncertain,
            rejected=result.rejected,
            total_evaluated=result.total_candidates_evaluated,
            note=result.selection_note,
        )
