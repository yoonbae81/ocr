from __future__ import annotations

from base64 import b64decode
from pathlib import Path
from struct import pack
from typing import Self
from warnings import catch_warnings, simplefilter
from zipfile import ZIP_DEFLATED, ZipFile
from zlib import compress, crc32, decompress

import fitz
import pytest

from adapters.source.image import ImageSource
from adapters.source.pdf import PdfSource
from adapters.source.zip import ZipSource
from domain.content import ImagePage, PageNumber, SourceKind, TextPage
from domain.document import Document
from domain.errors import PageNotAvailableError


def _pdf(
    path: Path,
    pages: tuple[str, ...],
) -> None:
    document = fitz.open()
    for text in pages:
        page = document.new_page()
        if text:
            _ = page.insert_text((72, 72), text)
    document.save(path)
    document.close()


def _png_bytes() -> bytes:
    return b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAAC0lEQVR4nGP4DwQACfsD/fteaysAAAAASUVORK5CYII="
    )


def _image_pdf(path: Path, images: tuple[bytes, ...]) -> None:
    document = fitz.open()
    page = document.new_page()
    for image in images:
        _ = page.insert_image(page.rect, stream=image)
    document.save(path)
    document.close()


def _opaque_png(width: int, height: int) -> bytes:
    header = pack(
        ">IIBBBBB",
        width,
        height,
        8,
        6,
        0,
        0,
        0,
    )
    pixels = b"".join(b"\x00" + b"\xff\xff\xff\xff" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", header)
        + _png_chunk(b"IDAT", compress(pixels))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, value: bytes) -> bytes:
    return pack(">I", len(value)) + kind + value + pack(">I", crc32(kind + value))


def test_png_fixture_decodes_to_an_opaque_white_pixel() -> None:
    # Given: the image fixture used by source and CLI integration tests.
    png = _png_bytes()
    idat_size = int.from_bytes(png[33:37], byteorder="big")

    # When: its IDAT payload is decompressed.
    pixels = decompress(png[41 : 41 + idat_size])

    # Then: the fixture encodes an opaque white pixel with a PNG filter byte.
    assert pixels == b"\x00\xff\xff\xff\xff"


def test_image_source_returns_the_input_as_logical_page_one(tmp_path: Path) -> None:
    # Given
    image_path = tmp_path / "scan.png"
    image_bytes = _png_bytes()
    _ = image_path.write_bytes(image_bytes)

    # When
    pages = ImageSource().read(Document(image_path), (PageNumber(1),))

    # Then
    assert pages == (
        ImagePage(
            page=PageNumber(1),
            image=image_bytes,
            media_type="image/png",
            source=SourceKind.IMAGE,
        ),
    )


def test_zip_source_when_nested_sequential_image_names_are_requested_uses_logical_pages(
    tmp_path: Path,
) -> None:
    # Given: an archive whose source prefix precedes three-digit logical pages.
    archive_path = tmp_path / "발전공학.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("발전공학/510006.jpg", b"six")
        archive.writestr("발전공학/510005.jpg", b"five")

    # When: logical pages are read in caller order from the ZIP document.
    pages = ZipSource().read(Document(archive_path), (PageNumber(5), PageNumber(6)))

    # Then: the numeric suffix, not the whole archive filename, identifies pages.
    assert tuple(page.page for page in pages) == (PageNumber(5), PageNumber(6))
    assert tuple(page.image for page in pages) == (b"five", b"six")


def test_zip_source_when_page_number_has_four_digits_preserves_all_digits(
    tmp_path: Path,
) -> None:
    # Given: an archive entry whose logical page number has four digits.
    archive_path = tmp_path / "large-book.zip"
    with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("pages/page-1000.png", b"thousand")

    # When: the four-digit logical page is requested.
    pages = ZipSource().read(Document(archive_path), (PageNumber(1000),))

    # Then: the complete suffix is used as the page number.
    assert pages[0].page == PageNumber(1000)
    assert pages[0].image == b"thousand"


def test_zip_source_when_duplicate_names_exist_reads_the_validated_entry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: duplicate archive names whose later entry exceeds the image limit.
    archive_path = tmp_path / "duplicate.zip"
    with catch_warnings():
        simplefilter("ignore", UserWarning)
        with ZipFile(archive_path, "w", ZIP_DEFLATED) as archive:
            archive.writestr("page-001.png", b"ok")
            archive.writestr("page-001.png", b"too-large")
    monkeypatch.setattr("adapters.source.zip.MAX_IMAGE_BYTES", 2)

    # When: the logical page is read.
    page = ZipSource().read(Document(archive_path), (PageNumber(1),))[0]

    # Then: the bytes belong to the validated first ZipInfo rather than its duplicate.
    assert page.image == b"ok"


def test_pdf_source_prefers_sidecar_zip_images_over_pdf_text(tmp_path: Path) -> None:
    # Given
    pdf_path = tmp_path / "book.pdf"
    _pdf(pdf_path, ("pdf page one", "pdf page two"))
    with ZipFile(tmp_path / "book.zip", "w", ZIP_DEFLATED) as archive:
        archive.writestr("001.png", _png_bytes())
        archive.writestr("002.png", _png_bytes())

    # When
    pages = PdfSource().read(Document(pdf_path), (PageNumber(2), PageNumber(1)))

    # Then
    assert tuple(page.source for page in pages) == (SourceKind.ZIP, SourceKind.ZIP)
    assert tuple(page.page for page in pages) == (PageNumber(2), PageNumber(1))
    assert tuple(page.chapter for page in pages) == (None, None)


def test_pdf_source_uses_nonblank_text_when_no_zip_image_exists(tmp_path: Path) -> None:
    # Given
    pdf_path = tmp_path / "text.pdf"
    _pdf(pdf_path, ("available text",))

    # When
    pages = PdfSource().read(Document(pdf_path), (PageNumber(1),))

    # Then
    assert pages == (
        TextPage(
            page=PageNumber(1),
            text="available text\n",
            source=SourceKind.PDF_TEXT,
        ),
    )


def test_pdf_source_ignores_invisible_ocr_text_over_a_full_page_scan(
    tmp_path: Path,
) -> None:
    # Given: a full-page scan with a separate app's invisible OCR text overlay.
    pdf_path = tmp_path / "ocr-overlay.pdf"
    scan = _opaque_png(1000, 1000)
    document = fitz.open()
    page = document.new_page()
    _ = page.insert_image(page.rect, stream=scan)
    _ = page.insert_text((10, 10), "mistaken OCR", render_mode=3)
    document.save(pdf_path)
    document.close()

    # When: the source selects the best input for recognition.
    pages = PdfSource().read(Document(pdf_path), (PageNumber(1),))

    # Then: the scan, not its inaccurate text layer, is sent to PaddleOCR.
    assert isinstance(pages[0], ImagePage)
    assert pages[0].source is SourceKind.PDF_IMAGE


def test_pdf_source_ignores_visible_ocr_text_from_abbyy_over_a_full_page_scan(
    tmp_path: Path,
) -> None:
    # Given: ABBYY FineReader's scan and its visible OCR layer.
    pdf_path = tmp_path / "abbyy-overlay.pdf"
    document = fitz.open()
    page = document.new_page()
    _ = page.insert_image(page.rect, stream=_opaque_png(1000, 1000))
    _ = page.insert_text((10, 10), "mistaken OCR")
    document.set_metadata(
        {"creator": "ABBYY FineReader 15", "producer": "ABBYY FineReader 15"},
    )
    document.save(pdf_path)
    document.close()

    # When: the source selects the best input for recognition.
    pages = PdfSource().read(Document(pdf_path), (PageNumber(1),))

    # Then: the original scan is used instead of ABBYY's OCR layer.
    assert isinstance(pages[0], ImagePage)
    assert pages[0].source is SourceKind.PDF_IMAGE


def test_pdf_source_uses_visible_native_text_over_a_full_page_image(
    tmp_path: Path,
) -> None:
    # Given: a document-export page with a visual background and native text.
    pdf_path = tmp_path / "export.pdf"
    document = fitz.open()
    page = document.new_page()
    _ = page.insert_image(page.rect, stream=_opaque_png(1000, 1000))
    _ = page.insert_text((10, 10), "authoritative source text")
    document.save(pdf_path)
    document.close()

    # When: the source selects the best input for recognition.
    pages = PdfSource().read(Document(pdf_path), (PageNumber(1),))

    # Then: visible, native text remains preferable to re-recognition.
    assert pages == (
        TextPage(
            page=PageNumber(1),
            text="authoritative source text\n",
            source=SourceKind.PDF_TEXT,
        ),
    )


def test_pdf_source_uses_the_largest_embedded_original_image_before_rendering(
    tmp_path: Path,
) -> None:
    # Given: a scanned PDF page with an embedded original PNG and no text layer.
    pdf_path = tmp_path / "scan.pdf"
    small_image = _opaque_png(1, 1)
    large_image = _opaque_png(2, 2)
    _image_pdf(pdf_path, (small_image, large_image))
    with fitz.open(pdf_path) as pdf:
        source_page = pdf.load_page(0)
        image_xref = max(
            source_page.get_images(full=True),
            key=lambda entry: entry[2] * entry[3],
        )[0]
        expected_image = pdf.extract_image(image_xref)["image"]

    # When: the page is acquired without a sidecar ZIP.
    pages = PdfSource().read(Document(pdf_path), (PageNumber(1),))

    # Then: the PDF image is returned directly, rather than a rendered substitute.
    assert pages == (
        ImagePage(
            page=PageNumber(1),
            image=expected_image,
            media_type="image/png",
            source=SourceKind.PDF_IMAGE,
        ),
    )


def test_pdf_source_renders_a_page_without_text(tmp_path: Path) -> None:
    # Given
    pdf_path = tmp_path / "scan.pdf"
    _pdf(pdf_path, ("",))

    # When
    pages = PdfSource().read(Document(pdf_path), (PageNumber(1),))

    # Then
    assert isinstance(pages[0], ImagePage)
    assert pages[0].source is SourceKind.PDF_RENDER
    assert pages[0].media_type == "image/png"
    assert pages[0].image.startswith(b"\x89PNG")


def test_pdf_source_renders_a_page_at_300_dpi_when_no_other_source_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Given: a PDF page without ZIP, text, or embedded image content.
    render_dpi: list[int] = []

    class Pixmap:
        def tobytes(self, _output: str) -> bytes:
            return b"rendered"

    class Page:
        def get_text(self, _option: str) -> str:
            return ""

        def get_images(self, *, full: bool) -> list[tuple[int]]:
            assert full is True
            return []

        def get_pixmap(self, *, dpi: int) -> Pixmap:
            render_dpi.append(dpi)
            return Pixmap()

    class Pdf:
        page_count: int = 1

        def __enter__(self) -> Self:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def load_page(self, page_id: int) -> Page:
            assert page_id == 0
            return Page()

        def extract_image(self, _xref: int) -> dict[str, bytes | str]:
            return {"image": b"", "ext": "png"}

    def open_pdf(_path: Path) -> Pdf:
        return Pdf()

    monkeypatch.setattr("adapters.source.pdf.fitz.open", open_pdf)

    # When: the page falls through to rendering.
    pages = PdfSource().read(Document(Path("scan.pdf")), (PageNumber(1),))

    # Then: rasterization is the final 300 DPI fallback.
    assert isinstance(pages[0], ImagePage)
    assert pages[0].image == b"rendered"
    assert render_dpi == [300]


def test_pdf_source_rejects_a_page_outside_the_document(tmp_path: Path) -> None:
    # Given
    pdf_path = tmp_path / "single.pdf"
    _pdf(pdf_path, ("one",))

    # When
    with pytest.raises(PageNotAvailableError, match="page 2 is not available"):
        _ = PdfSource().read(Document(pdf_path), (PageNumber(2),))
