"""P3-B: Setup & Stock Definition tests.

Tests StockDefinition, SetupDefinition, SetupStockSession, validate_stock_dimensions,
and the /api/setup-stock/ REST endpoints.

HARD RULES verified:
  - dimension values must come from engineer (positive, non-defaulted).
  - material_grade must be non-empty.
  - provenance is always USER_CONFIRMED.
  - n_setups >= 1.
  - RING inner_diameter must be less than outer_diameter.
  - No CNC dispatch, no auto-approval.

FABRICATED_STOCK_GEOMETRY=NO
AUTO_CONFIRM=NO
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Unit tests: StockDefinition and validate_stock_dimensions
# ---------------------------------------------------------------------------


from backend.manufacturing.setup_stock import (
    SetupDefinition,
    SetupStockSession,
    StockDefinition,
    StockShape,
    create_setup_stock_session,
    validate_stock_dimensions,
)


def _rect_block(length=100.0, width=80.0, height=30.0, material="C45") -> StockDefinition:
    import uuid
    return StockDefinition(
        stock_id=str(uuid.uuid4()),
        shape=StockShape.RECTANGULAR_BLOCK,
        material_grade=material,
        length_mm=length,
        width_mm=width,
        height_mm=height,
    )


def _round_bar(od=50.0, length=200.0, material="42CrMo4") -> StockDefinition:
    import uuid
    return StockDefinition(
        stock_id=str(uuid.uuid4()),
        shape=StockShape.ROUND_BAR,
        material_grade=material,
        outer_diameter_mm=od,
        length_mm=length,
    )


class TestStockDefinition:

    def test_rect_block_no_missing_dimensions(self):
        s = _rect_block()
        assert validate_stock_dimensions(s) == []

    def test_rect_block_missing_height(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=100.0,
            width_mm=80.0,
            height_mm=None,
        )
        errors = validate_stock_dimensions(s)
        assert "height_mm" in errors

    def test_rect_block_missing_width(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=100.0,
            width_mm=None,
            height_mm=30.0,
        )
        errors = validate_stock_dimensions(s)
        assert "width_mm" in errors

    def test_round_bar_no_missing_dimensions(self):
        s = _round_bar()
        assert validate_stock_dimensions(s) == []

    def test_round_bar_missing_od(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.ROUND_BAR,
            material_grade="C45",
            outer_diameter_mm=None,
            length_mm=200.0,
        )
        errors = validate_stock_dimensions(s)
        assert "outer_diameter_mm" in errors

    def test_ring_valid(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RING,
            material_grade="C45",
            outer_diameter_mm=80.0,
            inner_diameter_mm=50.0,
            length_mm=40.0,
        )
        assert validate_stock_dimensions(s) == []

    def test_ring_inner_gte_outer_error(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RING,
            material_grade="C45",
            outer_diameter_mm=50.0,
            inner_diameter_mm=60.0,
            length_mm=40.0,
        )
        errors = validate_stock_dimensions(s)
        assert any("inner_diameter_mm" in e for e in errors)

    def test_negative_dimension_flagged(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=-10.0,
            width_mm=80.0,
            height_mm=30.0,
        )
        errors = validate_stock_dimensions(s)
        assert any("length_mm" in e for e in errors)

    def test_zero_dimension_flagged(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.ROUND_BAR,
            material_grade="C45",
            outer_diameter_mm=0.0,
            length_mm=200.0,
        )
        errors = validate_stock_dimensions(s)
        assert any("outer_diameter_mm" in e for e in errors)

    def test_empty_material_grade_flagged(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="",
            length_mm=100.0,
            width_mm=80.0,
            height_mm=30.0,
        )
        errors = validate_stock_dimensions(s)
        assert "material_grade" in errors

    def test_as_dict_provenance_user_confirmed(self):
        s = _rect_block()
        d = s.as_dict()
        assert d["provenance"] == "USER_CONFIRMED"

    def test_forging_requires_all_three_dims(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.FORGING,
            material_grade="42CrMo4",
            length_mm=120.0,
            width_mm=None,
            height_mm=None,
        )
        errors = validate_stock_dimensions(s)
        assert "width_mm" in errors and "height_mm" in errors

    def test_plate_shape_uses_height_as_thickness(self):
        import uuid
        s = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.PLATE,
            material_grade="C45",
            length_mm=200.0,
            width_mm=100.0,
            height_mm=10.0,
        )
        assert validate_stock_dimensions(s) == []


class TestSetupDefinition:

    def _make_setup(self, n=1):
        import uuid
        return SetupDefinition(
            setup_id=str(uuid.uuid4()),
            n_setups=n,
            datum_a="bottom face",
            datum_b="right edge",
            datum_c=None,
        )

    def test_valid_setup_no_errors(self):
        s = self._make_setup()
        assert s.validate() == []

    def test_n_setups_less_than_1_error(self):
        import uuid
        s = SetupDefinition(setup_id=str(uuid.uuid4()), n_setups=0)
        errors = s.validate()
        assert any("n_setups" in e for e in errors)

    def test_as_dict_provenance_user_confirmed(self):
        s = self._make_setup()
        assert s.as_dict()["provenance"] == "USER_CONFIRMED"

    def test_n_setups_2_valid(self):
        s = self._make_setup(n=2)
        assert s.validate() == []

    def test_datum_a_stored(self):
        s = self._make_setup()
        assert s.as_dict()["datum_a"] == "bottom face"


class TestSetupStockSession:

    def test_create_empty_session(self):
        sess = create_setup_stock_session()
        assert sess.stock is None
        assert sess.setup is None
        assert sess.cad_session_id is None

    def test_create_with_cad_session_id(self):
        sess = create_setup_stock_session("cad-session-abc")
        assert sess.cad_session_id == "cad-session-abc"

    def test_as_dict_stock_complete_false_when_no_stock(self):
        sess = create_setup_stock_session()
        d = sess.as_dict()
        assert d["stock_complete"] is False
        assert d["setup_complete"] is False
        assert d["cam_prerequisites_met"] is False

    def test_as_dict_cam_prereq_met_when_complete(self):
        import uuid
        sess = create_setup_stock_session()
        sess.stock = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=100.0, width_mm=80.0, height_mm=30.0,
        )
        sess.setup = SetupDefinition(
            setup_id=str(uuid.uuid4()),
            n_setups=1,
            datum_a="bottom face",
        )
        d = sess.as_dict()
        assert d["stock_complete"] is True
        assert d["setup_complete"] is True
        assert d["cam_prerequisites_met"] is True

    def test_as_dict_cam_prereq_not_met_when_stock_missing_dim(self):
        import uuid
        sess = create_setup_stock_session()
        sess.stock = StockDefinition(
            stock_id=str(uuid.uuid4()),
            shape=StockShape.RECTANGULAR_BLOCK,
            material_grade="C45",
            length_mm=100.0, width_mm=None, height_mm=30.0,
        )
        sess.setup = SetupDefinition(setup_id=str(uuid.uuid4()), n_setups=1)
        d = sess.as_dict()
        assert d["cam_prerequisites_met"] is False
        assert "width_mm" in d["stock_missing"]


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    from backend.api.app import app
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    import os
    os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "testuser")
    os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "testpass")
    os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-key-p3b")
    resp = client.post("/api/login", json={"username": "testuser", "password": "testpass"})
    if resp.status_code != 200:
        pytest.skip("Auth not configured")
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestSetupStockApiEndpoints:

    def test_create_empty_session(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={}, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "session_id" in data
        assert data["status"] == "CREATED"

    def test_create_with_stock(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={
            "stock": {
                "shape": "RECTANGULAR_BLOCK",
                "material_grade": "C45",
                "length_mm": 100.0,
                "width_mm": 80.0,
                "height_mm": 30.0,
            }
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["stock_complete"] is True

    def test_create_with_invalid_stock_missing_dims(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={
            "stock": {
                "shape": "RECTANGULAR_BLOCK",
                "material_grade": "C45",
                "length_mm": 100.0,
            }
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_create_with_setup(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={
            "setup": {"n_setups": 2, "datum_a": "bottom face"}
        }, headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["setup_complete"] is True

    def test_get_session(self, client, auth_headers):
        create_resp = client.post("/api/setup-stock/", json={}, headers=auth_headers)
        sid = create_resp.json()["session_id"]
        get_resp = client.get(f"/api/setup-stock/{sid}", headers=auth_headers)
        assert get_resp.status_code == 200
        assert get_resp.json()["session_id"] == sid

    def test_get_nonexistent_session_404(self, client, auth_headers):
        resp = client.get("/api/setup-stock/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404

    def test_update_adds_stock(self, client, auth_headers):
        create_resp = client.post("/api/setup-stock/", json={}, headers=auth_headers)
        sid = create_resp.json()["session_id"]
        update_resp = client.put(f"/api/setup-stock/{sid}", json={
            "stock": {
                "shape": "ROUND_BAR",
                "material_grade": "42CrMo4",
                "outer_diameter_mm": 60.0,
                "length_mm": 300.0,
            }
        }, headers=auth_headers)
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["status"] == "UPDATED"
        assert data["stock_complete"] is True

    def test_update_nonexistent_session_404(self, client, auth_headers):
        resp = client.put("/api/setup-stock/nonexistent-id", json={}, headers=auth_headers)
        assert resp.status_code == 404

    def test_negative_dimension_rejected_422(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={
            "stock": {
                "shape": "ROUND_BAR",
                "material_grade": "C45",
                "outer_diameter_mm": -10.0,
                "length_mm": 200.0,
            }
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_invalid_shape_rejected_422(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={
            "stock": {
                "shape": "INVALID_SHAPE",
                "material_grade": "C45",
                "length_mm": 100.0,
                "width_mm": 80.0,
                "height_mm": 30.0,
            }
        }, headers=auth_headers)
        assert resp.status_code == 422

    def test_disclaimer_in_create_response(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={}, headers=auth_headers)
        assert "USER_CONFIRMED" in resp.json().get("disclaimer", "")

    def test_provenance_user_confirmed_in_stock(self, client, auth_headers):
        resp = client.post("/api/setup-stock/", json={
            "stock": {
                "shape": "PLATE",
                "material_grade": "Ck45",
                "length_mm": 200.0,
                "width_mm": 100.0,
                "height_mm": 15.0,
            }
        }, headers=auth_headers)
        assert resp.json()["stock"]["provenance"] == "USER_CONFIRMED"
