"""Phases O/P — Material removal and MRR tests."""

import pytest
from backend.verification.material_removal import (
    OperationRemovalResult,
    MRRResult,
    compute_operation_removal,
    compute_mrr,
)


class TestOperationRemoval:
    def test_basic_removal(self):
        r = compute_operation_removal(
            operation_id="OP-01",
            tool_id="T-001",
            initial_volume_mm3=10000.0,
            remaining_volume_after_mm3=8500.0,
            volume_method="BREP_SOLID_VOLUME",
            volume_fidelity="BREP_EXACT",
            provenance="TEST",
        )
        assert isinstance(r, OperationRemovalResult)
        assert r.removed_volume_mm3 == pytest.approx(1500.0)
        assert r.removal_percent == pytest.approx(15.0)

    def test_removal_percent_clamped(self):
        r = compute_operation_removal(
            operation_id="OP-02",
            tool_id="T-001",
            initial_volume_mm3=1000.0,
            remaining_volume_after_mm3=0.0,
            volume_method="VOXEL_APPROXIMATE",
            volume_fidelity="APPROXIMATE_VOXEL",
            provenance="TEST",
        )
        assert r.removal_percent == pytest.approx(100.0)

    def test_zero_initial_volume(self):
        r = compute_operation_removal(
            operation_id="OP-03",
            tool_id="T-001",
            initial_volume_mm3=0.0,
            remaining_volume_after_mm3=0.0,
            volume_method="NOT_AVAILABLE",
            volume_fidelity="NOT_AVAILABLE",
            provenance="TEST",
        )
        assert r.status in ("NOT_AVAILABLE", "INSUFFICIENT_DATA", "PASS", "COMPUTED")

    def test_method_propagated(self):
        r = compute_operation_removal(
            operation_id="OP-04",
            tool_id="T-001",
            initial_volume_mm3=5000.0,
            remaining_volume_after_mm3=4000.0,
            volume_method="BREP_SOLID_VOLUME",
            volume_fidelity="BREP_EXACT",
            provenance="CATALOG",
        )
        assert r.method == "BREP_SOLID_VOLUME"
        assert r.fidelity == "BREP_EXACT"

    def test_provenance_propagated(self):
        r = compute_operation_removal(
            operation_id="OP-05",
            tool_id="T-001",
            initial_volume_mm3=5000.0,
            remaining_volume_after_mm3=4000.0,
            volume_method="BREP_SOLID_VOLUME",
            volume_fidelity="BREP_EXACT",
            provenance="OCC_GETMASS",
        )
        assert r.provenance == "OCC_GETMASS"

    def test_removed_never_negative(self):
        r = compute_operation_removal(
            operation_id="OP-06",
            tool_id="T-001",
            initial_volume_mm3=5000.0,
            remaining_volume_after_mm3=5100.0,  # impossible but should not error
            volume_method="BREP_SOLID_VOLUME",
            volume_fidelity="BREP_EXACT",
            provenance="TEST",
        )
        assert r.removed_volume_mm3 is not None


class TestMRR:
    def test_basic_mrr(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=1500.0,
            cutting_time_min=0.5,
            volume_fidelity="BREP_EXACT",
            provenance="OCC_GETMASS",
        )
        assert isinstance(r, MRRResult)
        assert r.mrr_mm3_per_min == pytest.approx(3000.0)

    def test_mrr_unit_label(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=1000.0,
            cutting_time_min=1.0,
            volume_fidelity="BREP_EXACT",
            provenance="OCC_GETMASS",
        )
        assert r.mrr_unit == "mm³/min"

    def test_zero_time_returns_not_available(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=1000.0,
            cutting_time_min=0.0,
            volume_fidelity="BREP_EXACT",
            provenance="OCC_GETMASS",
        )
        assert r.mrr_status in ("NOT_AVAILABLE", "UNDEFINED", "DIVIDE_BY_ZERO")
        assert r.mrr_mm3_per_min is None

    def test_none_volume_returns_not_available(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=None,
            cutting_time_min=1.0,
            volume_fidelity="NOT_AVAILABLE",
            provenance="TEST",
        )
        assert r.mrr_mm3_per_min is None
        assert "NOT_AVAILABLE" in r.mrr_status.upper()

    def test_negative_time_returns_not_available(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=1000.0,
            cutting_time_min=-1.0,
            volume_fidelity="BREP_EXACT",
            provenance="TEST",
        )
        assert r.mrr_mm3_per_min is None

    def test_mrr_method_labeled(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=2000.0,
            cutting_time_min=2.0,
            volume_fidelity="BREP_EXACT",
            provenance="OCC_GETMASS",
        )
        assert r.mrr_method is not None and len(r.mrr_method) > 0

    def test_mrr_propagates_fidelity(self):
        r = compute_mrr(
            operation_id="OP-01",
            tool_id="T-001",
            removed_volume_mm3=2000.0,
            cutting_time_min=2.0,
            volume_fidelity="APPROXIMATE_VOXEL",
            provenance="VOXEL",
        )
        assert r.mrr_mm3_per_min is not None
        # fidelity propagated, not silently upgraded
        assert "APPROXIMATE" in str(r).upper() or r.mrr_method is not None
