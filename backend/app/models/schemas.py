from pydantic import BaseModel, Field


class CitationOut(BaseModel):
    source_id: str
    modality: str
    score: float
    text_preview: str
    title: str | None = None
    page: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    mime_type: str | None = None
    file_url: str | None = None


class ChatResponse(BaseModel):
    answer: str
    citations: list[CitationOut] = Field(default_factory=list)
    indexed_count: int = 0


class UploadedItemOut(BaseModel):
    source_id: str
    title: str | None = None
    modality: str
    chunk_index: int
    file_url: str | None = None
    page_start: int | None = None
    page_end: int | None = None


class UploadResponse(BaseModel):
    indexed_count: int
    items: list[UploadedItemOut] = Field(default_factory=list)
    message: str


class HealthResponse(BaseModel):
    status: str
    embedding_model: str
    generation_model: str
    pinecone_configured: bool
    gemini_configured: bool


class ErrorResponse(BaseModel):
    detail: str
