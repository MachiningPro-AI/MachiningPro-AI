"""Validation rules for MaterialCatalogRecord (V-MAT-01 through V-MAT-11).

FABRICATED_MATERIAL_PROPERTY=NO
MISSING_VALUE_AS_NONE=YES
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.material_library.enums import MaterialISOGroup, MaterialSubGroup
from backend.material_library.models import MaterialCatalogRecord

__all__ = [
    "MaterialValidationIssue",
    "MaterialValidationResult",
    "validate_material_catalog_record",
]

_S_REQUIRED_SUBGROUPS = {MaterialSubGroup.S_TITANIUM, MaterialSubGroup.S_NICKEL_HRSA}

_DENSITY_MIN = 1_500.0
_DENSITY_MAX = 22_000.0
_TENSILE_MAX = 3_500.0


@dataclass(frozen=True)
class MaterialValidationIssue:
    field: str
    code: str
    message: str


@dataclass
class MaterialValidationResult:
    stable_id: str
    issues: list[MaterialValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return len(self.issues) == 0

    @property
    def issue_codes(self) -> list[str]:
        return [i.code for i in self.issues]


def validate_material_catalog_record(
    record: MaterialCatalogRecord,
) -> MaterialValidationResult:
    """Run all V-MAT rules against *record*.

    Returns a result with an empty issue list when the record is valid.
    Rules applied in order; all rules checked (not short-circuit).
    """
    issues: list[MaterialValidationIssue] = []

    def _err(field: str, code: str, msg: str) -> None:
        issues.append(MaterialValidationIssue(field=field, code=code, message=msg))

    # V-MAT-01: stable_id non-empty slug
    if not record.stable_id.strip():
        _err("stable_id", "V-MAT-01", "stable_id must be a non-empty string")

    # V-MAT-02: designation non-empty
    if not record.designation.strip():
        _err("designation", "V-MAT-02", "designation must be non-empty")

    # V-MAT-03: iso_group declared (UNKNOWN allowed for DRAFT records)
    if record.iso_group is MaterialISOGroup.UNKNOWN and record.status.value == "ACTIVE":
        _err(
            "iso_group",
            "V-MAT-03",
            "ACTIVE records must declare a known ISO group (P/M/K/N/S/H)",
        )

    # V-MAT-04: ISO S must be differentiated into S_TITANIUM or S_NICKEL_HRSA
    if (
        record.iso_group is MaterialISOGroup.S
        and record.iso_subgroup not in _S_REQUIRED_SUBGROUPS
    ):
        _err(
            "iso_subgroup",
            "V-MAT-04",
            "ISO S must use S_TITANIUM or S_NICKEL_HRSA — never leave undifferentiated",
        )

    # V-MAT-05: density not zero (use None for unknown)
    density = record.properties.density_kg_m3
    if density == 0.0:
        _err(
            "properties.density_kg_m3",
            "V-MAT-05",
            "density_kg_m3=0.0 is not allowed — use None for unknown values",
        )

    # V-MAT-06: density plausible when present
    if density is not None and not (_DENSITY_MIN <= density <= _DENSITY_MAX):
        _err(
            "properties.density_kg_m3",
            "V-MAT-06",
            f"density_kg_m3={density} outside plausible range "
            f"[{_DENSITY_MIN}, {_DENSITY_MAX}]",
        )

    # V-MAT-07 / V-MAT-08 / V-MAT-09: per-condition checks
    for idx, cond in enumerate(record.conditions):
        prefix = f"conditions[{idx}]"

        if not cond.condition_code.strip():
            _err(
                f"{prefix}.condition_code",
                "V-MAT-07",
                "condition_code must be non-empty",
            )

        for hidx, h in enumerate(cond.hardness):
            hp = f"{prefix}.hardness[{hidx}]"
            if h.value_min <= 0 or h.value_max <= 0:
                _err(hp, "V-MAT-08", "Hardness values must be positive")
            if h.value_min > h.value_max:
                _err(hp, "V-MAT-08", "value_min must not exceed value_max")

        ts = cond.tensile_strength_mpa
        ys = cond.yield_strength_mpa
        if ts is not None and ts > _TENSILE_MAX:
            _err(
                f"{prefix}.tensile_strength_mpa",
                "V-MAT-09",
                f"tensile_strength_mpa={ts} > {_TENSILE_MAX} MPa — likely fabricated",
            )
        if ts is not None and ys is not None and ys > ts:
            _err(
                f"{prefix}.yield_strength_mpa",
                "V-MAT-09",
                f"yield_strength_mpa={ys} > tensile_strength_mpa={ts}",
            )

    # V-MAT-10: cutting reference vc must be positive
    for idx, cut in enumerate(record.cutting_references):
        for attr in ("vc_min_m_min", "vc_max_m_min"):
            val = getattr(cut, attr, None)
            if val is not None and val <= 0:
                _err(
                    f"cutting_references[{idx}].{attr}",
                    "V-MAT-10",
                    f"{attr}={val} must be positive when provided",
                )

    # V-MAT-11: cutting references must be REFERENCE_ONLY
    for idx, cut in enumerate(record.cutting_references):
        if cut.evidence_status.value != "REFERENCE_ONLY":
            _err(
                f"cutting_references[{idx}].evidence_status",
                "V-MAT-11",
                "Cutting references must carry evidence_status=REFERENCE_ONLY",
            )

    return MaterialValidationResult(stable_id=record.stable_id, issues=issues)
