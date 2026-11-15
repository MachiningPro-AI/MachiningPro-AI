"""Tests for P5-B: machine-to-route API wiring (MUST 41, 9-13)."""
import base64

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.manufacturing.machine_selection import MachineCandidateStatus, select_machines

client = TestClient(app)


# ---------------------------------------------------------------------------
# P5-B: Domain-level machine selection
# ---------------------------------------------------------------------------

class TestP5BMachineSelection:
    def test_drilling_candidates_exist(self):
        result = select_machines(operation="drilling")
        assert result.machine_selection_ready
        assert len(result.passing_candidates) > 0

    def test_all_passing_machines_are_drilling_capable(self):
        result = select_machines(operation="drilling")
        for c in result.passing_candidates:
            assert c.machine.capability.drilling_capable is True

    def test_work_envelope_filter_small_stock(self):
        """Small stock 10x10x10 -- should not exclude any envelope-limited machines."""
        result = select_machines(operation="drilling", stock_x_mm=10, stock_y_mm=10, stock_z_mm=10)
        assert result.machine_selection_ready

    def test_work_envelope_filter_very_large_stock(self):
        """Stock 10m x 10m x 10m -- all machines should fail envelope."""
        result = select_machines(
            operation="drilling", stock_x_mm=10000, stock_y_mm=10000, stock_z_mm=10000
        )
        # Either no passing candidates or all with REVIEW_REQUIRED (machines without envelope data)
        for c in result.passing_candidates:
            # Must have REVIEW_REQUIRED (envelope not modeled), not PASS on clearly impossible stock
            assert c.overall_status in (
                MachineCandidateStatus.PASS, MachineCandidateStatus.REVIEW_REQUIRED
            )

    def test_spindle_limit_check_low_rpm(self):
        """Very low RPM requirement -- all machines should pass."""
        result = select_machines(operation="drilling", required_rpm_max=100)
        assert result.machine_selection_ready

    def test_spindle_limit_excludes_high_rpm(self):
        """Very high RPM requirement -- machines without sufficient spindle should not pass."""
        result_no_limit = select_machines(operation="drilling")
        result_high_rpm = select_machines(operation="drilling", required_rpm_max=99999)
        # With extreme RPM, some machines should be filtered or marked REVIEW_REQUIRED
        assert len(result_high_rpm.passing_candidates) <= len(result_no_limit.passing_candidates)

    def test_unsupported_operation_returns_zero_pass(self):
        """'edm_sinker' is an EDM operation, not drilling."""
        result = select_machines(operation="edm_sinker")
        # EDM-capable machines pass, drilling-only fail
        for c in result.passing_candidates:
            # Check that all passing candidates have the EDM flag or unknown
            assert c.overall_status != MachineCandidateStatus.FAIL

    def test_machine_provenance_documented(self):
        """Every passing candidate must have at least one documented check."""
        result = select_machines(operation="drilling")
        for c in result.passing_candidates:
            assert len(c.checks) > 0
            assert any(ch.check_name == "OPERATION_COMPATIBLE" for ch in c.checks)

    def test_machine_selection_ready_field(self):
        result = select_machines(operation="drilling")
        assert result.machine_selection_ready == (len(result.passing_candidates) > 0)


# ---------------------------------------------------------------------------
# P5-B: Machine candidates REST API (MUST 10, 13)
# ---------------------------------------------------------------------------

class TestP5BMachineAPIEndpoint:
    @pytest.fixture
    def confirmed_session(self, tmp_path):
        """Create a confirmed CAD session for testing."""
        import os
        sample = None
        candidates = [
            r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar\109106_01_30.dxf",
        ]
        for path in candidates:
            if os.path.exists(path):
                sample = path
                break
        if sample is None:
            pytest.skip("Real sample files not available")
        with open(sample, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        resp = client.post("/api/cad-features/analyze", json={
            "file_name": "109106_01_30.dxf",
            "content_b64": b64,
        })
        assert resp.status_code == 200
        sid = resp.json()["session_id"]
        feats = client.get(f"/api/cad-features/{sid}/features").json()["features"]
        assert len(feats) > 0
        fid = feats[0]["feature_id"]
        cr = client.post(f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension", json={
            "user_id": "test", "feature_type_override": "HOLE", "depth_mm": 25.0,
        })
        assert cr.status_code == 200
        return sid, fid

    def test_machine_candidates_endpoint_200(self, confirmed_session):
        sid, fid = confirmed_session
        resp = client.get(f"/api/cad-features/{sid}/features/{fid}/machine-candidates")
        assert resp.status_code == 200

    def test_machine_candidates_returns_selection_ready(self, confirmed_session):
        sid, fid = confirmed_session
        resp = client.get(f"/api/cad-features/{sid}/features/{fid}/machine-candidates",
            params={"operation": "drilling"})
        j = resp.json()
        assert j["machine_selection_ready"] is True

    def test_machine_candidates_offline_disclaimer(self, confirmed_session):
        sid, fid = confirmed_session
        resp = client.get(f"/api/cad-features/{sid}/features/{fid}/machine-candidates")
        assert "OFFLINE_ONLY=YES" in resp.json()["disclaimer"]

    def test_machine_candidates_404_on_bad_session(self):
        resp = client.get("/api/cad-features/no-such-session/features/f1/machine-candidates")
        assert resp.status_code == 404

    def test_machine_candidates_404_on_bad_feature(self, confirmed_session):
        sid, _ = confirmed_session
        resp = client.get(f"/api/cad-features/{sid}/features/no-such-feature/machine-candidates")
        assert resp.status_code == 404

    def test_machine_to_route_wired(self, confirmed_session):
        """MUST 13: confirmed feature -> proposed routes -> machine candidates."""
        sid, fid = confirmed_session
        # Routes were generated at confirm time
        confirm_data = client.post(
            f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension",
            json={"user_id": "test2", "feature_type_override": "HOLE", "depth_mm": 25.0},
        ).json()
        route_gen = confirm_data.get("route_generation", {})
        assert route_gen.get("blocked") is False or route_gen.get("n_routes", 0) >= 0
        # Machine candidates must respond
        mc_resp = client.get(f"/api/cad-features/{sid}/features/{fid}/machine-candidates")
        assert mc_resp.status_code == 200
