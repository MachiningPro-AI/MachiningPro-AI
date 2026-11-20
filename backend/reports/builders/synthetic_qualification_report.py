"""Build a ReportDocument from synthetic qualification result data.

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO — the source data is never
modified.

MUST 36: SYNTHETIC_QUALIFICATION_REPORT
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


def build_synthetic_qualification_report(
    qual_data: dict[str, Any],
    *,
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
    section_ids: list[str] | None = None,
) -> ReportDocument:
    """Build a ReportDocument from a synthetic qualification result dict.

    Expected keys (all optional):
      - qualification_id: str
      - part_id: str
      - drawing_number: str
      - revision: str
      - verdict: str  (PASS / FAIL / PARTIAL)
      - expected_vs_actual: list[dict] with keys: check, expected, actual, result
      - feature_results: list[dict] with keys: feature_id, feature_type, result, note
      - process_results: list[dict] with keys: operation, result, note
      - defects: list[dict] with keys: severity, description, resolution
      - format_results: list[dict] with keys: format, result, note

    The source dict is NEVER modified.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED
    assert not REPORT_IS_DISPATCHABLE
    assert not REPORT_PRODUCTION_RELEASED
    assert not REPORT_AUTO_APPROVED
    assert REPORT_REVIEW_REQUIRED

    rid = report_id or f"RPT-SQ-{uuid.uuid4().hex[:12].upper()}"
    generated_at = ReportDocument.now_utc()
    L = language

    qual_id = qual_data.get("qualification_id", "UNKNOWN")
    part_id = qual_data.get("part_id", "UNKNOWN")
    drawing_number = qual_data.get("drawing_number")
    revision = qual_data.get("revision")

    metadata = ReportMetadata(
        report_id=rid,
        report_type=ReportType.SYNTHETIC_QUALIFICATION_REPORT,
        report_status=ReportStatus.REVIEW_REQUIRED,
        part_reference=part_id,
        drawing_number=drawing_number,
        revision=revision,
        generated_at=generated_at,
        generated_by="MachiningPro AI -- qualification report builder",
        language=language,
        units=units,
        is_dispatchable=False,
        production_released=False,
        auto_approved=False,
        review_required=True,
        engineering_state_changed=False,
    )

    provenance = ReportProvenance(
        source_type="SyntheticQualificationResult",
        source_id=qual_id,
        source_revision=revision,
        source_status=_safe(qual_data.get("verdict")),
        engineering_state_modified=False,
        auto_approved=False,
    )

    sections: list[ReportSection] = []

    # Safety disclaimer
    sections.append(ReportSection(
        section_id="disclaimer",
        title="Safety Disclaimer" if L != ReportLanguage.TR else "Guvenlik Bildirimi",
        content=[ReportWarningBox(
            text=(
                "DRAFT -- Engineering review required. "
                "IS_DISPATCHABLE=NO. PRODUCTION_RELEASED=NO. AUTO_APPROVED=NO."
                if L != ReportLanguage.TR else
                "TASLAK -- Muhendis incelemesi gereklidir. "
                "IS_DISPATCHABLE=HAYIR. URETIM_CIKISI=HAYIR. OTOMATIK_ONAY=HAYIR."
            ),
            level="SAFETY",
        )],
    ))

    # Summary
    if section_ids is None or "summary" in section_ids:
        verdict = _safe(qual_data.get("verdict", "UNKNOWN"))
        sections.append(ReportSection(
            section_id="summary",
            title="Qualification Summary" if L != ReportLanguage.TR else "Kalifikasyon Ozeti",
            content=[ReportKeyValue(items=[
                ("Qualification ID", _safe(qual_id)),
                ("Part ID", _safe(part_id)),
                ("Drawing Number", _safe(drawing_number)),
                ("Revision", _safe(revision)),
                ("Verdict", verdict),
                ("Generated At", generated_at),
                ("IS_DISPATCHABLE", "NO"),
                ("PRODUCTION_RELEASED", "NO"),
                ("AUTO_APPROVED", "NO"),
            ])],
        ))

    # Expected vs Actual
    ev = qual_data.get("expected_vs_actual", [])
    if ev and (section_ids is None or "expected_vs_actual" in section_ids):
        rows = [
            TableRow(cells=[
                _safe(r.get("check")),
                _safe(r.get("expected")),
                _safe(r.get("actual")),
                _safe(r.get("result")),
            ])
            for r in ev
        ]
        sections.append(ReportSection(
            section_id="expected_vs_actual",
            title=(
                "Expected vs Actual"
                if L != ReportLanguage.TR else "Beklenen - Gerceklesen"
            ),
            content=[ReportTable(
                headers=["Check", "Expected", "Actual", "Result"],
                rows=rows,
                caption=f"{len(ev)} checks",
            )],
        ))

    # Feature results
    fr = qual_data.get("feature_results", [])
    if fr and (section_ids is None or "feature_results" in section_ids):
        rows = [
            TableRow(cells=[
                _safe(r.get("feature_id")),
                _safe(r.get("feature_type")),
                _safe(r.get("result")),
                _safe(r.get("note")),
            ])
            for r in fr
        ]
        sections.append(ReportSection(
            section_id="feature_results",
            title=(
                "Feature Results"
                if L != ReportLanguage.TR else "Ozellik Sonuclari"
            ),
            content=[ReportTable(
                headers=["Feature ID", "Type", "Result", "Note"],
                rows=rows,
                caption=f"{len(fr)} features",
            )],
        ))

    # Process results
    pr = qual_data.get("process_results", [])
    if pr and (section_ids is None or "process_results" in section_ids):
        rows = [
            TableRow(cells=[
                _safe(r.get("operation")),
                _safe(r.get("result")),
                _safe(r.get("note")),
            ])
            for r in pr
        ]
        sections.append(ReportSection(
            section_id="process_results",
            title=(
                "Process Results"
                if L != ReportLanguage.TR else "Surec Sonuclari"
            ),
            content=[ReportTable(
                headers=["Operation", "Result", "Note"],
                rows=rows,
            )],
        ))

    # Format results
    fmr = qual_data.get("format_results", [])
    if fmr and (section_ids is None or "format_results" in section_ids):
        rows = [
            TableRow(cells=[
                _safe(r.get("format")),
                _safe(r.get("result")),
                _safe(r.get("note")),
            ])
            for r in fmr
        ]
        sections.append(ReportSection(
            section_id="format_results",
            title=(
                "Format Results"
                if L != ReportLanguage.TR else "Format Sonuclari"
            ),
            content=[ReportTable(
                headers=["Format", "Result", "Note"],
                rows=rows,
            )],
        ))

    # Defects
    defects = qual_data.get("defects", [])
    if defects and (section_ids is None or "defects" in section_ids):
        rows = [
            TableRow(cells=[
                _safe(d.get("severity")),
                _safe(d.get("description")),
                _safe(d.get("resolution")),
            ])
            for d in defects
        ]
        sections.append(ReportSection(
            section_id="defects",
            title="Defects" if L != ReportLanguage.TR else "Hatalar",
            content=[ReportTable(
                headers=["Severity", "Description", "Resolution"],
                rows=rows,
            )],
        ))

    # Final verdict
    if section_ids is None or "verdict" in section_ids:
        verdict = qual_data.get("verdict", "UNKNOWN")
        level = "SAFETY" if str(verdict).upper() == "FAIL" else "WARNING"
        sections.append(ReportSection(
            section_id="verdict",
            title="Final Verdict" if L != ReportLanguage.TR else "Son Karar",
            content=[ReportWarningBox(
                text=(
                    f"QUALIFICATION VERDICT: {verdict}\n"
                    "PRODUCTION_APPROVED: NOT SET -- requires explicit approval workflow."
                ),
                level=level,
            )],
        ))

    doc = ReportDocument(
        metadata=metadata,
        provenance=provenance,
        sections=sections,
    )
    assert not doc.metadata.engineering_state_changed
    return doc
