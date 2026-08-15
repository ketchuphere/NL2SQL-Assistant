"""
db/models.py
SQLAlchemy ORM models for the internal Postgres metadata store.

Tables
- QueryHistory   : stores every NL -> SQL request + result.
- DatabaseSource : registered target databases.
- UserSession    : optional session tracking for multi-turn conversations.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class QueryHistory(Base):
    """Persists every NL query, the generated SQL, execution status and
    latency so teams can audit, debug, and fine-tune the pipeline."""

    __tablename__ = "query_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=True, index=True)
    db_source_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("database_sources.id"), nullable=True
    )

    natural_language_query: Mapped[str] = mapped_column(Text, nullable=False)
    generated_sql: Mapped[str] = mapped_column(Text, nullable=True)
    intermediate_sqls: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list
    retrieved_schemas: Mapped[str] = mapped_column(Text, nullable=True)  # JSON list
    execution_result: Mapped[str] = mapped_column(Text, nullable=True)   # JSON rows
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    success: Mapped[bool] = mapped_column(Boolean, default=False)
    retrieval_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    generation_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    execution_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    total_latency_ms: Mapped[float] = mapped_column(Float, nullable=True)
    rows_returned: Mapped[int] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    db_source: Mapped["DatabaseSource"] = relationship(
        "DatabaseSource", back_populates="query_history"
    )

    def __repr__(self) -> str:
        return f"<QueryHistory id={self.id} success={self.success}>"


class DatabaseSource(Base):
    """Registry of target databases whose schemas are indexed in Qdrant."""

    __tablename__ = "database_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    db_type: Mapped[str] = mapped_column(String(32), nullable=False)  # mysql | postgresql | …
    host: Mapped[str] = mapped_column(String(256), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database_name: Mapped[str] = mapped_column(String(128), nullable=False)
    qdrant_collection: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    table_count: Mapped[int] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    query_history: Mapped[list["QueryHistory"]] = relationship(
        "QueryHistory", back_populates="db_source"
    )

    def __repr__(self) -> str:
        return f"<DatabaseSource name={self.name} type={self.db_type}>"


class UserSession(Base):
    """Tracks multi-turn conversation context per session."""

    __tablename__ = "user_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    conversation_history: Mapped[str] = mapped_column(Text, nullable=True)  # JSON
    active_db_source: Mapped[str] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<UserSession key={self.session_key}>"
