"""Level 6 — Cutting Data and Catalog Intelligence engine.

Derives CuttingDataIntelligenceResult from Level-5 MachineToolIntelligenceResult
and optional material input.  All calculations are deterministic and traceable.

HARD RULES:
  - Do NOT fabricate cutting speeds, feeds, depths, widths of cut, or tool-life.
  - Every result that carries numbers MUST have a CuttingDataProvenance record.
  - Generic reference ranges are explicitly labelled GENERIC_REFERENCE_RANGE.
  - Unknown material/tool/process remains UNKNOWN — do not invent it.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from backend.interoperability.cutting_data_intelligence import (
    CatalogLicenseStatus,
    CoolantMode,
    CuttingDataCandidate,
    CuttingDataIntelligenceResult,
    CuttingDataPlanStatus,
    CuttingDataProvenance,
    CuttingDataSourceType,
    CuttingDataStatus,
    FeedUnit,
    MachineConstraintResult,
    MachineConstraintStatus,
    MaterialRecord,
    MRRResult,
    OperationContext,
    RangeValue,
    ToolMaterialClass,
    calculate_milling_feed_rate,
    calculate_rpm,
    calculate_turning_feed_rate,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Phase 22 — Synthetic/test-only generic reference ranges
#
# These are GENERIC_REFERENCE_RANGE values intended for unit-test coverage.
# They must NOT be used in production without verification against a certified
# source.  Label is set IS_SYNTHETIC_TEST_DATA=True in the provenance.
# ---------------------------------------------------------------------------

# Key: (material_group, operation_type, tool_material_class)
# Value: (vc_min, vc_nom, vc_max, fz_min, fz_nom, fz_max, fn_min, fn_nom, fn_max)
#   fz = mm/tooth (milling), fn = mm/rev (drilling/turning)
#   None means the parameter does not apply to this operation family.
_GENERIC_REFERENCE_TABLE: dict[
    tuple[str, str, str],
    tuple[
        float, float, float,          # Vc min/nom/max  [m/min]
        float | None, float | None, float | None,  # fz min/nom/max  [mm/tooth]
        float | None, float | None, float | None,  # fn min/nom/max  [mm/rev]
    ],
] = {
    # P Steel
    ("P_STEEL", "DRILLING", "SOLID_CARBIDE"):
        (60.0, 90.0, 120.0, None, None, None, 0.10, 0.20, 0.30),
    ("P_STEEL", "DRILLING", "HSS"):
        (20.0, 30.0,  40.0, None, None, None, 0.10, 0.20, 0.25),
    ("P_STEEL", "DRILLING", "HSS_E"):
        (25.0, 35.0,  45.0, None, None, None, 0.10, 0.20, 0.25),
    ("P_STEEL", "CENTER_DRILLING", "SOLID_CARBIDE"):
        (40.0, 60.0,  80.0, None, None, None, 0.05, 0.10, 0.15),
    ("P_STEEL", "ROUGH_MILLING", "SOLID_CARBIDE"):
        (100.0, 140.0, 180.0, 0.05, 0.10, 0.15, None, None, None),
    ("P_STEEL", "FINISH_MILLING", "SOLID_CARBIDE"):
        (120.0, 160.0, 200.0, 0.02, 0.05, 0.08, None, None, None),
    ("P_STEEL", "FACE_MILLING", "CARBIDE_INSERT"):
        (150.0, 200.0, 250.0, 0.08, 0.12, 0.18, None, None, None),
    ("P_STEEL", "SLOT_MILLING", "SOLID_CARBIDE"):
        ( 80.0, 110.0, 140.0, 0.03, 0.06, 0.10, None, None, None),
    ("P_STEEL", "TURNING", "CARBIDE_INSERT"):
        (150.0, 220.0, 320.0, None, None, None, 0.10, 0.25, 0.40),
    # M Stainless steel
    ("M_STAINLESS", "DRILLING", "SOLID_CARBIDE"):
        (25.0, 40.0, 60.0, None, None, None, 0.05, 0.12, 0.20),
    ("M_STAINLESS", "ROUGH_MILLING", "SOLID_CARBIDE"):
        (60.0, 90.0, 120.0, 0.03, 0.06, 0.10, None, None, None),
    ("M_STAINLESS", "TURNING", "CARBIDE_INSERT"):
        (80.0, 120.0, 180.0, None, None, None, 0.08, 0.18, 0.30),
    # K Cast iron
    ("K_CAST_IRON", "DRILLING", "SOLID_CARBIDE"):
        (60.0, 90.0, 120.0, None, None, None, 0.10, 0.20, 0.30),
    ("K_CAST_IRON", "FACE_MILLING", "CARBIDE_INSERT"):
        (200.0, 300.0, 400.0, 0.10, 0.18, 0.25, None, None, None),
    # N Non-ferrous (aluminium alloys)
    ("N_NON_FERROUS", "DRILLING", "SOLID_CARBIDE"):
        (100.0, 150.0, 200.0, None, None, None, 0.10, 0.20, 0.35),
    ("N_NON_FERROUS", "ROUGH_MILLING", "SOLID_CARBIDE"):
        (200.0, 300.0, 400.0, 0.05, 0.10, 0.20, None, None, None),
    ("N_NON_FERROUS", "FINISH_MILLING", "SOLID_CARBIDE"):
        (300.0, 450.0, 600.0, 0.02, 0.05, 0.10, None, None, None),
    # S Superalloys / heat-resistant
    ("S_SUPERALLOY", "DRILLING", "SOLID_CARBIDE"):
        (10.0, 20.0, 35.0, None, None, None, 0.03, 0.08, 0.15),
    ("S_SUPERALLOY", "TURNING", "CARBIDE_INSERT"):
        (20.0, 35.0, 60.0, None, None, None, 0.05, 0.12, 0.20),
    # H Hardened steels
    ("H_HARDENED", "FINISH_MILLING", "SOLID_CARBIDE"):
        (60.0, 90.0, 120.0, 0.02, 0.04, 0.06, None, None, None),
    ("H_HARDENED", "TURNING", "CBN"):
        (80.0, 120.0, 180.0, None, None, None, 0.05, 0.10, 0.15),
}

_GENERIC_PROVENANCE = CuttingDataProvenance(
    source_type=CuttingDataSourceType.GENERIC_REFERENCE_RANGE,
    source_name="MachiningPro AI — Generic Engineering Reference",
    source_document="GENERIC_REFERENCE_RANGE (synthetic/test dataset)",
    source_version="1.0",
    source_date="2026-11-01",
    material_scope="P/M/K/N/S/H ISO material groups",
    tool_scope="generic carbide / HSS / CBN classes",
    operation_scope="drilling, milling, turning (generic)",
    validity_notes=(
        "These are generic engineering reference ranges for educational and "
        "test purposes only.  They are NOT vendor-certified.  Do NOT use "
        "without verification against a certified source."
    ),
    confidence="LOW — generic only, not material/grade specific",
    license_status=CatalogLicenseStatus.OPEN,
)


# ---------------------------------------------------------------------------
# Tool-family → operation context mapping
# ---------------------------------------------------------------------------

_TOOL_FAMILY_TO_OPERATION: dict[str, OperationContext] = {
    "DRILL":          OperationContext.DRILLING,
    "CENTER_DRILL":   OperationContext.CENTER_DRILLING,
    "REAMER":         OperationContext.REAMING,
    "TAP":            OperationContext.TAPPING,
    "THREAD_MILL":    OperationContext.THREAD_MILLING,
    "END_MILL":       OperationContext.ROUGH_MILLING,
    "BALL_END_MILL":  OperationContext.FINISH_MILLING,
    "FACE_MILL":      OperationContext.FACE_MILLING,
    "SLOT_MILL":      OperationContext.SLOT_MILLING,
    "CHAMFER_MILL":   OperationContext.CHAMFERING,
    "TURNING_INSERT": OperationContext.TURNING,
    "BORING_BAR":     OperationContext.BORING,
    "GROOVING_TOOL":  OperationContext.GROOVING,
    "PARTING_TOOL":   OperationContext.PARTING,
    "PROBE":          OperationContext.UNKNOWN,
    "DEBURRING_TOOL": OperationContext.UNKNOWN,
    "UNKNOWN":        OperationContext.UNKNOWN,
}

_TOOL_FAMILY_DEFAULT_MATERIAL: dict[str, ToolMaterialClass] = {
    "DRILL":          ToolMaterialClass.SOLID_CARBIDE,
    "CENTER_DRILL":   ToolMaterialClass.SOLID_CARBIDE,
    "REAMER":         ToolMaterialClass.SOLID_CARBIDE,
    "TAP":            ToolMaterialClass.HSS,
    "THREAD_MILL":    ToolMaterialClass.SOLID_CARBIDE,
    "END_MILL":       ToolMaterialClass.SOLID_CARBIDE,
    "BALL_END_MILL":  ToolMaterialClass.SOLID_CARBIDE,
    "FACE_MILL":      ToolMaterialClass.CARBIDE_INSERT,
    "SLOT_MILL":      ToolMaterialClass.SOLID_CARBIDE,
    "CHAMFER_MILL":   ToolMaterialClass.SOLID_CARBIDE,
    "TURNING_INSERT": ToolMaterialClass.CARBIDE_INSERT,
    "BORING_BAR":     ToolMaterialClass.CARBIDE_INSERT,
    "GROOVING_TOOL":  ToolMaterialClass.CARBIDE_INSERT,
    "PARTING_TOOL":   ToolMaterialClass.CARBIDE_INSERT,
    "PROBE":          ToolMaterialClass.UNKNOWN,
    "DEBURRING_TOOL": ToolMaterialClass.UNKNOWN,
    "UNKNOWN":        ToolMaterialClass.UNKNOWN,
}


# ---------------------------------------------------------------------------
# Hardness-based Vc adjustment (rule-based, not vendor-certified)
# ---------------------------------------------------------------------------

def _hardness_vc_factor(material_record: MaterialRecord) -> float:
    """Return a multiplier for Vc based on hardness (HRC).

    Rule: harder material → lower Vc.
    Only applied when hardness_unit is HRC and hardness is known.
    Returns 1.0 (no adjustment) when data is missing.
    """
    if material_record.hardness is None:
        return 1.0
    if material_record.hardness_unit.value != "HRC":
        return 1.0
    hrc = material_record.hardness
    if hrc <= 30:
        return 1.0
    elif hrc <= 40:
        return 0.85
    elif hrc <= 50:
        return 0.65
    elif hrc <= 55:
        return 0.45
    else:
        return 0.30


# ---------------------------------------------------------------------------
# Machine constraint check
# ---------------------------------------------------------------------------

def _check_machine_constraints(
    rpm_nominal: float | None,
    mti_result: object,
) -> MachineConstraintResult:
    """Check whether the nominal RPM falls within the machine's limits.

    Returns UNKNOWN when machine limits cannot be determined.
    """
    if rpm_nominal is None:
        return MachineConstraintResult(
            status=MachineConstraintStatus.UNKNOWN,
            evidence_notes="RPM unknown — cannot check machine constraints",
        )

    # Attempt to retrieve max_spindle_rpm from the first machine candidate.
    try:
        from backend.interoperability.machine_tool_intelligence import (
            MachineToolIntelligenceResult,
        )

        if not isinstance(mti_result, MachineToolIntelligenceResult):
            return MachineConstraintResult(
                status=MachineConstraintStatus.UNKNOWN,
                evidence_notes="mti_result is not a MachineToolIntelligenceResult",
            )

        candidates = mti_result.machine_candidates
        if not candidates:
            return MachineConstraintResult(
                status=MachineConstraintStatus.UNKNOWN,
                evidence_notes="No machine candidates — cannot check constraints",
            )

        # Use the first candidate's spindle speed range.
        first = candidates[0]
        max_rpm = getattr(first, "spindle_speed_rpm_max", None)
        min_rpm = getattr(first, "spindle_speed_rpm_min", None)

        if max_rpm is None:
            return MachineConstraintResult(
                status=MachineConstraintStatus.UNKNOWN,
                applied_constraint="spindle_speed_rpm_max",
                evidence_notes="Machine spindle max RPM not available",
            )

        if rpm_nominal > max_rpm:
            return MachineConstraintResult(
                status=MachineConstraintStatus.CONSTRAINED_BY_MACHINE,
                applied_constraint="spindle_speed_rpm_max",
                constrained_field="n_nominal",
                evidence_notes=(
                    f"Requested {rpm_nominal:.0f} rpm exceeds machine max "
                    f"{max_rpm:.0f} rpm — constrained to machine limit"
                ),
            )

        if min_rpm is not None and rpm_nominal < min_rpm:
            return MachineConstraintResult(
                status=MachineConstraintStatus.OUTSIDE_MACHINE_LIMITS,
                applied_constraint="spindle_speed_rpm_min",
                constrained_field="n_nominal",
                evidence_notes=(
                    f"Requested {rpm_nominal:.0f} rpm below machine min "
                    f"{min_rpm:.0f} rpm"
                ),
            )

        return MachineConstraintResult(
            status=MachineConstraintStatus.WITHIN_MACHINE_LIMITS,
            evidence_notes=f"n={rpm_nominal:.0f} rpm within machine limits",
        )

    except Exception as exc:  # noqa: BLE001
        return MachineConstraintResult(
            status=MachineConstraintStatus.UNKNOWN,
            evidence_notes=f"Machine constraint check failed: {exc}",
        )


# ---------------------------------------------------------------------------
# Generic range lookup
# ---------------------------------------------------------------------------

def _get_generic_range(
    material_group: str,
    operation: OperationContext,
    tool_material: ToolMaterialClass,
) -> tuple[RangeValue, RangeValue] | None:
    """Return (vc_range, feed_range) or None if no entry matches.

    feed_range is fz (mm/tooth) for milling, fn (mm/rev) for drilling/turning.
    """
    key = (material_group, operation.value, tool_material.value)
    row = _GENERIC_REFERENCE_TABLE.get(key)
    if row is None:
        return None

    vc_min, vc_nom, vc_max, fz_min, fz_nom, fz_max, fn_min, fn_nom, fn_max = row

    vc_range = RangeValue(
        min_val=vc_min,
        nominal_val=vc_nom,
        max_val=vc_max,
        unit="m/min",
    )

    if fz_nom is not None:
        feed_range = RangeValue(
            min_val=fz_min,
            nominal_val=fz_nom,
            max_val=fz_max,
            unit="mm/tooth",
        )
    elif fn_nom is not None:
        feed_range = RangeValue(
            min_val=fn_min,
            nominal_val=fn_nom,
            max_val=fn_max,
            unit="mm/rev",
        )
    else:
        feed_range = RangeValue(unit="")

    return vc_range, feed_range


# ---------------------------------------------------------------------------
# Candidate builder
# ---------------------------------------------------------------------------

def _build_candidate(
    candidate_id: str,
    material_record: MaterialRecord,
    operation: OperationContext,
    tool_family_str: str,
    tool_material: ToolMaterialClass,
    diameter_mm: float | None,
    machine_req_ref: str,
    tool_req_ref: str,
    mti_result: object,
) -> CuttingDataCandidate:
    """Build one CuttingDataCandidate.

    If material is UNKNOWN or no generic range exists for the combination,
    returns a candidate with status INSUFFICIENT_DATA — no values fabricated.
    """
    warns: list[str] = []

    # Determine whether we have material info.
    if material_record.material_group == "UNKNOWN":
        return CuttingDataCandidate(
            candidate_id=candidate_id,
            material_record=material_record,
            operation=operation,
            tool_family=tool_family_str,
            machine_requirement_ref=machine_req_ref,
            tool_requirement_ref=tool_req_ref,
            source=CuttingDataProvenance(
                source_type=CuttingDataSourceType.UNKNOWN,
                validity_notes=(
                    "Material group is UNKNOWN — cutting data cannot be derived. "
                    "Provide material information to enable cutting data."
                ),
            ),
            status=CuttingDataStatus.INSUFFICIENT_DATA,
            warnings=("material group unknown — cutting data requires material specification",),
            evidence_notes="Insufficient input: material_group is UNKNOWN",
        )

    if operation == OperationContext.UNKNOWN:
        return CuttingDataCandidate(
            candidate_id=candidate_id,
            material_record=material_record,
            operation=operation,
            tool_family=tool_family_str,
            machine_requirement_ref=machine_req_ref,
            tool_requirement_ref=tool_req_ref,
            source=CuttingDataProvenance(
                source_type=CuttingDataSourceType.UNKNOWN,
                validity_notes="Operation context unknown — cutting data cannot be derived",
            ),
            status=CuttingDataStatus.INSUFFICIENT_DATA,
            warnings=("operation context unknown",),
            evidence_notes="Insufficient input: operation_context is UNKNOWN",
        )

    # Look up generic range.
    result = _get_generic_range(material_record.material_group, operation, tool_material)

    if result is None:
        return CuttingDataCandidate(
            candidate_id=candidate_id,
            material_record=material_record,
            operation=operation,
            tool_family=tool_family_str,
            machine_requirement_ref=machine_req_ref,
            tool_requirement_ref=tool_req_ref,
            source=CuttingDataProvenance(
                source_type=CuttingDataSourceType.UNKNOWN,
                validity_notes=(
                    f"No generic reference range for combination: "
                    f"material={material_record.material_group}, "
                    f"operation={operation.value}, tool_material={tool_material.value}"
                ),
            ),
            status=CuttingDataStatus.INSUFFICIENT_DATA,
            warnings=(
                f"no generic range for {material_record.material_group}/"
                f"{operation.value}/{tool_material.value}",
            ),
            evidence_notes="No reference range available for this combination",
        )

    vc_range, feed_range = result

    # Apply hardness adjustment to Vc (rule-based only).
    factor = _hardness_vc_factor(material_record)
    if factor != 1.0:
        vc_range = RangeValue(
            min_val=vc_range.min_val * factor if vc_range.min_val is not None else None,
            nominal_val=vc_range.nominal_val * factor if vc_range.nominal_val is not None else None,
            max_val=vc_range.max_val * factor if vc_range.max_val is not None else None,
            unit=vc_range.unit,
        )
        warns.append(
            f"Vc adjusted by hardness factor {factor:.2f} "
            f"(HRC={material_record.hardness:.0f}) — rule-based only"
        )

    # Compute RPM if diameter is known.
    rpm_result = calculate_rpm(vc_range.nominal_val, diameter_mm)

    # Compute feed rate.
    feed_rate_result = None
    mrr = MRRResult(formula="MRR = ae × ap × Vf")

    if feed_range.unit == FeedUnit.MM_PER_TOOTH.value:
        # number_of_teeth is not derivable from L5 — left None, result = INSUFFICIENT
        feed_rate_result = calculate_milling_feed_rate(
            rpm=rpm_result.n_nominal,
            number_of_teeth=None,
            fz_mm_per_tooth=feed_range.nominal_val,
        )
    elif feed_range.unit == FeedUnit.MM_PER_REV.value:
        feed_rate_result = calculate_turning_feed_rate(
            rpm=rpm_result.n_nominal,
            fn_mm_per_rev=feed_range.nominal_val,
        )

    # MRR is not calculable without ae/ap specifics.
    mrr = MRRResult(
        warnings=("ae and ap not available from generic reference — MRR not calculable",),
        formula="MRR = ae × ap × Vf",
    )

    # Machine constraint check.
    constraint = _check_machine_constraints(rpm_result.n_nominal, mti_result)

    provenance = _GENERIC_PROVENANCE

    return CuttingDataCandidate(
        candidate_id=candidate_id,
        material_record=material_record,
        operation=operation,
        tool_family=tool_family_str,
        machine_requirement_ref=machine_req_ref,
        tool_requirement_ref=tool_req_ref,
        vc_range=vc_range,
        feed_range=feed_range,
        rpm_result=rpm_result,
        feed_rate_result=feed_rate_result or calculate_milling_feed_rate(None, None, None),
        mrr_result=mrr,
        machine_constraint=constraint,
        coolant=CoolantMode.UNKNOWN,
        source=provenance,
        status=CuttingDataStatus.GENERIC_REFERENCE,
        warnings=tuple(warns),
        evidence_notes=(
            f"Generic reference range: material={material_record.material_group}, "
            f"operation={operation.value}, tool_material={tool_material.value}. "
            f"Source: GENERIC_REFERENCE_RANGE (not vendor-certified). "
            f"Diameter={f'{diameter_mm:.2f} mm' if diameter_mm else 'unknown'}."
        ),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def derive_cutting_data_intelligence(
    mti_result: object,
    geometry: object = None,
    material: MaterialRecord | None = None,
) -> CuttingDataIntelligenceResult:
    """Derive a CuttingDataIntelligenceResult from Level-5 output.

    Parameters
    ----------
    mti_result:
        The MachineToolIntelligenceResult from Level-5.
    geometry:
        Optional CanonicalGeometry; used to extract diameter info.
    material:
        Optional MaterialRecord; when None the material group defaults to UNKNOWN
        and all cutting data candidates will have status INSUFFICIENT_DATA.

    Returns
    -------
    CuttingDataIntelligenceResult — always non-None.
    """
    plan_id = str(uuid.uuid4())

    try:
        from backend.interoperability.machine_tool_intelligence import (
            MachineToolIntelligenceResult,
        )
    except ImportError as exc:
        return CuttingDataIntelligenceResult(
            plan_id=plan_id,
            status=CuttingDataPlanStatus.INSUFFICIENT_DATA,
            recognition_basis="IMPORT_ERROR",
            warnings=(f"Import error: {exc}",),
        )

    if not isinstance(mti_result, MachineToolIntelligenceResult):
        return CuttingDataIntelligenceResult(
            plan_id=plan_id,
            status=CuttingDataPlanStatus.INSUFFICIENT_DATA,
            recognition_basis="INVALID_INPUT",
            warnings=("mti_result is not a MachineToolIntelligenceResult",),
        )

    mat = material if material is not None else MaterialRecord()

    source_mti_count = len(mti_result.machine_candidates)

    # If L5 had no tool candidates, there is nothing to derive cutting data for.
    tool_candidates = getattr(mti_result, "tool_candidates", ())
    if not tool_candidates:
        missing = list(getattr(mti_result, "missing_inputs", ()))
        if mat.material_group == "UNKNOWN":
            missing.insert(0, "material_group: required for cutting data derivation")
        return CuttingDataIntelligenceResult(
            plan_id=plan_id,
            status=CuttingDataPlanStatus.INSUFFICIENT_DATA,
            recognition_basis=f"L5_STATUS:{mti_result.status.value}",
            material_record=mat,
            missing_inputs=tuple(missing) + ("tool_candidates: no L5 tool candidates found",),
            warnings=(
                "No L5 tool candidates — cutting data cannot be derived. "
                "Material, operation, and tool information are all required.",
            ),
            source_mti_candidate_count=source_mti_count,
        )

    missing: list[str] = []
    if mat.material_group == "UNKNOWN":
        missing.append("material_group: required for cutting data derivation")

    # Build one cutting data candidate per tool candidate.
    candidates: list[CuttingDataCandidate] = []
    for i, tc in enumerate(tool_candidates):
        tool_family_str = getattr(tc, "tool_family", "UNKNOWN")
        if hasattr(tool_family_str, "value"):
            tool_family_str = tool_family_str.value

        operation = _TOOL_FAMILY_TO_OPERATION.get(
            tool_family_str, OperationContext.UNKNOWN
        )
        tool_material = _TOOL_FAMILY_DEFAULT_MATERIAL.get(
            tool_family_str, ToolMaterialClass.UNKNOWN
        )

        # Try to get diameter from tool requirement.
        diameter_mm: float | None = None
        tool_req_ref = getattr(tc, "requirement_ref", f"TOOL_REQ_{i}")
        machine_req_ref = ""

        # Attempt to extract diameter from requirement attributes.
        for attr in ("diameter_mm", "diameter", "nominal_diameter_mm"):
            val = getattr(tc, attr, None)
            if val is not None and isinstance(val, (int, float)) and val > 0:
                diameter_mm = float(val)
                break

        candidate = _build_candidate(
            candidate_id=f"CD-{plan_id[:8]}-{i:03d}",
            material_record=mat,
            operation=operation,
            tool_family_str=tool_family_str,
            tool_material=tool_material,
            diameter_mm=diameter_mm,
            machine_req_ref=machine_req_ref,
            tool_req_ref=str(tool_req_ref),
            mti_result=mti_result,
        )
        candidates.append(candidate)

    has_any = any(
        c.status not in (CuttingDataStatus.INSUFFICIENT_DATA, CuttingDataStatus.UNKNOWN)
        for c in candidates
    )

    if not candidates:
        status = CuttingDataPlanStatus.INSUFFICIENT_DATA
    elif has_any:
        status = CuttingDataPlanStatus.CANDIDATE_PLAN
    else:
        status = CuttingDataPlanStatus.INSUFFICIENT_DATA

    warns: list[str] = []
    if not has_any and candidates:
        warns.append(
            "All cutting data candidates have INSUFFICIENT_DATA status. "
            "Provide material information to enable cutting data derivation."
        )

    return CuttingDataIntelligenceResult(
        plan_id=plan_id,
        status=status,
        recognition_basis=f"L5_STATUS:{mti_result.status.value}",
        material_record=mat,
        cutting_data_candidates=tuple(candidates),
        missing_inputs=tuple(missing),
        warnings=tuple(warns),
        source_mti_candidate_count=source_mti_count,
    )
