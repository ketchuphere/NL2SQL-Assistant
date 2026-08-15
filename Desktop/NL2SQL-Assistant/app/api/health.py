"""
api/health.py
──────────────
Health-check endpoint for liveness and readiness probes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health", summary="Liveness check")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "NL2SQL-RAG",
    }


@router.get("/", include_in_schema=False)
async def root():
    return {"message": "NL2SQL RAG API is running. Visit /docs for the API reference."}
