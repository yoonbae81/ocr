"""Structured page and document content."""

from dataclasses import dataclass
from enum import StrEnum
from typing import NewType

PageNumber = NewType("PageNumber", int)


class SourceKind(StrEnum):
    """The source selected for a document page."""

    IMAGE = "image"
    ZIP = "zip"
    PDF_TEXT = "pdf_text"
    PDF_IMAGE = "pdf_image"
    PDF_RENDER = "pdf_render"


@dataclass(frozen=True, slots=True)
class TextPage:
    """A page obtained from an existing text layer."""

    page: PageNumber
    text: str
    source: SourceKind = SourceKind.PDF_TEXT


@dataclass(frozen=True, slots=True)
class ImagePage:
    """A page image that requires model recognition."""

    page: PageNumber
    image: bytes
    media_type: str
    source: SourceKind


type SourcePage = TextPage | ImagePage


@dataclass(frozen=True, slots=True)
class PageContent:
    """Recognized content for one page, independent of output format."""

    page: PageNumber
    body: str
