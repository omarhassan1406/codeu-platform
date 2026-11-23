"""Optional second-stage reranking of retrieved chunks.

The architecture design calls for BGE-Reranker-Large to re-score the top
vector hits and keep the best few. That model is large, so it is opt-in via
``settings.RERANKER`` and loaded only on first use.
"""

import logging
from dataclasses import replace
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.schemas.rag import RetrievedChunk

logger = logging.getLogger(__name__)

BGE_RERANKER_MODEL = "BAAI/bge-reranker-large"


class Reranker(Protocol):
    name: str

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]: ...


class NoOpReranker:
    """Keeps the vector-search order and truncates to ``top_k``."""

    name = "none"

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        return list(chunks[:top_k])


class CrossEncoderReranker:
    """Re-scores (query, chunk) pairs with a cross-encoder and keeps the best ``top_k``."""

    name = "bge"

    def __init__(self, model_name: str = BGE_RERANKER_MODEL, model=None):
        self.model_name = model_name
        self._model = model

    def _get_model(self):
        if self._model is None:
            from sentence_transformers import CrossEncoder

            logger.info("Loading reranker model %s ...", self.model_name)
            self._model = CrossEncoder(self.model_name)
        return self._model

    def rerank(self, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []
        scores = self._get_model().predict([(query, chunk.text) for chunk in chunks])
        rescored = [replace(chunk, rerank_score=float(score)) for chunk, score in zip(chunks, scores)]
        rescored.sort(key=lambda chunk: chunk.rerank_score, reverse=True)
        return rescored[:top_k]


def get_reranker(name: str | None = None) -> Reranker:
    """Return the reranker selected by ``name`` or ``settings.RERANKER``."""
    return _build_reranker(name or settings.RERANKER)


@lru_cache(maxsize=None)
def _build_reranker(name: str) -> Reranker:
    # Cached per name so the cross-encoder model is loaded at most once.
    if name == "none":
        return NoOpReranker()
    if name == "bge":
        return CrossEncoderReranker()
    raise ValueError(f"Unknown reranker: {name!r}")
