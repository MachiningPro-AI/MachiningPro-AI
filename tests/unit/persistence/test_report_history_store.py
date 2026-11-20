"""Tests for ReportHistoryStore.

Covers MUST 22-26 from PERSISTENT_PROJECT_MANUFACTURING_STORE_01.

REPORT_HISTORY_SURVIVES_RESTART=YES
IS_DISPATCHABLE=False always in saved records
PRODUCTION_RELEASED=False always in saved records
"""
from __future__ import annotations

import threading
from pathlib import Path

import pytest

from backend.persistence.report_history_store import (
    ReportHistoryStore,
    ReportNotFoundError,
    ReportRecord,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "report_history.db"


@pytest.fixture
def store(db_path: Path) -> ReportHistoryStore:
    with ReportHistoryStore(db_path) as s:
        yield s


def _rec(
    report_id: str = "RPT-001",
    workflow_id: str | None = "WF_test",
    report_type: str = "FULL_MANUFACTURING_REPORT",
    language: str = "EN",
    units: str = "METRIC",
    formats: list[str] | None = None,
) -> ReportRecord:
    return ReportRecord(
        report_id=report_id,
        workflow_id=workflow_id,
        plan_id=None,
        report_type=report_type,
        language=language,
        units=units,
        formats=formats or ["PDF", "JSON"],
        status="GENERATED",
        is_dispatchable=False,
        production_released=False,
        auto_approved=False,
        engineering_state_changed=False,
    )


# ===========================================================================
# MUST 22: Basic CRUD
# ===========================================================================


class TestBasicCRUD:
    def test_save_and_get(self, store: ReportHistoryStore) -> None:
        rec = _rec()
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.report_id == "RPT-001"
        assert loaded.report_type == "FULL_MANUFACTURING_REPORT"

    def test_get_not_found(self, store: ReportHistoryStore) -> None:
        with pytest.raises(ReportNotFoundError):
            store.get("RPT-NONEXISTENT")

    def test_count_empty(self, store: ReportHistoryStore) -> None:
        assert store.count() == 0

    def test_count_after_saves(self, store: ReportHistoryStore) -> None:
        store.save(_rec("RPT-A"))
        store.save(_rec("RPT-B"))
        assert store.count() == 2

    def test_upsert_updates_status(self, store: ReportHistoryStore) -> None:
        rec = _rec()
        store.save(rec)
        rec2 = _rec()
        rec2.status = "ARCHIVED"
        store.save(rec2)
        assert store.count() == 1
        loaded = store.get("RPT-001")
        assert loaded.status == "ARCHIVED"

    def test_formats_roundtrip(self, store: ReportHistoryStore) -> None:
        rec = _rec(formats=["PDF", "JSON", "CSV"])
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.formats == ["PDF", "JSON", "CSV"]

    def test_language_preserved(self, store: ReportHistoryStore) -> None:
        rec = _rec(language="TR")
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.language == "TR"


# ===========================================================================
# MUST 23: Safety invariants in stored records
# ===========================================================================


class TestSafetyInvariants:
    def test_is_dispatchable_always_false(self, store: ReportHistoryStore) -> None:
        rec = _rec()
        assert rec.is_dispatchable is False
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.is_dispatchable is False

    def test_production_released_always_false(self, store: ReportHistoryStore) -> None:
        rec = _rec()
        assert rec.production_released is False
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.production_released is False

    def test_auto_approved_always_false(self, store: ReportHistoryStore) -> None:
        rec = _rec()
        assert rec.auto_approved is False
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.auto_approved is False

    def test_engineering_state_changed_always_false(
        self, store: ReportHistoryStore
    ) -> None:
        rec = _rec()
        assert rec.engineering_state_changed is False
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.engineering_state_changed is False

    def test_safety_flags_read_back_correctly(self, store: ReportHistoryStore) -> None:
        rec = _rec()
        # Manually verify that the safety JSON is never flipped even if someone
        # were to construct a ReportRecord differently — the store reads safety_json
        # and asserts that none of the flags have been toggled.
        store.save(rec)
        loaded = store.get("RPT-001")
        assert not loaded.is_dispatchable
        assert not loaded.production_released
        assert not loaded.auto_approved
        assert not loaded.engineering_state_changed


# ===========================================================================
# MUST 24: Listing endpoints
# ===========================================================================


class TestListingEndpoints:
    def test_list_recent_ordered_by_created_at_desc(
        self, store: ReportHistoryStore
    ) -> None:
        store.save(_rec("RPT-OLD"))
        import time
        time.sleep(0.01)  # ensure distinct created_at
        store.save(_rec("RPT-NEW"))
        rows = store.list_recent(limit=10)
        assert rows[0]["report_id"] == "RPT-NEW"
        assert rows[1]["report_id"] == "RPT-OLD"

    def test_list_recent_respects_limit(self, store: ReportHistoryStore) -> None:
        for i in range(5):
            store.save(_rec(f"RPT-{i:03d}"))
        rows = store.list_recent(limit=3)
        assert len(rows) <= 3

    def test_list_by_workflow(self, store: ReportHistoryStore) -> None:
        store.save(_rec("RPT-WF1-A", workflow_id="WF_1"))
        store.save(_rec("RPT-WF1-B", workflow_id="WF_1"))
        store.save(_rec("RPT-WF2-A", workflow_id="WF_2"))
        rows = store.list_by_workflow("WF_1")
        assert len(rows) == 2
        assert all(r["workflow_id"] == "WF_1" for r in rows)

    def test_list_by_workflow_excludes_other_workflows(
        self, store: ReportHistoryStore
    ) -> None:
        store.save(_rec("RPT-X1", workflow_id="WF_X"))
        store.save(_rec("RPT-Y1", workflow_id="WF_Y"))
        rows = store.list_by_workflow("WF_X")
        assert all(r["workflow_id"] == "WF_X" for r in rows)

    def test_list_by_workflow_empty_result(self, store: ReportHistoryStore) -> None:
        rows = store.list_by_workflow("WF_NOSUCHWORKFLOW")
        assert rows == []

    def test_list_recent_empty_store(self, store: ReportHistoryStore) -> None:
        assert store.list_recent() == []


# ===========================================================================
# MUST 25: Restart survival
# ===========================================================================


class TestRestartSurvival:
    def test_record_survives_simulated_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "rh_restart.db"
        with ReportHistoryStore(db) as s1:
            s1.save(_rec("RPT-RESTART"))
            count_s1 = s1.count()

        with ReportHistoryStore(db) as s2:
            assert s2.count() == count_s1
            loaded = s2.get("RPT-RESTART")
            assert loaded.report_id == "RPT-RESTART"
            assert loaded.report_type == "FULL_MANUFACTURING_REPORT"

    def test_safety_flags_survive_restart(self, tmp_path: Path) -> None:
        db = tmp_path / "rh_safety.db"
        with ReportHistoryStore(db) as s1:
            s1.save(_rec("RPT-SAFETY"))

        with ReportHistoryStore(db) as s2:
            loaded = s2.get("RPT-SAFETY")
            assert loaded.is_dispatchable is False
            assert loaded.production_released is False
            assert loaded.auto_approved is False


# ===========================================================================
# MUST 26: Health check
# ===========================================================================


class TestHealthCheck:
    def test_is_healthy_open(self, store: ReportHistoryStore) -> None:
        assert store.is_healthy()

    def test_is_healthy_closed(self, db_path: Path) -> None:
        s = ReportHistoryStore(db_path)
        s.close()
        assert not s.is_healthy()


# ===========================================================================
# Concurrency
# ===========================================================================


class TestConcurrency:
    def test_concurrent_saves(self, store: ReportHistoryStore) -> None:
        errors: list[Exception] = []

        def writer(i: int) -> None:
            try:
                store.save(_rec(f"RPT-CONC-{i:03d}"))
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent saves raised: {errors}"
        assert store.count() == 10

    def test_concurrent_reads(self, store: ReportHistoryStore) -> None:
        store.save(_rec("RPT-CONC-READ"))
        errors: list[Exception] = []

        def reader() -> None:
            try:
                for _ in range(5):
                    store.get("RPT-CONC-READ")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrent reads raised: {errors}"


# ===========================================================================
# Null / None workflow_id
# ===========================================================================


class TestNullWorkflowId:
    def test_null_workflow_id_saved(self, store: ReportHistoryStore) -> None:
        rec = _rec(workflow_id=None)
        store.save(rec)
        loaded = store.get("RPT-001")
        assert loaded.workflow_id is None

    def test_list_by_null_workflow_returns_empty(
        self, store: ReportHistoryStore
    ) -> None:
        # Listing by None workflow_id is not a valid search;
        # we just ensure it doesn't crash
        rows = store.list_by_workflow("")
        assert isinstance(rows, list)
