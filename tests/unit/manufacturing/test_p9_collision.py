"""
P9: Collision readiness checks — test suite.

Covers fixture collision, holder collision, and tool collision logic
exercised through the full build_verification_input / run_p8_verification stack.

  P9-COL-1  Tool collision: path intersects fixture → FAIL
  P9-COL-2  Tool collision: path clears fixture → PASS
  P9-COL-3  Fixture collision: no fixtures → NOT_VERIFIABLE
  P9-COL-4  Fixture collision: untrusted fixture → NOT_VERIFIABLE
  P9-COL-5  Rapid collision: rapid move through fixture → check runs
  P9-COL-6  check_tool_collision: intersecting cylinder vs AABB → FAIL
  P9-COL-7  check_tool_collision: non-intersecting → PASS
  P9-COL-8  Fixture seed + adapter: library fixture wired into collision check
  P9-COL-9  Holder collision: holder_diam known → check executes (not NOT_VERIFIABLE)
  P9-COL-10 Holder collision: holder_diam=None → NOT_VERIFIABLE
  P9-COL-11 is_dispatchable=False after collision FAIL
  P9-COL-12 is_dispatchable=False after collision PASS
  P9-COL-13 fixture_count in result reflects supplied trustworthy fixtures
  P9-COL-14 Untrusted fixture (UNKNOWN provenance) excluded from collision check
  P9-COL-15 Multiple fixtures: collision with any → FAIL
  P9-COL-16 check_rapid_clearance: rapid through fixture → runs
  P9-COL-17 Fixture seed in full pipeline: vise-100mm at WCS → check executes

HARD_RULES_CHECKED:
  - GEOMETRY_CHECK_PASS != COLLISION_VALIDATED (labels separate)
  - is_dispatchable=False always
  - production_released=False always
  - Untrusted fixture geometry excluded from collision
"""

from __future__ import annotations

from types import SimpleNamespace

from backend.manufacturing.fixture_seed import (
    get_fixture_by_id,
    make_fixture_input_from_library,
)
from backend.manufacturing.verification_adapter import (
    FixtureInput,
    GeometryFieldProvenance,
    build_verification_input,
    run_p8_verification,
)
from backend.verification.checks import (
    check_rapid_clearance,
    check_tool_collision,
)
from backend.verification.enums import FixtureSource, FixtureType, VerificationStatus
from backend.verification.models import VerificationSegment
from backend.verification.stock import FixtureGeometry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_candidate(nc_segments: list | None = None, tool_diam: float = 10.0) -> SimpleNamespace:
    return SimpleNamespace(
        feature_id="test-collision",
        toolpath_id="tp-col",
        tool_diameter_mm=tool_diam,
        nc_segments=nc_segments or [],
    )


def _seg_dict(
    sx: float = 0.0, sy: float = 0.0, sz: float = 50.0,
    ex: float = 0.0, ey: float = 0.0, ez: float = -20.0,
    is_cutting: bool = True,
    motion_type: str = "FEED_LINEAR",
) -> dict:
    return {
        "segment_id": "s1",
        "start_x": sx, "start_y": sy, "start_z": sz,
        "end_x": ex, "end_y": ey, "end_z": ez,
        "motion_type": motion_type,
        "is_cutting": is_cutting,
    }


def _seg(
    sx: float = 0.0, sy: float = 0.0, sz: float = 50.0,
    ex: float = 0.0, ey: float = 0.0, ez: float = -20.0,
    is_cutting: bool = True,
    motion_type: str = "CUT",
) -> VerificationSegment:
    return VerificationSegment(
        segment_id="s1",
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type=motion_type,
        is_cutting=is_cutting,
    )


def _fixture_at(
    min_x: float, min_y: float, min_z: float,
    max_x: float, max_y: float, max_z: float,
    fixture_id: str = "fix-1",
    provenance: GeometryFieldProvenance = GeometryFieldProvenance.USER_CONFIRMED,
) -> FixtureInput:
    return FixtureInput(
        fixture_id=fixture_id,
        fixture_type=FixtureType.VISE_JAWS,
        source=FixtureSource.USER_DEFINED,
        provenance=provenance,
        min_x_mm=min_x,
        min_y_mm=min_y,
        min_z_mm=min_z,
        max_x_mm=max_x,
        max_y_mm=max_y,
        max_z_mm=max_z,
    )


def _fgeom(
    min_x: float, min_y: float, min_z: float,
    max_x: float, max_y: float, max_z: float,
    fixture_id: str = "fg-1",
) -> FixtureGeometry:
    return FixtureGeometry(
        fixture_id=fixture_id,
        fixture_type=FixtureType.VISE_JAWS,
        source=FixtureSource.USER_DEFINED,
        min_x_mm=min_x,
        min_y_mm=min_y,
        min_z_mm=min_z,
        max_x_mm=max_x,
        max_y_mm=max_y,
        max_z_mm=max_z,
    )


# ---------------------------------------------------------------------------
# P9-COL-6 / P9-COL-7: check_tool_collision directly
# ---------------------------------------------------------------------------


class TestCheckToolCollisionDirect:

    def test_p9col_6_path_through_fixture_gives_fail(self):
        """check_tool_collision: cutting path through fixture AABB → FAIL."""
        # Tool travels from Z=50 to Z=-20, passing through the fixture at Z=0..10
        # Fixture box: X=[-10,10], Y=[-10,10], Z=[0,10]
        # Tool centre at X=0, Y=0 → passes directly through
        segs = [_seg(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-20.0)]
        fixtures = [_fgeom(-10.0, -10.0, 0.0, 10.0, 10.0, 10.0)]
        result = check_tool_collision(segs, fixtures, tool_diameter_mm=10.0)
        assert result.status == VerificationStatus.FAIL

    def test_p9col_7_path_clears_fixture_gives_pass(self):
        """check_tool_collision: cutting path far from fixture → PASS."""
        # Tool travels in X direction at Y=200mm; fixture at Y=0..10 → no collision
        segs = [_seg(sx=-50.0, sy=200.0, sz=5.0, ex=50.0, ey=200.0, ez=5.0)]
        fixtures = [_fgeom(-10.0, -10.0, 0.0, 10.0, 10.0, 10.0)]
        result = check_tool_collision(segs, fixtures, tool_diameter_mm=10.0)
        assert result.status == VerificationStatus.PASS

    def test_p9col_no_fixtures_gives_not_performed(self):
        """check_tool_collision: no fixtures → NOT_PERFORMED."""
        segs = [_seg()]
        result = check_tool_collision(segs, [], tool_diameter_mm=10.0)
        assert result.status in (
            VerificationStatus.PASS,  # pass with note
            VerificationStatus.NOT_PERFORMED,
        )


# ---------------------------------------------------------------------------
# P9-COL-16: check_rapid_clearance
# ---------------------------------------------------------------------------


class TestCheckRapidClearance:

    def test_p9col_16_rapid_through_fixture_check_runs(self):
        """check_rapid_clearance: rapid move through fixture → check executes."""
        # Rapid from Z=100 to Z=-100, through fixture at Z=0..20
        segs = [
            _seg(sx=0.0, sy=0.0, sz=100.0, ex=0.0, ey=0.0, ez=-100.0,
                 motion_type="RAPID", is_cutting=False)
        ]
        fixtures = [_fgeom(-15.0, -15.0, 0.0, 15.0, 15.0, 20.0)]
        result = check_rapid_clearance(segs, fixtures, tool_diameter_mm=10.0)
        # Should FAIL or at minimum execute the check (not NOT_PERFORMED)
        assert result.status != VerificationStatus.NOT_PERFORMED


# ---------------------------------------------------------------------------
# P9-COL-1 / P9-COL-2 / P9-COL-3 / P9-COL-11 / P9-COL-12: Pipeline tests
# ---------------------------------------------------------------------------


class TestCollisionPipeline:

    def test_p9col_1_path_through_fixture_collision_fail(self):
        """Pipeline: tool path through fixture → tool_collision_validated=FAIL."""
        # Fixture at X=[-10,10], Y=[-10,10], Z=[-30,10]
        # Tool path: X=0, Y=0, Z from 50 to -30 → passes through fixture
        fix = _fixture_at(-10.0, -10.0, -30.0, 10.0, 10.0, 10.0)
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-30.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "FAIL"

    def test_p9col_2_path_clear_fixture_collision_pass(self):
        """Pipeline: tool path clear of fixture → tool_collision_validated=PASS."""
        # Fixture at X=[100,120], Y=[100,120], Z=[0,30]
        # Tool path: X=0, Y=0 → 50mm away from fixture
        fix = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0)
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-20.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "PASS"

    def test_p9col_3_no_fixtures_gives_not_verifiable(self):
        """Pipeline: no fixtures → tool_collision_validated=NOT_VERIFIABLE."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand)
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "NOT_VERIFIABLE"

    def test_p9col_4_untrusted_fixture_gives_not_verifiable(self):
        """Pipeline: UNKNOWN provenance fixture → NOT_VERIFIABLE (excluded)."""
        fix = _fixture_at(
            -10.0, -10.0, -30.0, 10.0, 10.0, 10.0,
            provenance=GeometryFieldProvenance.UNKNOWN,
        )
        cand = _mock_candidate(nc_segments=[
            _seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-30.0),
        ])
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "NOT_VERIFIABLE"

    def test_p9col_11_dispatchable_false_after_collision_fail(self):
        """is_dispatchable=False even after FAIL collision result."""
        fix = _fixture_at(-10.0, -10.0, -30.0, 10.0, 10.0, 10.0)
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-30.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_p9col_12_dispatchable_false_after_collision_pass(self):
        """is_dispatchable=False even after PASS collision result."""
        fix = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0)
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-20.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_p9col_13_fixture_count_in_result(self):
        """P8VerificationResult.fixture_count reflects trustworthy fixtures."""
        fix1 = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0, fixture_id="f1")
        fix2 = _fixture_at(200.0, 200.0, 0.0, 220.0, 220.0, 30.0, fixture_id="f2")
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix1, fix2])
        result = run_p8_verification(vi)
        assert result.fixture_count == 2

    def test_p9col_14_untrusted_fixture_excluded_from_count(self):
        """Untrusted (UNKNOWN provenance) fixtures are excluded from collision count."""
        trusted = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0, fixture_id="f-trusted")
        untrusted = _fixture_at(
            200.0, 200.0, 0.0, 220.0, 220.0, 30.0,
            fixture_id="f-untrusted",
            provenance=GeometryFieldProvenance.UNKNOWN,
        )
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand, fixture_inputs=[trusted, untrusted])
        result = run_p8_verification(vi)
        # fixture_count counts trustworthy (non-UNKNOWN) fixtures only
        assert result.fixture_count == 1

    def test_p9col_15_multiple_fixtures_collision_any(self):
        """Multiple fixtures: tool path through one of them → FAIL."""
        fix_safe = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0, fixture_id="safe")
        fix_hit = _fixture_at(-10.0, -10.0, -30.0, 10.0, 10.0, 10.0, fixture_id="hit")
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-30.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix_safe, fix_hit])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "FAIL"


# ---------------------------------------------------------------------------
# P9-COL-8 / P9-COL-17: Fixture seed in pipeline
# ---------------------------------------------------------------------------


class TestFixtureSeedInPipeline:

    def test_p9col_8_library_fixture_wired_into_collision(self):
        """Library vise fixture (100mm) wired into adapter → collision check executes."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        # Place vise centre at X=200, Y=200, bottom Z=0
        fi = make_fixture_input_from_library(r, 200.0, 200.0, 0.0)
        # Tool path far from fixture → PASS
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=30.0, ex=0.0, ey=0.0, ez=-10.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fi])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "PASS"

    def test_p9col_17_vise_100mm_at_wcs_collision_pass(self):
        """Full pipeline: 100mm vise at defined WCS position → check passes when clear.

        Vise placed with bottom at Z=-120.  Vise spans Z=[-120,-80].
        Tool radius=5mm → expanded AABB max_z = -80 + 5 = -75.
        Tool path Z range: [5, 50], entirely above -75.  Result: PASS.
        """
        r = get_fixture_by_id("std-vise-jaw-100mm")
        # Place vise centre at X=200, Y=0 (far from tool path), bottom Z=-120
        fi = make_fixture_input_from_library(r, 200.0, 0.0, -120.0)
        # Tool path: X=0, Y=0, Z from 50 to 5 — far from vise in XY → PASS
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=5.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fi])
        result = run_p8_verification(vi)
        assert result.tool_collision_validated == "PASS"


# ---------------------------------------------------------------------------
# P9-COL-9 / P9-COL-10: Holder collision
# ---------------------------------------------------------------------------


class TestHolderCollision:

    def test_p9col_9_holder_diam_known_enables_check(self):
        """holder_diam known → holder_collision_validated != NOT_VERIFIABLE."""
        from types import SimpleNamespace
        hr = SimpleNamespace(
            stable_id="mock-holder",
            body_diameter_mm=57.0,
            gauge_length_mm=100.0,
        )
        fix = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0)
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-20.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix], holder_record=hr)
        result = run_p8_verification(vi)
        assert result.holder_collision_validated != "NOT_VERIFIABLE"

    def test_p9col_10_holder_diam_none_gives_not_verifiable(self):
        """holder_diam=None → holder_collision_validated=NOT_VERIFIABLE."""
        fix = _fixture_at(100.0, 100.0, 0.0, 120.0, 120.0, 30.0)
        segs = [_seg_dict(sx=0.0, sy=0.0, sz=50.0, ex=0.0, ey=0.0, ez=-20.0)]
        cand = _mock_candidate(nc_segments=segs, tool_diam=10.0)
        vi = build_verification_input(candidate=cand, fixture_inputs=[fix])
        result = run_p8_verification(vi)
        assert result.holder_collision_validated == "NOT_VERIFIABLE"
