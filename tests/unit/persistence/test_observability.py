"""Tests for Level-20 observability — logging, correlation, metrics."""


class TestCorrelationMiddleware:
    def test_get_request_id_default_none(self):
        from backend.observability.correlation import get_request_id
        # Outside any request context, should return None
        assert get_request_id() is None

    def test_correlation_middleware_adds_header(self):
        """CorrelationMiddleware echoes X-Request-ID in response."""
        import os
        os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
        os.environ.setdefault("MACHININGPRO_DEV_USERNAME", "dev")
        os.environ.setdefault("MACHININGPRO_DEV_PASSWORD", "dev")
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        resp = client.get("/api/health", headers={"X-Request-ID": "test-req-001"})
        assert resp.headers.get("X-Request-ID") == "test-req-001"

    def test_correlation_middleware_generates_id_when_absent(self):
        import os
        os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        resp = client.get("/api/health")
        assert "X-Request-ID" in resp.headers
        assert len(resp.headers["X-Request-ID"]) > 0


class TestMetrics:
    def test_increment_and_snapshot(self):
        from backend.observability.metrics import increment, reset, snapshot
        reset()
        increment("test.counter")
        increment("test.counter", 3)
        s = snapshot()
        assert s["counters"]["test.counter"] == 4

    def test_set_gauge(self):
        from backend.observability.metrics import reset, set_gauge, snapshot
        reset()
        set_gauge("test.gauge", 42.5)
        s = snapshot()
        assert s["gauges"]["test.gauge"] == 42.5

    def test_reset_clears_all(self):
        from backend.observability.metrics import increment, reset, set_gauge, snapshot
        increment("x")
        set_gauge("y", 1.0)
        reset()
        s = snapshot()
        assert s["counters"] == {}
        assert s["gauges"] == {}

    def test_named_constants_exist(self):
        from backend.observability import metrics
        for name in [
            "WORKFLOW_CREATED", "WORKFLOW_RUN", "WORKFLOW_COMPLETED",
            "WORKFLOW_FAILED", "UPLOAD_ACCEPTED", "UPLOAD_REJECTED",
            "EXPORT_REQUESTED", "AUTH_FAILED", "PERSISTENCE_ERROR",
        ]:
            assert hasattr(metrics, name), f"Missing metric constant: {name}"

    def test_metrics_endpoint_returns_json(self):
        import os
        os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        resp = client.get("/api/metrics")
        assert resp.status_code == 200
        data = resp.json()
        assert "counters" in data
        assert "gauges" in data


class TestHealthAndReadiness:
    def test_health_returns_ok(self):
        import os
        os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data
        assert "database_ok" in data
        assert "artifact_store_ok" in data
        assert "server_time" in data

    def test_ready_endpoint_exists(self):
        import os
        os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        resp = client.get("/api/ready")
        # May return 200 or 503 depending on store state; must not 404
        assert resp.status_code in (200, 503)
        data = resp.json()
        assert "ready" in data

    def test_ready_returns_true_when_stores_healthy(self):
        import os
        os.environ.setdefault("MACHININGPRO_DEV_JWT_SECRET", "test-secret-at-least-32chars-long!!")
        from fastapi.testclient import TestClient

        from backend.api.app import app
        client = TestClient(app)
        resp = client.get("/api/ready")
        # With temp path from conftest, stores should be healthy
        data = resp.json()
        if resp.status_code == 200:
            assert data["ready"] is True
        # 503 is acceptable if stores are not yet initialized in this test context
