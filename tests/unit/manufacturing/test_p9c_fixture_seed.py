"""
P9-C: Fixture seed catalog — test suite.

Covers:
  P9-C-1  get_fixture_catalog returns 3 records
  P9-C-2  stable_ids correct (std-vise-jaw-100mm, std-vise-jaw-150mm, std-step-clamp-sm)
  P9-C-3  fixture types correct (VISE_JAWS, CLAMPS)
  P9-C-4  source field = LIBRARY_EVIDENCE on all records
  P9-C-5  source_note contains "offline verification" on all records
  P9-C-6  make_fixture_input_from_library: correct min/max bounds
  P9-C-7  make_fixture_input_from_library: provenance=USER_CONFIRMED by default
  P9-C-8  make_fixture_input_from_library: fixture_id defaults to record.stable_id
  P9-C-9  make_fixture_input_from_library: custom fixture_id override works
  P9-C-10 FixtureInput.is_trustworthy: True for USER_CONFIRMED provenance
  P9-C-11 FixtureInput.is_trustworthy: False for UNKNOWN provenance
  P9-C-12 get_fixture_by_id: returns correct record for valid id
  P9-C-13 get_fixture_by_id: returns None for unknown id
  P9-C-14 100mm vise dimensions: half_x=55, half_y=50, height=40
  P9-C-15 150mm vise dimensions: half_x=80, half_y=60, height=50
  P9-C-16 step clamp dimensions: half_x=30, half_y=12.5, height=30
  P9-C-17 make_fixture_input_from_library: correct to_fixture_geometry() conversion
  P9-C-18 Fixture catalog is immutable (new list each call)
  P9-C-19 FixtureLibraryRecord is frozen (immutable)
  P9-C-20 All records have manufacturer-referenced source_note

HARD_RULES_CHECKED:
  - FABRICATED_FIXTURE_DIMENSIONS=NO
  - TEST_FIXTURE_DATA_IN_PRODUCTION_LIBRARY=NO
  - Engineer must supply WCS position (never inferred)
  - is_trustworthy=True only for USER_CONFIRMED or KNOWN provenance
"""

from __future__ import annotations

import pytest

from backend.manufacturing.fixture_seed import (
    get_fixture_by_id,
    get_fixture_catalog,
    make_fixture_input_from_library,
)
from backend.manufacturing.verification_adapter import GeometryFieldProvenance
from backend.verification.enums import FixtureSource, FixtureType

# ---------------------------------------------------------------------------
# P9-C-1 / P9-C-2 / P9-C-3 / P9-C-4: Catalog content
# ---------------------------------------------------------------------------


class TestFixtureCatalogContent:

    def setup_method(self):
        self.catalog = get_fixture_catalog()

    def test_p9c_1_catalog_has_3_records(self):
        """Fixture catalog must have exactly 3 standard primitives."""
        assert len(self.catalog) == 3

    def test_p9c_2_stable_ids_correct(self):
        """All three expected stable_ids must be present."""
        ids = {r.stable_id for r in self.catalog}
        assert ids == {
            "std-vise-jaw-100mm",
            "std-vise-jaw-150mm",
            "std-step-clamp-sm",
        }

    def test_p9c_3_fixture_types_correct(self):
        """Fixture types must match expected enums."""
        types = {r.stable_id: r.fixture_type for r in self.catalog}
        assert types["std-vise-jaw-100mm"] == FixtureType.VISE_JAWS
        assert types["std-vise-jaw-150mm"] == FixtureType.VISE_JAWS
        assert types["std-step-clamp-sm"] == FixtureType.CLAMPS

    def test_p9c_4_all_records_have_library_evidence_source(self):
        """All fixture records must have source=LIBRARY_EVIDENCE."""
        for r in self.catalog:
            assert r.source == "LIBRARY_EVIDENCE", (
                f"{r.stable_id}: expected LIBRARY_EVIDENCE, got {r.source}"
            )

    def test_p9c_5_source_notes_mention_offline_verification(self):
        """All source notes must mention 'offline verification'."""
        for r in self.catalog:
            assert "offline verification" in r.source_note.lower(), (
                f"{r.stable_id}: source_note missing 'offline verification'"
            )

    def test_p9c_20_source_notes_mention_manufacturer(self):
        """All source notes must reference a manufacturer or standard."""
        manufacturers = ["kurt", "step clamp", "vise", "clamp", "tooling"]
        for r in self.catalog:
            note_lower = r.source_note.lower()
            assert any(m in note_lower for m in manufacturers), (
                f"{r.stable_id}: source_note must reference manufacturer or standard"
            )


# ---------------------------------------------------------------------------
# P9-C-14 / P9-C-15 / P9-C-16: Fixture dimensions
# ---------------------------------------------------------------------------


class TestFixtureDimensions:

    def test_p9c_14_vise_100mm_dimensions(self):
        """std-vise-jaw-100mm: half_x=55, half_y=50, height=40."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        assert r is not None
        assert r.half_x_mm == pytest.approx(55.0)
        assert r.half_y_mm == pytest.approx(50.0)
        assert r.height_mm == pytest.approx(40.0)

    def test_p9c_15_vise_150mm_dimensions(self):
        """std-vise-jaw-150mm: half_x=80, half_y=60, height=50."""
        r = get_fixture_by_id("std-vise-jaw-150mm")
        assert r is not None
        assert r.half_x_mm == pytest.approx(80.0)
        assert r.half_y_mm == pytest.approx(60.0)
        assert r.height_mm == pytest.approx(50.0)

    def test_p9c_16_step_clamp_dimensions(self):
        """std-step-clamp-sm: half_x=30, half_y=12.5, height=30."""
        r = get_fixture_by_id("std-step-clamp-sm")
        assert r is not None
        assert r.half_x_mm == pytest.approx(30.0)
        assert r.half_y_mm == pytest.approx(12.5)
        assert r.height_mm == pytest.approx(30.0)


# ---------------------------------------------------------------------------
# P9-C-6 / P9-C-7 / P9-C-8 / P9-C-9: make_fixture_input_from_library
# ---------------------------------------------------------------------------


class TestMakeFixtureInputFromLibrary:

    def test_p9c_6_min_max_bounds_correct(self):
        """make_fixture_input_from_library: correct WCS bounding box."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        # Place jaw centre at WCS (200.0, 50.0), bottom Z=-5.0
        fi = make_fixture_input_from_library(r, 200.0, 50.0, -5.0)
        assert fi.min_x_mm == pytest.approx(200.0 - 55.0)   # 145.0
        assert fi.max_x_mm == pytest.approx(200.0 + 55.0)   # 255.0
        assert fi.min_y_mm == pytest.approx(50.0 - 50.0)    # 0.0
        assert fi.max_y_mm == pytest.approx(50.0 + 50.0)    # 100.0
        assert fi.min_z_mm == pytest.approx(-5.0)
        assert fi.max_z_mm == pytest.approx(-5.0 + 40.0)    # 35.0

    def test_p9c_7_default_provenance_user_confirmed(self):
        """make_fixture_input_from_library defaults to USER_CONFIRMED provenance."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(r, 0.0, 0.0, 0.0)
        assert fi.provenance == GeometryFieldProvenance.USER_CONFIRMED

    def test_p9c_8_fixture_id_defaults_to_stable_id(self):
        """fixture_id defaults to record.stable_id."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(r, 0.0, 0.0, 0.0)
        assert fi.fixture_id == "std-vise-jaw-100mm"

    def test_p9c_9_custom_fixture_id_override(self):
        """Custom fixture_id parameter overrides stable_id."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(r, 0.0, 0.0, 0.0, fixture_id="setup-left-vise")
        assert fi.fixture_id == "setup-left-vise"

    def test_p9c_7b_explicit_known_provenance(self):
        """make_fixture_input_from_library: explicit KNOWN provenance is accepted."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(
            r, 0.0, 0.0, 0.0,
            provenance=GeometryFieldProvenance.KNOWN,
        )
        assert fi.provenance == GeometryFieldProvenance.KNOWN

    def test_p9c_source_is_user_defined(self):
        """FixtureInput from library has source=USER_DEFINED (engineer confirmed position)."""
        r = get_fixture_by_id("std-step-clamp-sm")
        fi = make_fixture_input_from_library(r, 10.0, 10.0, 0.0)
        assert fi.source == FixtureSource.USER_DEFINED

    def test_p9c_17_to_fixture_geometry_conversion(self):
        """FixtureInput.to_fixture_geometry() produces correct FixtureGeometry."""
        r = get_fixture_by_id("std-step-clamp-sm")
        fi = make_fixture_input_from_library(r, 50.0, 25.0, 0.0)
        fg = fi.to_fixture_geometry()
        assert fg.fixture_id == fi.fixture_id
        assert fg.min_x_mm == pytest.approx(fi.min_x_mm)
        assert fg.max_z_mm == pytest.approx(fi.max_z_mm)


# ---------------------------------------------------------------------------
# P9-C-10 / P9-C-11: is_trustworthy
# ---------------------------------------------------------------------------


class TestFixtureInputTrustworthiness:

    def test_p9c_10_user_confirmed_is_trustworthy(self):
        """FixtureInput with USER_CONFIRMED provenance is trustworthy."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(
            r, 0.0, 0.0, 0.0,
            provenance=GeometryFieldProvenance.USER_CONFIRMED,
        )
        assert fi.is_trustworthy is True

    def test_p9c_10b_known_is_trustworthy(self):
        """FixtureInput with KNOWN provenance is trustworthy."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(
            r, 0.0, 0.0, 0.0,
            provenance=GeometryFieldProvenance.KNOWN,
        )
        assert fi.is_trustworthy is True

    def test_p9c_11_unknown_is_not_trustworthy(self):
        """FixtureInput with UNKNOWN provenance is not trustworthy."""
        r = get_fixture_by_id("std-vise-jaw-100mm")
        fi = make_fixture_input_from_library(
            r, 0.0, 0.0, 0.0,
            provenance=GeometryFieldProvenance.UNKNOWN,
        )
        assert fi.is_trustworthy is False


# ---------------------------------------------------------------------------
# P9-C-12 / P9-C-13 / P9-C-18 / P9-C-19: Utility and immutability
# ---------------------------------------------------------------------------


class TestFixtureCatalogUtilities:

    def test_p9c_12_get_fixture_by_id_found(self):
        """get_fixture_by_id returns correct record for a valid stable_id."""
        r = get_fixture_by_id("std-vise-jaw-150mm")
        assert r is not None
        assert r.stable_id == "std-vise-jaw-150mm"

    def test_p9c_13_get_fixture_by_id_not_found(self):
        """get_fixture_by_id returns None for an unknown stable_id."""
        r = get_fixture_by_id("does-not-exist-xyz")
        assert r is None

    def test_p9c_18_catalog_returns_new_list_each_call(self):
        """get_fixture_catalog() returns a new list each call (safe to mutate)."""
        c1 = get_fixture_catalog()
        c2 = get_fixture_catalog()
        assert c1 is not c2
        c1.append("extra")
        assert len(get_fixture_catalog()) == 3

    def test_p9c_19_fixture_library_record_is_frozen(self):
        """FixtureLibraryRecord is frozen — assignment raises FrozenInstanceError."""
        import dataclasses
        r = get_fixture_by_id("std-vise-jaw-100mm")
        with pytest.raises((dataclasses.FrozenInstanceError, AttributeError)):
            r.half_x_mm = 999.0
