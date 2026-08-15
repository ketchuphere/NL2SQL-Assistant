"""
ingestion/parser.py
────────────────────
Parses and extracts structured information from raw Document content
before embedding.

Operations
----------
1. ``clean_text``       — normalise whitespace, strip control chars.
2. ``extract_metadata`` — infer extra metadata (column names, keywords).
3. ``parse_documents``  — full pipeline: clean → extract → return enriched docs.
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

Document = dict[str, Any]


# ── Public API ────────────────────────────────────────────────────────────────

def parse_documents(documents: list[Document]) -> list[Document]:
    """Run all parsing passes on a list of Documents."""
    parsed: list[Document] = []
    for doc in documents:
        doc = _clean_document(doc)
        doc = _enrich_metadata(doc)
        parsed.append(doc)

    logger.info("Parsed %d documents.", len(parsed))
    return parsed


# ── Internal helpers ──────────────────────────────────────────────────────────

def _clean_document(doc: Document) -> Document:
    """Normalise whitespace and remove non-printable characters."""
    text = doc["content"]

    # Remove null bytes and other control characters (keep newlines/tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Collapse runs of blank lines to at most two
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse inline multiple spaces (but not leading indentation)
    text = re.sub(r"[ \t]{2,}", " ", text)

    doc["content"] = text.strip()
    return doc


def _enrich_metadata(doc: Document) -> Document:
    """Extract additional metadata signals from the document content."""
    meta = doc["metadata"]
    content = doc["content"]

    if meta.get("source_type") == "sql_schema":
        meta.update(_parse_schema_metadata(content))
    else:
        meta.update(_parse_generic_metadata(content))

    return doc


def _parse_schema_metadata(content: str) -> dict[str, Any]:
    """Extract column names and keywords from a schema document."""
    column_names: list[str] = re.findall(r"^\s+-\s+(\w+)\s*\(", content, re.MULTILINE)
    keywords = _extract_keywords(content)

    return {
        "column_names": column_names,
        "keyword_hints": keywords,
        "char_count": len(content),
    }


def _parse_generic_metadata(content: str) -> dict[str, Any]:
    """Extract keyword hints from free-form text documents."""
    return {
        "keyword_hints": _extract_keywords(content),
        "char_count": len(content),
        "word_count": len(content.split()),
    }


def _extract_keywords(text: str, max_kw: int = 20) -> list[str]:
    """Very lightweight keyword extraction — top N most frequent non-stopwords."""
    _STOPWORDS = {
        "the", "a", "an", "and", "or", "in", "on", "at", "to", "of", "for",
        "is", "are", "was", "be", "with", "from", "this", "that", "it",
        "as", "by", "not", "table", "column", "database", "schema", "name",
    }
    words = re.findall(r"\b[a-zA-Z_][a-zA-Z0-9_]*\b", text.lower())
    freq: dict[str, int] = {}
    for w in words:
        if w not in _STOPWORDS and len(w) > 2:
            freq[w] = freq.get(w, 0) + 1

    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:max_kw]]
