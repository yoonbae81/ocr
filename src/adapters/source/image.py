"""Image-file page source."""

from pathlib import Path

from domain.content import ImagePage, PageNumber, SourceKind
from domain.document import Document
from domain.errors import (
    ImageSizeLimitError,
    PageNotAvailableError,
    UnsupportedDocumentError,
)

MAX_IMAGE_BYTES = 64 * 1024 * 1024


class ImageSource:
    """Read a standalone image as logical page one."""

    def read(
        self,
        document: Document,
        pages: tuple[PageNumber, ...],
    ) -> tuple[ImagePage, ...]:
        """Return requested image pages."""
        return tuple(self._read_page(document.path, page) for page in pages)

    def _read_page(self, path: Path, page: PageNumber) -> ImagePage:
        if page != PageNumber(1):
            raise PageNotAvailableError(page)
        image = path.read_bytes()
        if len(image) > MAX_IMAGE_BYTES:
            raise ImageSizeLimitError(path=path, limit=MAX_IMAGE_BYTES)
        return ImagePage(
            page=page,
            image=image,
            media_type=_media_type(path),
            source=SourceKind.IMAGE,
        )


def _media_type(path: Path) -> str:
    match path.suffix.lower():
        case ".jpg" | ".jpeg":
            return "image/jpeg"
        case ".png":
            return "image/png"
        case _:
            raise UnsupportedDocumentError(path)
