import logging
import time
from typing import Any

from google import genai
from google.genai import types

from app.core.config import Settings
from app.models.domain import MediaAsset

logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        if not settings.gemini_api_key:
            self._client = None
        else:
            self._client = genai.Client(api_key=settings.gemini_api_key)

    @property
    def configured(self) -> bool:
        return self._client is not None

    def _require(self) -> genai.Client:
        if self._client is None:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add it to .env before running RAG."
            )
        return self._client

    def _model_candidates(self) -> list[str]:
        primary = self.settings.gemini_generation_model
        fallbacks = ["gemini-flash-latest", "gemini-2.0-flash", "gemini-2.5-flash"]
        ordered = [primary] + [m for m in fallbacks if m != primary]
        return ordered

    @staticmethod
    def _is_quota_error(exc: Exception) -> bool:
        text = str(exc).lower()
        return "429" in text or "resource_exhausted" in text or "quota" in text

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if text and str(text).strip():
            return str(text).strip()
        candidates = getattr(response, "candidates", None) or []
        parts: list[str] = []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                part_text = getattr(part, "text", None)
                if part_text:
                    parts.append(str(part_text))
        return "\n".join(parts).strip()

    def _generate(self, contents: Any) -> str:
        client = self._require()
        last_error: Exception | None = None
        for model in self._model_candidates():
            for attempt in range(2):
                try:
                    response = client.models.generate_content(
                        model=model,
                        contents=contents,
                    )
                    text = self._response_text(response)
                    if text:
                        if model != self.settings.gemini_generation_model:
                            logger.info("Used fallback generation model %s", model)
                        return text
                    return ""
                except Exception as exc:
                    last_error = exc
                    if self._is_quota_error(exc):
                        logger.warning(
                            "Quota/rate limit on model %s (attempt %s): %s",
                            model,
                            attempt + 1,
                            str(exc)[:180],
                        )
                        time.sleep(2 + attempt * 2)
                        break  # try next model
                    logger.exception("generate_content failed on %s", model)
                    break
        if last_error and self._is_quota_error(last_error):
            raise RuntimeError(
                "Gemini generate quota exceeded for the configured models. "
                "Wait about a minute and retry, or switch GEMINI_GENERATION_MODEL / billing plan."
            ) from last_error
        if last_error:
            raise last_error
        return ""

    def _parts_for_asset(self, asset: MediaAsset) -> list[Any]:
        if asset.modality == "text" and asset.text_content is not None:
            return [asset.text_content]
        return [
            types.Part.from_bytes(data=asset.data, mime_type=asset.mime_type),
        ]

    def embed_text(self, text: str) -> list[float]:
        client = self._require()
        result = client.models.embed_content(
            model=self.settings.gemini_embedding_model,
            contents=text,
            config=types.EmbedContentConfig(
                output_dimensionality=self.settings.embedding_dimensions,
            ),
        )
        return list(result.embeddings[0].values)

    def embed_asset(self, asset: MediaAsset) -> list[float]:
        client = self._require()
        contents = self._parts_for_asset(asset)
        result = client.models.embed_content(
            model=self.settings.gemini_embedding_model,
            contents=contents,
            config=types.EmbedContentConfig(
                output_dimensionality=self.settings.embedding_dimensions,
            ),
        )
        return list(result.embeddings[0].values)

    def generate_answer(
        self,
        query: str,
        context_blocks: list[str],
        media_assets: list[MediaAsset] | None = None,
    ) -> str:
        context = "\n\n".join(context_blocks) if context_blocks else "(no retrieved context)"
        prompt = (
            "You are an enterprise multimodal RAG assistant. Use the retrieved text "
            "context AND any attached image/video/audio parts to answer. "
            "For video questions (e.g. who is wishing whom, what was said), use the "
            "transcript/scene summary and/or attached video. Name matching files and "
            "source_id. If quota prevented transcription, say so clearly.\n\n"
            f"Retrieved context:\n{context}\n\n"
            f"User question:\n{query}"
        )

        usable_media = [
            a
            for a in (media_assets or [])
            if a.modality in {"image", "video", "audio"} and len(a.data) >= 1024
        ]
        # Prefer smaller media first; videos can be large — attach at most 1 video
        images = [a for a in usable_media if a.modality == "image"][:3]
        videos = [a for a in usable_media if a.modality == "video"][:1]
        audios = [a for a in usable_media if a.modality == "audio"][:1]
        attach = images + videos + audios

        parts: list[Any] = [prompt]
        for asset in attach:
            parts.append(
                f"\n[attached_{asset.modality} title={asset.parent_filename or asset.filename} "
                f"mime={asset.mime_type} file_url={asset.file_url or ''}]\n"
            )
            parts.append(
                types.Part.from_bytes(data=asset.data, mime_type=asset.mime_type)
            )

        try:
            text = self._generate(parts if attach else prompt)
        except RuntimeError as exc:
            return str(exc)
        except Exception:
            logger.exception("Multimodal generate failed; retrying text-only")
            try:
                text = self._generate(prompt)
            except Exception as exc:
                if self._is_quota_error(exc):
                    return (
                        "Gemini API quota is exhausted right now. Please wait ~30s and "
                        "ask again (video/image answers need the generation model)."
                    )
                raise
        return text or "I could not generate an answer from the current context."

    def describe_asset(self, asset: MediaAsset) -> str:
        """Extract interactive text content from image/video/audio via Gemini."""
        prompts = {
            "image": (
                "Analyze this image for retrieval-augmented QA. Be concrete and visual. "
                "Include: clothing colors (e.g. red t-shirt), people, objects, OCR text, "
                "scene, and distinctive details useful for search queries."
            ),
            "video": (
                "Analyze this video for retrieval-augmented QA. Provide a chronological "
                "scene summary, full spoken dialogue/transcript if audible (who speaks "
                "to whom, names mentioned like Mukesh), on-screen text, key events with "
                "approximate timing, and overall topic."
            ),
            "audio": (
                "Analyze this audio for retrieval-augmented QA. Provide a transcript, "
                "speakers/topics if identifiable, and a concise summary."
            ),
        }
        instruction = prompts.get(asset.modality)
        if not instruction:
            return ""

        try:
            return self._generate(
                [
                    instruction,
                    types.Part.from_bytes(data=asset.data, mime_type=asset.mime_type),
                ]
            )
        except Exception as exc:
            if self._is_quota_error(exc):
                logger.warning("Describe skipped due to quota for %s", asset.filename)
                return ""
            logger.exception("Describe failed for %s", asset.filename)
            return ""
