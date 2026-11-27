"""
Phase I — Fixture collision tests (tool-fixture, part-fixture-interference).

TEST_ONLY=YES
"""

import pytest

from backend.verification.checks import (
    check_part_fixture_interference,
    check_tool_fixture_collision,
)
from backend.verification.enums import VerificationStatus, FixtureType, FixtureSource
from backend.verification.models import VerificationSegment
from backend.verification.stock import FixtureGeometry


def _seg(sx=0.0, sy=0.0, sz=10.0, ex=0.0, ey=0.0, ez=0.0, is_cutting=True):
    return VerificationSegment(
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type="CUT" if is_cutting else "RAPID",
        is_cutting=is_cutting,
    )


def _fixture(x0=-20, y0=-20, z0=-5, x1=20, y1=20, z1=0, fid="FIX01"):
    return FixtureGeometry(
        fixture_id=fid,
        fixture_type=FixtureType.VISE_JAWS,
        source=FixtureSource.USER_DEFINED,
        min_x_mm=float(x0), min_y_mm=float(y0), min_z_mm=float(z0),
        max_x_mm=float(x1), max_y_mm=float(y1), max_z_mm=float(z1),
    )


# ---------------------------------------------------------------------------
# TOOL_FIXTURE_COLLISION
# ---------------------------------------------------------------------------

class TestToolFixtureCollision:
    def test_tool_into_fixture_fail(self):
        """Tool passes through fixture — FAIL."""
        segs = [_seg(sz=5.0, ez=-5.0)]  # through z=0 plane (fixture top)
        fix = _fixture(x0=-5, y0=-5, z0=-10, x1=5, y1=5, z1=0)
        result = check_tool_fixture_collision(segs, [fix], tool_diameter_mm=5.0)
        assert result.status == VerificationStatus.FAIL

    def test_tool_clear_of_fixture_pass(self):
        """Tool stays far from fixture — PASS."""
        segs = [_seg(sx=100.0, ex=100.0)]  # far from fixture
        fix = _fixture(x0=-5, y0=-5, z0=-5, x1=5, y1=5, z1=0)
        result = check_tool_fixture_collision(segs, [fix], tool_diameter_mm=5.0)
        assert result.status == VerificationStatus.PASS

    def test_no_fixture_not_performed(self):
        segs = [_seg()]
        result = check_tool_fixture_collision(segs, [], tool_diameter_mm=5.0)
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_no_tool_diameter_insufficient(self):
        segs = [_seg()]
        fix = _fixture()
        result = check_tool_fixture_collision(segs, [fix], tool_diameter_mm=None)
        assert result.status == VerificationStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# PART_FIXTURE_INTERFERENCE
# ---------------------------------------------------------------------------

class TestPartFixtureInterference:
    def test_part_overlaps_fixture_partial(self):
        """Part bbox overlaps fixture → PARTIAL (possible setup interference)."""
        part_min = (-10.0, -10.0, -5.0)
        part_max = (10.0, 10.0, 15.0)
        fix = _fixture(x0=-15, y0=-15, z0=-10, x1=15, y1=15, z1=5)
        result = check_part_fixture_interference(part_min, part_max, [fix])
        assert result.status == VerificationStatus.PARTIAL

    def test_part_clear_of_fixture_pass(self):
        """Part bbox does not overlap fixture → PASS."""
        part_min = (100.0, 100.0, 0.0)
        part_max = (110.0, 110.0, 10.0)
        fix = _fixture(x0=-15, y0=-15, z0=-10, x1=15, y1=15, z1=5)
        result = check_part_fixture_interference(part_min, part_max, [fix])
        assert result.status == VerificationStatus.PASS

    def test_no_part_not_performed(self):
        fix = _fixture()
        result = check_part_fixture_interference(None, None, [fix])
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_no_fixture_not_performed(self):
        result = check_part_fixture_interference((-5, -5, 0), (5, 5, 10), [])
        assert result.status == VerificationStatus.NOT_PERFORMED

    def test_multiple_fixtures_all_clear(self):
        part_min = (100.0, 100.0, 0.0)
        part_max = (110.0, 110.0, 10.0)
        fixtures = [
            _fixture(x0=-15, y0=-15, z0=-10, x1=15, y1=15, z1=0, fid="F1"),
            _fixture(x0=-20, y0=-20, z0=-15, x1=20, y1=20, z1=-1, fid="F2"),
        ]
        result = check_part_fixture_interference(part_min, part_max, fixtures)
        assert result.status == VerificationStatus.PASS
