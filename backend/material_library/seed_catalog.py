"""Seed material catalog — 19 grades migrated from EPIC_01_MATERIAL_INTELLIGENCE_FOUNDATION.

Sources
-------
Hardness : EN 10083-1:2006, EN 10083-3:2006, EN 10084:2008, EN 1561:2011,
           EN 1563:2011, EN 10088-2:2014, ASTM B209, AMS 4928, AMS 5662/5664
Strength : EN 10025:2004, EN 10083 series, ASTM A240, ASTM A564, AMS 5643
Density  : Smithells Metals Reference Book, 5th ed.
Cutting  : Programlar Kesici Takımlar synthesis — REFERENCE_ONLY, NOT OEM values
Compat   : Programlar Sandvik matrix synthesis — REFERENCE_ONLY

FABRICATED_MATERIAL_PROPERTY=NO
FABRICATED_CUTTING_PARAMETER=NO
FABRICATED_TOOL_COMPATIBILITY=NO
CUTTING_ENVELOPE_IS_NOT_OEM_SPEC=YES
CUSTOMER_PROPRIETARY_DATA_COMMITTED=NO
"""

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

__all__ = ["seed_material_library"]

# ---------------------------------------------------------------------------
# Hardness helpers
# ---------------------------------------------------------------------------

_STD_EN10083 = "EN 10083-1:2006 / EN 10083-3:2006"


def _hb(
    lo: float,
    hi: float,
    src: str = _STD_EN10083,
) -> list[MaterialHardnessEntry]:
    return [
        MaterialHardnessEntry(
            scale=HardnessScale.HB,
            value_min=lo,
            value_max=hi,
            confidence=DataConfidence.VERIFIED_STANDARD,
            source=src,
        )
    ]


def _hrc(lo: float, hi: float, src: str) -> list[MaterialHardnessEntry]:
    return [
        MaterialHardnessEntry(
            scale=HardnessScale.HRC,
            value_min=lo,
            value_max=hi,
            confidence=DataConfidence.VERIFIED_STANDARD,
            source=src,
        )
    ]


# ---------------------------------------------------------------------------
# Tool compatibility helpers (REFERENCE_ONLY, Programlar Sandvik synthesis)
# ---------------------------------------------------------------------------

def _tc(mat: str, rating: str, notes: str | None = None) -> MaterialToolCompatEntry:
    return MaterialToolCompatEntry(
        tool_material=mat,
        rating=rating,
        condition_notes=notes,
        evidence_status=DataConfidence.REFERENCE_ONLY,
        source="Programlar Sandvik synthesis",
    )


def _p_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc("carbide", "RECOMMENDED"),
        _tc("HSS", "ACCEPTABLE"),
        _tc("cermet", "ACCEPTABLE"),
        _tc(
            "ceramic", "CONDITIONAL",
            "High cutting speed only; brittle interruptions risk edge fracture",
        ),
        _tc(
            "CBN", "CONDITIONAL",
            "Suited for hardened steel (>45 HRC); not for soft P steel",
        ),
        _tc(
            "PCD", "NOT_RECOMMENDED",
            "PCD reacts with iron in steel — chemical wear",
        ),
    ]


def _m_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc("carbide", "RECOMMENDED"),
        _tc(
            "HSS", "CONDITIONAL",
            "Low speed only; work hardening limits tool life",
        ),
        _tc("cermet", "ACCEPTABLE"),
        _tc(
            "ceramic", "CONDITIONAL",
            "Avoid interrupted cuts; suitable for continuous turning",
        ),
        _tc("CBN", "CONDITIONAL", "Only for hardened grades >50 HRC"),
        _tc("PCD", "NOT_RECOMMENDED"),
    ]


def _k_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc("carbide", "RECOMMENDED"),
        _tc("ceramic", "RECOMMENDED", "High productivity; SiC or Al2O3"),
        _tc("CBN", "RECOMMENDED", "High-speed dry machining of grey CI"),
        _tc("HSS", "ACCEPTABLE"),
        _tc("cermet", "CONDITIONAL"),
        _tc("PCD", "NOT_RECOMMENDED"),
    ]


def _n_al_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc("carbide", "RECOMMENDED"),
        _tc(
            "PCD", "RECOMMENDED",
            "Preferred for high-Si alloys (>=9% Si) — reduces BUE",
        ),
        _tc("HSS", "ACCEPTABLE"),
        _tc("cermet", "CONDITIONAL"),
        _tc("ceramic", "NOT_RECOMMENDED", "Adhesion wear; not suitable for Al"),
        _tc("CBN", "NOT_RECOMMENDED"),
    ]


def _n_cu_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc("carbide", "RECOMMENDED"),
        _tc("HSS", "ACCEPTABLE"),
        _tc("PCD", "ACCEPTABLE"),
        _tc("cermet", "CONDITIONAL"),
        _tc("ceramic", "NOT_RECOMMENDED"),
        _tc("CBN", "NOT_RECOMMENDED"),
    ]


def _s_ti_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc(
            "carbide", "RECOMMENDED",
            "Sharp edges, positive geometry, flood coolant required",
        ),
        _tc(
            "HSS", "NOT_RECOMMENDED",
            "Thermal load exceeds HSS capability in production",
        ),
        _tc("cermet", "NOT_RECOMMENDED"),
        _tc(
            "ceramic", "CONDITIONAL",
            "SiAlON for continuous turning only; no interrupted cuts",
        ),
        _tc("CBN", "NOT_RECOMMENDED", "CBN reacts with Ti above 800 deg C"),
        _tc(
            "PCD", "CONDITIONAL",
            "Low-speed only; PCD degrades rapidly above 400 deg C in Ti",
        ),
    ]


def _s_ni_compat() -> list[MaterialToolCompatEntry]:
    return [
        _tc(
            "carbide", "RECOMMENDED",
            "Coated submicron carbide; positive geometry essential",
        ),
        _tc("HSS", "NOT_RECOMMENDED", "Insufficient hot hardness for Inconel"),
        _tc("cermet", "NOT_RECOMMENDED"),
        _tc(
            "ceramic", "CONDITIONAL",
            "SiAlON ceramic for continuous turning; highest vc possible",
        ),
        _tc(
            "CBN", "NOT_RECOMMENDED",
            "CBN is brittle in high-work-hardening HRSA interrupted cuts",
        ),
        _tc("PCD", "NOT_RECOMMENDED"),
    ]


# ---------------------------------------------------------------------------
# Cutting reference helpers (REFERENCE_ONLY)
# ---------------------------------------------------------------------------

def _cut(
    op: str,
    mat: str,
    vc_min: float,
    vc_max: float,
    fn_min: float | None = None,
    fn_max: float | None = None,
    fz_min: float | None = None,
    fz_max: float | None = None,
    ap_min: float | None = None,
    ap_max: float | None = None,
) -> MaterialCuttingRef:
    return MaterialCuttingRef(
        operation=op,
        tool_material=mat,
        vc_min_m_min=vc_min,
        vc_max_m_min=vc_max,
        fn_min_mm_rev=fn_min,
        fn_max_mm_rev=fn_max,
        fz_min_mm_tooth=fz_min,
        fz_max_mm_tooth=fz_max,
        ap_min_mm=ap_min,
        ap_max_mm=ap_max,
        evidence_status=DataConfidence.REFERENCE_ONLY,
        source="Programlar general industry envelope",
    )


def _p_cuts() -> list[MaterialCuttingRef]:
    return [
        _cut("turning", "carbide", 120.0, 280.0,
             fn_min=0.10, fn_max=0.45, ap_min=0.5, ap_max=4.0),
        _cut("milling", "carbide", 150.0, 300.0,
             fz_min=0.05, fz_max=0.20),
        _cut("drilling", "carbide", 80.0, 180.0,
             fn_min=0.05, fn_max=0.25),
    ]


def _m_cuts() -> list[MaterialCuttingRef]:
    return [
        _cut("turning", "carbide", 70.0, 180.0,
             fn_min=0.08, fn_max=0.30, ap_min=0.4, ap_max=3.0),
    ]


def _k_cuts() -> list[MaterialCuttingRef]:
    return [
        _cut("turning", "carbide", 140.0, 320.0,
             fn_min=0.10, fn_max=0.50),
    ]


def _n_al_cuts() -> list[MaterialCuttingRef]:
    return [
        _cut("turning", "carbide", 300.0, 1000.0,
             fn_min=0.10, fn_max=0.50),
    ]


def _s_ti_cuts() -> list[MaterialCuttingRef]:
    return [
        _cut("turning", "carbide", 35.0, 90.0,
             fn_min=0.05, fn_max=0.25),
    ]


def _s_ni_cuts() -> list[MaterialCuttingRef]:
    return [
        _cut("turning", "carbide", 20.0, 70.0,
             fn_min=0.05, fn_max=0.20),
    ]


# ---------------------------------------------------------------------------
# Machinability profile helpers (REFERENCE_ONLY)
# ---------------------------------------------------------------------------

def _p_mach(chip: str = "CONTINUOUS") -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation=chip,
        work_hardening="LOW",
        bue_tendency="LOW",
        abrasiveness="LOW",
        thermal_load="LOW",
        cutting_force="MODERATE",
    )


def _m_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="CONTINUOUS",
        work_hardening="HIGH",
        bue_tendency="MODERATE",
        abrasiveness="LOW",
        thermal_load="MODERATE",
        cutting_force="HIGH",
        coolant_guidance=(
            "Flood coolant essential; prevent work hardening "
            "by maintaining cutting engagement"
        ),
    )


def _k_grey_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="POWDER",
        work_hardening="LOW",
        bue_tendency="LOW",
        abrasiveness="HIGH",
        thermal_load="LOW",
        cutting_force="LOW",
        coolant_guidance=(
            "Dry machining acceptable; compressed air for chip evacuation"
        ),
    )


def _k_ductile_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="SEGMENTED",
        work_hardening="LOW",
        bue_tendency="LOW",
        abrasiveness="MODERATE",
        thermal_load="LOW",
        cutting_force="MODERATE",
    )


def _n_al_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="CONTINUOUS",
        work_hardening="LOW",
        bue_tendency="MODERATE",
        abrasiveness="LOW",
        thermal_load="LOW",
        cutting_force="LOW",
        coolant_guidance=(
            "Flood coolant or MQL for long-chipping alloys; "
            "PCD preferred for high-Si"
        ),
    )


def _n_cu_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="CONTINUOUS",
        work_hardening="LOW",
        bue_tendency="LOW",
        abrasiveness="LOW",
        thermal_load="LOW",
        cutting_force="LOW",
    )


def _s_ti_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="SEGMENTED",
        work_hardening="MODERATE",
        bue_tendency="HIGH",
        abrasiveness="LOW",
        thermal_load="HIGH",
        cutting_force="HIGH",
        tool_wear_rate="HIGH",
        coolant_guidance=(
            "High-pressure flood coolant mandatory; "
            "minimum 70 bar through-tool recommended"
        ),
        notes=(
            "Low thermal conductivity traps heat at cutting edge. "
            "Keep vc conservative."
        ),
    )


def _s_ni_mach() -> MachinabilityProfile:
    return MachinabilityProfile(
        chip_formation="SEGMENTED",
        work_hardening="VERY_HIGH",
        bue_tendency="HIGH",
        abrasiveness="HIGH",
        thermal_load="EXTREME",
        cutting_force="VERY_HIGH",
        tool_wear_rate="VERY_HIGH",
        coolant_guidance=(
            "High-pressure flood coolant or through-tool; do not interrupt cut"
        ),
        notes=(
            "Inconel 718 is among the most difficult materials to machine. "
            "Never allow rubbing — maintain continuous chip formation."
        ),
    )


# ---------------------------------------------------------------------------
# Source metadata helper
# ---------------------------------------------------------------------------

def _src(doc: str, notes: str | None = None) -> MaterialSourceMetadata:
    return MaterialSourceMetadata(
        data_confidence=DataConfidence.VERIFIED_STANDARD,
        source_document=doc,
        evidence_grade=EvidenceGrade.LITERATURE_REFERENCE,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Seed records
# ---------------------------------------------------------------------------

def seed_material_library() -> list[MaterialCatalogRecord]:
    """Return all 19 migrated material records.

    All values are sourced; None where no traceable source is available.
    Cutting envelopes and tool compatibility are REFERENCE_ONLY.
    """
    return [

        # ── ISO P — Steels ────────────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="P-C45",
            designation="C45",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.0503",
                standard_en="C45",
                standard_din="C45",
                standard_aisi="1045",
                aliases=["1045", "C45E", "1.0503", "Ck45"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="ANNEALED",
                    condition_label="Annealed",
                    hardness=_hb(160.0, 190.0, "EN 10083-1:2006"),
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10083-1:2006",
                ),
                MaterialCondition(
                    condition_code="QT",
                    condition_label="Quenched & Tempered",
                    hardness=_hb(230.0, 270.0, "EN 10083-1:2006"),
                    tensile_strength_mpa=700.0,
                    yield_strength_mpa=490.0,
                    elongation_pct=14.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10083-1:2006",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10083-1:2006"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-42CrMo4",
            designation="42CrMo4",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.7225",
                standard_en="42CrMo4",
                standard_din="42CrMo4",
                standard_aisi="4140",
                aliases=["4140", "42CrMoS4", "1.7225", "SCM440"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="ANNEALED",
                    condition_label="Annealed",
                    hardness=_hb(190.0, 225.0, "EN 10083-3:2006"),
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10083-3:2006",
                ),
                MaterialCondition(
                    condition_code="QT_850_600",
                    condition_label="Q+T (850 deg C / 600 deg C)",
                    hardness=_hb(260.0, 310.0, "EN 10083-3:2006"),
                    tensile_strength_mpa=1000.0,
                    yield_strength_mpa=850.0,
                    elongation_pct=12.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10083-3:2006",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10083-3:2006"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-16MnCr5",
            designation="16MnCr5",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.7131",
                standard_en="16MnCr5",
                standard_din="16MnCr5",
                standard_aisi="5115",
                aliases=["5115", "1.7131"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="CASE_HARDENED",
                    condition_label="Case-hardened (carburized)",
                    hardness=[
                        MaterialHardnessEntry(
                            scale=HardnessScale.HRC,
                            value_min=58.0,
                            value_max=62.0,
                            confidence=DataConfidence.GENERAL_INDUSTRY,
                            source="General industry — case depth dependent",
                        )
                    ],
                    confidence=DataConfidence.GENERAL_INDUSTRY,
                    source="General industry",
                ),
                MaterialCondition(
                    condition_code="NORMALIZED",
                    condition_label="Normalized",
                    hardness=_hb(156.0, 207.0, "EN 10084:2008"),
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10084:2008",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10084:2008"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-20MnCr5",
            designation="20MnCr5",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.7147",
                standard_en="20MnCr5",
                standard_din="20MnCr5",
                standard_aisi="5120",
                aliases=["5120", "1.7147"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="NORMALIZED",
                    condition_label="Normalized",
                    hardness=_hb(156.0, 207.0, "EN 10084:2008"),
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10084:2008",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10084:2008"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-S355JR",
            designation="S355JR",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.0045",
                standard_en="S355JR",
                standard_din="St52-3",
                standard_aisi=None,
                aliases=["1.0045", "St52-3", "A572 Gr.50"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="AS_ROLLED",
                    condition_label="As-rolled / normalized",
                    hardness=_hb(143.0, 178.0, "EN 10025-2:2004"),
                    tensile_strength_mpa=510.0,
                    yield_strength_mpa=355.0,
                    elongation_pct=22.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10025-2:2004",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10025-2:2004"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-S355J2",
            designation="S355J2",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.0570",
                standard_en="S355J2",
                standard_din="St52-3N",
                standard_aisi=None,
                aliases=["1.0570", "S355J2G3"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="NORMALIZED",
                    condition_label="Normalized",
                    hardness=_hb(143.0, 178.0, "EN 10025-2:2004"),
                    tensile_strength_mpa=510.0,
                    yield_strength_mpa=355.0,
                    elongation_pct=22.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10025-2:2004",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10025-2:2004"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-S235JR",
            designation="S235JR",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.0037",
                standard_en="S235JR",
                standard_din="St37-2",
                standard_aisi="A36",
                aliases=["1.0037", "St37-2", "A36"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="AS_ROLLED",
                    condition_label="As-rolled",
                    hardness=_hb(105.0, 131.0, "EN 10025-2:2004"),
                    tensile_strength_mpa=400.0,
                    yield_strength_mpa=235.0,
                    elongation_pct=26.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10025-2:2004",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src("EN 10025-2:2004"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="P-Ck45",
            designation="Ck45",
            iso_group=MaterialISOGroup.P,
            iso_subgroup=MaterialSubGroup.P_STEEL,
            material_family=MaterialFamily.STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.1191",
                standard_en="C45E",
                standard_din="Ck45",
                standard_aisi="1045",
                aliases=["C45E", "1.1191", "1045"],
            ),
            properties=MaterialProperty(density_kg_m3=7850.0),
            conditions=[
                MaterialCondition(
                    condition_code="ANNEALED",
                    condition_label="Annealed",
                    hardness=_hb(160.0, 190.0, "EN 10083-1:2006"),
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10083-1:2006",
                ),
                MaterialCondition(
                    condition_code="QT",
                    condition_label="Quenched & Tempered",
                    hardness=_hb(230.0, 270.0, "EN 10083-1:2006"),
                    tensile_strength_mpa=700.0,
                    yield_strength_mpa=490.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10083-1:2006",
                ),
            ],
            machinability=_p_mach(),
            tool_compatibility=_p_compat(),
            cutting_references=_p_cuts(),
            source_metadata=_src(
                "EN 10083-1:2006",
                notes=(
                    "Ck45 (1.1191) is the unalloyed variant of C45 (1.0503) "
                    "with tighter S/P limits."
                ),
            ),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        # ── ISO M — Stainless Steels ──────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="M-304",
            designation="X5CrNi18-10",
            iso_group=MaterialISOGroup.M,
            iso_subgroup=MaterialSubGroup.M_STAINLESS,
            material_family=MaterialFamily.STAINLESS_STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.4301",
                standard_en="X5CrNi18-10",
                standard_din="X5CrNi18-10",
                standard_aisi="304",
                standard_uns="S30400",
                aliases=["304", "1.4301", "AISI 304", "SS304"],
            ),
            properties=MaterialProperty(density_kg_m3=7930.0),
            conditions=[
                MaterialCondition(
                    condition_code="SOLUTION_ANNEALED",
                    condition_label="Solution annealed",
                    hardness=_hb(130.0, 180.0, "EN 10088-2:2014"),
                    tensile_strength_mpa=515.0,
                    yield_strength_mpa=205.0,
                    elongation_pct=40.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10088-2:2014 / ASTM A240",
                ),
            ],
            machinability=_m_mach(),
            tool_compatibility=_m_compat(),
            cutting_references=_m_cuts(),
            source_metadata=_src("EN 10088-2:2014 / ASTM A240"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="M-316L",
            designation="X2CrNiMo17-12-2",
            iso_group=MaterialISOGroup.M,
            iso_subgroup=MaterialSubGroup.M_STAINLESS,
            material_family=MaterialFamily.STAINLESS_STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.4404",
                standard_en="X2CrNiMo17-12-2",
                standard_din="X2CrNiMo17-12-2",
                standard_aisi="316L",
                standard_uns="S31603",
                aliases=["316L", "1.4404", "AISI 316L"],
            ),
            properties=MaterialProperty(density_kg_m3=8000.0),
            conditions=[
                MaterialCondition(
                    condition_code="SOLUTION_ANNEALED",
                    condition_label="Solution annealed",
                    hardness=_hb(130.0, 175.0, "EN 10088-2:2014"),
                    tensile_strength_mpa=485.0,
                    yield_strength_mpa=170.0,
                    elongation_pct=40.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 10088-2:2014 / ASTM A240",
                ),
            ],
            machinability=_m_mach(),
            tool_compatibility=_m_compat(),
            cutting_references=_m_cuts(),
            source_metadata=_src("EN 10088-2:2014 / ASTM A240"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="M-17-4PH",
            designation="X5CrNiCuNb17-4",
            iso_group=MaterialISOGroup.M,
            iso_subgroup=MaterialSubGroup.M_STAINLESS,
            material_family=MaterialFamily.STAINLESS_STEEL,
            designation_detail=MaterialDesignation(
                werkstoff_nr="1.4542",
                standard_en="X5CrNiCuNb17-4",
                standard_din=None,
                standard_aisi="630",
                standard_uns="S17400",
                aliases=["17-4PH", "630", "1.4542", "SUS630"],
            ),
            properties=MaterialProperty(density_kg_m3=7780.0),
            conditions=[
                MaterialCondition(
                    condition_code="H900",
                    condition_label="Condition H900 (aged 482 deg C)",
                    hardness=_hrc(40.0, 44.0, "ASTM A564 / AMS 5643"),
                    tensile_strength_mpa=1310.0,
                    yield_strength_mpa=1170.0,
                    elongation_pct=10.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="ASTM A564 / AMS 5643",
                ),
                MaterialCondition(
                    condition_code="H1025",
                    condition_label="Condition H1025 (aged 552 deg C)",
                    hardness=_hrc(33.0, 38.0, "ASTM A564 / AMS 5643"),
                    tensile_strength_mpa=1070.0,
                    yield_strength_mpa=1000.0,
                    elongation_pct=12.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="ASTM A564 / AMS 5643",
                ),
            ],
            machinability=_m_mach(),
            tool_compatibility=_m_compat(),
            cutting_references=_m_cuts(),
            source_metadata=_src("ASTM A564 / AMS 5643"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        # ── ISO K — Cast Irons ────────────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="K-GJL-250",
            designation="EN-GJL-250",
            iso_group=MaterialISOGroup.K,
            iso_subgroup=MaterialSubGroup.K_CAST_IRON,
            material_family=MaterialFamily.CAST_IRON,
            designation_detail=MaterialDesignation(
                werkstoff_nr="EN-GJL-250",
                standard_en="EN-GJL-250",
                standard_din="GG25",
                standard_aisi="Class 30",
                aliases=["GG25", "GJL-250", "Grey Cast Iron 250", "FC250"],
            ),
            properties=MaterialProperty(density_kg_m3=7150.0),
            conditions=[
                MaterialCondition(
                    condition_code="AS_CAST",
                    condition_label="As-cast",
                    hardness=_hb(180.0, 230.0, "EN 1561:2011"),
                    tensile_strength_mpa=250.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 1561:2011",
                ),
            ],
            machinability=_k_grey_mach(),
            tool_compatibility=_k_compat(),
            cutting_references=_k_cuts(),
            source_metadata=_src("EN 1561:2011"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="K-GJS-400",
            designation="EN-GJS-400-15",
            iso_group=MaterialISOGroup.K,
            iso_subgroup=MaterialSubGroup.K_CAST_IRON,
            material_family=MaterialFamily.CAST_IRON,
            designation_detail=MaterialDesignation(
                werkstoff_nr="EN-GJS-400-15",
                standard_en="EN-GJS-400-15",
                standard_din="GGG40",
                standard_aisi="Grade 60-40-18",
                aliases=["GGG40", "GJS-400", "Ductile Iron 400", "FCD400"],
            ),
            properties=MaterialProperty(density_kg_m3=7100.0),
            conditions=[
                MaterialCondition(
                    condition_code="AS_CAST",
                    condition_label="As-cast",
                    hardness=_hb(130.0, 175.0, "EN 1563:2011"),
                    tensile_strength_mpa=400.0,
                    yield_strength_mpa=250.0,
                    elongation_pct=15.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 1563:2011",
                ),
            ],
            machinability=_k_ductile_mach(),
            tool_compatibility=_k_compat(),
            cutting_references=_k_cuts(),
            source_metadata=_src("EN 1563:2011"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        # ── ISO N — Aluminum ──────────────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="N-6061-T6",
            designation="AlMg1SiCu",
            iso_group=MaterialISOGroup.N,
            iso_subgroup=MaterialSubGroup.N_ALUMINUM,
            material_family=MaterialFamily.ALUMINUM,
            designation_detail=MaterialDesignation(
                werkstoff_nr=None,
                standard_en="EN AW-6061",
                standard_din="AlMg1SiCu",
                standard_aisi="6061",
                standard_uns="A96061",
                aliases=["6061-T6", "6061", "EN AW-6061", "AA6061"],
            ),
            properties=MaterialProperty(density_kg_m3=2700.0),
            conditions=[
                MaterialCondition(
                    condition_code="T6",
                    condition_label="T6 — Solution heat treated, artificially aged",
                    hardness=_hb(95.0, 100.0, "ASTM B209 / AMS 2770"),
                    tensile_strength_mpa=310.0,
                    yield_strength_mpa=276.0,
                    elongation_pct=12.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="ASTM B209 / ASTM B221",
                ),
            ],
            machinability=_n_al_mach(),
            tool_compatibility=_n_al_compat(),
            cutting_references=_n_al_cuts(),
            source_metadata=_src("ASTM B209 / ASTM B221"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="N-6082-T6",
            designation="AlSi1MgMn",
            iso_group=MaterialISOGroup.N,
            iso_subgroup=MaterialSubGroup.N_ALUMINUM,
            material_family=MaterialFamily.ALUMINUM,
            designation_detail=MaterialDesignation(
                werkstoff_nr=None,
                standard_en="EN AW-6082",
                standard_din="AlSi1MgMn",
                standard_aisi="6082",
                standard_uns="A96082",
                aliases=["6082-T6", "6082", "EN AW-6082", "AA6082"],
            ),
            properties=MaterialProperty(density_kg_m3=2700.0),
            conditions=[
                MaterialCondition(
                    condition_code="T6",
                    condition_label="T6 — Solution heat treated, artificially aged",
                    hardness=_hb(90.0, 105.0, "EN 485-2:2016"),
                    tensile_strength_mpa=310.0,
                    yield_strength_mpa=260.0,
                    elongation_pct=10.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 485-2:2016",
                ),
            ],
            machinability=_n_al_mach(),
            tool_compatibility=_n_al_compat(),
            cutting_references=_n_al_cuts(),
            source_metadata=_src("EN 485-2:2016"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        MaterialCatalogRecord(
            stable_id="N-7075-T6",
            designation="AlZnMgCu1.5",
            iso_group=MaterialISOGroup.N,
            iso_subgroup=MaterialSubGroup.N_ALUMINUM,
            material_family=MaterialFamily.ALUMINUM,
            designation_detail=MaterialDesignation(
                werkstoff_nr=None,
                standard_en="EN AW-7075",
                standard_din="AlZnMgCu1.5",
                standard_aisi="7075",
                standard_uns="A97075",
                aliases=["7075-T6", "7075", "EN AW-7075", "AA7075"],
            ),
            properties=MaterialProperty(density_kg_m3=2810.0),
            conditions=[
                MaterialCondition(
                    condition_code="T6",
                    condition_label="T6 — Solution heat treated, artificially aged",
                    hardness=_hb(135.0, 150.0, "ASTM B209"),
                    tensile_strength_mpa=503.0,
                    yield_strength_mpa=434.0,
                    elongation_pct=11.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="ASTM B209",
                ),
            ],
            machinability=_n_al_mach(),
            tool_compatibility=_n_al_compat(),
            cutting_references=_n_al_cuts(),
            source_metadata=_src("ASTM B209"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        # ── ISO N — Copper ────────────────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="N-CW614N",
            designation="CuZn39Pb3",
            iso_group=MaterialISOGroup.N,
            iso_subgroup=MaterialSubGroup.N_COPPER,
            material_family=MaterialFamily.COPPER_ALLOY,
            designation_detail=MaterialDesignation(
                werkstoff_nr="CW614N",
                standard_en="CW614N",
                standard_din="CuZn39Pb3",
                standard_aisi="C38500",
                standard_uns="C38500",
                aliases=["CW614N", "C38500", "CuZn39Pb3", "Brass 360"],
            ),
            properties=MaterialProperty(density_kg_m3=8500.0),
            conditions=[
                MaterialCondition(
                    condition_code="EXTRUDED",
                    condition_label="Extruded / as-supplied",
                    hardness=_hb(65.0, 90.0, "EN 12164:2016"),
                    tensile_strength_mpa=370.0,
                    yield_strength_mpa=None,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="EN 12164:2016",
                ),
            ],
            machinability=_n_cu_mach(),
            tool_compatibility=_n_cu_compat(),
            cutting_references=_n_al_cuts(),  # reuse N envelope order of magnitude
            source_metadata=_src(
                "EN 12164:2016",
                notes=(
                    "CuZn39Pb3 (CW614N) is a free-cutting brass; "
                    "machinability index ~100 (reference standard for machinability)."
                ),
            ),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        # ── ISO S — Titanium ──────────────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="S-Ti64",
            designation="Ti-6Al-4V",
            iso_group=MaterialISOGroup.S,
            iso_subgroup=MaterialSubGroup.S_TITANIUM,
            material_family=MaterialFamily.TITANIUM,
            designation_detail=MaterialDesignation(
                werkstoff_nr=None,
                standard_en=None,
                standard_din="3.7164",
                standard_aisi="Grade 5",
                standard_uns="R56400",
                aliases=["Ti-6Al-4V", "Grade 5", "3.7164", "Ti6Al4V", "AMS 4928"],
            ),
            properties=MaterialProperty(density_kg_m3=4430.0),
            conditions=[
                MaterialCondition(
                    condition_code="ANNEALED",
                    condition_label="Mill annealed",
                    hardness=_hrc(30.0, 36.0, "AMS 4928 / ASTM B265"),
                    tensile_strength_mpa=950.0,
                    yield_strength_mpa=880.0,
                    elongation_pct=14.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="AMS 4928 / ASTM B265",
                ),
            ],
            machinability=_s_ti_mach(),
            tool_compatibility=_s_ti_compat(),
            cutting_references=_s_ti_cuts(),
            source_metadata=_src("AMS 4928 / ASTM B265"),
            status=MaterialCatalogStatus.ACTIVE,
        ),

        # ── ISO S — Nickel HRSA ───────────────────────────────────────────────

        MaterialCatalogRecord(
            stable_id="S-IN718",
            designation="Inconel 718",
            iso_group=MaterialISOGroup.S,
            iso_subgroup=MaterialSubGroup.S_NICKEL_HRSA,
            material_family=MaterialFamily.NICKEL_ALLOY,
            designation_detail=MaterialDesignation(
                werkstoff_nr="2.4668",
                standard_en=None,
                standard_din="2.4668",
                standard_aisi=None,
                standard_uns="N07718",
                aliases=["Inconel 718", "IN718", "N07718", "2.4668", "AMS 5662"],
            ),
            properties=MaterialProperty(density_kg_m3=8220.0),
            conditions=[
                MaterialCondition(
                    condition_code="SOLUTION_AGED",
                    condition_label="Solution treated and double aged (AMS 5664)",
                    hardness=_hrc(36.0, 44.0, "AMS 5662 / AMS 5664"),
                    tensile_strength_mpa=1240.0,
                    yield_strength_mpa=1036.0,
                    elongation_pct=12.0,
                    confidence=DataConfidence.VERIFIED_STANDARD,
                    source="AMS 5662 / AMS 5664",
                ),
            ],
            machinability=_s_ni_mach(),
            tool_compatibility=_s_ni_compat(),
            cutting_references=_s_ni_cuts(),
            source_metadata=_src("AMS 5662 / AMS 5664"),
            status=MaterialCatalogStatus.ACTIVE,
        ),
    ]
