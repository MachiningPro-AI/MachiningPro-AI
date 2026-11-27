"""
Exact Gouge / Overcut Verification Tests — BREP_BOOLEAN_OCC

Phase 9: Deterministic test geometry cases.
Phase 2: Engine selection verification.
Phase 10: Boolean integrity checks.
Phase Y: Separation from conservative check.

TEST_ONLY geometry — not production tolerances.
"""


from backend.verification.checks import check_part_gouge_exact
from backend.verification.enums import VerificationStatus
from backend.verification.exact_gouge import ExactGougeConfig, run_exact_gouge_check
from backend.verification.models import VerificationSegment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _drill_segment(
    cx: float, cy: float,
    z_start: float, z_end: float,
) -> tuple[float, float, float, float, float, float]:
    """Vertical drill segment from z_start to z_end."""
    return (cx, cy, z_start, cx, cy, z_end)


def _stock_config_20x20x10() -> dict:
    return dict(
        stock_x_mm=0.0, stock_y_mm=0.0, stock_z_mm=0.0,
        stock_w_mm=20.0, stock_h_mm=20.0, stock_d_mm=10.0,
    )


# ---------------------------------------------------------------------------
# Phase 2 — Engine availability
# ---------------------------------------------------------------------------


class TestEngineAvailability:
    def test_gmsh_import_succeeds(self):
        """gmsh must be importable (project dependency)."""
        import gmsh
        assert gmsh is not None

    def test_exact_gouge_module_importable(self):
        from backend.verification.exact_gouge import run_exact_gouge_check
        assert callable(run_exact_gouge_check)

    def test_config_dataclass_instantiates(self):
        cfg = ExactGougeConfig(tool_radius_mm=5.0, test_only=True)
        assert cfg.tool_radius_mm == 5.0

    def test_enums_include_brep_boolean_occ(self):
        from backend.verification.enums import ExactGougeMethod
        assert ExactGougeMethod.BREP_BOOLEAN_OCC == "BREP_BOOLEAN_OCC"

    def test_enums_include_target_geometry_fidelity(self):
        from backend.verification.enums import TargetGeometryFidelity
        assert TargetGeometryFidelity.BREP_EXACT == "BREP_EXACT"


# ---------------------------------------------------------------------------
# Phase 9A — KNOWN_NO_GOUGE
# Stock: 20×20×10 box. Tool: Ø8 drill (radius=4). Path: vertical through center.
# Target: not provided → partial check only.
# With test_only=True + no gouge expected → PASS (no over-cut).
# ---------------------------------------------------------------------------


class TestKnownNoGouge:
    def _config(self) -> ExactGougeConfig:
        return ExactGougeConfig(
            **_stock_config_20x20x10(),
            tool_radius_mm=4.0,
            cutting_segments=[
                _drill_segment(10.0, 10.0, 10.5, -0.5)  # through stock
            ],
            tolerance_mm=0.1,
            tolerance_source="TEST_ONLY",
            test_only=True,
            test_label="KNOWN_NO_GOUGE",
        )

    def test_no_gouge_boolean_succeeds(self):
        result = run_exact_gouge_check(self._config())
        assert result.boolean_success, f"Boolean failed: {result.error}"

    def test_no_gouge_no_error(self):
        result = run_exact_gouge_check(self._config())
        assert result.error is None

    def test_no_gouge_gouge_volume_zero(self):
        result = run_exact_gouge_check(self._config())
        # Without STEP target we can't compute gouge — PARTIAL
        # gouge_volume should be 0.0 (not computed without target)
        assert result.gouge_volume_mm3 == 0.0

    def test_no_gouge_timing_recorded(self):
        result = run_exact_gouge_check(self._config())
        assert result.total_exact_verification_ms > 0.0

    def test_no_gouge_method_reported(self):
        result = run_exact_gouge_check(self._config())
        assert result.method == "BREP_BOOLEAN_OCC"


# ---------------------------------------------------------------------------
# Phase 9B — KNOWN_GOUGE (programmatic: target is a STEP box with 8mm hole,
# but we drill with 10mm → 1mm annular gouge)
# We test via check_part_gouge_exact using test geometry constructed at runtime
# ---------------------------------------------------------------------------


class TestKnownGougeViaChecks:
    """Test exact gouge check with oversized tool (gouge case)."""

    def _make_target_step(self, tmp_path, hole_radius: float = 4.0) -> str:
        """Create a STEP file: 20×20×10 box with a hole_radius drill hole."""
        import gmsh
        step_path = str(tmp_path / "target.step")
        with __import__('threading').Lock():
            try:
                gmsh.initialize()
                gmsh.option.setNumber("General.Verbosity", 0)
                gmsh.model.add("target_step")
                box = gmsh.model.occ.addBox(0, 0, 0, 20, 20, 10)
                cyl = gmsh.model.occ.addCylinder(10, 10, -0.5, 0, 0, 11, hole_radius)
                gmsh.model.occ.cut([(3, box)], [(3, cyl)])
                gmsh.model.occ.synchronize()
                gmsh.write(step_path)
            finally:
                gmsh.finalize()
        return step_path

    def test_gouge_detected_with_oversized_tool(self, tmp_path):
        """8mm hole target, 10mm drill → gouge of annular ring."""
        target = self._make_target_step(tmp_path, hole_radius=4.0)  # 8mm hole
        cfg = ExactGougeConfig(
            target_step_path=target,
            **_stock_config_20x20x10(),
            tool_radius_mm=5.0,  # 10mm drill — 1mm oversized
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            tolerance_mm=0.05,
            tolerance_source="TEST_ONLY",
            test_only=True,
            test_label="KNOWN_GOUGE",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success, f"Boolean failed: {result.error}"
        # Gouge should be detected (annular ring was removed)
        assert result.status == "FAIL", (
            f"Expected FAIL (gouge detected), got {result.status}. "
            f"gouge_volume={result.gouge_volume_mm3:.3f}"
        )
        # Gouge volume should be non-zero
        assert result.gouge_volume_mm3 > 0.0, (
            f"Expected non-zero gouge volume, got {result.gouge_volume_mm3}"
        )

    def test_no_gouge_exact_match(self, tmp_path):
        """8mm hole target, 8mm drill → no gouge."""
        target = self._make_target_step(tmp_path, hole_radius=4.0)
        cfg = ExactGougeConfig(
            target_step_path=target,
            **_stock_config_20x20x10(),
            tool_radius_mm=4.0,  # exact match
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            tolerance_mm=0.05,
            tolerance_source="TEST_ONLY",
            test_only=True,
            test_label="KNOWN_NO_GOUGE_EXACT",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success, f"Boolean failed: {result.error}"
        assert result.status == "PASS", (
            f"Expected PASS (exact match), got {result.status}. "
            f"gouge_volume={result.gouge_volume_mm3:.3f}"
        )

    def test_remaining_material_detected(self, tmp_path):
        """8mm hole target, 6mm drill → remaining material (undercut)."""
        target = self._make_target_step(tmp_path, hole_radius=4.0)
        cfg = ExactGougeConfig(
            target_step_path=target,
            **_stock_config_20x20x10(),
            tool_radius_mm=3.0,  # 6mm drill — 2mm undersize
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            tolerance_mm=0.05,
            tolerance_source="TEST_ONLY",
            test_only=True,
            test_label="KNOWN_REMAINING_MATERIAL",
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success, f"Boolean failed: {result.error}"
        assert result.status == "PARTIAL", (
            f"Expected PARTIAL (remaining material), got {result.status}. "
            f"remaining={result.remaining_material_volume_mm3:.3f}"
        )
        assert result.remaining_material_volume_mm3 > 0.0


# ---------------------------------------------------------------------------
# Phase 10 — Boolean integrity
# ---------------------------------------------------------------------------


class TestBooleanIntegrity:
    def test_no_cutting_segments_returns_not_verifiable(self):
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[],
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        assert result.status == "NOT_VERIFIABLE"
        assert result.gouge_exact_ready is False

    def test_missing_tolerance_non_test_returns_not_verifiable(self):
        """Without tolerance and test_only=False → NOT_VERIFIABLE."""
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            tolerance_mm=None,
            test_only=False,
        )
        result = run_exact_gouge_check(cfg)
        assert result.status == "NOT_VERIFIABLE"

    def test_degenerate_segment_skipped(self):
        """Zero-length cutting segment should not crash engine."""
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[
                (10.0, 10.0, 5.0, 10.0, 10.0, 5.0),  # degenerate
                _drill_segment(10.0, 10.0, 10.5, -0.5),  # valid
            ],
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        # Should not crash; boolean should succeed with the valid segment
        assert result.boolean_success or result.status == "NOT_VERIFIABLE"

    def test_boolean_success_field_set(self):
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        assert result.boolean_success is True

    def test_timing_all_fields_present(self):
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        assert result.target_prep_ms >= 0.0
        assert result.machined_result_ms >= 0.0
        assert result.boolean_ms >= 0.0
        assert result.total_exact_verification_ms > 0.0

    def test_nonexistent_step_file_uses_partial(self):
        """Non-existent STEP → no target → PARTIAL (partial check only)."""
        cfg = ExactGougeConfig(
            target_step_path="/nonexistent/file.step",
            **_stock_config_20x20x10(),
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        # No target → PARTIAL check (stock removal verified, not gouge)
        assert result.status in ("PARTIAL", "NOT_VERIFIABLE")


# ---------------------------------------------------------------------------
# Phase Y — Exact vs conservative separation
# ---------------------------------------------------------------------------


class TestExactConservativeSeparation:
    def test_exact_check_has_brep_method(self):
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            test_only=True,
        )
        result = run_exact_gouge_check(cfg)
        assert result.method == "BREP_BOOLEAN_OCC"

    def test_check_part_gouge_exact_uses_engine(self):
        """check_part_gouge_exact now returns engine result, not hardcoded NOT_VERIFIABLE."""
        segs = [
            VerificationSegment(
                start_x=10.0, start_y=10.0, start_z=10.5,
                end_x=10.0, end_y=10.0, end_z=-0.5,
                motion_type="LINEAR", is_cutting=True,
            )
        ]
        vr = check_part_gouge_exact(
            segments=segs,
            part_bbox_min=(0.0, 0.0, 0.0),
            part_bbox_max=(20.0, 20.0, 10.0),
            tool_diameter_mm=8.0,
            test_only=True,
            test_label="SEPARATION_TEST",
        )
        # Should NOT be hardcoded NOT_VERIFIABLE anymore — engine ran
        assert vr.check_type.value == "GOUGE_EXACT"
        assert vr.evidence.get("method") == "BREP_BOOLEAN_OCC"

    def test_check_part_gouge_exact_no_segs_returns_not_verifiable(self):
        """No cutting segments → NOT_VERIFIABLE."""
        vr = check_part_gouge_exact(
            segments=[],
            part_bbox_min=(0.0, 0.0, 0.0),
            part_bbox_max=(20.0, 20.0, 10.0),
            tool_diameter_mm=8.0,
        )
        assert vr.status == VerificationStatus.NOT_VERIFIABLE
        assert vr.evidence.get("gouge_exact_ready") is False

    def test_exact_and_conservative_have_different_check_types(self):
        from backend.verification.checks import check_part_gouge

        segs = [
            VerificationSegment(
                start_x=10, start_y=10, start_z=10.5,
                end_x=10, end_y=10, end_z=-0.5,
                motion_type="LINEAR", is_cutting=True,
            )
        ]
        conservative = check_part_gouge(segs, (0.0, 0.0, 0.0), (20.0, 20.0, 10.0), 8.0)
        exact_vr = check_part_gouge_exact(segs, (0, 0, 0), (20, 20, 10), 8.0, test_only=True)

        assert conservative.check_type.value == "PART_GOUGE"
        assert exact_vr.check_type.value == "GOUGE_EXACT"


# ---------------------------------------------------------------------------
# Phase 13 — Performance (non-strict, just ensure reasonable bounds)
# ---------------------------------------------------------------------------


class TestPerformance:
    def test_simple_drill_under_30_seconds(self):
        """Simple drill scenario must complete in under 30 seconds."""
        import time
        cfg = ExactGougeConfig(
            **_stock_config_20x20x10(),
            cutting_segments=[_drill_segment(10.0, 10.0, 10.5, -0.5)],
            test_only=True,
        )
        t0 = time.perf_counter()
        result = run_exact_gouge_check(cfg)
        elapsed = time.perf_counter() - t0
        assert elapsed < 30.0, f"Took {elapsed:.1f}s — too slow"
        # Total field should match
        assert abs(result.total_exact_verification_ms - elapsed * 1000.0) < 2000.0
