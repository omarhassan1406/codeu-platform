"""Speech-to-text (Groq Whisper) and text-to-speech (edge-tts).

Both are hosted services, so the server needs no audio models, GPU or extra
RAM. Upstream error details are logged, never returned to learners.
"""

import logging
import re

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

STT_TIMEOUT_SECONDS = 30

# Patched in tests; keeps the HTTP call in one place.
http_post = httpx.post

_ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿ]")
_LATIN = re.compile(r"[A-Za-z]")


# Whisper invents these on silence or noise (live: 3s of silence -> "Thank
# you.", room noise -> "so"). Groq's no_speech_prob stays 0 for them, so they
# are matched by text. Compared lowercased with punctuation removed.
SILENCE_HALLUCINATIONS = {
    "thank you",
    "thanks",
    "thank you for watching",
    "thanks for watching",
    "so",
    "you",
    "bye",
    "okay",
    "subtitles by the amaraorg community",
    "ترجمة نانسي قنقر",
    "اشتركوا في القناة",
    "شكرا للمشاهدة",
    "شكرا",
}
# Mean segment avg_logprob below this means Whisper was guessing
# (live: clear speech -0.18, noise read as "so" -0.77).
MIN_AVG_LOGPROB = -0.65
SUPPORTED_LANGUAGES = {"arabic", "english", "ar", "en"}


def _normalize(text: str) -> str:
    return " ".join("".join(ch for ch in text.lower() if ch.isalnum() or ch.isspace()).split())


def _rejection_reason(text: str, language: str | None, segments: list[dict]) -> str | None:
    """Why a transcript should not be treated as a question, or None if it is fine."""
    normalized = _normalize(text)
    if not normalized or not any(ch.isalpha() for ch in normalized) or normalized in SILENCE_HALLUCINATIONS:
        return "no_speech"
    if language and language.lower() not in SUPPORTED_LANGUAGES:
        return "unsupported_language"
    logprobs = [s["avg_logprob"] for s in segments if isinstance(s.get("avg_logprob"), (int, float))]
    if logprobs and sum(logprobs) / len(logprobs) < MIN_AVG_LOGPROB:
        return "low_confidence"
    return None


class VoiceUnavailableError(RuntimeError):
    """The voice service cannot be used right now. The message is learner-safe."""


class VoiceInputError(ValueError):
    """The recording itself could not be used. The message is learner-safe."""


# Groq picks the decoder from the file extension and rejects names without one
# ("blob", "q"), so the server names uploads from their content type.
_EXTENSIONS = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/opus": "opus",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/x-m4a": "m4a",
    "audio/m4a": "m4a",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/flac": "flac",
    "audio/x-flac": "flac",
}
_GROQ_EXTENSIONS = {"flac", "mp3", "mp4", "mpeg", "mpga", "m4a", "ogg", "opus", "wav", "webm"}


def upload_filename(content_type: str, client_filename: str | None) -> str | None:
    """A filename Groq accepts, or None when the audio format is unknown."""
    base_type = (content_type or "").split(";")[0].strip().lower()
    ext = _EXTENSIONS.get(base_type)
    if not ext and client_filename and "." in client_filename:
        candidate = client_filename.rsplit(".", 1)[1].lower()
        ext = candidate if candidate in _GROQ_EXTENSIONS else None
    return f"question.{ext}" if ext else None


def pick_voice(text: str, language: str | None = None) -> str:
    """Arabic voice for mostly-Arabic text (English terms inside are fine)."""
    if language == "ar":
        return settings.TTS_VOICE_AR
    if language == "en":
        return settings.TTS_VOICE_EN
    arabic, latin = len(_ARABIC.findall(text)), len(_LATIN.findall(text))
    return settings.TTS_VOICE_AR if arabic and arabic >= latin * 0.5 else settings.TTS_VOICE_EN


def voice_chain(text: str, language: str | None = None) -> list[str]:
    """Voices to try in order: the language's primary voice, then its fallback."""
    if pick_voice(text, language) == settings.TTS_VOICE_AR:
        return [settings.TTS_VOICE_AR, settings.TTS_VOICE_AR_FALLBACK]
    return [settings.TTS_VOICE_EN, settings.TTS_VOICE_EN_FALLBACK]


def transcribe(audio: bytes, filename: str, content_type: str, language: str | None = None) -> dict:
    """Send a recording to Groq Whisper and return its text."""
    if not settings.GROQ_API_KEY:
        raise VoiceUnavailableError("Speech recognition is not configured on the server")

    data = {"model": settings.GROQ_STT_MODEL, "response_format": "verbose_json", "temperature": "0"}
    if language:
        data["language"] = language
    try:
        response = http_post(
            f"{settings.GROQ_API_BASE}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.GROQ_API_KEY}"},
            data=data,
            files={"file": (filename, audio, content_type)},
            timeout=STT_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning("Groq transcription request failed", exc_info=True)
        raise VoiceUnavailableError("Speech recognition is unavailable right now")

    if response.status_code != 200:
        error_code = None
        try:
            error_code = (response.json().get("error") or {}).get("code")
        except Exception:
            pass
        logger.warning("Groq transcription returned HTTP %s (%s)", response.status_code, error_code)
        if response.status_code == 400:
            raise VoiceInputError("We couldn't read that recording. Please record your question again.")
        if response.status_code == 429:
            raise VoiceUnavailableError("Speech recognition is busy. Try again in a moment")
        raise VoiceUnavailableError("Speech recognition is unavailable right now")

    payload = response.json()
    text = (payload.get("text") or "").strip()
    language = payload.get("language")
    rejected = _rejection_reason(text, language, payload.get("segments") or [])
    if rejected:
        logger.info("Transcript rejected (%s, language=%s, chars=%d)", rejected, language, len(text))
    return {
        "text": "" if rejected else text,
        "language": language,
        "duration_seconds": payload.get("duration"),
        "rejected": rejected,
    }


async def synthesize(text: str, voice: str) -> bytes:
    """Render ``text`` to MP3 with an edge-tts voice."""
    try:
        import edge_tts

        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
    except Exception:
        logger.warning("edge-tts synthesis failed (voice=%s)", voice, exc_info=True)
        raise VoiceUnavailableError("Voice playback is unavailable right now")
    if not audio:
        logger.warning("edge-tts returned no audio (voice=%s)", voice)
        raise VoiceUnavailableError("Voice playback is unavailable right now")
    return bytes(audio)
