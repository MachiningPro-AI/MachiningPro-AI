"""ManufacturingPlan serializer — plan ↔ JSON dict.

ARBITRARY_OBJECT_DESERIALIZATION=NO
PERSISTENCE_STATUS_PROMOTION=NO  — statuses are restored exactly as stored
AUTO_CONFIRM_ON_RELOAD=NO
AUTO_APPROVE_ON_RELOAD=NO
"""
from __future__ import annotations

import json
from dataclasses import fields as dc_fields
from dataclasses import is_dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from .characteristic import (
    CharacteristicCriticality,
    CharacteristicReviewStatus,
    CharacteristicType,
    ManufacturingCharacteristic,
)
from .control_plan import ControlPlan, ControlPlanRow, ControlPlanStatus, ReactionPlan
from .inspection_library import InspectionMethod
from .inspection_plan import (
    FAIStatus,
    FinalInspectionPlan,
    FirstArticleInspection,
    InspectionFrequency,
    InspectionFrequencySpec,
    InspectionPlanRow,
    InspectionStage,
)
from .models import (
    ChangeDriver,
    CompletenessStatus,
    ManufacturingOperation,
    ManufacturingPlan,
    ManufacturingPlanMachine,
    ManufacturingPlanParameter,
    ManufacturingPlanStatus,
    ManufacturingPlanTool,
    ManufacturingSetup,
    OpenItem,
    OpenItemCategory,
    OpenItemSeverity,
    OpenItemStatus,
    PFMEAHook,
    PlanCompleteness,
    PlanRevisionEntry,
    ProcessFlow,
    ProcessFlowNode,
    ReleaseGateStatus,
)

_SCHEMA_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


def _ser(val: Any) -> Any:
    """Recursively convert a value to a JSON-safe primitive."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, int | float | str):
        return val
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, Enum):
        return val.value
    if isinstance(val, PFMEAHook):
        return val.to_dict()
    if isinstance(val, dict):
        return {str(k): _ser(v) for k, v in val.items()}
    if isinstance(val, list | tuple):
        return [_ser(item) for item in val]
    if is_dataclass(val):
        return {f.name: _ser(getattr(val, f.name)) for f in dc_fields(val)}
    # Unknown / Any typed — attempt best-effort
    try:
        json.dumps(val)
        return val
    except (TypeError, ValueError):
        return None


def plan_to_json(plan: ManufacturingPlan) -> str:
    d = _ser(plan)
    d["__schema_version__"] = _SCHEMA_VERSION
    return json.dumps(d, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Deserialisation helpers
# ---------------------------------------------------------------------------


def _dt(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str):
        return datetime.fromisoformat(raw)
    return datetime.utcnow()


def _str_opt(d: dict, key: str, default: str | None = None) -> str | None:
    v = d.get(key)
    return str(v) if v is not None else default


def _list(d: dict, key: str) -> list:
    return d.get(key) or []


def _float_opt(d: dict, key: str) -> float | None:
    v = d.get(key)
    return float(v) if v is not None else None


# --- Leaf types -----------------------------------------------------------


def _load_freq_spec(d: dict | None) -> InspectionFrequencySpec:
    if not d:
        return InspectionFrequencySpec(frequency=InspectionFrequency.UNKNOWN)
    return InspectionFrequencySpec(
        frequency=InspectionFrequency(d.get("frequency", "UNKNOWN")),
        sample_size=d.get("sample_size"),
        batch_size=d.get("batch_size"),
        notes=d.get("notes", ""),
    )


def _load_characteristic(d: dict) -> ManufacturingCharacteristic:
    return ManufacturingCharacteristic(
        characteristic_id=d["characteristic_id"],
        source_requirement_id=_str_opt(d, "source_requirement_id"),
        feature_id=_str_opt(d, "feature_id"),
        char_type=CharacteristicType(d.get("char_type", "SPECIAL_NOTE")),
        label=d.get("label", ""),
        nominal_value=_float_opt(d, "nominal_value"),
        upper_limit=_float_opt(d, "upper_limit"),
        lower_limit=_float_opt(d, "lower_limit"),
        unit=_str_opt(d, "unit"),
        specification=_str_opt(d, "specification"),
        gdt_characteristic=_str_opt(d, "gdt_characteristic"),
        criticality=CharacteristicCriticality(d.get("criticality", "UNKNOWN")),
        source_confidence=d.get("source_confidence", "EXTRACTED"),
        review_status=CharacteristicReviewStatus(d.get("review_status", "PENDING")),
        notes=d.get("notes", ""),
    )


def _load_inspection_plan_row(d: dict) -> InspectionPlanRow:
    return InspectionPlanRow(
        row_id=d["row_id"],
        char_id=d["char_id"],
        char_label=d.get("char_label", ""),
        char_type=CharacteristicType(d.get("char_type", "SPECIAL_NOTE")),
        criticality=CharacteristicCriticality(d.get("criticality", "UNKNOWN")),
        feature_ref=_str_opt(d, "feature_ref"),
        op_id=_str_opt(d, "op_id"),
        inspection_op_id=_str_opt(d, "inspection_op_id"),
        stage=InspectionStage(d.get("stage", "FINAL")),
        method=InspectionMethod(d.get("method", "UNKNOWN")),
        gage_suggestion=_str_opt(d, "gage_suggestion"),
        frequency=_load_freq_spec(d.get("frequency")),
        acceptance_criterion=_str_opt(d, "acceptance_criterion"),
        source=d.get("source", "LITERATURE_REFERENCE"),
        confidence=d.get("confidence", "LITERATURE_REFERENCE"),
        status=d.get("status", "COVERED"),
    )


def _load_fai(d: dict | None) -> FirstArticleInspection | None:
    if not d:
        return None
    return FirstArticleInspection(
        fai_id=d["fai_id"],
        plan_id=d["plan_id"],
        drawing_number=_str_opt(d, "drawing_number"),
        revision=_str_opt(d, "revision"),
        char_ids_to_inspect=_list(d, "char_ids_to_inspect"),
        scope_note=d.get("scope_note", "All characteristics from drawing"),
        status=FAIStatus(d.get("status", "REQUIRED")),
        engineer_note=d.get("engineer_note", ""),
    )


def _load_final_inspection_plan(d: dict | None) -> FinalInspectionPlan | None:
    if not d:
        return None
    plan = FinalInspectionPlan(
        plan_id=d["plan_id"],
        manufacturing_plan_id=d.get("manufacturing_plan_id", ""),
        rows=[_load_inspection_plan_row(r) for r in _list(d, "rows")],
        coverage_rate=float(d.get("coverage_rate", 0.0)),
        uninspected_chars=_list(d, "uninspected_chars"),
        disclaimer=d.get("disclaimer", "REFERENCE_ONLY"),
    )
    return plan


def _load_control_plan_row(d: dict) -> ControlPlanRow:
    return ControlPlanRow(
        row_id=d["row_id"],
        operation_no=d.get("operation_no", ""),
        operation_name=d.get("operation_name", ""),
        char_id=d["char_id"],
        char_label=d.get("char_label", ""),
        char_type=CharacteristicType(d.get("char_type", "SPECIAL_NOTE")),
        criticality=CharacteristicCriticality(d.get("criticality", "UNKNOWN")),
        specification=_str_opt(d, "specification"),
        method=InspectionMethod(d.get("method", "UNKNOWN")),
        gage_suggestion=_str_opt(d, "gage_suggestion"),
        stage=InspectionStage(d.get("stage", "FINAL")),
        frequency=_load_freq_spec(d.get("frequency")),
        reaction_plan=ReactionPlan(d.get("reaction_plan", "UNKNOWN")),
        responsibility=_str_opt(d, "responsibility"),
        record_reference=_str_opt(d, "record_reference"),
        notes=d.get("notes", ""),
    )


def _load_control_plan(d: dict | None) -> ControlPlan | None:
    if not d:
        return None
    return ControlPlan(
        plan_id=d["plan_id"],
        manufacturing_plan_id=d.get("manufacturing_plan_id", ""),
        drawing_number=_str_opt(d, "drawing_number"),
        revision=_str_opt(d, "revision"),
        rows=[_load_control_plan_row(r) for r in _list(d, "rows")],
        status=ControlPlanStatus(d.get("status", "DRAFT")),
        disclaimer=d.get("disclaimer", "REFERENCE_ONLY"),
    )


def _load_setup(d: dict) -> ManufacturingSetup:
    return ManufacturingSetup(
        setup_id=d["setup_id"],
        setup_number=int(d.get("setup_number", 0)),
        label=d.get("label", ""),
        machine_id=_str_opt(d, "machine_id"),
        machine_label=_str_opt(d, "machine_label"),
        orientation_note=d.get("orientation_note", ""),
        datum_references=tuple(d.get("datum_references") or []),
        fixturing_note=d.get("fixturing_note", ""),
        zero_reference=d.get("zero_reference", ""),
        tool_ids=tuple(d.get("tool_ids") or []),
        holder_ids=tuple(d.get("holder_ids") or []),
        operation_ids=tuple(d.get("operation_ids") or []),
        inspection_char_ids=tuple(d.get("inspection_char_ids") or []),
        notes=d.get("notes", ""),
        REFERENCE_ONLY=bool(d.get("REFERENCE_ONLY", True)),
    )


def _load_operation(d: dict) -> ManufacturingOperation:
    return ManufacturingOperation(
        op_id=d["op_id"],
        op_number=int(d.get("op_number", 0)),
        setup_id=d["setup_id"],
        feature_id=_str_opt(d, "feature_id"),
        operation_type=d.get("operation_type", "UNKNOWN"),
        machine_id=_str_opt(d, "machine_id"),
        machine_label=_str_opt(d, "machine_label"),
        tool_id=_str_opt(d, "tool_id"),
        holder_id=_str_opt(d, "holder_id"),
        cutting_speed_m_min=_float_opt(d, "cutting_speed_m_min"),
        feed_rate_mm_min=_float_opt(d, "feed_rate_mm_min"),
        rpm=_float_opt(d, "rpm"),
        ap_mm=_float_opt(d, "ap_mm"),
        ae_mm=_float_opt(d, "ae_mm"),
        coolant_note=_str_opt(d, "coolant_note"),
        target_tolerance=_str_opt(d, "target_tolerance"),
        surface_finish=_str_opt(d, "surface_finish"),
        inspection_note=_str_opt(d, "inspection_note"),
        cycle_time_context=d.get("cycle_time_context"),
        capability_context=d.get("capability_context"),
        surface_capability_context=d.get("surface_capability_context"),
        parameter_source=d.get("parameter_source", "INSUFFICIENT_DATA"),
        notes=d.get("notes", ""),
        REFERENCE_ONLY=bool(d.get("REFERENCE_ONLY", True)),
    )


def _load_tool_entry(d: dict) -> ManufacturingPlanTool:
    return ManufacturingPlanTool(
        entry_id=d["entry_id"],
        tool_id=_str_opt(d, "tool_id"),
        tool_label=d.get("tool_label", ""),
        tool_type=d.get("tool_type", ""),
        holder_id=_str_opt(d, "holder_id"),
        holder_label=_str_opt(d, "holder_label"),
        quantity_required=int(d.get("quantity_required", 1)),
        operation_ids=tuple(d.get("operation_ids") or []),
        notes=d.get("notes", ""),
        REFERENCE_ONLY=bool(d.get("REFERENCE_ONLY", True)),
    )


def _load_machine_entry(d: dict) -> ManufacturingPlanMachine:
    return ManufacturingPlanMachine(
        entry_id=d["entry_id"],
        machine_id=_str_opt(d, "machine_id"),
        machine_label=d.get("machine_label", ""),
        machine_type=d.get("machine_type", ""),
        setup_ids=tuple(d.get("setup_ids") or []),
        operation_ids=tuple(d.get("operation_ids") or []),
        REFERENCE_ONLY=bool(d.get("REFERENCE_ONLY", True)),
    )


def _load_parameter(d: dict) -> ManufacturingPlanParameter:
    return ManufacturingPlanParameter(
        entry_id=d["entry_id"],
        op_id=d["op_id"],
        operation_type=d.get("operation_type", ""),
        material_iso_group=_str_opt(d, "material_iso_group"),
        vc_m_min=_float_opt(d, "vc_m_min"),
        fz_mm=_float_opt(d, "fz_mm"),
        ap_mm=_float_opt(d, "ap_mm"),
        ae_mm=_float_opt(d, "ae_mm"),
        feed_rate_mm_min=_float_opt(d, "feed_rate_mm_min"),
        rpm=_float_opt(d, "rpm"),
        source=d.get("source", "INSUFFICIENT_DATA"),
        confidence=d.get("confidence", "INSUFFICIENT_DATA"),
        notes=d.get("notes", ""),
        REFERENCE_ONLY=bool(d.get("REFERENCE_ONLY", True)),
    )


def _load_process_flow(d: dict | None) -> ProcessFlow | None:
    if not d:
        return None
    nodes = [
        ProcessFlowNode(
            node_id=n["node_id"],
            node_type=n.get("node_type", ""),
            label=n.get("label", ""),
            setup_id=_str_opt(n, "setup_id"),
            op_id=_str_opt(n, "op_id"),
            notes=n.get("notes", ""),
        )
        for n in _list(d, "nodes")
    ]
    edges = [tuple(e) for e in _list(d, "edges")]
    return ProcessFlow(
        flow_id=d["flow_id"],
        nodes=nodes,
        edges=edges,  # type: ignore[arg-type]
        start_node_id=_str_opt(d, "start_node_id"),
        end_node_id=_str_opt(d, "end_node_id"),
    )


def _load_completeness(d: dict | None) -> PlanCompleteness:
    if not d:
        return PlanCompleteness()
    c = PlanCompleteness(
        requirements_coverage=float(d.get("requirements_coverage", 0.0)),
        feature_coverage=float(d.get("feature_coverage", 0.0)),
        operation_coverage=float(d.get("operation_coverage", 0.0)),
        machine_assignment_coverage=float(d.get("machine_assignment_coverage", 0.0)),
        tool_assignment_coverage=float(d.get("tool_assignment_coverage", 0.0)),
        holder_assignment_coverage=float(d.get("holder_assignment_coverage", 0.0)),
        parameter_coverage=float(d.get("parameter_coverage", 0.0)),
        inspection_coverage=float(d.get("inspection_coverage", 0.0)),
        cycle_time_coverage=float(d.get("cycle_time_coverage", 0.0)),
        overall_completeness=float(d.get("overall_completeness", 0.0)),
        completeness_status=CompletenessStatus(
            d.get("completeness_status", "INCOMPLETE")
        ),
    )
    return c


def _load_open_item(d: dict) -> OpenItem:
    return OpenItem(
        item_id=d["item_id"],
        category=OpenItemCategory(d.get("category", "OTHER")),
        severity=OpenItemSeverity(d.get("severity", "ADVISORY")),
        description=d.get("description", ""),
        related_step_id=_str_opt(d, "related_step_id"),
        related_char_id=_str_opt(d, "related_char_id"),
        resolution_hint=d.get("resolution_hint", ""),
        status=OpenItemStatus(d.get("status", "OPEN")),
        notes=d.get("notes", ""),
    )


def _load_revision_entry(d: dict) -> PlanRevisionEntry:
    return PlanRevisionEntry(
        revision_id=d["revision_id"],
        revision_number=int(d.get("revision_number", 0)),
        change_driver=ChangeDriver(d.get("change_driver", "OTHER")),
        previous_plan_id=_str_opt(d, "previous_plan_id"),
        new_plan_id=d["new_plan_id"],
        changed_fields=_list(d, "changed_fields"),
        engineer_note=d.get("engineer_note", ""),
        timestamp=_dt(d.get("timestamp")),
    )


def _load_pfmea_hook(d: dict) -> PFMEAHook:
    return PFMEAHook(
        feature_id=d.get("feature_id", ""),
        op_id=d.get("op_id", ""),
        failure_mode_hint=d.get("failure_mode_hint", ""),
        control=d.get("control", ""),
        severity_hint=d.get("severity_hint", ""),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def plan_from_json(payload: str) -> ManufacturingPlan:
    """Reconstruct a ManufacturingPlan from JSON.

    PERSISTENCE_STATUS_PROMOTION=NO — statuses restored exactly as stored.
    AUTO_CONFIRM_ON_RELOAD=NO
    AUTO_APPROVE_ON_RELOAD=NO
    """
    d = json.loads(payload)
    return ManufacturingPlan(
        plan_id=d["plan_id"],
        source_id=d.get("source_id", ""),
        drawing_number=_str_opt(d, "drawing_number"),
        revision=_str_opt(d, "revision"),
        part_id=_str_opt(d, "part_id"),
        status=ManufacturingPlanStatus(d.get("status", "DRAFT")),
        characteristics=[_load_characteristic(c) for c in _list(d, "characteristics")],
        setups=[_load_setup(s) for s in _list(d, "setups")],
        operations=[_load_operation(o) for o in _list(d, "operations")],
        tool_list=[_load_tool_entry(t) for t in _list(d, "tool_list")],
        machine_list=[_load_machine_entry(m) for m in _list(d, "machine_list")],
        parameter_table=[_load_parameter(p) for p in _list(d, "parameter_table")],
        inspection_plan=_load_final_inspection_plan(d.get("inspection_plan")),
        control_plan=_load_control_plan(d.get("control_plan")),
        process_flow=_load_process_flow(d.get("process_flow")),
        completeness=_load_completeness(d.get("completeness")),
        open_items=[_load_open_item(o) for o in _list(d, "open_items")],
        release_gate=ReleaseGateStatus(d.get("release_gate", "INCOMPLETE")),
        pfmea_hooks=[_load_pfmea_hook(h) for h in _list(d, "pfmea_hooks")],
        traceability_fingerprint=_str_opt(d, "traceability_fingerprint"),
        drawing_fingerprint=_str_opt(d, "drawing_fingerprint"),
        requirements_fingerprint=_str_opt(d, "requirements_fingerprint"),
        route_fingerprint=_str_opt(d, "route_fingerprint"),
        calibration_profile_ids=_list(d, "calibration_profile_ids"),
        generation_warnings=_list(d, "generation_warnings"),
        revision_history=[_load_revision_entry(r) for r in _list(d, "revision_history")],
        created_at=_dt(d.get("created_at")),
        updated_at=_dt(d.get("updated_at")),
        disclaimer=d.get(
            "disclaimer",
            "REFERENCE_ONLY — advisory manufacturing plan; engineer review required; "
            "AUTO_GENERATED_PLAN_MARKED_APPROVED=NO",
        ),
        AUTO_GENERATED_PLAN_MARKED_APPROVED=bool(
            d.get("AUTO_GENERATED_PLAN_MARKED_APPROVED", False)
        ),
    )
