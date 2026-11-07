from fastapi import APIRouter
from app.api.v1.endpoints import courses, tutor

api_router = APIRouter()
api_router.include_router(courses.router, prefix="/courses", tags=["Courses Engine"])
api_router.include_router(tutor.router, prefix="/tutor", tags=["AI Tutor & Raise Hand"])