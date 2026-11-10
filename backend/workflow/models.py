"""Level 19 workflow domain models."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .enums import (
    AlternativePlanType,
    AuditEventType,
    EvidenceLabel,
    StageStatus,
    WorkflowMode,
    WorkflowObjective,
    WorkflowStage,
    WorkflowStatus,
)


def _now() -> datetime:
    return datetime.now(UTC)


def _id(prefix: str, seed: str) -> str:
    h = hashlib.sha256(seed.encode()).hexdigest()[:12]
    return f"{prefix}_{h}"


# ---------------------------------------------------------------------------
# WorkflowContext — single shared mutable bag of provenance refs
# ---------------------------------------------------------------------------

@dataclass
class WorkflowContext:
    """Accumulates references and provenance across all stages.

    Stages write their output refs here; downstream stages read from here.
    Never copy disconnected dicts — read from the context directly.
    """
    workflow_id: str
    part_reference: str
    revision: str
    source_file_ref: str | None
    material_ref: str | None
    quantity: int
    stock_ref: str | None
    objective: WorkflowObjective
    units: str = "MM"

    # Accumulated refs (set by stage runners as they complete)
    cad_provenance: dict[str, Any] = field(default_factory=dict)
    geometry_ref: str | None = None
    features_ref: str | None = None
    dfm_ref: str | None = None
    process_ref: str | None = None
    machine_candidates_ref: str | None = None
    tool_candidates_ref: str | None = None
    cutting_data_ref: str | None = None
    cycle_time_ref: str | None = None
    cost_ref: str | None = None
    cam_ref: str | None = None
    toolpath_refs: list[str] = field(default_factory=list)
    verification_ref: str | None = None
    nc_ref: str | None = None
    schedule_ref: str | None = None
    job_assignment_ref: str | None = None
    adaptive_ref: str | None = None
    digital_twin_refs: list[str] = field(default_factory=list)

    # Accumulated lightweight data snapshots used by downstream stages
    # (only set when needed for cross-stage dependencies)
    material_iso_group: str | None = None
    machine_class_library: str | None = None  # library MachineClass value
    machine_class_scheduling: str | None = None  # scheduling MachineClass value
    selected_machine_id: str | None = None
    selected_tool_ids: list[str] = field(default_factory=list)

    def input_hash(self, keys: list[str]) -> str:
        """Deterministic hash of named context fields for stale detection."""
        values = {k: getattr(self, k, None) for k in sorted(keys)}
        return hashlib.sha256(json.dumps(values, sort_keys=True, default=str).encode()).hexdigest()


# ---------------------------------------------------------------------------
# BlockingIssue
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BlockingIssue:
    stage: WorkflowStage
    code: str
    description: str
    required_action: str
    blocking: bool = True


# ---------------------------------------------------------------------------
# KnownUnknown
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class KnownUnknown:
    category: str
    description: str
    stage: WorkflowStage | None = None


# ---------------------------------------------------------------------------
# ReviewItem
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReviewItem:
    category: str  # DFM / CAM / verification / NC / machine_assignment / digital_twin
    description: str
    stage: WorkflowStage
    mandatory: bool = True


# ---------------------------------------------------------------------------
# StageResult — standard result returned by every stage runner
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    stage: WorkflowStage
    status: StageStatus
    input_refs: dict[str, Any] = field(default_factory=dict)
    output_refs: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    blocking_reasons: list[str] = field(default_factory=list)
    known_unknowns: list[KnownUnknown] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)
    started_at: datetime = field(default_factory=_now)
    completed_at: datetime | None = None
    review_required: bool = False
    input_hash: str | None = None
    duration_ms: float | None = None

    def finish(self) -> None:
        self.completed_at = _now()
        if self.started_at:
            self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000


# ---------------------------------------------------------------------------
# AuditEvent
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AuditEvent:
    event_type: AuditEventType
    workflow_id: str
    stage: WorkflowStage | None
    timestamp: datetime
    detail: str = ""


# ---------------------------------------------------------------------------
# ManufacturingPlanSummary value containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EvidenceValue:
    value: Any
    label: EvidenceLabel
    source: str = ""


@dataclass
class AlternativePlan:
    plan_type: AlternativePlanType
    description: str
    objective_score: dict[str, Any] = field(default_factory=dict)
    machine_id: str | None = None
    tool_ids: list[str] = field(default_factory=list)
    estimated_cycle_time_s: float | None = None
    estimated_cost: float | None = None
    evidence: EvidenceLabel = EvidenceLabel.PROPOSED


@dataclass
class ManufacturingPlanSummary:
    """Final aggregated manufacturing plan — built from all stage outputs."""
    plan_id: str
    workflow_id: str
    part: EvidenceValue | None = None
    revision: EvidenceValue | None = None
    material: EvidenceValue | None = None
    quantity: EvidenceValue | None = None
    features: list[EvidenceValue] = field(default_factory=list)
    dfm_summary: EvidenceValue | None = None
    process_route: list[EvidenceValue] = field(default_factory=list)
    machine_candidates: list[EvidenceValue] = field(default_factory=list)
    recommended_machine: EvidenceValue | None = None
    tool_plan: list[EvidenceValue] = field(default_factory=list)
    cutting_data: list[EvidenceValue] = field(default_factory=list)
    cycle_time: EvidenceValue | None = None
    cost_rfq: EvidenceValue | None = None
    setups: list[EvidenceValue] = field(default_factory=list)
    cam_operations: list[EvidenceValue] = field(default_factory=list)
    toolpath_status: EvidenceValue | None = None
    verification_status: EvidenceValue | None = None
    nc_status: EvidenceValue | None = None
    scheduling: EvidenceValue | None = None
    job_assignment: EvidenceValue | None = None
    adaptive_recommendations: list[EvidenceValue] = field(default_factory=list)
    digital_twin_scenarios: list[EvidenceValue] = field(default_factory=list)
    recommended_scenario: EvidenceValue | None = None
    blocking_issues: list[BlockingIssue] = field(default_factory=list)
    known_unknowns: list[KnownUnknown] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    alternative_plans: list[AlternativePlan] = field(default_factory=list)
    created_at: datetime = field(default_factory=_now)


# ---------------------------------------------------------------------------
# ManufacturingWorkflow — top-level aggregate
# ---------------------------------------------------------------------------

@dataclass
class ManufacturingWorkflow:
    workflow_id: str
    part_reference: str
    revision: str
    source_file_ref: str | None
    requested_mode: WorkflowMode
    objective: WorkflowObjective
    status: WorkflowStatus
    current_stage: WorkflowStage | None
    created_at: datetime
    updated_at: datetime
    material_ref: str | None
    quantity: int
    stock_ref: str | None
    stage_results: dict[WorkflowStage, StageResult] = field(default_factory=dict)
    blocking_issues: list[BlockingIssue] = field(default_factory=list)
    known_unknowns: list[KnownUnknown] = field(default_factory=list)
    review_items: list[ReviewItem] = field(default_factory=list)
    audit_log: list[AuditEvent] = field(default_factory=list)
    final_plan_ref: str | None = None
    final_plan: ManufacturingPlanSummary | None = None
    context: WorkflowContext | None = None

    @classmethod
    def create(
        cls,
        part_reference: str,
        revision: str,
        source_file_ref: str | None,
        requested_mode: WorkflowMode,
        objective: WorkflowObjective,
        material_ref: str | None,
        quantity: int,
        stock_ref: str | None,
    ) -> ManufacturingWorkflow:
        now = _now()
        wid = _id("WF", f"{part_reference}{revision}{now.isoformat()}")
        ctx = WorkflowContext(
            workflow_id=wid,
            part_reference=part_reference,
            revision=revision,
            source_file_ref=source_file_ref,
            material_ref=material_ref,
            quantity=quantity,
            stock_ref=stock_ref,
            objective=objective,
        )
        return cls(
            workflow_id=wid,
            part_reference=part_reference,
            revision=revision,
            source_file_ref=source_file_ref,
            requested_mode=requested_mode,
            objective=objective,
            status=WorkflowStatus.CREATED,
            current_stage=None,
            created_at=now,
            updated_at=now,
            material_ref=material_ref,
            quantity=quantity,
            stock_ref=stock_ref,
            context=ctx,
        )

    def record_stage(self, result: StageResult) -> None:
        self.stage_results[result.stage] = result
        self.updated_at = _now()
        if result.blocking_reasons or result.status is StageStatus.BLOCKED:
            for reason in result.blocking_reasons:
                self.blocking_issues.append(
                    BlockingIssue(
                        stage=result.stage,
                        code=f"BLOCKED_{result.stage.name}",
                        description=reason,
                        required_action="Provide required input or correct upstream stage",
                        blocking=True,
                    )
                )
        self.known_unknowns.extend(result.known_unknowns)
        if result.review_required:
            self.review_items.append(
                ReviewItem(
                    category=result.stage.name.split("_")[0].lower(),
                    description=f"Engineering review required for stage {result.stage}",
                    stage=result.stage,
                    mandatory=True,
                )
            )

    def add_audit(
        self, event_type: AuditEventType, stage: WorkflowStage | None = None, detail: str = ""
    ) -> None:
        self.audit_log.append(
            AuditEvent(
                event_type=event_type,
                workflow_id=self.workflow_id,
                stage=stage,
                timestamp=_now(),
                detail=detail,
            )
        )

    def stage_status(self, stage: WorkflowStage) -> StageStatus:
        result = self.stage_results.get(stage)
        return result.status if result else StageStatus.NOT_STARTED
