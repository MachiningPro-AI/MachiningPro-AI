"""Tests for backend.material_library.registry."""

from __future__ import annotations

import pytest

from backend.material_library.enums import (
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)
from backend.material_library.models import MaterialCatalogRecord, MaterialDesignation
from backend.material_library.registry import MaterialCatalogError, MaterialCatalogRegistry


def _rec(
    stable_id: str,
    designation: str,
    iso_group: MaterialISOGroup = MaterialISOGroup.P,
    iso_subgroup: MaterialSubGroup = MaterialSubGroup.P_STEEL,
    family: MaterialFamily = MaterialFamily.STEEL,
    aliases: list[str] | None = None,
) -> MaterialCatalogRecord:
    return MaterialCatalogRecord(
        stable_id=stable_id,
        designation=designation,
        iso_group=iso_group,
        iso_subgroup=iso_subgroup,
        material_family=family,
        designation_detail=MaterialDesignation(aliases=aliases or []),
    )


class TestRegistryCreation:
    def test_empty_registry(self):
        reg = MaterialCatalogRegistry([])
        assert len(reg) == 0

    def test_single_record(self):
        reg = MaterialCatalogRegistry([_rec("P-001", "Steel A")])
        assert len(reg) == 1

    def test_multiple_records(self):
        records = [_rec(f"P-{i:03d}", f"Steel {i}") for i in range(5)]
        reg = MaterialCatalogRegistry(records)
        assert len(reg) == 5

    def test_duplicate_stable_id_raises(self):
        with pytest.raises(MaterialCatalogError):
            MaterialCatalogRegistry([
                _rec("DUPE", "A"),
                _rec("DUPE", "B"),
            ])


class TestRegistryGet:
    def test_get_existing(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        rec = reg.get("P-C45")
        assert rec is not None
        assert rec.designation == "C45"

    def test_get_missing_returns_none(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert reg.get("NONEXISTENT") is None

    def test_get_empty_string_returns_none(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert reg.get("") is None

    def test_get_case_sensitive(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert reg.get("p-c45") is None
        assert reg.get("P-C45") is not None


class TestRegistryAll:
    def test_all_returns_all_records(self):
        records = [_rec(f"P-{i:03d}", f"Steel {i}") for i in range(3)]
        reg = MaterialCatalogRegistry(records)
        result = reg.all()
        assert len(result) == 3

    def test_all_returns_copy(self):
        records = [_rec("P-001", "Steel")]
        reg = MaterialCatalogRegistry(records)
        result = reg.all()
        result.clear()
        assert len(reg) == 1


class TestRegistryByISOGroup:
    def test_by_iso_group_p(self):
        reg = MaterialCatalogRegistry([
            _rec("P-001", "Steel", iso_group=MaterialISOGroup.P),
            _rec("M-001", "Stainless",
                 iso_group=MaterialISOGroup.M,
                 iso_subgroup=MaterialSubGroup.M_STAINLESS,
                 family=MaterialFamily.STAINLESS_STEEL),
        ])
        p_records = reg.by_iso_group(MaterialISOGroup.P)
        assert len(p_records) == 1
        assert p_records[0].stable_id == "P-001"

    def test_by_iso_group_empty(self):
        reg = MaterialCatalogRegistry([_rec("P-001", "Steel")])
        assert reg.by_iso_group(MaterialISOGroup.S) == []

    def test_by_iso_group_multiple(self):
        reg = MaterialCatalogRegistry([
            _rec("P-001", "Steel A"),
            _rec("P-002", "Steel B"),
        ])
        assert len(reg.by_iso_group(MaterialISOGroup.P)) == 2


class TestRegistryBySubgroup:
    def test_by_subgroup_s_titanium(self):
        reg = MaterialCatalogRegistry([
            _rec("S-Ti64", "Ti-6Al-4V",
                 iso_group=MaterialISOGroup.S,
                 iso_subgroup=MaterialSubGroup.S_TITANIUM,
                 family=MaterialFamily.TITANIUM),
            _rec("S-IN718", "Inconel 718",
                 iso_group=MaterialISOGroup.S,
                 iso_subgroup=MaterialSubGroup.S_NICKEL_HRSA,
                 family=MaterialFamily.NICKEL_ALLOY),
        ])
        ti = reg.by_subgroup(MaterialSubGroup.S_TITANIUM)
        assert len(ti) == 1
        assert ti[0].stable_id == "S-Ti64"

    def test_by_subgroup_empty(self):
        reg = MaterialCatalogRegistry([_rec("P-001", "Steel")])
        assert reg.by_subgroup(MaterialSubGroup.H_HARDENED) == []


class TestRegistryByFamily:
    def test_by_family_aluminum(self):
        reg = MaterialCatalogRegistry([
            _rec("N-6061", "Al 6061",
                 iso_group=MaterialISOGroup.N,
                 iso_subgroup=MaterialSubGroup.N_ALUMINUM,
                 family=MaterialFamily.ALUMINUM),
            _rec("P-001", "Steel"),
        ])
        al = reg.by_family(MaterialFamily.ALUMINUM)
        assert len(al) == 1
        assert al[0].stable_id == "N-6061"

    def test_by_family_empty(self):
        reg = MaterialCatalogRegistry([_rec("P-001", "Steel")])
        assert reg.by_family(MaterialFamily.TITANIUM) == []


class TestRegistryFindByAlias:
    def test_find_by_primary_designation(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        result = reg.find_by_alias("C45")
        assert len(result) == 1
        assert result[0].stable_id == "P-C45"

    def test_find_by_alias_case_insensitive(self):
        reg = MaterialCatalogRegistry([
            _rec("P-C45", "C45", aliases=["1045", "Ck45"]),
        ])
        assert len(reg.find_by_alias("ck45")) == 1
        assert len(reg.find_by_alias("CK45")) == 1

    def test_find_by_werkstoff_alias(self):
        reg = MaterialCatalogRegistry([
            _rec("M-304", "X5CrNi18-10", aliases=["1.4301", "304"]),
        ])
        result = reg.find_by_alias("1.4301")
        assert len(result) == 1

    def test_find_by_alias_no_match(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert reg.find_by_alias("NONEXISTENT") == []

    def test_find_by_alias_multiple_matches(self):
        reg = MaterialCatalogRegistry([
            _rec("P-C45", "C45", aliases=["1045"]),
            _rec("P-Ck45", "Ck45", aliases=["1045"]),
        ])
        result = reg.find_by_alias("1045")
        assert len(result) == 2


class TestRegistryContains:
    def test_contains_existing(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert "P-C45" in reg

    def test_not_contains_missing(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert "MISSING" not in reg

    def test_contains_non_string(self):
        reg = MaterialCatalogRegistry([_rec("P-C45", "C45")])
        assert 42 not in reg


class TestRegistryRepr:
    def test_repr_shows_count(self):
        reg = MaterialCatalogRegistry([_rec("P-001", "Steel")])
        assert "1" in repr(reg)
