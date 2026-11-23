"""Application settings.

Every value can be overridden with an environment variable of the same name,
or in the project-root ``.env`` file (see ``.env.example``). Real environment
variables take precedence over ``.env``.
"""

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        extra="ignore",  # unknown keys in .env are ignored instead of raising
    )

    PROJECT_NAME: str = "CodeU Platform Backend"
    VERSION: str = "1.0.0"

    # ---- API keys (never commit real values) -------------------------------
    GEMINI_API_KEY: str = ""
    GROQ_API_KEY: str = ""  # reserved for speech-to-text; not used yet

    # ---- Gemini models -----------------------------------------------------
    # Model used to generate roadmaps and lessons.
    GEMINI_COURSE_MODEL: str = "gemini-3.5-flash-lite"
    # Model used by the tutor (raise-hand answers).
    # gemini-2.0-flash was the old default; it now returns 404 (retired).
    GEMINI_MODEL_NAME: str = "gemini-3.5-flash-lite"
    # Fallback order when a model is rate limited (429) or unavailable (404).
    GEMINI_MODEL_HIERARCHY: list[str] = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
    ]

    # ---- Qdrant ------------------------------------------------------------
    QDRANT_URL: str = ""
    QDRANT_API_KEY: str = ""
    COLLECTION_NAME: str = "CodeU"

    # ---- Retrieval / grounding ---------------------------------------------
    # Number of chunks given to the tutor as context.
    RAG_TOP_K: int = Field(3, ge=1, le=20)
    # Minimum cosine similarity (bge-m3) for a chunk to count as relevant.
    # Below this the chunk is dropped; with no chunks left the tutor declines
    # instead of answering from weak context.
    RAG_MIN_SCORE: float = Field(0.45, ge=0.0, le=1.0)
    # Optional second-stage reranker. "none" keeps vector order; "bge" loads
    # BAAI/bge-reranker-large (lazily) and re-scores RAG_RERANK_CANDIDATES hits.
    RERANKER: Literal["none", "bge"] = "none"
    # How many vector hits to fetch before reranking down to RAG_TOP_K.
    # Only used when RERANKER is not "none".
    RAG_RERANK_CANDIDATES: int = Field(20, ge=1, le=100)

    # ---- Chunking (ingestion into Qdrant) ----------------------------------
    # "character": structure-aware splitter that keeps headings, paragraphs and
    #   fenced code blocks intact where possible (architecture doc: 600/120).
    # "word": legacy flat word windows (500 words / 50 overlap), kept for
    #   backwards compatibility.
    CHUNK_STRATEGY: Literal["character", "word"] = "character"
    CHUNK_SIZE_CHARS: int = Field(600, ge=100, le=8000)
    CHUNK_OVERLAP_CHARS: int = Field(120, ge=0)
    CHUNK_SIZE_WORDS: int = Field(500, ge=10)
    CHUNK_OVERLAP_WORDS: int = Field(50, ge=0)

    # ---- Course generation completeness rules ------------------------------
    # Attempts per roadmap/lesson before generation fails explicitly.
    GENERATION_MAX_ATTEMPTS: int = Field(3, ge=1, le=10)
    # A generated roadmap is rejected if any section has fewer steps than this.
    ROADMAP_MIN_STEPS_PER_SECTION: int = Field(4, ge=1, le=20)
    # A generated lesson shorter than this (characters) is treated as truncated.
    LESSON_MIN_CHARS: int = Field(800, ge=0)

    # ---- Storage -----------------------------------------------------------
    # Where generated courses live (one folder per course).
    GENERATED_COURSES_DIR: Path = PROJECT_ROOT / "generated_courses"

    @model_validator(mode="after")
    def _check_consistency(self) -> "Settings":
        if self.CHUNK_OVERLAP_CHARS >= self.CHUNK_SIZE_CHARS:
            raise ValueError("CHUNK_OVERLAP_CHARS must be smaller than CHUNK_SIZE_CHARS")
        if self.CHUNK_OVERLAP_WORDS >= self.CHUNK_SIZE_WORDS:
            raise ValueError("CHUNK_OVERLAP_WORDS must be smaller than CHUNK_SIZE_WORDS")
        if self.RERANKER != "none" and self.RAG_RERANK_CANDIDATES < self.RAG_TOP_K:
            raise ValueError("RAG_RERANK_CANDIDATES must be at least RAG_TOP_K when reranking")
        return self


settings = Settings()
