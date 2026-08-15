"""
middleware/logger.py
─────────────────────
Request/response logging middleware.

Logs every HTTP request with:
  - Method, path, status code, latency
  - Client IP  (X-Forwarded-For aware)
  - Correlation ID  (X-Request-ID header, auto-generated if absent)
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("nl2sql.access")


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start = time.perf_counter()

        # Inject request-id so downstream handlers can reference it
        request.state.request_id = request_id

        response: Response = await call_next(request)

        latency_ms = (time.perf_counter() - start) * 1000
        client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")

        logger.info(
            "%s %s %s %.1fms [%s] ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            latency_ms,
            request_id,
            client_ip,
        )

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Latency-Ms"] = f"{latency_ms:.1f}"
        return response
