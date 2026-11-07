from google import genai
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.core.console import configure_console

configure_console()

print("🔄 جاري تحميل نموذج الـ Embeddings (BAAI/bge-m3) في الـ Backend...")

embedding_model = SentenceTransformer("BAAI/bge-m3")

qdrant_client = QdrantClient(
    url=settings.QDRANT_URL,
    api_key=settings.QDRANT_API_KEY,
    timeout=60,
)

gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
