"""Read-only access to generated courses on disk.

Layout (see app/core/course_paths.py):
    <GENERATED_COURSES_DIR>/<course_id>/roadmap.json
    <GENERATED_COURSES_DIR>/<course_id>/manifest.json   (absent for legacy courses)
    <GENERATED_COURSES_DIR>/<course_id>/step_<id>_<title>.md
"""

import json
import logging
import os
from pathlib import Path

from app.core.config import settings
from app.core.course_paths import MANIFEST_FILENAME, ROADMAP_FILENAME, lesson_filename
from app.schemas.courses import (
    CourseDetail,
    CourseSummary,
    LessonDetail,
    SectionSummary,
    StepSummary,
)

logger = logging.getLogger(__name__)


class CourseNotFoundError(LookupError):
    pass


class LessonNotFoundError(LookupError):
    pass


def _base_dir(base_dir: str | Path | None) -> Path:
    return Path(base_dir) if base_dir is not None else Path(settings.GENERATED_COURSES_DIR)


def _read_json(path: Path) -> dict | None:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError):
        logger.warning("Could not read %s", path, exc_info=True)
        return None


def _course_ids(base: Path) -> list[str]:
    if not base.is_dir():
        return []
    return sorted(
        name for name in os.listdir(base) if (base / name / ROADMAP_FILENAME).is_file()
    )


def _resolve_course_dir(course_id: str, base: Path) -> Path:
    # Only ids that appear in the listing are accepted, so path tricks such as
    # "../" can never escape the courses directory.
    if course_id not in _course_ids(base):
        raise CourseNotFoundError(course_id)
    return base / course_id


def _build_detail(course_id: str, course_path: Path) -> CourseDetail | None:
    roadmap = _read_json(course_path / ROADMAP_FILENAME)
    if not roadmap or "course_title" not in roadmap:
        return None
    manifest = _read_json(course_path / MANIFEST_FILENAME)

    sections: list[SectionSummary] = []
    for section in roadmap.get("sections", []):
        steps = [
            StepSummary(
                step_id=step["step_id"],
                title=step["step_title"],
                duration_mins=step.get("duration_mins", 0),
                learning_objectives=step.get("learning_objectives", []),
                available=(course_path / lesson_filename(step["step_id"], step["step_title"])).is_file(),
            )
            for step in section.get("steps", [])
        ]
        sections.append(
            SectionSummary(
                section_id=section["section_id"],
                title=section["section_title"],
                description=section.get("description", ""),
                steps=steps,
            )
        )

    all_steps = [step for section in sections for step in section.steps]
    available = sum(step.available for step in all_steps)
    if manifest and manifest.get("status") in {"complete", "in_progress", "failed"}:
        status = manifest["status"]
    else:
        status = "complete" if all_steps and available == len(all_steps) else "incomplete"

    return CourseDetail(
        course_id=course_id,
        title=roadmap["course_title"],
        target_audience=roadmap.get("target_audience", ""),
        status=status,
        sections_count=len(sections),
        lessons_count=len(all_steps),
        available_lessons_count=available,
        total_duration_mins=sum(step.duration_mins for step in all_steps),
        section_titles=[section.title for section in sections],
        sections=sections,
    )


def _safe_detail(course_id: str, course_path: Path) -> CourseDetail | None:
    try:
        return _build_detail(course_id, course_path)
    except (KeyError, TypeError, ValueError):
        logger.warning("Course %r has a malformed roadmap", course_id, exc_info=True)
        return None


def list_courses(base_dir: str | Path | None = None, status: str | None = None) -> list[CourseSummary]:
    base = _base_dir(base_dir)
    courses: list[CourseSummary] = []
    for course_id in _course_ids(base):
        detail = _safe_detail(course_id, base / course_id)
        if detail is None:
            logger.warning("Skipping course %r: unreadable roadmap", course_id)
            continue
        if status and detail.status != status:
            continue
        courses.append(CourseSummary(**detail.model_dump(exclude={"sections"})))
    return courses


def find_course_id(course_title: str, base_dir: str | Path | None = None) -> str:
    """Course folder for a course title (the tutor API identifies courses by title)."""
    for course in list_courses(base_dir):
        if course.title == course_title:
            return course.course_id
    raise CourseNotFoundError(course_title)


def get_course(course_id: str, base_dir: str | Path | None = None) -> CourseDetail:
    base = _base_dir(base_dir)
    detail = _safe_detail(course_id, _resolve_course_dir(course_id, base))
    if detail is None:
        raise CourseNotFoundError(course_id)
    return detail


def get_lesson(course_id: str, step_id: str, base_dir: str | Path | None = None) -> LessonDetail:
    base = _base_dir(base_dir)
    course = get_course(course_id, base)
    ordered = [(section, step) for section in course.sections for step in section.steps]

    for index, (section, step) in enumerate(ordered):
        if step.step_id != step_id:
            continue
        path = base / course_id / lesson_filename(step.step_id, step.title)
        if not path.is_file():
            raise LessonNotFoundError(f"{course_id}/{step_id}")
        return LessonDetail(
            course_id=course_id,
            course_title=course.title,
            section_id=section.section_id,
            section_title=section.title,
            step_id=step.step_id,
            title=step.title,
            duration_mins=step.duration_mins,
            learning_objectives=step.learning_objectives,
            content_markdown=path.read_text(encoding="utf-8"),
            previous_step_id=ordered[index - 1][1].step_id if index > 0 else None,
            next_step_id=ordered[index + 1][1].step_id if index + 1 < len(ordered) else None,
        )
    raise LessonNotFoundError(f"{course_id}/{step_id}")
