from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from app.services.storage import resolve_media_path, safe_filename

router = APIRouter(prefix="/api/media", tags=["media"])


@router.get("/{source_id}/{filename}")
async def get_media(source_id: str, filename: str) -> FileResponse:
    path = resolve_media_path(source_id, safe_filename(filename))
    if path is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found. Re-upload the file to enable preview.",
        )
    return FileResponse(path)
