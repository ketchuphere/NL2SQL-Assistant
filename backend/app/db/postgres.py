"""
db/postgres.py
──────────────
Async SQLAlchemy engine + session factory for the internal Postgres
metadata store (query history, session data, user records).

This is NOT the target database that users query in natural language —
that lives in app/rag/pipeline.py via the SQL connectors.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config.settings import settings

# ── Engine ────────────────────────────────────────────────────────────────────
engine: AsyncEngine = create_async_engine(
    settings.postgres_url,
    echo=settings.debug,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

# ── Session factory ───────────────────────────────────────────────────────────
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


# ── Base for ORM models ───────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ── Dependency (FastAPI) ──────────────────────────────────────────────────────
@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Async context-manager that yields a database session and handles
    commit/rollback automatically."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — use with `Depends(get_db)`."""
    async with get_db_session() as session:
        yield session


# ── Lifecycle helpers ─────────────────────────────────────────────────────────
async def init_db() -> None:
    """Create all tables defined in ORM models (idempotent)."""
    from app.db import models  # noqa: F401 — import to register metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """Dispose the connection pool on shutdown."""
    await engine.dispose()
