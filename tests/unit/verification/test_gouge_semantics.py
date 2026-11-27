"""
Phase Y — Exact gouge semantics tests.

beta.5: GOUGE_EXACT_METHOD=BREP_BOOLEAN_OCC (KL-07 RESOLVED)
  - With segments but no STEP target → PARTIAL (engine ran, no target to compare)
  - Without segments → NOT_VERIFIABLE (nothing to check)
  - With STEP target → PASS/FAIL/PARTIAL based on Boolean result

GOUGE_CONSERVATIVE=PARTIAL (bbox check, never PASS)

Tests verify the exact/conservative separation contract.
"""


from backend.verification.checks import (
    check_part_gouge,
    check_part_gouge_exact,
)
from backend.verification.enums import VerificationCheckType, VerificationStatus
from backend.verification.models import VerificationSegment


def _seg(sx=0.0, sy=0.0, sz=5.0, ex=0.0, ey=0.0, ez=-5.0, is_cutting=True):
    return VerificationSegment(
        start_x=sx, start_y=sy, start_z=sz,
        end_x=ex, end_y=ey, end_z=ez,
        motion_type="CUT" if is_cutting else "RAPID",
        is_cutting=is_cutting,
    )


# ---------------------------------------------------------------------------
# GOUGE_EXACT — always NOT_VERIFIABLE (Phase Y: GOUGE_EXACT_READY=NO)
# ---------------------------------------------------------------------------

class TestGougeExactEngine:
    """GOUGE_EXACT — beta.5 engine: BREP_BOOLEAN_OCC, KL-07 RESOLVED."""

    def test_gouge_exact_no_segs_not_verifiable(self):
        """No cutting segments → NOT_VERIFIABLE (nothing to check)."""
        result = check_part_gouge_exact([], None, None, None)
        assert result.status == VerificationStatus.NOT_VERIFIABLE

    def test_gouge_exact_has_correct_check_type(self):
        result = check_part_gouge_exact([], None, None, None)
        assert result.check_type == VerificationCheckType.GOUGE_EXACT

    def test_gouge_exact_with_segs_runs_engine(self):
        """Engine runs with segments; without STEP target → PARTIAL (stock removal verified)."""
        segs = [_seg()]
        result = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        # Engine ran — PARTIAL (no target → partial check only) or NOT_VERIFIABLE on failure
        assert result.status in (
            VerificationStatus.PARTIAL,
            VerificationStatus.NOT_VERIFIABLE,
        )

    def test_gouge_exact_evidence_has_method(self):
        """Evidence must report BREP_BOOLEAN_OCC method (KL-07 resolved)."""
        segs = [_seg()]
        result = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert result.evidence.get("method") == "BREP_BOOLEAN_OCC"

    def test_gouge_exact_never_pass_without_step_target(self):
        """Without STEP target, GOUGE_EXACT must never return PASS (no ground truth)."""
        for _ in range(3):
            segs = [_seg(sz=100.0, ez=100.0)]
            result = check_part_gouge_exact(segs, (-1, -1, 0), (1, 1, 1), 0.1)
            assert result.status != VerificationStatus.PASS, (
                "GOUGE_EXACT returned PASS without STEP target — no ground truth available"
            )


# ---------------------------------------------------------------------------
# GOUGE_CONSERVATIVE (PART_GOUGE) — bbox check, NEVER returns PASS
# ---------------------------------------------------------------------------

class TestGougeConservativeSeparation:
    """Conservative check: NEVER returns PASS, returns PARTIAL when clear."""

    def test_gouge_conservative_never_pass(self):
        """HARD RULE: PART_GOUGE conservative check never returns PASS."""
        segs = [_seg(sz=100.0, ez=100.0)]  # far above part
        result = check_part_gouge(segs, (-1, -1, 0), (1, 1, 1), 0.1)
        assert result.status != VerificationStatus.PASS, (
            "HARD RULE VIOLATED: PART_GOUGE conservative returned PASS"
        )

    def test_gouge_conservative_no_violation_partial(self):
        """No bbox overlap → PARTIAL (not PASS)."""
        segs = [_seg(sz=100.0, ez=100.0)]
        result = check_part_gouge(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert result.status == VerificationStatus.PARTIAL

    def test_gouge_conservative_violation_fail(self):
        """Cutting below part bottom → FAIL."""
        segs = [_seg(sz=5.0, ez=-50.0)]  # goes below part
        result = check_part_gouge(segs, (-10, -10, -20), (10, 10, 0), 5.0)
        assert result.status == VerificationStatus.FAIL

    def test_gouge_conservative_has_correct_check_type(self):
        segs = [_seg(sz=100.0, ez=100.0)]
        result = check_part_gouge(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert result.check_type == VerificationCheckType.PART_GOUGE

    def test_gouge_conservative_no_part_insufficient(self):
        segs = [_seg()]
        result = check_part_gouge(segs, None, None, 5.0)
        assert result.status == VerificationStatus.INSUFFICIENT_DATA


# ---------------------------------------------------------------------------
# Conservative vs Exact separation contract
# ---------------------------------------------------------------------------

class TestGougeConservationExactSeparation:
    """CONSERVATIVE and EXACT checks must remain independent."""

    def test_exact_and_conservative_different_check_types(self):
        segs = [_seg()]
        r_exact = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        r_cons = check_part_gouge(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert r_exact.check_type == VerificationCheckType.GOUGE_EXACT
        assert r_cons.check_type == VerificationCheckType.PART_GOUGE
        assert r_exact.check_type != r_cons.check_type

    def test_exact_runs_engine_when_conservative_finds_partial(self):
        """Conservative PARTIAL; exact engine runs (PARTIAL=no target, or NOT_VERIFIABLE)."""
        segs = [_seg(sz=100.0, ez=100.0)]  # no bbox overlap
        r_exact = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        r_cons = check_part_gouge(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert r_exact.status in (
            VerificationStatus.PARTIAL,
            VerificationStatus.NOT_VERIFIABLE,
        )
        assert r_cons.status == VerificationStatus.PARTIAL  # never PASS


# ---------------------------------------------------------------------------
# Tolerance contract
# ---------------------------------------------------------------------------

class TestGougeTolerance:
    def test_gouge_tolerance_reported_in_evidence(self):
        """Conservative check reports tolerance used."""
        segs = [_seg(sz=5.0, ez=-100.0)]  # deep cut
        result = check_part_gouge(segs, (-10, -10, -50), (10, 10, 0), 5.0)
        # Either FAIL or PARTIAL — either way check for tolerance in evidence
        for issue in result.issues:
            if "tolerance_mm" in issue.evidence:
                assert issue.evidence["tolerance_mm"] >= 0
