"""Tests for the Material Library seed catalog (19 migrated grades)."""

from __future__ import annotations

from backend.material_library.enums import (
    DataConfidence,
    MaterialCatalogStatus,
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)
from backend.material_library.registry import MaterialCatalogRegistry
from backend.material_library.seed_catalog import seed_material_library
from backend.material_library.validation import validate_material_catalog_record


class TestSeedStructure:
    def test_record_count(self):
        records = seed_material_library()
        assert len(records) >= 19

    def test_stable_ids_unique(self):
        records = seed_material_library()
        ids = [r.stable_id for r in records]
        assert len(ids) == len(set(ids)), "Duplicate stable_id in seed"

    def test_all_p_m_k_n_s_groups_present(self):
        records = seed_material_library()
        groups = {r.iso_group for r in records}
        for g in (
            MaterialISOGroup.P,
            MaterialISOGroup.M,
            MaterialISOGroup.K,
            MaterialISOGroup.N,
            MaterialISOGroup.S,
        ):
            assert g in groups, f"ISO group {g.value} missing from seed"

    def test_p_group_has_at_least_four_steels(self):
        records = seed_material_library()
        p = [r for r in records if r.iso_group is MaterialISOGroup.P]
        assert len(p) >= 4

    def test_m_group_has_at_least_two_stainless(self):
        records = seed_material_library()
        m = [r for r in records if r.iso_group is MaterialISOGroup.M]
        assert len(m) >= 2

    def test_s_group_has_both_ti_and_ni(self):
        records = seed_material_library()
        s = [r for r in records if r.iso_group is MaterialISOGroup.S]
        subgroups = {r.iso_subgroup for r in s}
        assert MaterialSubGroup.S_TITANIUM in subgroups
        assert MaterialSubGroup.S_NICKEL_HRSA in subgroups

    def test_n_group_has_aluminum_and_copper(self):
        records = seed_material_library()
        n = [r for r in records if r.iso_group is MaterialISOGroup.N]
        subgroups = {r.iso_subgroup for r in n}
        assert MaterialSubGroup.N_ALUMINUM in subgroups
        assert MaterialSubGroup.N_COPPER in subgroups

    def test_all_records_active(self):
        records = seed_material_library()
        for rec in records:
            assert rec.status is MaterialCatalogStatus.ACTIVE, (
                f"{rec.stable_id} has status {rec.status} — seed records should be ACTIVE"
            )


class TestSeedDataIntegrity:
    def test_no_zero_density(self):
        for rec in seed_material_library():
            assert rec.properties.density_kg_m3 != 0.0, (
                f"{rec.stable_id} density=0.0 — use None"
            )

    def test_density_plausible_when_present(self):
        for rec in seed_material_library():
            d = rec.properties.density_kg_m3
            if d is not None:
                assert 1500 <= d <= 22000, (
                    f"{rec.stable_id} density {d} out of range"
                )

    def test_no_fabricated_tensile_strength(self):
        for rec in seed_material_library():
            for cond in rec.conditions:
                ts = cond.tensile_strength_mpa
                if ts is not None:
                    assert ts <= 3500, (
                        f"{rec.stable_id} Rm={ts} > 3500 MPa — likely fabricated"
                    )

    def test_hardness_ranges_not_inverted(self):
        for rec in seed_material_library():
            for cond in rec.conditions:
                for h in cond.hardness:
                    assert h.value_min <= h.value_max, (
                        f"{rec.stable_id} inverted hardness range"
                    )

    def test_hardness_values_positive(self):
        for rec in seed_material_library():
            for cond in rec.conditions:
                for h in cond.hardness:
                    assert h.value_min > 0
                    assert h.value_max > 0

    def test_all_records_pass_validation(self):
        for rec in seed_material_library():
            result = validate_material_catalog_record(rec)
            assert result.is_valid, (
                f"{rec.stable_id} validation failed: {result.issue_codes}"
            )


class TestKnownRecordsPresent:
    def _get(self, stable_id: str):
        records = {r.stable_id: r for r in seed_material_library()}
        return records.get(stable_id)

    def test_p_c45_present(self):
        assert self._get("P-C45") is not None

    def test_p_42crmo4_present(self):
        assert self._get("P-42CrMo4") is not None

    def test_m_304_present(self):
        assert self._get("M-304") is not None

    def test_m_316l_present(self):
        assert self._get("M-316L") is not None

    def test_k_gjl250_present(self):
        assert self._get("K-GJL-250") is not None

    def test_n_6061_t6_present(self):
        assert self._get("N-6061-T6") is not None

    def test_n_cw614n_present(self):
        assert self._get("N-CW614N") is not None

    def test_s_ti64_present(self):
        assert self._get("S-Ti64") is not None

    def test_s_in718_present(self):
        assert self._get("S-IN718") is not None


class TestKnownRecordValues:
    def _get(self, stable_id: str):
        records = {r.stable_id: r for r in seed_material_library()}
        return records[stable_id]

    def test_c45_annealed_hb(self):
        rec = self._get("P-C45")
        annealed = next(
            (c for c in rec.conditions if c.condition_code == "ANNEALED"), None
        )
        assert annealed is not None
        hb = next((h for h in annealed.hardness if h.scale.value == "HB"), None)
        assert hb is not None
        assert hb.value_min == 160.0
        assert hb.value_max == 190.0

    def test_c45_qt_strength(self):
        rec = self._get("P-C45")
        qt = next((c for c in rec.conditions if c.condition_code == "QT"), None)
        assert qt is not None
        assert qt.tensile_strength_mpa == 700.0
        assert qt.yield_strength_mpa == 490.0

    def test_ti64_hrc_hardness(self):
        rec = self._get("S-Ti64")
        annealed = next(
            (c for c in rec.conditions if c.condition_code == "ANNEALED"), None
        )
        assert annealed is not None
        hrc = next((h for h in annealed.hardness if h.scale.value == "HRC"), None)
        assert hrc is not None
        assert hrc.value_min == 30.0
        assert hrc.value_max == 36.0

    def test_in718_subgroup(self):
        rec = self._get("S-IN718")
        assert rec.iso_subgroup is MaterialSubGroup.S_NICKEL_HRSA

    def test_m_304_density(self):
        rec = self._get("M-304")
        assert rec.properties.density_kg_m3 == 7930.0

    def test_n_6061_family(self):
        rec = self._get("N-6061-T6")
        assert rec.material_family is MaterialFamily.ALUMINUM


class TestSeedCuttingData:
    def test_all_cutting_refs_reference_only(self):
        for rec in seed_material_library():
            for cut in rec.cutting_references:
                assert cut.evidence_status is DataConfidence.REFERENCE_ONLY, (
                    f"{rec.stable_id} cutting ref missing REFERENCE_ONLY"
                )

    def test_vc_ranges_positive(self):
        for rec in seed_material_library():
            for cut in rec.cutting_references:
                if cut.vc_min_m_min is not None:
                    assert cut.vc_min_m_min > 0
                if cut.vc_max_m_min is not None:
                    assert cut.vc_max_m_min > 0

    def test_titanium_vc_low(self):
        records = {r.stable_id: r for r in seed_material_library()}
        ti = records["S-Ti64"]
        for cut in ti.cutting_references:
            if cut.operation == "turning" and cut.tool_material == "carbide":
                assert cut.vc_max_m_min <= 100


class TestSeedToolCompat:
    def test_all_tool_compat_reference_only(self):
        for rec in seed_material_library():
            for tc in rec.tool_compatibility:
                assert tc.evidence_status is DataConfidence.REFERENCE_ONLY, (
                    f"{rec.stable_id} tool compat missing REFERENCE_ONLY"
                )

    def test_p_carbide_recommended(self):
        records = {r.stable_id: r for r in seed_material_library()}
        p_rec = records["P-C45"]
        carbide = next(
            (tc for tc in p_rec.tool_compatibility if tc.tool_material == "carbide"),
            None,
        )
        assert carbide is not None
        assert carbide.rating == "RECOMMENDED"

    def test_titanium_hss_not_recommended(self):
        records = {r.stable_id: r for r in seed_material_library()}
        ti = records["S-Ti64"]
        hss = next(
            (tc for tc in ti.tool_compatibility if tc.tool_material == "HSS"), None
        )
        assert hss is not None
        assert hss.rating == "NOT_RECOMMENDED"


class TestSeedRegistry:
    def test_seed_loads_into_registry(self):
        reg = MaterialCatalogRegistry(seed_material_library())
        assert len(reg) >= 19

    def test_registry_lookup_p_c45(self):
        reg = MaterialCatalogRegistry(seed_material_library())
        rec = reg.get("P-C45")
        assert rec is not None
        assert rec.designation == "C45"

    def test_registry_p_group_count(self):
        reg = MaterialCatalogRegistry(seed_material_library())
        p_records = reg.by_iso_group(MaterialISOGroup.P)
        assert len(p_records) >= 4

    def test_registry_alias_lookup(self):
        reg = MaterialCatalogRegistry(seed_material_library())
        result = reg.find_by_alias("4140")
        assert len(result) >= 1

    def test_registry_no_duplicates(self):
        # Should not raise MaterialCatalogError
        reg = MaterialCatalogRegistry(seed_material_library())
        assert len(reg) == len(seed_material_library())
