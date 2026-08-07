from functools import lru_cache

from app.clients.gemini import GeminiClient
from app.clients.pinecone_client import PineconeClient
from app.core.config import Settings, get_settings
from app.pipelines.ingest import IngestPipeline
from app.services.rag import RagService


@lru_cache
def get_gemini_client() -> GeminiClient:
    return GeminiClient(get_settings())


@lru_cache
def get_pinecone_client() -> PineconeClient:
    return PineconeClient(get_settings())


def get_rag_service() -> RagService:
    settings: Settings = get_settings()
    gemini = get_gemini_client()
    pinecone = get_pinecone_client()
    ingest = IngestPipeline(gemini, settings)
    return RagService(settings, gemini, pinecone, ingest)
