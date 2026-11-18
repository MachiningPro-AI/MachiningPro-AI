"""
Tests for Phase 7D-7H: End-to-end CAM assessment with WCS + contour + toolpath.

Covers:
  - Phase 7B: tool catalog audit (no new records for 2.5/6.6/7.0/9.0mm)
  - Phase 7D: pocket E2E readiness matrix
  - Phase 7E: slot E2E readiness matrix
  - Phase 7G: drill E2E readiness matrix
  - Phase 7H: real STEP file aggregate metrics
  - Safety invariants: is_dispatchable=False, production_released=False
  - Negative: missing WCS, no tool, non-horizontal slot, unknown depth
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.step_brep.phase7_cam_e2e import (
    PHASE7_IS_DISPATCHABLE,
    PHASE7_PRODUCTION_RELEASED,
    PHASE7_REVIEW_REQUIRED,
    PHASE7B_TOOL_MATCH_AFTER,
    PHASE7B_TOOL_MATCH_BEFORE,
    PHASE7B_UNMATCHED_DIAMETERS,
    Phase7B_ToolCatalogAudit,
    ReadinessStatus,
    run_phase7_e2e,
)
from backend.step_brep.phase7_wcs_provider import WCSProvenance

# ---------------------------------------------------------------------------
# Real STEP file path resolution
# ---------------------------------------------------------------------------

_REAL_CAD_ROOT = Path(r"D:\makina_ogrenmesi\olcum_denemeleri")
_EE_STEP = _REAL_CAD_ROOT / "electronics-enclosure.step"
_LB_STEP = _REAL_CAD_ROOT / "l-bracket.step"
_FB_STEP = _REAL_CAD_ROOT / "flanged-bushing (1).step"
_FP_STEP = _REAL_CAD_ROOT / "flange-plate.step"
_PM_STEP = _REAL_CAD_ROOT / "Pump Manifold v3.step"
_SK_STEP = _REAL_CAD_ROOT / "stepped-shaft-keyway.step"

_REAL_STEP_FILES = [_EE_STEP, _LB_STEP, _FB_STEP, _FP_STEP, _PM_STEP, _SK_STEP]
_HAS_REAL_STEP = all(f.exists() for f in _REAL_STEP_FILES)
_skip_no_real = pytest.mark.skipif(not _HAS_REAL_STEP, reason="Real STEP files not present")


def _load_ee_with_topo():
    """Load electronics-enclosure.step with canonical topology. Requires gmsh."""
    import gmsh

    from backend.step_brep.gmsh_step_parser import parse_step_file
    from backend.step_brep.topology_adapter import build_canonical_topology
    path = str(_EE_STEP)
    rec = parse_step_file(path, sample_origin="REAL_EXTERNAL_STEP")
    gmsh.initialize()
    try:
        gmsh.model.occ.importShapes(path)
        gmsh.model.occ.synchronize()
        topo = build_canonical_topology(topology_id="ee-test")
    finally:
        gmsh.finalize()
    return rec, topo


def _load_step_with_topo(step_path: str):
    import gmsh

    from backend.step_brep.gmsh_step_parser import parse_step_file
    from backend.step_brep.topology_adapter import build_canonical_topology
    rec = parse_step_file(step_path, sample_origin="REAL_EXTERNAL_STEP")
    gmsh.initialize()
    try:
        gmsh.model.occ.importShapes(step_path)
        gmsh.model.occ.synchronize()
        topo = build_canonical_topology(topology_id=step_path[-20:])
    finally:
        gmsh.finalize()
    return rec, topo


# ---------------------------------------------------------------------------
# Safety invariants
# ---------------------------------------------------------------------------

class TestPhase7SafetyInvariants:
    def test_is_dispatchable_always_false(self):
        assert PHASE7_IS_DISPATCHABLE is False

    def test_production_released_always_false(self):
        assert PHASE7_PRODUCTION_RELEASED is False

    def test_review_required_always_true(self):
        assert PHASE7_REVIEW_REQUIRED is True


# ---------------------------------------------------------------------------
# Phase 7B: Tool catalog audit
# ---------------------------------------------------------------------------

class TestPhase7BToolCatalogAudit:
    def test_unmatched_diameters_tuple(self):
        assert 2.5 in PHASE7B_UNMATCHED_DIAMETERS
        assert 6.6 in PHASE7B_UNMATCHED_DIAMETERS
        assert 7.0 in PHASE7B_UNMATCHED_DIAMETERS
        assert 9.0 in PHASE7B_UNMATCHED_DIAMETERS

    def test_tool_match_before_is_zero(self):
        assert PHASE7B_TOOL_MATCH_BEFORE == 0

    def test_tool_match_after_is_zero(self):
        assert PHASE7B_TOOL_MATCH_AFTER == 0

    def test_no_fabricated_records(self):
        # No new records should be added without source-backed evidence
        assert PHASE7B_TOOL_MATCH_AFTER == PHASE7B_TOOL_MATCH_BEFORE

    @_skip_no_real
    def test_audit_in_e2e_result(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        audit = result.tool_catalog_audit
        assert isinstance(audit, Phase7B_ToolCatalogAudit)
        assert audit.source_backed_added == 0


# ---------------------------------------------------------------------------
# Phase 7 E2E — without topology (no contour extraction)
# ---------------------------------------------------------------------------

class TestPhase7E2EWithoutTopology:
    @_skip_no_real
    def test_wcs_always_suggested(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        assert result.wcs is not None
        assert result.wcs.provenance == WCSProvenance.SUGGESTED

    @_skip_no_real
    def test_wcs_is_valid(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        assert result.wcs_ready is True

    @_skip_no_real
    def test_no_toolpaths_without_topology(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        assert result.total_toolpath_count == 0

    @_skip_no_real
    def test_is_dispatchable_false_always(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        assert result.is_dispatchable is False

    @_skip_no_real
    def test_production_released_false_always(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        assert result.production_released is False


# ---------------------------------------------------------------------------
# Phase 7 E2E — electronics-enclosure WITH topology
# ---------------------------------------------------------------------------

@_skip_no_real
class TestPhase7EEWithTopology:
    @pytest.fixture(scope="class")
    def ee_result(self):
        rec, topo = _load_ee_with_topo()
        return run_phase7_e2e(rec, topo)

    def test_wcs_valid_and_suggested(self, ee_result):
        assert ee_result.wcs_ready is True
        assert ee_result.wcs.provenance == WCSProvenance.SUGGESTED

    def test_at_least_one_pocket_toolpath(self, ee_result):
        assert ee_result.pocket_toolpath_count >= 1

    def test_total_toolpath_count_positive(self, ee_result):
        assert ee_result.total_toolpath_count > 0

    def test_any_toolpath_generated_true(self, ee_result):
        assert ee_result.any_toolpath_generated is True

    def test_is_dispatchable_false(self, ee_result):
        assert ee_result.is_dispatchable is False

    def test_production_released_false(self, ee_result):
        assert ee_result.production_released is False

    def test_review_required_true(self, ee_result):
        assert ee_result.review_required is True

    def test_first_pocket_has_toolpath(self, ee_result):
        pocket = ee_result.pocket_results[0]
        assert pocket.toolpath_ready == ReadinessStatus.YES
        assert pocket.toolpath is not None

    def test_toolpath_status_is_verification_required(self, ee_result):
        pocket = next(
            p for p in ee_result.pocket_results if p.toolpath_ready == ReadinessStatus.YES
        )
        from backend.toolpath.models import ToolpathStatus
        assert pocket.toolpath.status == ToolpathStatus.VERIFICATION_REQUIRED

    def test_toolpath_has_segments(self, ee_result):
        pocket = next(
            p for p in ee_result.pocket_results if p.toolpath_ready == ReadinessStatus.YES
        )
        assert len(pocket.toolpath.segments) > 0

    def test_wcs_ref_contains_suggested(self, ee_result):
        pocket = next(
            p for p in ee_result.pocket_results if p.toolpath_ready == ReadinessStatus.YES
        )
        assert "SUGGESTED" in pocket.toolpath.wcs_ref

    def test_tool_ref_is_catalog_id(self, ee_result):
        pocket = next(
            p for p in ee_result.pocket_results if p.toolpath_ready == ReadinessStatus.YES
        )
        assert pocket.toolpath.tool_ref is not None
        assert len(pocket.toolpath.tool_ref) > 0

    def test_pocket_feature_confirmed_no(self, ee_result):
        # CANDIDATE features remain CANDIDATE — never auto-confirmed
        for pocket in ee_result.pocket_results:
            assert pocket.feature_confirmed == ReadinessStatus.NO

    def test_pocket_is_dispatchable_false(self, ee_result):
        for pocket in ee_result.pocket_results:
            assert pocket.is_dispatchable is False

    def test_pocket_review_required_true(self, ee_result):
        for pocket in ee_result.pocket_results:
            assert pocket.review_required is True

    def test_small_pockets_blocked_no_tool(self, ee_result):
        # 7×7mm pockets have no matching tool (7mm not in catalog below 7% threshold)
        small_blocked = [
            p for p in ee_result.pocket_results
            if p.toolpath_ready == ReadinessStatus.NO and p.tool_ready == ReadinessStatus.NO
        ]
        assert len(small_blocked) >= 1

    def test_step_results_all_blocked(self, ee_result):
        for step in ee_result.step_results:
            assert step.toolpath_ready == ReadinessStatus.NO
            assert "deferred" in (step.blocker or "").lower() or \
                   "BOUNDARY_READY=NO" in (step.blocker or "")


# ---------------------------------------------------------------------------
# Phase 7H: aggregate across all 6 real STEP files
# ---------------------------------------------------------------------------

@_skip_no_real
class TestPhase7HRealSTEPAggregates:
    @pytest.fixture(scope="class")
    def all_results(self):
        results = []
        for fp in _REAL_STEP_FILES:
            rec, topo = _load_step_with_topo(str(fp))
            results.append(run_phase7_e2e(rec, topo))
        return results

    def test_wcs_ready_all_6_files(self, all_results):
        wcs_count = sum(1 for r in all_results if r.wcs_ready)
        assert wcs_count == 6

    def test_toolpath_ready_at_least_1_file(self, all_results):
        tp_count = sum(1 for r in all_results if r.any_toolpath_generated)
        assert tp_count >= 1

    def test_no_result_is_dispatchable(self, all_results):
        assert all(r.is_dispatchable is False for r in all_results)

    def test_no_result_is_production_released(self, all_results):
        assert all(r.production_released is False for r in all_results)

    def test_all_results_review_required(self, all_results):
        assert all(r.review_required is True for r in all_results)

    def test_all_wcs_provenance_is_suggested(self, all_results):
        for r in all_results:
            assert r.wcs.provenance == WCSProvenance.SUGGESTED

    def test_all_wcs_never_user_confirmed(self, all_results):
        for r in all_results:
            assert r.wcs.provenance != WCSProvenance.USER_CONFIRMED


# ---------------------------------------------------------------------------
# Negative tests: blocked conditions
# ---------------------------------------------------------------------------

@_skip_no_real
class TestPhase7NegativeCases:
    def test_no_topology_means_no_toolpath(self):
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, topo=None)
        assert result.total_toolpath_count == 0

    def test_shaft_slot_non_horizontal_blocked(self):
        """Stepped-shaft-keyway has a Z-axis keyway with non-horizontal floor → blocked."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_SK_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        # With no topology all slots are blocked; shaft slot is Z-axis (non-horizontal)
        for slot in result.slot_results:
            assert slot.toolpath_ready == ReadinessStatus.NO

    def test_flange_plate_holes_no_matching_drill(self):
        """flange-plate.step has 9mm holes — no matching drill in catalog."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_FP_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        for drill in result.drill_results:
            assert drill.toolpath_ready == ReadinessStatus.NO
            assert drill.tool_ready == ReadinessStatus.NO

    def test_pump_manifold_pockets_no_tool_or_no_contour(self):
        """Pump Manifold has no matching tools for available pockets."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_PM_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        # Without topology, boundary is not ready
        for pocket in result.pocket_results:
            assert pocket.toolpath_ready == ReadinessStatus.NO

    def test_feature_confirmed_always_no(self):
        """Feature status must remain CANDIDATE (never auto-confirmed)."""
        from backend.step_brep.gmsh_step_parser import parse_step_file
        rec = parse_step_file(str(_EE_STEP), sample_origin="REAL_EXTERNAL_STEP")
        result = run_phase7_e2e(rec, None)
        for pocket in result.pocket_results:
            assert pocket.feature_confirmed == ReadinessStatus.NO
        for slot in result.slot_results:
            assert slot.feature_confirmed == ReadinessStatus.NO
        for drill in result.drill_results:
            assert drill.feature_confirmed == ReadinessStatus.NO
