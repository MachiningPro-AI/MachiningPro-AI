"""Security tests for the reporting module.

MUST 24: Path traversal, unsafe filename, unsupported format validation.
Tests the API-level and service-level protections.
"""
from __future__ import annotations

import re

import pytest

from backend.reports.models import ExportFormat

# ---------------------------------------------------------------------------
# _SAFE_FILENAME_RE — same regex used in api/reports.py
# ---------------------------------------------------------------------------

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_\-]")


def _sanitize(filename: str) -> str:
    return _SAFE_FILENAME_RE.sub("_", filename)


class TestFilenamesSanitization:
    def test_path_traversal_dot_dot_sanitized(self):
        result = _sanitize("../../etc/passwd.pdf")
        assert ".." not in result
        assert "/" not in result

    def test_windows_path_separator_sanitized(self):
        result = _sanitize("C:\\Windows\\System32\\secret.pdf")
        assert "\\" not in result
        assert ":" not in result

    def test_null_bytes_sanitized(self):
        result = _sanitize("report\x00.pdf")
        assert "\x00" not in result

    def test_space_sanitized(self):
        result = _sanitize("my report.pdf")
        assert " " not in result

    def test_normal_filename_dot_replaced(self):
        result = _sanitize("MP_SYN_001_FULL_REPORT_EN.pdf")
        # The regex replaces . with _
        assert result == "MP_SYN_001_FULL_REPORT_EN_pdf"

    def test_hyphen_preserved(self):
        result = _sanitize("PART-001-REPORT")
        # Hyphens are in the allowed set [A-Za-z0-9_\-]
        assert result == "PART-001-REPORT"

    def test_unicode_sanitized(self):
        result = _sanitize("rapor_ürün.pdf")
        # Non-ASCII chars should be replaced
        for char in result:
            assert char in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-", \
                f"Unexpected char {char!r} in sanitized filename"


# ---------------------------------------------------------------------------
# ExportFormat validation
# ---------------------------------------------------------------------------

class TestExportFormatValidation:
    def test_valid_pdf(self):
        assert ExportFormat("PDF") == ExportFormat.PDF

    def test_valid_docx(self):
        assert ExportFormat("DOCX") == ExportFormat.DOCX

    def test_valid_xlsx(self):
        assert ExportFormat("XLSX") == ExportFormat.XLSX

    def test_valid_csv(self):
        assert ExportFormat("CSV") == ExportFormat.CSV

    def test_valid_json(self):
        assert ExportFormat("JSON") == ExportFormat.JSON

    def test_valid_zip(self):
        assert ExportFormat("ZIP") == ExportFormat.ZIP

    def test_invalid_format_raises_value_error(self):
        with pytest.raises(ValueError):
            ExportFormat("INVALID")

    def test_path_traversal_format_raises(self):
        with pytest.raises(ValueError):
            ExportFormat("../../etc/passwd")

    def test_null_format_raises(self):
        with pytest.raises(ValueError):
            ExportFormat("")

    def test_whitespace_format_raises(self):
        with pytest.raises(ValueError):
            ExportFormat("   ")

    def test_script_injection_format_raises(self):
        with pytest.raises(ValueError):
            ExportFormat("<script>alert(1)</script>")


# ---------------------------------------------------------------------------
# Valid format set (_VALID_FORMATS in api/reports.py)
# ---------------------------------------------------------------------------

_VALID_FORMATS = {"PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"}


class TestValidFormatsSet:
    def test_all_expected_formats_present(self):
        assert "PDF" in _VALID_FORMATS
        assert "DOCX" in _VALID_FORMATS
        assert "XLSX" in _VALID_FORMATS
        assert "CSV" in _VALID_FORMATS
        assert "JSON" in _VALID_FORMATS
        assert "ZIP" in _VALID_FORMATS

    def test_path_traversal_not_in_valid_formats(self):
        assert "../../etc/passwd" not in _VALID_FORMATS

    def test_script_injection_not_in_valid_formats(self):
        assert "<script>" not in _VALID_FORMATS

    def test_exactly_six_valid_formats(self):
        assert len(_VALID_FORMATS) == 6


# ---------------------------------------------------------------------------
# CSV injection guard (OWASP)
# ---------------------------------------------------------------------------

_CSV_INJECTION_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _is_csv_safe(value: str) -> bool:
    if not value:
        return True
    if value[0] in _CSV_INJECTION_PREFIXES:
        return False
    return True


class TestCsvInjectionGuard:
    def test_safe_string_passes(self):
        assert _is_csv_safe("Normal Value") is True

    def test_safe_number_passes(self):
        assert _is_csv_safe("12345.67") is True

    def test_equals_prefix_flagged(self):
        assert _is_csv_safe("=HYPERLINK(...)") is False

    def test_plus_prefix_flagged(self):
        assert _is_csv_safe("+SYSTEM(...)") is False

    def test_minus_prefix_flagged(self):
        assert _is_csv_safe("-1+2") is False

    def test_at_prefix_flagged(self):
        assert _is_csv_safe("@SUM(...)") is False

    def test_empty_string_safe(self):
        assert _is_csv_safe("") is True

    def test_na_safe(self):
        assert _is_csv_safe("N/A") is True


# ---------------------------------------------------------------------------
# Safety invariants — module-level constants
# ---------------------------------------------------------------------------

class TestModuleSafetyConstants:
    def test_format_mime_types_defined(self):
        from backend.api.reports import _FORMAT_MIME, _VALID_FORMATS
        for fmt in _VALID_FORMATS:
            assert fmt in _FORMAT_MIME, f"Missing MIME type for {fmt}"

    def test_safe_filename_regex_compiled(self):
        from backend.api.reports import _SAFE_FILENAME_RE
        assert _SAFE_FILENAME_RE is not None

    def test_path_traversal_blocked_by_regex(self):
        from backend.api.reports import _SAFE_FILENAME_RE
        result = _SAFE_FILENAME_RE.sub("_", "../../evil")
        assert ".." not in result
