"""Contracts for learner progress and quota endpoints."""

from pydantic import BaseModel, Field


class CourseProgress(BaseModel):
    course_id: str
    completed_steps: list[str]
    total_lessons: int
    percent: int = Field(ge=0, le=100, description="Completed lessons as a whole-number percentage")


class QuotaStatus(BaseModel):
    limit: int | None = Field(description="Questions allowed per UTC day; null means unlimited")
    used: int
    remaining: int | None
    resets_at: str = Field(description="Next UTC midnight, ISO 8601")
