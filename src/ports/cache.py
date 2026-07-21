"""Port for reusing raw page-recognition results."""

from typing import Protocol

from domain import PageMarkdown, SourcePage


class RecognitionCache(Protocol):
    """Caches recognizer output before output-format postprocessing."""

    def load(self, page: SourcePage) -> PageMarkdown | None:
        """Return a matching raw result when available."""
        ...

    def store(self, result: PageMarkdown) -> None:
        """Persist a raw recognition result."""
        ...
