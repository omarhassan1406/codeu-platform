import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "CodeU Platform Backend"
    VERSION: str = "1.0.0"
    
    # تعريف المفاتيح المطلوبة بدقة
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")  # 👈 أضفنا هذا السطر
    GEMINI_COURSE_MODEL: str = os.getenv("GEMINI_COURSE_MODEL", "gemini-3.5-flash-lite")
    GEMINI_MODEL_NAME: str = os.getenv("GEMINI_MODEL_NAME", "gemini-2.0-flash")
    # ترتيب نماذج الـ Fallback عند استنفاد الحصة (Rate Limit)
    GEMINI_MODEL_HIERARCHY: list[str] = [
        "gemini-3.5-flash-lite",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.6-flash",
        "gemini-3.0-flash",
        "gemini-2.5-flash",
    ]
    QDRANT_URL: str = os.getenv("QDRANT_URL", "")
    QDRANT_API_KEY: str = os.getenv("QDRANT_API_KEY", "")
    COLLECTION_NAME: str = "CodeU"

    class Config:
        env_file = ".env"
        extra = "ignore"  # 👈 هذا السطر يتجاهل أي متغيرات إضافية في ملف الـ .env لتمنع حدوث الخطأ مستقبلاً

settings = Settings()