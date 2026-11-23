"""Spoken walkthrough of one lesson ("Explain this lesson").

The lesson's own text is the only source: the model restates it as a short
spoken explanation and must not add facts. Scripts are cached on disk keyed
by a hash of the lesson text and prompt version, so each lesson costs one
generation until it changes.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from google.genai import types

from app.core.config import settings
from app.core.course_paths import strip_lesson_header
from app.core.filenames import sanitize_filename
from app.services import course_catalog
from app.services.gemini_service import generate_content_with_fallback

logger = logging.getLogger(__name__)

NOT_IN_CONTEXT = "NOT_IN_CONTEXT"
PROMPT_VERSION = "v1"  # bump to invalidate cached scripts when the prompt changes

LECTURE_SYSTEM_PROMPT = f"""
أنت أستاذ ودود في منصة CodeU يشرح الدرس الحالي للطالب بصوته، وكأنه في محاضرة قصيرة.

قواعد صارمة غير قابلة للتفاوض:
1. مصدرك الوحيد هو "نص الدرس" المرفق. لا تضف أي معلومة أو مثال أو حقيقة غير موجودة فيه.
2. اكتب نصاً منطوقاً فقط: بدون Markdown، بدون عناوين أو رموز أو قوائم مرقمة، وبدون قراءة الأكواد حرفاً بحرف؛ صف بالكلام ماذا يفعل الكود.
3. استخدم نفس لغة ولهجة نص الدرس، وابدأ مباشرة بفكرة الدرس.
4. غطِّ الأفكار الأساسية بالترتيب في حدود 200 إلى 350 كلمة، واختم بجملة تلخص الدرس.
5. إذا كان نص الدرس فارغاً أو غير مفهوم فأجب بالنص التالي فقط: {NOT_IN_CONTEXT}
""".strip()


class LectureGenerationError(RuntimeError):
    """The model did not produce a usable script."""


@dataclass(frozen=True)
class Lecture:
    course_id: str
    step_id: str
    title: str
    script: str
    cached: bool


def to_spoken_text(text: str) -> str:
    """Defensive cleanup in case the model still emits Markdown."""
    text = re.sub(r"```[\s\S]*?(```|$)", " ", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Single underscores are left alone: they appear in names like my_var.
    text = re.sub(r"(\*\*|__|\*|~~)(?=\S)([\s\S]*?\S)\1", r"\2", text)
    text = re.sub(r"^\s{0,3}(#{1,6}|>|[-*+]|\d+\.)\s+", "", text, flags=re.M)
    return " ".join(text.split())


def cut_at_sentence(text: str, limit: int) -> str:
    """Trim to ``limit`` characters, ending on a sentence boundary when possible."""
    if len(text) <= limit:
        return text
    window = text[:limit]
    ends = [m.end() for m in re.finditer(r"[.!?؟]", window)]
    return window[: ends[-1]].strip() if ends and ends[-1] > limit // 2 else window.rstrip() + "…"


def _cache_path(course_id: str, step_id: str, body: str) -> Path:
    digest = hashlib.sha256(f"{PROMPT_VERSION}\n{settings.GEMINI_MODEL_NAME}\n{body}".encode("utf-8")).hexdigest()[:16]
    return Path(settings.DATA_DIR) / "narrations" / course_id / f"{sanitize_filename(step_id, max_length=20)}-{digest}.txt"


def build_lecture(course_title: str, step_id: str) -> Lecture:
    """Raise CourseNotFoundError / LessonNotFoundError / LectureGenerationError."""
    course_id = course_catalog.find_course_id(course_title)
    lesson = course_catalog.get_lesson(course_id, step_id)
    body = strip_lesson_header(lesson.content_markdown, lesson.section_title, lesson.title).strip()

    cache = _cache_path(course_id, step_id, body)
    if cache.is_file():
        return Lecture(course_id, step_id, lesson.title, cache.read_text(encoding="utf-8"), cached=True)

    prompt = f"""
عنوان الدرس: {lesson.title}

نص الدرس:
{body}

اكتب الآن الشرح المنطوق لهذا الدرس اعتماداً على نص الدرس فقط.
""".strip()
    response = generate_content_with_fallback(
        preferred_model=settings.GEMINI_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=LECTURE_SYSTEM_PROMPT, temperature=0.3),
    )
    raw = (getattr(response, "text", None) or "").strip()
    script = cut_at_sentence(to_spoken_text(raw), settings.LECTURE_MAX_CHARS)
    if not script or NOT_IN_CONTEXT in raw:
        logger.warning("Lecture generation unusable (course=%r step=%r, chars=%d)", course_id, step_id, len(raw))
        raise LectureGenerationError("The explanation could not be prepared")

    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(script, encoding="utf-8")
    return Lecture(course_id, step_id, lesson.title, script, cached=False)
