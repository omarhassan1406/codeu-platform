# CodeU backend API (v1)

Base URL: `/api/v1`. The live OpenAPI schema is at `/docs` (Swagger) and
`/openapi.json` when the server runs. The Pydantic models in `app/schemas/` are
the source of truth; this page is a quick map for frontend work.

Run the server:

```
.venv\Scripts\uvicorn app.main:app --reload
```

## Courses (read-only catalog)

| Method | Path | Returns |
|---|---|---|
| GET | `/courses` | `CourseSummary[]`. Optional `?status=complete\|in_progress\|failed\|incomplete` |
| GET | `/courses/{course_id}` | `CourseDetail`: summary plus sections and steps, each step with `available` |
| GET | `/courses/{course_id}/lessons/{step_id}` | `LessonDetail`: lesson Markdown, `previous_step_id`, `next_step_id` |

`course_id` is the course folder name. URL-encode it, since titles can
contain characters like `&`. `CourseSummary.title` is the exact title the
tutor expects as `course_title`.

Status meanings:

- `complete`: every lesson was generated and ingested.
- `in_progress`: generation is running, or stopped mid-way without recording an error.
- `failed`: generation stopped with an error.
- `incomplete`: an older course with no manifest and missing lesson files.

Only show `complete` courses to learners.

Errors: `404` with `{"detail": "Course not found"}` or `{"detail": "Lesson not found"}`.

## Course generation

`POST /courses/generate` with `{"course_topic": "..."}` returns `202` with a
`job_id` and starts generation in the background.

`GET /courses/jobs/{job_id}` returns a `GenerationJob`:

```json
{
  "job_id": "3f2c…", "course_topic": "Calculus for Beginners",
  "status": "running", "course_id": "Calculus_for_Beginners",
  "course_title": "Calculus for Beginners",
  "total_steps": 12, "completed_steps": 4, "error": null,
  "created_at": "…", "updated_at": "…"
}
```

- `status`: `queued`, `running`, `complete` or `failed`. Poll every few
  seconds until it is `complete` or `failed`.
- `course_id` is set once the roadmap exists; open it with `GET /courses/{course_id}`.
- `error` is a learner-safe message. Details stay in the server log.
- `404` with `{"detail": "Job not found"}`: jobs live in server memory, so a
  restart forgets them. The course folder's `manifest.json` still records progress.

## Embeddings and re-ingesting courses

Embeddings come from the Gemini API by default (`EMBEDDING_PROVIDER=gemini`,
`gemini-embedding-001`, 768 dims), so the server needs no local model, torch
or GPU. `EMBEDDING_PROVIDER=local` switches to BAAI/bge-m3 (1024 dims) after
`pip install -r requirements-local.txt`.

The Qdrant collection's vector size must match the embedding model. On
startup of ingestion, a mismatch stops with a message instead of mixing
vectors. Rebuild the collection after changing provider or dimensions.

`reingest_courses.py` re-chunks saved lessons with the configured chunker,
embeds them, and replaces each lesson's Qdrant points (delete by course + step,
then upsert with deterministic IDs). Run with `--dry-run` first to see chunk
counts.

```
.venv\Scripts\python reingest_courses.py --dry-run
.venv\Scripts\python reingest_courses.py --course Programming_in_Python_for_Beginners_to_Advanced
.venv\Scripts\python reingest_courses.py --recreate-collection   # after a provider/dimension change
```

`--recreate-collection` deletes every stored chunk, so re-ingest every course
the tutor should answer for.

## Onboarding suggestions

`POST /onboarding/suggestions`

```json
{
  "profile": {
    "background": "first-year engineering student",
    "interests": ["Python", "Calculus"],
    "level": "beginner",
    "goals": "pass my programming course",
    "preferred_language": "ar"
  },
  "max_suggestions": 5
}
```

Response:

```json
{
  "strategy": "keyword-v1",
  "suggestions": [
    {"kind": "existing", "title": "Programming in Python for Beginners to Advanced",
     "course_id": "Programming_in_Python_for_Beginners_to_Advanced",
     "match_score": 1.0, "reason": "Matches your interest in Python"},
    {"kind": "generate", "title": "Calculus for Beginners",
     "generation_topic": "Calculus for Beginners",
     "match_score": 1.0, "reason": "No existing course covers Calculus yet; we can generate one for you"}
  ]
}
```

- `existing`: open the course with `GET /courses/{course_id}`.
- `generate`: send `generation_topic` as `course_topic` to `POST /courses/generate`.

Profiles are not stored yet. The endpoint is stateless and matches on keywords
only; a smarter ranker can replace it later without changing this contract.

## Tutor

`POST /tutor/raise-hand` with `{"course_title", "step_id", "student_question"}`.

Retrieval is step-aware: chunks from `step_id` (the lesson the learner is on)
come first, and other lessons of the same course fill in only when that lesson
has fewer than `RAG_TOP_K` relevant chunks. Every chunk must still reach
`RAG_MIN_SCORE`. Excerpts are labelled "current lesson" or "another lesson",
and the tutor names the other lesson when it uses one.

- `200` with `avatar_state: "explaining"`: a grounded answer, with the
  source chunks in `context_used`.
- `200` with `avatar_state: "idle"`: the course does not cover the question, so
  the tutor declines rather than guessing.
- `503`: the knowledge base is unreachable.
- `502`: the AI model failed.

## Voice

Both services are hosted, so the server needs no audio models or GPU.

`POST /voice/transcribe` (multipart): field `audio` (webm/ogg/mp4/wav/mp3,
up to `STT_MAX_BYTES`, default 5 MB) and optional field `language` (`ar` or
`en`; omit to auto-detect). Uses Groq Whisper (`GROQ_STT_MODEL`).

```json
{"text": "ما هو المتغير في بايثون؟", "language": "Arabic", "duration_seconds": 4.26, "rejected": null}
```

- `rejected` explains an empty `text`: `no_speech` (silence or noise; Whisper
  invents phrases like "Thank you." for these), `unsupported_language`
  (neither Arabic nor English), or `low_confidence`. Never send an empty
  `text` to the tutor.
- The server names the upload from its content type (Groq needs a real audio
  extension), so a client filename like `blob` is fine.
- `400` empty upload or unreadable audio, `413` too large, `415` not audio or
  unknown format, `503` Groq unavailable (missing key, rate limited, or down).
  `detail` is safe to show learners.
- The classroom also measures the mic level while recording and does not
  upload silent clips.

`POST /voice/speak` with `{"text": "...", "language": "ar" | "en" | null}`
returns `audio/mpeg` via edge-tts. Send plain text, not Markdown. The voice is
picked from the text (mostly Arabic → `TTS_VOICE_AR`) and each language has a
fallback voice; the `X-Voice` header names the one used. `503` when both
voices fail. Text is limited to `TTS_MAX_CHARS` (default 3000).

The classroom sends the answer's caption lines as the text, so captions and
audio cover the same words, and advances captions by each line's share of the
audio duration.
