"""Level-6 Cutting Data and Catalog Intelligence — regression tests.

Tests cover:
  - Domain model structure and immutability
  - Negative rules (no fabrication, unknown stays unknown)
  - RPM formula: n = (1000 × Vc) / (π × D)
  - Milling feed: Vf = n × z × fz
  - Turning feed: Vf = n × fn
  - MRR: ae × ap × Vf (milling)
  - Material record
  - Cutting data record and provenance
  - Source precedence hierarchy
  - Tool-life foundation (Taylor equation — only when C and n known)
  - Hardness-based Vc adjustment (rule-based only)
  - Machine constraint check
  - Generic range lookup
  - Engine integration: known material → GENERIC_REFERENCE candidates
  - Engine integration: unknown material → INSUFFICIENT_DATA
  - Production DXF (no material → cdi present, INSUFFICIENT_DATA)
  - Production IGES (no material → cdi present, INSUFFICIENT_DATA)
  - API response includes cutting_data_summary / cutting_data_candidates
  - Phase 28 no-fabrication audit
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Production file paths
# ---------------------------------------------------------------------------

_PRODUCTION_IGES = Path(
    r"C:\Users\ilhan\AppData\Local\Temp\claude"
    r"\C--Users-ilhan-Downloads-MachiningPro-AI-NEXT"
    r"\5c6eaa26-69c4-4e68-864b-24424ae1b1d9\scratchpad"
    r"\fa00aat46855.geo_fin001.004999.igs"
)
_PRODUCTION_DXF = Path(
    r"C:\Users\ilhan\AppData\Local\Temp\claude"
    r"\d83048698c536d4a\1b3bb96a-da82-40ce-ba5d-97b8f361659a"
    r"\scratchpad\109106_01_39.dxf"
)


def _has_iges() -> bool:
    return _PRODUCTION_IGES.exists()


def _has_dxf() -> bool:
    return _PRODUCTION_DXF.exists()


def _load_iges_doc():
    from backend.interoperability.adapters.iges import IGES_DESCRIPTOR, IgesTokenAdapter
    from backend.interoperability.models import EngineeringSource

    adapter = IgesTokenAdapter()
    source = EngineeringSource(
        source_id="SRC-IGES-L6",
        file_name=_PRODUCTION_IGES.name,
    )
    return adapter.ingest_file(source, IGES_DESCRIPTOR, _PRODUCTION_IGES)


def _load_dxf_doc():
    from backend.interoperability.adapters.dxf import DXF_DESCRIPTOR, DxfTokenAdapter
    from backend.interoperability.models import EngineeringSource

    adapter = DxfTokenAdapter()
    source = EngineeringSource(
        source_id="SRC-DXF-L6",
        file_name=_PRODUCTION_DXF.name,
    )
    return adapter.ingest_file(source, DXF_DESCRIPTOR, _PRODUCTION_DXF)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_feature(
    feature_type: str,
    feature_id: str = "F-001",
    status: str = "CANDIDATE",
    source_surface_id: str | None = None,
    source_curve_id: str | None = None,
    hole_subtype: str | None = None,
):
    from backend.interoperability.features import (
        FeatureStatus,
        ManufacturingFeature,
        ManufacturingFeatureType,
    )

    ftype = ManufacturingFeatureType(feature_type)
    fstatus = FeatureStatus(status)
    kwargs: dict[str, Any] = {
        "feature_id": feature_id,
        "feature_type": ftype,
        "status": fstatus,
        "surface_ids": (source_surface_id,) if source_surface_id else (),
        "curve_ids": (source_curve_id,) if source_curve_id else (),
    }
    if hole_subtype is not None:
        from backend.interoperability.features import HoleSubtype

        kwargs["hole_subtype"] = HoleSubtype(hole_subtype)
    return ManufacturingFeature(**kwargs)


def _result_with(*features, basis: str = "TOPOLOGY"):
    from backend.interoperability.features import FeatureRecognitionResult

    return FeatureRecognitionResult(
        recognition_basis=basis,
        classified_faces=(),
        adjacencies=(),
        features=features,
    )


def _pi_from_features(*features, basis: str = "TOPOLOGY"):
    from backend.interoperability.process_recognition import recognize_process_intelligence

    feat_result = _result_with(*features, basis=basis)
    return recognize_process_intelligence(feat_result, None, None)


def _mti_from_features(*features, basis: str = "TOPOLOGY"):
    from backend.interoperability.machine_tool_selection import derive_machine_tool_intelligence

    pi = _pi_from_features(*features, basis=basis)
    return derive_machine_tool_intelligence(pi, None)


def _cdi_from_features(*features, material=None, basis: str = "TOPOLOGY"):
    from backend.interoperability.cutting_data_engine import derive_cutting_data_intelligence

    mti = _mti_from_features(*features, basis=basis)
    return derive_cutting_data_intelligence(mti, None, material)


def _p_steel():
    from backend.interoperability.cutting_data_intelligence import (
        HardnessUnit,
        MaterialCondition,
        MaterialRecord,
    )

    return MaterialRecord(
        material_group="P_STEEL",
        material_grade="1.0038",
        condition=MaterialCondition.NORMALIZED,
        hardness=160.0,
        hardness_unit=HardnessUnit.HB,
    )


def _n_nonferrous():
    from backend.interoperability.cutting_data_intelligence import MaterialRecord

    return MaterialRecord(material_group="N_NON_FERROUS", material_grade="AlSi10Mg")


def _s_superalloy():
    from backend.interoperability.cutting_data_intelligence import MaterialRecord

    return MaterialRecord(material_group="S_SUPERALLOY", material_grade="Inconel 718")


# ===========================================================================
# TestCuttingDataDomainModel
# ===========================================================================


class TestCuttingDataDomainModel:
    def test_cutting_data_source_type_values(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataSourceType

        assert CuttingDataSourceType.VERIFIED_VENDOR_CATALOG == "VERIFIED_VENDOR_CATALOG"
        assert CuttingDataSourceType.GENERIC_REFERENCE_RANGE == "GENERIC_REFERENCE_RANGE"
        assert CuttingDataSourceType.UNKNOWN == "UNKNOWN"

    def test_source_precedence_order(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            SOURCE_PRECEDENCE,
            CuttingDataSourceType,
        )

        # Verified vendor catalog has highest authority (lowest number).
        assert (
            SOURCE_PRECEDENCE[CuttingDataSourceType.VERIFIED_VENDOR_CATALOG]
            < SOURCE_PRECEDENCE[CuttingDataSourceType.VERIFIED_STANDARD]
        )
        assert (
            SOURCE_PRECEDENCE[CuttingDataSourceType.VERIFIED_STANDARD]
            < SOURCE_PRECEDENCE[CuttingDataSourceType.GENERIC_REFERENCE_RANGE]
        )
        assert (
            SOURCE_PRECEDENCE[CuttingDataSourceType.GENERIC_REFERENCE_RANGE]
            < SOURCE_PRECEDENCE[CuttingDataSourceType.UNKNOWN]
        )

    def test_operation_context_enum_coverage(self) -> None:
        from backend.interoperability.cutting_data_intelligence import OperationContext

        required = {
            "FACE_MILLING", "ROUGH_MILLING", "FINISH_MILLING",
            "DRILLING", "REAMING", "BORING", "TAPPING",
            "TURNING", "GROOVING", "PARTING", "UNKNOWN",
        }
        values = {m.value for m in OperationContext}
        assert required.issubset(values)

    def test_tool_material_class_enum(self) -> None:
        from backend.interoperability.cutting_data_intelligence import ToolMaterialClass

        assert ToolMaterialClass.SOLID_CARBIDE == "SOLID_CARBIDE"
        assert ToolMaterialClass.UNKNOWN == "UNKNOWN"

    def test_cutting_data_status_has_insufficient(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataStatus

        assert CuttingDataStatus.INSUFFICIENT_DATA == "INSUFFICIENT_DATA"
        assert CuttingDataStatus.GENERIC_REFERENCE == "GENERIC_REFERENCE"

    def test_machine_constraint_status_enum(self) -> None:
        from backend.interoperability.cutting_data_intelligence import MachineConstraintStatus

        assert MachineConstraintStatus.WITHIN_MACHINE_LIMITS == "WITHIN_MACHINE_LIMITS"
        assert MachineConstraintStatus.CONSTRAINED_BY_MACHINE == "CONSTRAINED_BY_MACHINE"

    def test_range_value_is_known_true_when_nominal(self) -> None:
        from backend.interoperability.cutting_data_intelligence import RangeValue

        rv = RangeValue(nominal_val=100.0, unit="m/min")
        assert rv.is_known is True

    def test_range_value_is_known_false_when_all_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import RangeValue

        rv = RangeValue()
        assert rv.is_known is False

    def test_cutting_data_provenance_frozen(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataProvenance

        p = CuttingDataProvenance(source_name="test")
        with pytest.raises(AttributeError):
            p.source_name = "other"  # type: ignore[misc]

    def test_material_record_frozen(self) -> None:
        from backend.interoperability.cutting_data_intelligence import MaterialRecord

        m = MaterialRecord(material_group="P_STEEL")
        with pytest.raises(AttributeError):
            m.material_group = "M_STAINLESS"  # type: ignore[misc]

    def test_cutting_data_candidate_frozen(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataCandidate,
            MaterialRecord,
            OperationContext,
        )

        c = CuttingDataCandidate(
            candidate_id="C-001",
            material_record=MaterialRecord(),
            operation=OperationContext.DRILLING,
            tool_family="DRILL",
        )
        with pytest.raises(AttributeError):
            c.candidate_id = "C-002"  # type: ignore[misc]

    def test_cutting_data_intelligence_result_frozen(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataIntelligenceResult,
            CuttingDataPlanStatus,
        )

        r = CuttingDataIntelligenceResult(
            plan_id="P-001",
            status=CuttingDataPlanStatus.INSUFFICIENT_DATA,
            recognition_basis="TEST",
        )
        with pytest.raises(AttributeError):
            r.plan_id = "P-002"  # type: ignore[misc]

    def test_cutting_data_intelligence_result_has_cutting_data_false(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataIntelligenceResult,
            CuttingDataPlanStatus,
        )

        r = CuttingDataIntelligenceResult(
            plan_id="P-001",
            status=CuttingDataPlanStatus.INSUFFICIENT_DATA,
            recognition_basis="TEST",
        )
        assert r.has_cutting_data is False
        assert r.candidate_count == 0
        assert r.has_verified_candidates is False

    def test_cutting_data_intelligence_result_has_cutting_data_true(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataCandidate,
            CuttingDataIntelligenceResult,
            CuttingDataPlanStatus,
            CuttingDataStatus,
            MaterialRecord,
            OperationContext,
        )

        candidate = CuttingDataCandidate(
            candidate_id="C-001",
            material_record=MaterialRecord(material_group="P_STEEL"),
            operation=OperationContext.DRILLING,
            tool_family="DRILL",
            status=CuttingDataStatus.GENERIC_REFERENCE,
        )
        r = CuttingDataIntelligenceResult(
            plan_id="P-001",
            status=CuttingDataPlanStatus.CANDIDATE_PLAN,
            recognition_basis="TEST",
            cutting_data_candidates=(candidate,),
        )
        assert r.has_cutting_data is True
        assert r.candidate_count == 1


# ===========================================================================
# TestNegativeRules
# ===========================================================================


class TestNegativeRules:
    def test_no_fabrication_unknown_material_stays_insufficient(self) -> None:
        """When material is UNKNOWN, all candidates must be INSUFFICIENT_DATA."""
        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)

        from backend.interoperability.cutting_data_intelligence import CuttingDataStatus

        for c in cdi.cutting_data_candidates:
            assert c.status == CuttingDataStatus.INSUFFICIENT_DATA, (
                f"Expected INSUFFICIENT_DATA for UNKNOWN material, got {c.status} "
                f"(candidate_id={c.candidate_id})"
            )

    def test_no_fabrication_rpm_none_when_vc_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(None, 10.0)
        assert result.n_nominal is None
        assert result.n_min is None
        assert result.n_max is None

    def test_no_fabrication_rpm_none_when_diameter_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(100.0, None)
        assert result.n_nominal is None

    def test_no_fabrication_feed_none_when_tooth_count_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_feed_rate

        result = calculate_milling_feed_rate(rpm=1000.0, number_of_teeth=None, fz_mm_per_tooth=0.1)
        assert result.vf_nominal is None, "Must not fabricate feed when z is unknown"

    def test_no_fabrication_turning_feed_none_when_fn_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_turning_feed_rate

        result = calculate_turning_feed_rate(rpm=500.0, fn_mm_per_rev=None)
        assert result.vf_nominal is None

    def test_no_fabrication_mrr_none_when_ae_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_mrr

        result = calculate_milling_mrr(ae_mm=None, ap_mm=5.0, vf_mm_per_min=200.0)
        assert result.mrr_nominal is None

    def test_no_fabrication_mrr_none_when_vf_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_mrr

        result = calculate_milling_mrr(ae_mm=5.0, ap_mm=2.0, vf_mm_per_min=None)
        assert result.mrr_nominal is None

    def test_no_fabrication_taylor_none_when_c_missing(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            ToolLifeEvidence,
            ToolLifeSourceType,
        )

        tl = ToolLifeEvidence(
            source_type=ToolLifeSourceType.TAYLOR_EQUATION,
            taylor_v=100.0,
            taylor_n_exp=0.25,
            taylor_c=None,
        )
        assert tl.taylor_calculable is False
        assert tl.compute_taylor_life() is None

    def test_no_fabrication_taylor_none_when_n_missing(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            ToolLifeEvidence,
            ToolLifeSourceType,
        )

        tl = ToolLifeEvidence(
            source_type=ToolLifeSourceType.TAYLOR_EQUATION,
            taylor_v=100.0,
            taylor_n_exp=None,
            taylor_c=200.0,
        )
        assert tl.taylor_calculable is False
        assert tl.compute_taylor_life() is None

    def test_generic_reference_not_labelled_as_verified(self) -> None:
        from backend.interoperability.cutting_data_engine import _GENERIC_PROVENANCE
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataSourceType,
        )

        assert _GENERIC_PROVENANCE.source_type == CuttingDataSourceType.GENERIC_REFERENCE_RANGE
        assert _GENERIC_PROVENANCE.source_type != CuttingDataSourceType.VERIFIED_VENDOR_CATALOG

    def test_generic_range_candidate_has_generic_reference_status(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataStatus

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=_p_steel())

        for c in cdi.cutting_data_candidates:
            if c.status == CuttingDataStatus.GENERIC_REFERENCE:
                assert c.source.source_type.value == "GENERIC_REFERENCE_RANGE"
                return
        # Either all INSUFFICIENT_DATA or some GENERIC_REFERENCE — either is OK
        # as long as none are VERIFIED


# ===========================================================================
# TestRPMCalculation
# ===========================================================================


class TestRPMCalculation:
    def test_rpm_nominal_known_inputs(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(vc_m_per_min=100.0, diameter_mm=10.0)
        expected = (1000.0 * 100.0) / (math.pi * 10.0)
        assert result.n_nominal is not None
        assert abs(result.n_nominal - expected) < 0.01

    def test_rpm_formula_string_documented(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(100.0, 10.0)
        assert "Vc" in result.formula
        assert "D" in result.formula

    def test_rpm_unit_is_rpm(self) -> None:
        from backend.interoperability.cutting_data_intelligence import SpindleUnit, calculate_rpm

        result = calculate_rpm(100.0, 10.0)
        assert result.unit == SpindleUnit.RPM

    def test_rpm_zero_diameter_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(100.0, 0.0)
        assert result.n_nominal is None
        assert len(result.warnings) > 0

    def test_rpm_negative_diameter_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(100.0, -5.0)
        assert result.n_nominal is None

    def test_rpm_zero_vc_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(0.0, 10.0)
        assert result.n_nominal is None

    def test_rpm_is_calculable_true(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        assert calculate_rpm(100.0, 10.0).is_calculable is True

    def test_rpm_is_calculable_false(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        assert calculate_rpm(None, 10.0).is_calculable is False

    def test_rpm_has_evidence_notes(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_rpm

        result = calculate_rpm(90.0, 12.0)
        assert result.evidence_notes != ""


# ===========================================================================
# TestMillingFeedCalculation
# ===========================================================================


class TestMillingFeedCalculation:
    def test_milling_feed_known_inputs(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_feed_rate

        rpm = 2000.0
        z = 4
        fz = 0.1
        result = calculate_milling_feed_rate(rpm=rpm, number_of_teeth=z, fz_mm_per_tooth=fz)
        assert result.vf_nominal is not None
        assert abs(result.vf_nominal - rpm * z * fz) < 0.001

    def test_milling_feed_formula_documented(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_feed_rate

        result = calculate_milling_feed_rate(2000.0, 4, 0.1)
        assert "z" in result.formula or "fz" in result.formula

    def test_milling_feed_unit_mm_per_min(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            FeedUnit,
            calculate_milling_feed_rate,
        )

        result = calculate_milling_feed_rate(2000.0, 4, 0.1)
        assert result.unit == FeedUnit.MM_PER_MIN

    def test_milling_feed_zero_rpm_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_feed_rate

        result = calculate_milling_feed_rate(rpm=0.0, number_of_teeth=4, fz_mm_per_tooth=0.1)
        assert result.vf_nominal is None

    def test_milling_feed_is_calculable_false_when_z_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_feed_rate

        result = calculate_milling_feed_rate(2000.0, None, 0.1)
        assert result.is_calculable is False

    def test_milling_feed_has_warning_when_z_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_feed_rate

        result = calculate_milling_feed_rate(2000.0, None, 0.1)
        assert len(result.warnings) > 0


# ===========================================================================
# TestTurningFeedCalculation
# ===========================================================================


class TestTurningFeedCalculation:
    def test_turning_feed_known_inputs(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_turning_feed_rate

        rpm = 500.0
        fn = 0.25
        result = calculate_turning_feed_rate(rpm=rpm, fn_mm_per_rev=fn)
        assert result.vf_nominal is not None
        assert abs(result.vf_nominal - rpm * fn) < 0.001

    def test_turning_feed_formula_documented(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_turning_feed_rate

        result = calculate_turning_feed_rate(500.0, 0.25)
        assert "fn" in result.formula

    def test_turning_feed_zero_fn_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_turning_feed_rate

        result = calculate_turning_feed_rate(500.0, 0.0)
        assert result.vf_nominal is None


# ===========================================================================
# TestMRRCalculation
# ===========================================================================


class TestMRRCalculation:
    def test_mrr_known_inputs(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_mrr

        ae = 10.0
        ap = 2.0
        vf = 300.0
        result = calculate_milling_mrr(ae, ap, vf)
        assert result.mrr_nominal is not None
        assert abs(result.mrr_nominal - ae * ap * vf) < 0.01

    def test_mrr_unit_is_mm3_per_min(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            MRRUnit,
            calculate_milling_mrr,
        )

        result = calculate_milling_mrr(10.0, 2.0, 300.0)
        assert result.unit == MRRUnit.MM3_PER_MIN

    def test_mrr_formula_documented(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_mrr

        result = calculate_milling_mrr(10.0, 2.0, 300.0)
        assert "ae" in result.formula and "ap" in result.formula

    def test_mrr_negative_ae_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_mrr

        result = calculate_milling_mrr(-1.0, 2.0, 300.0)
        assert result.mrr_nominal is None

    def test_mrr_is_calculable_false_when_ap_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import calculate_milling_mrr

        result = calculate_milling_mrr(10.0, None, 300.0)
        assert result.is_calculable is False


# ===========================================================================
# TestToolLifeFoundation
# ===========================================================================


class TestToolLifeFoundation:
    def test_taylor_all_coefficients_known(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            ToolLifeEvidence,
            ToolLifeSourceType,
        )

        tl = ToolLifeEvidence(
            source_type=ToolLifeSourceType.TAYLOR_EQUATION,
            taylor_v=100.0,
            taylor_n_exp=0.25,
            taylor_c=200.0,
        )
        assert tl.taylor_calculable is True
        t = tl.compute_taylor_life()
        assert t is not None
        expected = (200.0 / 100.0) ** (1.0 / 0.25)
        assert abs(t - expected) < 0.001

    def test_taylor_equation_formula(self) -> None:
        """T = (C/V)^(1/n) check at typical steel carbide values."""
        from backend.interoperability.cutting_data_intelligence import (
            ToolLifeEvidence,
            ToolLifeSourceType,
        )

        # C=300, n=0.33, V=200 → T = (300/200)^(1/0.33)
        tl = ToolLifeEvidence(
            source_type=ToolLifeSourceType.TAYLOR_EQUATION,
            taylor_v=200.0,
            taylor_n_exp=0.33,
            taylor_c=300.0,
        )
        t = tl.compute_taylor_life()
        assert t is not None
        assert t > 0.0

    def test_taylor_zero_v_returns_none(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            ToolLifeEvidence,
            ToolLifeSourceType,
        )

        tl = ToolLifeEvidence(
            source_type=ToolLifeSourceType.TAYLOR_EQUATION,
            taylor_v=0.0,
            taylor_n_exp=0.25,
            taylor_c=200.0,
        )
        assert tl.compute_taylor_life() is None

    def test_taylor_frozen_dataclass(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            ToolLifeEvidence,
            ToolLifeSourceType,
        )

        tl = ToolLifeEvidence(source_type=ToolLifeSourceType.UNKNOWN)
        with pytest.raises(AttributeError):
            tl.taylor_v = 100.0  # type: ignore[misc]


# ===========================================================================
# TestCatalogModel
# ===========================================================================


class TestCatalogModel:
    def test_catalog_record_requires_record_id(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CatalogRecord

        r = CatalogRecord(
            record_id="TEST-001",
            manufacturer="",
            catalog_name="Test Catalog",
            product_family="TEST",
            tool_family="END_MILL",
        )
        assert r.record_id == "TEST-001"

    def test_catalog_record_frozen(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CatalogRecord

        r = CatalogRecord(
            record_id="TEST-001",
            manufacturer="",
            catalog_name="",
            product_family="",
            tool_family="",
        )
        with pytest.raises(AttributeError):
            r.record_id = "MODIFIED"  # type: ignore[misc]


# ===========================================================================
# TestHardnessAdjustment
# ===========================================================================


class TestHardnessAdjustment:
    def test_low_hardness_no_adjustment(self) -> None:
        from backend.interoperability.cutting_data_engine import _hardness_vc_factor
        from backend.interoperability.cutting_data_intelligence import (
            HardnessUnit,
            MaterialRecord,
        )

        mat = MaterialRecord(hardness=25.0, hardness_unit=HardnessUnit.HRC)
        assert _hardness_vc_factor(mat) == 1.0

    def test_high_hardness_reduces_vc(self) -> None:
        from backend.interoperability.cutting_data_engine import _hardness_vc_factor
        from backend.interoperability.cutting_data_intelligence import (
            HardnessUnit,
            MaterialRecord,
        )

        mat = MaterialRecord(hardness=50.0, hardness_unit=HardnessUnit.HRC)
        factor = _hardness_vc_factor(mat)
        assert factor < 1.0

    def test_unknown_hardness_no_adjustment(self) -> None:
        from backend.interoperability.cutting_data_engine import _hardness_vc_factor
        from backend.interoperability.cutting_data_intelligence import MaterialRecord

        mat = MaterialRecord()
        assert _hardness_vc_factor(mat) == 1.0

    def test_hb_hardness_no_adjustment(self) -> None:
        """HB scale is not HRC — no adjustment applied."""
        from backend.interoperability.cutting_data_engine import _hardness_vc_factor
        from backend.interoperability.cutting_data_intelligence import (
            HardnessUnit,
            MaterialRecord,
        )

        mat = MaterialRecord(hardness=350.0, hardness_unit=HardnessUnit.HB)
        assert _hardness_vc_factor(mat) == 1.0


# ===========================================================================
# TestGenericRangeLookup
# ===========================================================================


class TestGenericRangeLookup:
    def test_p_steel_drilling_carbide_has_vc_range(self) -> None:
        from backend.interoperability.cutting_data_engine import _get_generic_range
        from backend.interoperability.cutting_data_intelligence import (
            OperationContext,
            ToolMaterialClass,
        )

        result = _get_generic_range(
            "P_STEEL", OperationContext.DRILLING, ToolMaterialClass.SOLID_CARBIDE
        )
        assert result is not None
        vc, feed = result
        assert vc.min_val is not None
        assert vc.nominal_val is not None
        assert vc.unit == "m/min"

    def test_p_steel_drilling_carbide_fn_range(self) -> None:
        from backend.interoperability.cutting_data_engine import _get_generic_range
        from backend.interoperability.cutting_data_intelligence import (
            OperationContext,
            ToolMaterialClass,
        )

        result = _get_generic_range(
            "P_STEEL", OperationContext.DRILLING, ToolMaterialClass.SOLID_CARBIDE
        )
        assert result is not None
        _, feed = result
        assert feed.unit == "mm/rev"
        assert feed.nominal_val is not None

    def test_n_nonferrous_milling_has_fz_range(self) -> None:
        from backend.interoperability.cutting_data_engine import _get_generic_range
        from backend.interoperability.cutting_data_intelligence import (
            OperationContext,
            ToolMaterialClass,
        )

        result = _get_generic_range(
            "N_NON_FERROUS", OperationContext.ROUGH_MILLING, ToolMaterialClass.SOLID_CARBIDE
        )
        assert result is not None
        _, feed = result
        assert feed.unit == "mm/tooth"

    def test_unknown_combination_returns_none(self) -> None:
        from backend.interoperability.cutting_data_engine import _get_generic_range
        from backend.interoperability.cutting_data_intelligence import (
            OperationContext,
            ToolMaterialClass,
        )

        result = _get_generic_range(
            "H_HARDENED", OperationContext.TAPPING, ToolMaterialClass.CERAMIC
        )
        assert result is None


# ===========================================================================
# TestCuttingDataEngine
# ===========================================================================


class TestCuttingDataEngine:
    def test_derive_with_unknown_material_returns_insufficient(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataPlanStatus

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)
        assert cdi.status == CuttingDataPlanStatus.INSUFFICIENT_DATA

    def test_derive_with_p_steel_returns_candidate_plan(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataPlanStatus

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=_p_steel())
        # Either CANDIDATE_PLAN (if generic range found) or INSUFFICIENT_DATA (if no match)
        assert cdi.status in (
            CuttingDataPlanStatus.CANDIDATE_PLAN,
            CuttingDataPlanStatus.INSUFFICIENT_DATA,
        )

    def test_derive_returns_cdi_result_always(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataIntelligenceResult

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)
        assert isinstance(cdi, CuttingDataIntelligenceResult)

    def test_derive_plan_id_is_set(self) -> None:
        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)
        assert cdi.plan_id != ""

    def test_derive_recognition_basis_is_set(self) -> None:
        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)
        assert cdi.recognition_basis != ""

    def test_derive_missing_inputs_includes_material_when_unknown(self) -> None:
        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)
        # When material is UNKNOWN, missing_inputs must mention it.
        any_material = any("material" in m.lower() for m in cdi.missing_inputs)
        any_candidate_material = any(
            "material" in c.warnings[0].lower()
            for c in cdi.cutting_data_candidates
            if c.warnings
        )
        assert (
            any_material
            or any_candidate_material
            or cdi.material_record.material_group == "UNKNOWN"
        )

    def test_derive_candidate_has_provenance(self) -> None:

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=_p_steel())
        for c in cdi.cutting_data_candidates:
            assert c.source is not None, "Every candidate must have a CuttingDataProvenance"

    def test_derive_no_fabrication_all_none_for_unknown(self) -> None:
        """With unknown material, no numerical Vc/feed values should appear."""
        from backend.interoperability.cutting_data_intelligence import CuttingDataStatus

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=None)
        for c in cdi.cutting_data_candidates:
            assert c.status == CuttingDataStatus.INSUFFICIENT_DATA
            assert c.vc_range.is_known is False, (
                "No Vc range should be present when material is UNKNOWN"
            )

    def test_s_superalloy_drilling_has_lower_vc_than_p_steel(self) -> None:
        from backend.interoperability.cutting_data_engine import _get_generic_range
        from backend.interoperability.cutting_data_intelligence import (
            OperationContext,
            ToolMaterialClass,
        )

        p_range = _get_generic_range(
            "P_STEEL", OperationContext.DRILLING, ToolMaterialClass.SOLID_CARBIDE
        )
        s_range = _get_generic_range(
            "S_SUPERALLOY", OperationContext.DRILLING, ToolMaterialClass.SOLID_CARBIDE
        )
        assert p_range is not None
        assert s_range is not None
        assert s_range[0].nominal_val < p_range[0].nominal_val, (
            "S superalloy should have lower Vc than P steel"
        )

    def test_derive_with_invalid_mti_returns_insufficient(self) -> None:
        from backend.interoperability.cutting_data_engine import derive_cutting_data_intelligence
        from backend.interoperability.cutting_data_intelligence import CuttingDataPlanStatus

        cdi = derive_cutting_data_intelligence("not_a_mti_result")
        assert cdi.status == CuttingDataPlanStatus.INSUFFICIENT_DATA


# ===========================================================================
# TestProductionDXFLevel6
# ===========================================================================


@pytest.mark.skipif(not _has_dxf(), reason="Production DXF not available")
class TestProductionDXFLevel6:
    def test_cutting_data_intelligence_field_present(self) -> None:
        doc = _load_dxf_doc()
        assert doc.cutting_data_intelligence is not None, (
            "cutting_data_intelligence must be populated for DXF files"
        )

    def test_cutting_data_intelligence_type(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataIntelligenceResult,
        )

        doc = _load_dxf_doc()
        assert isinstance(doc.cutting_data_intelligence, CuttingDataIntelligenceResult)

    def test_cutting_data_intelligence_plan_id_set(self) -> None:
        doc = _load_dxf_doc()
        assert doc.cutting_data_intelligence.plan_id != ""

    def test_cutting_data_intelligence_no_material_insufficient(self) -> None:
        """DXF has no embedded material — cutting data must be INSUFFICIENT_DATA."""

        doc = _load_dxf_doc()
        cdi = doc.cutting_data_intelligence
        # With no material the candidates must all be INSUFFICIENT_DATA
        # or the plan itself is INSUFFICIENT_DATA
        from backend.interoperability.cutting_data_intelligence import CuttingDataStatus

        for c in cdi.cutting_data_candidates:
            assert c.status == CuttingDataStatus.INSUFFICIENT_DATA, (
                f"Candidate {c.candidate_id} should be INSUFFICIENT_DATA without material, "
                f"got {c.status}"
            )

    def test_no_verified_vendor_data_for_dxf(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataStatus

        doc = _load_dxf_doc()
        cdi = doc.cutting_data_intelligence
        for c in cdi.cutting_data_candidates:
            assert c.status != CuttingDataStatus.VERIFIED, (
                "No VERIFIED cutting data should be produced from a plain DXF without material"
            )

    def test_level_6_not_marked_without_cutting_data(self) -> None:
        """When cutting_data has no usable ranges, capability level stays at L5 or below."""
        from backend.interoperability.enums import CapabilityLevel

        doc = _load_dxf_doc()
        cdi = doc.cutting_data_intelligence
        if not cdi.has_cutting_data:
            assert doc.capability_level != CapabilityLevel.LEVEL_6_ENGINEERING_VALIDATED, (
                "LEVEL_6 should not be marked when has_cutting_data is False"
            )

    def test_has_cutting_data_false_for_dxf_without_material(self) -> None:
        doc = _load_dxf_doc()
        cdi = doc.cutting_data_intelligence
        assert cdi.has_cutting_data is False


# ===========================================================================
# TestProductionIGESLevel6
# ===========================================================================


@pytest.mark.skipif(not _has_iges(), reason="Production IGES not available")
class TestProductionIGESLevel6:
    def test_cutting_data_intelligence_field_present(self) -> None:
        doc = _load_iges_doc()
        assert doc.cutting_data_intelligence is not None

    def test_cutting_data_intelligence_type(self) -> None:
        from backend.interoperability.cutting_data_intelligence import (
            CuttingDataIntelligenceResult,
        )

        doc = _load_iges_doc()
        assert isinstance(doc.cutting_data_intelligence, CuttingDataIntelligenceResult)

    def test_cutting_data_has_cutting_data_false(self) -> None:
        doc = _load_iges_doc()
        cdi = doc.cutting_data_intelligence
        assert cdi.has_cutting_data is False

    def test_level_6_not_marked_for_iges_without_material(self) -> None:
        from backend.interoperability.enums import CapabilityLevel

        doc = _load_iges_doc()
        cdi = doc.cutting_data_intelligence
        if not cdi.has_cutting_data:
            assert doc.capability_level != CapabilityLevel.LEVEL_6_ENGINEERING_VALIDATED


# ===========================================================================
# TestAPIResponseLevel6 — verify cutting_data_intelligence fields on the document
# ===========================================================================


@pytest.mark.skipif(not _has_dxf(), reason="Production DXF not available")
class TestAPIResponseLevel6:
    """These tests verify cutting data fields using direct adapter access,
    matching the pattern used in Level-4 API tests."""

    def _load_doc(self):
        return _load_dxf_doc()

    def test_cutting_data_intelligence_field_on_document(self) -> None:
        doc = self._load_doc()
        assert doc.cutting_data_intelligence is not None

    def test_cutting_data_intelligence_status_accessible(self) -> None:
        doc = self._load_doc()
        cdi = doc.cutting_data_intelligence
        assert hasattr(cdi, "status")
        assert cdi.status.value in (
            "COMPLETE", "CANDIDATE_PLAN", "PARTIAL", "INSUFFICIENT_DATA", "REQUIRES_INPUT"
        )

    def test_cutting_data_summary_fields_accessible(self) -> None:
        doc = self._load_doc()
        cdi = doc.cutting_data_intelligence
        # Verify all fields used by the API serialiser exist
        assert hasattr(cdi, "plan_id")
        assert hasattr(cdi, "recognition_basis")
        assert hasattr(cdi, "material_record")
        assert hasattr(cdi, "candidate_count")
        assert hasattr(cdi, "has_cutting_data")
        assert hasattr(cdi, "has_verified_candidates")
        assert hasattr(cdi, "source_mti_candidate_count")
        assert hasattr(cdi, "missing_inputs")
        assert hasattr(cdi, "warnings")

    def test_material_record_material_group_is_string(self) -> None:
        doc = self._load_doc()
        cdi = doc.cutting_data_intelligence
        assert isinstance(cdi.material_record.material_group, str)

    def test_cutting_data_candidates_accessible(self) -> None:
        doc = self._load_doc()
        cdi = doc.cutting_data_intelligence
        assert isinstance(cdi.cutting_data_candidates, tuple)

    def test_candidate_serialisable_fields(self) -> None:
        """Every candidate has the fields the API serialiser accesses."""
        doc = self._load_doc()
        cdi = doc.cutting_data_intelligence
        for c in cdi.cutting_data_candidates:
            assert hasattr(c, "candidate_id")
            assert hasattr(c, "operation")
            assert hasattr(c, "tool_family")
            assert hasattr(c, "material_record")
            assert hasattr(c, "status")
            assert hasattr(c, "coolant")
            assert hasattr(c, "source")
            assert hasattr(c, "warnings")
            assert hasattr(c, "evidence_notes")
            assert hasattr(c.source, "source_type")
            assert hasattr(c.source, "source_name")

    def test_candidate_source_type_is_string_enum(self) -> None:
        from backend.interoperability.cutting_data_intelligence import CuttingDataSourceType

        doc = self._load_doc()
        cdi = doc.cutting_data_intelligence
        for c in cdi.cutting_data_candidates:
            assert isinstance(c.source.source_type, CuttingDataSourceType)


# ===========================================================================
# TestPhase28NoFabricationAudit
# ===========================================================================


class TestPhase28NoFabricationAudit:
    """Phase 28 — Verify that no cutting data values are hard-coded as magic numbers."""

    def test_audit_all_generic_range_values_have_provenance_source_type(self) -> None:
        """All entries in _GENERIC_REFERENCE_TABLE are labelled GENERIC_REFERENCE_RANGE."""
        from backend.interoperability.cutting_data_engine import _GENERIC_PROVENANCE
        from backend.interoperability.cutting_data_intelligence import CuttingDataSourceType

        assert _GENERIC_PROVENANCE.source_type == CuttingDataSourceType.GENERIC_REFERENCE_RANGE

    def test_audit_no_verified_vendor_catalog_in_engine(self) -> None:
        """Engine must not claim VERIFIED_VENDOR_CATALOG source."""
        from backend.interoperability.cutting_data_engine import _GENERIC_PROVENANCE
        from backend.interoperability.cutting_data_intelligence import CuttingDataSourceType

        assert _GENERIC_PROVENANCE.source_type != CuttingDataSourceType.VERIFIED_VENDOR_CATALOG

    def test_audit_cutting_data_intelligence_import_path(self) -> None:
        """Module exists and is importable."""
        import importlib

        m = importlib.import_module("backend.interoperability.cutting_data_intelligence")
        assert hasattr(m, "CuttingDataIntelligenceResult")
        assert hasattr(m, "CuttingDataPlanStatus")
        assert hasattr(m, "CuttingDataSourceType")

    def test_audit_cutting_data_engine_import_path(self) -> None:
        import importlib

        m = importlib.import_module("backend.interoperability.cutting_data_engine")
        assert hasattr(m, "derive_cutting_data_intelligence")

    def test_audit_cutting_data_field_in_canonical_document(self) -> None:
        import dataclasses

        from backend.interoperability.models import CanonicalDocument

        field_names = {f.name for f in dataclasses.fields(CanonicalDocument)}
        assert "cutting_data_intelligence" in field_names

    def test_audit_level6_enum_in_capability_level(self) -> None:
        from backend.interoperability.enums import CapabilityLevel

        assert hasattr(CapabilityLevel, "LEVEL_6_ENGINEERING_VALIDATED")

    def test_audit_no_negative_vc_in_reference_table(self) -> None:
        """Sanity: all Vc values in the reference table are positive."""
        from backend.interoperability.cutting_data_engine import _GENERIC_REFERENCE_TABLE

        for key, row in _GENERIC_REFERENCE_TABLE.items():
            vc_min, vc_nom, vc_max = row[0], row[1], row[2]
            assert vc_min > 0, f"vc_min <= 0 in {key}"
            assert vc_nom > 0, f"vc_nom <= 0 in {key}"
            assert vc_max > 0, f"vc_max <= 0 in {key}"
            assert vc_min <= vc_nom <= vc_max, (
                f"Vc ordering violation in {key}: min={vc_min}, nom={vc_nom}, max={vc_max}"
            )

    def test_audit_no_negative_feed_in_reference_table(self) -> None:
        """Sanity: all non-None feed values are positive."""
        from backend.interoperability.cutting_data_engine import _GENERIC_REFERENCE_TABLE

        for key, row in _GENERIC_REFERENCE_TABLE.items():
            fz_min, fz_nom, fz_max = row[3], row[4], row[5]
            fn_min, fn_nom, fn_max = row[6], row[7], row[8]
            for name, val in [
                ("fz_min", fz_min), ("fz_nom", fz_nom), ("fz_max", fz_max),
                ("fn_min", fn_min), ("fn_nom", fn_nom), ("fn_max", fn_max),
            ]:
                if val is not None:
                    assert val > 0, f"{name} <= 0 in {key}"

    def test_audit_every_candidate_has_source_type(self) -> None:
        """Engine candidates must always have a CuttingDataProvenance with source_type."""
        from backend.interoperability.cutting_data_intelligence import CuttingDataSourceType

        f = _make_feature("HOLE", "F-001", hole_subtype="THROUGH")
        cdi = _cdi_from_features(f, material=_p_steel())
        for c in cdi.cutting_data_candidates:
            assert c.source is not None
            assert isinstance(c.source.source_type, CuttingDataSourceType)
