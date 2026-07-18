"""PDF page source with ZIP, text, and render priority."""

from collections.abc import Mapping
from pathlib import Path
from typing import Final

import fitz

from adapters.source.zip import ZipSource
from domain.content import ImagePage, PageNumber, SourceKind, SourcePage, TextPage
from domain.document import Document
from domain.errors import PageNotAvailableError

_INVISIBLE_TEXT_RENDER_MODE: Final = 3
_OCR_PRODUCER_MARKERS: Final = ("abbyy", "ocrmypdf", "tesseract")
_PAGE_IMAGE_COVERAGE_THRESHOLD: Final = 0.9


class PdfSource:
    """Acquire each PDF page from the best available local source."""

    def __init__(self, zip_source: ZipSource | None = None) -> None:
        """Create a PDF source with an optional sidecar ZIP reader."""
        self._zip_source: ZipSource = zip_source or ZipSource()

    def read(
        self,
        document: Document,
        pages: tuple[PageNumber, ...],
    ) -> tuple[SourcePage, ...]:
        """Return requested pages in their requested order."""
        with fitz.open(document.path) as pdf:
            return tuple(self._read_page(pdf, document.path, page) for page in pages)

    def _read_page(
        self,
        pdf: fitz.Document,
        path: Path,
        page_number: PageNumber,
    ) -> SourcePage:
        if page_number < 1 or page_number > pdf.page_count:
            raise PageNotAvailableError(page_number)
        zip_page = self._zip_source.read_page(path.with_suffix(".zip"), page_number)
        if zip_page is not None:
            return ImagePage(
                page=zip_page.page,
                image=zip_page.image,
                media_type=zip_page.media_type,
                source=zip_page.source,
            )
        page = pdf.load_page(page_number - 1)
        image = _embedded_image(pdf, page)
        text = page.get_text("text")
        if text.strip() and not _has_scanned_ocr_overlay(pdf, page):
            return TextPage(page=page_number, text=text)
        if image is not None:
            image_bytes, media_type = image
            return ImagePage(
                page=page_number,
                image=image_bytes,
                media_type=media_type,
                source=SourceKind.PDF_IMAGE,
            )
        return ImagePage(
            page=page_number,
            image=page.get_pixmap(dpi=300).tobytes("png"),
            media_type="image/png",
            source=SourceKind.PDF_RENDER,
        )


def _has_scanned_ocr_overlay(pdf: fitz.Document, page: fitz.Page) -> bool:
    if not (_has_invisible_text(page) or _is_ocr_producer(pdf.metadata)):
        return False
    return _has_full_page_image(page)


def _has_invisible_text(page: fitz.Page) -> bool:
    traces = page.get_texttrace()
    return bool(traces) and all(
        trace["type"] == _INVISIBLE_TEXT_RENDER_MODE for trace in traces
    )


def _is_ocr_producer(metadata: Mapping[str, str | None] | None) -> bool:
    values = metadata or {}
    provenance = " ".join(
        (values.get("creator") or "", values.get("producer") or "")
    ).lower()
    return any(marker in provenance for marker in _OCR_PRODUCER_MARKERS)


def _has_full_page_image(page: fitz.Page) -> bool:
    page_area = page.rect.width * page.rect.height
    return any(
        image_rect.width * image_rect.height
        >= page_area * _PAGE_IMAGE_COVERAGE_THRESHOLD
        for image_reference in page.get_images(full=True)
        for image_rect in page.get_image_rects(image_reference[0])
    )


def _embedded_image(
    pdf: fitz.Document,
    page: fitz.Page,
) -> tuple[bytes, str] | None:
    images: list[tuple[bytes, str, int]] = []
    for image_reference in page.get_images(full=True):
        has_page_coverage = any(
            image_rect.width * image_rect.height
            >= page.rect.width * page.rect.height * _PAGE_IMAGE_COVERAGE_THRESHOLD
            for image_rect in page.get_image_rects(image_reference[0])
        )
        if not has_page_coverage:
            continue
        image = pdf.extract_image(image_reference[0])
        match (
            image.get("image"),
            image.get("ext"),
            image.get("width"),
            image.get("height"),
        ):
            case (
                bytes() as image_bytes,
                str() as extension,
                int() as width,
                int() as height,
            ) if (media_type := _media_type(extension)) is not None:
                images.append((image_bytes, media_type, width * height))
            case _:
                continue
    if not images:
        return None
    image_bytes, media_type, _ = max(images, key=lambda image: image[2])
    return image_bytes, media_type


def _media_type(extension: str) -> str | None:
    match extension.lower():
        case "jpg" | "jpeg":
            return "image/jpeg"
        case "png":
            return "image/png"
        case _:
            return None
