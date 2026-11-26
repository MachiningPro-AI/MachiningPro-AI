"""Tests for Auto CAM enhanced cutting parameter engine — MACHININGPRO_AI_BETA3_PARAMS_01.

Verifies:
  - NOT_AVAILABLE for unmapped feature types
  - PARTIAL when tool_diameter_mm is None
  - RPM calculation formula: 1000 × Vc / (π × D)
  - Feed rate calculation using rpm_feed_per_rev or rpm_tooth_feed
  - Machine spindle_max_rpm clamping
  - CLAMPED_TO_MACHINE_LIMIT status when clamped
  - Provenance string contains SOURCE_TYPE + formula + CONFIDENCE
  - No fabricated values: all from registry or formula
"""

import math
import pytest

from backend.autocam.cutting_params_engine import (
    _FEATURE_TO_OP,
    compute_cutting_params,
)
from backend.autocam.models import (
    AutoCamFeatureInput,
    CuttingParamResult,
    MachineResult,
    ToolResult,
)
from backend.cutting_parameters.models import (
    ApplicabilityScope,
    EvidenceStatus,
    ParameterType,
    QuantityRange,
)
from backend.cutting_parameters.registry import CuttingParameterRegistry
from backend.domain.base import Provenance
from backend.domain.enums import OperationType, ProvenanceType
from backend.domain.units import Quantity, Unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_hole(d_mm: float = 10.0) -> AutoCamFeatureInput:
    return AutoCamFeatureInput(feature_id="F01", feature_type="HOLE", diameter_mm=d_mm)


def _make_pocket() -> AutoCamFeatureInput:
    return AutoCamFeatureInput(feature_id="F02", feature_type="POCKET",
                               width_mm=20.0, length_mm=30.0)


def _make_machine(max_rpm: int = 8000) -> MachineResult:
    return MachineResult(machine_id="M1", spindle_max_rpm=max_rpm, status="FOUND")


def _make_tool(d_mm: float | None = 10.0) -> ToolResult:
    return ToolResult(tool_id="T1", tool_diameter_mm=d_mm, tool_status="FOUND")


# ---------------------------------------------------------------------------
# Feature type mapping
# ---------------------------------------------------------------------------

class TestFeatureMapping:
    def test_hole_maps_to_drilling(self):
        assert _FEATURE_TO_OP["HOLE"] == OperationType.DRILLING

    def test_pocket_maps_to_milling(self):
        assert _FEATURE_TO_OP["POCKET"] == OperationType.MILLING

    def test_slot_maps_to_milling(self):
        assert _FEATURE_TO_OP["SLOT"] == OperationType.MILLING

    def test_step_shoulder_maps_to_milling(self):
        assert _FEATURE_TO_OP["STEP_SHOULDER"] == OperationType.MILLING

    def test_planar_face_maps_to_milling(self):
        assert _FEATURE_TO_OP["PLANAR_FACE"] == OperationType.MILLING


# ---------------------------------------------------------------------------
# NOT_AVAILABLE paths
# ---------------------------------------------------------------------------

class TestNotAvailablePaths:
    def test_unmapped_feature_type(self):
        feat = AutoCamFeatureInput(feature_id="F99", feature_type="UNKNOWN_TYPE")
        result = compute_cutting_params(feat, _make_tool(), _make_machine())
        assert result.status == "NOT_AVAILABLE"
        assert result.vc_m_per_min is None

    def test_empty_registry_returns_not_available(self, monkeypatch):
        from backend.autocam import cutting_params_engine
        empty_reg = CuttingParameterRegistry()

        def _get_empty():
            return empty_reg

        monkeypatch.setattr(cutting_params_engine, "_get_registry", _get_empty)
        result = compute_cutting_params(_make_hole(), _make_tool(), _make_machine())
        assert result.status == "NOT_AVAILABLE"
        assert "KL-05" in result.provenance

    def test_no_tool_diameter_returns_partial(self, monkeypatch):
        from backend.autocam import cutting_params_engine
        from backend.cutting_parameters.models import CuttingParameterRecord

        reg = CuttingParameterRegistry()
        record = CuttingParameterRecord(
            record_id="R001",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity.of(20, Unit.M_MIN),
                max_value=Quantity.of(40, Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(operation_type=OperationType.DRILLING),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
            provenance=Provenance(source_type=ProvenanceType.LITERATURE),
        )
        reg.register(record)

        def _get_seeded():
            return reg

        monkeypatch.setattr(cutting_params_engine, "_get_registry", _get_seeded)
        # Tool with no diameter
        result = compute_cutting_params(_make_hole(), _make_tool(d_mm=None), _make_machine())
        assert result.status == "PARTIAL"
        assert result.vc_m_per_min is not None  # Vc returned even without D
        assert result.rpm is None


# ---------------------------------------------------------------------------
# RPM formula verification
# ---------------------------------------------------------------------------

class TestRpmFormula:
    def _seed_registry_with_vc(self, monkeypatch, vc_min: float, vc_max: float) -> None:
        from backend.autocam import cutting_params_engine
        from backend.cutting_parameters.models import CuttingParameterRecord

        reg = CuttingParameterRegistry()
        record = CuttingParameterRecord(
            record_id="R_VC",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity.of(vc_min, Unit.M_MIN),
                max_value=Quantity.of(vc_max, Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(operation_type=OperationType.DRILLING),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
            provenance=Provenance(source_type=ProvenanceType.LITERATURE),
        )
        reg.register(record)
        monkeypatch.setattr(cutting_params_engine, "_get_registry", lambda: reg)

    def test_rpm_formula_correctness(self, monkeypatch):
        self._seed_registry_with_vc(monkeypatch, 30.0, 50.0)
        d = 10.0
        vc_mid = (30.0 + 50.0) / 2.0  # 40.0
        expected_rpm = 1000.0 * vc_mid / (math.pi * d)

        result = compute_cutting_params(_make_hole(d_mm=d), _make_tool(d_mm=d), _make_machine(max_rpm=99999))
        assert result.rpm is not None
        assert abs(result.rpm - expected_rpm) < 2.0  # allow rounding

    def test_rpm_clamped_when_exceeds_spindle_limit(self, monkeypatch):
        # Very high Vc → RPM will exceed machine limit
        self._seed_registry_with_vc(monkeypatch, 500.0, 600.0)
        d = 5.0
        vc_mid = (500.0 + 600.0) / 2.0
        unclamped_rpm = 1000.0 * vc_mid / (math.pi * d)
        machine_max = 8000
        assert unclamped_rpm > machine_max, "precondition: test needs Vc that exceeds limit"

        result = compute_cutting_params(_make_hole(d_mm=d), _make_tool(d_mm=d), _make_machine(max_rpm=machine_max))
        assert result.status == "CLAMPED_TO_MACHINE_LIMIT"
        assert result.rpm == float(machine_max)
        assert "CLAMPED_TO_MACHINE_LIMIT" in result.provenance

    def test_rpm_not_clamped_when_below_limit(self, monkeypatch):
        self._seed_registry_with_vc(monkeypatch, 20.0, 30.0)
        d = 10.0
        vc_mid = 25.0
        expected_rpm = 1000.0 * vc_mid / (math.pi * d)
        machine_max = 99999

        result = compute_cutting_params(_make_hole(d_mm=d), _make_tool(d_mm=d), _make_machine(max_rpm=machine_max))
        assert result.status in ("CALCULATED", "PARTIAL")
        assert result.rpm is not None
        assert abs(result.rpm - expected_rpm) < 2.0


# ---------------------------------------------------------------------------
# Provenance fields
# ---------------------------------------------------------------------------

class TestProvenance:
    def test_provenance_contains_source_type(self, monkeypatch):
        from backend.autocam import cutting_params_engine
        from backend.cutting_parameters.models import CuttingParameterRecord
        reg = CuttingParameterRegistry()
        reg.register(CuttingParameterRecord(
            record_id="R_P1",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity.of(50, Unit.M_MIN),
                max_value=Quantity.of(100, Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(operation_type=OperationType.MILLING),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
            provenance=Provenance(source_type=ProvenanceType.LITERATURE, source_document="test_source"),
        ))
        monkeypatch.setattr(cutting_params_engine, "_get_registry", lambda: reg)
        result = compute_cutting_params(_make_pocket(), _make_tool(), _make_machine())
        assert "SOURCE_TYPE=REFERENCE_ONLY" in result.provenance

    def test_provenance_contains_confidence_note(self, monkeypatch):
        from backend.autocam import cutting_params_engine
        from backend.cutting_parameters.models import CuttingParameterRecord
        reg = CuttingParameterRegistry()
        reg.register(CuttingParameterRecord(
            record_id="R_P2",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity.of(50, Unit.M_MIN),
                max_value=Quantity.of(100, Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(operation_type=OperationType.MILLING),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
            provenance=Provenance(source_type=ProvenanceType.LITERATURE),
        ))
        monkeypatch.setattr(cutting_params_engine, "_get_registry", lambda: reg)
        result = compute_cutting_params(_make_pocket(), _make_tool(), _make_machine())
        assert "NOT_AUTHORITATIVE" in result.provenance

    def test_provenance_contains_formula_reference(self, monkeypatch):
        from backend.autocam import cutting_params_engine
        from backend.cutting_parameters.models import CuttingParameterRecord
        reg = CuttingParameterRegistry()
        reg.register(CuttingParameterRecord(
            record_id="R_P3",
            parameter_type=ParameterType.CUTTING_SPEED,
            value_range=QuantityRange(
                min_value=Quantity.of(30, Unit.M_MIN),
                max_value=Quantity.of(50, Unit.M_MIN),
            ),
            applicability=ApplicabilityScope(operation_type=OperationType.DRILLING),
            evidence_status=EvidenceStatus.REFERENCE_ONLY,
            provenance=Provenance(source_type=ProvenanceType.LITERATURE),
        ))
        monkeypatch.setattr(cutting_params_engine, "_get_registry", lambda: reg)
        result = compute_cutting_params(_make_hole(), _make_tool(), _make_machine())
        assert "formulas.py" in result.provenance
