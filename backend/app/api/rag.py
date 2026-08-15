"""
api/rag.py
───────────
Core NL2SQL query API endpoints.

Routes
------
POST /rag/query          — convert NL question → SQL, execute, return results
POST /rag/generate       — NL → SQL only (no execution, dry-run / preview)
GET  /rag/history        — paginated query history
DELETE /rag/session/{id} — clear multi-turn conversation session
"""

from __future__ import annotations

import logging
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.db.models import QueryHistory
from app.db.postgres import AsyncSession, get_db
from app.rag.pipeline import NL2SQLPipeline, PipelineResult
from app.utils.helpers import paginate, to_json_str

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rag", tags=["NL2SQL RAG"])


# ── Shared pipeline dependency ────────────────────────────────────────────────

def get_pipeline() -> NL2SQLPipeline:
    return NL2SQLPipeline()


# ── Request / Response models ─────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=3, description="Natural language question about your data.")
    session_id: str | None = Field(None, description="Session ID for multi-turn conversation.")
    execute: bool = Field(True, description="Execute the generated SQL against the target DB.")
    max_rows: int = Field(500, ge=1, le=5000, description="Maximum rows to return.")
    db_type: str | None = Field(None, description="Override target DB type.")


class QueryResponse(BaseModel):
    request_id: str
    question: str
    generated_sql: str
    intermediate_sqls: list[str]
    rows: list[dict[str, Any]]
    row_count: int
    explanation: str
    assumptions: str
    success: bool
    error: str
    latency: dict[str, float]
    session_id: str | None
    # ── NEW: tables used — consumed by the frontend SchemaExplorer ──────────
    tables_used: list[str]


class GenerateOnlyRequest(BaseModel):
    question: str = Field(..., min_length=3)
    session_id: str | None = None
    db_type: str | None = None


class GenerateOnlyResponse(BaseModel):
    request_id: str
    question: str
    generated_sql: str
    intermediate_sqls: list[str]
    query_type: str
    explanation: str
    assumptions: str
    retrieved_schema_count: int
    latency: dict[str, float]
    tables_used: list[str]


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/query", response_model=QueryResponse, summary="NL → SQL → Execute")
async def query(
    req: QueryRequest,
    pipeline: Annotated[NL2SQLPipeline, Depends(get_pipeline)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Convert a natural-language question into SQL, execute it against the
    configured target database, and return structured results.

    Supports multi-turn conversation via ``session_id``.
    """
    request_id = str(uuid.uuid4())
    session_id = req.session_id or str(uuid.uuid4())

    try:
        result: PipelineResult = pipeline.query(
            nl_query=req.question,
            session_id=session_id,
            execute=req.execute,
            max_rows=req.max_rows,
        )
    except Exception as exc:
        logger.error("Pipeline error for request %s: %s", request_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))

    # Extract table names from retrieved schemas
    tables_used = list({
        s.get("table_name", "")
        for s in result.retrieved_schemas
        if s.get("table_name")
    })

    # ── Persist to query history ──────────────────────────────────────────────
    try:
        history_record = QueryHistory(
            session_id=session_id,
            natural_language_query=req.question,
            generated_sql=result.generated_sql,
            intermediate_sqls=to_json_str(result.intermediate_sqls),
            retrieved_schemas=to_json_str(tables_used),
            execution_result=to_json_str(result.rows[:10]),
            success=result.success,
            error_message=result.error or None,
            retrieval_latency_ms=result.retrieval_ms,
            generation_latency_ms=result.generation_ms,
            execution_latency_ms=result.execution_ms,
            total_latency_ms=result.total_ms,
            rows_returned=len(result.rows),
        )
        db.add(history_record)
        await db.commit()
    except Exception as exc:
        logger.warning("Failed to persist query history: %s", exc)

    return QueryResponse(
        request_id=request_id,
        question=req.question,
        generated_sql=result.generated_sql,
        intermediate_sqls=result.intermediate_sqls,
        rows=result.rows,
        row_count=len(result.rows),
        explanation=result.explanation,
        assumptions=result.assumptions,
        success=result.success,
        error=result.error,
        latency={
            "retrieval_ms": round(result.retrieval_ms, 2),
            "generation_ms": round(result.generation_ms, 2),
            "execution_ms": round(result.execution_ms, 2),
            "total_ms": round(result.total_ms, 2),
        },
        session_id=session_id,
        tables_used=tables_used,
    )


@router.post("/generate", response_model=GenerateOnlyResponse, summary="NL → SQL (dry-run)")
async def generate_sql_only(
    req: GenerateOnlyRequest,
    pipeline: Annotated[NL2SQLPipeline, Depends(get_pipeline)],
):
    """Generate SQL from a natural-language question WITHOUT executing it."""
    request_id = str(uuid.uuid4())

    result: PipelineResult = pipeline.query(
        nl_query=req.question,
        session_id=req.session_id,
        execute=False,
    )

    query_type = "explanation"
    if result.generated_sql:
        query_type = "final_query"
    elif result.intermediate_sqls:
        query_type = "intermediate_query"

    tables_used = list({
        s.get("table_name", "")
        for s in result.retrieved_schemas
        if s.get("table_name")
    })

    return GenerateOnlyResponse(
        request_id=request_id,
        question=req.question,
        generated_sql=result.generated_sql,
        intermediate_sqls=result.intermediate_sqls,
        query_type=query_type,
        explanation=result.explanation,
        assumptions=result.assumptions,
        retrieved_schema_count=len(result.retrieved_schemas),
        latency={
            "retrieval_ms": round(result.retrieval_ms, 2),
            "generation_ms": round(result.generation_ms, 2),
            "total_ms": round(result.total_ms, 2),
        },
        tables_used=tables_used,
    )


@router.get("/history", summary="Paginated query history")
async def get_history(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    session_id: str | None = Query(None),
):
    """Return paginated query history records from the Postgres metadata store."""
    from sqlalchemy import select, desc

    stmt = select(QueryHistory).order_by(desc(QueryHistory.created_at))
    if session_id:
        stmt = stmt.where(QueryHistory.session_id == session_id)

    result = await db.execute(stmt)
    all_records = result.scalars().all()

    records_dict = [
        {
            "id": str(r.id),
            "session_id": r.session_id,
            "nl_query": r.natural_language_query,
            "generated_sql": r.generated_sql,
            "success": r.success,
            "rows_returned": r.rows_returned,
            "total_latency_ms": r.total_latency_ms,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in all_records
    ]

    return paginate(records_dict, page=page, page_size=page_size)


@router.delete("/session/{session_id}", summary="Clear conversation session")
async def clear_session(
    session_id: str,
    pipeline: Annotated[NL2SQLPipeline, Depends(get_pipeline)],
):
    """Clear the multi-turn conversation history for the given session ID."""
    pipeline.clear_session(session_id)
    return {"message": f"Session '{session_id}' cleared."}
