"""Learner profile, lesson progress and quota ("me" = the X-Learner-Id caller)."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_learner_id
from app.schemas.learners import CourseProgress, QuotaStatus
from app.schemas.onboarding import LearnerProfile
from app.services import course_catalog, quota
from app.services.learner_store import LearnerRepository, get_learner_repository

router = APIRouter()


def _course_steps(course_id: str) -> list[str]:
    try:
        course = course_catalog.get_course(course_id)
    except course_catalog.CourseNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Course not found")
    return [step.step_id for section in course.sections for step in section.steps]


def _progress(repo: LearnerRepository, learner_id: str, course_id: str) -> CourseProgress:
    steps = _course_steps(course_id)
    known = set(steps)
    # Ignore records for steps the course no longer has (e.g. regenerated).
    done = [s for s in repo.completed_steps(learner_id, course_id) if s in known]
    percent = int(len(done) * 100 / len(steps)) if steps else 0
    return CourseProgress(course_id=course_id, completed_steps=done, total_lessons=len(steps), percent=percent)


def _check_step(course_id: str, step_id: str) -> None:
    if step_id not in _course_steps(course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lesson not found")


@router.get("/me/profile", response_model=LearnerProfile)
def get_profile(
    learner_id: str = Depends(require_learner_id), repo: LearnerRepository = Depends(get_learner_repository)
) -> LearnerProfile:
    profile = repo.get_profile(learner_id)
    if profile is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No profile saved yet")
    return LearnerProfile.model_validate(profile)


@router.put("/me/profile", response_model=LearnerProfile)
def save_profile(
    profile: LearnerProfile,
    learner_id: str = Depends(require_learner_id),
    repo: LearnerRepository = Depends(get_learner_repository),
) -> LearnerProfile:
    repo.save_profile(learner_id, profile.model_dump())
    return profile


@router.get("/me/progress", response_model=list[CourseProgress])
def list_progress(
    learner_id: str = Depends(require_learner_id), repo: LearnerRepository = Depends(get_learner_repository)
) -> list[CourseProgress]:
    result = []
    for course_id in repo.all_completed(learner_id):
        try:
            result.append(_progress(repo, learner_id, course_id))
        except HTTPException:
            continue  # course was removed
    return result


@router.get("/me/progress/{course_id}", response_model=CourseProgress)
def course_progress(
    course_id: str,
    learner_id: str = Depends(require_learner_id),
    repo: LearnerRepository = Depends(get_learner_repository),
) -> CourseProgress:
    return _progress(repo, learner_id, course_id)


@router.post("/me/progress/{course_id}/lessons/{step_id}/complete", response_model=CourseProgress)
def complete_lesson(
    course_id: str,
    step_id: str,
    learner_id: str = Depends(require_learner_id),
    repo: LearnerRepository = Depends(get_learner_repository),
) -> CourseProgress:
    _check_step(course_id, step_id)
    repo.mark_lesson_complete(learner_id, course_id, step_id)
    return _progress(repo, learner_id, course_id)


@router.delete("/me/progress/{course_id}/lessons/{step_id}/complete", response_model=CourseProgress)
def uncomplete_lesson(
    course_id: str,
    step_id: str,
    learner_id: str = Depends(require_learner_id),
    repo: LearnerRepository = Depends(get_learner_repository),
) -> CourseProgress:
    _check_step(course_id, step_id)
    repo.mark_lesson_incomplete(learner_id, course_id, step_id)
    return _progress(repo, learner_id, course_id)


@router.get("/me/quota", response_model=QuotaStatus)
def get_quota(
    learner_id: str = Depends(require_learner_id), repo: LearnerRepository = Depends(get_learner_repository)
) -> QuotaStatus:
    return quota.quota_status(repo, learner_id)
