"""
Custom middleware for request tracing and rate limiting.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.core.logging_config import generate_request_id, get_logger, request_id_ctx

log = get_logger(__name__)


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Assigns every inbound request a unique ID, stores it in a context var,
    injects it into the response header, and logs request/response pairs.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        rid = generate_request_id()
        request_id_ctx.set(rid)

        log.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else "unknown",
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid

        log.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response
