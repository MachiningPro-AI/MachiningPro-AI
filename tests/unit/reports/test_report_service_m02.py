"""Unit tests for report service Module 02 additions.

Tests:
- REPORT_TYPES registry (17 types, MUST 6/7)
- generate_full_manufacturing_report
- generate_synthetic_qualification_report
- _build_bundle with ExportFormat.ZIP
REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
"""
from __future__ import annotations

from backend.manufacturing_plan.models import ManufacturingPlan
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportLanguage,
    ReportType,
    ReportUnits,
)
from backend.reports.report_service import (
    REPORT_TYPES,
    generate_full_manufacturing_report,
    generate_synthetic_qualification_report,
)


def _minimal_plan(**kwargs) -> ManufacturingPlan:
    defaults = dict(
        plan_id="P-SVC-TEST",
        source_id="W-SVC-001",
        drawing_number="DWG-SVC",
        revision="A",
        part_id="PART-SVC",
    )
    defaults.update(kwargs)
    return ManufacturingPlan(**defaults)


# ---------------------------------------------------------------------------
# REPORT_TYPES registry
# ---------------------------------------------------------------------------

class TestReportTypesRegistry:
    def test_registry_not_empty(self):
        assert len(REPORT_TYPES) > 0

    def test_full_manufacturing_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "FULL_MANUFACTURING_REPORT" in ids

    def test_manufacturing_plan_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "MANUFACTURING_PLAN" in ids

    def test_synthetic_qualification_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "SYNTHETIC_QUALIFICATION_REPORT" in ids

    def test_part_analysis_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "PART_ANALYSIS_REPORT" in ids

    def test_drawing_analysis_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "DRAWING_ANALYSIS_REPORT" in ids

    def test_feature_analysis_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "FEATURE_ANALYSIS_REPORT" in ids

    def test_process_plan_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "PROCESS_PLAN_REPORT" in ids

    def test_machine_selection_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "MACHINE_SELECTION_REPORT" in ids

    def test_tool_selection_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "TOOL_SELECTION_REPORT" in ids

    def test_cutting_parameters_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "CUTTING_PARAMETERS_REPORT" in ids

    def test_cam_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "CAM_REPORT" in ids

    def test_toolpath_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "TOOLPATH_REPORT" in ids

    def test_verification_report_in_registry(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert "VERIFICATION_REPORT" in ids

    def test_registry_at_least_12_types(self):
        # MUST 7 requires at least 12 specific types
        assert len(REPORT_TYPES) >= 12

    def test_each_type_has_label_en(self):
        for rt in REPORT_TYPES:
            assert "label_en" in rt, f"Missing label_en in {rt['id']}"

    def test_each_type_has_label_tr(self):
        for rt in REPORT_TYPES:
            assert "label_tr" in rt, f"Missing label_tr in {rt['id']}"

    def test_each_type_has_supported_formats(self):
        for rt in REPORT_TYPES:
            assert "supported_formats" in rt, f"Missing supported_formats in {rt['id']}"

    def test_full_mfr_supports_all_formats(self):
        fmr = next(rt for rt in REPORT_TYPES if rt["id"] == "FULL_MANUFACTURING_REPORT")
        for fmt in ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"]:
            assert fmt in fmr["supported_formats"]

    def test_full_mfr_has_section_ids(self):
        fmr = next(rt for rt in REPORT_TYPES if rt["id"] == "FULL_MANUFACTURING_REPORT")
        assert "section_ids" in fmr
        assert len(fmr["section_ids"]) >= 20

    def test_no_duplicate_type_ids(self):
        ids = [rt["id"] for rt in REPORT_TYPES]
        assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# generate_full_manufacturing_report
# ---------------------------------------------------------------------------

class TestGenerateFullManufacturingReport:
    def test_returns_bundle(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON]
        )
        assert bundle is not None

    def test_bundle_contains_json(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON]
        )
        item = bundle.get(ExportFormat.JSON)
        assert item is not None

    def test_bundle_contains_pdf(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.PDF]
        )
        item = bundle.get(ExportFormat.PDF)
        assert item is not None
        assert len(item.content) > 0

    def test_bundle_contains_docx(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.DOCX]
        )
        item = bundle.get(ExportFormat.DOCX)
        assert item is not None
        assert len(item.content) > 0

    def test_bundle_contains_xlsx(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.XLSX]
        )
        item = bundle.get(ExportFormat.XLSX)
        assert item is not None
        assert len(item.content) > 0

    def test_bundle_contains_csv(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.CSV]
        )
        item = bundle.get(ExportFormat.CSV)
        assert item is not None
        assert len(item.content) > 0

    def test_bundle_contains_zip(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.ZIP]
        )
        item = bundle.get(ExportFormat.ZIP)
        assert item is not None
        assert len(item.content) > 0

    def test_all_formats_in_one_call(self):
        plan = _minimal_plan()
        all_fmts = [
            ExportFormat.PDF,
            ExportFormat.DOCX,
            ExportFormat.XLSX,
            ExportFormat.CSV,
            ExportFormat.JSON,
            ExportFormat.ZIP,
        ]
        bundle = generate_full_manufacturing_report(plan, formats=all_fmts)
        for fmt in all_fmts:
            item = bundle.get(fmt)
            assert item is not None, f"Missing format {fmt}"

    def test_engineering_state_not_changed(self):
        plan = _minimal_plan()
        _ = generate_full_manufacturing_report(plan, formats=[ExportFormat.JSON])
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False
        assert not plan.plan_id != "P-SVC-TEST"  # plan_id unchanged

    def test_bundle_engineering_state_not_changed(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(plan, formats=[ExportFormat.JSON])
        assert bundle.engineering_state_changed is False

    def test_language_en(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], language=ReportLanguage.EN
        )
        assert bundle.document.metadata.language == ReportLanguage.EN

    def test_language_tr(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], language=ReportLanguage.TR
        )
        assert bundle.document.metadata.language == ReportLanguage.TR

    def test_units_metric(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], units=ReportUnits.METRIC
        )
        assert bundle.document.metadata.units == ReportUnits.METRIC

    def test_units_imperial(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], units=ReportUnits.IMPERIAL
        )
        assert bundle.document.metadata.units == ReportUnits.IMPERIAL

    def test_report_type_full_manufacturing(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON]
        )
        assert bundle.document.metadata.report_type == ReportType.FULL_MANUFACTURING_REPORT

    def test_section_ids_filter_applied(self):
        plan = _minimal_plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON],
            section_ids=["executive_summary"]
        )
        ids = [s.section_id for s in bundle.document.sections]
        assert "executive_summary" in ids
        assert "disclaimer" in ids  # always present


# ---------------------------------------------------------------------------
# generate_synthetic_qualification_report
# ---------------------------------------------------------------------------

class TestGenerateSyntheticQualReport:
    def test_returns_bundle(self):
        bundle = generate_synthetic_qualification_report(
            {}, formats=[ExportFormat.JSON]
        )
        assert bundle is not None

    def test_bundle_contains_json(self):
        bundle = generate_synthetic_qualification_report(
            {}, formats=[ExportFormat.JSON]
        )
        item = bundle.get(ExportFormat.JSON)
        assert item is not None

    def test_bundle_contains_pdf(self):
        bundle = generate_synthetic_qualification_report(
            {}, formats=[ExportFormat.PDF]
        )
        item = bundle.get(ExportFormat.PDF)
        assert item is not None

    def test_all_formats(self):
        all_fmts = [
            ExportFormat.PDF, ExportFormat.DOCX,
            ExportFormat.XLSX, ExportFormat.CSV,
            ExportFormat.JSON, ExportFormat.ZIP,
        ]
        bundle = generate_synthetic_qualification_report({}, formats=all_fmts)
        for fmt in all_fmts:
            assert bundle.get(fmt) is not None, f"Missing {fmt}"

    def test_engineering_state_not_changed(self):
        _ = generate_synthetic_qualification_report({}, formats=[ExportFormat.JSON])
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False

    def test_bundle_state_not_changed(self):
        bundle = generate_synthetic_qualification_report(
            {}, formats=[ExportFormat.JSON]
        )
        assert bundle.engineering_state_changed is False

    def test_report_type(self):
        bundle = generate_synthetic_qualification_report(
            {}, formats=[ExportFormat.JSON]
        )
        assert bundle.document.metadata.report_type == ReportType.SYNTHETIC_QUALIFICATION_REPORT
