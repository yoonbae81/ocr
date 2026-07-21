from pathlib import Path

from adapters.cache.filesystem import FilesystemRecognitionCache
from domain import PageMarkdown, PageNumber, SourcePage


def test_recognition_cache_reuses_raw_markdown_for_identical_render(tmp_path: Path) -> None:
    image_path = tmp_path / "page.jpg"
    image_path.write_bytes(b"rendered page")
    page = SourcePage(PageNumber(3), image_path)
    cache = FilesystemRecognitionCache(tmp_path / "cache", "model-v1")
    cache.store(PageMarkdown(page, "raw markdown"))

    cached = cache.load(page)

    assert cached == PageMarkdown(page, "raw markdown")


def test_recognition_cache_misses_when_render_or_model_changes(tmp_path: Path) -> None:
    image_path = tmp_path / "page.jpg"
    image_path.write_bytes(b"first render")
    page = SourcePage(PageNumber(3), image_path)
    cache_root = tmp_path / "cache"
    FilesystemRecognitionCache(cache_root, "model-v1").store(
        PageMarkdown(page, "raw markdown")
    )

    image_path.write_bytes(b"second render")

    assert FilesystemRecognitionCache(cache_root, "model-v1").load(page) is None
    image_path.write_bytes(b"first render")
    assert FilesystemRecognitionCache(cache_root, "model-v2").load(page) is None
