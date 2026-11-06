"""Tool Assembly models.

A ToolAssemblyRecord combines a cutting tool, a holder and an optional insert
into a single assembled unit with declared geometry and a validation result.

No manufacturer specifications are fabricated here.
Geometry fields must be measured or stated from a real setup sheet.
"""
from __future__ import annotations

from pydantic import BaseModel

from .catalog_models import CuttingToolCatalogRecord
from .compatibility import CompatibilityResult, CompatibilityStatus
from .holder_models import ToolHolderRecord
from .insert_models import InsertRecord


class ToolAssemblyComponent(BaseModel):
    """Lightweight reference to one component in an assembly."""

    component_type: str           # TOOL, HOLDER, INSERT, EXTENSION
    stable_id: str
    manufacturer: str
    product_name: str


class ToolAssemblyGeometry(BaseModel):
    """Declared or measured geometry of an assembled tool unit.

    All dimensions are None when not measured; None is never coerced to 0.
    """

    shank_diameter_mm: float | None = None          # tool shank entering spindle/collet
    clamping_length_mm: float | None = None         # shank length gripped by holder
    gauge_length_mm: float | None = None            # spindle face → tool tip (reference)
    tool_stick_out_mm: float | None = None          # holder face → tool tip
    overall_assembly_length_mm: float | None = None # total holder + tool length
    effective_reach_mm: float | None = None         # usable depth reach into workpiece
    holder_diameter_mm: float | None = None         # max holder body diameter (clearance)
    spindle_interface: str | None = None            # HSK-A63, BT40, CAT40, etc.
    coolant_enabled: bool | None = None             # active coolant in this setup


class ToolAssemblySourceMetadata(BaseModel):
    """Provenance of the assembly record."""

    source_title: str
    source_authority: str
    evidence_status: str                            # MANUFACTURER_CATALOG or UNVERIFIED
    assembly_note: str | None = None


class ToolAssemblyValidationResult(BaseModel):
    """Aggregated compatibility result for a complete tool assembly."""

    overall_status: CompatibilityStatus
    tool_holder_check: CompatibilityResult
    insert_holder_check: CompatibilityResult | None
    geometry_check: CompatibilityResult
    all_reasons: list[str]


class ToolAssemblyRecord(BaseModel):
    """A complete tool assembly ready for machining readiness evaluation.

    Combines a cutting tool, holder and optional insert with declared
    geometry and provenance.  Validation is computed separately via
    :func:`~backend.cutting_tools.assembly_compatibility.validate_assembly`.
    """

    stable_id: str
    tool: CuttingToolCatalogRecord
    holder: ToolHolderRecord
    insert: InsertRecord | None = None

    geometry: ToolAssemblyGeometry
    provenance: ToolAssemblySourceMetadata

    # Set by validate_assembly(); None if not yet validated
    validation: ToolAssemblyValidationResult | None = None

    @property
    def components(self) -> list[ToolAssemblyComponent]:
        """Return lightweight component references for this assembly."""
        parts = [
            ToolAssemblyComponent(
                component_type="HOLDER",
                stable_id=self.holder.stable_id,
                manufacturer=self.holder.manufacturer,
                product_name=self.holder.product_name,
            ),
            ToolAssemblyComponent(
                component_type="TOOL",
                stable_id=self.tool.stable_id,
                manufacturer=self.tool.manufacturer,
                product_name=self.tool.product_name,
            ),
        ]
        if self.insert is not None:
            parts.append(
                ToolAssemblyComponent(
                    component_type="INSERT",
                    stable_id=self.insert.stable_id,
                    manufacturer=self.insert.manufacturer,
                    product_name=self.insert.product_name,
                )
            )
        return parts
