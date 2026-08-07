import logging
import re

from app.clients.gemini import GeminiClient
from app.clients.pinecone_client import PineconeClient
from app.core.config import Settings
from app.core.modality import EXT_TO_MIME
from app.models.domain import Citation, DocumentChunk, MediaAsset, RagAnswer
from app.pipelines.ingest import IngestPipeline
from app.services.storage import resolve_media_path, uploads_root

logger = logging.getLogger(__name__)

IMAGE_SEEK_RE = re.compile(
    r"\b("
    r"image|photo|picture|pic|jpg|jpeg|png|"
    r"t-?shirt|shirt|wearing|person|people|someone|"
    r"show\s+me|give\s+me|find\s+(the\s+)?(image|photo|picture)"
    r")\b",
    re.IGNORECASE,
)

VIDEO_SEEK_RE = re.compile(
    r"\b("
    r"video|clip|mp4|mov|footage|wishing|wish|said|speaking|talking|"
    r"mukesh|transcript|watch|show\s+me\s+the\s+video"
    r")\b",
    re.IGNORECASE,
)


def _is_thin_media_preview(preview: str, title: str | None, modality: str) -> bool:
    text = (preview or "").strip()
    if not text:
        return True
    if text.startswith("[no_text_description]") or text.startswith(
        "[description_deferred]"
    ):
        return True
    if f" | {modality} |" in text:
        return True
    if title and text.startswith(title) and len(text) < 120:
        return True
    return False


def _wants_image(query: str) -> bool:
    return bool(IMAGE_SEEK_RE.search(query))


def _wants_video(query: str) -> bool:
    return bool(VIDEO_SEEK_RE.search(query))


class RagService:
    def __init__(
        self,
        settings: Settings,
        gemini: GeminiClient,
        pinecone: PineconeClient,
        ingest: IngestPipeline,
    ) -> None:
        self.settings = settings
        self.gemini = gemini
        self.pinecone = pinecone
        self.ingest = ingest

    async def ingest_only(self, assets: list[MediaAsset]) -> list[DocumentChunk]:
        """Upload path: extract, store, embed, index — no chat generation."""
        if not assets:
            raise ValueError("Provide at least one file to upload")
        chunks = self.ingest.process_assets(assets)
        indexed = self.pinecone.upsert_chunks(chunks)
        logger.info("Upload indexed %s chunks", indexed)
        return chunks

    async def chat(self, query: str, assets: list[MediaAsset]) -> RagAnswer:
        indexed_count = 0
        fresh_chunks: list[DocumentChunk] = []
        fresh_media: list[MediaAsset] = []
        if assets:
            fresh_chunks = self.ingest.process_assets(assets)
            indexed_count = self.pinecone.upsert_chunks(fresh_chunks)
            logger.info("Indexed %s chunks for chat request", indexed_count)
            fresh_media = list(assets)

        query_for_embed = self._resolve_query(query, assets, fresh_chunks)
        if not query_for_embed:
            raise ValueError("Provide a text message and/or at least one attachment")

        wants_image = _wants_image(query_for_embed)
        wants_video = _wants_video(query_for_embed)
        query_vector = self.gemini.embed_text(query_for_embed)

        metadata_filter = None
        if re.search(r"\bvideo\b|\.mp4\b|\.mov\b", query_for_embed, re.I):
            metadata_filter = {"modality": {"$eq": "video"}}
        elif wants_image:
            metadata_filter = {"modality": {"$eq": "image"}}
        elif wants_video:
            metadata_filter = {"modality": {"$eq": "video"}}
        top_k = max(
            self.settings.rag_top_k,
            8 if (wants_image or wants_video) else self.settings.rag_top_k,
        )
        citations = self.pinecone.query(
            query_vector,
            top_k=top_k,
            metadata_filter=metadata_filter,
        )
        if (wants_image or wants_video) and not citations:
            citations = self.pinecone.query(query_vector, top_k=top_k)

        citations = self._hydrate_citations(citations)

        context_blocks: list[str] = []
        for chunk in fresh_chunks:
            context_blocks.append(self._format_chunk(chunk))

        fresh_keys = {
            f"{c.source_id}:{c.page_start}:{c.page_end}" for c in fresh_chunks
        }
        for citation in citations:
            key = f"{citation.source_id}:{citation.page_start}:{citation.page_end}"
            if key in fresh_keys:
                continue
            context_blocks.append(self._format_citation(citation))

        media_for_answer = list(fresh_media)
        media_for_answer.extend(self._load_media_from_citations(citations, fresh_media))
        if wants_image:
            media_for_answer.extend(
                self._load_all_stored_media(
                    modalities={".png", ".jpg", ".jpeg"},
                    modality_name="image",
                    exclude=media_for_answer,
                )
            )
        if wants_video:
            media_for_answer.extend(
                self._load_all_stored_media(
                    modalities={".mp4", ".mov"},
                    modality_name="video",
                    exclude=media_for_answer,
                )
            )

        if wants_image:
            missing = [
                c
                for c in citations
                if c.modality == "image"
                and (
                    not c.file_url
                    or _is_thin_media_preview(c.text_preview, c.title, "image")
                )
            ]
            if missing and not media_for_answer:
                names = ", ".join(
                    sorted({c.title or c.source_id for c in missing if c.title or c.source_id})
                )
                context_blocks.insert(
                    0,
                    (
                        "[system_note] Visual matches were found in the vector index "
                        f"({names}), but the original image files were not stored on "
                        "disk (uploaded before media persistence). Ask the user to "
                        "re-upload those image files with the Upload button, then ask "
                        "again so the system can describe and display them."
                    ),
                )

        if not context_blocks:
            context_blocks = [self._format_citation(c) for c in citations]

        answer = self.gemini.generate_answer(
            query=query_for_embed,
            context_blocks=context_blocks,
            media_assets=media_for_answer,
        )
        return RagAnswer(
            answer=answer,
            citations=citations,
            indexed_count=indexed_count,
        )

    def _hydrate_citations(self, citations: list[Citation]) -> list[Citation]:
        hydrated: list[Citation] = []
        for citation in citations:
            if citation.modality not in {"image", "video", "audio"}:
                hydrated.append(citation)
                continue
            if not _is_thin_media_preview(
                citation.text_preview, citation.title, citation.modality
            ):
                # Still attach file_url if file exists
                path = resolve_media_path(
                    citation.source_id, citation.title or "file"
                )
                if path is not None and not citation.file_url:
                    citation.file_url = (
                        f"/api/media/{citation.source_id}/{path.name}"
                    )
                hydrated.append(citation)
                continue

            path = resolve_media_path(
                citation.source_id,
                citation.title or "file",
            )
            if path is None:
                hydrated.append(citation)
                continue

            try:
                data = path.read_bytes()
                mime = citation.mime_type or EXT_TO_MIME.get(
                    path.suffix.lower(), "application/octet-stream"
                )
                asset = MediaAsset(
                    filename=path.name,
                    mime_type=mime,
                    modality=citation.modality,
                    data=data,
                    parent_filename=citation.title or path.name,
                    file_url=citation.file_url
                    or f"/api/media/{citation.source_id}/{path.name}",
                )
                description = self.gemini.describe_asset(asset)
                if description:
                    citation.text_preview = description
                    citation.file_url = asset.file_url
                    logger.info(
                        "Hydrated %s citation %s (%s chars)",
                        citation.modality,
                        citation.source_id,
                        len(description),
                    )
            except Exception:
                logger.exception(
                    "Failed hydrating citation %s", citation.source_id
                )
            hydrated.append(citation)
        return hydrated

    def _load_media_from_citations(
        self,
        citations: list[Citation],
        already: list[MediaAsset],
    ) -> list[MediaAsset]:
        already_names = {(a.parent_filename or a.filename).lower() for a in already}
        loaded: list[MediaAsset] = []
        for citation in citations:
            if citation.modality not in {"image", "video", "audio"}:
                continue
            title = (citation.title or "").lower()
            if title and title in already_names:
                continue
            path = resolve_media_path(citation.source_id, citation.title or "file")
            if path is None:
                continue
            mime = citation.mime_type or EXT_TO_MIME.get(
                path.suffix.lower(), "application/octet-stream"
            )
            file_url = (
                citation.file_url
                or f"/api/media/{citation.source_id}/{path.name}"
            )
            loaded.append(
                MediaAsset(
                    filename=path.name,
                    mime_type=mime,
                    modality=citation.modality,
                    data=path.read_bytes(),
                    parent_filename=citation.title or path.name,
                    file_url=file_url,
                )
            )
            citation.file_url = file_url
        return loaded

    def _load_all_stored_media(
        self,
        modalities: set[str],
        modality_name: str,
        exclude: list[MediaAsset],
    ) -> list[MediaAsset]:
        exclude_names = {(a.parent_filename or a.filename).lower() for a in exclude}
        loaded: list[MediaAsset] = []
        root = uploads_root()
        if not root.exists():
            return loaded
        for source_dir in root.iterdir():
            if not source_dir.is_dir():
                continue
            for path in source_dir.iterdir():
                if not path.is_file():
                    continue
                if path.suffix.lower() not in modalities:
                    continue
                if path.stat().st_size < 1024:
                    continue
                if path.name.lower() in exclude_names:
                    continue
                mime = EXT_TO_MIME.get(
                    path.suffix.lower(),
                    "video/mp4" if modality_name == "video" else "image/jpeg",
                )
                loaded.append(
                    MediaAsset(
                        filename=path.name,
                        mime_type=mime,
                        modality=modality_name,
                        data=path.read_bytes(),
                        parent_filename=path.name,
                        file_url=f"/api/media/{source_dir.name}/{path.name}",
                    )
                )
        return loaded

    def _resolve_query(
        self,
        query: str,
        assets: list[MediaAsset],
        fresh_chunks: list[DocumentChunk],
    ) -> str:
        cleaned = query.strip()
        if cleaned:
            return cleaned
        if fresh_chunks:
            title = fresh_chunks[0].title or (
                assets[0].filename if assets else "uploaded file"
            )
            modality = fresh_chunks[0].modality
            if modality == "image":
                return (
                    f"Describe the uploaded image '{title}' and answer using the "
                    "visual content."
                )
            if modality == "video":
                return (
                    f"Summarize the uploaded video '{title}' using scenes and transcript."
                )
            if modality == "audio":
                return f"Summarize the uploaded audio '{title}' using the transcript."
            return (
                f"Summarize the uploaded document '{title}' and explain its key ideas."
            )
        if assets:
            return (
                f"Describe and answer based on attached {assets[0].modality} file: "
                f"{assets[0].filename}"
            )
        return ""

    @staticmethod
    def _format_chunk(chunk: DocumentChunk) -> str:
        bits = [
            f"source_id={chunk.source_id}",
            f"modality={chunk.modality}",
            f"chunk_index={chunk.chunk_index}",
        ]
        if chunk.title:
            bits.append(f"title={chunk.title}")
        if chunk.file_url:
            bits.append(f"file_url={chunk.file_url}")
        if chunk.page_start is not None and chunk.page_end is not None:
            bits.append(f"pages={chunk.page_start}-{chunk.page_end}")
        return f"[{', '.join(bits)}]\n{chunk.text_preview}"

    @staticmethod
    def _format_citation(citation: Citation) -> str:
        bits = [
            f"source_id={citation.source_id}",
            f"modality={citation.modality}",
            f"score={citation.score:.3f}",
        ]
        if citation.title:
            bits.append(f"title={citation.title}")
        if citation.file_url:
            bits.append(f"file_url={citation.file_url}")
        if citation.page_start is not None and citation.page_end is not None:
            bits.append(f"pages={citation.page_start}-{citation.page_end}")
        elif citation.page is not None:
            bits.append(f"page={citation.page}")
        return f"[{', '.join(bits)}]\n{citation.text_preview}"
