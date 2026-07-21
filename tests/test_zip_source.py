from pathlib import Path
from zipfile import ZipFile

from domain import PageNumber
from source_adapter import ZipSourceAdapter


def test_zip_source_selects_requested_filename_prefix(tmp_path: Path) -> None:
    archive_path = tmp_path / "book.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr("120022.jpg", b"first")
        archive.writestr("130022.jpg", b"second")

    pages = tuple(
        ZipSourceAdapter(archive_path, tmp_path, filename_prefix="120").pages(
            (PageNumber(22),)
        )
    )

    assert len(pages) == 1
    assert pages[0].image_path.read_bytes() == b"first"
