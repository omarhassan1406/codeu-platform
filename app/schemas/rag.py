from dataclasses import dataclass


@dataclass(frozen=True)
class RetrievedChunk:
    """One piece of course content returned by retrieval."""

    text: str
    score: float  # vector similarity from Qdrant
    step_id: str | None = None
    step_title: str | None = None
    rerank_score: float | None = None  # set only when a reranker ran
