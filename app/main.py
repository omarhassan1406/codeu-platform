import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
# httpx logs every request URL at INFO, which writes the private Qdrant
# cluster address into server logs. Keep only its warnings and errors.
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Backend API Service for CodeU Interactive AI Platform"
)

# السماح بالاتصالات الخارجية (CORS) للربط مع تطبيق الـ Flutter أو الواجهات
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ربط مسارات الـ API النسخة الأولى
app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Health Check"])
async def root():
    return {
        "status": "online",
        "message": f"Welcome to {settings.PROJECT_NAME} API Service!"
    }