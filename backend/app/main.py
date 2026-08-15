"""
main.py
────────
FastAPI application entry point for the NL2SQL RAG system.

Startup sequence
----------------
1. Apply all middleware (error handler, request logger, rate limiter).
2. Register API routers (health, documents, rag).
3. On startup: initialise Postgres tables.
4. On shutdown: close DB connection pool.

Run with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import documents, health, rag
from app.config.settings import settings
from app.db.postgres import close_db, init_db
from app.middleware.error_handler import ErrorHandlerMiddleware
from app.middleware.logger import RequestLoggerMiddleware
from app.middleware.rate_limiter import RateLimiterMiddleware

# ── Logging configuration ─────────────────────────────────────────────────────

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app/logs/app.log", encoding="utf-8"),
    ],
)

error_file_handler = logging.FileHandler("app/logs/error.log", encoding="utf-8")
error_file_handler.setLevel(logging.ERROR)
logging.getLogger().addHandler(error_file_handler)

logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s in '%s' mode…", settings.app_name, settings.app_env)
    await init_db()
    logger.info("Database tables initialised.")
    yield
    await close_db()
    logger.info("Database connection pool closed. Goodbye!")


# ── Application factory ───────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="NL2SQL RAG API",
        description=(
            "A Retrieval-Augmented Generation system that converts natural-language "
            "questions into executable SQL queries using schema-aware vector search "
            "and an LLM generator with self-healing retry logic.\n\n"
            "**Supported Databases:** MySQL · PostgreSQL · Snowflake · SQL Server"
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── Middleware (order matters — outermost runs first on request) ──────────
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestLoggerMiddleware)
    app.add_middleware(RateLimiterMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(rag.router, prefix="/api/v1")

    logger.info("All routers registered.")
    return app


app = create_app()
