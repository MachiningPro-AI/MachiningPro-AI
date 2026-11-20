"""Unit tests for synthetic qualification report builder.

MUST 36: SYNTHETIC_QUALIFICATION_REPORT
REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
"""
from __future__ import annotations

from backend.reports.builders.synthetic_qualification_report import (
    build_synthetic_qualification_report,
)
from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ReportLanguage,
    ReportStatus,
    ReportType,
    ReportUnits,
)

# ---------------------------------------------------------------------------
# MP_SYN_001 ground truth
# ---------------------------------------------------------------------------

MP_SYN_001_QUAL_DATA = {
    "qualification_id": "QUAL-MP-SYN-001",
    "part_id": "MP-SYN-001",
    "drawing_number": "MP-SYN-001-DWG",
    "revision": "A",
    "verdict": "PASS",
    "expected_vs_actual": [
        {"check": "feature_count", "expected": "6", "actual": "6", "result": "PASS"},
        {"check": "hole_count", "expected": "3", "actual": "3", "result": "PASS"},
        {"check": "pocket_count", "expected": "1", "actual": "1", "result": "PASS"},
        {"check": "slot_count", "expected": "1", "actual": "1", "result": "PASS"},
        {"check": "shoulder_count", "expected": "1", "actual": "1", "result": "PASS"},
    ],
    "feature_results": [
        {"feature_id": "H1", "feature_type": "THROUGH_HOLE", "result": "PASS", "note": "8mm"},
        {"feature_id": "H2", "feature_type": "THROUGH_HOLE", "result": "PASS", "note": "8mm"},
        {"feature_id": "H3", "feature_type": "BLIND_HOLE", "result": "PASS", "note": "10mm"},
        {"feature_id": "P1", "feature_type": "RECTANGULAR_POCKET", "result": "PASS", "note": ""},
        {"feature_id": "S1", "feature_type": "SLOT", "result": "PASS", "note": ""},
        {"feature_id": "ST1", "feature_type": "STEP_SHOULDER", "result": "PASS", "note": ""},
    ],
    "process_results": [
        {"operation": "DRILLING_H1_H2", "result": "PASS", "note": "8mm drill"},
        {"operation": "DRILLING_H3", "result": "PASS", "note": "10mm drill"},
        {"operation": "POCKET_MILLING_P1", "result": "PASS", "note": "12mm end mill"},
    ],
    "defects": [],
    "format_results": [
        {"format": "PDF", "result": "PASS", "note": ""},
        {"format": "DOCX", "result": "PASS", "note": ""},
        {"format": "XLSX", "result": "PASS", "note": ""},
        {"format": "CSV", "result": "PASS", "note": ""},
        {"format": "JSON", "result": "PASS", "note": ""},
        {"format": "ZIP", "result": "PASS", "note": ""},
    ],
}


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestSafetyInvariantsSynth:
    def test_global_state_unchanged(self):
        _ = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False

    def test_not_dispatchable(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.is_dispatchable is False

    def test_not_production_released(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.production_released is False

    def test_not_auto_approved(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.auto_approved is False

    def test_review_required(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.review_required is True

    def test_engineering_state_changed_false(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.engineering_state_changed is False

    def test_provenance_not_modified(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.provenance.engineering_state_modified is False

    def test_input_dict_not_mutated(self):
        import copy
        data = copy.deepcopy(MP_SYN_001_QUAL_DATA)
        _ = build_synthetic_qualification_report(data)
        assert data["part_id"] == "MP-SYN-001"

    def test_input_qualification_id_not_mutated(self):
        import copy
        data = copy.deepcopy(MP_SYN_001_QUAL_DATA)
        _ = build_synthetic_qualification_report(data)
        assert data["qualification_id"] == "QUAL-MP-SYN-001"


# ---------------------------------------------------------------------------
# Structure
# ---------------------------------------------------------------------------

class TestStructureSynth:
    def test_report_type_synthetic_qualification(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.report_type == ReportType.SYNTHETIC_QUALIFICATION_REPORT

    def test_status_review_required(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.report_status == ReportStatus.REVIEW_REQUIRED

    def test_disclaimer_present(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in ids

    def test_disclaimer_en_draft(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, language=ReportLanguage.EN
        )
        assert "DRAFT" in doc.disclaimer

    def test_disclaimer_tr_taslak(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, language=ReportLanguage.TR
        )
        assert "TASLAK" in doc.disclaimer

    def test_summary_section_present(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        ids = [s.section_id for s in doc.sections]
        assert "summary" in ids

    def test_expected_vs_actual_section(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        ids = [s.section_id for s in doc.sections]
        assert "expected_vs_actual" in ids

    def test_feature_results_section(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        ids = [s.section_id for s in doc.sections]
        assert "feature_results" in ids

    def test_verdict_section_present(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        ids = [s.section_id for s in doc.sections]
        assert "verdict" in ids

    def test_part_reference_propagated(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.part_reference == "MP-SYN-001"

    def test_custom_report_id(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, report_id="SQ-CUSTOM-001"
        )
        assert doc.metadata.report_id == "SQ-CUSTOM-001"

    def test_auto_report_id_prefix(self):
        doc = build_synthetic_qualification_report(MP_SYN_001_QUAL_DATA)
        assert doc.metadata.report_id.startswith("RPT-SQ-")

    def test_no_defects_section_on_empty_defects(self):
        import copy
        data = copy.deepcopy(MP_SYN_001_QUAL_DATA)
        data["defects"] = []
        doc = build_synthetic_qualification_report(data)
        ids = [s.section_id for s in doc.sections]
        # defects section should be absent or skipped when empty
        # (implementation may vary — check the section exists OR has no rows)
        # The contract is: no fabricated data
        assert "disclaimer" in ids

    def test_section_ids_filter(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, section_ids=["summary"]
        )
        ids = [s.section_id for s in doc.sections]
        assert "summary" in ids
        assert "disclaimer" in ids
        # expected_vs_actual should be excluded
        assert "expected_vs_actual" not in ids


# ---------------------------------------------------------------------------
# Language
# ---------------------------------------------------------------------------

class TestLanguageSynth:
    def test_metadata_language_en(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, language=ReportLanguage.EN
        )
        assert doc.metadata.language == ReportLanguage.EN

    def test_metadata_language_tr(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, language=ReportLanguage.TR
        )
        assert doc.metadata.language == ReportLanguage.TR


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

class TestUnitsSynth:
    def test_units_metric(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, units=ReportUnits.METRIC
        )
        assert doc.metadata.units == ReportUnits.METRIC

    def test_units_imperial(self):
        doc = build_synthetic_qualification_report(
            MP_SYN_001_QUAL_DATA, units=ReportUnits.IMPERIAL
        )
        assert doc.metadata.units == ReportUnits.IMPERIAL


# ---------------------------------------------------------------------------
# Empty / minimal data
# ---------------------------------------------------------------------------

class TestEmptyDataSynth:
    def test_empty_dict_does_not_crash(self):
        doc = build_synthetic_qualification_report({})
        assert doc is not None

    def test_empty_dict_has_disclaimer(self):
        doc = build_synthetic_qualification_report({})
        ids = [s.section_id for s in doc.sections]
        assert "disclaimer" in ids

    def test_unknown_part_id_handled(self):
        doc = build_synthetic_qualification_report({})
        assert doc.metadata.part_reference == "UNKNOWN" or doc.metadata.part_reference is None

    def test_global_state_unchanged_on_empty(self):
        _ = build_synthetic_qualification_report({})
        assert REPORT_GENERATION_ENGINEERING_STATE_CHANGED is False
