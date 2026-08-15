"""
api/documents.py
─────────────────
Endpoints for managing schema documents in the vector store.

Routes
------
POST   /documents/index    — trigger schema extraction + indexing for a DB
GET    /documents/status   — collection stats (doc count, etc.)
GET    /documents/schema   — return full schema metadata (tables + columns)
DELETE /documents/reset    — drop and recreate the vector collection
POST   /documents/upload   — upload a PDF / TXT data-dictionary to index
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.config.settings import settings
from app.ingestion.chunker import chunk_documents
from app.ingestion.loader import load_from_file, load_schema_from_dataframe
from app.ingestion.parser import parse_documents
from app.utils.sql_connectors import SQLConnector
from app.vectorstore.vector_db import VectorDB

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])


# ── Shared dependency ─────────────────────────────────────────────────────────

def get_vector_db() -> VectorDB:
    return VectorDB()


# ── Request / Response models ─────────────────────────────────────────────────

class IndexRequest(BaseModel):
    db_type: str = settings.target_db_type
    host: str = settings.target_db_host
    port: int = settings.target_db_port
    username: str = settings.target_db_user
    password: str = settings.target_db_password
    database: str = settings.target_db_name
    collection_name: str | None = None


class IndexResponse(BaseModel):
    message: str
    documents_indexed: int
    collection_name: str


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/index", response_model=IndexResponse, summary="Index database schema")
async def index_schema(
    req: IndexRequest,
    vdb: Annotated[VectorDB, Depends(get_vector_db)],
):
    """Connect to the specified database, extract its schema, and index it into
    the Qdrant vector store so it can be retrieved during NL2SQL queries."""
    try:
        connector = SQLConnector(
            db_type=req.db_type,
            host=req.host,
            port=req.port,
            username=req.username,
            password=req.password,
            database=req.database,
        )
        schema_df = connector.get_schema()

        if schema_df is None or schema_df.empty:
            raise HTTPException(status_code=422, detail="No schema found in the target database.")

        docs = load_schema_from_dataframe(schema_df, source_name=req.database)
        docs = parse_documents(docs)
        docs = chunk_documents(docs)

        if req.collection_name:
            vdb.collection_name = req.collection_name

        count = vdb.add_documents(docs)
        connector.disconnect()

        return IndexResponse(
            message="Schema indexed successfully.",
            documents_indexed=count,
            collection_name=vdb.collection_name,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Schema indexing failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/status", summary="Vector store collection status")
async def collection_status(vdb: Annotated[VectorDB, Depends(get_vector_db)]):
    """Return stats about the current Qdrant collection."""
    try:
        return vdb.collection_info()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/schema", summary="Return full database schema (tables + columns)")
async def get_schema():
    """Connect to the configured target database and return its full schema
    as structured JSON.

    Used by the frontend SchemaExplorer and DbStatus components to display
    live table / column metadata without querying Qdrant.
    """
    try:
        connector = SQLConnector(
            db_type=settings.target_db_type,
            host=settings.target_db_host,
            port=settings.target_db_port,
            username=settings.target_db_user,
            password=settings.target_db_password,
            database=settings.target_db_name,
        )
        schema_df = connector.get_schema()
        connector.disconnect()

        if schema_df is None or schema_df.empty:
            return {
                "db_name": settings.target_db_name,
                "db_type": settings.target_db_type,
                "host": settings.target_db_host,
                "tables": [],
            }

        # Group by (schema, table)
        group_cols = [c for c in ["table_schema", "table_name"] if c in schema_df.columns]
        tables = []

        for key, group in schema_df.groupby(group_cols):
            schema_name, table_name = (key if isinstance(key, tuple) else ("public", key))
            columns = []
            for _, row in group.iterrows():
                columns.append(
                    {
                        "column_name": row.get("column_name", ""),
                        "data_type": row.get("data_type", ""),
                        "is_primary_key": row.get("is_primary_key", "NO"),
                        "referenced_table": row.get("referenced_table") or None,
                        "referenced_column": row.get("referenced_column") or None,
                        "column_comment": row.get("column_comment", ""),
                    }
                )
            tables.append(
                {
                    "table_schema": schema_name,
                    "table_name": table_name,
                    "columns": columns,
                }
            )

        return {
            "db_name": settings.target_db_name,
            "db_type": settings.target_db_type,
            "host": settings.target_db_host,
            "table_count": len(tables),
            "tables": tables,
        }

    except Exception as exc:
        logger.error("Schema fetch failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.delete("/reset", summary="Reset vector store collection")
async def reset_collection(vdb: Annotated[VectorDB, Depends(get_vector_db)]):
    """Drop and recreate the Qdrant collection.
    ⚠️  This deletes all indexed schemas."""
    try:
        vdb.delete_collection()
        return {"message": f"Collection '{vdb.collection_name}' has been reset."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/upload", summary="Upload a data-dictionary document")
async def upload_document(
    file: Annotated[UploadFile, File(description="PDF or TXT data-dictionary")],
    vdb: Annotated[VectorDB, Depends(get_vector_db)],
):
    """Upload a PDF or TXT file (e.g. a data dictionary or ER diagram description)
    and index its content into the vector store."""
    allowed_types = {
        "application/pdf": ".pdf",
        "text/plain": ".txt",
        "text/markdown": ".md",
    }

    content_type = file.content_type or ""
    if content_type not in allowed_types and not file.filename.endswith((".pdf", ".txt", ".md")):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Allowed: .pdf, .txt, .md",
        )

    suffix = allowed_types.get(content_type, Path(file.filename).suffix)

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(await file.read())
        tmp_path = Path(tmp.name)

    try:
        docs = load_from_file(tmp_path)
        docs = parse_documents(docs)
        docs = chunk_documents(docs)
        count = vdb.add_documents(docs)
    finally:
        tmp_path.unlink(missing_ok=True)

    return {
        "message": "Document uploaded and indexed successfully.",
        "filename": file.filename,
        "chunks_indexed": count,
    }
