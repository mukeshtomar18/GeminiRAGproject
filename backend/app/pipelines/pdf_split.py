from io import BytesIO

from pypdf import PdfReader, PdfWriter


def pdf_page_count(data: bytes) -> int:
    reader = PdfReader(BytesIO(data))
    return len(reader.pages)


def extract_pdf_text(data: bytes) -> str:
    """Extract plain text from a PDF (or PDF segment) for RAG generation context."""
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        raw = page.extract_text() or ""
        cleaned = "\n".join(line.strip() for line in raw.splitlines() if line.strip())
        if cleaned:
            parts.append(f"[page {index}]\n{cleaned}")
    return "\n\n".join(parts).strip()


def split_pdf_into_page_windows(
    data: bytes,
    max_pages: int,
) -> list[tuple[bytes, int, int]]:
    """
    Split a PDF into segments of at most `max_pages` each.

    Returns list of (segment_pdf_bytes, page_start_1based, page_end_1based).
    """
    if max_pages < 1:
        raise ValueError("max_pages must be >= 1")

    reader = PdfReader(BytesIO(data))
    total = len(reader.pages)
    if total == 0:
        raise ValueError("PDF has no pages")

    segments: list[tuple[bytes, int, int]] = []
    start = 0
    while start < total:
        end = min(start + max_pages, total)
        writer = PdfWriter()
        for i in range(start, end):
            writer.add_page(reader.pages[i])
        buffer = BytesIO()
        writer.write(buffer)
        segments.append((buffer.getvalue(), start + 1, end))
        start = end
    return segments
