"""
ingestion/loader.py
Loads raw input for the ingestion pipeline.

- SQL Database schema   (auto-extracted from live DB)
- PDF / TXT / Markdown  (data dictionaries, ER-diagram docs)
- Raw text strings      (ad-hoc descriptions passed via API)

The loader normalises everything into a list of ``Document`` dicts:
    {
        "content": str,          # raw text to embed
        "metadata": {
            "source": str,       # origin (file path | db | string)
            "source_type": str,  # "sql_schema" | "pdf" | "txt" | "md" | "raw"
            "table_name": str,   # populated for sql_schema docs
            "schema_name": str,  # populated for sql_schema docs
            "page": int,         # populated for pdf docs
        }
    }
"""

import logging
import os
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)

Document = dict[str, Any]


def load_schema_from_dataframe(
    schema_df: pd.DataFrame,
    source_name: str = "database",
) -> list[Document]:
    """Convert a schema DataFrame (produced by SQLConnector) into Documents.

    Each document represents one table with its full column description.

    Expected columns in schema_df:
        table_schema, table_name, column_name, data_type,
        is_primary_key, referenced_table, referenced_column,
        column_comment (optional)
    """
    if schema_df is None or schema_df.empty:
        logger.warning("Empty schema DataFrame — nothing to load.")
        return []

    documents: list[Document] = []

    group_cols = [c for c in ["table_schema", "table_name"] if c in schema_df.columns]
    grouped = schema_df.groupby(group_cols)

    for key, group in grouped:
        schema_name, table_name = (key if isinstance(key, tuple) else ("public", key))

        lines: list[str] = [
            f"Database Schema: {schema_name}",
            f"Table Name: {table_name}",
            "",
            "Columns:",
        ]
        for _, row in group.iterrows():
            col_desc = f"  - {row['column_name']} ({row['data_type']})"
            if row.get("is_primary_key") == "YES":
                col_desc += " [PRIMARY KEY]"
            if row.get("referenced_table"):
                col_desc += f" → {row['referenced_table']}.{row['referenced_column']}"
            if row.get("column_comment"):
                col_desc += f" — {row['column_comment']}"
            lines.append(col_desc)

        documents.append(
            {
                "content": "\n".join(lines),
                "metadata": {
                    "source": source_name,
                    "source_type": "sql_schema",
                    "table_name": table_name,
                    "schema_name": schema_name,
                    "page": 0,
                },
            }
        )

    logger.info("Loaded %d table schema documents from '%s'.", len(documents), source_name)
    return documents


def load_from_file(file_path: str | Path) -> list[Document]:
    """Load a PDF, TXT, or Markdown file into Documents.

    PDF loading requires ``pypdf``; install it with:
        pip install pypdf
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    ext = path.suffix.lower()

    if ext == ".pdf":
        return _load_pdf(path)
    elif ext in {".txt", ".md", ".markdown"}:
        return _load_text(path)
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Supported: .pdf, .txt, .md")


def _load_pdf(path: Path) -> list[Document]:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        raise ImportError("Install pypdf: pip install pypdf")

    reader = PdfReader(str(path))
    documents: list[Document] = []

    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            documents.append(
                {
                    "content": text,
                    "metadata": {
                        "source": str(path),
                        "source_type": "pdf",
                        "table_name": "",
                        "schema_name": "",
                        "page": page_num,
                    },
                }
            )

    logger.info("Loaded %d pages from PDF '%s'.", len(documents), path.name)
    return documents


def _load_text(path: Path) -> list[Document]:
    content = path.read_text(encoding="utf-8")
    ext = path.suffix.lower().lstrip(".")
    doc = {
        "content": content,
        "metadata": {
            "source": str(path),
            "source_type": ext,
            "table_name": "",
            "schema_name": "",
            "page": 1,
        },
    }
    logger.info("Loaded text file '%s' (%d chars).", path.name, len(content))
    return [doc]


def load_from_string(text: str, source_label: str = "raw") -> list[Document]:
    """Wrap a plain text string as a single Document."""
    return [
        {
            "content": text,
            "metadata": {
                "source": source_label,
                "source_type": "raw",
                "table_name": "",
                "schema_name": "",
                "page": 1,
            },
        }
    ]


def load_from_directory(directory: str | Path, recursive: bool = False) -> list[Document]:
    """Load all supported files (.pdf, .txt, .md) from a directory."""
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    pattern = "**/*" if recursive else "*"
    documents: list[Document] = []

    for file_path in dir_path.glob(pattern):
        if file_path.suffix.lower() in {".pdf", ".txt", ".md", ".markdown"}:
            try:
                documents.extend(load_from_file(file_path))
            except Exception as exc:
                logger.warning("Skipping '%s': %s", file_path, exc)

    logger.info(
        "Loaded %d documents from directory '%s'.", len(documents), dir_path
    )
    return documents
