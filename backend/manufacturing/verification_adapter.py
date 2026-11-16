"""
P8 verification adapter — wires OfflineNCCandidate into the existing verification engine.

P8-A: Canonical adapter from toolpath candidate to verification input (MUST 4–7).
P8-B: Tool geometry provenance tracking — UNKNOWN remains UNKNOWN (MUST 8–12).
P8-C: Fixture geometry input model with provenance (MUST 13–17).
P8-D: Bounded offline collision / clearance checks (MUST 18–22).
P8-E: Machine envelope wiring from machine catalog (MUST 23–26).

HARD RULES (all enforced unconditionally):
  - UNKNOWN remains UNKNOWN — missing geometry NEVER becomes a pass.
  - NO_FABRICATED_GEOMETRY=YES
  - is_dispatchable=False at all times.
  - production_released=False at all times.
  - GEOMETRY_CHECK_PASS != COLLISION_VALIDATED (labels kept separate).
  - Fixture absent → FIXTURE_COLLISION_VALIDATED=NOT_VERIFIABLE.
  - Holder geometry absent → HOLDER_COLLISION_VALIDATED=NOT_VERIFIABLE.
  - 2D DXF + engineer-confirmed depth → scope CLEARANCE_CHECK_2_5D only.
  - STEP/B-Rep geometry absent → part gouge check returns NOT_VERIFIABLE.

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE  PRODUCTION_RELEASED=ALWAYS_FALSE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from backend.verification.enums import (
    FixtureSource,
    FixtureType,
    StockShape,
    VerificationStatus,
)
from backend.verification.models import SimulationRequest, SimulationResult, VerificationSegment
from backend.verification.simulation import run_simulation
from backend.verification.stock import FixtureGeometry, StockModel

__all__ = [
    "GeometryFieldProvenance",
    "FixtureInput",
    "P8VerificationInput",
    "P8VerificationResult",
    "build_verification_input",
    "run_p8_verification",
    "nc_segments_to_verification_segments",
    "stock_definition_to_stock_model",
]


# ---------------------------------------------------------------------------
# Provenance labels (MUST 5)
# ---------------------------------------------------------------------------


class GeometryFieldProvenance(StrEnum):
    """Provenance label for every safety-critical geometric field."""
    KNOWN = "KNOWN"
    USER_CONFIRMED = "USER_CONFIRMED"
    PROPOSED = "PROPOSED"
    UNKNOWN = "UNKNOWN"


# Canonical NOT_VERIFIABLE status string used throughout.
_NOT_VERIFIABLE = "NOT_VERIFIABLE"
_PASS = "PASS"
_FAIL = "FAIL"
_INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
_NOT_PERFORMED = "NOT_PERFORMED"


# ---------------------------------------------------------------------------
# Fixture input model (P8-C)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FixtureInput:
    """Engineer-supplied fixture geometry with explicit provenance.

    Coordinates must come from USER_CONFIRMED or LIBRARY_EVIDENCE.
    NEVER fabricate min_x/y/z or max_x/y/z values.

    provenance must be one of:
        USER_CONFIRMED     — engineer entered / confirmed coordinates
        LIBRARY_EVIDENCE   — from a known fixture catalog record
        FILE_EVIDENCE      — imported from a geometry file
        UNKNOWN            — coordinates not available → renders NOT_VERIFIABLE
    """
    fixture_id: str
    fixture_type: FixtureType
    source: FixtureSource
    provenance: GeometryFieldProvenance
    min_x_mm: float
    min_y_mm: float
    min_z_mm: float
    max_x_mm: float
    max_y_mm: float
    max_z_mm: float

    @property
    def is_trustworthy(self) -> bool:
        return self.provenance in (
            GeometryFieldProvenance.USER_CONFIRMED,
            GeometryFieldProvenance.KNOWN,
        )

    def to_fixture_geometry(self) -> FixtureGeometry:
        return FixtureGeometry(
            fixture_id=self.fixture_id,
            fixture_type=self.fixture_type,
            source=self.source,
            min_x_mm=self.min_x_mm,
            min_y_mm=self.min_y_mm,
            min_z_mm=self.min_z_mm,
            max_x_mm=self.max_x_mm,
            max_y_mm=self.max_y_mm,
            max_z_mm=self.max_z_mm,
        )


# ---------------------------------------------------------------------------
# Verification input (assembled from P7 candidate + supplementary geometry)
# ---------------------------------------------------------------------------


@dataclass
class P8VerificationInput:
    """All geometry inputs assembled from P7 manufacturing workflow.

    Each safety-critical field carries an explicit provenance label.
    UNKNOWN fields remain UNKNOWN — they never become defaults.

    This is the canonical intermediate between OfflineNCCandidate and
    the existing backend.verification.simulation.run_simulation() engine.
    """

    # Identity
    candidate_id: str
    feature_id: str
    toolpath_id: str | None

    # Segments derived from nc_segments
    segments: list[VerificationSegment]

    # Tool geometry (P8-B)
    tool_diameter_mm: float | None
    tool_diameter_provenance: GeometryFieldProvenance
    tool_flute_length_mm: float | None
    tool_flute_length_provenance: GeometryFieldProvenance
    tool_overall_length_mm: float | None
    tool_overall_length_provenance: GeometryFieldProvenance
    tool_cutting_length_mm: float | None
    tool_cutting_length_provenance: GeometryFieldProvenance

    # Holder geometry (P8-B)
    holder_diameter_mm: float | None
    holder_diameter_provenance: GeometryFieldProvenance
    holder_length_mm: float | None
    holder_length_provenance: GeometryFieldProvenance

    # Stock (P8-D)
    stock_model: StockModel | None
    stock_provenance: GeometryFieldProvenance

    # Fixtures (P8-C)
    fixture_inputs: list[FixtureInput]

    # Machine envelope (P8-E)
    machine_travel_x_mm: float | None
    machine_travel_y_mm: float | None
    machine_travel_z_mm: float | None
    machine_travel_provenance: GeometryFieldProvenance

    # Part bounding box (requires STEP — almost always UNKNOWN from DXF)
    part_bbox_min: tuple[float, float, float] | None
    part_bbox_max: tuple[float, float, float] | None
    part_bbox_provenance: GeometryFieldProvenance

    # Verification scope description (MUST 20)
    verification_scope: str

    # Provenance audit trail
    provenance_notes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# P8 verification result
# ---------------------------------------------------------------------------


@dataclass
class P8VerificationResult:
    """Offline geometric verification result for a single NC candidate.

    Preserves all P7 readiness levels (unchanged).
    Adds independent P8 verification states — none implies the others.

    Status values per check:
      PASS           — geometric check ran and passed
      FAIL           — geometric check ran and found a problem
      NOT_VERIFIABLE — required geometry was absent (fixture/holder/part)
      INSUFFICIENT_DATA — required tool/stock field was absent
      NOT_PERFORMED  — check not attempted for this profile

    Safety invariants: is_dispatchable and production_released remain False.
    GEOMETRY_CHECK_PASS != COLLISION_VALIDATED (kept separate per MUST 21).
    """

    # Input identity
    candidate_id: str
    feature_id: str
    toolpath_id: str | None
    verification_scope: str

    # P8 independent verification states (MUST 37)
    geometry_verification_ready: bool
    tool_reach_validated: str
    machine_envelope_validated: str
    tool_collision_validated: str
    holder_collision_validated: str
    fixture_collision_validated: str
    stock_removal_validated: str
    gouge_validated: str

    # Underlying simulation result (may be None if segments empty)
    simulation_result: SimulationResult | None

    # Provenance summary
    tool_diameter_provenance: GeometryFieldProvenance
    tool_flute_length_provenance: GeometryFieldProvenance
    machine_travel_provenance: GeometryFieldProvenance
    fixture_count: int
    part_bbox_provenance: GeometryFieldProvenance
    stock_provenance: GeometryFieldProvenance

    # Warnings and notes
    warnings: list[str] = field(default_factory=list)
    provenance_notes: list[str] = field(default_factory=list)

    # Safety invariants — always enforced
    is_dispatchable: bool = False
    production_released: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)


# ---------------------------------------------------------------------------
# Segment conversion (MUST 4)
# ---------------------------------------------------------------------------

# Maps NC bridge motion type strings back to verification-compatible labels.
# NC bridge uses "RAPID_LINEAR" / "FEED_LINEAR"; verification checks use "RAPID" / "CUT".
_NC_TO_VERIF_MOTION: dict[str, str] = {
    "RAPID_LINEAR": "RAPID",
    "FEED_LINEAR": "CUT",
    "HELIX": "CUT",
}


def nc_segments_to_verification_segments(
    nc_segments: list[dict],
) -> list[VerificationSegment]:
    """Convert nc_bridge output dicts to VerificationSegment objects.

    Only segments that have both start and end coordinates are included.
    Segments with missing or non-finite coordinates are silently skipped
    (the caller's warnings list records the skip count).

    Motion type mapping:
      RAPID_LINEAR → RAPID  (non-cutting rapid / approach / retract / link)
      FEED_LINEAR  → CUT    (cutting feed)
      HELIX        → CUT    (cutting helix)
    """
    result: list[VerificationSegment] = []
    for seg_dict in nc_segments:
        # Require all six coordinate fields.
        try:
            sx = float(seg_dict["start_x"])
            sy = float(seg_dict["start_y"])
            sz = float(seg_dict["start_z"])
            ex = float(seg_dict["end_x"])
            ey = float(seg_dict["end_y"])
            ez = float(seg_dict["end_z"])
        except (KeyError, TypeError, ValueError):
            continue

        import math
        if any(math.isnan(v) or math.isinf(v) for v in (sx, sy, sz, ex, ey, ez)):
            continue

        raw_motion = seg_dict.get("motion_type", "RAPID_LINEAR")
        verif_motion = _NC_TO_VERIF_MOTION.get(raw_motion, raw_motion)

        is_cutting = bool(seg_dict.get("is_cutting", False))

        result.append(
            VerificationSegment(
                segment_id=str(seg_dict.get("segment_id", "")),
                start_x=sx,
                start_y=sy,
                start_z=sz,
                end_x=ex,
                end_y=ey,
                end_z=ez,
                motion_type=verif_motion,
                is_cutting=is_cutting,
                operation_id=seg_dict.get("operation_id"),
                tool_id=seg_dict.get("tool_id"),
                setup_id=seg_dict.get("setup_id"),
                feature_id=seg_dict.get("feature_id"),
            )
        )
    return result


# ---------------------------------------------------------------------------
# StockDefinition → StockModel adapter (P8-D)
# ---------------------------------------------------------------------------


def stock_definition_to_stock_model(stock_def: Any) -> StockModel | None:
    """Convert a manufacturing.setup_stock.StockDefinition to a verification StockModel.

    Returns None if the stock definition lacks sufficient dimensions.
    Fidelity is set to ANALYTIC_PRIMITIVE for explicit dimensions.

    StockShape mapping:
      RECTANGULAR_BLOCK / PLATE / FORGING → BOX
      ROUND_BAR / RING                    → CYLINDER (outer bounding cylinder)
    """
    from backend.manufacturing.setup_stock import StockShape as MfgStockShape
    from backend.manufacturing.setup_stock import validate_stock_dimensions
    from backend.verification.enums import StockFidelity

    if stock_def is None:
        return None

    missing = validate_stock_dimensions(stock_def)
    if missing:
        return None

    shape = stock_def.shape

    if shape in (MfgStockShape.RECTANGULAR_BLOCK, MfgStockShape.PLATE, MfgStockShape.FORGING):
        # Center at origin; engineer defines stock origin relative to WCS at setup time.
        half_l = stock_def.length_mm / 2.0
        half_w = stock_def.width_mm / 2.0
        return StockModel(
            shape=StockShape.BOX,
            fidelity=StockFidelity.ANALYTIC_PRIMITIVE,
            min_x_mm=-half_l,
            min_y_mm=-half_w,
            min_z_mm=-stock_def.height_mm,
            max_x_mm=half_l,
            max_y_mm=half_w,
            max_z_mm=0.0,
        )

    if shape == MfgStockShape.ROUND_BAR:
        r = stock_def.outer_diameter_mm / 2.0
        return StockModel(
            shape=StockShape.CYLINDER,
            fidelity=StockFidelity.ANALYTIC_PRIMITIVE,
            radius_mm=r,
            height_mm=stock_def.length_mm,
            center_x_mm=0.0,
            center_y_mm=0.0,
            bottom_z_mm=-stock_def.length_mm,
        )

    if shape == MfgStockShape.RING:
        # Use outer radius for conservative collision bounds.
        r = stock_def.outer_diameter_mm / 2.0
        return StockModel(
            shape=StockShape.CYLINDER,
            fidelity=StockFidelity.ANALYTIC_PRIMITIVE,
            radius_mm=r,
            height_mm=stock_def.length_mm,
            center_x_mm=0.0,
            center_y_mm=0.0,
            bottom_z_mm=-stock_def.length_mm,
        )

    return None


# ---------------------------------------------------------------------------
# P8-A: build_verification_input (MUST 4–7)
# ---------------------------------------------------------------------------


def build_verification_input(
    *,
    candidate: Any,
    machine_record: dict | None = None,
    stock_def: Any = None,
    fixture_inputs: list[FixtureInput] | None = None,
    tool_record: Any = None,
) -> P8VerificationInput:
    """Build a P8VerificationInput from an OfflineNCCandidate and supplementary geometry.

    Parameters
    ----------
    candidate:
        An OfflineNCCandidate from P7 (backend.manufacturing.nc_candidate).
    machine_record:
        A machine catalog dict (from seed_machine_catalog()), or None.
        Provides travel_x_mm, travel_y_mm, travel_z_mm for P8-E.
    stock_def:
        A StockDefinition from setup_stock, or None.
        Converted to StockModel if dimensions are complete.
    fixture_inputs:
        List of FixtureInput objects with explicit provenance. Default [].
        When empty, all fixture-dependent checks return NOT_VERIFIABLE.
    tool_record:
        A CuttingToolCatalogRecord, or None.
        Used to populate flute_length_mm and overall_length_mm when available.

    Notes
    -----
    - Every geometric field carries an explicit GeometryFieldProvenance label.
    - UNKNOWN fields remain UNKNOWN — no fabrication, no default-to-safe.
    - Segments with missing coordinates are silently skipped.
    - P7 nc_segments dicts → VerificationSegment conversion is lossless for
      all segments with valid start/end coordinate pairs.
    """
    provenance_notes: list[str] = []
    fixtures = fixture_inputs or []

    # --- Tool diameter (from P7 candidate — USER_CONFIRMED in P6 workflow) ---
    tool_diam = getattr(candidate, "tool_diameter_mm", None)
    tool_diam_prov = (
        GeometryFieldProvenance.USER_CONFIRMED
        if tool_diam is not None
        else GeometryFieldProvenance.UNKNOWN
    )
    if tool_diam is None:
        provenance_notes.append("TOOL_DIAMETER_UNKNOWN: tool_reach and collision checks blocked")

    # --- Flute length (from catalog record if available) ---
    flute_len: float | None = None
    flute_len_prov = GeometryFieldProvenance.UNKNOWN
    if tool_record is not None:
        fl = getattr(tool_record, "flute_length_mm", None)
        if fl is not None:
            flute_len = float(fl)
            flute_len_prov = GeometryFieldProvenance.KNOWN
        else:
            provenance_notes.append(
                f"FLUTE_LENGTH_MISSING: {getattr(tool_record, 'stable_id', '?')} "
                "has no flute_length_mm in catalog; TOOL_REACH check will return "
                "INSUFFICIENT_DATA"
            )

    # --- Overall length (from catalog record if available) ---
    overall_len: float | None = None
    overall_len_prov = GeometryFieldProvenance.UNKNOWN
    if tool_record is not None:
        ol = getattr(tool_record, "overall_length_mm", None)
        if ol is not None:
            overall_len = float(ol)
            overall_len_prov = GeometryFieldProvenance.KNOWN

    # --- Cutting length (from catalog record if available) ---
    cut_len: float | None = None
    cut_len_prov = GeometryFieldProvenance.UNKNOWN
    if tool_record is not None:
        cl = getattr(tool_record, "cutting_length_mm", None)
        if cl is not None:
            cut_len = float(cl)
            cut_len_prov = GeometryFieldProvenance.KNOWN

    # --- Holder geometry (not populated in P7; always UNKNOWN until P8-B data phase) ---
    holder_diam: float | None = None
    holder_diam_prov = GeometryFieldProvenance.UNKNOWN
    holder_len: float | None = None
    holder_len_prov = GeometryFieldProvenance.UNKNOWN
    provenance_notes.append(
        "HOLDER_GEOMETRY: outer diameter and body length not populated in P8; "
        "HOLDER_COLLISION_VALIDATED=NOT_VERIFIABLE"
    )

    # --- Stock model (P8-D) ---
    stock_model: StockModel | None = None
    stock_prov = GeometryFieldProvenance.UNKNOWN
    if stock_def is not None:
        stock_model = stock_definition_to_stock_model(stock_def)
        if stock_model is not None:
            stock_prov = GeometryFieldProvenance.USER_CONFIRMED
        else:
            provenance_notes.append(
                "STOCK_DEFINITION_INCOMPLETE: stock dimensions missing; "
                "stock collision checks blocked"
            )

    # --- Machine travel (P8-E) ---
    travel_x: float | None = None
    travel_y: float | None = None
    travel_z: float | None = None
    travel_prov = GeometryFieldProvenance.UNKNOWN
    if machine_record is not None:
        tx = machine_record.get("travel_x_mm")
        ty = machine_record.get("travel_y_mm")
        tz = machine_record.get("travel_z_mm")
        if tx is not None and ty is not None and tz is not None:
            travel_x = float(tx)
            travel_y = float(ty)
            travel_z = float(tz)
            travel_prov = GeometryFieldProvenance.KNOWN
        else:
            provenance_notes.append(
                "MACHINE_TRAVEL_UNKNOWN: machine record missing travel_x/y/z_mm; "
                "MACHINE_ENVELOPE check will return INSUFFICIENT_DATA"
            )

    # --- Part bounding box (requires STEP — UNKNOWN from DXF/IGES) ---
    part_bbox_min: tuple[float, float, float] | None = None
    part_bbox_max: tuple[float, float, float] | None = None
    part_bbox_prov = GeometryFieldProvenance.UNKNOWN
    provenance_notes.append(
        "PART_BBOX: not derivable from 2D DXF; requires STEP/B-Rep solid geometry; "
        "GOUGE check returns NOT_VERIFIABLE"
    )

    # --- Segment conversion (MUST 4) ---
    nc_segs_raw: list[dict] = getattr(candidate, "nc_segments", []) or []
    segments = nc_segments_to_verification_segments(nc_segs_raw)
    skipped = len(nc_segs_raw) - len(segments)
    if skipped > 0:
        provenance_notes.append(
            f"SEGMENT_SKIP: {skipped} nc_segment(s) skipped (missing/invalid coords)"
        )
    if not segments and nc_segs_raw:
        provenance_notes.append("SEGMENTS_EMPTY: all nc_segments had invalid coordinates")

    # --- Verification scope label (MUST 20) ---
    scope_parts: list[str] = []
    if segments:
        scope_parts.append("TOOLPATH_WIRED")
    if flute_len is not None:
        scope_parts.append("TOOL_REACH_CHECK")
    elif cut_len is not None:
        scope_parts.append("CUTTING_LENGTH_APPROX")
    if travel_x is not None:
        scope_parts.append("STATIC_ENVELOPE_CHECK")
    if fixtures:
        scope_parts.append("TOOL_COLLISION_CHECK")
    if stock_model is not None:
        scope_parts.append("STOCK_CHECK")
    if part_bbox_min is not None:
        scope_parts.append("GOUGE_CHECK")
    # DXF-derived geometry: label as 2.5D
    if segments and part_bbox_min is None:
        scope_parts.append("CLEARANCE_CHECK_2_5D")
    verification_scope = "+".join(scope_parts) if scope_parts else "NO_GEOMETRY"

    # --- Toolpath ID ---
    toolpath_id = getattr(candidate, "toolpath_id", None)

    return P8VerificationInput(
        candidate_id=getattr(candidate, "feature_id", "unknown"),
        feature_id=getattr(candidate, "feature_id", "unknown"),
        toolpath_id=toolpath_id,
        segments=segments,
        tool_diameter_mm=tool_diam,
        tool_diameter_provenance=tool_diam_prov,
        tool_flute_length_mm=flute_len,
        tool_flute_length_provenance=flute_len_prov,
        tool_overall_length_mm=overall_len,
        tool_overall_length_provenance=overall_len_prov,
        tool_cutting_length_mm=cut_len,
        tool_cutting_length_provenance=cut_len_prov,
        holder_diameter_mm=holder_diam,
        holder_diameter_provenance=holder_diam_prov,
        holder_length_mm=holder_len,
        holder_length_provenance=holder_len_prov,
        stock_model=stock_model,
        stock_provenance=stock_prov,
        fixture_inputs=fixtures,
        machine_travel_x_mm=travel_x,
        machine_travel_y_mm=travel_y,
        machine_travel_z_mm=travel_z,
        machine_travel_provenance=travel_prov,
        part_bbox_min=part_bbox_min,
        part_bbox_max=part_bbox_max,
        part_bbox_provenance=part_bbox_prov,
        verification_scope=verification_scope,
        provenance_notes=provenance_notes,
    )


# ---------------------------------------------------------------------------
# P8-D: run_p8_verification (MUST 7)
# ---------------------------------------------------------------------------


def run_p8_verification(vi: P8VerificationInput) -> P8VerificationResult:
    """Run offline geometric verification on a prepared P8VerificationInput.

    Returns a P8VerificationResult with per-check status.

    If segments are empty → geometry_verification_ready=False and
    all checks return NOT_VERIFIABLE or INSUFFICIENT_DATA.

    Safety invariants:
      is_dispatchable=False (enforced in __post_init__)
      production_released=False (enforced in __post_init__)
    """
    warnings: list[str] = list(vi.provenance_notes)

    if not vi.segments:
        return P8VerificationResult(
            candidate_id=vi.candidate_id,
            feature_id=vi.feature_id,
            toolpath_id=vi.toolpath_id,
            verification_scope="NO_SEGMENTS",
            geometry_verification_ready=False,
            tool_reach_validated=_NOT_VERIFIABLE,
            machine_envelope_validated=_NOT_VERIFIABLE,
            tool_collision_validated=_NOT_VERIFIABLE,
            holder_collision_validated=_NOT_VERIFIABLE,
            fixture_collision_validated=_NOT_VERIFIABLE,
            stock_removal_validated=_NOT_VERIFIABLE,
            gouge_validated=_NOT_VERIFIABLE,
            simulation_result=None,
            tool_diameter_provenance=vi.tool_diameter_provenance,
            tool_flute_length_provenance=vi.tool_flute_length_provenance,
            machine_travel_provenance=vi.machine_travel_provenance,
            fixture_count=0,
            part_bbox_provenance=vi.part_bbox_provenance,
            stock_provenance=vi.stock_provenance,
            warnings=["NO_SEGMENTS: nc_candidate has no valid segments; verification blocked"],
        )

    # Build SimulationRequest for existing verification engine
    fixture_geoms = [f.to_fixture_geometry() for f in vi.fixture_inputs if f.is_trustworthy]

    sim_req = SimulationRequest(
        toolpath_id=vi.toolpath_id or vi.candidate_id,
        segments=vi.segments,
        tool_diameter_mm=vi.tool_diameter_mm,
        tool_length_mm=vi.tool_overall_length_mm,
        tool_flute_length_mm=vi.tool_flute_length_mm,
        holder_diameter_mm=vi.holder_diameter_mm,
        holder_length_mm=vi.holder_length_mm,
        stock=vi.stock_model,
        fixtures=fixture_geoms,
        machine_travel_x_mm=vi.machine_travel_x_mm,
        machine_travel_y_mm=vi.machine_travel_y_mm,
        machine_travel_z_mm=vi.machine_travel_z_mm,
        part_bbox_min=vi.part_bbox_min,
        part_bbox_max=vi.part_bbox_max,
    )

    sim_result = run_simulation(sim_req)

    # --- Extract per-check statuses ---
    checks = sim_result.checks

    def _check_status(key: str) -> str:
        result = checks.get(key)
        if result is None:
            return _NOT_PERFORMED
        s = result.status
        if s == VerificationStatus.PASS:
            return _PASS
        if s == VerificationStatus.FAIL:
            return _FAIL
        if s == VerificationStatus.INSUFFICIENT_DATA:
            return _INSUFFICIENT_DATA
        if s == VerificationStatus.NOT_PERFORMED:
            return _NOT_PERFORMED
        # PARTIAL / ERROR → NOT_VERIFIABLE (conservative)
        return _NOT_VERIFIABLE

    # Tool reach (MUST 12)
    if vi.tool_flute_length_mm is None:
        tool_reach_status = _INSUFFICIENT_DATA
        warnings.append(
            "TOOL_REACH: flute_length_mm=UNKNOWN; check returns INSUFFICIENT_DATA"
        )
    else:
        tool_reach_status = _check_status("TOOL_REACH")

    # Machine envelope (MUST 25)
    if vi.machine_travel_x_mm is None:
        machine_env_status = _INSUFFICIENT_DATA
    else:
        machine_env_status = _check_status("MACHINE_ENVELOPE")

    # Tool collision (MUST 22) — only trustworthy (non-UNKNOWN-provenance) fixtures count
    if not fixture_geoms:
        tool_col_status = _NOT_VERIFIABLE
        warnings.append("TOOL_COLLISION: no trustworthy fixture geometry → NOT_VERIFIABLE")
    else:
        tool_col_status = _check_status("TOOL_COLLISION")

    # Holder collision (MUST 22)
    if vi.holder_diameter_mm is None:
        holder_col_status = _NOT_VERIFIABLE
        warnings.append("HOLDER_COLLISION: holder geometry UNKNOWN → NOT_VERIFIABLE")
    else:
        holder_col_status = _check_status("HOLDER_COLLISION")

    # Fixture collision (combined)
    if not fixture_geoms:
        fixture_col_status = _NOT_VERIFIABLE
    else:
        fixture_col_status = _check_status("FIXTURE_COLLISION")

    # Stock removal (MUST 36)
    if vi.stock_model is None:
        stock_rem_status = _NOT_VERIFIABLE
    else:
        stock_rem_status = _check_status("STOCK_REMAINING")

    # Gouge (MUST 17 — requires STEP)
    if vi.part_bbox_min is None:
        gouge_status = _NOT_VERIFIABLE
        warnings.append(
            "GOUGE: part_bbox=UNKNOWN (no STEP geometry); check returns NOT_VERIFIABLE"
        )
    else:
        part_gouge = _check_status("PART_GOUGE")
        stock_gouge = _check_status("STOCK_GOUGE")
        # Conservative: fail if either fails
        if _FAIL in (part_gouge, stock_gouge):
            gouge_status = _FAIL
        elif _PASS in (part_gouge, stock_gouge):
            gouge_status = _PASS
        else:
            gouge_status = _NOT_VERIFIABLE

    # geometry_verification_ready = at least one check ran and returned PASS or FAIL
    statuses = [
        tool_reach_status, machine_env_status, tool_col_status,
        holder_col_status, fixture_col_status, stock_rem_status, gouge_status,
    ]
    geometry_verification_ready = any(s in (_PASS, _FAIL) for s in statuses)

    return P8VerificationResult(
        candidate_id=vi.candidate_id,
        feature_id=vi.feature_id,
        toolpath_id=vi.toolpath_id,
        verification_scope=vi.verification_scope,
        geometry_verification_ready=geometry_verification_ready,
        tool_reach_validated=tool_reach_status,
        machine_envelope_validated=machine_env_status,
        tool_collision_validated=tool_col_status,
        holder_collision_validated=holder_col_status,
        fixture_collision_validated=fixture_col_status,
        stock_removal_validated=stock_rem_status,
        gouge_validated=gouge_status,
        simulation_result=sim_result,
        tool_diameter_provenance=vi.tool_diameter_provenance,
        tool_flute_length_provenance=vi.tool_flute_length_provenance,
        machine_travel_provenance=vi.machine_travel_provenance,
        fixture_count=len(fixture_geoms),  # only trustworthy fixtures
        part_bbox_provenance=vi.part_bbox_provenance,
        stock_provenance=vi.stock_provenance,
        warnings=warnings,
    )
