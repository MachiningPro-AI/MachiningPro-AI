"""Canonical report domain model.

Central contract for all report types. Exporters consume ReportDocument only —
they never touch source engineering objects directly.

Safety invariants (enforced, never bypassed):
  REPORT_GENERATION_ENGINEERING_STATE_CHANGED = False
  REPORT_IS_DISPATCHABLE = False
  REPORT_PRODUCTION_RELEASED = False
  REPORT_AUTO_APPROVED = False
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

# ---------------------------------------------------------------------------
# Safety constants — always False, never overridden
# ---------------------------------------------------------------------------

REPORT_GENERATION_ENGINEERING_STATE_CHANGED: bool = False
REPORT_IS_DISPATCHABLE: bool = False
REPORT_PRODUCTION_RELEASED: bool = False
REPORT_AUTO_APPROVED: bool = False
REPORT_REVIEW_REQUIRED: bool = True


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ReportType(StrEnum):
    MANUFACTURING_PLAN = "MANUFACTURING_PLAN"
    PROCESS_ROUTE = "PROCESS_ROUTE"
    DFM_ANALYSIS = "DFM_ANALYSIS"
    NC_PROGRAM_REVIEW = "NC_PROGRAM_REVIEW"
    WORKFLOW_SUMMARY = "WORKFLOW_SUMMARY"


class ReportStatus(StrEnum):
    DRAFT = "DRAFT"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"


class ExportFormat(StrEnum):
    PDF = "PDF"
    DOCX = "DOCX"
    XLSX = "XLSX"
    CSV = "CSV"
    JSON = "JSON"
    ZIP = "ZIP"


class ReportLanguage(StrEnum):
    EN = "EN"
    TR = "TR"


class ReportUnits(StrEnum):
    METRIC = "METRIC"
    IMPERIAL = "IMPERIAL"


# ---------------------------------------------------------------------------
# Provenance — what engineering state fed this report
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportProvenance:
    """Records what engineering data fed this report. Read-only snapshot."""

    source_type: str
    source_id: str
    source_revision: str | None = None
    source_status: str | None = None
    input_hash: str | None = None
    # Immutable safety guards
    engineering_state_modified: bool = False
    auto_approved: bool = False


# ---------------------------------------------------------------------------
# Report metadata
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ReportMetadata:
    report_id: str
    report_type: ReportType
    report_status: ReportStatus
    part_reference: str | None
    drawing_number: str | None
    revision: str | None
    generated_at: str
    generated_by: str
    language: ReportLanguage
    units: ReportUnits
    schema_version: str = "1.0"
    application: str = "MachiningPro AI"
    # Immutable safety flags
    is_dispatchable: bool = False
    production_released: bool = False
    auto_approved: bool = False
    review_required: bool = True
    engineering_state_changed: bool = False


# ---------------------------------------------------------------------------
# Section content types
# ---------------------------------------------------------------------------

@dataclass
class TableRow:
    cells: list[str]


@dataclass
class ReportTable:
    headers: list[str]
    rows: list[TableRow]
    caption: str = ""


@dataclass
class ReportKeyValue:
    items: list[tuple[str, str]]


@dataclass
class ReportText:
    body: str


@dataclass
class ReportWarningBox:
    text: str
    level: str = "WARNING"


# ---------------------------------------------------------------------------
# Report section
# ---------------------------------------------------------------------------

@dataclass
class ReportSection:
    section_id: str
    title: str
    content: list[Any] = field(default_factory=list)
    provenance_note: str = ""


# ---------------------------------------------------------------------------
# Central canonical report document
# ---------------------------------------------------------------------------

@dataclass
class ReportDocument:
    """Central canonical report document.

    Exporters receive this and nothing else.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False — this document is a
    snapshot; building it never modifies the source engineering objects.
    """

    metadata: ReportMetadata
    provenance: ReportProvenance
    sections: list[ReportSection] = field(default_factory=list)
    safety_disclaimer_en: str = (
        "DRAFT — ENGINEERING REVIEW REQUIRED. "
        "This report is for reference only. No CNC machine writes have been performed. "
        "IS_DISPATCHABLE=NO. PRODUCTION_RELEASED=NO. AUTO_APPROVED=NO."
    )
    safety_disclaimer_tr: str = (
        "TASLAK — MÜHENDİS İNCELEMESİ GEREKLİDİR. "
        "Bu rapor yalnızca referans amaçlıdır. CNC makinesi yazma işlemi gerçekleştirilmemiştir. "
        "GÖNDERILEBILIR=HAYIR. ÜRETİME_ÇIKIŞ=HAYIR. OTOMATİK_ONAY=HAYIR."
    )

    @property
    def disclaimer(self) -> str:
        if self.metadata.language == ReportLanguage.TR:
            return self.safety_disclaimer_tr
        return self.safety_disclaimer_en

    @staticmethod
    def now_utc() -> str:
        return datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")


# ---------------------------------------------------------------------------
# Export bundle
# ---------------------------------------------------------------------------

@dataclass
class ReportExportItem:
    format: ExportFormat
    filename: str
    content: bytes
    mime_type: str


@dataclass
class ReportBundle:
    """All requested export formats for one report."""

    document: ReportDocument
    items: list[ReportExportItem] = field(default_factory=list)
    # Safety
    engineering_state_changed: bool = False

    def get(self, fmt: ExportFormat) -> ReportExportItem | None:
        for item in self.items:
            if item.format == fmt:
                return item
        return None
