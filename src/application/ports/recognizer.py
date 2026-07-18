"""Image recognition contract."""

from typing import Protocol

from domain.content import ImagePage


class RecognizerPort(Protocol):
    """Recognize one page image using a configured model."""

    def recognize(self, page: ImagePage, prompt: str) -> str:
        """Return the page transcription."""
        ...
