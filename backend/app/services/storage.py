from pathlib import Path
import re

from app.core.config import BACKEND_ROOT, Settings


def uploads_root(settings: Settings | None = None) -> Path:
    root = BACKEND_ROOT / "uploads"
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_filename(name: str) -> str:
    cleaned = Path(name).name
    cleaned = re.sub(r"[^\w.\- ()\[\]]+", "_", cleaned).strip("._")
    return cleaned or "file"


def save_media_bytes(
    source_id: str,
    filename: str,
    data: bytes,
) -> tuple[Path, str]:
    """
    Persist bytes and return (absolute_path, public_api_path).
    public_api_path is like /api/media/{source_id}/{filename}
    """
    folder = uploads_root() / source_id
    folder.mkdir(parents=True, exist_ok=True)
    fname = safe_filename(filename)
    path = folder / fname
    path.write_bytes(data)
    api_path = f"/api/media/{source_id}/{fname}"
    return path, api_path


def resolve_media_path(source_id: str, filename: str) -> Path | None:
    path = uploads_root() / source_id / safe_filename(filename)
    if path.is_file():
        return path
    # fallback: first file in source folder
    folder = uploads_root() / source_id
    if folder.is_dir():
        files = sorted(p for p in folder.iterdir() if p.is_file())
        if files:
            return files[0]
    return None
