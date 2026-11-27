"""Phase N — Stock removal tests."""

import pytest

try:
    import gmsh  # noqa: F401
    _GMSH = True
except ImportError:
    _GMSH = False

from backend.verification.stock_removal import (
    StockRemovalMode,
    StockRemovalResult,
    compute_stock_removal_fast,
    compute_stock_removal_brep,
)
from backend.verification.stock import StockModel
from backend.verification.enums import StockShape


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _box_stock(x=100.0, y=100.0, z=50.0) -> StockModel:
    return StockModel(shape=StockShape.BOX,
                      min_x_mm=0.0, min_y_mm=0.0, min_z_mm=0.0,
                      max_x_mm=x, max_y_mm=y, max_z_mm=z)


def _cyl_stock(d=80.0, h=60.0) -> StockModel:
    return StockModel(shape=StockShape.CYLINDER,
                      radius_mm=d / 2, height_mm=h,
                      center_x_mm=0.0, center_y_mm=0.0, bottom_z_mm=0.0)


def _segments():
    # list of (x1, y1, z1, x2, y2, z2)
    return [
        (0.0, 0.0, 5.0, 0.0, 0.0, -5.0),
        (10.0, 0.0, 5.0, 10.0, 0.0, -5.0),
    ]


# ---------------------------------------------------------------------------
# FAST mode
# ---------------------------------------------------------------------------

class TestFastMode:
    def test_returns_fast_approximate(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.mode == StockRemovalMode.FAST_APPROXIMATE

    def test_initial_volume_positive(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.initial_volume_mm3 is not None
        assert r.initial_volume_mm3 > 0

    def test_removed_volume_non_negative(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.removed_volume_mm3 >= 0.0

    def test_remaining_volume_positive(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.remaining_volume_mm3 > 0

    def test_volume_conservation(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        total = r.removed_volume_mm3 + r.remaining_volume_mm3
        assert abs(total - r.initial_volume_mm3) < 1e-6 * r.initial_volume_mm3 + 1e-3

    def test_cylinder_stock_fast(self):
        r = compute_stock_removal_fast(_cyl_stock(), tool_radius_mm=4.0,
                                       cutting_segments=_segments())
        assert r.mode == StockRemovalMode.FAST_APPROXIMATE
        assert r.initial_volume_mm3 > 0

    def test_fast_fidelity_label(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert "APPROXIMATE" in r.removed_volume_fidelity.upper() \
            or r.removed_volume_fidelity in ("VOXEL_APPROXIMATE", "FAST_APPROXIMATE")

    def test_no_error(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.error is None

    def test_zero_segments_fast(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=[])
        assert r.removed_volume_mm3 == 0.0
        assert r.remaining_volume_mm3 == r.initial_volume_mm3

    def test_result_dataclass(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert isinstance(r, StockRemovalResult)

    def test_fallback_not_used_in_fast(self):
        r = compute_stock_removal_fast(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert not r.fallback_used


# ---------------------------------------------------------------------------
# B-Rep Boolean mode
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _GMSH, reason="gmsh not available")
class TestBRepBooleanMode:
    def test_returns_brep_boolean_mode(self):
        r = compute_stock_removal_brep(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.mode in (StockRemovalMode.BREP_BOOLEAN, StockRemovalMode.FAST_APPROXIMATE)

    def test_brep_initial_volume_positive(self):
        r = compute_stock_removal_brep(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.initial_volume_mm3 > 0

    def test_brep_exact_or_fallback(self):
        r = compute_stock_removal_brep(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        if r.mode == StockRemovalMode.BREP_BOOLEAN:
            assert r.remaining_volume_fidelity in ("BREP_EXACT",)
        else:
            assert r.fallback_used

    def test_fallback_disclosed(self):
        r = compute_stock_removal_brep(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        if r.fallback_used:
            assert r.fallback_reason is not None and len(r.fallback_reason) > 0

    def test_no_silent_upgrade(self):
        r = compute_stock_removal_brep(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        if r.mode == StockRemovalMode.FAST_APPROXIMATE:
            assert r.fallback_used

    def test_removed_volume_finite(self):
        r = compute_stock_removal_brep(_box_stock(), tool_radius_mm=5.0,
                                       cutting_segments=_segments())
        assert r.removed_volume_mm3 >= 0.0
