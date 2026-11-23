"""Qdrant collection setup that matches the active embedding model."""

import logging

from qdrant_client.http import models as rest

from app.core.config import settings
from app.services.ai_clients import get_qdrant_client

logger = logging.getLogger(__name__)

# Fields the tutor and ingestion filter on. Qdrant Cloud can reject filters on
# unindexed fields, and indexes keep filtered search fast as the corpus grows.
INDEXED_FIELDS = ("course_title", "step_id")


class CollectionDimensionError(RuntimeError):
    """The collection's vector size does not match the embedding model."""


def collection_vector_size(client, name: str) -> int | None:
    if not client.collection_exists(name):
        return None
    vectors = client.get_collection(name).config.params.vectors
    # Single unnamed vector config (what this project creates).
    return getattr(vectors, "size", None)


def ensure_collection(dimensions: int, recreate: bool = False, client=None, name: str | None = None) -> str:
    """Make sure the collection exists with ``dimensions``-sized cosine vectors.

    Returns "created", "recreated" or "exists". A size mismatch raises
    CollectionDimensionError unless ``recreate`` is True, in which case the
    collection (and every stored chunk) is deleted and rebuilt empty.
    """
    client = client or get_qdrant_client()
    name = name or settings.COLLECTION_NAME
    current = collection_vector_size(client, name)
    action = "exists"

    if current is not None and current != dimensions:
        if not recreate:
            raise CollectionDimensionError(
                f"Qdrant collection {name!r} stores {current}-dim vectors but the embedding model "
                f"produces {dimensions}. Rebuild it with: python reingest_courses.py --recreate-collection"
            )
        logger.warning("Recreating collection %r: %s -> %s dims (old chunks are deleted)", name, current, dimensions)
        client.delete_collection(name)
        current = None
        action = "recreated"

    if current is None:
        client.create_collection(
            collection_name=name,
            vectors_config=rest.VectorParams(size=dimensions, distance=rest.Distance.COSINE),
        )
        action = "created" if action == "exists" else action

    for field in INDEXED_FIELDS:
        # Idempotent: creating an existing index is a no-op on the server.
        client.create_payload_index(name, field_name=field, field_schema=rest.PayloadSchemaType.KEYWORD)
    return action
