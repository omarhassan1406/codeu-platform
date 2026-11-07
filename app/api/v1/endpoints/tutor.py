from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from google.genai import types
from app.core.config import settings
from app.services.gemini_service import generate_content_with_fallback
from app.services.rag_service import search_course_rag

router = APIRouter()

class RaiseHandRequest(BaseModel):
    course_title: str
    step_id: str
    student_question: str

class RaiseHandResponse(BaseModel):
    answer_text: str
    avatar_state: str
    context_used: list[str]

@router.post("/raise-hand", response_model=RaiseHandResponse)
async def raise_hand(request: RaiseHandRequest):
    """
    استقبال سؤال الطالب أثناء الدرس، والبحث الجراحي في Qdrant، ثم إجابة الأستاذ الذكي بدون هلوسة[cite: 3, 13].
    """
    # 1. جلب السياق من قاعدة المعرفة عبر الـ RAG
    context_chunks = search_course_rag(
        course_title=request.course_title,
        student_question=request.student_question,
        limit=3
    )
    
    if not context_chunks:
        return RaiseHandResponse(
            answer_text="عذراً يا بطل، لم أجد معلومات مطابقة لهذا السؤال في منهج هذا الكورس الحالي.",
            avatar_state="idle",
            context_used=[]
        )
        
    retrieved_context = "\n\n".join(context_chunks)
    
    # 2. إعداد الشخصية وقواعد منع الهلوسة (System Prompt)[cite: 3, 13]
    system_prompt = """
    أنت أستاذ برمجيات خبير، ودود، وتفاعلي جداً في منصة CodeU.
    مهمتك هي شرح المفاهيم البرمجية للطالب بأسلوب شيق وحي وكأنك تجلس معه وجهاً لوجه.
    قواعد صارمة:
    1. أجب حصرياً وبناءً على "السياق المسترجع من المنهج" أدناه.
    2. ممنوع منعاً باتاً اختراع معلومات خارجية أو هلوسة أكواد غير موجودة في السياق.
    3. إذا لم تجد الإجابة في السياق، اعتذر بلطف ووجه الطالب لما تم شرحه في الكورس.
    """
    
    user_prompt = f"""
    السياق المسترجع من منهج كورس ({request.course_title}):
    {retrieved_context}

    سؤال الطالب:
    {request.student_question}

    قم بشرح الإجابة للطالب بأسلوب تعليمي متفاعل ومبسط مع توضيح الأكواد إن وجدت:
    """
    
    try:
        response = generate_content_with_fallback(
            preferred_model=settings.GEMINI_MODEL_NAME,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.4,
            ),
        )
        
        return RaiseHandResponse(
            answer_text=response.text,
            avatar_state="explaining",
            context_used=context_chunks
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating AI response: {str(e)}")