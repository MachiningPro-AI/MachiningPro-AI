"""Unit tests for manufacturing plan report builder."""
from __future__ import annotations

from backend.manufacturing_plan.models import ManufacturingPlan
from backend.reports.builders.manufacturing_plan_report import (
    build_manufacturing_plan_report,
)
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ReportLanguage,
    ReportStatus,
    ReportType,
    ReportUnits,
    ReportWarningBox,
)


def _minimal_plan(**kwargs) -> ManufacturingPlan:
    defaults = dict(
        plan_id="P-001",
        source_id="W-001",
        drawing_number="DWG-001",
        revision="A",
        part_id="PART-001",
    )
    defaults.update(kwargs)
    return ManufacturingPlan(**defaults)


class TestBuildManufacturingPlanReport:
    def test_returns_report_document(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(
            plan, language=ReportLanguage.EN, units=ReportUnits.METRIC
        )
        assert doc is not None

    def test_safety_invariants_in_metadata(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        assert doc.metadata.is_dispatchable is False
        assert doc.metadata.production_released is False
        assert doc.metadata.auto_approved is False
        assert doc.metadata.review_required is True
        assert doc.metadata.engineering_state_changed is False

    def test_provenance_state_not_modified(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        assert doc.provenance.engineering_state_modified is False
        assert doc.provenance.auto_approved is False

    def test_report_type_manufacturing_plan(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        assert doc.metadata.report_type == ReportType.MANUFACTURING_PLAN

    def test_status_is_review_required(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        assert doc.metadata.report_status == ReportStatus.REVIEW_REQUIRED

    def test_drawing_number_propagated(self):
        plan = _minimal_plan(drawing_number="TEST-999")
        doc = build_manufacturing_plan_report(plan)
        assert doc.metadata.drawing_number == "TEST-999"

    def test_revision_propagated(self):
        plan = _minimal_plan(revision="B")
        doc = build_manufacturing_plan_report(plan)
        assert doc.metadata.revision == "B"

    def test_language_en(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan, language=ReportLanguage.EN)
        assert doc.metadata.language == ReportLanguage.EN

    def test_language_tr(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan, language=ReportLanguage.TR)
        assert doc.metadata.language == ReportLanguage.TR

    def test_units_metric(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan, units=ReportUnits.METRIC)
        assert doc.metadata.units == ReportUnits.METRIC

    def test_disclaimer_contains_draft(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan, language=ReportLanguage.EN)
        assert "DRAFT" in doc.disclaimer

    def test_disclaimer_tr_contains_taslak(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan, language=ReportLanguage.TR)
        assert "TASLAK" in doc.disclaimer

    def test_sections_not_empty(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        assert len(doc.sections) > 0

    def test_disclaimer_section_present(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        section_ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in section_ids

    def test_plan_info_section_present(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        section_ids = [s.section_id for s in doc.sections]
        assert "plan_info" in section_ids

    def test_disclaimer_section_has_warning_box(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        disc_section = next(s for s in doc.sections if s.section_id == "disclaimer")
        warning_items = [c for c in disc_section.content if isinstance(c, ReportWarningBox)]
        assert len(warning_items) >= 1

    def test_custom_report_id_propagated(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan, report_id="CUSTOM-123")
        assert doc.metadata.report_id == "CUSTOM-123"

    def test_auto_report_id_format(self):
        plan = _minimal_plan()
        doc = build_manufacturing_plan_report(plan)
        assert doc.metadata.report_id.startswith("RPT-")

    def test_plan_not_modified(self):
        plan = _minimal_plan(drawing_number="ORIG")
        _ = build_manufacturing_plan_report(plan)
        assert plan.drawing_number == "ORIG"

    def test_global_state_not_changed(self):
        plan = _minimal_plan()
        _ = build_manufacturing_plan_report(plan)
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False
