from qdrant_client.http import models as rest
from app.core.config import settings
from app.services.ai_clients import embedding_model, qdrant_client

def search_course_rag(course_title: str, student_question: str, limit: int = 3) -> list[str]:
    """
    إجراء بحث جراحي في Qdrant مع فلترة الكورس المستهدف لضمان عدم تداخل المعلومات.
    """
    query_vector = embedding_model.encode(student_question).tolist()
    
    try:
        response = qdrant_client.query_points(
            collection_name=settings.COLLECTION_NAME,
            query=query_vector,
            query_filter=rest.Filter(
                must=[
                    rest.FieldCondition(
                        key="course_title",
                        match=rest.MatchValue(value=course_title)
                    )
                ]
            ),
            limit=limit,
            with_payload=True
        )
        
        context_chunks = []
        for hit in response.points:
            payload = hit.payload
            if payload and "text" in payload:
                context_chunks.append(payload["text"])
                
        return context_chunks
        
    except Exception as e:
        print(f"⚠️ خطأ أثناء البحث في Qdrant: {e}")
        return []
