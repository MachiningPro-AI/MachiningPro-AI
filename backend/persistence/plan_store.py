"""SQLite-backed ManufacturingPlan persistence store.

Follows the same architecture as WorkflowStore:
  PERSISTENCE_FAILURE_POLICY=FAIL_CLOSED
  ARBITRARY_OBJECT_DESERIALIZATION=NO
  CONCURRENCY_PROTECTION=THREADING_LOCK + WAL_MODE
  AUTO_CONFIRM_ON_RELOAD=NO
  AUTO_APPROVE_ON_RELOAD=NO
  PERSISTENCE_STATUS_PROMOTION=NO
"""
from __future__ import annotations

import logging
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path

from ..manufacturing_plan.models import (
    ChangeDriver,
    ManufacturingPlan,
    ManufacturingPlanStatus,
    PlanRevisionEntry,
)
from ..manufacturing_plan.serializer import plan_from_json, plan_to_json
from ..manufacturing_plan.store import PlanApprovalError, PlanNotFoundError

logger = logging.getLogger(__name__)


class PlanStoreError(RuntimeError):
    """Raised when plan persistence is unavailable or an operation fails."""


class PersistentManufacturingPlanStore:
    """Thread-safe SQLite-backed ManufacturingPlan store.

    Compatible interface with the in-memory ManufacturingPlanStore.
    Each plan is serialised to a JSON blob column; metadata columns
    support fast listing.

    Usage::

        store = PersistentManufacturingPlanStore(Path("data/plans.db"))
        saved = store.save(plan)
        plan = store.get(plan_id)
        store.close()
    """

    _SCHEMA = """
        CREATE TABLE IF NOT EXISTS manufacturing_plans (
            plan_id        TEXT PRIMARY KEY,
            drawing_number TEXT,
            part_id        TEXT,
            source_id      TEXT,
            status         TEXT NOT NULL,
            created_at     TEXT NOT NULL,
            updated_at     TEXT NOT NULL,
            payload        TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_plans_part_id
            ON manufacturing_plans(part_id);
        CREATE INDEX IF NOT EXISTS idx_plans_drawing
            ON manufacturing_plans(drawing_number);
        CREATE INDEX IF NOT EXISTS idx_plans_status
            ON manufacturing_plans(status);
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
            logger.info("PersistentManufacturingPlanStore initialised at %s", self._db_path)
        except Exception as exc:
            raise PlanStoreError(
                f"Cannot open plan database at {self._db_path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------ CRUD

    def save(self, plan: ManufacturingPlan) -> ManufacturingPlan:
        """Upsert a plan. Raises PlanStoreError on failure."""
        self._assert_open()
        updated = _stamp(plan)
        payload = plan_to_json(updated)
        with self._lock:
            try:
                self._conn.execute(  # type: ignore[union-attr]
                    """
                    INSERT INTO manufacturing_plans
                        (plan_id, drawing_number, part_id, source_id,
                         status, created_at, updated_at, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(plan_id) DO UPDATE SET
                        drawing_number = excluded.drawing_number,
                        part_id        = excluded.part_id,
                        source_id      = excluded.source_id,
                        status         = excluded.status,
                        updated_at     = excluded.updated_at,
                        payload        = excluded.payload
                    """,
                    (
                        updated.plan_id,
                        updated.drawing_number,
                        updated.part_id,
                        updated.source_id,
                        str(updated.status),
                        updated.created_at.isoformat(),
                        updated.updated_at.isoformat(),
                        payload,
                    ),
                )
                self._conn.commit()  # type: ignore[union-attr]
            except sqlite3.Error as exc:
                raise PlanStoreError(
                    f"Failed to save plan {plan.plan_id}: {exc}"
                ) from exc
        return updated

    def get(self, plan_id: str) -> ManufacturingPlan:
        """Load a plan by ID. Raises PlanNotFoundError if absent."""
        self._assert_open()
        with self._lock:
            try:
                row = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT payload FROM manufacturing_plans WHERE plan_id = ?",
                    (plan_id,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise PlanStoreError(f"Failed to load plan {plan_id}: {exc}") from exc
        if row is None:
            raise PlanNotFoundError(plan_id)
        return plan_from_json(row[0])

    def list_all(self) -> list[ManufacturingPlan]:
        """Return all stored plans, ordered by created_at DESC."""
        self._assert_open()
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT payload FROM manufacturing_plans ORDER BY created_at DESC"
                ).fetchall()
            except sqlite3.Error as exc:
                raise PlanStoreError(f"Failed to list plans: {exc}") from exc
        return [plan_from_json(r[0]) for r in rows]

    def list_summary(self, limit: int = 100) -> list[dict]:
        """Return lightweight listing rows without deserialising full payloads."""
        self._assert_open()
        limit = max(1, min(limit, 1000))
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    """SELECT plan_id, drawing_number, part_id, source_id,
                              status, created_at, updated_at
                       FROM manufacturing_plans
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise PlanStoreError(f"Failed to list plan summaries: {exc}") from exc
        return [
            {
                "plan_id": r[0],
                "drawing_number": r[1],
                "part_id": r[2],
                "source_id": r[3],
                "status": r[4],
                "created_at": r[5],
                "updated_at": r[6],
            }
            for r in rows
        ]

    def delete(self, plan_id: str) -> None:
        """Delete a plan by ID. Raises PlanNotFoundError if absent."""
        self._assert_open()
        with self._lock:
            try:
                cur = self._conn.execute(  # type: ignore[union-attr]
                    "DELETE FROM manufacturing_plans WHERE plan_id = ?", (plan_id,)
                )
                self._conn.commit()  # type: ignore[union-attr]
            except sqlite3.Error as exc:
                raise PlanStoreError(f"Failed to delete plan {plan_id}: {exc}") from exc
        if cur.rowcount == 0:
            raise PlanNotFoundError(plan_id)

    # ---------------------------------------------------------------- Actions

    def mark_engineer_reviewed(self, plan_id: str, engineer_note: str = "") -> ManufacturingPlan:
        plan = self.get(plan_id)
        if plan.status not in (ManufacturingPlanStatus.DRAFT, ManufacturingPlanStatus.REJECTED):
            raise PlanApprovalError(
                f"Cannot mark ENGINEER_REVIEWED from status {plan.status}"
            )
        entry = _revision_entry(plan, ChangeDriver.ENGINEER_EDIT, engineer_note)
        import dataclasses
        updated = dataclasses.replace(
            plan,
            status=ManufacturingPlanStatus.ENGINEER_REVIEWED,
            revision_history=[*plan.revision_history, entry],
        )
        return self.save(updated)

    def approve(self, plan_id: str, engineer_note: str = "") -> ManufacturingPlan:
        """AUTO_GENERATED_PLAN_MARKED_APPROVED=NO. Only ENGINEER_REVIEWED plans."""
        plan = self.get(plan_id)
        if plan.AUTO_GENERATED_PLAN_MARKED_APPROVED:
            raise PlanApprovalError(
                "AUTO_GENERATED_PLAN_MARKED_APPROVED=True — approval not permitted"
            )
        if plan.status != ManufacturingPlanStatus.ENGINEER_REVIEWED:
            raise PlanApprovalError(
                f"Cannot approve plan in status {plan.status}; must be ENGINEER_REVIEWED first"
            )
        entry = _revision_entry(plan, ChangeDriver.ENGINEER_EDIT, engineer_note)
        import dataclasses
        updated = dataclasses.replace(
            plan,
            status=ManufacturingPlanStatus.APPROVED,
            revision_history=[*plan.revision_history, entry],
        )
        return self.save(updated)

    def reject(self, plan_id: str, engineer_note: str = "") -> ManufacturingPlan:
        plan = self.get(plan_id)
        if plan.status not in (
            ManufacturingPlanStatus.DRAFT,
            ManufacturingPlanStatus.ENGINEER_REVIEWED,
        ):
            raise PlanApprovalError(f"Cannot reject plan in status {plan.status}")
        entry = _revision_entry(plan, ChangeDriver.ENGINEER_EDIT, engineer_note)
        import dataclasses
        updated = dataclasses.replace(
            plan,
            status=ManufacturingPlanStatus.REJECTED,
            revision_history=[*plan.revision_history, entry],
        )
        return self.save(updated)

    def supersede(self, old_plan_id: str, new_plan: ManufacturingPlan) -> ManufacturingPlan:
        old = self.get(old_plan_id)
        import dataclasses
        superseded = dataclasses.replace(old, status=ManufacturingPlanStatus.SUPERSEDED)
        self.save(superseded)
        return self.save(new_plan)

    # ----------------------------------------------------------------- Query

    def find_by_drawing(self, drawing_number: str) -> list[ManufacturingPlan]:
        self._assert_open()
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT payload FROM manufacturing_plans WHERE drawing_number = ?",
                    (drawing_number,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise PlanStoreError(
                    f"Failed to find plans for drawing {drawing_number}: {exc}"
                ) from exc
        return [plan_from_json(r[0]) for r in rows]

    def find_by_source(self, source_id: str) -> list[ManufacturingPlan]:
        self._assert_open()
        with self._lock:
            try:
                rows = self._conn.execute(  # type: ignore[union-attr]
                    "SELECT payload FROM manufacturing_plans WHERE source_id = ?",
                    (source_id,),
                ).fetchall()
            except sqlite3.Error as exc:
                raise PlanStoreError(
                    f"Failed to find plans for source {source_id}: {exc}"
                ) from exc
        return [plan_from_json(r[0]) for r in rows]

    def count(self) -> int:
        if self._conn is None:
            return 0
        with self._lock:
            try:
                row = self._conn.execute(
                    "SELECT COUNT(*) FROM manufacturing_plans"
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
            raise PlanStoreError("PersistentManufacturingPlanStore is closed")

    def __enter__(self) -> PersistentManufacturingPlanStore:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stamp(plan: ManufacturingPlan) -> ManufacturingPlan:
    import dataclasses
    return dataclasses.replace(plan, updated_at=datetime.utcnow())


def _revision_entry(
    plan: ManufacturingPlan,
    driver: ChangeDriver,
    note: str,
) -> PlanRevisionEntry:
    return PlanRevisionEntry(
        revision_id=str(uuid.uuid4()),
        revision_number=len(plan.revision_history) + 1,
        change_driver=driver,
        previous_plan_id=None,
        new_plan_id=plan.plan_id,
        changed_fields=["status"],
        engineer_note=note,
    )
