"""Level-20 persistence layer — durable workflow and artifact storage.

ARBITRARY_OBJECT_DESERIALIZATION=NO
PERSISTENCE_FAILURE_POLICY=FAIL_CLOSED
"""
from __future__ import annotations

import os
from pathlib import Path

from ..manufacturing_plan.store import ManufacturingPlanStore
from .artifact_store import ArtifactStore, ArtifactStoreError
from .store import WorkflowStore, WorkflowStoreError

__all__ = [
    "ArtifactStore",
    "ArtifactStoreError",
    "ManufacturingPlanStore",
    "WorkflowStore",
    "WorkflowStoreError",
    "get_workflow_store",
    "get_artifact_store",
    "get_plan_store",
    "reset_stores",
]

_DATA_DIR = Path(os.getenv("MACHININGPRO_DATA_DIR", "data"))

_workflow_store: WorkflowStore | None = None
_artifact_store: ArtifactStore | None = None
_plan_store: ManufacturingPlanStore | None = None


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


def get_plan_store() -> ManufacturingPlanStore:
    """Return the process-scoped ManufacturingPlanStore singleton."""
    global _plan_store
    if _plan_store is None:
        _plan_store = ManufacturingPlanStore()
    return _plan_store


def reset_stores(data_dir: str | Path | None = None) -> None:
    """Reset data-dir-dependent store singletons. Used in tests to inject a temp path.

    The in-memory ManufacturingPlanStore is NOT reset because it has no data-dir
    dependency; callers that need a clean plan store can call get_plan_store()
    and clear it directly.
    """
    global _workflow_store, _artifact_store, _DATA_DIR
    if _workflow_store is not None:
        _workflow_store.close()
        _workflow_store = None
    _artifact_store = None
    if data_dir is not None:
        _DATA_DIR = Path(data_dir)
