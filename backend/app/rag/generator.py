"""
rag/generator.py
─────────────────
The Generator is the "G" in RAG.

It takes:
  - The NL query
  - The retrieved + formatted schema context
  - The conversation history (for multi-turn)

…and returns a structured ``SQLGenerationResult`` that contains:
  - The final SQL query (or empty string if unanswerable)
  - Any intermediate queries needed to resolve ambiguous values
  - A plain-language explanation
  - The reasoning / step-by-step plan

Uses ``instructor`` for reliable Pydantic-typed LLM responses with
auto-retry on validation failure.
"""

from __future__ import annotations

import logging
from typing import Any

import instructor
from openai import OpenAI
from pydantic import BaseModel, Field

from app.config.settings import settings
from app.rag.prompt_builder import build_system_prompt, build_user_prompt

logger = logging.getLogger(__name__)


# ── Output schema (enforced via instructor) ───────────────────────────────────

class SQLGenerationResult(BaseModel):
    """Structured output from the SQL generator."""

    requirements: str = Field(
        description="Detailed restatement of the user's requirements."
    )
    step_by_step_plan: str = Field(
        description=(
            "Step-by-step reasoning identifying which tables and columns "
            "are needed, and how they should be joined."
        )
    )
    query_type: str = Field(
        description=(
            "Type of response. One of: "
            "'final_query' (ready to execute), "
            "'intermediate_query' (needs a sub-query run first), "
            "'explanation' (cannot generate SQL — explains why)."
        ),
        examples=["final_query", "intermediate_query", "explanation"],
    )
    intermediate_queries: list[str] = Field(
        default_factory=list,
        description=(
            "One or more intermediate SQL queries to discover distinct values "
            "or validate assumptions before writing the final query."
        ),
    )
    final_query: str = Field(
        default="",
        description=(
            "The complete, executable SQL query answering the user's question. "
            "Empty if query_type is 'intermediate_query' or 'explanation'."
        ),
    )
    explanation: str = Field(
        default="",
        description=(
            "If the schema is insufficient or the question is unanswerable, "
            "a clear explanation of why."
        ),
    )
    assumptions: str = Field(
        default="",
        description="Any assumptions made about ambiguous terms in the question.",
    )

    def is_final(self) -> bool:
        return self.query_type == "final_query" and bool(self.final_query.strip())

    def is_intermediate(self) -> bool:
        return self.query_type == "intermediate_query" and bool(self.intermediate_queries)

    def primary_sql(self) -> str:
        """Return the most actionable SQL — final or first intermediate."""
        if self.is_final():
            return self.final_query
        if self.is_intermediate():
            return self.intermediate_queries[0]
        return ""


# ── Generator ─────────────────────────────────────────────────────────────────

class SQLGenerator:
    """Generates SQL queries from NL + schema context using an LLM.

    Parameters
    ----------
    db_type:
        Target DB dialect ('mysql', 'postgresql', 'snowflake', 'sqlserver').
    max_retries:
        Number of instructor validation retries on malformed LLM output.
    """

    def __init__(
        self,
        db_type: str = "postgresql",
        max_retries: int = 3,
    ) -> None:
        self.db_type = db_type
        self.max_retries = max_retries

        raw_client = OpenAI(api_key=settings.openai_api_key)
        self.client = instructor.from_openai(raw_client)
        self.system_prompt = build_system_prompt(db_type)

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        nl_query: str,
        retrieved_schemas: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> SQLGenerationResult:
        """Generate a SQL query (or explanation) for the given NL query.

        Parameters
        ----------
        nl_query:
            The user's natural-language question.
        retrieved_schemas:
            Schema context from SchemaRetriever.retrieve().
        conversation_history:
            Optional list of {"role": "user"|"assistant", "content": str}
            dicts for multi-turn awareness.

        Returns
        -------
        SQLGenerationResult
            Structured Pydantic model with the generated SQL and metadata.
        """
        user_prompt = build_user_prompt(
            nl_query=nl_query,
            retrieved_schemas=retrieved_schemas,
            conversation_history=conversation_history,
        )

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        logger.info(
            "Generating SQL for query (%.80s…) with %d schema(s).",
            nl_query,
            len(retrieved_schemas),
        )

        result: SQLGenerationResult = self.client.chat.completions.create(
            model=settings.llm_model,
            response_model=SQLGenerationResult,
            messages=messages,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            max_retries=self.max_retries,
        )

        logger.info(
            "SQL generation complete. type=%s, has_final=%s",
            result.query_type,
            result.is_final(),
        )
        return result

    def refine(
        self,
        original_query: str,
        failed_sql: str,
        error_message: str,
        retrieved_schemas: list[dict[str, Any]],
        conversation_history: list[dict[str, str]] | None = None,
    ) -> SQLGenerationResult:
        """Attempt to fix a SQL query that raised a database error.

        Appends the error context to the user prompt and asks the LLM to
        correct the query.
        """
        error_context = (
            f"\n\n=== Previous SQL (FAILED) ===\n{failed_sql}\n\n"
            f"=== Database Error ===\n{error_message}\n\n"
            "Please diagnose the error and generate a corrected SQL query."
        )

        amended_query = original_query + error_context
        return self.generate(
            nl_query=amended_query,
            retrieved_schemas=retrieved_schemas,
            conversation_history=conversation_history,
        )
