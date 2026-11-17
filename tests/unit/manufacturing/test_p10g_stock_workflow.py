"""
P10-G test suite: stock/simulation production workflow wiring.

Validates:
  - StockDefinition wired → voxel simulation runs → STOCK_REMOVAL_VALIDATED exits NOT_VERIFIABLE
  - StockDefinition absent → STOCK_REMOVAL_VALIDATED=NOT_VERIFIABLE
  - Incomplete StockDefinition → STOCK_REMOVAL_VALIDATED=NOT_VERIFIABLE
  - SIMULATION_METHOD=VOXEL_APPROXIMATION preserved (never EXACT_BOOLEAN)
  - GOUGE_VALIDATED=NOT_VERIFIABLE without STEP part_bbox (always from DXF)
  - SIMULATION_RAN flag correctly set
  - Separate result fields: SIMULATION_RAN, STOCK_REMOVAL_VALIDATED, GOUGE_VALIDATED

HARD RULES verified:
  - SIMULATION_METHOD never claimed as EXACT_BOOLEAN
  - Stock absent → NOT_VERIFIABLE (not PASS)
  - GOUGE NOT_VERIFIABLE from DXF flow
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.manufacturing.setup_stock import StockDefinition, StockShape
from backend.manufacturing.workflow_orchestrator import (
    SIMULATION_METHOD,
    WorkflowVerificationRequest,
    run_production_verification,
)

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------

def _seg(sx, sy, sz, ex, ey, ez, motion="RAPID_LINEAR", is_cutting=False):
    return {
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "motion_type": motion, "is_cutting": is_cutting, "segment_id": "s1",
    }


def _candidate(segs=None, tool_diam=5.0, feature_id="feat-g1"):
    if segs is None:
        segs = [
            _seg(0, 0, 10, 0, 0, 1, "RAPID_LINEAR"),
            _seg(0, 0, 1, 0, 0, -15, "FEED_LINEAR", True),
            _seg(0, 0, -15, 0, 0, 10, "RAPID_LINEAR"),
        ]
    return SimpleNamespace(
        nc_segments=segs,
        tool_diameter_mm=tool_diam,
        feature_id=feature_id,
        toolpath_id="tp-g1",
    )


def _rect_stock(length=100.0, width=100.0, height=50.0, material="1.4301"):
    return StockDefinition(
        stock_id="test-stock",
        shape=StockShape.RECTANGULAR_BLOCK,
        material_grade=material,
        length_mm=length,
        width_mm=width,
        height_mm=height,
    )


def _round_stock(outer_diam=80.0, length=100.0, material="6082-T6"):
    return StockDefinition(
        stock_id="test-round-stock",
        shape=StockShape.ROUND_BAR,
        material_grade=material,
        outer_diameter_mm=outer_diam,
        length_mm=length,
    )


# ---------------------------------------------------------------------------
# P10-G1: No stock → NOT_VERIFIABLE
# ---------------------------------------------------------------------------

class TestNoStock:
    def test_no_stock_def_stock_removal_not_verifiable(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.stock_removal_validated == "NOT_VERIFIABLE"

    def test_no_stock_def_stock_def_supplied_false(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.stock_def_supplied is False

    def test_no_stock_simulation_method_still_set(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.simulation_method == "VOXEL_APPROXIMATION"


# ---------------------------------------------------------------------------
# P10-G2: Stock def present → simulation runs
# ---------------------------------------------------------------------------

class TestStockDefPresent:
    def test_rect_stock_stock_def_supplied_true(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.stock_def_supplied is True

    def test_rect_stock_exits_not_verifiable(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        # Stock present and tool path (z=0 to z=-15) is within stock (height=50)
        # STOCK_REMOVAL should not be NOT_VERIFIABLE
        assert result.stock_removal_validated != "NOT_VERIFIABLE"

    def test_round_stock_wired(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_round_stock(),
        )
        result = run_production_verification(req)
        assert result.stock_def_supplied is True
        assert result.stock_removal_validated != "NOT_VERIFIABLE"

    def test_simulation_method_always_voxel_approximation(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.simulation_method == SIMULATION_METHOD
        assert result.simulation_method == "VOXEL_APPROXIMATION"
        assert "EXACT" not in result.simulation_method

    def test_simulation_ran_true_when_stock_and_segments(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.simulation_ran is True


# ---------------------------------------------------------------------------
# P10-G3: Incomplete stock def → NOT_VERIFIABLE
# ---------------------------------------------------------------------------

class TestIncompleteStockDef:
    def test_missing_height_not_verifiable(self):
        stock = StockDefinition(
            stock_id="incomplete-stock",
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="1.4301",
            length_mm=100.0,
            width_mm=100.0,
            height_mm=None,
        )
        req = WorkflowVerificationRequest(candidate=_candidate(), stock_def=stock)
        result = run_production_verification(req)
        assert result.stock_removal_validated == "NOT_VERIFIABLE"

    def test_missing_material_grade_not_verifiable(self):
        stock = StockDefinition(
            stock_id="no-material-stock",
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="",  # empty → validate_stock_dimensions returns missing
            length_mm=100.0,
            width_mm=100.0,
            height_mm=50.0,
        )
        req = WorkflowVerificationRequest(candidate=_candidate(), stock_def=stock)
        result = run_production_verification(req)
        assert result.stock_removal_validated == "NOT_VERIFIABLE"


# ---------------------------------------------------------------------------
# P10-G4: Gouge always NOT_VERIFIABLE without STEP (MUST 10)
# ---------------------------------------------------------------------------

class TestGougeAlwaysNotVerifiable:
    def test_gouge_not_verifiable_no_stock(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.gouge_validated == "NOT_VERIFIABLE"

    def test_gouge_not_verifiable_with_stock(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.gouge_validated == "NOT_VERIFIABLE"

    def test_gouge_not_verifiable_with_stock_and_fixture(self):
        from backend.manufacturing.workflow_orchestrator import FixtureSelection
        sel = FixtureSelection("std-vise-jaw-100mm", 500.0, 500.0, -40.0)
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
            fixture_selections=[sel],
        )
        result = run_production_verification(req)
        assert result.gouge_validated == "NOT_VERIFIABLE"


# ---------------------------------------------------------------------------
# P10-G5: Separate result fields (MUST 9)
# ---------------------------------------------------------------------------

class TestSeparateResultFields:
    def test_all_fields_present(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert hasattr(result, "simulation_ran")
        assert hasattr(result, "stock_removal_validated")
        assert hasattr(result, "gouge_validated")
        assert hasattr(result, "collision_scope_validated")

    def test_fields_are_independent(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        # gouge and stock_removal are separate — one NOT_VERIFIABLE doesn't require both
        assert result.gouge_validated == "NOT_VERIFIABLE"
        # stock_removal can be PASS/FAIL when stock supplied
        assert result.stock_removal_validated != "NOT_VERIFIABLE"

    def test_p8_result_wrapped(self):
        req = WorkflowVerificationRequest(candidate=_candidate())
        result = run_production_verification(req)
        assert result.p8_result is not None
        assert hasattr(result.p8_result, "tool_reach_validated")
        assert hasattr(result.p8_result, "machine_envelope_validated")


# ---------------------------------------------------------------------------
# P10-G6: Safety invariants
# ---------------------------------------------------------------------------

class TestStockSafetyInvariants:
    def test_is_dispatchable_always_false(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.is_dispatchable is False
        assert result.p8_result.is_dispatchable is False

    def test_production_released_always_false(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.production_released is False

    def test_simulation_method_not_exact_boolean(self):
        req = WorkflowVerificationRequest(
            candidate=_candidate(),
            stock_def=_rect_stock(),
        )
        result = run_production_verification(req)
        assert result.simulation_method != "EXACT_BOOLEAN"
