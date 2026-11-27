"""
Phase G + Phase W + Phase X — Holder collision tests.

Tests holder-part, holder-stock, and holder-fixture collision checks
with deterministic test-only geometry.

TEST_ONLY=YES — no production catalog data modified.
"""

import pytest

from backend.verification.checks import (
    check_holder_fixture_collision,
    check_holder_part_collision,
    check_holder_stock_collision,
)
from backend.verification.enums import VerificationStatus
from backend.verification.models import VerificationSegment
from backend.verification.stock import FixtureGeometry, StockModel
from backend.verification.enums import StockShape, FixtureSource, FixtureType


def _seg(sx=0.0, sy=0.0, sz=10.0, ex=0.0, ey=0.0, ez=-10.0, is_cutting=True, op=None):
    return VerificationSegment(
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type="CUT" if is_cutting else "RAPID",
        is_cutting=is_cutting,
        operation_id=op,
    )


def _fixture(x0=-20, y0=-20, z0=-5, x1=20, y1=20, z1=0):
    return FixtureGeometry(
        fixture_id="TEST_FIXTURE_01",
        fixture_type=FixtureType.VISE_JAWS,
        source=FixtureSource.USER_DEFINED,
        min_x_mm=float(x0), min_y_mm=float(y0), min_z_mm=float(z0),
        max_x_mm=float(x1), max_y_mm=float(y1), max_z_mm=float(z1),
    )


def _stock_box(x0=-50, y0=-50, z0=-20, x1=50, y1=50, z1=20):
    return StockModel(
        shape=StockShape.BOX,
        min_x_mm=float(x0), min_y_mm=float(y0), min_z_mm=float(z0),
        max_x_mm=float(x1), max_y_mm=float(y1), max_z_mm=float(z1),
    )


# ---------------------------------------------------------------------------
# Phase W: POSITIVE COLLISION TEST (deterministic FAIL cases)
# TEST_ONLY — does not modify production catalog
# ---------------------------------------------------------------------------

class TestHolderPartCollisionFail:
    """Phase W — COLLISION_TRIGGERED=YES cases."""

    def test_holder_part_collision_known_collision(self):
        """Large holder directly over part → FAIL.

        Holder offset_z = tool_length = 20mm, holder_diameter = 60mm (very wide).
        Part bbox is z=[0,10] with XY=[-5,5].
        Tool tip at z=5 → holder base at z=25, holder top at z=75.
        But holder radius=30 extends well past the XY extent of the tool.
        """
        segs = [_seg(sz=5.0, ez=5.0)]  # stationary point inside part
        # Part bbox: small box at centre
        part_min = (-5.0, -5.0, 0.0)
        part_max = (5.0, 5.0, 10.0)
        result = check_holder_part_collision(
            segs, part_min, part_max,
            tool_length_mm=0.0,     # holder starts at same Z as tool tip
            holder_diameter_mm=60.0,  # very wide
            holder_length_mm=50.0,
        )
        # Holder cylinder (r=30, z_base=5..55) vs part AABB(x=-5..5, y=-5..5, z=0..10)
        assert result.status == VerificationStatus.FAIL, (
            f"Expected FAIL — large holder over part. Got {result.status}"
        )
        assert result.issues, "Expected collision issues"

    def test_holder_stock_collision_known_collision(self):
        """Phase W — holder wider than stock bbox in Z → FAIL."""
        segs = [_seg(sz=100.0, ez=100.0)]  # above stock
        stock = _stock_box(x0=-10, y0=-10, z0=90, x1=10, y1=10, z1=110)
        result = check_holder_stock_collision(
            segs, stock,
            tool_length_mm=0.0,
            holder_diameter_mm=40.0,
            holder_length_mm=50.0,
        )
        assert result.status == VerificationStatus.FAIL, (
            f"Expected FAIL — holder over stock. Got {result.status}"
        )

    def test_holder_fixture_collision_known_collision(self):
        """Phase W — holder intersects fixture → FAIL."""
        # Tool at z=0, fixture at z=[-5..0], holder starts at z=tool_length_mm
        segs = [_seg(sz=0.0, ez=0.0)]
        fixture = _fixture(x0=-5, y0=-5, z0=15, x1=5, y1=5, z1=65)
        result = check_holder_fixture_collision(
            segs, [fixture],
            tool_length_mm=10.0,  # holder base at z=10
            holder_diameter_mm=40.0,
            holder_length_mm=60.0,
        )
        assert result.status == VerificationStatus.FAIL, (
            f"Expected FAIL — holder into fixture. Got {result.status}"
        )


# ---------------------------------------------------------------------------
# Phase X: NEGATIVE COLLISION TEST (deterministic PASS cases)
# ---------------------------------------------------------------------------

class TestHolderCollisionPass:
    """Phase X — COLLISION_STATUS=PASS with real geometry."""

    def test_holder_part_collision_clear(self):
        """Holder far above part — PASS."""
        segs = [_seg(sz=100.0, ez=100.0)]  # very high
        part_min = (-5.0, -5.0, 0.0)
        part_max = (5.0, 5.0, 10.0)
        result = check_holder_part_collision(
            segs, part_min, part_max,
            tool_length_mm=50.0,  # holder starts at z=150
            holder_diameter_mm=40.0,
            holder_length_mm=60.0,
        )
        assert result.status == VerificationStatus.PASS, (
            f"Expected PASS — holder far above part. Got {result.status}"
        )

    def test_holder_stock_collision_clear(self):
        """Holder starts above stock — PASS."""
        segs = [_seg(sz=200.0, ez=200.0)]
        stock = _stock_box(x0=-50, y0=-50, z0=0, x1=50, y1=50, z1=50)
        result = check_holder_stock_collision(
            segs, stock,
            tool_length_mm=100.0,  # holder base at z=300
            holder_diameter_mm=40.0,
            holder_length_mm=60.0,
        )
        assert result.status == VerificationStatus.PASS

    def test_holder_fixture_collision_clear(self):
        """Holder above fixture — PASS."""
        segs = [_seg(sz=200.0, ez=200.0)]
        fixture = _fixture(x0=-5, y0=-5, z0=-5, x1=5, y1=5, z1=0)
        result = check_holder_fixture_collision(
            segs, [fixture],
            tool_length_mm=50.0,  # holder base at z=250
            holder_diameter_mm=40.0,
            holder_length_mm=60.0,
        )
        assert result.status == VerificationStatus.PASS


# ---------------------------------------------------------------------------
# NOT_PERFORMED cases (missing data)
# ---------------------------------------------------------------------------

class TestHolderCollisionNotPerformed:
    def test_holder_part_no_holder_geometry(self):
        segs = [_seg()]
        result = check_holder_part_collision(segs, (-5, -5, 0), (5, 5, 10), None, None, None)
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_holder_part_no_part_geometry(self):
        segs = [_seg()]
        result = check_holder_part_collision(segs, None, None, 20.0, 40.0, 50.0)
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_holder_stock_no_stock(self):
        segs = [_seg()]
        result = check_holder_stock_collision(segs, None, 20.0, 40.0, 50.0)
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_holder_fixture_no_fixtures(self):
        segs = [_seg()]
        result = check_holder_fixture_collision(segs, [], 20.0, 40.0, 50.0)
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_holder_part_missing_tool_length(self):
        segs = [_seg()]
        result = check_holder_part_collision(segs, (-5, -5, 0), (5, 5, 10), None, 40.0, 50.0)
        assert result.status == VerificationStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Fidelity and evidence reporting
# ---------------------------------------------------------------------------

class TestHolderCollisionEvidence:
    def test_holder_part_collision_evidence_on_fail(self):
        segs = [_seg(sz=5.0, ez=5.0)]
        result = check_holder_part_collision(
            segs, (-5.0, -5.0, 0.0), (5.0, 5.0, 10.0),
            tool_length_mm=0.0, holder_diameter_mm=60.0, holder_length_mm=50.0,
        )
        if result.status == VerificationStatus.FAIL:
            for issue in result.issues:
                ev = issue.evidence
                assert ev.get("method") == "BBOX_CYLINDER"
                assert ev.get("fidelity") == "SIMPLIFIED_CYLINDER"
                assert ev.get("geometry_source") == "CATALOG"

    def test_holder_part_pass_evidence(self):
        segs = [_seg(sz=200.0, ez=200.0)]
        result = check_holder_part_collision(
            segs, (-5.0, -5.0, 0.0), (5.0, 5.0, 10.0),
            tool_length_mm=50.0, holder_diameter_mm=40.0, holder_length_mm=60.0,
        )
        if result.status == VerificationStatus.PASS:
            assert result.evidence.get("method") == "BBOX_CYLINDER"
            assert result.evidence.get("fidelity") == "SIMPLIFIED_CYLINDER"
