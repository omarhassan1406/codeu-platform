"""In-memory registry of course generation jobs.

The pipeline reports progress through a callback after every manifest save,
so the frontend can poll ``GET /courses/jobs/{job_id}``. Jobs live in process
memory: they are lost on restart and are not shared between worker processes.
The course folder's manifest.json stays the durable record of progress.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Callable

from app.schemas.courses import GenerationJob

# Messages shown to learners. Internal details stay in the server log.
INCOMPLETE_MESSAGE = "The AI kept returning incomplete content, so the course was not saved as finished."
FAILED_MESSAGE = "Course generation failed. Please try again later."

_lock = threading.Lock()
_jobs: dict[str, GenerationJob] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(course_topic: str) -> GenerationJob:
    job_id = uuid.uuid4().hex
    now = _now()
    job = GenerationJob(
        job_id=job_id,
        course_topic=course_topic,
        status="queued",
        created_at=now,
        updated_at=now,
    )
    with _lock:
        _jobs[job_id] = job
    return job.model_copy()


def get_job(job_id: str) -> GenerationJob | None:
    with _lock:
        job = _jobs.get(job_id)
        return job.model_copy() if job else None


def _update(job_id: str, **changes) -> None:
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        _jobs[job_id] = job.model_copy(update={**changes, "updated_at": _now()})


def mark_running(job_id: str) -> None:
    _update(job_id, status="running")


def progress_callback(job_id: str) -> Callable[[dict], None]:
    """Build the callback the pipeline calls with (course_id, manifest) updates."""

    def report(update: dict) -> None:
        _update(
            job_id,
            course_id=update.get("course_id"),
            course_title=update.get("course_title"),
            total_steps=update.get("total_steps", 0),
            completed_steps=len(update.get("completed_steps", [])),
        )

    return report


def mark_complete(job_id: str) -> None:
    _update(job_id, status="complete", error=None)


def mark_failed(job_id: str, incomplete: bool = False) -> None:
    _update(job_id, status="failed", error=INCOMPLETE_MESSAGE if incomplete else FAILED_MESSAGE)


def clear() -> None:
    """Drop all jobs (used by tests)."""
    with _lock:
        _jobs.clear()
