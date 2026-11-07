
import os
import time
from typing import List

from google.genai import types
from pydantic import BaseModel, Field
from qdrant_client.http import models as rest

from app.core.config import settings
from app.core.console import configure_console
from app.core.filenames import sanitize_filename
from app.services.ai_clients import embedding_model, qdrant_client
from app.services.gemini_service import generate_content_with_fallback

configure_console()

# ==========================================
# 1. الإعدادات والتهيئة (Configuration)
# ==========================================

COLLECTION_NAME = settings.COLLECTION_NAME

# تحديد مسار مجلد المشروع تلقائياً بناءً على مكان وجود السكريبت
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "generated_courses")
os.makedirs(OUTPUT_DIR, exist_ok=True)


def ensure_collection() -> None:
    try:
        if not qdrant_client.collection_exists(COLLECTION_NAME):
            qdrant_client.create_collection(
                collection_name=COLLECTION_NAME,
                vectors_config=rest.VectorParams(size=1024, distance=rest.Distance.COSINE)
            )
    except Exception as e:
        print(f"⚠️ تنبيه بخصوص الاتصال بـ Qdrant (سيتم المتابعة والحفظ المحلي): {e}")


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
# 3. وظائف التوليد (Generation Functions)
# ==========================================
def generate_course_roadmap(course_topic: str) -> CourseRoadmap:
    print(f"\n🚀 [1/3] جاري توليد الهيكل الشامل والمفصل لكورس: {course_topic} باستخدام {settings.GEMINI_COURSE_MODEL}...")
    
    prompt = f"""
    أنت مهندس مناهج تعليمية خبير في منصة CodeU.
    قم بتصميم منهج تعليمي احترافي وعميق جداً من الصفر وحتى الاحتراف لموضوع: '{course_topic}'.
    
    شروط صارمة لتصميم المنهج:
    1. قسّم الكورس إلى أقسام منطقية (Sections) تغطي الموضوع باحترافية.
    2. **يجب** ألا يقل عدد الخطوات (Steps) في كل قسم عن **4 إلى 6 خطوات** تفصيلية ومترابطة (وليست خطوتين فقط).
    3. يجب أن تكون الخطوات **متسلسلة وتكمل بعضها البعض تماماً** (كل خطوة تبني على مفاهيم الخطوة التي تسبقها مباشرة لضمان رحلة تعلم سلسة للطالب).
    """
    
    response = generate_content_with_fallback(
        preferred_model=settings.GEMINI_COURSE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CourseRoadmap,
            temperature=0.3, # تقليل الـ temperature ليكون التوليد أكثر انضباطاً ومنطقية
        ),
    )
    return CourseRoadmap.model_validate_json(response.text)


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
    """

    response = generate_content_with_fallback(
        preferred_model=settings.GEMINI_COURSE_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.4),
    )
    return response.text


# ==========================================
# 4. وظيفة الرفع لـ Qdrant مع إعادة المحاولة
# ==========================================
def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words), chunk_size - overlap):
        chunk = " ".join(words[i:i + chunk_size])
        chunks.append(chunk)
    return chunks

def ingest_lesson_to_qdrant_with_retry(course_title: str, section_title: str, step_id: str, step_title: str, content: str):
    print(f"   🧠 [RAG] جاري تقطيع ورفع محتوى الدرس {step_id} إلى Qdrant Cloud...")
    chunks = chunk_text(content)
    
    points = []
    for idx, chunk in enumerate(chunks):
        vector = embedding_model.encode(chunk).tolist()
        point_id = abs(hash(f"{course_title}_{section_title}_{step_id}_{idx}")) % (2**63)
        points.append(
            rest.PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "course_title": course_title,
                    "section_title": section_title,
                    "step_id": step_id,
                    "step_title": step_title,
                    "chunk_index": idx,
                    "text": chunk
                }
            )
        )
    
    # محاولة الرفع مع إعادة المحاولة في حال حدوث Timeout
    max_retries = 3
    for attempt in range(max_retries):
        try:
            qdrant_client.upsert(collection_name=COLLECTION_NAME, points=points)
            print(f"   ✅ تم تخزين {len(points)} قطعة سياقية للدرس في قاعدة البيانات بنجاح.")
            return
        except Exception as e:
            print(f"   ⚠️ محاولة الاتصال بـ Qdrant فشلت ({attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(3) # الانتظار 3 ثوانٍ قبل إعادة المحاولة
            else:
                print("   ❌ تخطى الرفع السحابي مؤقتاً وتم حفظ الملف محلياً بنجاح.")


# ==========================================
# 5. الـ Pipeline الرئيسي المتكامل
# ==========================================
def run_codeu_complete_pipeline(course_topic: str):
    ensure_collection()

    # الخطوة 1: توليد الهيكل
    roadmap = generate_course_roadmap(course_topic)
    print(f"✨ تم إنشاء الهيكل: {roadmap.course_title} (يحتوي على {len(roadmap.sections)} أقسام)\n")

    # حفظ الهيكل كملف JSON محلي
    safe_topic_name = sanitize_filename(course_topic)
    roadmap_filename = os.path.join(OUTPUT_DIR, f"{safe_topic_name}_roadmap.json")
    with open(roadmap_filename, "w", encoding="utf-8") as f:
        f.write(roadmap.model_dump_json(indent=2))

    total_steps = sum(len(sec.steps) for sec in roadmap.sections)
    current = 0
    
    # 🌟 متغير لتتبع اسم الدرس السابق لضمان الترابط
    prev_step_title = None

    print(f"⏳ بدء توليد ومعالجة محتوى {total_steps} درس تفصيلي متسلسل...\n")

    for section in roadmap.sections:
        print(f"\n📂 ----------------------------------------")
        print(f"📂 [القسم]: {section.section_title}")
        print(f"📂 ----------------------------------------")
        
        for step in section.steps:
            current += 1
            print(f"\n--- [التقدم: {current}/{total_steps}] ---")
            
            # توليد محتوى الدرس مع تمرير اسم الدرس السابق كـ السياق
            lesson_markdown = generate_step_content(
                course_title=roadmap.course_title,
                section_title=section.section_title,
                step=step,
                prev_step_title=prev_step_title  # <-- تمرير الخطوة السابقة هنا
            )
            
            # تحديث قيمة الدرس السابق للخطوة الحالية للترابط في المرة القادمة
            prev_step_title = step.step_title
            
            # 1. حفظ الدرس محلياً بصيغة Markdown
            safe_step_title = sanitize_filename(step.step_title)
            md_filename = f"step_{step.step_id}_{safe_step_title}.md"
            md_path = os.path.join(OUTPUT_DIR, md_filename)
            with open(md_path, "w", encoding="utf-8") as md_file:
                md_file.write(f"# {section.section_title}\n## {step.step_title}\n\n{lesson_markdown}")
            print(f"   💾 تم حفظ السكريبت محلياً في: {md_filename}")

            # 2. رفع المحتوى إلى Qdrant Cloud للـ RAG
            ingest_lesson_to_qdrant_with_retry(
                course_title=roadmap.course_title,
                section_title=section.section_title,
                step_id=step.step_id,
                step_title=step.step_title,
                content=lesson_markdown
            )

    print(f"\n🎉 مبروك! انتهى بناء الكورس بالكامل بتسلسل احترافي ومحفوظ محلياً ومرفوع للـ RAG!")

if __name__ == "__main__":
    TOPIC = "Programming in Python for Beginners to Advanced"
    run_codeu_complete_pipeline(course_topic=TOPIC)