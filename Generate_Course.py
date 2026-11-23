import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Callable, List, TypeVar

from google.genai import types
from pydantic import BaseModel, Field, ValidationError
from qdrant_client.http import models as rest

from app.core.config import settings
from app.core.console import configure_console
from app.core.course_paths import MANIFEST_FILENAME, ROADMAP_FILENAME, course_dir, lesson_filename
from app.services.ai_clients import get_embedding_model, get_qdrant_client
from app.services.chunking import WordChunker, get_chunker
from app.services.gemini_service import generate_content_with_fallback

configure_console()
logger = logging.getLogger(__name__)

# ==========================================
# 1. الإعدادات والتهيئة (Configuration)
# ==========================================

COLLECTION_NAME = settings.COLLECTION_NAME

# مجلد الكورسات المولدة (قابل للتغيير عبر GENERATED_COURSES_DIR)
OUTPUT_DIR = str(settings.GENERATED_COURSES_DIR)

# Fixed namespace so the same (course, step, chunk) always maps to the same Qdrant point id.
QDRANT_POINT_NAMESPACE = uuid.UUID("6f1c2a4e-8d3b-5e7f-9a0b-1c2d3e4f5a6b")


class GenerationIncompleteError(RuntimeError):
    """Generated content failed completeness checks after all retries."""


class IngestionError(RuntimeError):
    """Lesson chunks could not be stored in Qdrant."""


def ensure_collection() -> None:
    """Create the Qdrant collection if needed. Fails fast if Qdrant is unreachable,
    before any generation tokens are spent."""
    client = get_qdrant_client()
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=rest.VectorParams(size=1024, distance=rest.Distance.COSINE),
        )


# ==========================================
# 2. تعريف هيكل الكورس (Pydantic Schema)
# ==========================================
class Step(BaseModel):
    step_id: str = Field(description="رقم الخطوة مثل 1.1, 1.2")
    step_title: str = Field(description="عنوان الدرس أو الخطوة")
    duration_mins: int = Field(description="الوقت المتوقع بالدقائق")
    learning_objectives: List[str] = Field(description="الأهداف التعليمية للدرس")

class Section(BaseModel):
    section_id: int
    section_title: str
    description: str
    steps: List[Step]

class CourseRoadmap(BaseModel):
    course_title: str
    target_audience: str
    sections: List[Section]


# ==========================================
# 3. فحص اكتمال المحتوى (Completeness checks)
# ==========================================
def validate_roadmap(roadmap: CourseRoadmap, min_steps_per_section: int | None = None) -> list[str]:
    """Return a list of problems; an empty list means the roadmap is complete."""
    if min_steps_per_section is None:
        min_steps_per_section = settings.ROADMAP_MIN_STEPS_PER_SECTION

    problems: list[str] = []
    if not roadmap.course_title.strip():
        problems.append("course_title is empty")
    if not roadmap.sections:
        problems.append("roadmap has no sections")

    seen_sections: set[int] = set()
    seen_steps: set[str] = set()
    for section in roadmap.sections:
        label = f"section {section.section_id}"
        if section.section_id in seen_sections:
            problems.append(f"{label}: duplicate section_id")
        seen_sections.add(section.section_id)
        if not section.section_title.strip():
            problems.append(f"{label}: empty section_title")
        if len(section.steps) < min_steps_per_section:
            problems.append(
                f"{label}: has {len(section.steps)} steps, needs at least {min_steps_per_section}"
            )
        for step in section.steps:
            step_label = f"step {step.step_id or '?'}"
            if not step.step_id.strip():
                problems.append(f"{label}: step with empty step_id")
            elif step.step_id in seen_steps:
                problems.append(f"{step_label}: duplicate step_id")
            seen_steps.add(step.step_id)
            if not step.step_title.strip():
                problems.append(f"{step_label}: empty step_title")
            if step.duration_mins <= 0:
                problems.append(f"{step_label}: duration_mins must be positive")
            if not [obj for obj in step.learning_objectives if obj.strip()]:
                problems.append(f"{step_label}: no learning_objectives")
    return problems


def _finish_reason_name(response) -> str | None:
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return None
    reason = getattr(candidates[0], "finish_reason", None)
    if reason is None:
        return None
    return getattr(reason, "name", str(reason))


def validate_lesson(text: str | None, finish_reason: str | None = None, min_chars: int | None = None) -> list[str]:
    """Return a list of problems; an empty list means the lesson looks complete."""
    if min_chars is None:
        min_chars = settings.LESSON_MIN_CHARS

    problems: list[str] = []
    content = (text or "").strip()
    if not content:
        return ["lesson content is empty"]
    if finish_reason and finish_reason != "STOP":
        problems.append(f"generation stopped early (finish_reason={finish_reason})")
    if len(content) < min_chars:
        problems.append(f"lesson is too short ({len(content)} chars, needs at least {min_chars})")
    if content.count("```") % 2 != 0:
        problems.append("lesson has an unclosed code block (likely truncated)")
    return problems


T = TypeVar("T")


def _generate_until_complete(label: str, attempt_fn: Callable[[], tuple[T, list[str]]]) -> T:
    """Call ``attempt_fn`` until it returns no problems, up to GENERATION_MAX_ATTEMPTS."""
    max_attempts = max(1, settings.GENERATION_MAX_ATTEMPTS)
    problems: list[str] = []
    for attempt in range(1, max_attempts + 1):
        result, problems = attempt_fn()
        if not problems:
            return result
        logger.warning(
            "%s incomplete (attempt %d/%d): %s", label, attempt, max_attempts, "; ".join(problems)
        )
    raise GenerationIncompleteError(
        f"{label} still incomplete after {max_attempts} attempts: {'; '.join(problems)}"
    )


# ==========================================
# 4. وظائف التوليد (Generation Functions)
# ==========================================
def generate_course_roadmap(course_topic: str) -> CourseRoadmap:
    print(f"\n🚀 [1/3] جاري توليد الهيكل الشامل والمفصل لكورس: {course_topic} باستخدام {settings.GEMINI_COURSE_MODEL}...")

    min_steps = settings.ROADMAP_MIN_STEPS_PER_SECTION
    prompt = f"""
    أنت مهندس مناهج تعليمية خبير في منصة CodeU.
    قم بتصميم منهج تعليمي احترافي وعميق جداً من الصفر وحتى الاحتراف لموضوع: '{course_topic}'.

    شروط صارمة لتصميم المنهج:
    1. قسّم الكورس إلى أقسام منطقية (Sections) تغطي الموضوع باحترافية.
    2. **يجب** ألا يقل عدد الخطوات (Steps) في كل قسم عن **{min_steps} خطوات** تفصيلية ومترابطة.
    3. يجب أن تكون الخطوات **متسلسلة وتكمل بعضها البعض تماماً** (كل خطوة تبني على مفاهيم الخطوة التي تسبقها مباشرة لضمان رحلة تعلم سلسة للطالب).
    4. لكل خطوة: رقم فريد (مثل 1.1)، عنوان واضح، مدة بالدقائق أكبر من صفر، وهدف تعليمي واحد على الأقل.
    """

    def attempt() -> tuple[CourseRoadmap | None, list[str]]:
        response = generate_content_with_fallback(
            preferred_model=settings.GEMINI_COURSE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=CourseRoadmap,
                temperature=0.3,  # تقليل الـ temperature ليكون التوليد أكثر انضباطاً ومنطقية
            ),
        )
        try:
            roadmap = CourseRoadmap.model_validate_json(response.text or "")
        except ValidationError as error:
            return None, [f"roadmap JSON is invalid or truncated: {error.error_count()} errors"]
        return roadmap, validate_roadmap(roadmap, min_steps)

    return _generate_until_complete(f"Roadmap for {course_topic!r}", attempt)


def generate_step_content(course_title: str, section_title: str, step: Step, prev_step_title: str = None) -> str:
    print(f"   📖 كتابة محتوى الدرس [{step.step_id}]: {step.step_title}...")

    # تحديد السياق بناءً على الخطوة السابقة لضمان التسلسل
    context_note = f"ملاحظة هامة: هذا الدرس يكمل مباشرة ما تم شرحه في الخطوة السابقة ({prev_step_title}). اربط الأفكار بسلاسة ولا تبدأ كأنها معلومات معزولة." if prev_step_title else "هذه هي الخطوة الأولى في القسم، ابدأ بمقدمة تمهيدية مشوقة."

    prompt = f"""
    أنت أستاذ برمجيات خبير، ودود، وتفاعلي جداً في منصة CodeU.
    لا تقتصر أبداً على سرد المعلومات أو الرموز بشكل جاف (مثل رص الـ Operators أو العناصر دون شرح)، بل اشرح كل مفهوم كأنك تتحدث مع طالبك وجهاً لوجه (وضح الغرض منها، كيف تعمل تحت الغطاء، ولماذا ومتى نستخدمها في المشاريع الحقيقية).

    بيانات الدرس:
    - الكورس: {course_title}
    - القسم: {section_title}
    - الدرس الحالي: [{step.step_id}] {step.step_title}
    - السياق: {context_note}
    - الأهداف التعليمية: {', '.join(step.learning_objectives)}

    اكتب المحتوى بصيغة Markdown احترافية وغنية تشمل:
    1. **مقدمة حوارية وتفاعلية** تربط الدرس بما تم تعلمه في الخطوة السابقة لتسلسل الأفكار.
    2. **شرح عميق ومفصل** لكل مفهوم (تجنب السرد المختصر، واشرح التفاصيل الفنية بأسلوب مبسط).
    3. **أمثلة أكواد برمجية نظيفة** مع شرح سطر بسطر لما يحدث في الكود.
    4. **أخطاء شائعة وتحذيرات** يقع فيها المطورون عادة وكيفية تفاديها.
    5. **خلاصة أو تمرين عملي سريع** يمهد للخطوة القادمة.

    يجب أن تغطي جميع الأهداف التعليمية المذكورة، وأن تُكمل الدرس حتى نهايته (أغلق كل كتلة كود تفتحها).
    """

    def attempt() -> tuple[str, list[str]]:
        response = generate_content_with_fallback(
            preferred_model=settings.GEMINI_COURSE_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.4),
        )
        text = (response.text or "").strip()
        return text, validate_lesson(text, _finish_reason_name(response))

    return _generate_until_complete(f"Lesson {step.step_id} ({step.step_title!r})", attempt)


# ==========================================
# 5. وظيفة الرفع لـ Qdrant مع إعادة المحاولة
# ==========================================
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    """Legacy word-window chunking, kept for backwards compatibility.
    Ingestion uses ``get_chunker()`` (settings.CHUNK_STRATEGY) instead."""
    return WordChunker(chunk_size, overlap).split(text)


def make_point_id(course_title: str, step_id: str, chunk_index: int) -> str:
    """Deterministic Qdrant point id: re-ingesting a lesson overwrites its chunks."""
    return str(uuid.uuid5(QDRANT_POINT_NAMESPACE, f"{course_title}|{step_id}|{chunk_index}"))


def _lesson_filter(course_title: str, step_id: str) -> rest.Filter:
    return rest.Filter(
        must=[
            rest.FieldCondition(key="course_title", match=rest.MatchValue(value=course_title)),
            rest.FieldCondition(key="step_id", match=rest.MatchValue(value=step_id)),
        ]
    )


def ingest_lesson_to_qdrant_with_retry(course_title: str, section_title: str, step_id: str, step_title: str, content: str):
    print(f"   🧠 [RAG] جاري تقطيع ورفع محتوى الدرس {step_id} إلى Qdrant Cloud...")
    chunker = get_chunker()
    chunks = chunker.split(content)
    embedding_model = get_embedding_model()
    qdrant_client = get_qdrant_client()

    points = []
    for idx, chunk in enumerate(chunks):
        vector = embedding_model.encode(chunk).tolist()
        points.append(
            rest.PointStruct(
                id=make_point_id(course_title, step_id, idx),
                vector=vector,
                payload={
                    "course_title": course_title,
                    "section_title": section_title,
                    "step_id": step_id,
                    "step_title": step_title,
                    "chunk_index": idx,
                    "chunk_strategy": chunker.name,
                    "text": chunk
                }
            )
        )

    # محاولة الرفع مع إعادة المحاولة في حال حدوث Timeout
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # Remove this lesson's old chunks first so a shorter regenerated
            # lesson leaves no stale chunks behind for the tutor to retrieve.
            qdrant_client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=rest.FilterSelector(filter=_lesson_filter(course_title, step_id)),
            )
            qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"   ✅ تم تخزين {len(points)} قطعة سياقية للدرس في قاعدة البيانات بنجاح.")
            return
        except Exception as e:
            print(f"   ⚠️ محاولة الاتصال بـ Qdrant فشلت ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(3) # الانتظار 3 ثوانٍ قبل إعادة المحاولة
            else:
                raise IngestionError(
                    f"Could not store lesson {step_id} of {course_title!r} in Qdrant"
                ) from e


# ==========================================
# 6. الـ Pipeline الرئيسي المتكامل
# ==========================================
def _write_json(path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def run_codeu_complete_pipeline(
    course_topic: str,
    output_dir: str = OUTPUT_DIR,
    on_progress: Callable[[dict], None] | None = None,
):
    """Generate, save and ingest a full course.

    ``on_progress`` (optional) receives a copy of the manifest plus ``course_id``
    every time the manifest is saved, so callers can track progress.
    """
    ensure_collection()

    # الخطوة 1: توليد الهيكل (مع فحص الاكتمال)
    roadmap = generate_course_roadmap(course_topic)
    print(f"✨ تم إنشاء الهيكل: {roadmap.course_title} (يحتوي على {len(roadmap.sections)} أقسام)\n")

    # كل كورس في مجلد خاص به حتى لا تتداخل الملفات بين الكورسات
    target_dir = course_dir(output_dir, roadmap.course_title)
    target_dir.mkdir(parents=True, exist_ok=True)
    with open(target_dir / ROADMAP_FILENAME, "w", encoding="utf-8") as f:
        f.write(roadmap.model_dump_json(indent=2))

    total_steps = sum(len(sec.steps) for sec in roadmap.sections)
    manifest = {
        "course_title": roadmap.course_title,
        "course_topic": course_topic,
        "status": "in_progress",
        "total_steps": total_steps,
        "completed_steps": [],
        "error": None,
        "updated_at": None,
    }

    def save_manifest() -> None:
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        _write_json(target_dir / MANIFEST_FILENAME, manifest)
        if on_progress is not None:
            update = {**manifest, "completed_steps": list(manifest["completed_steps"])}
            update["course_id"] = target_dir.name
            try:
                on_progress(update)
            except Exception:
                logging.getLogger(__name__).exception("Progress callback failed")

    save_manifest()
    current = 0
    prev_step_title = None

    print(f"⏳ بدء توليد ومعالجة محتوى {total_steps} درس تفصيلي متسلسل...\n")

    try:
        for section in roadmap.sections:
            print(f"\n📂 [القسم]: {section.section_title}")

            for step in section.steps:
                current += 1
                print(f"\n--- [التقدم: {current}/{total_steps}] ---")

                lesson_markdown = generate_step_content(
                    course_title=roadmap.course_title,
                    section_title=section.section_title,
                    step=step,
                    prev_step_title=prev_step_title,
                )
                prev_step_title = step.step_title

                # 1. حفظ الدرس محلياً بصيغة Markdown
                md_filename = lesson_filename(step.step_id, step.step_title)
                with open(target_dir / md_filename, "w", encoding="utf-8") as md_file:
                    md_file.write(f"# {section.section_title}\n## {step.step_title}\n\n{lesson_markdown}")
                print(f"   💾 تم حفظ السكريبت محلياً في: {target_dir.name}/{md_filename}")

                # 2. رفع المحتوى إلى Qdrant Cloud للـ RAG
                ingest_lesson_to_qdrant_with_retry(
                    course_title=roadmap.course_title,
                    section_title=section.section_title,
                    step_id=step.step_id,
                    step_title=step.step_title,
                    content=lesson_markdown,
                )

                manifest["completed_steps"].append(step.step_id)
                save_manifest()
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error"] = f"{type(error).__name__}: {error}"
        save_manifest()
        raise

    manifest["status"] = "complete"
    save_manifest()
    print(f"\n🎉 مبروك! انتهى بناء الكورس بالكامل بتسلسل احترافي ومحفوظ محلياً ومرفوع للـ RAG!")
    return roadmap


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    TOPIC = "Programming in Python for Beginners to Advanced"
    run_codeu_complete_pipeline(course_topic=TOPIC)
