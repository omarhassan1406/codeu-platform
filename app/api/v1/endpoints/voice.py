from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.services import voice_service

router = APIRouter()

# Browsers record webm/ogg (Opus) or mp4; Safari may label webm as video/webm.
ALLOWED_PREFIXES = ("audio/", "video/webm", "video/mp4")


class TranscriptionResponse(BaseModel):
    text: str = Field(description="Empty when nothing intelligible was heard")
    language: str | None = None
    duration_seconds: float | None = None


class SpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=settings.TTS_MAX_CHARS)
    language: Literal["ar", "en"] | None = Field(None, description="Omit to detect from the text")

    @field_validator("text")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("text must not be blank")
        return value


# Plain def: the Groq call is blocking, so it runs in FastAPI's threadpool.
@router.post("/transcribe", response_model=TranscriptionResponse)
def transcribe(
    audio: UploadFile = File(..., description="Recorded question (webm/ogg/mp4/wav/mp3)"),
    language: Literal["ar", "en"] | None = Form(None),
) -> TranscriptionResponse:
    """Speech-to-text for a learner's spoken question (Groq Whisper)."""
    content_type = (audio.content_type or "").lower()
    if not content_type.startswith(ALLOWED_PREFIXES):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, "Upload an audio recording")
    data = audio.file.read(settings.STT_MAX_BYTES + 1)
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The recording is empty")
    if len(data) > settings.STT_MAX_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "The recording is too long")
    try:
        result = voice_service.transcribe(data, audio.filename or "question.webm", content_type, language=language)
    except voice_service.VoiceUnavailableError as error:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(error))
    return TranscriptionResponse(**result)


@router.post(
    "/speak",
    response_class=Response,
    responses={200: {"content": {"audio/mpeg": {}}, "description": "MP3 audio"}},
)
async def speak(request: SpeakRequest) -> Response:
    """Text-to-speech for the tutor's answer (edge-tts). Send plain text, not Markdown."""
    last_error: Exception | None = None
    for voice in voice_service.voice_chain(request.text, request.language):
        try:
            audio = await voice_service.synthesize(request.text, voice)
        except voice_service.VoiceUnavailableError as error:
            last_error = error
            continue
        return Response(content=audio, media_type="audio/mpeg", headers={"X-Voice": voice, "Cache-Control": "no-store"})
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(last_error))
