"""Course suggestions for a learner profile.

Baseline strategy ("keyword-v1"): match each interest's words against each
finished course's title, audience and section titles. Interests that no
course covers well become "generate" suggestions. It is deterministic and
needs no model calls; a smarter (embedding or LLM) ranker can replace
``suggest_courses`` later without changing the API contract.
"""

import re

from app.schemas.courses import CourseSummary
from app.schemas.onboarding import CourseSuggestion, LearnerProfile, SuggestionsResponse

STRATEGY = "keyword-v1"
# An interest whose best course match is below this gets a "generate" suggestion.
COVERED_THRESHOLD = 0.5

_STOPWORDS = {
    "and", "the", "for", "with", "from", "into", "to", "of", "in", "on", "a", "an",
    "beginners", "beginner", "advanced", "intermediate", "course", "introduction", "intro",
}
_LEVEL_LABEL = {"beginner": "Beginners", "intermediate": "Intermediate learners", "advanced": "Advanced learners"}


def _tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"\w+", text.lower()) if len(t) > 1 and t not in _STOPWORDS}


def _course_tokens(course: CourseSummary) -> set[str]:
    return _tokens(" ".join([course.title, course.target_audience, *course.section_titles]))


def _match(interest: str, course_tokens: set[str]) -> float:
    wanted = _tokens(interest)
    if not wanted:
        return 0.0
    return len(wanted & course_tokens) / len(wanted)


def suggest_courses(
    profile: LearnerProfile, courses: list[CourseSummary], max_suggestions: int = 5
) -> SuggestionsResponse:
    finished = [course for course in courses if course.status == "complete"]
    tokens = {course.course_id: _course_tokens(course) for course in finished}

    existing: dict[str, CourseSuggestion] = {}
    uncovered: list[str] = []
    for interest in profile.interests:
        best = 0.0
        for course in finished:
            score = _match(interest, tokens[course.course_id])
            best = max(best, score)
            if score <= 0:
                continue
            previous = existing.get(course.course_id)
            if previous is None or score > previous.match_score:
                existing[course.course_id] = CourseSuggestion(
                    kind="existing",
                    title=course.title,
                    course_id=course.course_id,
                    match_score=round(score, 3),
                    reason=f"Matches your interest in {interest}",
                )
        if best < COVERED_THRESHOLD:
            uncovered.append(interest)

    ranked = sorted(existing.values(), key=lambda s: (-s.match_score, s.title))
    to_generate = [
        CourseSuggestion(
            kind="generate",
            title=f"{interest} for {_LEVEL_LABEL[profile.level]}",
            generation_topic=f"{interest} for {_LEVEL_LABEL[profile.level]}",
            match_score=1.0,
            reason=f"No existing course covers {interest} yet; we can generate one for you",
        )
        for interest in uncovered
    ]

    # Interleave so both kinds stay visible when the list is capped.
    merged: list[CourseSuggestion] = []
    for pair in zip(ranked, to_generate):
        merged.extend(pair)
    longer = ranked if len(ranked) > len(to_generate) else to_generate
    merged.extend(longer[min(len(ranked), len(to_generate)):])
    return SuggestionsResponse(suggestions=merged[:max_suggestions], strategy=STRATEGY)
