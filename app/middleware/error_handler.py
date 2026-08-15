"""
middleware/error_handler.py
Global FastAPI exception handler middleware.

Catches any unhandled exception and returns a consistent JSON error envelope:
    {
        "error":   "<error type>",
        "message": "<human-readable message>",
        "path":    "<request path>",
        "status":  <HTTP status code>
    }
"""

from __future__ import annotations
import logging
import traceback
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)

        except ValueError as exc:
            logger.warning("ValueError on %s: %s", request.url.path, exc)
            return JSONResponse(
                status_code=400,
                content={
                    "error": "Bad Request",
                    "message": str(exc),
                    "path": str(request.url.path),
                    "status": 400,
                },
            )

        except PermissionError as exc:
            logger.warning("PermissionError on %s: %s", request.url.path, exc)
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": str(exc),
                    "path": str(request.url.path),
                    "status": 403,
                },
            )

        except Exception as exc:
            logger.error(
                "Unhandled exception on %s:\n%s",
                request.url.path,
                traceback.format_exc(),
            )
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred. Please try again.",
                    "path": str(request.url.path),
                    "status": 500,
                },
            )
