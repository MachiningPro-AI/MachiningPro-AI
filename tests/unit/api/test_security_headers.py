"""Security header tests — MUST 6 (PRODUCTION_PILOT_FINAL_INFRASTRUCTURE_HARDENING).

Verifies that SecurityHeadersMiddleware injects the required headers on all
response paths, and that HSTS is omitted on plain-HTTP requests.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from backend.api.app import app

client = TestClient(app)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_REQUIRED_ALWAYS = [
    "x-content-type-options",
    "x-frame-options",
    "content-security-policy",
]

_REQUIRED_VALUES = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
}

_CSP_REQUIRED_DIRECTIVES = [
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
]


def _headers(response) -> dict[str, str]:
    return {k.lower(): v for k, v in response.headers.items()}


# ---------------------------------------------------------------------------
# Tests on unauthenticated public endpoints
# ---------------------------------------------------------------------------

class TestSecurityHeadersPublicEndpoints:

    def test_health_has_nosniff(self):
        h = _headers(client.get("/api/health"))
        assert h.get("x-content-type-options") == "nosniff"

    def test_health_has_x_frame_options_deny(self):
        h = _headers(client.get("/api/health"))
        assert h.get("x-frame-options") == "DENY"

    def test_health_has_csp(self):
        h = _headers(client.get("/api/health"))
        csp = h.get("content-security-policy", "")
        assert csp, "Content-Security-Policy header missing on /api/health"
        for directive in _CSP_REQUIRED_DIRECTIVES:
            assert directive in csp, f"CSP missing directive: {directive}"

    def test_ready_has_security_headers(self):
        h = _headers(client.get("/api/ready"))
        for header in _REQUIRED_ALWAYS:
            assert header in h, f"Missing {header} on /api/ready"

    def test_metrics_has_security_headers(self):
        h = _headers(client.get("/api/metrics"))
        for header in _REQUIRED_ALWAYS:
            assert header in h, f"Missing {header} on /api/metrics"

    def test_error_response_has_security_headers(self):
        """404 on unknown API path should still carry security headers."""
        h = _headers(client.get("/api/nonexistent-endpoint-xyz"))
        for header in _REQUIRED_ALWAYS:
            assert header in h, f"Missing {header} on 404 response"


class TestSecurityHeadersProtectedEndpoints:

    def test_protected_endpoint_401_has_security_headers(self):
        """Unauthenticated call to a protected endpoint should still return security headers."""
        h = _headers(client.get("/api/materials"))
        for header in _REQUIRED_ALWAYS:
            assert header in h, f"Missing {header} on 401 response from /api/materials"


class TestHSTSBehavior:

    def test_hsts_absent_on_plain_http(self):
        """HSTS must NOT be set on plain HTTP (TestClient default is http://)."""
        h = _headers(client.get("/api/health"))
        assert "strict-transport-security" not in h, (
            "HSTS must not be sent over plain HTTP — it would break local dev"
        )

    def test_hsts_present_on_https(self):
        """HSTS must be set when X-Forwarded-Proto indicates HTTPS."""
        h = _headers(
            client.get("/api/health", headers={"x-forwarded-proto": "https"})
        )
        hsts = h.get("strict-transport-security", "")
        assert "max-age=" in hsts, f"HSTS max-age missing on HTTPS request: {hsts!r}"
        assert "includeSubDomains" in hsts

    def test_hsts_not_sent_on_http_forwarded(self):
        """Explicit x-forwarded-proto: http must suppress HSTS."""
        h = _headers(
            client.get("/api/health", headers={"x-forwarded-proto": "http"})
        )
        assert "strict-transport-security" not in h


class TestCSPDirectives:

    def test_csp_no_unsafe_eval(self):
        """'unsafe-eval' must not appear in CSP — prohibits eval() in JS."""
        h = _headers(client.get("/api/health"))
        csp = h.get("content-security-policy", "")
        assert "unsafe-eval" not in csp

    def test_csp_no_wildcard_default(self):
        """CSP default-src must not be '*'."""
        h = _headers(client.get("/api/health"))
        csp = h.get("content-security-policy", "")
        assert "default-src *" not in csp
        assert "default-src '*'" not in csp

    def test_csp_frame_ancestors_none(self):
        """frame-ancestors 'none' must be present (consistent with X-Frame-Options: DENY)."""
        h = _headers(client.get("/api/health"))
        csp = h.get("content-security-policy", "")
        assert "frame-ancestors 'none'" in csp


class TestHealthVersionRemoved:

    def test_version_not_in_public_health(self):
        """Version string removed from unauthenticated /api/health (ADV-002 fix)."""
        data = client.get("/api/health").json()
        assert "version" not in data
