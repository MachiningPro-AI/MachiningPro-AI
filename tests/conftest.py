"""Global test fixtures for MachiningPro AI test suite.

Level-20: Provides a temporary persistence data directory so all tests
use isolated SQLite databases and artifact stores instead of sharing
the production data directory.

Also sets TESSERACT_CMD for drawing-intelligence tests when Tesseract is
installed at a standard OS location but not on PATH.

HARDCODED_TESSERACT_PATH=NO (production code rule)
TEST_TESSERACT_DISCOVERY=AUTO (test infrastructure rule)
"""

from __future__ import annotations

import os
import shutil
import sys

import pytest


def _discover_tesseract() -> str | None:
    """Discover Tesseract binary for the test environment."""
    env_val = os.environ.get("TESSERACT_CMD", "").strip()
    if env_val:
        return env_val

    found = shutil.which("tesseract")
    if found:
        return found

    if sys.platform == "win32":
        candidates = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]
    elif sys.platform == "darwin":
        candidates = [
            "/usr/local/bin/tesseract",
            "/opt/homebrew/bin/tesseract",
        ]
    else:
        candidates = [
            "/usr/bin/tesseract",
            "/usr/local/bin/tesseract",
        ]

    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    return None


_tesseract_cmd = _discover_tesseract()
if _tesseract_cmd and not os.environ.get("TESSERACT_CMD", "").strip():
    os.environ["TESSERACT_CMD"] = _tesseract_cmd


@pytest.fixture(autouse=True, scope="function")
def _isolated_persistence(tmp_path, monkeypatch):
    """Redirect persistence layer to a fresh temp directory for each test.

    Resets module-level singletons so each test gets a clean store.
    Does not affect tests that do not import backend.persistence.
    """
    monkeypatch.setenv("MACHININGPRO_DATA_DIR", str(tmp_path / "data"))
    try:
        import backend.persistence as _p
        _p.reset_stores(tmp_path / "data")
    except ImportError:
        pass
    yield
    try:
        import backend.persistence as _p
        _p.reset_stores()
    except ImportError:
        pass
