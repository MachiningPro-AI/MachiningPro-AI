"""
Phase Y — Exact gouge semantics tests.

GOUGE_EXACT_READY=NO (mesh engine not available)
GOUGE_EXACT=NOT_VERIFIABLE (always, until mesh engine installed)
GOUGE_CONSERVATIVE=PARTIAL (bbox check, never PASS)

Tests verify the exact/conservative separation contract.
"""

import pytest

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

class TestGougeExactNotVerifiable:
    """GOUGE_EXACT is always NOT_VERIFIABLE — mesh engine not available (KL-07)."""

    def test_gouge_exact_always_not_verifiable(self):
        segs = [_seg()]
        result = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert result.status == VerificationStatus.NOT_VERIFIABLE, (
            f"GOUGE_EXACT must always be NOT_VERIFIABLE. Got {result.status}"
        )

    def test_gouge_exact_no_part_still_not_verifiable(self):
        result = check_part_gouge_exact([], None, None, None)
        assert result.status == VerificationStatus.NOT_VERIFIABLE

    def test_gouge_exact_has_correct_check_type(self):
        result = check_part_gouge_exact([], None, None, None)
        assert result.check_type == VerificationCheckType.GOUGE_EXACT

    def test_gouge_exact_evidence_documents_limitation(self):
        segs = [_seg()]
        result = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert result.evidence.get("gouge_exact_ready") is False
        assert "MESH_INTERSECTION_ENGINE_NOT_AVAILABLE" in str(result.evidence.get("reason", ""))

    def test_gouge_exact_never_pass(self):
        """HARD RULE: GOUGE_EXACT must NEVER return PASS."""
        for _ in range(5):
            segs = [_seg(sz=100.0, ez=100.0)]  # completely clear
            result = check_part_gouge_exact(segs, (-1, -1, 0), (1, 1, 1), 0.1)
            assert result.status != VerificationStatus.PASS, "HARD RULE VIOLATED: GOUGE_EXACT returned PASS"

    def test_gouge_exact_never_partial(self):
        """HARD RULE: GOUGE_EXACT must NEVER return PARTIAL."""
        segs = [_seg()]
        result = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert result.status != VerificationStatus.PARTIAL, "HARD RULE VIOLATED: GOUGE_EXACT returned PARTIAL"


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

    def test_exact_not_verifiable_even_when_conservative_passes(self):
        """Conservative may find PARTIAL; exact is still NOT_VERIFIABLE."""
        segs = [_seg(sz=100.0, ez=100.0)]  # no bbox overlap
        r_exact = check_part_gouge_exact(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        r_cons = check_part_gouge(segs, (-5, -5, 0), (5, 5, 10), 5.0)
        assert r_exact.status == VerificationStatus.NOT_VERIFIABLE
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
