"""Raster image source adapter for OCR input."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from shutil import copyfile

from domain import PageNumber, SourcePage


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
