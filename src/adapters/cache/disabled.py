"""Disabled recognition-cache adapter."""

from domain import PageMarkdown, SourcePage


class DisabledRecognitionCache:
    """Provide the cache port while explicitly disabling persistence."""

    def load(self, page: SourcePage) -> None:
        """Return a cache miss for every rendered page."""
        del page

    def store(self, result: PageMarkdown) -> None:
        """Discard a recognition result without persistence."""
        del result
