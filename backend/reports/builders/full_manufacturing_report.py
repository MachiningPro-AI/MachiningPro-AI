"""Build a full 28-section ReportDocument from a ManufacturingPlan.

REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO — the source plan is never
modified. All data is read-only snapshot extraction.

MUST 7: Full Manufacturing Report with 28 sections.
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
    ReadinessStatus,
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

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

_LABELS_EN: dict[str, str] = {
    # section titles
    "s_executive_summary": "1. Executive Summary",
    "s_part_info": "2. Part / Project Information",
    "s_input_files": "3. Input Files",
    "s_source_integrity": "4. Source Integrity / Hashes",
    "s_drawing_analysis": "5. Drawing Analysis",
    "s_cad_geometry": "6. CAD Geometry",
    "s_topology": "7. Topology",
    "s_features": "8. Manufacturing Features",
    "s_dimensions": "9. Dimensions",
    "s_tolerances": "10. Tolerances / GD&T",
    "s_material": "11. Material",
    "s_process_plan": "12. Process Plan",
    "s_machine_selection": "13. Machine Selection",
    "s_tool_selection": "14. Tool Selection",
    "s_cutting_parameters": "15. Cutting Parameters",
    "s_wcs_setup": "16. WCS / Setup",
    "s_cam_strategy": "17. CAM Strategy",
    "s_toolpath_summary": "18. Toolpath Summary",
    "s_verification": "19. Verification",
    "s_collision": "20. Collision / Reach / Envelope",
    "s_simulation": "21. Simulation",
    "s_cost_analysis": "22. Cost Analysis",
    "s_rfq_summary": "23. RFQ Summary",
    "s_warnings": "24. Warnings / Blockers",
    "s_provenance": "25. Provenance Summary",
    "s_engineering_status": "26. Engineering Confirmation Status",
    "s_readiness": "27. Final Readiness",
    "s_next_actions": "28. Recommended Next Actions",
    "s_disclaimer": "Safety Disclaimer",
    # labels
    "plan_id": "Plan ID",
    "part_id": "Part Reference",
    "drawing_number": "Drawing Number",
    "revision": "Revision",
    "status": "Status",
    "release_gate": "Release Gate",
    "completeness": "Overall Completeness",
    "generated_at": "Generated At",
    "operations_count": "Operations",
    "tools_count": "Tools",
    "machines_count": "Machines",
    "open_items": "Open Items",
    "blocking_items": "Blocking Items",
    "is_dispatchable": "IS_DISPATCHABLE",
    "production_released": "PRODUCTION_RELEASED",
    "auto_approved": "AUTO_APPROVED",
    "eng_state_changed": "ENGINEERING_STATE_CHANGED",
    "readiness": "Overall Readiness",
    "na": "N/A",
    # column headers
    "col_severity": "Severity",
    "col_category": "Category",
    "col_description": "Description",
    "col_resolution": "Resolution Hint",
    "col_col_status": "Status",
    "col_op_no": "#",
    "col_op_type": "Operation Type",
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
    "col_tool_id": "Tool ID",
    "col_tool_label": "Tool Label",
    "col_holder": "Holder",
    "col_qty": "Qty",
    "col_machine_id": "Machine ID",
    "col_machine_label": "Machine",
    "col_machine_type": "Machine Type",
}

_LABELS_TR: dict[str, str] = {
    "s_executive_summary": "1. Yönetici Ozeti",
    "s_part_info": "2. Parca / Proje Bilgileri",
    "s_input_files": "3. Giris Dosyalari",
    "s_source_integrity": "4. Kaynak Butunlugu / Hash",
    "s_drawing_analysis": "5. Cizim Analizi",
    "s_cad_geometry": "6. CAD Geometrisi",
    "s_topology": "7. Topoloji",
    "s_features": "8. Imalat Ozellikleri",
    "s_dimensions": "9. Olculer",
    "s_tolerances": "10. Toleranslar / GD&T",
    "s_material": "11. Malzeme",
    "s_process_plan": "12. Surec Plani",
    "s_machine_selection": "13. Tezgah Secimi",
    "s_tool_selection": "14. Takim Secimi",
    "s_cutting_parameters": "15. Kesme Parametreleri",
    "s_wcs_setup": "16. WCS / Baglama",
    "s_cam_strategy": "17. CAM Stratejisi",
    "s_toolpath_summary": "18. Takim Yolu Ozeti",
    "s_verification": "19. Dogrulama",
    "s_collision": "20. Carpisma / Erisim / Zarf",
    "s_simulation": "21. Simulasyon",
    "s_cost_analysis": "22. Maliyet Analizi",
    "s_rfq_summary": "23. Teklif Ozeti",
    "s_warnings": "24. Uyarilar / Blokajlar",
    "s_provenance": "25. Kaynak Ozeti",
    "s_engineering_status": "26. Muhendislik Onay Durumu",
    "s_readiness": "27. Son Hazirlik Durumu",
    "s_next_actions": "28. Onerilen Sonraki Adimlar",
    "s_disclaimer": "Guvenlik Bildirimi",
    "plan_id": "Plan Kimligi",
    "part_id": "Parca Referansi",
    "drawing_number": "Cizim Numarasi",
    "revision": "Revizyon",
    "status": "Durum",
    "release_gate": "Yayin Kapisi",
    "completeness": "Genel Tamlik",
    "generated_at": "Olusturulma",
    "operations_count": "Operasyonlar",
    "tools_count": "Takimlar",
    "machines_count": "Tezgahlar",
    "open_items": "Acik Maddeler",
    "blocking_items": "Bloke Edici Maddeler",
    "is_dispatchable": "GONDERILEBILIR",
    "production_released": "URETIM_CIKISI",
    "auto_approved": "OTOMATIK_ONAY",
    "eng_state_changed": "MUHENDISLIK_DURUMU_DEGISTIRILDI",
    "readiness": "Genel Hazirlik Durumu",
    "na": "N/A",
    "col_severity": "Onem",
    "col_category": "Kategori",
    "col_description": "Aciklama",
    "col_resolution": "Cozum Ipucu",
    "col_col_status": "Durum",
    "col_op_no": "#",
    "col_op_type": "Operasyon Turu",
    "col_machine": "Tezgah",
    "col_tool": "Takim",
    "col_vc": "Vc (m/dak)",
    "col_feed": "Ilerleme (mm/dak)",
    "col_rpm": "Devir",
    "col_ap": "ap (mm)",
    "col_ae": "ae (mm)",
    "col_source": "Kaynak",
    "col_char": "Ozellik",
    "col_type": "Tur",
    "col_criticality": "Kritiklik",
    "col_stage": "Asama",
    "col_method": "Yontem",
    "col_gage": "Olcum Aleti",
    "col_tool_id": "Takim Kimligi",
    "col_tool_label": "Takim Adi",
    "col_holder": "Tutucu",
    "col_qty": "Adet",
    "col_machine_id": "Tezgah Kimligi",
    "col_machine_label": "Tezgah",
    "col_machine_type": "Tezgah Turu",
}


def _lbl(key: str, lang: ReportLanguage) -> str:
    if lang == ReportLanguage.TR:
        return _LABELS_TR.get(key, _LABELS_EN.get(key, key))
    return _LABELS_EN.get(key, key)


def _safe(v: Any) -> str:
    if v is None:
        return "N/A"
    s = str(v)
    return s if s.strip() else "N/A"


def _pct(v: float) -> str:
    return f"{v:.0%}"


def _enum_val(v: Any) -> str:
    if v is None:
        return "N/A"
    return str(v.value) if hasattr(v, "value") else str(v)


# ---------------------------------------------------------------------------
# Section builders (each returns None if section is empty/unavailable)
# ---------------------------------------------------------------------------

def _s_disclaimer(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection:
    text = (
        "TASLAK -- Muhendis incelemesi gereklidir. "
        "IS_DISPATCHABLE=HAYIR. URETIM_CIKISI=HAYIR. OTOMATIK_ONAY=HAYIR. "
        "Bu rapor yalnizca referans amaclidir."
        if L == ReportLanguage.TR else
        "DRAFT -- Engineering review required. "
        "IS_DISPATCHABLE=NO. PRODUCTION_RELEASED=NO. AUTO_APPROVED=NO. "
        "This report is for reference only. No CNC machine writes have been performed."
    )
    return ReportSection(
        section_id="disclaimer",
        title=_lbl("s_disclaimer", L),
        content=[ReportWarningBox(text=text, level="SAFETY")],
    )


def _s_executive_summary(
    plan: ManufacturingPlan,
    L: ReportLanguage,
    readiness: ReadinessStatus,
    generated_at: str,
) -> ReportSection:
    blocking = [i for i in plan.open_items if _enum_val(i.severity) == "BLOCKING"]
    items = [
        (_lbl("plan_id", L), _safe(plan.plan_id)),
        (_lbl("part_id", L), _safe(plan.part_id)),
        (_lbl("drawing_number", L), _safe(plan.drawing_number)),
        (_lbl("revision", L), _safe(plan.revision)),
        (_lbl("status", L), _enum_val(plan.status)),
        (_lbl("completeness", L), _pct(plan.completeness.overall_completeness)),
        (_lbl("operations_count", L), str(len(plan.operations))),
        (_lbl("tools_count", L), str(len(plan.tool_list))),
        (_lbl("machines_count", L), str(len(plan.machine_list))),
        (_lbl("open_items", L), str(len(plan.open_items))),
        (_lbl("blocking_items", L), str(len(blocking))),
        (_lbl("readiness", L), str(readiness)),
        (_lbl("is_dispatchable", L), "NO"),
        (_lbl("production_released", L), "NO"),
        (_lbl("auto_approved", L), "NO"),
        (_lbl("eng_state_changed", L), "NO"),
        (_lbl("generated_at", L), generated_at),
    ]
    return ReportSection(
        section_id="executive_summary",
        title=_lbl("s_executive_summary", L),
        content=[ReportKeyValue(items=items)],
    )


def _s_part_info(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection:
    items = [
        (_lbl("plan_id", L), _safe(plan.plan_id)),
        (_lbl("drawing_number", L), _safe(plan.drawing_number)),
        (_lbl("revision", L), _safe(plan.revision)),
        (_lbl("part_id", L), _safe(plan.part_id)),
        (_lbl("release_gate", L), _safe(plan.release_gate)),
        (_lbl("completeness", L), _pct(plan.completeness.overall_completeness)),
    ]
    return ReportSection(
        section_id="part_info",
        title=_lbl("s_part_info", L),
        content=[ReportKeyValue(items=items)],
    )


def _s_source_integrity(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    fingerprints = {
        "drawing_fingerprint": plan.drawing_fingerprint,
        "requirements_fingerprint": plan.requirements_fingerprint,
        "route_fingerprint": plan.route_fingerprint,
        "traceability_fingerprint": plan.traceability_fingerprint,
    }
    any_set = any(v for v in fingerprints.values())
    if not any_set:
        return None
    rows = [
        TableRow(cells=[k, _safe(v)])
        for k, v in fingerprints.items()
        if v
    ]
    return ReportSection(
        section_id="source_integrity",
        title=_lbl("s_source_integrity", L),
        content=[ReportTable(
            headers=["Hash Type", "Value"],
            rows=rows,
            caption=(
                "Source file fingerprints for audit traceability"
                if L != ReportLanguage.TR else
                "Kaynak dosya parmak izleri"
            ),
        )],
    )


def _s_process_plan(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not plan.operations:
        return None
    rows = [
        TableRow(cells=[
            _safe(op.op_number),
            _enum_val(op.operation_type),
            _safe(op.machine_label or op.machine_id),
            _safe(op.tool_id),
            _safe(op.target_tolerance),
            _safe(op.surface_finish),
            _safe(op.inspection_note),
        ])
        for op in plan.operations
    ]
    return ReportSection(
        section_id="process_plan",
        title=_lbl("s_process_plan", L),
        content=[ReportTable(
            headers=[
                _lbl("col_op_no", L), _lbl("col_op_type", L),
                _lbl("col_machine", L), _lbl("col_tool", L),
                "Tolerance", "Surface Finish", "Inspection Note",
            ],
            rows=rows,
            caption=f"{len(plan.operations)} operations",
        )],
    )


def _s_machine_selection(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not plan.machine_list:
        return None
    rows = [
        TableRow(cells=[
            _safe(m.machine_id),
            _safe(m.machine_label),
            _safe(m.machine_type),
        ])
        for m in plan.machine_list
    ]
    return ReportSection(
        section_id="machine_selection",
        title=_lbl("s_machine_selection", L),
        content=[ReportTable(
            headers=[
                _lbl("col_machine_id", L),
                _lbl("col_machine_label", L),
                _lbl("col_machine_type", L),
            ],
            rows=rows,
        )],
    )


def _s_tool_selection(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not plan.tool_list:
        return None
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
    return ReportSection(
        section_id="tool_selection",
        title=_lbl("s_tool_selection", L),
        content=[ReportTable(
            headers=[
                _lbl("col_tool_id", L), _lbl("col_tool_label", L),
                _lbl("col_type", L), _lbl("col_holder", L),
                _lbl("col_qty", L),
            ],
            rows=rows,
        )],
    )


def _s_cutting_parameters(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not plan.parameter_table:
        return None
    rows = [
        TableRow(cells=[
            _enum_val(p.operation_type),
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
    return ReportSection(
        section_id="cutting_parameters",
        title=_lbl("s_cutting_parameters", L),
        content=[ReportTable(
            headers=[
                _lbl("col_op_type", L), _lbl("col_vc", L), "fz (mm/tooth)",
                _lbl("col_ap", L), _lbl("col_ae", L),
                _lbl("col_feed", L), _lbl("col_rpm", L),
                _lbl("col_source", L), "Confidence",
            ],
            rows=rows,
        )],
    )


def _s_operations_full(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not plan.operations:
        return None
    rows = [
        TableRow(cells=[
            _safe(op.op_number),
            _enum_val(op.operation_type),
            _safe(op.machine_label or op.machine_id),
            _safe(op.tool_id),
            _safe(op.cutting_speed_m_min),
            _safe(op.feed_rate_mm_min),
            _safe(op.rpm),
            _safe(op.ap_mm),
            _safe(op.ae_mm),
            _safe(op.coolant_note),
        ])
        for op in plan.operations
    ]
    return ReportSection(
        section_id="cam_strategy",
        title=_lbl("s_cam_strategy", L),
        content=[ReportTable(
            headers=[
                _lbl("col_op_no", L), _lbl("col_op_type", L),
                _lbl("col_machine", L), _lbl("col_tool", L),
                _lbl("col_vc", L), _lbl("col_feed", L),
                _lbl("col_rpm", L), _lbl("col_ap", L),
                _lbl("col_ae", L), "Coolant",
            ],
            rows=rows,
            caption=f"{len(plan.operations)} operations",
        )],
    )


def _s_inspection(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not (plan.inspection_plan and plan.inspection_plan.rows):
        return None
    rows = [
        TableRow(cells=[
            _safe(r.char_label),
            _enum_val(r.char_type),
            _enum_val(r.criticality),
            _enum_val(r.stage),
            _enum_val(r.method),
            _safe(r.gage_suggestion),
        ])
        for r in plan.inspection_plan.rows
    ]
    return ReportSection(
        section_id="verification",
        title=_lbl("s_verification", L),
        content=[ReportTable(
            headers=[
                _lbl("col_char", L), _lbl("col_type", L),
                _lbl("col_criticality", L), _lbl("col_stage", L),
                _lbl("col_method", L), _lbl("col_gage", L),
            ],
            rows=rows,
        )],
    )


def _s_control_plan(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not (plan.control_plan and plan.control_plan.rows):
        return None
    rows = [
        TableRow(cells=[
            _safe(r.char_label),
            _enum_val(r.char_type),
            _enum_val(r.criticality),
            _safe(r.specification),
            _enum_val(r.method),
            _safe(r.gage_suggestion),
        ])
        for r in plan.control_plan.rows
    ]
    return ReportSection(
        section_id="control_plan",
        title="Control Plan",
        content=[ReportTable(
            headers=[
                _lbl("col_char", L), _lbl("col_type", L),
                _lbl("col_criticality", L), "Specification",
                _lbl("col_method", L), _lbl("col_gage", L),
            ],
            rows=rows,
        )],
    )


def _s_warnings(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection | None:
    if not plan.open_items:
        return None
    rows = [
        TableRow(cells=[
            _enum_val(i.severity),
            _enum_val(i.category),
            _safe(i.description),
            _safe(i.resolution_hint),
            _enum_val(i.status),
        ])
        for i in plan.open_items
    ]
    return ReportSection(
        section_id="warnings",
        title=_lbl("s_warnings", L),
        content=[ReportTable(
            headers=[
                _lbl("col_severity", L), _lbl("col_category", L),
                _lbl("col_description", L), _lbl("col_resolution", L),
                _lbl("col_col_status", L),
            ],
            rows=rows,
        )],
    )


def _s_provenance(
    plan: ManufacturingPlan,
    L: ReportLanguage,
    generated_at: str,
) -> ReportSection:
    items = [
        ("Source Type", "ManufacturingPlan"),
        ("Source ID", _safe(plan.plan_id)),
        ("Revision", _safe(plan.revision)),
        ("Status at Export", _enum_val(plan.status)),
        ("Generated At", generated_at),
        ("Auto Approved", "NO"),
        ("Engineering State Modified", "NO"),
        ("Is Dispatchable", "NO"),
        ("Production Released", "NO"),
    ]
    return ReportSection(
        section_id="provenance",
        title=_lbl("s_provenance", L),
        content=[ReportKeyValue(items=items)],
    )


def _s_engineering_status(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection:
    items = [
        ("IS_DISPATCHABLE", "NO"),
        ("PRODUCTION_RELEASED", "NO"),
        ("AUTO_APPROVED", "NO"),
        ("REVIEW_REQUIRED", "YES"),
        ("ENGINEERING_STATE_CHANGED", "NO"),
        ("Plan Status", _enum_val(plan.status)),
        ("Release Gate", _safe(plan.release_gate)),
    ]
    return ReportSection(
        section_id="engineering_status",
        title=_lbl("s_engineering_status", L),
        content=[ReportKeyValue(items=items)],
    )


def _s_readiness(
    plan: ManufacturingPlan,
    L: ReportLanguage,
    readiness: ReadinessStatus,
) -> ReportSection:
    blocking = [i for i in plan.open_items if _enum_val(i.severity) == "BLOCKING"]
    body_en = (
        f"Overall Readiness: {readiness}\n"
        f"Blocking items: {len(blocking)}\n"
        f"Total open items: {len(plan.open_items)}\n"
        "PRODUCTION_APPROVED: NOT SET — explicit production approval workflow required."
    )
    body_tr = (
        f"Genel Hazirlik: {readiness}\n"
        f"Bloke edici maddeler: {len(blocking)}\n"
        f"Toplam acik maddeler: {len(plan.open_items)}\n"
        "URETIM_ONAYLANDI: AYARLANMADI — acik uretim onay sureci gereklidir."
    )
    return ReportSection(
        section_id="readiness",
        title=_lbl("s_readiness", L),
        content=[ReportText(body=body_tr if L == ReportLanguage.TR else body_en)],
    )


def _s_next_actions(plan: ManufacturingPlan, L: ReportLanguage) -> ReportSection:
    blocking = [i for i in plan.open_items if _enum_val(i.severity) == "BLOCKING"]
    lines = []
    if blocking:
        lines.append("BLOCKERS must be resolved before engineering review:")
        for b in blocking[:5]:
            lines.append(f"  - [{_enum_val(b.category)}] {_safe(b.description)}")
    else:
        lines.append("No BLOCKING items.")
    lines.append("")
    lines.append("Required before production release:")
    lines.append("  1. Engineer review and sign-off on this report")
    lines.append("  2. Explicit production approval workflow")
    lines.append("  3. Machine capability verification")
    lines.append("  4. Tool availability confirmation")
    return ReportSection(
        section_id="next_actions",
        title=_lbl("s_next_actions", L),
        content=[ReportText(body="\n".join(lines))],
    )


# ---------------------------------------------------------------------------
# Sections that are DEFERRED / NOT_AVAILABLE in current implementation
# ---------------------------------------------------------------------------

def _s_deferred(section_id: str, title: str, reason: str) -> ReportSection:
    """Placeholder for sections where data source is not yet integrated."""
    return ReportSection(
        section_id=section_id,
        title=title,
        content=[ReportWarningBox(
            text=f"NOT_AVAILABLE: {reason}",
            level="WARNING",
        )],
    )


# ---------------------------------------------------------------------------
# Readiness calculation
# ---------------------------------------------------------------------------

def _compute_readiness(plan: ManufacturingPlan) -> ReadinessStatus:
    blocking = [i for i in plan.open_items if _enum_val(i.severity) == "BLOCKING"]
    if blocking:
        return ReadinessStatus.BLOCKED
    if plan.completeness.overall_completeness >= 0.9:
        return ReadinessStatus.READY_FOR_REVIEW
    if plan.completeness.overall_completeness >= 0.5:
        return ReadinessStatus.PARTIAL
    return ReadinessStatus.NOT_VERIFIABLE


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_full_manufacturing_report(
    plan: ManufacturingPlan,
    *,
    language: ReportLanguage = ReportLanguage.EN,
    units: ReportUnits = ReportUnits.METRIC,
    report_id: str | None = None,
    section_ids: list[str] | None = None,
) -> ReportDocument:
    """Build a 28-section ReportDocument from a ManufacturingPlan.

    The source plan is NEVER modified.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always.

    section_ids: if provided, only sections with matching section_id are included
                 (disclaimer and safety sections are always included).
    """
    assert not REPORT_GENERATION_ENGINEERING_STATE_CHANGED
    assert not REPORT_IS_DISPATCHABLE
    assert not REPORT_PRODUCTION_RELEASED
    assert not REPORT_AUTO_APPROVED
    assert REPORT_REVIEW_REQUIRED

    rid = report_id or f"RPT-FMR-{uuid.uuid4().hex[:12].upper()}"
    generated_at = ReportDocument.now_utc()
    L = language

    readiness = _compute_readiness(plan)

    metadata = ReportMetadata(
        report_id=rid,
        report_type=ReportType.FULL_MANUFACTURING_REPORT,
        report_status=ReportStatus.REVIEW_REQUIRED,
        part_reference=plan.part_id,
        drawing_number=plan.drawing_number,
        revision=plan.revision,
        generated_at=generated_at,
        generated_by="MachiningPro AI -- full report builder",
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
        source_status=_enum_val(plan.status),
        engineering_state_modified=False,
        auto_approved=False,
    )

    # Build all candidate sections
    candidates: list[ReportSection | None] = [
        _s_disclaimer(plan, L),  # always included
        _s_executive_summary(plan, L, readiness, generated_at),
        _s_part_info(plan, L),
        _s_deferred("input_files", _lbl("s_input_files", L),
                    "CAD file attachment integration not yet available"),
        _s_source_integrity(plan, L),
        _s_deferred("drawing_analysis", _lbl("s_drawing_analysis", L),
                    "Drawing analysis module integration pending"),
        _s_deferred("cad_geometry", _lbl("s_cad_geometry", L),
                    "CAD geometry integration pending"),
        _s_deferred("topology", _lbl("s_topology", L),
                    "STEP/B-Rep topology integration pending"),
        _s_deferred("features", _lbl("s_features", L),
                    "Feature recognition integration pending"),
        _s_deferred("dimensions", _lbl("s_dimensions", L),
                    "Drawing dimension integration pending"),
        _s_deferred("tolerances", _lbl("s_tolerances", L),
                    "GD&T tolerance integration pending"),
        _s_deferred("material", _lbl("s_material", L),
                    "Material specification integration pending"),
        _s_process_plan(plan, L),
        _s_machine_selection(plan, L),
        _s_tool_selection(plan, L),
        _s_cutting_parameters(plan, L),
        _s_deferred("wcs_setup", _lbl("s_wcs_setup", L),
                    "WCS / Setup integration pending"),
        _s_operations_full(plan, L),
        _s_deferred("toolpath_summary", _lbl("s_toolpath_summary", L),
                    "Toolpath integration pending"),
        _s_inspection(plan, L),
        _s_deferred("collision", _lbl("s_collision", L),
                    "Collision/reach/envelope analysis not yet available"),
        _s_deferred("simulation", _lbl("s_simulation", L),
                    "Simulation integration pending"),
        _s_deferred("cost_analysis", _lbl("s_cost_analysis", L),
                    "Cost analysis integration pending"),
        _s_deferred("rfq_summary", _lbl("s_rfq_summary", L),
                    "RFQ integration pending"),
        _s_warnings(plan, L),
        _s_provenance(plan, L, generated_at),
        _s_engineering_status(plan, L),
        _s_readiness(plan, L, readiness),
        _s_next_actions(plan, L),
        _s_control_plan(plan, L),
    ]

    # Filter to non-None; apply section_ids if requested
    # Disclaimer/safety sections are always included regardless of filter
    always_include = {"disclaimer", "engineering_status"}
    sections: list[ReportSection] = []
    for s in candidates:
        if s is None:
            continue
        if section_ids is not None and s.section_id not in always_include:
            if s.section_id not in section_ids:
                continue
        sections.append(s)

    doc = ReportDocument(
        metadata=metadata,
        provenance=provenance,
        sections=sections,
    )
    assert not doc.metadata.engineering_state_changed
    return doc
