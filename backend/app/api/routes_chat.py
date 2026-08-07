from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.deps import get_rag_service
from app.core.config import get_settings
from app.models.schemas import (
    ChatResponse,
    CitationOut,
    UploadedItemOut,
    UploadResponse,
)
from app.services.rag import RagService
from app.services.validation import (
    ValidationError,
    http_validation_error,
    read_and_validate_upload,
    validate_attachment_batch,
    validate_text_query,
)

router = APIRouter(prefix="/api", tags=["chat"])


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    files: list[UploadFile] = File(...),
    rag: RagService = Depends(get_rag_service),
) -> UploadResponse:
    """Index files immediately (separate from chat/send)."""
    settings = get_settings()
    try:
        if not files:
            raise ValidationError("Select at least one file to upload")
        assets = []
        for upload in files:
            assets.append(await read_and_validate_upload(upload, settings))
        validate_attachment_batch(assets, settings)
        chunks = await rag.ingest_only(assets)
    except ValidationError as exc:
        raise http_validation_error(exc) from exc
    except ValueError as exc:
        raise http_validation_error(ValidationError(str(exc))) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        name = type(exc).__name__
        if "Pinecone" in name or "Api" in name or "ClientError" in name:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        raise

    items = [
        UploadedItemOut(
            source_id=c.source_id,
            title=c.title,
            modality=c.modality,
            chunk_index=c.chunk_index,
            file_url=c.file_url,
            page_start=c.page_start,
            page_end=c.page_end,
        )
        for c in chunks
    ]
    names = sorted({i.title or i.source_id for i in items})
    return UploadResponse(
        indexed_count=len(chunks),
        items=items,
        message=f"Uploaded and indexed {len(chunks)} chunk(s) from {', '.join(names)}",
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(
    message: str = Form(default=""),
    files: list[UploadFile] | None = File(default=None),
    rag: RagService = Depends(get_rag_service),
) -> ChatResponse:
    settings = get_settings()
    uploads = files or []

    try:
        if message.strip():
            validate_text_query(message, settings)

        assets = []
        for upload in uploads:
            assets.append(await read_and_validate_upload(upload, settings))
        validate_attachment_batch(assets, settings)

        # Prefer message-only chat; files optional for backward compatibility
        if not message.strip() and not assets:
            raise ValidationError("Provide a text message")

        if not message.strip() and assets:
            raise ValidationError(
                "Use the Upload button to index files. Send is for questions only."
            )

        result = await rag.chat(message, assets)
    except ValidationError as exc:
        raise http_validation_error(exc) from exc
    except ValueError as exc:
        raise http_validation_error(ValidationError(str(exc))) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        name = type(exc).__name__
        if "Pinecone" in name or "Api" in name:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(exc),
            ) from exc
        raise

    return ChatResponse(
        answer=result.answer,
        indexed_count=result.indexed_count,
        citations=[
            CitationOut(
                source_id=c.source_id,
                modality=c.modality,
                score=c.score,
                text_preview=c.text_preview,
                title=c.title,
                page=c.page,
                page_start=c.page_start,
                page_end=c.page_end,
                mime_type=c.mime_type,
                file_url=c.file_url,
            )
            for c in result.citations
        ],
    )
