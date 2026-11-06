"""Tests for backend.material_library.validation (V-MAT-01 through V-MAT-11)."""

from __future__ import annotations

from backend.material_library.enums import (
    DataConfidence,
    HardnessScale,
    MaterialCatalogStatus,
    MaterialFamily,
    MaterialISOGroup,
    MaterialSubGroup,
)
from backend.material_library.models import (
    MaterialCatalogRecord,
    MaterialCondition,
    MaterialCuttingRef,
    MaterialHardnessEntry,
    MaterialProperty,
)
from backend.material_library.validation import (
    validate_material_catalog_record,
)


def _base(
    stable_id: str = "P-TEST",
    designation: str = "TestMaterial",
    iso_group: MaterialISOGroup = MaterialISOGroup.P,
    iso_subgroup: MaterialSubGroup = MaterialSubGroup.P_STEEL,
    family: MaterialFamily = MaterialFamily.STEEL,
    status: MaterialCatalogStatus = MaterialCatalogStatus.ACTIVE,
) -> MaterialCatalogRecord:
    return MaterialCatalogRecord(
        stable_id=stable_id,
        designation=designation,
        iso_group=iso_group,
        iso_subgroup=iso_subgroup,
        material_family=family,
        status=status,
    )


class TestValidResult:
    def test_minimal_record_is_valid(self):
        result = validate_material_catalog_record(_base())
        assert result.is_valid

    def test_result_carries_stable_id(self):
        result = validate_material_catalog_record(_base(stable_id="P-C45"))
        assert result.stable_id == "P-C45"

    def test_no_issues_on_clean_record(self):
        result = validate_material_catalog_record(_base())
        assert result.issues == []


class TestVMat01StableId:
    def test_empty_stable_id_raises_issue(self):
        rec = MaterialCatalogRecord(
            stable_id="   ",
            designation="Test",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-01" in result.issue_codes


class TestVMat02Designation:
    def test_empty_designation_raises_issue(self):
        rec = MaterialCatalogRecord(
            stable_id="P-001",
            designation="   ",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-02" in result.issue_codes


class TestVMat03ISOGroup:
    def test_unknown_iso_group_on_active_raises_issue(self):
        rec = _base(iso_group=MaterialISOGroup.UNKNOWN)
        result = validate_material_catalog_record(rec)
        assert "V-MAT-03" in result.issue_codes

    def test_unknown_iso_group_on_draft_is_ok(self):
        rec = _base(
            iso_group=MaterialISOGroup.UNKNOWN,
            status=MaterialCatalogStatus.DRAFT,
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-03" not in result.issue_codes


class TestVMat04SGroupSubgroup:
    def test_s_group_with_undifferentiated_subgroup_raises(self):
        rec = _base(
            iso_group=MaterialISOGroup.S,
            iso_subgroup=MaterialSubGroup.UNKNOWN,
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-04" in result.issue_codes

    def test_s_titanium_subgroup_ok(self):
        rec = _base(
            iso_group=MaterialISOGroup.S,
            iso_subgroup=MaterialSubGroup.S_TITANIUM,
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-04" not in result.issue_codes

    def test_s_nickel_hrsa_subgroup_ok(self):
        rec = _base(
            iso_group=MaterialISOGroup.S,
            iso_subgroup=MaterialSubGroup.S_NICKEL_HRSA,
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-04" not in result.issue_codes


class TestVMat05DensityZero:
    def test_zero_density_raises_issue(self):
        rec = _base()
        rec = rec.model_copy(
            update={"properties": MaterialProperty(density_kg_m3=0.0)}
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-05" in result.issue_codes

    def test_none_density_ok(self):
        rec = _base()
        result = validate_material_catalog_record(rec)
        assert "V-MAT-05" not in result.issue_codes


class TestVMat06DensityRange:
    def test_density_too_low_raises(self):
        rec = _base()
        rec = rec.model_copy(
            update={"properties": MaterialProperty(density_kg_m3=100.0)}
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-06" in result.issue_codes

    def test_density_too_high_raises(self):
        rec = _base()
        rec = rec.model_copy(
            update={"properties": MaterialProperty(density_kg_m3=25000.0)}
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-06" in result.issue_codes

    def test_density_in_range_ok(self):
        rec = _base()
        rec = rec.model_copy(
            update={"properties": MaterialProperty(density_kg_m3=7850.0)}
        )
        result = validate_material_catalog_record(rec)
        assert "V-MAT-06" not in result.issue_codes


class TestVMat07ConditionCode:
    def test_empty_condition_code_raises(self):
        cond = MaterialCondition(condition_code="   ", condition_label="Bad")
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-07" in result.issue_codes


class TestVMat08Hardness:
    def test_zero_hardness_raises(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HB, value_min=0.0, value_max=180.0, source="Test"
        )
        cond = MaterialCondition(
            condition_code="ANNEALED", condition_label="Annealed", hardness=[h]
        )
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-08" in result.issue_codes

    def test_inverted_hardness_raises(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HB, value_min=200.0, value_max=100.0, source="Test"
        )
        cond = MaterialCondition(
            condition_code="QT", condition_label="QT", hardness=[h]
        )
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-08" in result.issue_codes

    def test_valid_hardness_ok(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HB, value_min=160.0, value_max=190.0, source="EN"
        )
        cond = MaterialCondition(
            condition_code="ANNEALED", condition_label="Annealed", hardness=[h]
        )
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-08" not in result.issue_codes


class TestVMat09StrengthPlausibility:
    def test_tensile_above_3500_raises(self):
        cond = MaterialCondition(
            condition_code="EXTREME",
            condition_label="Extreme",
            tensile_strength_mpa=4000.0,
        )
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-09" in result.issue_codes

    def test_yield_above_tensile_raises(self):
        cond = MaterialCondition(
            condition_code="INVERTED",
            condition_label="Inverted",
            tensile_strength_mpa=700.0,
            yield_strength_mpa=800.0,
        )
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-09" in result.issue_codes

    def test_valid_strength_ok(self):
        cond = MaterialCondition(
            condition_code="QT",
            condition_label="QT",
            tensile_strength_mpa=1000.0,
            yield_strength_mpa=850.0,
        )
        rec = _base()
        rec = rec.model_copy(update={"conditions": [cond]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-09" not in result.issue_codes


class TestVMat10CuttingVc:
    def test_negative_vc_min_raises(self):
        cut = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=-10.0,
            vc_max_m_min=200.0,
        )
        rec = _base()
        rec = rec.model_copy(update={"cutting_references": [cut]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-10" in result.issue_codes

    def test_zero_vc_max_raises(self):
        cut = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=100.0,
            vc_max_m_min=0.0,
        )
        rec = _base()
        rec = rec.model_copy(update={"cutting_references": [cut]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-10" in result.issue_codes

    def test_valid_vc_ok(self):
        cut = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=120.0,
            vc_max_m_min=280.0,
        )
        rec = _base()
        rec = rec.model_copy(update={"cutting_references": [cut]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-10" not in result.issue_codes


class TestVMat11CuttingEvidenceStatus:
    def test_non_reference_only_raises(self):
        cut = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=120.0,
            vc_max_m_min=280.0,
            evidence_status=DataConfidence.VERIFIED_STANDARD,
        )
        rec = _base()
        rec = rec.model_copy(update={"cutting_references": [cut]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-11" in result.issue_codes

    def test_reference_only_ok(self):
        cut = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=120.0,
            vc_max_m_min=280.0,
            evidence_status=DataConfidence.REFERENCE_ONLY,
        )
        rec = _base()
        rec = rec.model_copy(update={"cutting_references": [cut]})
        result = validate_material_catalog_record(rec)
        assert "V-MAT-11" not in result.issue_codes
