"""Sidecar ZIP image page source."""

import re
from pathlib import Path
from zipfile import ZipFile

from domain.content import ImagePage, PageNumber, SourceKind
from domain.document import Document
from domain.errors import (
    ArchiveImageSizeLimitError,
    ArchiveSizeLimitError,
    PageNotAvailableError,
)

MAX_ARCHIVE_ENTRIES = 10_000
MAX_IMAGE_BYTES = 64 * 1024 * 1024


class ZipSource:
    """Read logical image pages from a ZIP archive or a PDF sidecar ZIP."""

    def read(
        self,
        document: Document,
        pages: tuple[PageNumber, ...],
    ) -> tuple[ImagePage, ...]:
        """Return all requested ZIP image pages."""
        return tuple(
            self.require_page(document.path.with_suffix(".zip"), page) for page in pages
        )

    def read_page(self, archive_path: Path, page: PageNumber) -> ImagePage | None:
        """Return a matching image page when present in an archive."""
        if not archive_path.is_file():
            return None
        with ZipFile(archive_path) as archive:
            _validate_archive(archive)
            for info in archive.infolist():
                name = info.filename
                entry = Path(name)
                if _page_number(entry) != page:
                    continue
                media_type = _media_type(entry)
                if media_type is not None:
                    if info.file_size > MAX_IMAGE_BYTES:
                        raise ArchiveImageSizeLimitError(
                            name=name,
                            limit=MAX_IMAGE_BYTES,
                        )
                    with archive.open(info) as image_file:
                        image = image_file.read(MAX_IMAGE_BYTES + 1)
                    if len(image) > MAX_IMAGE_BYTES:
                        raise ArchiveImageSizeLimitError(
                            name=name,
                            limit=MAX_IMAGE_BYTES,
                        )
                    return ImagePage(
                        page=page,
                        image=image,
                        media_type=media_type,
                        source=SourceKind.ZIP,
                    )
        return None

    def available_pages(self, archive_path: Path) -> frozenset[PageNumber]:
        """Return all image-backed logical pages present in an archive."""
        if not archive_path.is_file():
            return frozenset()
        with ZipFile(archive_path) as archive:
            _validate_archive(archive)
            return frozenset(
                page
                for info in archive.infolist()
                if _media_type(Path(info.filename)) is not None
                if (page := _page_number(Path(info.filename))) is not None
            )

    def require_page(self, archive_path: Path, page: PageNumber) -> ImagePage:
        """Return a ZIP page or report its absence."""
        image = self.read_page(archive_path, page)
        if image is None:
            raise PageNotAvailableError(page)
        return image


def _page_number(entry: Path) -> PageNumber | None:
    match = re.search(r"(?P<page>\d+)$", entry.stem)
    if match is None:
        return None
    digits = match.group("page")
    prefix = entry.stem[: match.start()]
    page = digits if prefix.endswith(("-", "_", " ")) else digits[-3:]
    return PageNumber(int(page))


def _media_type(entry: Path) -> str | None:
    match entry.suffix.lower():
        case ".jpg" | ".jpeg":
            return "image/jpeg"
        case ".png":
            return "image/png"
        case _:
            return None


def _validate_archive(archive: ZipFile) -> None:
    if len(archive.infolist()) > MAX_ARCHIVE_ENTRIES:
        raise ArchiveSizeLimitError(limit=MAX_ARCHIVE_ENTRIES)
