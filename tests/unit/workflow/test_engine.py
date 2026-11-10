"""Tests for the WorkflowEngine — orchestration, resume, retry, invalidation."""
import pytest

from backend.workflow.engine import WorkflowEngine
from backend.workflow.enums import (
    AuditEventType,
    StageStatus,
    WorkflowMode,
    WorkflowObjective,
    WorkflowStage,
    WorkflowStatus,
)
from backend.workflow.models import ManufacturingWorkflow


def _make_engine() -> WorkflowEngine:
    return WorkflowEngine()


def _make_wf(
    mode: WorkflowMode = WorkflowMode.ANALYSIS_ONLY,
    material_ref: str | None = None,
    source_file_ref: str | None = None,
) -> ManufacturingWorkflow:
    engine = _make_engine()
    return engine.create_workflow(
        part_reference="TEST_PART",
        revision="REV-TEST",
        source_file_ref=source_file_ref,
        requested_mode=mode,
        objective=WorkflowObjective.BALANCED,
        material_ref=material_ref,
        quantity=1,
        stock_ref=None,
    )


class TestCreateWorkflow:
    def test_create_produces_workflow(self):
        wf = _make_wf()
        assert wf.workflow_id.startswith("WF_")
        assert wf.status == WorkflowStatus.CREATED

    def test_audit_event_on_create(self):
        wf = _make_wf()
        events = [e.event_type for e in wf.audit_log]
        assert AuditEventType.WORKFLOW_CREATED in events

    def test_context_initialized(self):
        wf = _make_wf(material_ref="AL6061_TEST")
        assert wf.context is not None
        assert wf.context.material_ref == "AL6061_TEST"


class TestRunWorkflow:
    def test_analysis_only_runs_to_completion(self):
        """ANALYSIS_ONLY mode: CAD_IMPORT, GEOMETRY, FEATURE_RECOGNITION — all will
        reach PARTIAL (no actual file) but workflow must not crash."""
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        result = engine.run_workflow(wf)
        # Should complete without raising
        assert result.status in (WorkflowStatus.PARTIAL, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED)

    def test_workflow_audit_started(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        events = [e.event_type for e in wf.audit_log]
        assert AuditEventType.WORKFLOW_STARTED in events

    def test_stage_results_populated(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        # At minimum CAD_IMPORT should be attempted
        assert WorkflowStage.CAD_IMPORT in wf.stage_results

    def test_skipped_stages_marked_correctly(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        # COST_RFQ is not in ANALYSIS_ONLY mode
        cost_result = wf.stage_results.get(WorkflowStage.COST_RFQ)
        assert cost_result is None or cost_result.status == StageStatus.SKIPPED_NOT_REQUESTED

    def test_no_fabricated_success(self):
        """Verify that a workflow without a CAD file does not falsely complete all stages."""
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.FULL_MANUFACTURING_PLAN, source_file_ref=None)
        engine.run_workflow(wf)
        # CAD_IMPORT should be BLOCKED (no file provided)
        cad_result = wf.stage_results.get(WorkflowStage.CAD_IMPORT)
        assert cad_result is not None
        assert cad_result.status in (StageStatus.BLOCKED, StageStatus.FAILED, StageStatus.PARTIAL)

    def test_workflow_cancelled_state_persists(self):
        engine = _make_engine()
        wf = _make_wf()
        engine.cancel_workflow(wf)
        result = engine.run_workflow(wf)
        assert result.status == WorkflowStatus.CANCELLED


class TestSyntheticE2E:
    """Synthetic complete E2E test with TEST_ONLY part per MUST 28."""

    def test_full_workflow_with_test_part(self):
        """Full mode workflow should run all stages; plan created; no production approval."""
        engine = _make_engine()
        wf = engine.create_workflow(
            part_reference="TEST_PART_AL6061",
            revision="REV-TEST",
            source_file_ref=None,  # No actual file — stages will PARTIAL/BLOCKED
            requested_mode=WorkflowMode.FULL_MANUFACTURING_PLAN,
            objective=WorkflowObjective.MINIMUM_CYCLE_TIME,
            material_ref="AL6061_TEST",
            quantity=5,
            stock_ref="STOCK_BAR_50MM",
        )
        engine.run_workflow(wf)

        # Safety invariants: never production-approved, dispatched, or machine-started
        assert wf.final_plan is None or not getattr(wf.final_plan, "production_approved", True) is True

        # Even if plan not generated (no file), workflow did not crash
        assert wf.status in (
            WorkflowStatus.PARTIAL,
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
        )

        # Audit trail must exist
        assert len(wf.audit_log) >= 1

    def test_production_approved_never_set(self):
        engine = _make_engine()
        wf = engine.create_workflow(
            part_reference="TEST_P",
            revision="R1",
            source_file_ref=None,
            requested_mode=WorkflowMode.FULL_MANUFACTURING_PLAN,
            objective=WorkflowObjective.BALANCED,
            material_ref="AL6061_TEST",
            quantity=1,
            stock_ref=None,
        )
        engine.run_workflow(wf)
        # No production_approved field on workflow
        assert not hasattr(wf, "production_approved") or not getattr(wf, "production_approved", False)

    def test_dispatched_never_set(self):
        engine = _make_engine()
        wf = engine.create_workflow(
            part_reference="TEST_P",
            revision="R1",
            source_file_ref=None,
            requested_mode=WorkflowMode.FULL_MANUFACTURING_PLAN,
            objective=WorkflowObjective.BALANCED,
            material_ref="AL6061_TEST",
            quantity=1,
            stock_ref=None,
        )
        engine.run_workflow(wf)
        assert not hasattr(wf, "dispatched") or not getattr(wf, "dispatched", False)


class TestResumeWorkflow:
    def test_resume_does_not_crash(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        # Resume should re-run where needed
        engine.resume_workflow(wf)
        assert wf.status in (WorkflowStatus.PARTIAL, WorkflowStatus.COMPLETED, WorkflowStatus.FAILED)

    def test_resume_skips_valid_pass_stages(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)

        # Snapshot stage results before resume
        before = dict(wf.stage_results)
        engine.resume_workflow(wf)
        # Passed stages should stay the same (not re-run)
        for stage, result in before.items():
            if result.status == StageStatus.PASS:
                assert wf.stage_results[stage].started_at == result.started_at


class TestRetryStage:
    def test_retry_does_not_raise(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        # Retry CAD_IMPORT regardless of its status
        engine.retry_stage(wf, WorkflowStage.CAD_IMPORT)

    def test_retry_audit_event(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        engine.retry_stage(wf, WorkflowStage.CAD_IMPORT)
        events = [e.event_type for e in wf.audit_log]
        assert AuditEventType.STAGE_RETRIED in events


class TestInvalidation:
    def test_cad_change_clears_geometry(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.run_workflow(wf)
        # Pre-check: geometry may be in results
        engine.invalidate_stages(wf, "CAD_CHANGE")
        # After CAD change, GEOMETRY should be cleared
        assert WorkflowStage.GEOMETRY not in wf.stage_results

    def test_material_change_clears_cutting_data(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.FULL_MANUFACTURING_PLAN)
        # We just test invalidation logic, not full run
        from backend.workflow.models import StageResult
        wf.stage_results[WorkflowStage.CUTTING_DATA] = StageResult(
            stage=WorkflowStage.CUTTING_DATA,
            status=StageStatus.PASS,
        )
        engine.invalidate_stages(wf, "MATERIAL_CHANGE")
        assert WorkflowStage.CUTTING_DATA not in wf.stage_results

    def test_cost_change_does_not_clear_geometry(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.FULL_MANUFACTURING_PLAN)
        from backend.workflow.models import StageResult
        wf.stage_results[WorkflowStage.GEOMETRY] = StageResult(
            stage=WorkflowStage.GEOMETRY,
            status=StageStatus.PASS,
        )
        engine.invalidate_stages(wf, "COST_INPUT_CHANGE")
        # Geometry should NOT be cleared by cost change
        assert WorkflowStage.GEOMETRY in wf.stage_results


class TestCancelWorkflow:
    def test_cancel_sets_status(self):
        engine = _make_engine()
        wf = _make_wf()
        engine.cancel_workflow(wf)
        assert wf.status == WorkflowStatus.CANCELLED

    def test_run_after_cancel_no_op(self):
        engine = _make_engine()
        wf = _make_wf(mode=WorkflowMode.ANALYSIS_ONLY)
        engine.cancel_workflow(wf)
        engine.run_workflow(wf)
        assert wf.status == WorkflowStatus.CANCELLED

    def test_cancel_audit_event(self):
        engine = _make_engine()
        wf = _make_wf()
        engine.cancel_workflow(wf)
        events = [e.event_type for e in wf.audit_log]
        assert AuditEventType.WORKFLOW_CANCELLED in events


class TestSafetyConstants:
    def test_engine_no_cnc_write(self):
        engine = WorkflowEngine()
        assert engine.NO_CNC_WRITE is True

    def test_engine_no_auto_dispatch(self):
        engine = WorkflowEngine()
        assert engine.NO_AUTO_DISPATCH is True

    def test_engine_no_auto_approval(self):
        engine = WorkflowEngine()
        assert engine.NO_AUTO_APPROVAL is True

    def test_engine_no_auto_adaptive(self):
        engine = WorkflowEngine()
        assert engine.NO_AUTO_ADAPTIVE_APPLICATION is True
