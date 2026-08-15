"""
ingestion/chunker.py
─────────────────────
Splits ``Document`` objects (from loader.py) into smaller chunks that fit
within an embedding model's context window.

Strategy
--------
- ``sql_schema`` documents  → one chunk per table (already atomic; no split).
- ``pdf / txt / md / raw``  → semantic or token-based splitting.

We use a lightweight recursive character splitter by default so the project
has no hard dependency on LangChain.  If ``semantic_text_splitter`` is
installed (included in requirements.txt) it is used for richer splits.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

Document = dict[str, Any]


# ── Public entry point ────────────────────────────────────────────────────────

def chunk_documents(
    documents: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 64,
) -> list[Document]:
    """Chunk a list of Documents.

    SQL schema documents are returned as-is (one table = one chunk).
    All other source types are split into overlapping text chunks.
    """
    chunked: list[Document] = []

    for doc in documents:
        if doc["metadata"]["source_type"] == "sql_schema":
            # Schema docs are already one-table-per-doc — keep them whole.
            chunked.append(doc)
        else:
            chunked.extend(
                _split_text_document(doc, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            )

    logger.info(
        "Chunking: %d input docs → %d chunks (chunk_size=%d, overlap=%d).",
        len(documents),
        len(chunked),
        chunk_size,
        chunk_overlap,
    )
    return chunked


# ── Splitter implementations ──────────────────────────────────────────────────

def _split_text_document(
    doc: Document,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Document]:
    """Try semantic splitter first; fall back to the simple recursive splitter."""
    text = doc["content"]

    try:
        chunks = _semantic_split(text, chunk_size)
    except ImportError:
        chunks = _recursive_character_split(text, chunk_size, chunk_overlap)

    result: list[Document] = []
    for idx, chunk in enumerate(chunks):
        if chunk.strip():
            result.append(
                {
                    "content": chunk,
                    "metadata": {
                        **doc["metadata"],
                        "chunk_index": idx,
                    },
                }
            )

    return result or [doc]  # fall back to original if split produced nothing


def _semantic_split(text: str, chunk_size: int) -> list[str]:
    """Use ``semantic_text_splitter`` for smarter boundary detection."""
    from semantic_text_splitter import TextSplitter  # type: ignore

    splitter = TextSplitter(capacity=chunk_size)
    return splitter.chunks(text)


def _recursive_character_split(
    text: str,
    chunk_size: int,
    chunk_overlap: int,
    separators: list[str] | None = None,
) -> list[str]:
    """Pure-Python recursive character splitter — no external dependencies."""
    if separators is None:
        separators = ["\n\n", "\n", ". ", " ", ""]

    def _split(t: str, seps: list[str]) -> list[str]:
        if not seps:
            # leaf case: split by characters
            return [t[i: i + chunk_size] for i in range(0, len(t), chunk_size - chunk_overlap)]

        sep = seps[0]
        parts = t.split(sep) if sep else list(t)

        chunks: list[str] = []
        current = ""

        for part in parts:
            candidate = current + (sep if current else "") + part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current)
                if len(part) > chunk_size:
                    # recurse on the oversized part
                    chunks.extend(_split(part, seps[1:]))
                    current = ""
                else:
                    current = part

        if current:
            chunks.append(current)

        # merge tiny adjacent chunks with overlap
        merged: list[str] = []
        for ch in chunks:
            if merged and len(merged[-1]) + len(sep) + len(ch) <= chunk_size:
                merged[-1] += sep + ch
            else:
                merged.append(ch)

        return merged

    return _split(text, separators)
