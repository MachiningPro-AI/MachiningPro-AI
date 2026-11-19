"""DOCX exporter — generates a minimal .docx using raw Open XML (zipfile).

No python-docx dependency required.
Generates OOXML-compliant .docx with:
  - Cover page with safety disclaimer
  - One heading2 + table per section
  - Footer disclaimer on every page

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
"""
from __future__ import annotations

import zipfile
from io import BytesIO
from xml.sax.saxutils import escape as _esc

from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportDocument,
    ReportExportItem,
    ReportKeyValue,
    ReportTable,
    ReportWarningBox,
)

_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


# ---------------------------------------------------------------------------
# Minimal OOXML skeletons
# ---------------------------------------------------------------------------

_CONTENT_TYPES = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
  <Override PartName="/word/styles.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
  <Override PartName="/word/settings.xml"
            ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>
</Types>"""

_RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
    Target="word/document.xml"/>
</Relationships>"""

_WORD_RELS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    Target="styles.xml"/>
  <Relationship Id="rId2"
    Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings"
    Target="settings.xml"/>
</Relationships>"""

_SETTINGS = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:defaultTabStop w:val="720"/>
</w:settings>"""

_STYLES = """\
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
          xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">
  <w:style w:type="paragraph" w:styleId="Normal" w:default="1">
    <w:name w:val="Normal"/>
    <w:rPr><w:sz w:val="20"/><w:szCs w:val="20"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading1">
    <w:name w:val="heading 1"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:numPr/><w:spacing w:before="240" w:after="60"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="2E5090"/><w:sz w:val="32"/><w:szCs w:val="32"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="Heading2">
    <w:name w:val="heading 2"/>
    <w:basedOn w:val="Normal"/>
    <w:pPr><w:spacing w:before="200" w:after="60"/></w:pPr>
    <w:rPr><w:b/><w:color w:val="2E5090"/><w:sz w:val="24"/><w:szCs w:val="24"/></w:rPr>
  </w:style>
  <w:style w:type="paragraph" w:styleId="TableHeader">
    <w:name w:val="Table Header"/>
    <w:basedOn w:val="Normal"/>
    <w:rPr><w:b/><w:color w:val="FFFFFF"/><w:sz w:val="18"/></w:rPr>
  </w:style>
</w:styles>"""

# XML namespace shortcuts
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


# ---------------------------------------------------------------------------
# XML helpers
# ---------------------------------------------------------------------------

def _p(text: str, style: str = "Normal", bold: bool = False, color: str | None = None,
       shade_color: str | None = None) -> str:
    r_props = ""
    if bold:
        r_props += "<w:b/>"
    if color:
        r_props += f'<w:color w:val="{color}"/>'
    shading = ""
    if shade_color:
        shading = f'<w:shd w:val="clear" w:color="auto" w:fill="{shade_color}"/>'
    return (
        f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{shading}</w:pPr>'
        f'<w:r><w:rPr>{r_props}</w:rPr><w:t xml:space="preserve">{_esc(text)}</w:t></w:r></w:p>'
    )


def _h1(text: str) -> str:
    return _p(text, style="Heading1")


def _h2(text: str) -> str:
    return _p(text, style="Heading2")


def _kv_para(label: str, value: str) -> str:
    return (
        f'<w:p><w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{_esc(label)}: </w:t></w:r>'
        f'<w:r><w:t xml:space="preserve">{_esc(value)}</w:t></w:r></w:p>'
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    tbl_props = (
        '<w:tblPr>'
        '<w:tblStyle w:val="TableGrid"/>'
        '<w:tblW w:w="0" w:type="auto"/>'
        '<w:tblBorders>'
        '<w:top w:val="single" w:sz="4" w:color="D1D5DB"/>'
        '<w:left w:val="single" w:sz="4" w:color="D1D5DB"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="D1D5DB"/>'
        '<w:right w:val="single" w:sz="4" w:color="D1D5DB"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D1D5DB"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D1D5DB"/>'
        '</w:tblBorders>'
        '</w:tblPr>'
    )

    def _header_cell(text: str) -> str:
        return (
            '<w:tc><w:tcPr>'
            '<w:shd w:val="clear" w:color="auto" w:fill="2E5090"/>'
            '</w:tcPr>'
            f'<w:p><w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/><w:sz w:val="16"/></w:rPr>'
            f'<w:t xml:space="preserve">{_esc(str(text)[:50])}</w:t></w:r></w:p></w:tc>'
        )

    def _data_cell(text: str, shade: bool) -> str:
        shading = '<w:shd w:val="clear" w:color="auto" w:fill="F0F4FF"/>' if shade else ""
        return (
            f'<w:tc><w:tcPr>{shading}</w:tcPr>'
            f'<w:p><w:r><w:rPr><w:sz w:val="16"/></w:rPr>'
            f'<w:t xml:space="preserve">'
            f'{_esc(str(text)[:60] if text else "-")}</w:t></w:r></w:p></w:tc>'
        )

    header_row = "<w:tr>" + "".join(_header_cell(h) for h in headers) + "</w:tr>"
    data_rows = ""
    for idx, row in enumerate(rows):
        shade = idx % 2 == 0
        cells = "".join(_data_cell(c, shade) for c in row)
        data_rows += f"<w:tr>{cells}</w:tr>"

    return f"<w:tbl>{tbl_props}{header_row}{data_rows}</w:tbl>"


# ---------------------------------------------------------------------------
# Document body builder
# ---------------------------------------------------------------------------

def _build_body(doc: ReportDocument) -> str:
    parts: list[str] = []

    # Cover
    parts.append(_h1("MachiningPro AI — Manufacturing Report"))
    parts.append(_p("DRAFT — Engineering Review Required", bold=True, color="991B1B"))
    parts.append(_p(""))

    disclaimer_text = (
        "⚠ SAFETY DISCLAIMER: " + doc.disclaimer
    )
    parts.append(_p(disclaimer_text, bold=True, color="991B1B", shade_color="FEE2E2"))
    parts.append(_p(""))

    # Metadata
    parts.append(_h2("Report Information"))
    meta_items = [
        ("Report ID", doc.metadata.report_id),
        ("Drawing Number", doc.metadata.drawing_number or "—"),
        ("Revision", doc.metadata.revision or "—"),
        ("Generated At", doc.metadata.generated_at),
        ("Language", str(doc.metadata.language)),
        ("Units", str(doc.metadata.units)),
        ("IS_DISPATCHABLE", "NO"),
        ("PRODUCTION_RELEASED", "NO"),
        ("AUTO_APPROVED", "NO"),
        ("ENGINEERING_STATE_CHANGED", "NO"),
    ]
    for label, value in meta_items:
        parts.append(_kv_para(label, value))
    parts.append(_p(""))

    # Sections
    for section in doc.sections:
        if section.section_id == "disclaimer":
            continue
        parts.append(_h2(section.title))
        for content_item in section.content:
            if isinstance(content_item, ReportWarningBox):
                parts.append(_p(f"⚠  {content_item.text}", bold=True, color="991B1B"))
            elif isinstance(content_item, ReportKeyValue):
                for label, value in content_item.items:
                    parts.append(_kv_para(label, value))
            elif isinstance(content_item, ReportTable):
                if content_item.rows:
                    parts.append(_table(
                        content_item.headers,
                        [r.cells for r in content_item.rows],
                    ))
                    if content_item.caption:
                        parts.append(_p(content_item.caption, color="6B7280"))
            parts.append(_p(""))

    # Page break before final disclaimer
    parts.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    parts.append(_h2("Safety & Provenance"))
    parts.append(_p(doc.disclaimer, bold=True, color="991B1B"))
    parts.append(_p(""))
    parts.append(_kv_para("Source Type", doc.provenance.source_type))
    parts.append(_kv_para("Source ID", doc.provenance.source_id))
    parts.append(_kv_para("Engineering State Modified", "NO"))
    parts.append(_kv_para("Auto Approved", "NO"))

    body = "\n".join(parts)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">\n'
        f'<w:body>{body}'
        '<w:sectPr>'
        '<w:pgSz w:w="12240" w:h="15840"/>'
        '<w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" w:footer="720"/>'
        '</w:sectPr>'
        '</w:body></w:document>'
    )


# ---------------------------------------------------------------------------
# Public export function
# ---------------------------------------------------------------------------

def export_docx(doc: ReportDocument) -> ReportExportItem:
    """Export ReportDocument as DOCX bytes (raw Open XML, no python-docx required).

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    buf = BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", _CONTENT_TYPES)
        zf.writestr("_rels/.rels", _RELS)
        zf.writestr("word/_rels/document.xml.rels", _WORD_RELS)
        zf.writestr("word/settings.xml", _SETTINGS)
        zf.writestr("word/styles.xml", _STYLES)
        zf.writestr("word/document.xml", _build_body(doc))
    buf.seek(0)

    dn = doc.metadata.drawing_number or "unknown"
    filename = f"MachiningPro_Report_{_safe_name(dn)}_{doc.metadata.generated_at[:10]}.docx"
    return ReportExportItem(
        format=ExportFormat.DOCX,
        filename=filename,
        content=buf.getvalue(),
        mime_type=_MIME,
    )


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:40]
