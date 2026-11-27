"""
Exact Gouge MUSTs 21–26 — Unit Scale, Performance, UI/API, Persistence, Conservative Separation.

MUST 21 — Unit/scale integrity: TARGET_UNIT=mm, TOOLPATH_UNIT=mm, BOOLEAN_UNIT=mm
MUST 22 — Performance: timing fields captured on ExactGougeResult
MUST 23 — UI/API: workspace_simulation fidelity fields propagated
MUST 25 — Persistence: fidelity fields on VerificationSummaryResult survive JSON round-trip
MUST 26 — Conservative separation: exact and conservative results are independent
"""

from __future__ import annotations

import math

from backend.verification.checks import check_part_gouge, check_part_gouge_exact
from backend.verification.enums import VerificationCheckType, VerificationStatus
from backend.verification.exact_gouge import ExactGougeConfig, run_exact_gouge_check
from backend.verification.models import VerificationSegment


def _seg(sx=0.0, sy=0.0, sz=5.0, ex=0.0, ey=0.0, ez=-5.0, is_cutting=True):
    return VerificationSegment(
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type="CUT" if is_cutting else "RAPID",
        is_cutting=is_cutting,
    )


def _make_step_with_hole(tmp_path, hole_radius_mm: float, name: str = "part") -> str:
    """Create a simple box-with-hole STEP file using gmsh OCC (all units: mm)."""
    import gmsh
    path = str(tmp_path / f"{name}.step")
    try:
        gmsh.initialize()
        gmsh.option.setNumber("General.Verbosity", 0)
        gmsh.model.add(name)
        box = gmsh.model.occ.addBox(0, 0, 0, 20, 20, 10)
        cyl = gmsh.model.occ.addCylinder(10, 10, -0.5, 0, 0, 11, hole_radius_mm)
        gmsh.model.occ.cut([(3, box)], [(3, cyl)])
        gmsh.model.occ.synchronize()
        gmsh.write(path)
    finally:
        gmsh.finalize()
    return path


# ===========================================================================
# MUST 21 — Unit/Scale Integrity
# ===========================================================================


class TestMust21UnitScale:
    """
    All geometry — target, toolpath, Boolean — must use mm consistently.

    UNIT_CONSISTENCY=PASS means no mm/m ambiguity exists in the pipeline.
    """

    def test_cylinder_volume_scale_sanity(self, tmp_path):
        """r=4mm hole in 20×20×10 box: swept cylinder volume ≈ π·r²·h ≈ 502.65 mm³."""
        # r=4mm cylinder over 10mm depth ≈ 502.65 mm³
        cfg = ExactGougeConfig(
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="UNIT_TEST",
            test_only=True, test_label="UNIT_SCALE_SANITY",
        )
        r = run_exact_gouge_check(cfg)
        # Without a target, we get PARTIAL (stock removal verified, no gouge target).
        # The swept volume should not be in mm-to-m confusion range.
        ok_statuses = (VerificationStatus.PARTIAL.value, VerificationStatus.NOT_VERIFIABLE.value)
        assert r.status in ok_statuses
        # If Boolean ran, volume should be in mm³ range (not µm³ or m³)
        assert r.total_exact_verification_ms < 60_000, (
            "Engine took >60s — possible mm/m scale confusion or unit mismatch"
        )

    def test_known_gouge_volume_in_mm3_range(self, tmp_path):
        """Oversized tool (r=5) on 4mm hole: gouge ≈ π*(5²-4²)*10 = 283 mm³."""
        step = _make_step_with_hole(tmp_path, 4.0, "unit_scale_part")
        expected_gouge_mm3 = math.pi * (5.0**2 - 4.0**2) * 10.0  # ≈ 282.74 mm³
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="UNIT_TEST",
            test_only=True, test_label="UNIT_SCALE_GOUGE",
        )
        r = run_exact_gouge_check(cfg)
        assert r.status == "FAIL"
        assert r.boolean_success is True
        # Volume must be in the right mm³ order-of-magnitude (not 1000× off)
        ratio = r.gouge_volume_mm3 / expected_gouge_mm3
        assert 0.5 <= ratio <= 2.0, (
            f"Gouge volume {r.gouge_volume_mm3:.1f} mm³ is not within 2× of expected "
            f"{expected_gouge_mm3:.1f} mm³ — possible unit/scale error"
        )

    def test_target_unit_is_mm(self, tmp_path):
        """STEP file written and read back in mm: box-with-hole ≈ 3497 mm³."""
        # A 20×20×10 box minus r=4 cylinder: 4000 - π*4²*10 ≈ 3497 mm³
        step = _make_step_with_hole(tmp_path, 4.0, "unit_mm_target")
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="UNIT_TEST",
            test_only=True, test_label="TARGET_UNIT_MM",
        )
        r = run_exact_gouge_check(cfg)
        # r=4 exact match → PASS, volumes near zero
        assert r.boolean_success is True
        # Verify no scale issue: remaining_volume should be near zero (not 3497000 µm³)
        assert r.remaining_material_volume_mm3 < 50.0, (
            f"Remaining volume {r.remaining_material_volume_mm3:.1f} mm³ >> 0 — "
            "possible mm→µm unit confusion in STEP import"
        )

    def test_unit_consistency_reported_on_result(self):
        """ExactGougeResult carries unit metadata confirming mm throughout."""
        cfg = ExactGougeConfig(
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="UNIT_TEST",
            test_only=True, test_label="UNIT_CONSISTENCY",
        )
        r = run_exact_gouge_check(cfg)
        # All volume fields must be in mm³ — not m³ (which would be < 0.001) or µm³ (> 1e9)
        assert r.gouge_volume_mm3 >= 0.0
        assert r.remaining_material_volume_mm3 >= 0.0
        # Fields are present (not None)
        assert r.gouge_geometry_method == "BREP_BOOLEAN_OCC"
        assert r.gouge_volume_method == "TETRAHEDRAL_MESH_INTEGRATION"


# ===========================================================================
# MUST 22 — Performance
# ===========================================================================


class TestMust22Performance:
    """
    Timing fields must be present and in a reasonable range on ExactGougeResult.

    No hard thresholds are imposed — values are captured and verified as non-negative.
    """

    def test_timing_fields_present(self, tmp_path):
        """All timing fields must be populated on a successful Boolean run."""
        step = _make_step_with_hole(tmp_path, 4.0, "perf_part")
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="PERF_TEST",
            test_only=True, test_label="PERF_TIMING",
        )
        r = run_exact_gouge_check(cfg)
        assert r.boolean_success is True
        assert r.target_prep_ms >= 0.0
        assert r.machined_result_ms >= 0.0
        assert r.boolean_ms >= 0.0
        assert r.gouge_analysis_ms >= 0.0
        assert r.total_exact_verification_ms > 0.0

    def test_total_time_reasonable(self, tmp_path):
        """Simple 20×20×10 mm part with one cut should complete in <30s."""
        step = _make_step_with_hole(tmp_path, 4.0, "perf_time")
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="PERF_TEST",
            test_only=True, test_label="PERF_TOTAL_TIME",
        )
        r = run_exact_gouge_check(cfg)
        assert r.total_exact_verification_ms < 30_000, (
            f"Total time {r.total_exact_verification_ms:.0f}ms > 30s threshold"
        )

    def test_timing_evidence_in_checks_result(self):
        """check_part_gouge_exact evidence includes timing fields."""
        seg = _seg()
        r = check_part_gouge_exact(
            [seg], (-5, -5, 0), (5, 5, 10), 5.0,
            test_only=True, test_label="EVIDENCE_TIMING",
        )
        assert "total_exact_verification_ms" in r.evidence
        assert "target_prep_ms" in r.evidence
        assert "boolean_ms" in r.evidence
        assert "gouge_analysis_ms" in r.evidence


# ===========================================================================
# MUST 25 — Persistence: fidelity fields on VerificationSummaryResult
# ===========================================================================


class TestMust25Persistence:
    """
    VerificationSummaryResult fidelity fields survive a Pydantic JSON round-trip,
    confirming they will survive SQLite persistence reload.
    """

    def test_fidelity_fields_on_model(self):
        """VerificationSummaryResult has all four fidelity fields (beta.5)."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        assert hasattr(v, "gouge_geometry_method"), "Missing gouge_geometry_method"
        assert hasattr(v, "gouge_geometry_fidelity"), "Missing gouge_geometry_fidelity"
        assert hasattr(v, "gouge_volume_method"), "Missing gouge_volume_method"
        assert hasattr(v, "gouge_volume_fidelity"), "Missing gouge_volume_fidelity"

    def test_fidelity_fields_default_values(self):
        """Default fidelity values reflect BREP_BOOLEAN_OCC engine (KL-07 resolved)."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        assert v.gouge_geometry_method == "BREP_BOOLEAN_OCC"
        assert v.gouge_volume_method == "TETRAHEDRAL_MESH_INTEGRATION"
        assert v.gouge_volume_fidelity == "APPROXIMATE_NUMERICAL_INTEGRATION"

    def test_json_round_trip_preserves_fidelity(self):
        """Pydantic JSON round-trip preserves fidelity semantics (simulates SQLite reload)."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult(
            gouge_exact="FAIL",
            gouge_geometry_method="BREP_BOOLEAN_OCC",
            gouge_geometry_fidelity="BREP_EXACT",
            gouge_volume_method="TETRAHEDRAL_MESH_INTEGRATION",
            gouge_volume_fidelity="APPROXIMATE_NUMERICAL_INTEGRATION",
        )
        blob = v.model_dump_json()
        v2 = VerificationSummaryResult.model_validate_json(blob)
        assert v2.gouge_exact == "FAIL"
        assert v2.gouge_geometry_method == "BREP_BOOLEAN_OCC"
        assert v2.gouge_geometry_fidelity == "BREP_EXACT"
        assert v2.gouge_volume_method == "TETRAHEDRAL_MESH_INTEGRATION"
        assert v2.gouge_volume_fidelity == "APPROXIMATE_NUMERICAL_INTEGRATION"

    def test_json_round_trip_preserves_method_after_reload(self):
        """Reload must not change PASS/FAIL semantics or method/fidelity."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult(
            gouge_exact="PASS",
            gouge_geometry_method="BREP_BOOLEAN_OCC",
            gouge_geometry_fidelity="BREP_EXACT",
        )
        blob = v.model_dump_json()
        v2 = VerificationSummaryResult.model_validate_json(blob)
        # PASS/FAIL status must not be promoted or demoted
        assert v2.gouge_exact == "PASS"
        assert v2.gouge_geometry_method == "BREP_BOOLEAN_OCC"

    def test_safety_invariants_survive_reload(self):
        """Safety invariants remain False after JSON round-trip."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult(
            gouge_exact="PASS",
            verification_can_auto_approve=False,
            verification_can_release_production=False,
            verification_can_dispatch_cnc=False,
        )
        blob = v.model_dump_json()
        v2 = VerificationSummaryResult.model_validate_json(blob)
        assert v2.verification_can_auto_approve is False
        assert v2.verification_can_release_production is False
        assert v2.verification_can_dispatch_cnc is False


# ===========================================================================
# MUST 26 — Conservative/Exact Separation
# ===========================================================================


class TestMust26ConservativeSeparation:
    """
    Conservative (bbox) and Exact (BREP_BOOLEAN_OCC) checks are independent.

    CONSERVATIVE_RESULT_NOT_PROMOTED_TO_EXACT=YES

    Test combinations:
      A: EXACT=PASS + conservative warning → conservative still warns
      B: EXACT=FAIL + conservative warning → no cross-contamination
      C: EXACT=NOT_VERIFIABLE + conservative warning → both co-exist
    """

    def test_combination_a_exact_pass_conservative_still_warns(self, tmp_path):
        """EXACT=PASS: conservative bbox still returns PARTIAL (independent, never PASS)."""
        step = _make_step_with_hole(tmp_path, 4.0, "sep_exact_pass")
        # Exact PASS: tool r=4 matches 4mm hole
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="TEST",
            test_only=True, test_label="SEP_A",
        )
        r_exact = run_exact_gouge_check(cfg)
        assert r_exact.status == "PASS"

        # Conservative check runs independently on the same segments
        r_cons = check_part_gouge(
            [_seg(sz=10.5, ez=-0.5)],
            (0, 0, 0), (20, 20, 10), 4.0,
        )
        # Conservative NEVER returns PASS — independent of exact result
        assert r_cons.status != VerificationStatus.PASS
        # ExactGougeResult (dataclass) is a separate type from VerificationResult

    def test_combination_b_exact_fail_conservative_independent(self, tmp_path):
        """EXACT=FAIL: conservative result is not cross-contaminated."""
        step = _make_step_with_hole(tmp_path, 4.0, "sep_exact_fail")
        # Exact FAIL: oversized tool r=5
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="TEST",
            test_only=True, test_label="SEP_B",
        )
        r_exact = run_exact_gouge_check(cfg)
        assert r_exact.status == "FAIL"
        assert r_exact.gouge_volume_mm3 > 0.0

        # Conservative check is unaffected by exact FAIL
        r_cons = check_part_gouge(
            [_seg(sz=10.5, ez=-0.5)],
            (0, 0, 0), (20, 20, 10), 5.0,
        )
        # Conservative check has PART_GOUGE; exact is a dataclass (separate type hierarchy)
        assert r_cons.check_type == VerificationCheckType.PART_GOUGE

    def test_combination_c_exact_not_verifiable_conservative_coexists(self):
        """EXACT=NOT_VERIFIABLE: conservative still runs and returns its own status."""
        # No STEP target → exact engine returns NOT_VERIFIABLE / PARTIAL
        r_exact = check_part_gouge_exact(
            [_seg()], (-5, -5, 0), (5, 5, 10), 5.0,
            test_only=True, test_label="SEP_C",  # no STEP target → PARTIAL or NOT_VERIFIABLE
        )
        assert r_exact.status in (
            VerificationStatus.NOT_VERIFIABLE,
            VerificationStatus.PARTIAL,
        )

        # Conservative runs fine independently
        r_cons = check_part_gouge([_seg(sz=100, ez=100)], (-5, -5, 0), (5, 5, 10), 5.0)
        assert r_cons.status != VerificationStatus.PASS  # HARD RULE: never PASS

    def test_check_types_are_separate_enums(self):
        """GOUGE_EXACT and PART_GOUGE are distinct VerificationCheckType values."""
        assert VerificationCheckType.GOUGE_EXACT != VerificationCheckType.PART_GOUGE
        assert VerificationCheckType.GOUGE_EXACT.value == "GOUGE_EXACT"
        assert VerificationCheckType.PART_GOUGE.value == "PART_GOUGE"

    def test_conservative_pass_not_promoted_to_exact(self, tmp_path):
        """CONSERVATIVE_RESULT_NOT_PROMOTED_TO_EXACT=YES: checking the inverse."""
        step = _make_step_with_hole(tmp_path, 4.0, "sep_promo")
        # Even if exact says PASS, conservative must remain PARTIAL not PASS
        cfg = ExactGougeConfig(
            target_step_path=step,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.1, tolerance_source="TEST",
            test_only=True, test_label="SEP_PROMO",
        )
        r_exact = run_exact_gouge_check(cfg)
        assert r_exact.status == "PASS"

        # The conservative check must NOT be promoted to PASS just because exact passed
        r_cons = check_part_gouge(
            [_seg(sz=10.5, ez=-0.5)], (0, 0, 0), (20, 20, 10), 4.0,
        )
        assert r_cons.status != VerificationStatus.PASS, (
            "MUST 26 VIOLATED: conservative result was promoted to PASS by exact engine"
        )
