"""PDF source adapter for rendered page extraction."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

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
