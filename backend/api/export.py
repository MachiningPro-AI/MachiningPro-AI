"""Level-20 authenticated export/download endpoints.

Safety invariants:
  OWNERSHIP_AUTH_PROTECTION=YES    — all endpoints require Bearer token
  SAFE_CONTENT_DISPOSITION=YES     — filenames are sanitised
  NO_SERVER_PATH_IN_RESPONSE=YES
  NC_OFFLINE_LABEL=YES             — NC exports are always marked OFFLINE_CANDIDATE
  NO_CNC_TRANSFER=YES
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import Response

from ..export.export_service import (
    export_dfm_json,
    export_nc_manifest_json,
    export_plan_html,
    export_plan_json,
    export_stage_csv,
)
from ..observability import metrics
from ..persistence import WorkflowStoreError, get_workflow_store
from .auth import verify_token

router = APIRouter(prefix="/api/workflow", tags=["export"])

_SAFE_FILENAME_RE = re.compile(r"[^A-Za-z0-9_\-]")


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


def _safe_filename(wf_id: str, suffix: str) -> str:
    safe = _SAFE_FILENAME_RE.sub("_", wf_id)[:40]
    return f"machiningpro_{safe}{suffix}"


def _get_wf(workflow_id: str):
    try:
        store = get_workflow_store()
        wf = store.load(workflow_id)
    except WorkflowStoreError as exc:
        metrics.increment(metrics.PERSISTENCE_ERROR)
        raise HTTPException(503, detail="Persistence unavailable") from exc
    if wf is None:
        raise HTTPException(404, detail=f"Workflow {workflow_id!r} not found")
    return wf


@router.get("/{workflow_id}/export/plan.json")
def export_plan_as_json(
    workflow_id: str,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> Response:
    """Download manufacturing plan as JSON."""
    metrics.increment(metrics.EXPORT_REQUESTED)
    wf = _get_wf(workflow_id)
    data = export_plan_json(wf)
    filename = _safe_filename(workflow_id, "_plan.json")
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{workflow_id}/export/plan.html")
def export_plan_as_html(
    workflow_id: str,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> Response:
    """Download manufacturing plan as HTML report."""
    metrics.increment(metrics.EXPORT_REQUESTED)
    wf = _get_wf(workflow_id)
    data = export_plan_html(wf)
    filename = _safe_filename(workflow_id, "_plan.html")
    return Response(
        content=data,
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{workflow_id}/export/stages.csv")
def export_stages_as_csv(
    workflow_id: str,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> Response:
    """Download stage summary as CSV."""
    metrics.increment(metrics.EXPORT_REQUESTED)
    wf = _get_wf(workflow_id)
    data = export_stage_csv(wf)
    filename = _safe_filename(workflow_id, "_stages.csv")
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{workflow_id}/export/dfm.json")
def export_dfm_as_json(
    workflow_id: str,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> Response:
    """Download DFM analysis summary as JSON."""
    metrics.increment(metrics.EXPORT_REQUESTED)
    wf = _get_wf(workflow_id)
    data = export_dfm_json(wf)
    filename = _safe_filename(workflow_id, "_dfm.json")
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{workflow_id}/export/nc-manifest.json")
def export_nc_manifest(
    workflow_id: str,
    _auth: dict = Depends(_require_user),  # noqa: B008
) -> Response:
    """Download NC candidate manifest as JSON (OFFLINE_CANDIDATE — not for CNC dispatch)."""
    metrics.increment(metrics.EXPORT_REQUESTED)
    wf = _get_wf(workflow_id)
    data = export_nc_manifest_json(wf)
    filename = _safe_filename(workflow_id, "_nc_manifest.json")
    return Response(
        content=data,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
