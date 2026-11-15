"""P5 E2E qualification tests: DXF real samples (MUST 45, 29-35)."""
import base64
import os

import pytest
from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

SAMPLE_DIR = r"D:\makina_ogrenmesi\olcum_denemeleri\örnek dosyalar"


def _path(fname: str) -> str:
    return os.path.join(SAMPLE_DIR, fname)


def _b64(fname: str) -> str:
    with open(_path(fname), "rb") as f:
        return base64.b64encode(f.read()).decode()


def _skip_if_missing(fname: str):
    if not os.path.exists(_path(fname)):
        pytest.skip(f"Real sample {fname!r} not available")


def _full_p5_flow(fname: str, depth_mm: float, material: str = "C45"):
    """Run the full P5 flow for one DXF file. Returns metrics dict."""
    _skip_if_missing(fname)
    b64 = _b64(fname)
    sid = client.post("/api/cad-features/analyze", json={
        "file_name": fname, "content_b64": b64,
    }).json()["session_id"]

    feats = client.get(f"/api/cad-features/{sid}/features").json()["features"]
    if not feats:
        return {"feature_count": 0}

    fid = feats[0]["feature_id"]
    diam = feats[0].get("diameter_mm")

    cr = client.post(f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension", json={
        "user_id": "qualification", "feature_type_override": "HOLE", "depth_mm": depth_mm,
    })
    assert cr.status_code == 200

    # Machine candidates
    mc = client.get(f"/api/cad-features/{sid}/features/{fid}/machine-candidates",
        params={"operation": "drilling", "stock_x_mm": 100, "stock_y_mm": 80, "stock_z_mm": 30})
    mj = mc.json()

    # Tool candidates
    tc = client.get(
        f"/api/cad-features/{sid}/features/{fid}/tool-candidates",
        params={"operation": "drilling", "material_grade": material,
                "required_cutting_length_mm": depth_mm},
    )
    tj = tc.json()

    # CAM gate
    ss = client.post("/api/setup-stock/", json={
        "cad_session_id": sid,
        "stock": {"shape": "RECTANGULAR_BLOCK", "material_grade": material,
                  "length_mm": 100, "width_mm": 80, "height_mm": 30},
        "setup": {"datum_a": "Bottom face"},
    })
    ss_id = ss.json()["session_id"]
    cam = client.get(f"/api/setup-stock/{ss_id}/cam-status", params={"cad_session_id": sid})
    cj = cam.json()

    return {
        "feature_count": len(feats),
        "diameter_mm": diam,
        "machine_selection_ready": mj.get("machine_selection_ready", False),
        "machine_candidate_count": mj.get("candidate_count", 0),
        "tool_selection_ready": tj.get("tool_selection_ready", False),
        "cutting_data_ready": tj.get("cutting_data_ready", False),
        "best_tool": tj.get("best_match_stable_id"),
        "tool_candidate_count": tj.get("candidate_count", 0),
        "cam_ready": cj.get("overall_cam_ready", False),
        "cam_first_blocker": cj.get("first_blocker"),
    }


class TestP5EDxf01E2E:
    def test_dxf01_machine_selection_ready(self):
        m = _full_p5_flow("109106_01_30.dxf", depth_mm=25.0)
        assert m["machine_selection_ready"] is True

    def test_dxf01_tool_selection_ready(self):
        m = _full_p5_flow("109106_01_30.dxf", depth_mm=25.0)
        assert m["tool_selection_ready"] is True

    def test_dxf01_cutting_data_ready(self):
        m = _full_p5_flow("109106_01_30.dxf", depth_mm=25.0)
        assert m["cutting_data_ready"] is True

    def test_dxf01_cam_ready(self):
        m = _full_p5_flow("109106_01_30.dxf", depth_mm=25.0)
        assert m["cam_ready"] is True

    def test_dxf01_best_tool_is_5mm_sandvik(self):
        m = _full_p5_flow("109106_01_30.dxf", depth_mm=25.0)
        # Best match is 5.0mm sandvik drill (COMPATIBLE for 4.891mm feature)
        assert m["best_tool"] == "sandvik-860-1-0500-026a1-pm"

    def test_dxf01_no_auto_approval(self):
        """Route status must remain PROPOSED, not auto-approved."""
        _skip_if_missing("109106_01_30.dxf")
        b64 = _b64("109106_01_30.dxf")
        sid = client.post("/api/cad-features/analyze", json={
            "file_name": "109106_01_30.dxf", "content_b64": b64,
        }).json()["session_id"]
        feats = client.get(f"/api/cad-features/{sid}/features").json()["features"]
        fid = feats[0]["feature_id"]
        cr = client.post(f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension", json={
            "user_id": "test", "feature_type_override": "HOLE", "depth_mm": 25.0,
        }).json()
        route_gen = cr.get("route_generation", {})
        routes = route_gen.get("routes", [])
        for r in routes:
            status = r.get("status", "")
            assert status != "AUTO_APPROVED", f"Route {r.get('route_id')} was AUTO_APPROVED"


class TestP5EDxf02E2E:
    def test_dxf02_machine_selection_ready(self):
        """DXF-02: 60mm feature -- machines available but no drill tool."""
        m = _full_p5_flow("109106_01_22.dxf", depth_mm=25.0)
        assert m["machine_selection_ready"] is True

    def test_dxf02_tool_not_ready(self):
        """DXF-02: 60mm feature -- no solid carbide drill in catalog (correct NO_MATCH)."""
        m = _full_p5_flow("109106_01_22.dxf", depth_mm=25.0)
        assert m["tool_selection_ready"] is False

    def test_dxf02_cam_ready(self):
        """DXF-02: CAM gate still passes (confirmed feature + stock)."""
        m = _full_p5_flow("109106_01_22.dxf", depth_mm=25.0)
        assert m["cam_ready"] is True


class TestP5EDxf03E2E:
    def test_dxf03_machine_selection_ready(self):
        """DXF-03: 8.5mm feature -- machines available."""
        m = _full_p5_flow("Pense_Sema.dxf", depth_mm=10.0)
        assert m["machine_selection_ready"] is True

    def test_dxf03_tool_not_ready(self):
        """DXF-03: 8.5mm feature -- no drill in 3-8mm range matches 8.5mm (correct NO_MATCH)."""
        m = _full_p5_flow("Pense_Sema.dxf", depth_mm=10.0)
        assert m["tool_selection_ready"] is False

    def test_dxf03_cam_ready(self):
        m = _full_p5_flow("Pense_Sema.dxf", depth_mm=10.0)
        assert m["cam_ready"] is True


class TestP5ENoRegression:
    def test_offline_only_flag_all_samples(self):
        for fname, depth in [
            ("109106_01_30.dxf", 25.0),
            ("109106_01_22.dxf", 25.0),
            ("Pense_Sema.dxf", 10.0),
        ]:
            if not os.path.exists(_path(fname)):
                continue
            _full_p5_flow(fname, depth_mm=depth)
            # CAM gate offline_only check is part of the gate itself
            # Verify no machine write / no dispatch by checking machine candidate disclaimer
            b64 = _b64(fname)
            sid = client.post("/api/cad-features/analyze", json={
                "file_name": fname, "content_b64": b64,
            }).json()["session_id"]
            feats = client.get(f"/api/cad-features/{sid}/features").json()["features"]
            if not feats:
                continue
            fid = feats[0]["feature_id"]
            client.post(f"/api/cad-features/{sid}/features/{fid}/confirm-with-dimension", json={
                "user_id": "test", "feature_type_override": "HOLE", "depth_mm": depth,
            })
            mc = client.get(f"/api/cad-features/{sid}/features/{fid}/machine-candidates").json()
            assert "OFFLINE_ONLY=YES" in mc.get("disclaimer", "")
            tc = client.get(f"/api/cad-features/{sid}/features/{fid}/tool-candidates").json()
            assert "OFFLINE_ONLY=YES" in tc.get("disclaimer", "")
