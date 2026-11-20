"""Unit tests for the generic report builder."""
from __future__ import annotations

from backend.reports.builders.generic_report import build_generic_report
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ReportKeyValue,
    ReportLanguage,
    ReportStatus,
    ReportText,
    ReportType,
    ReportUnits,
)


class TestGenericReportSafety:
    def test_global_state_unchanged(self):
        build_generic_report(ReportType.PART_ANALYSIS_REPORT, [])
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False

    def test_not_dispatchable(self):
        doc = build_generic_report(ReportType.FEATURE_ANALYSIS_REPORT, [])
        assert doc.metadata.is_dispatchable is False

    def test_not_production_released(self):
        doc = build_generic_report(ReportType.FEATURE_ANALYSIS_REPORT, [])
        assert doc.metadata.production_released is False

    def test_not_auto_approved(self):
        doc = build_generic_report(ReportType.FEATURE_ANALYSIS_REPORT, [])
        assert doc.metadata.auto_approved is False

    def test_review_required(self):
        doc = build_generic_report(ReportType.FEATURE_ANALYSIS_REPORT, [])
        assert doc.metadata.review_required is True

    def test_engineering_state_changed_false(self):
        doc = build_generic_report(ReportType.FEATURE_ANALYSIS_REPORT, [])
        assert doc.metadata.engineering_state_changed is False

    def test_provenance_not_modified(self):
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, [])
        assert doc.provenance.engineering_state_modified is False

    def test_provenance_not_auto_approved(self):
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, [])
        assert doc.provenance.auto_approved is False


class TestGenericReportStructure:
    def test_disclaimer_always_present(self):
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, [])
        ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in ids

    def test_disclaimer_en_draft(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], language=ReportLanguage.EN
        )
        assert "DRAFT" in doc.disclaimer

    def test_disclaimer_tr_taslak(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], language=ReportLanguage.TR
        )
        assert "TASLAK" in doc.disclaimer

    def test_report_type_propagated(self):
        doc = build_generic_report(ReportType.DRAWING_ANALYSIS_REPORT, [])
        assert doc.metadata.report_type == ReportType.DRAWING_ANALYSIS_REPORT

    def test_status_review_required(self):
        doc = build_generic_report(ReportType.CAM_REPORT, [])
        assert doc.metadata.report_status == ReportStatus.REVIEW_REQUIRED

    def test_language_en(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], language=ReportLanguage.EN
        )
        assert doc.metadata.language == ReportLanguage.EN

    def test_language_tr(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], language=ReportLanguage.TR
        )
        assert doc.metadata.language == ReportLanguage.TR

    def test_units_metric(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], units=ReportUnits.METRIC
        )
        assert doc.metadata.units == ReportUnits.METRIC

    def test_units_imperial(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], units=ReportUnits.IMPERIAL
        )
        assert doc.metadata.units == ReportUnits.IMPERIAL

    def test_custom_report_id(self):
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, [], report_id="GEN-TEST-001"
        )
        assert doc.metadata.report_id == "GEN-TEST-001"

    def test_auto_report_id_prefix(self):
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, [])
        assert doc.metadata.report_id.startswith("RPT-GEN-")


class TestGenericReportSections:
    def test_keyvalue_section_added(self):
        sections_data = [
            {
                "section_id": "my_kv",
                "title": "Key Values",
                "type": "keyvalue",
                "items": [["Key A", "Value A"], ["Key B", "Value B"]],
            }
        ]
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, sections_data)
        ids = [s.section_id for s in doc.sections]
        assert "my_kv" in ids
        sec = next(s for s in doc.sections if s.section_id == "my_kv")
        assert any(isinstance(c, ReportKeyValue) for c in sec.content)

    def test_table_section_added(self):
        sections_data = [
            {
                "section_id": "my_table",
                "title": "Table",
                "type": "table",
                "headers": ["Col1", "Col2"],
                "rows": [["A", "B"], ["C", "D"]],
            }
        ]
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, sections_data)
        ids = [s.section_id for s in doc.sections]
        assert "my_table" in ids

    def test_text_section_added(self):
        sections_data = [
            {
                "section_id": "my_text",
                "title": "Text Section",
                "type": "text",
                "body": "Some description here",
            }
        ]
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, sections_data)
        ids = [s.section_id for s in doc.sections]
        assert "my_text" in ids
        sec = next(s for s in doc.sections if s.section_id == "my_text")
        assert any(isinstance(c, ReportText) for c in sec.content)

    def test_warning_section_added(self):
        sections_data = [
            {
                "section_id": "my_warn",
                "title": "Warning",
                "type": "warning",
                "text": "This is a warning",
                "level": "WARNING",
            }
        ]
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, sections_data)
        ids = [s.section_id for s in doc.sections]
        assert "my_warn" in ids

    def test_section_ids_filter(self):
        sections_data = [
            {"section_id": "s1", "title": "S1", "type": "text", "body": "one"},
            {"section_id": "s2", "title": "S2", "type": "text", "body": "two"},
        ]
        doc = build_generic_report(
            ReportType.PART_ANALYSIS_REPORT, sections_data, section_ids=["s1"]
        )
        ids = [s.section_id for s in doc.sections]
        assert "s1" in ids
        assert "s2" not in ids
        assert "disclaimer" in ids  # always included

    def test_empty_sections_data_still_has_disclaimer(self):
        doc = build_generic_report(ReportType.PART_ANALYSIS_REPORT, [])
        ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in ids
        assert len(doc.sections) == 1  # only disclaimer
