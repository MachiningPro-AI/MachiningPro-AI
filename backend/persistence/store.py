"""SQLite-backed workflow store.

PERSISTENCE_FAILURE_POLICY=FAIL_CLOSED
ARBITRARY_OBJECT_DESERIALIZATION=NO
CONCURRENCY_PROTECTION=THREADING_LOCK + WAL_MODE
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any

from ..workflow.models import ManufacturingWorkflow
from .serializer import from_json, to_json

logger = logging.getLogger(__name__)


class WorkflowStoreError(RuntimeError):
    """Raised when persistence is unavailable or an operation fails.

    Never silently swallows failures — callers must handle this explicitly.
    """


class WorkflowStore:
    """Thread-safe SQLite workflow persistence store.

    Each workflow is serialised to a JSON blob column; metadata columns
    support fast listing without full deserialisation.

    Usage::

        store = WorkflowStore(Path("data/workflows.db"))
        store.save(workflow)
        wf = store.load("WF_abc123")
        store.close()

    Or as context manager::

        with WorkflowStore(":memory:") as store:
            ...
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS workflows (
            workflow_id   TEXT PRIMARY KEY,
            part_reference TEXT NOT NULL,
            status         TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            payload        TEXT NOT NULL
        )
    """

    def __init__(self, db_path: str | Path) -> None:
        self._db_path = str(db_path)
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._setup()

    def _setup(self) -> None:
        try:
            if self._db_path != ":memory:":
                Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(self._db_path, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(self._SCHEMA)
            conn.commit()
            self._conn = conn
            logger.info("WorkflowStore initialised at %s", self._db_path)
        except Exception as exc:
            raise WorkflowStoreError(
                f"Cannot open workflow database at {self._db_path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------

    def save(self, wf: ManufacturingWorkflow) -> None:
        """Upsert a workflow. Raises WorkflowStoreError on failure."""
        self._assert_open()
        payload = to_json(wf)
        with self._lock:
            try:
                self._conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO workflows
                        (workflow_id, part_reference, status, created_at, updated_at, payload)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(workflow_id) DO UPDATE SET
                        status     = excluded.status,
                        updated_at = excluded.updated_at,
                        payload    = excluded.payload
                    """,
                    (
                        wf.workflow_id,
                        wf.part_reference,
                        str(wf.status),
                        wf.created_at.isoformat(),
                        wf.updated_at.isoformat(),
                        payload,
                    ),
                )
                self._conn.commit()  # type: ignore[union-attr]
            except sqlite3.Error as exc:
                raise WorkflowStoreError(
                    f"Failed to save workflow {wf.workflow_id}: {exc}"
                ) from exc

    def mark_interrupted(self) -> int:
        """Mark all RUNNING workflows as INTERRUPTED on startup.

        Returns count of workflows updated.
        Called once at application startup to handle crash recovery.
        """
        self._assert_open()
        with self._lock:
            try:
                cur = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT workflow_id, payload FROM workflows WHERE status = 'RUNNING'"
                )
                rows = cur.fetchall()
            except sqlite3.Error as exc:
                raise WorkflowStoreError(f"Failed to query RUNNING workflows: {exc}") from exc

        count = 0
        for wf_id, payload_str in rows:
            try:
                wf = from_json(payload_str)
                from ..workflow.enums import AuditEventType, WorkflowStatus  # local import
                wf.status = WorkflowStatus.INTERRUPTED
                wf.add_audit(
                    AuditEventType.WORKFLOW_CANCELLED,
                    detail="INTERRUPTED_BY_RESTART — resume to continue",
                )
                self.save(wf)
                count += 1
                logger.warning("Marked workflow %s as INTERRUPTED on restart", wf_id)
            except Exception as exc:  # noqa: BLE001
                logger.error("Could not mark %s as INTERRUPTED: %s", wf_id, exc)
        return count

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    def load(self, workflow_id: str) -> ManufacturingWorkflow | None:
        """Load a workflow by ID. Returns None if not found."""
        self._assert_open()
        with self._lock:
            try:
                row = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT payload FROM workflows WHERE workflow_id = ?", (workflow_id,)
                ).fetchone()
            except sqlite3.Error as exc:
                raise WorkflowStoreError(
                    f"Failed to load workflow {workflow_id}: {exc}"
                ) from exc
        if row is None:
            return None
        return from_json(row[0])

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return lightweight listing rows ordered by created_at DESC."""
        self._assert_open()
        limit = max(1, min(limit, 500))
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    """SELECT workflow_id, part_reference, status, created_at, updated_at
                       FROM workflows ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise WorkflowStoreError(f"Failed to list workflows: {exc}") from exc
        return [
            {
                "workflow_id": r[0],
                "part_reference": r[1],
                "status": r[2],
                "created_at": r[3],
                "updated_at": r[4],
            }
            for r in rows
        ]

    def count(self) -> int:
        """Return total number of stored workflows."""
        if self._conn is None:
            return 0
        with self._lock:
            try:
                row = self._conn.execute("SELECT COUNT(*) FROM workflows").fetchone()
                return row[0] if row else 0
            except sqlite3.Error:
                return 0

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def is_healthy(self) -> bool:
        if self._conn is None:
            return False
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:  # noqa: BLE001
            return False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _assert_open(self) -> None:
        if self._conn is None:
            raise WorkflowStoreError("WorkflowStore is closed")

    def __enter__(self) -> WorkflowStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
