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
    GROQ_API_KEY: str = ""  # speech-to-text (Groq Whisper)

    # ---- Voice --------------------------------------------------------------
    # Speech-to-text: Groq's hosted Whisper (OpenAI-compatible API, free tier).
    GROQ_API_BASE: str = "https://api.groq.com/openai/v1"
    GROQ_STT_MODEL: str = "whisper-large-v3-turbo"
    # Largest accepted recording (5 MB is ~5 minutes of Opus audio).
    STT_MAX_BYTES: int = Field(5 * 1024 * 1024, ge=1024, le=25 * 1024 * 1024)
    # Text-to-speech: edge-tts (Microsoft Edge online voices, no key, no model).
    # Lessons use Egyptian Arabic, so the Arabic voice is Egyptian. Each
    # language has a fallback voice tried when the first returns no audio
    # (live check: ar-EG-ShakirNeural failed 4/4 on ordinary sentences).
    TTS_VOICE_AR: str = "ar-EG-SalmaNeural"
    TTS_VOICE_AR_FALLBACK: str = "ar-SA-HamedNeural"
    TTS_VOICE_EN: str = "en-US-AndrewNeural"
    TTS_VOICE_EN_FALLBACK: str = "en-US-AriaNeural"
    TTS_MAX_CHARS: int = Field(3000, ge=100, le=10000)

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

    # ---- Embeddings ---------------------------------------------------------
    # "gemini": Gemini Embedding API. No model download, low RAM; fits free
    #   cloud hosting. Default.
    # "local": BAAI/bge-m3 via sentence-transformers (~2.3 GB download, needs
    #   torch: pip install -r requirements-local.txt). Fixed 1024 dims.
    # Switching provider or dimensions changes the vector size, so the Qdrant
    # collection must be rebuilt: reingest_courses.py --recreate-collection.
    EMBEDDING_PROVIDER: Literal["gemini", "local"] = "gemini"
    # gemini-embedding-001 returns one vector per text; gemini-embedding-2
    # merges a multi-text request into a single vector, so it cannot batch.
    GEMINI_EMBEDDING_MODEL: str = "gemini-embedding-001"
    # Output size for Gemini embeddings (Matryoshka: 768, 1536 or 3072 are the
    # recommended sizes). 768 keeps the collection small on free tiers.
    EMBEDDING_DIMENSIONS: int = Field(768, ge=128, le=3072)
    LOCAL_EMBEDDING_MODEL: str = "BAAI/bge-m3"

    # ---- Retrieval / grounding ---------------------------------------------
    # Number of chunks given to the tutor as context.
    RAG_TOP_K: int = Field(3, ge=1, le=20)
    # Minimum cosine similarity for a chunk to count as relevant. The scale
    # depends on the embedding model, so recalibrate after switching provider.
    # Below this the chunk is dropped; with no chunks left the tutor declines
    # instead of answering from weak context.
    # Calibrated live for gemini-embedding-001 @768 (2026-11-23, Python course):
    # in-lesson questions scored 0.67-0.74, off-topic 0.51-0.60. 0.64 sits in
    # the gap, so off-topic questions are declined before any generation call.
    # Small sample: re-check as more courses are ingested. (bge-m3 used 0.45.)
    RAG_MIN_SCORE: float = Field(0.64, ge=0.0, le=1.0)
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
    # Runtime data that is not committed: learner database, narration cache.
    DATA_DIR: Path = PROJECT_ROOT / "data"
    # SQLite file for learner profiles, progress and question quota. The
    # repository interface (app/services/learner_store.py) is what a future
    # Supabase/Postgres implementation replaces. ":memory:" works for tests.
    LEARNER_DB_PATH: str = str(PROJECT_ROOT / "data" / "codeu.db")

    # ---- Learners and quota --------------------------------------------------
    # Free questions per learner per UTC day (architecture doc: 3/day, more via
    # rewarded ads later). 0 disables the limit (handy for local development).
    DAILY_QUESTION_LIMIT: int = Field(3, ge=0, le=1000)

    # ---- Lesson narration ("Explain this lesson") -----------------------------
    # Longest spoken walkthrough. Stays under TTS_MAX_CHARS so it is spoken whole.
    LECTURE_MAX_CHARS: int = Field(2800, ge=300, le=10000)

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
