"""In-process metrics counters — no external dependency.

Provides a simple, thread-safe counter store for operational observability.
Values are approximate under high concurrency (no atomic ops needed for demo scale).
Do NOT use these values for billing or SLA enforcement.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from typing import Any

_lock = threading.Lock()
_counters: dict[str, int] = defaultdict(int)
_gauges: dict[str, float] = {}


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def set_gauge(name: str, value: float) -> None:
    with _lock:
        _gauges[name] = value


def snapshot() -> dict[str, Any]:
    """Return a copy of all current metrics values."""
    with _lock:
        return {
            "counters": dict(_counters),
            "gauges": dict(_gauges),
        }


def reset() -> None:
    """Reset all metrics. For testing only."""
    with _lock:
        _counters.clear()
        _gauges.clear()


# Named counter constants — prevents typo-driven metric divergence
WORKFLOW_CREATED = "workflow.created"
WORKFLOW_RUN = "workflow.run"
WORKFLOW_COMPLETED = "workflow.completed"
WORKFLOW_FAILED = "workflow.failed"
WORKFLOW_INTERRUPTED = "workflow.interrupted"
STAGE_FAILED = "stage.failed"
STAGE_BLOCKED = "stage.blocked"
UPLOAD_ACCEPTED = "upload.accepted"
UPLOAD_REJECTED = "upload.rejected"
UPLOAD_OVERSIZED = "upload.oversized"
EXPORT_REQUESTED = "export.requested"
AUTH_FAILED = "auth.failed"
PERSISTENCE_ERROR = "persistence.error"
