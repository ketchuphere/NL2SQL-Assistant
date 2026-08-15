from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any
import pandas as pd
from app.config.settings import settings
from app.ingestion.chunker import chunk_documents
from app.ingestion.loader import load_schema_from_dataframe
from app.ingestion.parser import parse_documents
from app.rag.generator import SQLGenerationResult, SQLGenerator
from app.rag.retriever import SchemaRetriever
from app.vectorstore.vector_db import VectorDB
from app.utils.sql_connectors import SQLConnector

logger = logging.getLogger(__name__)

@dataclass
class PipelineResult:
    nl_query: str
    generated_sql: str = ""
    intermediate_sqls: list[str] = field(default_factory=list)
    result_df: pd.DataFrame | None = None
    rows: list[dict[str, Any]] = field(default_factory=list)
    retrieved_schemas: list[dict[str, Any]] = field(default_factory=list)
    explanation: str = ""
    assumptions: str = ""
    success: bool = False
    error: str = ""

    #Timing
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    execution_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "nl_query": self.nl_query,
            "generated_sql": self.generated_sql,
            "intermediate_sqls": self.intermediate_sqls,
            "rows": self.rows,
            "row_count": len(self.rows),
            "explanation": self.explanation,
            "assumptions": self.assumptions,
            "success": self.success,
            "error": self.error,
            "latency": {
                "retrieval_ms": round(self.retrieval_ms, 2),
                "generation_ms": round(self.generation_ms, 2),
                "execution_ms": round(self.execution_ms, 2),
                "total_ms": round(self.total_ms, 2),
            },
        }


class NL2SQLPipeline:
    """End-to-end Natural Language to SQL pipeline.

    Parameters
    ----------
    db_type:
        Target database type ('mysql', 'postgresql', 'snowflake', 'sqlserver').
    host, port, username, password, database:
        Connection parameters for the target database.
    collection_name:
        Qdrant collection name for this database's schemas.
    max_self_healing_attempts:
        How many times to retry SQL generation after an execution error.
    """

    def __init__(
        self,
        db_type: str = settings.target_db_type,
        host: str = settings.target_db_host,
        port: int = settings.target_db_port,
        username: str = settings.target_db_user,
        password: str = settings.target_db_password,
        database: str = settings.target_db_name,
        collection_name: str | None = None,
        max_self_healing_attempts: int = 3,
    ) -> None:
        self.db_type = db_type
        self.database = database
        self.max_attempts = max_self_healing_attempts

        self.sql_connector = SQLConnector(
            db_type=db_type,
            host=host,
            port=port,
            username=username,
            password=password,
            database=database,
        )

        self.vector_db = VectorDB(
            collection_name=collection_name or settings.qdrant_collection,
        )

        self.retriever = SchemaRetriever(
            vector_db=self.vector_db,
            top_k=15,
            rerank_top_n=5,
            max_tables=5,
        )
        self.generator = SQLGenerator(db_type=db_type)

        self._sessions: dict[str, list[dict[str, str]]] = {}

    def index_database_schema(self) -> int:
        """Connect to the target DB, extract its schema, and index into Qdrant.

        Returns the number of table documents indexed.
        Safe to call multiple times — Qdrant deduplicates on the content hash.
        """
        logger.info("Connecting to target database and extracting schema…")
        schema_df = self.sql_connector.get_schema()

        if schema_df is None or schema_df.empty:
            logger.error("Failed to extract schema — no documents indexed.")
            return 0

        docs = load_schema_from_dataframe(schema_df, source_name=self.database)
        docs = parse_documents(docs)
        docs = chunk_documents(docs)

        count = self.vector_db.add_documents(docs)
        logger.info("Schema indexing complete: %d documents indexed.", count)
        return count


    def query(
        self,
        nl_query: str,
        session_id: str | None = None,
        execute: bool = True,
        max_rows: int = 500,
    ) -> PipelineResult:
        """Process a natural-language query end-to-end.

        Parameters
        ----------
        nl_query:
            The user's question in plain English.
        session_id:
            Optional session identifier for multi-turn conversation context.
        execute:
            If True, run the generated SQL against the target DB.
            Set to False to get SQL without executing (dry-run / preview).
        max_rows:
            Maximum rows to return in the result set.

        Returns
        -------
        PipelineResult
        """
        pipeline_start = time.perf_counter()
        result = PipelineResult(nl_query=nl_query)
        history = self._sessions.get(session_id, []) if session_id else []

        t0 = time.perf_counter()
        try:
            schemas = self.retriever.retrieve(nl_query)
            result.retrieved_schemas = schemas
        except Exception as exc:
            logger.error("Retrieval failed: %s", exc)
            result.error = f"Schema retrieval failed: {exc}"
            result.total_ms = (time.perf_counter() - pipeline_start) * 1000
            return result
        result.retrieval_ms = (time.perf_counter() - t0) * 1000

        t0 = time.perf_counter()
        gen_result: SQLGenerationResult = self.generator.generate(
            nl_query=nl_query,
            retrieved_schemas=schemas,
            conversation_history=history,
        )
        result.generation_ms = (time.perf_counter() - t0) * 1000

        result.generated_sql = gen_result.final_query
        result.intermediate_sqls = gen_result.intermediate_queries
        result.explanation = gen_result.explanation
        result.assumptions = gen_result.assumptions

        if not execute or not gen_result.primary_sql():
            result.success = gen_result.query_type != "explanation"
            result.total_ms = (time.perf_counter() - pipeline_start) * 1000
            self._update_session(session_id, nl_query, gen_result)
            return result

        sql_to_run = gen_result.primary_sql()
        last_error = ""

        for attempt in range(1, self.max_attempts + 1):
            t0 = time.perf_counter()
            try:
                df = self.sql_connector.execute_query(sql_to_run, max_rows=max_rows)
                result.execution_ms = (time.perf_counter() - t0) * 1000
                result.result_df = df
                result.rows = df.to_dict(orient="records") if df is not None else []
                result.success = True
                logger.info(
                    "Query executed successfully on attempt %d. Rows: %d",
                    attempt,
                    len(result.rows),
                )
                break

            except Exception as exc:
                result.execution_ms = (time.perf_counter() - t0) * 1000
                last_error = str(exc)
                logger.warning(
                    "Execution attempt %d/%d failed: %s",
                    attempt,
                    self.max_attempts,
                    last_error,
                )

                if attempt < self.max_attempts:
                    logger.info("Attempting self-healing refinement…")
                    gen_result = self.generator.refine(
                        original_query=nl_query,
                        failed_sql=sql_to_run,
                        error_message=last_error,
                        retrieved_schemas=schemas,
                        conversation_history=history,
                    )
                    sql_to_run = gen_result.primary_sql()
                    result.generated_sql = gen_result.final_query
                    result.intermediate_sqls = gen_result.intermediate_queries

                    if not sql_to_run:
                        break

        if not result.success:
            result.error = last_error

        result.total_ms = (time.perf_counter() - pipeline_start) * 1000
        self._update_session(session_id, nl_query, gen_result)
        return result


    def _update_session(
        self,
        session_id: str | None,
        nl_query: str,
        gen_result: SQLGenerationResult,
    ) -> None:
        if not session_id:
            return

        history = self._sessions.setdefault(session_id, [])
        history.append({"role": "user", "content": nl_query})
        history.append(
            {
                "role": "assistant",
                "content": (
                    gen_result.final_query
                    or gen_result.explanation
                    or ", ".join(gen_result.intermediate_queries)
                ),
            }
        )
        self._sessions[session_id] = history[-20:]

    def clear_session(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)