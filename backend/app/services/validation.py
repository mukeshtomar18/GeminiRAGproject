from pathlib import PurePosixPath

from fastapi import HTTPException, UploadFile, status
from mutagen import File as MutagenFile

from app.core.config import Settings
from app.core.modality import (
    ALLOWED_MIME_TYPES,
    EXT_TO_MIME,
    EXT_TO_MODALITY,
    Modality,
)
from app.models.domain import MediaAsset
from app.pipelines.pdf_split import pdf_page_count


class ValidationError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


def _extension(filename: str) -> str:
    return PurePosixPath(filename.lower()).suffix


def resolve_modality(filename: str, content_type: str | None) -> Modality:
    ext = _extension(filename)
    modality = EXT_TO_MODALITY.get(ext)
    if modality is None:
        raise ValidationError(
            f"Unsupported file type '{ext or filename}'. "
            "Allowed: .txt, .png, .jpg, .jpeg, .pdf, .mp3, .wav, .mp4, .mov"
        )
    if content_type and content_type.split(";")[0].strip():
        mime = content_type.split(";")[0].strip().lower()
        allowed = ALLOWED_MIME_TYPES[modality]
        # Browsers sometimes send application/octet-stream — fall back to extension
        if mime not in allowed and mime != "application/octet-stream":
            raise ValidationError(
                f"MIME type '{mime}' is not allowed for {modality.value} files"
            )
    return modality


def estimate_word_count(text: str) -> int:
    return len([w for w in text.split() if w.strip()])


def validate_text_query(text: str, settings: Settings) -> str:
    cleaned = text.strip()
    words = estimate_word_count(cleaned)
    if words > settings.max_text_words:
        raise ValidationError(
            f"Text exceeds limit of ~{settings.max_text_words} words "
            f"({settings.max_text_tokens} tokens). Got ~{words} words."
        )
    return cleaned


def _media_duration_seconds(data: bytes, filename: str) -> float | None:
    from io import BytesIO

    try:
        audio = MutagenFile(BytesIO(data))
        if audio is not None and audio.info is not None and hasattr(audio.info, "length"):
            return float(audio.info.length)
    except Exception:
        return None
    return None


async def read_and_validate_upload(
    upload: UploadFile,
    settings: Settings,
) -> MediaAsset:
    filename = upload.filename or "upload"
    data = await upload.read()
    if not data:
        raise ValidationError(f"File '{filename}' is empty")
    if len(data) > settings.max_upload_bytes:
        raise ValidationError(
            f"File '{filename}' exceeds max size of {settings.max_upload_bytes} bytes"
        )

    modality = resolve_modality(filename, upload.content_type)
    ext = _extension(filename)
    mime = EXT_TO_MIME[ext]

    text_content: str | None = None
    page_count: int | None = None
    duration: float | None = None
    page_start: int | None = None
    page_end: int | None = None

    if modality == Modality.TEXT:
        text_content = data.decode("utf-8", errors="replace")
        validate_text_query(text_content, settings)

    elif modality == Modality.PDF:
        try:
            page_count = pdf_page_count(data)
        except Exception as exc:
            raise ValidationError(f"PDF '{filename}' could not be read: {exc}") from exc
        if page_count < 1:
            raise ValidationError(f"PDF '{filename}' has no pages")
        # Long PDFs are accepted and split into max_pdf_pages windows at ingest.
        page_start = 1
        page_end = page_count

    elif modality == Modality.AUDIO:
        duration = _media_duration_seconds(data, filename)
        if duration is not None and duration > settings.max_audio_seconds:
            raise ValidationError(
                f"Audio '{filename}' is {duration:.1f}s; max is {settings.max_audio_seconds}s"
            )

    elif modality == Modality.VIDEO:
        duration = _media_duration_seconds(data, filename)
        if duration is not None and duration > settings.max_video_seconds:
            raise ValidationError(
                f"Video '{filename}' is {duration:.1f}s; max is {settings.max_video_seconds}s"
            )

    return MediaAsset(
        filename=filename,
        mime_type=mime,
        modality=modality.value,
        data=data,
        text_content=text_content,
        page_count=page_count,
        duration_seconds=duration,
        page_start=page_start,
        page_end=page_end,
        parent_filename=filename if modality == Modality.PDF else None,
    )


def validate_attachment_batch(
    assets: list[MediaAsset],
    settings: Settings,
) -> None:
    images = [a for a in assets if a.modality == Modality.IMAGE.value]
    pdfs = [a for a in assets if a.modality == Modality.PDF.value]

    if len(images) > settings.max_images_per_request:
        raise ValidationError(
            f"At most {settings.max_images_per_request} images per request "
            f"(got {len(images)})"
        )
    if len(pdfs) > settings.max_pdf_files_per_request:
        raise ValidationError(
            f"At most {settings.max_pdf_files_per_request} PDF per request "
            f"(got {len(pdfs)})"
        )


def http_validation_error(exc: ValidationError) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)
