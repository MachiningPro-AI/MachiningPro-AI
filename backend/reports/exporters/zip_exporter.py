"""ZIP exporter — bundles all report export formats into a single ZIP archive.

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
"""
from __future__ import annotations

import zipfile
from io import BytesIO

from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportBundle,
    ReportDocument,
    ReportExportItem,
)

_MIME = "application/zip"


def export_zip(doc: ReportDocument, bundle: ReportBundle) -> ReportExportItem:
    """Bundle all items in bundle into a ZIP archive.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for item in bundle.items:
            if item.format != ExportFormat.ZIP:
                zf.writestr(item.filename, item.content)
    buf.seek(0)

    dn = doc.metadata.drawing_number or "unknown"
    filename = f"MachiningPro_Report_{_safe_name(dn)}_{doc.metadata.generated_at[:10]}.zip"
    return ReportExportItem(
        format=ExportFormat.ZIP,
        filename=filename,
        content=buf.getvalue(),
        mime_type=_MIME,
    )


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:40]
