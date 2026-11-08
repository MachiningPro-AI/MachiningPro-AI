"""Tests for backend.material_library.enums."""

from __future__ import annotations

from backend.material_library.enums import (
    DataConfidence,
    EvidenceGrade,
    HardnessScale,
    MaterialCatalogStatus,
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)


class TestMaterialISOGroup:
    def test_all_six_iso_groups_present(self):
        values = {g.value for g in MaterialISOGroup}
        for g in ("P", "M", "K", "N", "S", "H"):
            assert g in values

    def test_unknown_present(self):
        assert MaterialISOGroup.UNKNOWN.value == "UNKNOWN"

    def test_p_is_steel(self):
        assert MaterialISOGroup.P == "P"

    def test_m_is_stainless(self):
        assert MaterialISOGroup.M == "M"

    def test_s_group_exists(self):
        assert MaterialISOGroup.S == "S"

    def test_h_group_exists(self):
        assert MaterialISOGroup.H == "H"

    def test_enum_count(self):
        assert len(MaterialISOGroup) == 7  # P M K N S H UNKNOWN


class TestMaterialSubGroup:
    def test_p_steel_present(self):
        assert MaterialSubGroup.P_STEEL.value == "P_STEEL"

    def test_m_stainless_present(self):
        assert MaterialSubGroup.M_STAINLESS.value == "M_STAINLESS"

    def test_k_cast_iron_present(self):
        assert MaterialSubGroup.K_CAST_IRON.value == "K_CAST_IRON"

    def test_n_aluminum_present(self):
        assert MaterialSubGroup.N_ALUMINUM.value == "N_ALUMINUM"

    def test_n_copper_present(self):
        assert MaterialSubGroup.N_COPPER.value == "N_COPPER"

    def test_s_titanium_present(self):
        assert MaterialSubGroup.S_TITANIUM.value == "S_TITANIUM"

    def test_s_nickel_hrsa_present(self):
        assert MaterialSubGroup.S_NICKEL_HRSA.value == "S_NICKEL_HRSA"

    def test_h_hardened_present(self):
        assert MaterialSubGroup.H_HARDENED.value == "H_HARDENED"

    def test_unknown_present(self):
        assert MaterialSubGroup.UNKNOWN.value == "UNKNOWN"


class TestMaterialFamily:
    def test_steel_present(self):
        assert MaterialFamily.STEEL.value == "steel"

    def test_stainless_steel_present(self):
        assert MaterialFamily.STAINLESS_STEEL.value == "stainless_steel"

    def test_cast_iron_present(self):
        assert MaterialFamily.CAST_IRON.value == "cast_iron"

    def test_aluminum_present(self):
        assert MaterialFamily.ALUMINUM.value == "aluminum"

    def test_copper_alloy_present(self):
        assert MaterialFamily.COPPER_ALLOY.value == "copper_alloy"

    def test_titanium_present(self):
        assert MaterialFamily.TITANIUM.value == "titanium"

    def test_nickel_alloy_present(self):
        assert MaterialFamily.NICKEL_ALLOY.value == "nickel_alloy"

    def test_unknown_present(self):
        assert MaterialFamily.UNKNOWN.value == "UNKNOWN"


class TestEvidenceGrade:
    def test_manufacturer_datasheet(self):
        assert EvidenceGrade.MANUFACTURER_DATASHEET == "MANUFACTURER_DATASHEET"

    def test_literature_reference(self):
        assert EvidenceGrade.LITERATURE_REFERENCE == "LITERATURE_REFERENCE"

    def test_estimated(self):
        assert EvidenceGrade.ESTIMATED == "ESTIMATED"

    def test_unknown(self):
        assert EvidenceGrade.UNKNOWN == "UNKNOWN"

    def test_six_grades_present(self):
        assert len(EvidenceGrade) == 6


class TestDataConfidence:
    def test_verified_standard(self):
        assert DataConfidence.VERIFIED_STANDARD == "VERIFIED_STANDARD"

    def test_reference_only(self):
        assert DataConfidence.REFERENCE_ONLY == "REFERENCE_ONLY"

    def test_general_industry(self):
        assert DataConfidence.GENERAL_INDUSTRY == "GENERAL_INDUSTRY"

    def test_unknown(self):
        assert DataConfidence.UNKNOWN == "UNKNOWN"

    def test_four_values(self):
        assert len(DataConfidence) == 4


class TestHardnessScale:
    def test_hb(self):
        assert HardnessScale.HB == "HB"

    def test_hrc(self):
        assert HardnessScale.HRC == "HRC"

    def test_hrb(self):
        assert HardnessScale.HRB == "HRB"

    def test_hv(self):
        assert HardnessScale.HV == "HV"

    def test_four_scales(self):
        assert len(HardnessScale) == 4


class TestMaterialCatalogStatus:
    def test_active(self):
        assert MaterialCatalogStatus.ACTIVE == "ACTIVE"

    def test_draft(self):
        assert MaterialCatalogStatus.DRAFT == "DRAFT"

    def test_deprecated(self):
        assert MaterialCatalogStatus.DEPRECATED == "DEPRECATED"
