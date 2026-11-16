"""
P9-B: Holder geometry library wiring — test suite.

Covers:
  P9-B-1  build_verification_input: no holder_record → NOT_VERIFIABLE note
  P9-B-2  build_verification_input: holder with body_diameter_mm → KNOWN provenance
  P9-B-3  build_verification_input: holder with gauge_length_mm → KNOWN proxy note
  P9-B-4  build_verification_input: holder without body_diameter_mm → MISSING note
  P9-B-5  build_verification_input: holder without gauge_length_mm → MISSING note
  P9-B-6  kennametal-cat40-er32: body_diameter_mm=57.0, gauge_length_mm=100.0
  P9-B-7  kennametal-cat40-er40: body_diameter_mm=None in catalog (documented)
  P9-B-8  run_p8_verification: holder_diam known → holder_collision_validated != NOT_VERIFIABLE
  P9-B-9  run_p8_verification: holder_diam None → holder_collision_validated = NOT_VERIFIABLE
  P9-B-10 P8VerificationInput.holder_diameter_mm propagated correctly
  P9-B-11 P8VerificationInput.holder_length_mm propagated correctly
  P9-B-12 is_dispatchable remains False when holder geometry is known
  P9-B-13 production_released remains False when holder geometry is known
  P9-B-14 Holder with both fields missing → HOLDER_GEOMETRY note in provenance
  P9-B-15 Holder body_diameter_mm is a float in the populated record

HARD_RULES_CHECKED:
  - NEVER fabricate holder dimensions
  - UNKNOWN remains UNKNOWN when holder_record absent or missing fields
  - is_dispatchable=False always
  - production_released=False always
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from backend.manufacturing.verification_adapter import (
    GeometryFieldProvenance,
    build_verification_input,
    run_p8_verification,
)
from backend.tool_holders.seed_catalog import get_catalog as seed_tool_holder_catalog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_candidate(nc_segments: list | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        feature_id="test-p9b",
        toolpath_id="tp-p9b",
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


def _mock_holder(
    stable_id: str = "mock-holder",
    body_diameter_mm: float | None = None,
    gauge_length_mm: float | None = None,
    overall_length_mm: float | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        stable_id=stable_id,
        body_diameter_mm=body_diameter_mm,
        gauge_length_mm=gauge_length_mm,
        overall_length_mm=overall_length_mm,
    )


# ---------------------------------------------------------------------------
# P9-B-1: No holder_record → NOT_VERIFIABLE note
# ---------------------------------------------------------------------------


class TestNoHolderRecord:

    def test_p9b_1_no_holder_record_note(self):
        """build_verification_input without holder_record → NOT_VERIFIABLE note."""
        cand = _mock_candidate()
        vi = build_verification_input(candidate=cand)
        note_text = " ".join(vi.provenance_notes)
        assert "no holder_record supplied" in note_text.lower()

    def test_p9b_1b_no_holder_record_prov_unknown(self):
        """holder fields remain UNKNOWN when no holder_record is supplied."""
        cand = _mock_candidate()
        vi = build_verification_input(candidate=cand)
        assert vi.holder_diameter_mm is None
        assert vi.holder_diameter_provenance == GeometryFieldProvenance.UNKNOWN
        assert vi.holder_length_mm is None
        assert vi.holder_length_provenance == GeometryFieldProvenance.UNKNOWN

    def test_p9b_9_holder_diam_none_gives_not_verifiable(self):
        """run_p8_verification: holder_diam=None → holder_collision_validated=NOT_VERIFIABLE."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        vi = build_verification_input(candidate=cand)
        result = run_p8_verification(vi)
        assert result.holder_collision_validated == "NOT_VERIFIABLE"


# ---------------------------------------------------------------------------
# P9-B-2 / P9-B-3: Holder with body_diameter_mm and gauge_length_mm
# ---------------------------------------------------------------------------


class TestHolderWithDimensions:

    def test_p9b_2_body_diameter_mm_known_provenance(self):
        """holder_record.body_diameter_mm → holder_diameter_provenance=KNOWN."""
        cand = _mock_candidate()
        hr = _mock_holder(stable_id="mock-er32", body_diameter_mm=57.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        assert vi.holder_diameter_mm == pytest.approx(57.0)
        assert vi.holder_diameter_provenance == GeometryFieldProvenance.KNOWN

    def test_p9b_3_gauge_length_as_proxy_known_provenance(self):
        """holder_record.gauge_length_mm → holder_length_provenance=KNOWN with proxy note."""
        cand = _mock_candidate()
        hr = _mock_holder(stable_id="mock-er32", gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        assert vi.holder_length_mm == pytest.approx(100.0)
        assert vi.holder_length_provenance == GeometryFieldProvenance.KNOWN
        note_text = " ".join(vi.provenance_notes)
        assert "HOLDER_LENGTH_PROXY" in note_text
        assert "gauge_length_mm" in note_text

    def test_p9b_10_holder_diameter_propagated(self):
        """holder_diameter_mm propagates correctly from holder_record."""
        cand = _mock_candidate()
        hr = _mock_holder(body_diameter_mm=57.0, gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        assert vi.holder_diameter_mm == 57.0

    def test_p9b_11_holder_length_propagated(self):
        """holder_length_mm propagates correctly from gauge_length_mm proxy."""
        cand = _mock_candidate()
        hr = _mock_holder(body_diameter_mm=57.0, gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        assert vi.holder_length_mm == 100.0

    def test_p9b_15_body_diameter_is_float(self):
        """body_diameter_mm is returned as float (not int) in P8VerificationInput."""
        cand = _mock_candidate()
        hr = _mock_holder(body_diameter_mm=57, gauge_length_mm=100)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        assert isinstance(vi.holder_diameter_mm, float)
        assert isinstance(vi.holder_length_mm, float)


# ---------------------------------------------------------------------------
# P9-B-4 / P9-B-5: Missing individual fields
# ---------------------------------------------------------------------------


class TestHolderMissingFields:

    def test_p9b_4_no_body_diameter_gives_missing_note(self):
        """holder_record without body_diameter_mm → HOLDER_DIAMETER_MISSING note."""
        cand = _mock_candidate()
        hr = _mock_holder(stable_id="no-diam", body_diameter_mm=None, gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        note_text = " ".join(vi.provenance_notes)
        assert "HOLDER_DIAMETER_MISSING" in note_text
        assert "no-diam" in note_text

    def test_p9b_5_no_gauge_length_gives_missing_note(self):
        """holder_record without gauge_length_mm → HOLDER_LENGTH_MISSING note."""
        cand = _mock_candidate()
        hr = _mock_holder(stable_id="no-gauge", body_diameter_mm=57.0, gauge_length_mm=None)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        note_text = " ".join(vi.provenance_notes)
        assert "HOLDER_LENGTH_MISSING" in note_text
        assert "no-gauge" in note_text

    def test_p9b_14_holder_both_missing_gives_geometry_note(self):
        """holder_record with both fields None → HOLDER_GEOMETRY NOT_VERIFIABLE note."""
        cand = _mock_candidate()
        hr = _mock_holder(stable_id="all-missing", body_diameter_mm=None, gauge_length_mm=None)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        note_text = " ".join(vi.provenance_notes)
        assert "HOLDER_GEOMETRY" in note_text


# ---------------------------------------------------------------------------
# P9-B-6 / P9-B-7: Real holder catalog records
# ---------------------------------------------------------------------------


class TestHolderCatalogRecords:

    def setup_method(self):
        self.holders = {h.stable_id: h for h in seed_tool_holder_catalog()}

    def test_p9b_6_kennametal_er32_body_diameter(self):
        """kennametal-cat40-er32-collet-chuck: body_diameter_mm=57.0 (catalog-backed)."""
        holder_id = "kennametal-cat40-er32-collet-chuck"
        if holder_id not in self.holders:
            pytest.skip(f"Holder record {holder_id} not in catalog")
        h = self.holders[holder_id]
        assert h.body_diameter_mm == pytest.approx(57.0)
        assert h.gauge_length_mm == pytest.approx(100.0)

    def test_p9b_7_kennametal_er40_body_diameter_absent(self):
        """kennametal-cat40-er40-collet-chuck: body_diameter_mm=None (documented gap)."""
        holder_id = "kennametal-cat40-er40-collet-chuck"
        if holder_id not in self.holders:
            pytest.skip(f"Holder record {holder_id} not in catalog")
        h = self.holders[holder_id]
        assert h.body_diameter_mm is None, (
            "kennametal-cat40-er40 body_diameter_mm should remain None "
            "(insufficient catalog evidence for P9-B)"
        )

    def test_p9b_6b_er32_wired_into_adapter_body_diameter(self):
        """Wiring kennametal-cat40-er32 into adapter yields holder_diameter_mm=57.0."""
        holder_id = "kennametal-cat40-er32-collet-chuck"
        if holder_id not in self.holders:
            pytest.skip(f"Holder record {holder_id} not in catalog")
        cand = _mock_candidate()
        vi = build_verification_input(candidate=cand, holder_record=self.holders[holder_id])
        assert vi.holder_diameter_mm == pytest.approx(57.0)
        assert vi.holder_diameter_provenance == GeometryFieldProvenance.KNOWN

    def test_p9b_6c_er32_wired_into_adapter_gauge_length(self):
        """Wiring kennametal-cat40-er32 → holder_length_mm=100.0 (gauge proxy)."""
        holder_id = "kennametal-cat40-er32-collet-chuck"
        if holder_id not in self.holders:
            pytest.skip(f"Holder record {holder_id} not in catalog")
        cand = _mock_candidate()
        vi = build_verification_input(candidate=cand, holder_record=self.holders[holder_id])
        assert vi.holder_length_mm == pytest.approx(100.0)
        assert vi.holder_length_provenance == GeometryFieldProvenance.KNOWN


# ---------------------------------------------------------------------------
# P9-B-8 / P9-B-12 / P9-B-13: Safety invariants with holder data
# ---------------------------------------------------------------------------


class TestHolderSafetyInvariants:

    def test_p9b_8_holder_diam_known_enables_collision_check(self):
        """When holder_diam is known, holder_collision_validated leaves NOT_VERIFIABLE."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        hr = _mock_holder(body_diameter_mm=57.0, gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        result = run_p8_verification(vi)
        assert result.holder_collision_validated != "NOT_VERIFIABLE"

    def test_p9b_12_is_dispatchable_false_with_holder_data(self):
        """is_dispatchable must remain False even when holder geometry is fully known."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        hr = _mock_holder(body_diameter_mm=57.0, gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        result = run_p8_verification(vi)
        assert result.is_dispatchable is False

    def test_p9b_13_production_released_false_with_holder_data(self):
        """production_released must remain False even when holder geometry is known."""
        cand = _mock_candidate(nc_segments=[_seg_dict()])
        hr = _mock_holder(body_diameter_mm=57.0, gauge_length_mm=100.0)
        vi = build_verification_input(candidate=cand, holder_record=hr)
        result = run_p8_verification(vi)
        assert result.production_released is False
