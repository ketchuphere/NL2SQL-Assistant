"""
rag/retriever.py
─────────────────
The Retriever is the "R" in RAG.

It sits between the API layer and the vector store, and is responsible for:
1. Decomposing the NL query into sub-queries (entity extraction).
2. Retrieving relevant schema Documents from the VectorDB.
3. Optionally filtering/summarising the retrieved schemas via the LLM.

This separation means pipeline.py stays clean — it just calls
``retriever.retrieve(nl_query)`` and gets back a list of relevant schemas.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from openai import OpenAI

from app.config.settings import settings
from app.vectorstore.vector_db import VectorDB

logger = logging.getLogger(__name__)

RetrievedDoc = dict[str, Any]


class SchemaRetriever:
    """Retrieves the most relevant DB schema chunks for a NL query.

    Parameters
    ----------
    vector_db:
        Initialised VectorDB instance to query against.
    top_k:
        Number of candidates to pull from the vector store per sub-query.
    rerank_top_n:
        Final number of schema chunks returned after reranking.
    max_tables:
        Hard cap on distinct tables returned (avoids context bloat).
    use_query_decomposition:
        Whether to use the LLM to extract sub-queries / entities before
        vector search.  Improves recall for complex questions.
    """

    def __init__(
        self,
        vector_db: VectorDB,
        top_k: int = 15,
        rerank_top_n: int = 5,
        max_tables: int = 5,
        use_query_decomposition: bool = True,
    ) -> None:
        self.vector_db = vector_db
        self.top_k = top_k
        self.rerank_top_n = rerank_top_n
        self.max_tables = max_tables
        self.use_query_decomposition = use_query_decomposition

        self._llm = OpenAI(api_key=settings.openai_api_key)

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        nl_query: str,
        extra_hints: list[str] | None = None,
    ) -> list[RetrievedDoc]:
        """Return the most relevant schema chunks for ``nl_query``.

        Steps
        -----
        1. Optionally decompose the query into sub-queries.
        2. Retrieve from vector store (deduplicated across sub-queries).
        3. Return final ranked list.
        """
        sub_queries = [nl_query]

        if self.use_query_decomposition:
            try:
                sub_queries = self._decompose_query(nl_query)
            except Exception as exc:
                logger.warning("Query decomposition failed (%s) — using raw query.", exc)

        if extra_hints:
            sub_queries = sub_queries + extra_hints

        logger.info("Retrieval sub-queries: %s", sub_queries)

        results = self.vector_db.retrieve_multi(
            queries=sub_queries,
            top_k_per_query=self.top_k,
            rerank_top_n=self.rerank_top_n,
            max_tables=self.max_tables,
        )

        logger.info("Retriever returned %d schema chunks.", len(results))
        return results

    # ── Query decomposition ───────────────────────────────────────────────────

    def _decompose_query(self, nl_query: str) -> list[str]:
        """Use the LLM to extract focused sub-queries from a complex NL question.

        Returns a list of 1-5 short sub-queries that cover different entities
        or dimensions of the original question.
        """
        system = (
            "You are a query-decomposition assistant for a text-to-SQL system. "
            "Given a natural-language database question, extract 1 to 5 focused "
            "sub-queries that capture the different entities, metrics, or table "
            "concepts mentioned.  Each sub-query should be a short phrase (< 10 words) "
            "that describes one concept to look up in a schema index.\n\n"
            "Return ONLY a JSON array of strings.  Example:\n"
            '["monthly sales totals", "customer region", "product category"]'
        )

        response = self._llm.chat.completions.create(
            model=settings.llm_model,
            temperature=0,
            max_tokens=256,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": nl_query},
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "[]"

        try:
            parsed = json.loads(raw)
            # Handle both {"queries": [...]} and plain [...]
            if isinstance(parsed, dict):
                for key in ("queries", "sub_queries", "results"):
                    if key in parsed and isinstance(parsed[key], list):
                        parsed = parsed[key]
                        break
            if isinstance(parsed, list) and parsed:
                return [str(q) for q in parsed[:5]]
        except json.JSONDecodeError:
            pass

        logger.warning("Could not parse decomposition response — using raw query.")
        return [nl_query]

    # ── Schema text formatter ─────────────────────────────────────────────────

    @staticmethod
    def format_schemas_for_prompt(schemas: list[RetrievedDoc]) -> str:
        """Convert retrieved schema dicts to a single formatted string for the LLM."""
        parts: list[str] = []
        for i, s in enumerate(schemas, start=1):
            header = f"[Table {i}] {s.get('schema_name', 'public')}.{s.get('table_name', '?')}"
            parts.append(f"{header}\n{s.get('content', '')}")
        return ("\n" + "─" * 60 + "\n").join(parts)
