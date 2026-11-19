"""XLSX exporter — creates a professional multi-sheet Excel report.

Uses openpyxl (available in requirements).
One sheet per report section that contains a table.
Safety disclaimer on the cover sheet.

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
"""
from __future__ import annotations

from io import BytesIO

import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportDocument,
    ReportExportItem,
    ReportTable,
)

_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

# Color scheme
_HEADER_FILL = PatternFill("solid", fgColor="2E5090")
_WARN_FILL = PatternFill("solid", fgColor="FFF3CD")
_SAFETY_FILL = PatternFill("solid", fgColor="FEE2E2")
_ALT_FILL = PatternFill("solid", fgColor="F0F4FF")
_HEADER_FONT = Font(color="FFFFFF", bold=True, name="Calibri", size=10)
_TITLE_FONT = Font(bold=True, name="Calibri", size=14, color="2E5090")
_LABEL_FONT = Font(bold=True, name="Calibri", size=10)
_BODY_FONT = Font(name="Calibri", size=10)
_WARN_FONT = Font(bold=True, name="Calibri", size=10, color="92400E")
_SAFETY_FONT = Font(bold=True, name="Calibri", size=10, color="991B1B")

_THIN = Side(style="thin", color="D1D5DB")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)


def _auto_width(ws: openpyxl.worksheet.worksheet.Worksheet) -> None:
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = min(max(max_len + 2, 8), 50)


def _write_cover(ws: openpyxl.worksheet.worksheet.Worksheet, doc: ReportDocument) -> None:
    ws.title = "Cover"
    ws.column_dimensions["A"].width = 30
    ws.column_dimensions["B"].width = 50

    # Title
    ws["A1"] = "MachiningPro AI — Manufacturing Report"
    ws["A1"].font = _TITLE_FONT
    ws.merge_cells("A1:B1")
    ws.row_dimensions[1].height = 24

    # Safety disclaimer
    ws["A3"] = "⚠ SAFETY DISCLAIMER"
    ws["A3"].font = _SAFETY_FONT
    ws["A3"].fill = _SAFETY_FILL
    ws["B3"] = doc.disclaimer
    ws["B3"].font = _SAFETY_FONT
    ws["B3"].fill = _SAFETY_FILL
    ws["B3"].alignment = Alignment(wrap_text=True)
    ws.row_dimensions[3].height = 40

    # Metadata
    row = 5
    meta_items = [
        ("Report ID", doc.metadata.report_id),
        ("Drawing Number", doc.metadata.drawing_number or "—"),
        ("Revision", doc.metadata.revision or "—"),
        ("Part Reference", doc.metadata.part_reference or "—"),
        ("Generated At", doc.metadata.generated_at),
        ("Language", str(doc.metadata.language)),
        ("Units", str(doc.metadata.units)),
        ("Status", str(doc.metadata.report_status)),
        ("IS_DISPATCHABLE", "NO"),
        ("PRODUCTION_RELEASED", "NO"),
        ("AUTO_APPROVED", "NO"),
        ("REVIEW_REQUIRED", "YES"),
        ("ENGINEERING_STATE_CHANGED", "NO"),
    ]
    for label, value in meta_items:
        ws.cell(row=row, column=1, value=label).font = _LABEL_FONT
        ws.cell(row=row, column=2, value=value).font = _BODY_FONT
        row += 1


def _write_table_section(
    ws: openpyxl.worksheet.worksheet.Worksheet,
    title: str,
    table: ReportTable,
) -> None:
    ws.freeze_panes = "A2"

    # Section title row
    _title_cell = ws.cell(row=1, column=1, value=title)
    _title_cell.font = Font(bold=True, name="Calibri", size=12, color="2E5090")
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=max(len(table.headers), 1))

    # Header row
    header_row = 2
    for col_idx, header in enumerate(table.headers, start=1):
        cell = ws.cell(row=header_row, column=col_idx, value=header)
        cell.font = _HEADER_FONT
        cell.fill = _HEADER_FILL
        cell.border = _BORDER
        cell.alignment = Alignment(horizontal="center")

    # Data rows
    for row_idx, row_data in enumerate(table.rows, start=header_row + 1):
        fill = _ALT_FILL if row_idx % 2 == 1 else None
        for col_idx, cell_val in enumerate(row_data.cells, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=cell_val)
            cell.font = _BODY_FONT
            cell.border = _BORDER
            if fill:
                cell.fill = fill

    _auto_width(ws)


def export_xlsx(doc: ReportDocument) -> ReportExportItem:
    """Export ReportDocument as XLSX bytes.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    wb = openpyxl.Workbook()
    # Remove default sheet
    default_sheet = wb.active
    if default_sheet is not None:
        wb.remove(default_sheet)

    # Cover sheet
    cover_ws = wb.create_sheet("Cover")
    _write_cover(cover_ws, doc)

    # One sheet per table section
    sheet_names_used: set[str] = {"Cover"}
    for section in doc.sections:
        for content_item in section.content:
            if isinstance(content_item, ReportTable):
                # Safe sheet name (max 31 chars, no special chars)
                raw = section.title[:25]
                sheet_name = "".join(c if c.isalnum() or c in " _-" else "" for c in raw).strip()
                if not sheet_name:
                    sheet_name = section.section_id[:25]
                # Deduplicate
                base = sheet_name
                suffix = 2
                while sheet_name in sheet_names_used:
                    sheet_name = f"{base[:27]}_{suffix}"
                    suffix += 1
                sheet_names_used.add(sheet_name)

                ws = wb.create_sheet(sheet_name)
                _write_table_section(ws, section.title, content_item)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)

    dn = doc.metadata.drawing_number or "unknown"
    filename = f"MachiningPro_Report_{_safe_name(dn)}_{doc.metadata.generated_at[:10]}.xlsx"
    return ReportExportItem(
        format=ExportFormat.XLSX,
        filename=filename,
        content=buf.getvalue(),
        mime_type=_MIME,
    )


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:40]
