"""
P10-C/G: Production verification workflow orchestrator.

Wires the manufacturing workflow end-to-end:
  Setup / Stock Definition
  → Fixture Selection (from catalog by stable_id + engineer WCS)
  → Fixture Geometry (FixtureInput with provenance)
  → WCS relationship (always engineer-confirmed; never inferred)
  → Verification Input (build_verification_input)
  → Voxel Simulation (run_p8_verification)
  → Verification Result

P10-C covers: fixture/workholding workflow wiring.
P10-G covers: stock/simulation workflow wiring.

HARD RULES (all enforced unconditionally):
  - SIMULATION_METHOD=VOXEL_APPROXIMATION (never EXACT_BOOLEAN)
  - WCS always from engineer — never inferred or defaulted
  - Fixture absent or WCS incomplete → FIXTURE_COLLISION=NOT_VERIFIABLE
  - Stock absent → STOCK_REMOVAL_VALIDATED=NOT_VERIFIABLE
  - GOUGE_VALIDATED=NOT_VERIFIABLE without STEP part_bbox (always NOT_VERIFIABLE from DXF)
  - is_dispatchable=False always
  - production_released=False always
  - No silent coordinates — every fixture placement is LIBRARY_EVIDENCE or USER_CONFIRMED
  - Unknown fixture_id → FixtureInput with UNKNOWN provenance → NOT_VERIFIABLE

Supported fixture geometry primitives (bounded, existing architecture):
  BOX         (FixtureType.VISE_JAWS, CLAMPS — from fixture_seed)
  CYLINDER    (future: round fixture bodies — same AABB expansion applies)
  KEEP_OUT    (future: exclusion volumes)

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE  PRODUCTION_RELEASED=ALWAYS_FALSE
SIMULATION_METHOD=VOXEL_APPROXIMATION
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.manufacturing.fixture_seed import (
    get_fixture_by_id,
    make_fixture_input_from_library,
)
from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    P8VerificationResult,
    build_verification_input,
    nc_segments_to_verification_segments,
    run_p8_verification,
)
from backend.verification.enums import FixtureSource, FixtureType

__all__ = [
    "FixtureSelection",
    "WorkflowVerificationRequest",
    "WorkflowVerificationResult",
    "run_production_verification",
    "SIMULATION_METHOD",
]

SIMULATION_METHOD = "VOXEL_APPROXIMATION"


# ---------------------------------------------------------------------------
# Fixture selection — engineer-specified placement
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureSelection:
    """Engineer-specified fixture placement: which fixture + where in WCS.

    fixture_id must match a stable_id in the fixture catalog
    (backend.manufacturing.fixture_seed).  An unrecognised fixture_id
    produces a NOT_VERIFIABLE FixtureInput with UNKNOWN provenance.

    WCS coordinates are NEVER inferred or defaulted.  When any coordinate is
    None the resulting FixtureInput carries UNKNOWN provenance and
    is_trustworthy=False → all collision checks return NOT_VERIFIABLE.

    provenance:
        USER_CONFIRMED (default) — engineer entered/confirmed WCS at NC gen time
        KNOWN          — from a measured or referenced source
        (UNKNOWN is set automatically when any coordinate is None)
    """

    fixture_id: str
    wcs_centre_x_mm: float | None = None
    wcs_centre_y_mm: float | None = None
    wcs_bottom_z_mm: float | None = None
    provenance: GeometryFieldProvenance = GeometryFieldProvenance.USER_CONFIRMED


# ---------------------------------------------------------------------------
# Production verification request
# ---------------------------------------------------------------------------


@dataclass
class WorkflowVerificationRequest:
    """Single-candidate production verification request.

    All supplementary geometry fields are optional. Missing fields propagate
    conservatively: UNKNOWN / NOT_VERIFIABLE / INSUFFICIENT_DATA — never PASS.

    candidate:
        P7 OfflineNCCandidate (nc_candidate_review_ready must be True for
        full production flow; works with any candidate for verification-only use).

    machine_record:
        Machine catalog dict (from seed_machine_catalog()), or None.
        Required for machine envelope check.

    stock_def:
        StockDefinition from setup_stock, or None.
        Required for stock removal simulation.

    fixture_selections:
        List of FixtureSelection objects with engineer-confirmed WCS positions.
        Empty list → all fixture/collision checks return NOT_VERIFIABLE.

    tool_record:
        CuttingToolCatalogRecord, or None.
        Required for flute_length_mm / overall_length_mm to run tool reach check.

    holder_record:
        ToolHolderCatalogRecord, or None.
        Required for holder body_diameter_mm to run holder collision check.
    """

    candidate: Any
    machine_record: dict | None = None
    stock_def: Any | None = None
    fixture_selections: list[FixtureSelection] = field(default_factory=list)
    tool_record: Any | None = None
    holder_record: Any | None = None


# ---------------------------------------------------------------------------
# Production verification result
# ---------------------------------------------------------------------------


@dataclass
class WorkflowVerificationResult:
    """Extended verification result with workflow and simulation metadata.

    Wraps P8VerificationResult and exposes separate simulation metadata
    per MUST 9 requirements.

    simulation_method:
        Always VOXEL_APPROXIMATION. Never EXACT_BOOLEAN.

    simulation_ran:
        True if the voxel simulation engine was invoked (segments were present
        and stock model was supplied). Does not imply a meaningful result.

    stock_removal_validated:
        From p8_result.stock_removal_validated. Preserved verbatim.

    gouge_validated:
        Always NOT_VERIFIABLE from DXF workflow (requires STEP part_bbox).
        Preserved verbatim from p8_result.

    collision_scope_validated:
        Summary of the three collision checks (tool, holder, fixture).
        Values:
          SCOPED_FAIL     — at least one collision check ran and failed
          SCOPED_PASS     — all collision checks that ran passed; none failed
          NOT_VERIFIABLE  — no collision check ran (no trustworthy fixture/holder)
          PARTIAL         — mixed states across collision checks
        Note: SCOPED_PASS does NOT imply global collision safety.

    rapid_segments_checked:
        Count of RAPID motion segments included in verification.

    feed_segments_checked:
        Count of CUT/FEED motion segments included in verification.

    fixture_selections_processed:
        Total number of FixtureSelection objects in the request.

    fixture_resolved_count:
        Fixtures resolved from catalog (stable_id found). May still be
        NOT_VERIFIABLE if WCS was incomplete.

    fixture_trustworthy_count:
        Fixtures with is_trustworthy=True (USER_CONFIRMED or KNOWN provenance
        and all WCS coordinates supplied). Only these affect collision checks.

    fixture_unknown_count:
        Fixtures where WCS was incomplete or stable_id not found → UNKNOWN provenance.

    stock_def_supplied:
        True if stock_def was not None in the request.
    """

    p8_result: P8VerificationResult
    simulation_method: str
    simulation_ran: bool
    stock_removal_validated: str
    gouge_validated: str
    collision_scope_validated: str
    rapid_segments_checked: int
    feed_segments_checked: int
    fixture_selections_processed: int
    fixture_resolved_count: int
    fixture_trustworthy_count: int
    fixture_unknown_count: int
    stock_def_supplied: bool
    warnings: list[str] = field(default_factory=list)

    # Safety invariants — always enforced (delegated to p8_result)
    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def production_released(self) -> bool:
        return False


# ---------------------------------------------------------------------------
# Fixture selection → FixtureInput resolution
# ---------------------------------------------------------------------------


def _resolve_fixture_selection(
    sel: FixtureSelection,
    warnings: list[str],
) -> FixtureInput:
    """Resolve a FixtureSelection to a FixtureInput.

    Resolution logic:
      1. Look up fixture_id in the fixture catalog.
         Not found → UNKNOWN provenance (NOT_VERIFIABLE).
      2. If any WCS coordinate is None → UNKNOWN provenance (NOT_VERIFIABLE).
      3. Otherwise → make_fixture_input_from_library with engineer provenance.

    Returns a FixtureInput in all cases. When UNKNOWN provenance is set,
    the resulting FixtureInput.is_trustworthy=False → NOT_VERIFIABLE in checks.
    """
    record = get_fixture_by_id(sel.fixture_id)
    if record is None:
        warnings.append(
            f"FIXTURE_UNKNOWN_ID: '{sel.fixture_id}' not found in fixture catalog; "
            "provenance=UNKNOWN → collision check NOT_VERIFIABLE"
        )
        # Return a minimal UNKNOWN-provenance fixture so the structure is complete
        return FixtureInput(
            fixture_id=sel.fixture_id,
            fixture_type=FixtureType.CLAMPS,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.UNKNOWN,
            min_x_mm=0.0,
            min_y_mm=0.0,
            min_z_mm=0.0,
            max_x_mm=0.0,
            max_y_mm=0.0,
            max_z_mm=0.0,
        )

    if (
        sel.wcs_centre_x_mm is None
        or sel.wcs_centre_y_mm is None
        or sel.wcs_bottom_z_mm is None
    ):
        warnings.append(
            f"FIXTURE_WCS_INCOMPLETE: '{sel.fixture_id}' has None WCS coordinate(s); "
            "provenance=UNKNOWN → collision check NOT_VERIFIABLE"
        )
        return FixtureInput(
            fixture_id=sel.fixture_id,
            fixture_type=record.fixture_type,
            source=FixtureSource.USER_DEFINED,
            provenance=GeometryFieldProvenance.UNKNOWN,
            min_x_mm=0.0,
            min_y_mm=0.0,
            min_z_mm=0.0,
            max_x_mm=0.0,
            max_y_mm=0.0,
            max_z_mm=0.0,
        )

    return make_fixture_input_from_library(
        record,
        wcs_centre_x_mm=sel.wcs_centre_x_mm,
        wcs_centre_y_mm=sel.wcs_centre_y_mm,
        wcs_bottom_z_mm=sel.wcs_bottom_z_mm,
        provenance=sel.provenance,
    )


# ---------------------------------------------------------------------------
# Collision scope summary
# ---------------------------------------------------------------------------

_PASS = "PASS"
_FAIL = "FAIL"
_NV = "NOT_VERIFIABLE"
_ID = "INSUFFICIENT_DATA"


def _collision_scope(
    tool_col: str,
    holder_col: str,
    fixture_col: str,
) -> str:
    """Summarise three scoped collision check statuses into a scope descriptor.

    Rules (conservative — fail-closed):
      Any FAIL → SCOPED_FAIL
      All NOT_VERIFIABLE / INSUFFICIENT_DATA → NOT_VERIFIABLE
      All three ran AND all PASS → SCOPED_PASS (no check was skipped)
      Any check NOT_VERIFIABLE or INSUFFICIENT_DATA + others PASS → PARTIAL

    IMPORTANT: SCOPED_PASS does NOT imply global collision safety.
    SCOPED_PASS requires that all three checks (tool, holder, fixture) ran
    and returned PASS — not just the ones that could run.
    """
    statuses = [tool_col, holder_col, fixture_col]
    if _FAIL in statuses:
        return "SCOPED_FAIL"
    blocked = [s for s in statuses if s in (_NV, _ID, "NOT_PERFORMED")]
    if len(blocked) == 3:
        return _NV
    # At least one check ran
    if blocked:
        # Some checks could not run → PARTIAL (not SCOPED_PASS)
        return "PARTIAL"
    # All three checks ran
    if all(s == _PASS for s in statuses):
        return "SCOPED_PASS"
    return "PARTIAL"


# ---------------------------------------------------------------------------
# Rapid / feed segment counting
# ---------------------------------------------------------------------------


def _count_rapid_feed(candidate: Any) -> tuple[int, int]:
    """Count RAPID and FEED motion segments from nc_segments."""
    nc_segs = getattr(candidate, "nc_segments", []) or []
    segments = nc_segments_to_verification_segments(nc_segs)
    rapid = sum(1 for s in segments if s.motion_type == "RAPID")
    feed = sum(1 for s in segments if s.motion_type == "CUT")
    return rapid, feed


# ---------------------------------------------------------------------------
# P10-C/G: run_production_verification
# ---------------------------------------------------------------------------


def run_production_verification(
    request: WorkflowVerificationRequest,
) -> WorkflowVerificationResult:
    """Run production-workflow verification for a single candidate.

    Flow (per MUST 7):
      Stock Definition → Toolpath → Tool Geometry → Fixture/WCS
      → Voxel Simulation → Verification Result

    Returns a WorkflowVerificationResult with separate simulation metadata fields.

    All geometry gaps propagate conservatively:
      No fixture WCS → NOT_VERIFIABLE (not PASS)
      No stock def   → NOT_VERIFIABLE (not PASS)
      No STEP bbox   → GOUGE=NOT_VERIFIABLE (always, from DXF workflow)
      No tool record → INSUFFICIENT_DATA (tool reach blocked)
    """
    warnings: list[str] = []

    # --- Rapid / feed segment counts (MUST 11) ---
    rapid_count, feed_count = _count_rapid_feed(request.candidate)

    # --- Resolve fixture selections → FixtureInput list ---
    fixture_inputs: list[FixtureInput] = []
    resolved_count = 0
    trustworthy_count = 0
    unknown_count = 0

    for sel in request.fixture_selections:
        fi = _resolve_fixture_selection(sel, warnings)
        fixture_inputs.append(fi)
        record = get_fixture_by_id(sel.fixture_id)
        if record is not None:
            resolved_count += 1
        if fi.is_trustworthy:
            trustworthy_count += 1
        else:
            unknown_count += 1

    if not fixture_inputs:
        warnings.append(
            "FIXTURE_SELECTIONS_EMPTY: no fixture selections supplied; "
            "TOOL_COLLISION=NOT_VERIFIABLE, FIXTURE_COLLISION=NOT_VERIFIABLE, "
            "HOLDER_COLLISION=NOT_VERIFIABLE"
        )

    # --- Build verification input ---
    vi = build_verification_input(
        candidate=request.candidate,
        machine_record=request.machine_record,
        stock_def=request.stock_def,
        fixture_inputs=fixture_inputs,
        tool_record=request.tool_record,
        holder_record=request.holder_record,
    )

    # --- Run P8 verification ---
    p8_result = run_p8_verification(vi)

    # --- Simulation metadata ---
    simulation_ran = (
        p8_result.simulation_result is not None
        and bool(getattr(p8_result.simulation_result, "checks", None))
    )
    stock_def_supplied = request.stock_def is not None

    # --- Collision scope summary ---
    cscope = _collision_scope(
        p8_result.tool_collision_validated,
        p8_result.holder_collision_validated,
        p8_result.fixture_collision_validated,
    )

    return WorkflowVerificationResult(
        p8_result=p8_result,
        simulation_method=SIMULATION_METHOD,
        simulation_ran=simulation_ran,
        stock_removal_validated=p8_result.stock_removal_validated,
        gouge_validated=p8_result.gouge_validated,
        collision_scope_validated=cscope,
        rapid_segments_checked=rapid_count,
        feed_segments_checked=feed_count,
        fixture_selections_processed=len(request.fixture_selections),
        fixture_resolved_count=resolved_count,
        fixture_trustworthy_count=trustworthy_count,
        fixture_unknown_count=unknown_count,
        stock_def_supplied=stock_def_supplied,
        warnings=warnings + p8_result.warnings,
    )
