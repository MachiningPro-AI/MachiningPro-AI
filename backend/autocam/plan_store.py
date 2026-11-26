"""SQLite-backed Auto CAM plan persistence store.

Follows the same architecture as WorkflowStore / PersistentManufacturingPlanStore:
  PERSISTENCE_FAILURE_POLICY=FAIL_CLOSED
  ARBITRARY_OBJECT_DESERIALIZATION=NO
  CONCURRENCY_PROTECTION=THREADING_LOCK + WAL_MODE
  AUTO_APPROVE_ON_RELOAD=NO
  PERSISTENCE_STATUS_PROMOTION=NO
  AUTOCAM_PLAN_SURVIVES_BACKEND_RESTART=YES

Safety invariants are re-enforced on deserialisation — reload never promotes
feature_confirmation, wcs_confirmation, or production_release status.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path

from .models import _SAFETY_INVARIANTS, AutoCamPlan

logger = logging.getLogger(__name__)


class AutoCamPlanStoreError(RuntimeError):
    """Raised when Auto CAM plan persistence is unavailable or an operation fails."""


class AutoCamPlanStore:
    """Thread-safe SQLite-backed Auto CAM plan store.

    Each plan is serialised to a JSON blob column; metadata columns
    support fast listing without full deserialisation.

    Usage::

        store = AutoCamPlanStore(Path("data/autocam_plans.db"))
        store.save(plan)
        plan = store.get("abc123")
        store.close()
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS autocam_plans (
            plan_id      TEXT PRIMARY KEY,
            file_ref     TEXT NOT NULL,
            plan_status  TEXT NOT NULL,
            cost_status  TEXT,
            report_status TEXT,
            created_at   TEXT NOT NULL,
            updated_at   TEXT NOT NULL,
            payload      TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_autocam_file_ref
            ON autocam_plans(file_ref);
        CREATE INDEX IF NOT EXISTS idx_autocam_status
            ON autocam_plans(plan_status);
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
            conn.executescript(self._SCHEMA)
            conn.commit()
            self._conn = conn
            logger.info("AutoCamPlanStore initialised at %s", self._db_path)
        except Exception as exc:
            raise AutoCamPlanStoreError(
                f"Cannot open AutoCam plan database at {self._db_path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def save(self, plan: AutoCamPlan) -> None:
        """Upsert a plan. Raises AutoCamPlanStoreError on failure."""
        self._assert_open()
        payload = plan.model_dump_json()
        updated_at = datetime.now(UTC).isoformat()
        with self._lock:
            try:
                self._conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO autocam_plans
                        (plan_id, file_ref, plan_status, cost_status,
                         report_status, created_at, updated_at, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plan_id) DO UPDATE SET
                        plan_status   = excluded.plan_status,
                        cost_status   = excluded.cost_status,
                        report_status = excluded.report_status,
                        updated_at    = excluded.updated_at,
                        payload       = excluded.payload
                    """,
                    (
                        plan.plan_id,
                        plan.file_ref,
                        str(plan.plan_status),
                        getattr(plan.cost_estimate, "total_status", None)
                        if plan.cost_estimate
                        else plan.cost_estimate_status,
                        plan.report_status,
                        plan.created_at or updated_at,
                        updated_at,
                        payload,
                    ),
                )
                self._conn.commit()  # type: ignore[union-attr]
            except sqlite3.Error as exc:
                raise AutoCamPlanStoreError(
                    f"Failed to save AutoCam plan {plan.plan_id}: {exc}"
                ) from exc

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get(self, plan_id: str) -> AutoCamPlan | None:
        """Return plan or None if not found. Never raises on missing plan."""
        self._assert_open()
        with self._lock:
            try:
                cur = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT payload FROM autocam_plans WHERE plan_id = ?",
                    (plan_id,),
                )
                row = cur.fetchone()
            except sqlite3.Error as exc:
                raise AutoCamPlanStoreError(
                    f"Failed to query AutoCam plan {plan_id}: {exc}"
                ) from exc

        if row is None:
            return None
        return self._deserialise(row[0])

    def list_recent(self, limit: int = 50) -> list[dict]:
        """Return lightweight plan metadata rows, most recent first."""
        self._assert_open()
        with self._lock:
            try:
                cur = self._conn.execute(  # type: ignore[union-attr]
                    """
                    SELECT plan_id, file_ref, plan_status, cost_status,
                           report_status, created_at, updated_at
                    FROM autocam_plans
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                rows = cur.fetchall()
            except sqlite3.Error as exc:
                raise AutoCamPlanStoreError(
                    f"Failed to list AutoCam plans: {exc}"
                ) from exc

        return [
            {
                "plan_id": r[0],
                "file_ref": r[1],
                "plan_status": r[2],
                "cost_status": r[3],
                "report_status": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                try:
                    self._conn.close()
                except Exception:
                    pass
                self._conn = None

    def __enter__(self) -> AutoCamPlanStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _assert_open(self) -> None:
        if self._conn is None:
            raise AutoCamPlanStoreError("AutoCamPlanStore is closed")

    def _deserialise(self, payload: str) -> AutoCamPlan:
        """Deserialise a plan from JSON.

        PERSISTENCE_STATUS_PROMOTION=NO:
          safety invariants are re-enforced after deserialisation.
          Reload never changes confirmation or production_release status.
        """
        plan = AutoCamPlan.model_validate_json(payload)
        # Re-enforce safety invariants (never serialise-then-promote)
        for key, val in _SAFETY_INVARIANTS.items():
            plan.safety[key] = val
        return plan
