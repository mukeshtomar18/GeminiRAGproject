from fastapi import APIRouter

from app.api.deps import get_gemini_client, get_pinecone_client
from app.core.config import get_settings
from app.models.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    gemini = get_gemini_client()
    pinecone = get_pinecone_client()
    return HealthResponse(
        status="ok",
        embedding_model=settings.gemini_embedding_model,
        generation_model=settings.gemini_generation_model,
        pinecone_configured=pinecone.configured,
        gemini_configured=gemini.configured,
    )
