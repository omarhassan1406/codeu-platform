import logging
import time
import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field, field_validator

from app.schemas.courses import CourseDetail, CourseStatus, CourseSummary, LessonDetail
from app.services import course_catalog

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


# ---- Read-only catalog -----------------------------------------------------
# Plain ``def`` handlers: they read files, so FastAPI runs them in its threadpool.


@router.get("", response_model=list[CourseSummary])
def list_courses(
    status_filter: CourseStatus | None = Query(None, alias="status"),
) -> list[CourseSummary]:
    """List generated courses. Use ?status=complete to show only finished ones."""
    return course_catalog.list_courses(status=status_filter)


@router.get("/{course_id}", response_model=CourseDetail)
def get_course(course_id: str) -> CourseDetail:
    """Full roadmap of one course, with per-lesson availability."""
    try:
        return course_catalog.get_course(course_id)
    except course_catalog.CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")


@router.get("/{course_id}/lessons/{step_id}", response_model=LessonDetail)
def get_lesson(course_id: str, step_id: str) -> LessonDetail:
    """One lesson's Markdown plus its position (previous/next step) in the course."""
    try:
        return course_catalog.get_lesson(course_id, step_id)
    except course_catalog.CourseNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    except course_catalog.LessonNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
