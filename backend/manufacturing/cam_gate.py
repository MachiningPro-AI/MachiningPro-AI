"""CAM Prerequisite Gate (P4-B).

Checks all engineering prerequisites before a file is considered CAM-ready
for offline preparation. Returns granular per-requirement status and an
overall CAM_READY flag.

CAM_READY=YES means: sufficient engineering data exists for OFFLINE CAM
preparation. It does NOT mean: auto-dispatch, machine-start, or auto-approval.

Design invariants:
  - Gate returns NO if any required field is unresolved (MUST 13).
  - Every blocker is named explicitly — no generic failure (MUST 12).
  - Gate never bypasses missing data with defaults.
  - Only features with USER_CONFIRMED confidence are accepted (MUST 5 / MUST 14).

OFFLINE_ONLY=YES
AUTO_APPROVE=NO
CNC_DISPATCH=NO
FABRICATED_PREREQUISITE=NO
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from backend.interoperability.cad_feature_recognition import (
    FeatureRecognitionConfidence,
    ManufacturingFeature,
    ManufacturingFeatureType,
)
from backend.manufacturing.confirmed_feature_route import MFT_TO_FT
from backend.manufacturing.setup_stock import SetupStockSession, validate_stock_dimensions

__all__ = [
    "CamPrerequisiteStatus",
    "CamPrerequisiteItem",
    "CamPrerequisiteState",
    "check_cam_prerequisites",
]

# Feature types that require a known depth to reach CAM-ready
_DEPTH_REQUIRED_TYPES: frozenset[ManufacturingFeatureType] = frozenset({
    ManufacturingFeatureType.HOLE,
    ManufacturingFeatureType.BLIND_HOLE,
    ManufacturingFeatureType.THROUGH_HOLE,
    ManufacturingFeatureType.COUNTERBORE,
    ManufacturingFeatureType.COUNTERSINK,
    ManufacturingFeatureType.STEPPED_HOLE,
    ManufacturingFeatureType.PRECISION_BORE_CANDIDATE,
    ManufacturingFeatureType.THREADED_HOLE_CANDIDATE,
    ManufacturingFeatureType.OPEN_POCKET,
    ManufacturingFeatureType.CLOSED_POCKET,
    ManufacturingFeatureType.OPEN_SLOT,
    ManufacturingFeatureType.CLOSED_SLOT,
})

# Feature types that require a known diameter to reach CAM-ready
_DIAMETER_REQUIRED_TYPES: frozenset[ManufacturingFeatureType] = frozenset({
    ManufacturingFeatureType.HOLE,
    ManufacturingFeatureType.BLIND_HOLE,
    ManufacturingFeatureType.THROUGH_HOLE,
    ManufacturingFeatureType.COUNTERBORE,
    ManufacturingFeatureType.COUNTERSINK,
    ManufacturingFeatureType.STEPPED_HOLE,
    ManufacturingFeatureType.PRECISION_BORE_CANDIDATE,
    ManufacturingFeatureType.OUTER_DIAMETER,
    ManufacturingFeatureType.INNER_DIAMETER,
    ManufacturingFeatureType.TURNING_DIAMETER,
})


class CamPrerequisiteStatus(StrEnum):
    MET = "MET"
    MISSING = "MISSING"
    BLOCKED = "BLOCKED"


@dataclass(frozen=True, slots=True)
class CamPrerequisiteItem:
    """One prerequisite check result."""

    name: str
    status: CamPrerequisiteStatus
    detail: str


@dataclass(frozen=True, slots=True)
class CamPrerequisiteState:
    """Granular CAM prerequisite check for one confirmed feature + setup/stock.

    ``cam_ready=True`` means: OFFLINE CAM preparation may proceed.
    It does NOT mean: auto-dispatch, machine-start, or auto-approval.

    OFFLINE_ONLY=YES
    AUTO_APPROVE=NO
    CNC_DISPATCH=NO
    """

    feature_id: str
    cam_ready: bool
    prerequisites: tuple[CamPrerequisiteItem, ...]
    first_blocker: str | None
    all_blockers: tuple[str, ...]
    disclaimer: str = (
        "CAM_READY=YES authorises OFFLINE preparation only. "
        "AUTO_APPROVED=NO. CNC_DISPATCH=NO. "
        "Engineer sign-off required before production use."
    )

    def as_dict(self) -> dict:
        return {
            "feature_id": self.feature_id,
            "cam_ready": self.cam_ready,
            "prerequisites": [
                {
                    "name": p.name,
                    "status": str(p.status),
                    "detail": p.detail,
                }
                for p in self.prerequisites
            ],
            "first_blocker": self.first_blocker,
            "all_blockers": list(self.all_blockers),
            "offline_only": True,
            "disclaimer": self.disclaimer,
        }


def check_cam_prerequisites(
    mfeat: ManufacturingFeature,
    setup_session: SetupStockSession | None,
) -> CamPrerequisiteState:
    """Check all CAM prerequisites for a confirmed feature + setup/stock session.

    Returns a granular CamPrerequisiteState with per-requirement status.
    cam_ready=True only when EVERY prerequisite is MET.

    Parameters
    ----------
    mfeat:
        The confirmed ManufacturingFeature (should be USER_CONFIRMED).
    setup_session:
        The SetupStockSession containing stock and setup definitions (may be None
        if no session has been created yet).

    Returns
    -------
    CamPrerequisiteState with cam_ready=True when all prerequisites are met.

    OFFLINE_ONLY=YES
    AUTO_APPROVE=NO
    """
    items: list[CamPrerequisiteItem] = []

    # 1. Feature must be confirmed
    if mfeat.confidence == FeatureRecognitionConfidence.USER_CONFIRMED:
        items.append(CamPrerequisiteItem(
            name="feature_confirmed",
            status=CamPrerequisiteStatus.MET,
            detail=f"Feature {mfeat.feature_id} is USER_CONFIRMED",
        ))
    else:
        items.append(CamPrerequisiteItem(
            name="feature_confirmed",
            status=CamPrerequisiteStatus.MISSING,
            detail=(
                f"Feature {mfeat.feature_id} confidence is {mfeat.confidence!s} — "
                "must be USER_CONFIRMED before CAM preparation"
            ),
        ))

    # 2. Feature type must be mappable to a domain route type
    domain_ft = MFT_TO_FT.get(mfeat.feature_type)
    if domain_ft is not None:
        items.append(CamPrerequisiteItem(
            name="feature_type_mappable",
            status=CamPrerequisiteStatus.MET,
            detail=f"{mfeat.feature_type!s} → {domain_ft!s}",
        ))
    else:
        items.append(CamPrerequisiteItem(
            name="feature_type_mappable",
            status=CamPrerequisiteStatus.BLOCKED,
            detail=(
                f"Feature type {mfeat.feature_type!s} has no route-generator mapping — "
                "FREEFORM and UNKNOWN features cannot reach CAM-ready"
            ),
        ))

    # 3. Depth known (required for depth-sensitive feature types)
    if mfeat.feature_type in _DEPTH_REQUIRED_TYPES:
        if mfeat.depth_mm is not None:
            items.append(CamPrerequisiteItem(
                name="depth_known",
                status=CamPrerequisiteStatus.MET,
                detail=f"depth_mm={mfeat.depth_mm} mm (USER_CONFIRMED)",
            ))
        else:
            items.append(CamPrerequisiteItem(
                name="depth_known",
                status=CamPrerequisiteStatus.MISSING,
                detail=(
                    f"depth_mm is None for {mfeat.feature_type!s} — "
                    "engineer must supply depth via confirm_with_dimensions"
                ),
            ))
    else:
        items.append(CamPrerequisiteItem(
            name="depth_known",
            status=CamPrerequisiteStatus.MET,
            detail=f"{mfeat.feature_type!s} does not require depth",
        ))

    # 4. Diameter known (required for diameter-sensitive feature types)
    if mfeat.feature_type in _DIAMETER_REQUIRED_TYPES:
        has_diameter = mfeat.diameter_mm is not None or mfeat.radius_mm is not None
        if has_diameter:
            dval = mfeat.diameter_mm if mfeat.diameter_mm is not None else mfeat.radius_mm * 2  # type: ignore[operator]
            items.append(CamPrerequisiteItem(
                name="diameter_known",
                status=CamPrerequisiteStatus.MET,
                detail=f"diameter={dval} mm",
            ))
        else:
            items.append(CamPrerequisiteItem(
                name="diameter_known",
                status=CamPrerequisiteStatus.MISSING,
                detail=(
                    f"diameter_mm is None for {mfeat.feature_type!s} — "
                    "engineer must supply diameter or radius"
                ),
            ))
    else:
        items.append(CamPrerequisiteItem(
            name="diameter_known",
            status=CamPrerequisiteStatus.MET,
            detail=f"{mfeat.feature_type!s} does not require diameter",
        ))

    # 5. Material defined (from setup_session.stock)
    if setup_session is None or setup_session.stock is None:
        items.append(CamPrerequisiteItem(
            name="material_defined",
            status=CamPrerequisiteStatus.MISSING,
            detail="No setup/stock session — engineer must define stock with material grade",
        ))
    elif not setup_session.stock.material_grade.strip():
        items.append(CamPrerequisiteItem(
            name="material_defined",
            status=CamPrerequisiteStatus.MISSING,
            detail="material_grade is empty — engineer must confirm material",
        ))
    else:
        items.append(CamPrerequisiteItem(
            name="material_defined",
            status=CamPrerequisiteStatus.MET,
            detail=f"material_grade={setup_session.stock.material_grade!r} (USER_CONFIRMED)",
        ))

    # 6. Stock dimensions complete
    if setup_session is None or setup_session.stock is None:
        items.append(CamPrerequisiteItem(
            name="stock_complete",
            status=CamPrerequisiteStatus.MISSING,
            detail="No stock definition — engineer must define stock shape and dimensions",
        ))
    else:
        stock_errors = validate_stock_dimensions(setup_session.stock)
        if stock_errors:
            items.append(CamPrerequisiteItem(
                name="stock_complete",
                status=CamPrerequisiteStatus.MISSING,
                detail=f"Stock incomplete — missing: {', '.join(stock_errors)}",
            ))
        else:
            items.append(CamPrerequisiteItem(
                name="stock_complete",
                status=CamPrerequisiteStatus.MET,
                detail=f"Stock shape={setup_session.stock.shape!s} complete",
            ))

    # 7. Setup defined (datum + n_setups)
    if setup_session is None or setup_session.setup is None:
        items.append(CamPrerequisiteItem(
            name="setup_defined",
            status=CamPrerequisiteStatus.MISSING,
            detail="No setup definition — engineer must define datum and orientation",
        ))
    else:
        setup_errors = setup_session.setup.validate()
        has_datum = setup_session.setup.datum_a is not None
        if setup_errors or not has_datum:
            problems = list(setup_errors)
            if not has_datum:
                problems.append("datum_a:required")
            items.append(CamPrerequisiteItem(
                name="setup_defined",
                status=CamPrerequisiteStatus.MISSING,
                detail=f"Setup incomplete — missing: {', '.join(problems)}",
            ))
        else:
            items.append(CamPrerequisiteItem(
                name="setup_defined",
                status=CamPrerequisiteStatus.MET,
                detail=(
                    f"Setup defined with {setup_session.setup.n_setups} setup(s), datum_a confirmed"
                ),
            ))

    # Collect blockers
    blockers = [
        item.name for item in items
        if item.status in (CamPrerequisiteStatus.MISSING, CamPrerequisiteStatus.BLOCKED)
    ]
    cam_ready = len(blockers) == 0

    return CamPrerequisiteState(
        feature_id=mfeat.feature_id,
        cam_ready=cam_ready,
        prerequisites=tuple(items),
        first_blocker=blockers[0] if blockers else None,
        all_blockers=tuple(blockers),
    )


def check_cam_prerequisites_for_features(
    features: Sequence[ManufacturingFeature],
    setup_session: SetupStockSession | None,
) -> dict[str, CamPrerequisiteState]:
    """Check CAM prerequisites for multiple features, returning one state per feature."""
    return {
        f.feature_id: check_cam_prerequisites(f, setup_session)
        for f in features
    }
