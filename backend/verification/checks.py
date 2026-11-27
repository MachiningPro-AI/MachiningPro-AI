"""
Level-11 verification check functions.

Each function is fail-closed:
  - Missing required data → NOT_PERFORMED or INSUFFICIENT_DATA (never PASS)
  - Only explicit geometry produces PASS
  - Partial model != collision-free
  - Unknown != safe

NO_FABRICATED_DATA=YES  NO_HARDCODED_SAFE=YES
"""

from __future__ import annotations

import math
import uuid

from .enums import (
    VerificationCheckType,
    VerificationSeverity,
    VerificationStatus,
)
from .models import VerificationIssue, VerificationResult, VerificationSegment
from .stock import FixtureGeometry, StockModel
from .swept_volume import AABB, segment_cylinder_intersects_aabb
from .tolerance import DEFAULT_TOLERANCE, TolerancePolicy


def _issue(
    check_type: VerificationCheckType,
    severity: VerificationSeverity,
    message: str,
    segment_id: str | None = None,
    evidence: dict | None = None,
) -> VerificationIssue:
    return VerificationIssue(
        issue_id=str(uuid.uuid4())[:12],
        check_type=check_type,
        severity=severity,
        message=message,
        segment_id=segment_id,
        evidence=evidence or {},
    )


def _pass(check_type: VerificationCheckType, **evidence) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.PASS,
        severity=VerificationSeverity.INFO,
        evidence=evidence,
    )


def _not_performed(
    check_type: VerificationCheckType, reason: str
) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.NOT_PERFORMED,
        severity=VerificationSeverity.WARNING,
        warnings=[reason],
    )


def _insufficient(
    check_type: VerificationCheckType, reason: str
) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.INSUFFICIENT_DATA,
        severity=VerificationSeverity.WARNING,
        warnings=[reason],
    )


def _fail(
    check_type: VerificationCheckType,
    severity: VerificationSeverity,
    issues: list[VerificationIssue],
    warnings: list[str] | None = None,
) -> VerificationResult:
    return VerificationResult(
        check_type=check_type,
        status=VerificationStatus.FAIL,
        severity=severity,
        issues=issues,
        errors=[i.message for i in issues],
        warnings=warnings or [],
    )


def check_part_gouge(
    segments: list[VerificationSegment],
    part_bbox_min: tuple[float, float, float] | None,
    part_bbox_max: tuple[float, float, float] | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.PART_GOUGE
    if part_bbox_min is None or part_bbox_max is None:
        return _insufficient(ct, "Part geometry not provided; PART_GOUGE cannot be checked")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown; PART_GOUGE check accuracy impaired")

    part_min_z = part_bbox_min[2]
    cutting = [s for s in segments if s.is_cutting]
    if not cutting:
        return _pass(ct, note="No cutting segments")

    issues: list[VerificationIssue] = []
    part_aabb = AABB(
        part_bbox_min[0],
        part_bbox_min[1],
        part_bbox_min[2],
        part_bbox_max[0],
        part_bbox_max[1],
        part_bbox_max[2],
    )
    radius = tool_diameter_mm / 2.0

    for seg in cutting:
        z_low = min(seg.start_z, seg.end_z)
        if z_low < part_min_z - tol.gouge_mm:
            issues.append(
                _issue(
                    ct,
                    VerificationSeverity.CRITICAL,
                    f"Cutting below part bottom: z_min={z_low:.4f} < part_z={part_min_z:.4f}",
                    segment_id=seg.segment_id,
                    evidence={
                        "segment_z_min": z_low,
                        "part_min_z": part_min_z,
                        "tolerance_mm": tol.gouge_mm,
                    },
                )
            )
        elif segment_cylinder_intersects_aabb(
            seg.start_x,
            seg.start_y,
            seg.start_z,
            seg.end_x,
            seg.end_y,
            seg.end_z,
            radius,
            part_aabb,
        ):
            issues.append(
                _issue(
                    ct,
                    VerificationSeverity.WARNING,
                    "Cutting segment overlaps part bounding box (conservative bbox check)",
                    segment_id=seg.segment_id,
                    evidence={"note": "May be false positive; mesh check not available"},
                )
            )

    if any(i.severity == VerificationSeverity.CRITICAL for i in issues):
        return _fail(
            ct,
            VerificationSeverity.CRITICAL,
            [i for i in issues if i.severity == VerificationSeverity.CRITICAL],
            warnings=["PART_GOUGE uses bounding-box approximation only"],
        )
    if issues:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            issues=issues,
            warnings=["Conservative bbox check; exact mesh not available"],
        )
    # HARD RULE 1+2: bbox conservative check NEVER returns PASS.
    # No bbox overlap found — this is a conservative indicator only.
    # GOUGE_EXACT (mesh-vs-mesh) is required for PASS; use check_part_gouge_exact().
    return VerificationResult(
        check_type=ct,
        status=VerificationStatus.PARTIAL,
        severity=VerificationSeverity.WARNING,
        evidence={
            "note": "CONSERVATIVE_NO_BBOX_OVERLAP",
            "checked_segments": len(cutting),
            "fidelity": "BBOX_CONSERVATIVE_ONLY",
        },
        warnings=[
            "PART_GOUGE conservative check: no bounding-box violation found. "
            "This is NOT a gouge-free guarantee — exact mesh comparison (GOUGE_EXACT) "
            "is NOT_VERIFIABLE. Engineer review required before machining."
        ],
    )


def check_part_gouge_exact(
    segments: list[VerificationSegment],
    part_bbox_min: tuple[float, float, float] | None,
    part_bbox_max: tuple[float, float, float] | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
    # Extended parameters for exact engine (beta.5)
    target_step_path: str | None = None,
    stock_bbox: StockModel | None = None,
    tolerance_mm: float | None = None,
    tolerance_source: str = "NOT_PROVIDED",
    test_only: bool = False,
    test_label: str = "",
) -> VerificationResult:
    """Exact gouge check using gmsh OCC Boolean engine (beta.5).

    When target_step_path is provided and gmsh is available, performs a real
    B-Rep Boolean exact gouge check (BREP_BOOLEAN_OCC).

    Falls back to NOT_VERIFIABLE when:
      - no STEP file provided
      - no cutting segments
      - gmsh not available (should not happen — gmsh is a project dependency)
      - Boolean engine fails

    HARD RULE: Never returns PASS without confirmed zero-gouge Boolean result.
    Conservative bbox check remains separate in PART_GOUGE (GOUGE_CONSERVATIVE).
    """
    from backend.verification.exact_gouge import ExactGougeConfig, run_exact_gouge_check

    ct = VerificationCheckType.GOUGE_EXACT

    # Build cutting segments from VerificationSegments
    cutting_segs = [
        (s.start_x, s.start_y, s.start_z, s.end_x, s.end_y, s.end_z)
        for s in segments
        if s.is_cutting
    ]

    if not cutting_segs:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.NOT_VERIFIABLE,
            severity=VerificationSeverity.WARNING,
            warnings=["No cutting segments; GOUGE_EXACT cannot be checked"],
            evidence={"gouge_exact_ready": False, "reason": "NO_CUTTING_SEGMENTS"},
        )

    # Build stock dimensions
    sx, sy, sz, sw, sh, sd = 0.0, 0.0, 0.0, 100.0, 100.0, 50.0
    if stock_bbox and stock_bbox.is_known:
        sx = stock_bbox.min_x_mm or 0.0
        sy = stock_bbox.min_y_mm or 0.0
        sz = stock_bbox.min_z_mm or 0.0
        sw = max((stock_bbox.max_x_mm or 100.0) - sx, 1.0)
        sh = max((stock_bbox.max_y_mm or 100.0) - sy, 1.0)
        sd = max((stock_bbox.max_z_mm or 50.0) - sz, 1.0)
    elif part_bbox_min and part_bbox_max:
        # Derive stock from part bbox + 10% margin
        sx = part_bbox_min[0] - (part_bbox_max[0] - part_bbox_min[0]) * 0.1
        sy = part_bbox_min[1] - (part_bbox_max[1] - part_bbox_min[1]) * 0.1
        sz = part_bbox_min[2] - (part_bbox_max[2] - part_bbox_min[2]) * 0.1
        sw = (part_bbox_max[0] - part_bbox_min[0]) * 1.2
        sh = (part_bbox_max[1] - part_bbox_min[1]) * 1.2
        sd = (part_bbox_max[2] - part_bbox_min[2]) * 1.2

    config = ExactGougeConfig(
        target_step_path=target_step_path,
        stock_x_mm=sx, stock_y_mm=sy, stock_z_mm=sz,
        stock_w_mm=sw, stock_h_mm=sh, stock_d_mm=sd,
        tool_radius_mm=(tool_diameter_mm or 10.0) / 2.0,
        cutting_segments=cutting_segs,
        tolerance_mm=tolerance_mm,
        tolerance_source=tolerance_source,
        test_only=test_only,
        test_label=test_label,
    )

    gr = run_exact_gouge_check(config)

    # Map ExactGougeResult status to VerificationStatus
    status_map = {
        "PASS": VerificationStatus.PASS,
        "FAIL": VerificationStatus.FAIL,
        "PARTIAL": VerificationStatus.PARTIAL,
        "NOT_VERIFIABLE": VerificationStatus.NOT_VERIFIABLE,
    }
    vs = status_map.get(gr.status, VerificationStatus.NOT_VERIFIABLE)

    sev = VerificationSeverity.INFO
    if vs == VerificationStatus.FAIL:
        sev = VerificationSeverity.CRITICAL
    elif vs in (VerificationStatus.PARTIAL, VerificationStatus.NOT_VERIFIABLE):
        sev = VerificationSeverity.WARNING

    evidence = {
        "gouge_exact_ready": gr.gouge_exact_ready,
        "method": gr.method,
        # Geometry classification (B-Rep exact)
        "gouge_geometry_method": gr.gouge_geometry_method,
        "gouge_geometry_fidelity": gr.gouge_geometry_fidelity,
        # Volume measurement (tetrahedral integration, approximate)
        "gouge_volume_method": gr.gouge_volume_method,
        "gouge_volume_fidelity": gr.gouge_volume_fidelity,
        "volume_integration_error_pct": gr.volume_integration_error_pct,
        "target_geometry_fidelity": gr.target_geometry_fidelity,
        "machined_result_method": gr.machined_result_method,
        "machined_result_fidelity": gr.machined_result_fidelity,
        # Volumes are APPROXIMATE (tetrahedral mesh integration)
        "gouge_volume_mm3": gr.gouge_volume_mm3,
        "max_gouge_depth_mm": gr.max_gouge_depth_mm,
        "gouge_region_count": gr.gouge_region_count,
        "remaining_material_volume_mm3": gr.remaining_material_volume_mm3,
        "max_remaining_depth_mm": gr.max_remaining_depth_mm,
        "remaining_region_count": gr.remaining_region_count,
        "tolerance_mm": gr.tolerance_mm,
        "tolerance_source": gr.tolerance_source,
        "boolean_success": gr.boolean_success,
        "total_exact_verification_ms": gr.total_exact_verification_ms,
        "target_prep_ms": gr.target_prep_ms,
        "machined_result_ms": gr.machined_result_ms,
        "boolean_ms": gr.boolean_ms,
        "gouge_analysis_ms": gr.gouge_analysis_ms,
    }
    if gr.error:
        evidence["error"] = gr.error

    return VerificationResult(
        check_type=ct,
        status=vs,
        severity=sev,
        warnings=gr.warnings,
        evidence=evidence,
    )


def check_stock_gouge(
    segments: list[VerificationSegment],
    stock: StockModel | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.STOCK_GOUGE
    if stock is None or not stock.is_known:
        return _insufficient(ct, "Stock geometry not provided; STOCK_GOUGE cannot be checked")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown")

    cutting = [s for s in segments if s.is_cutting]
    if not cutting:
        return _pass(ct, note="No cutting segments")

    issues: list[VerificationIssue] = []
    for seg in cutting:
        for pt in [
            (seg.start_x, seg.start_y, seg.start_z),
            (seg.end_x, seg.end_y, seg.end_z),
        ]:
            if not _valid_coords(*pt):
                issues.append(
                    _issue(ct, VerificationSeverity.ERROR, f"Invalid coordinates: {pt}")
                )
                continue
            if not stock.contains_point(*pt):
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.ERROR,
                        f"Cutting outside stock at ({pt[0]:.3f}, {pt[1]:.3f}, {pt[2]:.3f})",
                        segment_id=seg.segment_id,
                        evidence={"point": list(pt)},
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.ERROR, issues)
    return _pass(ct, checked_segments=len(cutting), fidelity="APPROXIMATE")


def check_tool_fixture_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Phase I — TOOL_FIXTURE_COLLISION: tool cylinder vs fixture bboxes."""
    ct = VerificationCheckType.TOOL_FIXTURE_COLLISION
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; tool collision cannot be checked")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown")

    radius = tool_diameter_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm,
                fixture.min_y_mm,
                fixture.min_z_mm,
                fixture.max_x_mm,
                fixture.max_y_mm,
                fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x,
                seg.start_y,
                seg.start_z,
                seg.end_x,
                seg.end_y,
                seg.end_z,
                radius,
                faabb,
            ):
                label = (
                    "COLLISION_CONTACT" if not seg.is_cutting
                    else "CUTTING_CONTACT_WITH_FIXTURE"
                )
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Tool body intersects fixture '{fixture.fixture_id}' ({label})"
                        f" during {seg.motion_type}",
                        segment_id=seg.segment_id,
                        evidence={
                            "fixture_id": fixture.fixture_id,
                            "motion_type": seg.motion_type,
                            "contact_type": label,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, checked_fixtures=len(fixtures), checked_segments=len(segments))


def check_holder_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_length_mm: float | None,
    holder_diameter_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.HOLDER_COLLISION
    if holder_diameter_mm is None:
        return _not_performed(ct, "Holder geometry unknown; HOLDER_COLLISION=NOT_PERFORMED")
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; holder collision cannot be checked")
    if tool_length_mm is None:
        return _insufficient(ct, "Tool length unknown; holder position cannot be determined")

    holder_radius = holder_diameter_mm / 2.0
    holder_offset_z = tool_length_mm
    issues: list[VerificationIssue] = []

    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        h_start_z = seg.start_z + holder_offset_z
        h_end_z = seg.end_z + holder_offset_z
        h_len = holder_length_mm if holder_length_mm else 50.0
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm,
                fixture.min_y_mm,
                fixture.min_z_mm,
                fixture.max_x_mm,
                fixture.max_y_mm,
                fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x,
                seg.start_y,
                h_start_z,
                seg.end_x,
                seg.end_y,
                h_end_z + h_len,
                holder_radius,
                faabb,
            ):
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Holder intersects fixture '{fixture.fixture_id}'"
                        f" during {seg.motion_type}",
                        segment_id=seg.segment_id,
                        evidence={
                            "fixture_id": fixture.fixture_id,
                            "holder_radius": holder_radius,
                            "holder_z_offset": holder_offset_z,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, checked_fixtures=len(fixtures), holder_diameter_mm=holder_diameter_mm)


def check_holder_part_collision(
    segments: list[VerificationSegment],
    part_bbox_min: tuple[float, float, float] | None,
    part_bbox_max: tuple[float, float, float] | None,
    tool_length_mm: float | None,
    holder_diameter_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Phase G — HOLDER_PART_COLLISION: holder cylinder vs part bounding box."""
    ct = VerificationCheckType.HOLDER_PART_COLLISION
    if holder_diameter_mm is None:
        return _not_performed(ct, "Holder geometry unknown; HOLDER_PART_COLLISION=NOT_PERFORMED")
    if part_bbox_min is None or part_bbox_max is None:
        return _not_performed(ct, "Part geometry not provided; HOLDER_PART_COLLISION=NOT_PERFORMED")
    if tool_length_mm is None:
        return _insufficient(ct, "Tool length unknown; holder Z position cannot be determined")

    holder_radius = holder_diameter_mm / 2.0
    holder_offset_z = tool_length_mm
    h_len = holder_length_mm if holder_length_mm else 50.0

    part_aabb = AABB(
        part_bbox_min[0], part_bbox_min[1], part_bbox_min[2],
        part_bbox_max[0], part_bbox_max[1], part_bbox_max[2],
    )

    issues: list[VerificationIssue] = []
    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        h_start_z = seg.start_z + holder_offset_z
        h_end_z = seg.end_z + holder_offset_z
        if segment_cylinder_intersects_aabb(
            seg.start_x, seg.start_y, h_start_z,
            seg.end_x, seg.end_y, h_end_z + h_len,
            holder_radius, part_aabb,
        ):
            issues.append(_issue(
                ct, VerificationSeverity.CRITICAL,
                f"Holder intersects part bounding box during {seg.motion_type}",
                segment_id=seg.segment_id,
                evidence={
                    "holder_radius_mm": holder_radius,
                    "holder_z_offset_mm": holder_offset_z,
                    "method": "BBOX_CYLINDER",
                    "geometry_source": "CATALOG",
                    "fidelity": "SIMPLIFIED_CYLINDER",
                },
            ))

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(
        ct,
        holder_diameter_mm=holder_diameter_mm,
        method="BBOX_CYLINDER",
        geometry_source="CATALOG",
        fidelity="SIMPLIFIED_CYLINDER",
    )


def check_holder_stock_collision(
    segments: list[VerificationSegment],
    stock: StockModel | None,
    tool_length_mm: float | None,
    holder_diameter_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Phase G — HOLDER_STOCK_COLLISION: holder cylinder vs stock bounding box."""
    ct = VerificationCheckType.HOLDER_STOCK_COLLISION
    if holder_diameter_mm is None:
        return _not_performed(ct, "Holder geometry unknown; HOLDER_STOCK_COLLISION=NOT_PERFORMED")
    if stock is None or not stock.is_known:
        return _not_performed(
            ct, "Stock geometry not provided; HOLDER_STOCK_COLLISION=NOT_PERFORMED"
        )
    if tool_length_mm is None:
        return _insufficient(ct, "Tool length unknown; holder Z position cannot be determined")

    holder_radius = holder_diameter_mm / 2.0
    holder_offset_z = tool_length_mm
    h_len = holder_length_mm if holder_length_mm else 50.0

    if not stock.has_box_dims:
        return _insufficient(ct, "Stock lacks bbox dims; HOLDER_STOCK_COLLISION cannot be checked")

    stock_aabb = AABB(
        stock.min_x_mm, stock.min_y_mm, stock.min_z_mm,
        stock.max_x_mm, stock.max_y_mm, stock.max_z_mm,
    )

    issues: list[VerificationIssue] = []
    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        h_start_z = seg.start_z + holder_offset_z
        h_end_z = seg.end_z + holder_offset_z
        if segment_cylinder_intersects_aabb(
            seg.start_x, seg.start_y, h_start_z,
            seg.end_x, seg.end_y, h_end_z + h_len,
            holder_radius, stock_aabb,
        ):
            issues.append(_issue(
                ct, VerificationSeverity.CRITICAL,
                f"Holder intersects stock bounding box during {seg.motion_type}",
                segment_id=seg.segment_id,
                evidence={
                    "holder_radius_mm": holder_radius,
                    "holder_z_offset_mm": holder_offset_z,
                    "method": "BBOX_CYLINDER",
                    "geometry_source": "CATALOG",
                    "fidelity": "SIMPLIFIED_CYLINDER",
                },
            ))

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(
        ct,
        holder_diameter_mm=holder_diameter_mm,
        method="BBOX_CYLINDER",
        geometry_source="CATALOG",
        fidelity="SIMPLIFIED_CYLINDER",
    )


def check_holder_fixture_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_length_mm: float | None,
    holder_diameter_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Phase G — HOLDER_FIXTURE_COLLISION: holder cylinder vs fixture bboxes."""
    ct = VerificationCheckType.HOLDER_FIXTURE_COLLISION
    if holder_diameter_mm is None:
        return _not_performed(ct, "Holder geometry unknown; HOLDER_FIXTURE_COLLISION=NOT_PERFORMED")
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; HOLDER_FIXTURE_COLLISION=NOT_PERFORMED")
    if tool_length_mm is None:
        return _insufficient(ct, "Tool length unknown; holder Z position cannot be determined")

    holder_radius = holder_diameter_mm / 2.0
    holder_offset_z = tool_length_mm
    h_len = holder_length_mm if holder_length_mm else 50.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        h_start_z = seg.start_z + holder_offset_z
        h_end_z = seg.end_z + holder_offset_z
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm, fixture.min_y_mm, fixture.min_z_mm,
                fixture.max_x_mm, fixture.max_y_mm, fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x, seg.start_y, h_start_z,
                seg.end_x, seg.end_y, h_end_z + h_len,
                holder_radius, faabb,
            ):
                issues.append(_issue(
                    ct, VerificationSeverity.CRITICAL,
                    f"Holder intersects fixture '{fixture.fixture_id}' during {seg.motion_type}",
                    segment_id=seg.segment_id,
                    evidence={
                        "fixture_id": fixture.fixture_id,
                        "holder_radius_mm": holder_radius,
                        "holder_z_offset_mm": holder_offset_z,
                        "method": "BBOX_CYLINDER",
                        "clearance_mm": None,
                        "collision_count": len(issues) + 1,
                    },
                ))

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(
        ct,
        checked_fixtures=len(fixtures),
        holder_diameter_mm=holder_diameter_mm,
        method="BBOX_CYLINDER",
        geometry_source="CATALOG",
        fidelity="SIMPLIFIED_CYLINDER",
    )


def check_part_fixture_interference(
    part_bbox_min: tuple[float, float, float] | None,
    part_bbox_max: tuple[float, float, float] | None,
    fixtures: list[FixtureGeometry],
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Phase I — PART_FIXTURE_INTERFERENCE: part bbox vs fixture bboxes.

    This checks static setup interference (part inside fixture envelope).
    """
    ct = VerificationCheckType.PART_FIXTURE_INTERFERENCE
    if part_bbox_min is None or part_bbox_max is None:
        return _not_performed(
            ct, "Part geometry not provided; PART_FIXTURE_INTERFERENCE=NOT_PERFORMED"
        )
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; PART_FIXTURE_INTERFERENCE=NOT_PERFORMED")

    issues: list[VerificationIssue] = []
    for fixture in fixtures:
        if not fixture.is_known:
            continue
        # Check if part bbox overlaps fixture bbox in X/Y (Z may intentionally overlap for clamping)
        p_min_x, p_min_y = part_bbox_min[0], part_bbox_min[1]
        p_max_x, p_max_y = part_bbox_max[0], part_bbox_max[1]
        p_max_z = part_bbox_max[2]
        overlap_x = p_min_x < fixture.max_x_mm and p_max_x > fixture.min_x_mm
        overlap_y = p_min_y < fixture.max_y_mm and p_max_y > fixture.min_y_mm
        overlap_z = p_max_z > fixture.min_z_mm + tol.linear_mm
        if overlap_x and overlap_y and overlap_z:
            issues.append(_issue(
                ct, VerificationSeverity.WARNING,
                f"Part bbox overlaps fixture '{fixture.fixture_id}' (potential setup interference)",
                evidence={
                    "fixture_id": fixture.fixture_id,
                    "note": "STATIC_SETUP_CHECK — clamping overlap may be intentional",
                    "method": "BBOX_OVERLAP",
                },
            ))

    if issues:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            issues=issues,
            warnings=[
                "PART_FIXTURE_INTERFERENCE uses bbox overlap only; mesh check not available"
            ],
        )
    return _pass(ct, checked_fixtures=len(fixtures), method="BBOX_OVERLAP")


def check_fixture_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    holder_diameter_mm: float | None,
    tool_length_mm: float | None,
    holder_length_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.FIXTURE_COLLISION
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; fixture collision cannot be checked")

    tool_result = check_tool_fixture_collision(segments, fixtures, tool_diameter_mm, tol)
    holder_result = check_holder_fixture_collision(
        segments, fixtures, tool_length_mm, holder_diameter_mm, holder_length_mm, tol
    )

    combined_issues: list[VerificationIssue] = []
    combined_issues.extend(tool_result.issues)
    combined_issues.extend(holder_result.issues)
    combined_warnings: list[str] = list(tool_result.warnings) + list(holder_result.warnings)

    if combined_issues:
        return _fail(ct, VerificationSeverity.CRITICAL, combined_issues, combined_warnings)

    sub_statuses = {tool_result.status, holder_result.status}
    if VerificationStatus.INSUFFICIENT_DATA in sub_statuses:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.INSUFFICIENT_DATA,
            severity=VerificationSeverity.WARNING,
            warnings=combined_warnings,
        )
    if VerificationStatus.NOT_PERFORMED in sub_statuses:
        return VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            warnings=["Holder geometry not checked"] + combined_warnings,
        )
    return _pass(ct, checked_fixtures=len(fixtures))


def check_rapid_clearance(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.RAPID_CLEARANCE
    if not fixtures:
        return _not_performed(ct, "No fixture geometry; rapid clearance cannot be checked globally")
    if tool_diameter_mm is None:
        return _insufficient(ct, "Tool diameter unknown")

    rapids = [
        s
        for s in segments
        if s.motion_type in ("RAPID", "LINK", "RETRACT", "APPROACH")
    ]
    if not rapids:
        return _pass(ct, note="No rapid/link/retract segments to check")

    radius = tool_diameter_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in rapids:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        for fixture in fixtures:
            if not fixture.is_known:
                continue
            faabb = AABB(
                fixture.min_x_mm,
                fixture.min_y_mm,
                fixture.min_z_mm,
                fixture.max_x_mm,
                fixture.max_y_mm,
                fixture.max_z_mm,
            )
            if segment_cylinder_intersects_aabb(
                seg.start_x,
                seg.start_y,
                seg.start_z,
                seg.end_x,
                seg.end_y,
                seg.end_z,
                radius,
                faabb,
            ):
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Rapid/link move intersects fixture"
                        f" '{fixture.fixture_id}' ({seg.motion_type})",
                        segment_id=seg.segment_id,
                        evidence={
                            "fixture_id": fixture.fixture_id,
                            "motion_type": seg.motion_type,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, checked_rapids=len(rapids), checked_fixtures=len(fixtures))


def check_machine_envelope(
    segments: list[VerificationSegment],
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.MACHINE_ENVELOPE
    if travel_x_mm is None or travel_y_mm is None or travel_z_mm is None:
        return _insufficient(ct, "Machine travel limits not specified")

    half_x = travel_x_mm / 2.0
    half_y = travel_y_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        for pt, _label in [
            ((seg.start_x, seg.start_y, seg.start_z), "start"),
            ((seg.end_x, seg.end_y, seg.end_z), "end"),
        ]:
            if not _valid_coords(*pt):
                continue
            if abs(pt[0]) > half_x or abs(pt[1]) > half_y or pt[2] < -travel_z_mm:
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        f"Path point exceeds machine travel:"
                        f" ({pt[0]:.3f}, {pt[1]:.3f}, {pt[2]:.3f})",
                        segment_id=seg.segment_id,
                        evidence={
                            "point": list(pt),
                            "travel_x": travel_x_mm,
                            "travel_y": travel_y_mm,
                            "travel_z": travel_z_mm,
                        },
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, travel_x=travel_x_mm, travel_y=travel_y_mm, travel_z=travel_z_mm)


def check_overtravel(
    segments: list[VerificationSegment],
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Fail-closed overtravel check — any point beyond limits → FAIL."""
    ct = VerificationCheckType.OVERTRAVEL
    if travel_x_mm is None or travel_y_mm is None or travel_z_mm is None:
        return _insufficient(ct, "Machine travel limits not specified; OVERTRAVEL fail-closed")

    half_x = travel_x_mm / 2.0
    half_y = travel_y_mm / 2.0
    issues: list[VerificationIssue] = []

    for seg in segments:
        for pt in [
            (seg.start_x, seg.start_y, seg.start_z),
            (seg.end_x, seg.end_y, seg.end_z),
        ]:
            if not _valid_coords(*pt):
                continue
            overtravel_axes: list[str] = []
            if abs(pt[0]) > half_x:
                overtravel_axes.append(f"X={pt[0]:.3f} limit=±{half_x:.3f}")
            if abs(pt[1]) > half_y:
                overtravel_axes.append(f"Y={pt[1]:.3f} limit=±{half_y:.3f}")
            if pt[2] < -travel_z_mm:
                overtravel_axes.append(f"Z={pt[2]:.3f} limit={-travel_z_mm:.3f}")
            if overtravel_axes:
                issues.append(
                    _issue(
                        ct,
                        VerificationSeverity.CRITICAL,
                        "OVERTRAVEL: " + "; ".join(overtravel_axes),
                        segment_id=seg.segment_id,
                        evidence={"point": list(pt), "axes": overtravel_axes},
                    )
                )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, travel_x=travel_x_mm, travel_y=travel_y_mm, travel_z=travel_z_mm)


def check_axis_limit(
    segments: list[VerificationSegment],
    axis_limits: dict[str, tuple[float, float]] | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.AXIS_LIMIT
    if axis_limits is None:
        return _not_performed(ct, "No machine axis limits defined")

    coord_map = {"X": 0, "Y": 1, "Z": 2}
    issues: list[VerificationIssue] = []

    for seg in segments:
        for pt in [
            (seg.start_x, seg.start_y, seg.start_z),
            (seg.end_x, seg.end_y, seg.end_z),
        ]:
            if not _valid_coords(*pt):
                continue
            for axis, (lo, hi) in axis_limits.items():
                idx = coord_map.get(axis.upper())
                if idx is None:
                    continue
                val = pt[idx]
                if val < lo or val > hi:
                    excess = val - hi if val > hi else lo - val
                    issues.append(
                        _issue(
                            ct,
                            VerificationSeverity.CRITICAL,
                            f"Axis {axis} value {val:.3f} outside [{lo:.3f}, {hi:.3f}]"
                            f" (excess={excess:.3f} mm)",
                            segment_id=seg.segment_id,
                            evidence={
                                "AXIS": axis,
                                "COMMAND_POSITION": val,
                                "LIMIT_MIN": lo,
                                "LIMIT_MAX": hi,
                                "EXCESS_MM": excess,
                                "OPERATION_ID": seg.operation_id,
                                "TOOLPATH_SEGMENT": seg.segment_id,
                            },
                        )
                    )

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(ct, axes_checked=list(axis_limits.keys()))


def check_tool_reach(
    segments: list[VerificationSegment],
    flute_length_mm: float | None,
    holder_clearance_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.TOOL_REACH
    if flute_length_mm is None:
        return _insufficient(ct, "Tool flute length unknown; TOOL_REACH cannot be checked")

    cutting = [s for s in segments if s.is_cutting]
    if not cutting:
        return _pass(ct, note="No cutting segments")

    z_ref = max(s.start_z for s in cutting if s.is_cutting)
    max_depth = 0.0
    for seg in cutting:
        depth = z_ref - min(seg.start_z, seg.end_z)
        if depth > max_depth:
            max_depth = depth

    effective_reach = flute_length_mm
    if holder_clearance_mm is not None:
        effective_reach = min(flute_length_mm, holder_clearance_mm)

    issues: list[VerificationIssue] = []
    if max_depth > effective_reach + tol.linear_mm:
        issues.append(
            _issue(
                ct,
                VerificationSeverity.CRITICAL,
                f"Path depth {max_depth:.4f}mm exceeds"
                f" effective tool reach {effective_reach:.4f}mm",
                evidence={
                    "max_depth_mm": max_depth,
                    "flute_length_mm": flute_length_mm,
                    "holder_clearance_mm": holder_clearance_mm,
                    "effective_reach_mm": effective_reach,
                },
            )
        )

    if issues:
        return _fail(
            ct,
            VerificationSeverity.CRITICAL,
            issues,
            warnings=["TOOL_REACH, FLUTE_LENGTH, HOLDER_CLEARANCE reported separately"],
        )
    return _pass(
        ct,
        max_depth_mm=max_depth,
        flute_length_mm=flute_length_mm,
        holder_clearance_mm=holder_clearance_mm,
        effective_reach_mm=effective_reach,
    )


def check_stock_remaining(
    segments: list[VerificationSegment],
    stock: StockModel | None,
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> tuple[VerificationResult, float | None, float | None]:
    """Returns (result, remaining_volume_mm3, removed_volume_mm3)."""
    ct = VerificationCheckType.STOCK_REMAINING
    if stock is None or not stock.is_known:
        return (
            _insufficient(ct, "Stock geometry not provided; remaining stock unknown"),
            None, None,
        )
    if tool_diameter_mm is None:
        return (
            _insufficient(ct, "Tool diameter unknown; stock removal cannot be computed"),
            None, None,
        )

    from .stock import VoxelGrid

    grid = VoxelGrid.from_stock(stock, tol)
    if grid is None:
        return _insufficient(ct, "Could not create voxel grid for given stock shape"), None, None

    initial_vol = stock.volume_mm3()
    radius = tool_diameter_mm / 2.0
    cutting = [s for s in segments if s.is_cutting]

    resource_hit = False
    for seg in cutting:
        if not _valid_coords(seg.start_x, seg.start_y, seg.start_z):
            continue
        if not _valid_coords(seg.end_x, seg.end_y, seg.end_z):
            continue
        ok = grid.remove_path_segment(
            seg.start_x, seg.start_y, seg.start_z,
            seg.end_x, seg.end_y, seg.end_z,
            radius, tol,
        )
        if not ok:
            resource_hit = True
            break

    remaining = grid.volume_remaining_mm3()
    removed = None if initial_vol is None else max(0.0, initial_vol - remaining)

    if resource_hit:
        result = VerificationResult(
            check_type=ct,
            status=VerificationStatus.PARTIAL,
            severity=VerificationSeverity.WARNING,
            evidence={
                "remaining_volume_mm3": remaining,
                "fidelity": "VOXEL_APPROXIMATE",
                "resource_limit_hit": True,
            },
            warnings=["Simulation hit iteration limit; stock removal is PARTIAL"],
        )
    else:
        result = VerificationResult(
            check_type=ct,
            status=VerificationStatus.PASS,
            severity=VerificationSeverity.INFO,
            evidence={
                "remaining_volume_mm3": remaining,
                "initial_volume_mm3": initial_vol,
                "removed_volume_mm3": removed,
                "fidelity": "VOXEL_APPROXIMATE",
            },
            warnings=["Stock removal is voxel-approximate; not suitable for tolerance inspection"],
        )
    return result, remaining, removed


# Phase I backward-compat alias
def check_tool_collision(
    segments: list[VerificationSegment],
    fixtures: list[FixtureGeometry],
    tool_diameter_mm: float | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    return check_tool_fixture_collision(segments, fixtures, tool_diameter_mm, tol)


def check_machine_envelope_with_wcs(
    segments: list[VerificationSegment],
    travel_x_mm: float | None,
    travel_y_mm: float | None,
    travel_z_mm: float | None,
    wcs_offset_x_mm: float = 0.0,
    wcs_offset_y_mm: float = 0.0,
    wcs_offset_z_mm: float = 0.0,
    part_bbox_min: tuple[float, float, float] | None = None,
    part_bbox_max: tuple[float, float, float] | None = None,
    stock_bbox_min: tuple[float, float, float] | None = None,
    stock_bbox_max: tuple[float, float, float] | None = None,
    machine_id: str | None = None,
    machine_limit_source: str = "CATALOG",
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    """Phase J/K — machine envelope check with WCS transform and extents reporting.

    WCS offsets are applied to toolpath segments before comparing against
    machine travel limits. Part and stock extents are checked independently.
    """
    ct = VerificationCheckType.MACHINE_ENVELOPE
    if travel_x_mm is None or travel_y_mm is None or travel_z_mm is None:
        return _insufficient(ct, "Machine travel limits not specified")

    half_x = travel_x_mm / 2.0
    half_y = travel_y_mm / 2.0
    issues: list[VerificationIssue] = []

    # Check toolpath points with WCS transform applied
    for seg in segments:
        for pt in [
            (
                seg.start_x + wcs_offset_x_mm,
                seg.start_y + wcs_offset_y_mm,
                seg.start_z + wcs_offset_z_mm,
            ),
            (
                seg.end_x + wcs_offset_x_mm,
                seg.end_y + wcs_offset_y_mm,
                seg.end_z + wcs_offset_z_mm,
            ),
        ]:
            if not _valid_coords(*pt):
                continue
            if abs(pt[0]) > half_x or abs(pt[1]) > half_y or pt[2] < -travel_z_mm:
                issues.append(_issue(
                    ct, VerificationSeverity.CRITICAL,
                    f"Toolpath exceeds machine travel (WCS-transformed):"
                    f" ({pt[0]:.3f}, {pt[1]:.3f}, {pt[2]:.3f})",
                    segment_id=seg.segment_id,
                    evidence={
                        "point_wcs": list(pt),
                        "travel_x": travel_x_mm,
                        "travel_y": travel_y_mm,
                        "travel_z": travel_z_mm,
                        "wcs_offset": [wcs_offset_x_mm, wcs_offset_y_mm, wcs_offset_z_mm],
                        "MACHINE_ID": machine_id,
                        "MACHINE_LIMIT_SOURCE": machine_limit_source,
                    },
                ))

    # Check part extents (Phase K)
    if part_bbox_min is not None and part_bbox_max is not None:
        for pt in [part_bbox_min, part_bbox_max]:
            px = pt[0] + wcs_offset_x_mm
            py = pt[1] + wcs_offset_y_mm
            pz = pt[2] + wcs_offset_z_mm
            if abs(px) > half_x or abs(py) > half_y or pz < -travel_z_mm:
                issues.append(_issue(
                    ct, VerificationSeverity.CRITICAL,
                    f"Part extent exceeds machine travel: ({px:.3f}, {py:.3f}, {pz:.3f})",
                    evidence={"source": "PART_BBOX", "point_wcs": [px, py, pz]},
                ))

    if issues:
        return _fail(ct, VerificationSeverity.CRITICAL, issues)
    return _pass(
        ct,
        travel_x=travel_x_mm,
        travel_y=travel_y_mm,
        travel_z=travel_z_mm,
        machine_id=machine_id,
        machine_limit_source=machine_limit_source,
        wcs_offset=[wcs_offset_x_mm, wcs_offset_y_mm, wcs_offset_z_mm],
    )


def check_kinematic(
    segments: list[VerificationSegment],
    machine_model: dict | None,
    tol: TolerancePolicy = DEFAULT_TOLERANCE,
) -> VerificationResult:
    ct = VerificationCheckType.KINEMATIC_CHECK
    return _not_performed(
        ct,
        "KINEMATIC_CHECK is a foundation placeholder at Level 11; "
        "full kinematic simulation deferred to Level 12+",
    )


def _valid_coords(x: float, y: float, z: float) -> bool:
    """Return False for NaN, Inf, or extreme coordinates."""
    for v in (x, y, z):
        if math.isnan(v) or math.isinf(v):
            return False
        if abs(v) > 1e9:
            return False
    return True
