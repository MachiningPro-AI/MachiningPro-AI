"""Tests for backend.material_library.models."""

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
from backend.material_library.models import (
    MachinabilityProfile,
    MaterialCatalogRecord,
    MaterialCondition,
    MaterialCuttingRef,
    MaterialDesignation,
    MaterialHardnessEntry,
    MaterialProperty,
    MaterialSourceMetadata,
    MaterialToolCompatEntry,
)


def _minimal_record() -> MaterialCatalogRecord:
    return MaterialCatalogRecord(
        stable_id="TEST-001",
        designation="TestMaterial",
        iso_group=MaterialISOGroup.P,
        iso_subgroup=MaterialSubGroup.P_STEEL,
        material_family=MaterialFamily.STEEL,
    )


class TestMaterialHardnessEntry:
    def test_hb_construction(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HB,
            value_min=160.0,
            value_max=190.0,
            source="EN 10083-1",
        )
        assert h.scale is HardnessScale.HB
        assert h.value_min == 160.0
        assert h.value_max == 190.0

    def test_hrc_construction(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HRC,
            value_min=30.0,
            value_max=36.0,
            source="AMS 4928",
        )
        assert h.scale is HardnessScale.HRC

    def test_default_confidence_verified(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HV,
            value_min=200.0,
            value_max=250.0,
            source="Test",
        )
        assert h.confidence is DataConfidence.VERIFIED_STANDARD


class TestMaterialCondition:
    def test_minimal_condition(self):
        c = MaterialCondition(condition_code="ANNEALED", condition_label="Annealed")
        assert c.condition_code == "ANNEALED"
        assert c.hardness == []
        assert c.tensile_strength_mpa is None
        assert c.yield_strength_mpa is None
        assert c.elongation_pct is None

    def test_full_condition(self):
        h = MaterialHardnessEntry(
            scale=HardnessScale.HB,
            value_min=160.0,
            value_max=190.0,
            source="EN",
        )
        c = MaterialCondition(
            condition_code="QT",
            condition_label="Quenched & Tempered",
            hardness=[h],
            tensile_strength_mpa=700.0,
            yield_strength_mpa=490.0,
            elongation_pct=14.0,
        )
        assert len(c.hardness) == 1
        assert c.tensile_strength_mpa == 700.0

    def test_none_values_allowed(self):
        c = MaterialCondition(
            condition_code="UNKNOWN_STATE",
            condition_label="Unknown",
            tensile_strength_mpa=None,
        )
        assert c.tensile_strength_mpa is None


class TestMaterialDesignation:
    def test_all_none_defaults(self):
        d = MaterialDesignation()
        assert d.werkstoff_nr is None
        assert d.standard_en is None
        assert d.aliases == []

    def test_full_designation(self):
        d = MaterialDesignation(
            werkstoff_nr="1.7225",
            standard_en="42CrMo4",
            standard_din="42CrMo4",
            standard_aisi="4140",
            standard_uns=None,
            aliases=["4140", "1.7225"],
        )
        assert d.werkstoff_nr == "1.7225"
        assert "4140" in d.aliases


class TestMaterialProperty:
    def test_all_none_by_default(self):
        p = MaterialProperty()
        assert p.density_kg_m3 is None
        assert p.elastic_modulus_gpa is None
        assert p.thermal_conductivity_w_mk is None

    def test_density_set(self):
        p = MaterialProperty(density_kg_m3=7850.0)
        assert p.density_kg_m3 == 7850.0

    def test_missing_is_none_not_zero(self):
        p = MaterialProperty(density_kg_m3=None)
        assert p.density_kg_m3 is None


class TestMachinabilityProfile:
    def test_minimal_construction(self):
        m = MachinabilityProfile()
        assert m.chip_formation is None
        assert m.work_hardening is None

    def test_full_profile(self):
        m = MachinabilityProfile(
            chip_formation="CONTINUOUS",
            work_hardening="LOW",
            bue_tendency="LOW",
            abrasiveness="LOW",
            thermal_load="LOW",
            cutting_force="MODERATE",
        )
        assert m.chip_formation == "CONTINUOUS"
        assert m.cutting_force == "MODERATE"

    def test_default_evidence_reference_only(self):
        m = MachinabilityProfile()
        assert m.evidence_status is DataConfidence.REFERENCE_ONLY

    def test_notes_allowed(self):
        m = MachinabilityProfile(notes="Keep vc conservative.")
        assert "conservative" in m.notes


class TestMaterialToolCompatEntry:
    def test_minimal(self):
        e = MaterialToolCompatEntry(tool_material="carbide", rating="RECOMMENDED")
        assert e.tool_material == "carbide"
        assert e.rating == "RECOMMENDED"
        assert e.condition_notes is None

    def test_conditional_with_notes(self):
        e = MaterialToolCompatEntry(
            tool_material="ceramic",
            rating="CONDITIONAL",
            condition_notes="High speed only",
        )
        assert e.condition_notes == "High speed only"

    def test_default_evidence(self):
        e = MaterialToolCompatEntry(tool_material="HSS", rating="ACCEPTABLE")
        assert e.evidence_status is DataConfidence.REFERENCE_ONLY


class TestMaterialCuttingRef:
    def test_minimal(self):
        c = MaterialCuttingRef(
            operation="turning",
            tool_material="carbide",
            vc_min_m_min=120.0,
            vc_max_m_min=280.0,
        )
        assert c.vc_min_m_min == 120.0
        assert c.fn_min_mm_rev is None

    def test_default_evidence(self):
        c = MaterialCuttingRef(operation="milling", tool_material="carbide")
        assert c.evidence_status is DataConfidence.REFERENCE_ONLY


class TestMaterialSourceMetadata:
    def test_defaults(self):
        m = MaterialSourceMetadata()
        assert m.data_confidence is DataConfidence.VERIFIED_STANDARD
        assert m.source_document == ""
        assert m.notes is None

    def test_with_document(self):
        m = MaterialSourceMetadata(
            source_document="EN 10083-1:2006",
            evidence_grade=EvidenceGrade.LITERATURE_REFERENCE,
        )
        assert m.source_document == "EN 10083-1:2006"


class TestMaterialCatalogRecord:
    def test_minimal_record(self):
        r = _minimal_record()
        assert r.stable_id == "TEST-001"
        assert r.iso_group is MaterialISOGroup.P
        assert r.conditions == []
        assert r.machinability is None
        assert r.tool_compatibility == []
        assert r.cutting_references == []

    def test_default_status_active(self):
        r = _minimal_record()
        assert r.status is MaterialCatalogStatus.ACTIVE

    def test_default_properties_none(self):
        r = _minimal_record()
        assert r.properties.density_kg_m3 is None

    def test_with_conditions(self):
        r = MaterialCatalogRecord(
            stable_id="P-TEST",
            designation="Test",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            conditions=[
                MaterialCondition(
                    condition_code="ANNEALED",
                    condition_label="Annealed",
                    tensile_strength_mpa=700.0,
                )
            ],
        )
        assert len(r.conditions) == 1
        assert r.conditions[0].tensile_strength_mpa == 700.0

    def test_unknown_iso_group_allowed(self):
        r = MaterialCatalogRecord(
            stable_id="DRAFT-001",
            designation="Draft",
            iso_group=MaterialISOGroup.UNKNOWN,
            iso_subgroup=MaterialSubGroup.UNKNOWN,
            material_family=MaterialFamily.UNKNOWN,
            status=MaterialCatalogStatus.DRAFT,
        )
        assert r.iso_group is MaterialISOGroup.UNKNOWN
