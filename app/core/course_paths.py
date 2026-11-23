"""On-disk layout for generated courses, shared by the pipeline and the viewer.

generated_courses/
    <sanitized course title>/
        roadmap.json
        manifest.json          # generation status and progress
        step_<id>_<title>.md
"""

from pathlib import Path

from app.core.filenames import sanitize_filename

ROADMAP_FILENAME = "roadmap.json"
MANIFEST_FILENAME = "manifest.json"


def course_dir(base_dir: str | Path, course_title: str) -> Path:
    return Path(base_dir) / sanitize_filename(course_title)


def lesson_filename(step_id: str, step_title: str) -> str:
    return f"step_{sanitize_filename(step_id, max_length=20)}_{sanitize_filename(step_title)}.md"
