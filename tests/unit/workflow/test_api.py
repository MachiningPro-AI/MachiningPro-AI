"""API endpoint tests for the Level-19 workflow router."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from backend.api.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Get auth headers for authenticated endpoints."""
    # Try to login with test credentials
    resp = client.post("/api/login", json={"username": "admin", "password": "admin"})
    if resp.status_code == 200:
        token = resp.json().get("access_token", "")
        return {"Authorization": f"Bearer {token}"}
    return {}


class TestCreateWorkflow:
    def test_create_basic(self, client):
        resp = client.post("/api/workflow", json={
            "part_reference": "API_TEST_PART",
            "revision": "REV-A",
            "requested_mode": "ANALYSIS_ONLY",
            "objective": "BALANCED",
            "quantity": 1,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert "workflow_id" in data
        assert data["part_reference"] == "API_TEST_PART"
        assert data["status"] == "CREATED"

    def test_create_with_material(self, client):
        resp = client.post("/api/workflow", json={
            "part_reference": "PART_WITH_MAT",
            "material_ref": "AL6061",
            "quantity": 5,
            "objective": "MINIMUM_COST",
        })
        assert resp.status_code == 201
        assert resp.json()["material_ref"] == "AL6061"

    def test_create_invalid_mode(self, client):
        resp = client.post("/api/workflow", json={
            "part_reference": "P",
            "requested_mode": "INVALID_MODE_XYZ",
        })
        assert resp.status_code == 422


class TestGetWorkflow:
    def test_get_existing(self, client):
        # Create first
        create_resp = client.post("/api/workflow", json={
            "part_reference": "GET_TEST",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]

        # Get it
        resp = client.get(f"/api/workflow/{wid}")
        assert resp.status_code == 200
        assert resp.json()["workflow_id"] == wid

    def test_get_nonexistent(self, client):
        resp = client.get("/api/workflow/NONEXISTENT_WF_12345")
        assert resp.status_code == 404


class TestRunWorkflow:
    def test_run_analysis_only(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "RUN_TEST",
            "requested_mode": "ANALYSIS_ONLY",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]

        run_resp = client.post(f"/api/workflow/{wid}/run")
        assert run_resp.status_code == 200
        status = run_resp.json()["status"]
        assert status in ("PARTIAL", "COMPLETED", "FAILED", "CANCELLED")

    def test_run_nonexistent(self, client):
        resp = client.post("/api/workflow/NONEXISTENT_RUN/run")
        assert resp.status_code == 404


class TestGetStages:
    def test_stages_returns_19_stages(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "STAGES_TEST",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]

        resp = client.get(f"/api/workflow/{wid}/stages")
        assert resp.status_code == 200
        stages = resp.json()
        assert len(stages) == 19

    def test_stages_all_have_status(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "STAGES_STATUS",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]
        resp = client.get(f"/api/workflow/{wid}/stages")
        for stage in resp.json():
            assert "status" in stage
            assert "stage" in stage


class TestGetPlan:
    def test_plan_not_available_before_run(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "PLAN_TEST",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]
        resp = client.get(f"/api/workflow/{wid}/plan")
        assert resp.status_code == 404

    def test_plan_production_approved_false(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "PLAN_SAFETY",
            "requested_mode": "FULL_MANUFACTURING_PLAN",
            "material_ref": "AL6061",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]
        client.post(f"/api/workflow/{wid}/run")

        plan_resp = client.get(f"/api/workflow/{wid}/plan")
        if plan_resp.status_code == 200:
            plan = plan_resp.json()
            assert plan["production_approved"] is False
            assert plan["dispatched"] is False
            assert plan["machine_started"] is False


class TestCancelWorkflow:
    def test_cancel_sets_cancelled_status(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "CANCEL_TEST",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]
        resp = client.post(f"/api/workflow/{wid}/cancel")
        assert resp.status_code == 200
        assert resp.json()["status"] == "CANCELLED"


class TestResumeWorkflow:
    def test_resume_does_not_crash(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "RESUME_TEST",
            "requested_mode": "ANALYSIS_ONLY",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]
        client.post(f"/api/workflow/{wid}/run")
        resp = client.post(f"/api/workflow/{wid}/resume")
        assert resp.status_code == 200


class TestRetryWorkflow:
    def test_retry_blocked_stage(self, client):
        create_resp = client.post("/api/workflow", json={
            "part_reference": "RETRY_TEST",
            "requested_mode": "ANALYSIS_ONLY",
            "quantity": 1,
        })
        wid = create_resp.json()["workflow_id"]
        client.post(f"/api/workflow/{wid}/run")

        resp = client.post(f"/api/workflow/{wid}/retry", json={"stage": "01_CAD_IMPORT"})
        assert resp.status_code == 200


class TestNoMachineControlEndpoints:
    """Verify no machine-control endpoints exist."""

    def test_no_cnc_endpoint(self, client):
        resp = client.post("/api/workflow/test/cnc-start", json={})
        assert resp.status_code in (404, 405, 422)

    def test_no_machine_start_endpoint(self, client):
        resp = client.post("/api/workflow/test/machine-start", json={})
        assert resp.status_code in (404, 405, 422)

    def test_no_dispatch_endpoint(self, client):
        resp = client.post("/api/workflow/test/dispatch", json={})
        assert resp.status_code in (404, 405, 422)
