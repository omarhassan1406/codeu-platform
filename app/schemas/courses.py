"""Response contracts for the read-only course catalog endpoints."""

from typing import Literal

from pydantic import BaseModel, Field

# complete:    every lesson was generated and ingested
# in_progress: generation is running (or was interrupted mid-way)
# failed:      generation stopped with an error (see manifest)
# incomplete:  legacy course without a manifest and with missing lesson files
CourseStatus = Literal["complete", "in_progress", "failed", "incomplete"]


class StepSummary(BaseModel):
    step_id: str
    title: str
    duration_mins: int
    learning_objectives: list[str]
    available: bool = Field(description="True when the lesson Markdown exists on disk")


class SectionSummary(BaseModel):
    section_id: int
    title: str
    description: str
    steps: list[StepSummary]


class CourseSummary(BaseModel):
    course_id: str = Field(description="Stable id used in catalog URLs (the course folder name)")
    title: str = Field(description="Exact course title; send this as course_title to /tutor/raise-hand")
    target_audience: str
    status: CourseStatus
    sections_count: int
    lessons_count: int
    available_lessons_count: int
    total_duration_mins: int
    section_titles: list[str]


class CourseDetail(CourseSummary):
    sections: list[SectionSummary]


class LessonDetail(BaseModel):
    course_id: str
    course_title: str
    section_id: int
    section_title: str
    step_id: str
    title: str
    duration_mins: int
    learning_objectives: list[str]
    content_markdown: str
    previous_step_id: str | None
    next_step_id: str | None
