"""Auto CAM enhanced cutting parameter engine — MACHININGPRO_AI_BETA3_PARAMS_01.

Enhanced S08 stage that queries the existing CuttingParameterRegistry,
then calculates RPM and feed rate using existing formula functions.

HARD RULES:
  NO fabricated cutting parameters.
  Every derived value reports SOURCE_TYPE + formula provenance.
  Machine spindle_max_rpm clamping where data available.
  NOT_AVAILABLE when no registry data exists for the operation.
  DUPLICATE_ENGINE_CREATED=NO — calls existing registry + formulas.

Coverage audit (Phase M):
  DRILLING   — OperationType.DRILLING; Vc + fn/fz from registry
  MILLING    — OperationType.MILLING;  Vc + fz from registry
  Vc source  — REFERENCE_ONLY records (74 total when env var set)
  RPM calc   — spindle_speed_from_cutting_speed (formulas.py)
  Feed calc  — feed_rate_from_rpm_feed_per_rev / feed_rate_from_rpm_tooth_feed
  Clamp      — CLAMPED_TO_MACHINE_LIMIT when RPM > spindle_max_rpm
"""
from __future__ import annotations

import os
from pathlib import Path

from backend.cutting_parameters.models import ApplicabilityScope, ParameterType
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.cutting_parameters.seed_reference import seed_reference_registry
from backend.domain.enums import OperationType
from backend.domain.units import Quantity, Unit
from backend.machining.formulas import (
    feed_rate_from_rpm_feed_per_rev,
    feed_rate_from_rpm_tooth_feed,
    spindle_speed_from_cutting_speed,
)

from .models import AutoCamFeatureInput, CuttingParamResult, MachineResult, ToolResult

# ---------------------------------------------------------------------------
# Registry singleton (lazy, shared with cutting_parameters API)
# ---------------------------------------------------------------------------

_registry: CuttingParameterRegistry | None = None
_seeded_path: str | None = None


def _get_registry() -> CuttingParameterRegistry:
    global _registry, _seeded_path
    current_path = os.environ.get("MACHININGPRO_CUTTING_PARAM_REF_PATH")
    if _registry is None or (
        current_path and current_path != _seeded_path
    ):
        reg = CuttingParameterRegistry()
        if current_path and Path(current_path).is_file():
            try:
                seed_reference_registry(reg, current_path)
                _seeded_path = current_path
            except Exception:
                pass
        _registry = reg
    return _registry


def _set_registry(reg: CuttingParameterRegistry | None) -> None:
    """Inject a pre-seeded registry. Used in tests only. Pass None to reset."""
    global _registry, _seeded_path
    _registry = reg
    _seeded_path = None  # allow env-var override after injection


# ---------------------------------------------------------------------------
# Feature → operation type mapping
# ---------------------------------------------------------------------------

_FEATURE_TO_OP: dict[str, OperationType] = {
    "HOLE": OperationType.DRILLING,
    "POCKET": OperationType.MILLING,
    "SLOT": OperationType.MILLING,
    "STEP_SHOULDER": OperationType.MILLING,
    "PLANAR_FACE": OperationType.MILLING,
}

_DEFAULT_FLUTE_COUNT: dict[str, int] = {
    "HOLE": 2,       # standard twist drill
    "POCKET": 2,
    "SLOT": 2,
    "STEP_SHOULDER": 2,
    "PLANAR_FACE": 2,
}


# ---------------------------------------------------------------------------
# Main engine function
# ---------------------------------------------------------------------------


def compute_cutting_params(
    feature: AutoCamFeatureInput,
    tool: ToolResult,
    machine: MachineResult,
) -> CuttingParamResult:
    """Compute cutting parameters with provenance for one feature.

    Phase N provenance fields returned:
      PARAMETER / VALUE / UNIT / SOURCE_TYPE / SOURCE_NAME /
      SOURCE_REFERENCE / STATUS / CONFIDENCE_OR_QUALITY_STATE

    Phase O formulas used (from formulas.py):
      RPM   = spindle_speed_from_cutting_speed(Vc, D)
            = 1000 × Vc / (π × D)
      Feed  = feed_rate_from_rpm_feed_per_rev(RPM, fn)   [drilling]
            = feed_rate_from_rpm_tooth_feed(RPM, z, fz)  [milling]

    Phase P clamping:
      If RPM > machine.spindle_max_rpm:
        status += CLAMPED_TO_MACHINE_LIMIT
        final RPM = spindle_max_rpm
    """
    ft = feature.feature_type.upper()
    op_type = _FEATURE_TO_OP.get(ft)
    if op_type is None:
        return CuttingParamResult(
            status="NOT_AVAILABLE",
            provenance=f"feature_type={ft} not mapped to OperationType",
        )

    reg = _get_registry()
    scope = ApplicabilityScope(operation_type=op_type)

    # ── Query registry for Vc ─────────────────────────────────────────────
    vc_records = reg.find(scope=scope, parameter_type=ParameterType.CUTTING_SPEED)
    if not vc_records:
        return CuttingParamResult(
            status="NOT_AVAILABLE",
            provenance=(
                f"No CUTTING_SPEED records for {op_type.value} in registry "
                f"(KL-05: set MACHININGPRO_CUTTING_PARAM_REF_PATH)"
            ),
        )

    # Use midpoint of first record's range (reference orientation)
    vc_rec = vc_records[0]
    vc_min = float(vc_rec.value_range.min_value.value)
    vc_max = float(vc_rec.value_range.max_value.value)
    vc_mid = (vc_min + vc_max) / 2.0
    vc_provenance = (
        f"SOURCE_TYPE=REFERENCE_ONLY "
        f"PROVENANCE_TYPE={vc_rec.provenance.source_type} "
        f"SOURCE_REFERENCE={vc_rec.provenance.source_reference or 'none'} "
        f"SOURCE_DOCUMENT={vc_rec.provenance.source_document or 'none'} "
        f"EVIDENCE_STATUS={vc_rec.evidence_status.value} "
        f"CONFIDENCE=REFERENCE_ONLY_NOT_AUTHORITATIVE"
    )

    # Need tool diameter for RPM calculation
    tool_d = tool.tool_diameter_mm
    if tool_d is None or tool_d <= 0:
        return CuttingParamResult(
            vc_m_per_min=round(vc_mid, 2),
            status="PARTIAL",
            provenance=(
                f"Vc={vc_mid:.2f} m/min {vc_provenance}; "
                f"RPM not calculated (tool_diameter_mm unknown)"
            ),
        )

    # ── RPM calculation (Phase O) ─────────────────────────────────────────
    rpm_qty = spindle_speed_from_cutting_speed(
        Quantity.of(vc_mid, Unit.M_MIN),
        Quantity.of(tool_d, Unit.MM),
    )
    rpm_raw = float(rpm_qty.value)
    rpm_formula = (
        f"RPM = 1000 × {vc_mid:.2f} / (π × {tool_d}) = {rpm_raw:.1f} "
        f"[formulas.py:spindle_speed_from_cutting_speed]"
    )

    # ── Machine limit clamping (Phase P) ──────────────────────────────────
    rpm_final = rpm_raw
    clamp_note = ""
    if machine.spindle_max_rpm and rpm_raw > machine.spindle_max_rpm:
        rpm_final = float(machine.spindle_max_rpm)
        clamp_note = (
            f" CLAMPED_TO_MACHINE_LIMIT: "
            f"RAW_CALCULATED_VALUE={rpm_raw:.1f} "
            f"MACHINE_LIMIT={machine.spindle_max_rpm} "
            f"FINAL_SUGGESTED_VALUE={rpm_final:.1f} "
            f"LIMITING_REASON=spindle_max_rpm exceeded"
        )

    # ── Feed rate calculation ─────────────────────────────────────────────
    fn_records = reg.find(scope=scope, parameter_type=ParameterType.FEED_PER_REV)
    fz_records = reg.find(scope=scope, parameter_type=ParameterType.FEED_PER_TOOTH)

    feed_mm_min: float | None = None
    fz_val: float | None = None
    fn_val: float | None = None
    feed_note = ""

    if fn_records:
        fn_rec = fn_records[0]
        fn_min = float(fn_rec.value_range.min_value.value)
        fn_max = float(fn_rec.value_range.max_value.value)
        fn_val = (fn_min + fn_max) / 2.0
        feed_qty = feed_rate_from_rpm_feed_per_rev(
            Quantity.of(rpm_final, Unit.RPM),
            Quantity.of(fn_val, Unit.MM_REV),
        )
        feed_mm_min = float(feed_qty.value)
        feed_note = (
            f"Feed = {rpm_final:.1f} RPM × {fn_val:.4f} mm/rev = {feed_mm_min:.2f} mm/min "
            f"[formulas.py:feed_rate_from_rpm_feed_per_rev]"
        )
    elif fz_records:
        fz_rec = fz_records[0]
        fz_min = float(fz_rec.value_range.min_value.value)
        fz_max = float(fz_rec.value_range.max_value.value)
        fz_val = (fz_min + fz_max) / 2.0
        z = _DEFAULT_FLUTE_COUNT.get(ft, 2)
        feed_qty = feed_rate_from_rpm_tooth_feed(
            Quantity.of(rpm_final, Unit.RPM),
            z,
            Quantity.of(fz_val, Unit.MM_TOOTH),
        )
        feed_mm_min = float(feed_qty.value)
        feed_note = (
            f"Feed = {rpm_final:.1f} RPM × {z} teeth × {fz_val:.4f} mm/tooth "
            f"= {feed_mm_min:.2f} mm/min "
            f"[formulas.py:feed_rate_from_rpm_tooth_feed]"
        )

    full_provenance = (
        f"{vc_provenance} "
        f"FORMULA: {rpm_formula}"
        f"{clamp_note}"
    )
    if feed_note:
        full_provenance += f" {feed_note}"

    calc_status = "CALCULATED" if feed_mm_min is not None else "PARTIAL"
    if clamp_note:
        calc_status = "CLAMPED_TO_MACHINE_LIMIT"

    return CuttingParamResult(
        vc_m_per_min=round(vc_mid, 2),
        rpm=round(rpm_final, 1),
        feed_mm_per_min=round(feed_mm_min, 2) if feed_mm_min is not None else None,
        fz_mm=round(fz_val, 4) if fz_val is not None else None,
        status=calc_status,
        provenance=full_provenance,
    )
