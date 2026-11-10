"""Global test fixtures for MachiningPro AI test suite.

Level-20: Provides a temporary persistence data directory so all tests
use isolated SQLite databases and artifact stores instead of sharing
the production data directory.
"""
import os
import tempfile
import pytest


@pytest.fixture(autouse=True, scope="function")
def _isolated_persistence(tmp_path, monkeypatch):
    """Redirect persistence layer to a fresh temp directory for each test.

    Resets module-level singletons so each test gets a clean store.
    Does not affect tests that do not import backend.persistence.
    """
    monkeypatch.setenv("MACHININGPRO_DATA_DIR", str(tmp_path / "data"))
    # Reset singletons if the module has been imported
    try:
        import backend.persistence as _p
        _p.reset_stores(tmp_path / "data")
    except ImportError:
        pass
    yield
    # Cleanup singletons after test
    try:
        import backend.persistence as _p
        _p.reset_stores()
    except ImportError:
        pass
