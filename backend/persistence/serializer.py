"""Workflow serializer — ManufacturingWorkflow ↔ plain JSON dict.

ARBITRARY_OBJECT_DESERIALIZATION=NO — only explicit field reconstruction.
No pickle, no eval, no arbitrary deserialization.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from ..workflow.enums import (
    AlternativePlanType,
    AuditEventType,
    EvidenceLabel,
    StageStatus,
    WorkflowMode,
    WorkflowObjective,
    WorkflowStage,
    WorkflowStatus,
)
from ..workflow.models import (
    AlternativePlan,
    AuditEvent,
    BlockingIssue,
    EvidenceValue,
    KnownUnknown,
    ManufacturingPlanSummary,
    ManufacturingWorkflow,
    ReviewItem,
    StageResult,
    WorkflowContext,
)

# ---------------------------------------------------------------------------
# Serialization (domain → dict → JSON)
# ---------------------------------------------------------------------------

def to_json(wf: ManufacturingWorkflow) -> str:
    return json.dumps(_workflow_to_dict(wf))


def _workflow_to_dict(wf: ManufacturingWorkflow) -> dict[str, Any]:
    return {
        "workflow_id": wf.workflow_id,
        "part_reference": wf.part_reference,
        "revision": wf.revision,
        "source_file_ref": wf.source_file_ref,
        "requested_mode": str(wf.requested_mode),
        "objective": str(wf.objective),
        "status": str(wf.status),
        "current_stage": str(wf.current_stage) if wf.current_stage else None,
        "created_at": wf.created_at.isoformat(),
        "updated_at": wf.updated_at.isoformat(),
        "material_ref": wf.material_ref,
        "quantity": wf.quantity,
        "stock_ref": wf.stock_ref,
        "final_plan_ref": wf.final_plan_ref,
        "stage_results": {
            str(stage): _stage_result_to_dict(result)
            for stage, result in wf.stage_results.items()
        },
        "blocking_issues": [_blocking_issue_to_dict(bi) for bi in wf.blocking_issues],
        "known_unknowns": [_known_unknown_to_dict(ku) for ku in wf.known_unknowns],
        "review_items": [_review_item_to_dict(ri) for ri in wf.review_items],
        "audit_log": [_audit_event_to_dict(ae) for ae in wf.audit_log],
        "final_plan": _plan_to_dict(wf.final_plan) if wf.final_plan else None,
        "context": _context_to_dict(wf.context) if wf.context else None,
    }


def _stage_result_to_dict(r: StageResult) -> dict[str, Any]:
    return {
        "stage": str(r.stage),
        "status": str(r.status),
        "input_refs": r.input_refs,
        "output_refs": r.output_refs,
        "warnings": r.warnings,
        "errors": r.errors,
        "blocking_reasons": r.blocking_reasons,
        "known_unknowns": [_known_unknown_to_dict(ku) for ku in r.known_unknowns],
        "provenance": r.provenance,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        "review_required": r.review_required,
        "input_hash": r.input_hash,
        "duration_ms": r.duration_ms,
    }


def _blocking_issue_to_dict(bi: BlockingIssue) -> dict[str, Any]:
    return {
        "stage": str(bi.stage),
        "code": bi.code,
        "description": bi.description,
        "required_action": bi.required_action,
        "blocking": bi.blocking,
    }


def _known_unknown_to_dict(ku: KnownUnknown) -> dict[str, Any]:
    return {
        "category": ku.category,
        "description": ku.description,
        "stage": str(ku.stage) if ku.stage else None,
    }


def _review_item_to_dict(ri: ReviewItem) -> dict[str, Any]:
    return {
        "category": ri.category,
        "description": ri.description,
        "stage": str(ri.stage),
        "mandatory": ri.mandatory,
    }


def _audit_event_to_dict(ae: AuditEvent) -> dict[str, Any]:
    return {
        "event_type": str(ae.event_type),
        "workflow_id": ae.workflow_id,
        "stage": str(ae.stage) if ae.stage else None,
        "timestamp": ae.timestamp.isoformat(),
        "detail": ae.detail,
    }


def _evidence_value_to_dict(ev: EvidenceValue) -> dict[str, Any]:
    return {"value": ev.value, "label": str(ev.label), "source": ev.source}


def _alternative_plan_to_dict(ap: AlternativePlan) -> dict[str, Any]:
    return {
        "plan_type": str(ap.plan_type),
        "description": ap.description,
        "objective_score": ap.objective_score,
        "machine_id": ap.machine_id,
        "tool_ids": ap.tool_ids,
        "estimated_cycle_time_s": ap.estimated_cycle_time_s,
        "estimated_cost": ap.estimated_cost,
        "evidence": str(ap.evidence),
    }


def _plan_to_dict(p: ManufacturingPlanSummary) -> dict[str, Any]:
    _ev = lambda v: _evidence_value_to_dict(v) if v else None  # noqa: E731
    _ev_list = lambda lst: [_evidence_value_to_dict(v) for v in lst]  # noqa: E731
    return {
        "plan_id": p.plan_id,
        "workflow_id": p.workflow_id,
        "part": _ev(p.part),
        "revision": _ev(p.revision),
        "material": _ev(p.material),
        "quantity": _ev(p.quantity),
        "features": _ev_list(p.features),
        "dfm_summary": _ev(p.dfm_summary),
        "process_route": _ev_list(p.process_route),
        "machine_candidates": _ev_list(p.machine_candidates),
        "recommended_machine": _ev(p.recommended_machine),
        "tool_plan": _ev_list(p.tool_plan),
        "cutting_data": _ev_list(p.cutting_data),
        "cycle_time": _ev(p.cycle_time),
        "cost_rfq": _ev(p.cost_rfq),
        "setups": _ev_list(p.setups),
        "cam_operations": _ev_list(p.cam_operations),
        "toolpath_status": _ev(p.toolpath_status),
        "verification_status": _ev(p.verification_status),
        "nc_status": _ev(p.nc_status),
        "scheduling": _ev(p.scheduling),
        "job_assignment": _ev(p.job_assignment),
        "adaptive_recommendations": _ev_list(p.adaptive_recommendations),
        "digital_twin_scenarios": _ev_list(p.digital_twin_scenarios),
        "recommended_scenario": _ev(p.recommended_scenario),
        "blocking_issues": [_blocking_issue_to_dict(bi) for bi in p.blocking_issues],
        "known_unknowns": [_known_unknown_to_dict(ku) for ku in p.known_unknowns],
        "review_items": [_review_item_to_dict(ri) for ri in p.review_items],
        "alternative_plans": [_alternative_plan_to_dict(ap) for ap in p.alternative_plans],
        "created_at": p.created_at.isoformat(),
    }


def _context_to_dict(ctx: WorkflowContext) -> dict[str, Any]:
    return {
        "workflow_id": ctx.workflow_id,
        "part_reference": ctx.part_reference,
        "revision": ctx.revision,
        "source_file_ref": ctx.source_file_ref,
        "material_ref": ctx.material_ref,
        "quantity": ctx.quantity,
        "stock_ref": ctx.stock_ref,
        "objective": str(ctx.objective),
        "units": ctx.units,
        "cad_provenance": ctx.cad_provenance,
        "geometry_ref": ctx.geometry_ref,
        "features_ref": ctx.features_ref,
        "dfm_ref": ctx.dfm_ref,
        "process_ref": ctx.process_ref,
        "machine_candidates_ref": ctx.machine_candidates_ref,
        "tool_candidates_ref": ctx.tool_candidates_ref,
        "cutting_data_ref": ctx.cutting_data_ref,
        "cycle_time_ref": ctx.cycle_time_ref,
        "cost_ref": ctx.cost_ref,
        "cam_ref": ctx.cam_ref,
        "toolpath_refs": ctx.toolpath_refs,
        "verification_ref": ctx.verification_ref,
        "nc_ref": ctx.nc_ref,
        "schedule_ref": ctx.schedule_ref,
        "job_assignment_ref": ctx.job_assignment_ref,
        "adaptive_ref": ctx.adaptive_ref,
        "digital_twin_refs": ctx.digital_twin_refs,
        "material_iso_group": ctx.material_iso_group,
        "machine_class_library": ctx.machine_class_library,
        "machine_class_scheduling": ctx.machine_class_scheduling,
        "selected_machine_id": ctx.selected_machine_id,
        "selected_tool_ids": ctx.selected_tool_ids,
    }


# ---------------------------------------------------------------------------
# Deserialization (JSON → dict → domain)
# ---------------------------------------------------------------------------

def from_json(s: str) -> ManufacturingWorkflow:
    d = json.loads(s)
    return _workflow_from_dict(d)


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


def _dt_req(s: str) -> datetime:
    return datetime.fromisoformat(s)


def _workflow_from_dict(d: dict[str, Any]) -> ManufacturingWorkflow:
    stage_results = {}
    for stage_str, result_d in d.get("stage_results", {}).items():
        stage = WorkflowStage(stage_str)
        stage_results[stage] = _stage_result_from_dict(result_d)

    return ManufacturingWorkflow(
        workflow_id=d["workflow_id"],
        part_reference=d["part_reference"],
        revision=d["revision"],
        source_file_ref=d.get("source_file_ref"),
        requested_mode=WorkflowMode(d["requested_mode"]),
        objective=WorkflowObjective(d["objective"]),
        status=WorkflowStatus(d["status"]),
        current_stage=WorkflowStage(d["current_stage"]) if d.get("current_stage") else None,
        created_at=_dt_req(d["created_at"]),
        updated_at=_dt_req(d["updated_at"]),
        material_ref=d.get("material_ref"),
        quantity=d.get("quantity", 1),
        stock_ref=d.get("stock_ref"),
        final_plan_ref=d.get("final_plan_ref"),
        stage_results=stage_results,
        blocking_issues=[_blocking_issue_from_dict(bi) for bi in d.get("blocking_issues", [])],
        known_unknowns=[_known_unknown_from_dict(ku) for ku in d.get("known_unknowns", [])],
        review_items=[_review_item_from_dict(ri) for ri in d.get("review_items", [])],
        audit_log=[_audit_event_from_dict(ae) for ae in d.get("audit_log", [])],
        final_plan=_plan_from_dict(d["final_plan"]) if d.get("final_plan") else None,
        context=_context_from_dict(d["context"]) if d.get("context") else None,
    )


def _stage_result_from_dict(d: dict[str, Any]) -> StageResult:
    r = StageResult(stage=WorkflowStage(d["stage"]), status=StageStatus(d["status"]))
    r.input_refs = d.get("input_refs", {})
    r.output_refs = d.get("output_refs", {})
    r.warnings = d.get("warnings", [])
    r.errors = d.get("errors", [])
    r.blocking_reasons = d.get("blocking_reasons", [])
    r.known_unknowns = [_known_unknown_from_dict(ku) for ku in d.get("known_unknowns", [])]
    r.provenance = d.get("provenance", {})
    r.started_at = _dt_req(d["started_at"])
    r.completed_at = _dt(d.get("completed_at"))
    r.review_required = d.get("review_required", False)
    r.input_hash = d.get("input_hash")
    r.duration_ms = d.get("duration_ms")
    return r


def _blocking_issue_from_dict(d: dict[str, Any]) -> BlockingIssue:
    return BlockingIssue(
        stage=WorkflowStage(d["stage"]),
        code=d["code"],
        description=d["description"],
        required_action=d["required_action"],
        blocking=d.get("blocking", True),
    )


def _known_unknown_from_dict(d: dict[str, Any]) -> KnownUnknown:
    return KnownUnknown(
        category=d["category"],
        description=d["description"],
        stage=WorkflowStage(d["stage"]) if d.get("stage") else None,
    )


def _review_item_from_dict(d: dict[str, Any]) -> ReviewItem:
    return ReviewItem(
        category=d["category"],
        description=d["description"],
        stage=WorkflowStage(d["stage"]),
        mandatory=d.get("mandatory", True),
    )


def _audit_event_from_dict(d: dict[str, Any]) -> AuditEvent:
    return AuditEvent(
        event_type=AuditEventType(d["event_type"]),
        workflow_id=d["workflow_id"],
        stage=WorkflowStage(d["stage"]) if d.get("stage") else None,
        timestamp=_dt_req(d["timestamp"]),
        detail=d.get("detail", ""),
    )


def _evidence_value_from_dict(d: dict[str, Any] | None) -> EvidenceValue | None:
    if d is None:
        return None
    return EvidenceValue(
        value=d["value"], label=EvidenceLabel(d["label"]), source=d.get("source", "")
    )


def _alternative_plan_from_dict(d: dict[str, Any]) -> AlternativePlan:
    return AlternativePlan(
        plan_type=AlternativePlanType(d["plan_type"]),
        description=d["description"],
        objective_score=d.get("objective_score", {}),
        machine_id=d.get("machine_id"),
        tool_ids=d.get("tool_ids", []),
        estimated_cycle_time_s=d.get("estimated_cycle_time_s"),
        estimated_cost=d.get("estimated_cost"),
        evidence=EvidenceLabel(d.get("evidence", "PROPOSED")),
    )


def _plan_from_dict(d: dict[str, Any]) -> ManufacturingPlanSummary:
    _ev = lambda v: _evidence_value_from_dict(v) if v else None  # noqa: E731
    _ev_list = lambda lst: [_evidence_value_from_dict(v) for v in (lst or [])]  # noqa: E731
    return ManufacturingPlanSummary(
        plan_id=d["plan_id"],
        workflow_id=d["workflow_id"],
        part=_ev(d.get("part")),
        revision=_ev(d.get("revision")),
        material=_ev(d.get("material")),
        quantity=_ev(d.get("quantity")),
        features=_ev_list(d.get("features", [])),
        dfm_summary=_ev(d.get("dfm_summary")),
        process_route=_ev_list(d.get("process_route", [])),
        machine_candidates=_ev_list(d.get("machine_candidates", [])),
        recommended_machine=_ev(d.get("recommended_machine")),
        tool_plan=_ev_list(d.get("tool_plan", [])),
        cutting_data=_ev_list(d.get("cutting_data", [])),
        cycle_time=_ev(d.get("cycle_time")),
        cost_rfq=_ev(d.get("cost_rfq")),
        setups=_ev_list(d.get("setups", [])),
        cam_operations=_ev_list(d.get("cam_operations", [])),
        toolpath_status=_ev(d.get("toolpath_status")),
        verification_status=_ev(d.get("verification_status")),
        nc_status=_ev(d.get("nc_status")),
        scheduling=_ev(d.get("scheduling")),
        job_assignment=_ev(d.get("job_assignment")),
        adaptive_recommendations=_ev_list(d.get("adaptive_recommendations", [])),
        digital_twin_scenarios=_ev_list(d.get("digital_twin_scenarios", [])),
        recommended_scenario=_ev(d.get("recommended_scenario")),
        blocking_issues=[_blocking_issue_from_dict(bi) for bi in d.get("blocking_issues", [])],
        known_unknowns=[_known_unknown_from_dict(ku) for ku in d.get("known_unknowns", [])],
        review_items=[_review_item_from_dict(ri) for ri in d.get("review_items", [])],
        alternative_plans=[
            _alternative_plan_from_dict(ap) for ap in d.get("alternative_plans", [])
        ],
        created_at=_dt_req(d["created_at"]),
    )


def _context_from_dict(d: dict[str, Any]) -> WorkflowContext:
    return WorkflowContext(
        workflow_id=d["workflow_id"],
        part_reference=d["part_reference"],
        revision=d["revision"],
        source_file_ref=d.get("source_file_ref"),
        material_ref=d.get("material_ref"),
        quantity=d.get("quantity", 1),
        stock_ref=d.get("stock_ref"),
        objective=WorkflowObjective(d["objective"]),
        units=d.get("units", "MM"),
        cad_provenance=d.get("cad_provenance", {}),
        geometry_ref=d.get("geometry_ref"),
        features_ref=d.get("features_ref"),
        dfm_ref=d.get("dfm_ref"),
        process_ref=d.get("process_ref"),
        machine_candidates_ref=d.get("machine_candidates_ref"),
        tool_candidates_ref=d.get("tool_candidates_ref"),
        cutting_data_ref=d.get("cutting_data_ref"),
        cycle_time_ref=d.get("cycle_time_ref"),
        cost_ref=d.get("cost_ref"),
        cam_ref=d.get("cam_ref"),
        toolpath_refs=d.get("toolpath_refs", []),
        verification_ref=d.get("verification_ref"),
        nc_ref=d.get("nc_ref"),
        schedule_ref=d.get("schedule_ref"),
        job_assignment_ref=d.get("job_assignment_ref"),
        adaptive_ref=d.get("adaptive_ref"),
        digital_twin_refs=d.get("digital_twin_refs", []),
        material_iso_group=d.get("material_iso_group"),
        machine_class_library=d.get("machine_class_library"),
        machine_class_scheduling=d.get("machine_class_scheduling"),
        selected_machine_id=d.get("selected_machine_id"),
        selected_tool_ids=d.get("selected_tool_ids", []),
    )
