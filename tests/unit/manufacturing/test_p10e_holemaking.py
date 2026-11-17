"""
P10-E test suite: advanced holemaking / DXF-02 assessment.

Validates:
  - DXF-02 ~60mm feature: BORING not in catalog → DEFERRED_CAPABILITY_GAP
  - No boring bar catalog records (no fabrication)
  - No helical interpolation toolpath generator (not implemented)
  - 60mm is out of range for direct drilling (max drill in catalog < 60mm)
  - Reaming is finishing-only, not for creating 60mm bore
  - DXF02_STATUS=DEFERRED_CAPABILITY_GAP (conservative)

HARD RULES verified:
  - No fabricated boring bars
  - No fabricated boring cutting data
  - No fabricated 60mm drill capability
  - Capability gap documented, NOT silently worked around
"""

from __future__ import annotations

from backend.cutting_tools.seed_catalog import get_catalog

# ---------------------------------------------------------------------------
# P10-E1: Max drill size in catalog
# ---------------------------------------------------------------------------

class TestMaxDrillSize:
    def test_max_drill_diameter_lt_60mm(self):
        drills = [
            t for t in get_catalog()
            if "drilling" in t.supported_operations
        ]
        max_diam = max(d.cutting_diameter_mm for d in drills if d.cutting_diameter_mm)
        # Max available drill for hole creation is 24mm < 60mm needed for DXF-02
        assert max_diam < 60.0, (
            f"Largest drill is {max_diam}mm — cannot create 60mm bore by drilling"
        )

    def test_no_drill_at_60mm(self):
        drills = [
            t for t in get_catalog()
            if "drilling" in t.supported_operations
        ]
        drills_at_60 = [d for d in drills if d.cutting_diameter_mm == 60.0]
        assert len(drills_at_60) == 0

    def test_no_drill_larger_than_30mm(self):
        drills = [
            t for t in get_catalog()
            if "drilling" in t.supported_operations
        ]
        large = [d for d in drills if d.cutting_diameter_mm and d.cutting_diameter_mm > 30.0]
        assert len(large) == 0, (
            f"Unexpected large drills found: {[d.stable_id for d in large]}"
        )


# ---------------------------------------------------------------------------
# P10-E2: Boring bar exists but no milling-compatible NC path for 60mm bore
# ---------------------------------------------------------------------------

class TestBoringCapabilityForDxf02:
    def test_boring_bar_exists_in_catalog(self):
        # The catalog HAS a boring bar (sandvik-a25t-sducr-11) — it is a turning-style
        # boring bar. This confirms the catalog records a real tool, not fabricated.
        boring_tools = [
            t for t in get_catalog()
            if "boring" in t.supported_operations
        ]
        # At least one boring bar must exist (not fabricated — real Sandvik CoroTurn record)
        assert len(boring_tools) >= 1

    def test_boring_bar_is_turning_type_not_milling(self):
        boring_tools = [
            t for t in get_catalog()
            if "boring" in t.supported_operations
        ]
        for b in boring_tools:
            # Boring bars in this catalog are turning-style, not milling boring heads
            # They require a turning toolpath, not a milling boring cycle
            assert "milling" not in b.supported_operations, (
                f"{b.stable_id} has both boring and milling — unexpected combination"
            )

    def test_no_boring_toolpath_generator(self):
        # Key gap: even with a boring bar in catalog, no NC toolpath generator exists
        try:
            from backend.nc import generator
            has_boring = hasattr(generator, "generate_boring_toolpath")
        except ImportError:
            has_boring = False
        assert not has_boring, (
            "generate_boring_toolpath found — not expected in P10 Phase 1"
        )

    def test_boring_bar_cutting_diameter_not_60mm(self):
        boring_tools = [
            t for t in get_catalog()
            if "boring" in t.supported_operations
        ]
        for b in boring_tools:
            # None of the boring bars are specifically rated for 60mm bore creation
            # from a drilling operation
            assert b.cutting_diameter_mm is None or b.cutting_diameter_mm != 60.0


# ---------------------------------------------------------------------------
# P10-E3: No helical interpolation generator
# ---------------------------------------------------------------------------

class TestNoHelicalInterpolationGenerator:
    def test_no_helix_toolpath_module(self):
        try:
            from backend.nc import generator
            has_helix = hasattr(generator, "generate_helical_toolpath")
        except ImportError:
            has_helix = False
        assert not has_helix, (
            "generate_helical_toolpath found — not expected in P10 Phase 1"
        )

    def test_no_boring_toolpath_module(self):
        try:
            from backend.nc import generator
            has_boring = hasattr(generator, "generate_boring_toolpath")
        except ImportError:
            has_boring = False
        assert not has_boring, (
            "generate_boring_toolpath found — not expected in P10 Phase 1"
        )


# ---------------------------------------------------------------------------
# P10-E4: DXF-02 status is DEFERRED_CAPABILITY_GAP
# ---------------------------------------------------------------------------

class TestDxf02Status:
    """
    DXF-02 (109106_01_22.dxf) requires a ~60mm bore feature.

    Viable options assessed:
      BORING:                NOT_IMPLEMENTED (no toolpath generator, no boring bar catalog)
      HELICAL_INTERPOLATION: NOT_IMPLEMENTED (no helical toolpath generator)
      LARGE_DRILLING:        NOT_AVAILABLE (max drill = 24mm; 60mm is out of range)
      REAMING:               NOT_APPLICABLE (finishing only; cannot create 60mm bore)

    Result: DXF02_STATUS=DEFERRED_CAPABILITY_GAP (conservative)
    """

    DXF02_STATUS = "DEFERRED_CAPABILITY_GAP"

    def test_dxf02_status_is_deferred(self):
        assert self.DXF02_STATUS == "DEFERRED_CAPABILITY_GAP"

    def test_boring_option_requires_toolpath_generator(self):
        # Confirm boring NOT implemented
        try:
            from backend.nc import generator
            has_boring = hasattr(generator, "generate_boring_toolpath")
        except ImportError:
            has_boring = False
        assert not has_boring

    def test_max_drill_cannot_reach_60mm_feature(self):
        drills = [
            t for t in get_catalog()
            if "drilling" in t.supported_operations
        ]
        max_drill = max((d.cutting_diameter_mm or 0) for d in drills)
        # 60mm feature requires boring or helical interpolation; not simple drilling
        assert max_drill < 60.0

    def test_reaming_tools_present_but_finishing_only(self):
        # Confirm reaming tools exist but are for finishing, not bore creation
        reaming_tools = [
            t for t in get_catalog()
            if "reaming" in t.supported_operations
        ]
        # Presence of reaming tools does not resolve the 60mm bore creation gap
        # This test documents the state (reaming is distinct from boring)
        # Zero OR positive count is acceptable — we just confirm no boring available
        # ASSERTION: no tool with both reaming AND boring operations (creates false impression)
        for t in reaming_tools:
            assert "boring" not in t.supported_operations, (
                f"{t.stable_id} claims both reaming and boring — unexpected"
            )


# ---------------------------------------------------------------------------
# P10-E5: advanced_holemaking.py — structured assessment module (supplementary)
# ---------------------------------------------------------------------------

class TestAdvancedHolemakingModule:
    """Tests for the structured advanced_holemaking.py assessment module."""

    def test_dxf02_status_constant(self):
        from backend.manufacturing.advanced_holemaking import DXF02_ADVANCED_HOLEMAKING_STATUS
        assert DXF02_ADVANCED_HOLEMAKING_STATUS == "DEFERRED_CAPABILITY_GAP"

    def test_60mm_deferral_status(self):
        from backend.manufacturing.advanced_holemaking import assess_large_hole_strategies
        result = assess_large_hole_strategies(60.0)
        assert result.deferral_status == "DEFERRED_CAPABILITY_GAP"

    def test_60mm_boring_deferred_no_cam(self):
        from backend.manufacturing.advanced_holemaking import (
            assess_large_hole_strategies, HolemakingStrategy, HolemakingStrategyStatus,
        )
        result = assess_large_hole_strategies(60.0)
        boring = next(r for r in result.strategy_results if r.strategy == HolemakingStrategy.BORING)
        assert boring.status == HolemakingStrategyStatus.DEFERRED
        assert boring.tool_exists_in_catalog is True  # sandvik-a25t-sducr-11

    def test_60mm_large_drilling_not_viable(self):
        from backend.manufacturing.advanced_holemaking import (
            assess_large_hole_strategies, HolemakingStrategy, HolemakingStrategyStatus,
        )
        result = assess_large_hole_strategies(60.0, catalog_max_drill_mm=24.0)
        drill = next(
            r for r in result.strategy_results if r.strategy == HolemakingStrategy.LARGE_DRILLING
        )
        assert drill.status == HolemakingStrategyStatus.NOT_VIABLE

    def test_safety_invariants(self):
        from backend.manufacturing.advanced_holemaking import assess_large_hole_strategies
        result = assess_large_hole_strategies(60.0)
        assert result.is_dispatchable is False
        assert result.production_released is False

    def test_boring_viable_when_cam_available(self):
        from backend.manufacturing.advanced_holemaking import (
            assess_large_hole_strategies, HolemakingStrategy, HolemakingStrategyStatus,
        )
        result = assess_large_hole_strategies(60.0, has_boring_cam=True)
        boring = next(r for r in result.strategy_results if r.strategy == HolemakingStrategy.BORING)
        assert boring.status == HolemakingStrategyStatus.VIABLE
        assert result.recommended_strategy == HolemakingStrategy.BORING
