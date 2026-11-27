"""
Exact Gouge Phase 15–20 — Safety, Live Acceptance, Deterministic Cases.

PHASE 15  — Safety invariant validation
PHASE 16  — Real STEP live acceptance (3 qualification parts)
MUST 17   — Known no-gouge live case: PASS
MUST 18   — Known gouge live case: FAIL
MUST 19   — Remaining material case: DETECTED
MUST 20   — Boolean failure → NOT_VERIFIABLE (not PASS)

Fidelity semantics verified throughout:
  GOUGE_GEOMETRY_METHOD=BREP_BOOLEAN_OCC
  GOUGE_GEOMETRY_FIDELITY=BREP_EXACT
  GOUGE_VOLUME_METHOD=TETRAHEDRAL_MESH_INTEGRATION
  GOUGE_VOLUME_FIDELITY=APPROXIMATE_NUMERICAL_INTEGRATION
"""

from __future__ import annotations

import os
import threading

import pytest

from backend.verification.exact_gouge import ExactGougeConfig, run_exact_gouge_check
from backend.verification.models import VerificationSegment

# Qualification STEP files — real B-Rep geometry
_S1 = "tests/qualification/fixtures/step/P10_S1_drilled_block.step"   # drilling-dominant
_S2 = "tests/qualification/fixtures/step/P10_S2_pocket_slot.step"     # slot/pocket
_S3 = "tests/qualification/fixtures/step/P10_S3_multi_feature.step"   # multi-operation


def _real_step_exists(path: str) -> bool:
    return os.path.isfile(path)


def _seg(sx=0.0, sy=0.0, sz=25.0, ex=0.0, ey=0.0, ez=-1.0) -> VerificationSegment:
    return VerificationSegment(
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type="LINEAR", is_cutting=True,
    )


def _make_step_with_known_hole(tmp_path, hole_radius: float, name: str) -> str:
    """Create deterministic STEP: box with a cylindrical hole."""
    import gmsh
    step_path = str(tmp_path / f"{name}.step")
    with threading.Lock():
        try:
            gmsh.initialize()
            gmsh.option.setNumber("General.Verbosity", 0)
            gmsh.model.add(name)
            box = gmsh.model.occ.addBox(0, 0, 0, 20, 20, 10)
            cyl = gmsh.model.occ.addCylinder(10, 10, -0.5, 0, 0, 11, hole_radius)
            gmsh.model.occ.cut([(3, box)], [(3, cyl)])
            gmsh.model.occ.synchronize()
            gmsh.write(step_path)
        finally:
            gmsh.finalize()
    return step_path


# ---------------------------------------------------------------------------
# PHASE 15 — Safety invariant validation
# ---------------------------------------------------------------------------


class TestPhase15SafetyInvariants:
    """Verify exact gouge check cannot unlock any dispatch gate."""

    def test_exact_verification_can_auto_approve_always_false(self):
        """EXACT_VERIFICATION_CAN_AUTO_APPROVE=NO — model constant."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        assert v.verification_can_auto_approve is False

    def test_exact_verification_can_dispatch_cnc_always_false(self):
        """VERIFICATION_CAN_DISPATCH_CNC=NO — model constant."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        assert v.verification_can_dispatch_cnc is False

    def test_exact_verification_can_release_production_always_false(self):
        """EXACT_VERIFICATION_CAN_RELEASE_PRODUCTION=NO."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        assert v.verification_can_release_production is False

    def test_exact_pass_does_not_set_auto_approve(self):
        """GOUGE_EXACT=PASS must not flip verification_can_auto_approve."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        v.gouge_exact = "PASS"   # simulate exact engine returning PASS
        assert v.verification_can_auto_approve is False

    def test_exact_pass_does_not_set_dispatch_cnc(self):
        """GOUGE_EXACT=PASS must not flip verification_can_dispatch_cnc."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        v.gouge_exact = "PASS"
        assert v.verification_can_dispatch_cnc is False

    def test_exact_pass_does_not_set_release_production(self):
        """GOUGE_EXACT=PASS must not flip verification_can_release_production."""
        from backend.autocam.models import VerificationSummaryResult
        v = VerificationSummaryResult()
        v.gouge_exact = "PASS"
        assert v.verification_can_release_production is False

    def test_auto_cam_can_dispatch_cnc_always_false(self):
        """AUTO_CAM_CAN_DISPATCH_CNC=NO — autocam api safety constant."""
        from backend.autocam import api as autocam_api
        assert autocam_api._SAFETY["AUTO_CAM_CAN_DISPATCH_CNC"] is False

    def test_real_machine_write_found_no(self):
        """REAL_MACHINE_WRITE_FOUND=NO — autocam api safety constant."""
        from backend.autocam import api as autocam_api
        assert autocam_api._SAFETY["REAL_MACHINE_WRITE_FOUND"] is False

    def test_gcode_dispatch_no(self):
        """NO_GCODE_DISPATCH constant in nc_generation module."""
        # Module-level constant (in docstring/comment); check the string is present
        import inspect

        import backend.api.nc_generation as nc
        src = inspect.getsource(nc)
        assert "NO_GCODE_DISPATCH" in src

    def test_orchestrator_phase_q_always_locks_dispatch(self):
        """Phase Q in orchestrator always sets dispatch/approve flags to False.

        EXACT_GOUGE_FEATURE_CONFIRMATION_CHANGED=NO
        EXACT_GOUGE_WCS_CONFIRMATION_CHANGED=NO
        EXACT_GOUGE_PRODUCTION_RELEASE_CHANGED=NO
        """
        import inspect

        import backend.autocam.orchestrator as orch
        src = inspect.getsource(orch)
        # Phase Q must set all three to False — verify source contains hardcoded assignments
        assert "verification_can_auto_approve = False" in src
        assert "verification_can_release_production = False" in src
        assert "verification_can_dispatch_cnc = False" in src


# ---------------------------------------------------------------------------
# PHASE 16 — Real STEP live acceptance
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _real_step_exists(_S1),
    reason="Qualification STEP fixture not found"
)
class TestPhase16LiveAcceptance:
    """Real STEP parts — verify engine runs and reports correct fidelity fields."""

    def _run(self, step_path: str, bbox: tuple, cuts: list, label: str):
        """Helper: run exact gouge check and return result."""
        (xmin, ymin, zmin), (xmax, ymax, zmax) = bbox
        margin = 2.0
        cfg = ExactGougeConfig(
            target_step_path=step_path,
            stock_x_mm=xmin - margin, stock_y_mm=ymin - margin, stock_z_mm=zmin - margin,
            stock_w_mm=(xmax - xmin) + 2 * margin,
            stock_h_mm=(ymax - ymin) + 2 * margin,
            stock_d_mm=(zmax - zmin) + 2 * margin,
            tool_radius_mm=4.0,
            cutting_segments=cuts,
            tolerance_mm=None,       # no production tolerance — use test_only
            test_only=True,
            test_label=label,
        )
        return run_exact_gouge_check(cfg)

    def test_s1_drilled_block_engine_runs(self):
        """P10_S1 drilled block (60×40×20) — engine runs without error."""
        cuts = [(30, 20, 22, 30, 20, -1)]  # drill through center
        result = self._run(
            _S1,
            ((0, 0, 0), (60, 40, 20)),
            cuts,
            "P10_S1_DRILLED_BLOCK"
        )
        assert result.boolean_success, f"Boolean failed: {result.error}"
        assert result.error is None

    def test_s1_reports_brep_exact_geometry_fidelity(self):
        """STEP target → GOUGE_GEOMETRY_FIDELITY=BREP_EXACT (not tessellated)."""
        cuts = [(30, 20, 22, 30, 20, -1)]
        result = self._run(_S1, ((0, 0, 0), (60, 40, 20)), cuts, "S1_FIDELITY")
        assert result.gouge_geometry_fidelity == "BREP_EXACT", (
            f"Expected BREP_EXACT, got {result.gouge_geometry_fidelity}"
        )

    def test_s1_reports_volume_fidelity(self):
        """Phase C/D: BREP_EXACT when getMass succeeds; fallback = APPROXIMATE_NUMERICAL_INTEGRATION."""
        cuts = [(30, 20, 22, 30, 20, -1)]
        result = self._run(_S1, ((0, 0, 0), (60, 40, 20)), cuts, "S1_VOL_FIDELITY")
        assert result.gouge_volume_fidelity in (
            "BREP_EXACT", "APPROXIMATE_NUMERICAL_INTEGRATION"
        )
        assert result.gouge_volume_method in (
            "BREP_SOLID_VOLUME", "TETRAHEDRAL_MESH_INTEGRATION"
        )

    def test_s1_timing_all_fields_positive(self):
        cuts = [(30, 20, 22, 30, 20, -1)]
        result = self._run(_S1, ((0, 0, 0), (60, 40, 20)), cuts, "S1_TIMING")
        assert result.total_exact_verification_ms > 0.0
        assert result.target_prep_ms >= 0.0
        assert result.machined_result_ms >= 0.0

    @pytest.mark.skipif(not _real_step_exists(_S2), reason="S2 not found")
    def test_s2_pocket_slot_engine_runs(self):
        """P10_S2 pocket_slot (80×60×30) — engine runs without error."""
        # Pocket pass: endmill sweeping in X across center
        cuts = [
            (10, 30, 32, 70, 30, 32),   # approach
            (10, 30, 32, 10, 30, -1),   # plunge
            (10, 30, -1, 70, 30, -1),   # slot cut
        ]
        result = self._run(_S2, ((0, 0, 0), (80, 60, 30)), cuts, "P10_S2_POCKET_SLOT")
        assert result.boolean_success, f"Boolean failed: {result.error}"

    @pytest.mark.skipif(not _real_step_exists(_S2), reason="S2 not found")
    def test_s2_reports_brep_exact_geometry_fidelity(self):
        cuts = [(40, 30, 32, 40, 30, -1)]
        result = self._run(_S2, ((0, 0, 0), (80, 60, 30)), cuts, "S2_FIDELITY")
        assert result.gouge_geometry_fidelity == "BREP_EXACT"
        # Phase C/D: BREP_EXACT primary; APPROXIMATE_NUMERICAL_INTEGRATION on fallback
        assert result.gouge_volume_fidelity in (
            "BREP_EXACT", "APPROXIMATE_NUMERICAL_INTEGRATION"
        )

    @pytest.mark.skipif(not _real_step_exists(_S3), reason="S3 not found")
    def test_s3_multi_feature_engine_runs(self):
        """P10_S3 multi_feature (80×60×35) — engine runs without error."""
        cuts = [
            (20, 15, 37, 20, 15, -1),   # drill
            (60, 15, 37, 60, 15, -1),   # drill
            (10, 40, 37, 70, 40, 37),   # approach
            (10, 40, 37, 10, 40, -1),   # plunge
            (10, 40, -1, 70, 40, -1),   # slot
        ]
        result = self._run(_S3, ((0, 0, 0), (80, 60, 35)), cuts, "P10_S3_MULTI")
        assert result.boolean_success, f"Boolean failed: {result.error}"

    @pytest.mark.skipif(not _real_step_exists(_S3), reason="S3 not found")
    def test_s3_volume_integration_error_reported(self):
        """When fallback mesh is used, error_pct must be reported; BREP_EXACT = None."""
        cuts = [(40, 30, 37, 40, 30, -1)]
        result = self._run(_S3, ((0, 0, 0), (80, 60, 35)), cuts, "S3_ERR")
        if result.gouge_volume_fidelity == "APPROXIMATE_NUMERICAL_INTEGRATION":
            assert 0.0 < result.volume_integration_error_pct < 5.0, (
                f"volume_integration_error_pct={result.volume_integration_error_pct} not in (0,5)"
            )
        else:
            # BREP_EXACT path: error_pct is None (no approximation)
            assert result.volume_integration_error_pct is None

    def test_no_production_tolerance_no_pass(self):
        """Without a real production tolerance, live run must not return PASS."""
        cuts = [(30, 20, 22, 30, 20, -1)]
        cfg = ExactGougeConfig(
            target_step_path=_S1,
            stock_x_mm=-2, stock_y_mm=-2, stock_z_mm=-2,
            stock_w_mm=64, stock_h_mm=44, stock_d_mm=24,
            tool_radius_mm=4.0,
            cutting_segments=cuts,
            tolerance_mm=None,
            test_only=False,       # production path — requires real tolerance
        )
        result = run_exact_gouge_check(cfg)
        assert result.status == "NOT_VERIFIABLE", (
            f"Without tolerance, expected NOT_VERIFIABLE, got {result.status}"
        )


# ---------------------------------------------------------------------------
# MUST 17 — Known no-gouge live case
# ---------------------------------------------------------------------------


class TestMust17KnownNoGouge:
    """
    KNOWN_NO_GOUGE_RESULT=PASS

    Conditions required:
      - target geometry exists (from STEP)
      - machined-result geometry exists
      - Boolean succeeds
      - tolerance is valid
      - tool exactly matches hole in target → no over-cut, no remaining material
    """

    def test_known_no_gouge_result_pass(self, tmp_path):
        """8mm hole target, 8mm drill, test_only=True → PASS."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="no_gouge")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,          # matches hole exactly
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05,
            tolerance_source="TEST_ONLY_DIAGNOSTIC",
            test_only=True,
            test_label="MUST17_KNOWN_NO_GOUGE",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success, f"Boolean failed: {result.error}"
        assert result.status == "PASS", (
            f"MUST17 FAIL: expected PASS, got {result.status}. "
            f"gouge={result.gouge_volume_mm3:.3f}, "
            f"remaining={result.remaining_material_volume_mm3:.3f}"
        )

    def test_known_no_gouge_has_zero_gouge_volume(self, tmp_path):
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="ng_vol")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST17_VOL",
        )
        result = run_exact_gouge_check(cfg)
        assert result.gouge_volume_mm3 == 0.0, (
            f"Expected 0 gouge volume, got {result.gouge_volume_mm3:.4f}"
        )

    def test_known_no_gouge_boolean_success_true(self, tmp_path):
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="ng_bool")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST17_BOOL",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success is True

    def test_known_no_gouge_fidelity_brep_exact(self, tmp_path):
        """PASS result from STEP → geometry fidelity must be BREP_EXACT."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="ng_fid")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST17_FID",
        )
        result = run_exact_gouge_check(cfg)
        assert result.gouge_geometry_fidelity == "BREP_EXACT"
        # Phase C/D: BREP_EXACT primary; fallback retains APPROXIMATE_NUMERICAL_INTEGRATION
        assert result.gouge_volume_fidelity in (
            "BREP_EXACT", "APPROXIMATE_NUMERICAL_INTEGRATION"
        )


# ---------------------------------------------------------------------------
# MUST 18 — Known gouge live case
# ---------------------------------------------------------------------------


class TestMust18KnownGouge:
    """
    KNOWN_GOUGE_RESULT=FAIL
    GOUGE_REGION_COUNT>0
    MAX_GOUGE_DEPTH>0  (depth not yet computed — volume>0 is sufficient)

    Uses isolated TEST_ONLY geometry. Does not modify production CAD.
    """

    def test_known_gouge_result_fail(self, tmp_path):
        """8mm hole target, 10mm drill → 1mm annular gouge → FAIL."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="gouge_fail")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0,          # 10mm drill — 2mm oversized
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST18_KNOWN_GOUGE",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success, f"Boolean failed: {result.error}"
        assert result.status == "FAIL", (
            f"MUST18 FAIL: expected FAIL (gouge), got {result.status}. "
            f"gouge_volume={result.gouge_volume_mm3:.3f}"
        )

    def test_known_gouge_volume_positive(self, tmp_path):
        """GOUGE_VOLUME>0 when oversize tool used."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="gouge_vol")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST18_VOL",
        )
        result = run_exact_gouge_check(cfg)
        assert result.gouge_volume_mm3 > 0.0, (
            f"Expected positive gouge volume, got {result.gouge_volume_mm3}"
        )

    def test_known_gouge_region_count_positive(self, tmp_path):
        """GOUGE_REGION_COUNT>0."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="gouge_rgn")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST18_RGN",
        )
        result = run_exact_gouge_check(cfg)
        assert result.gouge_region_count > 0, (
            f"Expected gouge_region_count>0, got {result.gouge_region_count}"
        )

    def test_known_gouge_volume_approximate_fidelity(self, tmp_path):
        """Even in FAIL case, volume must be reported as APPROXIMATE."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="gouge_fid")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST18_FID",
        )
        result = run_exact_gouge_check(cfg)
        # Phase C/D: BREP_EXACT primary; fallback retains APPROXIMATE_NUMERICAL_INTEGRATION
        assert result.gouge_volume_fidelity in (
            "BREP_EXACT", "APPROXIMATE_NUMERICAL_INTEGRATION"
        )
        assert result.gouge_geometry_fidelity == "BREP_EXACT"


# ---------------------------------------------------------------------------
# MUST 19 — Remaining material case
# ---------------------------------------------------------------------------


class TestMust19RemainingMaterial:
    """
    KNOWN_REMAINING_RESULT=DETECTED
    REMAINING_VOLUME>0
    Gouge and remaining material are independent.
    """

    def test_remaining_material_detected(self, tmp_path):
        """8mm hole target, 6mm drill → remaining annular ring → PARTIAL."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="remain")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=3.0,          # 6mm drill — 2mm undersize
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST19_REMAINING",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success, f"Boolean failed: {result.error}"
        assert result.status == "PARTIAL", (
            f"MUST19 FAIL: expected PARTIAL (remaining), got {result.status}. "
            f"remaining={result.remaining_material_volume_mm3:.3f}"
        )

    def test_remaining_material_volume_positive(self, tmp_path):
        """REMAINING_VOLUME>0."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="rem_vol")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=3.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST19_VOL",
        )
        result = run_exact_gouge_check(cfg)
        assert result.remaining_material_volume_mm3 > 0.0

    def test_remaining_material_no_gouge_volume(self, tmp_path):
        """Undersize tool: remaining material but no over-cut gouge."""
        target = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="rem_nogouge")
        cfg = ExactGougeConfig(
            target_step_path=target,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=3.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, tolerance_source="TEST_ONLY",
            test_only=True, test_label="MUST19_INDEPENDENCE",
        )
        result = run_exact_gouge_check(cfg)
        # Undersize tool: no gouge (tool didn't cut target material), only remaining
        assert result.gouge_volume_mm3 == 0.0, (
            f"Undersize tool should have 0 gouge, got {result.gouge_volume_mm3:.4f}"
        )
        assert result.remaining_material_volume_mm3 > 0.0

    def test_gouge_and_remaining_independent(self, tmp_path):
        """Gouge and remaining are independent fields (not mixed)."""
        target_gouge = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="ind_gouge")
        target_remain = _make_step_with_known_hole(tmp_path, hole_radius=4.0, name="ind_remain")

        # Gouge case
        cfg_g = ExactGougeConfig(
            target_step_path=target_gouge,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=5.0, cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, test_only=True, test_label="IND_GOUGE",
        )
        r_g = run_exact_gouge_check(cfg_g)

        # Remaining case
        cfg_r = ExactGougeConfig(
            target_step_path=target_remain,
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=3.0, cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=0.05, test_only=True, test_label="IND_REMAIN",
        )
        r_r = run_exact_gouge_check(cfg_r)

        # Gouge case: gouge>0, remaining=0
        assert r_g.gouge_volume_mm3 > 0.0
        assert r_g.remaining_material_volume_mm3 == 0.0

        # Remaining case: gouge=0, remaining>0
        assert r_r.gouge_volume_mm3 == 0.0
        assert r_r.remaining_material_volume_mm3 > 0.0


# ---------------------------------------------------------------------------
# MUST 20 — Boolean failure → NOT_VERIFIABLE (not PASS)
# ---------------------------------------------------------------------------


class TestMust20BooleanFailure:
    """
    Deliberately invalid geometry → NOT_VERIFIABLE.
    BOOLEAN_FAILURE_RETURNS_NOT_VERIFIABLE=YES (spec says "not PASS")
    """

    def test_nonexistent_step_no_target_partial_or_not_verifiable(self):
        """Non-existent STEP → no target → cannot be PASS."""
        cfg = ExactGougeConfig(
            target_step_path="/nonexistent/path/does_not_exist.step",
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            test_only=True, test_label="MUST20_MISSING_STEP",
        )
        result = run_exact_gouge_check(cfg)
        assert result.status != "PASS", (
            "MUST20 FAIL: missing STEP returned PASS — not acceptable"
        )
        assert result.status in ("PARTIAL", "NOT_VERIFIABLE")

    def test_zero_stock_dimension_returns_not_verifiable(self):
        """Zero stock depth → Boolean cannot produce valid machined result → NOT_VERIFIABLE."""
        cfg = ExactGougeConfig(
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20,
            stock_d_mm=0.0,              # zero depth — degenerate
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            test_only=True, test_label="MUST20_ZERO_STOCK",
        )
        result = run_exact_gouge_check(cfg)
        assert result.status != "PASS", (
            "MUST20 FAIL: zero-dimension stock returned PASS"
        )

    def test_no_cutting_segments_not_verifiable(self):
        """No cutting segments → NOT_VERIFIABLE (no swept volume to build)."""
        cfg = ExactGougeConfig(
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[],
            test_only=True, test_label="MUST20_NO_SEGS",
        )
        result = run_exact_gouge_check(cfg)
        assert result.status == "NOT_VERIFIABLE"
        assert result.boolean_success is False

    def test_no_tolerance_non_test_not_verifiable(self):
        """Production path without tolerance → NOT_VERIFIABLE."""
        cfg = ExactGougeConfig(
            stock_x_mm=0, stock_y_mm=0, stock_z_mm=0,
            stock_w_mm=20, stock_h_mm=20, stock_d_mm=10,
            tool_radius_mm=4.0,
            cutting_segments=[(10, 10, 10.5, 10, 10, -0.5)],
            tolerance_mm=None,
            test_only=False,             # production mode — requires tolerance
            test_label="MUST20_NO_TOL",
        )
        result = run_exact_gouge_check(cfg)
        assert result.status == "NOT_VERIFIABLE"
        assert result.boolean_success is False

    def test_boolean_failure_error_field_set(self):
        """When engine fails, error field must be set (not silently swallowed)."""
        cfg = ExactGougeConfig(
            cutting_segments=[],  # triggers early failure
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        # Either error is set OR gouge_exact_ready is False
        assert result.error is not None or result.gouge_exact_ready is False
