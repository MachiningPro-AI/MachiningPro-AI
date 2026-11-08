"""Machine Library import pipeline.

Converts flat dict records (from CSV or JSON) into MachineCatalogRecord
instances, validates them, and deduplicates against existing stable_ids.

Safety contract
---------------
MISSING_VALUE_AS_ZERO=NO   — empty cells become None, never 0.
SYNTHETIC_SPECIFICATIONS_ADDED=NO — no values fabricated during import.
PRIVATE_SOURCE_PATH_EXPOSED=NO — source file paths are stripped.
UNLICENSED_PROPRIETARY_MACHINE_DATA_IMPORTED=NO — caller responsibility.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from io import StringIO
from pathlib import Path
from typing import Any

from backend.machine_library.enums import (
    AxisType,
    EvidenceGrade,
    MachineCatalogStatus,
    MachineClass,
)
from backend.machine_library.models import (
    MachineAxisSpecification,
    MachineCapability,
    MachineCatalogRecord,
    MachineEnvelope,
    MachineSourceMetadata,
    MachineSpindleSpecification,
)
from backend.machine_library.validation import (
    MachineCatalogValidationResult,
    validate_machine_catalog_record,
)

__all__ = [
    "ImportPipelineResult",
    "ImportedRecordRow",
    "flat_dict_to_record",
    "parse_csv_machines",
    "parse_json_machines",
    "run_ml_import_pipeline",
]

# ---------------------------------------------------------------------------
# Field coercion maps
# ---------------------------------------------------------------------------

_INT_FIELDS = frozenset({
    "axis_count",
    "simultaneous_axis_count",
    "spindle_max_rpm",
    "spindle_min_rpm",
    "spindle_torque_at_rpm",
    "tool_magazine_capacity",
    "year_introduced",
    "year_discontinued",
})

_FLOAT_FIELDS = frozenset({
    "spindle_power_kw",
    "spindle_torque_nm",
    "travel_x_mm",
    "travel_y_mm",
    "travel_z_mm",
    "table_length_mm",
    "table_width_mm",
    "table_load_kg",
    "max_turning_diameter_mm",
    "max_turning_length_mm",
    "bar_capacity_mm",
    "max_tool_diameter_mm",
    "max_tool_length_mm",
    "atc_chip_to_chip_sec",
    "atc_tool_to_tool_sec",
    "rapid_traverse_mpm",
    "max_cutting_feed_mm_min",
    "coolant_pressure_bar",
    "machine_weight_kg",
    "grinding_wheel_diameter_mm",
    "max_grinding_length_mm",
})

_BOOL_FIELDS = frozenset({
    "turning_capable",
    "milling_capable",
    "drilling_capable",
    "grinding_capable",
    "edm_capable",
    "capable_tapping",
    "capable_boring",
    "capable_threading",
    "capable_reaming",
    "capable_5axis_simultaneous",
    "capable_3plus2",
    "has_subspindle",
    "has_y_axis",
    "has_live_tooling",
    "has_b_axis",
    "has_pallet_changer",
    "has_through_spindle_coolant",
    "mql_support",
    "flood_coolant",
    "chip_conveyor",
})

_LIST_FIELDS = frozenset({"supported_processes", "spindle_interfaces_supported"})

_REQUIRED_FLAT_FIELDS = frozenset({
    "stable_id",
    "manufacturer",
    "model",
    "machine_class",
    "axis_count",
    "source_title",
})


def _coerce(key: str, raw: Any) -> Any:
    """Coerce *raw* to domain type for *key*.  Empty → None (never 0)."""
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if key in _INT_FIELDS:
        try:
            return int(raw)
        except (ValueError, TypeError):
            return None
    if key in _FLOAT_FIELDS:
        try:
            return float(raw)
        except (ValueError, TypeError):
            return None
    if key in _BOOL_FIELDS:
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in ("true", "1", "yes")
    if key in _LIST_FIELDS:
        if isinstance(raw, list):
            return raw
        return [s.strip() for s in str(raw).split(";") if s.strip()]
    return raw


def _normalize_flat(raw: dict) -> dict:
    """Normalize raw flat row dict for all typed fields."""
    out: dict = {}
    for k, v in raw.items():
        out[k] = _coerce(k, v)
    if out.get("supported_processes") is None:
        out["supported_processes"] = []
    if out.get("spindle_interfaces_supported") is None:
        out["spindle_interfaces_supported"] = []
    return out


def flat_dict_to_record(flat: dict) -> MachineCatalogRecord:
    """Assemble a MachineCatalogRecord from a normalized flat dict.

    Maps flat CSV/JSON fields to the structured Pydantic model hierarchy.
    Missing optional fields remain None — never coerced to 0.

    Raises:
        ValueError: when required fields are absent or machine_class is invalid.
    """
    for req in _REQUIRED_FLAT_FIELDS:
        if not flat.get(req):
            raise ValueError(f"required field {req!r} is missing or empty")

    # Resolve machine_class
    mc_raw = str(flat["machine_class"]).strip()
    try:
        machine_class = MachineClass(mc_raw)
    except ValueError as exc:
        raise ValueError(
            f"unknown machine_class {mc_raw!r}; "
            f"valid values: {[mc.value for mc in MachineClass]}"
        ) from exc

    # Resolve catalog_status
    status_raw = str(flat.get("catalog_status") or "ACTIVE").strip()
    try:
        catalog_status = MachineCatalogStatus(status_raw)
    except ValueError:
        catalog_status = MachineCatalogStatus.UNKNOWN

    # Resolve evidence_grade
    grade_raw = str(flat.get("evidence_grade") or "MANUFACTURER_DATASHEET").strip()
    try:
        evidence_grade = EvidenceGrade(grade_raw)
    except ValueError:
        evidence_grade = EvidenceGrade.UNKNOWN

    capability = MachineCapability(
        machine_class=machine_class,
        controlled_axes=int(flat.get("axis_count") or 1),
        simultaneous_axes=flat.get("simultaneous_axis_count"),
        turning_capable=bool(flat.get("turning_capable", False)),
        milling_capable=bool(flat.get("milling_capable", False)),
        drilling_capable=bool(flat.get("drilling_capable", False)),
        grinding_capable=bool(flat.get("grinding_capable", False)),
        edm_capable=bool(flat.get("edm_capable", False)),
        capable_tapping=flat.get("capable_tapping"),
        capable_boring=flat.get("capable_boring"),
        capable_threading=flat.get("capable_threading"),
        capable_reaming=flat.get("capable_reaming"),
        capable_5axis_simultaneous=flat.get("capable_5axis_simultaneous"),
        capable_3plus2=flat.get("capable_3plus2"),
        has_subspindle=bool(flat.get("has_subspindle", False)),
        has_y_axis=bool(flat.get("has_y_axis", False)),
        has_live_tooling=bool(flat.get("has_live_tooling", False)),
        has_b_axis=bool(flat.get("has_b_axis", False)),
        has_pallet_changer=bool(flat.get("has_pallet_changer", False)),
        tool_magazine_capacity=flat.get("tool_magazine_capacity"),
        tool_magazine_type=flat.get("tool_magazine_type"),
        tool_interface=flat.get("tool_interface"),
        max_tool_diameter_mm=flat.get("max_tool_diameter_mm"),
        max_tool_length_mm=flat.get("max_tool_length_mm"),
        atc_chip_to_chip_sec=flat.get("atc_chip_to_chip_sec"),
        atc_tool_to_tool_sec=flat.get("atc_tool_to_tool_sec"),
        max_cutting_feed_mm_min=flat.get("max_cutting_feed_mm_min"),
        rapid_traverse_mpm=flat.get("rapid_traverse_mpm"),
        has_through_spindle_coolant=flat.get("has_through_spindle_coolant"),
        coolant_pressure_bar=flat.get("coolant_pressure_bar"),
        mql_support=flat.get("mql_support"),
        flood_coolant=bool(flat.get("flood_coolant", True)),
        chip_conveyor=flat.get("chip_conveyor"),
        controller_family=flat.get("controller_family"),
        controller_model=flat.get("controller_model"),
        controller_generation=flat.get("controller_generation"),
        nc_dialect=flat.get("nc_dialect"),
        positioning_accuracy_um=flat.get("positioning_accuracy_um"),
        repeatability_um=flat.get("repeatability_um"),
        supported_processes=flat.get("supported_processes") or [],
    )

    spindle = MachineSpindleSpecification(
        min_rpm=flat.get("spindle_min_rpm"),
        max_rpm=flat.get("spindle_max_rpm"),
        power_kw=flat.get("spindle_power_kw"),
        torque_nm=flat.get("spindle_torque_nm"),
        torque_at_rpm=flat.get("spindle_torque_at_rpm"),
        interface=flat.get("spindle_interface"),
        interfaces_supported=flat.get("spindle_interfaces_supported") or [],
    )

    rotary_axes: list[MachineAxisSpecification] = []
    for label in ("A", "B", "C"):
        travel_key = f"rotary_{label.lower()}_deg"
        if flat.get(travel_key) is not None:
            rotary_axes.append(
                MachineAxisSpecification(
                    axis_label=label,
                    axis_type=AxisType.ROTARY,
                    max_angle_deg=flat.get(travel_key),
                )
            )

    envelope = MachineEnvelope(
        travel_x_mm=flat.get("travel_x_mm"),
        travel_y_mm=flat.get("travel_y_mm"),
        travel_z_mm=flat.get("travel_z_mm"),
        rotary_axes=rotary_axes,
        table_length_mm=flat.get("table_length_mm"),
        table_width_mm=flat.get("table_width_mm"),
        table_load_kg=flat.get("table_load_kg"),
        max_workpiece_mass_kg=flat.get("max_workpiece_mass_kg"),
        max_turning_diameter_mm=flat.get("max_turning_diameter_mm"),
        max_turning_length_mm=flat.get("max_turning_length_mm"),
        bar_capacity_mm=flat.get("bar_capacity_mm"),
        grinding_wheel_diameter_mm=flat.get("grinding_wheel_diameter_mm"),
        max_grinding_length_mm=flat.get("max_grinding_length_mm"),
    )

    source = MachineSourceMetadata(
        source_title=str(flat.get("source_title") or ""),
        evidence_grade=evidence_grade,
        source_url=flat.get("source_url"),
        source_note=flat.get("source_note"),
        verified_date=flat.get("verified_date"),
    )

    return MachineCatalogRecord(
        stable_id=str(flat["stable_id"]).strip(),
        manufacturer=str(flat["manufacturer"]).strip(),
        model=str(flat["model"]).strip(),
        family=flat.get("family"),
        capability=capability,
        spindle=spindle,
        envelope=envelope,
        source=source,
        catalog_status=catalog_status,
        year_introduced=flat.get("year_introduced"),
        year_discontinued=flat.get("year_discontinued"),
        country_of_origin=flat.get("country_of_origin"),
        machine_weight_kg=flat.get("machine_weight_kg"),
    )


def parse_csv_machines(csv_text: str) -> list[dict]:
    """Parse flat machine dicts from CSV text."""
    reader = csv.DictReader(StringIO(csv_text))
    return [_normalize_flat(dict(row)) for row in reader]


def parse_json_machines(json_text: str) -> list[dict]:
    """Parse flat machine dicts from JSON array text."""
    data = json.loads(json_text)
    if not isinstance(data, list):
        raise ValueError("JSON import expects a top-level array")
    return [_normalize_flat(item) for item in data]


def parse_csv_file(path: Path) -> list[dict]:
    return parse_csv_machines(path.read_text(encoding="utf-8"))


def parse_json_file(path: Path) -> list[dict]:
    return parse_json_machines(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

@dataclass
class ImportedRecordRow:
    """Per-record outcome from the import pipeline."""

    stable_id: str
    is_duplicate: bool
    parse_error: str | None
    validation: MachineCatalogValidationResult | None
    record: MachineCatalogRecord | None


@dataclass
class ImportPipelineResult:
    """Aggregate result of one import run."""

    total_input: int
    accepted: int
    rejected_validation: int
    rejected_duplicate: int
    rejected_parse: int
    rows: list[ImportedRecordRow] = field(default_factory=list)
    dry_run: bool = True

    @property
    def accepted_records(self) -> list[MachineCatalogRecord]:
        return [
            r.record
            for r in self.rows
            if r.record is not None
            and r.validation is not None
            and r.validation.is_valid
            and not r.is_duplicate
        ]


def run_ml_import_pipeline(
    flat_records: list[dict],
    existing_ids: frozenset[str] | None = None,
    *,
    dry_run: bool = True,
) -> ImportPipelineResult:
    """Validate, deduplicate, and convert flat machine records.

    Args:
        flat_records:  Normalized flat dicts (from CSV or JSON).
        existing_ids:  stable_ids already registered; duplicates skipped.
        dry_run:       When True, returns result without side effects.

    Returns:
        ImportPipelineResult with per-row outcomes and counts.
    """
    if existing_ids is None:
        existing_ids = frozenset()

    rows: list[ImportedRecordRow] = []
    seen_in_batch: set[str] = set()
    accepted = rejected_val = rejected_dup = rejected_parse = 0

    for flat in flat_records:
        normalized = _normalize_flat(flat)
        raw_sid = str(normalized.get("stable_id") or "").strip()

        # Attempt parse
        record: MachineCatalogRecord | None = None
        parse_error: str | None = None
        try:
            record = flat_dict_to_record(normalized)
        except (ValueError, Exception) as exc:
            parse_error = str(exc)

        if parse_error:
            rows.append(ImportedRecordRow(
                stable_id=raw_sid,
                is_duplicate=False,
                parse_error=parse_error,
                validation=None,
                record=None,
            ))
            rejected_parse += 1
            continue

        assert record is not None
        sid = record.stable_id

        # Duplicate check
        is_dup = sid in existing_ids or sid in seen_in_batch
        if not is_dup:
            seen_in_batch.add(sid)

        # Validation
        validation = validate_machine_catalog_record(record)

        rows.append(ImportedRecordRow(
            stable_id=sid,
            is_duplicate=is_dup,
            parse_error=None,
            validation=validation,
            record=record,
        ))

        if is_dup:
            rejected_dup += 1
        elif not validation.is_valid:
            rejected_val += 1
        else:
            accepted += 1

    return ImportPipelineResult(
        total_input=len(flat_records),
        accepted=accepted,
        rejected_validation=rejected_val,
        rejected_duplicate=rejected_dup,
        rejected_parse=rejected_parse,
        rows=rows,
        dry_run=dry_run,
    )
