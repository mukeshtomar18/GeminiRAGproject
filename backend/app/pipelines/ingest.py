import logging
import uuid
from pathlib import PurePosixPath

from app.clients.gemini import GeminiClient
from app.core.config import Settings, get_settings
from app.models.domain import DocumentChunk, MediaAsset
from app.pipelines.pdf_split import extract_pdf_text, split_pdf_into_page_windows
from app.services.storage import save_media_bytes

logger = logging.getLogger(__name__)

MEDIA_DESCRIBE_MODALITIES = frozenset({"image", "video", "audio"})


class IngestPipeline:
    """Validate → chunk/split → extract content → store → embed."""

    def __init__(
        self,
        gemini: GeminiClient,
        settings: Settings | None = None,
    ) -> None:
        self.gemini = gemini
        self.settings = settings or get_settings()

    def _clip_text(self, text: str) -> str:
        limit = self.settings.max_chunk_text_chars
        if len(text) <= limit:
            return text
        return text[: limit - 20].rstrip() + "\n...[truncated]"

    def _preview(self, asset: MediaAsset) -> str:
        if asset.text_content and asset.text_content.strip():
            return self._clip_text(asset.text_content.strip())
        parts = [asset.filename, asset.modality, asset.mime_type]
        if asset.page_start is not None and asset.page_end is not None:
            parts.append(f"pages {asset.page_start}-{asset.page_end}")
        elif asset.page_count is not None:
            parts.append(f"{asset.page_count} pages")
        if asset.duration_seconds is not None:
            parts.append(f"{asset.duration_seconds:.1f}s")
        return " | ".join(parts)

    def _with_pdf_text(self, segment: MediaAsset) -> MediaAsset:
        text = extract_pdf_text(segment.data)
        if not text:
            logger.warning(
                "No extractable text in PDF segment '%s' (pages %s-%s)",
                segment.filename,
                segment.page_start,
                segment.page_end,
            )
        segment.text_content = text or None
        return segment

    def enrich_asset(self, asset: MediaAsset) -> MediaAsset:
        """Attach textual content used for generation/RAG context."""
        if asset.text_content and asset.text_content.strip():
            return asset

        if asset.modality == "pdf":
            return self._with_pdf_text(asset)

        if asset.modality in MEDIA_DESCRIBE_MODALITIES:
            # Video/audio describe is slow and quota-heavy; defer unless enabled.
            if (
                asset.modality in {"video", "audio"}
                and not self.settings.describe_media_on_upload
            ):
                asset.text_content = (
                    f"[description_deferred] modality={asset.modality} "
                    f"file={asset.filename}. Indexed for retrieval; transcript/"
                    "summary will be extracted when you ask a question."
                )
                logger.info(
                    "Deferred %s describe on upload for '%s'",
                    asset.modality,
                    asset.filename,
                )
                return asset

            try:
                description = self.gemini.describe_asset(asset)
            except Exception:
                logger.exception(
                    "Failed to extract content from %s '%s'",
                    asset.modality,
                    asset.filename,
                )
                description = ""
            if description:
                asset.text_content = description
                logger.info(
                    "Extracted %s content for '%s' (%s chars)",
                    asset.modality,
                    asset.filename,
                    len(description),
                )
            else:
                asset.text_content = (
                    f"[no_text_description] modality={asset.modality} "
                    f"file={asset.filename}. Visual/audio content must be read from "
                    "the attached media bytes."
                )
                logger.warning(
                    "No content extracted from %s '%s'; using placeholder",
                    asset.modality,
                    asset.filename,
                )
        return asset

    def expand_asset(self, asset: MediaAsset) -> list[MediaAsset]:
        if asset.modality != "pdf":
            return [asset]

        max_pages = self.settings.max_pdf_pages
        total_pages = asset.page_count or 0
        if total_pages <= max_pages:
            return [
                MediaAsset(
                    filename=asset.filename,
                    mime_type=asset.mime_type,
                    modality=asset.modality,
                    data=asset.data,
                    page_count=total_pages or None,
                    page_start=1,
                    page_end=total_pages or 1,
                    segment_index=0,
                    parent_filename=asset.filename,
                )
            ]

        windows = split_pdf_into_page_windows(asset.data, max_pages=max_pages)
        logger.info(
            "Split PDF '%s' (%s pages) into %s segments of <=%s pages",
            asset.filename,
            total_pages,
            len(windows),
            max_pages,
        )
        segments: list[MediaAsset] = []
        stem = PurePosixPath(asset.filename).stem
        suffix = PurePosixPath(asset.filename).suffix or ".pdf"
        for idx, (segment_bytes, page_start, page_end) in enumerate(windows):
            segments.append(
                MediaAsset(
                    filename=f"{stem}.pages-{page_start}-{page_end}{suffix}",
                    mime_type=asset.mime_type,
                    modality=asset.modality,
                    data=segment_bytes,
                    page_count=(page_end - page_start + 1),
                    page_start=page_start,
                    page_end=page_end,
                    segment_index=idx,
                    parent_filename=asset.filename,
                )
            )
        return segments

    def build_chunk(
        self,
        asset: MediaAsset,
        source_id: str,
        chunk_index: int,
    ) -> DocumentChunk:
        title = PurePosixPath(asset.parent_filename or asset.filename).name
        _, file_url = save_media_bytes(source_id, asset.filename, asset.data)
        asset.file_url = file_url
        embedding = self.gemini.embed_asset(asset)
        return DocumentChunk(
            id=f"{source_id}-{chunk_index}",
            source_id=source_id,
            modality=asset.modality,
            mime_type=asset.mime_type,
            chunk_index=chunk_index,
            text_preview=self._preview(asset),
            embedding=embedding,
            title=title,
            page=asset.page_start,
            page_start=asset.page_start,
            page_end=asset.page_end,
            timestamp_start=0.0 if asset.duration_seconds is not None else None,
            timestamp_end=asset.duration_seconds,
            file_url=file_url,
            metadata={
                "segment_filename": asset.filename,
                "parent_filename": asset.parent_filename or asset.filename,
            },
        )

    def process_assets(self, assets: list[MediaAsset]) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        for asset in assets:
            source_id = str(uuid.uuid4())
            segments = self.expand_asset(asset)
            for index, segment in enumerate(segments):
                enriched = self.enrich_asset(segment)
                chunks.append(self.build_chunk(enriched, source_id, index))
        return chunks
