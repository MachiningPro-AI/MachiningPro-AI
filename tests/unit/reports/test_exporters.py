"""Unit tests for all report exporters."""
from __future__ import annotations

import json
import zipfile
from io import BytesIO

from backend.manufacturing_plan.models import ManufacturingPlan
from backend.reports.builders.manufacturing_plan_report import (
    build_manufacturing_plan_report,
)
from backend.reports.exporters.csv_exporter import export_csv
from backend.reports.exporters.docx_exporter import export_docx
from backend.reports.exporters.json_exporter import export_json
from backend.reports.exporters.pdf_exporter import export_pdf
from backend.reports.exporters.xlsx_exporter import export_xlsx
from backend.reports.exporters.zip_exporter import export_zip
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportBundle,
    ReportLanguage,
    ReportUnits,
)


def _make_doc(drawing_number: str = "DWG-001", language: ReportLanguage = ReportLanguage.EN):
    plan = ManufacturingPlan(
        plan_id="P-001",
        source_id="W-001",
        drawing_number=drawing_number,
        revision="A",
        part_id="PART-001",
    )
    return build_manufacturing_plan_report(plan, language=language, units=ReportUnits.METRIC)


# ---------------------------------------------------------------------------
# JSON exporter
# ---------------------------------------------------------------------------

class TestJsonExporter:
    def test_format_is_json(self):
        doc = _make_doc()
        item = export_json(doc)
        assert item.format == ExportFormat.JSON

    def test_mime_type(self):
        doc = _make_doc()
        item = export_json(doc)
        assert "json" in item.mime_type

    def test_content_is_valid_json(self):
        doc = _make_doc()
        item = export_json(doc)
        data = json.loads(item.content)
        assert isinstance(data, dict)

    def test_safety_in_json(self):
        doc = _make_doc()
        item = export_json(doc)
        data = json.loads(item.content)
        safety = data.get("safety", {})
        assert safety.get("is_dispatchable") is False
        assert safety.get("production_released") is False
        assert safety.get("auto_approved") is False
        assert safety.get("engineering_state_changed") is False

    def test_metadata_in_json(self):
        doc = _make_doc()
        item = export_json(doc)
        data = json.loads(item.content)
        assert "metadata" in data

    def test_filename_has_drawing_number(self):
        doc = _make_doc(drawing_number="TEST-999")
        item = export_json(doc)
        assert "TEST-999" in item.filename or "TEST_999" in item.filename

    def test_filename_ends_with_json(self):
        doc = _make_doc()
        item = export_json(doc)
        assert item.filename.endswith(".json")

    def test_content_not_empty(self):
        doc = _make_doc()
        item = export_json(doc)
        assert len(item.content) > 0


# ---------------------------------------------------------------------------
# CSV exporter
# ---------------------------------------------------------------------------

class TestCsvExporter:
    def test_format_is_csv(self):
        doc = _make_doc()
        item = export_csv(doc)
        assert item.format == ExportFormat.CSV

    def test_mime_type(self):
        doc = _make_doc()
        item = export_csv(doc)
        assert "csv" in item.mime_type

    def test_filename_ends_with_csv(self):
        doc = _make_doc()
        item = export_csv(doc)
        assert item.filename.endswith(".csv")

    def test_content_is_valid_utf8(self):
        doc = _make_doc()
        item = export_csv(doc)
        text = item.content.decode("utf-8-sig")
        assert len(text) > 0

    def test_safety_disclaimer_in_csv(self):
        doc = _make_doc()
        item = export_csv(doc)
        text = item.content.decode("utf-8-sig")
        assert "DRAFT" in text or "IS_DISPATCHABLE" in text

    def test_injection_guard_prefix(self):
        """Cells starting with = are prefixed with single-quote."""
        from backend.reports.exporters.csv_exporter import _guard
        assert _guard("=SUM(A1:A10)") == "'=SUM(A1:A10)"

    def test_injection_guard_safe(self):
        from backend.reports.exporters.csv_exporter import _guard
        assert _guard("Normal text") == "Normal text"

    def test_injection_guard_plus(self):
        from backend.reports.exporters.csv_exporter import _guard
        assert _guard("+cmd") == "'+cmd"

    def test_injection_guard_at(self):
        from backend.reports.exporters.csv_exporter import _guard
        assert _guard("@SUM") == "'@SUM"

    def test_content_not_empty(self):
        doc = _make_doc()
        item = export_csv(doc)
        assert len(item.content) > 0


# ---------------------------------------------------------------------------
# XLSX exporter
# ---------------------------------------------------------------------------

class TestXlsxExporter:
    def test_format_is_xlsx(self):
        doc = _make_doc()
        item = export_xlsx(doc)
        assert item.format == ExportFormat.XLSX

    def test_mime_type(self):
        doc = _make_doc()
        item = export_xlsx(doc)
        assert "spreadsheet" in item.mime_type or "xlsx" in item.mime_type

    def test_filename_ends_with_xlsx(self):
        doc = _make_doc()
        item = export_xlsx(doc)
        assert item.filename.endswith(".xlsx")

    def test_content_is_valid_xlsx(self):
        import openpyxl
        doc = _make_doc()
        item = export_xlsx(doc)
        wb = openpyxl.load_workbook(BytesIO(item.content))
        assert len(wb.sheetnames) >= 1

    def test_cover_sheet_present(self):
        import openpyxl
        doc = _make_doc()
        item = export_xlsx(doc)
        wb = openpyxl.load_workbook(BytesIO(item.content))
        has_cover = "Cover" in wb.sheetnames or any(
            "Cover" in s or "cover" in s.lower() for s in wb.sheetnames
        )
        assert has_cover

    def test_content_not_empty(self):
        doc = _make_doc()
        item = export_xlsx(doc)
        assert len(item.content) > 0


# ---------------------------------------------------------------------------
# PDF exporter
# ---------------------------------------------------------------------------

class TestPdfExporter:
    def test_format_is_pdf(self):
        doc = _make_doc()
        item = export_pdf(doc)
        assert item.format == ExportFormat.PDF

    def test_mime_type(self):
        doc = _make_doc()
        item = export_pdf(doc)
        assert item.mime_type == "application/pdf"

    def test_filename_ends_with_pdf(self):
        doc = _make_doc()
        item = export_pdf(doc)
        assert item.filename.endswith(".pdf")

    def test_content_starts_with_pdf_header(self):
        doc = _make_doc()
        item = export_pdf(doc)
        assert item.content[:4] == b"%PDF"

    def test_content_not_empty(self):
        doc = _make_doc()
        item = export_pdf(doc)
        assert len(item.content) > 100

    def test_pdf_tr_language(self):
        doc = _make_doc(language=ReportLanguage.TR)
        item = export_pdf(doc)
        assert item.content[:4] == b"%PDF"


# ---------------------------------------------------------------------------
# DOCX exporter
# ---------------------------------------------------------------------------

class TestDocxExporter:
    def test_format_is_docx(self):
        doc = _make_doc()
        item = export_docx(doc)
        assert item.format == ExportFormat.DOCX

    def test_mime_type(self):
        doc = _make_doc()
        item = export_docx(doc)
        assert "wordprocessingml" in item.mime_type

    def test_filename_ends_with_docx(self):
        doc = _make_doc()
        item = export_docx(doc)
        assert item.filename.endswith(".docx")

    def test_content_is_valid_zip(self):
        doc = _make_doc()
        item = export_docx(doc)
        with zipfile.ZipFile(BytesIO(item.content)) as zf:
            names = zf.namelist()
        assert "[Content_Types].xml" in names

    def test_document_xml_present(self):
        doc = _make_doc()
        item = export_docx(doc)
        with zipfile.ZipFile(BytesIO(item.content)) as zf:
            names = zf.namelist()
        assert "word/document.xml" in names

    def test_styles_xml_present(self):
        doc = _make_doc()
        item = export_docx(doc)
        with zipfile.ZipFile(BytesIO(item.content)) as zf:
            names = zf.namelist()
        assert "word/styles.xml" in names

    def test_document_xml_contains_disclaimer(self):
        doc = _make_doc()
        item = export_docx(doc)
        with zipfile.ZipFile(BytesIO(item.content)) as zf:
            xml = zf.read("word/document.xml").decode("utf-8")
        assert "DRAFT" in xml

    def test_content_not_empty(self):
        doc = _make_doc()
        item = export_docx(doc)
        assert len(item.content) > 100


# ---------------------------------------------------------------------------
# ZIP exporter
# ---------------------------------------------------------------------------

class TestZipExporter:
    def _make_bundle(self, doc):
        bundle = ReportBundle(document=doc)
        bundle.items.append(export_pdf(doc))
        bundle.items.append(export_json(doc))
        return bundle

    def test_format_is_zip(self):
        doc = _make_doc()
        bundle = self._make_bundle(doc)
        item = export_zip(doc, bundle)
        assert item.format == ExportFormat.ZIP

    def test_mime_type(self):
        doc = _make_doc()
        bundle = self._make_bundle(doc)
        item = export_zip(doc, bundle)
        assert item.mime_type == "application/zip"

    def test_filename_ends_with_zip(self):
        doc = _make_doc()
        bundle = self._make_bundle(doc)
        item = export_zip(doc, bundle)
        assert item.filename.endswith(".zip")

    def test_contains_all_bundle_items(self):
        doc = _make_doc()
        bundle = self._make_bundle(doc)
        item = export_zip(doc, bundle)
        with zipfile.ZipFile(BytesIO(item.content)) as zf:
            names = zf.namelist()
        assert len(names) == 2  # PDF + JSON (no ZIP recursion)

    def test_does_not_include_zip_items(self):
        doc = _make_doc()
        bundle = self._make_bundle(doc)
        # Add a fake ZIP item — should be excluded
        fake_zip = export_zip(doc, bundle)
        bundle.items.append(fake_zip)
        item2 = export_zip(doc, bundle)
        with zipfile.ZipFile(BytesIO(item2.content)) as zf:
            names = zf.namelist()
        # ZIP item should not be recursed into
        for name in names:
            assert not name.endswith(".zip")


# ---------------------------------------------------------------------------
# Full bundle via service
# ---------------------------------------------------------------------------

class TestReportService:
    def test_all_formats_generated(self):
        from backend.reports.report_service import generate_manufacturing_plan_report
        plan = ManufacturingPlan(
            plan_id="P-TEST",
            source_id="W-TEST",
            drawing_number="SVC-001",
            revision="A",
            part_id="PART-SVC",
        )
        formats = [
            ExportFormat.PDF,
            ExportFormat.DOCX,
            ExportFormat.XLSX,
            ExportFormat.CSV,
            ExportFormat.JSON,
            ExportFormat.ZIP,
        ]
        bundle = generate_manufacturing_plan_report(plan, formats=formats)
        assert len(bundle.items) == 6

    def test_engineering_state_not_changed(self):
        from backend.reports.report_service import generate_manufacturing_plan_report
        plan = ManufacturingPlan(
            plan_id="P-TEST",
            source_id="W-TEST",
            drawing_number="SVC-001",
            revision="A",
            part_id="PART-SVC",
        )
        bundle = generate_manufacturing_plan_report(plan, formats=[ExportFormat.JSON])
        assert bundle.engineering_state_changed is False

    def test_global_constant_still_false_after_generation(self):
        from backend.reports.report_service import generate_manufacturing_plan_report
        plan = ManufacturingPlan(
            plan_id="P-TEST2",
            source_id="W-TEST2",
            drawing_number="SVC-002",
            revision="B",
            part_id="PART-SVC2",
        )
        _ = generate_manufacturing_plan_report(plan, formats=[ExportFormat.PDF, ExportFormat.JSON])
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False
