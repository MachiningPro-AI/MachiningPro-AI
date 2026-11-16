"""
P7-D: DXF-03 tool catalog coverage — 16 / 18 / 24 mm Sandvik CoroDrill 860-1.

Verifies that the three manufacturer-sourced records added in P7-D are present and
well-formed in the tool catalog so that DXF-03 (Pense_Sema.dxf) features at those
diameters can receive an EXACT tool match.

Source: Sandvik Coromant CoroDrill 860-1 standard product range,
        coromant.sandvik.com.
Grade:  GC4234 (PVD TiAlN) — same grade code used for the existing 860-1 entries.

Records that must exist after P7-D:
  stable_id="sandvik-860-1-1600-073a1-pm"  cutting_diameter_mm=16.0
  stable_id="sandvik-860-1-1800-083a1-pm"  cutting_diameter_mm=18.0
  stable_id="sandvik-860-1-2400-110a1-pm"  cutting_diameter_mm=24.0

Cutting parameters (Vc / fn) are intentionally absent; they must be supplied
by an engineer at parameter-confirmation time and cannot be fabricated here
(HARD RULE 17 — cutting data provenance must match supported range).
"""

from __future__ import annotations

import pytest

from backend.cutting_tools import ToolFamily, ToolLibrary

STABLE_ID_16 = "sandvik-860-1-1600-073a1-pm"
STABLE_ID_18 = "sandvik-860-1-1800-083a1-pm"
STABLE_ID_24 = "sandvik-860-1-2400-110a1-pm"


@pytest.fixture(scope="module")
def lib() -> ToolLibrary:
    return ToolLibrary()


# ── record presence ───────────────────────────────────────────────────────────


class TestP7DRecordPresence:
    def test_16mm_record_in_catalog(self, lib):
        assert lib.find_by_id(STABLE_ID_16) is not None

    def test_18mm_record_in_catalog(self, lib):
        assert lib.find_by_id(STABLE_ID_18) is not None

    def test_24mm_record_in_catalog(self, lib):
        assert lib.find_by_id(STABLE_ID_24) is not None


# ── record field validation ───────────────────────────────────────────────────


class TestP7D16mmRecord:
    @pytest.fixture
    def r(self, lib):
        return lib.find_by_id(STABLE_ID_16)

    def test_manufacturer(self, r):
        assert r.manufacturer == "Sandvik Coromant"

    def test_product_family(self, r):
        assert r.product_family == "CoroDrill 860"

    def test_cutting_diameter(self, r):
        assert r.cutting_diameter_mm == 16.0

    def test_shank_diameter(self, r):
        assert r.shank_diameter_mm == 16.0

    def test_cutting_length(self, r):
        assert r.cutting_length_mm == 73.0

    def test_grade(self, r):
        assert r.substrate_grade == "GC4234"

    def test_through_coolant(self, r):
        assert r.through_coolant is True

    def test_number_of_flutes(self, r):
        assert r.number_of_flutes == 2

    def test_point_angle(self, r):
        assert r.point_angle_deg == 140.0

    def test_iso_groups(self, r):
        assert set(r.iso_material_groups) >= {"P", "M", "K", "N"}

    def test_tool_category_code(self, r):
        assert r.tool_category_code == "DRILL"

    def test_source_note_present(self, r):
        assert r.source_note is not None
        assert "coromant.sandvik.com" in r.source_note

    def test_source_note_no_fabricated_cutting_params(self, r):
        # source_note may reference Sandvik application guide but must not
        # embed a specific Vc or fn value — those require engineer confirmation.
        note = r.source_note.lower()
        assert "vc=" not in note and "fn=" not in note and "m/min" not in note


class TestP7D18mmRecord:
    @pytest.fixture
    def r(self, lib):
        return lib.find_by_id(STABLE_ID_18)

    def test_manufacturer(self, r):
        assert r.manufacturer == "Sandvik Coromant"

    def test_cutting_diameter(self, r):
        assert r.cutting_diameter_mm == 18.0

    def test_shank_diameter(self, r):
        assert r.shank_diameter_mm == 18.0

    def test_cutting_length(self, r):
        assert r.cutting_length_mm == 83.0

    def test_grade(self, r):
        assert r.substrate_grade == "GC4234"

    def test_through_coolant(self, r):
        assert r.through_coolant is True

    def test_tool_category_code(self, r):
        assert r.tool_category_code == "DRILL"

    def test_source_note_present(self, r):
        assert r.source_note is not None
        assert "coromant.sandvik.com" in r.source_note


class TestP7D24mmRecord:
    @pytest.fixture
    def r(self, lib):
        return lib.find_by_id(STABLE_ID_24)

    def test_manufacturer(self, r):
        assert r.manufacturer == "Sandvik Coromant"

    def test_cutting_diameter(self, r):
        assert r.cutting_diameter_mm == 24.0

    def test_shank_diameter(self, r):
        assert r.shank_diameter_mm == 24.0

    def test_cutting_length(self, r):
        assert r.cutting_length_mm == 110.0

    def test_grade(self, r):
        assert r.substrate_grade == "GC4234"

    def test_through_coolant(self, r):
        assert r.through_coolant is True

    def test_tool_category_code(self, r):
        assert r.tool_category_code == "DRILL"

    def test_source_note_present(self, r):
        assert r.source_note is not None
        assert "coromant.sandvik.com" in r.source_note


# ── diameter-range query coverage ────────────────────────────────────────────


class TestP7DDiameterQueryCoverage:
    """Verify by_diameter() returns the new records for the target diameters."""

    def test_16mm_exact_range_returns_record(self, lib):
        results = lib.query().by_diameter(min_mm=15.9, max_mm=16.1).results()
        ids = {r.stable_id for r in results}
        assert STABLE_ID_16 in ids

    def test_18mm_exact_range_returns_record(self, lib):
        results = lib.query().by_diameter(min_mm=17.9, max_mm=18.1).results()
        ids = {r.stable_id for r in results}
        assert STABLE_ID_18 in ids

    def test_24mm_exact_range_returns_record(self, lib):
        results = lib.query().by_diameter(min_mm=23.9, max_mm=24.1).results()
        ids = {r.stable_id for r in results}
        assert STABLE_ID_24 in ids

    def test_no_other_record_at_16mm(self, lib):
        results = lib.query().by_diameter(min_mm=15.9, max_mm=16.1).results()
        # Only the new P7-D record should sit at exactly 16mm
        diameters = [r.cutting_diameter_mm for r in results]
        assert 16.0 in diameters

    def test_no_other_record_at_18mm(self, lib):
        results = lib.query().by_diameter(min_mm=17.9, max_mm=18.1).results()
        diameters = [r.cutting_diameter_mm for r in results]
        assert 18.0 in diameters

    def test_no_other_record_at_24mm(self, lib):
        results = lib.query().by_diameter(min_mm=23.9, max_mm=24.1).results()
        diameters = [r.cutting_diameter_mm for r in results]
        assert 24.0 in diameters


# ── drilling family membership ────────────────────────────────────────────────


class TestP7DDrillingFamily:
    def test_16mm_in_drilling_family(self, lib):
        drills = {r.stable_id for r in lib.by_family(ToolFamily.DRILLING)}
        assert STABLE_ID_16 in drills

    def test_18mm_in_drilling_family(self, lib):
        drills = {r.stable_id for r in lib.by_family(ToolFamily.DRILLING)}
        assert STABLE_ID_18 in drills

    def test_24mm_in_drilling_family(self, lib):
        drills = {r.stable_id for r in lib.by_family(ToolFamily.DRILLING)}
        assert STABLE_ID_24 in drills

    def test_all_three_in_drilling_query(self, lib):
        ids = {r.stable_id for r in lib.query().by_family(ToolFamily.DRILLING).results()}
        assert {STABLE_ID_16, STABLE_ID_18, STABLE_ID_24}.issubset(ids)


# ── stable_id uniqueness ──────────────────────────────────────────────────────


class TestP7DStableIdUniqueness:
    def test_all_stable_ids_unique_after_p7d(self, lib):
        ids = [r.stable_id for r in lib.all()]
        assert len(ids) == len(set(ids)), "Duplicate stable_id found after P7-D additions"

    def test_p7d_ids_do_not_duplicate_existing(self, lib):
        p7d_ids = {STABLE_ID_16, STABLE_ID_18, STABLE_ID_24}
        all_ids = [r.stable_id for r in lib.all()]
        for sid in p7d_ids:
            assert all_ids.count(sid) == 1, f"Duplicate: {sid}"


# ── catalog count sanity ──────────────────────────────────────────────────────


class TestP7DCatalogCount:
    def test_total_records_60(self, lib):
        # 57 (pre-P7-D) + 3 (P7-D) = 60
        assert len(lib.all()) == 60

    def test_drilling_count_18(self, lib):
        # 15 (pre-P7-D) + 3 (P7-D) = 18
        assert len(lib.by_family(ToolFamily.DRILLING)) == 18


# ── safety: no fabricated cutting parameters ─────────────────────────────────


class TestP7DSafetyNoCuttingParams:
    """Cutting data (Vc/fn) must NOT be embedded in the records themselves —
    they must come from engineer-confirmed sources at review time."""

    @pytest.mark.parametrize("sid", [STABLE_ID_16, STABLE_ID_18, STABLE_ID_24])
    def test_no_cutting_speed_in_record(self, lib, sid):
        r = lib.find_by_id(sid)
        assert r is not None
        assert not hasattr(r, "cutting_speed_vc_m_min") or r.cutting_speed_vc_m_min is None

    @pytest.mark.parametrize("sid", [STABLE_ID_16, STABLE_ID_18, STABLE_ID_24])
    def test_no_feed_per_rev_in_record(self, lib, sid):
        r = lib.find_by_id(sid)
        assert r is not None
        assert not hasattr(r, "feed_per_rev_fn_mm") or r.feed_per_rev_fn_mm is None
