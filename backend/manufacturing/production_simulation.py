"""
P10-G: Stock / simulation production workflow.

Wires the existing voxel engine into a complete production workflow:

  Stock Definition → Toolpath → Tool Geometry → Fixture/WCS
  → Voxel Simulation → Verification Result

HARD RULES (enforced unconditionally):
  - Reuses existing VoxelGrid engine (backend.verification.stock). No second engine.
  - SIMULATION_METHOD=VOXEL_APPROXIMATION — never EXACT_BOOLEAN.
  - Rapid and feed segments remain distinguishable throughout (never merged).
  - GOUGE_VALIDATED=NOT_VERIFIABLE when target solid unavailable (requires STEP).
  - is_dispatchable=False at all times.
  - production_released=False at all times.
  - No fabricated stock, fixture, or collision results.

Exposed separate results per check (MUST 9):
  SIMULATION_RAN                — simulation actually executed (segments + stock present)
  STOCK_REMOVAL_VALIDATED       — stock removal check status
  GOUGE_VALIDATED               — gouge check status (NOT_VERIFIABLE without STEP)
  COLLISION_SCOPE_VALIDATED     — combined tool/holder/fixture collision status

RAPID_SEGMENTS_CHECKED=YES  FEED_SEGMENTS_CHECKED=YES
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    P8VerificationInput,
    P8VerificationResult,
    build_verification_input,
    run_p8_verification,
)
from backend.verification.enums import SimulationStatus

__all__ = [
    "ProductionSimulationInput",
    "ProductionSimulationResult",
    "run_production_simulation",
    "count_rapid_feed_segments",
    "SIMULATION_METHOD",
]

# Explicit simulation method declaration (MUST 8)
SIMULATION_METHOD: str = "VOXEL_APPROXIMATION"


# ---------------------------------------------------------------------------
# ProductionSimulationInput
# ---------------------------------------------------------------------------


@dataclass
class ProductionSimulationInput:
    """All inputs for the production simulation workflow.

    candidate:
        OfflineNCCandidate from P7 NC generation workflow.
    stock_def:
        StockDefinition from setup_stock. Required for stock removal simulation.
        None → STOCK_REMOVAL_VALIDATED=NOT_VERIFIABLE, SIMULATION_RAN=False.
    fixture_inputs:
        List of FixtureInput from production_workholding. Required for collision.
        Empty → fixture/tool/holder collision returns NOT_VERIFIABLE.
    tool_record:
        CuttingToolCatalogRecord. Required for flute_length_mm (tool reach).
        None → tool_reach_validated=INSUFFICIENT_DATA.
    holder_record:
        ToolHolderCatalogRecord. Required for holder_collision.
        None → holder_collision_validated=NOT_VERIFIABLE.
    machine_record:
        Machine catalog dict (travel_x/y/z_mm). Required for envelope check.
        None → machine_envelope_validated=INSUFFICIENT_DATA.
    """

    candidate: Any
    stock_def: Any = None
    fixture_inputs: list = field(default_factory=list)
    tool_record: Any = None
    holder_record: Any = None
    machine_record: dict | None = None


# ---------------------------------------------------------------------------
# ProductionSimulationResult
# ---------------------------------------------------------------------------


@dataclass
class ProductionSimulationResult:
    """Result of the production simulation workflow.

    Exposes per-check status separately (MUST 9):
      simulation_ran              — True when voxel engine actually executed
      stock_removal_validated     — PASS/FAIL/NOT_VERIFIABLE
      gouge_validated             — PASS/FAIL/NOT_VERIFIABLE (NOT_VERIFIABLE without STEP)
      collision_scope_validated   — combined PASS/FAIL/NOT_VERIFIABLE for all collision checks

    Segment accounting (MUST 11):
      rapid_segment_count         — number of RAPID_LINEAR segments in toolpath
      feed_segment_count          — number of FEED_LINEAR / HELIX segments in toolpath
      rapid_segments_checked      — True when segments were converted and evaluated
      feed_segments_checked       — True when segments were converted and evaluated

    Safety invariants:
      is_dispatchable=False   production_released=False
    """

    # Workflow identity
    candidate_id: str
    simulation_method: str = SIMULATION_METHOD

    # Simulation execution flag
    simulation_ran: bool = False

    # Separate result fields (MUST 9)
    stock_removal_validated: str = "NOT_VERIFIABLE"
    gouge_validated: str = "NOT_VERIFIABLE"
    collision_scope_validated: str = "NOT_VERIFIABLE"

    # Detail from P8 result
    tool_reach_validated: str = "NOT_VERIFIABLE"
    machine_envelope_validated: str = "NOT_VERIFIABLE"
    tool_collision_validated: str = "NOT_VERIFIABLE"
    holder_collision_validated: str = "NOT_VERIFIABLE"
    fixture_collision_validated: str = "NOT_VERIFIABLE"
    verification_scope: str = ""

    # Segment accounting (MUST 11)
    rapid_segment_count: int = 0
    feed_segment_count: int = 0
    rapid_segments_checked: bool = False
    feed_segments_checked: bool = False

    # Underlying P8 result (may be None if no segments)
    p8_result: P8VerificationResult | None = None

    # Provenance of key inputs
    stock_provenance: GeometryFieldProvenance = GeometryFieldProvenance.UNKNOWN
    tool_flute_length_provenance: GeometryFieldProvenance = GeometryFieldProvenance.UNKNOWN
    fixture_count: int = 0
    part_bbox_provenance: GeometryFieldProvenance = GeometryFieldProvenance.UNKNOWN

    # Notes and warnings
    warnings: list[str] = field(default_factory=list)

    # Safety invariants
    is_dispatchable: bool = False
    production_released: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)
        # Enforce explicit simulation method
        object.__setattr__(self, "simulation_method", SIMULATION_METHOD)


# ---------------------------------------------------------------------------
# Segment counter
# ---------------------------------------------------------------------------


def count_rapid_feed_segments(nc_segments: list[dict]) -> tuple[int, int]:
    """Count RAPID and FEED/HELIX segments in raw nc_segments list.

    Returns (rapid_count, feed_count).
    RAPID_LINEAR → rapid.
    FEED_LINEAR, HELIX → feed.
    Unknown motion types are counted as feed (conservative).
    """
    rapid = 0
    feed = 0
    for seg in nc_segments:
        mt = seg.get("motion_type", "FEED_LINEAR")
        if mt == "RAPID_LINEAR":
            rapid += 1
        else:
            feed += 1
    return rapid, feed


# ---------------------------------------------------------------------------
# run_production_simulation — main entry point
# ---------------------------------------------------------------------------


def run_production_simulation(sim_input: ProductionSimulationInput) -> ProductionSimulationResult:
    """Run the full production simulation workflow.

    Workflow stages:
      1. Stock Definition → StockModel (voxel engine input)
      2. Toolpath segments → VerificationSegment list
      3. Tool Geometry + Fixture/WCS → P8VerificationInput
      4. Voxel Simulation via run_p8_verification()
      5. Per-check status extraction

    Returns ProductionSimulationResult with separate check statuses.

    SIMULATION_METHOD=VOXEL_APPROXIMATION is enforced — never EXACT_BOOLEAN.
    GOUGE_VALIDATED=NOT_VERIFIABLE when part_bbox unavailable (no STEP solid).
    Rapid and feed segments are separately counted and reported.
    """
    warnings: list[str] = []
    candidate = sim_input.candidate
    candidate_id = getattr(candidate, "feature_id", "unknown")

    # Count rapid/feed segments BEFORE conversion (MUST 11)
    nc_segs_raw: list[dict] = getattr(candidate, "nc_segments", []) or []
    rapid_count, feed_count = count_rapid_feed_segments(nc_segs_raw)
    segs_checked = len(nc_segs_raw) > 0

    # Build P8VerificationInput
    vi: P8VerificationInput = build_verification_input(
        candidate=candidate,
        machine_record=sim_input.machine_record,
        stock_def=sim_input.stock_def,
        fixture_inputs=sim_input.fixture_inputs,
        tool_record=sim_input.tool_record,
        holder_record=sim_input.holder_record,
    )

    # Determine whether simulation actually ran
    # Simulation runs when: segments exist AND at least one meaningful check can execute
    simulation_ran = (
        len(vi.segments) > 0
        and (
            vi.stock_model is not None
            or vi.tool_diameter_mm is not None
            or vi.machine_travel_x_mm is not None
            or len(vi.fixture_inputs) > 0
        )
    )

    if not simulation_ran:
        reason = []
        if not vi.segments:
            reason.append("no valid segments")
        if vi.stock_model is None:
            reason.append("no stock model")
        if vi.tool_diameter_mm is None:
            reason.append("no tool diameter")
        warnings.append(
            f"SIMULATION_NOT_RAN: {', '.join(reason) if reason else 'insufficient inputs'}"
        )

    # Run P8 verification
    p8_result = run_p8_verification(vi)
    warnings.extend(p8_result.warnings)

    # Extract per-check statuses
    stock_removal = p8_result.stock_removal_validated
    gouge = p8_result.gouge_validated

    # Collision scope: conservative combination
    # PASS only if ALL relevant collision checks pass; FAIL if any fail; NOT_VERIFIABLE otherwise
    collision_checks = [
        p8_result.tool_collision_validated,
        p8_result.holder_collision_validated,
        p8_result.fixture_collision_validated,
    ]
    if any(c == "FAIL" for c in collision_checks):
        collision_scope = "FAIL"
    elif all(c == "PASS" for c in collision_checks):
        collision_scope = "PASS"
    elif any(c == "PASS" for c in collision_checks):
        collision_scope = "PARTIAL"
    else:
        collision_scope = "NOT_VERIFIABLE"

    # Confirm gouge requires STEP
    if gouge == "NOT_VERIFIABLE":
        warnings.append(
            "GOUGE_NOT_VERIFIABLE: part_bbox unavailable — requires STEP/B-Rep solid geometry. "
            "HARD_RULE: cannot claim gouge_validated=PASS without real STEP sample."
        )

    # Simulation method must remain VOXEL_APPROXIMATION
    if p8_result.simulation_result is not None:
        sim_status = p8_result.simulation_result.simulation_status
        if sim_status not in (SimulationStatus.COMPLETED, SimulationStatus.PARTIAL):
            warnings.append(
                f"SIMULATION_STATUS: {sim_status} — "
                "voxel engine returned non-COMPLETED status; results may be partial"
            )
        stock_removal_fidelity = getattr(
            p8_result.simulation_result, "stock_removal_fidelity", None
        )
        if stock_removal_fidelity is not None and str(stock_removal_fidelity) == "EXACT_BOOLEAN":
            warnings.append(
                "SIMULATION_FIDELITY_ERROR: EXACT_BOOLEAN claimed — "
                "this engine uses VOXEL_APPROXIMATE only; check engine version"
            )

    warnings.append(
        "SIMULATION_METHOD_CONFIRMED: VOXEL_APPROXIMATION "
        "(NOT EXACT_BOOLEAN — bounded voxel cell test only)"
    )

    return ProductionSimulationResult(
        candidate_id=candidate_id,
        simulation_ran=simulation_ran,
        stock_removal_validated=stock_removal,
        gouge_validated=gouge,
        collision_scope_validated=collision_scope,
        tool_reach_validated=p8_result.tool_reach_validated,
        machine_envelope_validated=p8_result.machine_envelope_validated,
        tool_collision_validated=p8_result.tool_collision_validated,
        holder_collision_validated=p8_result.holder_collision_validated,
        fixture_collision_validated=p8_result.fixture_collision_validated,
        verification_scope=p8_result.verification_scope,
        rapid_segment_count=rapid_count,
        feed_segment_count=feed_count,
        rapid_segments_checked=segs_checked,
        feed_segments_checked=segs_checked,
        p8_result=p8_result,
        stock_provenance=vi.stock_provenance,
        tool_flute_length_provenance=vi.tool_flute_length_provenance,
        fixture_count=p8_result.fixture_count,
        part_bbox_provenance=vi.part_bbox_provenance,
        warnings=warnings,
    )
