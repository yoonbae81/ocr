"""ZIP source adapter for image-page archives."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from zipfile import ZipFile

import re

from domain import PageNumber, SourcePage


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
