"""Level-18 Digital Twin — versioning and stale detection.

Deterministic reproducibility: same input + same evaluator version = same result.
Stale detection marks scenarios that need re-simulation when inputs change.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime

from .enums import StaleReason
from .models import ManufacturingTwinScenario, StalenessCheck

EVALUATOR_VERSION = "18.0.0"


def _stable_hash(obj: dict) -> str:
    raw = json.dumps(obj, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_scenario_hash(scenario: ManufacturingTwinScenario) -> str:
    """Deterministic content hash of a scenario (excludes audit/timestamps)."""
    payload = {
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "machine_ref": scenario.machine_ref,
        "tool_refs": scenario.tool_refs,
        "cutting_data": scenario.cutting_data,
        "quantity": scenario.quantity,
        "batch_size": scenario.batch_size,
        "baseline_ref": scenario.baseline_ref,
        "schedule_ref": scenario.schedule_ref,
    }
    return _stable_hash(payload)


def compute_input_snapshot_hash(
    scenario: ManufacturingTwinScenario,
    machine_catalog_version: str | None = None,
    tool_catalog_version: str | None = None,
    material_catalog_version: str | None = None,
) -> str:
    """Hash of scenario content + all external data versions used."""
    payload = {
        "scenario_hash": compute_scenario_hash(scenario),
        "machine_catalog_version": machine_catalog_version,
        "tool_catalog_version": tool_catalog_version,
        "material_catalog_version": material_catalog_version,
        "evaluator_version": EVALUATOR_VERSION,
    }
    return _stable_hash(payload)


def check_staleness(
    scenario: ManufacturingTwinScenario,
    current_input_snapshot_hash: str,
    recorded_input_snapshot_hash: str | None,
    recorded_evaluator_version: str | None,
    machine_catalog_updated: bool = False,
    tool_catalog_updated: bool = False,
    material_catalog_updated: bool = False,
    baseline_changed: bool = False,
    cutting_data_changed: bool = False,
    schedule_changed: bool = False,
    machine_capability_changed: bool = False,
    tool_geometry_changed: bool = False,
    cost_model_changed: bool = False,
) -> StalenessCheck:
    """Determine whether a scenario needs re-simulation."""
    stale_reasons: list[StaleReason] = []
    is_stale = False

    if recorded_input_snapshot_hash is None:
        stale_reasons.append(StaleReason.NEVER_SIMULATED)
        is_stale = True

    elif current_input_snapshot_hash != recorded_input_snapshot_hash:
        is_stale = True

        if baseline_changed:
            stale_reasons.append(StaleReason.BASELINE_CHANGED)
        if machine_catalog_updated:
            stale_reasons.append(StaleReason.MACHINE_CATALOG_UPDATED)
        if tool_catalog_updated:
            stale_reasons.append(StaleReason.TOOL_CATALOG_UPDATED)
        if material_catalog_updated:
            stale_reasons.append(StaleReason.MATERIAL_CATALOG_UPDATED)
        if cutting_data_changed:
            stale_reasons.append(StaleReason.CUTTING_DATA_CHANGED)
        if schedule_changed:
            stale_reasons.append(StaleReason.SCHEDULE_CHANGED)
        if machine_capability_changed:
            stale_reasons.append(StaleReason.MACHINE_CAPABILITY_CHANGED)
        if tool_geometry_changed:
            stale_reasons.append(StaleReason.TOOL_GEOMETRY_CHANGED)
        if cost_model_changed:
            stale_reasons.append(StaleReason.COST_MODEL_CHANGED)

        if not stale_reasons:
            # Hash changed but no specific reason flagged — evaluator version change
            stale_reasons.append(StaleReason.EVALUATOR_VERSION_CHANGED)

    elif recorded_evaluator_version and recorded_evaluator_version != EVALUATOR_VERSION:
        is_stale = True
        stale_reasons.append(StaleReason.EVALUATOR_VERSION_CHANGED)

    return StalenessCheck(
        scenario_id=scenario.scenario_id,
        is_stale=is_stale,
        stale_reasons=stale_reasons,
        current_input_snapshot_hash=current_input_snapshot_hash,
        recorded_input_snapshot_hash=recorded_input_snapshot_hash,
        evaluator_version=EVALUATOR_VERSION,
        checked_at=datetime.now(UTC),
    )
