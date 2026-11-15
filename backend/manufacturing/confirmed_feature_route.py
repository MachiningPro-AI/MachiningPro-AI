"""Confirmed Feature → Route Generator Bridge (P4-A).

Takes a USER_CONFIRMED ManufacturingFeature and runs route generation against
the existing RouteGenerator. This is the bridge between the CAD feature
recognition pipeline (P3-A) and the drawing-intelligence route generator.

Design invariants:
  - Only USER_CONFIRMED (or higher) features enter route generation.
    CANDIDATE, AMBIGUOUS, REJECTED are blocked — they never enter route gen.
  - depth_mm and diameter_mm come from the confirmed feature; never re-inferred.
  - Route result is DRAFT/PROPOSED — AUTO_APPROVED=NO.
  - ManufacturingFeatureType → FeatureType mapping is deterministic; no
    unsupported types silently produce routes.

FABRICATED_ROUTE=NO
AUTO_APPROVED=NO
ROUTE_STATUS=PROPOSED
OFFLINE_ONLY=YES
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum

from backend.domain.base import Provenance
from backend.domain.enums import FeatureType, ProvenanceType
from backend.domain.feature import Feature
from backend.domain.units import Quantity, Unit
from backend.drawing_intelligence.feature_recognition import RecognizedFeature
from backend.drawing_intelligence.requirements import (
    DrawingRequirementSet,
    RequirementExtractionStatus,
)
from backend.drawing_intelligence.route_generator import (
    RouteGenerationResult,
    RouteGenerator,
)
from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeature,
    ManufacturingFeatureType,
)

__all__ = [
    "RouteBlockedReason",
    "ConfirmedFeatureRouteResult",
    "bridge_confirmed_feature_to_route",
    "MFT_TO_FT",
]

# ---------------------------------------------------------------------------
# Confidence guard: only these may enter route generation (MUST 5)
# ---------------------------------------------------------------------------

_ROUTE_ELIGIBLE_CONFIDENCE: frozenset[FeatureRecognitionConfidence] = frozenset({
    FeatureRecognitionConfidence.USER_CONFIRMED,
    FeatureRecognitionConfidence.EXACT_BREP,
    FeatureRecognitionConfidence.TOPOLOGY_RULE,
})

# ---------------------------------------------------------------------------
# ManufacturingFeatureType → FeatureType mapping (deterministic, no fabrication)
# ---------------------------------------------------------------------------

MFT_TO_FT: dict[ManufacturingFeatureType, FeatureType] = {
    # Hole family
    ManufacturingFeatureType.HOLE: FeatureType.HOLE,
    ManufacturingFeatureType.BLIND_HOLE: FeatureType.HOLE,
    ManufacturingFeatureType.THROUGH_HOLE: FeatureType.HOLE,
    ManufacturingFeatureType.COUNTERBORE: FeatureType.HOLE,
    ManufacturingFeatureType.COUNTERSINK: FeatureType.HOLE,
    ManufacturingFeatureType.STEPPED_HOLE: FeatureType.HOLE,
    ManufacturingFeatureType.PRECISION_BORE_CANDIDATE: FeatureType.HOLE,
    # Thread
    ManufacturingFeatureType.THREADED_HOLE_CANDIDATE: FeatureType.THREAD,
    # Pocket family
    ManufacturingFeatureType.OPEN_POCKET: FeatureType.POCKET,
    ManufacturingFeatureType.CLOSED_POCKET: FeatureType.POCKET,
    ManufacturingFeatureType.ISLAND: FeatureType.POCKET,
    ManufacturingFeatureType.BOSS: FeatureType.POCKET,
    ManufacturingFeatureType.STEP: FeatureType.POCKET,
    ManufacturingFeatureType.SHOULDER: FeatureType.POCKET,
    ManufacturingFeatureType.PAD: FeatureType.POCKET,
    # Slot family
    ManufacturingFeatureType.OPEN_SLOT: FeatureType.SLOT,
    ManufacturingFeatureType.CLOSED_SLOT: FeatureType.SLOT,
    # Turned/cylindrical family
    ManufacturingFeatureType.OUTER_DIAMETER: FeatureType.CYLINDRICAL_SURFACE,
    ManufacturingFeatureType.INNER_DIAMETER: FeatureType.CYLINDRICAL_SURFACE,
    ManufacturingFeatureType.TURNING_DIAMETER: FeatureType.CYLINDRICAL_SURFACE,
    ManufacturingFeatureType.TAPER: FeatureType.CYLINDRICAL_SURFACE,
    # Planar
    ManufacturingFeatureType.PLANAR_FACE: FeatureType.PLANAR_FACE,
    ManufacturingFeatureType.FACE_TURN: FeatureType.PLANAR_FACE,
    # Chamfer / fillet / groove
    ManufacturingFeatureType.CHAMFER: FeatureType.CHAMFER,
    ManufacturingFeatureType.EDGE_BREAK: FeatureType.CHAMFER,
    ManufacturingFeatureType.FILLET: FeatureType.FILLET,
    ManufacturingFeatureType.GROOVE: FeatureType.GROOVE,
    # FREEFORM and UNKNOWN intentionally absent → unsupported → blocked
}

# Provenance for all features entering the route generator via this bridge
_USER_CONFIRMED_PROVENANCE = Provenance(
    source_type=ProvenanceType.USER_CONFIRMED_FIELD,
    notes="Engineer-confirmed via confirm_with_dimensions (P4-A bridge)",
)

_ROUTE_DISCLAIMER = (
    "DRAFT/PROPOSED route generated from engineer-confirmed feature data. "
    "AUTO_APPROVED=NO. ROUTE_STATUS=PROPOSED. "
    "Engineer review required before production use. OFFLINE_ONLY=YES."
)


class RouteBlockedReason(StrEnum):
    NOT_CONFIRMED = "NOT_CONFIRMED"
    UNSUPPORTED_FEATURE_TYPE = "UNSUPPORTED_FEATURE_TYPE"


@dataclass(frozen=True, slots=True)
class ConfirmedFeatureRouteResult:
    """Route generation result for a single confirmed feature.

    ``route_result`` is None when blocked.
    When present, its routes are always DRAFT — never APPROVED.

    AUTO_APPROVED=NO
    ROUTE_STATUS=PROPOSED
    FABRICATED_ROUTE=NO
    """

    feature_id: str
    manufacturing_feature_type: ManufacturingFeatureType
    domain_feature_type: FeatureType | None
    route_result: RouteGenerationResult | None
    blocked: bool
    blocked_reason: RouteBlockedReason | None
    provenance: str = "USER_CONFIRMED"
    disclaimer: str = _ROUTE_DISCLAIMER

    def as_dict(self) -> dict:
        base: dict = {
            "feature_id": self.feature_id,
            "manufacturing_feature_type": str(self.manufacturing_feature_type),
            "domain_feature_type": (
                str(self.domain_feature_type) if self.domain_feature_type else None
            ),
            "blocked": self.blocked,
            "blocked_reason": str(self.blocked_reason) if self.blocked_reason else None,
            "provenance": self.provenance,
            "disclaimer": self.disclaimer,
            "route_generation": None,
        }
        if self.route_result is not None:
            rr = self.route_result
            base["route_generation"] = {
                "feature_id": rr.feature_id,
                "feature_type": str(rr.feature_type),
                "route_count": len(rr.routes),
                "has_routes": rr.has_routes,
                "routes": [
                    {
                        "route_id": r.route_id,
                        "operations": [str(op) for op in r.operations],
                        "requires_grinding": r.requires_grinding,
                        "achievable_ra_um": float(r.achievable_ra_um),
                        "route_description": r.route_description,
                        "status": "PROPOSED",
                    }
                    for r in rr.routes
                ],
                "rejections": [
                    {
                        "route_id": rej.route_id,
                        "reason": str(rej.reason),
                        "detail": rej.detail,
                    }
                    for rej in rr.rejections
                ],
                "warnings": list(rr.warnings),
                "status": "PROPOSED",
            }
        return base


def bridge_confirmed_feature_to_route(
    mfeat: ManufacturingFeature,
) -> ConfirmedFeatureRouteResult:
    """Bridge: ManufacturingFeature(USER_CONFIRMED) → RouteGenerationResult.

    Only features with USER_CONFIRMED, EXACT_BREP, or TOPOLOGY_RULE confidence
    may enter route generation. CANDIDATE, AMBIGUOUS, and REJECTED are blocked.

    Dimension values (depth_mm, diameter_mm, etc.) are taken directly from the
    confirmed feature — never re-inferred from geometry.

    Route result carries DRAFT/PROPOSED status — AUTO_APPROVED=NO.

    MUST 5 enforcement: non-eligible confidence → blocked=True.
    MUST 12: USER_CONFIRMED provenance is preserved throughout.
    MUST 15: route output is always PROPOSED, never APPROVED.
    """
    # MUST 5: guard — only confirmed/trusted features enter route generation
    if mfeat.confidence not in _ROUTE_ELIGIBLE_CONFIDENCE:
        return ConfirmedFeatureRouteResult(
            feature_id=mfeat.feature_id,
            manufacturing_feature_type=mfeat.feature_type,
            domain_feature_type=None,
            route_result=None,
            blocked=True,
            blocked_reason=RouteBlockedReason.NOT_CONFIRMED,
        )

    # Map ManufacturingFeatureType → FeatureType
    domain_ft = MFT_TO_FT.get(mfeat.feature_type)
    if domain_ft is None:
        return ConfirmedFeatureRouteResult(
            feature_id=mfeat.feature_id,
            manufacturing_feature_type=mfeat.feature_type,
            domain_feature_type=None,
            route_result=None,
            blocked=True,
            blocked_reason=RouteBlockedReason.UNSUPPORTED_FEATURE_TYPE,
        )

    # Build Feature dimensions from engineer-confirmed values only (MUST 4)
    # depth_mm and diameter_mm MUST come from the confirmed feature — never inferred
    dims: dict[str, Quantity] = {}
    if mfeat.diameter_mm is not None:
        dims["diameter"] = Quantity(mfeat.diameter_mm, Unit.MM)
    elif mfeat.radius_mm is not None:
        # radius → diameter only when diameter is absent (surface geometry)
        dims["diameter"] = Quantity(mfeat.radius_mm * Decimal("2"), Unit.MM)
    if mfeat.depth_mm is not None:
        dims["depth"] = Quantity(mfeat.depth_mm, Unit.MM)
    if mfeat.width_mm is not None:
        dims["width"] = Quantity(mfeat.width_mm, Unit.MM)
    if mfeat.length_mm is not None:
        dims["length"] = Quantity(mfeat.length_mm, Unit.MM)

    # Build the domain Feature with USER_CONFIRMED provenance (MUST 12)
    part_id = mfeat.source_body_id if mfeat.source_body_id else "CONFIRMED_FEATURE"
    feature = Feature(
        feature_id=mfeat.feature_id,
        part_id=part_id,
        feature_type=domain_ft,
        provenance=_USER_CONFIRMED_PROVENANCE,
        dimensions=dims,
    )

    # Wrap in RecognizedFeature with recognition_rule=USER_CONFIRMED
    rf = RecognizedFeature(
        feature=feature,
        source_req_ids=(),
        recognition_rule="USER_CONFIRMED",
    )

    # Minimal DrawingRequirementSet — no drawing requirements beyond confirmed dims
    # extraction_status=PARTIAL because this is engineer-only data, not full drawing
    req_set = DrawingRequirementSet(
        source_id=mfeat.feature_id,
        drawing_number=None,
        revision=None,
        extraction_status=RequirementExtractionStatus.PARTIAL,
        dimensional=(),
        geometric=(),
        surface_finish=(),
        threads=(),
        material=None,
        heat_treatment=(),
    )

    route_result = RouteGenerator().generate(rf, req_set)

    return ConfirmedFeatureRouteResult(
        feature_id=mfeat.feature_id,
        manufacturing_feature_type=mfeat.feature_type,
        domain_feature_type=domain_ft,
        route_result=route_result,
        blocked=False,
        blocked_reason=None,
    )
