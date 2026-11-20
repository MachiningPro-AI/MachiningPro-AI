"""SQLite-backed ReportHistoryStore — persists report metadata.

PERSISTENCE_FAILURE_POLICY=FAIL_CLOSED
ARBITRARY_PATH_READ=NO
ARBITRARY_PATH_WRITE=NO
RAW_FILESYSTEM_PATH_IN_RESPONSE=NO
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ReportHistoryError(RuntimeError):
    """Raised when report history persistence fails."""


class ReportNotFoundError(KeyError):
    """Raised when a report record is not found."""


@dataclass
class ReportRecord:
    """Lightweight metadata record for a generated report.

    Does NOT store raw file content. Stores an optional safe
    storage_ref (artifact_id or None) that callers can use to
    retrieve the actual file through the ArtifactStore.

    PATH_TRAVERSAL_PROTECTION=YES — storage_ref is an opaque id, not a path.
    SECRET_PERSISTENCE=NO — no credentials or tokens stored.
    """

    report_id: str
    workflow_id: str | None
    plan_id: str | None
    report_type: str
    language: str
    units: str
    formats: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: str = "GENERATED"
    storage_ref: str | None = None
    schema_version: str = "1.0"
    is_dispatchable: bool = False
    production_released: bool = False
    auto_approved: bool = False
    engineering_state_changed: bool = False


class ReportHistoryStore:
    """Thread-safe SQLite-backed store for report generation metadata.

    Usage::

        store = ReportHistoryStore(Path("data/report_history.db"))
        store.save(record)
        records = store.list_by_workflow("WF_abc123")
        store.close()
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS report_history (
            report_id       TEXT PRIMARY KEY,
            workflow_id     TEXT,
            plan_id         TEXT,
            report_type     TEXT NOT NULL,
            language        TEXT NOT NULL,
            units           TEXT NOT NULL,
            formats         TEXT NOT NULL,
            created_at      TEXT NOT NULL,
            status          TEXT NOT NULL,
            storage_ref     TEXT,
            schema_version  TEXT,
            safety_json     TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_rh_workflow
            ON report_history(workflow_id);
        CREATE INDEX IF NOT EXISTS idx_rh_plan
            ON report_history(plan_id);
        CREATE INDEX IF NOT EXISTS idx_rh_created
            ON report_history(created_at);
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
            for stmt in self._SCHEMA.strip().split(";"):
                stmt = stmt.strip()
                if stmt:
                    conn.execute(stmt)
            conn.commit()
            self._conn = conn
            logger.info("ReportHistoryStore initialised at %s", self._db_path)
        except Exception as exc:
            raise ReportHistoryError(
                f"Cannot open report history database at {self._db_path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------ Write

    def save(self, record: ReportRecord) -> ReportRecord:
        """Upsert a report record. Raises ReportHistoryError on failure."""
        self._assert_open()
        safety = json.dumps({
            "is_dispatchable": record.is_dispatchable,
            "production_released": record.production_released,
            "auto_approved": record.auto_approved,
            "engineering_state_changed": record.engineering_state_changed,
        })
        with self._lock:
            try:
                self._conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO report_history
                        (report_id, workflow_id, plan_id, report_type, language, units,
                         formats, created_at, status, storage_ref, schema_version, safety_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(report_id) DO UPDATE SET
                        status       = excluded.status,
                        storage_ref  = excluded.storage_ref,
                        safety_json  = excluded.safety_json
                    """,
                    (
                        record.report_id,
                        record.workflow_id,
                        record.plan_id,
                        record.report_type,
                        record.language,
                        record.units,
                        json.dumps(record.formats),
                        record.created_at.isoformat(),
                        record.status,
                        record.storage_ref,
                        record.schema_version,
                        safety,
                    ),
                )
                self._conn.commit()  # type: ignore[union-attr]
            except sqlite3.Error as exc:
                raise ReportHistoryError(
                    f"Failed to save report record {record.report_id}: {exc}"
                ) from exc
        return record

    # ------------------------------------------------------------------ Read

    def get(self, report_id: str) -> ReportRecord:
        """Load a report record by ID. Raises ReportNotFoundError if absent."""
        self._assert_open()
        with self._lock:
            try:
                row = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT * FROM report_history WHERE report_id = ?", (report_id,)
                ).fetchone()
            except sqlite3.Error as exc:
                raise ReportHistoryError(
                    f"Failed to load report {report_id}: {exc}"
                ) from exc
        if row is None:
            raise ReportNotFoundError(report_id)
        return _row_to_record(row)

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return lightweight listing rows ordered by created_at DESC."""
        self._assert_open()
        limit = max(1, min(limit, 500))
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    """SELECT report_id, workflow_id, plan_id, report_type,
                              language, units, formats, created_at, status
                       FROM report_history ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise ReportHistoryError(f"Failed to list reports: {exc}") from exc
        return [
            {
                "report_id": r[0],
                "workflow_id": r[1],
                "plan_id": r[2],
                "report_type": r[3],
                "language": r[4],
                "units": r[5],
                "formats": json.loads(r[6]) if r[6] else [],
                "created_at": r[7],
                "status": r[8],
            }
            for r in rows
        ]

    def list_by_workflow(self, workflow_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """Return report records for a specific workflow, newest first."""
        self._assert_open()
        limit = max(1, min(limit, 500))
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    """SELECT report_id, workflow_id, plan_id, report_type,
                              language, units, formats, created_at, status
                       FROM report_history WHERE workflow_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (workflow_id, limit),
                ).fetchall()
            except sqlite3.Error as exc:
                raise ReportHistoryError(
                    f"Failed to list reports for workflow {workflow_id}: {exc}"
                ) from exc
        return [
            {
                "report_id": r[0],
                "workflow_id": r[1],
                "plan_id": r[2],
                "report_type": r[3],
                "language": r[4],
                "units": r[5],
                "formats": json.loads(r[6]) if r[6] else [],
                "created_at": r[7],
                "status": r[8],
            }
            for r in rows
        ]

    def count(self) -> int:
        if self._conn is None:
            return 0
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM report_history"
                ).fetchone()
                return row[0] if row else 0
            except sqlite3.Error:
                return 0

    # ------------------------------------------------------------------ Health

    def is_healthy(self) -> bool:
        if self._conn is None:
            return False
        try:
            with self._lock:
                self._conn.execute("SELECT 1").fetchone()
            return True
        except Exception:  # noqa: BLE001
            return False

    # ---------------------------------------------------------------- Lifecycle

    def close(self) -> None:
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None

    def _assert_open(self) -> None:
        if self._conn is None:
            raise ReportHistoryError("ReportHistoryStore is closed")

    def __enter__(self) -> ReportHistoryStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _row_to_record(row: tuple) -> ReportRecord:
    # row order: report_id, workflow_id, plan_id, report_type, language, units,
    #            formats, created_at, status, storage_ref, schema_version, safety_json
    safety: dict = {}
    if row[11]:
        try:
            safety = json.loads(row[11])
        except (json.JSONDecodeError, TypeError):
            pass
    formats: list[str] = []
    if row[6]:
        try:
            formats = json.loads(row[6])
        except (json.JSONDecodeError, TypeError):
            pass
    created: datetime = datetime.utcnow()
    if row[7]:
        try:
            created = datetime.fromisoformat(row[7])
        except ValueError:
            pass
    return ReportRecord(
        report_id=row[0],
        workflow_id=row[1],
        plan_id=row[2],
        report_type=row[3],
        language=row[4],
        units=row[5],
        formats=formats,
        created_at=created,
        status=row[8],
        storage_ref=row[9],
        schema_version=row[10] or "1.0",
        is_dispatchable=bool(safety.get("is_dispatchable", False)),
        production_released=bool(safety.get("production_released", False)),
        auto_approved=bool(safety.get("auto_approved", False)),
        engineering_state_changed=bool(safety.get("engineering_state_changed", False)),
    )
