"""
tests/test_rag.py
Unit tests for the NL2SQL RAG pipeline components.

Run with:  pytest tests/ -v
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from app.ingestion.chunker import chunk_documents
from app.ingestion.loader import load_from_string, load_schema_from_dataframe
from app.ingestion.parser import parse_documents
from app.rag.prompt_builder import build_system_prompt, build_user_prompt
from app.rag.generator import SQLGenerationResult



@pytest.fixture
def sample_schema_df():
    import pandas as pd
    return pd.DataFrame(
        {
            "table_schema": ["public"] * 4,
            "table_name": ["orders", "orders", "customers", "customers"],
            "column_name": ["order_id", "customer_id", "customer_id", "name"],
            "data_type": ["integer", "integer", "integer", "varchar"],
            "column_default": [None, None, None, None],
            "is_primary_key": ["YES", "NO", "YES", "NO"],
            "referenced_table": [None, "customers", None, None],
            "referenced_column": [None, "customer_id", None, None],
            "column_comment": ["", "", "", ""],
        }
    )


@pytest.fixture
def sample_documents():
    return [
        {
            "content": "Database Schema: public\nTable Name: orders\n\nColumns:\n  - order_id (integer) [PRIMARY KEY]\n  - customer_id (integer) → customers.customer_id",
            "metadata": {
                "source": "test_db",
                "source_type": "sql_schema",
                "table_name": "orders",
                "schema_name": "public",
                "page": 0,
            },
        },
        {
            "content": "Database Schema: public\nTable Name: customers\n\nColumns:\n  - customer_id (integer) [PRIMARY KEY]\n  - name (varchar)",
            "metadata": {
                "source": "test_db",
                "source_type": "sql_schema",
                "table_name": "customers",
                "schema_name": "public",
                "page": 0,
            },
        },
    ]


class TestLoader:
    def test_load_from_string(self):
        docs = load_from_string("Hello world", source_label="test")
        assert len(docs) == 1
        assert docs[0]["content"] == "Hello world"
        assert docs[0]["metadata"]["source"] == "test"
        assert docs[0]["metadata"]["source_type"] == "raw"

    def test_load_schema_from_dataframe(self, sample_schema_df):
        docs = load_schema_from_dataframe(sample_schema_df, source_name="test_db")
        # Should produce 2 documents (one per table)
        assert len(docs) == 2
        table_names = {d["metadata"]["table_name"] for d in docs}
        assert table_names == {"orders", "customers"}

    def test_load_schema_empty_df(self):
        import pandas as pd
        docs = load_schema_from_dataframe(pd.DataFrame(), source_name="empty")
        assert docs == []

    def test_load_schema_marks_primary_keys(self, sample_schema_df):
        docs = load_schema_from_dataframe(sample_schema_df)
        orders_doc = next(d for d in docs if d["metadata"]["table_name"] == "orders")
        assert "[PRIMARY KEY]" in orders_doc["content"]

    def test_load_schema_marks_foreign_keys(self, sample_schema_df):
        docs = load_schema_from_dataframe(sample_schema_df)
        orders_doc = next(d for d in docs if d["metadata"]["table_name"] == "orders")
        assert "customers" in orders_doc["content"]


class TestChunker:
    def test_schema_docs_not_split(self, sample_documents):
        """SQL schema documents must remain atomic (one doc per table)."""
        chunked = chunk_documents(sample_documents, chunk_size=20)
        assert len(chunked) == 2  # unchanged despite tiny chunk_size

    def test_text_docs_are_split(self):
        long_text = "word " * 500  # ~2500 chars
        docs = [
            {
                "content": long_text,
                "metadata": {
                    "source": "file.txt",
                    "source_type": "txt",
                    "table_name": "",
                    "schema_name": "",
                    "page": 1,
                },
            }
        ]
        chunked = chunk_documents(docs, chunk_size=100, chunk_overlap=10)
        assert len(chunked) > 1
        for ch in chunked:
            assert len(ch["content"]) <= 150  # allow some tolerance

    def test_chunk_metadata_preserved(self, sample_documents):
        chunked = chunk_documents(sample_documents)
        for ch in chunked:
            assert "source" in ch["metadata"]
            assert "source_type" in ch["metadata"]


class TestParser:
    def test_clean_text_strips_control_chars(self):
        docs = [
            {
                "content": "Hello\x00World\x1bTest",
                "metadata": {"source": "x", "source_type": "raw",
                             "table_name": "", "schema_name": "", "page": 1},
            }
        ]
        parsed = parse_documents(docs)
        assert "\x00" not in parsed[0]["content"]
        assert "\x1b" not in parsed[0]["content"]
        assert "HelloWorldTest" in parsed[0]["content"]

    def test_enrich_schema_metadata(self, sample_documents):
        parsed = parse_documents(sample_documents)
        for doc in parsed:
            assert "char_count" in doc["metadata"]
            assert "column_names" in doc["metadata"]

    def test_keyword_hints_extracted(self):
        docs = [
            {
                "content": "revenue sales customer customer orders",
                "metadata": {"source": "x", "source_type": "raw",
                             "table_name": "", "schema_name": "", "page": 1},
            }
        ]
        parsed = parse_documents(docs)
        hints = parsed[0]["metadata"]["keyword_hints"]
        assert "customer" in hints or "revenue" in hints


class TestPromptBuilder:
    def test_system_prompt_contains_dialect(self):
        prompt = build_system_prompt("postgresql")
        assert "PostgreSQL" in prompt

    def test_system_prompt_mysql(self):
        prompt = build_system_prompt("mysql")
        assert "MySQL" in prompt

    def test_user_prompt_contains_query(self, sample_documents):
        schemas = [
            {
                "content": doc["content"],
                "table_name": doc["metadata"]["table_name"],
                "schema_name": doc["metadata"]["schema_name"],
                "source": doc["metadata"]["source"],
            }
            for doc in sample_documents
        ]
        prompt = build_user_prompt("How many orders per customer?", schemas)
        assert "How many orders per customer?" in prompt
        assert "orders" in prompt or "customers" in prompt

    def test_user_prompt_no_schemas(self):
        prompt = build_user_prompt("show me revenue", [])
        assert "show me revenue" in prompt

    def test_user_prompt_with_history(self, sample_documents):
        history = [
            {"role": "user", "content": "previous question"},
            {"role": "assistant", "content": "SELECT * FROM orders"},
        ]
        schemas = [{"content": "x", "table_name": "orders", "schema_name": "public", "source": "db"}]
        prompt = build_user_prompt("follow-up question", schemas, conversation_history=history)
        assert "previous question" in prompt
        assert "follow-up question" in prompt


class TestSQLGenerationResult:
    def test_is_final(self):
        r = SQLGenerationResult(
            requirements="req",
            step_by_step_plan="plan",
            query_type="final_query",
            final_query="SELECT 1",
        )
        assert r.is_final() is True
        assert r.is_intermediate() is False
        assert r.primary_sql() == "SELECT 1"

    def test_is_intermediate(self):
        r = SQLGenerationResult(
            requirements="req",
            step_by_step_plan="plan",
            query_type="intermediate_query",
            intermediate_queries=["SELECT DISTINCT category FROM orders"],
        )
        assert r.is_intermediate() is True
        assert r.primary_sql() == "SELECT DISTINCT category FROM orders"

    def test_is_explanation(self):
        r = SQLGenerationResult(
            requirements="req",
            step_by_step_plan="plan",
            query_type="explanation",
            explanation="Cannot answer this question.",
        )
        assert r.is_final() is False
        assert r.is_intermediate() is False
        assert r.primary_sql() == ""
