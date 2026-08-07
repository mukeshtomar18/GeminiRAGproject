from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class MediaAsset:
    filename: str
    mime_type: str
    modality: str
    data: bytes
    text_content: str | None = None
    page_count: int | None = None
    duration_seconds: float | None = None
    # PDF segment provenance (1-based inclusive page range)
    page_start: int | None = None
    page_end: int | None = None
    segment_index: int | None = None
    parent_filename: str | None = None
    file_url: str | None = None


@dataclass
class DocumentChunk:
    id: str
    source_id: str
    modality: str
    mime_type: str
    chunk_index: int
    text_preview: str
    embedding: list[float] | None = None
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    title: str | None = None
    page: int | None = None
    page_start: int | None = None
    page_end: int | None = None
    timestamp_start: float | None = None
    timestamp_end: float | None = None
    file_url: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def pinecone_metadata(self) -> dict[str, Any]:
        # Keep under Pinecone metadata size limits while retaining usable RAG text.
        preview = self.text_preview[:12000]
        meta: dict[str, Any] = {
            "source_id": self.source_id,
            "modality": self.modality,
            "chunk_index": self.chunk_index,
            "mime_type": self.mime_type,
            "created_at": self.created_at,
            "text_preview": preview,
        }
        if self.title:
            meta["title"] = self.title
        if self.page is not None:
            meta["page"] = self.page
        if self.page_start is not None:
            meta["page_start"] = self.page_start
        if self.page_end is not None:
            meta["page_end"] = self.page_end
        if self.timestamp_start is not None:
            meta["timestamp_start"] = self.timestamp_start
        if self.timestamp_end is not None:
            meta["timestamp_end"] = self.timestamp_end
        if self.file_url:
            meta["file_url"] = self.file_url
        return meta


@dataclass
class Citation:
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


@dataclass
class RagAnswer:
    answer: str
    citations: list[Citation]
    indexed_count: int = 0
