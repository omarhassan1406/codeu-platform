import logging

from qdrant_client.http import models as rest

from app.core.config import settings
from app.schemas.rag import RetrievedChunk
from app.services.ai_clients import get_embedding_model, get_qdrant_client
from app.services.reranker import NoOpReranker, Reranker, get_reranker

__all__ = ["RagUnavailableError", "RetrievedChunk", "search_course_rag"]

logger = logging.getLogger(__name__)


class RagUnavailableError(RuntimeError):
    """The vector store could not be queried, so no grounded answer is possible."""


def search_course_rag(
    course_title: str,
    student_question: str,
    limit: int | None = None,
    min_score: float | None = None,
    reranker: Reranker | None = None,
) -> list[RetrievedChunk]:
    """Search Qdrant for chunks of one course that are relevant to the question.

    Only chunks with a similarity score at or above ``min_score`` are kept, so
    an empty list means "the course does not cover this". When a reranker is
    configured, ``RAG_RERANK_CANDIDATES`` hits are fetched and reranked down to
    ``limit``. Infrastructure failures raise ``RagUnavailableError`` instead of
    looking like "no answer".
    """
    limit = settings.RAG_TOP_K if limit is None else limit
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score
    reranker = reranker or get_reranker()
    reranking = not isinstance(reranker, NoOpReranker)
    fetch_limit = max(limit, settings.RAG_RERANK_CANDIDATES) if reranking else limit

    try:
        query_vector = get_embedding_model().encode(student_question).tolist()
        response = get_qdrant_client().query_points(
            collection_name=settings.COLLECTION_NAME,
            query=query_vector,
            query_filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="course_title",
                        match=rest.MatchValue(value=course_title),
                    )
                ]
            ),
            limit=fetch_limit,
            score_threshold=min_score,
            with_payload=True,
        )
    except Exception as error:
        logger.exception("RAG search failed for course %r", course_title)
        raise RagUnavailableError("Course knowledge base is unavailable") from error

    chunks: list[RetrievedChunk] = []
    for hit in response.points:
        payload = hit.payload or {}
        text = (payload.get("text") or "").strip()
        if not text or hit.score is None or hit.score < min_score:
            continue
        chunks.append(
            RetrievedChunk(
                text=text,
                score=float(hit.score),
                step_id=payload.get("step_id"),
                step_title=payload.get("step_title"),
            )
        )

    try:
        return reranker.rerank(student_question, chunks, limit)
    except Exception:
        # A reranker failure must not block answers: fall back to vector order.
        logger.exception("Reranker %s failed; using vector order", getattr(reranker, "name", "?"))
        return chunks[:limit]
