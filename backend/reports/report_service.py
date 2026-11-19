"""Central report generation service.

Entry point for all report generation. Dispatches to builders and exporters.

Safety invariants (enforced, never bypassed):
  REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always
  IS_DISPATCHABLE=False always
  PRODUCTION_RELEASED=False always
  AUTO_APPROVED=False always
"""
from __future__ import annotations

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

# ---------------------------------------------------------------------------
# Safety constants
# ---------------------------------------------------------------------------

REPORT_SERVICE_IS_DISPATCHABLE: bool = False
REPORT_SERVICE_PRODUCTION_RELEASED: bool = False
REPORT_SERVICE_AUTO_APPROVED: bool = False
REPORT_SERVICE_REVIEW_REQUIRED: bool = True

# Available report types with their supported formats
REPORT_TYPES = [
    {
        "id": "MANUFACTURING_PLAN",
        "label_en": "Full Manufacturing Report",
        "label_tr": "Tam İmalat Raporu",
        "description_en": (
            "Operations, tools, machines, cutting parameters, "
            "inspection, control plan, open items"
        ),
        "description_tr": (
            "Operasyonlar, takımlar, tezgahlar, kesme parametreleri, "
            "muayene, kontrol planı, açık maddeler"
        ),
        "supported_formats": ["PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"],
    },
]


def generate_manufacturing_plan_report(
    plan: ManufacturingPlan,
    formats: list[ExportFormat],
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
) -> ReportBundle:
    """Generate a full manufacturing plan report in the requested formats.

    The source plan is NEVER modified.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.

    Args:
        plan: Source ManufacturingPlan — read-only, never modified.
        formats: List of ExportFormat values to generate.
        language: Report language (EN or TR).
        units: Report units (METRIC or IMPERIAL).
        report_id: Optional stable report ID for reproducibility.

    Returns:
        ReportBundle containing one ReportExportItem per requested format.
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
        # ZIP bundles all other formats; generate non-ZIP items first if not already present
        non_zip = [f for f in formats if f != ExportFormat.ZIP]
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
