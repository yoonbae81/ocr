"""Input and recognition ports for the OCR application."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from domain import PageMarkdown, SourcePage


class PageRecognizer(Protocol):
    """Recognizes rendered pages through the document pipeline."""

    def recognize_many(
        self, pages: tuple[SourcePage, ...]
    ) -> Iterator[PageMarkdown]:
        """Recognize a bounded page batch in input order."""
        ...
