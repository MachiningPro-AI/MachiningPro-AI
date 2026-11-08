"""Material Machining Context contract for Machine Library.

MaterialMachiningContext is a planning scenario:
  - ISO 513 material group (P / M / K / N / S / H)
  - Material grade reference (free text, optional)
  - Material condition (heat treatment state)
  - Intended machining operation
  - Optional spindle speed / power / torque requirements

evaluate_material_context() checks whether a MachineCatalogRecord's
declared capabilities are CONSISTENT with the context.

IMPORTANT
---------
A PASS result means "declared capabilities are not contradicted by this
context".  It is NOT a machine-safety certification, NOT a guarantee
the machine can successfully cut the material, and NOT an endorsement
that the tooling or parameters are correct.

ISO group is preserved as planning context metadata. It does NOT
drive PASS / FAIL on its own — only operation flags and spindle
specs drive the verdict.

Design rules
------------
MATERIAL_PASS_IS_NOT_CERTIFICATION=YES
MISSING_CAPABILITY_AS_CAPABLE=NO  — fail-closed on absent flags
UNKNOWN_TREATED_AS_PASS=NO
ISO_GROUP_GATES_MACHINE_VERDICT=NO  — planning context only
FABRICATED_SPINDLE_LIMIT=NO
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel

from backend.machine_library.models import MachineCatalogRecord

__all__ = [
    "MaterialISOGroup",
    "MaterialCondition",
    "MachiningOperation",
    "MaterialCompatibilityVerdict",
    "MaterialMachiningContext",
    "MaterialCompatibilityResult",
    "evaluate_material_context",
]


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class MaterialISOGroup(StrEnum):
    """ISO 513 chip-forming material groups."""

    P = "P"       # Steel (carbon, alloy, stainless ferritic/martensitic, cast steel)
    M = "M"       # Stainless steel (austenitic, duplex, super-austenitic)
    K = "K"       # Cast iron (grey, nodular, vermicular, malleable)
    N = "N"       # Non-ferrous (aluminium, copper, brass, bronze)
    S = "S"       # Superalloys and titanium
    H = "H"       # Hardened materials (> ~45 HRC, HSS, chilled cast iron)
    UNKNOWN = "UNKNOWN"


class MaterialCondition(StrEnum):
    """Heat treatment or as-received condition of the workpiece."""

    ANNEALED = "ANNEALED"
    NORMALISED = "NORMALISED"
    QUENCHED_TEMPERED = "QUENCHED_TEMPERED"
    HARDENED = "HARDENED"
    AS_CAST = "AS_CAST"
    AS_FORGED = "AS_FORGED"
    WORK_HARDENED = "WORK_HARDENED"
    UNKNOWN = "UNKNOWN"


class MachiningOperation(StrEnum):
    """Intended machining operation for context evaluation."""

    TURNING = "TURNING"
    MILLING = "MILLING"
    DRILLING = "DRILLING"
    TAPPING = "TAPPING"
    BORING = "BORING"
    REAMING = "REAMING"
    THREADING = "THREADING"
    GRINDING = "GRINDING"
    WIRE_EDM = "WIRE_EDM"
    SINKER_EDM = "SINKER_EDM"
    UNKNOWN = "UNKNOWN"


class MaterialCompatibilityVerdict(StrEnum):
    """Verdict of a material context evaluation against a machine record."""

    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


# ---------------------------------------------------------------------------
# Context model
# ---------------------------------------------------------------------------


class MaterialMachiningContext(BaseModel):
    """Planning context describing what is to be machined and how.

    All spindle requirement fields are optional — None means unconstrained.
    Setting a spindle requirement without a matching machine spec yields UNKNOWN
    (not PASS) because the constraint cannot be verified.
    """

    iso_group: MaterialISOGroup
    material_grade_ref: str | None = None       # e.g. "1.4301", "Ti-6Al-4V", "HB 300"
    material_condition: MaterialCondition = MaterialCondition.UNKNOWN
    operation: MachiningOperation

    # Optional spindle requirements — None = unconstrained
    min_spindle_speed_rpm: int | None = None
    min_spindle_power_kw: float | None = None
    min_spindle_torque_nm: float | None = None


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class MaterialCompatibilityResult:
    """Outcome of evaluate_material_context() for one machine record."""

    verdict: MaterialCompatibilityVerdict
    machine_stable_id: str
    operation: MachiningOperation
    iso_group: MaterialISOGroup
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_pass(self) -> bool:
        return self.verdict is MaterialCompatibilityVerdict.PASS

    @property
    def is_fail(self) -> bool:
        return self.verdict is MaterialCompatibilityVerdict.FAIL

    @property
    def is_unknown(self) -> bool:
        return self.verdict is MaterialCompatibilityVerdict.UNKNOWN


# ---------------------------------------------------------------------------
# Operation → capability flag mapping
# ---------------------------------------------------------------------------

# Maps MachiningOperation to the boolean attribute on MachineCapability that
# declares the machine can perform that operation.
# TAPPING, BORING, REAMING, THREADING may also use sub-flags when present.
_PRIMARY_CAPABILITY: dict[MachiningOperation, str] = {
    MachiningOperation.TURNING:   "turning_capable",
    MachiningOperation.MILLING:   "milling_capable",
    MachiningOperation.DRILLING:  "drilling_capable",
    MachiningOperation.GRINDING:  "grinding_capable",
    MachiningOperation.WIRE_EDM:  "edm_capable",
    MachiningOperation.SINKER_EDM: "edm_capable",
}

# Sub-flags checked when primary is True (None = no sub-flag exists)
_SUB_FLAG: dict[MachiningOperation, str | None] = {
    MachiningOperation.TAPPING:   "capable_tapping",
    MachiningOperation.BORING:    "capable_boring",
    MachiningOperation.REAMING:   "capable_reaming",
    MachiningOperation.THREADING: "capable_threading",
}

# Operations that derive primary capability from an existing primary op
_DERIVED_FROM: dict[MachiningOperation, MachiningOperation] = {
    MachiningOperation.TAPPING:   MachiningOperation.DRILLING,
    MachiningOperation.BORING:    MachiningOperation.MILLING,
    MachiningOperation.REAMING:   MachiningOperation.DRILLING,
    MachiningOperation.THREADING: MachiningOperation.TURNING,
}


# ---------------------------------------------------------------------------
# Evaluation function
# ---------------------------------------------------------------------------


def evaluate_material_context(
    context: MaterialMachiningContext,
    record: MachineCatalogRecord,
) -> MaterialCompatibilityResult:
    """Evaluate whether *record* is consistent with *context*.

    Verdict rules (applied in order):
    1. UNKNOWN operation → UNKNOWN.
    2. Primary process capability flag False → FAIL.
    3. For derived operations: primary capability must be True first.
    4. Sub-flag explicitly False → FAIL (None = not declared, not False).
    5. Spindle speed constraint: if min_spindle_speed_rpm set
         and spindle.max_rpm is None → UNKNOWN (insufficient data)
         and spindle.max_rpm < requirement → FAIL.
    6. Spindle power constraint: same pattern for power_kw.
    7. Spindle torque constraint: same pattern for torque_nm.
    8. All constraints satisfied → PASS.

    The ISO group is recorded in the result but does NOT alter the verdict.
    A PASS result is not a certification of machining suitability.
    """
    cap = record.capability
    spn = record.spindle
    op = context.operation
    reasons: list[str] = []
    warnings: list[str] = []

    # --- Step 1: Unknown operation ---
    if op is MachiningOperation.UNKNOWN:
        return MaterialCompatibilityResult(
            verdict=MaterialCompatibilityVerdict.UNKNOWN,
            machine_stable_id=record.stable_id,
            operation=op,
            iso_group=context.iso_group,
            reasons=["UNKNOWN_OPERATION: operation not specified"],
        )

    # --- Step 2: Primary capability check ---
    primary_flag_name: str | None = None
    if op in _PRIMARY_CAPABILITY:
        primary_flag_name = _PRIMARY_CAPABILITY[op]
    elif op in _DERIVED_FROM:
        primary_flag_name = _PRIMARY_CAPABILITY.get(_DERIVED_FROM[op])

    if primary_flag_name is not None:
        primary_val = getattr(cap, primary_flag_name, None)
        if primary_val is False:
            return MaterialCompatibilityResult(
                verdict=MaterialCompatibilityVerdict.FAIL,
                machine_stable_id=record.stable_id,
                operation=op,
                iso_group=context.iso_group,
                reasons=[
                    f"OPERATION_NOT_SUPPORTED: {primary_flag_name}=False "
                    f"for operation {op}"
                ],
            )
        if primary_val is None:
            reasons.append(
                f"CAPABILITY_FLAG_MISSING: {primary_flag_name} not declared"
            )

    # --- Step 3: Sub-flag check for derived operations ---
    if op in _SUB_FLAG:
        sub_flag_name = _SUB_FLAG[op]
        if sub_flag_name is not None:
            sub_val = getattr(cap, sub_flag_name, None)
            if sub_val is False:
                return MaterialCompatibilityResult(
                    verdict=MaterialCompatibilityVerdict.FAIL,
                    machine_stable_id=record.stable_id,
                    operation=op,
                    iso_group=context.iso_group,
                    reasons=[
                        f"OPERATION_NOT_SUPPORTED: {sub_flag_name}=False "
                        f"for operation {op}"
                    ],
                )
            if sub_val is None:
                reasons.append(
                    f"CAPABILITY_FLAG_MISSING: {sub_flag_name} not declared "
                    f"(None does not mean capable)"
                )

    # --- Step 4: Spindle speed constraint ---
    unknown_due_to_spindle = False
    if context.min_spindle_speed_rpm is not None:
        if spn.max_rpm is None:
            reasons.append(
                f"SPINDLE_DATA_ABSENT: spindle.max_rpm unknown — cannot verify "
                f"min_spindle_speed_rpm={context.min_spindle_speed_rpm}"
            )
            unknown_due_to_spindle = True
        elif spn.max_rpm < context.min_spindle_speed_rpm:
            return MaterialCompatibilityResult(
                verdict=MaterialCompatibilityVerdict.FAIL,
                machine_stable_id=record.stable_id,
                operation=op,
                iso_group=context.iso_group,
                reasons=[
                    f"SPINDLE_SPEED_INSUFFICIENT: machine max_rpm={spn.max_rpm} < "
                    f"required {context.min_spindle_speed_rpm} rpm"
                ],
            )

    # --- Step 5: Spindle power constraint ---
    if context.min_spindle_power_kw is not None:
        if spn.power_kw is None:
            reasons.append(
                f"SPINDLE_DATA_ABSENT: spindle.power_kw unknown — cannot verify "
                f"min_spindle_power_kw={context.min_spindle_power_kw}"
            )
            unknown_due_to_spindle = True
        elif spn.power_kw < context.min_spindle_power_kw:
            return MaterialCompatibilityResult(
                verdict=MaterialCompatibilityVerdict.FAIL,
                machine_stable_id=record.stable_id,
                operation=op,
                iso_group=context.iso_group,
                reasons=[
                    f"SPINDLE_POWER_INSUFFICIENT: machine power_kw={spn.power_kw} < "
                    f"required {context.min_spindle_power_kw} kW"
                ],
            )

    # --- Step 6: Spindle torque constraint ---
    if context.min_spindle_torque_nm is not None:
        if spn.torque_nm is None:
            reasons.append(
                f"SPINDLE_DATA_ABSENT: spindle.torque_nm unknown — cannot verify "
                f"min_spindle_torque_nm={context.min_spindle_torque_nm}"
            )
            unknown_due_to_spindle = True
        elif spn.torque_nm < context.min_spindle_torque_nm:
            return MaterialCompatibilityResult(
                verdict=MaterialCompatibilityVerdict.FAIL,
                machine_stable_id=record.stable_id,
                operation=op,
                iso_group=context.iso_group,
                reasons=[
                    f"SPINDLE_TORQUE_INSUFFICIENT: machine torque_nm={spn.torque_nm} < "
                    f"required {context.min_spindle_torque_nm} Nm"
                ],
            )

    # --- ISO group advisory warning (planning context only) ---
    if context.iso_group is MaterialISOGroup.S:
        warnings.append(
            "ISO_S: Superalloys/titanium — verify spindle power and torque specs; "
            "PASS does not certify suitability for high-temperature alloys"
        )
    elif context.iso_group is MaterialISOGroup.H:
        warnings.append(
            "ISO_H: Hardened material — verify process and tooling independently; "
            "PASS does not certify suitability for hard cutting/grinding"
        )

    # --- Final verdict ---
    if unknown_due_to_spindle or reasons:
        # At least one UNKNOWN reason (spindle data absent or flag missing)
        return MaterialCompatibilityResult(
            verdict=MaterialCompatibilityVerdict.UNKNOWN,
            machine_stable_id=record.stable_id,
            operation=op,
            iso_group=context.iso_group,
            reasons=reasons,
            warnings=warnings,
        )

    reasons.append(f"OPERATION_CONSISTENT: {op} declared capable")
    return MaterialCompatibilityResult(
        verdict=MaterialCompatibilityVerdict.PASS,
        machine_stable_id=record.stable_id,
        operation=op,
        iso_group=context.iso_group,
        reasons=reasons,
        warnings=warnings,
    )
