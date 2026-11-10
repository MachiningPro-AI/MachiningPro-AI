"""Export service — generates structured exports from manufacturing workflow data.

Supported formats:
  JSON  — machine-readable, full plan data
  HTML  — human-readable report (via Jinja2, already a project dependency)
  CSV   — tabular data for selected report types

Safety:
  NC_EXPORT_LABEL=OFFLINE_CANDIDATE,NOT_MACHINE_APPROVED,NOT_DISPATCHED
  NO_CNC_TRANSFER=YES
  NO_SERVER_PATH_IN_EXPORT=YES
"""
from __future__ import annotations

import csv
import io
import json
import logging
from datetime import UTC, datetime
from typing import Any

from jinja2 import Environment, select_autoescape

from ..workflow.models import ManufacturingWorkflow

logger = logging.getLogger(__name__)

EXPORT_VERSION = "1.0"


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------

def export_plan_json(wf: ManufacturingWorkflow) -> bytes:
    """Export the final manufacturing plan as indented JSON bytes."""
    if wf.final_plan is None:
        return _error_json("No final plan available — run the full workflow first")

    plan = wf.final_plan
    payload = {
        "export_format": "MachiningPro-Plan-JSON",
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "safety": {
            "PRODUCTION_APPROVED": False,
            "DISPATCHED": False,
            "MACHINE_STARTED": False,
        },
        "workflow_id": wf.workflow_id,
        "part_reference": wf.part_reference,
        "revision": wf.revision,
        "status": str(wf.status),
        "objective": str(wf.objective),
        "material_ref": wf.material_ref,
        "quantity": wf.quantity,
        "plan_id": plan.plan_id,
        "blocking_issues": [
            {
                "stage": str(bi.stage),
                "code": bi.code,
                "description": bi.description,
                "required_action": bi.required_action,
            }
            for bi in plan.blocking_issues
        ],
        "known_unknowns": [
            {"category": ku.category, "description": ku.description}
            for ku in plan.known_unknowns
        ],
        "review_items": [
            {"category": ri.category, "description": ri.description, "mandatory": ri.mandatory}
            for ri in plan.review_items
        ],
        "stage_results": {
            str(stage): {
                "status": str(result.status),
                "duration_ms": result.duration_ms,
                "warnings": result.warnings,
                "errors": result.errors,
                "blocking_reasons": result.blocking_reasons,
            }
            for stage, result in wf.stage_results.items()
        },
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def export_dfm_json(wf: ManufacturingWorkflow) -> bytes:
    """Export DFM analysis summary as JSON."""
    from ..workflow.enums import WorkflowStage
    result = wf.stage_results.get(WorkflowStage.DFM)
    payload = {
        "export_format": "MachiningPro-DFM-JSON",
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "workflow_id": wf.workflow_id,
        "part_reference": wf.part_reference,
        "dfm_stage_status": str(result.status) if result else "NOT_RUN",
        "dfm_warnings": result.warnings if result else [],
        "dfm_errors": result.errors if result else [],
        "dfm_blocking_reasons": result.blocking_reasons if result else [],
        "dfm_provenance": result.provenance if result else {},
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def export_stage_csv(wf: ManufacturingWorkflow) -> bytes:
    """Export all stage statuses and durations as CSV bytes."""
    buf = io.StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["stage", "status", "duration_ms", "review_required",
                    "warning_count", "error_count"],
    )
    writer.writeheader()
    from ..workflow.enums import WorkflowStage
    for stage in WorkflowStage:
        result = wf.stage_results.get(stage)
        writer.writerow({
            "stage": str(stage),
            "status": str(result.status) if result else "NOT_STARTED",
            "duration_ms": result.duration_ms if result else "",
            "review_required": result.review_required if result else False,
            "warning_count": len(result.warnings) if result else 0,
            "error_count": len(result.errors) if result else 0,
        })
    return buf.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# HTML report export
# ---------------------------------------------------------------------------

_HTML_REPORT_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MachiningPro AI — Manufacturing Plan Report</title>
<style>
  body{font-family:system-ui,sans-serif;margin:2rem;color:#111;background:#fff}
  h1{color:#1a56db;border-bottom:2px solid #1a56db;padding-bottom:.5rem}
  h2{color:#374151;margin-top:2rem;border-bottom:1px solid #d1d5db;padding-bottom:.25rem}
  .badge{display:inline-block;padding:.15rem .6rem;border-radius:9999px;
         font-size:.8rem;font-weight:600}
  .pass{background:#d1fae5;color:#065f46}
  .partial{background:#fef3c7;color:#92400e}
  .blocked{background:#fee2e2;color:#991b1b}
  .failed{background:#fee2e2;color:#991b1b}
  .not_started{background:#f3f4f6;color:#6b7280}
  .skipped{background:#f3f4f6;color:#6b7280}
  table{border-collapse:collapse;width:100%;margin-top:1rem}
  th{background:#f9fafb;text-align:left;padding:.5rem .75rem;
     border:1px solid #e5e7eb;font-size:.85rem}
  td{padding:.4rem .75rem;border:1px solid #e5e7eb;font-size:.85rem}
  .safety-box{background:#fef9c3;border:1px solid #fcd34d;
              border-radius:.5rem;padding:1rem;margin:1rem 0}
  .safety-box strong{color:#92400e}
  .meta{color:#6b7280;font-size:.85rem;margin-top:.25rem}
  @media print{.no-print{display:none}}
</style>
</head>
<body>
<h1>MachiningPro AI — Manufacturing Plan Report</h1>
<div class="safety-box">
  <strong>⚠ Engineering Review Required</strong><br>
  PRODUCTION_APPROVED: NO &nbsp;|&nbsp; DISPATCHED: NO &nbsp;|&nbsp; MACHINE_STARTED: NO<br>
  This report is a <em>proposal only</em>. No CNC machine writes have been performed.
  Human engineering review is mandatory before any production use.
</div>

<p class="meta">
  Exported: {{ exported_at }}<br>
  Workflow: {{ workflow_id }}<br>
  Part: <strong>{{ part_reference }}</strong> rev {{ revision }}<br>
  Status: <span class="badge {{ status_class }}">{{ status }}</span> &nbsp;
  Objective: {{ objective }}
</p>

<h2>Stage Summary</h2>
<table>
<tr>
  <th>Stage</th><th>Status</th><th>Duration (ms)</th>
  <th>Warnings</th><th>Errors</th><th>Review Required</th>
</tr>
{% for row in stage_rows %}
<tr>
  <td>{{ row.label }}</td>
  <td><span class="badge {{ row.status_class }}">{{ row.status }}</span></td>
  <td>{{ row.duration }}</td>
  <td>{{ row.warnings }}</td>
  <td>{{ row.errors }}</td>
  <td>{{ "YES" if row.review_required else "—" }}</td>
</tr>
{% endfor %}
</table>

{% if blocking_issues %}
<h2>Blocking Issues ({{ blocking_issues | length }})</h2>
<table>
<tr><th>Stage</th><th>Code</th><th>Description</th><th>Required Action</th></tr>
{% for bi in blocking_issues %}
<tr>
  <td>{{ bi.stage }}</td>
  <td>{{ bi.code }}</td>
  <td>{{ bi.description }}</td>
  <td>{{ bi.required_action }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

{% if known_unknowns %}
<h2>Known Unknowns ({{ known_unknowns | length }})</h2>
<table>
<tr><th>Category</th><th>Description</th><th>Stage</th></tr>
{% for ku in known_unknowns %}
<tr>
  <td>{{ ku.category }}</td>
  <td>{{ ku.description }}</td>
  <td>{{ ku.stage or "—" }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

{% if review_items %}
<h2>Review Items ({{ review_items | length }})</h2>
<table>
<tr><th>Category</th><th>Description</th><th>Mandatory</th></tr>
{% for ri in review_items %}
<tr>
  <td>{{ ri.category }}</td>
  <td>{{ ri.description }}</td>
  <td>{{ "YES" if ri.mandatory else "no" }}</td>
</tr>
{% endfor %}
</table>
{% endif %}

<p class="meta" style="margin-top:3rem;border-top:1px solid #e5e7eb;padding-top:1rem">
  Generated by MachiningPro AI &mdash; OFFLINE ANALYSIS ONLY &mdash; NOT FOR CNC DISPATCH
</p>
</body>
</html>"""

_STAGE_LABELS: dict[str, str] = {
    "01_CAD_IMPORT": "CAD Import",
    "02_GEOMETRY": "Geometry",
    "03_FEATURE_RECOGNITION": "Feature Recognition",
    "04_DFM": "DFM",
    "05_PROCESS_PLANNING": "Process Planning",
    "06_MACHINE_SELECTION": "Machine Selection",
    "07_TOOL_SELECTION": "Tool Selection",
    "08_CUTTING_DATA": "Cutting Data",
    "09_CYCLE_TIME": "Cycle Time",
    "10_COST_RFQ": "Cost / RFQ",
    "11_CAM_PLANNING": "CAM Planning",
    "12_TOOLPATH": "Toolpath",
    "13_VERIFICATION": "Verification",
    "14_NC_CANDIDATE": "NC Candidate",
    "15_SCHEDULING": "Scheduling",
    "16_JOB_ASSIGNMENT": "Job Assignment",
    "17_ADAPTIVE_INTELLIGENCE": "Adaptive Intelligence",
    "18_DIGITAL_TWIN": "Digital Twin",
    "19_FINAL_MANUFACTURING_PLAN": "Final Plan",
}

_STATUS_CSS: dict[str, str] = {
    "PASS": "pass",
    "PARTIAL": "partial",
    "BLOCKED": "blocked",
    "FAILED": "failed",
    "NOT_STARTED": "not_started",
    "SKIPPED_NOT_REQUESTED": "skipped",
    "RUNNING": "partial",
    "REVIEW_REQUIRED": "partial",
}

_jinja_env = Environment(autoescape=select_autoescape(["html"]))


def export_plan_html(wf: ManufacturingWorkflow) -> bytes:
    """Render a human-readable HTML report for the manufacturing plan."""
    from ..workflow.enums import WorkflowStage

    stage_rows = []
    for stage in WorkflowStage:
        result = wf.stage_results.get(stage)
        status_str = str(result.status) if result else "NOT_STARTED"
        stage_rows.append({
            "label": _STAGE_LABELS.get(str(stage), str(stage)),
            "status": status_str,
            "status_class": _STATUS_CSS.get(status_str, "not_started"),
            "duration": f"{result.duration_ms:.1f}" if result and result.duration_ms else "—",
            "warnings": len(result.warnings) if result else 0,
            "errors": len(result.errors) if result else 0,
            "review_required": result.review_required if result else False,
        })

    plan = wf.final_plan

    template = _jinja_env.from_string(_HTML_REPORT_TEMPLATE)
    html = template.render(
        exported_at=datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC"),
        workflow_id=wf.workflow_id,
        part_reference=wf.part_reference,
        revision=wf.revision,
        status=str(wf.status),
        status_class=_STATUS_CSS.get(str(wf.status), "not_started"),
        objective=str(wf.objective),
        stage_rows=stage_rows,
        blocking_issues=[
            {
                "stage": str(bi.stage),
                "code": bi.code,
                "description": bi.description,
                "required_action": bi.required_action,
            }
            for bi in (plan.blocking_issues if plan else wf.blocking_issues)
        ],
        known_unknowns=[
            {
                "category": ku.category,
                "description": ku.description,
                "stage": str(ku.stage) if ku.stage else None,
            }
            for ku in (plan.known_unknowns if plan else wf.known_unknowns)
        ],
        review_items=[
            {
                "category": ri.category,
                "description": ri.description,
                "mandatory": ri.mandatory,
            }
            for ri in (plan.review_items if plan else wf.review_items)
        ],
    )
    return html.encode("utf-8")


# ---------------------------------------------------------------------------
# NC export with safety labelling (MUST 12)
# ---------------------------------------------------------------------------

def export_nc_manifest_json(wf: ManufacturingWorkflow) -> bytes:
    """Export NC candidate manifest with mandatory safety labels.

    NC_OFFLINE_EXPORT_SAFETY=YES
    Label: OFFLINE_CANDIDATE / NOT_MACHINE_APPROVED / NOT_DISPATCHED
    """
    from ..workflow.enums import WorkflowStage
    result = wf.stage_results.get(WorkflowStage.NC_CANDIDATE)
    payload: dict[str, Any] = {
        "export_format": "MachiningPro-NC-Manifest-JSON",
        "export_version": EXPORT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "safety": {
            "OFFLINE_CANDIDATE": True,
            "NOT_MACHINE_APPROVED": True,
            "NOT_DISPATCHED": True,
            "NO_CNC_TRANSFER": True,
        },
        "workflow_id": wf.workflow_id,
        "part_reference": wf.part_reference,
        "nc_stage_status": str(result.status) if result else "NOT_RUN",
        "nc_provenance": result.provenance if result else {},
        "nc_warnings": result.warnings if result else [],
        "nc_errors": result.errors if result else [],
    }
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _error_json(message: str) -> bytes:
    return json.dumps({"error": message}, indent=2).encode("utf-8")
