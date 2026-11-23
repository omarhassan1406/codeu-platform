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


class VoiceUnavailableError(RuntimeError):
    """The voice service cannot be used right now. The message is learner-safe."""


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
        logger.warning("Groq transcription returned HTTP %s", response.status_code)
        if response.status_code == 429:
            raise VoiceUnavailableError("Speech recognition is busy. Try again in a moment")
        raise VoiceUnavailableError("Speech recognition is unavailable right now")

    payload = response.json()
    return {
        "text": (payload.get("text") or "").strip(),
        "language": payload.get("language"),
        "duration_seconds": payload.get("duration"),
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
