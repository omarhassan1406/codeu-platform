import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, status
from pydantic import BaseModel, Field, field_validator

router = APIRouter()
logger = logging.getLogger(__name__)


class GenerateCourseRequest(BaseModel):
    course_topic: str = Field(..., min_length=3, max_length=200)

    @field_validator("course_topic")
    @classmethod
    def normalize_course_topic(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 3:
            raise ValueError("course_topic must contain at least 3 characters")
        return value


class GenerateCourseResponse(BaseModel):
    status: str
    course_topic: str
    message: str


def _generate_course(job_id: str, course_topic: str) -> None:
    started_at = time.monotonic()
    logger.info("Course generation job %s started (topic=%r)", job_id, course_topic)
    try:
        from Generate_Course import run_codeu_complete_pipeline

        run_codeu_complete_pipeline(course_topic=course_topic)
    except Exception:
        logger.exception(
            "Course generation job %s failed (topic=%r, elapsed=%.1fs)",
            job_id,
            course_topic,
            time.monotonic() - started_at,
        )
    else:
        logger.info(
            "Course generation job %s completed (topic=%r, elapsed=%.1fs)",
            job_id,
            course_topic,
            time.monotonic() - started_at,
        )


@router.post(
    "/generate",
    response_model=GenerateCourseResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def generate_course(
    request: GenerateCourseRequest,
    background_tasks: BackgroundTasks,
) -> GenerateCourseResponse:
    """Start full course generation (roadmap, lessons, Qdrant ingestion) in the background."""
    job_id = uuid.uuid4().hex[:12]
    logger.info("Accepted course generation job %s (topic=%r)", job_id, request.course_topic)
    background_tasks.add_task(_generate_course, job_id, request.course_topic)
    return GenerateCourseResponse(
        status="accepted",
        course_topic=request.course_topic,
        message="Course generation started in the background.",
    )
