import logging
import time
from typing import Any

from pinecone import Pinecone, ServerlessSpec

from app.core.config import Settings
from app.models.domain import Citation, DocumentChunk

logger = logging.getLogger(__name__)


class PineconeClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._index = None
        if not settings.pinecone_api_key:
            self._pc = None
            return
        self._pc = Pinecone(api_key=settings.pinecone_api_key)
        self._ensure_index()

    @property
    def configured(self) -> bool:
        return self._pc is not None and self._index is not None

    def _ensure_index(self) -> None:
        assert self._pc is not None
        name = self.settings.pinecone_index_name
        existing = {idx.name: idx for idx in self._pc.list_indexes()}
        if name not in existing:
            logger.info(
                "Creating dense Pinecone index '%s' (dim=%s, cosine)",
                name,
                self.settings.embedding_dimensions,
            )
            self._pc.create_index(
                name=name,
                dimension=self.settings.embedding_dimensions,
                metric="cosine",
                spec=ServerlessSpec(
                    cloud=self.settings.pinecone_cloud,
                    region=self.settings.pinecone_region,
                ),
            )
            self._wait_until_ready(name)
        else:
            self._validate_existing_index(existing[name])
            self._wait_until_ready(name)
        self._index = self._pc.Index(name)

    def _validate_existing_index(self, index_info: Any) -> None:
        """Reject sparse-only indexes — Gemini embeddings need dense vectors."""
        vector_type = getattr(index_info, "vector_type", None)
        if vector_type is None and isinstance(index_info, dict):
            vector_type = index_info.get("vector_type")
        if vector_type and str(vector_type).lower() == "sparse":
            raise RuntimeError(
                f"Pinecone index '{self.settings.pinecone_index_name}' is sparse-only. "
                "Set PINECONE_INDEX_NAME to a dense cosine index "
                f"(dimension={self.settings.embedding_dimensions})."
            )
        dimension = getattr(index_info, "dimension", None)
        if dimension is None and isinstance(index_info, dict):
            dimension = index_info.get("dimension")
        if dimension and int(dimension) != self.settings.embedding_dimensions:
            raise RuntimeError(
                f"Pinecone index dimension is {dimension}, but "
                f"EMBEDDING_DIMENSIONS={self.settings.embedding_dimensions}."
            )

    def _wait_until_ready(self, name: str, timeout_s: int = 120) -> None:
        assert self._pc is not None
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            desc = self._pc.describe_index(name)
            status = getattr(desc, "status", None)
            ready = False
            if status is not None:
                ready = bool(getattr(status, "ready", False))
                if isinstance(status, dict):
                    ready = bool(status.get("ready", False))
            if ready:
                return
            time.sleep(2)
        raise RuntimeError(f"Pinecone index '{name}' was not ready within {timeout_s}s")

    def _require(self):
        if self._index is None:
            raise RuntimeError(
                "PINECONE_API_KEY is not set. Add it to .env before running RAG."
            )
        return self._index

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        index = self._require()
        vectors = []
        for chunk in chunks:
            if chunk.embedding is None:
                continue
            vectors.append(
                {
                    "id": chunk.id,
                    "values": chunk.embedding,
                    "metadata": chunk.pinecone_metadata(),
                }
            )
        if not vectors:
            return 0
        index.upsert(vectors=vectors, namespace=self.settings.pinecone_namespace)
        return len(vectors)

    def query(
        self,
        vector: list[float],
        top_k: int,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Citation]:
        index = self._require()
        kwargs: dict[str, Any] = {
            "vector": vector,
            "top_k": top_k,
            "include_metadata": True,
            "namespace": self.settings.pinecone_namespace,
        }
        if metadata_filter:
            kwargs["filter"] = metadata_filter
        result = index.query(**kwargs)
        citations: list[Citation] = []
        matches = getattr(result, "matches", None) or result.get("matches", [])
        for match in matches:
            meta: dict[str, Any] = getattr(match, "metadata", None) or match.get(
                "metadata", {}
            )
            score = float(getattr(match, "score", None) or match.get("score", 0.0))
            citations.append(
                Citation(
                    source_id=str(meta.get("source_id", "")),
                    modality=str(meta.get("modality", "")),
                    score=score,
                    text_preview=str(meta.get("text_preview", "")),
                    title=meta.get("title"),
                    page=meta.get("page"),
                    page_start=meta.get("page_start"),
                    page_end=meta.get("page_end"),
                    mime_type=meta.get("mime_type"),
                    file_url=meta.get("file_url"),
                )
            )
        return citations
