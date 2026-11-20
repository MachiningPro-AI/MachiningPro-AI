"""i18n tests for the reporting module.

MUST 19: TR/EN language separation.
No TR strings in EN reports, no EN strings in TR reports (for section titles).
Engineering values unchanged across language switch.
"""
from __future__ import annotations

import json

from backend.manufacturing_plan.models import ManufacturingPlan
from backend.reports.builders.full_manufacturing_report import (
    build_full_manufacturing_report,
)
from backend.reports.builders.synthetic_qualification_report import (
    build_synthetic_qualification_report,
)
from backend.reports.models import (
    ExportFormat,
    ReportLanguage,
    ReportUnits,
)
from backend.reports.report_service import generate_full_manufacturing_report


def _plan() -> ManufacturingPlan:
    return ManufacturingPlan(
        plan_id="P-I18N-TEST",
        source_id="W-I18N",
        drawing_number="DWG-I18N",
        revision="A",
        part_id="PART-I18N",
    )


# ---------------------------------------------------------------------------
# EN section titles — must NOT contain key Turkish-specific words
# ---------------------------------------------------------------------------

_TR_ONLY_WORDS = ["Ozeti", "Parca", "Bilgi", "Tezgah", "Takim", "Kesme", "Surec",
                  "Uyari", "Blok", "Ozet", "Topoloji", "Olculer", "Tolerans",
                  "Malzeme", "Maliyet", "Teklif", "Kaynak", "Muhendis"]


class TestEnLanguageNoleak:
    def test_executive_summary_title_en_no_tr(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.EN)
        sec = next(s for s in doc.sections if s.section_id == "executive_summary")
        for word in _TR_ONLY_WORDS:
            assert word not in sec.title, \
                f"TR word '{word}' found in EN executive_summary title: {sec.title}"

    def test_part_info_title_en_no_tr(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.EN)
        sec = next(s for s in doc.sections if s.section_id == "part_info")
        for word in _TR_ONLY_WORDS:
            assert word not in sec.title, \
                f"TR word '{word}' in EN part_info title: {sec.title}"

    def test_provenance_title_en_no_tr(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.EN)
        sec = next(s for s in doc.sections if s.section_id == "provenance")
        for word in _TR_ONLY_WORDS:
            assert word not in sec.title, \
                f"TR word '{word}' in EN provenance title: {sec.title}"

    def test_readiness_title_en_no_tr(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.EN)
        sec = next(s for s in doc.sections if s.section_id == "readiness")
        for word in _TR_ONLY_WORDS:
            assert word not in sec.title, \
                f"TR word '{word}' in EN readiness title: {sec.title}"

    def test_disclaimer_en_draft(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.EN)
        assert "DRAFT" in doc.disclaimer
        assert "TASLAK" not in doc.disclaimer


# ---------------------------------------------------------------------------
# TR section titles — must NOT contain key English-specific words
# ---------------------------------------------------------------------------

_EN_ONLY_WORDS = ["Executive", "Summary", "Information", "Process", "Machine",
                  "Selection", "Warnings", "Blockers", "Provenance", "Readiness",
                  "Verification", "Inspection", "Cutting", "Parameters", "Features",
                  "Topology", "Dimensions", "Tolerances", "Material", "Analysis",
                  "Recommended"]


class TestTrLanguageNoleak:
    def test_executive_summary_title_tr_no_en_key_words(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.TR)
        sec = next(s for s in doc.sections if s.section_id == "executive_summary")
        # Should contain Turkish words like "Ozet" or "Yonetici"
        assert any(word in sec.title for word in ["Ozet", "Yonetici"]), \
            f"TR executive_summary title not in Turkish: {sec.title}"

    def test_part_info_title_tr_has_turkish(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.TR)
        sec = next(s for s in doc.sections if s.section_id == "part_info")
        assert any(word in sec.title for word in ["Parca", "Proje", "Bilgi"]), \
            f"TR part_info title not in Turkish: {sec.title}"

    def test_disclaimer_tr_taslak(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.TR)
        assert "TASLAK" in doc.disclaimer
        assert "DRAFT" not in doc.disclaimer

    def test_disclaimer_tr_dispatchable_hayir(self):
        doc = build_full_manufacturing_report(_plan(), language=ReportLanguage.TR)
        assert "HAYIR" in doc.disclaimer


# ---------------------------------------------------------------------------
# Engineering values must not change with language switch
# ---------------------------------------------------------------------------

class TestEngValuesUnchangedWithLanguage:
    def test_part_id_same_en_vs_tr(self):
        plan = _plan()
        doc_en = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        doc_tr = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        assert doc_en.metadata.part_reference == doc_tr.metadata.part_reference

    def test_drawing_number_same_en_vs_tr(self):
        plan = _plan()
        doc_en = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        doc_tr = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        assert doc_en.metadata.drawing_number == doc_tr.metadata.drawing_number

    def test_revision_same_en_vs_tr(self):
        plan = _plan()
        doc_en = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        doc_tr = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        assert doc_en.metadata.revision == doc_tr.metadata.revision

    def test_safety_flags_same_en_vs_tr(self):
        plan = _plan()
        doc_en = build_full_manufacturing_report(plan, language=ReportLanguage.EN)
        doc_tr = build_full_manufacturing_report(plan, language=ReportLanguage.TR)
        assert doc_en.metadata.is_dispatchable == doc_tr.metadata.is_dispatchable
        assert doc_en.metadata.production_released == doc_tr.metadata.production_released
        assert doc_en.metadata.auto_approved == doc_tr.metadata.auto_approved


# ---------------------------------------------------------------------------
# JSON export — language field propagated
# ---------------------------------------------------------------------------

class TestJsonLanguagePropagation:
    def test_json_language_en(self):
        plan = _plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], language=ReportLanguage.EN
        )
        data = json.loads(bundle.get(ExportFormat.JSON).content)
        assert data["language"] == "EN"

    def test_json_language_tr(self):
        plan = _plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], language=ReportLanguage.TR
        )
        data = json.loads(bundle.get(ExportFormat.JSON).content)
        assert data["language"] == "TR"


# ---------------------------------------------------------------------------
# Units propagation
# ---------------------------------------------------------------------------

class TestUnitsPropagation:
    def test_json_units_metric(self):
        plan = _plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], units=ReportUnits.METRIC
        )
        data = json.loads(bundle.get(ExportFormat.JSON).content)
        assert data["units"] == "METRIC"

    def test_json_units_imperial(self):
        plan = _plan()
        bundle = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], units=ReportUnits.IMPERIAL
        )
        data = json.loads(bundle.get(ExportFormat.JSON).content)
        assert data["units"] == "IMPERIAL"

    def test_plan_state_unchanged_after_imperial_export(self):
        plan = _plan()
        original = plan.drawing_number
        _ = generate_full_manufacturing_report(
            plan, formats=[ExportFormat.JSON], units=ReportUnits.IMPERIAL
        )
        assert plan.drawing_number == original


# ---------------------------------------------------------------------------
# Synth qual report i18n
# ---------------------------------------------------------------------------

class TestSynthQualReportI18n:
    def test_synth_disclaimer_en_draft(self):
        doc = build_synthetic_qualification_report({}, language=ReportLanguage.EN)
        assert "DRAFT" in doc.disclaimer

    def test_synth_disclaimer_tr_taslak(self):
        doc = build_synthetic_qualification_report({}, language=ReportLanguage.TR)
        assert "TASLAK" in doc.disclaimer

    def test_synth_language_en_metadata(self):
        doc = build_synthetic_qualification_report({}, language=ReportLanguage.EN)
        assert doc.metadata.language == ReportLanguage.EN

    def test_synth_language_tr_metadata(self):
        doc = build_synthetic_qualification_report({}, language=ReportLanguage.TR)
        assert doc.metadata.language == ReportLanguage.TR
