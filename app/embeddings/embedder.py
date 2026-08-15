"""
embeddings/embedder.py
Generates dense (and optionally sparse) vector embeddings for Documents.

This module is intentionally thin — the heavy lifting (batching, CUDA/CPU
selection, model download) is delegated to ``fastembed`` which is already
used by the Qdrant client in this project.

Usage
    from app.embeddings.embedder import Embedder
    embedder = Embedder()
    vecs = embedder.embed_texts(["SELECT * FROM orders", "monthly revenue"])
"""

from __future__ import annotations

import logging
from typing import Any
import numpy as np
from app.config.settings import settings
logger = logging.getLogger(__name__)
Document = dict[str, Any]

class Embedder:
    """Wraps fastembed models to produce dense (and sparse) embeddings.

    Parameters
    dense_model:
        HuggingFace model id for dense embeddings.
        Default: ``sentence-transformers/all-MiniLM-L6-v2``
    sparse_model:
        Model id for sparse (SPLADE) embeddings.
        Only loaded when ``hybrid=True``.
    hybrid:
        Whether to also produce sparse vectors.
    """

    def __init__(
        self,
        dense_model: str | None = None,
        sparse_model: str | None = None,
        hybrid: bool | None = None,
    ) -> None:
        self.dense_model_name = dense_model or settings.dense_embed_model
        self.sparse_model_name = sparse_model or settings.sparse_embed_model
        self.hybrid = hybrid if hybrid is not None else settings.hybrid_search

        self._dense_model = None   #lazy-loaded
        self._sparse_model = None  #lazy-loaded


    def _get_dense_model(self):
        if self._dense_model is None:
            from fastembed import TextEmbedding  #type: ignore

            logger.info("Loading dense embedding model: %s", self.dense_model_name)
            self._dense_model = TextEmbedding(self.dense_model_name)
        return self._dense_model

    def _get_sparse_model(self):
        if not self.hybrid:
            return None
        if self._sparse_model is None:
            from fastembed.sparse import SparseTextEmbedding  # type: ignore

            logger.info("Loading sparse embedding model: %s", self.sparse_model_name)
            self._sparse_model = SparseTextEmbedding(self.sparse_model_name)
        return self._sparse_model


    def embed_texts(self, texts: list[str]) -> list[np.ndarray]:
        """Return dense embedding vectors for a list of text strings."""
        model = self._get_dense_model()
        embeddings = list(model.embed(texts))
        logger.debug("Embedded %d texts → %d vectors.", len(texts), len(embeddings))
        return embeddings

    def embed_documents(self, documents: list[Document]) -> list[Document]:
        """Attach ``embedding`` field to each Document in-place and return them."""
        texts = [doc["content"] for doc in documents]
        vectors = self.embed_texts(texts)

        for doc, vec in zip(documents, vectors):
            doc["embedding"] = vec

        return documents

    def embed_query(self, query: str) -> np.ndarray:
        """Embed a single query string (for retrieval)."""
        return self.embed_texts([query])[0]

    def embed_query_sparse(self, query: str):
        """Return a sparse embedding for the query (SPLADE).  Returns None if
        hybrid search is disabled."""
        model = self._get_sparse_model()
        if model is None:
            return None
        result = list(model.embed([query]))
        return result[0] if result else None

    @property
    def embedding_dim(self) -> int:
        """Return the dimensionality of the dense embedding vectors."""
        sample = self.embed_texts(["probe"])
        return len(sample[0])
