"""Central report generation service.

Entry point for all report generation. Dispatches to builders and exporters.

Safety invariants (enforced, never bypassed):
  REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always
  IS_DISPATCHABLE=False always
  PRODUCTION_RELEASED=False always
  AUTO_APPROVED=False always
"""
from __future__ import annotations

from typing import Any

from backend.manufacturing_plan.models import ManufacturingPlan
from backend.reports.builders.full_manufacturing_report import (
    build_full_manufacturing_report,
)
from backend.reports.builders.manufacturing_plan_report import (
    build_manufacturing_plan_report,
)
from backend.reports.builders.synthetic_qualification_report import (
    build_synthetic_qualification_report,
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
    ReportDocument,
    ReportLanguage,
    ReportUnits,
)

# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------

REPORT_SERVICE_IS_DISPATCHABLE: bool = False
REPORT_SERVICE_PRODUCTION_RELEASED: bool = False
REPORT_SERVICE_AUTO_APPROVED: bool = False
REPORT_SERVICE_REVIEW_REQUIRED: bool = True

# ---------------------------------------------------------------------------
# Report type registry — MUST 6
# ---------------------------------------------------------------------------

REPORT_TYPES = [
    {
        "id": "FULL_MANUFACTURING_REPORT",
        "label_en": "Full Manufacturing Report (28 sections)",
        "label_tr": "Tam Imalat Raporu (28 bolum)",
        "description_en": (
            "Comprehensive 28-section report: part info, process plan, "
            "machine/tool selection, cutting parameters, verification, "
            "cost, RFQ, warnings, provenance, readiness"
        ),
        "description_tr": (
            "Kapsamli 28 bolumlu rapor: parca bilgisi, surec plani, "
            "tezgah/takim secimi, kesme parametreleri, dogrulama, "
            "maliyet, teklif, uyarilar, kaynak, hazirlik"
        ),
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": [
            "disclaimer", "executive_summary", "part_info", "input_files",
            "source_integrity", "drawing_analysis", "cad_geometry", "topology",
            "features", "dimensions", "tolerances", "material", "process_plan",
            "machine_selection", "tool_selection", "cutting_parameters",
            "wcs_setup", "cam_strategy", "toolpath_summary", "verification",
            "collision", "simulation", "cost_analysis", "rfq_summary",
            "warnings", "provenance", "engineering_status", "readiness",
            "next_actions", "control_plan",
        ],
    },
    {
        "id": "MANUFACTURING_PLAN",
        "label_en": "Manufacturing Plan Report",
        "label_tr": "Imalat Plani Raporu",
        "description_en": (
            "Operations, tools, machines, cutting parameters, "
            "inspection, control plan, open items"
        ),
        "description_tr": (
            "Operasyonlar, takimlar, tezgahlar, kesme parametreleri, "
            "muayene, kontrol plani, acik maddeler"
        ),
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": [
            "disclaimer", "plan_info", "operations", "tools", "machines",
            "parameters", "inspection", "control_plan", "open_items",
        ],
    },
    {
        "id": "SYNTHETIC_QUALIFICATION_REPORT",
        "label_en": "Synthetic Qualification Report",
        "label_tr": "Sentetik Kalifikasyon Raporu",
        "description_en": (
            "Expected vs Actual, feature results, process results, "
            "defects, final verdict"
        ),
        "description_tr": (
            "Beklenen - Gerceklesen, ozellik sonuclari, surec sonuclari, "
            "hatalar, son karar"
        ),
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": [
            "disclaimer", "summary", "expected_vs_actual", "feature_results",
            "process_results", "format_results", "defects", "verdict",
        ],
    },
    {
        "id": "PART_ANALYSIS_REPORT",
        "label_en": "Part Analysis Report",
        "label_tr": "Parca Analiz Raporu",
        "description_en": "Part geometry, features, dimensions, tolerances and material",
        "description_tr": "Parca geometrisi, ozellikler, olcular, toleranslar ve malzeme",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": [
            "disclaimer", "part_info", "cad_geometry", "features",
            "dimensions", "tolerances", "material",
        ],
    },
    {
        "id": "DRAWING_ANALYSIS_REPORT",
        "label_en": "Drawing Analysis Report",
        "label_tr": "Cizim Analiz Raporu",
        "description_en": "Drawing extraction results, GD&T, dimensions, annotations",
        "description_tr": "Cizim cikarma sonuclari, GD&T, olcular, aciklamalar",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": [
            "disclaimer", "drawing_analysis", "dimensions", "tolerances",
        ],
    },
    {
        "id": "CAD_INTEROPERABILITY_REPORT",
        "label_en": "CAD Interoperability Report",
        "label_tr": "CAD Birlikte Calisabilirlik Raporu",
        "description_en": "STEP/IGES/DXF import results, topology, B-Rep quality",
        "description_tr": "STEP/IGES/DXF iceri aktarma sonuclari, topoloji, B-Rep kalitesi",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": [
            "disclaimer", "input_files", "source_integrity",
            "cad_geometry", "topology",
        ],
    },
    {
        "id": "FEATURE_ANALYSIS_REPORT",
        "label_en": "Feature Analysis Report",
        "label_tr": "Ozellik Analiz Raporu",
        "description_en": "Manufacturing feature recognition results",
        "description_tr": "Imalat ozellik tanima sonuclari",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "features"],
    },
    {
        "id": "PROCESS_PLAN_REPORT",
        "label_en": "Process Plan Report",
        "label_tr": "Surec Plani Raporu",
        "description_en": "Process routing, operation sequence, setup sequence",
        "description_tr": "Surec rotasi, operasyon sirasi, baglama sirasi",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "process_plan", "wcs_setup"],
    },
    {
        "id": "MACHINE_SELECTION_REPORT",
        "label_en": "Machine Selection Report",
        "label_tr": "Tezgah Secim Raporu",
        "description_en": "Machine assignments, capabilities, utilization",
        "description_tr": "Tezgah atamalari, kapasiteler, kullanim",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "machine_selection"],
    },
    {
        "id": "TOOL_SELECTION_REPORT",
        "label_en": "Tool Selection Report",
        "label_tr": "Takim Secim Raporu",
        "description_en": "Tool assignments, holders, quantities",
        "description_tr": "Takim atamalari, tutucular, miktarlar",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "tool_selection"],
    },
    {
        "id": "CUTTING_PARAMETERS_REPORT",
        "label_en": "Cutting Parameters Report",
        "label_tr": "Kesme Parametreleri Raporu",
        "description_en": "Vc, fz, ap, ae, RPM, feed rate per operation",
        "description_tr": "Vc, fz, ap, ae, devir, ilerleme hizi - operasyon bazinda",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "cutting_parameters"],
    },
    {
        "id": "CAM_REPORT",
        "label_en": "CAM Report",
        "label_tr": "CAM Raporu",
        "description_en": "CAM strategy, operation parameters, tool assignments",
        "description_tr": "CAM stratejisi, operasyon parametreleri, takim atamalari",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "cam_strategy", "cutting_parameters"],
    },
    {
        "id": "TOOLPATH_REPORT",
        "label_en": "Toolpath Report",
        "label_tr": "Takim Yolu Raporu",
        "description_en": "Toolpath summary, cycle times, verification",
        "description_tr": "Takim yolu ozeti, dongu sureleri, dogrulama",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "toolpath_summary", "verification"],
    },
    {
        "id": "VERIFICATION_REPORT",
        "label_en": "Verification Report",
        "label_tr": "Dogrulama Raporu",
        "description_en": "Inspection plan, control plan, measurement results",
        "description_tr": "Muayene plani, kontrol plani, olcum sonuclari",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "verification", "control_plan"],
    },
    {
        "id": "SIMULATION_REPORT",
        "label_en": "Simulation Report",
        "label_tr": "Simulasyon Raporu",
        "description_en": "Simulation results, collision analysis, envelope",
        "description_tr": "Simulasyon sonuclari, carpisma analizi, zarf",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "simulation", "collision"],
    },
    {
        "id": "COST_ANALYSIS_REPORT",
        "label_en": "Cost Analysis Report",
        "label_tr": "Maliyet Analiz Raporu",
        "description_en": "Material, machine time, labor, tooling, total cost",
        "description_tr": "Malzeme, tezgah suresi, is gucu, takim, toplam maliyet",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "cost_analysis"],
    },
    {
        "id": "RFQ_REPORT",
        "label_en": "RFQ Report",
        "label_tr": "Teklif (RFQ) Raporu",
        "description_en": "RFQ summary, pricing breakdown, delivery schedule",
        "description_tr": "Teklif ozeti, fiyat dagilimi, teslimat takvimi",
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
        "section_ids": ["disclaimer", "rfq_summary", "cost_analysis"],
    },
]


# ---------------------------------------------------------------------------
# Export bundle builder
# ---------------------------------------------------------------------------

def _build_bundle(
    doc: ReportDocument,
    formats: list[ExportFormat],
) -> ReportBundle:
    bundle = ReportBundle(document=doc, engineering_state_changed=False)

    if ExportFormat.PDF in formats:
        bundle.items.append(export_pdf(doc))
    if ExportFormat.DOCX in formats:
        bundle.items.append(export_docx(doc))
    if ExportFormat.XLSX in formats:
        bundle.items.append(export_xlsx(doc))
    if ExportFormat.CSV in formats:
        bundle.items.append(export_csv(doc))
    if ExportFormat.JSON in formats:
        bundle.items.append(export_json(doc))

    if ExportFormat.ZIP in formats:
        # ZIP bundles all other formats; generate non-ZIP items first.
        # When ZIP is the only requested format, default to all five formats.
        non_zip = [f for f in formats if f != ExportFormat.ZIP]
        if not non_zip:
            non_zip = [ExportFormat.PDF, ExportFormat.DOCX, ExportFormat.XLSX,
                       ExportFormat.CSV, ExportFormat.JSON]
        for fmt in non_zip:
            if bundle.get(fmt) is None:
                if fmt == ExportFormat.PDF:
                    bundle.items.append(export_pdf(doc))
                elif fmt == ExportFormat.DOCX:
                    bundle.items.append(export_docx(doc))
                elif fmt == ExportFormat.XLSX:
                    bundle.items.append(export_xlsx(doc))
                elif fmt == ExportFormat.CSV:
                    bundle.items.append(export_csv(doc))
                elif fmt == ExportFormat.JSON:
                    bundle.items.append(export_json(doc))
        bundle.items.append(export_zip(doc, bundle))

    assert not bundle.engineering_state_changed
    return bundle


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_manufacturing_plan_report(
    plan: ManufacturingPlan,
    formats: list[ExportFormat],
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
    section_ids: list[str] | None = None,
) -> ReportBundle:
    """Generate a manufacturing plan report in the requested formats.

    The source plan is NEVER modified.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED
    assert not REPORT_SERVICE_IS_DISPATCHABLE
    assert not REPORT_SERVICE_PRODUCTION_RELEASED
    assert not REPORT_SERVICE_AUTO_APPROVED
    assert REPORT_SERVICE_REVIEW_REQUIRED

    doc = build_manufacturing_plan_report(
        plan,
        language=language,
        units=units,
        report_id=report_id,
    )
    # Apply section filter if requested
    if section_ids is not None:
        always = {"disclaimer"}
        doc.sections[:] = [
            s for s in doc.sections
            if s.section_id in always or s.section_id in section_ids
        ]

    return _build_bundle(doc, formats)


def generate_full_manufacturing_report(
    plan: ManufacturingPlan,
    formats: list[ExportFormat],
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
    section_ids: list[str] | None = None,
) -> ReportBundle:
    """Generate the full 28-section manufacturing report.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    doc = build_full_manufacturing_report(
        plan,
        language=language,
        units=units,
        report_id=report_id,
        section_ids=section_ids,
    )
    return _build_bundle(doc, formats)


def generate_synthetic_qualification_report(
    qual_data: dict[str, Any],
    formats: list[ExportFormat],
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
    section_ids: list[str] | None = None,
) -> ReportBundle:
    """Generate a synthetic qualification report.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    doc = build_synthetic_qualification_report(
        qual_data,
        language=language,
        units=units,
        report_id=report_id,
        section_ids=section_ids,
    )
    return _build_bundle(doc, formats)
