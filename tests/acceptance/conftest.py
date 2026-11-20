"""Acceptance test configuration — sets auth env vars and shared persistence."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Must be set at module load time (before app/auth is imported by fixtures)
os.environ["MACHININGPRO_DEV_USERNAME"] = "admin"
os.environ["MACHININGPRO_DEV_PASSWORD"] = "machiningpro"
os.environ["MACHININGPRO_DEV_JWT_SECRET"] = "m02-e2e-acceptance-test-secret-32chars"

# Shared session data dir so workflows created in session fixtures survive
# across test functions (the root conftest resets per function otherwise)
_SESSION_DATA_DIR = Path(tempfile.mkdtemp(prefix="mp_acceptance_e2e_"))
os.environ["MACHININGPRO_DATA_DIR"] = str(_SESSION_DATA_DIR)


@pytest.fixture(autouse=True, scope="function")
def _isolated_persistence(monkeypatch):
    """Override root conftest's per-function isolation for acceptance tests.

    Acceptance tests use a shared session-scoped data dir so that workflows
    created in session fixtures can be found in subsequent test functions.
    """
    monkeypatch.setenv("MACHININGPRO_DATA_DIR", str(_SESSION_DATA_DIR))
    try:
        import backend.persistence as _p
        _p.reset_stores(_SESSION_DATA_DIR)
    except ImportError:
        pass
    yield
    # Do NOT reset after each function — keep the session store alive
