"""Level-20 end-to-end restart recovery test (MUST 38, 39).

Simulates:
  1. Create and persist workflow
  2. Mark workflow as RUNNING (simulates mid-run state)
  3. Simulate backend restart (new WorkflowStore instance)
  4. Recovery: RUNNING → INTERRUPTED
  5. Reload: persisted state matches expected

WORKFLOW_SURVIVES_RESTART=YES
"""

from backend.persistence.store import WorkflowStore
from backend.workflow.enums import WorkflowMode, WorkflowObjective, WorkflowStatus
from backend.workflow.models import ManufacturingWorkflow


def _create_workflow(part: str = "RESTART-TEST-PART") -> ManufacturingWorkflow:
    return ManufacturingWorkflow.create(
        part_reference=part,
        revision="REV-R",
        source_file_ref=None,
        requested_mode=WorkflowMode.ANALYSIS_ONLY,
        objective=WorkflowObjective.BALANCED,
        material_ref=None,
        quantity=1,
        stock_ref=None,
    )


class TestWorkflowSurvivesRestart:
    def test_completed_workflow_survives_restart(self, tmp_path):
        """COMPLETED workflows must remain COMPLETED after restart."""
        db = tmp_path / "restart.db"
        wf = _create_workflow("COMPLETED-PART")
        wf.status = WorkflowStatus.COMPLETED

        with WorkflowStore(db) as store:
            store.save(wf)
            wf_id = wf.workflow_id

        # Simulate restart — new store instance
        with WorkflowStore(db) as store2:
            loaded = store2.load(wf_id)

        assert loaded is not None
        assert str(loaded.status) == "COMPLETED"
        assert loaded.part_reference == "COMPLETED-PART"

    def test_blocked_workflow_survives_restart(self, tmp_path):
        """PARTIAL (blocked) workflows must remain PARTIAL after restart."""
        db = tmp_path / "blocked.db"
        from backend.workflow.enums import StageStatus, WorkflowStage
        from backend.workflow.models import StageResult
        wf = _create_workflow("BLOCKED-PART")
        wf.status = WorkflowStatus.PARTIAL
        result = StageResult(stage=WorkflowStage.CAD_IMPORT, status=StageStatus.BLOCKED)
        result.blocking_reasons.append("No source file")
        result.finish()
        wf.stage_results[WorkflowStage.CAD_IMPORT] = result

        with WorkflowStore(db) as store:
            store.save(wf)
            wf_id = wf.workflow_id

        with WorkflowStore(db) as store2:
            loaded = store2.load(wf_id)

        assert loaded is not None
        assert str(loaded.status) == "PARTIAL"
        cad = loaded.stage_results.get(WorkflowStage.CAD_IMPORT)
        assert cad is not None
        assert str(cad.status) == "BLOCKED"

    def test_running_workflow_marked_interrupted_on_restart(self, tmp_path):
        """RUNNING workflows must be marked INTERRUPTED, not silently left as RUNNING."""
        db = tmp_path / "running.db"
        wf = _create_workflow("RUNNING-PART")
        wf.status = WorkflowStatus.RUNNING

        with WorkflowStore(db) as store:
            store.save(wf)
            wf_id = wf.workflow_id

        # Simulate restart with recovery
        with WorkflowStore(db) as store2:
            count = store2.mark_interrupted()
            assert count == 1
            loaded = store2.load(wf_id)

        assert loaded is not None
        assert str(loaded.status) == "INTERRUPTED"

    def test_interrupted_workflow_not_silent_pass(self, tmp_path):
        """Interrupted workflows must NOT be marked PASS (MUST 5)."""
        db = tmp_path / "nopass.db"
        wf = _create_workflow("NO-PASS-PART")
        wf.status = WorkflowStatus.RUNNING

        with WorkflowStore(db) as store:
            store.save(wf)
            wf_id = wf.workflow_id

        with WorkflowStore(db) as store2:
            store2.mark_interrupted()
            loaded = store2.load(wf_id)

        assert str(loaded.status) != "COMPLETED"
        assert str(loaded.status) != "PASS"

    def test_multiple_workflows_survive_restart(self, tmp_path):
        """Multiple workflows with different statuses all survive restart."""
        db = tmp_path / "multi.db"
        wf1 = _create_workflow("PART-COMPLETED")
        wf1.status = WorkflowStatus.COMPLETED
        wf2 = _create_workflow("PART-PARTIAL")
        wf2.status = WorkflowStatus.PARTIAL
        wf3 = _create_workflow("PART-RUNNING")
        wf3.status = WorkflowStatus.RUNNING

        with WorkflowStore(db) as store:
            store.save(wf1)
            store.save(wf2)
            store.save(wf3)

        with WorkflowStore(db) as store2:
            store2.mark_interrupted()
            loaded1 = store2.load(wf1.workflow_id)
            loaded2 = store2.load(wf2.workflow_id)
            loaded3 = store2.load(wf3.workflow_id)

        assert str(loaded1.status) == "COMPLETED"
        assert str(loaded2.status) == "PARTIAL"
        assert str(loaded3.status) == "INTERRUPTED"

    def test_audit_log_persisted_through_restart(self, tmp_path):
        """Audit log entries must survive restart."""
        db = tmp_path / "audit.db"
        wf = _create_workflow("AUDIT-PART")
        wf.status = WorkflowStatus.COMPLETED
        # wf.audit_log already has WORKFLOW_CREATED from .create()
        initial_audit_count = len(wf.audit_log)

        with WorkflowStore(db) as store:
            store.save(wf)

        with WorkflowStore(db) as store2:
            loaded = store2.load(wf.workflow_id)

        assert len(loaded.audit_log) == initial_audit_count

    def test_stage_results_survive_restart(self, tmp_path):
        """Stage results must survive restart."""
        db = tmp_path / "stages.db"
        from backend.workflow.enums import StageStatus, WorkflowStage
        from backend.workflow.models import StageResult
        wf = _create_workflow("STAGES-PART")
        result = StageResult(stage=WorkflowStage.DFM, status=StageStatus.PASS)
        result.warnings.append("TEST WARNING")
        result.finish()
        wf.stage_results[WorkflowStage.DFM] = result

        with WorkflowStore(db) as store:
            store.save(wf)

        with WorkflowStore(db) as store2:
            loaded = store2.load(wf.workflow_id)

        dfm = loaded.stage_results.get(WorkflowStage.DFM)
        assert dfm is not None
        assert str(dfm.status) == "PASS"
        assert dfm.warnings == ["TEST WARNING"]

    def test_workflow_history_after_restart(self, tmp_path):
        """list_recent must return workflows created before restart."""
        db = tmp_path / "history.db"
        parts = ["HISTORY-A", "HISTORY-B", "HISTORY-C"]
        wf_ids = []
        with WorkflowStore(db) as store:
            for p in parts:
                wf = _create_workflow(p)
                store.save(wf)
                wf_ids.append(wf.workflow_id)

        with WorkflowStore(db) as store2:
            rows = store2.list_recent(50)

        assert len(rows) >= 3
        returned_ids = {r["workflow_id"] for r in rows}
        for wf_id in wf_ids:
            assert wf_id in returned_ids
