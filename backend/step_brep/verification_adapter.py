"""
Wire STEP B-Rep geometry into P8/P9 verification inputs (P10 Phase 3).

MUST 24: Wire STEP geometry → P8/P9 verification input (part_bbox, COARSE_GEOMETRY_CHECK).
MUST 27: If multiple solids, stock/fixture relationship = UNKNOWN_TRANSFORM.
MUST 28: COLLISION_VALIDATION=NOT_VERIFIABLE until relationship manually reviewed.
MUST 29: STEP_TARGET_FOR_GOUGE_AVAILABLE=False, VOXEL_TO_TARGET_COMPARISON_READY=False.
MUST 30: Fail-closed: if topology does not meet minimum criteria → GOUGE_VALIDATED=NOT_VERIFIABLE.

HARD RULES:
  - is_dispatchable=False always.
  - production_released=False always.
  - part_bbox only from STEP B-Rep (never fabricated from other sources).
  - GOUGE_VALIDATED=NOT_VERIFIABLE until voxel-to-target comparison is implemented.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.step_brep.gmsh_step_parser import StepImportRecord

__all__ = [
    "StepVerificationInput",
    "build_step_verification_input",
    "STEP_TARGET_FOR_GOUGE_AVAILABLE",
    "VOXEL_TO_TARGET_COMPARISON_READY",
]

STEP_TARGET_FOR_GOUGE_AVAILABLE: bool = False
VOXEL_TO_TARGET_COMPARISON_READY: bool = False


@dataclass(frozen=True)
class StepVerificationInput:
    """P8/P9 verification input derived from STEP B-Rep.

    HARD RULES:
      - is_dispatchable=False always.
      - production_released=False always.
      - part_bbox_provenance='STEP_FILE_EVIDENCE' only when status=PASS.
      - gouge_validated='NOT_VERIFIABLE' until voxel-to-target is implemented.
      - collision_validation='NOT_VERIFIABLE' when body_count>1 or stock unknown.
    """

    source_path: str
    parse_status: str
    body_count: int
    part_bbox_min: tuple[float, float, float] | None
    part_bbox_max: tuple[float, float, float] | None
    part_bbox_provenance: str  # STEP_FILE_EVIDENCE | UNKNOWN
    gouge_validated: str  # NOT_VERIFIABLE (this phase)
    collision_validation: str  # NOT_VERIFIABLE (this phase)
    stock_fixture_relationship: str  # UNKNOWN_TRANSFORM | SINGLE_BODY | NOT_APPLICABLE
    step_target_for_gouge_available: bool  # always False this phase
    voxel_to_target_comparison_ready: bool  # always False this phase
    warnings: list[str]

    @property
    def is_dispatchable(self) -> bool:
        return False

    @property
    def production_released(self) -> bool:
        return False


def build_step_verification_input(record: StepImportRecord) -> StepVerificationInput:
    """Build P8/P9 verification input from a parsed STEP file.

    part_bbox is set only when record.status=PASS and bbox is available.
    gouge_validated is always NOT_VERIFIABLE in Phase 3 (no voxel model).
    """
    warnings: list[str] = list(record.warnings)

    if record.status != "PASS":
        return StepVerificationInput(
            source_path=record.source_path,
            parse_status=record.status,
            body_count=0,
            part_bbox_min=None,
            part_bbox_max=None,
            part_bbox_provenance="UNKNOWN",
            gouge_validated="NOT_VERIFIABLE",
            collision_validation="NOT_VERIFIABLE",
            stock_fixture_relationship="NOT_APPLICABLE",
            step_target_for_gouge_available=False,
            voxel_to_target_comparison_ready=False,
            warnings=warnings + [f"STEP_PARSE_STATUS={record.status}: bbox not available"],
        )

    bbox_min = record.bbox_min
    bbox_max = record.bbox_max
    bbox_provenance = "STEP_FILE_EVIDENCE" if (bbox_min and bbox_max) else "UNKNOWN"

    # Stock/fixture relationship
    if record.body_count > 1:
        sfr = "UNKNOWN_TRANSFORM"
        warnings.append(
            f"MULTI_BODY={record.body_count}: stock/fixture relationship is UNKNOWN_TRANSFORM. "
            "Manual review required before collision validation."
        )
        collision = "NOT_VERIFIABLE"
    else:
        sfr = "SINGLE_BODY"
        collision = "NOT_VERIFIABLE"  # No fixture body to compare against in this phase

    warnings.append(
        "GOUGE_VALIDATED=NOT_VERIFIABLE: voxel-to-target comparison not implemented in Phase 3. "
        "STEP_TARGET_FOR_GOUGE_AVAILABLE=False, VOXEL_TO_TARGET_COMPARISON_READY=False."
    )

    return StepVerificationInput(
        source_path=record.source_path,
        parse_status=record.status,
        body_count=record.body_count,
        part_bbox_min=bbox_min,
        part_bbox_max=bbox_max,
        part_bbox_provenance=bbox_provenance,
        gouge_validated="NOT_VERIFIABLE",
        collision_validation=collision,
        stock_fixture_relationship=sfr,
        step_target_for_gouge_available=False,
        voxel_to_target_comparison_ready=False,
        warnings=warnings,
    )
