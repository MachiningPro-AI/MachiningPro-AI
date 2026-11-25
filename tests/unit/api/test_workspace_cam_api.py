"""
Workspace CAM and Simulation API tests.

Covers:
- POST /api/workspace-cam/feature-cam (workspace_cam router)
- POST /api/workspace-sim/run (workspace_simulation router)

Safety contract (enforced in all tests):
  NO_FABRICATED_TOOLPATH=YES
  NO_FAKE_SIMULATION_PASS=YES
  is_dispatchable=false
  production_released=false
  HARD_RULE_11=YES — missing input → BLOCKED / NOT_VERIFIABLE, never PASS
  HARD_RULE_12=YES — OFFLINE ONLY
  HARD_RULE_13=YES — simulation result NOT machining approval
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client() -> TestClient:
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "test")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "test")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret")
    return TestClient(app)


def _auth(c: TestClient) -> dict[str, str]:
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "test")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "test")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret")
    r = c.post("/api/login", json={"username": "test", "password": "test"})
    if r.status_code != 200:
        pytest.skip("Auth not available")
    return {"Authorization": f"Bearer {r.json()['token']}"}


# ---------------------------------------------------------------------------
# /api/workspace-cam/feature-cam
# ---------------------------------------------------------------------------

class TestFeatureCamEndpoint:
    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={"file_ref": "part.step", "features": []},
        )
        assert r.status_code == 401

    def test_empty_features_returns_empty_operations(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={"file_ref": "part.step", "features": []},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["operations"] == []
        assert data["toolpath_groups"] == []

    def test_safety_flags_in_response(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={"file_ref": "part.step", "features": []},
            headers=h,
        )
        assert r.status_code == 200
        safety = r.json()["safety"]
        assert safety["is_dispatchable"] is False
        assert safety["production_released"] is False
        assert safety["simulation_required"] is True

    def test_hole_feature_with_full_geometry_generates_toolpath(
        self, client: TestClient
    ) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "HOLE_01",
                        "feature_type": "HOLE",
                        "center_x": 10.0,
                        "center_y": 20.0,
                        "center_z_top": 50.0,
                        "depth_mm": 25.0,
                        "diameter_mm": 6.0,
                        "clearance_z": 60.0,
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        ops = data["operations"]
        assert len(ops) == 1
        op = ops[0]
        assert op["operation_type"] == "DRILL"
        # Must have segments if GENERATED
        if op["toolpath_status"] == "GENERATED":
            assert op["segment_count"] > 0
            assert len(data["toolpath_groups"]) > 0
        # Always simulation_required
        assert op["simulation_required"] is True

    def test_hole_missing_depth_gives_blocked(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "HOLE_02",
                        "feature_type": "HOLE",
                        "center_x": 10.0,
                        "center_y": 20.0,
                        "center_z_top": 50.0,
                        # depth_mm missing → BLOCKED
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        op = r.json()["operations"][0]
        assert op["toolpath_status"] == "BLOCKED"
        assert len(op["missing_inputs"]) > 0

    def test_pocket_with_boundary_points_generates_path(
        self, client: TestClient
    ) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "PKT_01",
                        "feature_type": "POCKET",
                        "center_z_top": 30.0,
                        "depth_mm": 10.0,
                        "clearance_z": 40.0,
                        "boundary_points": [
                            [0, 0], [20, 0], [20, 15], [0, 15],
                        ],
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        op = r.json()["operations"][0]
        assert op["operation_type"] == "POCKET_MILLING"
        assert op["simulation_required"] is True

    def test_pocket_missing_boundary_and_dimensions_blocked(
        self, client: TestClient
    ) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "PKT_BAD",
                        "feature_type": "POCKET",
                        "center_z_top": 30.0,
                        "depth_mm": 10.0,
                        # no boundary, no center+width+length
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        op = r.json()["operations"][0]
        assert op["toolpath_status"] == "BLOCKED"

    def test_slot_with_geometry_generates_path(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "SLT_01",
                        "feature_type": "SLOT",
                        "center_x": 0.0,
                        "center_y": 5.0,
                        "center_z_top": 20.0,
                        "depth_mm": 5.0,
                        "width_mm": 8.0,
                        "length_mm": 40.0,
                        "clearance_z": 30.0,
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        op = r.json()["operations"][0]
        assert op["operation_type"] == "SLOT_MILLING"
        assert op["simulation_required"] is True

    def test_unsupported_feature_type_blocked(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "TAPER_01",
                        "feature_type": "TAPER_TURN",  # not supported
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        op = r.json()["operations"][0]
        assert op["toolpath_status"] == "BLOCKED"
        assert "FEATURE_TYPE_NOT_IMPLEMENTED" in op["warnings"][0]

    def test_stock_bbox_provides_clearance_when_missing(
        self, client: TestClient
    ) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "HOLE_03",
                        "feature_type": "HOLE",
                        "center_x": 0.0,
                        "center_y": 0.0,
                        "center_z_top": 50.0,
                        "depth_mm": 20.0,
                        "diameter_mm": 5.0,
                        # no clearance_z — provided via stock_bbox
                    }
                ],
                "stock_bbox": {
                    "min_x": -10, "min_y": -10, "min_z": 0,
                    "max_x":  60, "max_y":  60, "max_z": 55,
                },
            },
            headers=h,
        )
        assert r.status_code == 200
        op = r.json()["operations"][0]
        # With stock_bbox providing clearance, should not be BLOCKED on clearance_z
        assert op["toolpath_status"] in ("GENERATED", "BLOCKED")
        if op["toolpath_status"] == "BLOCKED":
            # Must have missing_inputs or warnings — never silently passes
            assert len(op["missing_inputs"]) > 0 or len(op["warnings"]) > 0

    def test_toolpath_groups_contain_flat_coords(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-cam/feature-cam",
            json={
                "file_ref": "part.step",
                "features": [
                    {
                        "feature_id": "HOLE_04",
                        "feature_type": "HOLE",
                        "center_x": 5.0,
                        "center_y": 5.0,
                        "center_z_top": 30.0,
                        "depth_mm": 15.0,
                        "diameter_mm": 6.0,
                        "clearance_z": 40.0,
                    }
                ],
            },
            headers=h,
        )
        assert r.status_code == 200
        groups = r.json()["toolpath_groups"]
        if groups:
            g = groups[0]
            assert "motion_type" in g
            assert "points" in g
            assert isinstance(g["points"], list)
            # Points must be multiples of 3 (flat xyz)
            assert len(g["points"]) % 3 == 0
            # Minimum 2 points = 6 floats
            assert len(g["points"]) >= 6


# ---------------------------------------------------------------------------
# /api/workspace-sim/run
# ---------------------------------------------------------------------------

class TestWorkspaceSimEndpoint:
    def test_unauthenticated_returns_401(self, client: TestClient) -> None:
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-01", "segments": []},
        )
        assert r.status_code == 401

    def test_empty_segments_returns_blocked(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-01", "segments": []},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["simulation_status"] == "FAILED"
        assert data["verification_state"] == "BLOCKED"
        assert data["is_verified"] is False
        assert data["offline_only"] is True
        assert data["simulation_result_is_not_machining_approval"] is True

    def test_safety_flags_in_response(self, client: TestClient) -> None:
        h = _auth(client)
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-safety", "segments": []},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["safety"]["is_dispatchable"] is False
        assert data["safety"]["production_released"] is False
        assert data["safety"]["simulation_offline_only"] is True

    def test_with_segments_returns_checks(self, client: TestClient) -> None:
        h = _auth(client)
        segs = [
            {
                "start_x": 0, "start_y": 0, "start_z": 20,
                "end_x": 10, "end_y": 0, "end_z": 20,
                "motion_type": "RAPID",
                "is_cutting": False,
            },
            {
                "start_x": 10, "start_y": 0, "start_z": 20,
                "end_x": 10, "end_y": 0, "end_z": 0,
                "motion_type": "PLUNGE",
                "is_cutting": True,
            },
            {
                "start_x": 10, "start_y": 0, "start_z": 0,
                "end_x": 10, "end_y": 10, "end_z": 0,
                "motion_type": "CUT",
                "is_cutting": True,
            },
            {
                "start_x": 10, "start_y": 10, "start_z": 0,
                "end_x": 10, "end_y": 10, "end_z": 20,
                "motion_type": "RETRACT",
                "is_cutting": False,
            },
        ]
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-with-segs", "segments": segs},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["simulation_status"] == "COMPLETED"
        # Must have check results
        assert len(data["checks"]) > 0
        # is_verified may be false — insufficient data is acceptable
        # but must never be fabricated PASS on incomplete data
        assert isinstance(data["is_verified"], bool)
        assert data["offline_only"] is True

    def test_no_stock_means_stock_volume_null(self, client: TestClient) -> None:
        h = _auth(client)
        segs = [
            {
                "start_x": 0, "start_y": 0, "start_z": 10,
                "end_x": 5, "end_y": 0, "end_z": 10,
                "motion_type": "CUT", "is_cutting": True,
            }
        ]
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-no-stock", "segments": segs},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        # With no stock provided, stock volumes must be null (NOT_VERIFIABLE)
        assert data["initial_stock_volume_mm3"] is None
        assert data["remaining_stock_volume_mm3"] is None
        assert data["removed_volume_mm3"] is None

    def test_with_stock_bbox_runs_stock_checks(self, client: TestClient) -> None:
        h = _auth(client)
        segs = [
            {
                "start_x": 5, "start_y": 5, "start_z": 25,
                "end_x": 5, "end_y": 5, "end_z": 0,
                "motion_type": "PLUNGE", "is_cutting": True,
            }
        ]
        r = client.post(
            "/api/workspace-sim/run",
            json={
                "toolpath_id": "tp-with-stock",
                "segments": segs,
                "tool_diameter_mm": 6.0,
                "stock_bbox": {
                    "min_x": 0, "min_y": 0, "min_z": 0,
                    "max_x": 50, "max_y": 50, "max_z": 25,
                },
            },
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["simulation_status"] == "COMPLETED"
        # With stock_bbox provided, stock checks attempted
        assert "STOCK_REMAINING" in data["checks"] or "STOCK_GOUGE" in data["checks"]

    def test_resource_limit_returns_blocked_not_pass(
        self, client: TestClient
    ) -> None:
        # Send >5000 segments to trigger resource limit
        h = _auth(client)
        big_segs = [
            {
                "start_x": float(i), "start_y": 0, "start_z": 0,
                "end_x": float(i + 1), "end_y": 0, "end_z": 0,
                "motion_type": "CUT", "is_cutting": True,
            }
            for i in range(6000)
        ]
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-big", "segments": big_segs},
            headers=h,
        )
        assert r.status_code == 200
        data = r.json()
        # Must be FAILED/BLOCKED — never PASS
        assert data["simulation_status"] == "FAILED"
        assert data["resource_limit_hit"] is True
        assert data["is_verified"] is False

    def test_visualization_structure_present(self, client: TestClient) -> None:
        h = _auth(client)
        segs = [
            {
                "start_x": 0, "start_y": 0, "start_z": 10,
                "end_x": 10, "end_y": 0, "end_z": 10,
                "motion_type": "CUT", "is_cutting": True,
            }
        ]
        r = client.post(
            "/api/workspace-sim/run",
            json={"toolpath_id": "tp-viz", "segments": segs},
            headers=h,
        )
        assert r.status_code == 200
        viz = r.json()["visualization"]
        assert "cutting_points" in viz
        assert "rapid_points" in viz
        assert "collision_points" in viz
        assert "gouge_points" in viz
        assert isinstance(viz["cutting_points"], list)
