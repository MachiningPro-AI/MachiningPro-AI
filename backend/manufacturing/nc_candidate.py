"""
Offline NC candidate builder for P6-D.

Implements the downstream CAM readiness model:
  CAM_READY                 ← existing cam_gate.py (unchanged)
  PARAMETERIZED_CAM_READY   ← machine + tool + ENGINEER_CONFIRMED params + setup/WCS
  TOOLPATH_READY            ← parameterized + clearance known + WCS defined
  NC_CANDIDATE_READY        ← toolpath segments generated (not BLOCKED)
  NC_CANDIDATE_REVIEW_READY ← all engineer confirmation gates complete

None of these imply PRODUCTION_RELEASED, DISPATCHABLE, or MACHINE_READY_TO_RUN.

HARD RULES:
  - is_dispatchable is ALWAYS False.
  - production_released is ALWAYS False.
  - engineer_review_required is ALWAYS True.
  - COMPATIBLE tool match risk is ALWAYS preserved in warnings.
  - DIMENSIONAL_CONFORMANCE=UNKNOWN when tolerance is unavailable.
  - NC candidates are GENERIC_NC_CANDIDATE unless postprocessor is validated.
  - No auto-approval, no NC dispatch, no machine write.

OFFLINE_ONLY=YES  IS_DISPATCHABLE=ALWAYS_FALSE  PRODUCTION_RELEASED=ALWAYS_FALSE
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from backend.manufacturing.clearance_policy import ClearanceEvaluationResult
from backend.manufacturing.nc_bridge import toolpath_to_nc_segments
from backend.manufacturing.parameter_confirmation import (
    EngineerConfirmedCuttingParameters,
    ParameterConfirmationStatus,
)
from backend.toolpath.enums import ToolpathStatus
from backend.toolpath.generators import DrillInput, generate_drill_toolpath
from backend.toolpath.models import Toolpath

__all__ = [
    "NcCandidateReadiness",
    "P6ReadinessReport",
    "OfflineNCCandidate",
    "build_offline_nc_candidate",
    "evaluate_p6_readiness",
]

# Mandatory label included in every offline NC candidate.
_LABEL_EN = "OFFLINE ENGINEERING CANDIDATE — NOT FOR DIRECT MACHINE EXECUTION"
_LABEL_TR = "OFLİN MÜHENDİSLİK ADAYI — DOĞRUDAN MAKİNE ÇALIŞTIRILMASI İÇİN DEĞİL"


class NcCandidateReadiness(StrEnum):
    READY = "READY"
    BLOCKED = "BLOCKED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    INCOMPLETE = "INCOMPLETE"


@dataclass(frozen=True)
class P6ReadinessReport:
    """Five-level CAM→NC readiness model for a single confirmed feature.

    Extends cam_gate.py's CAM_READY without overloading it.
    None of these levels imply PRODUCTION_RELEASED or DISPATCHABLE.

    cam_ready:
        Engineering information sufficient for OFFLINE CAM authoring.
        Defined by cam_gate.py (7 checks: feature/type/depth/diameter/material/stock/setup).
        DOES NOT imply tool or cutting data availability.

    parameterized_cam_ready:
        CAM_READY + machine candidate confirmed + tool candidate confirmed +
        cutting parameters ENGINEER_CONFIRMED + setup/WCS available.

    toolpath_ready:
        PARAMETERIZED_CAM_READY + clearance height validated + WCS ref named +
        toolpath geometry has been generated without BLOCKED status.

    nc_candidate_ready:
        TOOLPATH_READY + NC segment translation completed.

    nc_candidate_review_ready:
        NC_CANDIDATE_READY + all engineer gates complete
        (cutting parameters ENGINEER_CONFIRMED, not just MANUFACTURER_STARTING_VALUE).
    """

    feature_id: str

    cam_ready: bool
    parameterized_cam_ready: bool
    toolpath_ready: bool
    nc_candidate_ready: bool
    nc_candidate_review_ready: bool

    cam_ready_blocker: str | None
    parameterized_cam_ready_blocker: str | None
    toolpath_ready_blocker: str | None
    nc_candidate_ready_blocker: str | None
    nc_candidate_review_ready_blocker: str | None

    # Traceability
    tool_match_status: str | None
    cutting_params_status: str | None
    clearance_status: str | None

    # Invariants — always false
    production_released: bool = False
    is_dispatchable: bool = False
    machine_ready_to_run: bool = False


@dataclass
class OfflineNCCandidate:
    """Offline engineering NC candidate record for a single confirmed drilling feature.

    This record describes all inputs needed for eventual G-code generation once
    the toolpath is verified.  It does NOT contain production G-code.
    Use GENERIC_NC_CANDIDATE as the postprocessor status.

    Required metadata fields (MUST 23):
      sample_id, feature_id, route_id, machine_id, tool_id, tool_match_status,
      material, depth, cutting_params, wcs_ref, clearance, toolpath_summary,
      warnings, provenance, review_status.

    Safety invariants (MUST 24) — always enforced:
      offline_only=True, is_dispatchable=False,
      production_released=False, engineer_review_required=True.

    Labels (MUST 25) — always present in EN and TR.
    """

    # Identity
    sample_id: str
    feature_id: str
    route_id: str | None
    machine_id: str | None

    # Tool
    tool_id: str
    tool_match_status: str          # EXACT / COMPATIBLE / NO_MATCH
    tool_diameter_mm: float
    feature_diameter_mm: float
    tool_risk_warning: str | None   # None for EXACT, text for COMPATIBLE

    # Material + geometry
    material: str
    depth_mm: float
    operation: str

    # Cutting parameters (None = not yet confirmed)
    confirmed_params: EngineerConfirmedCuttingParameters | None

    # Setup
    wcs_ref: str | None
    clearance_z_mm: float | None
    clearance_source: str | None

    # Toolpath
    toolpath_id: str | None
    toolpath_status: str
    toolpath_summary: str

    # Tolerance — after required fields (MUST 22: never claim compliance)
    dimensional_conformance: str = "UNKNOWN"
    nc_segments: list[dict] = field(default_factory=list)

    # Provenance
    provenance: dict = field(default_factory=dict)

    # Warnings — preserved from every upstream stage
    warnings: list[str] = field(default_factory=list)

    # Review
    review_status: str = "PENDING_REVIEW"
    nc_candidate_review_ready: bool = False

    # Mandatory safety fields (MUST 24) — hardcoded, never overridable
    offline_only: bool = True
    is_dispatchable: bool = False
    production_released: bool = False
    engineer_review_required: bool = True

    # Postprocessor status (MUST 26)
    postprocessor_status: str = "GENERIC_NC_CANDIDATE"
    production_controller_compatibility: str = "NOT_CLAIMED"

    # Mandatory labels (MUST 25)
    label_en: str = _LABEL_EN
    label_tr: str = _LABEL_TR

    def __post_init__(self) -> None:
        # Safety invariants are enforced unconditionally.
        object.__setattr__(self, "offline_only", True)
        object.__setattr__(self, "is_dispatchable", False)
        object.__setattr__(self, "production_released", False)
        object.__setattr__(self, "engineer_review_required", True)
        object.__setattr__(self, "label_en", _LABEL_EN)
        object.__setattr__(self, "label_tr", _LABEL_TR)


def build_offline_nc_candidate(
    *,
    sample_id: str,
    feature_id: str,
    hole_x: float,
    hole_y: float,
    hole_top_z: float,
    hole_depth_mm: float,
    feature_diameter_mm: float,
    material: str,
    operation: str,
    tool_id: str,
    tool_match_status: str,
    tool_diameter_mm: float,
    clearance_eval: ClearanceEvaluationResult,
    wcs_ref: str | None,
    confirmed_params: EngineerConfirmedCuttingParameters | None,
    route_id: str | None = None,
    machine_id: str | None = None,
) -> OfflineNCCandidate:
    """Build an offline NC candidate from fully evaluated P6 inputs.

    The function:
    1. Calls generate_drill_toolpath() to produce motion segments.
    2. Translates segments to NC segment format via nc_bridge.
    3. Packages all metadata into an OfflineNCCandidate.
    4. Sets NC_CANDIDATE_REVIEW_READY only when all engineer gates pass.

    Returns a BLOCKED or INCOMPLETE candidate (not None) on any missing input.
    """
    warnings: list[str] = []

    # --- COMPATIBLE match risk (MUST 21, MUST 3, Condition 3) ---
    tool_risk: str | None = None
    if tool_match_status == "COMPATIBLE":
        tool_risk = (
            f"TOOL_DIAMETER_MATCH=COMPATIBLE_REVIEW: "
            f"selected drill={tool_diameter_mm:.4f} mm for feature={feature_diameter_mm:.4f} mm "
            f"(delta={tool_diameter_mm - feature_diameter_mm:+.4f} mm). "
            f"Resulting hole will be ~{tool_diameter_mm:.4f} mm, NOT {feature_diameter_mm:.4f} mm. "
            f"Engineer must verify fit tolerance before production."
        )
        warnings.append(tool_risk)
        warnings.append(
            f"UYARI (TR): Seçilen matkap çapı={tool_diameter_mm} mm, "
            f"özellik çapı={feature_diameter_mm} mm — "
            "boyutsal uyum mühendis tarafından doğrulanmalıdır."
        )

    # --- Clearance / WCS checks ---
    clearance_z_mm: float | None = None
    clearance_source_str: str | None = None
    toolpath_status_str = "NOT_GENERATED"
    toolpath_id: str | None = None
    toolpath_summary = "TOOLPATH_NOT_GENERATED"
    nc_segments: list[dict] = []

    if not clearance_eval.toolpath_ready:
        warnings.append(
            f"TOOLPATH_BLOCKED: {clearance_eval.blocker or 'clearance/WCS not ready'}"
        )
    else:
        clearance_z_mm = clearance_eval.clearance_plane.value_mm
        clearance_source_str = clearance_eval.clearance_plane.source.value
        warnings.extend(clearance_eval.validation_notes)

        # --- Generate drill toolpath ---
        drill_inp = DrillInput(
            operation_ref=f"drill-{feature_id}",
            hole_x=hole_x,
            hole_y=hole_y,
            hole_top_z=hole_top_z,
            hole_depth_mm=hole_depth_mm,
            clearance_z=clearance_z_mm,
            clearance_source=clearance_eval.clearance_plane.source,
            setup_ref=None,
            wcs_ref=wcs_ref,
            tool_ref=tool_id,
            feature_refs=[feature_id],
        )
        tp: Toolpath = generate_drill_toolpath(drill_inp)
        toolpath_id = tp.toolpath_id
        toolpath_status_str = tp.status.value
        warnings.extend(tp.warnings)

        _tp_ok = tp.status in (ToolpathStatus.GENERATED, ToolpathStatus.VERIFICATION_REQUIRED)
        if _tp_ok and tp.has_segments:
            nc_segments = toolpath_to_nc_segments(tp)
            toolpath_summary = (
                f"status={tp.status.value} segments={tp.metrics.segment_count} "
                f"cut_length={tp.metrics.cut_length_mm:.3f}mm "
                f"depth={hole_depth_mm:.3f}mm clearance_z={clearance_z_mm:.3f}mm"
            )
        else:
            toolpath_summary = (
                f"BLOCKED: {', '.join(tp.missing_inputs) or 'unknown reason'}"
            )
            warnings.extend(tp.missing_inputs)

    # --- NC_CANDIDATE_REVIEW_READY ---
    cutting_params_ok = (
        confirmed_params is not None
        and confirmed_params.status.value == "USER_CONFIRMED"
    )
    nc_candidate_ready = bool(nc_segments)
    nc_candidate_review_ready = nc_candidate_ready and cutting_params_ok

    if not cutting_params_ok:
        warnings.append(
            "NC_CANDIDATE_REVIEW_READY=NO: cutting parameters not ENGINEER_CONFIRMED. "
            "Engineer must call confirm-cutting-parameters before NC review-ready status."
        )

    # --- Provenance record ---
    provenance: dict = {
        "sample_id": sample_id,
        "feature_id": feature_id,
        "tool_id": tool_id,
        "tool_match_status": tool_match_status,
        "tool_diameter_mm": tool_diameter_mm,
        "feature_diameter_mm": feature_diameter_mm,
        "material": material,
        "operation": operation,
        "depth_mm": hole_depth_mm,
        "wcs_ref": wcs_ref,
        "clearance_z_mm": clearance_z_mm,
        "clearance_source": clearance_source_str,
        "cutting_params_status": (
            confirmed_params.status.value if confirmed_params else "NOT_CONFIRMED"
        ),
        "nc_candidate_ready": nc_candidate_ready,
        "nc_candidate_review_ready": nc_candidate_review_ready,
        "is_dispatchable": False,
        "production_released": False,
        "offline_only": True,
    }

    return OfflineNCCandidate(
        sample_id=sample_id,
        feature_id=feature_id,
        route_id=route_id,
        machine_id=machine_id,
        tool_id=tool_id,
        tool_match_status=tool_match_status,
        tool_diameter_mm=tool_diameter_mm,
        feature_diameter_mm=feature_diameter_mm,
        tool_risk_warning=tool_risk,
        material=material,
        depth_mm=hole_depth_mm,
        operation=operation,
        confirmed_params=confirmed_params,
        wcs_ref=wcs_ref,
        clearance_z_mm=clearance_z_mm,
        clearance_source=clearance_source_str,
        toolpath_id=toolpath_id,
        toolpath_status=toolpath_status_str,
        toolpath_summary=toolpath_summary,
        nc_segments=nc_segments,
        provenance=provenance,
        warnings=warnings,
        review_status="PENDING_REVIEW",
        nc_candidate_review_ready=nc_candidate_review_ready,
    )


def evaluate_p6_readiness(
    *,
    feature_id: str,
    cam_ready: bool,
    cam_ready_blocker: str | None,
    machine_id: str | None,
    tool_id: str | None,
    tool_match_status: str | None,
    confirmed_params: EngineerConfirmedCuttingParameters | None,
    param_confirmation_status: ParameterConfirmationStatus | None,
    wcs_ref: str | None,
    clearance_eval: ClearanceEvaluationResult | None,
    nc_candidate: OfflineNCCandidate | None,
) -> P6ReadinessReport:
    """Compute all five P6 readiness levels for a feature.

    Parameters
    ----------
    feature_id:
        The feature being evaluated.
    cam_ready:
        Result from cam_gate.check_cam_prerequisites().cam_ready.
    cam_ready_blocker:
        First blocker from cam_gate, or None.
    machine_id:
        Stable ID of the selected machine, or None if not yet confirmed.
    tool_id:
        Stable ID of the selected tool, or None if not yet confirmed.
    tool_match_status:
        EXACT / COMPATIBLE / NO_MATCH — from P5-A.
    confirmed_params:
        Result from P6-C confirmation gate, or None if not yet confirmed.
    param_confirmation_status:
        Status from ParameterConfirmationResult, or None.
    wcs_ref:
        Named WCS reference, or None.
    clearance_eval:
        Result from P6-A evaluate_clearance(), or None.
    nc_candidate:
        Result from P6-D build_offline_nc_candidate(), or None.

    Returns
    -------
    P6ReadinessReport with all five levels and their blockers.
    """
    # Level 1: CAM_READY (cam_gate result — do not recompute)
    cam_blocker = cam_ready_blocker if not cam_ready else None

    # Level 2: PARAMETERIZED_CAM_READY
    p_blockers: list[str] = []
    if not cam_ready:
        p_blockers.append(f"CAM_READY=NO: {cam_ready_blocker}")
    if machine_id is None:
        p_blockers.append("MACHINE_ID_REQUIRED: no machine candidate confirmed")
    if tool_id is None or tool_match_status == "NO_MATCH":
        p_blockers.append("TOOL_ID_REQUIRED: no compatible tool found in catalog")
    if confirmed_params is None:
        p_blockers.append(
            "CUTTING_PARAMETERS_NOT_CONFIRMED: "
            "engineer must call confirm-cutting-parameters"
        )
    elif param_confirmation_status not in (
        ParameterConfirmationStatus.ENGINEER_CONFIRMED,
        ParameterConfirmationStatus.REVIEW_REQUIRED,
    ):
        p_blockers.append(
            f"CUTTING_PARAMETERS_INVALID: status={param_confirmation_status!s}"
        )
    if wcs_ref is None:
        p_blockers.append("WCS_REF_REQUIRED: no WCS reference defined")

    parameterized_ready = len(p_blockers) == 0
    param_blocker = "; ".join(p_blockers) if p_blockers else None

    # Level 3: TOOLPATH_READY
    t_blockers: list[str] = []
    if not parameterized_ready:
        t_blockers.append("PARAMETERIZED_CAM_READY=NO")
    if clearance_eval is None:
        t_blockers.append("CLEARANCE_NOT_EVALUATED")
    elif not clearance_eval.toolpath_ready:
        t_blockers.append(
            clearance_eval.blocker or "CLEARANCE_NOT_READY"
        )
    if nc_candidate is not None:
        if nc_candidate.toolpath_status in ("BLOCKED", "NOT_GENERATED"):
            t_blockers.append(
                f"TOOLPATH_BLOCKED: {nc_candidate.toolpath_summary}"
            )

    toolpath_ready = len(t_blockers) == 0
    tp_blocker = "; ".join(t_blockers) if t_blockers else None

    # Level 4: NC_CANDIDATE_READY
    nc_ready = (
        toolpath_ready
        and nc_candidate is not None
        and bool(nc_candidate.nc_segments)
    )
    nc_ready_blocker: str | None = None
    if not toolpath_ready:
        nc_ready_blocker = "TOOLPATH_READY=NO"
    elif nc_candidate is None or not nc_candidate.nc_segments:
        nc_ready_blocker = "NC_SEGMENTS_NOT_GENERATED"

    # Level 5: NC_CANDIDATE_REVIEW_READY
    cutting_confirmed = (
        confirmed_params is not None
        and param_confirmation_status == ParameterConfirmationStatus.ENGINEER_CONFIRMED
    )
    nc_review_ready = nc_ready and cutting_confirmed
    nc_review_blocker: str | None = None
    if not nc_ready:
        nc_review_blocker = "NC_CANDIDATE_READY=NO"
    elif not cutting_confirmed:
        nc_review_blocker = (
            "CUTTING_PARAMETERS_NOT_ENGINEER_CONFIRMED: "
            "MANUFACTURER_STARTING_VALUE is not sufficient for review-ready status"
        )

    return P6ReadinessReport(
        feature_id=feature_id,
        cam_ready=cam_ready,
        parameterized_cam_ready=parameterized_ready,
        toolpath_ready=toolpath_ready,
        nc_candidate_ready=nc_ready,
        nc_candidate_review_ready=nc_review_ready,
        cam_ready_blocker=cam_blocker,
        parameterized_cam_ready_blocker=param_blocker,
        toolpath_ready_blocker=tp_blocker,
        nc_candidate_ready_blocker=nc_ready_blocker,
        nc_candidate_review_ready_blocker=nc_review_blocker,
        tool_match_status=tool_match_status,
        cutting_params_status=(
            param_confirmation_status.value
            if param_confirmation_status is not None
            else None
        ),
        clearance_status=(
            clearance_eval.status.value if clearance_eval is not None else None
        ),
    )
