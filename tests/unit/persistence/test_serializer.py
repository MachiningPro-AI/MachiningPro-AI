"""Tests for workflow serializer — round-trip fidelity and type safety."""
from datetime import UTC, datetime

from backend.persistence.serializer import from_json, to_json
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
    KnownUnknown,
    ManufacturingWorkflow,
    ReviewItem,
    StageResult,
)


def _make_workflow(
    part: str = "PART-001",
    source_ref: str | None = None,
) -> ManufacturingWorkflow:
    return ManufacturingWorkflow.create(
        part_reference=part,
        revision="REV-A",
        source_file_ref=source_ref,
        requested_mode=WorkflowMode.ANALYSIS_ONLY,
        objective=WorkflowObjective.BALANCED,
        material_ref="MAT-304",
        quantity=5,
        stock_ref=None,
    )


class TestSerializerRoundTrip:
    def test_basic_roundtrip(self):
        wf = _make_workflow()
        restored = from_json(to_json(wf))
        assert restored.workflow_id == wf.workflow_id
        assert restored.part_reference == wf.part_reference
        assert restored.revision == wf.revision
        assert restored.quantity == wf.quantity
        assert str(restored.status) == str(wf.status)
        assert str(restored.requested_mode) == str(wf.requested_mode)

    def test_datetime_preserved(self):
        wf = _make_workflow()
        restored = from_json(to_json(wf))
        assert restored.created_at.isoformat() == wf.created_at.isoformat()
        assert restored.updated_at.isoformat() == wf.updated_at.isoformat()

    def test_none_fields_preserved(self):
        wf = _make_workflow(source_ref=None)
        restored = from_json(to_json(wf))
        assert restored.source_file_ref is None
        assert restored.stock_ref is None
        assert restored.current_stage is None
        assert restored.final_plan is None
        assert restored.final_plan_ref is None

    def test_source_file_ref_preserved(self):
        wf = _make_workflow(source_ref="abc123def456abc123def456abc12345")
        restored = from_json(to_json(wf))
        assert restored.source_file_ref == "abc123def456abc123def456abc12345"

    def test_stage_results_roundtrip(self):
        wf = _make_workflow()
        result = StageResult(
            stage=WorkflowStage.CAD_IMPORT,
            status=StageStatus.PASS,
        )
        result.warnings.append("test warning")
        result.provenance["format"] = ".dxf"
        result.finish()
        wf.stage_results[WorkflowStage.CAD_IMPORT] = result

        restored = from_json(to_json(wf))
        r = restored.stage_results[WorkflowStage.CAD_IMPORT]
        assert str(r.status) == "PASS"
        assert r.warnings == ["test warning"]
        assert r.provenance["format"] == ".dxf"
        assert r.duration_ms is not None

    def test_blocking_issues_roundtrip(self):
        wf = _make_workflow()
        wf.blocking_issues.append(BlockingIssue(
            stage=WorkflowStage.DFM,
            code="TEST_BLOCK",
            description="Test blocking issue",
            required_action="Fix it",
        ))
        restored = from_json(to_json(wf))
        assert len(restored.blocking_issues) == 1
        bi = restored.blocking_issues[0]
        assert bi.code == "TEST_BLOCK"
        assert str(bi.stage) == "04_DFM"

    def test_known_unknowns_roundtrip(self):
        wf = _make_workflow()
        wf.known_unknowns.append(KnownUnknown(
            category="material_data",
            description="Material hardness not confirmed",
            stage=WorkflowStage.CUTTING_DATA,
        ))
        restored = from_json(to_json(wf))
        assert len(restored.known_unknowns) == 1
        ku = restored.known_unknowns[0]
        assert ku.category == "material_data"
        assert str(ku.stage) == "08_CUTTING_DATA"

    def test_review_items_roundtrip(self):
        wf = _make_workflow()
        wf.review_items.append(ReviewItem(
            category="cam",
            description="CAM review required",
            stage=WorkflowStage.CAM_PLANNING,
            mandatory=True,
        ))
        restored = from_json(to_json(wf))
        assert len(restored.review_items) == 1
        assert restored.review_items[0].mandatory is True

    def test_audit_log_roundtrip(self):
        wf = _make_workflow()
        wf.audit_log.append(AuditEvent(
            event_type=AuditEventType.WORKFLOW_CREATED,
            workflow_id=wf.workflow_id,
            stage=None,
            timestamp=datetime.now(UTC),
            detail="test",
        ))
        assert len(wf.audit_log) == 1
        restored = from_json(to_json(wf))
        assert len(restored.audit_log) == 1
        assert str(restored.audit_log[0].event_type) == "WORKFLOW_CREATED"

    def test_context_roundtrip(self):
        wf = _make_workflow()
        wf.context.geometry_ref = "GEO_abc123"
        wf.context.selected_tool_ids = ["TOOL-1", "TOOL-2"]
        wf.context.material_iso_group = "P"
        restored = from_json(to_json(wf))
        assert restored.context is not None
        assert restored.context.geometry_ref == "GEO_abc123"
        assert restored.context.selected_tool_ids == ["TOOL-1", "TOOL-2"]
        assert restored.context.material_iso_group == "P"

    def test_all_workflow_statuses(self):
        for status in WorkflowStatus:
            wf = _make_workflow()
            wf.status = status
            restored = from_json(to_json(wf))
            assert restored.status == status

    def test_all_stage_statuses(self):
        wf = _make_workflow()
        for s_status in StageStatus:
            result = StageResult(stage=WorkflowStage.CAD_IMPORT, status=s_status)
            wf.stage_results[WorkflowStage.CAD_IMPORT] = result
            restored = from_json(to_json(wf))
            assert restored.stage_results[WorkflowStage.CAD_IMPORT].status == s_status

    def test_no_pickle_no_eval(self):
        """Confirm serialized form is plain JSON — no pickle or eval markers."""
        wf = _make_workflow()
        payload = to_json(wf)
        assert "__reduce__" not in payload
        assert "pickle" not in payload
        assert "eval(" not in payload
        assert "exec(" not in payload
