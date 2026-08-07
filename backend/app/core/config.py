from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(
            str(PROJECT_ROOT / ".env"),
            str(BACKEND_ROOT / ".env"),
            ".env",
            "../.env",
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    cors_origins: str = "http://localhost:3000"

    gemini_api_key: str = ""
    gemini_embedding_model: str = "gemini-embedding-2-preview"
    gemini_generation_model: str = "gemini-flash-latest"
    embedding_dimensions: int = 768
    # Skip slow Gemini describe during upload for video/audio (describe on query instead)
    describe_media_on_upload: bool = False

    pinecone_api_key: str = ""
    pinecone_index_name: str = "gemini-multimodal-rag"
    pinecone_namespace: str = "default"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"

    rag_top_k: int = 5
    max_upload_bytes: int = 50 * 1024 * 1024

    # Gemini Embedding 2 Preview modality limits (canonical)
    max_text_tokens: int = 8192
    max_text_words: int = 6000
    max_images_per_request: int = 6
    max_video_seconds: int = 120
    max_audio_seconds: int = 80
    max_pdf_pages: int = 6
    max_pdf_files_per_request: int = 1
    # Stored in Pinecone metadata + used for generation context
    max_chunk_text_chars: int = 12000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
