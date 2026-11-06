"""Cutting Tool Library — public API.

Tool families supported:
  DRILLING · MILLING · TURNING · BORING · THREADING
  REAMING · GROOVING · GRINDING · EDM

Quick start
-----------
    from backend.cutting_tools import ToolLibrary, ToolFamily

    lib = ToolLibrary()

    # Chainable query:
    results = (
        lib.query()
        .by_family(ToolFamily.DRILLING)
        .by_diameter(min_mm=7.9, max_mm=8.1)
        .by_material_groups(["P", "M"])
        .results()
    )

    # One-shot helper:
    drills = lib.by_family(ToolFamily.DRILLING)
    summary = lib.summary()
    coverage = lib.family_coverage()
"""

from .assembly_compatibility import check_assembly_geometry, validate_assembly
from .assembly_models import (
    ToolAssemblyComponent,
    ToolAssemblyGeometry,
    ToolAssemblyRecord,
    ToolAssemblySourceMetadata,
    ToolAssemblyValidationResult,
)
from .catalog_models import CuttingToolCatalogRecord, CuttingToolCatalogSummary
from .compatibility import (
    CompatibilityResult,
    CompatibilityStatus,
    check_insert_holder_compatibility,
    check_tool_holder_compatibility,
)
from .families import (
    CATEGORY_CODE_TO_FAMILY,
    FAMILY_TO_CATEGORY_CODES,
    ToolFamily,
    category_codes_for_family,
    family_for_category_code,
)
from .holder_models import (
    HolderCapacity,
    HolderInterface,
    HolderSourceMetadata,
    ToolHolderRecord,
)
from .import_pipeline import (
    ImportPipelineResult,
    parse_csv_tools,
    parse_json_tools,
    run_import_pipeline,
)
from .insert_models import (
    InsertDesignation,
    InsertGeometry,
    InsertGrade,
    InsertRecord,
    InsertSourceMetadata,
)
from .iso1832_parser import parse_iso1832
from .library import ToolLibrary, ToolLibraryQuery
from .machining_readiness import (
    MachiningReadinessRequest,
    MachiningReadinessResult,
    OperationCompatibility,
    ToolAssemblyCompatibility,
    assess_machining_readiness,
)
from .seed_catalog import (
    get_catalog,
    get_categories,
    get_category_codes,
    get_coating_types,
    get_iso_groups,
    get_manufacturers,
    get_operations,
    get_substrate_codes,
    get_tool_materials,
)
from .selection_engine import (
    ToolSelectionCandidate,
    ToolSelectionEngine,
    ToolSelectionReason,
    ToolSelectionRequest,
    ToolSelectionResult,
)

__all__ = [
    # Core model
    "CuttingToolCatalogRecord",
    "CuttingToolCatalogSummary",
    # Families
    "ToolFamily",
    "FAMILY_TO_CATEGORY_CODES",
    "CATEGORY_CODE_TO_FAMILY",
    "family_for_category_code",
    "category_codes_for_family",
    # Library
    "ToolLibrary",
    "ToolLibraryQuery",
    # Seed catalog helpers
    "get_catalog",
    "get_categories",
    "get_category_codes",
    "get_coating_types",
    "get_iso_groups",
    "get_manufacturers",
    "get_operations",
    "get_substrate_codes",
    "get_tool_materials",
    # Import pipeline
    "ImportPipelineResult",
    "parse_csv_tools",
    "parse_json_tools",
    "run_import_pipeline",
    # Insert taxonomy
    "InsertRecord",
    "InsertDesignation",
    "InsertGeometry",
    "InsertGrade",
    "InsertSourceMetadata",
    "parse_iso1832",
    # Holder models
    "HolderInterface",
    "HolderCapacity",
    "HolderSourceMetadata",
    "ToolHolderRecord",
    # Compatibility engine
    "CompatibilityStatus",
    "CompatibilityResult",
    "check_tool_holder_compatibility",
    "check_insert_holder_compatibility",
    # Assembly models
    "ToolAssemblyRecord",
    "ToolAssemblyComponent",
    "ToolAssemblyGeometry",
    "ToolAssemblySourceMetadata",
    "ToolAssemblyValidationResult",
    "validate_assembly",
    "check_assembly_geometry",
    # Selection engine
    "ToolSelectionRequest",
    "ToolSelectionReason",
    "ToolSelectionCandidate",
    "ToolSelectionResult",
    "ToolSelectionEngine",
    # Machining readiness
    "MachiningReadinessRequest",
    "MachiningReadinessResult",
    "OperationCompatibility",
    "ToolAssemblyCompatibility",
    "assess_machining_readiness",
]
