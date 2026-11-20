"""Reports API — generate and download manufacturing reports.

Safety invariants:
  OWNERSHIP_AUTH_PROTECTION=YES    — all endpoints require Bearer token
  SAFE_CONTENT_DISPOSITION=YES     — filenames are sanitised
  REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always
  IS_DISPATCHABLE=NO always
  PRODUCTION_RELEASED=NO always
  AUTO_APPROVED=NO always
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from ..observability import metrics
from ..persistence import WorkflowStoreError, get_workflow_store
from ..reports.models import ExportFormat, ReportLanguage, ReportUnits
from ..reports.report_service import (
    REPORT_TYPES,
    generate_full_manufacturing_report,
    generate_manufacturing_plan_report,
    generate_synthetic_qualification_report,
)
from .auth import verify_token

router = APIRouter(prefix="/api/reports", tags=["reports"])

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_\-]")

_VALID_FORMATS = {"PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"}

_FORMAT_MIME: dict[str, str] = {
    "PDF": "application/pdf",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "CSV": "text/csv; charset=utf-8",
    "JSON": "application/json; charset=utf-8",
    "ZIP": "application/zip",
}

_PLAN_REPORT_TYPES = {
    "MANUFACTURING_PLAN",
    "FULL_MANUFACTURING_REPORT",
    "PROCESS_PLAN_REPORT",
    "MACHINE_SELECTION_REPORT",
    "TOOL_SELECTION_REPORT",
    "CUTTING_PARAMETERS_REPORT",
    "CAM_REPORT",
    "TOOLPATH_REPORT",
    "VERIFICATION_REPORT",
}


def _require_user(
    authorization: str | None = Header(default=None),  # noqa: B008
) -> dict[str, Any]:
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


def _resolve_plan(wf: Any) -> Any:
    plan = getattr(wf, "manufacturing_plan", None) or getattr(wf, "final_plan", None)
    if plan is None:
        from ..workflow.enums import WorkflowStage
        mp_result = wf.stage_results.get(WorkflowStage.FINAL_MANUFACTURING_PLAN)
        if mp_result and hasattr(mp_result, "plan"):
            plan = mp_result.plan
    # Try the ManufacturingPlanStore when final_plan_ref is set but no in-memory plan
    # (or when final_plan is a ManufacturingPlanSummary, not the full ManufacturingPlan)
    plan_ref = getattr(wf, "final_plan_ref", None)
    if plan_ref and not _is_full_plan(plan):
        try:
            from ..persistence import get_plan_store
            full = get_plan_store().get(plan_ref)
            plan = full
        except Exception:  # noqa: BLE001
            pass
    return plan


def _is_full_plan(plan: Any) -> bool:
    """Return True when plan is a full ManufacturingPlan (has operations attr)."""
    return plan is not None and hasattr(plan, "operations")


def _validate_formats(formats: list[str]) -> list[ExportFormat]:
    result = []
    for f in formats:
        fu = f.upper()
        if fu not in _VALID_FORMATS:
            raise HTTPException(400, detail=f"Unknown format: {f!r}")
        result.append(ExportFormat(fu))
    return result


def _validate_lang_units(
    language: str,
    units: str,
) -> tuple[ReportLanguage, ReportUnits]:
    try:
        lang = ReportLanguage(language.upper())
    except ValueError as exc:
        raise HTTPException(400, detail=f"Unknown language: {language!r}") from exc
    try:
        unit = ReportUnits(units.upper())
    except ValueError as exc:
        raise HTTPException(400, detail=f"Unknown units: {units!r}") from exc
    return lang, unit


class GenerateReportRequest(BaseModel):
    workflow_id: str
    report_type: str = "FULL_MANUFACTURING_REPORT"
    formats: list[str] = ["PDF", "JSON"]
    language: str = "EN"
    units: str = "METRIC"
    section_ids: list[str] | None = None
    report_id: str | None = None


@router.get("/types")
def list_report_types(
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> dict[str, Any]:
    """List available report types and their supported formats."""
    return {
        "report_types": REPORT_TYPES,
        "safety": {
            "REPORT_GENERATION_ENGINEERING_STATE_CHANGED": False,
            "IS_DISPATCHABLE": False,
            "PRODUCTION_RELEASED": False,
            "AUTO_APPROVED": False,
            "REVIEW_REQUIRED": True,
        },
    }


@router.post("/preview")
def preview_report(
    req: GenerateReportRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> dict[str, Any]:
    """Generate a preview of the report structure (no binary output).

    Returns the report section list with titles and content summaries.
    Does NOT generate export files.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
    """
    try:
        store = get_workflow_store()
        wf = store.load(req.workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    if wf is None:
        raise HTTPException(404, detail=f"Workflow {req.workflow_id!r} not found")

    lang, unit = _validate_lang_units(req.language, req.units)

    if req.report_type == "SYNTHETIC_QUALIFICATION_REPORT":
        from ..reports.builders.synthetic_qualification_report import (
            build_synthetic_qualification_report,
        )
        doc = build_synthetic_qualification_report(
            {},
            language=lang,
            units=unit,
            section_ids=req.section_ids,
        )
    elif req.report_type in _PLAN_REPORT_TYPES:
        plan = _resolve_plan(wf)
        if plan is None:
            raise HTTPException(422, detail="No manufacturing plan available")
        if req.report_type == "FULL_MANUFACTURING_REPORT":
            from ..reports.builders.full_manufacturing_report import (
                build_full_manufacturing_report,
            )
            doc = build_full_manufacturing_report(
                plan,
                language=lang,
                units=unit,
                section_ids=req.section_ids,
            )
        else:
            from ..reports.builders.manufacturing_plan_report import (
                build_manufacturing_plan_report,
            )
            doc = build_manufacturing_plan_report(plan, language=lang, units=unit)
    else:
        from ..reports.builders.generic_report import build_generic_report
        from ..reports.models import ReportType
        try:
            rtype = ReportType(req.report_type)
        except ValueError as exc:
            raise HTTPException(400, detail=f"Unknown report type: {req.report_type!r}") from exc
        doc = build_generic_report(rtype, [], language=lang, units=unit)

    sections_summary = [
        {
            "section_id": s.section_id,
            "title": s.title,
            "content_types": [type(c).__name__ for c in s.content],
            "has_data": bool(s.content),
        }
        for s in doc.sections
    ]
    return {
        "report_id": doc.metadata.report_id,
        "report_type": str(doc.metadata.report_type),
        "generated_at": doc.metadata.generated_at,
        "language": str(doc.metadata.language),
        "units": str(doc.metadata.units),
        "section_count": len(doc.sections),
        "sections": sections_summary,
        "safety": {
            "REPORT_GENERATION_ENGINEERING_STATE_CHANGED": False,
            "IS_DISPATCHABLE": False,
            "PRODUCTION_RELEASED": False,
            "AUTO_APPROVED": False,
            "REVIEW_REQUIRED": True,
        },
        "disclaimer": doc.disclaimer,
    }


@router.post("/generate")
def generate_report(
    req: GenerateReportRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> dict[str, Any]:
    """Generate report and return metadata + download URLs.

    Does not return binary content — use /generate/{format}/download for files.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
    """
    # Validate inputs before hitting the store
    requested = _validate_formats(req.formats)
    lang, unit = _validate_lang_units(req.language, req.units)

    try:
        store = get_workflow_store()
        wf = store.load(req.workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    if wf is None:
        raise HTTPException(404, detail=f"Workflow {req.workflow_id!r} not found")

    if req.report_type == "SYNTHETIC_QUALIFICATION_REPORT":
        bundle = generate_synthetic_qualification_report(
            {},
            formats=requested,
            language=lang,
            units=unit,
            section_ids=req.section_ids,
        )
    elif req.report_type in _PLAN_REPORT_TYPES:
        plan = _resolve_plan(wf)
        if plan is None:
            raise HTTPException(
                422, detail="No manufacturing plan available -- run the full workflow first",
            )
        if req.report_type == "FULL_MANUFACTURING_REPORT":
            bundle = generate_full_manufacturing_report(
                plan,
                formats=requested,
                language=lang,
                units=unit,
                report_id=req.report_id,
                section_ids=req.section_ids,
            )
        else:
            bundle = generate_manufacturing_plan_report(
                plan,
                formats=requested,
                language=lang,
                units=unit,
                report_id=req.report_id,
                section_ids=req.section_ids,
            )
    else:
        # Generic report types — no workflow data needed for structure
        from ..reports.builders.generic_report import build_generic_report
        from ..reports.exporters.csv_exporter import export_csv
        from ..reports.exporters.docx_exporter import export_docx
        from ..reports.exporters.json_exporter import export_json
        from ..reports.exporters.pdf_exporter import export_pdf
        from ..reports.exporters.xlsx_exporter import export_xlsx
        from ..reports.exporters.zip_exporter import export_zip
        from ..reports.models import ReportBundle, ReportType
        try:
            rtype = ReportType(req.report_type)
        except ValueError as exc:
            raise HTTPException(400, detail=f"Unknown report type: {req.report_type!r}") from exc
        doc = build_generic_report(rtype, [], language=lang, units=unit)
        bundle = ReportBundle(document=doc, engineering_state_changed=False)
        if ExportFormat.PDF in requested:
            bundle.items.append(export_pdf(doc))
        if ExportFormat.JSON in requested:
            bundle.items.append(export_json(doc))
        if ExportFormat.CSV in requested:
            bundle.items.append(export_csv(doc))
        if ExportFormat.XLSX in requested:
            bundle.items.append(export_xlsx(doc))
        if ExportFormat.DOCX in requested:
            bundle.items.append(export_docx(doc))
        if ExportFormat.ZIP in requested:
            bundle.items.append(export_zip(doc, bundle))

    items = [
        {
            "format": str(item.format),
            "filename": item.filename,
            "mime_type": item.mime_type,
            "size_bytes": len(item.content),
        }
        for item in bundle.items
    ]

    metrics.increment(metrics.EXPORT_REQUESTED)
    return {
        "report_id": bundle.document.metadata.report_id,
        "generated_at": bundle.document.metadata.generated_at,
        "language": str(bundle.document.metadata.language),
        "units": str(bundle.document.metadata.units),
        "items": items,
        "safety": {
            "REPORT_GENERATION_ENGINEERING_STATE_CHANGED": False,
            "IS_DISPATCHABLE": False,
            "PRODUCTION_RELEASED": False,
            "AUTO_APPROVED": False,
            "REVIEW_REQUIRED": True,
        },
        "disclaimer": bundle.document.disclaimer,
    }


@router.post("/generate/{format}/download")
def generate_and_download(
    format: str,
    req: GenerateReportRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> Response:
    """Generate and immediately download one format.

    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
    """
    fu = format.upper()
    if fu not in _VALID_FORMATS:
        raise HTTPException(400, detail=f"Unknown format: {format!r}")

    try:
        store = get_workflow_store()
        wf = store.load(req.workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    if wf is None:
        raise HTTPException(404, detail=f"Workflow {req.workflow_id!r} not found")

    lang, unit = _validate_lang_units(req.language, req.units)
    fmt = ExportFormat(fu)

    if req.report_type == "SYNTHETIC_QUALIFICATION_REPORT":
        bundle = generate_synthetic_qualification_report(
            {},
            formats=[fmt],
            language=lang,
            units=unit,
            section_ids=req.section_ids,
        )
    elif req.report_type in _PLAN_REPORT_TYPES:
        plan = _resolve_plan(wf)
        if plan is None:
            raise HTTPException(422, detail="No manufacturing plan available")
        if req.report_type == "FULL_MANUFACTURING_REPORT":
            bundle = generate_full_manufacturing_report(
                plan,
                formats=[fmt],
                language=lang,
                units=unit,
                report_id=req.report_id,
                section_ids=req.section_ids,
            )
        else:
            bundle = generate_manufacturing_plan_report(
                plan,
                formats=[fmt],
                language=lang,
                units=unit,
                report_id=req.report_id,
                section_ids=req.section_ids,
            )
    else:
        from ..reports.builders.generic_report import build_generic_report
        from ..reports.models import ReportBundle, ReportType
        try:
            rtype = ReportType(req.report_type)
        except ValueError as exc:
            raise HTTPException(400, detail=f"Unknown report type: {req.report_type!r}") from exc
        doc = build_generic_report(rtype, [], language=lang, units=unit)
        bundle = ReportBundle(document=doc, engineering_state_changed=False)
        from ..reports.exporters.csv_exporter import export_csv
        from ..reports.exporters.docx_exporter import export_docx
        from ..reports.exporters.json_exporter import export_json
        from ..reports.exporters.pdf_exporter import export_pdf
        from ..reports.exporters.xlsx_exporter import export_xlsx
        from ..reports.exporters.zip_exporter import export_zip
        exporter_map = {
            ExportFormat.PDF: export_pdf,
            ExportFormat.JSON: export_json,
            ExportFormat.CSV: export_csv,
            ExportFormat.XLSX: export_xlsx,
            ExportFormat.DOCX: export_docx,
        }
        if fmt in exporter_map:
            bundle.items.append(exporter_map[fmt](doc))
        else:  # ZIP
            bundle.items.append(export_zip(doc, bundle))

    item = bundle.get(fmt)
    if item is None:
        raise HTTPException(500, detail="Report generation failed")

    safe_fn = _SAFE_FILENAME_RE.sub("_", item.filename)
    metrics.increment(metrics.EXPORT_REQUESTED)
    return Response(
        content=item.content,
        media_type=item.mime_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_fn}"'},
    )
