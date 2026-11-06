"""Source/destination reconciliation tests for the Material Library seed migration.

Verifies that backend/material_library/seed_catalog.py faithfully migrated
every record from backend/materials/seed_catalog.py with no data loss.

COUNT_DISCREPANCY_EXPLANATION:
  backend/materials/seed_catalog.py docstring says "23 grades" but the actual
  Python source contains exactly 19 material_id entries.  No test in
  tests/unit/materials/ asserts the exact count 23.  The "23" was an
  aspirational/planning figure written before the module was finalised.
  There are no missing records — the source and destination are in perfect
  1-to-1 correspondence.

ISO_H_COVERAGE:
  MaterialISOGroup.H is declared in enums.py (enum member H = "H").
  The seed catalog intentionally contains no H-group records because no
  traceable commercial hardened-material data was available at MVP scope.
  FABRICATED_MATERIAL_PROPERTY=NO prohibits creating records without sources.
  The enum member exists so H-group records can be added in a future phase
  with verified data (e.g. 100Cr6, X153CrMoV12 in hardened condition).
"""

from __future__ import annotations

import pytest

from backend.material_library.enums import (
    DataConfidence,
    MaterialISOGroup,
    MaterialSubGroup,
)
from backend.material_library.seed_catalog import seed_material_library
from backend.materials.seed_catalog import seed_material_catalog

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _src_map() -> dict:
    return {r["material_id"]: r for r in seed_material_catalog()}


def _dst_map() -> dict:
    return {r.stable_id: r for r in seed_material_library()}


# ===========================================================================
# TestIDReconciliation
# ===========================================================================


class TestIDReconciliation:
    def test_source_count_is_19(self):
        assert len(seed_material_catalog()) == 19

    def test_destination_count_is_19(self):
        assert len(seed_material_library()) == 19

    def test_counts_match(self):
        assert len(seed_material_catalog()) == len(seed_material_library())

    def test_no_source_only_ids(self):
        src_ids = {r["material_id"] for r in seed_material_catalog()}
        dst_ids = {r.stable_id for r in seed_material_library()}
        assert src_ids - dst_ids == set(), (
            f"Source IDs missing from destination: {src_ids - dst_ids}"
        )

    def test_no_destination_only_ids(self):
        src_ids = {r["material_id"] for r in seed_material_catalog()}
        dst_ids = {r.stable_id for r in seed_material_library()}
        assert dst_ids - src_ids == set(), (
            f"Destination IDs not in source: {dst_ids - src_ids}"
        )

    def test_no_source_duplicates(self):
        ids = [r["material_id"] for r in seed_material_catalog()]
        assert len(ids) == len(set(ids))

    def test_no_destination_duplicates(self):
        ids = [r.stable_id for r in seed_material_library()]
        assert len(ids) == len(set(ids))

    def test_id_sets_are_identical(self):
        src_ids = {r["material_id"] for r in seed_material_catalog()}
        dst_ids = {r.stable_id for r in seed_material_library()}
        assert src_ids == dst_ids


# ===========================================================================
# TestProvenancePreservation
# ===========================================================================


class TestProvenancePreservation:
    @pytest.fixture(scope="class")
    def maps(self):
        return _src_map(), _dst_map()

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_designation_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert s["designation"] == d.designation, (
            f"{mid}: designation {s['designation']!r} != {d.designation!r}"
        )

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_iso_group_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert s["iso_group"] == d.iso_group.value

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_iso_subgroup_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert s["iso_subgroup"] == d.iso_subgroup.value

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_density_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert s.get("density_kg_m3") == d.properties.density_kg_m3

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_data_confidence_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert s.get("data_confidence") == d.source_metadata.data_confidence.value

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_source_document_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert s.get("source_document") == d.source_metadata.source_document

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_condition_count_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert len(s.get("conditions", [])) == len(d.conditions)

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_tool_compat_count_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert len(s.get("tool_compatibility", [])) == len(d.tool_compatibility)

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_cutting_ref_count_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        assert len(s.get("cutting_references", [])) == len(d.cutting_references)


# ===========================================================================
# TestConditionProvenancePreservation
# ===========================================================================


class TestConditionProvenancePreservation:
    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_condition_codes_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        src_codes = [c["condition_code"] for c in s.get("conditions", [])]
        dst_codes = [c.condition_code for c in d.conditions]
        assert src_codes == dst_codes

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_tensile_strength_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for sc, dc in zip(s.get("conditions", []), d.conditions, strict=True):
            assert sc.get("tensile_strength_mpa") == dc.tensile_strength_mpa

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_yield_strength_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for sc, dc in zip(s.get("conditions", []), d.conditions, strict=True):
            assert sc.get("yield_strength_mpa") == dc.yield_strength_mpa

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_hardness_values_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for sc, dc in zip(s.get("conditions", []), d.conditions, strict=True):
            for sh, dh in zip(sc.get("hardness", []), dc.hardness, strict=True):
                assert sh["scale"] == dh.scale.value
                assert sh["value_min"] == dh.value_min
                assert sh["value_max"] == dh.value_max

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_condition_sources_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for sc, dc in zip(s.get("conditions", []), d.conditions, strict=True):
            assert sc.get("source", "") == dc.source


# ===========================================================================
# TestCuttingDataProvenancePreservation
# ===========================================================================


class TestCuttingDataProvenancePreservation:
    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_cutting_evidence_reference_only(self, mid):
        d = _dst_map()[mid]
        for cut in d.cutting_references:
            assert cut.evidence_status is DataConfidence.REFERENCE_ONLY

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_vc_min_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for sc, dc in zip(s.get("cutting_references", []), d.cutting_references, strict=True):
            assert sc.get("vc_min_m_min") == dc.vc_min_m_min

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_vc_max_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for sc, dc in zip(s.get("cutting_references", []), d.cutting_references, strict=True):
            assert sc.get("vc_max_m_min") == dc.vc_max_m_min


# ===========================================================================
# TestToolCompatProvenancePreservation
# ===========================================================================


class TestToolCompatProvenancePreservation:
    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_tool_materials_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        src_mats = [tc["tool_material"] for tc in s.get("tool_compatibility", [])]
        dst_mats = [tc.tool_material for tc in d.tool_compatibility]
        assert src_mats == dst_mats

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_ratings_preserved(self, mid):
        s = _src_map()[mid]
        d = _dst_map()[mid]
        for st, dt in zip(s.get("tool_compatibility", []), d.tool_compatibility, strict=True):
            assert st["rating"] == dt.rating

    @pytest.mark.parametrize("mid", [r["material_id"] for r in seed_material_catalog()])
    def test_compat_evidence_reference_only(self, mid):
        d = _dst_map()[mid]
        for tc in d.tool_compatibility:
            assert tc.evidence_status is DataConfidence.REFERENCE_ONLY


# ===========================================================================
# TestCountDiscrepancyExplanation
# ===========================================================================


class TestCountDiscrepancyExplanation:
    def test_source_docstring_says_23_but_source_has_19(self):
        import inspect
        import re

        from backend.materials import seed_catalog as sc_mod
        src_text = inspect.getsource(sc_mod)
        actual_ids = re.findall(r'"material_id":\s*"([^"]+)"', src_text)
        docstring = sc_mod.__doc__ or ""
        assert "23" in docstring, "Expected docstring to still reference 23"
        assert len(actual_ids) == 19, (
            f"Expected 19 actual material_id entries in source; found {len(actual_ids)}"
        )

    def test_source_tests_do_not_assert_count_23(self):
        import pathlib
        test_text = pathlib.Path(
            "tests/unit/materials/test_seed.py"
        ).read_text(encoding="utf-8")
        assert "== 23" not in test_text, (
            "Source tests assert exactly 23 — reconciliation may need revision"
        )

    def test_no_records_were_silently_dropped(self):
        src_ids = {r["material_id"] for r in seed_material_catalog()}
        dst_ids = {r.stable_id for r in seed_material_library()}
        assert src_ids == dst_ids, "Records were silently dropped during migration"


# ===========================================================================
# TestISOHCoverage
# ===========================================================================


class TestISOHCoverage:
    def test_iso_h_enum_member_exists(self):
        assert MaterialISOGroup.H.value == "H"

    def test_iso_h_subgroup_enum_exists(self):
        assert MaterialSubGroup.H_HARDENED.value == "H_HARDENED"

    def test_no_seed_records_in_iso_h(self):
        h_records = [
            r for r in seed_material_library()
            if r.iso_group is MaterialISOGroup.H
        ]
        assert len(h_records) == 0, (
            "ISO H seed records were added — verify they have cited sources"
        )

    def test_iso_h_absence_is_intentional_not_migration_loss(self):
        src_h = [
            r for r in seed_material_catalog()
            if r.get("iso_group") == "H"
        ]
        assert len(src_h) == 0, (
            "Source has ISO H records that were not migrated"
        )
