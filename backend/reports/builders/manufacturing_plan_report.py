"""Build a ReportDocument from a ManufacturingPlan.

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO — the source plan is never
modified. All data is read-only snapshot extraction.
"""
from __future__ import annotations

import uuid
from typing import Any

from backend.manufacturing_plan.models import ManufacturingPlan
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

# ---------------------------------------------------------------------------
# Labels by language
# ---------------------------------------------------------------------------

_LABELS_EN: dict[str, str] = {
    "cover_title": "Manufacturing Plan",
    "cover_subtitle": "DRAFT — Engineering Review Required",
    "section_summary": "Executive Summary",
    "section_plan_info": "Plan Information",
    "section_operations": "Operations",
    "section_tools": "Tool List",
    "section_machines": "Machines",
    "section_parameters": "Cutting Parameters",
    "section_inspection": "Inspection Plan",
    "section_control_plan": "Control Plan",
    "section_open_items": "Open Items",
    "section_completeness": "Completeness",
    "section_release_gate": "Release Gate",
    "section_disclaimer": "Safety Disclaimer",
    "label_plan_id": "Plan ID",
    "label_part": "Part Reference",
    "label_drawing": "Drawing Number",
    "label_revision": "Revision",
    "label_status": "Status",
    "label_release": "Release Gate",
    "label_completeness": "Overall Completeness",
    "label_generated": "Generated",
    "label_operations_count": "Operations",
    "label_open_items": "Open Items",
    "label_blocking_items": "Blocking Items",
    "col_op_no": "#",
    "col_op_type": "Operation",
    "col_machine": "Machine",
    "col_tool": "Tool",
    "col_vc": "Vc (m/min)",
    "col_feed": "Feed (mm/min)",
    "col_rpm": "RPM",
    "col_ap": "ap (mm)",
    "col_ae": "ae (mm)",
    "col_source": "Source",
    "col_char": "Characteristic",
    "col_type": "Type",
    "col_criticality": "Criticality",
    "col_stage": "Stage",
    "col_method": "Method",
    "col_gage": "Gage",
    "col_severity": "Severity",
    "col_category": "Category",
    "col_description": "Description",
    "col_resolution": "Resolution Hint",
    "col_tool_id": "Tool ID",
    "col_tool_label": "Tool Label",
    "col_tool_type": "Type",
    "col_holder": "Holder",
    "col_qty": "Qty",
    "col_machine_id": "Machine ID",
    "col_machine_label": "Machine",
    "col_machine_type": "Type",
    "na": "—",
    "yes": "YES",
    "no": "NO",
}

_LABELS_TR: dict[str, str] = {
    "cover_title": "İmalat Planı",
    "cover_subtitle": "TASLAK — Mühendis İncelemesi Gereklidir",
    "section_summary": "Yönetici Özeti",
    "section_plan_info": "Plan Bilgileri",
    "section_operations": "Operasyonlar",
    "section_tools": "Takım Listesi",
    "section_machines": "Tezgahlar",
    "section_parameters": "Kesme Parametreleri",
    "section_inspection": "Muayene Planı",
    "section_control_plan": "Kontrol Planı",
    "section_open_items": "Açık Maddeler",
    "section_completeness": "Tamlık",
    "section_release_gate": "Yayın Kapısı",
    "section_disclaimer": "Güvenlik Bildirimi",
    "label_plan_id": "Plan Kimliği",
    "label_part": "Parça Referansı",
    "label_drawing": "Çizim Numarası",
    "label_revision": "Revizyon",
    "label_status": "Durum",
    "label_release": "Yayın Kapısı",
    "label_completeness": "Genel Tamlık",
    "label_generated": "Oluşturulma",
    "label_operations_count": "Operasyonlar",
    "label_open_items": "Açık Maddeler",
    "label_blocking_items": "Bloke Edici Maddeler",
    "col_op_no": "#",
    "col_op_type": "Operasyon",
    "col_machine": "Tezgah",
    "col_tool": "Takım",
    "col_vc": "Vc (m/dak)",
    "col_feed": "İlerleme (mm/dak)",
    "col_rpm": "Devir",
    "col_ap": "ap (mm)",
    "col_ae": "ae (mm)",
    "col_source": "Kaynak",
    "col_char": "Özellik",
    "col_type": "Tür",
    "col_criticality": "Kritiklik",
    "col_stage": "Aşama",
    "col_method": "Yöntem",
    "col_gage": "Ölçüm Aleti",
    "col_severity": "Önem",
    "col_category": "Kategori",
    "col_description": "Açıklama",
    "col_resolution": "Çözüm İpucu",
    "col_tool_id": "Takım Kimliği",
    "col_tool_label": "Takım Adı",
    "col_tool_type": "Tür",
    "col_holder": "Tutucu",
    "col_qty": "Adet",
    "col_machine_id": "Tezgah Kimliği",
    "col_machine_label": "Tezgah",
    "col_machine_type": "Tür",
    "na": "—",
    "yes": "EVET",
    "no": "HAYIR",
}


def _lbl(key: str, lang: ReportLanguage) -> str:
    if lang == ReportLanguage.TR:
        return _LABELS_TR.get(key, _LABELS_EN.get(key, key))
    return _LABELS_EN.get(key, key)


def _safe(v: Any) -> str:
    if v is None:
        return "—"
    return str(v)


def _pct(v: float) -> str:
    return f"{v:.0%}"


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

def build_manufacturing_plan_report(
    plan: ManufacturingPlan,
    *,
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
) -> ReportDocument:
    """Build a ReportDocument from a ManufacturingPlan.

    The source plan is NEVER modified.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED
    assert not REPORT_IS_DISPATCHABLE
    assert not REPORT_PRODUCTION_RELEASED
    assert not REPORT_AUTO_APPROVED
    assert REPORT_REVIEW_REQUIRED

    rid = report_id or f"RPT-{uuid.uuid4().hex[:12].upper()}"
    generated_at = ReportDocument.now_utc()

    L = language  # noqa: N806

    metadata = ReportMetadata(
        report_id=rid,
        report_type=ReportType.MANUFACTURING_PLAN,
        report_status=ReportStatus.REVIEW_REQUIRED,
        part_reference=plan.part_id,
        drawing_number=plan.drawing_number,
        revision=plan.revision,
        generated_at=generated_at,
        generated_by="MachiningPro AI — automated builder",
        language=language,
        units=units,
        is_dispatchable=False,
        production_released=False,
        auto_approved=False,
        review_required=True,
        engineering_state_changed=False,
    )

    provenance = ReportProvenance(
        source_type="ManufacturingPlan",
        source_id=plan.plan_id,
        source_revision=plan.revision,
        source_status=str(plan.status),
        engineering_state_modified=False,
        auto_approved=False,
    )

    sections: list[ReportSection] = []

    # -- Safety disclaimer (always first) ------------------------------------
    sections.append(ReportSection(
        section_id="disclaimer",
        title=_lbl("section_disclaimer", L),
        content=[ReportWarningBox(
            text=(
                "TASLAK — Mühendis incelemesi gereklidir. "
                "IS_DISPATCHABLE=HAYIR. ÜRETİME_ÇIKIŞ=HAYIR. OTOMATİK_ONAY=HAYIR."
                if L == ReportLanguage.TR else
                "DRAFT — Engineering review required. "
                "IS_DISPATCHABLE=NO. PRODUCTION_RELEASED=NO. AUTO_APPROVED=NO."
            ),
            level="SAFETY",
        )],
    ))

    # -- Plan information ----------------------------------------------------
    blocking = [i for i in plan.open_items if str(i.severity) == "BLOCKING"]
    sections.append(ReportSection(
        section_id="plan_info",
        title=_lbl("section_plan_info", L),
        content=[ReportKeyValue(items=[
            (_lbl("label_plan_id", L), _safe(plan.plan_id)),
            (_lbl("label_part", L), _safe(plan.part_id)),
            (_lbl("label_drawing", L), _safe(plan.drawing_number)),
            (_lbl("label_revision", L), _safe(plan.revision)),
            (_lbl("label_status", L), _safe(plan.status)),
            (_lbl("label_release", L), _safe(plan.release_gate)),
            (_lbl("label_completeness", L), _pct(plan.completeness.overall_completeness)),
            (_lbl("label_generated", L), generated_at),
            (_lbl("label_operations_count", L), str(len(plan.operations))),
            (_lbl("label_open_items", L), str(len(plan.open_items))),
            (_lbl("label_blocking_items", L), str(len(blocking))),
        ])],
    ))

    # -- Operations ----------------------------------------------------------
    if plan.operations:
        rows = [
            TableRow(cells=[
                _safe(op.op_number),
                _safe(op.operation_type),
                _safe(op.machine_label or op.machine_id),
                _safe(op.tool_id),
                _safe(op.cutting_speed_m_min),
                _safe(op.feed_rate_mm_min),
                _safe(op.rpm),
                _safe(op.ap_mm),
                _safe(op.ae_mm),
                _safe(op.parameter_source),
            ])
            for op in plan.operations
        ]
        sections.append(ReportSection(
            section_id="operations",
            title=_lbl("section_operations", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_op_no", L), _lbl("col_op_type", L),
                    _lbl("col_machine", L), _lbl("col_tool", L),
                    _lbl("col_vc", L), _lbl("col_feed", L),
                    _lbl("col_rpm", L), _lbl("col_ap", L),
                    _lbl("col_ae", L), _lbl("col_source", L),
                ],
                rows=rows,
                caption=f"{len(plan.operations)} operations",
            )],
        ))

    # -- Tool list -----------------------------------------------------------
    if plan.tool_list:
        rows = [
            TableRow(cells=[
                _safe(t.tool_id),
                _safe(t.tool_label),
                _safe(t.tool_type),
                _safe(t.holder_label or t.holder_id),
                _safe(t.quantity_required),
            ])
            for t in plan.tool_list
        ]
        sections.append(ReportSection(
            section_id="tools",
            title=_lbl("section_tools", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_tool_id", L), _lbl("col_tool_label", L),
                    _lbl("col_tool_type", L), _lbl("col_holder", L),
                    _lbl("col_qty", L),
                ],
                rows=rows,
            )],
        ))

    # -- Machine list --------------------------------------------------------
    if plan.machine_list:
        rows = [
            TableRow(cells=[
                _safe(m.machine_id),
                _safe(m.machine_label),
                _safe(m.machine_type),
            ])
            for m in plan.machine_list
        ]
        sections.append(ReportSection(
            section_id="machines",
            title=_lbl("section_machines", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_machine_id", L), _lbl("col_machine_label", L),
                    _lbl("col_machine_type", L),
                ],
                rows=rows,
            )],
        ))

    # -- Cutting parameters --------------------------------------------------
    if plan.parameter_table:
        rows = [
            TableRow(cells=[
                _safe(p.operation_type),
                _safe(p.vc_m_min),
                _safe(p.fz_mm),
                _safe(p.ap_mm),
                _safe(p.ae_mm),
                _safe(p.feed_rate_mm_min),
                _safe(p.rpm),
                _safe(p.source),
                _safe(p.confidence),
            ])
            for p in plan.parameter_table
        ]
        sections.append(ReportSection(
            section_id="parameters",
            title=_lbl("section_parameters", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_op_type", L), _lbl("col_vc", L), "fz (mm/tooth)",
                    _lbl("col_ap", L), _lbl("col_ae", L),
                    _lbl("col_feed", L), _lbl("col_rpm", L),
                    _lbl("col_source", L), "Confidence",
                ],
                rows=rows,
            )],
        ))

    # -- Inspection plan -----------------------------------------------------
    if plan.inspection_plan and plan.inspection_plan.rows:
        rows = [
            TableRow(cells=[
                _safe(r.char_label),
                _safe(r.char_type.value if hasattr(r.char_type, "value") else r.char_type),
                _safe(r.criticality.value if hasattr(r.criticality, "value") else r.criticality),
                _safe(r.stage.value if hasattr(r.stage, "value") else r.stage),
                _safe(r.method.value if hasattr(r.method, "value") else r.method),
                _safe(r.gage_suggestion),
            ])
            for r in plan.inspection_plan.rows
        ]
        sections.append(ReportSection(
            section_id="inspection",
            title=_lbl("section_inspection", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_char", L), _lbl("col_type", L),
                    _lbl("col_criticality", L), _lbl("col_stage", L),
                    _lbl("col_method", L), _lbl("col_gage", L),
                ],
                rows=rows,
            )],
        ))

    # -- Control plan --------------------------------------------------------
    if plan.control_plan and plan.control_plan.rows:
        rows = [
            TableRow(cells=[
                _safe(r.char_label),
                _safe(r.char_type.value if hasattr(r.char_type, "value") else r.char_type),
                _safe(r.criticality.value if hasattr(r.criticality, "value") else r.criticality),
                _safe(r.specification),
                _safe(r.method.value if hasattr(r.method, "value") else r.method),
                _safe(r.gage_suggestion),
            ])
            for r in plan.control_plan.rows
        ]
        sections.append(ReportSection(
            section_id="control_plan",
            title=_lbl("section_control_plan", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_char", L), _lbl("col_type", L),
                    _lbl("col_criticality", L), "Specification",
                    _lbl("col_method", L), _lbl("col_gage", L),
                ],
                rows=rows,
            )],
        ))

    # -- Open items ----------------------------------------------------------
    if plan.open_items:
        rows = [
            TableRow(cells=[
                _safe(i.severity.value if hasattr(i.severity, "value") else i.severity),
                _safe(i.category.value if hasattr(i.category, "value") else i.category),
                _safe(i.description),
                _safe(i.resolution_hint),
                _safe(i.status.value if hasattr(i.status, "value") else i.status),
            ])
            for i in plan.open_items
        ]
        sections.append(ReportSection(
            section_id="open_items",
            title=_lbl("section_open_items", L),
            content=[ReportTable(
                headers=[
                    _lbl("col_severity", L), _lbl("col_category", L),
                    _lbl("col_description", L), _lbl("col_resolution", L),
                    "Status",
                ],
                rows=rows,
            )],
        ))

    doc = ReportDocument(
        metadata=metadata,
        provenance=provenance,
        sections=sections,
    )
    # Confirm source plan was not modified
    assert not doc.metadata.engineering_state_changed
    return doc
