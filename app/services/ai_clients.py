"""Lazily created clients for external AI services.

Nothing heavy happens at import time: the bge-m3 embedding model (several GB)
and the network clients are built on first use and cached for the process.
"""

import logging
from functools import lru_cache

from app.core.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_MODEL_NAME = "BAAI/bge-m3"


@lru_cache(maxsize=1)
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %s ...", EMBEDDING_MODEL_NAME)
    return SentenceTransformer(EMBEDDING_MODEL_NAME)


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
