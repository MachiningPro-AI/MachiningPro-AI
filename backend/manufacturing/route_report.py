"""Process Route Report Generator (P4-C).

Generates a structured engineering process route report from a confirmed
feature, its route generation result, GD&T constraints, and setup/stock
definition.

Report is DRAFT status — engineer review required before production use.

Design invariants:
  - Report carries DRAFT status; no auto-approval path.
  - All sections include provenance labels.
  - Reports are human-readable + machine-readable (dict / HTML).
  - TR and EN disclaimers are both included.

FABRICATED_REPORT_CONTENT=NO
AUTO_APPROVED=NO
ROUTE_STATUS=PROPOSED
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from html import escape as _esc

from backend.drawing_intelligence.gdt_process_constraints import GdtProcessConstraint
from backend.drawing_intelligence.route_generator import RouteGenerationResult
from backend.interoperability.cad_feature_recognition import ManufacturingFeature
from backend.manufacturing.cam_gate import CamPrerequisiteState
from backend.manufacturing.setup_stock import SetupStockSession

__all__ = [
    "ProcessRouteReport",
    "generate_route_report",
    "generate_route_report_html",
]

_EN_DISCLAIMER = (
    "DRAFT: This process route report was generated from engineer-confirmed data. "
    "It is for reference only and requires engineer review and sign-off "
    "before any production use. AUTO_APPROVED=NO. OFFLINE_ONLY=YES."
)
_TR_DISCLAIMER = (
    "TASLAK: Bu proses rota raporu, mühendis tarafından onaylanmış verilerden "
    "üretilmiştir. Yalnızca referans amaçlıdır; üretim kullanımından önce mühendis "
    "incelemesi ve imzası gereklidir. OTOMATİK_ONAY=HAYIR. YALNIZCA_OFFLİNE=EVET."
)


@dataclass(frozen=True, slots=True)
class ProcessRouteReport:
    """Structured process route report for one confirmed feature.

    Status is always DRAFT — never APPROVED.
    AUTO_APPROVED=NO.
    """

    report_id: str
    generated_at: str
    feature_id: str
    feature_type: str
    part_id: str
    material_grade: str | None
    depth_mm: float | None
    diameter_mm: float | None
    width_mm: float | None
    stock_shape: str | None
    setup_datum_a: str | None
    n_setups: int | None
    routes: tuple[dict, ...]           # each: route_id, ops, achievable_ra_um, status
    gdt_constraints: tuple[dict, ...]  # each: constraint_id, type, note, status
    cam_ready: bool
    cam_first_blocker: str | None
    review_status: str = "PENDING_REVIEW"
    provenance: str = "USER_CONFIRMED"
    disclaimer_en: str = _EN_DISCLAIMER
    disclaimer_tr: str = _TR_DISCLAIMER

    def as_dict(self) -> dict:
        return {
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "feature_id": self.feature_id,
            "feature_type": self.feature_type,
            "part_id": self.part_id,
            "material_grade": self.material_grade,
            "depth_mm": self.depth_mm,
            "diameter_mm": self.diameter_mm,
            "width_mm": self.width_mm,
            "stock_shape": self.stock_shape,
            "setup_datum_a": self.setup_datum_a,
            "n_setups": self.n_setups,
            "routes": list(self.routes),
            "gdt_constraints": list(self.gdt_constraints),
            "cam_ready": self.cam_ready,
            "cam_first_blocker": self.cam_first_blocker,
            "review_status": self.review_status,
            "provenance": self.provenance,
            "disclaimer_en": self.disclaimer_en,
            "disclaimer_tr": self.disclaimer_tr,
        }


def generate_route_report(
    mfeat: ManufacturingFeature,
    route_result: RouteGenerationResult | None,
    gdt_constraints: tuple[GdtProcessConstraint, ...] = (),
    setup_session: SetupStockSession | None = None,
    cam_state: CamPrerequisiteState | None = None,
) -> ProcessRouteReport:
    """Build a ProcessRouteReport from confirmed feature + route + context.

    Parameters
    ----------
    mfeat:         Confirmed ManufacturingFeature (USER_CONFIRMED).
    route_result:  Result from bridge_confirmed_feature_to_route; may be None.
    gdt_constraints: GD&T process constraints from P3-E.
    setup_session: Setup/stock session, if available.
    cam_state:     CAM prerequisite gate result, if available.

    Returns
    -------
    ProcessRouteReport with DRAFT/PENDING_REVIEW status.
    AUTO_APPROVED=NO.
    """
    import hashlib
    report_id = "RPT-" + hashlib.sha256(
        f"{mfeat.feature_id}|{datetime.datetime.now(datetime.UTC).isoformat()}".encode()
    ).hexdigest()[:10]

    routes: list[dict] = []
    if route_result is not None and route_result.has_routes:
        for r in route_result.routes:
            routes.append({
                "route_id": r.route_id,
                "operations": [str(op) for op in r.operations],
                "requires_grinding": r.requires_grinding,
                "achievable_ra_um": float(r.achievable_ra_um),
                "route_description": r.route_description,
                "status": "PROPOSED",
            })
    elif route_result is not None:
        for rej in route_result.rejections:
            routes.append({
                "route_id": rej.route_id,
                "rejected": True,
                "reason": str(rej.reason),
                "detail": rej.detail,
                "status": "REJECTED",
            })

    gdt_items: list[dict] = [
        {
            "constraint_id": c.constraint_id,
            "req_id": c.req_id,
            "characteristic": str(c.characteristic),
            "constraint_type": str(c.constraint_type),
            "note": c.constraint_note,
            "gdnt_status": str(c.gdnt_status),
            "provenance": c.provenance,
            "feature_ref": c.feature_ref,
        }
        for c in gdt_constraints
    ]

    material_grade: str | None = None
    stock_shape: str | None = None
    setup_datum_a: str | None = None
    n_setups: int | None = None
    if setup_session is not None:
        if setup_session.stock is not None:
            material_grade = setup_session.stock.material_grade or None
            stock_shape = str(setup_session.stock.shape)
        if setup_session.setup is not None:
            setup_datum_a = setup_session.setup.datum_a
            n_setups = setup_session.setup.n_setups

    cam_ready = cam_state.cam_ready if cam_state is not None else False
    cam_first_blocker = cam_state.first_blocker if cam_state is not None else None

    return ProcessRouteReport(
        report_id=report_id,
        generated_at=datetime.datetime.now(datetime.UTC).isoformat(),
        feature_id=mfeat.feature_id,
        feature_type=str(mfeat.feature_type),
        part_id=mfeat.source_body_id or "UNKNOWN",
        material_grade=material_grade,
        depth_mm=float(mfeat.depth_mm) if mfeat.depth_mm is not None else None,
        diameter_mm=float(mfeat.diameter_mm) if mfeat.diameter_mm is not None else None,
        width_mm=float(mfeat.width_mm) if mfeat.width_mm is not None else None,
        stock_shape=stock_shape,
        setup_datum_a=setup_datum_a,
        n_setups=n_setups,
        routes=tuple(routes),
        gdt_constraints=tuple(gdt_items),
        cam_ready=cam_ready,
        cam_first_blocker=cam_first_blocker,
    )


def generate_route_report_html(report: ProcessRouteReport) -> str:
    """Render a ProcessRouteReport as an HTML string.

    HTML is intended for engineering review — includes all provenance,
    disclaimers, and PENDING_REVIEW status banner.
    """
    rows_html = ""
    if report.routes:
        rows_html = "".join(
            f"<tr>"
            f"<td>{_esc(r['route_id'])}</td>"
            f"<td>{_esc(' → '.join(r['operations']))}</td>"
            f"<td>{'Yes' if r.get('requires_grinding') else 'No'}</td>"
            f"<td>{r.get('achievable_ra_um', '—')}</td>"
            f"<td><span class='badge proposed'>{_esc(r.get('status', 'PROPOSED'))}</span></td>"
            f"</tr>"
            for r in report.routes
            if not r.get("rejected")
        )
        rows_html += "".join(
            f"<tr class='rejected'>"
            f"<td>{_esc(r['route_id'])}</td>"
            f"<td colspan='3'>{_esc(r.get('detail', ''))}</td>"
            f"<td><span class='badge rejected'>REJECTED</span></td>"
            f"</tr>"
            for r in report.routes
            if r.get("rejected")
        )
    else:
        rows_html = "<tr><td colspan='5'>No routes generated</td></tr>"

    gdt_rows = ""
    if report.gdt_constraints:
        gdt_rows = "".join(
            f"<tr>"
            f"<td>{_esc(c['req_id'])}</td>"
            f"<td>{_esc(c['characteristic'])}</td>"
            f"<td>{_esc(c['constraint_type'])}</td>"
            f"<td>{_esc(c['note'])}</td>"
            f"<td>{_esc(c['gdnt_status'])}</td>"
            f"</tr>"
            for c in report.gdt_constraints
        )
    else:
        gdt_rows = "<tr><td colspan='5'>No GD&amp;T constraints</td></tr>"

    cam_badge = (
        "<span class='badge cam-ready'>CAM READY (OFFLINE)</span>"
        if report.cam_ready
        else f"<span class='badge cam-blocked'>BLOCKED: {_esc(report.cam_first_blocker or 'unknown')}</span>"
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Process Route Report — {_esc(report.feature_id)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 2em; color: #111; }}
h1 {{ font-size: 1.3em; border-bottom: 2px solid #333; padding-bottom: .4em; }}
h2 {{ font-size: 1.1em; margin-top: 1.5em; color: #444; }}
table {{ border-collapse: collapse; width: 100%; margin-top: .5em; }}
th, td {{ border: 1px solid #ccc; padding: .4em .7em; text-align: left; font-size: .9em; }}
th {{ background: #f4f4f4; }}
tr.rejected {{ background: #fff8f8; }}
.badge {{ display: inline-block; padding: .2em .6em; border-radius: 3px; font-size: .8em; font-weight: bold; }}
.badge.proposed {{ background: #e8f4fd; color: #1565c0; }}
.badge.rejected {{ background: #fce4e4; color: #b71c1c; }}
.badge.cam-ready {{ background: #e8f5e9; color: #1b5e20; }}
.badge.cam-blocked {{ background: #fff3e0; color: #e65100; }}
.disclaimer {{ background: #fff9c4; border: 1px solid #f9a825; padding: .7em 1em; margin-top: 1.5em; font-size: .85em; }}
.review-banner {{ background: #fff3e0; border-left: 4px solid #e65100; padding: .5em 1em; margin-bottom: 1em; font-weight: bold; }}
dl {{ display: grid; grid-template-columns: max-content auto; gap: .2em .8em; }}
dt {{ font-weight: bold; color: #555; }}
</style>
</head>
<body>
<div class="review-banner">STATUS: {_esc(report.review_status)} — Engineer sign-off required before production use</div>
<h1>Process Route Report</h1>
<dl>
  <dt>Report ID</dt><dd>{_esc(report.report_id)}</dd>
  <dt>Generated</dt><dd>{_esc(report.generated_at)}</dd>
  <dt>Feature ID</dt><dd>{_esc(report.feature_id)}</dd>
  <dt>Feature Type</dt><dd>{_esc(report.feature_type)}</dd>
  <dt>Part ID</dt><dd>{_esc(report.part_id)}</dd>
  <dt>Provenance</dt><dd>{_esc(report.provenance)}</dd>
</dl>
<h2>Engineering Data</h2>
<dl>
  <dt>Material</dt><dd>{_esc(report.material_grade or 'UNKNOWN')}</dd>
  <dt>Depth (mm)</dt><dd>{report.depth_mm if report.depth_mm is not None else 'UNKNOWN'}</dd>
  <dt>Diameter (mm)</dt><dd>{report.diameter_mm if report.diameter_mm is not None else 'N/A'}</dd>
  <dt>Width (mm)</dt><dd>{report.width_mm if report.width_mm is not None else 'N/A'}</dd>
  <dt>Stock</dt><dd>{_esc(report.stock_shape or 'Not defined')}</dd>
  <dt>Datum A</dt><dd>{_esc(report.setup_datum_a or 'Not defined')}</dd>
  <dt>Setups</dt><dd>{report.n_setups if report.n_setups is not None else 'Not defined'}</dd>
  <dt>CAM Readiness</dt><dd>{cam_badge}</dd>
</dl>
<h2>Process Routes</h2>
<table>
<tr><th>Route ID</th><th>Operations</th><th>Grinding</th><th>Ra (µm)</th><th>Status</th></tr>
{rows_html}
</table>
<h2>GD&amp;T Constraints</h2>
<table>
<tr><th>Req ID</th><th>Characteristic</th><th>Constraint Type</th><th>Note</th><th>GD&amp;T Status</th></tr>
{gdt_rows}
</table>
<div class="disclaimer">
<strong>EN:</strong> {_esc(report.disclaimer_en)}<br><br>
<strong>TR:</strong> {_esc(report.disclaimer_tr)}
</div>
</body>
</html>"""
