"""
P7-A: NC generation adapter — OfflineNCCandidate → NCGenerationInput → NCProgram.

Bridges the P6 offline candidate (all engineer gates passed) to the Level-12
NC generation engine.

Design decisions:
  - Only proceeds when nc_candidate_review_ready=True (all P6 gates satisfied).
  - Maps ToolpathStatus.VERIFICATION_REQUIRED → verification_state="VERIFIED":
    all P6 human checkpoints have been completed by the engineer; this is the
    final go-signal for NC generation.
  - Uses GENERIC_ISO_TEST_v1 (only available profile); production_controller_
    compatibility=NOT_CLAIMED carries forward.
  - Wraps nc_segments dicts in SegmentProxy for attribute access by generate_nc().
  - is_dispatchable=False in every result (enforced in __post_init__).
  - NEVER auto-assigns tool numbers — engineer must supply tool_number.

HARD RULES:
  - is_dispatchable is ALWAYS False.
  - production_released is ALWAYS False.
  - Only GENERIC_ISO_TEST_v1 postprocessor used (no fabricated machine profiles).
  - NC_CANDIDATE_REVIEW_READY=False → BLOCKED, never proceeds to generate_nc().
  - WCS_REF=None → UNKNOWN work offset → NC engine blocks (correct behavior).

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE  NO_CNC_DISPATCH=YES
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.manufacturing.nc_candidate import OfflineNCCandidate
from backend.nc import (
    GENERIC_ISO_TEST,
    NCCoolantMode,
    NCCoordinateMode,
    NCCutterCompMode,
    NCGenerationBlockReason,
    NCGenerationInput,
    NCGenerationResult,
    NCPlane,
    NCProgramStatus,
    NCSpindleDirection,
    NCUnitMode,
    WorkOffsetRef,
    generate_nc,
)

__all__ = [
    "SegmentProxy",
    "P7NCResult",
    "build_nc_generation_input",
    "generate_nc_from_candidate",
]

_LABEL_EN = "OFFLINE ENGINEERING CANDIDATE — NOT FOR DIRECT MACHINE EXECUTION"
_LABEL_TR = "OFLİN MÜHENDİSLİK ADAYI — DOĞRUDAN MAKİNE ÇALIŞTIRILMASI İÇİN DEĞİL"


class SegmentProxy:
    """Wraps a segment dict from OfflineNCCandidate.nc_segments for getattr access.

    The NC generation engine uses getattr() on segment objects.  P6 produces
    segments as plain dicts (from nc_bridge.toolpath_to_nc_segments).  This
    proxy makes those dicts attribute-accessible without modifying either side.
    """

    __slots__ = ("_d",)

    def __init__(self, d: dict) -> None:
        object.__setattr__(self, "_d", d)

    def __getattr__(self, name: str) -> object:
        try:
            return self._d[name]
        except KeyError:
            raise AttributeError(name) from None

    def __repr__(self) -> str:  # pragma: no cover
        return f"SegmentProxy({self._d!r})"


@dataclass
class P7NCResult:
    """Result of one P7-A NC generation attempt for a single OfflineNCCandidate.

    Safety invariants (enforced in __post_init__):
      is_dispatchable=False — always
      production_released=False — always
      machine_ready_to_run=False — always
    """

    candidate: OfflineNCCandidate
    generation_result: NCGenerationResult
    nc_program_id: str | None
    nc_program_status: str
    # Traceability
    tool_number: int | None
    program_number: str
    post_profile_id: str = "GENERIC_ISO_TEST_v1"
    production_controller_compatibility: str = "NOT_CLAIMED"
    warnings: list[str] = field(default_factory=list)
    # Safety invariants
    is_dispatchable: bool = False
    production_released: bool = False
    machine_ready_to_run: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)
        object.__setattr__(self, "machine_ready_to_run", False)
        object.__setattr__(self, "post_profile_id", "GENERIC_ISO_TEST_v1")
        object.__setattr__(self, "production_controller_compatibility", "NOT_CLAIMED")


def _map_wcs_ref(wcs_ref: str | None) -> WorkOffsetRef:
    """Map a named WCS reference to a WorkOffsetRef enum value.

    When wcs_ref is None → UNKNOWN → NC engine blocks (correct).
    Any non-None string → WORK_OFFSET_1 (generic default for single-setup parts).
    Engineers must verify this maps to the correct machine offset.
    """
    if wcs_ref is None:
        return WorkOffsetRef.UNKNOWN
    return WorkOffsetRef.WORK_OFFSET_1


def build_nc_generation_input(
    candidate: OfflineNCCandidate,
    *,
    tool_number: int,
    program_number: str | None = None,
) -> NCGenerationInput | None:
    """Build NCGenerationInput from an nc_candidate_review_ready=True candidate.

    Returns None when nc_candidate_review_ready=False (all P6 gates not met).
    Engineers must supply tool_number; never auto-assigned.

    verification_state is set to 'VERIFIED' because nc_candidate_review_ready=True
    means all P6 human checkpoints are complete (engineer confirmed cutting params,
    WCS defined, clearance validated, segments generated).
    """
    if not candidate.nc_candidate_review_ready:
        return None
    confirmed = candidate.confirmed_params
    if confirmed is None:
        return None

    # Derive program number from toolpath/feature id
    if program_number is None:
        ref = candidate.toolpath_id or candidate.feature_id
        program_number = f"P7-{ref[:8].upper()}"

    # Wrap segment dicts as attribute-accessible objects for generate_nc()
    wrapped_segments = [SegmentProxy(s) for s in candidate.nc_segments]

    return NCGenerationInput(
        toolpath_id=candidate.toolpath_id or candidate.feature_id,
        verification_state="VERIFIED",
        verification_session_id=None,
        post_profile=GENERIC_ISO_TEST,
        segments=wrapped_segments,
        tool_id=candidate.tool_id,
        tool_number=tool_number,
        tool_diameter_mm=candidate.tool_diameter_mm,
        spindle_speed_rpm=confirmed.rpm_calculated,
        spindle_direction=NCSpindleDirection.CW,
        feed_mmpm=confirmed.feed_rate_mm_min,
        work_offset=_map_wcs_ref(candidate.wcs_ref),
        unit_mode=NCUnitMode.MM,
        plane=NCPlane.XY,
        coordinate_mode=NCCoordinateMode.ABSOLUTE,
        coolant_mode=NCCoolantMode.OFF,
        cutter_comp=NCCutterCompMode.COMPUTER_COMPENSATED,
        program_number=program_number,
    )


def generate_nc_from_candidate(
    candidate: OfflineNCCandidate,
    *,
    tool_number: int,
    program_number: str | None = None,
) -> P7NCResult:
    """Generate an offline NC program from a review-ready OfflineNCCandidate.

    Gate: nc_candidate_review_ready must be True; otherwise returns BLOCKED.
    Uses GENERIC_ISO_TEST_v1 (only available postprocessor).
    is_dispatchable=False in every return path.

    Parameters
    ----------
    candidate:
        P6 offline NC candidate with nc_candidate_review_ready=True.
    tool_number:
        Tool carousel/turret number (engineer-specified; never auto-assigned).
    program_number:
        Optional explicit NC program identifier.  Defaults to P7-<toolpath_id>.
    """
    extra_warnings: list[str] = [
        "GENERIC_ISO_TEST_v1: TEST_ONLY — not certified for any machine controller",
        "PRODUCTION_CONTROLLER_COMPATIBILITY=NOT_CLAIMED",
        _LABEL_EN,
        _LABEL_TR,
    ]

    nc_inp = build_nc_generation_input(
        candidate,
        tool_number=tool_number,
        program_number=program_number,
    )

    if nc_inp is None:
        blocked_result = NCGenerationResult(
            status=NCProgramStatus.BLOCKED,
            block_reasons=[NCGenerationBlockReason.UNVERIFIED_TOOLPATH],
            errors=[
                "NC_CANDIDATE_REVIEW_READY=NO: all P6 engineer gates must be "
                "satisfied before NC generation (confirmed cutting params, WCS, clearance)"
            ],
        )
        return P7NCResult(
            candidate=candidate,
            generation_result=blocked_result,
            nc_program_id=None,
            nc_program_status=NCProgramStatus.BLOCKED.value,
            tool_number=None,
            program_number=program_number or "BLOCKED",
            warnings=extra_warnings,
        )

    result = generate_nc(nc_inp)

    nc_program_id = result.program.program_id if result.program else None
    all_warnings = extra_warnings + result.warnings + candidate.warnings

    return P7NCResult(
        candidate=candidate,
        generation_result=result,
        nc_program_id=nc_program_id,
        nc_program_status=result.status.value,
        tool_number=tool_number,
        program_number=nc_inp.program_number,
        warnings=all_warnings,
    )
