"""Machine Library catalog-record validation rules (V-ML-01 through V-ML-28).

Design principles
-----------------
* Pure functions — no I/O, no AI.
* Fail-closed: absent capability limits produce warnings, never passes.
* MISSING_VALUE_AS_ZERO=NO — None fields are never coerced.
* FABRICATED_MACHINE_SPEC=NO — no synthetic values injected.
* UNKNOWN_LIMIT_TREATED_AS_UNLIMITED=NO.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.machine_library.enums import MachineClass
from backend.machine_library.models import MachineCatalogRecord

__all__ = [
    "MachineCatalogValidationResult",
    "validate_machine_catalog_record",
]

_ALL_MACHINE_CLASSES = frozenset(mc.value for mc in MachineClass)


@dataclass
class MachineCatalogValidationResult:
    """Result of validating one MachineCatalogRecord."""

    stable_id: str
    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


def validate_machine_catalog_record(
    record: MachineCatalogRecord,
) -> MachineCatalogValidationResult:
    """Validate *record* against V-ML-01 through V-ML-28.

    Returns MachineCatalogValidationResult.  Records with errors are
    not safe to register in production catalogs.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # V-ML-01: stable_id must be non-empty, no leading/trailing whitespace
    sid = record.stable_id
    if not sid or sid != sid.strip():
        errors.append("V-ML-01: stable_id is empty or contains leading/trailing whitespace")

    # V-ML-02: manufacturer must be non-empty
    if not record.manufacturer or not record.manufacturer.strip():
        errors.append("V-ML-02: manufacturer is required and must be non-empty")

    # V-ML-03: model must be non-empty
    if not record.model or not record.model.strip():
        errors.append("V-ML-03: model is required and must be non-empty")

    # V-ML-04: machine_class must be a valid MachineClass
    cap = record.capability
    if cap.machine_class.value not in _ALL_MACHINE_CLASSES:
        errors.append(
            f"V-ML-04: machine_class {cap.machine_class!r} is not a known MachineClass"
        )

    # V-ML-05: controlled_axes must be a positive integer
    if cap.controlled_axes < 1:
        errors.append("V-ML-05: controlled_axes must be a positive integer (≥1)")

    # V-ML-06: simultaneous_axes ≤ controlled_axes when present
    if cap.simultaneous_axes is not None:
        if cap.simultaneous_axes < 1:
            errors.append(
                "V-ML-06: simultaneous_axes must be positive when provided"
            )
        elif cap.simultaneous_axes > cap.controlled_axes:
            errors.append(
                f"V-ML-06: simultaneous_axes ({cap.simultaneous_axes}) cannot exceed "
                f"controlled_axes ({cap.controlled_axes})"
            )

    # V-ML-07: at least one primary process capability must be True
    if not cap.has_primary_capability:
        errors.append(
            "V-ML-07: at least one of turning_capable/milling_capable/drilling_capable/"
            "grinding_capable/edm_capable must be True"
        )

    # V-ML-08: source_title must be non-empty
    src = record.source
    if not src.source_title or not src.source_title.strip():
        errors.append("V-ML-08: source.source_title is required and must be non-empty")

    # V-ML-09: spindle max_rpm must be positive when present
    spn = record.spindle
    if spn.max_rpm is not None:
        if spn.max_rpm <= 0:
            errors.append("V-ML-09: spindle.max_rpm must be positive when provided")

    # V-ML-10: spindle min_rpm must be positive and < max_rpm when both present
    if spn.min_rpm is not None:
        if spn.min_rpm <= 0:
            errors.append("V-ML-10: spindle.min_rpm must be positive when provided")
        elif spn.max_rpm is not None and spn.min_rpm >= spn.max_rpm:
            errors.append(
                f"V-ML-10: spindle.min_rpm ({spn.min_rpm}) must be < "
                f"spindle.max_rpm ({spn.max_rpm})"
            )

    # V-ML-11: spindle power must be positive when present
    if spn.power_kw is not None and spn.power_kw <= 0:
        errors.append("V-ML-11: spindle.power_kw must be positive when provided")

    # V-ML-12: spindle torque must be positive when present
    if spn.torque_nm is not None and spn.torque_nm <= 0:
        errors.append("V-ML-12: spindle.torque_nm must be positive when provided")

    # V-ML-13: travel dimensions must be positive when present
    env = record.envelope
    for attr in ("travel_x_mm", "travel_y_mm", "travel_z_mm"):
        val = getattr(env, attr)
        if val is not None and val <= 0:
            errors.append(f"V-ML-13: envelope.{attr} must be positive when provided")

    # V-ML-14: table dimensions must be positive when present
    for attr in ("table_length_mm", "table_width_mm"):
        val = getattr(env, attr)
        if val is not None and val <= 0:
            errors.append(f"V-ML-14: envelope.{attr} must be positive when provided")

    # V-ML-15: table_load_kg must be positive when present
    if env.table_load_kg is not None and env.table_load_kg <= 0:
        errors.append("V-ML-15: envelope.table_load_kg must be positive when provided")

    # V-ML-16: bar_capacity_mm only relevant when turning_capable
    if env.bar_capacity_mm is not None and not cap.turning_capable:
        warnings.append(
            "V-ML-16: envelope.bar_capacity_mm provided but capability.turning_capable=False"
        )

    # V-ML-17: max_turning_diameter_mm only relevant when turning_capable
    if env.max_turning_diameter_mm is not None and not cap.turning_capable:
        warnings.append(
            "V-ML-17: envelope.max_turning_diameter_mm provided but "
            "capability.turning_capable=False"
        )

    # V-ML-18: tool_magazine_capacity must be positive when present
    if cap.tool_magazine_capacity is not None and cap.tool_magazine_capacity <= 0:
        errors.append(
            "V-ML-18: capability.tool_magazine_capacity must be positive when provided"
        )

    # V-ML-19: rapid_traverse_mpm must be positive when present
    if cap.rapid_traverse_mpm is not None and cap.rapid_traverse_mpm <= 0:
        errors.append(
            "V-ML-19: capability.rapid_traverse_mpm must be positive when provided"
        )

    # V-ML-20: 5-axis simultaneous requires simultaneous_axes == 5
    if cap.capable_5axis_simultaneous is True and cap.simultaneous_axes != 5:
        warnings.append(
            "V-ML-20: capable_5axis_simultaneous=True but simultaneous_axes != 5"
        )

    # V-ML-21: HMC/5-axis classes should declare pallet_changer or >= 4 axes
    if cap.machine_class is MachineClass.HMC and cap.controlled_axes < 4:
        warnings.append(
            "V-ML-21: MachineClass.HMC typically has ≥4 controlled axes; "
            f"controlled_axes={cap.controlled_axes}"
        )

    # V-ML-22: SWISS_LATHE should declare bar_capacity_mm
    if cap.machine_class is MachineClass.SWISS_LATHE and env.bar_capacity_mm is None:
        warnings.append(
            "V-ML-22: MachineClass.SWISS_LATHE — bar_capacity_mm is absent "
            "(INSUFFICIENT_DATA for Swiss-type compatibility)"
        )

    # V-ML-23: spindle max_rpm absent → INSUFFICIENT_DATA warning
    if spn.max_rpm is None:
        warnings.append(
            "V-ML-23: spindle.max_rpm is absent — INSUFFICIENT_DATA for spindle checks"
        )

    # V-ML-24: spindle power_kw absent → INSUFFICIENT_DATA warning
    if spn.power_kw is None:
        warnings.append(
            "V-ML-24: spindle.power_kw is absent — INSUFFICIENT_DATA for power checks"
        )

    # V-ML-25: machine_weight_kg must be positive when present
    if record.machine_weight_kg is not None and record.machine_weight_kg <= 0:
        errors.append("V-ML-25: machine_weight_kg must be positive when provided")

    # V-ML-26: year_discontinued requires year_introduced when both present
    if (
        record.year_discontinued is not None
        and record.year_introduced is not None
        and record.year_discontinued < record.year_introduced
    ):
        errors.append(
            "V-ML-26: year_discontinued cannot be earlier than year_introduced"
        )

    # V-ML-27: TURN_MILL should be both turning and milling capable
    if cap.machine_class is MachineClass.TURN_MILL:
        if not cap.turning_capable or not cap.milling_capable:
            warnings.append(
                "V-ML-27: MachineClass.TURN_MILL should declare both "
                "turning_capable=True and milling_capable=True"
            )

    # V-ML-28: DRILL_TAP_CENTER should declare capable_tapping
    if cap.machine_class is MachineClass.DRILL_TAP_CENTER and cap.capable_tapping is None:
        warnings.append(
            "V-ML-28: MachineClass.DRILL_TAP_CENTER — capable_tapping is absent; "
            "set True or False explicitly"
        )

    return MachineCatalogValidationResult(
        stable_id=record.stable_id,
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
