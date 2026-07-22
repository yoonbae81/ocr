"""Recognition ports used by the OCR application."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Protocol

from domain import PageMarkdown, SourcePage


class PageRecognizer(Protocol):
    """Recognize rendered pages without exposing a concrete inference engine."""

    def recognize_many(
        self, pages: tuple[SourcePage, ...]
    ) -> Iterator[PageMarkdown]:
        """Recognize a bounded page batch in input order."""
        ...


class RecognitionBackend(Protocol):
    """Lazily provide a shared recognizer and its cache identity."""

    @property
    def cache_namespace(self) -> str:
        """Return a stable identity for result-affecting backend settings."""
        ...

    def get_recognizer(self) -> PageRecognizer:
        """Initialize the backend on first use and reuse it afterward."""
        ...
