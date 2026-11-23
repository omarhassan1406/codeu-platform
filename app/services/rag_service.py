import logging

from qdrant_client.http import models as rest

from app.core.config import settings
from app.schemas.rag import RetrievedChunk
from app.services.ai_clients import get_qdrant_client
from app.services.embeddings import get_embedder
from app.services.reranker import NoOpReranker, Reranker, get_reranker

__all__ = ["RagUnavailableError", "RetrievedChunk", "search_course_rag"]

logger = logging.getLogger(__name__)


class RagUnavailableError(RuntimeError):
    """The vector store could not be queried, so no grounded answer is possible."""


def _match(key: str, value: str) -> rest.FieldCondition:
    return rest.FieldCondition(key=key, match=rest.MatchValue(value=value))


def _query(vector: list[float], conditions: list[rest.FieldCondition], limit: int, min_score: float):
    return get_qdrant_client().query_points(
        collection_name=settings.COLLECTION_NAME,
        query=vector,
        query_filter=rest.Filter(must=conditions),
        limit=limit,
        score_threshold=min_score,
        with_payload=True,
    ).points


def _to_chunks(hits, min_score: float, seen: set) -> list[RetrievedChunk]:
    chunks: list[RetrievedChunk] = []
    for hit in hits:
        payload = hit.payload or {}
        text = (payload.get("text") or "").strip()
        key = getattr(hit, "id", None) or text
        if not text or hit.score is None or hit.score < min_score or key in seen:
            continue
        seen.add(key)
        chunks.append(
            RetrievedChunk(
                text=text,
                score=float(hit.score),
                step_id=payload.get("step_id"),
                step_title=payload.get("step_title"),
            )
        )
    return chunks


def _rerank(reranker: Reranker, question: str, chunks: list[RetrievedChunk], limit: int) -> list[RetrievedChunk]:
    if not chunks:
        return []
    try:
        return reranker.rerank(question, chunks, limit)
    except Exception:
        # A reranker failure must not block answers: fall back to vector order.
        logger.exception("Reranker %s failed; using vector order", getattr(reranker, "name", "?"))
        return chunks[:limit]


def search_course_rag(
    course_title: str,
    student_question: str,
    limit: int | None = None,
    min_score: float | None = None,
    reranker: Reranker | None = None,
    step_id: str | None = None,
) -> list[RetrievedChunk]:
    """Search Qdrant for chunks of one course that are relevant to the question.

    With ``step_id``, chunks from the learner's current lesson come first; if
    that lesson has fewer than ``limit`` relevant chunks, the rest of the course
    fills the gap. Every chunk must reach ``min_score``, so an empty list means
    "the course does not cover this". The question is embedded once for both
    searches. When a reranker is configured, each group is reranked on its own
    so the current lesson keeps priority. Infrastructure failures raise
    ``RagUnavailableError`` instead of looking like "no answer".
    """
    limit = settings.RAG_TOP_K if limit is None else limit
    min_score = settings.RAG_MIN_SCORE if min_score is None else min_score
    reranker = reranker or get_reranker()
    reranking = not isinstance(reranker, NoOpReranker)
    fetch_limit = max(limit, settings.RAG_RERANK_CANDIDATES) if reranking else limit
    course = _match("course_title", course_title)

    seen: set = set()
    try:
        vector = get_embedder().embed_query(student_question)
        lesson: list[RetrievedChunk] = []
        if step_id:
            lesson = _to_chunks(_query(vector, [course, _match("step_id", step_id)], fetch_limit, min_score), min_score, seen)
        others: list[RetrievedChunk] = []
        if len(lesson) < limit:
            # Fetch extra so hits already taken from the lesson can be skipped.
            others = _to_chunks(_query(vector, [course], fetch_limit + len(lesson), min_score), min_score, seen)
    except Exception as error:
        logger.exception("RAG search failed for course %r", course_title)
        raise RagUnavailableError("Course knowledge base is unavailable") from error

    lesson = _rerank(reranker, student_question, lesson, limit)
    others = _rerank(reranker, student_question, others, limit - len(lesson))
    return (lesson + others)[:limit]
