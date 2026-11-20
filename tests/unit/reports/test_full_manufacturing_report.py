"""Unit tests for the Full Manufacturing Report builder (28 sections).

MUST 7, MUST 8, MUST 9, MUST 15, MUST 16, MUST 17 — full report structure.
REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
"""
from __future__ import annotations

from backend.manufacturing_plan.models import (
    ManufacturingOperation,
    ManufacturingPlan,
    ManufacturingPlanMachine,
    ManufacturingPlanParameter,
    ManufacturingPlanTool,
    OpenItem,
    OpenItemCategory,
    OpenItemSeverity,
    OpenItemStatus,
)
from backend.reports.builders.full_manufacturing_report import (
    build_full_manufacturing_report,
)
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ReportLanguage,
    ReportStatus,
    ReportType,
    ReportUnits,
    ReportWarningBox,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_plan(**kwargs) -> ManufacturingPlan:
    defaults = dict(
        plan_id="P-M02-TEST",
        source_id="W-TEST-001",
        drawing_number="DWG-M02",
        revision="B",
        part_id="PART-M02",
    )
    defaults.update(kwargs)
    return ManufacturingPlan(**defaults)


def _op(op_id: str, op_no: int) -> ManufacturingOperation:
    return ManufacturingOperation(
        op_id=op_id, op_number=op_no, setup_id="S1", feature_id="F1",
        operation_type="DRILLING", machine_id="M1", machine_label="Haas VF-2",
        tool_id="T1", holder_id="H1",
        cutting_speed_m_min=120.0, feed_rate_mm_min=200.0, rpm=5000.0,
        ap_mm=5.0, ae_mm=None, coolant_note="Flood coolant",
        target_tolerance="H7", surface_finish="Ra 1.6",
        inspection_note="CMM", cycle_time_context=None,
        capability_context=None, surface_capability_context=None,
    )


def _machine(mid: str) -> ManufacturingPlanMachine:
    return ManufacturingPlanMachine(
        entry_id=mid, machine_id=mid, machine_label="Haas VF-2",
        machine_type="VMC", setup_ids=(), operation_ids=(),
    )


def _tool(tid: str) -> ManufacturingPlanTool:
    return ManufacturingPlanTool(
        entry_id=tid, tool_id=tid, tool_label="10mm Drill", tool_type="DRILL",
        holder_id="H1", holder_label="ER32 Collet", quantity_required=1,
        operation_ids=(),
    )


def _param(pid: str, op_id: str) -> ManufacturingPlanParameter:
    return ManufacturingPlanParameter(
        entry_id=pid, op_id=op_id, operation_type="DRILLING",
        material_iso_group="N", vc_m_min=120.0, fz_mm=0.1,
        ap_mm=5.0, ae_mm=None, feed_rate_mm_min=200.0, rpm=5000.0,
        source="MANUFACTURER_CATALOG", confidence="HIGH",
    )


def _blocking_item() -> OpenItem:
    return OpenItem(
        item_id="OI-01",
        category=OpenItemCategory.MISSING_MACHINE,
        severity=OpenItemSeverity.BLOCKING,
        description="Machine not assigned",
        status=OpenItemStatus.OPEN,
    )


def _advisory_item() -> OpenItem:
    return OpenItem(
        item_id="OI-02",
        category=OpenItemCategory.REVIEW_REQUIRED,
        severity=OpenItemSeverity.ADVISORY,
        description="Review surface finish requirement",
        status=OpenItemStatus.OPEN,
    )


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariants:
    def test_global_state_unchanged_after_build(self):
        plan = _minimal_plan()
        _ = build_full_manufacturing_report(plan)
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False

    def test_metadata_not_dispatchable(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.is_dispatchable is False

    def test_metadata_not_production_released(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.production_released is False

    def test_metadata_not_auto_approved(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.auto_approved is False

    def test_metadata_review_required(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.review_required is True

    def test_metadata_engineering_state_changed_false(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.engineering_state_changed is False

    def test_provenance_state_not_modified(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.provenance.engineering_state_modified is False

    def test_provenance_not_auto_approved(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.provenance.auto_approved is False

    def test_plan_not_mutated(self):
        plan = _minimal_plan(drawing_number="ORIG-DWG")
        _ = build_full_manufacturing_report(plan)
        assert plan.drawing_number == "ORIG-DWG"

    def test_plan_part_id_not_mutated(self):
        plan = _minimal_plan(part_id="ORIG-PART")
        _ = build_full_manufacturing_report(plan)
        assert plan.part_id == "ORIG-PART"


# ---------------------------------------------------------------------------
# Report type and structure
# ---------------------------------------------------------------------------

class TestReportTypeAndStructure:
    def test_report_type_full_manufacturing(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.report_type == ReportType.FULL_MANUFACTURING_REPORT

    def test_report_status_review_required(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.report_status == ReportStatus.REVIEW_REQUIRED

    def test_sections_not_empty(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert len(doc.sections) > 0

    def test_disclaimer_always_present(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in ids

    def test_executive_summary_present(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "executive_summary" in ids

    def test_provenance_section_present(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "provenance" in ids

    def test_engineering_status_section_present(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "engineering_status" in ids

    def test_readiness_section_present(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "readiness" in ids

    def test_disclaimer_contains_draft_warning(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        assert "DRAFT" in doc.disclaimer

    def test_disclaimer_tr_contains_taslak(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        assert "TASLAK" in doc.disclaimer

    def test_disclaimer_contains_no_dispatchable(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        assert "IS_DISPATCHABLE=NO" in doc.disclaimer

    def test_disclaimer_section_has_warning_box(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        disc = next(s for s in doc.sections if s.section_id == "disclaimer")
        assert any(isinstance(c, ReportWarningBox) for c in disc.content)

    def test_custom_report_id(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, report_id="CUSTOM-FMR-001")
        assert doc.metadata.report_id == "CUSTOM-FMR-001"

    def test_auto_report_id_starts_with_rpt(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.metadata.report_id.startswith("RPT-")


# ---------------------------------------------------------------------------
# Language — EN
# ---------------------------------------------------------------------------

class TestLanguageEN:
    def test_metadata_language_en(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        assert doc.metadata.language == ReportLanguage.EN

    def test_executive_summary_title_en(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        sec = next(s for s in doc.sections if s.section_id == "executive_summary")
        assert "Executive" in sec.title

    def test_warnings_section_title_en(self):
        plan = _minimal_plan()
        plan.open_items.append(_advisory_item())
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        sec = next((s for s in doc.sections if s.section_id == "warnings"), None)
        if sec:
            assert "Warnings" in sec.title or "Block" in sec.title


# ---------------------------------------------------------------------------
# Language — TR
# ---------------------------------------------------------------------------

class TestLanguageTR:
    def test_metadata_language_tr(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        assert doc.metadata.language == ReportLanguage.TR

    def test_executive_summary_title_tr(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        sec = next(s for s in doc.sections if s.section_id == "executive_summary")
        assert "Ozeti" in sec.title or "Ozet" in sec.title

    def test_part_info_title_tr(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        sec = next(s for s in doc.sections if s.section_id == "part_info")
        assert "Parca" in sec.title or "Bilgi" in sec.title

    def test_no_english_leak_in_tr_section_titles(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        # Check key sections that should be in Turkish
        tr_map = {
            "executive_summary": "Ozet",
            "part_info": "Parca",
        }
        for sid, keyword in tr_map.items():
            sec = next((s for s in doc.sections if s.section_id == sid), None)
            if sec:
                assert keyword in sec.title, f"Section {sid} not in Turkish: {sec.title}"


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

class TestUnits:
    def test_units_metric(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, units=ReportUnits.METRIC)
        assert doc.metadata.units == ReportUnits.METRIC

    def test_units_imperial(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan, units=ReportUnits.IMPERIAL)
        assert doc.metadata.units == ReportUnits.IMPERIAL

    def test_engineering_state_not_changed_on_imperial(self):
        plan = _minimal_plan()
        original_drawing = plan.drawing_number
        _ = build_full_manufacturing_report(plan, units=ReportUnits.IMPERIAL)
        assert plan.drawing_number == original_drawing
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False


# ---------------------------------------------------------------------------
# Data presence: operations, tools, machines, parameters
# ---------------------------------------------------------------------------

class TestDataSections:
    def test_process_plan_section_with_operations(self):
        plan = _minimal_plan()
        plan.operations.append(_op("OP-01", 1))
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "process_plan" in ids or "cam_strategy" in ids

    def test_machine_selection_section_with_machines(self):
        plan = _minimal_plan()
        plan.machine_list.append(_machine("M1"))
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "machine_selection" in ids

    def test_tool_selection_section_with_tools(self):
        plan = _minimal_plan()
        plan.tool_list.append(_tool("T1"))
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "tool_selection" in ids

    def test_cutting_params_section_with_parameters(self):
        plan = _minimal_plan()
        plan.parameter_table.append(_param("PA-01", "OP-01"))
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "cutting_parameters" in ids

    def test_warnings_section_with_open_items(self):
        plan = _minimal_plan()
        plan.open_items.append(_advisory_item())
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "warnings" in ids

    def test_no_machine_section_without_machines(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "machine_selection" not in ids

    def test_no_tool_section_without_tools(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "tool_selection" not in ids

    def test_no_warnings_section_without_open_items(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        ids = [s.section_id for s in doc.sections]
        assert "warnings" not in ids


# ---------------------------------------------------------------------------
# Readiness calculation
# ---------------------------------------------------------------------------

class TestReadiness:
    def test_blocked_when_blocking_items(self):
        plan = _minimal_plan()
        plan.open_items.append(_blocking_item())
        doc = build_full_manufacturing_report(plan)
        # readiness section should mention BLOCKED
        sec = next(s for s in doc.sections if s.section_id == "readiness")
        content_text = " ".join(
            str(c.body if hasattr(c, "body") else str(c))
            for c in sec.content
        )
        assert "BLOCKED" in content_text

    def test_no_blocking_items_on_minimal_plan(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        sec = next(s for s in doc.sections if s.section_id == "readiness")
        content_text = " ".join(
            str(c.body if hasattr(c, "body") else str(c))
            for c in sec.content
        )
        assert "BLOCKED" not in content_text


# ---------------------------------------------------------------------------
# Section selection filter
# ---------------------------------------------------------------------------

class TestSectionSelection:
    def test_section_ids_filter_excludes_other_sections(self):
        plan = _minimal_plan()
        plan.open_items.append(_advisory_item())
        doc = build_full_manufacturing_report(
            plan, section_ids=["executive_summary"]
        )
        ids = [s.section_id for s in doc.sections]
        assert "executive_summary" in ids
        # always_include sections are always present
        assert "disclaimer" in ids
        assert "engineering_status" in ids
        # warnings should be excluded
        assert "warnings" not in ids

    def test_section_ids_none_includes_all_available(self):
        plan = _minimal_plan()
        plan.open_items.append(_advisory_item())
        doc = build_full_manufacturing_report(plan, section_ids=None)
        ids = [s.section_id for s in doc.sections]
        assert "warnings" in ids

    def test_disclaimer_always_included_in_filter(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(
            plan, section_ids=["executive_summary"]
        )
        ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in ids

    def test_engineering_status_always_included_in_filter(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(
            plan, section_ids=["executive_summary"]
        )
        ids = [s.section_id for s in doc.sections]
        assert "engineering_status" in ids


# ---------------------------------------------------------------------------
# Provenance fields
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_provenance_source_type(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.provenance.source_type == "ManufacturingPlan"

    def test_provenance_source_id_matches_plan(self):
        plan = _minimal_plan(plan_id="P-XYZ-999")
        doc = build_full_manufacturing_report(plan)
        assert doc.provenance.source_id == "P-XYZ-999"

    def test_provenance_engineering_state_not_modified(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.provenance.engineering_state_modified is False

    def test_provenance_not_auto_approved(self):
        plan = _minimal_plan()
        doc = build_full_manufacturing_report(plan)
        assert doc.provenance.auto_approved is False
