"""GD&T → Process Planning constraint extraction (P3-E).

Connects verified GD&T feature control frames to process planning constraints.
Constraints may flag: process choice requirements, capability reviews,
inspection steps, same-setup requirements, or REVIEW_REQUIRED status.

HARD RULES:
- GDNT_STATUS=REVIEW_REQUIRED when confidence is AMBIGUOUS or INFERRED.
- GD&T MUST NOT auto-approve a route.
- GD&T MUST NOT invent process capability, machine capability, tolerance, or datum.
- Provenance (FILE_EVIDENCE/DRAWING_TEXT/OCR/USER_CONFIRMED) is preserved throughout.

AUTO_APPROVE=NO
FABRICATED_PROCESS_CAPABILITY=NO
FABRICATED_MACHINE_CAPABILITY=NO
FABRICATED_TOLERANCE=NO
FABRICATED_DATUM=NO
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from backend.drawing_intelligence.requirements import (
    DrawingRequirementSet,
    GdtCharacteristic,
    GdtConfidence,
    GeometricRequirement,
)

__all__ = [
    "GdtProcessStatus",
    "GdtConstraintType",
    "GdtProcessConstraint",
    "extract_gdt_process_constraints",
]

# Characteristics with deterministic, non-fabricated constraints in this module
_SUPPORTED_CHARACTERISTICS: frozenset[GdtCharacteristic] = frozenset({
    GdtCharacteristic.POSITION,
    GdtCharacteristic.PERPENDICULARITY,
    GdtCharacteristic.PARALLELISM,
    GdtCharacteristic.FLATNESS,
    GdtCharacteristic.CIRCULAR_RUNOUT,
    GdtCharacteristic.TOTAL_RUNOUT,
    GdtCharacteristic.CYLINDRICITY,
    GdtCharacteristic.CIRCULARITY,
    GdtCharacteristic.STRAIGHTNESS,
    GdtCharacteristic.PROFILE_OF_A_SURFACE,
    GdtCharacteristic.PROFILE_OF_A_LINE,
    GdtCharacteristic.ANGULARITY,
})

# Confidence levels that require engineer review before process planning
_REVIEW_REQUIRED_CONFIDENCE: frozenset[GdtConfidence] = frozenset({
    GdtConfidence.AMBIGUOUS,
    GdtConfidence.INFERRED,
})


class GdtProcessStatus(StrEnum):
    """Status of a GD&T-derived process constraint."""

    VERIFIED = "VERIFIED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class GdtConstraintType(StrEnum):
    """Type of process planning constraint derived from a GD&T requirement."""

    PROCESS_CHOICE = "PROCESS_CHOICE"           # e.g., prefer boring over drilling
    CAPABILITY_REVIEW = "CAPABILITY_REVIEW"     # machine capability must be verified
    INSPECTION_REQUIRED = "INSPECTION_REQUIRED" # explicit inspection step needed
    SAME_SETUP_REQUIRED = "SAME_SETUP_REQUIRED" # surfaces must share one chucking/setup
    REVIEW_REQUIRED = "REVIEW_REQUIRED"         # ambiguous/OCR GD&T — engineer must review


@dataclass(frozen=True, slots=True)
class GdtProcessConstraint:
    """A single process planning constraint derived from a GD&T requirement.

    Provenance is preserved verbatim from the source GeometricRequirement.
    ``gdnt_status=REVIEW_REQUIRED`` means the GD&T evidence is ambiguous or
    OCR-only and must not be used to auto-approve any process decision.

    AUTO_APPROVE=NO
    FABRICATED_PROCESS_CAPABILITY=NO
    """

    constraint_id: str
    req_id: str
    characteristic: GdtCharacteristic
    constraint_type: GdtConstraintType
    constraint_note: str
    gdnt_status: GdtProcessStatus
    provenance: str              # FILE_EVIDENCE | DRAWING_TEXT | OCR | USER_CONFIRMED
    feature_ref: str | None

    def __post_init__(self) -> None:
        if not self.constraint_id.strip():
            raise ValueError("GdtProcessConstraint.constraint_id must be non-empty")
        if not self.req_id.strip():
            raise ValueError("GdtProcessConstraint.req_id must be non-empty")
        if not isinstance(self.characteristic, GdtCharacteristic):
            raise TypeError("GdtProcessConstraint.characteristic must be GdtCharacteristic")
        if not isinstance(self.constraint_type, GdtConstraintType):
            raise TypeError("GdtProcessConstraint.constraint_type must be GdtConstraintType")
        if not isinstance(self.gdnt_status, GdtProcessStatus):
            raise TypeError("GdtProcessConstraint.gdnt_status must be GdtProcessStatus")
        if self.provenance not in (
            "FILE_EVIDENCE", "DRAWING_TEXT", "OCR", "USER_CONFIRMED"
        ):
            raise ValueError(
                "GdtProcessConstraint.provenance must be FILE_EVIDENCE, DRAWING_TEXT, "
                "OCR, or USER_CONFIRMED"
            )


def extract_gdt_process_constraints(
    req_set: DrawingRequirementSet,
    confidence_map: dict[str, GdtConfidence] | None = None,
) -> tuple[GdtProcessConstraint, ...]:
    """Extract process planning constraints from GD&T requirements.

    ``confidence_map`` maps req_id → GdtConfidence. When absent, every
    requirement defaults to EXACT_STRUCTURED (highest confidence).

    Constraints are only emitted for characteristics in
    _SUPPORTED_CHARACTERISTICS. Unsupported or UNKNOWN characteristics
    produce a REVIEW_REQUIRED constraint instead of a process decision.

    OCR-derived or INFERRED confidence → REVIEW_REQUIRED + provenance=OCR.
    AMBIGUOUS confidence → REVIEW_REQUIRED.

    AUTO_APPROVE=NO
    """
    if confidence_map is None:
        confidence_map = {}

    constraints: list[GdtProcessConstraint] = []
    for geom in req_set.geometric:
        confidence = confidence_map.get(geom.req_id, GdtConfidence.EXACT_STRUCTURED)
        provenance = _provenance_for(confidence)
        status = (
            GdtProcessStatus.REVIEW_REQUIRED
            if confidence in _REVIEW_REQUIRED_CONFIDENCE
            else GdtProcessStatus.VERIFIED
        )
        constraints.extend(
            _constraints_for(geom, geom.fcf.characteristic, status, provenance)
        )

    return tuple(constraints)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _provenance_for(confidence: GdtConfidence) -> str:
    """Map GdtConfidence to a provenance label."""
    if confidence == GdtConfidence.USER_CONFIRMED:
        return "USER_CONFIRMED"
    if confidence in (GdtConfidence.EXACT_STRUCTURED, GdtConfidence.RULE_PARSED):
        return "FILE_EVIDENCE"
    if confidence in (GdtConfidence.GEOMETRY_MATCHED, GdtConfidence.PATTERN_MATCHED):
        return "DRAWING_TEXT"
    # INFERRED, AMBIGUOUS → OCR (most likely source of low-confidence GD&T)
    return "OCR"


def _constraints_for(
    geom: GeometricRequirement,
    char: GdtCharacteristic,
    status: GdtProcessStatus,
    provenance: str,
) -> list[GdtProcessConstraint]:
    req_id = geom.req_id
    feature_ref = geom.feature_ref

    # REVIEW_REQUIRED overrides all — emit single review constraint, no process decision
    if status == GdtProcessStatus.REVIEW_REQUIRED:
        return [GdtProcessConstraint(
            constraint_id=f"GPC-{req_id}-REVIEW",
            req_id=req_id,
            characteristic=char,
            constraint_type=GdtConstraintType.REVIEW_REQUIRED,
            constraint_note=(
                f"{char.value} at {req_id}: GD&T confidence too low for automatic "
                "process constraint — engineer review required before planning. "
                "GDNT_STATUS=REVIEW_REQUIRED. AUTO_APPROVE=NO."
            ),
            gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
            provenance=provenance,
            feature_ref=feature_ref,
        )]

    # Unsupported or UNKNOWN characteristic → review required, no process decision
    if char == GdtCharacteristic.UNKNOWN or char not in _SUPPORTED_CHARACTERISTICS:
        return [GdtProcessConstraint(
            constraint_id=f"GPC-{req_id}-UNSUPPORTED",
            req_id=req_id,
            characteristic=char,
            constraint_type=GdtConstraintType.REVIEW_REQUIRED,
            constraint_note=(
                f"{char.value} at {req_id}: characteristic not supported for "
                "automatic constraint derivation — engineer review required. "
                "GDNT_STATUS=REVIEW_REQUIRED."
            ),
            gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
            provenance=provenance,
            feature_ref=feature_ref,
        )]

    result: list[GdtProcessConstraint] = []

    if char == GdtCharacteristic.POSITION:
        if geom.fcf.datum_frame is None:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-POS-MISSING-DATUM",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.REVIEW_REQUIRED,
                constraint_note=(
                    f"POSITION at {req_id}: no datum reference found — "
                    "cannot derive datum-based setup constraint. "
                    "GDNT_STATUS=REVIEW_REQUIRED."
                ),
                gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))
        else:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-POS-DATUM-SETUP",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.CAPABILITY_REVIEW,
                constraint_note=(
                    f"POSITION at {req_id}: datum-based setup required "
                    f"({'/'.join(geom.fcf.datum_frame.labels)}); "
                    "positional machine capability must be verified before route selection. "
                    "AUTO_APPROVE=NO."
                ),
                gdnt_status=GdtProcessStatus.VERIFIED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))

    elif char == GdtCharacteristic.PERPENDICULARITY:
        if geom.fcf.datum_frame is None:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-PERP-MISSING-DATUM",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.REVIEW_REQUIRED,
                constraint_note=(
                    f"PERPENDICULARITY at {req_id}: no datum reference — "
                    "GDNT_STATUS=REVIEW_REQUIRED."
                ),
                gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))
        else:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-PERP-CAPABILITY",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.CAPABILITY_REVIEW,
                constraint_note=(
                    f"PERPENDICULARITY at {req_id}: setup perpendicularity capability review "
                    "required; surface grinding or precision boring may be needed in final setup. "
                    "AUTO_APPROVE=NO."
                ),
                gdnt_status=GdtProcessStatus.VERIFIED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))

    elif char == GdtCharacteristic.PARALLELISM:
        if geom.fcf.datum_frame is None:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-PARA-MISSING-DATUM",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.REVIEW_REQUIRED,
                constraint_note=(
                    f"PARALLELISM at {req_id}: no datum reference — "
                    "GDNT_STATUS=REVIEW_REQUIRED."
                ),
                gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))
        else:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-PARA-PROCESS",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.PROCESS_CHOICE,
                constraint_note=(
                    f"PARALLELISM at {req_id}: surface grinding or precision milling "
                    "recommended; machine parallelism capability must be reviewed. "
                    "AUTO_APPROVE=NO."
                ),
                gdnt_status=GdtProcessStatus.VERIFIED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))

    elif char == GdtCharacteristic.FLATNESS:
        result.append(GdtProcessConstraint(
            constraint_id=f"GPC-{req_id}-FLAT-INSPECTION",
            req_id=req_id,
            characteristic=char,
            constraint_type=GdtConstraintType.INSPECTION_REQUIRED,
            constraint_note=(
                f"FLATNESS at {req_id}: surface plate inspection or CMM verification "
                "required; surface grinding may be needed if tolerance is tight. "
                "AUTO_APPROVE=NO."
            ),
            gdnt_status=GdtProcessStatus.VERIFIED,
            provenance=provenance,
            feature_ref=feature_ref,
        ))

    elif char in (GdtCharacteristic.CIRCULAR_RUNOUT, GdtCharacteristic.TOTAL_RUNOUT):
        if geom.fcf.datum_frame is None:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-RUNOUT-MISSING-DATUM",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.REVIEW_REQUIRED,
                constraint_note=(
                    f"{char.value} at {req_id}: datum axis required — "
                    "GDNT_STATUS=REVIEW_REQUIRED."
                ),
                gdnt_status=GdtProcessStatus.REVIEW_REQUIRED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))
        else:
            result.append(GdtProcessConstraint(
                constraint_id=f"GPC-{req_id}-RUNOUT-SAME-SETUP",
                req_id=req_id,
                characteristic=char,
                constraint_type=GdtConstraintType.SAME_SETUP_REQUIRED,
                constraint_note=(
                    f"{char.value} at {req_id}: all runout-controlled surfaces "
                    "must be machined in one chucking; rotational setup verification required. "
                    "AUTO_APPROVE=NO."
                ),
                gdnt_status=GdtProcessStatus.VERIFIED,
                provenance=provenance,
                feature_ref=feature_ref,
            ))

    elif char in (GdtCharacteristic.CYLINDRICITY, GdtCharacteristic.CIRCULARITY):
        result.append(GdtProcessConstraint(
            constraint_id=f"GPC-{req_id}-CYL-PROCESS",
            req_id=req_id,
            characteristic=char,
            constraint_type=GdtConstraintType.PROCESS_CHOICE,
            constraint_note=(
                f"{char.value} at {req_id}: cylindrical grinding (OD or ID) "
                "recommended in route. AUTO_APPROVE=NO."
            ),
            gdnt_status=GdtProcessStatus.VERIFIED,
            provenance=provenance,
            feature_ref=feature_ref,
        ))

    elif char == GdtCharacteristic.PROFILE_OF_A_SURFACE:
        result.append(GdtProcessConstraint(
            constraint_id=f"GPC-{req_id}-PROFILE-FINISH",
            req_id=req_id,
            characteristic=char,
            constraint_type=GdtConstraintType.PROCESS_CHOICE,
            constraint_note=(
                f"PROFILE_OF_A_SURFACE at {req_id}: surface finishing "
                "(grinding or lapping) required in final route step. AUTO_APPROVE=NO."
            ),
            gdnt_status=GdtProcessStatus.VERIFIED,
            provenance=provenance,
            feature_ref=feature_ref,
        ))

    elif char in (
        GdtCharacteristic.STRAIGHTNESS,
        GdtCharacteristic.PROFILE_OF_A_LINE,
        GdtCharacteristic.ANGULARITY,
    ):
        result.append(GdtProcessConstraint(
            constraint_id=f"GPC-{req_id}-CAPABILITY",
            req_id=req_id,
            characteristic=char,
            constraint_type=GdtConstraintType.CAPABILITY_REVIEW,
            constraint_note=(
                f"{char.value} at {req_id}: machine capability review required; "
                "process route must be validated against this requirement. AUTO_APPROVE=NO."
            ),
            gdnt_status=GdtProcessStatus.VERIFIED,
            provenance=provenance,
            feature_ref=feature_ref,
        ))

    return result
