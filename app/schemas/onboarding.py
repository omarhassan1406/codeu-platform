"""Contract for learner onboarding and course suggestions.

The frontend collects a ``LearnerProfile`` during onboarding and posts it to
``POST /api/v1/onboarding/suggestions``. The response mixes:

- ``existing`` suggestions: finished courses from the catalog (open them with
  ``GET /api/v1/courses/{course_id}``), and
- ``generate`` suggestions: topics not covered yet (start them with
  ``POST /api/v1/courses/generate`` using ``generation_topic``).

Profiles are not stored yet (no user database); the endpoint is stateless.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator

Level = Literal["beginner", "intermediate", "advanced"]


class LearnerProfile(BaseModel):
    background: str = Field(
        "",
        max_length=1000,
        description="Free text, e.g. 'high-school student', 'CS undergrad', 'accountant'",
    )
    interests: list[str] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Subjects or skills, any domain: 'Python', 'Calculus', 'Organic chemistry'",
    )
    level: Level = Field(..., description="Self-assessed level in these interests")
    goals: str = Field("", max_length=1000, description="What the learner wants to achieve")
    preferred_language: str = Field(
        "ar", min_length=2, max_length=10, description="Lesson language code, e.g. 'ar' or 'en'"
    )

    @field_validator("interests")
    @classmethod
    def clean_interests(cls, values: list[str]) -> list[str]:
        cleaned: list[str] = []
        for value in values:
            value = " ".join(value.split())
            if not 2 <= len(value) <= 100:
                raise ValueError("each interest must be 2-100 characters")
            if value.lower() not in {v.lower() for v in cleaned}:
                cleaned.append(value)
        return cleaned


class SuggestionsRequest(BaseModel):
    profile: LearnerProfile
    max_suggestions: int = Field(5, ge=1, le=20)


class CourseSuggestion(BaseModel):
    kind: Literal["existing", "generate"]
    title: str
    reason: str
    match_score: float = Field(..., ge=0.0, le=1.0)
    course_id: str | None = Field(None, description="Set when kind == 'existing'")
    generation_topic: str | None = Field(
        None, description="Set when kind == 'generate'; send as course_topic to /courses/generate"
    )


class SuggestionsResponse(BaseModel):
    suggestions: list[CourseSuggestion]
    strategy: str = Field(description="Which matching strategy produced the list")
