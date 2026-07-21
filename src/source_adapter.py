"""PDF and raster-image implementations of the page-source port."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from shutil import copyfile
from zipfile import ZipFile

import re

import fitz

from domain import PageNumber, SourcePage


class PdfSourceAdapter:
    """Rasterize selected PDF pages into a command-scoped temporary directory."""

    def __init__(self, source: Path, dpi: int, temporary: Path) -> None:
        self._source = source
        self._dpi = dpi
        self._temporary = temporary

    def pages(self, selection: tuple[PageNumber, ...] | None) -> Iterator[SourcePage]:
        """Render requested PDF pages as JPEG images."""
        with fitz.open(self._source) as document:
            numbers = selection or tuple(
                PageNumber(index + 1) for index in range(document.page_count)
            )
            for number in numbers:
                if number.value > document.page_count:
                    raise ValueError(f"Page {number.value} exceeds PDF page count.")
                image_path = self._temporary / f"{number.value}.jpg"
                document.load_page(number.value - 1).get_pixmap(dpi=self._dpi).save(
                    image_path
                )
                yield SourcePage(number, image_path)


class ImageSourceAdapter:
    """Copy one raster input into the command-scoped page workspace."""

    def __init__(self, source: Path, temporary: Path) -> None:
        self._source = source
        self._temporary = temporary

    def pages(self, selection: tuple[PageNumber, ...] | None) -> Iterator[SourcePage]:
        """Yield the only physical page after validating the selection."""
        requested = selection or (PageNumber(1),)
        if requested != (PageNumber(1),):
            raise ValueError("A single image supports only page 1.")
        image_path = self._temporary / f"1{self._source.suffix.lower()}"
        copyfile(self._source, image_path)
        yield SourcePage(PageNumber(1), image_path)


class ZipSourceAdapter:
    """Extract selected archive images into the command-scoped page workspace."""

    def __init__(
        self, source: Path, temporary: Path, filename_prefix: str | None = None
    ) -> None:
        self._source = source
        self._temporary = temporary
        self._filename_prefix = filename_prefix

    def pages(self, selection: tuple[PageNumber, ...] | None) -> Iterator[SourcePage]:
        """Yield archive image pages using the trailing three filename digits."""
        with ZipFile(self._source) as archive:
            members = {
                page: name
                for name in archive.namelist()
                if (page := _archive_page_number(name, self._filename_prefix))
                is not None
            }
            numbers = selection or tuple(PageNumber(page) for page in sorted(members))
            for number in numbers:
                member = members.get(number.value)
                if member is None:
                    raise ValueError(f"ZIP does not contain page {number.value}.")
                image_path = self._temporary / f"{number.value}.jpg"
                image_path.write_bytes(archive.read(member))
                yield SourcePage(number, image_path)


def _archive_page_number(name: str, filename_prefix: str | None) -> int | None:
    suffix = Path(name).suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        return None
    pattern = (
        rf"{re.escape(filename_prefix)}(\d{{3}})$"
        if filename_prefix is not None
        else r"(\d{3})$"
    )
    matched = re.search(pattern, Path(name).stem)
    return int(matched.group(1)) if matched else None
