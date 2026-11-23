from fastapi import APIRouter
from app.api.v1.endpoints import courses, learners, onboarding, tutor, voice

api_router = APIRouter()
api_router.include_router(courses.router, prefix="/courses", tags=["Courses Engine"])
api_router.include_router(tutor.router, prefix="/tutor", tags=["AI Tutor & Raise Hand"])
api_router.include_router(onboarding.router, prefix="/onboarding", tags=["Onboarding"])
api_router.include_router(voice.router, prefix="/voice", tags=["Voice"])
api_router.include_router(learners.router, prefix="/learners", tags=["Learners"])
