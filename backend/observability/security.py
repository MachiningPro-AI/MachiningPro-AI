"""HTTP security headers middleware.

Adds the following headers to every response:
  X-Content-Type-Options: nosniff
  X-Frame-Options: DENY
  Content-Security-Policy: (strict SPA-compatible policy)
  Strict-Transport-Security: (HTTPS-only; omitted on plain HTTP)
"""
from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# CSP suited to the production SPA bundle:
#   - all resources self-hosted (no CDN)
#   - no inline <script> blocks in dist/index.html
#   - React may apply inline styles; 'unsafe-inline' is required for style-src
#   - File-preview UIs may generate blob: / data: image URLs
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_HSTS = "max-age=31536000; includeSubDomains"


def _is_https(request: Request) -> bool:
    """Return True when the request arrived over HTTPS (direct or via reverse proxy)."""
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return forwarded_proto.lower() == "https" or str(request.url).startswith("https://")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every HTTP response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = _CSP
        if _is_https(request):
            response.headers["Strict-Transport-Security"] = _HSTS
        return response
