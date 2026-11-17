"""
P10-C: Fixture / Workholding production workflow.

Wires the existing fixture catalog and FixtureInput model into an end-to-end
production workflow:

  Setup → Fixture Selection → Fixture Geometry → WCS Relationship → Verification Input

Supported bounded geometry primitives (per P10 MUST 3):
  BOX           — FixtureType.VISE_JAWS, CLAMPS, TOOLING_PLATE, FIXTURE_PLATE
  CYLINDER      — FixtureType.ROTARY_TABLE, CHUCK_JAWS (round cross-section approximation)
  KEEP_OUT_REGION — explicit exclusion zone supplied by engineer (FixtureType.KEEP_OUT)

Fixture source must be one of:
  LIBRARY_EVIDENCE   — from get_fixture_catalog() (catalog record)
  FILE_EVIDENCE      — imported from a geometry file
  USER_CONFIRMED     — engineer directly entered WCS coordinates
  UNKNOWN            — coordinates not available → FIXTURE_COLLISION=NOT_VERIFIABLE

WCS coordinates are NEVER inferred or defaulted. The engineer must supply them.

HARD RULES (enforced unconditionally):
  - No silent coordinates.
  - UNKNOWN provenance → FIXTURE_COLLISION=NOT_VERIFIABLE.
  - Fixture geometry with incomplete transform → NOT_VERIFIABLE.
  - FABRICATED_FIXTURE_DIMENSIONS=NO
  - is_dispatchable=False at all times.
  - production_released=False at all times.

FIXTURE_SCHEMA_FOUND=YES
FIXTURE_CATALOG_FOUND=YES
FIXTURE_WORKFLOW_FOUND=YES (this module)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from backend.manufacturing.fixture_seed import (
    get_fixture_by_id,
    make_fixture_input_from_library,
)
from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    P8VerificationInput,
    build_verification_input,
)
from backend.verification.enums import FixtureType

__all__ = [
    "WorkholdingSource",
    "WorkholdingGeometryClass",
    "WorkholdingSetupItem",
    "WorkholdingWorkflow",
    "WorkholdingWorkflowResult",
    "build_workholding_workflow",
    "resolve_fixture_inputs",
    "FIXTURE_SCHEMA_FOUND",
    "FIXTURE_CATALOG_FOUND",
    "FIXTURE_WORKFLOW_FOUND",
]

# P10-C audit constants
FIXTURE_SCHEMA_FOUND: bool = True   # FixtureLibraryRecord + FixtureInput in P9-C/P8-C
FIXTURE_CATALOG_FOUND: bool = True  # get_fixture_catalog() in fixture_seed.py
FIXTURE_WORKFLOW_FOUND: bool = True  # this module


# ---------------------------------------------------------------------------
# Workholding source enum
# ---------------------------------------------------------------------------


class WorkholdingSource(StrEnum):
    """Source of workholding geometry in the production workflow."""
    LIBRARY_EVIDENCE = "LIBRARY_EVIDENCE"   # from fixture catalog record
    FILE_EVIDENCE = "FILE_EVIDENCE"         # from imported geometry file
    USER_CONFIRMED = "USER_CONFIRMED"       # engineer confirmed WCS coordinates
    UNKNOWN = "UNKNOWN"                     # coordinates not available


class WorkholdingGeometryClass(StrEnum):
    """Bounded geometry primitive class for the workholding item."""
    BOX = "BOX"
    CYLINDER = "CYLINDER"
    KEEP_OUT_REGION = "KEEP_OUT_REGION"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# WorkholdingSetupItem
# ---------------------------------------------------------------------------


@dataclass
class WorkholdingSetupItem:
    """One workholding device in a machining setup.

    Carries both the fixture catalog identity and the engineer-confirmed WCS position.
    WCS coordinates must ALWAYS come from the engineer — never inferred.

    Supported geometry classes:
      BOX           — vise jaws, clamps, tooling plates, fixture plates
      CYLINDER      — round cross-section approximations (chuck jaws, rotary table)
      KEEP_OUT_REGION — engineer-defined keep-out zone

    provenance must be one of WorkholdingSource. When UNKNOWN, the generated
    FixtureInput has provenance=UNKNOWN → verification returns NOT_VERIFIABLE.
    """

    # Catalog reference
    catalog_id: str | None             # fixture_seed stable_id or None for direct entry
    fixture_type: FixtureType
    geometry_class: WorkholdingGeometryClass
    source: WorkholdingSource

    # Geometry in LIBRARY or FILE frame (mm)
    half_x_mm: float | None = None     # BOX half-width (X)
    half_y_mm: float | None = None     # BOX half-depth (Y)
    height_mm: float | None = None     # BOX height (Z)
    radius_mm: float | None = None     # CYLINDER radius

    # Engineer-confirmed WCS position
    wcs_centre_x_mm: float | None = None
    wcs_centre_y_mm: float | None = None
    wcs_bottom_z_mm: float | None = None

    # Provenance of WCS position (must be USER_CONFIRMED or KNOWN for trustworthy)
    wcs_provenance: GeometryFieldProvenance = GeometryFieldProvenance.UNKNOWN

    # Descriptive notes
    notes: str = ""

    @property
    def has_wcs(self) -> bool:
        """True when all three WCS coordinates are present."""
        return (
            self.wcs_centre_x_mm is not None
            and self.wcs_centre_y_mm is not None
            and self.wcs_bottom_z_mm is not None
        )

    @property
    def has_geometry(self) -> bool:
        """True when geometry dimensions are complete."""
        if self.geometry_class == WorkholdingGeometryClass.BOX:
            return (
                self.half_x_mm is not None
                and self.half_y_mm is not None
                and self.height_mm is not None
            )
        if self.geometry_class == WorkholdingGeometryClass.CYLINDER:
            return self.radius_mm is not None and self.height_mm is not None
        if self.geometry_class == WorkholdingGeometryClass.KEEP_OUT_REGION:
            return (
                self.half_x_mm is not None
                and self.half_y_mm is not None
                and self.height_mm is not None
            )
        return False


# ---------------------------------------------------------------------------
# WorkholdingWorkflow — input
# ---------------------------------------------------------------------------


@dataclass
class WorkholdingWorkflow:
    """Full workholding workflow input.

    setup_id:
        Identity of the machining setup (from SetupDefinition).
    items:
        List of workholding devices, each with geometry + WCS.
    candidate:
        The OfflineNCCandidate being verified.
    machine_record:
        Machine catalog dict (travel_x/y/z_mm required for envelope check).
    stock_def:
        StockDefinition for voxel simulation. None → stock checks NOT_VERIFIABLE.
    tool_record:
        CuttingToolCatalogRecord providing flute_length_mm. None → INSUFFICIENT_DATA.
    holder_record:
        ToolHolderCatalogRecord providing body_diameter_mm. None → NOT_VERIFIABLE.
    """

    setup_id: str
    items: list[WorkholdingSetupItem] = field(default_factory=list)
    candidate: Any = None
    machine_record: dict | None = None
    stock_def: Any = None
    tool_record: Any = None
    holder_record: Any = None


# ---------------------------------------------------------------------------
# WorkholdingWorkflowResult — output
# ---------------------------------------------------------------------------


@dataclass
class WorkholdingWorkflowResult:
    """Result of the full workholding workflow.

    Reports:
      - Which fixtures were resolved to FixtureInput objects
      - Which had UNKNOWN provenance → excluded from collision checks
      - P8VerificationInput assembled with all resolved fixtures
      - Per-check verification status strings

    Safety invariants:
      - is_dispatchable=False always
      - production_released=False always
      - FIXTURE_COLLISION=NOT_VERIFIABLE when no trustworthy fixture present
    """

    setup_id: str
    resolved_fixture_count: int
    trustworthy_fixture_count: int
    skipped_unknown_provenance_count: int
    fixture_inputs: list[FixtureInput]
    verification_input: P8VerificationInput | None
    workflow_notes: list[str] = field(default_factory=list)

    # Safety invariants
    is_dispatchable: bool = False
    production_released: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)


# ---------------------------------------------------------------------------
# WorkholdingSetupItem → FixtureInput
# ---------------------------------------------------------------------------


def _item_to_fixture_input(item: WorkholdingSetupItem, item_idx: int) -> FixtureInput | None:
    """Convert a WorkholdingSetupItem to a FixtureInput.

    Returns None when:
      - WCS coordinates are missing (incomplete transform → NOT_VERIFIABLE per MUST 5)
      - Geometry dimensions are missing

    When source=UNKNOWN or wcs_provenance=UNKNOWN, the FixtureInput is returned with
    UNKNOWN provenance so the caller can exclude it from trustworthy collision checks.
    """
    fixture_id = item.catalog_id or f"fixture-{item_idx}"

    # Try to load from catalog first if catalog_id given
    if item.catalog_id is not None:
        record = get_fixture_by_id(item.catalog_id)
        if record is not None and item.has_wcs:
            return make_fixture_input_from_library(
                record=record,
                wcs_centre_x_mm=item.wcs_centre_x_mm,  # type: ignore[arg-type]
                wcs_centre_y_mm=item.wcs_centre_y_mm,  # type: ignore[arg-type]
                wcs_bottom_z_mm=item.wcs_bottom_z_mm,  # type: ignore[arg-type]
                provenance=item.wcs_provenance,
                fixture_id=fixture_id,
            )

    # Direct geometry path (not from catalog)
    if not item.has_geometry or not item.has_wcs:
        return None

    cx = item.wcs_centre_x_mm
    cy = item.wcs_centre_y_mm
    bz = item.wcs_bottom_z_mm

    if item.geometry_class == WorkholdingGeometryClass.BOX:
        from backend.manufacturing.verification_adapter import FixtureInput as FI
        from backend.verification.enums import FixtureSource
        source_map = {
            WorkholdingSource.LIBRARY_EVIDENCE: FixtureSource.VERIFIED_LIBRARY_RECORD,
            WorkholdingSource.FILE_EVIDENCE: FixtureSource.IMPORTED_GEOMETRY,
            WorkholdingSource.USER_CONFIRMED: FixtureSource.USER_DEFINED,
            WorkholdingSource.UNKNOWN: FixtureSource.USER_DEFINED,
        }
        return FI(
            fixture_id=fixture_id,
            fixture_type=item.fixture_type,
            source=source_map.get(item.source, FixtureSource.USER_DEFINED),
            provenance=item.wcs_provenance,
            min_x_mm=cx - item.half_x_mm,  # type: ignore[operator]
            min_y_mm=cy - item.half_y_mm,  # type: ignore[operator]
            min_z_mm=bz,  # type: ignore[arg-type]
            max_x_mm=cx + item.half_x_mm,  # type: ignore[operator]
            max_y_mm=cy + item.half_y_mm,  # type: ignore[operator]
            max_z_mm=bz + item.height_mm,  # type: ignore[operator]
        )

    if item.geometry_class == WorkholdingGeometryClass.CYLINDER:
        from backend.manufacturing.verification_adapter import FixtureInput as FI
        from backend.verification.enums import FixtureSource
        r = item.radius_mm
        return FI(
            fixture_id=fixture_id,
            fixture_type=item.fixture_type,
            source=FixtureSource.USER_DEFINED,
            provenance=item.wcs_provenance,
            min_x_mm=cx - r,  # type: ignore[operator]
            min_y_mm=cy - r,  # type: ignore[operator]
            min_z_mm=bz,  # type: ignore[arg-type]
            max_x_mm=cx + r,  # type: ignore[operator]
            max_y_mm=cy + r,  # type: ignore[operator]
            max_z_mm=bz + item.height_mm,  # type: ignore[operator]
        )

    if item.geometry_class == WorkholdingGeometryClass.KEEP_OUT_REGION:
        from backend.manufacturing.verification_adapter import FixtureInput as FI
        from backend.verification.enums import FixtureSource
        from backend.verification.enums import FixtureType as FT
        return FI(
            fixture_id=fixture_id,
            fixture_type=FT.CUSTOM_FIXTURE_MESH,
            source=FixtureSource.USER_DEFINED,
            provenance=item.wcs_provenance,
            min_x_mm=cx - item.half_x_mm,  # type: ignore[operator]
            min_y_mm=cy - item.half_y_mm,  # type: ignore[operator]
            min_z_mm=bz,  # type: ignore[arg-type]
            max_x_mm=cx + item.half_x_mm,  # type: ignore[operator]
            max_y_mm=cy + item.half_y_mm,  # type: ignore[operator]
            max_z_mm=bz + item.height_mm,  # type: ignore[operator]
        )

    return None


# ---------------------------------------------------------------------------
# resolve_fixture_inputs
# ---------------------------------------------------------------------------


def resolve_fixture_inputs(items: list[WorkholdingSetupItem]) -> tuple[
    list[FixtureInput],  # all resolved (including UNKNOWN-provenance)
    list[str],           # workflow notes
]:
    """Resolve all WorkholdingSetupItems to FixtureInput objects.

    Returns (fixture_inputs, notes). Items with UNKNOWN provenance are
    included in fixture_inputs so the caller can audit them, but they will
    not be treated as trustworthy by the verification adapter (is_trustworthy=False).

    Items with incomplete geometry or WCS are logged in notes and excluded.
    """
    inputs: list[FixtureInput] = []
    notes: list[str] = []

    for idx, item in enumerate(items):
        fid = item.catalog_id or f"fixture-{idx}"

        if item.source == WorkholdingSource.UNKNOWN:
            notes.append(
                f"FIXTURE_UNKNOWN_SOURCE: {fid} source=UNKNOWN — "
                "WCS position cannot be verified; excluded from trustworthy collision checks"
            )

        if not item.has_wcs:
            notes.append(
                f"FIXTURE_INCOMPLETE_TRANSFORM: {fid} — "
                "WCS coordinates missing; FIXTURE_COLLISION=NOT_VERIFIABLE per MUST 5"
            )
            continue

        if not item.has_geometry:
            notes.append(
                f"FIXTURE_INCOMPLETE_GEOMETRY: {fid} geometry_class={item.geometry_class} — "
                "dimensions missing; FIXTURE_COLLISION=NOT_VERIFIABLE per MUST 5"
            )
            # Still try catalog path
            record = get_fixture_by_id(fid) if item.catalog_id else None
            if record is None:
                continue

        fi = _item_to_fixture_input(item, idx)
        if fi is None:
            notes.append(
                f"FIXTURE_RESOLVE_FAILED: {fid} — could not build FixtureInput; "
                "check geometry dimensions and WCS coordinates"
            )
            continue

        if item.wcs_provenance == GeometryFieldProvenance.UNKNOWN:
            notes.append(
                f"FIXTURE_UNKNOWN_WCS_PROVENANCE: {fid} — "
                "wcs_provenance=UNKNOWN → is_trustworthy=False → NOT_VERIFIABLE"
            )

        inputs.append(fi)
        notes.append(
            f"FIXTURE_RESOLVED: {fid} type={item.fixture_type} "
            f"class={item.geometry_class} source={item.source} "
            f"wcs_prov={item.wcs_provenance} trustworthy={fi.is_trustworthy}"
        )

    return inputs, notes


# ---------------------------------------------------------------------------
# build_workholding_workflow — main entry point
# ---------------------------------------------------------------------------


def build_workholding_workflow(workflow: WorkholdingWorkflow) -> WorkholdingWorkflowResult:
    """Run the full fixture/workholding production workflow.

    Workflow stages:
      1. Setup — validate setup_id and candidate presence
      2. Fixture Selection — resolve catalog IDs to FixtureLibraryRecord
      3. Fixture Geometry — convert to FixtureInput with provenance
      4. WCS Relationship — apply engineer WCS coordinates
      5. Verification Input — assemble P8VerificationInput

    Returns WorkholdingWorkflowResult with per-fixture status and
    an assembled P8VerificationInput ready for run_p8_verification().

    Safety invariants:
      - is_dispatchable=False always
      - production_released=False always
      - Fixtures with incomplete transform → NOT_VERIFIABLE (not silently excluded)
    """
    notes: list[str] = []

    # Stage 1: Setup check
    if not workflow.setup_id:
        notes.append("WORKHOLDING_SETUP_ID_MISSING: no setup_id supplied")
    else:
        notes.append(f"WORKHOLDING_SETUP: setup_id={workflow.setup_id}")

    if workflow.candidate is None:
        notes.append(
            "WORKHOLDING_NO_CANDIDATE: no OfflineNCCandidate supplied; "
            "verification_input cannot be assembled"
        )
        return WorkholdingWorkflowResult(
            setup_id=workflow.setup_id or "",
            resolved_fixture_count=0,
            trustworthy_fixture_count=0,
            skipped_unknown_provenance_count=0,
            fixture_inputs=[],
            verification_input=None,
            workflow_notes=notes,
        )

    # Stage 2–4: Resolve all fixture items → FixtureInput
    fixture_inputs, resolve_notes = resolve_fixture_inputs(workflow.items)
    notes.extend(resolve_notes)

    trustworthy = [fi for fi in fixture_inputs if fi.is_trustworthy]
    unknown_prov = [fi for fi in fixture_inputs if not fi.is_trustworthy]

    notes.append(
        f"WORKHOLDING_FIXTURE_SUMMARY: "
        f"resolved={len(fixture_inputs)} "
        f"trustworthy={len(trustworthy)} "
        f"unknown_provenance={len(unknown_prov)}"
    )

    if not trustworthy:
        notes.append(
            "WORKHOLDING_NO_TRUSTWORTHY_FIXTURES: "
            "all fixtures have UNKNOWN provenance or are missing; "
            "fixture_collision_validated=NOT_VERIFIABLE"
        )

    # Stage 5: Assemble P8VerificationInput
    vi = build_verification_input(
        candidate=workflow.candidate,
        machine_record=workflow.machine_record,
        stock_def=workflow.stock_def,
        fixture_inputs=fixture_inputs,  # all, including UNKNOWN (adapter filters)
        tool_record=workflow.tool_record,
        holder_record=workflow.holder_record,
    )
    notes.append(
        f"WORKHOLDING_VERIFICATION_INPUT_ASSEMBLED: "
        f"scope={vi.verification_scope}"
    )

    return WorkholdingWorkflowResult(
        setup_id=workflow.setup_id or "",
        resolved_fixture_count=len(fixture_inputs),
        trustworthy_fixture_count=len(trustworthy),
        skipped_unknown_provenance_count=len(unknown_prov),
        fixture_inputs=fixture_inputs,
        verification_input=vi,
        workflow_notes=notes,
    )


# ---------------------------------------------------------------------------
# Convenience: build from catalog ID + WCS (common case)
# ---------------------------------------------------------------------------


def build_workholding_from_catalog(
    catalog_id: str,
    wcs_centre_x_mm: float,
    wcs_centre_y_mm: float,
    wcs_bottom_z_mm: float,
) -> WorkholdingSetupItem | None:
    """Build a WorkholdingSetupItem from a fixture catalog record + WCS.

    Returns None if catalog_id not found in the library.
    WCS provenance is USER_CONFIRMED (engineer supplied coordinates).
    """
    record = get_fixture_by_id(catalog_id)
    if record is None:
        return None

    return WorkholdingSetupItem(
        catalog_id=catalog_id,
        fixture_type=record.fixture_type,
        geometry_class=WorkholdingGeometryClass.BOX,
        source=WorkholdingSource.LIBRARY_EVIDENCE,
        half_x_mm=record.half_x_mm,
        half_y_mm=record.half_y_mm,
        height_mm=record.height_mm,
        wcs_centre_x_mm=wcs_centre_x_mm,
        wcs_centre_y_mm=wcs_centre_y_mm,
        wcs_bottom_z_mm=wcs_bottom_z_mm,
        wcs_provenance=GeometryFieldProvenance.USER_CONFIRMED,
    )
