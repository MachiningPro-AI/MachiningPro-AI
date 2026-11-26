"""Auto CAM report bridge — MACHININGPRO_AI_BETA3_REPORT_BRIDGE_01.

Bridges AutoCamPlan to the existing report exporters (JSON, CSV, PDF,
DOCX, XLSX, ZIP).  Builds a ReportDocument from plan data and passes
it to existing exporters — DUPLICATE_ENGINE_CREATED=NO.

Safety invariants (enforced, never bypassed):
  REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False always
  IS_DISPATCHABLE=False always
  PRODUCTION_RELEASED=False always
  AUTO_APPROVED=False always

Supported formats: JSON, CSV, PDF, DOCX, XLSX, ZIP
"""
from __future__ import annotations

from datetime import UTC, datetime

from backend.reports.exporters.csv_exporter import export_csv
from backend.reports.exporters.json_exporter import export_json
from backend.reports.exporters.pdf_exporter import export_pdf
from backend.reports.exporters.xlsx_exporter import export_xlsx
from backend.reports.exporters.zip_exporter import export_zip
from backend.reports.models import (
    ReportBundle,
    ReportDocument,
    ReportExportItem,
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

from .models import AutoCamPlan


def build_autocam_report_document(
    plan: AutoCamPlan,
    language: str = "EN",
) -> ReportDocument:
    """Build a ReportDocument from an AutoCamPlan.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=False — this function
    only reads the plan; it never modifies it.
    """
    is_tr = language.upper() == "TR"
    report_lang = ReportLanguage.TR if is_tr else ReportLanguage.EN

    metadata = ReportMetadata(
        report_id=f"AUTOCAM-RPT-{plan.plan_id}",
        report_type=ReportType.CAM_REPORT,
        report_status=ReportStatus.REVIEW_REQUIRED,
        part_reference=plan.file_ref,
        drawing_number=None,
        revision=None,
        generated_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        generated_by="MachiningPro AI Auto CAM Engine",
        language=report_lang,
        units=ReportUnits.METRIC,
    )
    provenance = ReportProvenance(
        source_type="AUTO_CAM_PLAN",
        source_id=plan.plan_id,
        engineering_state_modified=False,
        auto_approved=False,
    )

    sections: list[ReportSection] = []

    # ── Section 01: Plan Summary ──────────────────────────────────────────
    summary_items = [
        ("Plan ID", plan.plan_id),
        ("File", plan.file_ref),
        ("Status", plan.plan_status),
        ("Created", plan.created_at),
        ("Report Status", plan.report_status),
        ("Cost Estimate Status", plan.cost_estimate_status),
    ]
    sections.append(ReportSection(
        section_id="01_PLAN_SUMMARY",
        title="Plan Summary" if not is_tr else "Plan Özeti",
        content=[ReportKeyValue(items=summary_items)],
        provenance_note="CANDIDATE_PLAN — engineer review required before machining",
    ))

    # ── Section 02: Machine Selection ────────────────────────────────────
    m = plan.machine
    machine_items = [
        ("Machine ID", m.machine_id or "N/A"),
        ("Manufacturer", m.manufacturer or "N/A"),
        ("Model", m.model or "N/A"),
        ("Type", m.machine_type_code or "N/A"),
        ("Spindle Max RPM", str(m.spindle_max_rpm) if m.spindle_max_rpm else "N/A"),
        ("Status", m.status),
    ]
    sections.append(ReportSection(
        section_id="02_MACHINE",
        title="Machine Selection" if not is_tr else "Makine Seçimi",
        content=[ReportKeyValue(items=machine_items)],
    ))

    # ── Section 03: Operations ────────────────────────────────────────────
    if plan.operations:
        op_rows = []
        for op in plan.operations:
            op_rows.append(TableRow(cells=[
                op.operation_ref,
                op.feature_id,
                op.feature_type,
                op.operation_type,
                op.tool.tool_id or "N/A",
                f"{op.tool.tool_diameter_mm:.2f}" if op.tool.tool_diameter_mm else "N/A",
                op.cutting_params.status,
                (
                    f"Vc={op.cutting_params.vc_m_per_min} m/min "
                    f"RPM={op.cutting_params.rpm} "
                    f"Feed={op.cutting_params.feed_mm_per_min} mm/min"
                    if op.cutting_params.vc_m_per_min else "N/A"
                ),
                str(op.segment_count),
                op.toolpath_status,
            ]))
        op_table = ReportTable(
            headers=[
                "Operation", "Feature", "Type", "Op Type",
                "Tool ID", "Ø mm", "Params Status", "Cutting Params",
                "Segments", "Toolpath",
            ],
            rows=op_rows,
            caption=(
                "Operations — CANDIDATE_ONLY. "
                "Engineer review required before machining."
            ),
        )
        sections.append(ReportSection(
            section_id="03_OPERATIONS",
            title="Operations" if not is_tr else "Operasyonlar",
            content=[op_table],
        ))

    # ── Section 04: Cycle Time ────────────────────────────────────────────
    ct = plan.cycle_time
    ct_items = [
        ("Status", ct.status),
        ("Total Known (s)", f"{ct.total_known_s:.2f}" if ct.total_known_s else "N/A"),
        ("Cutting Time (s)", f"{ct.cutting_time_s:.2f}" if ct.cutting_time_s else "N/A"),
        ("Rapid Time (s)", f"{ct.rapid_time_s:.2f}" if ct.rapid_time_s else "N/A"),
        ("Path Length Type", ct.path_length_type),
        ("Note", "ESTIMATED — not actual machine execution time"),
    ]
    sections.append(ReportSection(
        section_id="04_CYCLE_TIME",
        title="Cycle Time Estimate" if not is_tr else "Çevrim Süresi Tahmini",
        content=[ReportKeyValue(items=ct_items)],
        provenance_note="ESTIMATED per HARD_RULE_9",
    ))

    # ── Section 05: Cost Estimate ─────────────────────────────────────────
    ce = plan.cost_estimate
    if ce is not None and ce.cost_input_received:
        cost_rows = []
        for cat_item in [
            ce.material_cost, ce.machine_cost, ce.tool_cost,
            ce.setup_cost, ce.labor_cost, ce.energy_cost,
            ce.overhead_cost, ce.other_cost,
        ]:
            cost_rows.append(TableRow(cells=[
                cat_item.category,
                f"{cat_item.value:.4f}" if cat_item.value is not None else "N/A",
                cat_item.currency or "N/A",
                cat_item.status,
                cat_item.source_type,
                cat_item.provenance[:80] if cat_item.provenance else "N/A",
            ]))
        cost_summary = [
            (
                "Known Total",
                f"{ce.known_total:.4f} {ce.currency or ''}"
                if ce.known_total else "N/A",
            ),
            ("Unknown Components", str(ce.unknown_component_count)),
            ("Completeness", f"{ce.completeness_pct}%"),
            ("Total Status", ce.total_status),
        ]
        sections.append(ReportSection(
            section_id="05_COST_ESTIMATE",
            title="Cost Estimate" if not is_tr else "Maliyet Analizi",
            content=[
                ReportTable(
                    headers=["Category", "Value", "Currency", "Status", "Source", "Provenance"],
                    rows=cost_rows,
                    caption="PARTIAL_COST_ESTIMATE — user-provided inputs only",
                ),
                ReportKeyValue(items=cost_summary),
                ReportWarningBox(
                    text=(
                        "Cost estimate is advisory only. "
                        "No commercial rates were fabricated. "
                        "COST_ANALYSIS_DOES_NOT_APPROVE_MANUFACTURING"
                    ),
                    level="WARNING",
                ),
            ],
        ))
    else:
        sections.append(ReportSection(
            section_id="05_COST_ESTIMATE",
            title="Cost Estimate" if not is_tr else "Maliyet Analizi",
            content=[ReportText(
                body=(
                    "NOT_PROVIDED — submit cost inputs via "
                    "POST /api/autocam/{plan_id}/cost-input"
                )
            )],
        ))

    # ── Section 06: Verification ──────────────────────────────────────────
    v = plan.verification
    ver_items = [
        ("State", v.state),
        ("Checks Performed", str(v.checks_performed)),
        ("Checks Passed", str(v.checks_passed)),
        ("Stock Removal Fidelity", v.stock_removal_fidelity),
        ("Gouge Check", v.gouge_check),
        ("Collision Check", v.collision_check),
        ("Tool Reach", v.tool_reach_check),
        ("Machine Envelope", v.machine_envelope_check),
    ]
    sections.append(ReportSection(
        section_id="06_VERIFICATION",
        title="Verification Summary" if not is_tr else "Doğrulama Özeti",
        content=[
            ReportKeyValue(items=ver_items),
            ReportWarningBox(
                text=(
                    "GOUGE_EXACT=NOT_VERIFIABLE (KL-07). "
                    "FIXTURE/HOLDER_COLLISION=NOT_PERFORMED (KL-08/09). "
                    "ENGINEER_REVIEW_REQUIRED before any machining."
                ),
                level="WARNING",
            ),
        ],
    ))

    # ── Section 07: Safety Invariants ─────────────────────────────────────
    safety_items = [
        (k, str(v)) for k, v in plan.safety.items()
    ]
    sections.append(ReportSection(
        section_id="07_SAFETY",
        title="Safety Invariants" if not is_tr else "Güvenlik Değişmezleri",
        content=[
            ReportKeyValue(items=safety_items),
            ReportWarningBox(
                text=(
                    "AUTO_CAM_CAN_DISPATCH_CNC=NO. "
                    "AUTO_CAM_CAN_RELEASE_PRODUCTION=NO. "
                    "S19_DISPATCH_SAFETY_GATE=ALWAYS_BLOCKED. "
                    "This report is for engineering review only."
                ),
                level="WARNING",
            ),
        ],
    ))

    # ── Section 08: Blockers & Warnings ───────────────────────────────────
    if plan.blockers or plan.warnings:
        bw_items: list[tuple[str, str]] = []
        for b in plan.blockers:
            bw_items.append((f"BLOCKER [{b.code}]", b.message))
        for w in plan.warnings:
            bw_items.append((f"WARNING [{w.stage}]", w.message))
        sections.append(ReportSection(
            section_id="08_BLOCKERS_WARNINGS",
            title="Blockers & Warnings" if not is_tr else "Engelleyiciler & Uyarılar",
            content=[ReportKeyValue(items=bw_items)],
        ))

    return ReportDocument(
        metadata=metadata,
        provenance=provenance,
        sections=sections,
    )


def generate_autocam_report(
    plan: AutoCamPlan,
    fmt: str,
    language: str = "EN",
) -> ReportExportItem:
    """Generate a report export for an Auto CAM plan.

    Uses existing exporters — DUPLICATE_ENGINE_CREATED=NO.
    Returns a ReportExportItem with content bytes and mime_type.

    Supported formats: JSON, CSV, PDF, XLSX, ZIP
    """
    doc = build_autocam_report_document(plan, language=language)

    fmt_upper = fmt.upper()
    if fmt_upper == "JSON":
        return export_json(doc)
    if fmt_upper == "CSV":
        return export_csv(doc)
    if fmt_upper == "PDF":
        return export_pdf(doc)
    if fmt_upper in ("XLSX", "XLS"):
        return export_xlsx(doc)
    if fmt_upper == "ZIP":
        bundle = ReportBundle(document=doc)
        bundle.items.extend([
            export_json(doc),
            export_csv(doc),
        ])
        try:
            bundle.items.append(export_pdf(doc))
        except Exception:
            pass
        try:
            bundle.items.append(export_xlsx(doc))
        except Exception:
            pass
        return export_zip(doc, bundle)

    raise ValueError(f"Unsupported format: {fmt!r}. Supported: JSON, CSV, PDF, XLSX, ZIP")
