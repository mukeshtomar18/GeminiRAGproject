from app.core.config import Settings
from app.services.validation import ValidationError, validate_attachment_batch, validate_text_query
from app.models.domain import MediaAsset
import pytest


def test_text_within_limit():
    settings = Settings()
    assert validate_text_query("hello world", settings) == "hello world"


def test_text_over_word_limit():
    settings = Settings(max_text_words=5)
    with pytest.raises(ValidationError):
        validate_text_query("one two three four five six", settings)


def test_image_batch_limit():
    settings = Settings(max_images_per_request=2)
    assets = [
        MediaAsset("a.png", "image/png", "image", b"1"),
        MediaAsset("b.png", "image/png", "image", b"2"),
        MediaAsset("c.png", "image/png", "image", b"3"),
    ]
    with pytest.raises(ValidationError):
        validate_attachment_batch(assets, settings)
