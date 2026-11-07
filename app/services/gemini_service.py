import logging

from google.genai import types

from app.core.config import settings
from app.services.ai_clients import gemini_client

logger = logging.getLogger(__name__)


def is_rate_limit_error(error: Exception) -> bool:
    code = getattr(error, "code", None) or getattr(error, "status_code", None)
    if code == 429:
        return True
    if getattr(error, "status", None) == "RESOURCE_EXHAUSTED":
        return True
    if type(error).__name__ in {"ResourceExhausted", "TooManyRequests"}:
        return True
    message = str(error).lower()
    return "429" in message or "resource exhausted" in message or "rate limit" in message


def build_model_sequence(preferred_model: str | None = None) -> list[str]:
    sequence: list[str] = []
    if preferred_model:
        sequence.append(preferred_model)
    for model in settings.GEMINI_MODEL_HIERARCHY:
        if model not in sequence:
            sequence.append(model)
    return sequence


def generate_content_with_fallback(
    *,
    contents: str,
    config: types.GenerateContentConfig | None = None,
    preferred_model: str | None = None,
) -> types.GenerateContentResponse:
    models = build_model_sequence(preferred_model)
    if not models:
        raise RuntimeError("No Gemini models configured in GEMINI_MODEL_HIERARCHY")

    last_error: Exception | None = None
    for index, model in enumerate(models):
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
        except Exception as error:
            if not is_rate_limit_error(error):
                raise
            last_error = error
            logger.warning(
                "Gemini model %s exhausted (attempt %d/%d); switching to next model: %s",
                model,
                index + 1,
                len(models),
                error,
            )
            continue

        if index > 0:
            logger.info("Gemini generation recovered using fallback model %s", model)
        return response

    raise last_error if last_error else RuntimeError("Gemini generation failed")
