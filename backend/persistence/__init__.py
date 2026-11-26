"""Persistence layer — durable workflow, plan, artifact, and report storage.

ARBITRARY_OBJECT_DESERIALIZATION=NO
PERSISTENCE_FAILURE_POLICY=FAIL_CLOSED
MANUFACTURING_PLAN_STORE_MODE=SQLITE_PERSISTENT
AUTOCAM_PLAN_STORE_MODE=SQLITE_PERSISTENT
"""
from __future__ import annotations

import os
from pathlib import Path

from ..autocam.plan_store import AutoCamPlanStore, AutoCamPlanStoreError
from ..manufacturing_plan.store import ManufacturingPlanStore
from .artifact_store import ArtifactStore, ArtifactStoreError
from .plan_store import PersistentManufacturingPlanStore, PlanStoreError
from .report_history_store import ReportHistoryError, ReportHistoryStore, ReportRecord
from .store import WorkflowStore, WorkflowStoreError

__all__ = [
    "ArtifactStore",
    "ArtifactStoreError",
    "AutoCamPlanStore",
    "AutoCamPlanStoreError",
    "ManufacturingPlanStore",
    "PersistentManufacturingPlanStore",
    "PlanStoreError",
    "ReportHistoryStore",
    "ReportHistoryError",
    "ReportRecord",
    "WorkflowStore",
    "WorkflowStoreError",
    "get_workflow_store",
    "get_artifact_store",
    "get_plan_store",
    "get_report_history_store",
    "get_autocam_plan_store",
    "reset_stores",
]

_DATA_DIR = Path(os.getenv("MACHININGPRO_DATA_DIR", "data"))

_workflow_store: WorkflowStore | None = None
_artifact_store: ArtifactStore | None = None
_plan_store: PersistentManufacturingPlanStore | None = None
_report_history_store: ReportHistoryStore | None = None
_autocam_plan_store: AutoCamPlanStore | None = None


def get_workflow_store() -> WorkflowStore:
    global _workflow_store
    if _workflow_store is None:
        db_path = _DATA_DIR / "workflows.db"
        _workflow_store = WorkflowStore(db_path)
    return _workflow_store


def get_artifact_store() -> ArtifactStore:
    global _artifact_store
    if _artifact_store is None:
        artifacts_dir = _DATA_DIR / "artifacts"
        _artifact_store = ArtifactStore(artifacts_dir)
    return _artifact_store


def get_plan_store() -> PersistentManufacturingPlanStore:
    """Return the persistent ManufacturingPlan store singleton.

    Backed by SQLite at <data_dir>/plans.db.
    MANUFACTURING_PLAN_STORE_MODE=SQLITE_PERSISTENT
    PLAN_SURVIVES_BACKEND_RESTART=YES
    """
    global _plan_store
    if _plan_store is None:
        db_path = _DATA_DIR / "plans.db"
        _plan_store = PersistentManufacturingPlanStore(db_path)
    return _plan_store


def get_report_history_store() -> ReportHistoryStore:
    """Return the report history store singleton.

    Backed by SQLite at <data_dir>/report_history.db.
    REPORT_HISTORY_SURVIVES_RESTART=YES
    """
    global _report_history_store
    if _report_history_store is None:
        db_path = _DATA_DIR / "report_history.db"
        _report_history_store = ReportHistoryStore(db_path)
    return _report_history_store


def get_autocam_plan_store() -> AutoCamPlanStore:
    """Return the persistent AutoCam plan store singleton.

    Backed by SQLite at <data_dir>/autocam_plans.db.
    AUTOCAM_PLAN_STORE_MODE=SQLITE_PERSISTENT
    AUTOCAM_PLAN_SURVIVES_BACKEND_RESTART=YES
    """
    global _autocam_plan_store
    if _autocam_plan_store is None:
        db_path = _DATA_DIR / "autocam_plans.db"
        _autocam_plan_store = AutoCamPlanStore(db_path)
    return _autocam_plan_store


def reset_stores(data_dir: str | Path | None = None) -> None:
    """Reset data-dir-dependent store singletons. Used in tests to inject a temp path."""
    global _workflow_store, _artifact_store, _plan_store
    global _report_history_store, _autocam_plan_store, _DATA_DIR
    if _workflow_store is not None:
        _workflow_store.close()
        _workflow_store = None
    if _plan_store is not None:
        _plan_store.close()
        _plan_store = None
    if _report_history_store is not None:
        _report_history_store.close()
        _report_history_store = None
    if _autocam_plan_store is not None:
        _autocam_plan_store.close()
        _autocam_plan_store = None
    _artifact_store = None
    if data_dir is not None:
        _DATA_DIR = Path(data_dir)
    # Also reset the orchestrator-level store global so it re-initialises
    # with the new data_dir on next call to _get_store().
    try:
        import backend.autocam.orchestrator as _orch
        _orch._plan_store = None
    except ImportError:
        pass
