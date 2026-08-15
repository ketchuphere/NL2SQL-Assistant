"""
middleware/rate_limiter.py
──────────────────────────
Simple in-process token-bucket rate limiter middleware.

Limits requests per client IP.  For multi-process / production deployments
replace the in-memory dict with a Redis-backed store (e.g. ``slowapi``).

Configuration (from .env):
    RATE_LIMIT_REQUESTS=100   # max requests per window
    RATE_LIMIT_WINDOW=60      # sliding window in seconds
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.config.settings import settings


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """Sliding-window rate limiter keyed by client IP."""

    def __init__(self, app, requests: int | None = None, window: int | None = None) -> None:
        super().__init__(app)
        self.max_requests = requests or settings.rate_limit_requests
        self.window = window or settings.rate_limit_window
        # Maps IP → deque of timestamps
        self._buckets: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip rate limiting on health-check endpoints
        if request.url.path in {"/health", "/", "/docs", "/openapi.json", "/redoc"}:
            return await call_next(request)

        client_ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )

        now = time.time()
        bucket = self._buckets[client_ip]

        # Remove timestamps outside the sliding window
        while bucket and now - bucket[0] > self.window:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            retry_after = int(self.window - (now - bucket[0])) + 1
            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": (
                        f"Rate limit exceeded: {self.max_requests} requests "
                        f"per {self.window}s. Retry after {retry_after}s."
                    ),
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )

        bucket.append(now)
        response = await call_next(request)

        # Add rate-limit headers
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(self.max_requests - len(bucket))
        response.headers["X-RateLimit-Reset"] = str(int(now + self.window))
        return response
