"""Structured logging configuration for MachiningPro AI.

Uses Python's standard logging module with a JSON-line formatter for
structured log output (readable by Render's log aggregation and local dev).

Do NOT log sensitive file content, JWT secrets, or passwords.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from .correlation import get_request_id


class StructuredFormatter(logging.Formatter):
    """Emit one JSON object per log record on stdout/stderr."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        req_id = get_request_id()
        if req_id:
            payload["request_id"] = req_id
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Include any extra fields attached by the caller
        for key, val in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_"):
                payload[key] = val
        return json.dumps(payload)


_STANDARD_RECORD_ATTRS = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "message", "taskName",
})


def configure_logging(level: str = "INFO") -> None:
    """Configure application-wide structured logging.

    Safe to call multiple times — idempotent.
    """
    root = logging.getLogger()
    if root.handlers:
        return  # Already configured

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Suppress noisy uvicorn access log in production (kept at WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
