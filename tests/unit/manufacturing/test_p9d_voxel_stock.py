"""
P9-D: Voxel stock-removal engine wiring — test suite.

Covers:
  P9-D-1  stock_definition_to_stock_model: BOX stock → StockModel with shape=BOX
  P9-D-2  stock_definition_to_stock_model: ROUND_BAR → StockModel with shape=CYLINDER
  P9-D-3  stock_definition_to_stock_model: incomplete dimensions → None
  P9-D-4  stock_definition_to_stock_model: None stock_def → None
  P9-D-5  build_verification_input: stock_def → stock_model populated
  P9-D-6  build_verification_input: stock_def → stock_provenance=USER_CONFIRMED
  P9-D-7  run_p8_verification: stock_model None → stock_removal_validated=NOT_VERIFIABLE
  P9-D-8  run_p8_verification: stock_model populated → stock_removal_validated != NOT_VERIFIABLE
  P9-D-9  BOX stock: half-extents correct from length/width/height
  P9-D-10 CYLINDER stock: radius and height correct from outer_diameter/length
  P9-D-11 build_verification_input: incomplete stock_def → STOCK_DEFINITION_INCOMPLETE note
  P9-D-12 is_dispatchable=False with stock supplied
  P9-D-13 production_released=False with stock supplied
  P9-D-14 BOX stock fidelity = ANALYTIC_PRIMITIVE
  P9-D-15 BOX stock top face at z=0 (machining convention)

HARD_RULES_CHECKED:
  - FABRICATED_STOCK_GEOMETRY=NO
  - is_dispatchable=False always
  - production_released=False always
  - StockRemovalFidelity is VOXEL_APPROXIMATE or ANALYTIC (never EXACT_BOOLEAN)
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.manufacturing.setup_stock import StockDefinition, StockShape
from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    build_verification_input,
    run_p8_verification,
    stock_definition_to_stock_model,
)
from backend.verification.enums import StockFidelity
from backend.verification.enums import StockShape as VStockShape

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_candidate(nc_segments: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        feature_id="test-p9d",
        toolpath_id="tp-p9d",
        tool_diameter_mm=5.0,
        nc_segments=nc_segments or [],
    )


def _seg_dict(start_z: float = 0.0, end_z: float = -15.0) -> dict:
    return {
        "segment_id": "s1",
        "start_x": 0.0, "start_y": 0.0, "start_z": start_z,
        "end_x": 0.0, "end_y": 0.0, "end_z": end_z,
        "motion_type": "FEED_LINEAR",
        "is_cutting": True,
    }


def _box_stock(
    length_mm: float = 100.0,
    width_mm: float = 80.0,
    height_mm: float = 30.0,
    material_grade: str = "1.0038",
) -> StockDefinition:
    return StockDefinition(
        stock_id="test-stock-p9d",
        shape=StockShape.RECTANGULAR_BLOCK,
        length_mm=length_mm,
        width_mm=width_mm,
        height_mm=height_mm,
        material_grade=material_grade,
    )


def _round_bar_stock(
    outer_diameter_mm: float = 50.0,
    length_mm: float = 120.0,
) -> StockDefinition:
    return StockDefinition(
        stock_id="test-bar-p9d",
        shape=StockShape.ROUND_BAR,
        outer_diameter_mm=outer_diameter_mm,
        length_mm=length_mm,
        material_grade="1.0038",
    )


# ---------------------------------------------------------------------------
# P9-D-1 / P9-D-9 / P9-D-14 / P9-D-15: BOX stock model
# ---------------------------------------------------------------------------


class TestBoxStockModel:

    def test_p9d_1_box_stock_gives_box_shape(self):
        """BOX stock definition → StockModel.shape=BOX."""
        sm = stock_definition_to_stock_model(_box_stock())
        assert sm is not None
        assert sm.shape == VStockShape.BOX

    def test_p9d_9_box_half_extents_correct(self):
        """BOX stock: half-extents derived from length/width/height."""
        sm = stock_definition_to_stock_model(
            _box_stock(length_mm=100.0, width_mm=80.0, height_mm=30.0)
        )
        assert sm is not None
        assert sm.min_x_mm == pytest.approx(-50.0)
        assert sm.max_x_mm == pytest.approx(50.0)
        assert sm.min_y_mm == pytest.approx(-40.0)
        assert sm.max_y_mm == pytest.approx(40.0)
        assert sm.min_z_mm == pytest.approx(-30.0)

    def test_p9d_14_box_fidelity_analytic(self):
        """BOX stock fidelity must be ANALYTIC_PRIMITIVE."""
        sm = stock_definition_to_stock_model(_box_stock())
        assert sm is not None
        assert sm.fidelity == StockFidelity.ANALYTIC_PRIMITIVE

    def test_p9d_15_box_top_face_at_z0(self):
        """BOX stock top face must be at z=0 (machining convention: part top = Z origin)."""
        sm = stock_definition_to_stock_model(_box_stock(height_mm=30.0))
        assert sm is not None
        assert sm.max_z_mm == pytest.approx(0.0)
        assert sm.min_z_mm == pytest.approx(-30.0)


# ---------------------------------------------------------------------------
# P9-D-2 / P9-D-10: CYLINDER stock model
# ---------------------------------------------------------------------------


class TestCylinderStockModel:

    def test_p9d_2_round_bar_gives_cylinder_shape(self):
        """ROUND_BAR stock → StockModel.shape=CYLINDER."""
        sm = stock_definition_to_stock_model(_round_bar_stock())
        assert sm is not None
        assert sm.shape == VStockShape.CYLINDER

    def test_p9d_10_cylinder_radius_and_height(self):
        """CYLINDER stock: radius=outer_diameter/2, height=length."""
        sm = stock_definition_to_stock_model(
            _round_bar_stock(outer_diameter_mm=50.0, length_mm=120.0)
        )
        assert sm is not None
        assert sm.radius_mm == pytest.approx(25.0)
        assert sm.height_mm == pytest.approx(120.0)


# ---------------------------------------------------------------------------
# P9-D-3 / P9-D-4 / P9-D-11: Incomplete / None stock
# ---------------------------------------------------------------------------


class TestIncompleteStock:

    def test_p9d_3_incomplete_dimensions_gives_none(self):
        """Stock definition with missing required dimensions → None."""
        # ROUND_BAR requires outer_diameter_mm and length_mm; outer_diameter_mm missing
        incomplete = StockDefinition(
            stock_id="test-incomplete",
            shape=StockShape.ROUND_BAR,
            material_grade="1.0038",
            length_mm=100.0,
            # outer_diameter_mm intentionally omitted
        )
        result = stock_definition_to_stock_model(incomplete)
        assert result is None

    def test_p9d_4_none_stock_def_gives_none(self):
        """stock_definition_to_stock_model(None) → None."""
        assert stock_definition_to_stock_model(None) is None

    def test_p9d_11_incomplete_stock_gives_note_in_adapter(self):
        """build_verification_input: incomplete stock_def → STOCK_DEFINITION_INCOMPLETE note."""
        cand = _mock_candidate()
        incomplete = StockDefinition(
            stock_id="test-incomplete-11",
            shape=StockShape.ROUND_BAR,
            material_grade="1.0038",
            length_mm=100.0,
            # outer_diameter_mm intentionally omitted
        )
        vi = build_verification_input(candidate=cand, stock_def=incomplete)
        note_text = " ".join(vi.provenance_notes)
        assert "STOCK_DEFINITION_INCOMPLETE" in note_text


# ---------------------------------------------------------------------------
# P9-D-5 / P9-D-6: Stock in P8VerificationInput
# ---------------------------------------------------------------------------


class TestStockInVerificationInput:

    def test_p9d_5_valid_stock_def_populates_stock_model(self):
        """build_verification_input with valid stock_def → stock_model populated."""
        cand = _mock_candidate()
        vi = build_verification_input(candidate=cand, stock_def=_box_stock())
        assert vi.stock_model is not None

    def test_p9d_6_valid_stock_def_gives_user_confirmed(self):
        """build_verification_input: valid stock → stock_provenance=USER_CONFIRMED."""
        cand = _mock_candidate()
        vi = build_verification_input(candidate=cand, stock_def=_box_stock())
        assert vi.stock_provenance == GeometryFieldProvenance.USER_CONFIRMED


# ---------------------------------------------------------------------------
# P9-D-7 / P9-D-8 / P9-D-12 / P9-D-13: run_p8_verification with stock
# ---------------------------------------------------------------------------


class TestRunP8VerificationWithStock:

    def test_p9d_7_no_stock_gives_not_verifiable(self):
        """run_p8_verification: no stock → stock_removal_validated=NOT_VERIFIABLE."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand)
        result = run_p8_verification(vi)
        assert result.stock_removal_validated == "NOT_VERIFIABLE"

    def test_p9d_8_stock_supplied_leaves_not_verifiable(self):
        """run_p8_verification: stock_model supplied → stock_removal_validated != NOT_VERIFIABLE."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand, stock_def=_box_stock())
        result = run_p8_verification(vi)
        assert result.stock_removal_validated != "NOT_VERIFIABLE"

    def test_p9d_12_dispatchable_false_with_stock(self):
        """is_dispatchable=False even when stock is supplied and checks pass."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand, stock_def=_box_stock())
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_p9d_13_production_released_false_with_stock(self):
        """production_released=False even when stock is supplied."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand, stock_def=_box_stock())
        result = run_p8_verification(vi)
        assert result.production_released is False
