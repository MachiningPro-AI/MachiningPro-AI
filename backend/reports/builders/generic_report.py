"""Generic report builder — produces a ReportDocument from a dict of section data.

Used for report types that do not yet have a dedicated domain builder.
REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
"""
from __future__ import annotations

import uuid
from typing import Any

from backend.reports.models import (
    REPORT_AUTO_APPROVED,
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    REPORT_IS_DISPATCHABLE,
    REPORT_PRODUCTION_RELEASED,
    REPORT_REVIEW_REQUIRED,
    ReportDocument,
    ReportKeyValue,
    ReportLanguage,
    ReportMetadata,
    ReportProvenance,
    ReportSection,
    ReportStatus,
    ReportTable,
    ReportText,
    ReportType,
    ReportUnits,
    ReportWarningBox,
    TableRow,
)


def _safe(v: Any) -> str:
    if v is None:
        return "N/A"
    s = str(v)
    return s if s.strip() else "N/A"


def build_generic_report(
    report_type: ReportType,
    sections_data: list[dict[str, Any]],
    *,
    part_reference: str | None = None,
    drawing_number: str | None = None,
    revision: str | None = None,
    source_id: str | None = None,
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
    section_ids: list[str] | None = None,
) -> ReportDocument:
    """Build a ReportDocument from generic section data.

    sections_data: list of dicts, each with:
      - section_id: str
      - title: str
      - type: "keyvalue" | "table" | "text" | "warning"
      - items: for keyvalue, list of [label, value]
      - headers: for table, list of str
      - rows: for table, list of list of str
      - caption: for table, optional str
      - body: for text, str
      - text: for warning, str
      - level: for warning, str (WARNING/SAFETY/ADVISORY)

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED
    assert not REPORT_IS_DISPATCHABLE
    assert not REPORT_PRODUCTION_RELEASED
    assert not REPORT_AUTO_APPROVED
    assert REPORT_REVIEW_REQUIRED

    rid = report_id or f"RPT-GEN-{uuid.uuid4().hex[:12].upper()}"
    generated_at = ReportDocument.now_utc()
    L = language

    metadata = ReportMetadata(
        report_id=rid,
        report_type=report_type,
        report_status=ReportStatus.REVIEW_REQUIRED,
        part_reference=part_reference,
        drawing_number=drawing_number,
        revision=revision,
        generated_at=generated_at,
        generated_by="MachiningPro AI -- generic report builder",
        language=language,
        units=units,
        is_dispatchable=False,
        production_released=False,
        auto_approved=False,
        review_required=True,
        engineering_state_changed=False,
    )

    provenance = ReportProvenance(
        source_type="GenericData",
        source_id=source_id or rid,
        source_revision=revision,
        source_status="DRAFT",
        engineering_state_modified=False,
        auto_approved=False,
    )

    sections: list[ReportSection] = []

    # Mandatory disclaimer
    disc_text = (
        "DRAFT -- Engineering review required. "
        "IS_DISPATCHABLE=NO. PRODUCTION_RELEASED=NO. AUTO_APPROVED=NO."
        if L != ReportLanguage.TR else
        "TASLAK -- Muhendis incelemesi gereklidir. "
        "IS_DISPATCHABLE=HAYIR. URETIM_CIKISI=HAYIR. OTOMATIK_ONAY=HAYIR."
    )
    sections.append(ReportSection(
        section_id="disclaimer",
        title="Safety Disclaimer" if L != ReportLanguage.TR else "Guvenlik Bildirimi",
        content=[ReportWarningBox(text=disc_text, level="SAFETY")],
    ))

    # Build sections from data
    always_include = {"disclaimer"}
    for sd in sections_data:
        sid = sd.get("section_id", "section")
        if section_ids is not None and sid not in always_include:
            if sid not in section_ids:
                continue
        title = sd.get("title", sid)
        stype = sd.get("type", "text")
        content: list[Any] = []

        if stype == "keyvalue":
            raw = sd.get("items", [])
            kv_items = [(str(r[0]), _safe(r[1])) for r in raw if len(r) >= 2]
            if kv_items:
                content.append(ReportKeyValue(items=kv_items))

        elif stype == "table":
            headers = [str(h) for h in sd.get("headers", [])]
            rows = [
                TableRow(cells=[_safe(c) for c in row])
                for row in sd.get("rows", [])
            ]
            caption = sd.get("caption", "")
            if headers and rows:
                content.append(ReportTable(headers=headers, rows=rows, caption=caption))

        elif stype == "warning":
            content.append(ReportWarningBox(
                text=_safe(sd.get("text", "")),
                level=sd.get("level", "WARNING"),
            ))

        else:  # text
            body = _safe(sd.get("body", sd.get("text", "")))
            content.append(ReportText(body=body))

        if content:
            sections.append(ReportSection(
                section_id=sid,
                title=title,
                content=content,
            ))

    doc = ReportDocument(
        metadata=metadata,
        provenance=provenance,
        sections=sections,
    )
    assert not doc.metadata.engineering_state_changed
    return doc
