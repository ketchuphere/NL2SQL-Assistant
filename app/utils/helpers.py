"""
utils/helpers.py
─────────────────
Shared utility functions used across the project.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
import uuid
from datetime import datetime
from functools import wraps
from typing import Any, Callable

def deterministic_uuid(content: str | bytes) -> str:
    """Create a deterministic UUID from string or bytes content."""
    if isinstance(content, str):
        content = content.encode("utf-8")
    hash_hex = hashlib.sha256(content).hexdigest()
    namespace = uuid.UUID("00000000-0000-0000-0000-000000000000")
    return str(uuid.uuid5(namespace, hash_hex))


def new_uuid() -> str:
    return str(uuid.uuid4())

def safe_json_loads(text: str, default: Any = None) -> Any:
    """Parse JSON, returning ``default`` on failure instead of raising."""
    try:
        # Strip markdown code fences if present
        clean = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.DOTALL)
        return json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        return default


def to_json_str(obj: Any, indent: int | None = None) -> str:
    """Serialise an object to JSON, converting datetimes to ISO strings."""

    def _default(o: Any) -> Any:
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Object of type {type(o)} is not JSON serialisable")

    return json.dumps(obj, default=_default, ensure_ascii=False, indent=indent)


def sanitise_sql(sql: str) -> str:
    """Strip leading/trailing whitespace and normalise newlines."""
    return re.sub(r"\r\n|\r", "\n", sql.strip())


def extract_sql_from_markdown(text: str) -> str:
    """Extract SQL from a markdown code block if present."""
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else text.strip()


def timed(logger=None):
    """Decorator that logs execution time of a function."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed_ms = (time.perf_counter() - start) * 1000
            msg = f"{func.__qualname__} completed in {elapsed_ms:.1f}ms"
            if logger:
                logger.info(msg)
            else:
                print(msg)
            return result

        return wrapper

    return decorator


def truncate(text: str, max_chars: int = 200, suffix: str = "…") -> str:
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)] + suffix


def snake_to_title(name: str) -> str:
    """Convert ``snake_case`` to ``Title Case``."""
    return " ".join(word.capitalize() for word in name.split("_"))


def paginate(items: list[Any], page: int = 1, page_size: int = 50) -> dict[str, Any]:
    """Return a slice of ``items`` for the given page."""
    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": items[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }
