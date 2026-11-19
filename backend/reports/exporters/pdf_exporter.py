"""PDF exporter — creates a professional A4 PDF report using fpdf2.

Safety disclaimer on every page footer.
REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
"""
from __future__ import annotations

from io import BytesIO

from fpdf import FPDF, XPos, YPos

from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportDocument,
    ReportExportItem,
    ReportKeyValue,
    ReportTable,
    ReportText,
    ReportWarningBox,
)

_MIME = "application/pdf"

# fpdf2's built-in Helvetica is Latin-1 only — strip/replace non-Latin-1 characters
def _safe(text: str) -> str:
    """Replace characters outside Latin-1 with ASCII equivalents."""
    return (
        text
        .replace("—", "--")   # em dash
        .replace("–", "-")    # en dash
        .replace("’", "'")    # right single quotation
        .replace("‘", "'")    # left single quotation
        .replace("“", '"')    # left double quotation
        .replace("”", '"')    # right double quotation
        .replace("⚠", "[!]")  # warning sign ⚠
        .replace("°", " deg") # degree sign
        .encode("latin-1", errors="replace").decode("latin-1")
    )


# Color palette
_BRAND_R, _BRAND_G, _BRAND_B = 46, 80, 144        # #2E5090
_WARN_R, _WARN_G, _WARN_B = 146, 64, 14           # #92400E
_SAFETY_R, _SAFETY_G, _SAFETY_B = 153, 27, 27     # #991B1B
_LIGHT_R, _LIGHT_G, _LIGHT_B = 240, 244, 255      # #F0F4FF
_HEADER_R, _HEADER_G, _HEADER_B = 46, 80, 144
_TEXT_R, _TEXT_G, _TEXT_B = 30, 41, 59            # #1E293B
_GRAY_R, _GRAY_G, _GRAY_B = 107, 114, 128         # #6B7280


class _MachiningProPDF(FPDF):
    """Custom FPDF with header and safety footer."""

    _doc: ReportDocument

    def __init__(self, doc: ReportDocument) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self._doc = doc
        self.set_margins(15, 20, 15)
        self.set_auto_page_break(auto=True, margin=22)

    def header(self) -> None:
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(_BRAND_R, _BRAND_G, _BRAND_B)
        self.cell(
            0, 6, "MachiningPro AI - Manufacturing Report",
            align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        dn = _safe(self._doc.metadata.drawing_number or "-")
        rev = _safe(self._doc.metadata.revision or "-")
        self.set_font("Helvetica", "", 8)
        self.set_text_color(_GRAY_R, _GRAY_G, _GRAY_B)
        subtitle = f"Drawing: {dn} | Rev: {rev} | {self._doc.metadata.generated_at}"
        self.cell(0, 4, subtitle, align="L", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-18)
        # Safety disclaimer bar
        self.set_fill_color(254, 226, 226)
        self.set_draw_color(252, 165, 165)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(_SAFETY_R, _SAFETY_G, _SAFETY_B)
        _footer_txt = (
            "DRAFT - ENGINEERING REVIEW REQUIRED"
            " | IS_DISPATCHABLE=NO | PRODUCTION_RELEASED=NO | AUTO_APPROVED=NO"
        )
        self.cell(
            0, 7, _footer_txt,
            fill=True, border=1, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        # Page number
        self.set_font("Helvetica", "", 7)
        self.set_text_color(_GRAY_R, _GRAY_G, _GRAY_B)
        self.cell(0, 4, f"Page {self.page_no()} | {self._doc.metadata.report_id}", align="C",
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _write_cover(pdf: _MachiningProPDF, doc: ReportDocument) -> None:
    pdf.add_page()

    # Title block
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(_BRAND_R, _BRAND_G, _BRAND_B)
    pdf.cell(0, 12, "Manufacturing Report", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "I", 11)
    pdf.set_text_color(_SAFETY_R, _SAFETY_G, _SAFETY_B)
    pdf.cell(
        0, 7, "DRAFT - Engineering Review Required",
        align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT,
    )
    pdf.ln(4)

    # Safety disclaimer box
    pdf.set_fill_color(254, 226, 226)
    pdf.set_draw_color(252, 165, 165)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(_SAFETY_R, _SAFETY_G, _SAFETY_B)
    pdf.multi_cell(0, 6, _safe("[!]  " + doc.disclaimer), border=1, fill=True,
                   new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(6)

    # Metadata table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(_BRAND_R, _BRAND_G, _BRAND_B)
    pdf.cell(0, 7, "Report Information", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(_TEXT_R, _TEXT_G, _TEXT_B)

    items = [
        ("Report ID", doc.metadata.report_id),
        ("Drawing Number", doc.metadata.drawing_number or "-"),
        ("Revision", doc.metadata.revision or "-"),
        ("Part Reference", doc.metadata.part_reference or "-"),
        ("Generated At", doc.metadata.generated_at),
        ("Language", str(doc.metadata.language)),
        ("Units", str(doc.metadata.units)),
        ("Status", str(doc.metadata.report_status)),
        ("IS_DISPATCHABLE", "NO"),
        ("PRODUCTION_RELEASED", "NO"),
        ("AUTO_APPROVED", "NO"),
        ("ENGINEERING_STATE_CHANGED", "NO"),
    ]
    col_w = 60
    for label, value in items:
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(col_w, 6, label + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, _safe(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _write_section(pdf: _MachiningProPDF, section_title: str, content_item: object) -> None:
    # Section header
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(_BRAND_R, _BRAND_G, _BRAND_B)
    pdf.set_fill_color(_LIGHT_R, _LIGHT_G, _LIGHT_B)
    pdf.cell(0, 8, _safe(section_title), fill=True, border="B", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)

    if isinstance(content_item, ReportWarningBox):
        is_warn = content_item.level == "WARNING"
        fill_r, fill_g, fill_b = (254, 243, 199) if is_warn else (254, 226, 226)
        text_r = _WARN_R if is_warn else _SAFETY_R
        text_g = _WARN_G if is_warn else _SAFETY_G
        text_b = _WARN_B if is_warn else _SAFETY_B
        pdf.set_fill_color(fill_r, fill_g, fill_b)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(text_r, text_g, text_b)
        pdf.multi_cell(
            0, 6, _safe(content_item.text),
            border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(3)

    elif isinstance(content_item, ReportKeyValue):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(_TEXT_R, _TEXT_G, _TEXT_B)
        col_w = 65
        for label, value in content_item.items:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(col_w, 5, _safe(label) + ":", new_x=XPos.RIGHT, new_y=YPos.TOP)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, _safe(value), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    elif isinstance(content_item, ReportText):
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(_TEXT_R, _TEXT_G, _TEXT_B)
        pdf.multi_cell(0, 5, _safe(content_item.body), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    elif isinstance(content_item, ReportTable):
        _write_table(pdf, content_item)
        pdf.ln(3)


def _write_table(pdf: _MachiningProPDF, table: ReportTable) -> None:
    if not table.headers:
        return

    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    n_cols = len(table.headers)
    col_w = page_w / n_cols

    # Header row
    pdf.set_fill_color(_HEADER_R, _HEADER_G, _HEADER_B)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 8)
    for header in table.headers:
        pdf.cell(col_w, 6, _safe(str(header))[:30], border=1, fill=True, align="C",
                 new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.ln()

    # Data rows
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(_TEXT_R, _TEXT_G, _TEXT_B)
    for row_idx, row in enumerate(table.rows):
        if row_idx % 2 == 0:
            pdf.set_fill_color(_LIGHT_R, _LIGHT_G, _LIGHT_B)
            fill = True
        else:
            fill = False

        for cell_val in row.cells:
            val = _safe(str(cell_val))[:40] if cell_val else "-"
            pdf.cell(col_w, 5, val, border=1, fill=fill,
                     new_x=XPos.RIGHT, new_y=YPos.TOP)
        pdf.ln()

    if table.caption:
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(_GRAY_R, _GRAY_G, _GRAY_B)
        pdf.cell(0, 5, _safe(table.caption), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def export_pdf(doc: ReportDocument) -> ReportExportItem:
    """Export ReportDocument as PDF bytes.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    pdf = _MachiningProPDF(doc)
    _write_cover(pdf, doc)

    # Sections (skip disclaimer — it's in cover and footer)
    for section in doc.sections:
        if section.section_id == "disclaimer":
            continue
        pdf.add_page()
        for content_item in section.content:
            _write_section(pdf, section.title, content_item)

    buf = BytesIO()
    buf.write(pdf.output())
    buf.seek(0)

    dn = doc.metadata.drawing_number or "unknown"
    filename = f"MachiningPro_Report_{_safe_name(dn)}_{doc.metadata.generated_at[:10]}.pdf"
    return ReportExportItem(
        format=ExportFormat.PDF,
        filename=filename,
        content=buf.getvalue(),
        mime_type=_MIME,
    )


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:40]
