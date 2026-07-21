from pathlib import Path

from PIL import Image

from adapters.source import ImageSourceAdapter


def test_image_source_copies_original_image_without_reencoding(tmp_path: Path) -> None:
    source_image = tmp_path / "scan.png"
    Image.new("RGB", (20, 10), "white").save(source_image)
    temporary = tmp_path / "pages"
    temporary.mkdir()

    page = next(ImageSourceAdapter(source_image, temporary).pages(None))

    assert page.image_path.suffix == ".png"
    assert page.image_path.read_bytes() == source_image.read_bytes()
