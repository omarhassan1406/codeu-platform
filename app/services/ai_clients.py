"""Lazily created clients for external AI services.

Nothing heavy happens at import time: network clients are built on first use
and cached for the process. The local bge-m3 model (several GB, needs torch and
sentence-transformers from requirements-local.txt) loads only when
EMBEDDING_PROVIDER=local.
"""

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

# bge-m3 produces fixed 1024-dimensional vectors.
LOCAL_EMBEDDING_DIMENSIONS = 1024


@lru_cache(maxsize=1)
def get_embedding_model():
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError(
            "EMBEDDING_PROVIDER=local needs sentence-transformers: pip install -r requirements-local.txt"
        ) from error

    logger.info("Loading embedding model %s ...", settings.LOCAL_EMBEDDING_MODEL)
    return SentenceTransformer(settings.LOCAL_EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_qdrant_client():
    from qdrant_client import QdrantClient

    return QdrantClient(
        url=settings.QDRANT_URL,
        api_key=settings.QDRANT_API_KEY,
        timeout=60,
    )


@lru_cache(maxsize=1)
def get_gemini_client():
    from google import genai

    return genai.Client(api_key=settings.GEMINI_API_KEY)
