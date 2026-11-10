"""Request correlation ID middleware and context variable.

Each incoming HTTP request gets a unique X-Request-ID header that flows
through logs and responses, enabling request→workflow→stage tracing.
"""
from __future__ import annotations

import uuid
from collections.abc import Callable
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

_REQUEST_ID_VAR: ContextVar[str | None] = ContextVar("request_id", default=None)

REQUEST_ID_HEADER = "X-Request-ID"


def get_request_id() -> str | None:
    """Return the correlation ID for the current async context, or None."""
    return _REQUEST_ID_VAR.get()


class CorrelationMiddleware(BaseHTTPMiddleware):
    """Reads or generates X-Request-ID, stores it in a ContextVar, and echoes it in the response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        req_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        token = _REQUEST_ID_VAR.set(req_id)
        try:
            response: Response = await call_next(request)
        finally:
            _REQUEST_ID_VAR.reset(token)
        response.headers[REQUEST_ID_HEADER] = req_id
        return response
