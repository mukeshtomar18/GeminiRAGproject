from enum import Enum


class Modality(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    PDF = "pdf"


ALLOWED_EXTENSIONS: dict[Modality, set[str]] = {
    Modality.TEXT: {".txt"},
    Modality.IMAGE: {".png", ".jpg", ".jpeg"},
    Modality.AUDIO: {".mp3", ".wav"},
    Modality.VIDEO: {".mp4", ".mov"},
    Modality.PDF: {".pdf"},
}

ALLOWED_MIME_TYPES: dict[Modality, set[str]] = {
    Modality.TEXT: {"text/plain"},
    Modality.IMAGE: {"image/png", "image/jpeg"},
    Modality.AUDIO: {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/wave"},
    Modality.VIDEO: {"video/mp4", "video/quicktime"},
    Modality.PDF: {"application/pdf"},
}

EXT_TO_MODALITY: dict[str, Modality] = {
    ext: modality
    for modality, exts in ALLOWED_EXTENSIONS.items()
    for ext in exts
}

EXT_TO_MIME: dict[str, str] = {
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".pdf": "application/pdf",
}
