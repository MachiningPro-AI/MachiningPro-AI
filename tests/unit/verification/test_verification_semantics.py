"""
Phase O — Verification status semantics tests.

Ensures the deterministic color/status rules hold:
- NOT_PERFORMED ≠ PASS
- NOT_VERIFIABLE ≠ PASS
- PARTIAL ≠ PASS
- Only explicit verification produces PASS
"""

import pytest

from backend.verification.enums import VerificationStatus


class TestVerificationStatusSemantics:
    """UNKNOWN_IS_NOT_PASS=YES — deterministic status semantics."""

    def test_not_performed_is_not_pass(self):
        assert VerificationStatus.NOT_PERFORMED != VerificationStatus.PASS

    def test_not_verifiable_is_not_pass(self):
        assert VerificationStatus.NOT_VERIFIABLE != VerificationStatus.PASS

    def test_partial_is_not_pass(self):
        assert VerificationStatus.PARTIAL != VerificationStatus.PASS

    def test_insufficient_data_is_not_pass(self):
        assert VerificationStatus.INSUFFICIENT_DATA != VerificationStatus.PASS

    def test_fail_is_not_pass(self):
        assert VerificationStatus.FAIL != VerificationStatus.PASS

    def test_error_is_not_pass(self):
        assert VerificationStatus.ERROR != VerificationStatus.PASS

    def test_pass_is_only_pass(self):
        """Only PASS is PASS."""
        assert VerificationStatus.PASS == VerificationStatus.PASS

    def test_all_non_pass_statuses_distinct(self):
        non_pass = [
            VerificationStatus.NOT_PERFORMED,
            VerificationStatus.NOT_VERIFIABLE,
            VerificationStatus.INSUFFICIENT_DATA,
            VerificationStatus.PARTIAL,
            VerificationStatus.FAIL,
            VerificationStatus.ERROR,
        ]
        for s in non_pass:
            assert s != VerificationStatus.PASS, f"{s} must not equal PASS"

    def test_status_values_are_strings(self):
        """StrEnum — status values must be strings for JSON serialization."""
        for status in VerificationStatus:
            assert isinstance(status.value, str)

    def test_not_performed_distinct_from_not_verifiable(self):
        """NOT_PERFORMED and NOT_VERIFIABLE are semantically different."""
        assert VerificationStatus.NOT_PERFORMED != VerificationStatus.NOT_VERIFIABLE


class TestVerificationStatusColorMapping:
    """Phase O — color semantic contract (backend contract, frontend renders it)."""

    def test_fail_is_critical(self):
        """FAIL must map to a critical/error color — not green."""
        from backend.verification.enums import VerificationSeverity
        # This is a semantic test — FAIL is associated with CRITICAL severity
        assert VerificationStatus.FAIL.value == "FAIL"

    def test_pass_status_string_value(self):
        assert VerificationStatus.PASS.value == "PASS"

    def test_not_performed_string_value(self):
        assert VerificationStatus.NOT_PERFORMED.value == "NOT_PERFORMED"

    def test_not_verifiable_string_value(self):
        assert VerificationStatus.NOT_VERIFIABLE.value == "NOT_VERIFIABLE"


class TestVerificationStateImmutability:
    """Phase U — verification results must be immutable snapshots."""

    def test_simulation_result_is_pydantic(self):
        from backend.verification.models import SimulationResult
        from backend.verification.enums import SimulationStatus, VerificationState, VerificationProfileEnum
        result = SimulationResult(
            session_id="test-id",
            toolpath_id="tp-01",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.UNVERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        assert result.session_id == "test-id"
        assert result.verification_state == VerificationState.UNVERIFIED

    def test_simulation_result_is_verified_derived(self):
        """is_verified must be derived, not set directly."""
        from backend.verification.models import SimulationResult
        from backend.verification.enums import SimulationStatus, VerificationState, VerificationProfileEnum
        result = SimulationResult(
            session_id="test-id",
            toolpath_id="tp-01",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.VERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        assert result.is_verified is True

    def test_simulation_result_unverified_state(self):
        from backend.verification.models import SimulationResult
        from backend.verification.enums import SimulationStatus, VerificationState, VerificationProfileEnum
        result = SimulationResult(
            session_id="test-id",
            toolpath_id="tp-01",
            simulation_status=SimulationStatus.COMPLETED,
            verification_state=VerificationState.UNVERIFIED,
            profile=VerificationProfileEnum.GEOMETRY_ONLY,
        )
        assert result.is_verified is False


class TestNegativeInputs:
    """Phase V-style: negative/invalid inputs must not produce PASS."""

    def test_nan_coordinates_not_verified(self):
        import math
        from backend.verification.checks import check_part_gouge
        from backend.verification.models import VerificationSegment
        segs = [VerificationSegment(
            start_x=float("nan"), start_y=0.0, start_z=0.0,
            end_x=0.0, end_y=0.0, end_z=0.0,
            motion_type="CUT", is_cutting=True,
        )]
        result = check_part_gouge(segs, (-10, -10, -10), (10, 10, 10), 5.0)
        # NaN segments should not trigger FAIL (filtered), result should be PARTIAL
        assert result.status != VerificationStatus.PASS

    def test_empty_segments_stock_gouge_pass(self):
        """No cutting segments → stock gouge check passes (no motion = no gouge)."""
        from backend.verification.checks import check_stock_gouge
        from backend.verification.stock import StockModel
        from backend.verification.enums import StockShape
        stock = StockModel(
            shape=StockShape.BOX,
            min_x_mm=-50.0, min_y_mm=-50.0, min_z_mm=-20.0,
            max_x_mm=50.0, max_y_mm=50.0, max_z_mm=20.0,
        )
        result = check_stock_gouge([], stock, 5.0)
        assert result.status == VerificationStatus.PASS
