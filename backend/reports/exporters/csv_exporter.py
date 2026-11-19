"""CSV exporter — exports all ReportTable sections as CSV bytes.

One CSV file per report (all tables concatenated with section headers).
CSV injection guard applied to all cells.
"""
from __future__ import annotations

import csv
import io

from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportDocument,
    ReportExportItem,
    ReportTable,
)

_MIME = "text/csv; charset=utf-8"
_INJECT_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
_CSV_BOM = "﻿"


def _guard(value: str) -> str:
    if value and value[0] in _INJECT_PREFIXES:
        return "'" + value
    return value


def export_csv(doc: ReportDocument) -> ReportExportItem:
    """Export all table sections as CSV.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    buf = io.StringIO()
    writer = csv.writer(buf)

    # Header row: report metadata
    writer.writerow(["# MachiningPro AI — Manufacturing Report (CSV Export)"])
    writer.writerow(["# report_id", doc.metadata.report_id])
    writer.writerow(["# drawing_number", doc.metadata.drawing_number or "—"])
    writer.writerow(["# revision", doc.metadata.revision or "—"])
    writer.writerow(["# generated_at", doc.metadata.generated_at])
    writer.writerow(["# language", doc.metadata.language])
    writer.writerow(["# IS_DISPATCHABLE=NO", "PRODUCTION_RELEASED=NO", "AUTO_APPROVED=NO"])
    writer.writerow([])

    for section in doc.sections:
        for content_item in section.content:
            if isinstance(content_item, ReportTable):
                writer.writerow([f"# SECTION: {section.title}"])
                if content_item.caption:
                    writer.writerow([f"# {content_item.caption}"])
                writer.writerow([_guard(h) for h in content_item.headers])
                for row in content_item.rows:
                    writer.writerow([_guard(cell) for cell in row.cells])
                writer.writerow([])

    content = _CSV_BOM + buf.getvalue()
    dn = doc.metadata.drawing_number or "unknown"
    filename = f"MachiningPro_Report_{_safe_name(dn)}_{doc.metadata.generated_at[:10]}.csv"
    return ReportExportItem(
        format=ExportFormat.CSV,
        filename=filename,
        content=content.encode("utf-8-sig"),
        mime_type=_MIME,
    )


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:40]
