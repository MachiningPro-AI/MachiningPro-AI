"""Tests for SQLite WorkflowStore — save, load, list, restart recovery."""
import pytest

from backend.persistence.store import WorkflowStore, WorkflowStoreError
from backend.workflow.enums import WorkflowMode, WorkflowObjective, WorkflowStatus
from backend.workflow.models import ManufacturingWorkflow


def _make_wf(part: str = "PART-TEST") -> ManufacturingWorkflow:
    return ManufacturingWorkflow.create(
        part_reference=part,
        revision="REV-1",
        source_file_ref=None,
        requested_mode=WorkflowMode.ANALYSIS_ONLY,
        objective=WorkflowObjective.BALANCED,
        material_ref=None,
        quantity=1,
        stock_ref=None,
    )


class TestWorkflowStoreMemory:
    @pytest.fixture
    def store(self):
        with WorkflowStore(":memory:") as s:
            yield s

    def test_save_and_load(self, store):
        wf = _make_wf()
        store.save(wf)
        loaded = store.load(wf.workflow_id)
        assert loaded is not None
        assert loaded.workflow_id == wf.workflow_id
        assert loaded.part_reference == wf.part_reference

    def test_load_missing_returns_none(self, store):
        assert store.load("WF_nonexistent") is None

    def test_save_updates_existing(self, store):
        wf = _make_wf()
        store.save(wf)
        wf.status = WorkflowStatus.COMPLETED
        store.save(wf)
        loaded = store.load(wf.workflow_id)
        assert str(loaded.status) == "COMPLETED"

    def test_list_recent(self, store):
        wf1 = _make_wf("PART-A")
        wf2 = _make_wf("PART-B")
        store.save(wf1)
        store.save(wf2)
        rows = store.list_recent(10)
        assert len(rows) == 2
        ids = {r["workflow_id"] for r in rows}
        assert wf1.workflow_id in ids
        assert wf2.workflow_id in ids

    def test_list_recent_limit(self, store):
        for i in range(5):
            store.save(_make_wf(f"PART-{i}"))
        rows = store.list_recent(3)
        assert len(rows) == 3

    def test_count(self, store):
        assert store.count() == 0
        store.save(_make_wf("P1"))
        store.save(_make_wf("P2"))
        assert store.count() == 2

    def test_is_healthy(self, store):
        assert store.is_healthy() is True

    def test_multiple_workflows_independent(self, store):
        wf1 = _make_wf("PART-X")
        wf2 = _make_wf("PART-Y")
        store.save(wf1)
        store.save(wf2)
        loaded1 = store.load(wf1.workflow_id)
        loaded2 = store.load(wf2.workflow_id)
        assert loaded1.part_reference == "PART-X"
        assert loaded2.part_reference == "PART-Y"

    def test_mark_interrupted(self, store):
        wf = _make_wf()
        wf.status = WorkflowStatus.RUNNING
        store.save(wf)
        count = store.mark_interrupted()
        assert count == 1
        loaded = store.load(wf.workflow_id)
        assert str(loaded.status) == "INTERRUPTED"

    def test_mark_interrupted_non_running_untouched(self, store):
        wf = _make_wf()
        wf.status = WorkflowStatus.COMPLETED
        store.save(wf)
        count = store.mark_interrupted()
        assert count == 0
        loaded = store.load(wf.workflow_id)
        assert str(loaded.status) == "COMPLETED"

    def test_mark_interrupted_adds_audit_entry(self, store):
        wf = _make_wf()
        wf.status = WorkflowStatus.RUNNING
        store.save(wf)
        store.mark_interrupted()
        loaded = store.load(wf.workflow_id)
        audit_details = [ae.detail for ae in loaded.audit_log]
        assert any("INTERRUPTED_BY_RESTART" in d for d in audit_details)

    def test_closed_store_raises(self, store):
        store.close()
        with pytest.raises(WorkflowStoreError):
            store.load("WF_x")

    def test_stage_results_persisted(self, store):
        from backend.workflow.enums import StageStatus, WorkflowStage
        from backend.workflow.models import StageResult
        wf = _make_wf()
        result = StageResult(stage=WorkflowStage.CAD_IMPORT, status=StageStatus.PASS)
        result.finish()
        wf.stage_results[WorkflowStage.CAD_IMPORT] = result
        store.save(wf)
        loaded = store.load(wf.workflow_id)
        r = loaded.stage_results.get(WorkflowStage.CAD_IMPORT)
        assert r is not None
        assert str(r.status) == "PASS"


class TestWorkflowStoreFile:
    def test_persist_to_file_and_reload(self, tmp_path):
        db_path = tmp_path / "test_wf.db"
        wf = _make_wf("PART-FILE")
        with WorkflowStore(db_path) as store:
            store.save(wf)
            wf_id = wf.workflow_id

        with WorkflowStore(db_path) as store2:
            loaded = store2.load(wf_id)
            assert loaded is not None
            assert loaded.part_reference == "PART-FILE"

    def test_restart_recovery_scenario(self, tmp_path):
        db_path = tmp_path / "restart.db"
        wf = _make_wf("RESTART-PART")
        wf.status = WorkflowStatus.RUNNING

        with WorkflowStore(db_path) as store:
            store.save(wf)
            wf_id = wf.workflow_id

        # Simulate restart
        with WorkflowStore(db_path) as store2:
            store2.mark_interrupted()
            loaded = store2.load(wf_id)
            assert str(loaded.status) == "INTERRUPTED"

    def test_completed_workflow_survives_restart(self, tmp_path):
        db_path = tmp_path / "survive.db"
        wf = _make_wf("SURVIVE-PART")
        wf.status = WorkflowStatus.COMPLETED
        with WorkflowStore(db_path) as store:
            store.save(wf)

        with WorkflowStore(db_path) as store2:
            loaded = store2.load(wf.workflow_id)
            assert str(loaded.status) == "COMPLETED"
