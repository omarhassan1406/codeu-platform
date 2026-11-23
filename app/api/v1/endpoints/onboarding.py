from fastapi import APIRouter

from app.schemas.onboarding import SuggestionsRequest, SuggestionsResponse
from app.services import course_catalog
from app.services.suggestions import suggest_courses

router = APIRouter()


@router.post("/suggestions", response_model=SuggestionsResponse)
def onboarding_suggestions(request: SuggestionsRequest) -> SuggestionsResponse:
    """Suggest finished courses and new topics to generate for a learner profile."""
    return suggest_courses(
        request.profile,
        course_catalog.list_courses(),
        max_suggestions=request.max_suggestions,
    )
