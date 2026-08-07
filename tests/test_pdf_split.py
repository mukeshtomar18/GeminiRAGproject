from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import (
    DecodedStreamObject,
    DictionaryObject,
    NameObject,
)

from app.core.config import Settings
from app.models.domain import MediaAsset
from app.pipelines.ingest import IngestPipeline
from app.pipelines.pdf_split import (
    extract_pdf_text,
    pdf_page_count,
    split_pdf_into_page_windows,
)


class _FakeGemini:
    def embed_asset(self, asset: MediaAsset) -> list[float]:
        return [0.1, 0.2, 0.3]

    def describe_asset(self, asset: MediaAsset) -> str:
        return f"described-{asset.modality}:{asset.filename}"


def _make_pdf(pages: int) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _make_pdf_with_text(text: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=200)
    stream = DecodedStreamObject()
    content = f"BT /F1 12 Tf 50 100 Td ({text}) Tj ET".encode(
        "latin-1", errors="replace"
    )
    stream.set_data(content)
    page[NameObject("/Contents")] = stream
    fonts = DictionaryObject()
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    fonts[NameObject("/F1")] = font
    resources = DictionaryObject()
    resources[NameObject("/Font")] = fonts
    page[NameObject("/Resources")] = resources
    buf = BytesIO()
    writer.write(buf)
    return buf.getvalue()


def test_split_pdf_into_six_page_windows():
    data = _make_pdf(14)
    segments = split_pdf_into_page_windows(data, max_pages=6)
    assert len(segments) == 3
    assert [pdf_page_count(s[0]) for s in segments] == [6, 6, 2]
    assert [(s[1], s[2]) for s in segments] == [(1, 6), (7, 12), (13, 14)]


def test_extract_pdf_text_includes_content():
    data = _make_pdf_with_text("AttentionIsAllYouNeed")
    text = extract_pdf_text(data)
    assert "AttentionIsAllYouNeed" in text


def test_ingest_stores_extracted_pdf_text_in_chunk_preview():
    settings = Settings(max_pdf_pages=6)
    pipeline = IngestPipeline(_FakeGemini(), settings)  # type: ignore[arg-type]
    asset = MediaAsset(
        filename="paper.pdf",
        mime_type="application/pdf",
        modality="pdf",
        data=_make_pdf_with_text("TransformerArchitecture"),
        page_count=1,
    )
    chunks = pipeline.process_assets([asset])
    assert len(chunks) == 1
    assert "TransformerArchitecture" in chunks[0].text_preview


def test_ingest_extracts_image_and_video_descriptions():
    settings = Settings(max_pdf_pages=6)
    pipeline = IngestPipeline(_FakeGemini(), settings)  # type: ignore[arg-type]
    image = MediaAsset(
        filename="scene.png",
        mime_type="image/png",
        modality="image",
        data=b"fake-image",
    )
    video = MediaAsset(
        filename="clip.mp4",
        mime_type="video/mp4",
        modality="video",
        data=b"fake-video",
        duration_seconds=12.0,
    )
    image_chunks = pipeline.process_assets([image])
    video_chunks = pipeline.process_assets([video])
    assert "described-image:scene.png" in image_chunks[0].text_preview
    assert "described-video:clip.mp4" in video_chunks[0].text_preview


def test_ingest_expands_long_pdf_into_multiple_chunks():
    settings = Settings(max_pdf_pages=6)
    pipeline = IngestPipeline(_FakeGemini(), settings)  # type: ignore[arg-type]
    asset = MediaAsset(
        filename="report.pdf",
        mime_type="application/pdf",
        modality="pdf",
        data=_make_pdf(13),
        page_count=13,
        page_start=1,
        page_end=13,
        parent_filename="report.pdf",
    )
    chunks = pipeline.process_assets([asset])
    assert len(chunks) == 3
    assert [c.chunk_index for c in chunks] == [0, 1, 2]
    assert chunks[0].source_id == chunks[1].source_id == chunks[2].source_id
    assert [(c.page_start, c.page_end) for c in chunks] == [
        (1, 6),
        (7, 12),
        (13, 13),
    ]


def test_short_pdf_stays_single_segment():
    settings = Settings(max_pdf_pages=6)
    pipeline = IngestPipeline(_FakeGemini(), settings)  # type: ignore[arg-type]
    asset = MediaAsset(
        filename="short.pdf",
        mime_type="application/pdf",
        modality="pdf",
        data=_make_pdf(4),
        page_count=4,
    )
    chunks = pipeline.process_assets([asset])
    assert len(chunks) == 1
    assert chunks[0].page_start == 1
    assert chunks[0].page_end == 4
