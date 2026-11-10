"""Tests for Level-19 workflow domain models."""
import pytest

from backend.workflow.enums import (
    AuditEventType,
    StageStatus,
    WorkflowMode,
    WorkflowObjective,
    WorkflowStage,
    WorkflowStatus,
)
from backend.workflow.models import (
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
from backend.workflow.enums import EvidenceLabel


class TestManufacturingWorkflowCreate:
    def test_create_basic(self):
        wf = ManufacturingWorkflow.create(
            part_reference="PART-001",
            revision="REV-A",
            source_file_ref=None,
            requested_mode=WorkflowMode.ANALYSIS_ONLY,
            objective=WorkflowObjective.BALANCED,
            material_ref=None,
            quantity=1,
            stock_ref=None,
        )
        assert wf.workflow_id.startswith("WF_")
        assert wf.part_reference == "PART-001"
        assert wf.revision == "REV-A"
        assert wf.status == WorkflowStatus.CREATED
        assert wf.current_stage is None
        assert wf.context is not None
        assert wf.context.workflow_id == wf.workflow_id

    def test_create_with_material(self):
        wf = ManufacturingWorkflow.create(
            part_reference="PART-002",
            revision="REV-B",
            source_file_ref="/path/to/part.dxf",
            requested_mode=WorkflowMode.FULL_MANUFACTURING_PLAN,
            objective=WorkflowObjective.MINIMUM_COST,
            material_ref="AL6061",
            quantity=10,
            stock_ref="STOCK-BAR-50",
        )
        assert wf.material_ref == "AL6061"
        assert wf.quantity == 10
        assert wf.stock_ref == "STOCK-BAR-50"

    def test_different_ids_per_create(self):
        wf1 = ManufacturingWorkflow.create(
            part_reference="P1", revision="R1", source_file_ref=None,
            requested_mode=WorkflowMode.DFM_ONLY,
            objective=WorkflowObjective.BALANCED,
            material_ref=None, quantity=1, stock_ref=None,
        )
        wf2 = ManufacturingWorkflow.create(
            part_reference="P2", revision="R2", source_file_ref=None,
            requested_mode=WorkflowMode.DFM_ONLY,
            objective=WorkflowObjective.BALANCED,
            material_ref=None, quantity=1, stock_ref=None,
        )
        assert wf1.workflow_id != wf2.workflow_id


class TestRecordStage:
    def _make_wf(self):
        return ManufacturingWorkflow.create(
            part_reference="TEST", revision="R1", source_file_ref=None,
            requested_mode=WorkflowMode.FULL_MANUFACTURING_PLAN,
            objective=WorkflowObjective.BALANCED,
            material_ref=None, quantity=1, stock_ref=None,
        )

    def test_record_pass(self):
        wf = self._make_wf()
        result = StageResult(stage=WorkflowStage.CAD_IMPORT, status=StageStatus.PASS)
        result.finish()
        wf.record_stage(result)
        assert WorkflowStage.CAD_IMPORT in wf.stage_results
        assert wf.stage_results[WorkflowStage.CAD_IMPORT].status == StageStatus.PASS

    def test_record_blocked_adds_blocking_issue(self):
        wf = self._make_wf()
        result = StageResult(
            stage=WorkflowStage.GEOMETRY,
            status=StageStatus.BLOCKED,
            blocking_reasons=["CAD_IMPORT did not PASS"],
        )
        result.finish()
        wf.record_stage(result)
        assert len(wf.blocking_issues) == 1
        assert wf.blocking_issues[0].stage == WorkflowStage.GEOMETRY

    def test_record_review_required_adds_review_item(self):
        wf = self._make_wf()
        result = StageResult(
            stage=WorkflowStage.CAM_PLANNING,
            status=StageStatus.PASS,
            review_required=True,
        )
        result.finish()
        wf.record_stage(result)
        assert len(wf.review_items) == 1

    def test_known_unknowns_propagated(self):
        wf = self._make_wf()
        ku = KnownUnknown(category="material_hardness", description="Hardness unknown")
        result = StageResult(
            stage=WorkflowStage.CUTTING_DATA,
            status=StageStatus.PARTIAL,
            known_unknowns=[ku],
        )
        result.finish()
        wf.record_stage(result)
        assert len(wf.known_unknowns) == 1
        assert wf.known_unknowns[0].category == "material_hardness"


class TestAddAudit:
    def test_audit_event_added(self):
        wf = ManufacturingWorkflow.create(
            part_reference="A", revision="R1", source_file_ref=None,
            requested_mode=WorkflowMode.ANALYSIS_ONLY,
            objective=WorkflowObjective.BALANCED,
            material_ref=None, quantity=1, stock_ref=None,
        )
        wf.add_audit(AuditEventType.WORKFLOW_CREATED)
        wf.add_audit(AuditEventType.STAGE_STARTED, stage=WorkflowStage.CAD_IMPORT, detail="x")
        assert len(wf.audit_log) == 2
        assert wf.audit_log[0].event_type == AuditEventType.WORKFLOW_CREATED
        assert wf.audit_log[1].stage == WorkflowStage.CAD_IMPORT


class TestStageStatus:
    def test_not_started_when_missing(self):
        wf = ManufacturingWorkflow.create(
            part_reference="X", revision="R1", source_file_ref=None,
            requested_mode=WorkflowMode.ANALYSIS_ONLY,
            objective=WorkflowObjective.BALANCED,
            material_ref=None, quantity=1, stock_ref=None,
        )
        assert wf.stage_status(WorkflowStage.CAD_IMPORT) == StageStatus.NOT_STARTED


class TestWorkflowContext:
    def test_input_hash_deterministic(self):
        ctx = WorkflowContext(
            workflow_id="WF_1",
            part_reference="PART",
            revision="R1",
            source_file_ref="/path/file.dxf",
            material_ref="AL6061",
            quantity=5,
            stock_ref=None,
            objective=WorkflowObjective.BALANCED,
        )
        h1 = ctx.input_hash(["source_file_ref", "material_ref"])
        h2 = ctx.input_hash(["source_file_ref", "material_ref"])
        assert h1 == h2

    def test_input_hash_changes_with_input(self):
        ctx = WorkflowContext(
            workflow_id="WF_1",
            part_reference="PART",
            revision="R1",
            source_file_ref="/path/file.dxf",
            material_ref="AL6061",
            quantity=5,
            stock_ref=None,
            objective=WorkflowObjective.BALANCED,
        )
        h1 = ctx.input_hash(["material_ref"])
        ctx.material_ref = "SS316L"
        h2 = ctx.input_hash(["material_ref"])
        assert h1 != h2


class TestEvidenceValue:
    def test_evidence_value_fields(self):
        ev = EvidenceValue(value=42.5, label=EvidenceLabel.CONFIRMED, source="measurement")
        assert ev.value == 42.5
        assert ev.label == EvidenceLabel.CONFIRMED
        assert ev.source == "measurement"


class TestManufacturingPlanSummary:
    def test_create_minimal(self):
        plan = ManufacturingPlanSummary(
            plan_id="PLAN_001",
            workflow_id="WF_001",
        )
        assert plan.plan_id == "PLAN_001"
        assert plan.blocking_issues == []
        assert plan.known_unknowns == []
        assert plan.review_items == []
        # production_approved is on the API layer, not the domain model
        assert not hasattr(plan, "production_approved")
