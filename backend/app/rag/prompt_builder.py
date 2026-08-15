"""
rag/prompt_builder.py
──────────────────────
Constructs the system and user prompts injected into the LLM for
NL-to-SQL generation.

Design goals
------------
- Dialect-aware syntax rules (MySQL, PostgreSQL, Snowflake, SQL Server).
- Inject only the retrieved schema snippets (no full-DB dump).
- Enforce a structured Pydantic response schema via ``instructor``.
- Provide few-shot examples to improve accuracy.
"""

from __future__ import annotations

from typing import Any

# ── Dialect-specific syntax examples ─────────────────────────────────────────

DIALECT_SYNTAX: dict[str, str] = {
    "MySQL": (
        'SELECT column_name FROM database_name.table_name WHERE condition;\n'
        'SELECT DISTINCT category FROM db.orders;\n'
    ),
    "PostgreSQL": (
        'SELECT column_name FROM "schema_name"."table_name" WHERE condition;\n'
        'SELECT DISTINCT category FROM "public"."orders";\n'
        '-- Never use: schema_name.table_name (without quotes)\n'
    ),
    "Snowflake": (
        'SELECT column_name FROM schema_name.table_name WHERE condition;\n'
        'SELECT DISTINCT category FROM SALES.ORDERS;\n'
    ),
    "SQL Server": (
        'SELECT column_name FROM schema_name.table_name WHERE condition;\n'
        'SELECT DISTINCT category FROM dbo.Orders;\n'
    ),
}

DIALECT_ALIASES: dict[str, str] = {
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "snowflake": "Snowflake",
    "sqlserver": "SQL Server",
    "mssql": "SQL Server",
}


def _canonical_dialect(db_type: str) -> str:
    return DIALECT_ALIASES.get(db_type.lower(), db_type)


# ── System prompt ─────────────────────────────────────────────────────────────

def build_system_prompt(db_type: str) -> str:
    dialect = _canonical_dialect(db_type)
    syntax = DIALECT_SYNTAX.get(dialect, DIALECT_SYNTAX["PostgreSQL"])

    prompt = (
        f"You are a senior {dialect} SQL expert embedded in an NL2SQL assistant. "
        "Your responsibility is to generate precise, safe, and executable SQL queries "
        "that accurately answer the user's natural-language question. "
        "All responses must be grounded in the schema context provided — never hallucinate "
        "table or column names.\n\n"
        "=== Response Guidelines ===\n"
        "1. NEVER generate DDL (CREATE, DROP, ALTER) or DML that modifies data "
        "   (INSERT, UPDATE, DELETE, TRUNCATE).\n"
        "2. If the user references a value you are unsure about (e.g. a category name), "
        "   generate an intermediate query first to discover distinct values in that column.\n"
        "3. Use ONLY table and column names that appear in the provided schema context.\n"
        f"4. Always qualify table references as schema_name.table_name in {dialect} format.\n"
        "5. Prefer CTEs over nested subqueries for readability.\n"
        "6. If the schema context is insufficient, explain clearly what is missing — "
        "   do not fabricate a query.\n"
        "7. Generate either an intermediate query OR a final query — never both in one response.\n"
        "8. Do not use SQL reserved words as aliases.\n"
        "9. For date/time columns, cast or format so the output contains no raw timestamps "
        "   unless the user explicitly requests them.\n"
        "10. If the question is ambiguous, state your assumption before writing the query.\n\n"
        "=== Dialect Syntax Reference ===\n"
        f"{syntax}\n"
    )
    return prompt


# ── User prompt ───────────────────────────────────────────────────────────────

def build_user_prompt(
    nl_query: str,
    retrieved_schemas: list[dict[str, Any]],
    conversation_history: list[dict[str, str]] | None = None,
) -> str:
    """Construct the user-turn prompt with injected schema context.

    Parameters
    ----------
    nl_query:
        The user's natural-language question.
    retrieved_schemas:
        List of RetrievedDoc dicts from VectorDB.retrieve().
    conversation_history:
        Optional prior turns for multi-turn awareness.
    """
    separator = "\n" + "─" * 80 + "\n"

    # ── Schema context block ──────────────────────────────────────────────────
    schema_block = ""
    for i, schema in enumerate(retrieved_schemas, start=1):
        schema_block += (
            f"\n[Schema {i}] Table: {schema.get('schema_name', '')}.{schema.get('table_name', '')}\n"
            f"{schema.get('content', '')}\n"
        )

    # ── Conversation history (multi-turn) ─────────────────────────────────────
    history_block = ""
    if conversation_history:
        history_block = "\n=== Conversation History ===\n"
        for turn in conversation_history[-6:]:   # last 3 exchanges
            role = turn.get("role", "user").capitalize()
            history_block += f"{role}: {turn.get('content', '')}\n"
        history_block += separator

    prompt = (
        f"{history_block}"
        f"=== User Question ===\n{nl_query}\n"
        f"{separator}"
        f"=== Relevant Schema Context ({len(retrieved_schemas)} tables) ===\n"
        f"{schema_block}"
        f"{separator}"
        "Based ONLY on the schema context above, generate the SQL query. "
        "If you need an intermediate query to find distinct values, state that clearly."
    )
    return prompt


# ── Prompt for entity / value extraction ─────────────────────────────────────

def build_value_extraction_prompt(nl_query: str, column_name: str, sample_values: list[str]) -> str:
    """Ask the LLM to map a user-mentioned entity to an actual column value."""
    samples = ", ".join(f'"{v}"' for v in sample_values[:30])
    return (
        f"The user asked: \"{nl_query}\"\n\n"
        f"The column `{column_name}` contains these distinct values: {samples}\n\n"
        "Which of these values best matches the entity mentioned in the user's question? "
        "Return ONLY the exact matching value(s) as a JSON array, e.g. [\"value1\"]."
    )


# ── Schema-context summariser prompt ─────────────────────────────────────────

def build_schema_filter_prompt(nl_query: str, table_schema_text: str) -> str:
    """Ask the LLM to filter a table schema to only relevant columns."""
    return (
        "You are a data analyst assistant. Given one table schema and a user question, "
        "identify only the columns relevant to answering the question.\n\n"
        f"User Question: {nl_query}\n\n"
        f"Table Schema:\n{table_schema_text}\n\n"
        "Return a condensed description of the table that includes ONLY relevant columns. "
        "If this table is not useful at all, return an empty string."
    )
