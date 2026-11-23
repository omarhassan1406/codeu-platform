"""Text embedding providers.

``gemini`` (default) calls the Gemini Embedding API: no model download, low RAM,
suitable for free cloud hosting. ``local`` runs BAAI/bge-m3 through
sentence-transformers; its heavy imports (torch) happen only when it is used,
so cloud deployments never need those packages installed.

Documents and queries are embedded separately because Gemini uses different
task types for each, which improves retrieval quality.
"""

import logging
import math
import time
from functools import lru_cache
from typing import Protocol

from app.core.config import settings
from app.services.ai_clients import LOCAL_EMBEDDING_DIMENSIONS, get_embedding_model, get_gemini_client

logger = logging.getLogger(__name__)

# The Gemini API accepts at most 100 texts per embed call.
GEMINI_BATCH_SIZE = 100

# Free tier: 100 embedded texts per minute per model (each text in a batch
# counts). Ingestion waits as long as the server asks (RetryInfo), capped;
# a learner's query gives up quickly so the tutor answers 503 instead of hanging.
INGEST_MAX_RETRIES = 6
MAX_RETRY_WAIT_SECONDS = 90.0
QUERY_MAX_RETRIES = 2
QUERY_MAX_WAIT_SECONDS = 3.0


class Embedder(Protocol):
    name: str
    model: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _is_rate_limited(error: Exception) -> bool:
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    return code == 429 or getattr(error, "status", None) == "RESOURCE_EXHAUSTED"


def retry_delay_seconds(error: Exception, attempt: int) -> float:
    """Seconds to wait before retrying: the server's RetryInfo when present
    (plus 1s of slack), otherwise exponential backoff. Capped."""
    server_delay = None
    details = getattr(error, "details", None)
    try:
        for item in (details or {}).get("error", {}).get("details", []):
            if str(item.get("@type", "")).endswith("RetryInfo"):
                server_delay = float(str(item.get("retryDelay", "")).rstrip("s"))
    except (AttributeError, TypeError, ValueError):
        server_delay = None
    delay = math.ceil(server_delay) + 1 if server_delay is not None else 2.0 ** (attempt + 1)
    return float(min(delay, MAX_RETRY_WAIT_SECONDS))


class GeminiEmbedder:
    name = "gemini"

    def __init__(self, model: str, dimensions: int, client=None, sleep=time.sleep):
        self.model = model
        self.dimensions = dimensions
        self._client = client
        self._sleep = sleep

    def _embed(self, texts: list[str], task_type: str, max_retries: int, max_total_wait: float) -> list[list[float]]:
        from google.genai import types

        client = self._client or get_gemini_client()
        config = types.EmbedContentConfig(task_type=task_type, output_dimensionality=self.dimensions)
        vectors: list[list[float]] = []
        waited = 0.0
        for start in range(0, len(texts), GEMINI_BATCH_SIZE):
            batch = texts[start : start + GEMINI_BATCH_SIZE]
            for attempt in range(max_retries):
                try:
                    response = client.models.embed_content(model=self.model, contents=batch, config=config)
                    break
                except Exception as error:
                    budget = max_total_wait - waited
                    if not _is_rate_limited(error) or attempt == max_retries - 1 or budget <= 0:
                        raise
                    delay = min(retry_delay_seconds(error, attempt), budget)
                    logger.warning("Gemini embedding rate limited; retrying in %.0fs", delay)
                    self._sleep(delay)
                    waited += delay
            batch_vectors = [list(e.values) for e in response.embeddings]
            # Some models fold a multi-text request into one vector; never
            # silently store misaligned embeddings.
            if len(batch_vectors) != len(batch):
                raise RuntimeError(
                    f"{self.model} returned {len(batch_vectors)} embeddings for {len(batch)} texts"
                )
            for vector in batch_vectors:
                if len(vector) != self.dimensions:
                    raise RuntimeError(f"{self.model} returned {len(vector)} dims, expected {self.dimensions}")
            vectors.extend(batch_vectors)
        return vectors

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts, "RETRIEVAL_DOCUMENT", INGEST_MAX_RETRIES, INGEST_MAX_RETRIES * MAX_RETRY_WAIT_SECONDS)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY", QUERY_MAX_RETRIES, QUERY_MAX_WAIT_SECONDS)[0]


class LocalEmbedder:
    name = "local"

    def __init__(self, model=None):
        self.model = settings.LOCAL_EMBEDDING_MODEL
        self.dimensions = LOCAL_EMBEDDING_DIMENSIONS
        self._model = model

    def _encoder(self):
        return self._model or get_embedding_model()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return [list(map(float, v)) for v in self._encoder().encode(texts)]

    def embed_query(self, text: str) -> list[float]:
        return list(map(float, self._encoder().encode(text)))


@lru_cache(maxsize=4)
def _build_embedder(provider: str) -> Embedder:
    if provider == "gemini":
        return GeminiEmbedder(settings.GEMINI_EMBEDDING_MODEL, settings.EMBEDDING_DIMENSIONS)
    if provider == "local":
        return LocalEmbedder()
    raise ValueError(f"Unknown embedding provider: {provider!r}")


def get_embedder(provider: str | None = None) -> Embedder:
    """Embedder for ``provider`` (defaults to settings.EMBEDDING_PROVIDER), cached."""
    return _build_embedder(provider or settings.EMBEDDING_PROVIDER)
