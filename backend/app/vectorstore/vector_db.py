"""
vectorstore/vector_db.py
─────────────────────────
Qdrant-backed vector store for NL2SQL schema retrieval.

Responsibilities
----------------
- Create / manage Qdrant collections (dense + sparse hybrid).
- Index schema Documents produced by the ingestion pipeline.
- Retrieve the top-K most relevant schema chunks for a NL query.
- Re-rank retrieved results with FlashRank before returning.

Design notes
------------
We use the ``qdrant_client`` high-level ``add`` / ``query`` helpers that
accept plain text and handle embedding internally via fastembed.  This
keeps the embedder and the vector store loosely coupled: the Qdrant client
loads its own copy of the model, while ``embedder.py`` can be used
independently for other tasks.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

from tqdm import tqdm

from app.config.settings import settings

logger = logging.getLogger(__name__)

Document = dict[str, Any]
RetrievedDoc = dict[str, Any]


# ── Reranker (thin wrapper around FlashRank) ──────────────────────────────────

class _Reranker:
    """Wraps FlashRank cross-encoder reranking."""

    def __init__(self, model_name: str = "ms-marco-MiniLM-L-12-v2") -> None:
        from flashrank import Ranker, RerankRequest  # type: ignore

        self._Ranker = Ranker
        self._RerankRequest = RerankRequest
        self.ranker = Ranker(model_name=model_name, cache_dir="/tmp/flashrank")
        logger.info("Reranker loaded: %s", model_name)

    def rerank(self, query: str, docs: list[dict], top_n: int = 5) -> list[dict]:
        passages = [{"id": d["id"], "text": d["content"], **d} for d in docs]
        req = self._RerankRequest(query=query, passages=passages)
        reranked = self.ranker.rerank(req)
        return reranked[:top_n]


# ── VectorDB ──────────────────────────────────────────────────────────────────

class VectorDB:
    """Qdrant-backed schema vector store with optional hybrid search and
    cross-encoder reranking.

    Parameters
    ----------
    collection_name:
        Qdrant collection to use.  Each target database should get its own
        collection so schema lookups are scoped.
    use_reranker:
        Whether to apply cross-encoder reranking after vector retrieval.
    """

    def __init__(
        self,
        collection_name: str | None = None,
        use_reranker: bool = True,
        dense_model: str | None = None,
        sparse_model: str | None = None,
        hybrid: bool | None = None,
    ) -> None:
        from qdrant_client import QdrantClient  # type: ignore

        self.collection_name = collection_name or settings.qdrant_collection
        self.dense_model = dense_model or settings.dense_embed_model
        self.sparse_model = sparse_model or settings.sparse_embed_model
        self.hybrid = hybrid if hybrid is not None else settings.hybrid_search

        # Connect to Qdrant
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        self.client.set_model(self.dense_model)

        if self.hybrid:
            self.client.set_sparse_model(self.sparse_model)

        self._ensure_collection()

        # Optional reranker
        self.reranker: _Reranker | None = None
        if use_reranker:
            try:
                self.reranker = _Reranker(model_name=settings.reranker_model)
            except ImportError:
                logger.warning("flashrank not installed — reranking disabled.")

    # ── Collection management ─────────────────────────────────────────────────

    def _ensure_collection(self) -> None:
        """Create collection if it doesn't exist yet."""
        if self.client.collection_exists(self.collection_name):
            logger.info("Collection '%s' already exists.", self.collection_name)
            return

        vectors_config = self.client.get_fastembed_vector_params()
        kwargs: dict[str, Any] = {
            "collection_name": self.collection_name,
            "vectors_config": vectors_config,
        }
        if self.hybrid:
            kwargs["sparse_vectors_config"] = (
                self.client.get_fastembed_sparse_vector_params()
            )

        self.client.create_collection(**kwargs)
        logger.info("Created Qdrant collection '%s'.", self.collection_name)

    def delete_collection(self) -> None:
        """Drop the entire collection (use with care)."""
        self.client.delete_collection(self.collection_name)
        logger.warning("Deleted collection '%s'.", self.collection_name)
        self._ensure_collection()

    # ── Indexing ──────────────────────────────────────────────────────────────

    def add_documents(self, documents: list[Document]) -> int:
        """Index a list of Documents into Qdrant.

        Returns the number of documents indexed.
        """
        if not documents:
            logger.warning("add_documents called with empty list — skipping.")
            return 0

        texts = [doc["content"] for doc in documents]
        ids = [self._make_id(doc) for doc in documents]
        metadatas = [
            {
                "source": doc["metadata"].get("source", ""),
                "source_type": doc["metadata"].get("source_type", ""),
                "table_name": doc["metadata"].get("table_name", ""),
                "schema_name": doc["metadata"].get("schema_name", ""),
                "page": doc["metadata"].get("page", 0),
                "text_data": doc["content"],   # keep raw text for retrieval
            }
            for doc in documents
        ]

        self.client.add(
            collection_name=self.collection_name,
            documents=texts,
            ids=list(tqdm(ids, desc="Indexing")),
            metadata=metadatas,
        )

        logger.info(
            "Indexed %d documents into collection '%s'.",
            len(documents),
            self.collection_name,
        )
        return len(documents)

    # ── Retrieval ─────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        rerank_top_n: int = 5,
    ) -> list[RetrievedDoc]:
        """Retrieve the most relevant schema chunks for a natural-language query.

        1. Dense (+ optional sparse) search in Qdrant.
        2. Cross-encoder reranking (if reranker is available).

        Returns a list of dicts with keys:
            ``content``, ``score``, ``table_name``, ``schema_name``, ``source``
        """
        count = self.client.count(self.collection_name).count
        if count == 0:
            logger.warning("Collection '%s' is empty — no schemas indexed.", self.collection_name)
            return []

        effective_top_k = min(top_k, count)

        raw_results = self.client.query(
            collection_name=self.collection_name,
            query_text=query,
            limit=effective_top_k,
        )

        candidates: list[RetrievedDoc] = [
            {
                "id": str(hit.id),
                "content": hit.metadata.get("text_data", ""),
                "score": hit.score,
                "table_name": hit.metadata.get("table_name", ""),
                "schema_name": hit.metadata.get("schema_name", ""),
                "source": hit.metadata.get("source", ""),
                "source_type": hit.metadata.get("source_type", ""),
            }
            for hit in raw_results
        ]

        if self.reranker and len(candidates) > 1:
            try:
                candidates = self.reranker.rerank(query, candidates, top_n=rerank_top_n)
            except Exception as exc:
                logger.warning("Reranking failed (%s) — using raw results.", exc)
                candidates = candidates[:rerank_top_n]
        else:
            candidates = candidates[:rerank_top_n]

        logger.debug(
            "Retrieved %d candidates for query: %.60s…", len(candidates), query
        )
        return candidates

    def retrieve_multi(
        self,
        queries: list[str],
        top_k_per_query: int = 10,
        rerank_top_n: int = 5,
        max_tables: int = 5,
    ) -> list[RetrievedDoc]:
        """Retrieve and de-duplicate results across multiple sub-queries.

        Useful when the NL query has been decomposed into several facets
        (e.g. entities extracted from the question).
        """
        seen_tables: set[str] = set()
        results: list[RetrievedDoc] = []

        for q in queries:
            hits = self.retrieve(q, top_k=top_k_per_query, rerank_top_n=rerank_top_n)
            for hit in hits:
                key = f"{hit['schema_name']}.{hit['table_name']}"
                if key not in seen_tables and len(results) < max_tables:
                    seen_tables.add(key)
                    results.append(hit)

        return results

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _make_id(doc: Document) -> str:
        """Create a deterministic UUID from the document content."""
        content_bytes = doc["content"].encode("utf-8")
        hash_hex = hashlib.sha256(content_bytes).hexdigest()
        namespace = uuid.UUID("00000000-0000-0000-0000-000000000000")
        return str(uuid.uuid5(namespace, hash_hex))

    def collection_info(self) -> dict[str, Any]:
        """Return basic stats about the collection."""
        info = self.client.get_collection(self.collection_name)
        count = self.client.count(self.collection_name).count
        return {
            "collection_name": self.collection_name,
            "vector_count": count,
            "status": str(info.status),
        }
