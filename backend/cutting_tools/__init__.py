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

from .catalog_models import CuttingToolCatalogRecord, CuttingToolCatalogSummary
from .families import (
    CATEGORY_CODE_TO_FAMILY,
    FAMILY_TO_CATEGORY_CODES,
    ToolFamily,
    category_codes_for_family,
    family_for_category_code,
)
from .import_pipeline import (
    ImportPipelineResult,
    parse_csv_tools,
    parse_json_tools,
    run_import_pipeline,
)
from .library import ToolLibrary, ToolLibraryQuery
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
]
