"""Synthetic CAD test fixtures.

All files are TEST_ONLY / DEMO — not customer or production data.
Sources: programmatically generated minimal valid format samples.
"""
from __future__ import annotations

from pathlib import Path

FIXTURES_DIR = Path(__file__).parent


def minimal_dxf() -> bytes:
    """Minimal valid DXF R12 — section header only. TEST_ONLY."""
    return b"  0\nSECTION\n  2\nHEADER\n  0\nENDSEC\n  0\nEOF\n"


def minimal_step() -> bytes:
    """Minimal valid STEP AP203 file. TEST_ONLY."""
    return (
        b"ISO-10303-21;\n"
        b"HEADER;\n"
        b"FILE_DESCRIPTION(('TEST_ONLY minimal STEP fixture'),'2;1');\n"
        b"FILE_NAME('test.stp','2026-11-10T00:00:00',('MachiningPro AI TEST'),\n"
        b"(''),(''),'',' ');\n"
        b"FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));\n"
        b"ENDSEC;\n"
        b"DATA;\n"
        b"ENDSEC;\n"
        b"END-ISO-10303-21;\n"
    )


def minimal_iges() -> bytes:
    """Minimal valid IGES file with correct S-column format. TEST_ONLY."""
    # IGES has fixed 80-char records; column 73 must be 'S' in Start section
    start_line = b"                                                                        S      1"
    # Pad to exactly 80 characters
    start_line = start_line + b" " * (80 - len(start_line)) + b"\n"
    terminate_line = b"S      1G      0D      0P      0                                 T      1\n"
    return start_line + terminate_line


def malformed_dxf() -> bytes:
    """DXF file with invalid content. TEST_ONLY."""
    return b"NOT A VALID DXF\x00\xff\n"


def malformed_step() -> bytes:
    """STEP file with wrong header. TEST_ONLY."""
    return b"NOT-ISO-10303-21;\nINVALID CONTENT\n"


def malformed_iges() -> bytes:
    """IGES file with wrong column 73. TEST_ONLY."""
    return b"X" * 80 + b"\n"


def oversized_content(size_bytes: int = 51 * 1024 * 1024) -> bytes:
    """Content exceeding the default 50 MB upload limit. TEST_ONLY."""
    return b"0\n" + b"X" * size_bytes


def empty_content() -> bytes:
    return b""


# Write fixtures to disk for use as file paths in integration tests
def write_fixture(name: str, content: bytes) -> Path:
    path = FIXTURES_DIR / name
    path.write_bytes(content)
    return path


def ensure_fixtures() -> dict[str, Path]:
    """Write all standard fixtures to disk and return name→path mapping."""
    return {
        "minimal.dxf": write_fixture("TEST_ONLY_minimal.dxf", minimal_dxf()),
        "minimal.stp": write_fixture("TEST_ONLY_minimal.stp", minimal_step()),
        "minimal.iges": write_fixture("TEST_ONLY_minimal.iges", minimal_iges()),
        "malformed.dxf": write_fixture("TEST_ONLY_malformed.dxf", malformed_dxf()),
        "malformed.stp": write_fixture("TEST_ONLY_malformed.stp", malformed_step()),
        "malformed.iges": write_fixture("TEST_ONLY_malformed.iges", malformed_iges()),
    }
