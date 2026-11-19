"""Unit tests for report models and safety invariants."""
from __future__ import annotations

import pytest

from backend.reports.models import (
    REPORT_AUTO_APPROVED,
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    REPORT_IS_DISPATCHABLE,
    REPORT_PRODUCTION_RELEASED,
    REPORT_REVIEW_REQUIRED,
    ExportFormat,
    ReportBundle,
    ReportDocument,
    ReportExportItem,
    ReportKeyValue,
    ReportLanguage,
    ReportMetadata,
    ReportProvenance,
    ReportStatus,
    ReportTable,
    ReportText,
    ReportType,
    ReportUnits,
    ReportWarningBox,
    TableRow,
)

# ---------------------------------------------------------------------------
# Safety constant tests
# ---------------------------------------------------------------------------

class TestSafetyConstants:
    def test_engineering_state_not_changed(self):
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False

    def test_not_dispatchable(self):
        assert REPORT_IS_DISPATCHABLE is False

    def test_not_production_released(self):
        assert REPORT_PRODUCTION_RELEASED is False

    def test_not_auto_approved(self):
        assert REPORT_AUTO_APPROVED is False

    def test_review_required(self):
        assert REPORT_REVIEW_REQUIRED is True


# ---------------------------------------------------------------------------
# ReportMetadata
# ---------------------------------------------------------------------------

class TestReportMetadata:
    def _make(self, **kwargs):
        defaults = dict(
            report_id="R-001",
            report_type=ReportType.MANUFACTURING_PLAN,
            report_status=ReportStatus.DRAFT,
            part_reference=None,
            drawing_number="DWG-001",
            revision="A",
            generated_at="2026-11-19T00:00:00Z",
            generated_by="TEST",
            language=ReportLanguage.EN,
            units=ReportUnits.METRIC,
        )
        defaults.update(kwargs)
        return ReportMetadata(**defaults)

    def test_is_dispatchable_false(self):
        m = self._make()
        assert m.is_dispatchable is False

    def test_production_released_false(self):
        m = self._make()
        assert m.production_released is False

    def test_auto_approved_false(self):
        m = self._make()
        assert m.auto_approved is False

    def test_review_required_true(self):
        m = self._make()
        assert m.review_required is True

    def test_engineering_state_changed_false(self):
        m = self._make()
        assert m.engineering_state_changed is False

    def test_schema_version(self):
        m = self._make()
        assert m.schema_version == "1.0"

    def test_application_name(self):
        m = self._make()
        assert m.application == "MachiningPro AI"

    def test_frozen(self):
        m = self._make()
        with pytest.raises((AttributeError, TypeError)):
            m.report_id = "MUTATED"  # type: ignore


# ---------------------------------------------------------------------------
# ReportProvenance
# ---------------------------------------------------------------------------

class TestReportProvenance:
    def test_engineering_state_modified_default_false(self):
        p = ReportProvenance(source_type="WORKFLOW", source_id="W-001")
        assert p.engineering_state_modified is False

    def test_auto_approved_default_false(self):
        p = ReportProvenance(source_type="WORKFLOW", source_id="W-001")
        assert p.auto_approved is False

    def test_frozen(self):
        p = ReportProvenance(source_type="WORKFLOW", source_id="W-001")
        with pytest.raises((AttributeError, TypeError)):
            p.source_id = "MUTATED"  # type: ignore


# ---------------------------------------------------------------------------
# Content types
# ---------------------------------------------------------------------------

class TestContentTypes:
    def test_table_row_cells(self):
        row = TableRow(cells=["A", "B", "C"])
        assert row.cells == ["A", "B", "C"]

    def test_report_table(self):
        tbl = ReportTable(
            headers=["Col1", "Col2"],
            rows=[TableRow(cells=["a", "b"]), TableRow(cells=["c", "d"])],
            caption="Test table",
        )
        assert len(tbl.rows) == 2
        assert tbl.caption == "Test table"

    def test_report_key_value(self):
        kv = ReportKeyValue(items=[("Key", "Value"), ("K2", "V2")])
        assert len(kv.items) == 2

    def test_report_text(self):
        rt = ReportText(body="Hello")
        assert rt.body == "Hello"

    def test_warning_box_default_level(self):
        wb = ReportWarningBox(text="Caution")
        assert wb.level == "WARNING"

    def test_warning_box_error_level(self):
        wb = ReportWarningBox(text="Critical", level="ERROR")
        assert wb.level == "ERROR"


# ---------------------------------------------------------------------------
# ExportFormat
# ---------------------------------------------------------------------------

class TestExportFormat:
    def test_all_formats_present(self):
        formats = {str(f) for f in ExportFormat}
        assert "PDF" in formats
        assert "DOCX" in formats
        assert "XLSX" in formats
        assert "CSV" in formats
        assert "JSON" in formats
        assert "ZIP" in formats


# ---------------------------------------------------------------------------
# ReportBundle
# ---------------------------------------------------------------------------

class TestReportBundle:
    def _make_doc(self) -> ReportDocument:
        meta = ReportMetadata(
            report_id="R-001",
            report_type=ReportType.MANUFACTURING_PLAN,
            report_status=ReportStatus.DRAFT,
            part_reference=None,
            drawing_number="DWG-001",
            revision="A",
            generated_at="2026-11-19T00:00:00Z",
            generated_by="TEST",
            language=ReportLanguage.EN,
            units=ReportUnits.METRIC,
        )
        prov = ReportProvenance(source_type="WORKFLOW", source_id="W-001")
        return ReportDocument(
            metadata=meta,
            provenance=prov,
            sections=[],
            safety_disclaimer_en="DRAFT EN",
            safety_disclaimer_tr="TASLAK TR",
        )

    def test_bundle_engineering_state_false(self):
        doc = self._make_doc()
        bundle = ReportBundle(document=doc)
        assert bundle.engineering_state_changed is False

    def test_bundle_items_empty_by_default(self):
        doc = self._make_doc()
        bundle = ReportBundle(document=doc)
        assert bundle.items == []

    def test_bundle_get_missing(self):
        doc = self._make_doc()
        bundle = ReportBundle(document=doc)
        assert bundle.get(ExportFormat.PDF) is None

    def test_bundle_get_present(self):
        doc = self._make_doc()
        bundle = ReportBundle(document=doc)
        item = ReportExportItem(
            format=ExportFormat.PDF,
            filename="test.pdf",
            content=b"%PDF",
            mime_type="application/pdf",
        )
        bundle.items.append(item)
        assert bundle.get(ExportFormat.PDF) is item
        assert bundle.get(ExportFormat.JSON) is None


# ---------------------------------------------------------------------------
# ReportDocument disclaimer
# ---------------------------------------------------------------------------

class TestReportDocument:
    def _make(self, lang: ReportLanguage) -> ReportDocument:
        meta = ReportMetadata(
            report_id="R-001",
            report_type=ReportType.MANUFACTURING_PLAN,
            report_status=ReportStatus.DRAFT,
            part_reference=None,
            drawing_number=None,
            revision=None,
            generated_at="2026-11-19T00:00:00Z",
            generated_by="TEST",
            language=lang,
            units=ReportUnits.METRIC,
        )
        prov = ReportProvenance(source_type="WORKFLOW", source_id="W-001")
        return ReportDocument(
            metadata=meta,
            provenance=prov,
            sections=[],
            safety_disclaimer_en="DRAFT EN",
            safety_disclaimer_tr="TASLAK TR",
        )

    def test_disclaimer_en(self):
        doc = self._make(ReportLanguage.EN)
        assert doc.disclaimer == "DRAFT EN"

    def test_disclaimer_tr(self):
        doc = self._make(ReportLanguage.TR)
        assert doc.disclaimer == "TASLAK TR"

    def test_now_utc_format(self):
        ts = ReportDocument.now_utc()
        # Format is either ISO 'T...Z' or '... UTC'
        assert "UTC" in ts or "T" in ts
