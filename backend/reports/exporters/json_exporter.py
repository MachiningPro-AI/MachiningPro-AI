"""JSON exporter — serializes ReportDocument to JSON bytes."""
from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any

from backend.reports.models import (
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED,
    ExportFormat,
    ReportDocument,
    ReportExportItem,
)

_MIME = "application/json; charset=utf-8"


class _ReportEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, Enum):
            return obj.value
        if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
            return dataclasses.asdict(obj)
        return super().default(obj)


def export_json(doc: ReportDocument) -> ReportExportItem:
    """Export ReportDocument as indented JSON bytes.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False — this function never
    modifies the source engineering data.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED

    payload = {
        "schema_version": doc.metadata.schema_version,
        "report_type": doc.metadata.report_type,
        "report_id": doc.metadata.report_id,
        "generated_at": doc.metadata.generated_at,
        "language": doc.metadata.language,
        "units": doc.metadata.units,
        "safety": {
            "is_dispatchable": False,
            "production_released": False,
            "auto_approved": False,
            "review_required": True,
            "engineering_state_changed": False,
        },
        "metadata": dataclasses.asdict(doc.metadata),
        "provenance": dataclasses.asdict(doc.provenance),
        "disclaimer": doc.disclaimer,
        "sections": [
            {
                "section_id": s.section_id,
                "title": s.title,
                "provenance_note": s.provenance_note,
                "content": [_encode_content(c) for c in s.content],
            }
            for s in doc.sections
        ],
    }

    content = json.dumps(payload, indent=2, cls=_ReportEncoder, ensure_ascii=False)
    dn = doc.metadata.drawing_number or "unknown"
    filename = f"MachiningPro_Report_{_safe_name(dn)}_{doc.metadata.generated_at[:10]}.json"
    return ReportExportItem(
        format=ExportFormat.JSON,
        filename=filename,
        content=content.encode("utf-8"),
        mime_type=_MIME,
    )


def _encode_content(c: Any) -> Any:
    if dataclasses.is_dataclass(c) and not isinstance(c, type):
        return dataclasses.asdict(c)
    return str(c)


def _safe_name(s: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in s)[:40]
