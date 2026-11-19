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
from ..reports.report_service import REPORT_TYPES, generate_manufacturing_plan_report
from .auth import verify_token

router = APIRouter(prefix="/api/reports", tags=["reports"])

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_\-]")

_FORMAT_MIME: dict[str, str] = {
    "PDF": "application/pdf",
    "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "CSV": "text/csv; charset=utf-8",
    "JSON": "application/json; charset=utf-8",
    "ZIP": "application/zip",
}


def _require_user(authorization: str | None = Header(default=None)) -> dict[str, Any]:  # noqa: B008
    scheme, _, token = (authorization or "").partition(" ")
    payload = (
        verify_token(token.strip())
        if scheme.lower() == "bearer" and token.strip()
        else None
    )
    if payload is None:
        raise HTTPException(401, detail={"error_code": "UNAUTHENTICATED"})
    return payload


class GenerateReportRequest(BaseModel):
    workflow_id: str
    report_type: str = "MANUFACTURING_PLAN"
    formats: list[str] = ["PDF", "JSON"]
    language: str = "EN"
    units: str = "METRIC"


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


@router.post("/generate")
def generate_report(
    req: GenerateReportRequest,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> dict[str, Any]:
    """Generate report and return metadata + download URLs.

    Does not return binary content — use /download/{format} for file download.
    REPORT_GENERATION_ENGINEERING_STATE_CHANGED=NO always.
    """
    # Resolve workflow → manufacturing plan
    try:
        store = get_workflow_store()
        wf = store.load(req.workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    if wf is None:
        raise HTTPException(404, detail=f"Workflow {req.workflow_id!r} not found")

    # Validate formats
    valid_formats = {"PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"}
    requested = []
    for f in req.formats:
        fu = f.upper()
        if fu not in valid_formats:
            raise HTTPException(400, detail=f"Unknown format: {f!r}")
        requested.append(ExportFormat(fu))

    # Validate language / units
    try:
        lang = ReportLanguage(req.language.upper())
    except ValueError as exc:
        raise HTTPException(400, detail=f"Unknown language: {req.language!r}") from exc
    try:
        units = ReportUnits(req.units.upper())
    except ValueError as exc:
        raise HTTPException(400, detail=f"Unknown units: {req.units!r}") from exc

    if req.report_type != "MANUFACTURING_PLAN":
        raise HTTPException(400, detail=f"Unsupported report type: {req.report_type!r}")

    # Get the manufacturing plan from the workflow's final_plan or stage results
    plan = getattr(wf, "manufacturing_plan", None) or getattr(wf, "final_plan", None)
    if plan is None:
        # Try to get from stage results
        from ..workflow.enums import WorkflowStage
        mp_result = wf.stage_results.get(WorkflowStage.FINAL_MANUFACTURING_PLAN)
        if mp_result and hasattr(mp_result, "plan"):
            plan = mp_result.plan
    if plan is None:
        raise HTTPException(
            422, detail="No manufacturing plan available -- run the full workflow first",
        )

    bundle = generate_manufacturing_plan_report(
        plan,
        formats=requested,
        language=lang,
        units=units,
    )

    # Return metadata + download keys (not binary content)
    items = []
    for item in bundle.items:
        items.append({
            "format": str(item.format),
            "filename": item.filename,
            "mime_type": item.mime_type,
            "size_bytes": len(item.content),
        })

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
    if fu not in {"PDF", "DOCX", "XLSX", "CSV", "JSON", "ZIP"}:
        raise HTTPException(400, detail=f"Unknown format: {format!r}")

    # Resolve workflow → manufacturing plan
    try:
        store = get_workflow_store()
        wf = store.load(req.workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    if wf is None:
        raise HTTPException(404, detail=f"Workflow {req.workflow_id!r} not found")

    try:
        lang = ReportLanguage(req.language.upper())
        units = ReportUnits(req.units.upper())
    except ValueError as exc:
        raise HTTPException(400, detail=str(exc)) from exc

    plan = getattr(wf, "manufacturing_plan", None) or getattr(wf, "final_plan", None)
    if plan is None:
        raise HTTPException(422, detail="No manufacturing plan available")

    fmt = ExportFormat(fu)
    bundle = generate_manufacturing_plan_report(plan, formats=[fmt], language=lang, units=units)
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
